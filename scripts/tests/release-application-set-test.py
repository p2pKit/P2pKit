#!/usr/bin/env python3
"""Synthetic frozen-set lifecycle tests; no network, native tools or real artifacts."""

import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import unittest
from unittest import mock
import zipfile


SPEC = importlib.util.spec_from_file_location("sample_release_fixtures", Path(__file__).with_name("publish-sample-release-test.py"))
SUPPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUPPORT)
F, P = SUPPORT.F, SUPPORT.R


class FrozenApplicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = SUPPORT.ReleaseTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.addCleanup(self.fixture.tearDown)
        self.api, self.base = self.fixture.api, self.fixture.base
        self.plan = self.fixture.prepared(self.fixture.plan())
        self.invocation = F.invocation_fields(self.plan["mavenPublication"])
        self.binding = self.plan["frozenApplicationSet"]
        with zipfile.ZipFile(io.BytesIO(self.api.files[9001])) as archive:
            self.raw = archive.read(F.FILE)
        self.document = P.parsed(self.raw)

    def load(self, **options):
        return F.load(self.api, self.invocation, self.base, **options)

    def running(self):
        self.api.data["/actions/runs/900"].update(status="in_progress", conclusion=None)
        self.api.collections["/actions/runs/900/artifacts"] = []

    def replace_record(self, raw=None, extra=None):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as archive:
            archive.writestr(zipfile.ZipInfo(F.FILE), self.raw if raw is None else raw)
            if extra:
                archive.writestr(extra, b"unapproved synthetic bytes")
        binary = stream.getvalue()
        self.api.files[9001] = binary
        self.api.data["/actions/artifacts/9001"].update(size_in_bytes=len(binary), digest="sha256:" + hashlib.sha256(binary).hexdigest())

    def test_load_binds_original_tag_run_and_all_eight_main_originals(self):
        document, binding = self.load(artifact_id=9001, expected_hash=self.binding["sha256"])
        self.assertEqual(self.document, document)
        self.assertEqual(self.binding["artifact"], binding["artifact"])
        self.assertEqual(SUPPORT.SOURCE, document["qualification"]["source"]["commit"])
        self.assertEqual(SUPPORT.TREE, document["qualification"]["source"]["tree"])
        self.assertEqual(SUPPORT.VERSION, document["qualification"]["versionBinding"]["canonicalVersion"])
        self.assertEqual(8, len(document["qualification"]["artifacts"] + document["qualification"]["evidence"]))
        self.assertEqual(["android", "linux", "windows", "macos"], [x["platform"] for x in document["packages"]])
        self.assertFalse(self.api.mutations)

    def test_preflight_admits_running_tag_attempt_without_circular_publication_success(self):
        self.running()
        self.assertEqual(self.invocation, P.maven_invocation(self.api, SUPPORT.SOURCE, 900, 1, completed=False))
        with self.assertRaises(ValueError):
            P.maven_publication(self.api, SUPPORT.SOURCE, 900, 1)
        document = F.freeze(self.api, self.invocation, self.base)
        self.assertEqual(self.document["packages"], document["packages"])
        self.assertEqual(self.document["qualification"], document["qualification"])
        self.assertEqual(SUPPORT.EXPIRES, document["expiresAt"])
        self.assertFalse(list(self.base.glob("original-*.zip")))
        self.assertFalse(self.api.mutations)

    def test_preflight_does_not_replace_an_existing_attempt_set(self):
        self.api.data["/actions/runs/900"].update(status="in_progress", conclusion=None)
        with mock.patch.object(self.api, "download") as transfer, self.assertRaises(ValueError):
            F.freeze(self.api, self.invocation, self.base)
        transfer.assert_not_called()

    def test_preflight_revalidates_changed_gate_after_the_original_downloads(self):
        self.running()
        download = self.api.download
        def changed(artifact, path):
            download(artifact, path)
            if artifact["id"] == 4:
                self.api.collections[f"/commits/{SUPPORT.SOURCE}/check-runs?filter=all"][0]["conclusion"] = "failure"
        self.api.download = changed
        with self.assertRaises(ValueError):
            F.freeze(self.api, self.invocation, self.base)
        self.assertFalse(self.api.mutations)

    def test_preflight_rejects_differing_or_oversized_notices_before_maven(self):
        self.running()
        for payload, reason in ((b"different public notice", "notices differ"), (b"x" * (P.MIB + 1), "Oversized public notice")):
            raw = self.fixture.bundle("linux", "x64", extra={"licenses/P2pKit-LICENSE": payload})
            self.api.files[2] = raw
            self.api.collections["/actions/runs/300/artifacts"][1].update(
                size_in_bytes=len(raw), digest="sha256:" + hashlib.sha256(raw).hexdigest())
            with self.subTest(reason=reason), self.assertRaisesRegex(ValueError, reason):
                F.freeze(self.api, self.invocation, self.base)
            self.assertFalse(self.api.mutations)

    def test_main_artifacts_are_not_relabelled_as_tag_artifacts(self):
        item = self.api.data["/actions/artifacts/9001"]
        with self.assertRaises(ValueError):
            P.artifact_identity(item, 900, SUPPORT.SOURCE)
        item["workflow_run"]["head_branch"] = "main"
        with self.assertRaises(ValueError):
            self.load(artifact_id=9001, expected_hash=self.binding["sha256"])

    def test_changed_json_hash_and_wrong_attempt_cannot_be_selected(self):
        with self.assertRaises(ValueError):
            self.load(artifact_id=9001, expected_hash="0" * 64)
        self.api.data["/actions/artifacts/9001"]["name"] = "release-application-set-900-2"
        with self.assertRaises(ValueError):
            self.load(artifact_id=9001, expected_hash=self.binding["sha256"])

    def test_missing_or_ambiguous_frozen_sets_never_choose_latest(self):
        path = "/actions/runs/900/artifacts"
        original = copy.deepcopy(self.api.collections[path])
        for rows in ([], original + original):
            self.api.collections[path] = rows
            with self.subTest(count=len(rows)), self.assertRaises(ValueError):
                self.load()

    def test_unapproved_members_duplicate_keys_and_noncanonical_json_refuse(self):
        for raw, extra in ((None, "private-original.log"), (b'{"schema":1,"schema":1}', None),
                           (json.dumps(self.document).encode(), None)):
            self.replace_record(raw, extra)
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.load(artifact_id=9001, expected_hash=self.binding["sha256"])

    def test_record_cannot_renew_original_evidence_retention(self):
        # Frozen metadata expires Oct4; original main evidence still ends Sep29.
        self.assertGreater(P.timestamp(self.binding["artifact"]["expires_at"]), P.timestamp(self.document["expiresAt"]))
        with mock.patch.object(P.time, "time", return_value=P.timestamp(SUPPORT.EXPIRES) - F.MAVEN_HEADROOM):
            with self.assertRaises(ValueError):
                self.load(remaining_seconds=F.MAVEN_HEADROOM)
        changed = copy.deepcopy(self.document)
        changed["expiresAt"] = self.binding["artifact"]["expires_at"]
        with self.assertRaises(ValueError):
            F.eligibility(changed, F.DELIVERY_HEADROOM)

    def test_original_stage_job_must_succeed_with_exact_source_and_window(self):
        job = self.api.collections["/actions/runs/900/attempts/1/jobs"][0]
        original = copy.deepcopy(job)
        for change in ({"status": "in_progress"}, {"conclusion": "failure"}, {"head_sha": SUPPORT.HEAD},
                       {"run_attempt": 2}, {"started_at": "2026-09-20T15:01:00Z"},
                       {"completed_at": "2026-09-20T14:59:59Z"}):
            job.clear(); job.update({**original, **change})
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.load()

    def test_exact_owner_approval_is_required_and_no_self_generated_record_is_authority(self):
        key = "/actions/runs/900/approvals"
        original = copy.deepcopy(self.api.data[key][0])
        for changes in ({"user": {**SUPPORT.OWNER, "id": 1}}, {"comment": "approved"}, {"state": "rejected"},
                        {"comment": original["comment"].replace("900/1", "900/2")},
                        {"environments": [{"id": 600, "name": P.ENVIRONMENT}]}):
            self.api.data[key] = [{**original, **changes}]
            with self.subTest(change=changes), self.assertRaises(ValueError):
                F.require_approval(self.api, self.document, self.binding)
        for rows in ([], [original, original]):
            self.api.data[key] = rows
            with self.assertRaises(ValueError):
                F.require_approval(self.api, self.document, self.binding)
        self.assertFalse(self.api.mutations)

    def test_changed_original_evidence_digest_after_approval_prevents_delivery(self):
        self.api.collections["/actions/runs/200/artifacts"][0]["digest"] = "sha256:" + "b" * 64
        with self.assertRaises(ValueError):
            P.revalidate_plan(self.api, self.plan)
        self.assertFalse(self.api.mutations)

    def test_changed_protected_environment_is_not_silently_accepted(self):
        self.api.data["/environments/maven-central"]["can_admins_bypass"] = True
        with self.assertRaises(ValueError):
            self.load()
        self.assertFalse(self.api.mutations)

    def test_successful_historical_attempt_is_not_replaced_by_a_failed_new_attempt(self):
        original = copy.deepcopy(self.api.data["/actions/runs/900"])
        self.api.data["/actions/runs/900/attempts/1"] = original
        self.api.data["/actions/runs/900"].update(run_attempt=2, conclusion="failure")
        self.assertEqual(self.plan["mavenPublication"], P.maven_publication(self.api, SUPPORT.SOURCE, 900, 1))
        with self.assertRaises(ValueError):
            P.maven_publication(self.api, SUPPORT.SOURCE, 900, 2)
        P.revalidate_plan(self.api, self.plan)
        self.assertFalse(self.api.mutations)

    def test_tag_context_is_distinct_from_main_or_pr_even_for_the_same_source(self):
        env = {**SUPPORT.hosted_env(), "GITHUB_REF": "refs/tags/v" + SUPPORT.VERSION, "GITHUB_REF_NAME": "v" + SUPPORT.VERSION,
            "GITHUB_EVENT_NAME": "push", "GITHUB_JOB": "freeze-applications", "GITHUB_RUN_ID": "900",
            "GITHUB_WORKFLOW_REF": P.REPO + "/" + P.MAVEN_WORKFLOW + "@refs/tags/v" + SUPPORT.VERSION}
        self.assertEqual(900, F.hosted_context(env, "freeze")["id"])
        for change in ({"GITHUB_REF": "refs/heads/main"}, {"GITHUB_EVENT_NAME": "pull_request"},
                       {"GITHUB_JOB": "publish-release"}, {"GITHUB_REPOSITORY": "fork/P2pKit"},
                       {"GITHUB_WORKFLOW_SHA": SUPPORT.HEAD}, {"GITHUB_RUN_ATTEMPT": "0"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                F.hosted_context({**env, **change}, "freeze")


if __name__ == "__main__":
    unittest.main(failfast=True)
