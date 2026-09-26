#!/usr/bin/env python3
"""Offline encrypted-export controls using disposable, explicitly synthetic keys.

Mocked run labels are parser fixtures, never a hosted-run or product-test claim.
No network, dependency download, user's keyring, or real evidence is accessed.
"""
from __future__ import annotations

import base64
import dataclasses
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("hosted_evidence", ROOT / "scripts/hosted_evidence.py")
H = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = H
SPEC.loader.exec_module(H)
SOURCE = "1" * 40
TREE = "2" * 40
SYNTHETIC_GITHUB = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": H.REPOSITORY,
                    "GITHUB_SHA": SOURCE, "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1",
                    "GITHUB_EVENT_NAME": "workflow_dispatch"}


class EncryptedEvidenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("gpg") is None or shutil.which("gpgconf") is None:
            raise RuntimeError("Installed GPG and gpgconf are required; do not download for these controls")
        # Deliberately short, owned path: macOS agent socket paths are bounded.
        cls.fixture = Path(tempfile.mkdtemp(prefix="p2phe-", dir=Path("/tmp").resolve()))
        cls.home = cls.fixture / "g"
        cls.home.mkdir(mode=0o700)
        cls.environment = {"PATH": os.defpath, "HOME": str(cls.fixture), "GNUPGHOME": str(cls.home),
                           "LC_ALL": "C", "LANG": "C", "TMPDIR": str(cls.fixture)}
        cls.gpg_path = str(Path(shutil.which("gpg")).resolve())
        cls.gpgconf_path = str(Path(shutil.which("gpgconf")).resolve())
        cls.addClassCleanup(cls.retire_fixture)
        cls.good = cls.create("P2pKit synthetic roundtrip <roundtrip@invalid>")
        cls.command(["--quick-add-key", cls.good, "cv25519", "encr", "1d"])
        cls.sign_only = cls.create("P2pKit synthetic signing only <sign@invalid>")
        cls.expired = cls.create("P2pKit synthetic expired <expired@invalid>", "20200101T000000")
        cls.command(["--faked-system-time", "20200101T000000", "--quick-add-key", cls.expired,
                     "cv25519", "encr", "1d"])
        cls.public = cls.command(["--armor", "--export", cls.good]).stdout
        cls.secret = cls.command(["--armor", "--export-secret-keys", cls.good]).stdout
        cls.sign_public = cls.command(["--armor", "--export", cls.sign_only]).stdout
        cls.expired_public = cls.command(["--armor", "--export", cls.expired]).stdout
        cls.multiple = cls.command(["--armor", "--export", cls.good, cls.sign_only]).stdout

    @classmethod
    def command(cls, arguments, input_data=None):
        return subprocess.run([cls.gpg_path, "--no-options", "--homedir", str(cls.home), "--batch",
                               "--no-tty", "--pinentry-mode", "loopback", "--passphrase", "",
                               "--no-auto-key-retrieve", "--auto-key-locate", "clear", "--disable-dirmngr",
                               *arguments], input=input_data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              cwd=cls.fixture, env=cls.environment, timeout=30, check=True)

    @classmethod
    def create(cls, uid, fake_time=None):
        options = ["--faked-system-time", fake_time] if fake_time else []
        result = cls.command(options + ["--status-fd", "1", "--quick-generate-key", uid, "ed25519", "cert", "1d"])
        records = [line.split()[-1] for line in result.stdout.decode("ascii").splitlines()
                   if line.startswith("[GNUPG:] KEY_CREATED ")]
        if len(records) != 1:
            raise RuntimeError("Synthetic fixture key creation did not return one fingerprint")
        return records[0]

    @classmethod
    def retire_fixture(cls):
        # Address only the agent of this exclusively owned synthetic test home.
        result = subprocess.run([cls.gpgconf_path, "--homedir", str(cls.home), "--kill", "gpg-agent"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=cls.environment,
                                cwd=cls.fixture, timeout=15, check=False)
        if result.returncode != 0:
            raise RuntimeError("Synthetic test agent retirement failed; keep its owned directory")
        end = time.monotonic() + 5
        while any(cls.home.glob("S.gpg-agent*")) and time.monotonic() < end:
            time.sleep(0.05)
        if any(cls.home.glob("S.gpg-agent*")):
            raise RuntimeError("Synthetic test agent socket retirement is unknown; retain fixture")
        shutil.rmtree(cls.fixture)  # Only wholly synthetic, exclusively owned test material.

    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="case-", dir=self.fixture))
        self.key = self.base / "recipient.asc"
        self.key.write_bytes(self.public)
        self.key.chmod(0o600)
        self.work = self.base / "work"
        self.work.mkdir(mode=0o700)
        self.evidence = self.base / "evidence"
        self.evidence.mkdir(mode=0o700)
        (self.evidence / "fixture.log").write_bytes(b"synthetic transcript\x00\xff\r\n")
        (self.evidence / "empty").write_bytes(b"")
        self.output = self.base / "upload"
        self.identity_patch = patch.dict(os.environ, SYNTHETIC_GITHUB)
        self.identity_patch.start()

    def tearDown(self):
        self.identity_patch.stop()
        shutil.rmtree(self.base)  # No real campaign input or output is used by any case.

    def recipient(self):
        return H.validate_recipient(self.key, self.good, self.work)

    def export(self, recipient=None, **changes):
        arguments = {"source_commit": SOURCE, "source_tree": TREE, "run_id": "123", "run_attempt": "1"}
        arguments.update(changes)
        return H.export_encrypted(self.evidence, self.output, recipient or self.recipient(), **arguments)

    def no_upload_or_plaintext(self):
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.work.glob("export-*")))

    def test_real_roundtrip_has_only_ciphertext_and_sanitized_manifest(self):
        recipient = self.recipient()
        result = self.export(recipient)
        self.assertEqual({H.ARTIFACT, H.MANIFEST}, {path.name for path in self.output.iterdir()})
        self.assertEqual(result, json.loads((self.output / H.MANIFEST).read_text()))
        self.assertEqual({"schema", "scope", "source", "github", "artifact"}, set(result))
        self.assertEqual({"commit": SOURCE, "tree": TREE}, result["source"])
        ciphertext = (self.output / H.ARTIFACT).read_bytes()
        self.assertEqual(hashlib.sha256(ciphertext).hexdigest(), result["artifact"]["sha256"])
        self.assertEqual(len(ciphertext), result["artifact"]["size"])
        self.assertNotIn(b"synthetic transcript", ciphertext)
        self.assertNotIn(b"fixture.log", (self.output / H.MANIFEST).read_bytes())
        decrypted = self.command(["--status-fd", "2", "--decrypt", str(self.output / H.ARTIFACT)])
        self.assertIn(b"[GNUPG:] DECRYPTION_OKAY", decrypted.stderr)
        self.assertIn(b"[GNUPG:] GOODMDC", decrypted.stderr)
        with tarfile.open(fileobj=io.BytesIO(decrypted.stdout), mode="r:gz") as archive:
            self.assertEqual(["evidence", "evidence/empty", "evidence/fixture.log"], archive.getnames())
            self.assertEqual(b"synthetic transcript\x00\xff\r\n", archive.extractfile("evidence/fixture.log").read())
            self.assertEqual(b"", archive.extractfile("evidence/empty").read())
            self.assertTrue(all(member.uid == member.gid == 0 for member in archive.getmembers()))
        self.assertFalse(list(self.work.glob("export-*")))
        self.assertFalse(any(self.work.rglob("S.gpg-agent*")))
        self.assertEqual(b"synthetic transcript\x00\xff\r\n", (self.evidence / "fixture.log").read_bytes())

    def test_lowercase_full_fingerprint_is_canonicalized(self):
        recipient = H.validate_recipient(self.key, self.good.lower(), self.work)
        self.assertEqual(self.good, recipient.fingerprint)

    def test_real_large_roundtrip_covers_nontrivial_encrypted_packet_lengths(self):
        payload = os.urandom(1024 * 1024 + 137)  # Synthetic only; no network acquisition.
        (self.evidence / "large.bin").write_bytes(payload)
        self.export()
        decrypted = self.command(["--status-fd", "2", "--decrypt", str(self.output / H.ARTIFACT)])
        self.assertIn(b"[GNUPG:] DECRYPTION_OKAY", decrypted.stderr)
        self.assertIn(b"[GNUPG:] GOODMDC", decrypted.stderr)
        with tarfile.open(fileobj=io.BytesIO(decrypted.stdout), mode="r:gz") as archive:
            self.assertEqual(payload, archive.extractfile("evidence/large.bin").read())

    def test_wrong_full_fingerprint_fails_without_import(self):
        with self.assertRaises(H.EvidenceError):
            H.validate_recipient(self.key, "F" * 40, self.work)
        self.assertFalse((self.work / "gnupg" / "private-keys-v1.d").exists())
        self.no_upload_or_plaintext()

    def test_short_nonhex_or_whitespace_fingerprints_fail_before_gpg(self):
        for fingerprint in (self.good[-16:], "Z" * 40, self.good + "\n", " " + self.good, "F" * 64, None):
            with self.subTest(fingerprint=repr(fingerprint)), patch.object(H, "_gpg") as command:
                with self.assertRaises(H.EvidenceError):
                    H.validate_recipient(self.key, fingerprint, self.work)
                command.assert_not_called()

    def test_secret_disguised_secret_multiple_and_trailing_armor_fail_before_gpg(self):
        disguised = self.secret.replace(b"PGP PRIVATE KEY BLOCK", b"PGP PUBLIC KEY BLOCK")
        for data in (self.secret, disguised, self.multiple, self.public + b"untrusted trailing content\n"):
            with self.subTest(kind=data[:32]), patch.object(H, "_gpg") as command:
                self.key.write_bytes(data)
                with self.assertRaises(H.EvidenceError):
                    self.recipient()
                command.assert_not_called()

    def test_real_expired_encryption_key_is_rejected(self):
        self.key.write_bytes(self.expired_public)
        with self.assertRaises(H.EvidenceError):
            H.validate_recipient(self.key, self.expired, self.work)
        self.no_upload_or_plaintext()

    def test_real_signing_only_key_is_rejected(self):
        self.key.write_bytes(self.sign_public)
        with self.assertRaises(H.EvidenceError):
            H.validate_recipient(self.key, self.sign_only, self.work)
        self.no_upload_or_plaintext()

    def test_invalid_encryption_subkey_binding_is_rejected(self):
        packets = bytearray(H._public_armor(self.public))
        packets[-1] ^= 1  # Corrupt the last subkey binding signature, not the primary fingerprint.
        encoded = base64.b64encode(packets)
        self.key.write_bytes(b"-----BEGIN PGP PUBLIC KEY BLOCK-----\n\n" +
                             b"\n".join(encoded[index:index + 64] for index in range(0, len(encoded), 64)) +
                             b"\n-----END PGP PUBLIC KEY BLOCK-----\n")
        with self.assertRaises(H.EvidenceError):
            self.recipient()
        self.no_upload_or_plaintext()

    def test_oversized_key_is_rejected_before_gpg(self):
        self.key.write_bytes(b"x" * (H.MAX_KEY_BYTES + 1))
        with patch.object(H, "_gpg") as command, self.assertRaises(H.EvidenceError):
            self.recipient()
        command.assert_not_called()

    def test_symlink_key_and_parent_are_rejected(self):
        linked = self.base / "linked.asc"
        linked.symlink_to(self.key)
        parent = self.base / "linked-parent"
        parent.symlink_to(self.base, target_is_directory=True)
        for path in (linked, parent / self.key.name):
            with self.subTest(path=path.name), self.assertRaises(H.EvidenceError):
                H.validate_recipient(path, self.good, self.work)

    def test_hardlinked_and_writable_keys_are_rejected(self):
        link = self.base / "hardlink.asc"
        os.link(self.key, link)
        with self.assertRaises(H.EvidenceError):
            self.recipient()
        link.unlink()
        self.key.chmod(0o666)
        with self.assertRaises(H.EvidenceError):
            self.recipient()

    def test_work_must_be_empty_owned_private_directory(self):
        self.work.chmod(0o755)
        with self.assertRaises(H.EvidenceError):
            self.recipient()
        self.work.chmod(0o700)
        (self.work / "sentinel").write_text("preserve")
        with self.assertRaises(H.EvidenceError):
            self.recipient()
        self.assertEqual("preserve", (self.work / "sentinel").read_text())

    def test_existing_output_is_never_overwritten(self):
        recipient = self.recipient()
        self.output.mkdir(mode=0o700)
        sentinel = self.output / "unrelated"
        sentinel.write_bytes(b"preserve")
        with self.assertRaises(H.EvidenceError):
            self.export(recipient)
        self.assertEqual(b"preserve", sentinel.read_bytes())

    def test_output_inside_evidence_or_work_is_rejected(self):
        recipient = self.recipient()
        for parent in (self.evidence, self.work):
            with self.subTest(parent=parent.name), self.assertRaises(H.EvidenceError):
                H.export_encrypted(self.evidence, parent / "upload", recipient, source_commit=SOURCE,
                                   source_tree=TREE, run_id="123", run_attempt="1")
            self.assertFalse((parent / "upload").exists())

    def test_symlink_hardlink_fifo_and_unsafe_names_are_rejected(self):
        recipient = self.recipient()
        path = self.evidence / "unsafe"
        makers = [lambda: path.symlink_to(self.key), lambda: os.link(self.key, path), lambda: os.mkfifo(path)]
        for make in makers:
            with self.subTest(kind=make):
                make()
                try:
                    with self.assertRaises(H.EvidenceError):
                        self.export(recipient)
                    self.no_upload_or_plaintext()
                finally:
                    path.unlink()
        (self.evidence / "back\\slash").write_bytes(b"synthetic")
        with self.assertRaises(H.EvidenceError):
            self.export(recipient)
        self.no_upload_or_plaintext()

    def test_small_byte_and_member_limits_fail_before_archive(self):
        recipient = self.recipient()
        for limits in ({"max_bytes": 2}, {"max_members": 2}):
            with self.subTest(limits=limits), patch.object(H, "_archive") as archive:
                with self.assertRaises(H.EvidenceError):
                    self.export(recipient, **limits)
                archive.assert_not_called()
                self.no_upload_or_plaintext()

    def test_limits_cannot_be_expanded_or_disabled(self):
        recipient = self.recipient()
        for limits in ({"max_bytes": 0}, {"max_bytes": H.MAX_BYTES + 1}, {"max_members": H.MAX_MEMBERS + 1},
                       {"timeout_seconds": H.MAX_TIMEOUT_SECONDS + 1}, {"timeout_seconds": True}):
            with self.subTest(limits=limits), self.assertRaises(H.EvidenceError):
                self.export(recipient, **limits)
        self.no_upload_or_plaintext()

    def test_manifest_rejects_missing_or_mismatched_actual_run_environment(self):
        recipient = self.recipient()
        for key, value in (("GITHUB_SHA", "3" * 40), ("GITHUB_ACTIONS", "false"),
                           ("GITHUB_REPOSITORY", "another/repository"), ("GITHUB_RUN_ID", "124"),
                           ("GITHUB_RUN_ATTEMPT", "2"), ("GITHUB_EVENT_NAME", "push")):
            with self.subTest(key=key), patch.dict(os.environ, {key: value}), self.assertRaises(H.EvidenceError):
                self.export(recipient)
        for changes in ({"source_commit": "1" * 8}, {"source_tree": "bad"}, {"run_id": "00123"},
                        {"run_attempt": "1\n"}, {"run_id": "1" * 21}):
            with self.subTest(changes=changes), self.assertRaises(H.EvidenceError):
                self.export(recipient, **changes)
        self.no_upload_or_plaintext()

    def test_recipient_change_or_expiry_after_admission_blocks_export(self):
        recipient = self.recipient()
        with self.assertRaises(H.EvidenceError):
            self.export(dataclasses.replace(recipient, expires_at=1))
        (self.work / "recipient.asc").write_bytes(b"changed")
        with self.assertRaises(H.EvidenceError):
            self.export(recipient)
        self.no_upload_or_plaintext()

    def test_evidence_mutation_during_capture_is_rejected_and_plaintext_retired(self):
        recipient = self.recipient()
        original = H._archive

        def changing(*args):
            original(*args)
            (self.evidence / "fixture.log").write_bytes(b"changed synthetic fixture")

        with patch.object(H, "_archive", side_effect=changing), self.assertRaises(H.EvidenceError):
            self.export(recipient)
        self.no_upload_or_plaintext()
        self.assertEqual(b"changed synthetic fixture", (self.evidence / "fixture.log").read_bytes())

    def test_missing_end_status_and_truncated_ciphertext_cannot_be_uploaded(self):
        recipient = self.recipient()
        original = H._gpg
        for defect in ("missing-end", "truncated"):
            def broken(*args, **kwargs):
                stdout, status = original(*args, **kwargs)
                if "--encrypt" in args[1]:
                    if defect == "missing-end":
                        status = status.replace(b"[GNUPG:] END_ENCRYPTION\n", b"")
                    else:
                        output = kwargs["output"]
                        output.write_bytes(output.read_bytes()[:-1])
                return stdout, status
            with self.subTest(defect=defect), patch.object(H, "_gpg", side_effect=broken):
                with self.assertRaises(H.EvidenceError):
                    self.export(recipient)
                self.no_upload_or_plaintext()

    def test_outer_ciphertext_rejects_trailing_packets_and_wrong_recipient(self):
        recipient = self.recipient()
        self.export(recipient)
        ciphertext = self.output / H.ARTIFACT
        with self.assertRaises(H.EvidenceError):
            H._ciphertext_shape(ciphertext, "F" * 40)
        ciphertext.write_bytes(ciphertext.read_bytes() + b"\x00")
        with self.assertRaises(H.EvidenceError):
            H._ciphertext_shape(ciphertext, recipient.encryption_fingerprint)

    def test_partial_publication_is_removed_on_manifest_failure(self):
        recipient = self.recipient()
        original = H._exclusive

        def failing(path):
            if path == self.output / H.MANIFEST:
                raise OSError("synthetic manifest-write failure")
            return original(path)

        with patch.object(H, "_exclusive", side_effect=failing), self.assertRaises(OSError):
            self.export(recipient)
        self.no_upload_or_plaintext()

    def helper(self, body):
        path = self.base / "fake-gpg"
        path.write_text("#!/bin/sh\n" + body)
        path.chmod(0o700)
        return path

    def test_gpg_error_retains_private_diagnostics_without_public_leak(self):
        recipient = dataclasses.replace(self.recipient(), executable=self.helper(
            "printf 'synthetic-private-error-marker' >&2\nexit 7\n"))
        with self.assertRaises(H.EvidenceError) as error:
            self.export(recipient)
        self.assertNotIn("synthetic-private-error-marker", str(error.exception))
        self.assertTrue(any(b"synthetic-private-error-marker" in path.read_bytes()
                            for path in self.work.glob("gpg-*/stderr")))
        records = [json.loads(path.read_text()) for path in self.work.glob("gpg-*/process.json")]
        self.assertTrue(any(record["waitExitCode"] == 7 and record["retired"] for record in records))
        self.no_upload_or_plaintext()

    def test_gpg_deadline_retires_only_its_direct_owned_child(self):
        recipient = dataclasses.replace(self.recipient(), executable=self.helper("exec /bin/sleep 20\n"))
        started = time.monotonic()
        with self.assertRaises(H.EvidenceError):
            self.export(recipient, timeout_seconds=1)
        self.assertLess(time.monotonic() - started, 8)
        records = [json.loads(path.read_text()) for path in self.work.glob("gpg-*/process.json")]
        self.assertTrue(any(record["interruption"] == "operation-interrupted" and record["retired"]
                            and record["waitExitCode"] is not None for record in records))
        self.no_upload_or_plaintext()

    def test_gpg_output_overflow_is_not_a_success(self):
        recipient = dataclasses.replace(self.recipient(), executable=self.helper("printf '%0256d' 0\n"))
        with patch.object(H, "MAX_DIAGNOSTIC_BYTES", 128), self.assertRaises(H.EvidenceError):
            self.export(recipient)
        self.no_upload_or_plaintext()

    def test_public_gpg_never_inherits_hooks_credentials_or_agent_access(self):
        original = H.subprocess.Popen
        observed = []

        def recording(*args, **kwargs):
            observed.append((args[0], dict(kwargs["env"])))
            return original(*args, **kwargs)

        with patch.dict(os.environ, {"SSH_AUTH_SOCK": "synthetic-agent-hook", "GPG_AGENT_INFO": "synthetic",
                                     "DYLD_INSERT_LIBRARIES": "synthetic", "GITHUB_TOKEN": "synthetic"}), \
                patch.object(H.subprocess, "Popen", side_effect=recording):
            self.recipient()
        self.assertTrue(observed)
        for command, environment in observed:
            self.assertIn("--no-autostart", command)
            self.assertIn("--disable-dirmngr", command)
            self.assertIn("--no-options", command)
            self.assertEqual({"PATH", "HOME", "GNUPGHOME", "LANG", "LC_ALL", "TMPDIR"}, set(environment))
        self.assertFalse(any(self.work.rglob("S.gpg-agent*")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
