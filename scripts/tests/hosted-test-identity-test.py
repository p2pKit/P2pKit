#!/usr/bin/env python3
"""Pure modeled event/policy controls, not GitHub, native or GPG execution."""
from __future__ import annotations

import copy
from dataclasses import replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("hosted_test_identity", ROOT / "scripts/hosted_test_identity.py")
H = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = H
SPEC.loader.exec_module(H)
SOURCE, TREE, BASE, HEAD = (value * 40 for value in "1234")
NOW = 2000
# Deliberately NOT a valid cryptographic key; these tests stop at policy identity.
KEY = b"-----BEGIN PGP PUBLIC KEY BLOCK-----\nsynthetic-parser-only\n-----END PGP PUBLIC KEY BLOCK-----\n"


def policy():
    return {"schema": 1, "repository": H.REPOSITORY, "purpose": "P2PKIT_TEST_TRANSCRIPTS",
            "notBefore": 1000, "expiresAt": 3000, "retentionDays": 14, "retrievalOwner": "fixture-owner",
            "recipient": {"publicKey": KEY.decode(), "fingerprint": "A" * 40,
                          "sha256": hashlib.sha256(KEY).hexdigest()}}


def blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\x00" + raw).hexdigest()


class ModelGit:
    def __init__(self):
        self.head = SOURCE
        self.main = BASE
        self.dirty = False
        self.root_correct = True
        self.parent_set = [BASE, HEAD]
        self.commit_message = b"Synthetic ordinary merge, no Release request\n"
        self.policies = {SOURCE: H.encoded(policy()), BASE: H.encoded(policy())}
        self.requested = []

    def commit(self, ref):
        return self.head if ref == "HEAD" else self.main

    def tree(self, _):
        return TREE

    def parents(self, _):
        return self.parent_set

    def message(self, _):
        return self.commit_message

    def clean(self):
        return not self.dirty

    def root_matches(self):
        return self.root_correct

    def policy(self, commit):
        self.requested.append(commit)
        H.require(commit in self.policies, "MISSING_TRUSTED_RECIPIENT_POLICY")
        raw = self.policies[commit]
        return blob(raw), raw


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.git = ModelGit()
        self.profile = "desktop"
        self.env = {
            "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": H.REPOSITORY,
            "GITHUB_SERVER_URL": "https://github.com", "GITHUB_API_URL": "https://api.github.com",
            "RUNNER_ENVIRONMENT": "github-hosted", "RUNNER_OS": "Linux", "RUNNER_ARCH": "X64",
            "GITHUB_JOB": "verify", "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
            "GITHUB_EVENT_NAME": "push", "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": SOURCE,
            "GITHUB_WORKFLOW_SHA": SOURCE,
        }
        self.event = {"repository": {"full_name": H.REPOSITORY, "default_branch": "main"},
                      "ref": "refs/heads/main", "after": SOURCE, "before": BASE, "deleted": False}
        self.workflow_ref()
        # A pure test unexpectedly starting even a Git child must fail.
        guard = patch.object(subprocess, "run", side_effect=AssertionError("no child in pure controls"))
        guard.start()
        self.addCleanup(guard.stop)
        guard = patch.object(subprocess, "Popen", side_effect=AssertionError("no child in pure controls"))
        guard.start()
        self.addCleanup(guard.stop)

    def workflow_ref(self):
        self.env["GITHUB_WORKFLOW_REF"] = H.REPOSITORY + "/" + H.PROFILES[self.profile][0] + "@" + self.env["GITHUB_REF"]

    def admit(self):
        return H._admit(self.profile, self.env, H.encoded(self.event), self.git, NOW)

    def rejected(self, code):
        with self.assertRaisesRegex(H.AdmissionError, "^" + code + "$"):
            self.admit()

    def pr(self):
        self.env.update(GITHUB_EVENT_NAME="pull_request", GITHUB_REF="refs/pull/17/merge")
        self.workflow_ref()
        self.event = {"repository": self.event["repository"], "number": 17, "action": "synchronize",
                      "pull_request": {"number": 17, "state": "open", "merged": False,
                                       "base": {"sha": BASE, "ref": "main", "repo": {"full_name": H.REPOSITORY}},
                                       "head": {"sha": HEAD, "repo": {"full_name": "fixture-fork/P2pKit"}}}}

    def manual(self):
        self.env.update(GITHUB_EVENT_NAME="workflow_dispatch", GITHUB_REF="refs/heads/work/fixture")
        self.workflow_ref()
        self.event = {"repository": self.event["repository"], "ref": "work/fixture", "inputs": {
            "operation": "desktop", "expected_sha": "", "expected_tree": "", "reviewed_base": "",
            "evidence_public_key": "", "evidence_fingerprint": ""}}

    def full(self):
        self.profile = "full"
        self.env.update(GITHUB_JOB="complete-gate", RUNNER_OS="macOS", RUNNER_ARCH="ARM64")
        self.workflow_ref()

    def test_push_binds_source_workflow_run_event_and_approved_policy(self):
        value = self.admit()
        record = json.loads(value.record)
        self.assertEqual(record["source"], {"commit": SOURCE, "tree": TREE})
        self.assertEqual(record["github"]["event"], "push")
        self.assertEqual(record["github"]["eventSha256"], hashlib.sha256(value.original_event).hexdigest())
        self.assertEqual(record["policy"]["commit"], SOURCE)
        self.assertEqual(record["suites"], ["cli"])
        self.assertEqual(value.public_key, KEY)
        self.assertEqual(self.git.requested, [SOURCE])
        self.assertNotIn("publicKey", value.record.decode())
        self.assertNotIn("retrievalOwner", value.record.decode())

    def test_pr_retains_fork_identity_but_reads_only_original_base_policy(self):
        self.pr()
        self.git.policies[SOURCE] = b"arbitrary candidate rotation; must never be read"
        value = self.admit()
        record = json.loads(value.record)
        self.assertEqual(self.git.requested, [BASE])
        self.assertEqual(record["github"]["eventBinding"], {
            "number": 17, "base": BASE, "head": HEAD, "headRepository": "fixture-fork/P2pKit"})
        self.assertEqual(record["source"]["commit"], SOURCE)
        self.assertEqual(record["policy"]["commit"], BASE)

    def test_exact_main_merge_marker_alone_requests_packaging(self):
        self.assertFalse(H.sample_packaging_required(self.admit()))
        self.git.commit_message = b"Synthetic merge\n\n[release ci]\n"
        value = self.admit()
        self.assertTrue(H.sample_packaging_required(value))
        detail = json.loads(value.record)["github"]["eventBinding"]
        self.assertEqual(detail["releaseMessageSha256"], hashlib.sha256(self.git.commit_message).hexdigest())
        self.assertEqual(detail["releaseParents"], [BASE, HEAD])
        self.assertNotIn("Synthetic merge", value.record.decode())

    def test_marker_case_spacing_or_payload_only_do_not_request_packaging(self):
        self.event["head_commit"] = {"message": "[release ci]"}
        self.event["commits"] = [{"message": "[release ci]"}]
        for message in (b"ordinary", b"[Release ci]", b"[release CI]", b"[release  ci]", b"release ci", b""):
            with self.subTest(message=message):
                self.git.commit_message = message
                self.assertFalse(H.sample_packaging_required(self.admit()))

    def test_marked_nonmerge_push_keeps_normal_ci_without_packaging(self):
        self.git.commit_message = b"[release ci]\n"
        for parents in ([], [BASE], [BASE, HEAD, TREE]):
            with self.subTest(parents=parents):
                self.git.parent_set = parents
                self.assertFalse(H.sample_packaging_required(self.admit()))

    def test_pr_and_manual_source_markers_never_request_release_packaging(self):
        self.git.commit_message = b"[release ci]\n"
        self.pr()
        self.event["pull_request"]["body"] = "[release ci]"
        self.assertFalse(H.sample_packaging_required(self.admit()))
        self.manual()
        self.assertFalse(H.sample_packaging_required(self.admit()))

    def test_full_check_does_not_gain_packaging_from_marker(self):
        self.git.commit_message = b"[release ci]\n"
        self.full()
        value = self.admit()
        self.assertFalse(H.sample_packaging_required(value))
        self.assertNotIn("samplePackagingRequired", json.loads(value.record))

    def test_absent_or_nonboolean_admitted_intent_fails_closed(self):
        original = self.admit()
        for value in (None, "true", "false", 0, 1, [], {}):
            record = json.loads(original.record)
            if value is None:
                record.pop("samplePackagingRequired")
            else:
                record["samplePackagingRequired"] = value
            with self.subTest(value=value), self.assertRaisesRegex(H.AdmissionError, "IDENTITY_SAMPLE_INTENT"):
                H.sample_packaging_required(replace(original, record=H.encoded(record)))

    def test_unavailable_or_oversized_commit_message_cannot_request_packaging(self):
        for value in ("[release ci]", b"x" * (H.MESSAGE_LIMIT + 1)):
            self.git.commit_message = value
            self.rejected("IDENTITY_COMMIT_MESSAGE")
        self.git.message = Mock(side_effect=H.AdmissionError("IDENTITY_GIT_QUERY_FAILED"))
        self.rejected("IDENTITY_GIT_QUERY_FAILED")

    def test_absent_pr_base_policy_does_not_fall_back_to_candidate(self):
        self.pr()
        del self.git.policies[BASE]
        self.rejected("MISSING_TRUSTED_RECIPIENT_POLICY")
        self.assertEqual(self.git.requested, [BASE])

    def test_pr_rejects_changed_or_extra_parent_and_nonmain_base(self):
        self.pr()
        for parents in ([HEAD, BASE], [BASE], [BASE, HEAD, SOURCE], [BASE, SOURCE]):
            with self.subTest(parents=parents):
                self.git.parent_set = parents
                self.rejected("IDENTITY_PR_PARENTS")
        self.git.parent_set = [BASE, HEAD]
        self.event["pull_request"]["base"]["ref"] = "untrusted"
        self.rejected("IDENTITY_PR_BASE")

    def test_pr_rejects_closed_merged_wrong_number_and_foreign_base(self):
        self.pr()
        good = copy.deepcopy(self.event)
        for key, value in (("state", "closed"), ("merged", True), ("number", 18)):
            self.event = copy.deepcopy(good)
            self.event["pull_request"][key] = value
            self.rejected("IDENTITY_PR")
        self.event = good
        self.event["pull_request"]["base"]["repo"]["full_name"] = "fixture-fork/P2pKit"
        self.rejected("IDENTITY_PR_BASE")

    def test_manual_reads_main_policy_and_never_uses_lock_only_key_input(self):
        self.manual()
        self.git.policies[SOURCE] = b"candidate policy not trusted"
        value = self.admit()
        self.assertEqual(self.git.requested, [BASE])
        self.assertEqual(json.loads(value.record)["github"]["eventBinding"], {"policyMain": BASE})
        self.event["inputs"]["evidence_public_key"] = KEY.decode()
        self.rejected("IDENTITY_MANUAL_INPUTS")

    def test_build_only_and_special_manual_operations_are_not_test_custody(self):
        self.manual()
        for operation in ("sample-apps", "dependency-lock-candidate", "dependency-lock-candidate-x64",
                          "windows-directory-fsync-control", "macos-arm64-admission", "unknown"):
            with self.subTest(operation=operation):
                self.event["inputs"]["operation"] = operation
                self.rejected("IDENTITY_MANUAL_INPUTS")

    def test_manual_rejects_absent_main_policy_and_retired_audit_ref(self):
        self.manual()
        del self.git.policies[BASE]
        self.rejected("MISSING_TRUSTED_RECIPIENT_POLICY")
        self.env["GITHUB_REF"] = "refs/heads/audit/complete-2026-09-04"
        self.workflow_ref()
        self.rejected("IDENTITY_MANUAL_REF")

    def test_full_manual_has_both_suites_and_no_key_override(self):
        self.manual()
        self.full()
        self.event["inputs"] = None
        self.assertEqual(json.loads(self.admit().record)["suites"], ["cli", "diagnostics"])
        self.event["inputs"] = {"recipient": "attacker"}
        self.rejected("IDENTITY_MANUAL_INPUTS")

    def test_schedule_is_real_known_ci_main_event_not_desktop_or_manual(self):
        self.full()
        self.env["GITHUB_EVENT_NAME"] = "schedule"
        self.event = {"repository": self.event["repository"], "schedule": "17 4 * * 1"}
        self.assertEqual(json.loads(self.admit().record)["github"]["event"], "schedule")
        self.event["schedule"] = "* * * * *"
        self.rejected("IDENTITY_SCHEDULE")
        self.event["schedule"] = "17 4 * * 1"
        self.profile = "desktop"
        self.env["GITHUB_JOB"] = "verify"
        self.workflow_ref()
        self.rejected("IDENTITY_SCHEDULE")

    def test_wrong_hosted_repository_workflow_job_or_endpoints_rejected(self):
        original = dict(self.env)
        for key, value in (("GITHUB_ACTIONS", "false"), ("GITHUB_REPOSITORY", "fixture/P2pKit"),
                           ("GITHUB_SERVER_URL", "https://not-github.invalid"), ("GITHUB_API_URL", "bad"),
                           ("RUNNER_ENVIRONMENT", "self-hosted"), ("GITHUB_JOB", "other")):
            with self.subTest(key=key):
                self.env = dict(original, **{key: value})
                self.rejected("IDENTITY_HOSTED_CALLER")
        self.env = dict(original, GITHUB_WORKFLOW_SHA=BASE)
        self.rejected("IDENTITY_WORKFLOW")
        self.env = dict(original, GITHUB_WORKFLOW_REF="not-the-reviewed-workflow")
        self.rejected("IDENTITY_WORKFLOW")

    def test_no_nonordinary_or_unknown_events(self):
        for event in ("pull_request_target", "workflow_run", "repository_dispatch", "release", "unknown", None):
            with self.subTest(event=event):
                self.env["GITHUB_EVENT_NAME"] = event
                self.rejected("IDENTITY_EVENT")

    def test_native_labels_are_finite_and_full_ci_stays_on_mac(self):
        for host in (("Linux", "ARM64"), ("Windows", "ARM64"), ("Darwin", "ARM64"), ("Linux", None)):
            with self.subTest(host=host):
                self.env.update(RUNNER_OS=host[0], RUNNER_ARCH=host[1])
                self.rejected("IDENTITY_HOST_LABELS")
        self.full()
        self.env["RUNNER_OS"] = "Windows"
        self.env["RUNNER_ARCH"] = "X64"
        self.rejected("IDENTITY_HOST_LABELS")

    def test_identifiers_are_bounded_strings(self):
        for value in (None, True, 1, "", "0", "01", "1\n", "1" * 21):
            with self.subTest(value=value):
                self.env["GITHUB_RUN_ID"] = value
                self.rejected("IDENTITY_RUN")
        self.env["GITHUB_RUN_ID"] = "123"
        for value in ("a" * 7, "A" * 40, "1" * 39, "1" * 41, None, "1" * 40 + "\n"):
            with self.subTest(value=value):
                self.env["GITHUB_SHA"] = value
                self.rejected("IDENTITY_FULL_SHA")

    def test_dirty_wrong_root_or_wrong_checkout_does_not_admit(self):
        self.git.dirty = True
        self.rejected("IDENTITY_SOURCE")
        self.git.dirty = False
        self.git.root_correct = False
        self.rejected("IDENTITY_SOURCE")
        self.git.root_correct = True
        self.git.head = BASE
        self.rejected("IDENTITY_SOURCE")
        self.assertEqual(self.git.requested, [])

    def test_push_rejects_nonmain_deleted_mismatched_source_and_bad_repository(self):
        good = copy.deepcopy(self.event)
        for key, value in (("ref", "refs/heads/other"), ("deleted", True), ("after", BASE)):
            self.event = dict(good, **{key: value})
            self.rejected("IDENTITY_PUSH")
        self.event = good
        self.event["repository"]["default_branch"] = "other"
        self.rejected("IDENTITY_REPOSITORY")

    def test_policy_contract_rejects_extra_member_wrong_purpose_and_schema(self):
        for key, value in (("schema", True), ("schema", 2), ("purpose", "PRODUCTION"),
                           ("repository", "other/repo"), ("extra", "field")):
            item = policy()
            item[key] = value
            self.git.policies[SOURCE] = H.encoded(item)
            self.rejected("RECIPIENT_POLICY_CONTRACT")

    def test_policy_bounds_not_yet_valid_expired_retention_and_retrieval_owner(self):
        for key, value, error in (("notBefore", NOW + 1, "VALIDITY"), ("notBefore", True, "VALIDITY"),
                                   ("expiresAt", NOW, "VALIDITY"), ("expiresAt", NOW - 1, "VALIDITY"),
                                   ("retentionDays", 15, "RETENTION"), ("retentionDays", True, "RETENTION"),
                                   ("retrievalOwner", "", "RETRIEVAL_OWNER"),
                                   ("retrievalOwner", "owner\nsecret", "RETRIEVAL_OWNER")):
            with self.subTest(key=key, value=value):
                item = policy()
                item[key] = value
                self.git.policies[SOURCE] = H.encoded(item)
                self.rejected("RECIPIENT_POLICY_" + error)

    def test_policy_key_hash_full_fingerprint_and_public_only_framing(self):
        for key, value in (("sha256", "0" * 64), ("fingerprint", "A" * 16), ("fingerprint", "a" * 40),
                           ("publicKey", "private-key"), ("publicKey", KEY.decode() + "SECRET"),
                           ("publicKey", KEY.decode().replace("synthetic", "PRIVATE KEY")),
                           ("publicKey", "\u2603")):
            item = policy()
            item["recipient"][key] = value
            if key == "publicKey":
                item["recipient"]["sha256"] = hashlib.sha256(value.encode()).hexdigest()
            self.git.policies[SOURCE] = H.encoded(item)
            self.rejected("RECIPIENT_POLICY_KEY")

    def test_all_json_duplicate_nonfinite_nonobject_and_excess_inputs_rejected(self):
        for raw, reason in ((b'{"a":1,"a":2}', "DUPLICATE"), (b'{"a":NaN}', "NONFINITE"),
                             (b"[]", "OBJECT"), (b"{", "MALFORMED"), (b"", "SIZE"),
                             (b" " * (H.POLICY_LIMIT + 1), "SIZE")):
            self.git.policies[SOURCE] = raw
            self.rejected("IDENTITY_JSON_" + reason)

    def test_policy_rotation_after_admission_changes_immutable_binding(self):
        first = self.admit()
        changed = policy()
        changed["expiresAt"] = 3100
        self.git.policies[SOURCE] = H.encoded(changed)
        second = self.admit()
        self.assertNotEqual(first.record, second.record)
        self.assertNotEqual(first, second)
        # Mutating a decoded caller copy cannot alter the frozen record.
        decoded = json.loads(first.record)
        decoded["policy"]["commit"] = HEAD
        self.assertEqual(json.loads(first.record)["policy"]["commit"], SOURCE)

    def test_source_change_during_policy_read_is_not_admitted(self):
        self.git.clean = Mock(side_effect=[True, False])
        self.rejected("IDENTITY_SOURCE_CHANGED")

    def test_real_entrypoint_reseals_same_record_and_rejects_changed_policy(self):
        self.env["GITHUB_WORKSPACE"] = str(ROOT)
        self.env["GITHUB_EVENT_PATH"] = "/synthetic/original-event.json"
        with patch.dict(os.environ, self.env, clear=True), patch.object(H, "GitView", return_value=self.git), \
                patch.object(H, "read_regular", return_value=H.encoded(self.event)), \
                patch.object(H.time, "time", return_value=NOW):
            owner = Mock(side_effect=AssertionError("modeled Git does not call native owner"))
            first = H.admit(self.profile, ROOT, query_runner=owner)
            self.assertEqual(H.admit(self.profile, ROOT, query_runner=owner, expected=first), first)
            item = policy()
            item["expiresAt"] = 3001
            self.git.policies[SOURCE] = H.encoded(item)
            with self.assertRaisesRegex(H.AdmissionError, "^IDENTITY_CHANGED_BEFORE_SEAL$"):
                H.admit(self.profile, ROOT, query_runner=owner, expected=first)


