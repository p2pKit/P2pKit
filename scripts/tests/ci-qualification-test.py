#!/usr/bin/env python3
"""Synthetic original API/artifact fixtures; no service or private evidence."""
import copy
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock
import zipfile

SPEC = importlib.util.spec_from_file_location("qualification", Path(__file__).parents[1] / "ci_qualification.py")
Q = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(Q)
SOURCE, TREE, VERSION = "1" * 40, "2" * 40, "0.8.0-rc1"
NOW = Q.timestamp("2026-09-20T15:00:00Z")
CREATED, EXPIRES = "2026-09-15T10:15:00Z", "2026-09-29T10:15:00Z"


def zip_bytes(files):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, raw in files.items():
            archive.writestr(name, raw)
    return output.getvalue()


class Api:
    def __init__(self):
        self.data, self.collections, self.files = {}, {}, {}
    def json(self, path):
        return copy.deepcopy(self.data[path])
    def pages(self, path, key=None):
        return copy.deepcopy(self.collections[path])
    def download(self, artifact, path):
        with path.open("xb") as stream:
            stream.write(self.files[artifact["id"]])


class Fixture:
    def __init__(self, api=None):
        self.api = api or Api()
        a = self.api
        self.run = {"id": 300, "run_attempt": 1, "path": Q.WORKFLOW, "head_sha": SOURCE,
                    "event": "push", "head_branch": "main", "workflow_id": 77,
                    "repository": {"full_name": Q.REPOSITORY}, "head_repository": {"full_name": Q.REPOSITORY},
                    "status": "completed", "conclusion": "failure"}
        a.data["/actions/runs/300"] = self.run
        a.data["/actions/runs/300/attempts/1"] = self.run
        a.data["/actions/workflows/ci.yml"] = {"id": 77, "path": Q.WORKFLOW}
        a.data["/git/commits/" + SOURCE] = {"sha": SOURCE, "tree": {"sha": TREE}, "parents": []}
        a.collections["/actions/workflows/ci.yml/runs?branch=main&head_sha=" + SOURCE] = [self.run]
        self.jobs = [{"id": 10000 + i, "name": component + " / Execute component", "run_id": 300,
                      "run_attempt": 1, "head_sha": SOURCE, "status": "completed", "conclusion": "success",
                      "runner_id": 50 + i, "labels": [Q.RUNNERS[component]],
                      "started_at": "2026-09-15T10:01:00Z", "completed_at": "2026-09-15T10:20:00Z"}
                     for i, component in enumerate(Q.COMPONENTS)]
        self.jobs.append({**self.jobs[0], "id": 10100, "name": Q.QUALIFY_JOB,
                          "started_at": "2026-09-15T10:21:00Z", "completed_at": "2026-09-15T10:30:00Z"})
        a.collections["/actions/runs/300/attempts/1/jobs"] = self.jobs
        a.collections["/actions/runs/300/jobs?filter=all"] = list(self.jobs)
        self.artifacts = a.collections["/actions/runs/300/artifacts"] = []
        self.manifests = {}
        for i, (component, (platform, arch)) in enumerate(Q.COMPONENTS.items()):
            cipher = b"SYNTHETIC CIPHERTEXT NOT PRIVATE EVIDENCE:" + component.encode()
            manifest = {"schema": 1, "component": component, "source": {"commit": SOURCE, "tree": TREE, "version": VERSION},
                        "github": {"repository": Q.REPOSITORY, "runId": "300", "runAttempt": "1",
                                   "workflowPath": Q.WORKFLOW, "workflowSha": SOURCE, "jobId": "run"},
                        "host": {"platform": platform, "arch": arch, "runnerEnvironment": "github-hosted"},
                        "timing": {"startedAt": "2026-09-15T10:02:00Z", "completedAt": "2026-09-15T10:14:00Z"},
                        "tools": {"python": {"version": "3.12", "executableSha256": "a" * 64}},
                        "command": {"sha256": "b" * 64},
                        "outcome": {"exitCode": 0, "timedOut": False, "cleanupKnown": True, "stage": "COMMAND", "code": "PASS"},
                        "privateArchive": {"sha256": "c" * 64, "bytes": 100}, "reports": [],
                        "ciphertext": {"sha256": hashlib.sha256(cipher).hexdigest(), "bytes": len(cipher),
                                       "recipientFingerprint": "D" * 40}}
            if platform == "Darwin":
                manifest["outcome"].update(ownershipBoundary="GITHUB_HOSTED_DARWIN_MARKER_DOMAIN_V1",
                                           outsideDomainObservations=0)
            if component in ("consumers", "macos-shared"):
                manifest["tools"]["xcode"] = {"version": "16.2", "executableSha256": "e" * 64}
            self.manifests[component] = manifest
            self.artifact(5000 + i, f"ci-evidence-{component}-300-1",
                          zip_bytes({"manifest.json": Q.encoded(manifest), "evidence.tar.gz.gpg": cipher}))
        for i, (_, (_, _, prefix)) in enumerate(Q.APPLICATIONS.items(), 1):
            self.artifact(i, prefix + "-300-1", b"synthetic application bundle " + str(i).encode())

    def artifact(self, identifier, name, raw, created=CREATED):
        item = {"id": identifier, "name": name, "expired": False, "created_at": created, "expires_at": EXPIRES,
                "size_in_bytes": len(raw), "digest": "sha256:" + hashlib.sha256(raw).hexdigest(),
                "workflow_run": {"id": 300, "head_sha": SOURCE, "head_branch": "main"}}
        self.artifacts[:] = [old for old in self.artifacts if old["id"] != identifier] + [item]
        self.api.data[f"/actions/artifacts/{identifier}"] = item
        self.api.files[identifier] = raw
        return item

    def selection(self):
        return Q.collect(self.api, SOURCE, 300, 1)

    def qualify(self):
        document = Q.aggregate(self.api, self.selection())
        self.artifact(8001, f"ci-qualification-{SOURCE}-300-1", zip_bytes({"qualification.json": Q.encoded(document)}),
                      "2026-09-15T10:29:00Z")
        return document


