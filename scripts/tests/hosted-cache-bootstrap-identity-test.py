#!/usr/bin/env python3
"""OFFLINE bootstrap identity controls; no hosted, native, Git or producer run.

Events, policies, Git answers and query owners are synthetic. The key is not a
cryptographic key. The connected controls use the actual GitView and native
supplier's closed argument grammar, but never its process/filesystem backend.
"""
from __future__ import annotations

from contextlib import ExitStack
import copy
import dataclasses
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_cache_bootstrap_identity as B
import hosted_test_query as Q

H = B.ordinary
SOURCE, TREE, MAIN, OTHER = (item * 40 for item in "1234")
NOW = 2000
KEY = b"-----BEGIN PGP PUBLIC KEY BLOCK-----\nsynthetic-not-a-key\n-----END PGP PUBLIC KEY BLOCK-----\n"
# Independent expected choices: not generated from the implementation's table.
SELECTIONS = (
    ("desktop-linux-x64", "desktop", "linux-x64", "Linux", "X64"),
    ("desktop-windows-x64", "desktop", "windows-x64", "Windows", "X64"),
    ("desktop-macos-arm64", "desktop", "macos-arm64", "macOS", "ARM64"),
    ("desktop-macos-x64", "desktop", "macos-x64", "macOS", "X64"),
    ("full-macos-arm64", "full", "macos-arm64", "macOS", "ARM64"),
    ("full-macos-x64", "full", "macos-x64", "macOS", "X64"),
)


def policy():
    return {"schema": 1, "repository": "p2pKit/P2pKit", "purpose": "P2PKIT_TEST_TRANSCRIPTS",
            "notBefore": 1000, "expiresAt": 3000, "retentionDays": 14, "retrievalOwner": "fixture-owner",
            "recipient": {"publicKey": KEY.decode("ascii"), "fingerprint": "A" * 40,
                          "sha256": hashlib.sha256(KEY).hexdigest()}}


def blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


class ModelGit:
    def __init__(self):
        self.head, self.tree_value, self.main = SOURCE, TREE, MAIN
        self.root_correct, self.dirty, self.shallow, self.ancestor = True, False, False, True
        self.policies = {MAIN: H.encoded(policy()), SOURCE: b"candidate policy MUST NOT be read"}
        self.calls, self.policy_reads = [], []
        self.after_policy = lambda: None

    def root_matches(self):
        return self.root_correct

    def clean(self):
        return not self.dirty

    def commit(self, ref):
        if ref == "HEAD":
            return self.head
        if ref == "refs/remotes/origin/main":
            return self.main
        raise AssertionError("unexpected modeled commit query")

    def tree(self, commit):
        assert commit == SOURCE
        return self.tree_value

    def query(self, *args):
        self.calls.append(args)
        if args == ("rev-parse", "--is-shallow-repository"):
            return b"true\n" if self.shallow else b"false\n"
        if args == ("merge-base", MAIN, SOURCE):
            return ((MAIN if self.ancestor else OTHER) + "\n").encode("ascii")
        raise AssertionError("unexpected modeled Git query")

    def policy(self, commit):
        self.policy_reads.append(commit)
        H.require(commit in self.policies, "MISSING_TRUSTED_RECIPIENT_POLICY")
        raw = self.policies[commit]
        self.after_policy()
        return blob(raw), raw


