#!/usr/bin/env python3
"""Small portable custody controls; NOT hosted/native/GPG qualification.

Only synthetic bytes in a new temporary directory are opened. E/PC admission,
clocks, and Popen are explicit models. The real portable file/tar/gzip/readback
mechanics run over that small fixture; no process, network, key generation,
production key, original evidence, or build is used. The packet-shaped test
bytes are NOT encrypted evidence and cannot establish cryptographic integrity.
"""
from __future__ import annotations

import base64
from contextlib import ExitStack
import ctypes
import dataclasses
import hashlib
import io
import os
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


FORBID_NATIVE = False


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen") or \
            FORBID_NATIVE and event in ("open", "os.listdir", "os.scandir", "os.mkdir", "os.remove", "os.rmdir"):
        raise AssertionError("PRODUCTIVE_PORTABLE_CONTROL_FORBIDDEN_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_evidence as H
import hosted_initial_recipient_evidence as E

NS = 1_000_000_000
PRIMARY, ENCRYPTION = "A" * 40, "B" * 40
PUBLIC = (b"-----BEGIN PGP PUBLIC KEY BLOCK-----\n\n" + base64.b64encode(b"\xc6\x01x") +
    b"\n-----END PGP PUBLIC KEY BLOCK-----\n")
PACKET_MODEL = b"\xc1\x0b\x03" + bytes.fromhex(ENCRYPTION[-16:]) + b"\x01\x00\xd2\x28\x01" + b"x" * 39


def listing():
    lines = []
    for tag, fingerprint, capabilities in (("pub", PRIMARY, "cC"), ("sub", ENCRYPTION, "e")):
        key, full = [""] * 12, [""] * 10
        key[0], key[1], key[2], key[3], key[6], key[11] = tag, "u", "4096", "1", "1000000", capabilities
        full[0], full[9] = "fpr", fingerprint
        lines.extend((":".join(key), ":".join(full)))
    return ("\n".join(lines) + "\n").encode("ascii")


class PortableCustodyControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit-productive-posix-model-")
        self.root = Path(self.temporary.name)
        self.addCleanup(self.temporary.cleanup)
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.addCleanup(self.dispose_models)
        self.local, self.clock_forbidden = 1000.0, False
        self.guard_action = self.poll_action = lambda *_args: None
        self.processes, self.guard_calls, self.keyring_completed = [], 0, False
        self.keyring = None
        self.work = self.root / "public-crypto"
        self.work.mkdir(mode=0o700)
        self.child = object()
        self.clock = SimpleNamespace(role="linux-x64", domain="MODEL_ONLY", ticks_per_second=NS)
        self.validation_view = SimpleNamespace(child=self.child, role="linux-x64", work=self.work,
            public_key_raw=PUBLIC, policy_raw=('{"recipient":{"fingerprint":"' + PRIMARY + '"}}').encode("ascii"),
            source=SimpleNamespace(job_id="a" * 32), caps=self.caps(60))
        self.validation_binding = E._ProductiveValidationBinding(self.validation_view)
        model_time = SimpleNamespace(monotonic=self.now, time=lambda: 2000.0, sleep=lambda _seconds: None)
        self.install(H, "time", model_time)
        self.install(H.primitives, "time", model_time)  # The moved deadline keeps the SAME modeled original clock.
        for name in ("_PRODUCTIVE_SESSIONS", "_PRODUCTIVE_ATTEMPTS", "_PRODUCTIVE_RESOURCES", "_PRODUCTIVE_CLOSES",
                "_PRODUCTIVE_FINISHES", "_PRODUCTIVE_RESULTS", "_PRODUCTIVE_OBSERVATIONS", "_PRODUCTIVE_STREAMS",
                "_PRODUCTIVE_RECIPIENTS"):
            self.install(H, name, {})
        self.install(H, "_PRODUCTIVE_QUARANTINE", [])
        self.install(E, "_checked_productive_validation_binding", lambda binding: binding.view)
        self.install(E, "_checked_productive_export_binding", lambda binding: binding.view)
        self.install(E, "_productive_work_guard", self.guard)
        self.install(E, "_productive_whole_guard", self.guard)
        self.install(E, "_productive_node_guard", self.node_guard)
        self.install(E, "_productive_expected_node", lambda _binding, name: self.nodes[name])
        self.install(E, "_productive_check_snapshot", self.check_snapshot)
        self.install(E, "_productive_manifest", lambda _binding, digest, size:
            ('{"model":"NOT_ENCRYPTED_EVIDENCE","sha256":"' + digest + '","size":' + str(size) + '}\n').encode("ascii"))
        self.install(E, "_productive_keyring_begin", self.keyring_begin)
        self.install(E, "_productive_keyring_guard", self.keyring_guard)
        self.install(E, "_productive_keyring_complete", self.keyring_complete)
        self.install(H.shutil, "which", lambda name: sys.executable if name == "gpg" else None)
        self.install(H, "_gpg_environment", lambda recipient: {"HOME": str(recipient.work_dir),
            H.audit_processes.JOB_ENV: self.validation_view.source.job_id})
        case = self

        class ModelProcess:
            def __init__(self, command, **kwargs):
                case.assertIs(kwargs["stdin"], H.subprocess.DEVNULL)
                case.assertIs(kwargs["close_fds"], True)
                case.assertEqual(kwargs["cwd"], case.work)
                self.args, self.kwargs, self.pid = command, kwargs, 4000 + len(case.processes)
                self.returncode, self.waits, self.signals = None, [], []
                case.processes.append(self)
                if "--encrypt" in command:
                    # Independently inspect the tiny real tar/gzip input before
                    # the model returns its deliberately noncryptographic bytes.
                    with tarfile.open(fileobj=io.BytesIO(Path(command[-1]).read_bytes()), mode="r:gz") as archive:
                        case.assertEqual(set(archive.getnames()), {"evidence", "evidence/group",
                            *("evidence/" + name for name in case.contents)})
                        for member in archive:
                            case.assertEqual((member.uid, member.gid, member.uname, member.gname, member.mtime),
                                (0, 0, "", "", 0))
                            case.assertEqual(member.mode, 0o700 if member.isdir() else 0o600)
                            if member.isfile():
                                with archive.extractfile(member) as handle:
                                    case.assertEqual(handle.read(), case.contents[member.name.removeprefix("evidence/")])
                    kwargs["stdout"].write(PACKET_MODEL)
                    case.assertEqual(len(kwargs["pass_fds"]), 1)
                    os.write(kwargs["pass_fds"][0], b"[GNUPG:] BEGIN_ENCRYPTION 2 9\n[GNUPG:] END_ENCRYPTION\n")
                else:
                    kwargs["stdout"].write(listing())

            def poll(self):
                case.poll_action(self)
                self.returncode = 0 if self.returncode is None else self.returncode
                return self.returncode

            def wait(self, timeout=None):
                self.waits.append(timeout)
                return self.returncode

            def terminate(self):
                self.signals.append("terminate")

            def kill(self):
                self.signals.append("kill")
                self.returncode = -9

        self.ModelProcess = ModelProcess
        self.install(H.subprocess, "Popen", ModelProcess)

    def dispose_models(self):
        # Test-fixture disposal only, after assertions; never a source receipt.
        global FORBID_NATIVE
        FORBID_NATIVE = False
        for row in list(H._PRODUCTIVE_RESOURCES.values()):
            resource = row["resource"]
            if resource.kind == "file" and not resource.owner.closed:
                resource.owner.close()
        self.clock_forbidden = False

    def install(self, owner, name, value):
        return self.stack.enter_context(patch.object(owner, name, value))

    def caps(self, seconds):
        first = SimpleNamespace(clock=self.clock, nanoseconds=100 * NS)
        return SimpleNamespace(clock=self.clock, first=first, firstLocal=self.local, workEndNs=(100 + seconds) * NS,
            workEndLocal=self.local + seconds, operationFinishEndNs=(100 + seconds) * NS,
            operationFinishEndLocal=self.local + seconds, finishReserveNs=0, operationLimitNs=seconds * NS)

    def now(self):
        if self.clock_forbidden:
            raise AssertionError("PASSIVE_PORTABLE_CHECK_SAMPLED_CLOCK")
        return self.local

    def guard(self, binding):
        if self.clock_forbidden:
            raise AssertionError("PASSIVE_PORTABLE_CHECK_CALLED_E")
        self.guard_calls += 1
        self.guard_action(binding)
        return binding.view.caps

    def node_guard(self, binding, node):
        self.guard(binding)
        self.assertIs(self.nodes[node.relative], node)
        return node

    def check_snapshot(self, binding, entries):
        self.guard(binding)
        self.assertEqual(set(entries), set(self.nodes))
        for name, actual in entries.items():
            self.assertEqual(actual, self.nodes[name].native[1:])
        return entries

    def keyring_begin(self, binding):
        self.assertIsNone(self.keyring)
        first = SimpleNamespace(clock=self.clock, nanoseconds=100 * NS)
        self.keyring = E._ProductiveKeyringCap(first, self.local, 130 * NS, self.local + 30.0, 30 * NS)
        return self.keyring

    def keyring_guard(self, binding, cap):
        self.assertIs(cap, self.keyring)
        self.assertFalse(self.keyring_completed)
        self.guard(binding)
        return cap

    def keyring_complete(self, binding, cap):
        self.keyring_guard(binding, cap)
        state = H._PRODUCTIVE_ATTEMPTS[id(binding)]
        rows = [H._PRODUCTIVE_RESOURCES[id(value)] for value in state["resources"]]
        self.assertTrue(any(row["keyring"] is cap for row in rows))
        self.assertTrue(all(row["close"] is not None for row in rows if row["keyring"] is cap))
        self.keyring_completed = True
        return cap

    def validate(self):
        return H._validate_initial_productive(self.validation_binding)

    def prepare_export(self, recipient):
        self.payload, self.output = self.root / "payload", self.root / "export-output"
        self.payload.mkdir(mode=0o700)
        (self.payload / "group").mkdir(mode=0o700)
        self.contents = {"group/member-00000.bin": b"small synthetic input\n",
            "map-group.json": b"{}\n", "copy-index.json": b"{\"model\":true}\n"}
        for name, raw in self.contents.items():
            (self.payload / name).write_bytes(raw)
            (self.payload / name).chmod(0o600)
        self.nodes = {}
        for name in ("", "group", *self.contents):
            info = (self.payload / name).lstat()
            data = self.contents.get(name)
            self.nodes[name] = SimpleNamespace(relative=name, kind="directory" if data is None else "file",
                bytes=None if data is None else len(data), sha256=None if data is None else hashlib.sha256(data).hexdigest(),
                native=("posix", *H._stamp(info)), provenance=object())
        self.export_view = SimpleNamespace(child=self.child, role="linux-x64", recipient=recipient,
            payload=self.payload, output=self.output, caps=self.caps(240))
        self.export_binding = E._ProductiveExportBinding(self.export_view)
        return self.export_binding

    def full(self):
        validation = self.validate()
        self.prepare_export(validation.recipient)
        return validation, H._export_initial_productive(self.export_binding)

    def test_00_original_small_file_archive_readback_and_close_chain(self):
        validation, result = self.full()
        self.assertIs(H._checked_productive_validation_return(validation, self.validation_binding), validation)
        self.assertIs(H._checked_productive_export_return(result, self.export_binding), result)
        self.assertEqual(set(path.name for path in self.output.iterdir()), {H.ARTIFACT, H.MANIFEST})
        self.assertEqual((self.output / H.ARTIFACT).read_bytes(), PACKET_MODEL)
        self.assertEqual(result.artifact.sha256, hashlib.sha256(PACKET_MODEL).hexdigest())
        self.assertEqual(result.artifact.size, len(PACKET_MODEL))
        state = H._pg_state(result.session)
        self.assertFalse(state["private"][0].exists())
        self.assertIsNotNone(state["cleanup_return"])
        self.assertTrue(self.keyring_completed)
        self.assertEqual(len(self.processes), 4)  # show-only, list, one recheck, one model encryption.
        self.assertTrue(all(len(process.waits) == 1 for process in self.processes))
        self.assertTrue(all(H._PRODUCTIVE_RESOURCES[id(resource)]["close"] is not None for resource in state["resources"]))
        self.assertEqual({row[3].relative for row in result.observations if row[0] == "tar-input-complete"}, set(self.contents))
        formats = [row[1] for row in result.observations if row[0] == "actual-close-return" and
            row[1].kind in ("format-writer", "tar-stream", "gzip")]
        self.assertEqual([resource.kind for resource in formats], ["format-writer", "tar-stream", "gzip"])
        for resource in formats:
            row = H._PRODUCTIVE_RESOURCES[id(resource)]
            self.assertEqual(row["close"].operation, "DIRECT_CLOSE_RETURN")
            self.assertIsNone(row["transferred"])
            self.assertEqual(row["children"], ())
        self.assertIs(formats[0].owner.fileobj, formats[1].owner)
        self.assertIs(formats[0].owner._extfileobj, True)
        self.assertIs(formats[1].owner._extfileobj, True)
        self.assertEqual(formats[1].owner.buf, b"")
        transfers = [row for row in result.observations if row[0] == "original-tar-stream-direct-ownership-transfer"]
        self.assertEqual(len(transfers), 1)
        self.assertIs(transfers[0][1], formats[0])
        self.assertIs(transfers[0][2], formats[1])
        self.assertEqual(transfers[0][3], (False, True))

    def test_equal_unregistered_result_cannot_supply_known_close(self):
        result = self.validate()
        with self.assertRaises(H.EvidenceError):
            H._checked_productive_validation_return(dataclasses.replace(result), self.validation_binding)

    def test_duplicate_binding_is_sticky_before_more_effects(self):
        session = H._pg_new(self.validation_binding, "validation")
        with self.assertRaises(H.EvidenceError):
            H._pg_new(self.validation_binding, "validation")
        with self.assertRaises(H.EvidenceError):
            H._pg_guard(session)
        self.assertFalse(self.processes)

    def test_passive_return_does_not_sample_clock_or_reopen_child_roots(self):
        global FORBID_NATIVE
        validation, result = self.full()
        previous = self.guard_calls
        self.clock_forbidden = FORBID_NATIVE = True
        try:
            self.assertIs(H._checked_productive_validation_return(validation, self.validation_binding), validation)
            self.assertIs(H._checked_productive_export_return(result, self.export_binding), result)
        finally:
            self.clock_forbidden = FORBID_NATIVE = False
        self.assertEqual(self.guard_calls, previous)

    def test_actual_closed_process_returncode_mutation_is_rejected(self):
        result = self.validate()
        self.processes[0].returncode = 1
        with self.assertRaises(H.EvidenceError):
            H._checked_productive_validation_return(result, self.validation_binding)

    def test_recipient_field_mutation_is_not_adopted_after_return(self):
        result = self.validate()
        object.__setattr__(result.recipient, "encryption_fingerprint", "C" * 40)
        with self.assertRaises(H.EvidenceError):
            H._checked_productive_validation_return(result, self.validation_binding)

    def test_original_caps_replacement_refuses_before_file_open(self):
        session = H._pg_new(self.validation_binding, "validation")
        self.validation_view.caps = self.caps(60)
        with self.assertRaises(H.EvidenceError):
            H._pg_open(session, self.work / "not-created", write=True)
        self.assertFalse((self.work / "not-created").exists())

    def test_original_work_deadline_refuses_before_file_open(self):
        session = H._pg_new(self.validation_binding, "validation")
        self.local = self.validation_view.caps.workEndLocal
        with self.assertRaises(H.EvidenceError):
            H._pg_open(session, self.work / "not-created", write=True)
        self.assertFalse((self.work / "not-created").exists())

    def test_shared_primitive_clock_uses_original_end_and_passive_checks_never_sample_it(self):
        self.assertIs(H.time, H.primitives.time)
        session = H._pg_new(self.validation_binding, "validation")
        state = H._pg_state(session)
        original_end = state["caps"].workEndLocal
        self.local = original_end - 0.001
        self.assertIsNone(H._deadline(original_end))
        previous = self.guard_calls
        self.clock_forbidden = True
        try:
            self.assertIsNone(H._pg_passive(state))
        finally:
            self.clock_forbidden = False
        self.assertEqual(self.guard_calls, previous)
        self.local = original_end
        with self.assertRaisesRegex(H.EvidenceError, "operation exceeded its deadline"):
            H._deadline(original_end)
        with self.assertRaisesRegex(H.EvidenceError, "WORK_DEADLINE") as failed:
            H._pg_guard(session)
        self.assertEqual(state["caps"].workEndLocal, original_end)
        self.local = original_end - 1.0
        with self.assertRaises(H.EvidenceError) as repeated:
            H._pg_guard(session)
        self.assertIs(repeated.exception, failed.exception)
        self.assertEqual(self.processes, [])

    def primitive_mutations(self, *, suppliers):
        leaf = H.primitives
        rows = [(leaf, name) for name in ("EvidenceError", "_fail", "_deadline", "_path",
            "_private_directory", "_identity", "Path", "os", "stat", "time")]
        rows.append((H, "primitives"))
        if suppliers:
            rows.extend(((leaf.time, "monotonic"), (leaf.os, "getuid"),
                (leaf.stat, "S_ISDIR"), (leaf.stat, "S_ISLNK"), (leaf.Path, "lstat")))
        return rows

    def original_primitive_refusal(self, *, phase):
        global FORBID_NATIVE
        public = tuple((name, getattr(H, name)) for name in
            ("EvidenceError", "_fail", "_deadline", "_path", "_private_directory", "_identity"))
        for ordinal, (owner, name) in enumerate(self.primitive_mutations(suppliers=phase != "callback")):
            # Each row owns a new synthetic binding and quarantine namespace.
            # A failed original is never cleared or reused as a passing attempt.
            with self.subTest(phase=phase, slot=name, ordinal=ordinal), ExitStack() as stack:
                stack.enter_context(patch.object(H, "_PRODUCTIVE_QUARANTINE", []))
                original, invoked = getattr(owner, name), []
                if isinstance(original, ModuleType):
                    replacement = ModuleType(original.__name__)
                    vars(replacement).update(vars(original))
                elif isinstance(original, SimpleNamespace):
                    replacement = SimpleNamespace(**vars(original))
                elif isinstance(original, type):
                    replacement = type(original.__name__, (original,), {})
                else:
                    def replacement(*args, _original=original, **kwargs):
                        invoked.append(name)
                        return _original(*args, **kwargs)
                    replacement.__name__ = original.__name__
                binding = E._ProductiveValidationBinding(self.validation_view)
                target = self.work / ("primitive-must-not-exist-" + str(ordinal))
                changed = []
                def mutate(_binding):
                    if not changed:
                        changed.append(stack.enter_context(patch.object(owner, name, replacement)))
                    return _binding.view
                if phase == "admission":
                    stack.enter_context(patch.object(E, "_checked_productive_validation_binding", mutate))
                    session = None
                else:
                    session = H._pg_new(binding, "validation")
                    class ModelOwner:
                        def __init__(self):
                            self.closes = 0
                        def close(self):
                            self.closes += 1
                    retained = ModelOwner()
                    resource = H._pg_keep(session, retained, "scandir", "primitive-model", ("close",))
                    if phase == "callback":
                        self.guard_action = mutate
                    else:
                        mutate(binding)
                previous, FORBID_NATIVE = FORBID_NATIVE, True
                try:
                    with self.assertRaisesRegex(H.EvidenceError, "ADMISSION_CALLBACK_CHANGED|SUPPLIER_CHANGED") as failed:
                        if phase == "admission":
                            H._pg_new(binding, "validation")
                        else:
                            H._pg_open(session, target, write=True)
                    state = H._PRODUCTIVE_ATTEMPTS[id(binding)]
                    session = state["session"]
                    for alias, saved in public:
                        self.assertIs(getattr(H, alias), saved)
                    H._pg_abort(session, failed.exception)
                    self.assertTrue(state["unknown"])
                    self.assertIsNone(state["result"])
                    self.assertIsNone(state["finish"])
                    self.assertIs(state["failure"], failed.exception)
                    self.assertIn(session, H._PRODUCTIVE_QUARANTINE)
                    if phase != "admission":
                        self.assertEqual(retained.closes, 0)
                        self.assertFalse(H._PRODUCTIVE_RESOURCES[id(resource)]["attempted"])
                    self.assertEqual(invoked, [])
                finally:
                    FORBID_NATIVE = previous
                    self.guard_action = lambda *_args: None
                # Restore supplier slots, not session authority. Failure and
                # UNKNOWN must remain on that exact original session/binding.
                stack.close()
                with self.assertRaises(H.EvidenceError) as repeated:
                    H._pg_guard(session)
                self.assertIs(repeated.exception, failed.exception)
                with self.assertRaises(H.EvidenceError) as duplicate:
                    H._pg_new(binding, "validation")
                self.assertIs(duplicate.exception, failed.exception)
                self.assertTrue(state["unknown"])
                self.assertFalse(target.exists())
                self.assertEqual(self.processes, [])

    def test_original_leaf_slots_and_supplier_methods_are_pinned_before_admission_callback(self):
        self.original_primitive_refusal(phase="admission")

    def test_later_leaf_or_original_supplier_replacement_refuses_before_owned_effect(self):
        self.original_primitive_refusal(phase="guard")

    def test_later_callback_cannot_replace_leaf_globals_behind_unchanged_public_aliases(self):
        self.original_primitive_refusal(phase="callback")

    def test_file_close_records_original_descriptor_transitive_return(self):
        session = H._pg_new(self.validation_binding, "validation")
        H._pg_write(session, self.work / "small", b"x", 1)
        state = H._pg_state(session)
        file_row = next(H._PRODUCTIVE_RESOURCES[id(value)] for value in state["resources"] if value.kind == "file")
        descriptor_row = H._PRODUCTIVE_RESOURCES[id(file_row["parent"])]
        self.assertIs(descriptor_row["close"].returned, file_row["close"])
        self.assertEqual(descriptor_row["close"].operation, "TRANSITIVE_FDOPEN_OWNER_CLOSE")

    def test_builtin_readall_cannot_replace_same_owner_read(self):
        session = H._pg_new(self.validation_binding, "validation")
        path = self.work / "builtin-model"
        path.write_bytes(b"tiny synthetic input")
        resource, _ = H._pg_open(session, path)
        self.assertIs(H._pg_resource_current(resource)["resource"], resource)
        resource.owner.read = resource.owner.readall
        with self.assertRaisesRegex(H.EvidenceError, "RESOURCE_METHOD_CHANGED"):
            H._pg_resource_current(resource)

    def test_original_instance_method_slot_is_identity_pinned(self):
        with io.BytesIO(b"model") as owner:
            owner.read = owner.read
            original = H._pg_methods(owner, ("read",))
            H._pg_methods_current(owner, original, "MODEL_METHOD_CHANGED")
            owner.read = type(owner).read.__get__(owner)
            with self.assertRaisesRegex(H.EvidenceError, "MODEL_METHOD_CHANGED"):
                H._pg_methods_current(owner, original, "MODEL_METHOD_CHANGED")

    def test_guard_substituted_write_flush_is_never_invoked(self):
        session = H._pg_new(self.validation_binding, "validation")
        invoked = []
        def replace(_binding):
            frame = sys._getframe(3)  # guard action -> model E -> native guard -> actual caller.
            if frame.f_code.co_name == "_pg_write" and "resource" in frame.f_locals:
                frame.f_locals["resource"].owner.flush = lambda: invoked.append("flush")
        self.guard_action = replace
        with self.assertRaisesRegex(H.EvidenceError, "RESOURCE_METHOD_CHANGED"):
            H._pg_write(session, self.work / "flush-model", b"", 1)
        self.assertEqual(invoked, [])

    def test_guard_substituted_close_fileno_is_never_invoked(self):
        session = H._pg_new(self.validation_binding, "validation")
        resource, _ = H._pg_open(session, self.work / "close-model", write=True)
        invoked = []
        self.guard_action = lambda _binding: setattr(resource.owner, "fileno", lambda: invoked.append("fileno"))
        with self.assertRaisesRegex(H.EvidenceError, "RESOURCE_METHOD_CHANGED"):
            H._pg_close(session, resource)
        self.assertEqual(invoked, [])
        self.assertFalse(H._PRODUCTIVE_RESOURCES[id(resource)]["attempted"])

    def test_changed_descriptor_is_rejected_before_fdopen_transfer(self):
        invoked = []
        def fdopen(*_args, **_kwargs):
            invoked.append("fdopen")
            raise AssertionError("MODEL_CHANGED_DESCRIPTOR_TRANSFERRED")
        self.install(H.os, "fdopen", fdopen)
        session = H._pg_new(self.validation_binding, "validation")
        def replace(_binding):
            frame = sys._getframe(3)
            if frame.f_code.co_name == "_pg_open" and "descriptor" in frame.f_locals:
                object.__setattr__(frame.f_locals["descriptor"], "label", "changed-model-label")
        self.guard_action = replace
        with self.assertRaisesRegex(H.EvidenceError, "OBJECT_CHANGED"):
            H._pg_open(session, self.work / "transfer-model", write=True)
        self.assertEqual(invoked, [])
        resource = H._pg_state(session)["resources"][0]
        self.assertFalse(H._PRODUCTIVE_RESOURCES[id(resource)]["transfer_attempted"])
        os.close(resource.owner)  # Fixture disposal only, never a source close receipt.

    def test_poll_substituted_output_fileno_is_never_invoked(self):
        invoked = []
        self.poll_action = lambda process: setattr(process.kwargs["stdout"], "fileno",
            lambda: invoked.append("fileno"))
        with self.assertRaisesRegex(H.EvidenceError, "RESOURCE_METHOD_CHANGED"):
            self.validate()
        self.assertEqual(invoked, [])

    def test_guard_substituted_archive_final_flush_is_never_invoked(self):
        validation = self.validate()
        self.prepare_export(validation.recipient)
        invoked = []
        def replace(_binding):
            frame = sys._getframe(3)
            compressed = frame.f_locals.get("compressed_owner")
            if frame.f_code.co_name == "_pg_archive" and compressed is not None and \
                    H._PRODUCTIVE_RESOURCES[id(compressed)]["close"] is not None:
                frame.f_locals["raw"].owner.flush = lambda: invoked.append("flush")
        self.guard_action = replace
        with self.assertRaisesRegex(H.EvidenceError, "RESOURCE_METHOD_CHANGED"):
            H._export_initial_productive(self.export_binding)
        self.assertEqual(invoked, [])

    def test_gzip_header_callback_cannot_adopt_a_changed_close_descriptor(self):
        validation = self.validate()
        self.prepare_export(validation.recipient)
        original_close = H.gzip.GzipFile.close
        retained, invoked = [], []
        def changed_close(_owner):
            invoked.append("changed-close")
        def replace(_binding):
            frame = sys._getframe(1)
            for _ in range(15):
                if frame is None:
                    break
                if frame.f_code.co_name == "_write_gzip_header":
                    # Test-only retention of a constructor that has not yet
                    # returned; it is NOT an admitted backend resource/close.
                    retained.append(frame.f_locals["self"])
                    H.gzip.GzipFile.close = changed_close
                    return
                frame = frame.f_back
        self.guard_action = replace
        try:
            with self.assertRaisesRegex(H.EvidenceError, "SUPPLIER_CHANGED"):
                H._export_initial_productive(self.export_binding)
            self.assertEqual(len(retained), 1)
            self.assertEqual(invoked, [])
            state = H._PRODUCTIVE_ATTEMPTS[id(self.export_binding)]
            self.assertFalse(any(resource.kind == "gzip" for resource in state["resources"]))
            self.assertIsNone(state["result"])
            self.assertTrue(state["unknown"])
        finally:
            H.gzip.GzipFile.close = original_close
            for owner in retained:
                owner.fileobj = None  # Fixture disposal only; no trailer or source close receipt.

    def _premature_tar_close_flags(self, *, during_padding):
        validation = self.validate()
        self.prepare_export(validation.recipient)
        if during_padding:
            # Five entries give 40,448 pre-close tar bytes. The real 1,024-byte
            # ending emits the fourth ORIGINAL 10,240-byte stream chunk inside
            # TarFile.close, draining gzip's original buffered 30,720 bytes to
            # the guarded sink (also reached with unbuffered gzip).
            name = "group/member-00000.bin"
            raw = b"p" * 36864
            self.contents[name] = raw
            (self.payload / name).write_bytes(raw)
            info = (self.payload / name).lstat()
            self.nodes[name] = SimpleNamespace(relative=name, kind="file", bytes=len(raw),
                sha256=hashlib.sha256(raw).hexdigest(), native=("posix", *H._stamp(info)), provenance=object())
        changed = []

        def replace(_binding):
            if changed:
                return
            state = H._PRODUCTIVE_ATTEMPTS.get(id(self.export_binding))
            if state is None:
                return
            owners = {resource.kind: resource for resource in state["formats"]}
            archive_owner, stream_owner = owners.get("format-writer"), owners.get("tar-stream")
            if archive_owner is None or stream_owner is None:
                return
            frame = sys._getframe(1)
            for _ in range(30):
                if frame is None:
                    return
                target = (frame.f_code is H.tarfile.TarFile.close.__code__ and
                    frame.f_locals.get("self") is archive_owner.owner) if during_padding else (
                    frame.f_code is H._pg_close.__code__ and frame.f_locals.get("resource") is archive_owner)
                if target:
                    self.assertIs(H._PRODUCTIVE_RESOURCES[id(archive_owner)]["attempted"], during_padding)
                    self.assertIs(H._PRODUCTIVE_RESOURCES[id(stream_owner)]["attempted"], False)
                    self.assertIs(archive_owner.owner.closed, during_padding)
                    self.assertIs(stream_owner.owner.closed, False)
                    self.assertTrue(stream_owner.owner.buf)
                    changed.append((archive_owner, stream_owner, stream_owner.owner.buf))
                    archive_owner.owner.closed = True
                    stream_owner.owner.closed = True
                    return
                frame = frame.f_back

        self.guard_action = replace
        try:
            with self.assertRaisesRegex(H.EvidenceError, "LIVE_FORMAT_ALREADY_CLOSED") as caught:
                H._export_initial_productive(self.export_binding)
            self.assertEqual(len(changed), 1)
            archive_owner, stream_owner, pending = changed[0]
            state = H._PRODUCTIVE_ATTEMPTS[id(self.export_binding)]
            self.assertTrue(pending)
            self.assertIsNone(H._PRODUCTIVE_RESOURCES[id(archive_owner)]["close"])
            self.assertIsNone(H._PRODUCTIVE_RESOURCES[id(stream_owner)]["close"])
            self.assertFalse(H._PRODUCTIVE_RESOURCES[id(stream_owner)]["attempted"])
            self.assertIsNone(state["result"])
            self.assertIs(state["failure"], caught.exception)
            self.assertFalse(any("--encrypt" in process.args for process in self.processes))
            self.assertFalse(self.output.exists())
            archive_owner.owner.closed = stream_owner.owner.closed = False
            with self.assertRaises(H.EvidenceError) as repeated:
                H._pg_guard(state["session"])
            self.assertIs(repeated.exception, caught.exception)  # Restored flags do not renew failed authority.
        finally:
            # TEST-only disposal after assertions; no source receipt or later
            # destructor may manufacture padding/trailers for the failed run.
            self.guard_action = lambda *_args: None
            state = H._PRODUCTIVE_ATTEMPTS.get(id(self.export_binding))
            for resource in () if state is None else state["formats"]:
                if resource.kind == "gzip":
                    resource.owner.fileobj = None
                else:
                    resource.owner.closed = True

    def test_coupled_tar_stream_flags_before_close_do_not_supply_receipts(self):
        self._premature_tar_close_flags(during_padding=False)

    def test_stream_flag_during_real_tar_padding_cannot_skip_its_direct_close(self):
        self._premature_tar_close_flags(during_padding=True)

    def test_guard_substituted_publication_write_is_never_invoked(self):
        validation = self.validate()
        self.prepare_export(validation.recipient)
        invoked = []
        def replace(_binding):
            frame = sys._getframe(3)
            reader = frame.f_locals.get("reader")
            if frame.f_code.co_name == "_pg_publish" and reader is not None and reader.count:
                frame.f_locals["target"].owner.write = lambda _block: invoked.append("write")
        self.guard_action = replace
        with self.assertRaisesRegex(H.EvidenceError, "RESOURCE_METHOD_CHANGED"):
            H._export_initial_productive(self.export_binding)
        self.assertEqual(invoked, [])

    def test_failed_close_is_not_retried_or_converted_to_known_close(self):
        class FailedClose:
            def __init__(self):
                self.calls = 0

            def close(self):
                self.calls += 1
                raise OSError("MODEL_CLOSE_FAILURE")
        session = H._pg_new(self.validation_binding, "validation")
        owner = FailedClose()
        resource = H._pg_keep(session, owner, "scandir", "model", ("close",))
        with self.assertRaises(OSError):
            H._pg_close(session, resource)
        H._pg_abort(session, RuntimeError("later failure"))
        self.assertEqual(owner.calls, 1)
        self.assertIsNone(H._PRODUCTIVE_RESOURCES[id(resource)]["close"])
        self.assertTrue(H._pg_state(session)["unknown"])

    def test_failed_fdopen_retains_uncertain_transfer_without_double_close(self):
        def refuse(*_args, **_kwargs):
            raise OSError("MODEL_FDOPEN_FAILURE")
        self.install(H.os, "fdopen", refuse)
        session = H._pg_new(self.validation_binding, "validation")
        with self.assertRaises(OSError):
            H._pg_open(session, self.work / "small", write=True)
        H._pg_abort(session, RuntimeError("model abort"))
        descriptor = H._pg_state(session)["resources"][0]
        row = H._PRODUCTIVE_RESOURCES[id(descriptor)]
        self.assertTrue(row["transfer_attempted"])
        self.assertFalse(row["attempted"])
        self.assertTrue(H._pg_state(session)["unknown"])
        os.close(descriptor.owner)  # Test-owned disposal, NOT a registered source close.

    def test_actual_tar_bytes_must_match_expected_map_hash(self):
        validation = self.validate()
        self.prepare_export(validation.recipient)
        self.nodes["map-group.json"].sha256 = "0" * 64
        with self.assertRaisesRegex(H.EvidenceError, "TAR_ACTUAL_BYTES_OR_EOF"):
            H._export_initial_productive(self.export_binding)
        self.assertFalse(self.output.exists())

    def test_full_native_snapshot_rejects_new_unlisted_member(self):
        validation = self.validate()
        self.prepare_export(validation.recipient)
        (self.payload / "unexpected").write_bytes(b"fixture only")
        with self.assertRaises(AssertionError):
            H._export_initial_productive(self.export_binding)
        self.assertFalse(self.output.exists())

    def test_member_open_rejects_post_snapshot_native_change(self):
        validation = self.validate()
        self.prepare_export(validation.recipient)
        session = H._pg_new(self.export_binding, "export")
        snapshot = H._pg_snapshot(session, self.payload)
        (self.payload / "map-group.json").write_bytes(b"changed")
        with self.assertRaisesRegex(H.EvidenceError, "MEMBER_CHANGED"):
            H._pg_member(session, self.payload, "map-group.json", snapshot)
        H._pg_abort(session, RuntimeError("model abort"))

    def test_gpg_command_mutation_after_original_spawn_refuses(self):
        self.poll_action = lambda process: process.args.append("--not-original")
        with self.assertRaisesRegex(H.EvidenceError, "GPG_COMMAND_CHANGED"):
            self.validate()

    def test_gpg_original_environment_mutation_refuses(self):
        self.poll_action = lambda process: process.kwargs["env"].update(HOME="/different-model-home")
        with self.assertRaisesRegex(H.EvidenceError, "GPG_ENVIRONMENT_CHANGED|GPG_COMMAND_CHANGED"):
            self.validate()

    def test_known_failed_operation_removes_only_exclusive_owned_files(self):
        session = H._pg_new(self.validation_binding, "validation")
        state = H._pg_state(session)
        private = self.work / "export-model"
        private.mkdir(mode=0o700)
        state["private"] = (private, private.lstat())
        H._pg_write(session, private / "evidence.tar.gz", b"synthetic", 9)
        original = self.root / "unrelated"
        original.write_bytes(b"preserve")
        failure = RuntimeError("model failure after known close")
        H._pg_abort(session, failure)
        self.assertFalse(private.exists())
        self.assertEqual(original.read_bytes(), b"preserve")
        self.assertIs(state["failure"], failure)
        self.assertIsNone(state["finish"])

    def test_unknown_close_prevents_failure_file_deletion(self):
        session = H._pg_new(self.validation_binding, "validation")
        state = H._pg_state(session)
        private = self.work / "export-model"
        private.mkdir(mode=0o700)
        state["private"] = (private, private.lstat())
        H._pg_write(session, private / "evidence.tar.gz", b"synthetic", 9)
        state["unknown"] = True
        H._pg_abort(session, RuntimeError("unknown model close"))
        self.assertEqual((private / "evidence.tar.gz").read_bytes(), b"synthetic")
        self.assertIsNone(state["finish"])

    def test_failed_removal_is_attempted_once_not_retried_by_abort(self):
        original_unlink, attempts = H.os.unlink, []
        private = self.work / "export-model"
        private.mkdir(mode=0o700)
        target = private / "evidence.tar.gz"
        def unlink(path, *args, **kwargs):
            if Path(path) == target:
                attempts.append(path)
                raise OSError("MODEL_UNLINK_FAILURE")
            return original_unlink(path, *args, **kwargs)
        self.install(H.os, "unlink", unlink)
        session = H._pg_new(self.validation_binding, "validation")
        state = H._pg_state(session)
        state["mode"], state["private"] = "export", (private, private.lstat())
        for name in ("evidence.tar.gz", H.ARTIFACT):
            H._pg_write(session, private / name, b"synthetic", 9)
        with self.assertRaisesRegex(OSError, "MODEL_UNLINK_FAILURE") as failed:
            H._pg_cleanup(session)
        H._pg_abort(session, failed.exception)
        self.assertEqual(attempts, [target])
        self.assertTrue(target.exists())
        self.assertIsNone(state["finish"])
        self.assertIs(state["failure"], failed.exception)

    def test_failure_direct_child_wait_is_once_and_clipped_to_saved_end(self):
        class RunningModel:
            def __init__(self):
                self.returncode, self.waits, self.signals = None, [], []
            def poll(self):
                return self.returncode
            def terminate(self):
                self.signals.append("terminate")
            def kill(self):
                self.signals.append("kill")
                self.returncode = -9
            def wait(self, timeout=None):
                self.waits.append(timeout)
                return self.returncode
        session = H._pg_new(self.validation_binding, "validation")
        process = RunningModel()
        resource = H._pg_keep(session, process, "process", "model", ("poll", "terminate", "kill", "wait"))
        state = H._pg_state(session)
        state["pending_process"] = resource
        self.local = 1058.0
        H._pg_abort(session, RuntimeError("model cancellation"))
        H._pg_abort(session, RuntimeError("not another attempt"))
        self.assertEqual(process.waits, [2.0])
        self.assertEqual(process.signals, ["terminate", "kill"])
        self.assertIsNone(H._PRODUCTIVE_RESOURCES[id(resource)]["close"])
        self.assertIsNone(state["finish"])

    def test_shared_legacy_gpg_wrapper_keeps_byte_interface_and_restrictions(self):
        result = self.validate()
        recipient = result.recipient
        prefix = H._gpg_command(recipient)
        for option in ("--no-options", "--no-autostart", "--no-auto-key-retrieve", "--no-auto-key-import",
                "--disable-dirmngr", "--no-default-keyring", "--no-random-seed-file"):
            self.assertIn(option, prefix)
        self.assertEqual(prefix[prefix.index("--pinentry-mode") + 1], "error")
        self.assertEqual(prefix[prefix.index("--auto-key-locate") + 1], "clear")
        output = H._gpg(recipient, ["--with-colons", "--with-fingerprint", "--with-subkey-fingerprint", "--list-keys"], 1060.0)
        self.assertEqual(output, (listing(), b""))
        self.assertIs(type(output), tuple)
        self.assertEqual(len(self.processes[-1].waits), 1)


if __name__ == "__main__":
    unittest.main(failfast=True)
