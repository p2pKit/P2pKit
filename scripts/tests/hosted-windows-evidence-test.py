#!/usr/bin/env python3
"""Exporter OFFLINE/MODEL controls only: no native API, child, crypto or network.

Actual custody objects use the existing file suite's in-memory WinAPI model.
Synthetic packets/listings stand in for GPG output, never cryptographic proof.
Run -I -B -S. Native Windows/GPG/decryption and workflow acceptance are NOT_RUN.
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
import struct
import sys
import tarfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("windows_files_model", ROOT / "scripts/tests/hosted-windows-files-test.py")
model = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = model
spec.loader.exec_module(model)
import hosted_windows_evidence as W

F, H, P = W.files, W.portable, W.processes
PRIMARY, ENCRYPTION = "1" * 40, "2" * 40
SOURCE, TREE, JOB = "3" * 40, "4" * 40, "5" * 32
PUBLIC = (b"-----BEGIN PGP PUBLIC KEY BLOCK-----\n\n" + base64.b64encode(b"\xc6\x01x\xce\x01y") +
          b"\n-----END PGP PUBLIC KEY BLOCK-----\n")
GITHUB = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "p2pKit/P2pKit", "GITHUB_SHA": SOURCE,
          "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_EVENT_NAME": "workflow_dispatch",
          "SYSTEMROOT": "C:\\Windows"}


def listing(encryption=ENCRYPTION, expiry="0"):
    def key(kind, capability):
        row = [""] * 12
        row[0], row[1], row[6], row[11] = kind, "-", expiry, capability
        return ":".join(row)
    def fingerprint(value):
        return "fpr:::::::::" + value + ":"
    return ("\n".join((key("pub", "c"), fingerprint(PRIMARY), key("sub", "e"), fingerprint(encryption))) + "\n").encode()


def ciphertext(fingerprint=ENCRYPTION):
    recipient = b"\x03" + bytes.fromhex(fingerprint[-16:]) + b"\x12xy"
    protected = b"\x01" + b"SYNTHETIC-ONLY-NOT-CRYPTOGRAPHIC" * 2
    return b"\xc1" + bytes([len(recipient)]) + recipient + b"\xd2" + bytes([len(protected)]) + protected


class ScopeModel:
    """No CreateProcess, Windows API, threads, or real GPG exists in this model."""
    active = None

    def __init__(self, job, invocation, state, home):
        self.case = ScopeModel.active
        self.case.events.append(("scope-create", job, invocation, state, home))
        self.invocation = invocation
        self.code = self.case.gpg_exit
        if self.case.constructor_error is not None:
            raise self.case.constructor_error

    def spawn(self, argv, cwd, env, *, stdout, stderr):
        self.case.calls.append((argv, cwd, env))
        self.case.events.append(("spawn", stdout.native_handle, stderr.native_handle))
        self.case.borrowed = (stdout, stderr)
        if self.case.spawn_error is not None:
            raise self.case.spawn_error
        if "--version" in argv:
            output = self.case.version
        elif "--encrypt" in argv:
            output = self.case.cipher
        else:
            output = self.case.listing
        diagnostic = self.case.status if "--encrypt" in argv else b"private-model-diagnostic\x00\xff\r\n"
        # Deliberately bypass NativeFile.write(), just like the actual child's
        # borrowed output duplicate; live verify() must enforce the bound.
        if output:
            self.case.api.write(stdout.native_handle, output)
        if diagnostic:
            self.case.api.write(stderr.native_handle, diagnostic)
        if self.case.after_write is not None:
            self.case.after_write(argv, stdout, stderr)
        return SimpleNamespace(stdout=None, stderr=None, poll=self.poll)

    def poll(self):
        if self.case.poll_error is not None:
            raise self.case.poll_error
        if self.case.poll_hook is not None:
            return self.case.poll_hook()
        return self.code

    def drain(self, *, grace, kill_wait):
        self.case.events.append(("drain", grace, kill_wait))
        self.case.assertFalse(any(stream.closed for stream in self.case.borrowed), "Borrowed originals closed too early")
        if self.case.drain_error is not None:
            raise self.case.drain_error
        return self.case.remaining

    def discover(self):
        return self.case.live_members

    def description(self):
        return {"backend": "MODEL_ONLY", "launches": [{"jobAssignedBeforeResume": True}],
                "discoveryErrors": self.case.discovery_errors}

    def close(self):
        self.case.events.append(("scope-close",))
        if self.case.scope_close_error is not None:
            raise self.case.scope_close_error


class ExporterModelTests(unittest.TestCase):
    def setUp(self):
        self.api = model.ModelApi()
        self.work = F._root(r"C:\work\exporter", self.api, create=True)
        self.evidence = F._root(r"C:\work\evidence", self.api, create=True)
        self.output = F._root(r"C:\work\upload", self.api, create=True)
        self.roots = [self.work, self.evidence, self.output]
        self.gpg_exit = 0
        self.constructor_error = self.spawn_error = self.poll_error = self.drain_error = self.scope_close_error = None
        self.after_write = self.poll_hook = None
        self.remaining, self.discovery_errors, self.live_members = [], [], []
        self.cipher = ciphertext()
        self.version = b"gpg (GnuPG) 2.4.9\nmodel-only\n"
        self.listing = listing()
        self.status = b"private-model-diagnostic\n[GNUPG:] BEGIN_ENCRYPTION 2 9\n[GNUPG:] END_ENCRYPTION\n"
        self.calls, self.events, self.borrowed = [], [], ()
        ScopeModel.active = self
        self.patches = [patch.object(W, "_native"), patch.object(W, "_executable", return_value="a" * 64),
                        patch.object(W.shutil, "which", return_value=r"C:\GnuPG\bin\gpg.exe"),
                        patch.object(P, "WindowsScope", ScopeModel), patch.object(W, "_QUARANTINE", []),
                        patch.dict(os.environ, GITHUB, clear=True)]
        for item in self.patches:
            item.start()
        self.addCleanup(self.cleanup)
        self.put(self.evidence, "original.log", b"private-original\x00\xff\r\n")
        self.put(self.evidence, "empty", b"")

    def cleanup(self):
        # Only in-memory mocked handles exist. Explicitly release model quarantine
        # AFTER assertions; production has no quarantine-reset/retry API.
        self.api.close_failure = None
        self.api.flush_failure = False
        self.api.inspect_failure = None
        for session in W._QUARANTINE:
            for row in reversed(session.resources):
                owner = row["owner"]
                if isinstance(owner, F.NativeFile):
                    owner._deadline = time.monotonic() + 900
                    if owner._pins:
                        node = self.api.handles[owner._pins[-1].handle][0]
                        if len(node.content) > owner.max_bytes:
                            node.content = node.content[:owner.max_bytes]
                try:
                    owner.close()
                except BaseException:
                    pass  # Controlled model rejection; no native handle ever existed.
        for root in self.roots:
            root.close()
        self.assertEqual(self.api.handles, {}, "Offline model leaked an unaccounted handle")
        for item in reversed(self.patches):
            item.stop()

    def put(self, root, name, value):
        with root.create_file(name, max_bytes=len(value)) as stream:
            stream.write(value)

    def recipient(self):
        return W.validate_recipient(PUBLIC, PRIMARY.lower(), self.work, job_id=JOB)

    def export(self, recipient=None, **options):
        return W.export_encrypted(self.evidence, self.output, recipient or self.recipient(),
                                  source_commit=SOURCE, source_tree=TREE, run_id="123", run_attempt="1", **options)

    def node(self, root, name):
        return self.api.nodes[str(root.path) + "\\" + name.replace("/", "\\")]

    def records(self):
        return [json.loads(node.content) for name, node in self.api.nodes.items()
                if name.startswith(str(self.work.path) + "\\") and "-result-" in name and name.endswith(".json")]

    def test_model_export_seals_exact_two_files_and_preserves_original_normalized_archive(self):
        result = self.export()
        children = self.api.names(self.output._pins[-1].handle, 3, time.monotonic() + 10)
        self.assertEqual(set(children), {H.ARTIFACT, H.MANIFEST})
        self.assertEqual(self.node(self.output, H.ARTIFACT).content, self.cipher)
        self.assertEqual(json.loads(self.node(self.output, H.MANIFEST).content), result)
        self.assertEqual(result["artifact"], {"name": H.ARTIFACT, "size": len(self.cipher),
                                             "sha256": hashlib.sha256(self.cipher).hexdigest()})
        self.assertNotIn(b"private-model", self.node(self.output, H.MANIFEST).content)
        self.assertNotIn(b"original.log", self.node(self.output, H.MANIFEST).content)
        archives = [node.content for name, node in self.api.nodes.items() if name.endswith("\\evidence.tar.gz")]
        self.assertEqual(len(archives), 1)
        with tarfile.open(fileobj=io.BytesIO(archives[0]), mode="r:gz") as archive:
            self.assertEqual(archive.getnames(), ["evidence", "evidence/empty", "evidence/original.log"])
            self.assertEqual(archive.extractfile("evidence/original.log").read(), b"private-original\x00\xff\r\n")
            for entry in archive:
                self.assertEqual((entry.uid, entry.gid, entry.uname, entry.gname, entry.mtime), (0, 0, "", "", 0))
                self.assertEqual(entry.mode, 0o700 if entry.isdir() else 0o600)
        self.assertTrue(all(row["retirement"] == "KNOWN" for row in self.records()))
        self.assertEqual(self.node(self.evidence, "original.log").content, b"private-original\x00\xff\r\n")
        self.assertEqual(W._QUARANTINE, [])

    def test_model_gpg_commands_preserve_no_agent_network_and_exact_recipient_contract(self):
        self.export()
        self.assertEqual(len(self.calls), 5)  # version, show, selected, refresh, encrypt; all mocked.
        for command, cwd, environment in self.calls:
            for flag in ("--no-options", "--no-autostart", "--no-auto-key-retrieve", "--no-auto-key-import",
                         "--disable-dirmngr", "--no-random-seed-file", "--lock-never", "--no-auto-check-trustdb"):
                self.assertIn(flag, command)
            self.assertEqual(command[command.index("--keyring") + 1], str(self.work.path) + "\\recipient.gpg")
            self.assertEqual(cwd, str(self.work.path))
            self.assertNotIn("GITHUB_TOKEN", environment)
            self.assertNotIn("SSH_AUTH_SOCK", environment)
        command = self.calls[-1][0]
        self.assertEqual(command[command.index("--status-fd") + 1], "2")
        self.assertEqual(command[command.index("--recipient") + 1], ENCRYPTION + "!")
        self.assertEqual(command[command.index("--output") + 1], "-")
        self.assertIn("--no-encrypt-to", command)
        self.assertEqual(self.events.count(("drain", 0, 5)), 5)

    def test_parent_ownership_chain_is_preserved_without_credential_or_hook_inheritance(self):
        parent_job, parent_invocation = "a" * 32, "b" * 32
        inherited = P.ownership_environment({}, parent_job, parent_invocation, r"C:\parent\state", r"C:\parent\home")
        with patch.dict(os.environ, {**inherited, "GITHUB_TOKEN": "never-copy", "SSH_AUTH_SOCK": "never-copy",
                                     "GPG_AGENT_INFO": "never-copy", "PYTHONPATH": "never-copy"}):
            self.recipient()
        for _, _, environment in self.calls:
            chain = environment[P.CHAIN_ENV]
            self.assertTrue(chain.startswith(parent_invocation + ":"))
            domains = P.ownership_domains(chain, environment[P.DOMAINS_ENV])
            self.assertEqual(domains[0]["job"], parent_job)
            self.assertEqual(domains[1]["job"], JOB)
            self.assertEqual(domains[1]["state"], str(self.work.path))
            for name in ("GITHUB_TOKEN", "SSH_AUTH_SOCK", "GPG_AGENT_INFO", "PYTHONPATH"):
                self.assertNotIn(name, environment)

    def test_missing_installed_gpg_does_not_install_or_launch(self):
        with patch.object(W.shutil, "which", return_value=None), self.assertRaises(W.WindowsEvidenceError) as caught:
            self.recipient()
        self.assertIn("Installed native GPG", str(caught.exception.original))
        self.assertEqual(self.calls, [])

    def test_public_key_bounds_secret_and_wrong_fingerprint_fail_before_crypto(self):
        for public, fingerprint in ((b"", PRIMARY), (b"x" * (H.MAX_KEY_BYTES + 1), PRIMARY),
                                    (PUBLIC.replace(b"PUBLIC KEY", b"PRIVATE KEY"), PRIMARY),
                                    (PUBLIC, PRIMARY[-16:]), (PUBLIC, PRIMARY + "\n")):
            work = F._root(r"C:\work\key" + str(len(self.roots)), self.api, create=True)
            self.roots.append(work)
            with self.subTest(fingerprint=fingerprint), self.assertRaises(W.WindowsEvidenceError):
                W.validate_recipient(public, fingerprint, work, job_id=JOB)
        self.assertEqual(self.calls, [])

    def test_wrong_full_fingerprint_listing_rejected_by_shared_key_parser(self):
        self.listing = listing().replace(PRIMARY.encode(), b"F" * 40)
        with self.assertRaises(W.WindowsEvidenceError):
            self.recipient()
        self.assertEqual(len(self.calls), 2)

    def test_expired_key_listing_rejected_by_shared_key_parser(self):
        self.listing = listing(expiry="1")
        with self.assertRaises(W.WindowsEvidenceError):
            self.recipient()
        self.assertEqual(len(self.calls), 2)

    def test_validation_work_must_be_empty_and_keeps_existing_bytes(self):
        self.put(self.work, "unrelated", b"preserve")
        with self.assertRaises(W.WindowsEvidenceError):
            self.recipient()
        self.assertEqual(self.node(self.work, "unrelated").content, b"preserve")
        self.assertEqual(self.calls, [])

    def test_only_native_directory_objects_not_paths_are_accepted(self):
        with self.assertRaises(H.EvidenceError):
            W.validate_recipient(PUBLIC, PRIMARY, Path("/not-a-native-private-directory"), job_id=JOB)
        self.assertEqual(self.calls, [])

    def test_manual_identity_is_checked_without_synthesizing_ordinary_event(self):
        recipient = self.recipient()
        self.calls.clear()
        with patch.dict(os.environ, {"GITHUB_EVENT_NAME": "push"}), self.assertRaises(W.WindowsEvidenceError):
            self.export(recipient)
        self.assertEqual(self.calls, [])

    def admission(self, recipient):
        value = {"source": {"commit": SOURCE, "tree": TREE}, "github": {"event": "push", "runId": "123"},
                 "policy": {"sha256": "f" * 64}, "profile": "desktop", "suites": ["cli"]}
        return W.ordinary.hosted_test_identity.Admission(json.dumps(value).encode(), b"modeled-event", b"modeled-policy",
                                                        PUBLIC, recipient.fingerprint, recipient.key_sha256,
                                                        int(time.time()) + 300)

    def test_ordinary_entry_uses_exact_shared_admission_and_schema_without_manual_fallback(self):
        recipient = self.recipient()
        admission = self.admission(recipient)
        query = object()
        with patch.object(W.ordinary.hosted_test_identity, "admit", return_value=admission) as admit, \
                patch.object(H, "_manifest_identity", side_effect=AssertionError("Manual fallback forbidden")):
            result = W.export_test_encrypted(self.evidence, self.output, recipient, profile="desktop", root=ROOT,
                                             admission=admission, query_runner=query)
        self.assertEqual(admit.call_count, 2)
        for call in admit.call_args_list:
            self.assertEqual(call.args, ("desktop", ROOT))
            self.assertEqual(call.kwargs, {"query_runner": query, "expected": admission})
        self.assertEqual(set(result), {"schema", "scope", "source", "github", "policy", "custody", "artifact"})
        self.assertEqual(result["schema"], 2)
        self.assertEqual(result["custody"], {"profile": "desktop", "suites": ["cli"]})

    def test_ordinary_key_mismatch_fails_before_any_encryption(self):
        recipient = self.recipient()
        self.calls.clear()
        admission = dataclasses.replace(self.admission(recipient), key_sha256="f" * 64)
        with patch.object(W.ordinary.hosted_test_identity, "admit", return_value=admission), \
                self.assertRaises(W.WindowsEvidenceError):
            W.export_test_encrypted(self.evidence, self.output, recipient, profile="desktop", root=ROOT,
                                    admission=admission, query_runner=object())
        self.assertEqual(self.calls, [])

    def test_ordinary_policy_cannot_outlive_validated_recipient(self):
        recipient = dataclasses.replace(self.recipient(), expires_at=int(time.time()) + 1)
        admission = self.admission(recipient)
        self.calls.clear()
        with patch.object(W.ordinary.hosted_test_identity, "admit", return_value=admission), \
                self.assertRaises(W.WindowsEvidenceError):
            W.export_test_encrypted(self.evidence, self.output, recipient, profile="desktop", root=ROOT,
                                    admission=admission, query_runner=object())
        self.assertEqual(self.calls, [])

    def test_changed_ordinary_admission_during_crypto_prevents_output(self):
        recipient = self.recipient()
        admission = self.admission(recipient)
        changed = dataclasses.replace(admission, record=admission.record.replace(SOURCE.encode(), b"9" * 40))
        with patch.object(W.ordinary.hosted_test_identity, "admit", side_effect=(admission, changed)), \
                self.assertRaises(W.WindowsEvidenceError) as caught:
            W.export_test_encrypted(self.evidence, self.output, recipient, profile="desktop", root=ROOT,
                                    admission=admission, query_runner=object())
        self.assertIn("changed during export", str(caught.exception.original))
        self.assertEqual(self.api.names(self.output._pins[-1].handle, 3, time.monotonic() + 10), [])

    def test_existing_output_is_never_overwritten_or_deleted(self):
        recipient = self.recipient()
        self.put(self.output, "unrelated", b"preserve")
        self.calls.clear()
        with self.assertRaises(W.WindowsEvidenceError):
            self.export(recipient)
        self.assertEqual(self.node(self.output, "unrelated").content, b"preserve")
        self.assertEqual(self.calls, [])

    def test_overlapping_root_is_rejected_before_encryption(self):
        recipient = self.recipient()
        child = self.work.create_directory("upload")
        self.roots.append(child)
        self.calls.clear()
        with self.assertRaises(W.WindowsEvidenceError):
            W.export_encrypted(self.evidence, child, recipient, source_commit=SOURCE, source_tree=TREE,
                                run_id="123", run_attempt="1")
        self.assertEqual(self.calls, [])

    def test_expanded_or_disabled_bounds_are_rejected(self):
        recipient = self.recipient()
        for options in ({"max_bytes": H.MAX_BYTES + 1}, {"max_bytes": 0}, {"max_members": True},
                        {"max_members": H.MAX_MEMBERS + 1}, {"timeout_seconds": 901}, {"timeout_seconds": float("nan")}):
            with self.subTest(options=options), self.assertRaises(W.WindowsEvidenceError):
                self.export(recipient, **options)

    def test_evidence_byte_and_member_bound_failure_does_not_create_public_output(self):
        recipient = self.recipient()
        for options in ({"max_bytes": 1}, {"max_members": 2}):
            with self.subTest(options=options), self.assertRaises(W.WindowsEvidenceError):
                self.export(recipient, **options)
        self.assertEqual(self.api.names(self.output._pins[-1].handle, 3, time.monotonic() + 10), [])

    def test_native_supplier_rejects_unsafe_input_in_actual_export_path(self):
        recipient = self.recipient()
        self.node(self.evidence, "original.log").links = 2
        with self.assertRaises(W.WindowsEvidenceError):
            self.export(recipient)
        self.assertFalse(any("--encrypt" in call[0] for call in self.calls))
        self.node(self.evidence, "original.log").links = 1

    def test_input_mutation_after_archive_cannot_become_encrypted_success(self):
        recipient = self.recipient()
        archive = W._archive
        def changed(*args):
            archive(*args)
            self.node(self.evidence, "original.log").content = b"changed"
            self.node(self.evidence, "original.log").version += 1
        with patch.object(W, "_archive", side_effect=changed), self.assertRaises(W.WindowsEvidenceError):
            self.export(recipient)
        self.assertEqual(self.node(self.evidence, "original.log").content, b"changed")

    def test_missing_end_or_explicit_error_status_never_produces_output(self):
        recipient = self.recipient()
        for status in (b"[GNUPG:] BEGIN_ENCRYPTION 2 9\n", self.status + b"[GNUPG:] ERROR failure\n"):
            self.status = status
            with self.subTest(status=status), self.assertRaises(W.WindowsEvidenceError):
                self.export(recipient)
        self.assertEqual(self.api.names(self.output._pins[-1].handle, 3, time.monotonic() + 10), [])

    def test_truncated_extra_packet_and_wrong_recipient_are_shared_parser_failures(self):
        recipient = self.recipient()
        for value in (ciphertext()[:-1], ciphertext() + b"\0", ciphertext("F" * 40)):
            self.cipher = value
            with self.subTest(ciphertext=value), self.assertRaises(W.WindowsEvidenceError):
                self.export(recipient)
        self.assertEqual(self.api.names(self.output._pins[-1].handle, 3, time.monotonic() + 10), [])

    def test_published_copy_is_reopened_and_hash_checked_before_return(self):
        recipient = self.recipient()
        seal = W._seal
        def corrupt(*args):
            node = self.node(self.output, H.ARTIFACT)
            node.content = b"corrupted"
            node.version += 1
            return seal(*args)
        with patch.object(W, "_seal", side_effect=corrupt), self.assertRaises(W.WindowsEvidenceError):
            self.export(recipient)

    def test_manifest_failure_retains_partial_ciphertext_privately_but_never_returns_success(self):
        recipient = self.recipient()
        create = self.output.create_file
        original = OSError("private-modeled-manifest-write-error")
        def fail(name, **kwargs):
            if name == H.MANIFEST:
                raise original
            return create(name, **kwargs)
        with patch.object(self.output, "create_file", side_effect=fail), self.assertRaises(W.WindowsEvidenceError) as caught:
            self.export(recipient)
        self.assertIs(caught.exception.original, original)
        self.assertNotIn("private-modeled", str(caught.exception))
        self.assertEqual(self.node(self.output, H.ARTIFACT).content, self.cipher)
        self.assertNotIn(str(self.output.path) + "\\" + H.MANIFEST, self.api.nodes)

    def test_gpg_failure_keeps_original_private_stderr_and_native_exit_record(self):
        recipient = self.recipient()
        self.gpg_exit = 7
        with self.assertRaises(W.WindowsEvidenceError) as caught:
            self.export(recipient)
        self.assertNotIn("private-model-diagnostic", str(caught.exception))
        private = json.loads(caught.exception.private_record)
        self.assertEqual(private["commands"][-1]["waitExitCode"], 7)
        self.assertEqual(private["commands"][-1]["retirement"], "KNOWN")
        self.assertFalse(caught.exception.retirement_unknown)
        self.assertTrue(any(node.content == b"private-model-diagnostic\x00\xff\r\n"
                            for name, node in self.api.nodes.items() if name.endswith("\\stderr")))

    def test_live_direct_child_write_bound_is_checked_even_when_child_already_exited(self):
        recipient = self.recipient()
        self.listing = b"X" * 200
        with patch.object(H, "MAX_DIAGNOSTIC_BYTES", 64), self.assertRaises(W.WindowsEvidenceError) as caught:
            self.export(recipient)
        self.assertIn("exceeded", str(caught.exception.original))
        self.assertTrue(any(row[0] == "drain" for row in self.events))

    def test_ciphertext_direct_child_output_bound_is_not_only_native_write_method(self):
        recipient = self.recipient()
        with patch.object(H, "MAX_CIPHERTEXT_BYTES", 32), self.assertRaises(W.WindowsEvidenceError):
            self.export(recipient)
        self.assertEqual(self.api.names(self.output._pins[-1].handle, 3, time.monotonic() + 10), [])

    def test_cancellation_preserves_exact_original_object_and_attempts_scope_drain_close(self):
        recipient = self.recipient()
        cancellation = KeyboardInterrupt("private-model-cancellation")
        self.poll_error = cancellation
        self.events.clear()
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.export(recipient)
        self.assertIs(caught.exception, cancellation)
        self.assertIn(("drain", 0, 5), self.events)
        self.assertIn(("scope-close",), self.events)
        self.assertEqual(json.loads(cancellation._p2pkit_windows_evidence)["result"], "FAILED")

    def test_original_failure_plus_unknown_scope_close_is_sticky_in_real_result_path(self):
        recipient = self.recipient()
        original = RuntimeError("private-primary-operation-error")
        self.spawn_error = original
        self.scope_close_error = RuntimeError("private-secondary-close-error")
        with self.assertRaises(W.WindowsEvidenceError) as caught:
            self.export(recipient)
        self.assertIs(caught.exception.original, original)
        self.assertTrue(caught.exception.retirement_unknown)
        raw = caught.exception.private_record
        self.assertIn(b"private-primary-operation-error", raw)
        self.assertIn(b"private-secondary-close-error", raw)
        self.assertIn(b'"quarantined":true', raw)
        self.assertTrue(all(not sink.closed for sink in self.borrowed))
        self.assertTrue(W._QUARANTINE)

    def test_actual_supplier_note_cleanup_propagates_through_constructor_failure_receipt(self):
        recipient = self.recipient()
        original = F.FilesystemError("private-original-constructor-error")
        api = SimpleNamespace(close=lambda handle: (_ for _ in ()).throw(OSError("private-unknown-native-close")))
        F._cleanup((lambda: F._close_native(api, 77),), original)
        self.assertNotIn("UNKNOWN", str(original))
        self.constructor_error = original
        with self.assertRaises(W.WindowsEvidenceError) as caught:
            self.export(recipient)
        self.assertIs(caught.exception.original, original)
        self.assertTrue(caught.exception.retirement_unknown)
        self.assertIn(b"Native handle retirement UNKNOWN", caught.exception.private_record)
        self.assertTrue(any(not row["closed"] and row["quarantined"] for row in W._QUARANTINE[-1].resources))

    def test_process_retirement_carrier_is_not_hidden_when_exception_message_is_plain(self):
        recipient = self.recipient()
        original = RuntimeError("private-primary")
        P._finish_retirement([({"phase": "launch", "resource": "stdout-duplicate", "status": "UNKNOWN",
                               "error": "private-close"}, OSError("private-close"))], original)
        self.spawn_error = original
        with self.assertRaises(W.WindowsEvidenceError) as caught:
            self.export(recipient)
        self.assertTrue(caught.exception.retirement_unknown)
        self.assertIn(b"stdout-duplicate", caught.exception.private_record)

    def encryption_retirement_probe(self, failure, *, unknown):
        """Reach real exporter --encrypt setup; faults are model-only, never GPG."""
        recipient = self.recipient()
        original = RuntimeError("private-encryption-" + failure)
        if failure in {"constructor-carrier", "spawn-carrier"}:
            P._finish_retirement([({"phase": "launch", "resource": "encryption-input-borrower",
                                   "status": "UNKNOWN", "error": "private-unretired-domain"},
                                  OSError("private-unretired-domain"))], original)
            self.assertNotIn("UNKNOWN", str(original))
        captured = {}
        command = W._gpg

        def encrypt_only(session, bound_recipient, arguments, end, **options):
            if "--encrypt" not in arguments:
                return command(session, bound_recipient, arguments, end, **options)
            self.assertFalse(captured, "Exactly one encryption attempt is required")
            self.assertEqual(len(self.calls), 4, "Validation and key refresh must succeed first")
            self.assertEqual(len(session.commands), 1)
            self.assertIn("--list-keys", session.commands[0]["argv"])
            self.assertEqual(session.commands[0]["retirement"], "KNOWN")
            self.assertTrue(options["encryption"])
            for label in ("plaintext-input-pin", "export-work", "original-evidence-snapshot"):
                rows = [row for row in session.resources if row["label"] == label]
                self.assertEqual(len(rows), 1)
                captured[label] = rows[0]
            plaintext = captured["plaintext-input-pin"]["owner"]
            self.assertEqual(arguments[-1], str(plaintext.path))
            captured["pins"] = [(pin, pin.handle) for pin in plaintext._pins]
            captured["private-handle"] = captured["export-work"]["owner"]._pins[-1].handle
            self.assertFalse(plaintext.closed)
            if failure == "drain":
                self.drain_error = original
            elif failure == "close":
                self.scope_close_error = original
            elif failure == "constructor-carrier":
                self.constructor_error = original
            elif failure == "spawn-carrier":
                self.spawn_error = original
            elif failure == "known-exit":
                self.gpg_exit = 7
            else:
                self.fail("Unknown model fault")
            return command(session, bound_recipient, arguments, end, **options)

        with patch.object(W, "_gpg", side_effect=encrypt_only), self.assertRaises(W.WindowsEvidenceError) as caught:
            self.export(recipient)
        self.assertTrue(captured, "The regression must reach plaintext encryption, not early key refresh")
        self.assertEqual(caught.exception.retirement_unknown, unknown)
        if failure != "known-exit":
            self.assertIs(caught.exception.original, original)
        record = json.loads(caught.exception.private_record)
        self.assertEqual(record["result"], "FAILED")
        self.assertIn("--encrypt", record["commands"][-1]["argv"])
        self.assertEqual(record["commands"][-1]["retirement"], "UNKNOWN" if unknown else "KNOWN")
        self.assertEqual(len(self.calls), 4 if failure == "constructor-carrier" else 5)
        self.assertEqual(self.api.names(self.output._pins[-1].handle, 3, time.monotonic() + 10), [])
        plaintext = captured["plaintext-input-pin"]["owner"]
        if unknown:
            # Inspect the ACTUAL captured NativeFile after _export's finally ran.
            # A Python object reference alone is not an immutable native input pin.
            self.assertFalse(plaintext.closed, "UNKNOWN encryption must retain its borrowed plaintext pin")
            self.assertFalse(plaintext._retired)
            self.assertEqual(plaintext.verify(), plaintext.initial_info)
            for pin, handle in captured["pins"]:
                self.assertEqual(pin.handle, handle)
                self.assertGreater(pin.references, 0, "Input and every ancestor must remain natively pinned")
                self.assertIn(handle, self.api.handles)
            for label in ("plaintext-input-pin", "export-work"):
                self.assertFalse(captured[label]["closed"])
                self.assertTrue(captured[label]["quarantined"])
            self.assertFalse(captured["export-work"]["owner"]._closed)
            self.assertTrue(W._QUARANTINE)
            self.assertTrue(captured["original-evidence-snapshot"]["closed"],
                            "Safe independent resources still retire; do not quarantine the entire export")
        else:
            self.assertTrue(plaintext.closed)
            self.assertTrue(plaintext._retired)
            self.assertEqual(plaintext._pins, [])
            self.assertNotIn(captured["pins"][-1][1], self.api.handles)
            self.assertNotIn(captured["private-handle"], self.api.handles)
            self.assertTrue(captured["export-work"]["owner"]._closed)
            self.assertTrue(all(row["closed"] and not row["quarantined"] for row in record["resources"]))
            self.assertEqual(W._QUARANTINE, [])
        for root in self.roots:
            root.verify()  # Caller-owned roots are never retired by exporter finalization.

    def test_encrypt_drain_unknown_retains_input_and_ancestors_after_export_raises(self):
        self.encryption_retirement_probe("drain", unknown=True)

    def test_encrypt_close_unknown_retains_input_and_ancestors_after_export_raises(self):
        self.encryption_retirement_probe("close", unknown=True)

    def test_encrypt_constructor_carrier_retains_input_and_ancestors_after_export_raises(self):
        self.encryption_retirement_probe("constructor-carrier", unknown=True)

    def test_encrypt_spawn_carrier_retains_input_and_ancestors_after_export_raises(self):
        self.encryption_retirement_probe("spawn-carrier", unknown=True)

    def test_encrypt_known_retirement_failure_closes_input_and_safe_resources(self):
        self.encryption_retirement_probe("known-exit", unknown=False)

    def test_remaining_descendant_or_discovery_failure_blocks_all_upload_authority(self):
        recipient = self.recipient()
        self.remaining = [{"pid": 999, "creationFileTime": 123}]
        with self.assertRaises(W.WindowsEvidenceError) as caught:
            self.export(recipient)
        self.assertTrue(caught.exception.retirement_unknown)
        self.assertIn(("scope-close",), self.events)
        self.assertTrue(all(not sink.closed for sink in self.borrowed))

    def test_unexpected_descendant_retired_by_force_is_still_not_successful_gpg(self):
        recipient = self.recipient()
        self.live_members = [{"pid": 123, "creationFileTime": 456}]
        with self.assertRaises(W.WindowsEvidenceError) as caught:
            self.export(recipient)
        self.assertIn("live descendant", str(caught.exception.original))
        self.assertFalse(caught.exception.retirement_unknown, "Known forced cleanup is failure, not UNKNOWN")
        self.assertIn(("drain", 0, 5), self.events)

    def test_failed_discovery_record_remains_unknown_even_if_drain_returned_empty(self):
        recipient = self.recipient()
        self.discovery_errors = ["private-unobservable-native-member"]
        with self.assertRaises(W.WindowsEvidenceError) as caught:
            self.export(recipient)
        self.assertTrue(caught.exception.retirement_unknown)
        self.assertTrue(all(not sink.closed for sink in self.borrowed))

    def test_early_root_supplier_failure_and_unknown_are_retained_before_child_creation(self):
        recipient = self.recipient()
        self.calls.clear()
        original = F.FilesystemError("private-original-root-error")
        F._note(original, "Native handle retirement UNKNOWN: 177")
        with patch.object(self.evidence, "verify", side_effect=original), self.assertRaises(W.WindowsEvidenceError) as caught:
            self.export(recipient)
        self.assertIs(caught.exception.original, original)
        self.assertTrue(caught.exception.retirement_unknown)
        self.assertIn(b"private-original-root-error", caught.exception.private_record)
        self.assertEqual(self.calls, [])

    def test_validation_root_failure_preserves_notes_and_original_even_if_receipt_cannot_be_written(self):
        original = F.FilesystemError("private-work-root-error")
        F._note(original, "Native handle retirement UNKNOWN: 144")
        with patch.object(self.work, "verify", side_effect=original), self.assertRaises(W.WindowsEvidenceError) as caught:
            self.recipient()
        self.assertIs(caught.exception.original, original)
        self.assertTrue(caught.exception.retirement_unknown)
        self.assertIn(b"private-work-root-error", caught.exception.private_record)
        self.assertEqual(self.calls, [])

    def test_key_refresh_readers_are_closed_before_later_long_archive_phase(self):
        recipient = self.recipient()
        archive = W._archive
        def inspect(*args):
            active = [row for row in args[0].resources if not row["closed"]]
            self.assertFalse(any(row["label"] in {"recipient-armor-pin", "recipient-ring-pin", "gpg-stdout",
                                                  "gpg-stderr-status", "gpg-home", "gpg-temp"} for row in active))
            return archive(*args)
        with patch.object(W, "_archive", side_effect=inspect):
            self.export(recipient)

    def test_deadline_is_enforced_during_live_poll_and_owned_domain_is_retired(self):
        recipient = self.recipient()
        clock = [100.0]
        def advance():
            clock[0] = 200.0
            return None
        self.poll_hook = advance
        with patch.object(time, "monotonic", side_effect=lambda: clock[0]), patch.object(time, "sleep"), \
                self.assertRaises(W.WindowsEvidenceError) as caught:
            self.export(recipient, timeout_seconds=1)
        self.assertIn("deadline", str(caught.exception.original))
        self.assertIn(("drain", 0, 5), self.events)
        self.assertIn(("scope-close",), self.events)

    def test_ambiguous_sink_close_keeps_other_cleanup_attempts_and_never_retries_raw_handle(self):
        recipient = self.recipient()
        target = []
        def fail_close(argv, out, err):
            target.append(out.native_handle)
            self.api.close_failure = out.native_handle
        self.after_write = fail_close
        with self.assertRaises(W.WindowsEvidenceError) as caught:
            self.export(recipient)
        self.assertTrue(caught.exception.retirement_unknown)
        self.assertEqual(sum(event[:2] == ("close", target[0]) for event in self.api.events), 1)
        self.assertTrue(all(sink.closed for sink in self.borrowed))

    def test_recipient_work_key_change_is_rejected_before_child_creation(self):
        recipient = self.recipient()
        self.calls.clear()
        self.node(self.work, "recipient.asc").content = b"changed public-key bytes"
        with self.assertRaises(W.WindowsEvidenceError):
            self.export(recipient)
        self.assertEqual(self.calls, [])

    def test_expired_recipient_after_validation_prevents_encryption(self):
        recipient = dataclasses.replace(self.recipient(), expires_at=1)
        self.calls.clear()
        with self.assertRaises(W.WindowsEvidenceError):
            self.export(recipient)
        self.assertEqual(self.calls, [])

    def test_changed_installed_binary_prevents_child_creation(self):
        recipient = self.recipient()
        self.calls.clear()
        with patch.object(W, "_executable", return_value="b" * 64), self.assertRaises(W.WindowsEvidenceError):
            self.export(recipient)
        self.assertEqual(self.calls, [])

    def test_private_receipt_failure_preserves_original_and_reports_unretained_secondary(self):
        recipient = self.recipient()
        original = RuntimeError("private-original-failed-command")
        self.spawn_error = original
        create = self.work.create_file
        def fail(name, **kwargs):
            if "encrypted-export-result-" in name:
                raise OSError("private-receipt-write-error")
            return create(name, **kwargs)
        with patch.object(self.work, "create_file", side_effect=fail), self.assertRaises(W.WindowsEvidenceError) as caught:
            self.export(recipient)
        self.assertIs(caught.exception.original, original)
        self.assertIn(b"private-receipt-write-error", caught.exception.private_record)
        self.assertIn(b"private-original-failed-command", caught.exception.private_record)

    def test_private_receipt_close_failure_after_success_blocks_successful_return(self):
        recipient = self.recipient()
        create = self.work.create_file
        target = []
        def fail_close(name, **kwargs):
            stream = create(name, **kwargs)
            if name.startswith("encrypted-export-result-"):
                target.append(stream.native_handle)
                self.api.close_failure = stream.native_handle
            return stream
        with patch.object(self.work, "create_file", side_effect=fail_close), self.assertRaises(W.WindowsEvidenceError) as caught:
            self.export(recipient)
        self.assertTrue(caught.exception.retirement_unknown)
        self.assertIn(b"private-result-close", caught.exception.private_record)
        self.assertEqual(sum(event[:2] == ("close", target[0]) for event in self.api.events), 1)

    def test_native_reader_never_materializes_large_archive_or_ciphertext(self):
        payload = bytes(range(256)) * 8193
        self.put(self.evidence, "large.bin", payload)
        self.export()
        self.assertLessEqual(max(self.api.read_sizes), F.CHUNK)
        self.assertLessEqual(max(self.api.write_sizes), max(F.CHUNK, len(self.cipher), len(self.listing), len(self.status)))


class ExceptionModelTests(unittest.TestCase):
    def test_cycle_is_finite_and_unknown_note_is_sticky(self):
        first, second = RuntimeError("first"), RuntimeError("second")
        first.__cause__, second.__context__ = second, first
        F._note(second, "Native handle retirement UNKNOWN: 9")
        result = W._exception_detail(first)
        self.assertTrue(result["retirementUnknown"])
        self.assertFalse(result["incomplete"])
        self.assertLessEqual(len(result["nodes"]), 4)

    def test_graph_overflow_is_unknown_not_known_cleanup(self):
        first = current = RuntimeError("first")
        for i in range(100):
            child = RuntimeError(str(i))
            current.__cause__ = child
            current = child
        result = W._exception_detail(first)
        self.assertTrue(result["incomplete"])
        self.assertTrue(result["retirementUnknown"])
        self.assertLessEqual(len(result["nodes"]), 64)

    def test_raising_message_and_accessor_are_unknown_without_replacing_original(self):
        class Broken(RuntimeError):
            def __str__(self):
                raise KeyboardInterrupt()
            @property
            def __notes__(self):
                raise RuntimeError("unreadable")
            @property
            def _p2pkit_retirement(self):
                raise RuntimeError("unreadable")
        result = W._exception_detail(Broken("primary"))
        self.assertTrue(result["retirementUnknown"])
        self.assertTrue(result["incomplete"])
        self.assertEqual(result["nodes"][0]["type"], "Broken")

    def test_nested_group_and_malformed_carrier_fail_closed(self):
        child = RuntimeError("secondary")
        F._note(child, "Native handle retirement UNKNOWN: 17")
        original = RuntimeError("original")
        original.exceptions = (RuntimeError("sibling"), child)
        result = W._exception_detail(original)
        self.assertTrue(result["retirementUnknown"])
        original._p2pkit_retirement = {"status": "KNOWN"}
        self.assertTrue(W._exception_detail(original)["incomplete"])

    def test_oversized_diagnostic_is_explicitly_incomplete_and_finitely_encoded(self):
        error = RuntimeError("private" * 100_000)
        error.__notes__ = ["note" * 20_000] * 100
        result = W._exception_detail(error)
        self.assertTrue(result["incomplete"])
        self.assertTrue(result["retirementUnknown"])
        self.assertLess(len(json.dumps(result)), 100_000)

    def test_nonwindows_guard_cannot_start_native_work(self):
        with patch.object(P, "host_role", side_effect=AssertionError("Must not call native API")), \
                patch.object(W, "_QUARANTINE", []), patch.object(W.os, "name", "posix"), \
                self.assertRaises(H.EvidenceError):
            W._native()

    def test_unknown_quarantine_blocks_next_attempt_before_host_or_files(self):
        with patch.object(P, "host_role", side_effect=AssertionError("Must not call native API")), \
                patch.object(W, "_QUARANTINE", [object()]), self.assertRaisesRegex(H.EvidenceError, "Prior"):
            W._native()

    def test_pathless_parser_accepts_model_mdc_and_rejects_unprotected_tag9(self):
        value = ciphertext()
        H._ciphertext_stream(io.BytesIO(value), len(value), ENCRYPTION)
        corrupted = value.replace(b"\xd2", b"\xc9", 1)
        with self.assertRaises(H.EvidenceError):
            H._ciphertext_stream(io.BytesIO(corrupted), len(corrupted), ENCRYPTION)

    def test_many_shared_cycle_edges_cannot_exceed_node_bound(self):
        original = RuntimeError("original")
        original.exceptions = [original] * 64
        result = W._exception_detail(original)
        self.assertTrue(result["incomplete"])
        self.assertTrue(result["retirementUnknown"])
        self.assertLessEqual(len(result["nodes"]), 64)

    def test_oversized_or_nonstring_keyed_carrier_is_not_traversed_as_arbitrary_mapping(self):
        for carrier in ({str(i): i for i in range(1000)}, {1: "x", "resources": [], "omitted": 0}):
            original = RuntimeError("original")
            original._p2pkit_retirement = carrier
            result = W._exception_detail(original)
            self.assertTrue(result["incomplete"])
            self.assertTrue(result["retirementUnknown"])

    def test_exception_type_accessor_cannot_replace_primary_diagnostic(self):
        class BrokenMeta(type):
            def __getattribute__(self, name):
                if name == "__name__":
                    raise RuntimeError("private-type-accessor-error")
                return super().__getattribute__(name)
        class Broken(RuntimeError, metaclass=BrokenMeta):
            pass
        result = W._exception_detail(Broken("private-original"))
        self.assertTrue(result["incomplete"])
        self.assertEqual(result["nodes"][0]["message"], "private-original")


class ExecutableParserModelTests(unittest.TestCase):
    """Public PE header/stamp parser only; no fixture executable is ever written/run."""
    def setUp(self):
        self.raw = bytearray(128)
        self.raw[:2] = b"MZ"
        struct.pack_into("<I", self.raw, 60, 64)
        self.raw[64:68] = b"PE\0\0"
        struct.pack_into("<H", self.raw, 68, 0x8664)
        struct.pack_into("<H", self.raw, 88, 0x20B)
        self.info = SimpleNamespace(st_dev=1, st_ino=2, st_size=len(self.raw), st_mtime_ns=99,
                                    st_mode=0o100444, st_nlink=1, st_file_attributes=0)

    def check(self):
        case = self
        class Reader(io.BytesIO):
            def fileno(self):
                return 42  # Mocked public binary descriptor, NOT any NativeFile.
        class PublicPath:
            suffix = ".exe"
            parents = ()
            def __str__(self):
                return r"C:\GnuPG\bin\gpg.exe"
            def lstat(self):
                return case.info
            def open(self, mode):
                case.assertEqual(mode, "rb")
                return Reader(bytes(case.raw))
        with patch.object(W, "Path", return_value=PublicPath()), patch.object(W.os, "fstat", return_value=self.info):
            return W._executable(r"C:\GnuPG\bin\gpg.exe", time.monotonic() + 10)

    def test_native_amd64_pe_header_and_whole_byte_hash_are_read_from_same_public_stream(self):
        self.assertEqual(self.check(), hashlib.sha256(self.raw).hexdigest())

    def test_x86_arm64_and_bad_pe32_magic_are_rejected_without_running_any_binary(self):
        for machine, magic in ((0x14C, 0x10B), (0xAA64, 0x20B), (0x8664, 0x10B)):
            struct.pack_into("<H", self.raw, 68, machine)
            struct.pack_into("<H", self.raw, 88, magic)
            with self.subTest(machine=machine, magic=magic), self.assertRaises(H.EvidenceError):
                self.check()

    def test_header_offset_out_of_bounds_and_non_pe_inputs_are_rejected(self):
        for magic, offset in ((b"NO", 64), (b"MZ", 0), (b"MZ", 128)):
            self.raw[:2] = magic
            struct.pack_into("<I", self.raw, 60, offset)
            with self.subTest(magic=magic, offset=offset), self.assertRaises(H.EvidenceError):
                self.check()

    def test_public_executable_reparse_or_hardlink_is_not_admitted(self):
        for links, attributes in ((2, 0), (1, 0x400)):
            self.info.st_nlink, self.info.st_file_attributes = links, attributes
            with self.subTest(links=links, attributes=attributes), self.assertRaises(H.EvidenceError):
                self.check()


if __name__ == "__main__":
    unittest.main(verbosity=2)