class OfflineCase(unittest.TestCase):
    def setUp(self):
        guards = ExitStack()
        self.addCleanup(guards.close)
        for module, name in ((subprocess, "run"), (subprocess, "Popen"), (os, "system"),
                             (socket, "socket"), (socket, "create_connection"),
                             (Q.processes, "host_role"), (Q.processes, "make_scope"),
                             (Q, "_new_private_directory")):
            guards.enter_context(patch.object(module, name, side_effect=AssertionError("OFFLINE_ONLY")))
        self.git = ModelGit()
        self.env = {
            "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "p2pKit/P2pKit",
            "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
            "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
            "GITHUB_JOB": "populate", "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/work/fixture",
            "GITHUB_SHA": SOURCE, "GITHUB_WORKFLOW_SHA": SOURCE,
        }
        self.event = {"repository": {"full_name": "p2pKit/P2pKit", "default_branch": "main"},
                      "ref": "work/fixture", "inputs": {"selection": "desktop-linux-x64",
                                                       "expected_sha": SOURCE, "expected_tree": TREE}}
        self.workflow_ref()

    def workflow_ref(self):
        self.env["GITHUB_WORKFLOW_REF"] = (
            "p2pKit/P2pKit/.github/workflows/dependency-cache-bootstrap.yml@" + self.env["GITHUB_REF"])

    def admit(self, raw=None):
        return B._admit(self.env, H.encoded(self.event) if raw is None else raw, self.git, NOW)

    def rejected(self, reason):
        with self.assertRaisesRegex(H.AdmissionError, "^" + reason + "$"):
            self.admit()


