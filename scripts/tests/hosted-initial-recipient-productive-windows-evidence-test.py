#!/usr/bin/env python3
"""OFFLINE SYNTHETIC WINDOWS MODEL ONLY. No native/GPG/provider/hosted authority.

The actual Windows file-owner classes run over the existing in-memory WinAPI
model. A NEW modeled process scope owns modeled process/job handles. Synthetic
listings/packets are not cryptography. E is an explicitly registered fixture,
not PC/policy/bootstrap admission. Thirty SMALL synthetic partitions are NOT
the real fixed30 corpus or a capacity/timing qualification.

Only a new, bounded public PE-header fixture uses the local filesystem. It is
read, never executed. Its POSIX temporary path admission is explicitly modeled;
it does not qualify installed Windows GPG, ACLs, jobs, SDKs or application builds.
No old tests, original evidence, keys, binaries, downloads or CI are replayed.
Run only after the exact source/control freeze and independent review permit it.
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
import tempfile
from types import MappingProxyType, ModuleType
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location(
    "productive_windows_file_model", ROOT / "scripts/tests/hosted-windows-files-test.py")
MODEL = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODEL
SPEC.loader.exec_module(MODEL)  # Definitions/model only; never loads its unittest suite.
import hosted_windows_evidence as W

F, H, P = W.files, W.portable, W.processes
PRIMARY, ENCRYPTION, JOB = "1" * 40, "2" * 40, "5" * 32
NS = 10 ** 9
PUBLIC = (b"-----BEGIN PGP PUBLIC KEY BLOCK-----\n\n" + base64.b64encode(b"\xc6\x01x\xce\x01y") +
          b"\n-----END PGP PUBLIC KEY BLOCK-----\n")
POLICY = (json.dumps({"recipient": {"fingerprint": PRIMARY}}, sort_keys=True) + "\n").encode("ascii")
DISCARDED_SYNTHETIC_FIXTURES = []


def frozen(name, fields):
    return dataclasses.make_dataclass(name, [(field, object) for field in fields.split()], frozen=True)


ValidationCaps = frozen("ValidationCaps", "clock first firstLocal workEndNs workEndLocal "
                        "operationFinishEndNs operationFinishEndLocal finishReserveNs operationLimitNs")
ArchiveCaps = frozen("ArchiveCaps", "clock first firstLocal workEndNs workEndLocal "
                     "operationFinishEndNs operationFinishEndLocal finishReserveNs operationLimitNs")
ValidationView = frozen("ValidationView", "child role work public_key_raw policy_raw original_match_raw source caps")
ArchiveView = frozen("ArchiveView", "child archive recipient role payload output payload_root partitions index "
                     "lineage caps public_inputs")
Binding = frozen("Binding", "view")
Node = frozen("ExpectedNode", "relative kind bytes sha256 native provenance")
Partition = frozen("PartitionView", "ordinal group root members map")
Source = frozen("ChildSourceBinding", "job_id observed_raw event_sha256 context_sha256 start_sha256")
KeyringCap = frozen("KeyringCap", "first firstLocal workEndNs workEndLocal limitNs")


def native_vector(info):
    # Independent fixture projection: no production helper manufactures nodes.
    return ("windows", *info.identity, info.is_directory, info.size, info.links, info.attributes,
            info.creation_100ns, info.modified_100ns, info.change_100ns, info.owner_sid, info.protected_dacl)


def listing():
    def key(kind, capability):
        row = [""] * 12
        row[0], row[1], row[6], row[11] = kind, "-", "0", capability
        return ":".join(row)
    return ("\n".join((key("pub", "c"), "fpr:::::::::" + PRIMARY + ":",
                       key("sub", "e"), "fpr:::::::::" + ENCRYPTION + ":")) + "\n").encode("ascii")


def ciphertext(fingerprint=ENCRYPTION):
    recipient = b"\x03" + bytes.fromhex(fingerprint[-16:]) + b"\x12xy"
    protected = b"\x01" + b"SYNTHETIC-ONLY-NOT-CRYPTOGRAPHIC" * 2
    return b"\xc1" + bytes([len(recipient)]) + recipient + b"\xd2" + bytes([len(protected)]) + protected


class FileApi(MODEL.ModelApi):
    def __init__(self, fixture):
        super().__init__()
        self.fixture = fixture

    def read(self, handle, count):
        node = self.handles[handle][0]
        value = super().read(handle, count)
        return self.fixture.event("file-read", node.path, value)

    def close(self, handle):
        path = self.handles[handle][0].path
        super().close(handle)
        self.fixture.event("file-close", path, handle)

    def flush(self, handle):
        super().flush(handle)
        self.fixture.event("file-flush", self.handles[handle][0].path, handle)


class ProcessApi:
    """Separate in-memory process/job handle space; never calls a native API."""
    def __init__(self, fixture):
        self.fixture, self.handles, self.next_handle = fixture, {}, 1

    def allocate(self, kind):
        handle = self.next_handle
        self.next_handle += 1
        self.handles[handle] = kind
        self.fixture.events.append(("process-open", kind, handle))
        return handle

    def close(self, handle):
        if handle not in self.handles:
            raise RuntimeError("MODEL repeated process handle close")
        kind = self.handles.pop(handle)
        self.fixture.events.append(("process-close", kind, handle))
        self.fixture.event("process-close", kind, handle)


class Process:
    def __init__(self, api, handle, pid, stdout, stderr):
        self.api, self.handle, self.pid = api, handle, pid
        self.stdout, self.stderr, self.returncode = stdout, stderr, None

    def poll(self):
        self.api.fixture.event("process-poll", self, None)
        self.returncode = self.api.fixture.exit_code
        return self.returncode

    def wait(self, timeout=None):
        return self.poll()

    def close(self):
        if self.handle is not None:
            handle, self.handle = self.handle, None
            self.api.close(handle)


class Scope:
    active = None

    def __init__(self, job, invocation, state, home):
        fixture = Scope.active
        self.api = ProcessApi(fixture)
        self.job_id, self.invocation = job, invocation
        self.leaders, self.launches, self.known, self.discovery_errors = [], [], {}, set()
        self.job = self.api.allocate("job")
        fixture.scopes.append(self)
        try:
            fixture.event("scope-constructor", self, None)
        except BaseException as error:
            job, self.job = self.job, None
            try:
                self.api.close(job)
            except BaseException:
                error.add_note("MODEL scope constructor retirement UNKNOWN")
            raise

    def spawn(self, argv, cwd, env, *, stdout, stderr):
        fixture = self.api.fixture
        fixture.commands.append((argv, cwd, env))
        fixture.borrowed = (stdout, stderr)
        fixture.event("scope-spawn", self, None)
        process = Process(self.api, self.api.allocate("process"), 7000 + len(fixture.scopes), None, None)
        self.leaders.append(process)
        self.launches.append({"scope": "SYNTHETIC_NATIVE_PROCESS_MODEL_ONLY", "job": self.job_id,
                              "invocation": self.invocation, "argv": argv, "nativeAcceptance": False})
        if "--encrypt" in argv:
            fixture.plaintext = fixture.api.nodes[argv[-1]].content
            output, diagnostic = fixture.cipher, fixture.status
        elif "--version" in argv:
            output, diagnostic = fixture.version, b"SYNTHETIC-PRIVATE-DIAGNOSTIC\n"
        else:
            output, diagnostic = fixture.listing, b"SYNTHETIC-PRIVATE-DIAGNOSTIC\n"
        # Child duplicate semantics: do not use NativeFile.write as a surrogate.
        fixture.api.write(stdout.native_handle, output)
        fixture.api.write(stderr.native_handle, diagnostic)
        fixture.event("scope-spawn-return", self, process)
        return process

    def discover(self):
        return self.api.fixture.event("scope-discover", self, list(self.api.fixture.live))

    def _member_pids(self):
        return [item["pid"] for item in self.discover()]

    def signal_all(self, signum, *, deadline=None):
        self.api.fixture.event("scope-signal", self, deadline)

    def drain(self, grace=5.0, kill_wait=5.0, *, deadline=None):
        fixture = self.api.fixture
        if grace != 0 or kill_wait != 5 or (deadline is not None and
                                           (type(deadline) is not float or fixture.now >= deadline)):
            raise RuntimeError("MODEL original bounded drain differs")
        if any(stream.closed for stream in fixture.borrowed):
            raise RuntimeError("MODEL borrowed GPG sink closed before retirement")
        fixture.events.append(("drain", deadline))
        return fixture.event("scope-drain", self, list(fixture.remaining))

    def description(self):
        return {"backend": "SYNTHETIC_ONLY", "job": self.job_id, "invocation": self.invocation,
                "launches": self.launches, "discoveryErrors": sorted(self.discovery_errors)}

    def _retire(self, actions, **kwargs):
        failures = []
        for _label, action in actions:
            try:
                action()
            except BaseException as error:
                failures.append(error)
        if failures:
            failure = RuntimeError("MODEL native retirement UNKNOWN")
            raise failure from failures[0]

    def close(self):
        job, self.job = self.job, None
        actions = [("process", child.close) for child in self.leaders]
        if job is not None:
            actions.append(("job", lambda: self.api.close(job)))
        self._retire(actions)
        self.api.fixture.event("scope-close", self, None)


class Fixture:
    def __init__(self, case):
        self.case, self.now, self.wall = case, 100.0, 1800000000.0
        self.hook, self.effect_hook, self.raw_error = None, None, None
        self.events, self.scopes, self.commands = [], [], []
        self.borrowed, self.plaintext = (), None
        self.exit_code, self.live, self.remaining = 0, [], []
        self.version, self.listing = b"gpg (GnuPG) 2.4.9\nSYNTHETIC\n", listing()
        self.cipher = ciphertext()
        self.status = b"[GNUPG:] BEGIN_ENCRYPTION 2 9\n[GNUPG:] END_ENCRYPTION\n"
        self.guard_calls, self.keyring_begins, self.keyring_completions = 0, 0, 0
        self.local_calls = 0
        self.keyrings, self.bindings, self.nodes, self.payload_bytes = {}, {}, {}, {}
        self.patchers = []
        self.temp = tempfile.TemporaryDirectory(prefix="p2pkit-productive-windows-model-")
        self.executable = Path(self.temp.name) / "gpg.exe"
        pe = bytearray(128)
        pe[:2] = b"MZ"
        struct.pack_into("<I", pe, 60, 64)
        pe[64:68] = b"PE\0\0"
        struct.pack_into("<H", pe, 68, 0x8664)
        struct.pack_into("<H", pe, 88, 0x20B)
        self.executable.write_bytes(pe)
        self.executable_bytes = bytes(pe)
        original_parts = F.absolute_parts

        def admitted_parts(path):
            if path == str(self.executable):
                return "C:\\", ("MODEL_PUBLIC_PE_ONLY", "gpg.exe")
            return original_parts(path)

        def native_model():
            if W._QUARANTINE:
                raise H.EvidenceError("MODEL prior retirement UNKNOWN")

        def local_clock():
            self.local_calls += 1
            return self.now

        def wall_clock():
            return self.wall

        def installed(_name):
            return str(self.executable)

        self.e = self.make_e()
        self.replace(W, "_productive_e", lambda: self.e)
        self.replace(W, "_native", native_model)
        self.replace(F, "absolute_parts", admitted_parts)
        self.replace(W.time, "monotonic", local_clock)
        self.replace(W.time, "time", wall_clock)
        self.replace(W.shutil, "which", installed)
        self.replace(P, "WindowsScope", Scope)
        self.replace(P, "WindowsProcess", Process)
        Scope.active = self
        # Each testcase is a NEW isolated synthetic interpreter-state fixture.
        # No failed session is reset/reused to obtain a later PASS.
        for name in ("_QUARANTINE", "_PRODUCTIVE_SESSIONS", "_PRODUCTIVE_RESULTS", "_PRODUCTIVE_ARTIFACTS",
                     "_PRODUCTIVE_CLOSES", "_PRODUCTIVE_PINS", "_PRODUCTIVE_APIS", "_PRODUCTIVE_SESSION_PINS",
                     "_PRODUCTIVE_ROWS", "_PRODUCTIVE_ADAPTERS", "_PRODUCTIVE_COMMANDS", "_PRODUCTIVE_COMMAND_PINS"):
            self.replace(W, name, [] if name == "_QUARANTINE" else {})
        environment = patch.dict(os.environ, {"SYSTEMROOT": "C:\\Windows"}, clear=True)
        environment.start()
        self.patchers.append(environment)
        self.api = FileApi(self)
        self.work = F._root(r"C:\work\crypto", self.api, create=True)
        self.payload = F._root(r"C:\work\payload", self.api, create=True)
        self.output = F._root(r"C:\work\output", self.api, create=True)
        self.roots = (self.work, self.payload, self.output)
        self.child, self.clock = object(), object()
        self.source = Source(JOB, b"SYNTHETIC_ONLY", "6" * 64, "7" * 64, "8" * 64)
        caps = self.caps(True)
        view = ValidationView(self.child, "windows-x64", self.work, PUBLIC, POLICY, b"SYNTHETIC_ONLY",
                              self.source, caps)
        self.validation_binding = self.bind(view, True)
        self.validation_result = self.export_binding = None

    def replace(self, owner, name, value):
        item = patch.object(owner, name, value)
        item.start()
        self.patchers.append(item)

    def event(self, name, owner, value):
        if self.effect_hook is not None:
            return self.effect_hook(name, owner, value)
        return value

    def dispose(self):
        # Failure fixtures intentionally preserve their unclosed ORIGINAL model
        # resources. No deadline retiming, ambiguous raw-close retry or registry
        # reset is used as a success assertion. They are only in-memory objects.
        self.hook = self.effect_hook = None
        self.retained_states = tuple(W._PRODUCTIVE_SESSION_PINS.values())
        DISCARDED_SYNTHETIC_FIXTURES.append(self)
        for item in reversed(self.patchers):
            item.stop()
        self.temp.cleanup()  # Only the new 128-byte public model PE; never evidence.

    def caps(self, validation):
        limit = 60 if validation else 240
        finish, work = self.now + limit, self.now + limit - 30
        kind = ValidationCaps if validation else ArchiveCaps
        return kind(self.clock, object(), self.now, int(work * NS), work,
                    int(finish * NS), finish, 30 * NS, limit * NS)

    def bind(self, view, validation):
        binding = Binding(view)
        self.bindings[id(binding)] = (binding, view, validation)
        return binding

    def checked(self, binding, *, validation=None):
        record = self.bindings.get(id(binding))
        if record is None or record[0] is not binding or binding.view is not record[1]:
            raise H.EvidenceError("MODEL nonregistered/changed E binding")
        if validation is not None and record[2] is not validation:
            raise H.EvidenceError("MODEL E binding route differs")
        return record[1]

    def callback(self, name, binding):
        self.guard_calls += 1
        if self.hook is not None:
            self.hook(name, binding)
        if self.raw_error is not None:
            raise self.raw_error  # Synthetic RAW denial, not an original provider clock.

    def make_e(self):
        e = ModuleType("SYNTHETIC_REGISTERED_E_NOT_PC_OR_HOSTED_AUTHORITY")

        def checked_validation(binding):
            view = self.checked(binding, validation=True)
            self.callback("validation-binding", binding)
            return view

        def checked_export(binding):
            view = self.checked(binding, validation=False)
            self.callback("export-binding", binding)
            return view

        def work(binding):
            view = self.checked(binding)
            self.callback("work", binding)
            if not view.caps.firstLocal <= self.now < view.caps.workEndLocal:
                raise H.EvidenceError("MODEL original work bound expired")
            return view.caps

        def finish(binding):
            view = self.checked(binding)
            self.callback("finish", binding)
            if not view.caps.firstLocal <= self.now < view.caps.operationFinishEndLocal:
                raise H.EvidenceError("MODEL original finish bound expired")
            return view.caps

        def whole(binding):
            view = self.checked(binding)
            self.callback("whole", binding)
            return view.caps

        def node(binding, relative):
            self.checked(binding, validation=False)
            self.callback("expected-node", binding)
            return self.nodes[relative]

        def node_guard(binding, original):
            self.checked(binding, validation=False)
            self.callback("node", binding)
            if self.nodes.get(original.relative) is not original:
                raise H.EvidenceError("MODEL node is not original")
            return original

        def snapshot(binding, entries):
            self.checked(binding, validation=False)
            self.callback("snapshot", binding)
            if type(entries) is not MappingProxyType or set(entries) != set(self.nodes):
                raise H.EvidenceError("MODEL same owned Windows snapshot roster differs")
            if any(native_vector(info) != self.nodes[name].native for name, info in entries.items()):
                raise H.EvidenceError("MODEL full native snapshot vector differs")
            return entries

        def manifest(binding, digest, size):
            self.checked(binding, validation=False)
            self.callback("manifest", binding)
            return (json.dumps({"scope": "SYNTHETIC_CANONICAL_FORMAT_ONLY", "artifact": {
                "name": H.ARTIFACT, "sha256": digest, "size": size}}, sort_keys=True,
                separators=(",", ":")) + "\n").encode("ascii")

        def begin(binding):
            view = self.checked(binding, validation=False)
            if id(binding) in self.keyrings:
                raise H.EvidenceError("MODEL keyring begins once")
            self.callback("keyring-begin", binding)
            end = min(self.now + 30, view.caps.workEndLocal)
            cap = KeyringCap(object(), self.now, int(end * NS), end, 30 * NS)
            self.keyrings[id(binding)] = [cap, False]
            self.keyring_begins += 1
            return cap

        def keyring(binding, cap):
            self.checked(binding, validation=False)
            original, done = self.keyrings[id(binding)]
            if cap is not original or done or self.now >= cap.workEndLocal:
                raise H.EvidenceError("MODEL keyring original cap expired/completed")
            self.callback("keyring-guard", binding)
            return cap

        def complete(binding, cap):
            keyring(binding, cap)
            session = W._PRODUCTIVE_SESSIONS[id(binding)]
            rows = [row for row in session.resources if row["deadline"] == cap.workEndLocal]
            self.case.assertTrue(rows, "No actual modeled refresh resources were retained")
            self.case.assertTrue(all(row["closed"] and row["observed_return"] and
                                     row["completion"] < cap.workEndLocal for row in rows))
            self.keyrings[id(binding)][1] = True
            self.keyring_completions += 1
            self.callback("keyring-complete", binding)
            return cap

        for name, function in (("_checked_productive_validation_binding", checked_validation),
            ("_checked_productive_export_binding", checked_export), ("_productive_work_guard", work),
            ("_productive_finish_guard", finish), ("_productive_whole_guard", whole),
            ("_productive_expected_node", node), ("_productive_node_guard", node_guard),
            ("_productive_check_snapshot", snapshot), ("_productive_manifest", manifest),
            ("_productive_keyring_begin", begin), ("_productive_keyring_guard", keyring),
            ("_productive_keyring_complete", complete)):
            setattr(e, name, function)  # Plain fixed function slots, never rebound methods.
        return e

    def put(self, root, relative, raw):
        with root.create_file(relative, max_bytes=len(raw), deadline=self.now + 10) as stream:
            stream.write(raw)
        return str(root.path) + "\\" + relative.replace("/", "\\")

    def validate(self):
        self.validation_result = W._validate_initial_productive(self.validation_binding)
        return self.validation_result

    def prepare_archive(self, *, padding_callback=False):
        recipient = (self.validation_result or self.validate()).recipient
        # Exact30 SMALL fixture partitions only, not PC's real literal topology.
        for ordinal in range(30):
            group = f"synthetic-{ordinal:02d}"
            with self.payload.create_directory(group, deadline=self.now + 10):
                pass
            raw = (f"SYNTHETIC GROUP {ordinal}\n").encode("ascii") + b"\0\xff"
            self.payload_bytes[group + "/data.bin"] = raw
            self.payload_bytes[group + ".map.json"] = (b'{"scope":"SYNTHETIC_MAP","ordinal":' +
                                                         str(ordinal).encode("ascii") + b"}\n")
        self.payload_bytes["index.json"] = b'{"scope":"SYNTHETIC_POST_CLOSE_INDEX"}\n'
        if padding_callback:
            # Forty-six extra tar data blocks give 101888 = 9*10240+9728 bytes.
            # Original close adds 1024 zeros, forcing chunk 10. The original
            # 32768-byte gzip buffer flushes at writes 4/7/10, so its raw-writer
            # callback occurs DURING TarFile.close, even for empty compressed
            # output. Unbuffered gzip calls the sink there too. No forced flush
            # or buffer substitution is used.
            self.payload_bytes["index.json"] = (b'{"scope":"SYNTHETIC_POST_CLOSE_INDEX","padding":"' +
                                                b"x" * 23552 + b'"}\n')
        for relative, raw in self.payload_bytes.items():
            self.put(self.payload, relative, raw)
        with self.payload.snapshot(max_bytes=H.MAX_BYTES, max_members=H.MAX_MEMBERS,
                                   deadline=self.now + 10) as snapshot:
            for relative, info in snapshot.entries.items():
                raw = self.payload_bytes.get(relative)
                self.nodes[relative] = Node(relative, "directory" if info.is_directory else "file",
                    None if info.is_directory else len(raw), None if info.is_directory else hashlib.sha256(raw).hexdigest(),
                    native_vector(info), object())
        parts = tuple(Partition(i, f"synthetic-{i:02d}", self.nodes[f"synthetic-{i:02d}"],
                                (self.nodes[f"synthetic-{i:02d}/data.bin"],),
                                self.nodes[f"synthetic-{i:02d}.map.json"]) for i in range(30))
        view = ArchiveView(self.child, object(), recipient, "windows-x64", self.payload, self.output,
                           self.nodes[""], parts, self.nodes["index.json"], object(), self.caps(False),
                           b'{"scope":"SYNTHETIC_PUBLIC_INPUTS_NOT_AUTHORITY"}\n')
        self.export_binding = self.bind(view, False)
        return self.export_binding

    def export(self):
        return W._export_initial_productive(self.export_binding or self.prepare_archive())

    def session(self):
        return W._ProductiveSession(self.validation_binding, True)

    def archive_reader(self):
        binding = self.prepare_archive()
        session = W._ProductiveSession(binding, False)
        node = self.nodes["synthetic-00/data.bin"]
        stream = session.create("test-original-member", self.payload, "open_file", node.relative,
                                max_bytes=node.bytes, deadline=session.end())
        return session, W._ProductiveReader(session, stream, node)

    def record_nodes(self):
        return [(path, node) for path, node in self.api.nodes.items() if "-result-" in path and path.endswith(".json")]


class ProductiveWindowsControls(unittest.TestCase):
    def setUp(self):
        self.f = Fixture(self)
        self.addCleanup(self.f.dispose)

    def assert_sticky(self, session, original=None):
        first = W._PRODUCTIVE_SESSION_PINS[id(session)]["first"]
        self.assertIsNotNone(first)
        if original is not None:
            self.assertIs(first, original)
        with self.assertRaises(BaseException):
            W._session_check(session)
        self.assertIs(W._PRODUCTIVE_SESSION_PINS[id(session)]["first"], first)
        self.assertIsNone(session.result)

    def lookup_scopes(self):
        """Direct lookup model, not a GPG command or native admission.

        Use original model objects and the real child-pin adoption/close
        mechanisms. No close flag or actual-close receipt is fabricated.
        """
        session, rows = self.f.session(), []
        for ordinal in (1, 2):
            scope = Scope(JOB, f"{ordinal:032x}", "MODEL_STATE", "MODEL_HOME")
            session.hold(f"lookup-scope-{ordinal}", scope)
            process = Process(scope.api, scope.api.allocate("process"), 8000 + ordinal, None, None)
            scope.leaders.append(process)
            row = session._owners[id(scope)]
            W._ObjectPin.adopt_process(row["pin"], process)
            W._ObjectPin.check(row["pin"])
            rows.append((scope, process, row))
        W._session_close(session, rows[0][0])
        W._session_check(session)
        retired = rows[0][2]
        self.assertTrue(retired["attempted"] and retired["closed"] and retired["observed_return"])
        self.assertIs(W._PRODUCTIVE_ROWS[id(retired)]["actual_close"][0], rows[0][0])
        self.assertFalse(rows[0][0].api.handles)
        self.assertIsNone(rows[0][1].handle)
        return session, rows

    def test_process_lookup_selects_later_live_scope_behind_retired_original(self):
        session, rows = self.lookup_scopes()
        original_receipt = W._PRODUCTIVE_ROWS[id(rows[0][2])]["actual_close"]
        pin, row = session.pin_for(rows[1][1])
        self.assertIs(row, rows[1][2])
        self.assertIs(pin, row["pin"].children[0])
        self.assertIs(pin.owner, rows[1][1])
        self.assertEqual(len(session.resources), 2)
        self.assertIs(session.resources[0], rows[0][2])
        self.assertIs(W._PRODUCTIVE_ROWS[id(rows[0][2])]["actual_close"], original_receipt)
        W._session_close(session, rows[1][0])
        W._session_check(session)
        self.assertFalse(rows[1][0].api.handles)

    def test_process_lookup_cannot_select_the_retired_original_child(self):
        session, rows = self.lookup_scopes()
        with self.assertRaisesRegex(H.EvidenceError, "Productive process scope is not live"):
            session.pin_for(rows[0][1])

    def test_process_lookup_cannot_select_current_quarantined_scope(self):
        session, rows = self.lookup_scopes()
        session.quarantine((rows[1][0],))
        self.assertTrue(rows[1][2]["quarantined"] and session.unknown)
        with self.assertRaisesRegex(H.EvidenceError, "Productive process scope is not live"):
            session.pin_for(rows[1][1])

    def test_process_lookup_still_validates_unrelated_retired_row(self):
        session, rows = self.lookup_scopes()
        rows[0][2]["closed"] = False  # Invalid mutation, not a modeled close.
        with self.assertRaisesRegex(H.EvidenceError, "Productive original resource row field changed"):
            session.pin_for(rows[1][1])

    def test_process_lookup_still_pins_selected_original_child(self):
        session, rows = self.lookup_scopes()
        rows[1][1].handle += 10000  # Invalid mutation, not a native handle return.
        with self.assertRaisesRegex(H.EvidenceError, "Productive original process handle changed"):
            session.pin_for(rows[1][1])

    def test_process_lookup_rejects_unowned_equal_process_fields(self):
        session, rows = self.lookup_scopes()
        original = rows[1][1]
        lookalike = Process(original.api, original.handle, original.pid, original.stdout, original.stderr)
        with self.assertRaisesRegex(H.EvidenceError, "Productive operation on an unowned native resource"):
            session.pin_for(lookalike)

    def test_actual_validation_returns_retained_native_public_and_result_closes(self):
        result = self.f.validate()
        self.assertIs(W._checked_productive_validation_return(result, self.f.validation_binding), result)
        self.assertEqual(result.recipient.encryption_fingerprint, ENCRYPTION)
        self.assertEqual(result.recipient.executable_sha256, hashlib.sha256(self.f.executable_bytes).hexdigest())
        self.assertEqual(len(self.f.commands), 3)
        self.assertTrue(all(scope.job is None and not scope.api.handles for scope in self.f.scopes))
        self.assertTrue(all(row["closed"] and row["observed_return"] and row["completion"] < row["deadline"]
                            for row in result.known_close.resources))
        public = [row for row in result.session.resources if row["pin"].category == "public-file"]
        self.assertTrue(public)
        self.assertTrue(all(row["owner"].closed and row["pin"].children[0].owner.closed for row in public))
        receipt = result.known_close.receipt
        self.assertIsNot(receipt[2], receipt[3])
        self.assertTrue(receipt[2].closed and receipt[3].closed)
        record = json.loads(receipt[1])
        self.assertEqual(record["result"], "PENDING_RESULT_WRITER_READBACK_AND_FUNCTION_RETURN")
        self.assertEqual(record["ownWriterClose"], "PENDING")
        self.assertEqual(record["ownReadback"], "NOT_STARTED")
        self.assertEqual(record["outerOwnerClose"], "PENDING")
        self.assertEqual(len(self.f.record_nodes()), 1)

    def test_actual_tar_bytes_maps_index_and_ciphertext_public_readback_join(self):
        result = self.f.export()
        self.assertIs(W._checked_productive_export_return(result, self.f.export_binding), result)
        self.assertEqual(result.artifact.sha256, hashlib.sha256(self.f.cipher).hexdigest())
        self.assertEqual(result.artifact.size, len(self.f.cipher))
        with tarfile.open(fileobj=io.BytesIO(self.f.plaintext), mode="r:gz") as archive:
            self.assertEqual({member.name.removeprefix("evidence/") for member in archive if member.isfile()},
                             set(self.f.payload_bytes))
            for relative, raw in self.f.payload_bytes.items():
                self.assertEqual(archive.extractfile("evidence/" + relative).read(), raw)
        readers = [adapter for adapter in W._PRODUCTIVE_SESSION_PINS[id(result.session)]["adapters"]
                   if type(adapter) is W._ProductiveReader and adapter.node is not None]
        self.assertEqual(len(readers), len(self.f.payload_bytes))
        self.assertTrue(all(reader.done and reader.stream.closed and reader.count == reader.node.bytes and
                            reader.digest.hexdigest() == reader.node.sha256 for reader in readers))
        self.assertEqual(self.f.keyring_begins, 1)
        self.assertEqual(self.f.keyring_completions, 1)
        self.assertEqual(len(self.f.record_nodes()), 2)
        rows = {row["label"]: row for row in result.session.resources if
                row["label"] in ("plaintext-tar", "plaintext-tar-stream", "plaintext-gzip")}
        archive, stream = rows["plaintext-tar"]["owner"], rows["plaintext-tar-stream"]["owner"]
        self.assertIs(archive.fileobj, stream)
        self.assertIs(stream.fileobj, rows["plaintext-gzip"]["owner"])
        self.assertTrue(archive._extfileobj and stream._extfileobj)
        self.assertEqual(stream.buf, b"")
        state = W._PRODUCTIVE_SESSION_PINS[id(result.session)]
        self.assertIs(state["tar_stream_return"], state["tar_stream_transfer"])
        self.assertEqual(sum(owner is archive for _label, owner in state["factory_returns"]), 1)
        self.assertFalse(any(owner is stream for _label, owner in state["factory_returns"]))
        for label in ("plaintext-tar", "plaintext-tar-stream", "plaintext-gzip"):
            row = rows[label]
            self.assertEqual(row["coverage"], "DIRECT")
            self.assertTrue(row["attempted"] and row["closed"] and row["observed_return"])
            actual = W._PRODUCTIVE_ROWS[id(row)]["actual_close"]
            self.assertIs(actual[0], row["owner"])
            self.assertIs(actual[1], dict(row["pin"].methods)["close"])
            self.assertIsNone(actual[2])
        prefix = str(self.f.output.path) + "\\"
        self.assertEqual({path[len(prefix):] for path in self.f.api.nodes if path.startswith(prefix)},
                         {H.ARTIFACT, H.MANIFEST})

    def test_passive_checker_after_real_model_borrowed_root_closes_has_no_callbacks(self):
        result = self.f.validate()
        self.f.work.close()  # Actual model outer close, not fabricated backend currency.
        callbacks, clocks, native_events = self.f.guard_calls, self.f.local_calls, tuple(self.f.api.events)
        self.f.now = result.session.caps.operationFinishEndLocal + 1000
        self.f.raw_error = AssertionError("PASSIVE checker called fake E/clock")
        self.assertIs(W._checked_productive_validation_return(result, self.f.validation_binding), result)
        self.assertEqual((self.f.guard_calls, self.f.local_calls, tuple(self.f.api.events)),
                         (callbacks, clocks, native_events))

    def test_shared_ancestor_release_is_contribution_not_early_raw_close(self):
        result = self.f.validate()
        root_pin = result.session.borrowed_pins[0]
        self.assertFalse(self.f.work._closed)
        self.assertTrue(all(cell.references > 0 and cell.handle in self.f.api.handles for cell in root_pin.pin_slots))
        record = json.loads(result.known_close.receipt[1])
        accounting = record["priorResourceAccounting"]
        self.assertGreater(accounting["originalPinReleaseContributions"], accounting["uniqueOriginalPinReferences"])
        self.assertEqual(accounting["pinReleaseMeaning"], "OWNER_CONTRIBUTION_NOT_EARLY_BORROWED_RAW_HANDLE_CLOSE")
        self.assertEqual(accounting["timingCapacityQualification"], "NOT_PERFORMED")

    def test_equal_unregistered_binding_is_not_authority(self):
        binding = dataclasses.replace(self.f.validation_binding)
        with self.assertRaises(H.EvidenceError):
            W._validate_initial_productive(binding)
        self.assertFalse(self.f.scopes)
        self.assertFalse(self.f.record_nodes())

    def test_equal_unregistered_result_is_not_currency(self):
        original = self.f.validate()
        with self.assertRaises(H.EvidenceError):
            W._checked_productive_validation_return(dataclasses.replace(original), self.f.validation_binding)
        self.assertIs(W._checked_productive_validation_return(original, self.f.validation_binding), original)

    def test_wrong_original_binding_poisons_retained_result(self):
        result = self.f.validate()
        with self.assertRaises(H.EvidenceError):
            W._checked_productive_validation_return(result, dataclasses.replace(self.f.validation_binding))
        with self.assertRaises(H.EvidenceError):
            W._checked_productive_validation_return(result, self.f.validation_binding)

    def test_duplicate_begin_poisons_original_even_if_caught(self):
        session = self.f.session()
        with self.assertRaises(H.EvidenceError):
            W._ProductiveSession(self.f.validation_binding, True)
        self.assert_sticky(session)

    def test_caught_E_reentry_cannot_resume_original(self):
        session = self.f.session()
        def hook(_name, binding):
            self.f.hook = None
            try:
                W._validate_initial_productive(binding)
            except H.EvidenceError:
                pass
        self.f.hook = hook
        with self.assertRaises(H.EvidenceError):
            W._session_guard(session)
        self.assert_sticky(session)

    def test_caught_early_finish_cannot_be_retried(self):
        session = self.f.session()
        with self.assertRaises(H.EvidenceError):
            W._finish_initial_productive(session, self.f.validation_binding)
        self.assert_sticky(session)
        self.assertFalse(self.f.record_nodes())

    def test_duplicate_actual_finish_never_creates_a_second_record(self):
        result = self.f.validate()
        before = tuple(self.f.record_nodes())
        with self.assertRaises(H.EvidenceError):
            W._finish_initial_productive(result.session, self.f.validation_binding)
        self.assertEqual(tuple(self.f.record_nodes()), before)
        with self.assertRaises(H.EvidenceError):
            W._checked_productive_validation_return(result, self.f.validation_binding)

    def test_foreign_pid_result_refuses_without_clock_sampling(self):
        result = self.f.validate()
        before = self.f.guard_calls
        object.__setattr__(result.session, "pid", result.session.pid + 1)
        with self.assertRaises(H.EvidenceError):
            W._checked_productive_validation_return(result, self.f.validation_binding)
        self.assertEqual(self.f.guard_calls, before)

    def test_mutated_result_fields_cannot_be_restored_for_acceptance(self):
        result = self.f.validate()
        old = result.known_close
        object.__setattr__(result, "known_close", dataclasses.replace(old))
        with self.assertRaises(H.EvidenceError):
            W._checked_productive_validation_return(result, self.f.validation_binding)
        object.__setattr__(result, "known_close", old)
        with self.assertRaises(H.EvidenceError):
            W._checked_productive_validation_return(result, self.f.validation_binding)

    def test_same_caps_fields_replacement_and_sticky_restore(self):
        session = self.f.session()
        original = session.caps
        object.__setattr__(session.view, "caps", dataclasses.replace(original))
        with self.assertRaises(H.EvidenceError):
            W._session_guard(session)
        object.__setattr__(session.view, "caps", original)
        self.assert_sticky(session)

    def test_local_backward_sample_refuses_without_new_basis(self):
        session = self.f.session()
        self.f.now += 1
        W._session_guard(session)
        self.f.now -= 0.5  # Still above first, but below the actual previous sample.
        with self.assertRaises(H.EvidenceError):
            W._session_guard(session)
        self.assert_sticky(session)

    def test_modeled_RAW_refusal_preserves_original_error(self):
        session = self.f.session()
        error = RuntimeError("SYNTHETIC RAW denial; no provider identity")
        self.f.raw_error = error
        with self.assertRaises(RuntimeError) as caught:
            W._session_guard(session)
        self.assertIs(caught.exception, error)
        self.f.raw_error = None
        self.assert_sticky(session, error)

    def test_original_native_close_late_before_finish_is_not_accepted(self):
        session = self.f.session()
        stream = session.create("timed-native", self.f.work, "create_file", "timed.bin",
                                max_bytes=1, deadline=session.end())
        session.call(stream, "write", b"x")
        original_end = stream._deadline
        self.f.now = original_end + 1
        self.assertLess(self.f.now, session.caps.operationFinishEndLocal)
        W._session_close(session, stream)
        self.assertEqual(stream._deadline, original_end)
        self.assertTrue(session.unknown)
        self.assert_sticky(session)
        self.assertFalse(self.f.record_nodes())

    def test_finish_expiry_does_not_start_or_retry_result_io(self):
        session = self.f.session()
        W._productive_close_ordinary(session)
        self.f.now = session.caps.operationFinishEndLocal
        with self.assertRaises(H.EvidenceError):
            W._finish_initial_productive(session, self.f.validation_binding)
        self.assertFalse(self.f.record_nodes())
        self.assert_sticky(session)

    def test_spent_keyring_expiry_is_not_renewed_or_reapplied(self):
        self.f.prepare_archive()
        def hook(name, _binding):
            if name == "keyring-complete":
                self.f.hook = None
                self.f.now += 31
        self.f.hook = hook
        result = self.f.export()
        self.assertIs(W._checked_productive_export_return(result, self.f.export_binding), result)
        self.assertEqual((self.f.keyring_begins, self.f.keyring_completions), (1, 1))
        cap = result.session.keyring_return
        self.assertLess(cap.workEndLocal, self.f.now)
        self.assertIsNone(result.session.keyring_cap)

    def test_keyring_original_close_deadline_is_not_finish_cap(self):
        self.f.prepare_archive()
        def event(name, owner, value):
            if name == "scope-close" and self.f.export_binding is not None:
                session = W._PRODUCTIVE_SESSIONS.get(id(self.f.export_binding))
                if session is not None and session.keyring_cap is not None:
                    self.f.now = session.keyring_cap.workEndLocal
            return value
        self.f.effect_hook = event
        with self.assertRaises(W.WindowsEvidenceError):
            self.f.export()
        self.assertEqual(self.f.keyring_begins, 1)
        self.assertEqual(self.f.keyring_completions, 0)
        self.assertEqual(len(self.f.record_nodes()), 1)  # Prior actual validation only.

    def test_original_constructor_slot_is_pinned_before_first_E_callback(self):
        original = Scope.__init__
        called = []
        def replacement(*_args, **_kwargs):
            called.append("FORGED")
        def hook(_name, _binding):
            self.f.hook = None
            Scope.__init__ = replacement
        self.f.hook = hook
        try:
            with self.assertRaises(H.EvidenceError):
                self.f.validate()
        finally:
            Scope.__init__ = original
        self.assertFalse(called)
        self.assertFalse(self.f.scopes)

    def test_original_failure_dispatch_survives_callback_method_shadow(self):
        session = self.f.session()
        error = RuntimeError("SYNTHETIC callback failure")
        swallowed = []
        def hook(_name, _binding):
            self.f.hook = None
            session.capture = lambda *_args, **_kwargs: swallowed.append(True)
            raise error
        self.f.hook = hook
        with self.assertRaises(RuntimeError) as caught:
            W._session_guard(session)
        self.assertIs(caught.exception, error)
        del session.capture
        self.assertFalse(swallowed)
        self.assert_sticky(session, error)

    def test_callback_shadowed_check_and_guard_cannot_skip_original_pin_check(self):
        session = self.f.session()
        def hook(_name, _binding):
            self.f.hook = None
            session.check = lambda: None
            session.guard = lambda **_kwargs: self.f.now
        self.f.hook = hook
        with self.assertRaises(H.EvidenceError):
            W._session_guard(session)
        del session.check
        del session.guard
        self.assert_sticky(session)

    def test_resources_and_slots_cannot_be_replaced_together(self):
        session = self.f.session()
        owner = session.create("original-row", self.f.work, "create_directory", "row", deadline=session.end())
        row = session.resources[0]
        replacement = dict(row)
        session.resources[0] = session._slots[0] = replacement
        with self.assertRaises(H.EvidenceError):
            W._session_guard(session, whole=True)
        session.resources[0] = session._slots[0] = row
        self.assertIs(row["owner"], owner)
        self.assert_sticky(session)

    def test_resource_closed_flag_is_not_actual_close_currency(self):
        session = self.f.session()
        stream = session.create("early-flag", self.f.work, "create_file", "early.bin",
                                max_bytes=1, deadline=session.end())
        row = session._owners[id(stream)]
        row["closed"] = row["observed_return"] = True
        with self.assertRaises(H.EvidenceError):
            W._productive_close_ordinary(session)
        self.assertIsNone(W._PRODUCTIVE_ROWS[id(row)]["actual_close"])
        self.assertFalse(stream.closed)

    def test_snapshot_early_closed_flag_cannot_fake_nested_returns(self):
        self.f.put(self.f.work, "data.bin", b"x")
        session = self.f.session()
        snapshot = session.create("snapshot", self.f.work, "snapshot", max_bytes=1, max_members=2,
                                  deadline=session.end())
        original = snapshot._files["data.bin"]
        snapshot._closed = True
        W._session_close(session, snapshot)
        row = session._owners[id(snapshot)]
        self.assertFalse(row["closed"])
        self.assertFalse(original.closed)
        self.assertTrue(session.unknown)
        self.assert_sticky(session)

    def test_snapshot_aggregate_failure_never_becomes_transitive_success(self):
        self.f.put(self.f.work, "data.bin", b"x")
        session = self.f.session()
        snapshot = session.create("snapshot", self.f.work, "snapshot", max_bytes=1, max_members=2,
                                  deadline=session.end())
        stream = snapshot._files["data.bin"]
        handle = stream.native_handle
        self.f.api.close_failure = handle
        W._session_close(session, snapshot)
        row = session._owners[id(snapshot)]
        self.assertTrue(snapshot._closed and stream.closed)
        self.assertFalse(row["closed"])
        self.assertIsNone(W._PRODUCTIVE_ROWS[id(row)]["actual_close"])
        closes = [event for event in self.f.api.events if event[:2] == ("close", handle)]
        self.assertEqual(len(closes), 1)
        W._session_close(session, snapshot)
        self.assertEqual(len([event for event in self.f.api.events if event[:2] == ("close", handle)]), 1)
        self.assertTrue(session.unknown)

    def test_nested_native_pin_substitution_is_not_rebased_at_close(self):
        session = self.f.session()
        stream = session.create("native-pin", self.f.work, "create_file", "pin.bin",
                                max_bytes=1, deadline=session.end())
        originals = list(stream._pins)
        stream._pins[0] = self.f.output._pins[0]
        with self.assertRaises(H.EvidenceError):
            session.call(stream, "write", b"x")
        stream._pins[:] = originals
        self.assert_sticky(session)

    def test_scope_return_before_post_constructor_guard_failure_is_not_lost(self):
        error = RuntimeError("SYNTHETIC post-constructor guard failure")
        def event(name, _owner, value):
            if name == "scope-constructor":
                def hook(_name, _binding):
                    self.f.hook = None
                    raise error
                self.f.hook = hook
            return value
        self.f.effect_hook = event
        with self.assertRaises(W.WindowsEvidenceError) as caught:
            self.f.validate()
        self.assertIs(caught.exception.original, error)
        self.assertTrue(caught.exception.retirement_unknown)
        self.assertEqual(len(self.f.scopes), 1)
        scope = self.f.scopes[0]
        self.assertIsNone(scope.job)
        self.assertFalse(scope.api.handles)
        session = W._PRODUCTIVE_SESSIONS[id(self.f.validation_binding)]
        rows = [row for row in session.resources if row["label"] in ("gpg-stdout", "gpg-stderr-status")]
        self.assertTrue(rows)
        self.assertTrue(all(row["quarantined"] and not row["owner"].closed for row in rows))
        self.assertFalse(self.f.record_nodes())

    def test_spawn_return_error_retains_actual_process_and_unknown_sinks(self):
        error = RuntimeError("SYNTHETIC late spawn failure")
        def event(name, _owner, value):
            if name == "scope-spawn-return":
                raise error
            return value
        self.f.effect_hook = event
        with self.assertRaises(W.WindowsEvidenceError) as caught:
            self.f.validate()
        self.assertIs(caught.exception.original, error)
        self.assertTrue(caught.exception.retirement_unknown)
        self.assertEqual(len(self.f.scopes[0].leaders), 1)
        self.assertIsNone(self.f.scopes[0].leaders[0].handle)
        self.assertTrue(all(not stream.closed for stream in self.f.borrowed))

    def test_natural_nonzero_exit_cannot_be_relabelled_success(self):
        self.f.exit_code = 7
        with self.assertRaises(W.WindowsEvidenceError):
            self.f.validate()
        self.assertFalse(self.f.record_nodes())
        session = W._PRODUCTIVE_SESSIONS[id(self.f.validation_binding)]
        self.assertEqual(session.commands[0]["waitExitCode"], 7)

    def test_live_descendant_even_with_exit_zero_is_not_acceptance(self):
        self.f.live = [{"pid": 123, "scope": "SYNTHETIC_LIVE_MEMBER"}]
        with self.assertRaises(W.WindowsEvidenceError):
            self.f.validate()
        self.assertFalse(self.f.record_nodes())

    def test_ambiguous_original_scope_close_preserves_unknown(self):
        error = RuntimeError("SYNTHETIC ambiguous native scope close")
        def event(name, _owner, value):
            if name == "scope-close":
                raise error
            return value
        self.f.effect_hook = event
        with self.assertRaises(W.WindowsEvidenceError) as caught:
            self.f.validate()
        self.assertTrue(caught.exception.retirement_unknown)
        self.assertIs(caught.exception.original, error)
        self.assertFalse(self.f.record_nodes())

    def test_cancellation_preserves_same_object_not_generic_exception(self):
        cancellation = KeyboardInterrupt("SYNTHETIC cancellation")
        def event(name, _owner, value):
            if name == "process-poll":
                raise cancellation
            return value
        self.f.effect_hook = event
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.f.validate()
        self.assertIs(caught.exception, cancellation)
        self.assertFalse(self.f.record_nodes())

    def test_natural_returncode_callback_mutation_is_not_adopted(self):
        def hook(_name, binding):
            session = W._PRODUCTIVE_SESSIONS[id(binding)]
            scopes = [row["owner"] for row in session.resources if type(row["owner"]) is Scope]
            if scopes and scopes[-1].leaders:
                self.f.hook = None
                scopes[-1].leaders[0].returncode = 0
        self.f.hook = hook
        with self.assertRaises(W.WindowsEvidenceError):
            self.f.validate()
        self.assertFalse(self.f.record_nodes())

    def test_argv_callback_mutation_is_not_adopted_before_spawn(self):
        def hook(_name, binding):
            session = W._PRODUCTIVE_SESSIONS[id(binding)]
            if session.commands:
                self.f.hook = None
                session.commands[-1]["argv"].append("--forged-extra-option")
        self.f.hook = hook
        with self.assertRaises(W.WindowsEvidenceError):
            self.f.validate()
        self.assertFalse(self.f.commands)  # Actual modeled spawn never received forged argv.

    def test_command_completed_flag_is_not_an_actual_helper_return(self):
        def hook(_name, binding):
            session = W._PRODUCTIVE_SESSIONS[id(binding)]
            if session.command is not None:
                self.f.hook = None
                session.command["completed"] = ("FORGED",)
        self.f.hook = hook
        with self.assertRaises(W.WindowsEvidenceError):
            self.f.validate()
        self.assertFalse(self.f.record_nodes())

    def reader_mutation(self, mutate, restore):
        session, reader = self.f.archive_reader()
        def hook(_name, _binding):
            self.f.hook = None
            mutate(reader)
        self.f.hook = hook
        with self.assertRaises(H.EvidenceError):
            reader.read(1)
        restore(reader)
        self.assert_sticky(session)

    def test_per_stream_original_session_pin(self):
        original = []
        def mutate(reader):
            original.append(reader.session)
            reader.session = object()
        self.reader_mutation(mutate, lambda reader: setattr(reader, "session", original[0]))

    def test_per_stream_original_node_pin(self):
        original = []
        def mutate(reader):
            original.append(reader.node)
            reader.node = dataclasses.replace(reader.node)
        self.reader_mutation(mutate, lambda reader: setattr(reader, "node", original[0]))

    def test_per_stream_original_native_stream_pin(self):
        original = []
        def mutate(reader):
            original.append(reader.stream)
            reader.stream = object()
        self.reader_mutation(mutate, lambda reader: setattr(reader, "stream", original[0]))

    def test_per_stream_count_mutation_is_sticky(self):
        self.reader_mutation(lambda reader: setattr(reader, "count", 1), lambda reader: setattr(reader, "count", 0))

    def test_per_stream_digest_contents_not_only_digest_object_are_pinned(self):
        session, reader = self.f.archive_reader()
        digest = reader.digest
        self.f.hook = lambda _name, _binding: digest.update(b"SYNTHETIC INJECTION")
        with self.assertRaises(H.EvidenceError):
            reader.read(1)
        self.f.hook = None
        self.assertIs(reader.digest, digest)
        self.assert_sticky(session)

    def test_per_stream_method_substitution_during_callback_refuses(self):
        self.reader_mutation(lambda reader: setattr(reader, "check", lambda *_args: None),
                             lambda reader: delattr(reader, "check"))

    def test_writer_original_raw_pin_and_counter_are_not_caller_flags(self):
        session = self.f.session()
        raw = session.create("writer", self.f.work, "create_file", "writer.bin", max_bytes=16, deadline=session.end())
        writer = W._ProductiveWriter(session, raw)
        def hook(_name, _binding):
            self.f.hook = None
            writer.raw = object()
        self.f.hook = hook
        with self.assertRaises(H.EvidenceError):
            writer.write(b"x")
        writer.raw = raw
        self.assertEqual(writer.count, 0)
        self.assert_sticky(session)

    def test_exact_tar_bytes_mismatch_despite_unchanged_native_metadata(self):
        self.f.prepare_archive()
        def event(name, owner, value):
            if name == "file-read" and owner.endswith("\\synthetic-00\\data.bin") and value:
                return bytes([value[0] ^ 1]) + value[1:]
            return value
        self.f.effect_hook = event
        with self.assertRaises(W.WindowsEvidenceError):
            self.f.export()
        self.assertEqual(len(self.f.record_nodes()), 1)
        self.assertIsNone(self.f.plaintext)  # Encryption never received failed tar custody.

    def test_coupled_tar_closed_flags_during_close_guard_cannot_skip_buffer_flush(self):
        self.f.prepare_archive()
        attacked = []
        def hook(_name, binding):
            session = W._PRODUCTIVE_SESSIONS.get(id(binding))
            if session is None:
                return
            rows = [row for row in session.resources if row["label"] == "plaintext-tar"]
            if not rows or not rows[0]["attempted"]:
                return
            self.f.hook = None
            row = rows[0]
            archive, stream = row["owner"], row["owner"].fileobj
            self.assertIsNone(W._PRODUCTIVE_ROWS[id(row)]["actual_close"])
            self.assertFalse(archive.closed)
            self.assertFalse(stream.closed)
            self.assertTrue(stream.buf)  # Actual pending tar bytes in this SMALL fixture.
            attacked.append((session, row, archive, stream, stream.buf))
            archive.closed = stream.closed = True  # Coupled EARLY flags, no original close call.
        self.f.hook = hook
        with self.assertRaises(W.WindowsEvidenceError):
            self.f.export()
        self.assertEqual(len(attacked), 1)
        session, row, archive, stream, buffered = attacked[0]
        self.assertIs(row["owner"], archive)
        stream_row = session._owners[id(stream)]
        self.assertIs(stream_row["owner"], stream)
        self.assertEqual(row["pin"].children, ())
        self.assertEqual(stream.buf, buffered)
        self.assertTrue(archive.closed and stream.closed)  # Flags did not become close currency.
        self.assertTrue(row["attempted"] and row["quarantined"] and session.unknown)
        self.assertFalse(row["closed"] or row["observed_return"] or row["pin"].closed or
                         stream_row["closed"] or stream_row["observed_return"] or stream_row["pin"].closed)
        self.assertIsNone(W._PRODUCTIVE_ROWS[id(row)]["actual_close"])
        self.assertIsNone(W._PRODUCTIVE_ROWS[id(stream_row)]["actual_close"])
        self.assertIsNone(row["completion"])
        self.assertIsNone(self.f.plaintext)  # No encryption consumes the unflushed tar stream.
        self.assertEqual(len(self.f.record_nodes()), 1)  # Only prior validation; no export receipt.
        self.assert_sticky(session)

    def test_nested_tar_flag_during_actual_padding_cannot_inherit_parent_close(self):
        self.f.prepare_archive(padding_callback=True)
        attacked = []
        def hook(_name, binding):
            session = W._PRODUCTIVE_SESSIONS.get(id(binding))
            if session is None:
                return
            state = W._PRODUCTIVE_SESSION_PINS[id(session)]
            pipeline = state["pipeline"]
            if pipeline is None or type(pipeline[0]) is not tarfile.TarFile or pipeline[1] != "close":
                return
            self.f.hook = None
            archive, stream = pipeline[0], pipeline[0].fileobj
            row, stream_row = session._owners[id(archive)], session._owners[id(stream)]
            self.assertTrue(archive.closed and row["attempted"])  # SAME actual parent close in progress.
            self.assertFalse(stream.closed or stream_row["attempted"] or stream_row["observed_return"])
            self.assertIsNone(W._PRODUCTIVE_ROWS[id(row)]["actual_close"])
            self.assertIsNone(W._PRODUCTIVE_ROWS[id(stream_row)]["actual_close"])
            self.assertTrue(stream.buf)
            attacked.append((session, row, stream_row, stream))
            stream.closed = True  # Parent close permission must NOT apply to this independent owner.
        self.f.hook = hook
        with self.assertRaises(W.WindowsEvidenceError):
            self.f.export()
        self.assertEqual(len(attacked), 1)
        session, row, stream_row, stream = attacked[0]
        self.assertTrue(row["attempted"] and stream.closed and stream_row["quarantined"] and session.unknown)
        self.assertFalse(stream_row["closed"] or stream_row["observed_return"] or stream_row["pin"].closed)
        self.assertIsNone(W._PRODUCTIVE_ROWS[id(stream_row)]["actual_close"])
        self.assertIsNone(stream_row["completion"])
        self.assertIsNone(self.f.plaintext)
        self.assertEqual(len(self.f.record_nodes()), 1)
        self.assert_sticky(session)

    def test_snapshot_missing_map_fails_before_archive(self):
        self.f.prepare_archive()
        path = str(self.f.payload.path) + "\\synthetic-00.map.json"
        del self.f.api.nodes[path]
        with self.assertRaises(W.WindowsEvidenceError):
            self.f.export()
        self.assertIsNone(self.f.plaintext)

    def test_snapshot_full_native_metadata_not_only_hash_is_required(self):
        self.f.prepare_archive()
        path = str(self.f.payload.path) + "\\synthetic-00\\data.bin"
        self.f.api.nodes[path].version += 1  # Bytes/hash remain exactly the original fixture.
        with self.assertRaises(W.WindowsEvidenceError):
            self.f.export()
        self.assertIsNone(self.f.plaintext)

    def test_incomplete_encryption_status_cannot_publish_success(self):
        self.f.prepare_archive()
        self.f.status = b"[GNUPG:] BEGIN_ENCRYPTION 2 9\n"
        with self.assertRaises(W.WindowsEvidenceError):
            self.f.export()
        self.assertEqual(len(self.f.record_nodes()), 1)

    def test_ciphertext_wrong_recipient_packet_refuses(self):
        self.f.prepare_archive()
        self.f.cipher = ciphertext("9" * 40)
        with self.assertRaises(W.WindowsEvidenceError):
            self.f.export()
        self.assertEqual(len(self.f.record_nodes()), 1)

    def test_public_ciphertext_independent_readback_must_match_private_bytes(self):
        self.f.prepare_archive()
        target = str(self.f.output.path) + "\\" + H.ARTIFACT
        def event(name, owner, value):
            if name == "file-read" and owner == target and value:
                return bytes([value[0] ^ 1]) + value[1:]
            return value
        self.f.effect_hook = event
        with self.assertRaises(W.WindowsEvidenceError):
            self.f.export()
        self.assertEqual(len(self.f.record_nodes()), 1)

    def test_manifest_independent_readback_must_match_canonical_bytes(self):
        self.f.prepare_archive()
        target = str(self.f.output.path) + "\\" + H.MANIFEST
        def event(name, owner, value):
            if name == "file-read" and owner == target and value:
                return b"!" + value[1:]
            return value
        self.f.effect_hook = event
        with self.assertRaises(W.WindowsEvidenceError):
            self.f.export()
        self.assertEqual(len(self.f.record_nodes()), 1)

    def test_existing_result_independent_readback_mismatch_is_not_success(self):
        def event(name, owner, value):
            if name == "file-read" and "-result-" in owner and value:
                return b"!" + value[1:]
            return value
        self.f.effect_hook = event
        with self.assertRaises(W.WindowsEvidenceError):
            self.f.validate()
        self.assertEqual(len(self.f.record_nodes()), 1)
        session = W._PRODUCTIVE_SESSIONS[id(self.f.validation_binding)]
        self.assertIsNone(session.result)
        self.assertIsNone(session.known_close)

    def test_result_writer_actual_close_failure_is_not_retried(self):
        attempts = []
        def event(name, owner, value):
            if name == "file-close" and "-result-" in owner:
                attempts.append(value)
                raise RuntimeError("SYNTHETIC result writer close UNKNOWN")
            return value
        self.f.effect_hook = event
        with self.assertRaises(W.WindowsEvidenceError) as caught:
            self.f.validate()
        self.assertTrue(caught.exception.retirement_unknown)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(len(self.f.record_nodes()), 1)
        session = W._PRODUCTIVE_SESSIONS[id(self.f.validation_binding)]
        self.assertIsNone(session.receipt_reader)
        self.assertIsNone(session.result)

    def test_result_reader_actual_close_must_return_before_original_finish(self):
        closes = []
        def event(name, owner, value):
            if name == "file-close" and "-result-" in owner:
                closes.append(value)
                if len(closes) == 2:
                    session = W._PRODUCTIVE_SESSIONS[id(self.f.validation_binding)]
                    self.f.now = session.caps.operationFinishEndLocal
            return value
        self.f.effect_hook = event
        with self.assertRaises(W.WindowsEvidenceError) as caught:
            self.f.validate()
        self.assertTrue(caught.exception.retirement_unknown)
        self.assertEqual(len(closes), 2)
        self.assertEqual(len(self.f.record_nodes()), 1)

    def test_bounded_prior_record_overflow_refuses_without_new_file(self):
        # A formatting dependency fault is pinned BEFORE the actual session.
        # No fixture changes the production 1MiB bound or omits charged rows.
        original = W.json.dumps
        def oversized(value, *args, **kwargs):
            if type(value) is dict and value.get("scope") == "INITIAL_RECIPIENT_PRODUCTIVE_WINDOWS_PRIOR_FACTS_V1":
                return "x" * (W.MAX_RECORD_BYTES + 1)
            return original(value, *args, **kwargs)
        self.f.replace(W.json, "dumps", oversized)
        with self.assertRaises(W.WindowsEvidenceError):
            self.f.validate()
        self.assertFalse(self.f.record_nodes())

    def test_legacy_shared_read_write_wrappers_keep_old_nonproductive_contract(self):
        session = W._Session(self.f.work, "synthetic-legacy-shared-helpers")
        end = self.f.now + 10
        self.assertIsNone(W._write(session, self.f.work, "legacy.bin", b"legacy\0bytes", 32, end))
        self.assertEqual(W._read(session, self.f.work, "legacy.bin", 32, end), b"legacy\0bytes")
        self.assertFalse(session.unknown)
        self.assertTrue(all(row["closed"] for row in session.resources))
        self.assertFalse(W._PRODUCTIVE_SESSIONS)

    def test_legacy_shared_executable_wrapper_returns_only_digest(self):
        self.assertEqual(W._executable(self.f.executable, self.f.now + 10),
                         hashlib.sha256(self.f.executable_bytes).hexdigest())
        self.assertFalse(W._PRODUCTIVE_SESSIONS)

    def test_legacy_shared_gpg_keeps_tuple_and_old_scope_contract(self):
        recipient = self.f.validate().recipient
        session = W._Session(self.f.work, "synthetic-legacy-gpg")
        stdout, stderr = W._gpg(session, recipient, ["--version"], self.f.now + 10)
        self.assertEqual(stdout, self.f.version)
        self.assertEqual(stderr, b"SYNTHETIC-PRIVATE-DIAGNOSTIC\n")
        self.assertEqual(session.commands[0]["retirement"], "KNOWN")
        self.assertTrue(all(row["closed"] for row in session.resources))
        self.assertFalse(self.f.scopes[-1].api.handles)
        self.assertEqual(len(self.f.record_nodes()), 1)  # Only original productive validation.


class ProductiveTarInfoCacheControls(unittest.TestCase):
    """Eight new cache-admission controls; original66 and fixtures stay intact."""

    assert_sticky = ProductiveWindowsControls.assert_sticky

    def setUp(self):
        self.f = Fixture(self)
        self.addCleanup(self.f.dispose)
        self.kind = tarfile.TarInfo
        self.had_cache = "__slotnames__" in self.kind.__dict__
        self.original_cache = self.kind.__dict__.get("__slotnames__")
        self.original_cache_items = (tuple(self.original_cache) if type(self.original_cache) is list else None)
        self.declaration = self.kind.__dict__["__slots__"]
        self.declaration_items = (tuple(self.declaration.items()) if type(self.declaration) is dict
                                  else tuple(self.declaration))
        self.constructor = self.kind.__dict__["__init__"]
        self.addCleanup(self.restore_synthetic_class_changes)

    def restore_synthetic_class_changes(self):
        # Only isolated synthetic test state is restored, never a production
        # registry/close/currency reset. Failed original sessions stay failed.
        self.kind.__init__ = self.constructor
        if type(self.declaration) is dict:
            self.declaration.clear()
            self.declaration.update(self.declaration_items)
        elif type(self.declaration) is list:
            self.declaration[:] = self.declaration_items
        if self.original_cache_items is not None:
            self.original_cache[:] = self.original_cache_items
        if self.had_cache:
            self.kind.__slotnames__ = self.original_cache
        elif "__slotnames__" in self.kind.__dict__:
            del self.kind.__slotnames__

    def refuse_callback_mutation(self, session, mutate, message):
        reached = []
        def hook(_name, _binding):
            self.f.hook = None
            reached.append(True)
            mutate()
        self.f.hook = hook
        with self.assertRaisesRegex(H.EvidenceError, message) as caught:
            W._session_guard(session)
        self.assertEqual(reached, [True])
        self.assertFalse(self.f.scopes)
        self.assertFalse(self.f.record_nodes())
        return caught.exception

    def test_cold_cache_is_prepared_before_first_E_callback_with_exact_namespace(self):
        if "__slotnames__" in self.kind.__dict__:
            del self.kind.__slotnames__
        bases = self.kind.__mro__
        original = tuple((base, tuple(base.__dict__.items())) for base in bases)
        initializer = W.copyreg._slotnames
        seen = []
        def hook(_name, _binding):
            self.f.hook = None
            cache = self.kind.__dict__["__slotnames__"]
            self.assertIs(type(cache), list)
            self.assertEqual(tuple(cache), tuple(self.declaration))
            self.assertIs(self.kind.__mro__, bases)
            for base, items in original:
                self.assertEqual(len(base.__dict__), len(items) + (base is self.kind))
                for name, value in items:
                    self.assertIs(base.__dict__[name], value)
            seen.append(cache)
        self.f.hook = hook
        session = self.f.session()
        self.assertEqual(len(seen), 1)
        self.assertIs(session.tarinfo_copy_pin[0][0], self.declaration)
        self.assertIs(session.tarinfo_copy_pin[0][1], seen[0])
        self.assertIs(self.kind.__slotnames__, seen[0])
        supplier = [row for row in session.supplier_slots if row[:2] == (W.copyreg, "_slotnames")]
        self.assertEqual(len(supplier), 1)
        self.assertIs(supplier[0][2], initializer)
        W._session_check(session)
        self.assertFalse(self.f.scopes)

    def test_correct_warm_cache_keeps_original_object_contents_and_initializer(self):
        initializer = W.copyreg._slotnames
        cache = initializer(self.kind)  # Actual stdlib initialization, not a forged cache.
        contents = tuple(cache)
        original = tuple(self.kind.__dict__.items())
        session = self.f.session()
        self.assertIs(self.kind.__slotnames__, cache)
        self.assertEqual(tuple(cache), contents)
        self.assertEqual(contents, tuple(self.declaration))
        self.assertEqual(len(self.kind.__dict__), len(original))
        for name, value in original:
            self.assertIs(self.kind.__dict__[name], value)
        self.assertIs(session.tarinfo_copy_pin[0][1], cache)
        supplier = [row for row in session.supplier_slots if row[:2] == (W.copyreg, "_slotnames")]
        self.assertEqual(len(supplier), 1)
        self.assertIs(supplier[0][2], initializer)
        W._session_check(session)

    def test_malformed_warm_cache_refuses_before_callbacks_without_healing(self):
        malformed = list(self.declaration)[:-1]
        self.kind.__slotnames__ = malformed
        before, events = tuple(malformed), tuple(self.f.api.events)
        with self.assertRaisesRegex(H.EvidenceError, "Productive TarInfo copy cache differs"):
            self.f.session()
        self.assertIs(self.kind.__slotnames__, malformed)
        self.assertEqual(tuple(malformed), before)
        self.assertEqual(tuple(self.f.api.events), events)
        self.assertEqual(self.f.guard_calls, 0)
        self.assertFalse(self.f.scopes or self.f.commands or self.f.record_nodes())
        self.assertNotIn(id(self.f.validation_binding), W._PRODUCTIVE_SESSIONS)

    def test_equal_cache_replacement_cannot_become_original_currency(self):
        session = self.f.session()
        cache = self.kind.__slotnames__
        def mutate():
            self.kind.__slotnames__ = list(cache)
        error = self.refuse_callback_mutation(session, mutate, "supplier descriptor/constructor changed")
        self.kind.__slotnames__ = cache
        self.assert_sticky(session, error)

    def test_in_place_cache_mutation_is_pinned_and_sticky(self):
        session = self.f.session()
        cache, first = self.kind.__slotnames__, self.kind.__slotnames__[0]
        def mutate():
            cache[0] = "SYNTHETIC_WRONG_SLOT"
        error = self.refuse_callback_mutation(session, mutate, "original DATA slots changed")
        self.assertIs(self.kind.__slotnames__, cache)
        cache[0] = first
        self.assert_sticky(session, error)

    def test_deleted_cache_is_not_reinitialized_after_callback(self):
        session = self.f.session()
        cache = self.kind.__slotnames__
        def mutate():
            del self.kind.__slotnames__
        error = self.refuse_callback_mutation(session, mutate, "supplier descriptor/constructor changed")
        self.assertNotIn("__slotnames__", self.kind.__dict__)
        self.kind.__slotnames__ = cache
        self.assert_sticky(session, error)

    def test_in_place_slot_declaration_contents_remain_pinned(self):
        self.assertIs(type(self.declaration), dict)  # Actual supported stdlib TarInfo declaration.
        session = self.f.session()
        name = next(iter(self.declaration))
        original = self.declaration[name]
        def mutate():
            self.declaration[name] = "SYNTHETIC_CHANGED_SLOT_DOCUMENTATION"
        error = self.refuse_callback_mutation(session, mutate, "original DATA mapping changed")
        self.assertIs(self.kind.__slots__, self.declaration)
        self.declaration[name] = original
        self.assert_sticky(session, error)

    def test_first_callback_cannot_replace_unrelated_TarInfo_constructor(self):
        called = []
        def replacement(*_args, **_kwargs):
            called.append("FORGED")
        def hook(_name, _binding):
            self.f.hook = None
            self.kind.__init__ = replacement
        self.f.hook = hook
        with self.assertRaisesRegex(H.EvidenceError, "supplier descriptor/constructor changed") as caught:
            self.f.session()
        self.kind.__init__ = self.constructor
        session = W._PRODUCTIVE_SESSIONS[id(self.f.validation_binding)]
        self.assert_sticky(session, caught.exception)
        self.assertEqual(self.f.guard_calls, 1)
        self.assertFalse(called or self.f.scopes or self.f.record_nodes())


if __name__ == "__main__":
    result = unittest.main(verbosity=2, failfast=True, exit=False).result
    print("PRODUCTIVE_WINDOWS_CONTROLS=OFFLINE_SYNTHETIC_NATIVE_MODEL_ONLY "
          "NATIVE_WINDOWS_GPG=NOT_RUN HOSTED_POLICY_PROVIDER_CUSTODY=NOT_QUALIFIED "
          "REAL_FIXED30_CAPACITY_TIMING=NOT_MEASURED ACTIVATION_HOLDS=UNCHANGED")
    raise SystemExit(0 if result.wasSuccessful() else 1)