class GitReaderTests(unittest.TestCase):
    def view(self, answers):
        value = object.__new__(H.GitView)
        value.query = Mock(side_effect=answers)
        return value

    def test_fixed_regular_policy_blob_full_bytes_are_hash_checked(self):
        raw = H.encoded(policy())
        expected = blob(raw)
        view = self.view([f"100644 blob {expected}\t{H.POLICY_PATH}\0".encode(), str(len(raw)).encode(), raw])
        self.assertEqual(view.policy(BASE), (expected, raw))
        self.assertEqual(view.query.call_args_list[0].args, ("ls-tree", "-z", BASE, "--", H.POLICY_PATH))
        self.assertEqual(view.query.call_args_list[-1].args, ("cat-file", "blob", expected))

    def test_commit_message_query_is_exact_immutable_and_bounded(self):
        view = self.view([b"[release ci]\n"])
        self.assertEqual(view.message(SOURCE), b"[release ci]\n")
        view.query.assert_called_once_with("show", "-s", "--format=%B", SOURCE, limit=65536)
        for ref in ("HEAD", "main", SOURCE[:12], SOURCE + "~1"):
            view = self.view([])
            with self.subTest(ref=ref), self.assertRaisesRegex(H.AdmissionError, "IDENTITY_FULL_SHA"):
                view.message(ref)
            view.query.assert_not_called()

    def test_all_eight_abi_references_are_exact_full_sha_regular_blobs(self):
        for path in H.abi.BASELINES:
            with self.subTest(path=path):
                raw = ("synthetic reference " + path + "\n").encode()
                expected = H.abi.blob(raw)
                view = self.view([f"100644 blob {expected}\t{path}\0".encode(), str(len(raw)).encode(), raw])
                self.assertEqual(view.abi_baseline(BASE, path), (expected, raw))
                self.assertEqual(view.query.call_args_list[0].args, ("ls-tree", "-z", BASE, "--", path))
                self.assertEqual(view.query.call_args_list[2].kwargs, {"limit": 1024 * 1024})
                self.assertEqual(view.query.call_count, 3)

    def test_abi_reader_refuses_every_nonclosed_path_or_mutable_ref_before_query(self):
        for path in (H.POLICY_PATH, "private.key", "library/p2p-core/api/../api/p2p-core.klib.api",
                     H.abi.BASELINES[0] + "/", "/" + H.abi.BASELINES[0], True):
            view = self.view([])
            with self.subTest(path=path), self.assertRaisesRegex(H.AdmissionError, "ABI_BASELINE_CLOSED_PATH"):
                view.abi_baseline(BASE, path)
            view.query.assert_not_called()
        for commit in ("main", "HEAD", "refs/heads/main", BASE + "~1", BASE[:12], True):
            view = self.view([])
            with self.subTest(commit=commit), self.assertRaisesRegex(H.AdmissionError, "IDENTITY_FULL_SHA"):
                view.abi_baseline(commit, H.abi.BASELINES[0])
            view.query.assert_not_called()

    def test_abi_reader_rejects_tree_alias_links_modes_duplicates_and_wrong_path(self):
        path = H.abi.BASELINES[0]
        good = f"100644 blob {HEAD}\t{path}\0".encode()
        values = [b"", good[:-1], good + good, good.replace(b"100644", b"120000"),
                  good.replace(b"100644", b"100755"), good.replace(b"blob", b"tree"),
                  good.replace(path.encode(), H.abi.BASELINES[1].encode()), good.replace(HEAD.encode(), b"bad")]
        for value in values:
            with self.subTest(value=value):
                view = self.view([value])
                with self.assertRaisesRegex(H.AdmissionError, "ABI_BASELINE_REGULAR_BLOB_REQUIRED"):
                    view.abi_baseline(BASE, path)
                self.assertEqual(view.query.call_count, 1)

    def test_abi_reader_refuses_bad_size_truncation_growth_and_wrong_blob(self):
        path, raw = H.abi.BASELINES[0], b"synthetic\n"
        entry = f"100644 blob {H.abi.blob(raw)}\t{path}\0".encode()
        for size in (b"0", b"01", b"-1", b"NaN", str(H.abi.FILE_LIMIT + 1).encode()):
            view = self.view([entry, size])
            with self.subTest(size=size), self.assertRaisesRegex(H.AdmissionError, "ABI_BASELINE_SIZE"):
                view.abi_baseline(BASE, path)
            self.assertEqual(view.query.call_count, 2)
        for changed in (raw[:-1], raw + b"x", b"!" + raw[1:]):
            view = self.view([entry, str(len(raw)).encode(), changed])
            with self.subTest(changed=changed), self.assertRaises(H.AdmissionError):
                view.abi_baseline(BASE, path)

    def test_missing_symlink_executable_or_duplicate_policy_is_rejected(self):
        for raw in (b"", f"120000 blob {HEAD}\t{H.POLICY_PATH}\0".encode(),
                    f"100755 blob {HEAD}\t{H.POLICY_PATH}\0".encode(),
                    (f"100644 blob {HEAD}\t{H.POLICY_PATH}\0" * 2).encode()):
            view = self.view([raw])
            with self.assertRaisesRegex(H.AdmissionError, "MISSING_TRUSTED_RECIPIENT_POLICY"):
                view.policy(BASE)
            self.assertEqual(view.query.call_count, 1)

    def test_oversized_or_changed_policy_blob_is_rejected(self):
        entry = f"100644 blob {HEAD}\t{H.POLICY_PATH}\0".encode()
        for size in (b"0", b"01", str(H.POLICY_LIMIT + 1).encode()):
            view = self.view([entry, size])
            with self.assertRaisesRegex(H.AdmissionError, "RECIPIENT_POLICY_SIZE"):
                view.policy(BASE)
        view = self.view([entry, b"2", b"{}"])
        with self.assertRaisesRegex(H.AdmissionError, "RECIPIENT_POLICY_BLOB"):
            view.policy(BASE)

    def test_git_failure_never_exposes_raw_stderr_or_invokes_shell(self):
        view = object.__new__(H.GitView)
        view.executable, view.root, view.environment = "/synthetic/git", Path("/synthetic/repo"), {"SAFE": "1"}
        view.query_runner = Mock(side_effect=RuntimeError("private-token-and-path"))
        with self.assertRaisesRegex(H.AdmissionError, "^IDENTITY_GIT_QUERY_FAILED$"):
            view.query("status")
        self.assertEqual(view.query_runner.call_args.kwargs, {
            "argv": ("/synthetic/git", "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false",
                     "-C", "/synthetic/repo", "status"),
            "cwd": Path("/synthetic/repo"), "environment": {"SAFE": "1"},
            "stdout_limit": 4096, "stderr_limit": 4096, "timeout_seconds": 15,
        })

    def test_constructor_preserves_canonical_windows_systemroot(self):
        # Only the module's platform view changes, not pathlib or the host OS.
        windows = SimpleNamespace(name="nt", defpath="synthetic-path", devnull="synthetic-null")
        with patch.object(H, "os", windows), patch.object(H.shutil, "which", return_value=__file__):
            view = H.GitView(ROOT, {"SYSTEMROOT": r"C:\Windows", "GH_TOKEN": "never inherited"}, Mock())
        self.assertEqual(view.environment["SYSTEMROOT"], r"C:\Windows")
        self.assertNotIn("GH_TOKEN", view.environment)
        self.assertEqual(view.environment["GIT_NO_LAZY_FETCH"], "1")
        self.assertEqual(view.environment["GIT_OPTIONAL_LOCKS"], "0")

    def test_no_spawning_fallback_without_explicit_owned_runner(self):
        for owner in (None, False, "not-an-owner"):
            with self.subTest(owner=owner), \
                    patch.object(subprocess, "Popen", side_effect=AssertionError("no fallback child")), \
                    self.assertRaisesRegex(H.AdmissionError, "^IDENTITY_OWNED_QUERY_REQUIRED$"):
                H.GitView(ROOT, {}, owner)

    def test_runner_return_type_and_size_are_rechecked_not_treated_as_live_bound(self):
        view = object.__new__(H.GitView)
        view.executable, view.root, view.environment = "/synthetic/git", ROOT, {}
        for raw in (b"x" * 32, "text", bytearray(b"bytes"), None):
            with self.subTest(raw=type(raw)):
                view.query_runner = Mock(return_value=raw)
                with self.assertRaisesRegex(H.AdmissionError, "^IDENTITY_GIT_QUERY_OUTPUT$"):
                    view.query("status", limit=31)
        for raw in (b"", b"x" * 31):
            view.query_runner = Mock(return_value=raw)
            self.assertEqual(view.query("status", limit=31), raw)
            self.assertEqual(view.query_runner.call_args.kwargs["stdout_limit"], 31)

    def test_bad_query_limit_rejects_before_owner_and_cancellation_is_not_replaced(self):
        view = object.__new__(H.GitView)
        view.executable, view.root, view.environment = "/synthetic/git", ROOT, {}
        view.query_runner = Mock(side_effect=KeyboardInterrupt())
        for limit in (True, 0, -1, H.EVENT_LIMIT + 1):
            with self.assertRaisesRegex(H.AdmissionError, "^IDENTITY_GIT_OUTPUT_LIMIT$"):
                view.query("status", limit=limit)
        view.query_runner.assert_not_called()
        with self.assertRaises(KeyboardInterrupt):
            view.query("status")

    def test_owner_injects_markers_without_mutating_base_environment(self):
        view = object.__new__(H.GitView)
        view.executable, view.root, view.environment = "/synthetic/git", ROOT, {"SAFE": "1"}

        def owned_query(**request):
            request["environment"]["P2PKIT_AUDIT_OWNERSHIP_CHAIN"] = "modeled-owner-authority"
            return b""

        view.query_runner = owned_query
        self.assertEqual(view.query("status"), b"")
        self.assertEqual(view.environment, {"SAFE": "1"})


if __name__ == "__main__":
    unittest.main(verbosity=2)
