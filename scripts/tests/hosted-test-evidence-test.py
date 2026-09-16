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


if __name__ == "__main__":
    unittest.main(verbosity=2)