class QualificationTests(unittest.TestCase):
    def setUp(self):
        clock = mock.patch.object(Q.time, "time", return_value=NOW); clock.start(); self.addCleanup(clock.stop)
        self.f = Fixture(); self.api = self.f.api

    def test_successful_selected_jobs_admitted_even_if_whole_matrix_failed(self):
        result = self.f.qualify()
        actual, binding = Q.load_qualification(self.api, SOURCE)
        self.assertEqual(result, actual)
        self.assertEqual(14, len(actual["components"]))
        self.assertEqual(4, len(actual["applications"]))
        self.assertEqual(8001, binding["artifactId"])
        self.assertEqual("failure", self.f.run["conclusion"])

    def test_supported_cli_components_missing_wrong_runner_arch_or_xcode_cannot_qualify(self):
        for component in ("consumers", "macos-shared"):
            self.assertEqual(Q.COMPONENTS[component], ('Darwin', 'arm64'))
            self.assertEqual(Q.RUNNERS[component], 'macos-14')
            selection = self.f.selection()
            missing = {**selection, 'components': [row for row in selection['components'] if row['component'] != component]}
            with self.assertRaisesRegex(Q.AdmissionError, 'Missing/duplicate required components'):
                Q.aggregate(self.api, missing)
            job = next(row for row in self.f.jobs if row['name'] == component + ' / Execute component')
            for labels in (['macos-26'], ['macos-latest'], ['macos-14', 'self-hosted']):
                with mock.patch.dict(job, {'labels': labels}), self.assertRaisesRegex(Q.AdmissionError, 'runner labels'):
                    Q.aggregate(self.api, selection)
            for group, change in (('host', {'arch': 'x86_64'}), ('tools', {}),
                                  ('tools', {'xcode': {'version': '26.5', 'executableSha256': 'e' * 64}}),
                                  ('tools', {'xcode': {'version': '16.2', 'executableSha256': 'invalid'}})):
                manifests = copy.deepcopy(self.f.manifests)
                if group == 'host':
                    manifests[component][group].update(change)
                else:
                    manifests[component][group] = change
                with self.subTest(group=group, change=change), self.assertRaises(Q.AdmissionError):
                    Q.aggregate(self.api, selection, manifests=manifests)

    def test_missing_duplicate_and_unknown_components_refuse(self):
        original = self.f.selection()
        for rows in (original["components"][:-1], original["components"] + original["components"][:1],
                     [{**row, "component": "fake"} if i == 0 else row for i, row in enumerate(original["components"])]):
            with self.subTest(rows=len(rows)), self.assertRaises(Q.AdmissionError):
                Q.aggregate(self.api, {**original, "components": rows})

    def test_optional_diagnostics_cannot_replace_or_extend_qualification(self):
        self.assertEqual(len(Q.COMPONENTS), 14)
        for name in ('bundle-diagnostic', 'jmdns-diagnostic', 'consumers-pom-diagnostic'):
            self.assertNotIn(name, Q.COMPONENTS)
            original = self.f.selection()
            diagnostic = {**original['components'][-1], 'component': name}
            for rows in (original['components'] + [diagnostic],
                         [diagnostic if row['component'] == 'compatibility' else row for row in original['components']],
                         [diagnostic]):
                with self.subTest(name=name, count=len(rows)), self.assertRaisesRegex(Q.AdmissionError, 'Missing/duplicate required components'):
                    Q.aggregate(self.api, {**original, 'components': rows})
            manifests = copy.deepcopy(self.f.manifests)
            manifests['compatibility']['component'] = name
            with self.assertRaisesRegex(Q.AdmissionError, 'Evidence schema/component differs'):
                Q.aggregate(self.api, original, manifests=manifests)

    def test_failed_skipped_cancelled_unassigned_or_wrong_source_job_refuse(self):
        job = self.f.jobs[0]
        for change in ({"conclusion": "failure"}, {"conclusion": "skipped"}, {"conclusion": "cancelled"},
                       {"status": "in_progress"}, {"runner_id": None}, {"head_sha": "f" * 40}, {"run_attempt": 2}):
            old = dict(job); job.update(change)
            with self.subTest(change=change), self.assertRaises(Q.AdmissionError):
                Q.aggregate(self.api, self.f.selection())
            job.clear(); job.update(old)

    def test_source_workflow_repository_branch_and_attempt_mismatch_refuse(self):
        for change in ({"head_sha": "f" * 40}, {"path": ".github/workflows/evil.yml"}, {"workflow_id": 88},
                       {"repository": {"full_name": "fork/project"}}, {"head_branch": "candidate"}, {"run_attempt": 2}):
            old = dict(self.f.run); self.f.run.update(change)
            with self.subTest(change=change), self.assertRaises(Q.AdmissionError):
                Q.aggregate(self.api, self.f.selection(), require_main=True)
            self.f.run.clear(); self.f.run.update(old)

    def test_expired_digest_wrong_run_timestamp_and_arch_refuse(self):
        artifact = self.api.data["/actions/artifacts/5000"]
        selection = self.f.selection()
        for change in ({"expired": True}, {"digest": "sha256:" + "f" * 64},
                       {"created_at": "2026-09-15T10:25:00Z"}, {"expires_at": "2026-09-19T10:15:00Z"},
                       {"workflow_run": {"id": 301, "head_sha": SOURCE, "head_branch": "main"}}):
            old = dict(artifact); artifact.update(change)
            with self.subTest(change=change), self.assertRaises(Q.AdmissionError):
                Q.aggregate(self.api, selection)
            artifact.clear(); artifact.update(old)
        manifests = copy.deepcopy(self.f.manifests)
        manifests["apple-x64"]["host"]["arch"] = "arm64"
        with self.assertRaises(Q.AdmissionError):
            Q.aggregate(self.api, selection, manifests=manifests)

    def test_manifest_failure_incomplete_mixed_tree_and_bool_types_refuse(self):
        for group, change in (("outcome", {"exitCode": False}), ("outcome", {"cleanupKnown": False}),
                              ("outcome", {"timedOut": True}), ("source", {"tree": "f" * 40}),
                              ("github", {"runAttempt": True}), ("host", {"runnerEnvironment": "self-hosted"})):
            manifests = copy.deepcopy(self.f.manifests); manifests["source"][group].update(change)
            with self.subTest(group=group, change=change), self.assertRaises(Q.AdmissionError):
                Q.aggregate(self.api, self.f.selection(), manifests=manifests)

    def test_darwin_boundary_is_required_and_observation_count_is_not_foreign_exit_proof(self):
        selection = self.f.selection()
        manifests = copy.deepcopy(self.f.manifests)
        manifests["desktop-macos"]["outcome"]["outsideDomainObservations"] = 52
        self.assertEqual(len(Q.aggregate(self.api, selection, manifests=manifests)["components"]), 14)
        for field, value in (("ownershipBoundary", None), ("ownershipBoundary", "STRICT_OLD_SCOPE"),
                             ("outsideDomainObservations", None), ("outsideDomainObservations", True),
                             ("outsideDomainObservations", -1), ("outsideDomainObservations", 1_000_001),
                             ("cleanupKnown", False), ("code", "CLEANUP"), ("exitCode", 1)):
            with self.subTest(field=field, value=value):
                manifests = copy.deepcopy(self.f.manifests)
                if value is None:
                    manifests["desktop-macos"]["outcome"].pop(field)
                else:
                    manifests["desktop-macos"]["outcome"][field] = value
                with self.assertRaises(Q.AdmissionError):
                    Q.aggregate(self.api, selection, manifests=manifests)

    def test_application_cannot_be_from_different_attempt_or_component(self):
        for change in ({"runAttempt": 2}, {"runId": 999}, {"artifactId": 5000}, {"platform": "unknown"}):
            selection = self.f.selection(); selection["applications"][0].update(change)
            with self.subTest(change=change), self.assertRaises(Q.AdmissionError):
                Q.aggregate(self.api, selection)

    def test_actual_archive_ciphertext_digest_and_extra_members_refuse(self):
        artifact = self.api.data["/actions/artifacts/5000"]
        for files in ({"manifest.json": Q.encoded(self.f.manifests["source"]), "evidence.tar.gz.gpg": b"wrong"},
                      {"manifest.json": Q.encoded(self.f.manifests["source"]), "private.log": b"do not publish"}):
            replacement = self.f.artifact(5000, artifact["name"], zip_bytes(files))
            with self.assertRaises(Q.AdmissionError):
                Q.read_archive(self.api, replacement, evidence=True)

    def test_qualification_ambiguity_never_selects_latest_and_bound_record_rechecks(self):
        self.f.qualify(); original, binding = Q.load_qualification(self.api, SOURCE)
        self.f.artifact(8002, f"ci-qualification-{SOURCE}-300-1", self.api.files[8001], "2026-09-15T10:29:00Z")
        with self.assertRaises(Q.AdmissionError):
            Q.load_qualification(self.api, SOURCE)
        self.assertEqual(original, Q.load_qualification(self.api, SOURCE, binding)[0])
        with mock.patch.dict(os.environ, {"RELEASE_QUALIFICATION_BINDING": Q.encoded(binding).decode()}):
            self.assertEqual(original, Q.load_qualification(self.api, SOURCE)[0])
        with mock.patch.dict(os.environ, {"RELEASE_QUALIFICATION_BINDING": "invalid"}):
            # An already frozen selection is never changed by later repository variables.
            self.assertEqual(original, Q.load_qualification(self.api, SOURCE, binding)[0])
        self.f.jobs[0]["conclusion"] = "failure"
        with self.assertRaises(Q.AdmissionError):
            Q.load_qualification(self.api, SOURCE, binding)

    def test_successful_older_attempt_artifact_not_relabelled_as_new_attempt(self):
        self.f.qualify()
        self.api.data["/actions/runs/300"] = {**self.f.run, "run_attempt": 2, "conclusion": "failure"}
        result, _ = Q.load_qualification(self.api, SOURCE)
        self.assertEqual(1, result["components"][0]["run"]["attempt"])
        selection = copy.deepcopy(result["selection"]); selection["components"][0]["runAttempt"] = 2
        self.api.data["/actions/runs/300/attempts/2"] = self.api.data["/actions/runs/300"]
        self.api.collections["/actions/runs/300/attempts/2/jobs"] = self.f.jobs
        with self.assertRaises(Q.AdmissionError):
            Q.aggregate(self.api, selection)

    def test_pr_synthetic_merge_is_distinct_from_service_head_and_cannot_publish(self):
        head, base = "a" * 40, "b" * 40
        self.f.run.update(event="pull_request", head_sha=head, head_branch="topic",
            repository={"full_name": Q.REPOSITORY, "id": 42}, head_repository={"full_name": Q.REPOSITORY, "id": 42},
            pull_requests=[{"number": 2, "head": {"sha": head, "repo": {"id": 42}},
                            "base": {"sha": base, "ref": "main", "repo": {"id": 42}}}])
        commit = self.api.data["/git/commits/" + SOURCE]
        commit["parents"] = [{"sha": base}, {"sha": head}]
        for job in self.f.jobs:
            job["head_sha"] = head
        for artifact in self.f.artifacts:
            artifact["workflow_run"].update(head_sha=head, head_branch="topic")
        result = Q.aggregate(self.api, self.f.selection())
        self.assertEqual(SOURCE, result["source"]["commit"])
        self.assertEqual(head, result["applications"][0]["producer"]["serviceHead"])
        with self.assertRaises(Q.AdmissionError):
            Q.aggregate(self.api, self.f.selection(), require_main=True)
        commit["parents"].reverse()
        with self.assertRaises(Q.AdmissionError):
            Q.aggregate(self.api, self.f.selection())

    def test_wrong_actual_runner_environment_or_canonical_tree_refuse(self):
        self.f.jobs[0]["labels"] = ["self-hosted", "ubuntu-24.04"]
        with self.assertRaises(Q.AdmissionError):
            Q.aggregate(self.api, self.f.selection())

        self.f.jobs[0]["labels"] = ["ubuntu-24.04"]
        self.api.data["/git/commits/" + SOURCE]["tree"]["sha"] = "f" * 40
        with self.assertRaises(Q.AdmissionError):
            Q.aggregate(self.api, self.f.selection())

    def test_independent_successful_component_attempts_can_be_combined(self):
        selection = self.f.selection()
        component = "jvm-windows"
        row = next(item for item in selection["components"] if item["component"] == component)
        run = {**self.f.run, "id": 301, "run_attempt": 2, "conclusion": "cancelled"}
        self.api.data["/actions/runs/301"] = run
        self.api.data["/actions/runs/301/attempts/2"] = run
        job = {**next(job for job in self.f.jobs if job["name"].startswith(component + " /")),
               "run_id": 301, "run_attempt": 2, "id": 11000}
        self.api.collections["/actions/runs/301/attempts/2/jobs"] = [job]
        manifest = copy.deepcopy(self.f.manifests[component])
        manifest["github"].update(runId="301", runAttempt="2")
        cipher = b"SYNTHETIC CIPHERTEXT NOT PRIVATE EVIDENCE:" + component.encode()
        item = self.f.artifact(6000, f"ci-evidence-{component}-301-2",
                             zip_bytes({"manifest.json": Q.encoded(manifest), "evidence.tar.gz.gpg": cipher}))
        item["workflow_run"]["id"] = 301
        row.update(runId=301, runAttempt=2, artifactId=6000, digest=item["digest"])
        result = Q.aggregate(self.api, selection)
        selected = next(item for item in result["components"] if item["component"] == component)
        self.assertEqual((301, 2), (selected["run"]["id"], selected["run"]["attempt"]))

    def test_duplicate_json_and_missing_archive_identity_refuse(self):
        with self.assertRaises(Q.AdmissionError):
            Q.parsed(b'{"schema":1,"schema":1}')
        with self.assertRaises(Q.AdmissionError):
            Q.integer(True)

    def retry(self, component=None):
        """A synthetic partial rerun retains original job/artifact attempt IDs."""
        run = {**self.f.run, "run_attempt": 2, "status": "in_progress", "conclusion": None}
        self.api.data["/actions/runs/300"] = run
        self.api.data["/actions/runs/300/attempts/2"] = run
        name = Q.QUALIFY_JOB if component is None else component + " / Execute component"
        original = next(job for job in self.f.jobs if job["name"] == name)
        job = {**original, "id": original["id"] + 1000, "run_attempt": 2}
        self.api.collections["/actions/runs/300/attempts/2/jobs"] = [job]
        self.api.collections["/actions/runs/300/jobs?filter=all"].append(job)
        if component is not None:
            manifest = copy.deepcopy(self.f.manifests[component])
            manifest["github"]["runAttempt"] = "2"
            cipher = b"SYNTHETIC RETRY CIPHERTEXT NOT PRIVATE EVIDENCE"
            manifest["ciphertext"].update(bytes=len(cipher), sha256=hashlib.sha256(cipher).hexdigest())
            self.f.artifact(9000, f"ci-evidence-{component}-300-2",
                            zip_bytes({"manifest.json": Q.encoded(manifest), "evidence.tar.gz.gpg": cipher}))
            for _, (owner, _, prefix) in Q.APPLICATIONS.items():
                if owner == component:
                    self.f.artifact(9001, prefix + "-300-2", b"synthetic retried application bundle")
        return job

    def test_failed_job_retry_reuses_untouched_originals_and_pairs_rebuilt_application(self):
        self.retry("desktop-windows")
        selection = Q.collect(self.api, SOURCE, 300, 2)
        self.assertEqual({row["component"]: row["runAttempt"] for row in selection["components"]},
                         {component: 2 if component == "desktop-windows" else 1 for component in Q.COMPONENTS})
        self.assertEqual({row["platform"]: row["runAttempt"] for row in selection["applications"]},
                         {"android": 1, "linux": 1, "windows": 2, "macos": 1})
        document = Q.aggregate(self.api, selection)
        self.assertEqual(14, len(document["components"]))
        self.assertEqual(4, len(document["applications"]))
        windows = next(row for row in document["applications"] if row["platform"] == "windows")
        self.assertEqual(9001, windows["id"])
        self.assertEqual(2, windows["producer"]["attempt"])

    def test_qualifier_only_retry_reuses_all_unchanged_component_attempts(self):
        original = self.f.selection()
        self.retry()
        selected = Q.collect(self.api, SOURCE, 300, 2)
        self.assertEqual(original, selected)
        self.assertEqual(14, len(Q.aggregate(self.api, selected)["components"]))

    def test_latest_failed_skipped_cancelled_or_incomplete_execution_never_falls_back(self):
        job = self.retry("desktop-windows")
        for status, conclusion in (("completed", "failure"), ("completed", "skipped"),
                                   ("completed", "cancelled"), ("completed", "timed_out"),
                                   ("queued", None), ("in_progress", None)):
            job.update(status=status, conclusion=conclusion)
            with self.subTest(status=status, conclusion=conclusion), self.assertRaisesRegex(
                    Q.AdmissionError, "Latest component execution failed, skipped or is incomplete"):
                Q.collect(self.api, SOURCE, 300, 2)

    def test_retry_missing_or_duplicate_job_and_missing_paired_artifact_refuse(self):
        job = self.retry("desktop-windows")
        all_jobs = self.api.collections["/actions/runs/300/jobs?filter=all"]
        all_jobs.append({**job, "id": job["id"] + 1000})
        with self.assertRaisesRegex(Q.AdmissionError, "Ambiguous latest component execution"):
            Q.collect(self.api, SOURCE, 300, 2)
        all_jobs.pop()
        source_job = all_jobs.pop(0)
        with self.assertRaisesRegex(Q.AdmissionError, "Missing component execution history"):
            Q.collect(self.api, SOURCE, 300, 2)
        all_jobs.insert(0, source_job)
        for identifier in (9000, 9001):
            original = list(self.f.artifacts)
            self.f.artifacts[:] = [row for row in original if row["id"] != identifier]
            with self.subTest(identifier=identifier), self.assertRaisesRegex(
                    Q.AdmissionError, "Missing/ambiguous exact-attempt artifact"):
                Q.collect(self.api, SOURCE, 300, 2)
            self.f.artifacts[:] = original

    def test_collection_refuses_stale_future_invalid_and_inconsistent_job_attempts(self):
        job = self.retry("desktop-windows")
        for requested in (1, 3):
            with self.subTest(requested=requested), self.assertRaisesRegex(
                    Q.AdmissionError, "Collection must use the current run attempt"):
                Q.collect(self.api, SOURCE, 300, requested)
        for attempt in (0, 3, True, "2"):
            job["run_attempt"] = attempt
            with self.subTest(attempt=attempt), self.assertRaisesRegex(Q.AdmissionError, "future/invalid attempt"):
                Q.collect(self.api, SOURCE, 300, 2)
        job["run_attempt"] = 2
        job["run_id"] = 999
        with self.assertRaisesRegex(Q.AdmissionError, "another run"):
            Q.collect(self.api, SOURCE, 300, 2)
        job["run_id"] = 300
        self.api.collections["/actions/runs/300/jobs?filter=all"][-1] = {**job, "id": job["id"] + 1}
        with self.assertRaisesRegex(Q.AdmissionError, "history differs from its original job"):
            Q.collect(self.api, SOURCE, 300, 2)

    def test_partial_retry_preserves_exact_pr_synthetic_merge_not_service_head(self):
        head, base = "a" * 40, "b" * 40
        self.f.run.update(event="pull_request", head_sha=head, head_branch="topic",
            repository={"full_name": Q.REPOSITORY, "id": 42}, head_repository={"full_name": Q.REPOSITORY, "id": 42},
            pull_requests=[{"number": 2, "head": {"sha": head, "repo": {"id": 42}},
                            "base": {"sha": base, "ref": "main", "repo": {"id": 42}}}])
        self.api.data["/git/commits/" + SOURCE]["parents"] = [{"sha": base}, {"sha": head}]
        self.api.data["/git/commits/" + head] = {"sha": head, "tree": {"sha": TREE}, "parents": [{"sha": base}]}
        for job in self.f.jobs:
            job["head_sha"] = head
        self.retry("desktop-windows")
        for artifact in self.f.artifacts:
            artifact["workflow_run"].update(head_sha=head, head_branch="topic")
        selection = Q.collect(self.api, SOURCE, 300, 2)
        result = Q.aggregate(self.api, selection)
        self.assertEqual(SOURCE, result["source"]["commit"])
        self.assertTrue(all(row["producer"]["serviceHead"] == head for row in result["applications"]))
        with self.assertRaises(Q.AdmissionError):
            Q.collect(self.api, head, 300, 2)
        with self.assertRaises(Q.AdmissionError):
            Q.aggregate(self.api, selection, require_main=True)

    def test_cli_prints_only_source_owned_admission_reason_not_arbitrary_exception(self):
        argv = ["ci_qualification.py", "aggregate", "--source", SOURCE, "--output", "unused.json"]
        public = io.StringIO()
        with mock.patch.object(sys, "argv", argv), mock.patch.dict(os.environ, {"GITHUB_REPOSITORY": "other/repo"}), \
                contextlib.redirect_stdout(public):
            self.assertEqual(Q.main(), 1)
        self.assertEqual(public.getvalue(), "HOLD: Aggregator source/repository differs\n")
        public = io.StringIO()
        with mock.patch.object(sys, "argv", argv), \
                mock.patch.object(Q.importlib.util, "spec_from_file_location", side_effect=ValueError("PRIVATE_URL_TOKEN")), \
                contextlib.redirect_stdout(public):
            self.assertEqual(Q.main(), 1)
        self.assertEqual(public.getvalue(), "HOLD: component qualification refused\n")


if __name__ == "__main__":
    unittest.main(failfast=True)
