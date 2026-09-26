#!/usr/bin/env python3
"""Offline synthetic Portal-original joins; no upload, credentials or build."""

import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SPEC = importlib.util.spec_from_file_location("deployment", Path(__file__).resolve().parents[1] / "central_deployment_evidence.py")
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)
P = D.P
SOURCE, TREE = "a" * 40, "b" * 40
ID = "01234567-89ab-cdef-0123-456789abcdef"
VERSION = "0.8.0-rc1"


class DeploymentEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.context = {"source": SOURCE, "tag": "v" + VERSION, "id": 123, "attempt": 2}
        self.summary = {"schemaVersion": 2, "group": "io.github.apdelrahman1911", "version": VERSION,
                        "sourceSha": SOURCE, "sourceTree": TREE, "bundleFile": f"p2pkit-{VERSION}-central-bundle.zip",
                        "bundleSizeBytes": 1234, "bundleSha256": "c" * 64, "manifestSha256": "d" * 64,
                        "publicKeySha256": "e" * 64}
        self.events = [
            {"timestamp": "2026-09-25T00:00:00.000Z", "event": "upload_started", "state": "LOCAL",
             "detail": f"p2pkit-{VERSION}-{SOURCE[:12]}"},
            {"timestamp": "2026-09-25T00:00:01.000Z", "event": "upload_accepted", "state": "PENDING", "detail": ID},
            {"timestamp": "2026-09-25T00:00:02.000Z", "event": "deployment_state", "state": "PUBLISHED", "detail": "poll_1"},
            {"timestamp": "2026-09-25T00:00:02.000Z", "event": "publication_completed", "state": "PUBLISHED", "detail": ID},
        ]
        self.originals = {"bundle.sha256": ("c" * 64 + "\n").encode(), "commit-sha.txt": (SOURCE + "\n").encode(),
                          "deployment-id.txt": (ID + "\n").encode(), "status.json": P.encoded({"deploymentState": "PUBLISHED"})}

    def make(self):
        import json
        originals = {**self.originals, "portal-events.jsonl": b"".join(
            (json.dumps(x, separators=(",", ":")) + "\n").encode() for x in self.events)}
        return D.receipt(self.context, TREE, P.encoded(self.summary), originals)

    def test_original_completed_join_is_bound_not_a_recovery_verdict(self):
        value = self.make()
        self.assertEqual(value["scope"], "ORIGINAL_CENTRAL_PUBLISHED_DEPLOYMENT")
        self.assertEqual(value["source"], {"commit": SOURCE, "tree": TREE})
        self.assertEqual(value["invocation"]["attempt"], 2)
        self.assertEqual(value["deployment"]["id"], ID)
        self.assertEqual(set(value["originals"]), set(D.FILES))
        self.assertEqual(value["originals"]["status.json"], D.descriptor(self.originals["status.json"]))
        self.assertNotIn("approval", value)

    def test_missing_original_cannot_be_reconstructed(self):
        for name in list(self.originals):
            with self.subTest(name=name):
                value = self.originals.pop(name)
                with self.assertRaises(ValueError):
                    self.make()
                self.originals[name] = value

    def test_summary_schema_source_tree_version_size_and_hash_are_not_interchangeable(self):
        for key, value in (("schemaVersion", 1), ("sourceSha", "f" * 40), ("sourceTree", "f" * 40),
                           ("version", "0.8.0-rc2"), ("bundleFile", "other.zip"), ("group", "io.github.other"),
                           ("bundleSizeBytes", True), ("bundleSizeBytes", 0), ("bundleSha256", "x" * 64),
                           ("manifestSha256", ""), ("publicKeySha256", None)):
            with self.subTest(key=key, value=value):
                original = self.summary[key]
                self.summary[key] = value
                with self.assertRaises((ValueError, TypeError)):
                    self.make()
                self.summary[key] = original

    def test_attempt_requires_a_real_positive_identity(self):
        self.context["attempt"] = True
        with self.assertRaises(ValueError):
            self.make()

    def test_upload_source_bundle_and_deployment_must_join(self):
        for name in ("bundle.sha256", "commit-sha.txt", "deployment-id.txt"):
            with self.subTest(name=name):
                original = self.originals[name]
                self.originals[name] = b"different-original\n"
                with self.assertRaises(ValueError):
                    self.make()
                self.originals[name] = original

    def test_accepted_is_not_published(self):
        self.originals["status.json"] = P.encoded({"deploymentState": "VALIDATED"})
        with self.assertRaises(ValueError):
            self.make()

    def test_status_cannot_name_another_deployment(self):
        self.originals["status.json"] = P.encoded({"deploymentState": "PUBLISHED", "deploymentId": "another"})
        with self.assertRaises(ValueError):
            self.make()

    def test_failed_ambiguous_reordered_or_duplicate_events_hold(self):
        original = copy.deepcopy(self.events)
        for change in (
            lambda: self.events[1].update(event="upload_ambiguous"),
            lambda: self.events[2].update(state="FAILED"),
            lambda: self.events.append(copy.deepcopy(self.events[-1])),
            lambda: self.events[1].update(detail="another"),
            lambda: self.events[0].update(detail="other-source"),
            lambda: self.events[2].update(timestamp="2026-09-24T00:00:00.000Z"),
            lambda: self.events[2].update(timestamp="invalid"),
            lambda: self.events.pop(2),
        ):
            self.events = copy.deepcopy(original)
            change()
            with self.assertRaises(ValueError):
                self.make()

    def test_json_duplicates_are_rejected(self):
        self.originals["status.json"] = b'{"deploymentState":"PUBLISHED","deploymentState":"FAILED"}'
        with self.assertRaises(ValueError):
            self.make()

    def test_post_terminal_or_impossible_retry_sequences_are_rejected(self):
        original = copy.deepcopy(self.events)
        for event in (
            {"event": "deployment_state", "state": "VALIDATING", "detail": "poll_2"},
            {"event": "deployment_state", "state": "PUBLISHED", "detail": "poll_2"},
            {"event": "status_retry", "state": "PUBLISHED", "detail": "http_500"},
        ):
            self.events = copy.deepcopy(original)
            self.events.insert(-1, {"timestamp": "2026-09-25T00:00:02.000Z", **event})
            with self.subTest(event=event), self.assertRaises(ValueError):
                self.make()
        for event in (
            {"event": "status_retry", "state": "PENDING", "detail": "http_500"},
            {"event": "status_retry", "state": "", "detail": "http_401"},
            {"event": "status_retry", "state": "", "detail": "curl_exit_0"},
            {"event": "deployment_state", "state": "PENDING", "detail": "poll_0"},
            {"event": "deployment_state", "state": "PENDING", "detail": "poll_121"},
        ):
            self.events = copy.deepcopy(original)
            self.events[2]["detail"] = "poll_3"
            self.events.insert(2, {"timestamp": "2026-09-25T00:00:01.000Z", **event})
            with self.subTest(event=event), self.assertRaises(ValueError):
                self.make()

    def test_state_preserving_bounded_retries_match_real_uploader(self):
        self.events[2]["detail"] = "poll_3"
        self.events.insert(2, {"timestamp": "2026-09-25T00:00:01.000Z", "event": "status_retry",
                               "state": "", "detail": "http_429"})
        self.events.insert(3, {"timestamp": "2026-09-25T00:00:01.000Z", "event": "status_retry",
                               "state": "", "detail": "curl_exit_28"})
        self.assertEqual(self.make()["deployment"]["state"], "PUBLISHED")

    def test_file_reads_reject_links_empty_and_oversized_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "original"
            path.write_bytes(b"synthetic")
            self.assertEqual(D.read(path), b"synthetic")
            link = path.with_name("link")
            link.symlink_to(path)
            with self.assertRaises(ValueError):
                D.read(link)
            with self.assertRaises(ValueError):
                D.read(path, 1)
            link.unlink()
            os.link(path, link)
            with self.assertRaises(ValueError):
                D.read(path)
            link.unlink()
            path.write_bytes(b"")
            with self.assertRaises(ValueError):
                D.read(path)

    def test_local_environment_never_records_hosted_receipt(self):
        with mock.patch.dict(os.environ, {}, clear=True), self.assertRaises(ValueError):
            D.F.hosted_context(os.environ, "revalidate")


if __name__ == "__main__":
    unittest.main()