class IdentityTests(OfflineCase):
    def test_six_selections_bind_distinct_execution_and_byte_cohort(self):
        self.assertEqual(B.SELECTIONS, SELECTIONS)
        for name, profile, role, system, arch in SELECTIONS:
            with self.subTest(selection=name):
                self.env.update(RUNNER_OS=system, RUNNER_ARCH=arch)
                self.event["inputs"]["selection"] = name
                value = self.admit()
                record = json.loads(value.record)
                self.assertEqual(record["profile"], "cache-bootstrap")
                self.assertEqual(record["scope"], "CACHE_BOOTSTRAP_HOSTED_IDENTITY_V1")
                self.assertEqual(record["cacheCohort"], {"profile": profile, "role": role})
                self.assertEqual(record["selection"], name)
                self.assertEqual(record["producerCommand"], ["help", "--console=plain", "--no-configure-on-demand"])
                self.assertEqual(record["producerScope"], "CONFIGURATION_ONLY_NOT_COMPLETE_DEPENDENCIES_OR_TESTS")
                self.assertEqual(record["testAcceptance"], "NOT_PERFORMED")
                self.assertNotIn("suites", record)
                self.assertNotIn("cache-bootstrap", H.PROFILES)
                self.assertEqual(record["github"]["runnerOS"], system)
                self.assertEqual(record["github"]["runnerArch"], arch)

    def test_exact_original_bytes_and_source_run_policy_bindings(self):
        raw = json.dumps(self.event, indent=2).encode("ascii")
        value = self.admit(raw)
        record = json.loads(value.record)
        self.assertEqual(value.original_event, raw)
        self.assertEqual(value.original_policy, self.git.policies[MAIN])
        self.assertEqual(value.public_key, KEY)
        self.assertEqual(record["source"], {"commit": SOURCE, "tree": TREE})
        self.assertEqual(record["github"], {
            "repository": "p2pKit/P2pKit", "event": "workflow_dispatch", "ref": self.env["GITHUB_REF"],
            "workflow": ".github/workflows/dependency-cache-bootstrap.yml", "workflowSha": SOURCE,
            "job": "populate", "runId": "123", "runAttempt": "1", "eventSha256": hashlib.sha256(raw).hexdigest(),
            "eventBinding": {"policyMain": MAIN, "selection": "desktop-linux-x64",
                             "expectedCommit": SOURCE, "expectedTree": TREE},
            "runnerOS": "Linux", "runnerArch": "X64"})
        self.assertEqual(record["policy"], {
            "commit": MAIN, "blob": blob(value.original_policy), "path": ".github/test-evidence-recipient.json",
            "sha256": hashlib.sha256(value.original_policy).hexdigest(), "fingerprint": "A" * 40,
            "keySha256": hashlib.sha256(KEY).hexdigest(), "expiresAt": 3000, "retentionDays": 14})
        self.assertEqual(self.git.policy_reads, [MAIN])
        self.assertEqual(self.git.calls, [("rev-parse", "--is-shallow-repository"), ("merge-base", MAIN, SOURCE)])
        self.assertNotIn(KEY, value.record)
        self.assertNotIn(b"fixture-owner", value.record)

    def test_admission_is_immutable_and_supplied_models_are_not_native_proof(self):
        value = self.admit()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            value.record = b"changed"
        decoded = json.loads(value.record)
        decoded["cacheCohort"]["profile"] = "changed"
        self.assertEqual(json.loads(value.record)["cacheCohort"]["profile"], "desktop")
        self.assertEqual(json.loads(value.record)["testAcceptance"], "NOT_PERFORMED")

    def test_full_and_short_event_branch_refs_are_the_same_binding(self):
        for ref in ("work/fixture", "refs/heads/work/fixture"):
            self.event["ref"] = ref
            self.assertEqual(json.loads(self.admit().record)["github"]["ref"], "refs/heads/work/fixture")

    def test_only_workflow_dispatch_can_admit(self):
        for event in ("push", "pull_request", "pull_request_target", "schedule", "workflow_run", "release", "", None):
            with self.subTest(event=event):
                self.env["GITHUB_EVENT_NAME"] = event
                self.rejected("BOOTSTRAP_MANUAL_ONLY")
        self.assertEqual(self.git.policy_reads, [])

    def test_hosted_repository_endpoint_and_job_are_closed(self):
        for key in ("GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_SERVER_URL", "GITHUB_API_URL",
                    "RUNNER_ENVIRONMENT", "GITHUB_JOB"):
            for value in (None, "other", True):
                with self.subTest(key=key, value=value), patch.dict(self.env, {key: value}):
                    self.rejected("BOOTSTRAP_HOSTED_CALLER")

    def test_closed_selections_reject_profile_role_aliases_and_options(self):
        for name in (None, True, 1, "desktop", "full", "full-linux-x64", "desktop-linux-arm64",
                     "desktop-linux-x64\n", "Desktop-linux-x64", "--help"):
            with self.subTest(selection=name):
                self.event["inputs"]["selection"] = name
                self.rejected("BOOTSTRAP_SELECTION")

    def test_every_selection_refuses_wrong_host_or_architecture(self):
        for name, _, _, system, arch in SELECTIONS:
            self.event["inputs"]["selection"] = name
            for host in (("other", arch), (system, "other"), (system, None)):
                with self.subTest(selection=name, host=host):
                    self.env.update(RUNNER_OS=host[0], RUNNER_ARCH=host[1])
                    self.rejected("BOOTSTRAP_HOST_LABELS")

    def test_exact_input_roster_excludes_recipient_command_and_budget_authority(self):
        original = copy.deepcopy(self.event["inputs"])
        for key in ("evidence_public_key", "recipient", "operation", "command", "args", "timeout", "reviewed_base"):
            with self.subTest(extra=key):
                self.event["inputs"] = dict(original, **{key: ""})
                self.rejected("BOOTSTRAP_INPUTS")
        for key in original:
            self.event["inputs"] = {k: v for k, v in original.items() if k != key}
            self.rejected("BOOTSTRAP_INPUTS")
        for value in (None, [], "", True):
            self.event["inputs"] = value
            self.rejected("BOOTSTRAP_INPUTS")

    def test_run_identifiers_are_positive_bounded_decimal_strings(self):
        for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
            for value in (None, True, 1, "", "0", "01", "1\n", "1" * 21):
                with self.subTest(key=key, value=value), patch.dict(self.env, {key: value}):
                    self.rejected("BOOTSTRAP_RUN")

    def test_event_repository_and_ref_cannot_drift(self):
        for key, value in (("full_name", "fork/P2pKit"), ("default_branch", "other")):
            with patch.dict(self.event["repository"], {key: value}):
                self.rejected("BOOTSTRAP_REPOSITORY")
        for value in (None, "other", "refs/tags/release", self.env["GITHUB_REF"] + "\n"):
            self.event["ref"] = value
            self.rejected("BOOTSTRAP_EVENT_REF")

    def test_tags_pull_refs_retired_and_unbounded_branches_fail(self):
        for ref in ("refs/tags/v0.7.0-rc3", "refs/pull/1/merge", "refs/heads/",
                    "refs/heads/audit/complete-2026-09-04", "refs/heads/work\n", "refs/heads/a\x7f",
                    "refs/heads/" + "a" * 246):
            self.env["GITHUB_REF"] = ref
            self.workflow_ref()
            self.rejected("BOOTSTRAP_REF")

    def test_workflow_source_and_path_are_not_interchangeable_with_ordinary_ci(self):
        with patch.dict(self.env, GITHUB_WORKFLOW_SHA=MAIN):
            self.rejected("BOOTSTRAP_WORKFLOW")
        for path in ("ci.yml", "desktop-cross-host.yml", "dependency-cache-bootstrap.yml@refs/heads/other"):
            self.env["GITHUB_WORKFLOW_REF"] = "p2pKit/P2pKit/.github/workflows/" + path
            self.rejected("BOOTSTRAP_WORKFLOW")

    def test_expected_source_and_tree_require_full_exact_lowercase_shas(self):
        for key in ("expected_sha", "expected_tree"):
            for value in (None, True, SOURCE[:7], "A" * 40, "1" * 41, SOURCE + "\n"):
                with self.subTest(key=key, value=value), patch.dict(self.event["inputs"], {key: value}):
                    self.rejected("IDENTITY_FULL_SHA")
        with patch.dict(self.event["inputs"], expected_sha=MAIN):
            self.rejected("BOOTSTRAP_EXPECTED_SOURCE")
        with patch.dict(self.event["inputs"], expected_tree=OTHER):
            self.rejected("BOOTSTRAP_EXPECTED_TREE")

    def test_initial_source_root_and_cleanliness_are_required(self):
        for name, value in (("head", OTHER), ("root_correct", False), ("dirty", True)):
            with self.subTest(field=name), patch.object(self.git, name, value):
                self.rejected("BOOTSTRAP_SOURCE")
        self.assertEqual(self.git.policy_reads, [])

    def test_shallow_and_unrelated_main_are_refused_before_policy(self):
        self.git.shallow = True
        self.rejected("BOOTSTRAP_FULL_HISTORY")
        self.git.shallow, self.git.ancestor = False, False
        self.rejected("BOOTSTRAP_MAIN_ANCESTRY")
        self.assertEqual(self.git.policy_reads, [])

    def test_candidate_policy_cannot_bootstrap_missing_original_main_policy(self):
        del self.git.policies[MAIN]
        self.git.policies[SOURCE] = H.encoded(policy())
        self.rejected("MISSING_TRUSTED_RECIPIENT_POLICY")
        self.assertEqual(self.git.policy_reads, [MAIN])

    def test_source_main_root_or_tree_changes_during_admission_fail(self):
        for name, value in (("head", OTHER), ("main", OTHER), ("root_correct", False),
                            ("dirty", True), ("tree_value", OTHER)):
            with self.subTest(field=name):
                self.git = ModelGit()
                self.git.after_policy = lambda: setattr(self.git, name, value)
                self.rejected("BOOTSTRAP_SOURCE_OR_MAIN_CHANGED")

    def test_policy_expiry_retention_and_named_custodian_are_still_required(self):
        for key, value, reason in (("notBefore", NOW + 1, "VALIDITY"), ("expiresAt", NOW, "VALIDITY"),
                                   ("retentionDays", 15, "RETENTION"), ("retentionDays", True, "RETENTION"),
                                   ("retrievalOwner", "", "RETRIEVAL_OWNER")):
            with self.subTest(field=key):
                item = policy()
                item[key] = value
                self.git.policies[MAIN] = H.encoded(item)
                self.rejected("RECIPIENT_POLICY_" + reason)

    def test_policy_key_content_and_hash_are_not_recipient_validation(self):
        item = policy()
        item["recipient"]["sha256"] = "0" * 64
        self.git.policies[MAIN] = H.encoded(item)
        self.rejected("RECIPIENT_POLICY_KEY")
        self.git.policies[MAIN] = H.encoded(policy())
        # This deliberately invalid cryptographic key can pass identity only.
        self.assertEqual(self.admit().public_key, KEY)

    def test_malformed_duplicate_oversized_or_nonobject_events_fail(self):
        for raw, reason in ((b"", "SIZE"), (b" " * (H.EVENT_LIMIT + 1), "SIZE"), (b"{", "MALFORMED"),
                             (b'{"inputs":{},"inputs":{}}', "DUPLICATE"), (b"[]", "OBJECT"),
                             (b'{"value":NaN}', "NONFINITE"), (b"{} {}", "MALFORMED")):
            with self.subTest(reason=reason), self.assertRaisesRegex(H.AdmissionError, "^IDENTITY_JSON_" + reason + "$"):
                self.admit(raw)


