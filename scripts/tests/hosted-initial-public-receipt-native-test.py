#!/usr/bin/env python3
"""Actual nonroot POSIX file controls with synthetic public receipt DATA.

The real PrivateDirectory, _PrimaryOwner, K._File, byte-copy, metadata and close
mechanics execute. Clock/boot observations and the fixed worker location are
explicit models; no native/hosted acceptance, payload, key, network or child.
"""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
from copy import deepcopy
import ctypes
import hashlib
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise AssertionError("PUBLIC_RECEIPT_CONTROL_FORBIDDEN_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


R = load("public_receipt_native_controls", ROOT / "scripts/run-hosted-initial-recipient-productive-upload.py")
F = load("public_receipt_data_fixture", Path(__file__).with_name("hosted-initial-artifact-productive-delivery-test.py"))
D, K, C, Q, O = R.D, R.K, R.C, R.Q, R.O


class PublicReceiptNative(unittest.TestCase):
    @contextmanager
    def fixture(self):
        self.assertEqual(os.name, "posix")
        self.assertNotEqual(os.geteuid(), 0, "REQUIRES_ACTUAL_NONROOT_EXECUTION")
        with tempfile.TemporaryDirectory(prefix="p2pkit-public-receipts-") as temporary, ExitStack() as stack:
            temp = Path(temporary)
            base = temp / "custody"
            base.mkdir(mode=0o700)
            root = base / "productive-tail"
            root.mkdir(mode=0o700)
            for name in (*K._root_names(upload=True), "upload-returned"):
                (root / name).mkdir(mode=0o700)
            directory = root / "upload-returned"
            commands = temp / "_runner_file_commands"
            commands.mkdir(mode=0o700)
            output = commands / "set_output_00000000-0000-0000-0000-000000000001"
            output.touch(mode=0o600)
            model = F.qualification_fixture("linux-x64")
            upload = model["upload_raw"]
            upath = directory / D.UPLOAD_FILE
            upath.write_bytes(upload)
            upath.chmod(0o600)
            identity = D.sha(O.encoded([directory.stat().st_dev, directory.stat().st_ino]))
            with upath.open("rb") as stream:
                upload_metadata = O.encoded(Q._file_info(upath, stream, D.LIMIT).as_dict())
            close_hash = F.model_hash("original-upload-close-not-a-live-owner")
            after = deepcopy(model["after"])
            after["uploadCarrier"] = {"directoryIdentitySha256": identity,
                "fileMetadataSha256": D.sha(upload_metadata), "fileOwnerCloseSha256": close_hash}
            after_raw = D.encoded(D.pending_value(after, "after"), D.LIMIT)
            apath = directory / D.AFTER_FILE
            apath.write_bytes(after_raw)
            apath.chmod(0o600)
            with apath.open("rb") as stream:
                after_metadata = O.encoded(Q._file_info(apath, stream, D.LIMIT).as_dict())
            env = {"P2PKIT_EXPECTED_SHA": after["source"]["commit"], "P2PKIT_EXPECTED_TREE": after["source"]["tree"],
                "P2PKIT_INITIAL_SELECTION": after["selection"], "GITHUB_REPOSITORY": after["github"]["repository"],
                "GITHUB_SHA": after["source"]["commit"], "GITHUB_REF": D.S.SOURCE_REF,
                "GITHUB_RUN_ID": after["github"]["runId"], "GITHUB_RUN_ATTEMPT": after["github"]["runAttempt"],
                "GITHUB_JOB": after["github"]["job"], "RUNNER_TEMP": str(temp), "GITHUB_OUTPUT": str(output)}
            for label, raw, metadata, closed in (("UPLOAD", upload, upload_metadata, close_hash),
                    ("AFTER", after_raw, after_metadata, F.model_hash("original-after-close-not-a-live-owner"))):
                prefix = "P2PKIT_RECEIPT_" + label + "_"
                env.update({prefix + "OUTCOME": "success", prefix + "ARTIFACT_ID": after["artifact"]["id"],
                    prefix + "SHA256": D.sha(raw), prefix + "DIRECTORY_SHA256": identity,
                    prefix + "FILE_METADATA_SHA256": D.sha(metadata), prefix + "OWNER_CLOSE_SHA256": closed})
            first_ns = D.decimal(after["times"]["pendingPreparedNs"]) + R.NS
            clock = O.wire.clock_identity(after["deadline"]["clock"])
            state = SimpleNamespace(raw=first_ns, local_delta=0.0, wall=after["observedAt"] + 1, cancel=lambda: None,
                base=base, directory=directory, output=output, env=env, upload=upload, after=after_raw,
                boot=after["deadline"]["originalBootDigest"], first=O.clocks.Reading(clock, first_ns))
            attempts = {}
            stack.enter_context(patch.dict(os.environ, env, clear=True))
            stack.enter_context(patch.object(R, "_RECEIPT_ATTEMPTS", attempts))
            stack.enter_context(patch.object(R, "_RECEIPT_ENTRY", C.B.EntryLatch(attempts)))
            stack.enter_context(patch.object(R, "_RECEIPT_CLOCKS", {}))
            stack.enter_context(patch.object(R, "_QUARANTINE", []))
            stack.enter_context(patch.object(K.continuity, "QUARANTINE", []))
            stack.enter_context(patch.object(C, "_PRIMARY_OWNERS", {}))
            stack.enter_context(patch.object(C, "_PRIMARY_QUARANTINE", []))
            stack.enter_context(patch.object(K, "_FILE_PINS", {}))
            stack.enter_context(patch.object(C, "_paths", lambda kind: ({}, base, base)))
            stack.enter_context(patch.object(O.clocks, "observe", lambda: state.first))
            stack.enter_context(patch.object(O.clocks, "checked_now",
                lambda _clock, minimum_ns=0: max(minimum_ns, state.raw)))
            stack.enter_context(patch.object(K.continuity, "boot_digest", lambda _role: state.boot))
            stack.enter_context(patch.object(R, "time", SimpleNamespace(
                monotonic=lambda: time.monotonic() + state.local_delta, time=lambda: state.wall)))
            yield state

    def capture(self, fixture):
        return R.capture_public_originals("worker", lambda: fixture.cancel())

    def refused(self, fixture):
        with self.assertRaises(Exception):
            self.capture(fixture)
        self.assertEqual(fixture.output.read_bytes(), b"")

    def rewrite(self, fixture, name, raw):
        path = fixture.directory / name
        path.write_bytes(raw)
        path.chmod(0o600)
        prefix = "P2PKIT_RECEIPT_" + ("UPLOAD" if name == D.UPLOAD_FILE else "AFTER") + "_"
        os.environ[prefix + "SHA256"] = D.sha(raw)
        if len(raw) <= D.LIMIT:
            with path.open("rb") as stream:
                os.environ[prefix + "FILE_METADATA_SHA256"] = D.sha(O.encoded(
                    Q._file_info(path, stream, D.LIMIT).as_dict()))

    def test_original_bytes_and_both_native_owner_closes_precede_ready(self):
        with self.fixture() as f:
            owners, writes = [], []
            finish = C._PrimaryOwner.finish
            write = K._write_bytes
            def close(owner):
                result = finish(owner)
                owners.append(owner)
                return result
            def copy(owner, directory, name, raw):
                self.assertEqual(len(owners), 1)
                K._closed_files(owners[0])
                writes.append((name, raw))
                return write(owner, directory, name, raw)
            with patch.object(C._PrimaryOwner, "finish", close), patch.object(K, "_write_bytes", copy):
                clock = self.capture(f)
            self.assertEqual(len(owners), 2)
            self.assertIsNot(owners[0], owners[1])
            self.assertIs(owners[0].owner.fence, owners[1].owner.fence)
            self.assertEqual(owners[0].owner.local_end, owners[1].owner.local_end)
            for owner in owners:
                K._closed_files(owner)
            copied = f.base / R._RECEIPT_DIRECTORY
            self.assertEqual(set(p.name for p in copied.iterdir()), {D.UPLOAD_FILE, D.AFTER_FILE, R._RECEIPT_MANIFEST})
            self.assertEqual((copied / D.UPLOAD_FILE).read_bytes(), f.upload)
            self.assertEqual((copied / D.AFTER_FILE).read_bytes(), f.after)
            manifest = (copied / R._RECEIPT_MANIFEST).read_bytes()
            D.public_receipt_manifest_inputs(manifest, f.upload, f.after)
            self.assertEqual(f.output.read_bytes(), ("publicReceiptManifestSha256=" + D.sha(manifest) +
                "\npublicReceiptReady=true\n").encode("ascii"))
            self.assertEqual(clock.final - clock.first, 30 * R.NS)
            self.assertEqual(clock.work - clock.first, 20 * R.NS)
            self.assertEqual(writes[:2], [(D.UPLOAD_FILE, f.upload), (D.AFTER_FILE, f.after)])

    def test_missing_extra_oversize_noncanonical_and_wrong_source_refused(self):
        for mode in ("missing", "extra", "oversize", "noncanonical", "source"):
            with self.subTest(mode=mode), self.fixture() as f:
                if mode == "missing":
                    (f.directory / D.AFTER_FILE).unlink()
                elif mode == "extra":
                    (f.directory / "extra.json").write_bytes(b"{}")
                elif mode == "oversize":
                    self.rewrite(f, D.AFTER_FILE, b"x" * (D.LIMIT + 1))
                elif mode == "noncanonical":
                    self.rewrite(f, D.AFTER_FILE, f.after + b" ")
                else:
                    os.environ["P2PKIT_EXPECTED_SHA"] = "f" * 40
                    os.environ["GITHUB_SHA"] = "f" * 40
                self.refused(f)
                self.assertFalse((f.base / R._RECEIPT_DIRECTORY).exists())

    def test_symlink_hardlink_permission_and_same_bytes_replacement_refused(self):
        for mode in ("symlink", "hardlink", "permission", "replacement", "ancestor"):
            with self.subTest(mode=mode), self.fixture() as f:
                path = f.directory / D.UPLOAD_FILE
                if mode in ("symlink", "hardlink", "replacement"):
                    other = f.base / "saved-original"
                    path.rename(other)
                    if mode == "symlink":
                        path.symlink_to(other)
                    elif mode == "hardlink":
                        os.link(other, path)
                    else:
                        path.write_bytes(f.upload)
                        path.chmod(0o600)
                        other.unlink()
                elif mode == "permission":
                    path.chmod(0o644)
                else:
                    renamed = f.base / "moved-tail"
                    f.directory.parent.rename(renamed)
                    f.directory.parent.symlink_to(renamed, target_is_directory=True)
                self.refused(f)

    def test_byte_and_metadata_race_after_first_reads_refused(self):
        for mode in ("bytes", "inode", "directory"):
            with self.subTest(mode=mode), self.fixture() as f:
                original = D.public_receipt_pair
                def mutate(*args, **kwargs):
                    pair = original(*args, **kwargs)
                    path = f.directory / D.UPLOAD_FILE
                    if mode == "bytes":
                        path.write_bytes(f.upload[:-1] + b" ")
                    elif mode == "inode":
                        replacement = f.directory / "replacement"
                        replacement.write_bytes(f.upload)
                        replacement.chmod(0o600)
                        replacement.replace(path)
                    else:
                        os.utime(f.directory, ns=(1, 1))
                    return pair
                with patch.object(D, "public_receipt_pair", mutate):
                    self.refused(f)
                self.assertFalse((f.base / R._RECEIPT_DIRECTORY).exists())

    def test_anchor_artifact_and_upload_after_links_refused(self):
        for key in ("DIRECTORY_SHA256", "FILE_METADATA_SHA256", "OWNER_CLOSE_SHA256", "ARTIFACT_ID"):
            with self.subTest(key=key), self.fixture() as f:
                os.environ["P2PKIT_RECEIPT_UPLOAD_" + key] = "98765" if key == "ARTIFACT_ID" else "f" * 64
                self.refused(f)
        with self.fixture() as f:
            after = D.canonical(f.after)
            after["uploadSha256"] = "f" * 64
            self.rewrite(f, D.AFTER_FILE, D.encoded(after))
            self.refused(f)

    def test_duplicate_capture_or_existing_output_never_overwrites(self):
        with self.fixture() as f:
            self.capture(f)
            before = f.output.read_bytes()
            with self.assertRaises(Exception):
                self.capture(f)
            self.assertEqual(f.output.read_bytes(), before)
        with self.fixture() as f:
            target = f.base / R._RECEIPT_DIRECTORY
            target.mkdir(mode=0o700)
            marker = target / "preserved"
            marker.write_bytes(b"DO_NOT_REPLACE")
            self.refused(f)
            self.assertEqual(marker.read_bytes(), b"DO_NOT_REPLACE")

    def test_ambiguous_input_or_output_close_never_emits_ready(self):
        for target in ("upload-returned", R._RECEIPT_DIRECTORY):
            with self.subTest(target=target), self.fixture() as f:
                close, calls = Q._PosixDirectory.close, []
                def ambiguous(directory):
                    close(directory)
                    if directory.path.name == target:
                        calls.append(directory)
                        raise O.OriginError("MODEL_CLOSE_AMBIGUOUS_AFTER_REAL_CLOSE")
                with patch.object(Q._PosixDirectory, "close", ambiguous):
                    self.refused(f)
                self.assertEqual(len(calls), 1)
                if target == "upload-returned":
                    self.assertFalse((f.base / R._RECEIPT_DIRECTORY).exists())

    def test_cancel_deadline_boot_and_original_job_reserve_refused(self):
        for mode in ("cancel", "deadline", "boot", "jobreserve", "expiry"):
            with self.subTest(mode=mode), self.fixture() as f:
                if mode == "cancel":
                    def cancelled():
                        raise O.OriginError("MODEL_CANCELLED")
                    f.cancel = cancelled
                elif mode == "deadline":
                    f.raw += 20 * R.NS
                elif mode == "boot":
                    f.boot = "f" * 64
                elif mode == "jobreserve":
                    after = D.canonical(f.after)
                    f.raw = after["originalProposal"]["proposedJobEndNs"] - 180 * R.NS
                    f.first = O.clocks.Reading(f.first.clock, f.raw)
                else:
                    f.wall = D.canonical(f.after)["policyExpiresAt"]
                self.refused(f)
                self.assertFalse((f.base / R._RECEIPT_DIRECTORY).exists())

    def test_partial_copy_and_output_append_failure_not_upload_ready(self):
        with self.fixture() as f:
            write, calls = K._write_bytes, []
            def delayed(owner, directory, name, raw):
                result = write(owner, directory, name, raw)
                calls.append(name)
                f.local_delta = 31.0
                return result
            with patch.object(K, "_write_bytes", delayed):
                self.refused(f)
            self.assertEqual(calls, [D.UPLOAD_FILE])
        with self.fixture() as f:
            f.output.write_bytes(b"EXISTING_OUTPUT_MUST_NOT_BE_CHANGED")
            with self.assertRaises(Exception):
                self.capture(f)
            self.assertEqual(f.output.read_bytes(), b"EXISTING_OUTPUT_MUST_NOT_BE_CHANGED")


if __name__ == "__main__":
    unittest.main(failfast=True)
