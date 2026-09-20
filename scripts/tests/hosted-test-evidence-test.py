#!/usr/bin/env python3
"""Pure closed-entry wiring tests: all Git, crypto and native work is mocked."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_evidence as H
import hosted_test_evidence as E
import hosted_test_identity as I
import hosted_cache_bootstrap_identity as B
import hosted_windows_evidence as W


class OrdinaryExportTests(unittest.TestCase):
    def setUp(self):
        record = {"schema": 1, "scope": "ORDINARY_HOSTED_TEST_CUSTODY_IDENTITY", "profile": "desktop",
                  "suites": ["cli"], "source": {"commit": "1" * 40, "tree": "2" * 40},
                  "github": {"event": "pull_request", "runId": "123", "runAttempt": "1"},
                  "policy": {"commit": "3" * 40, "sha256": "a" * 64}}
        self.admission = I.Admission(I.encoded(record), b"synthetic-event", b"synthetic-policy",
                                     b"synthetic-public-key", "A" * 40, "b" * 64, 3000)
        self.recipient = H.Recipient(Path("/synthetic/work"), Path("/synthetic/work/gpg"),
                                     Path("/synthetic/gpg"), "A" * 40, "B" * 40, 4000, "b" * 64, (1, 2))
        self.query_runner = Mock(side_effect=AssertionError("native query must not run in pure controls"))
        self.admit = patch.object(I, "admit", return_value=self.admission)
        self.mechanism = patch.object(H, "_export_bound_manifest", return_value={"synthetic": "not encrypted"})
        self.accepted = self.admit.start()
        self.exporter = self.mechanism.start()
        self.addCleanup(self.admit.stop)
        self.addCleanup(self.mechanism.stop)

    def export(self, **changes):
        args = {"profile": "desktop", "root": ROOT, "admission": self.admission, "query_runner": self.query_runner,
                "max_bytes": 1234, "max_members": 20, "timeout_seconds": 30}
        args.update(changes)
        return E.export_encrypted("/synthetic/evidence", "/synthetic/output", self.recipient, **args)

    def test_ordinary_entry_revalidates_exact_admission_without_manual_identity(self):
        with patch.object(H, "_manifest_identity", side_effect=AssertionError("must not impersonate manual")):
            self.assertEqual(self.export(), {"synthetic": "not encrypted"})
        self.accepted.assert_called_once_with("desktop", ROOT, query_runner=self.query_runner,
                                              expected=self.admission)
        args = self.exporter.call_args.kwargs
        self.assertEqual((args["max_bytes"], args["max_members"], args["timeout_seconds"]), (1234, 20, 30))
        self.assertEqual(args["manifest"]["schema"], 2)
        self.assertEqual(args["manifest"]["github"]["event"], "pull_request")
        self.assertEqual(args["manifest"]["custody"], {"profile": "desktop", "suites": ["cli"]})
        self.assertNotIn("synthetic-public-key", json.dumps(args["manifest"]))

    def test_changed_actual_event_source_or_policy_rejects_before_export(self):
        self.accepted.side_effect = I.AdmissionError("IDENTITY_CHANGED_BEFORE_SEAL")
        with self.assertRaisesRegex(I.AdmissionError, "IDENTITY_CHANGED_BEFORE_SEAL"):
            self.export()
        self.exporter.assert_not_called()

    def test_recipient_fingerprint_or_key_bytes_cannot_substitute(self):
        import dataclasses
        original = self.recipient
        for changes in ({"fingerprint": "C" * 40}, {"key_sha256": "c" * 64}):
            self.recipient = dataclasses.replace(original, **changes)
            with self.assertRaisesRegex(H.EvidenceError, "recipient differs"):
                self.export()
        self.exporter.assert_not_called()

    def test_policy_cannot_outlive_cryptographically_validated_key(self):
        import dataclasses
        self.recipient = dataclasses.replace(self.recipient, expires_at=2999)
        with self.assertRaisesRegex(H.EvidenceError, "validity exceeds"):
            self.export()
        self.exporter.assert_not_called()

    def test_native_export_or_cleanup_failure_is_not_success(self):
        self.exporter.side_effect = H.EvidenceError("synthetic encryption or retirement failure")
        with self.assertRaisesRegex(H.EvidenceError, "synthetic encryption"):
            self.export()

    def test_windows_cannot_fall_back_to_posix_permission_bits(self):
        with patch.object(E.os, "name", "nt"):
            with self.assertRaisesRegex(H.EvidenceError, "native filesystem backend"):
                self.export()
        self.accepted.assert_not_called()
        self.exporter.assert_not_called()


class ManualEntryTests(unittest.TestCase):
    def test_original_manual_entry_still_requires_original_actual_identity(self):
        with patch.object(H, "_manifest_identity", side_effect=H.EvidenceError("actual manual environment required")), \
                patch.object(H, "_export_bound_manifest") as core:
            with self.assertRaisesRegex(H.EvidenceError, "actual manual environment required"):
                H.export_encrypted("unused", "unused", Mock(), source_commit="1" * 40, source_tree="2" * 40,
                                   run_id="123", run_attempt="1")
            core.assert_not_called()

    def test_original_manual_entry_forwards_only_its_checked_manifest(self):
        manifest = {"schema": 1, "scope": "ENCRYPTED_PRIVATE_TEST_EVIDENCE", "synthetic": "identity"}
        with patch.object(H, "_manifest_identity", return_value=manifest) as identity, \
                patch.object(H, "_export_bound_manifest", return_value={"synthetic": "core"}) as core:
            value = H.export_encrypted("input", "output", "recipient", source_commit="1" * 40,
                                        source_tree="2" * 40, run_id="123", run_attempt="1")
        self.assertEqual(value, {"synthetic": "core"})
        identity.assert_called_once_with("1" * 40, "2" * 40, "123", "1")
        self.assertIs(core.call_args.kwargs["manifest"], manifest)

    def test_shared_core_rejects_expanded_bounds_before_filesystem_use(self):
        for change in ({"max_bytes": H.MAX_BYTES + 1}, {"max_members": 0}, {"timeout_seconds": True}):
            args = {"max_bytes": H.MAX_BYTES, "max_members": H.MAX_MEMBERS,
                    "timeout_seconds": H.MAX_TIMEOUT_SECONDS}
            args.update(change)
            with patch.object(H, "_private_directory", side_effect=AssertionError("must reject before filesystem")):
                with self.assertRaisesRegex(H.EvidenceError, "Evidence bounds"):
                    H._export_bound_manifest("unused", "unused", Mock(), manifest={}, **args)


class BootstrapExportTests(unittest.TestCase):
    """Closed adapter models, not crypto, native custody or hosted admission."""

    selections = (
        ("desktop-linux-x64", "desktop", "linux-x64", "Linux", "X64"),
        ("desktop-windows-x64", "desktop", "windows-x64", "Windows", "X64"),
        ("desktop-macos-arm64", "desktop", "macos-arm64", "macOS", "ARM64"),
        ("desktop-macos-x64", "desktop", "macos-x64", "macOS", "X64"),
        ("full-macos-arm64", "full", "macos-arm64", "macOS", "ARM64"),
        ("full-macos-x64", "full", "macos-x64", "macOS", "X64"),
    )

    def setUp(self):
        # Reuse the existing synthetic identity fixture, never a real key/event.
        spec = importlib.util.spec_from_file_location("bootstrap_identity_fixture",
            ROOT / "scripts/tests/hosted-cache-bootstrap-identity-test.py")
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        self.fixture = fixture.OfflineCase()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.admission = self.fixture.admit()  # Actual pure decision over ModelGit.
        self.recipient = H.Recipient(Path("/synthetic/work"), Path("/synthetic/work/gpg"),
            Path("/synthetic/gpg"), "A" * 40, "B" * 40, 4000, self.admission.key_sha256, (1, 2))
        self.query_runner = Mock(side_effect=AssertionError("native query forbidden"))
        self.real_admit = B.admit
        admission_patch = patch.object(B, "admit", return_value=self.admission)
        export_patch = patch.object(H, "_export_bound_manifest", return_value={"synthetic": "not encrypted"})
        self.accepted, self.exporter = admission_patch.start(), export_patch.start()
        self.addCleanup(admission_patch.stop)
        self.addCleanup(export_patch.stop)

    def export(self, **changes):
        args = {"root": ROOT, "admission": self.admission, "query_runner": self.query_runner,
                "max_bytes": 1234, "max_members": 20, "timeout_seconds": 30}
        args.update(changes)
        return E.export_bootstrap_encrypted("/synthetic/evidence", "/synthetic/output", self.recipient, **args)

    def windows(self, **changes):
        args = {"root": ROOT, "admission": self.admission, "query_runner": self.query_runner,
                "max_bytes": 1234, "max_members": 20, "timeout_seconds": 30}
        args.update(changes)
        # Path strings/portable Recipient are stand-ins; _export is mocked here.
        return W.export_bootstrap_encrypted("synthetic-native-evidence", "synthetic-native-output",
                                            self.recipient, **args)

    def test_six_selections_keep_bootstrap_execution_distinct_from_cache_cohort(self):
        with patch.object(I, "admit", side_effect=AssertionError("ordinary admission forbidden")), \
                patch.object(H, "_manifest_identity", side_effect=AssertionError("manual admission forbidden")):
            for name, profile, role, system, arch in self.selections:
                self.fixture.env.update(RUNNER_OS=system, RUNNER_ARCH=arch)
                self.fixture.event["inputs"]["selection"] = name
                self.admission = self.fixture.admit()
                self.accepted.return_value = self.admission
                self.assertEqual(self.export(), {"synthetic": "not encrypted"})
                self.assertIs(self.accepted.call_args.kwargs["expected"], self.admission)
                self.accepted.assert_called_with(ROOT, query_runner=self.query_runner, expected=self.admission)
                manifest = self.exporter.call_args.kwargs["manifest"]
                self.assertEqual(manifest["schema"], 3)
                self.assertEqual(manifest["scope"], "ENCRYPTED_PRIVATE_CACHE_BOOTSTRAP_EVIDENCE")
                self.assertEqual(manifest["custody"], {"profile": "cache-bootstrap", "selection": name,
                    "cacheCohort": {"profile": profile, "role": role},
                    "producerCommand": ["help", "--console=plain", "--no-configure-on-demand"],
                    "producerScope": "CONFIGURATION_ONLY_NOT_COMPLETE_DEPENDENCIES_OR_TESTS",
                    "testAcceptance": "NOT_PERFORMED"})

    def test_public_manifest_contains_only_closed_identity_and_no_private_originals(self):
        self.export()
        manifest = self.exporter.call_args.kwargs["manifest"]
        self.assertEqual(set(manifest), {"schema", "scope", "source", "github", "policy", "custody"})
        original = json.loads(self.admission.record)
        for name in ("source", "github", "policy"):
            self.assertEqual(manifest[name], original[name])
        raw = json.dumps(manifest)
        for private in (self.admission.public_key.decode(), "synthetic/evidence", "fixture-owner", "suites"):
            self.assertNotIn(private, raw)
        manifest["custody"]["testAcceptance"] = "changed model output"
        self.export()
        self.assertEqual(self.exporter.call_args.kwargs["manifest"]["custody"]["testAcceptance"], "NOT_PERFORMED")
        self.assertEqual(json.loads(self.admission.record), original)

    def test_original_admission_is_mandatory_before_any_admission_or_export(self):
        for value in (None, {}, self.admission.record, Mock()):
            with self.subTest(kind=type(value).__name__), self.assertRaisesRegex(H.EvidenceError, "original admission"):
                self.export(admission=value)
        self.accepted.assert_not_called()
        self.exporter.assert_not_called()

    def test_readmission_refusal_and_cancellation_propagate_without_export(self):
        for error in (I.AdmissionError("BOOTSTRAP_CHANGED_BEFORE_SEAL"), KeyboardInterrupt()):
            self.accepted.side_effect = error
            with self.assertRaises(type(error)) as raised:
                self.export()
            self.assertIs(raised.exception, error)
        self.exporter.assert_not_called()

    def test_real_admission_entry_keeps_missing_original_main_policy_a_refusal_in_model(self):
        self.accepted.side_effect = self.real_admit
        env = {**self.fixture.env, "GITHUB_WORKSPACE": str(ROOT), "GITHUB_EVENT_PATH": "/synthetic/event"}
        with patch.dict(B.os.environ, env, clear=True), \
                patch.object(I, "read_regular", return_value=I.encoded(self.fixture.event)), \
                patch.object(I, "GitView", return_value=self.fixture.git), patch.object(B.time, "time", return_value=2000):
            self.export()
            self.assertEqual(self.fixture.git.policy_reads, ["3" * 40, "3" * 40])
            self.exporter.reset_mock()
            del self.fixture.git.policies["3" * 40]
            with self.assertRaisesRegex(I.AdmissionError, "MISSING_TRUSTED_RECIPIENT_POLICY"):
                self.export()
        self.exporter.assert_not_called()
        self.assertNotIn("1" * 40, self.fixture.git.policy_reads)

    def test_ordinary_and_relabelled_bootstrap_records_cannot_fill_this_identity(self):
        import dataclasses
        ordinary = {"schema": 1, "scope": "ORDINARY_HOSTED_TEST_CUSTODY_IDENTITY", "profile": "full"}
        relabelled = json.loads(self.admission.record)
        relabelled["profile"] = "full"
        for record in (ordinary, relabelled):
            self.accepted.return_value = dataclasses.replace(self.admission, record=I.encoded(record))
            with self.assertRaises((H.EvidenceError, I.AdmissionError)):
                self.export()
        self.exporter.assert_not_called()

    def test_recipient_fingerprint_and_exact_armor_hash_cannot_be_substituted(self):
        import dataclasses
        original = self.recipient
        for changes in ({"fingerprint": "C" * 40}, {"key_sha256": "c" * 64}):
            self.recipient = dataclasses.replace(original, **changes)
            with self.assertRaisesRegex(H.EvidenceError, "recipient differs"):
                self.export()
        self.exporter.assert_not_called()

    def test_policy_expiry_cannot_exceed_validated_recipient_expiry(self):
        import dataclasses
        self.recipient = dataclasses.replace(self.recipient, expires_at=2999)
        with self.assertRaisesRegex(H.EvidenceError, "validity exceeds"):
            self.export()
        self.exporter.assert_not_called()
        self.recipient = dataclasses.replace(self.recipient, expires_at=3000)
        self.export()
        self.exporter.assert_called_once()

    def test_relative_bounds_cannot_be_expanded_or_disabled_before_admission(self):
        for changes in ({"timeout_seconds": 241}, {"timeout_seconds": 900}, {"timeout_seconds": 0},
                        {"timeout_seconds": True}, {"timeout_seconds": 30.0},
                        {"max_bytes": H.MAX_BYTES + 1}, {"max_bytes": -1}, {"max_bytes": True},
                        {"max_members": H.MAX_MEMBERS + 1}, {"max_members": 0}):
            with self.subTest(changes=changes), self.assertRaisesRegex(H.EvidenceError, "bounds"):
                self.export(**changes)
        self.accepted.assert_not_called()
        self.exporter.assert_not_called()

    def test_exact_limits_and_shorter_values_are_forwarded_not_renewed_by_adapter(self):
        self.export(timeout_seconds=240, max_bytes=H.MAX_BYTES, max_members=H.MAX_MEMBERS)
        self.assertEqual({name: self.exporter.call_args.kwargs[name] for name in
            ("max_bytes", "max_members", "timeout_seconds")},
            {"max_bytes": 512 * 1024 * 1024, "max_members": 10000, "timeout_seconds": 240})
        self.export(timeout_seconds=1, max_bytes=1, max_members=1)
        self.assertEqual(self.exporter.call_args.kwargs["timeout_seconds"], 1)

    def test_caller_manifest_and_missing_explicit_timeout_are_not_supported(self):
        with self.assertRaises(TypeError):
            self.export(manifest={"schema": 2})
        with self.assertRaises(TypeError):
            E.export_bootstrap_encrypted("unused", "unused", self.recipient, root=ROOT,
                                         admission=self.admission, query_runner=self.query_runner)
        self.accepted.assert_not_called()
        self.exporter.assert_not_called()

    def test_posix_entry_refuses_windows_before_any_admission_or_mechanism(self):
        with patch.object(E.os, "name", "nt"):
            with self.assertRaisesRegex(H.EvidenceError, "native filesystem backend"):
                self.export()
        self.accepted.assert_not_called()
        self.exporter.assert_not_called()

    def test_encryption_or_unknown_retirement_failure_is_never_relabelled_success(self):
        error = H.EvidenceError("synthetic encryption failure")
        error.retirement_unknown = True
        self.exporter.side_effect = error
        with self.assertRaises(H.EvidenceError) as raised:
            self.export()
        self.assertIs(raised.exception, error)
        self.assertTrue(raised.exception.retirement_unknown)

    def test_windows_uses_only_native_mechanism_and_repeatable_closed_manifest_factory(self):
        def native(evidence, output, recipient, factory, **limits):
            self.assertEqual((evidence, output), ("synthetic-native-evidence", "synthetic-native-output"))
            self.assertIs(recipient, self.recipient)
            self.assertEqual(limits, {"max_bytes": 1234, "max_members": 20, "timeout_seconds": 30})
            first, second = factory(), factory()
            self.assertEqual(first, second)
            self.assertIsNot(first, second)
            self.assertEqual(first["scope"], "ENCRYPTED_PRIVATE_CACHE_BOOTSTRAP_EVIDENCE")
            return {"synthetic": "native mechanism not executed"}
        with patch.object(W, "_export", side_effect=native):
            self.assertEqual(self.windows(), {"synthetic": "native mechanism not executed"})
        self.assertEqual(self.accepted.call_count, 2)
        self.exporter.assert_not_called()

    def test_windows_bounds_refuse_before_native_mechanism(self):
        with patch.object(W, "_export") as native:
            with self.assertRaisesRegex(H.EvidenceError, "bounds"):
                self.windows(timeout_seconds=241)
            native.assert_not_called()
        self.accepted.assert_not_called()

    def test_windows_final_identity_refusal_and_native_failure_propagate(self):
        error = I.AdmissionError("BOOTSTRAP_CHANGED_BEFORE_SEAL")
        self.accepted.side_effect = (self.admission, error)
        def native(evidence, output, recipient, factory, **limits):
            factory()
            return factory()
        with patch.object(W, "_export", side_effect=native), self.assertRaises(I.AdmissionError) as raised:
            self.windows()
        self.assertIs(raised.exception, error)
        failure = H.EvidenceError("synthetic native UNKNOWN")
        failure.retirement_unknown = True
        with patch.object(W, "_export", side_effect=failure), self.assertRaises(H.EvidenceError) as raised:
            self.windows()
        self.assertIs(raised.exception, failure)


if __name__ == "__main__":
    unittest.main(verbosity=2)