class ConnectedQueryGrammarTests(OfflineCase):
    def view(self):
        raw = H.encoded(policy())
        answers = {
            ("rev-parse", "--show-toplevel"): os.fsencode(ROOT) + b"\n",
            ("status", "--porcelain=v1", "--untracked-files=all"): b"",
            ("rev-parse", "--verify", "HEAD^{commit}"): SOURCE.encode("ascii") + b"\n",
            ("rev-parse", "--verify", SOURCE + "^{tree}"): TREE.encode("ascii") + b"\n",
            ("rev-parse", "--is-shallow-repository"): b"false\n",
            ("rev-parse", "--verify", "refs/remotes/origin/main^{commit}"): MAIN.encode("ascii") + b"\n",
            ("merge-base", MAIN, SOURCE): MAIN.encode("ascii") + b"\n",
            ("ls-tree", "-z", MAIN, "--", H.POLICY_PATH): f"100644 blob {blob(raw)}\t{H.POLICY_PATH}\0".encode("ascii"),
            ("cat-file", "-s", blob(raw)): str(len(raw)).encode("ascii") + b"\n",
            ("cat-file", "blob", blob(raw)): raw,
        }
        self.requests = []

        def modeled_owner(**request):
            self.requests.append(request)
            self.assertEqual(request["argv"][:7], (
                str(Path(__file__).resolve()), "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false",
                "-C", str(ROOT)))
            suffix = request["argv"][7:]
            Q.require(Q._allowed_suffix(suffix), "QUERY_NOT_CLOSED_READONLY_GIT")
            self.assertEqual(request["cwd"], ROOT)
            self.assertEqual(request["timeout_seconds"], 15)
            self.assertEqual(request["stderr_limit"], 4096)
            self.assertNotIn("GH_TOKEN", request["environment"])
            self.assertNotIn("GITHUB_TOKEN", request["environment"])
            self.assertEqual(request["environment"]["GIT_NO_LAZY_FETCH"], "1")
            self.assertEqual(request["environment"]["GIT_NO_REPLACE_OBJECTS"], "1")
            self.assertEqual(request["environment"]["GIT_OPTIONAL_LOCKS"], "0")
            answer = answers[suffix]
            self.assertLessEqual(len(answer), request["stdout_limit"])
            return answer

        with patch.object(H.shutil, "which", return_value=__file__):
            return H.GitView(ROOT, dict(self.env, SYSTEMROOT="synthetic-systemroot"), modeled_owner)

    def test_exact_bootstrap_queries_are_admitted_by_real_supplier_grammar(self):
        for suffix in (("rev-parse", "--is-shallow-repository"), ("merge-base", MAIN, SOURCE)):
            with self.subTest(suffix=suffix):
                self.assertTrue(Q._allowed_suffix(suffix))

    def test_actual_gitview_and_supplier_grammar_accept_all_six_modeled_admissions(self):
        for name, _, _, system, arch in SELECTIONS:
            with self.subTest(selection=name):
                self.env.update(RUNNER_OS=system, RUNNER_ARCH=arch)
                self.event["inputs"]["selection"] = name
                value = B._admit(self.env, H.encoded(self.event), self.view(), NOW)
                self.assertEqual(json.loads(value.record)["selection"], name)
                self.assertEqual(len(self.requests), 15)
                self.assertIn(("merge-base", MAIN, SOURCE), [r["argv"][7:] for r in self.requests])

    def test_new_query_forms_do_not_admit_arbitrary_refs_flags_or_writes(self):
        rejected = [("rev-parse", "--is-shallow-repository", "HEAD"), ("rev-parse", "--git-dir"),
                    ("merge-base", MAIN), ("merge-base", MAIN, SOURCE, OTHER),
                    ("merge-base", "--is-ancestor", MAIN, SOURCE), ("merge-base", "--all", MAIN, SOURCE),
                    ("fetch", "origin"), ("config", "core.bare", "true")]
        for bad in ("HEAD", "origin/main", "refs/remotes/origin/main", MAIN[:12], "A" * 40, MAIN + "\n", "--all"):
            rejected.extend((("merge-base", bad, SOURCE), ("merge-base", MAIN, bad)))
        for suffix in rejected:
            with self.subTest(suffix=suffix):
                self.assertFalse(Q._allowed_suffix(suffix))


class EntrypointTests(OfflineCase):
    def entry(self, *, expected=None, root=ROOT):
        environment = dict(self.env, GITHUB_WORKSPACE=str(ROOT), GITHUB_EVENT_PATH="/synthetic/original.json")
        with patch.dict(os.environ, environment, clear=True), patch.object(H, "GitView", return_value=self.git), \
                patch.object(H, "read_regular", return_value=H.encoded(self.event)) as read, \
                patch.object(B.time, "time", return_value=NOW):
            owner = Mock(side_effect=AssertionError("no native supplier in entry model"))
            result = B.admit(root, query_runner=owner, expected=expected)
            read.assert_called_once_with(Path("/synthetic/original.json"), H.EVENT_LIMIT)
            owner.assert_not_called()
            return result

    def test_same_original_reseals_without_new_authority(self):
        first = self.entry()
        self.assertEqual(self.entry(expected=first), first)

    def test_changed_original_event_policy_and_attempt_cannot_reseal(self):
        first = self.entry()
        with patch.dict(self.env, GITHUB_RUN_ATTEMPT="2"), self.assertRaisesRegex(
                H.AdmissionError, "^BOOTSTRAP_CHANGED_BEFORE_SEAL$"):
            self.entry(expected=first)
        self.event["sender"] = {"login": "synthetic-extra-event-metadata"}
        with self.assertRaisesRegex(H.AdmissionError, "^BOOTSTRAP_CHANGED_BEFORE_SEAL$"):
            self.entry(expected=first)
        del self.event["sender"]
        item = policy()
        item["expiresAt"] = 3001
        self.git.policies[MAIN] = H.encoded(item)
        with self.assertRaisesRegex(H.AdmissionError, "^BOOTSTRAP_CHANGED_BEFORE_SEAL$"):
            self.entry(expected=first)

    def test_noncanonical_workspace_fails_before_original_read(self):
        with self.assertRaisesRegex(H.AdmissionError, "^BOOTSTRAP_WORKSPACE$"):
            self.entry(root=Path("relative"))

    def test_expected_binding_requires_the_actual_immutable_admission_type(self):
        for expected in ({}, True, self.entry().record):
            with self.assertRaisesRegex(H.AdmissionError, "^BOOTSTRAP_CHANGED_BEFORE_SEAL$"):
                self.entry(expected=expected)

    def test_no_native_query_fallback_and_no_git_environment_override(self):
        with self.assertRaisesRegex(H.AdmissionError, "^IDENTITY_OWNED_QUERY_REQUIRED$"):
            H.GitView(ROOT, {}, None)
        with self.assertRaisesRegex(H.AdmissionError, "^IDENTITY_GIT_OVERRIDE$"):
            H.GitView(ROOT, {"GIT_DIR": "/synthetic/other"}, Mock())


if __name__ == "__main__":
    unittest.main(verbosity=2)
