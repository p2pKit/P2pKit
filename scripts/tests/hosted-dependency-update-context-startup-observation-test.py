#!/usr/bin/env python3
"""Focused offline STARTUP observation controls, never native qualification.

Only the complete bridge module is imported, after the persistent offline
fence. Existing control files are read as DATA for exact inverse checks; no
accepted suite is imported or run. Every registration, stream, clock and
administrative return below is explicitly synthetic, not execution authority.
"""
import __future__
import ast
import contextlib
import copy
import ctypes
import errno
import grp
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import platform
import plistlib
import pwd
import re
import select
import signal
import socket
import stat
import struct
import subprocess
import sys
import time
import types
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[2]
BRIDGE = "scripts/hosted_dependency_update_context.py"
CALLER = "scripts/run-hosted-jmdns-startup.py"
SHARED = "scripts/tests/hosted-dependency-update-context-test.py"
STARTUP = "scripts/tests/hosted-jmdns-startup-context-test.py"
THIS = "scripts/tests/hosted-dependency-update-context-startup-observation-test.py"
BASELINE = {
    BRIDGE: "051f4942073f2fd8b7f0ce1b57a6a3a1246ffbd440a135573a6b7f84923bcfe7",
    CALLER: "ad665804f90287e22caccb291bb35f28dbfc3d5b7b1e96f431577efe16a27b07",
    SHARED: "4c736c6399ce69bf5578bb4624bf6acbb8b25f29d6bdb6d5205e46d8181d1b10",
    STARTUP: "8c191b0b4a57888aa336becbc68bf9fe5e55d86173db3b0bc68a0558e8cd3f6c",
}
SHARED_DELTA_BYTES = 17343
SHARED_DELTA_SHA256 = "fd4ac3ec1afc1e04ca4c568507dde65053d43004c39af2e3e5abad5da8e04b9c"
STARTUP_PIN_ADAPTER = (
    "                original = (ROOT / relative).read_bytes()\n"
    "                if relative == \"scripts/tests/hosted-dependency-update-context-test.py\":\n"
    "                    begin = b\"        # STARTUP_OBSERVATION_INVERSE_BEGIN\\n\"\n"
    "                    end = b\"        # STARTUP_OBSERVATION_INVERSE_END\\n\"\n"
    "                    self.assertEqual(original.count(begin), 1)\n"
    "                    self.assertEqual(original.count(end), 1)\n"
    "                    start, finish = original.index(begin), original.index(end) + len(end)\n"
    "                    self.assertLess(start, finish)\n"
    "                    adapter = original[start:finish]\n"
    "                    self.assertEqual(len(adapter), 17343)\n"
    "                    self.assertEqual(hashlib.sha256(adapter).hexdigest(),\n"
    "                                     \"fd4ac3ec1afc1e04ca4c568507dde65053d43004c39af2e3e5abad5da8e04b9c\")\n"
    "                    original = original[:start] + original[finish:]\n"
    "                self.assertEqual(hashlib.sha256(original).hexdigest(), expected)\n"
)
STARTUP_PIN_ORIGINAL = "                self.assertEqual(hashlib.sha256((ROOT / relative).read_bytes()).hexdigest(), expected)\n"
CALLER_HOOK = (
    "    except BaseException as error:\n"
    "        if owner is not None and not owner.finished:\n"
    "            owner.attach_startup_failure(error)\n"
    "            owner.abort()\n"
    "        raise\n"
    "    finally:\n"
)
CALLER_ORIGINAL = (
    "    except BaseException:\n"
    "        if owner is not None and not owner.finished:\n"
    "            owner.abort()\n"
    "        raise\n"
    "    finally:\n"
)
PHASES = ("PREPARE_CASE", "INPUTS_AND_ADMIN", "SOCKET_PREPARE", "LAUNCHER_CREATE", "BOOTSTRAP",
          "WAIT_CONNECT", "PEER_CHECK", "WAIT_HELLO", "HELLO_CHECK", "INSPECT_AND_ATTACH",
          "WAIT_CHILD_READY", "CHILD_READY_CHECK", "START_HANDOFF", "WAIT_FINAL", "FINAL_VALIDATE", "RETIRE")
STATUSES = ("NOT_OBSERVED", "RUNNING", "NOT_RUNNING", "SPAWN_SCHEDULED", "WAITING",
            "REGISTRATION_ABSENT", "PRINT_FAILED", "INVALID", "UNSUPPORTED")
NS = 1_000_000_000
DIRECTORY = Path("/controlled/STARTUP")
PRIVATE = "/private/var/db/p2pkit-context.abcdefghij"
PLIST, LAUNCHER = PRIVATE + "/job.plist", PRIVATE + "/launcher"
LABEL = "p2pkit.context.r123.a1.startup.abcdef"
PRINT_ARGV = ["/usr/bin/sudo", "-n", "--", "/bin/launchctl", "print", "system/" + LABEL]
ACCOUNT = {"uid": 501, "euid": 501, "gid": 20, "egid": 20, "groups": [20, 80]}


def offline(event, args):
    if event.startswith(("socket.", "subprocess.")) or event in {
        "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty",
        "os.kill", "os.killpg", "ctypes.dlopen", "ctypes.dlsym", "os.putenv", "os.unsetenv",
        "os.setuid", "os.seteuid", "os.setgid", "os.setegid", "os.setgroups",
        "os.setreuid", "os.setregid", "os.setresuid", "os.setresgid",
        "os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.link", "os.symlink", "os.chmod", "os.chown",
    }:
        raise AssertionError("offline STARTUP observation control attempted an external operation: " + event)
    if event == "open" and type(args[2]) is int and args[2] & (
            os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
        raise AssertionError("offline STARTUP observation control attempted a filesystem write")


# All standard-library imports above precede the sole, fenced project import.
sys.addaudithook(offline)


def setUpModule():
    global B
    if not (sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode):
        raise AssertionError("use python3 -I -B -S for offline STARTUP observation controls")
    spec = importlib.util.spec_from_file_location("startup_observation_bridge_controls", ROOT / BRIDGE)
    B = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = B
    spec.loader.exec_module(B)


class Unprintable:
    def __str__(self):
        raise AssertionError("private DATA must not be formatted")
    __repr__ = __str__


class StringSubclass(str):
    pass


class DictSubclass(dict):
    def __iter__(self):
        raise AssertionError("reject dictionary subclasses before iteration")


class Ledger(io.BytesIO):
    def fileno(self):
        return 999  # Only the mocked fsync receives this synthetic descriptor.


class ForbiddenNative:
    def __init__(self):
        self.attempts = []

    def __getattr__(self, name):
        self.attempts.append(name)
        raise AssertionError("diagnostic DATA cannot acquire native authority")


class BufferedChannel:
    """Synthetic recvmsg bytes; never an OS socket or descriptor."""

    def __init__(self, raw=b"", *, eof=False):
        self.raw, self.eof, self.reads, self.blocking = bytearray(raw), eof, [], None

    def ready(self):
        return bool(self.raw) or self.eof

    def recvmsg(self, size, ancillary_size):
        if not self.ready():
            raise AssertionError("synthetic unready channel was read")
        self.reads.append((size, ancillary_size))
        value = bytes(self.raw[:size])
        del self.raw[:size]
        return value, [], 0, None

    def setblocking(self, value):
        self.blocking = value


def framed(value):
    raw = B.encoded(value)
    return struct.pack("!I", len(raw)) + raw


def identity(pid, parent):
    value = {key: 1 for key in B.IDENTITY_KEYS}
    value.update(pid=pid, parentPid=parent, uniqueId=pid + 1000, parentUniqueId=parent + 1000,
                 uid=501, realUid=501, savedUid=501, gid=20, realGid=20, savedGid=20)
    return value


def print_bytes(state="running", exit_code=None, *, label=LABEL):
    rows = ["system/" + label + " = {", "\tpath = " + PLIST, "\ttype = LaunchDaemon",
            "\tprogram = " + LAUNCHER, "\targuments = {", "\t\t" + LAUNCHER, "\t}",
            "\tstate = " + state, "\tpid = 701", "\tenvironment = {", "\t\tFIXED = synthetic", "\t}"]
    if exit_code is not None:
        rows.append("\tlast exit code = " + exit_code)
    return ("\n".join([*rows, "}"]) + "\n").encode("ascii")


def print_result(raw=None, *, code=0, stderr=b"", label=LABEL):
    return {"argv": [*PRINT_ARGV[:-1], "system/" + label], "code": code,
            "stdout": print_bytes(label=label) if raw is None else raw, "stderr": stderr,
            "waited": True, "eof": True, "closed": True}


def make_owner(*, end=1000 * NS, phase="WAIT_CONNECT"):
    owner = object.__new__(B.Foreground)
    owner.profile = B.STARTUP
    owner.finished, owner.failed, owner._aborted = False, False, False
    owner._startup_phase, owner._startup_probe_end, owner._startup_probe_consumed = phase, None, False
    owner.os_env = {"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "LANG": "C", "LC_ALL": "C"}
    owner.native = ForbiddenNative()
    owner.current = {"common": {"case": "STARTUP"}, "directory": DIRECTORY, "end": end,
                     "service": None, "producer": None, "prepareSent": False, "started": False,
                     "listener": None, "channel": None, "socket": None, "trace": []}
    admin = object.__new__(B.Admin)
    admin.context, admin.directory, admin.label, admin.end_ns = owner, DIRECTORY, LABEL, end
    admin.root, admin.path, admin.launcher = PRIVATE, PLIST, LAUNCHER
    admin.arguments, admin.plist = [LAUNCHER], b"synthetic original plist"
    admin.root_meta, admin.root_populated_meta, admin.file_meta, admin.launcher_meta = {}, {}, {}, {}
    admin.launcher_bytes, admin.launcher_offset = b"x" * B.STREAM_BYTES, B.STREAM_BYTES
    admin.bootstrapped, admin.retired, admin.removed, admin.closed = True, False, False, False
    admin.service, admin.calls, admin.written, admin.record = None, 105, 0, Ledger()
    owner.current["admin"] = admin
    return owner, admin


def definition(text, name, owner=None):
    nodes = ast.parse(text).body
    if owner is not None:
        classes = [node for node in nodes if isinstance(node, ast.ClassDef) and node.name == owner]
        if len(classes) != 1:
            raise AssertionError("missing or duplicated source class")
        nodes = classes[0].body
    found = [node for node in nodes if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(found) != 1:
        raise AssertionError("missing or duplicated source method")
    return found[0]


class StartupObservationControls(unittest.TestCase):
    def test_finite_projection_and_exact_registration_parser(self):
        self.assertIs(type(B.STARTUP_DIAGNOSTIC_SECONDS), int)
        self.assertEqual(B.STARTUP_DIAGNOSTIC_SECONDS, 30)
        self.assertIs(type(B.STARTUP_DIAGNOSTIC_PHASES), frozenset)
        self.assertIs(type(B.STARTUP_DIAGNOSTIC_STATUSES), frozenset)
        self.assertEqual(B.STARTUP_DIAGNOSTIC_PHASES, frozenset(PHASES))
        self.assertEqual(B.STARTUP_DIAGNOSTIC_STATUSES, frozenset(STATUSES))
        owner, admin = make_owner()
        try:
            for phase in PHASES:
                owner._set_startup_phase(phase)
                for status in STATUSES:
                    error = B.ContextError("START", "STARTUP_OBSERVATION_ONLY")
                    owner.attach_startup_failure(error, status=status, exit_code="NONE")
                    rendered = B.public_error(error)
                    self.assertEqual(rendered, "DEPENDENCY_CONTEXT/START/STARTUP_OBSERVATION_ONLY/NONE/" +
                                     phase + "/" + status + "/NONE")
                    self.assertLessEqual(len(rendered), 160)
            owner._set_startup_phase("WAIT_HELLO")
            for code in ("NONE", "UNSUPPORTED", *("CODE_" + str(value) for value in range(256))):
                error = B.ContextError("START", "STARTUP_OBSERVATION_ONLY")
                owner.attach_startup_failure(error, status="RUNNING", exit_code=code)
                self.assertEqual(B.public_error(error),
                                 "DEPENDENCY_CONTEXT/START/STARTUP_OBSERVATION_ONLY/NONE/WAIT_HELLO/RUNNING/" + code)
            for native_errno in ("NONE", "ETIMEDOUT"):
                error = B.ContextError("START", "TIMEOUT", native_errno)
                owner.attach_startup_failure(error)
                rendered = B.public_error(error)
                self.assertEqual(rendered, "DEPENDENCY_CONTEXT/START/TIMEOUT/" + native_errno +
                                 "/WAIT_HELLO/NOT_OBSERVED/NONE")
                owner._set_startup_phase("RETIRE")
                owner.attach_startup_failure(error, status="RUNNING", exit_code="CODE_105")
                self.assertEqual(B.public_error(error), rendered)
                owner._set_startup_phase("WAIT_HELLO")
            valid = {"startup_phase": "WAIT_HELLO", "registration_status": "RUNNING", "registration_exit": "NONE"}
            malformed = [None, [], {}, DictSubclass(valid), {**valid, "private": Unprintable()}]
            for field in valid:
                malformed.extend({**valid, field: value} for value in
                                 (None, True, 1, [], {}, b"NONE", StringSubclass(valid[field]), Unprintable()))
            malformed.extend({**valid, "registration_exit": value} for value in
                             ("CODE_-1", "CODE_+1", "CODE_00", "CODE_01", "CODE_256", "CODE_999", "CODE_1\n",
                              "CODE_1\0", "CODE_１", "/private/not-an-exit", "X" * 1000))
            malformed.extend({**valid, "startup_phase": value} for value in ("UNKNOWN", "WAIT_HELLO\n", ""))
            malformed.extend({**valid, "registration_status": value} for value in ("running", "UNKNOWN", ""))
            malformed.extend({**{name: value for name, value in valid.items() if name != "startup_phase"}, key: "WAIT_HELLO"}
                             for key in (1, b"startup_phase", StringSubclass("startup_phase"), Unprintable()))
            for index, details in enumerate(malformed):
                error = B.ContextError("START", "TIMEOUT")
                error._startup_profile, error._startup_diagnostic = B.STARTUP, details
                with self.subTest(malformed=index):
                    self.assertFalse(B._startup_diagnostic_valid(details))
                    self.assertEqual(B.public_error(error), "DEPENDENCY_CONTEXT/START/TIMEOUT/NONE")
                    self.assertIs(error._startup_diagnostic, details)
            for profile in (B.GENERATION, B.QUALIFICATION, copy.copy(B.STARTUP), None):
                error = B.ContextError("START", "TIMEOUT")
                error._startup_profile, error._startup_diagnostic = profile, valid
                self.assertEqual(B.public_error(error), "DEPENDENCY_CONTEXT/START/TIMEOUT/NONE")
            for stage, reason, native_errno in (("CLOSE", "TIMEOUT", "NONE"), ("START", "REFUSED", "NONE"),
                                                ("START", "TIMEOUT", "EACCES")):
                error = B.ContextError(stage, reason, native_errno)
                owner.attach_startup_failure(error)
                self.assertEqual(B.public_error(error), "DEPENDENCY_CONTEXT/" + "/".join((stage, reason, native_errno)))
            self.assertEqual(B.public_error(Unprintable()), "DEPENDENCY_CONTEXT/UNKNOWN/REFUSED/UNKNOWN")
            self.assertEqual(B.public_error(B.ContextError("SOURCE", "LAUNCHER_MACHO", launcher_macho_predicate="HEADER")),
                             "DEPENDENCY_CONTEXT/SOURCE/LAUNCHER_MACHO/NONE/HEADER")
            for invalid_phase in (None, "UNKNOWN", StringSubclass("WAIT_HELLO"), Unprintable()):
                with self.assertRaises(B.ContextError):
                    owner._set_startup_phase(invalid_phase)
                self.assertEqual(owner._startup_phase, "WAIT_HELLO")
            owner._startup_phase = None
            error = B.ContextError("START", "TIMEOUT")
            owner.attach_startup_failure(error)
            self.assertFalse(hasattr(error, "_startup_diagnostic"))
            self.assertEqual(B.public_error(error), "DEPENDENCY_CONTEXT/START/TIMEOUT/NONE")
        finally:
            admin.record.close()

        parse = lambda result, label=LABEL, path=PLIST, arguments=None: B.parse_startup_registration(
            result, label, path, [LAUNCHER] if arguments is None else arguments)
        for state, expected in (("running", "RUNNING"), ("not running", "NOT_RUNNING"),
                                ("spawn scheduled", "SPAWN_SCHEDULED"), ("waiting", "WAITING"),
                                ("other printable state", "UNSUPPORTED")):
            self.assertEqual(parse(print_result(print_bytes(state))), (expected, "NONE"))
            self.assertEqual(parse(print_result(print_bytes(state, "(never exited)"))), (expected, "NONE"))
            self.assertEqual(parse(print_result(print_bytes(state, "105"))), (expected, "CODE_105"))
        for code in range(256):
            self.assertEqual(parse(print_result(print_bytes("running", str(code)))), ("RUNNING", "CODE_" + str(code)))
        for code in ("-1", "+1", "00", "01", "256", "9999", "0x69", "(unknown)", "105 extra"):
            self.assertEqual(parse(print_result(print_bytes("not running", code))), ("NOT_RUNNING", "UNSUPPORTED"))
        absent = ('Could not find service "' + LABEL + '" in domain for system\n').encode("ascii")
        for stderr in (absent, b"Bad request.\n" + absent):
            for code in (1, 113, 255):
                self.assertEqual(parse(print_result(b"", code=code, stderr=stderr)), ("REGISTRATION_ABSENT", "NONE"))
        for result in (print_result(b"", code=113), print_result(b"", code=-9),
                       print_result(b"", code=0, stderr=absent), print_result(code=1),
                       print_result(b"", code=1, stderr=absent.replace(LABEL.encode(), b"foreign"))):
            self.assertEqual(parse(result), ("PRINT_FAILED", "NONE"))
        raw = print_bytes()
        invalid = [b"", raw[:-2], raw + b"unconsumed\n", raw + b"}\n", b"\xff" + raw,
                   raw.replace(b"running", b"running\0"), raw.replace(b"running", b"running\r"),
                   raw.replace(b"running", b"running\x1b"), raw.replace(b"\tstate = running\n", b""),
                   raw.replace(b"state = running", b"state = "), raw.replace(LABEL.encode(), b"foreign", 1),
                   raw.replace(PLIST.encode(), b"/foreign/job.plist"), raw.replace(b"LaunchDaemon", b"LaunchAgent"),
                   raw.replace(b"program = " + LAUNCHER.encode(), b"program = /foreign/launcher"),
                   raw.replace(b"\t\t" + LAUNCHER.encode(), b"\t\t/foreign/launcher"),
                   raw.replace(b"\t\t" + LAUNCHER.encode(), b"\t\t" + LAUNCHER.encode() + b"\n\t\textra"),
                   raw.replace(b"\tstate = running", b"\tstate = running\n\tstate = waiting"),
                   raw.replace(b"\ttype = LaunchDaemon", b"\ttype = LaunchDaemon\n\ttype = LaunchDaemon"),
                   raw.replace(b"\targuments = {", b"\targuments = nope"),
                   print_bytes("not running", ""),
                   raw.replace(b"\tstate = running", b"\tstate = {\n\t}"),
                   raw.replace(b"\tstate = running", b"\tstate = running\n\tlast exit code = {\n\t}"),
                   raw.replace(b"\tenvironment = {", b"\tenvironment = }{"),
                   raw.replace(b"FIXED = synthetic", b"FIXED = }{"),
                   raw.replace(b"\tpid = 701", b"\t = 701"),
                   raw.replace(b"\tenvironment = {", b"\tenvironment = {\n" + b"\t\tinner = {\n" * 8),
                   b"x" * (B.STREAM_BYTES + 1)]
        for index, value in enumerate(invalid):
            with self.subTest(invalid_print=index):
                self.assertEqual(parse(print_result(value)), ("INVALID", "NONE"))
        environment = b"\tenvironment = {\n\t\tFIXED = synthetic\n\t}\n"
        for inner, expected in ((6, "RUNNING"), (7, "INVALID")):
            nested = (b"\tenvironment = {\n" + b"\t\tinner = {\n" * inner +
                      b"\t\tFIXED = synthetic\n" + b"\t\t}\n" * inner + b"\t}\n")
            self.assertEqual(parse(print_result(raw.replace(environment, nested))), (expected, "NONE"))
        base = print_result()
        malformed = [None, [], DictSubclass(base), {**base, "private": Unprintable()}]
        for field in base:
            malformed.append({name: value for name, value in base.items() if name != field})
        for field, value in (("argv", tuple(base["argv"])), ("argv", [*base["argv"][:-1], "system/foreign"]),
                             ("code", True), ("code", 256), ("code", -128), ("stdout", "not bytes"),
                             ("stderr", Unprintable()), ("waited", False), ("eof", False), ("closed", False)):
            malformed.append({**base, field: value})
        for index, value in enumerate(malformed):
            with self.subTest(malformed_result=index):
                self.assertEqual(parse(value), ("INVALID", "NONE"))
        for label, path, arguments in ((StringSubclass(LABEL), PLIST, [LAUNCHER]), (LABEL, "/foreign/job.plist", [LAUNCHER]),
                                       (LABEL, PLIST, (LAUNCHER,)), (LABEL, PLIST, []),
                                       (LABEL, PLIST, [LAUNCHER, "extra"]), (LABEL, PLIST, [StringSubclass(LAUNCHER)])):
            self.assertEqual(parse(base, label, path, arguments), ("INVALID", "NONE"))

    def test_original_ready_first_flow_and_shared_raw_deadline(self):
        binding = "a" * 64

        class AtInspect(Exception):
            pass

        def flow(profile, *, mode="complete", ready_at=130 * NS, expected="INSPECT", mutation=None):
            owner, template = make_owner()
            clock, phases, inspected, peers = [0], [], [], []
            peer, foreground = identity(701, 1), identity(700, 2)
            owner.profile = profile
            if profile is not B.STARTUP:
                for name in ("_startup_phase", "_startup_probe_end", "_startup_probe_consumed"):
                    delattr(owner, name)
            owner.github, owner.allocation = {"runId": "123", "runAttempt": "1"}, {}
            owner.source = {"files": {profile.script: "e" * 64}}
            owner.account, owner.foreground_identity = copy.deepcopy(ACCOUNT), foreground
            owner.boot, owner.interpreter, owner.operation_identity, owner.tools = "synthetic-boot", {}, [3, 4], {}
            owner.step_end_ns = owner.job_end_ns = owner.policy_end_ns = owner.current["end"]
            owner.outcomes, owner.sentinel = [], object()  # Q must not start a real sentinel.
            metadata = {"dev": 1, "ino": 2, "mode": 0o100755, "uid": 0, "gid": 0, "nlink": 1}
            owner.os_files = {name: [metadata[key] for key in ("dev", "ino", "mode", "uid", "gid")] +
                              ([metadata["nlink"]] if name in B.OS_TOOLS else [])
                              for name in (*B.OS_PARENTS, *B.OS_TOOLS)}
            inputs = {key: None for key in B.CASE_INPUT_KEYS}
            inputs.update(schema=1, scope=profile.scope, case=profile.cases[0], binding=binding)
            owner.current["common"] = dict(inputs)
            hello = {"service": dict(peer), "account": copy.deepcopy(ACCOUNT), "foregroundPeer": dict(foreground),
                     "boot": owner.boot, "sourceSha256": "e" * 64, "interpreter": {}, "directoryIdentity": [1, 2]}
            if mutation is not None:
                mutation(hello)
            packet = framed(B.frame_value(1, binding, hello))
            channel = BufferedChannel(packet[:6] if mode.startswith("partial") else packet)
            listener = Mock()
            listener.accept.return_value, listener.fileno.return_value = (channel, None), -1

            class PeerOnly(ForbiddenNative):
                def __init__(self):
                    super().__init__()
                    self.attach_attempts = []

                def peer(self, original_channel):
                    self_test.assertIs(original_channel, channel)
                    peers.append(original_channel)
                    return peer

            self_test, owner.native = self, PeerOnly()
            original_phase = owner._set_startup_phase

            def phase(value):
                phases.append(value)
                original_phase(value)

            def initialize(admin, context, directory, label, end_ns):
                self.assertIs(context, owner)
                self.assertEqual((directory, end_ns), (DIRECTORY, owner.current["end"]))
                admin.__dict__.update(template.__dict__)
                admin.label, admin.bootstrapped = label, False

            def create(admin):
                self.assertIs(admin, owner.current["admin"])
                if profile is B.STARTUP:
                    self.assertEqual(owner._startup_phase, "LAUNCHER_CREATE")

            def bootstrap(admin):
                if profile is B.STARTUP:
                    self.assertEqual(owner._startup_phase, "BOOTSTRAP")
                    self.assertIsNone(owner._startup_probe_end)
                admin.bootstrapped, clock[0] = True, 100 * NS

            def selected(readable, writable, exceptional, timeout):
                self.assertEqual((writable, exceptional), ([], []))
                if readable == [listener]:
                    self.assertGreater(timeout, 0)
                    clock[0] = ready_at
                    return ([] if mode == "no_connect" else [listener]), [], []
                self.assertEqual(readable, [channel])
                if timeout:
                    self.assertTrue(mode.startswith("partial"))
                    clock[0] = 130 * NS
                    if mode == "partial_complete":
                        channel.raw.extend(packet[6:])
                return ([channel] if channel.ready() else []), [], []

            def inspect(admin, actual_peer):
                self.assertIs(actual_peer, peer)
                inspected.append(admin)
                raise AtInspect()

            def observation(admin, argv, stage, *, success):
                self.assertTrue(owner._startup_probe_consumed)
                self.assertEqual((argv, stage, success),
                                 (["/bin/launchctl", "print", "system/" + admin.label], "START", False))
                return print_result(print_bytes(label=admin.label), label=admin.label)

            try:
                with contextlib.ExitStack() as stack:
                    stack.enter_context(patch.object(owner, "_original_data"))
                    stack.enter_context(patch.object(owner, "_set_startup_phase", side_effect=phase))
                    stack.enter_context(patch.object(B, "case_input", return_value=(inputs, "d" * 64)))
                    stack.enter_context(patch.object(B.Admin, "__init__", initialize))
                    stack.enter_context(patch.object(B.Admin, "metadata", return_value=metadata))
                    stack.enter_context(patch.object(B.Admin, "create", create))
                    stack.enter_context(patch.object(B.Admin, "bootstrap", bootstrap))
                    stack.enter_context(patch.object(B.Admin, "inspect", inspect))
                    observe = stack.enter_context(patch.object(B.Admin, "_run", autospec=True, side_effect=observation))
                    stack.enter_context(patch.object(B.socket, "socket", return_value=listener))
                    stack.enter_context(patch.object(B.os, "chmod"))
                    stack.enter_context(patch.object(B, "socket_identity", return_value=[5, 6]))
                    stack.enter_context(patch.object(B, "private_directory", return_value=[1, 2]))
                    writes = stack.enter_context(patch.object(B, "write_new"))
                    raw_clock = stack.enter_context(patch.object(B, "shared_raw_ns", side_effect=lambda: clock[0]))
                    stack.enter_context(patch.object(B.select, "select", side_effect=selected))
                    old_read = stack.enter_context(patch.object(B, "read_frame", wraps=B.read_frame))
                    startup_read = stack.enter_context(patch.object(owner, "_read_startup_hello", wraps=owner._read_startup_hello))
                    start_probe = stack.enter_context(patch.object(owner, "_start_startup_probe", wraps=owner._start_startup_probe))
                    try:
                        owner._run_current_case()
                    except AtInspect:
                        outcome = "INSPECT"
                    except B.ContextError as error:
                        outcome = error.stage if expected == "IDENTITY" else error.reason
                    else:
                        self.fail("synthetic flow must stop before native attachment")
                    self.assertEqual(outcome, expected)
                    self.assertEqual(observe.call_count, int(expected == "STARTUP_OBSERVATION_ONLY"))
                    start_probe.assert_called_once_with(owner.current["end"])
                    self.assertEqual(writes.call_count, 1)
                    self.assertEqual(writes.call_args.args[0], DIRECTORY / "prepared.json")
                    if mode != "no_connect":
                        listener.accept.assert_called_once_with()
                        listener.close.assert_called_once_with()
                        self.assertIs(channel.blocking, False)
                        self.assertEqual(peers, [channel])
                        self.assertEqual((startup_read.call_count, old_read.call_count),
                                         (1, 0) if profile is B.STARTUP else (0, 1))
                    else:
                        listener.accept.assert_not_called()
                        self.assertEqual((startup_read.call_count, old_read.call_count, len(peers)), (0, 0, 0))
                    if expected == "INSPECT":
                        self.assertEqual(inspected, [owner.current["admin"]])
                        self.assertIs(owner.current["service"], peer)
                        self.assertEqual(owner.current["trace"], [B.frame_record(B.frame_value(1, binding, hello))])
                        if mode == "complete":
                            self.assertEqual(raw_clock.call_count, 3 if profile is B.STARTUP else 2)
                    else:
                        self.assertEqual(inspected, [])
                        self.assertIsNone(owner.current["service"])
                    if profile is B.STARTUP:
                        self.assertEqual(owner._startup_probe_end, 130 * NS)
                        self.assertEqual(owner._startup_probe_consumed, expected == "STARTUP_OBSERVATION_ONLY")
                    else:
                        self.assertFalse(any(name.startswith("_startup_") for name in owner.__dict__))
                    self.assertEqual(phases[:5], list(PHASES[1:6]))
                    self.assertEqual(owner.native.attempts, [])
                    self.assertIsNone(owner.current["producer"])
                    self.assertFalse(owner.current["prepareSent"] or owner.current["started"])
                    self.assertIsNone(owner.current["admin"].service)
                    self.assertFalse(owner.current["admin"].retired or owner.current["admin"].removed)
            finally:
                template.record.close()

        # These call the complete original Foreground method. Ready connections
        # and complete frames at/after the diagnostic boundary must win first.
        for profile in (B.STARTUP, B.GENERATION, B.QUALIFICATION):
            for ready_at in (130 * NS, 131 * NS):
                with self.subTest(profile=profile.job, ready_at=ready_at):
                    flow(profile, ready_at=ready_at)
        flow(B.STARTUP, mode="partial_complete", ready_at=129 * NS)
        flow(B.STARTUP, mode="partial_pending", ready_at=129 * NS, expected="STARTUP_OBSERVATION_ONLY")
        flow(B.STARTUP, mode="no_connect", expected="STARTUP_OBSERVATION_ONLY")
        flow(B.STARTUP, ready_at=1000 * NS, expected="TIMEOUT")
        flow(B.STARTUP, mode="no_connect", ready_at=1000 * NS, expected="TIMEOUT")
        mutations = (
            lambda value: value["service"].update(uniqueId=9001),
            lambda value: value["account"].update(groups=[80, 20]),
            lambda value: value["foregroundPeer"].update(uniqueId=9002),
            lambda value: value.update(boot="foreign"),
            lambda value: value.update(sourceSha256="f" * 64),
            lambda value: value.update(interpreter={"foreign": True}),
            lambda value: value.update(directoryIdentity=[99, 100]),
            lambda value: value.update(extra=True),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(original_hello_gate=index):
                flow(B.STARTUP, ready_at=131 * NS, expected="IDENTITY", mutation=mutate)

        # Real FrameReader retains EOF, partial, length, binding and canonical
        # frame checks, even when the diagnostic deadline is already due.
        value = B.frame_value(1, binding, {"synthetic": True})
        packet = framed(value)
        variants = ((b"", True, "STATUS_MISSING"), (packet[:6], True, "PARTIAL_FRAME"),
                    (struct.pack("!I", 0), False, "BOUND"),
                    (struct.pack("!I", B.FRAME_BYTES + 1), False, "BOUND"),
                    (framed(B.frame_value(2, binding, {})), False, "FRAME"),
                    (framed(B.frame_value(1, "b" * 64, {})), False, "FRAME"),
                    (struct.pack("!I", 7) + b'{"x":1}', False, "FRAME"),
                    (struct.pack("!I", 1) + b"{", False, "REFUSED"))
        for raw, eof, reason in variants:
            owner, admin = make_owner(phase="WAIT_HELLO")
            owner._startup_probe_end = 130 * NS
            channel = BufferedChannel(raw, eof=eof)
            try:
                with patch.object(B, "shared_raw_ns", return_value=130 * NS), \
                        patch.object(B.select, "select", side_effect=lambda *_args: ([channel] if channel.ready() else [], [], [])), \
                        patch.object(B.Admin, "_run", side_effect=AssertionError("invalid frame must win")) as command, \
                        self.assertRaises(B.ContextError) as caught:
                    owner._read_startup_hello(channel, binding, [], owner.current["end"])
                self.assertEqual(caught.exception.reason, reason)
                self.assertFalse(owner._startup_probe_consumed)
                command.assert_not_called()
                self.assertEqual(owner.native.attempts, [])
            finally:
                admin.record.close()

    def test_original_one_shot_admin_refusal_and_pre_abort_capture(self):
        self.assertEqual(B.ADMIN_CALL_LIMIT, 130)
        self.assertEqual((B.ADMIN_SECONDS, B.STREAM_BYTES, B.FRAME_BYTES), (10, 65536, 16384))
        self.assertEqual(57 + (42 + 4) + 2, 105)
        self.assertEqual(105 + 1, 106)
        self.assertEqual(105 + 1 + 24, B.ADMIN_CALL_LIMIT)
        for end in (120 * NS, 1000 * NS):
            owner, admin = make_owner(end=end)
            clock = [100 * NS]
            try:
                with patch.object(B, "shared_raw_ns", side_effect=lambda: clock[0]), \
                        patch.object(B.Admin, "_run", side_effect=AssertionError("original deadline must win")) as command:
                    owner._start_startup_probe(end)
                    anchor = min(end, 130 * NS)
                    self.assertEqual(owner._startup_probe_end, anchor)
                    owner._set_startup_phase("WAIT_HELLO")
                    with self.assertRaises(B.ContextError) as reset:
                        owner._start_startup_probe(end)
                    self.assertEqual(reset.exception.reason, "DIAGNOSTIC_STATE")
                    self.assertEqual(owner._startup_probe_end, anchor)
                    clock[0] = anchor - 1
                    self.assertIsNone(owner._startup_wait_check())
                    clock[0] = end
                    with self.assertRaises(B.ContextError) as expired:
                        owner._startup_wait_check()
                    self.assertEqual(B.public_error(expired.exception), "DEPENDENCY_CONTEXT/START/TIMEOUT/NONE")
                    self.assertFalse(owner._startup_probe_consumed)
                    self.assertEqual(admin.calls, 105)
                    command.assert_not_called()
            finally:
                admin.record.close()

        for profile in (B.GENERATION, B.QUALIFICATION):
            owner, admin = make_owner()
            owner.profile = profile
            for name in ("_startup_phase", "_startup_probe_end", "_startup_probe_consumed"):
                delattr(owner, name)
            try:
                with patch.object(B, "shared_raw_ns", side_effect=AssertionError("no non-STARTUP clock work")), \
                        patch.object(B.Admin, "_run", side_effect=AssertionError("no non-STARTUP diagnostic")) as command:
                    owner._set_startup_phase(Unprintable())
                    owner._start_startup_probe(Unprintable())
                    owner._startup_wait_check()
                    error = B.ContextError("START", "TIMEOUT")
                    owner.attach_startup_failure(error)
                    self.assertEqual(B.public_error(error), "DEPENDENCY_CONTEXT/START/TIMEOUT/NONE")
                    self.assertFalse(hasattr(error, "_startup_diagnostic"))
                    self.assertFalse(any(name.startswith("_startup_") for name in owner.__dict__))
                    self.assertEqual(owner.native.attempts, [])
                    command.assert_not_called()
            finally:
                admin.record.close()
        prototype = object.__new__(B.Foreground)
        prototype._set_startup_phase(Unprintable())
        prototype.attach_startup_failure(B.ContextError("START", "TIMEOUT"))
        self.assertEqual(prototype.__dict__, {})

        absent = ('Could not find service "' + LABEL + '" in domain for system\n').encode("ascii")
        responses = (
            ("running", print_result(print_bytes("running", "105")), "RUNNING", "CODE_105"),
            ("stopped", print_result(print_bytes("not running", "0")), "NOT_RUNNING", "CODE_0"),
            ("scheduled", print_result(print_bytes("spawn scheduled")), "SPAWN_SCHEDULED", "NONE"),
            ("waiting", print_result(print_bytes("waiting")), "WAITING", "NONE"),
            ("unsupported", print_result(print_bytes("another state", "+1")), "UNSUPPORTED", "UNSUPPORTED"),
            ("absent", print_result(b"", code=113, stderr=absent), "REGISTRATION_ABSENT", "NONE"),
            ("invalid", print_result(b"synthetic malformed print\n"), "INVALID", "NONE"),
            ("query_failed", print_result(b"", code=1, stderr=b"synthetic private error\n"), "PRINT_FAILED", "NONE"),
            ("unclosed_return", {**print_result(), "closed": False}, "PRINT_FAILED", "NONE"),
            ("fsync_failed", print_result(), "PRINT_FAILED", "NONE"),
            ("capture_failed", None, "PRINT_FAILED", "NONE"),
            ("already_quarantined", None, "PRINT_FAILED", "NONE"),
        )
        original_run = B.Admin._run
        for phase in ("WAIT_CONNECT", "WAIT_HELLO"):
            for name, result, status, code in responses:
                with self.subTest(phase=phase, response=name):
                    owner, admin = make_owner(phase=phase)
                    clock, unresolved = [100 * NS], object()
                    quarantine = [unresolved] if name == "already_quarantined" else []
                    state_keys = set(owner.current)

                    def capture(argv, end_ns, environment, *, input_raw, stage):
                        self.assertEqual(argv, PRINT_ARGV)
                        self.assertEqual((end_ns, input_raw, stage), (owner.current["end"], b"", "START"))
                        self.assertIs(environment, owner.os_env)
                        self.assertTrue(owner._startup_probe_consumed)
                        if name == "capture_failed":
                            quarantine.append(unresolved)  # Models the existing capture_fixed quarantine only.
                            raise B.ContextError("START", "TIMEOUT")
                        return result

                    def command(original, argv, stage, **kwargs):
                        self.assertIs(original, admin)
                        self.assertTrue(owner._startup_probe_consumed)  # Before even _allowed / quarantine checks.
                        self.assertEqual((argv, stage, kwargs),
                                         (["/bin/launchctl", "print", "system/" + LABEL], "START", {"success": False}))
                        return original_run(original, argv, stage, **kwargs)

                    try:
                        with patch.object(B, "shared_raw_ns", side_effect=lambda: clock[0]), \
                                patch.object(B, "_UNCLOSED_COMMANDS", quarantine), \
                                patch.object(B, "capture_fixed", side_effect=capture) as captured, \
                                patch.object(B.os, "fsync", side_effect=OSError(errno.EIO, "synthetic private fsync error")
                                             if name == "fsync_failed" else None) as fsync, \
                                patch.object(B.Admin, "_run", autospec=True, side_effect=command) as commanded:
                            owner._start_startup_probe(owner.current["end"])
                            clock[0] = 130 * NS
                            with self.assertRaises(B.ContextError) as caught:
                                owner._startup_wait_check()
                            rendered = ("DEPENDENCY_CONTEXT/START/STARTUP_OBSERVATION_ONLY/NONE/" +
                                        phase + "/" + status + "/" + code)
                            self.assertEqual(B.public_error(caught.exception), rendered)
                            self.assertEqual(caught.exception.details, {})
                            self.assertEqual(admin.calls, 105 if name == "already_quarantined" else 106)
                            self.assertTrue(owner._startup_probe_consumed)
                            self.assertEqual(owner._startup_probe_end, 130 * NS)
                            self.assertEqual(commanded.call_count, 1)
                            commanded.assert_called_once_with(admin, ["/bin/launchctl", "print", "system/" + LABEL],
                                                              "START", success=False)
                            self.assertEqual(captured.call_count, int(name != "already_quarantined"))
                            if result is not None:
                                fsync.assert_called_once_with(999)
                                rows = admin.record.getvalue().splitlines(keepends=True)
                                self.assertEqual(len(rows), 1)
                                row = B.parsed(rows[0])
                                self.assertEqual((row["ordinal"], row["argv"], row["code"]),
                                                 (106, PRINT_ARGV, result["code"]))
                                self.assertEqual((row["stdoutHex"], row["stderrHex"]),
                                                 (result["stdout"].hex(), result["stderr"].hex()))
                                self.assertEqual(admin.written, len(rows[0]))
                            else:
                                fsync.assert_not_called()
                                self.assertEqual(admin.record.getvalue(), b"")
                            if name in ("capture_failed", "already_quarantined"):
                                self.assertEqual(quarantine, [unresolved])
                            else:
                                self.assertEqual(quarantine, [])
                            before_calls, before_ledger = admin.calls, admin.record.getvalue()
                            with self.assertRaises(B.ContextError) as replay:
                                owner._startup_wait_check()
                            self.assertEqual(replay.exception.reason, "DIAGNOSTIC_STATE")
                            self.assertEqual(commanded.call_count, 1)
                            self.assertEqual((admin.calls, admin.record.getvalue()), (before_calls, before_ledger))
                            owner._set_startup_phase("RETIRE")
                            owner.attach_startup_failure(caught.exception)
                            self.assertEqual(B.public_error(caught.exception), rendered)
                            self.assertEqual(set(owner.current), state_keys)
                            self.assertIs(owner.current["admin"], admin)
                            self.assertIsNone(owner.current["service"])
                            self.assertIsNone(owner.current["producer"])
                            self.assertFalse(owner.current["prepareSent"] or owner.current["started"])
                            self.assertIsNone(admin.service)
                            self.assertFalse(admin.retired or admin.removed or admin.closed)
                            self.assertFalse(owner.finished or owner.failed or owner._aborted)
                            self.assertEqual(owner.native.attempts, [])
                    finally:
                        admin.record.close()

        # No late phase, replaced original Admin, admitted peer or START state
        # can use this pre-HELLO diagnostic. Rejection precedes consumption.
        mutations = (
            lambda owner, admin: owner._set_startup_phase("HELLO_CHECK"),
            lambda owner, admin: owner._set_startup_phase("WAIT_FINAL"),
            lambda owner, admin: owner.current.update(admin=object()),
            lambda owner, admin: setattr(admin, "context", object()),
            lambda owner, admin: setattr(admin, "directory", Path("/controlled/foreign")),
            lambda owner, admin: setattr(admin, "end_ns", 999 * NS),
            lambda owner, admin: setattr(admin, "bootstrapped", False),
            lambda owner, admin: setattr(admin, "closed", True),
            lambda owner, admin: setattr(admin, "service", {}),
            lambda owner, admin: setattr(admin, "path", None),
            lambda owner, admin: setattr(admin, "arguments", [LAUNCHER, "extra"]),
            lambda owner, admin: owner.current.update(service={}),
            lambda owner, admin: owner.current.update(producer={}),
            lambda owner, admin: owner.current.update(prepareSent=True),
            lambda owner, admin: owner.current.update(started=True),
        )
        for index, mutate in enumerate(mutations):
            owner, admin = make_owner()
            owner._startup_probe_end = 130 * NS
            mutate(owner, admin)
            try:
                with self.subTest(ineligible=index), patch.object(B, "shared_raw_ns", return_value=130 * NS), \
                        patch.object(B.Admin, "_run", side_effect=AssertionError("ineligible probe")) as command, \
                        self.assertRaises(B.ContextError) as caught:
                    owner._startup_wait_check()
                self.assertEqual(caught.exception.reason, "DIAGNOSTIC_STATE")
                self.assertFalse(owner._startup_probe_consumed)
                self.assertEqual(admin.calls, 105)
                self.assertEqual(owner.native.attempts, [])
                command.assert_not_called()
            finally:
                admin.record.close()

        for phase in PHASES:
            for native_errno in ("NONE", "ETIMEDOUT"):
                owner, admin = make_owner(phase=phase)
                error, observed = B.ContextError("START", "TIMEOUT", native_errno), []
                expected = "DEPENDENCY_CONTEXT/START/TIMEOUT/" + native_errno + "/" + phase + "/NOT_OBSERVED/NONE"

                def abort():
                    observed.append(B.public_error(error))
                    owner._set_startup_phase("RETIRE")
                    owner._aborted = True

                try:
                    with patch.object(owner, "_run_current_case", side_effect=error), \
                            patch.object(owner, "abort", side_effect=abort) as aborted, \
                            self.assertRaises(B.ContextError) as caught:
                        owner.run_case("STARTUP", DIRECTORY / "case-input.json")
                    self.assertIs(caught.exception, error)
                    self.assertEqual(observed, [expected])
                    self.assertEqual(B.public_error(error), expected)
                    self.assertTrue(owner.failed and owner._aborted)
                    self.assertEqual(owner._startup_phase, "RETIRE")
                    aborted.assert_called_once_with()
                    self.assertFalse(admin.closed or admin.retired or admin.removed)
                    self.assertEqual(owner.native.attempts, [])
                finally:
                    admin.record.close()

    def test_source_phase_boundaries_exact_inverses_and_registrations(self):
        # Source DATA only: do not import old suites, callers, canonical helpers
        # or extracted snippets. Exact inverse bytes preserve their old guards.
        source = before_initgroups_module(self, (ROOT / BRIDGE).read_bytes()).decode("utf-8")
        shared_raw, startup_raw = before_initgroups_tests(
            self, (ROOT / SHARED).read_bytes(), (ROOT / STARTUP).read_bytes())
        shared = shared_raw.decode("utf-8")
        begin = b"        # STARTUP_OBSERVATION_INVERSE_BEGIN\n"
        end = b"        # STARTUP_OBSERVATION_INVERSE_END\n"
        self.assertEqual(shared_raw.count(begin), 1)
        self.assertEqual(shared_raw.count(end), 1)
        start, finish = shared_raw.index(begin), shared_raw.index(end) + len(end)
        self.assertLess(start, finish)
        adapter = shared_raw[start:finish]
        self.assertEqual(len(adapter), SHARED_DELTA_BYTES)
        self.assertEqual(hashlib.sha256(adapter).hexdigest(), SHARED_DELTA_SHA256)
        self.assertEqual(shared_raw.count(b"        source = BS.text\n" + begin), 1)
        restored_shared = shared_raw[:start] + shared_raw[finish:]
        self.assertEqual(hashlib.sha256(restored_shared).hexdigest(), BASELINE[SHARED])
        method = definition(shared, "test_ordered_inspector_structure_and_module_inverse_match_exact_b42",
                            "LauncherMachoDiagnosticControls")
        self.assertIn(adapter.decode("utf-8"), ast.get_source_segment(shared, method))
        assignments = [node for node in method.body if isinstance(node, ast.Assign) and
                       len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and
                       node.targets[0].id == "startup_inverse"]
        self.assertEqual(len(assignments), 1)
        inverse = ast.literal_eval(assignments[0].value)
        self.assertIs(type(inverse), tuple)
        self.assertEqual(len(inverse), 23)
        restored = source
        for index, pair in enumerate(inverse):
            with self.subTest(inverse=index):
                self.assertIs(type(pair), tuple)
                self.assertEqual(len(pair), 2)
                before, after = pair
                self.assertIs(type(before), str)
                self.assertIs(type(after), str)
                self.assertTrue(before)
                self.assertEqual(restored.count(before), 1)
                restored = restored.replace(before, after, 1)
        self.assertEqual(hashlib.sha256(restored.encode("utf-8")).hexdigest(), BASELINE[BRIDGE])
        for historical in ("a09e8405a13297c898e9263de8901ec222c67b12eb480c23572d3a6c5c58c309",
                           "54876ad6c013683164f4d500c396114b3419a5b4ba6a2e4afb22855e25b47259"):
            self.assertEqual(shared.count(historical), 1)
        startup = startup_raw.decode("utf-8")
        self.assertEqual(startup.count(STARTUP_PIN_ADAPTER), 1)
        restored_startup = startup.replace(STARTUP_PIN_ADAPTER, STARTUP_PIN_ORIGINAL, 1)
        self.assertEqual(hashlib.sha256(restored_startup.encode("utf-8")).hexdigest(), BASELINE[STARTUP])
        pinned = [node for node in ast.parse(startup).body if isinstance(node, ast.Assign) and
                  len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and
                  node.targets[0].id == "PINNED_READONLY"]
        self.assertEqual(len(pinned), 1)
        self.assertEqual(ast.literal_eval(pinned[0].value)[SHARED], BASELINE[SHARED])
        caller = (ROOT / CALLER).read_text(encoding="utf-8")
        self.assertEqual(caller.count(CALLER_HOOK), 1)
        restored_caller = caller.replace(CALLER_HOOK, CALLER_ORIGINAL, 1)
        self.assertEqual(hashlib.sha256(restored_caller.encode("utf-8")).hexdigest(), BASELINE[CALLER])
        launcher = original_setgroups_launcher(self, before_initgroups_launcher(
            self, (ROOT / "scripts/hosted_dependency_context_launcher.c").read_bytes()))
        self.assertEqual(hashlib.sha256(launcher).hexdigest(),
                         "91e07782141b85b181a9a143c8a717b92b023a22719f7255a005d034cf03c814")

        # The original shared frame/native-administration mechanisms are byte
        # identical, not replaced by the synthetic models in these controls.
        for name, owner in (("read_frame", None), ("parse_service_print", None), ("capture_fixed", None),
                            ("service_absent", None), ("_allowed", "Admin"), ("_run", "Admin"),
                            ("bootstrap", "Admin"), ("retire", "Admin")):
            self.assertEqual(ast.get_source_segment(source, definition(source, name, owner)),
                             ast.get_source_segment(restored, definition(restored, name, owner)))

        def calls(node, receiver, name):
            return sorted((item for item in ast.walk(node) if isinstance(item, ast.Call) and
                           isinstance(item.func, ast.Attribute) and item.func.attr == name and
                           isinstance(item.func.value, ast.Name) and item.func.value.id == receiver),
                          key=lambda item: item.lineno)

        prepare = definition(source, "prepare_case", "Foreground")
        self.assertEqual(ast.get_source_segment(source, prepare.body[0]), 'self._set_startup_phase("PREPARE_CASE")')
        current = definition(source, "_run_current_case", "Foreground")
        phases = calls(current, "self", "_set_startup_phase")
        self.assertEqual([ast.literal_eval(node.args[0]) for node in phases], list(PHASES[1:]))
        self.assertTrue(all(len(node.args) == 1 and not node.keywords for node in phases))
        self.assertEqual(ast.get_source_segment(source, current.body[0]), 'self._set_startup_phase("INPUTS_AND_ADMIN")')
        bootstrap = calls(current, "admin", "bootstrap")
        self.assertEqual(len(bootstrap), 1)
        bootstrap_index = next(index for index, node in enumerate(current.body)
                               if isinstance(node, ast.Expr) and node.value is bootstrap[0])
        self.assertEqual(ast.get_source_segment(source, current.body[bootstrap_index - 1]),
                         'self._set_startup_phase("BOOTSTRAP")')
        self.assertEqual(ast.get_source_segment(source, current.body[bootstrap_index + 1]),
                         "self._start_startup_probe(end_ns)")
        self.assertEqual(ast.get_source_segment(source, current.body[bootstrap_index + 2]),
                         'self._set_startup_phase("WAIT_CONNECT")')
        accept = current.body[bootstrap_index + 3]
        self.assertIsInstance(accept, ast.While)
        self.assertEqual(ast.get_source_segment(source, accept.test), 'state["channel"] is None')
        ready = accept.body[1]
        self.assertIsInstance(ready, ast.If)
        self.assertEqual(ast.get_source_segment(source, ready.test), "ready")
        self.assertEqual(ast.get_source_segment(source, ready.body[0]), "channel, _address = listener.accept()")
        self.assertEqual(len(ready.orelse), 1)
        self.assertIsInstance(ready.orelse[0], ast.If)
        self.assertEqual(ast.get_source_segment(source, ready.orelse[0].test), "self.profile is STARTUP")
        self.assertEqual(ast.get_source_segment(source, ready.orelse[0].body[0]), "self._startup_wait_check()")
        self.assertEqual(len(calls(current, "self", "_startup_wait_check")), 1)
        self.assertEqual(len(calls(current, "self", "_read_startup_hello")), 1)

        hello = definition(source, "_read_startup_hello", "Foreground")
        waiting = [node for node in hello.body if isinstance(node, ast.While)]
        self.assertEqual(len(waiting), 1)
        self.assertEqual(ast.get_source_segment(source, waiting[0].body[0]), "reader.poll()")
        self.assertEqual(ast.get_source_segment(source, waiting[0].body[1]),
                         'require(not reader.eof, "START", "STATUS_MISSING")')
        self.assertIsInstance(waiting[0].body[2], ast.If)
        self.assertEqual(ast.get_source_segment(source, waiting[0].body[2].test), "reader.value is None")
        self.assertEqual(ast.get_source_segment(source, waiting[0].body[2].body[0]), "self._startup_wait_check()")
        self.assertEqual(ast.get_source_segment(source, hello.body[-2]), "left(end_ns)")
        self.assertEqual(ast.get_source_segment(source, hello.body[-1]), "return reader.value")
        wait = definition(source, "_startup_wait_check", "Foreground")
        consume = [node for node in wait.body if isinstance(node, ast.Assign) and
                   any(isinstance(target, ast.Attribute) and target.attr == "_startup_probe_consumed"
                       for target in node.targets)]
        print_calls = calls(wait, "admin", "_run")
        self.assertEqual((len(consume), len(print_calls)), (1, 1))
        self.assertIs(ast.literal_eval(consume[0].value), True)
        self.assertLess(consume[0].lineno, print_calls[0].lineno)
        self.assertIsInstance(wait.body[-1], ast.Raise)
        self.assertEqual(ast.get_source_segment(source, wait.body[-1]), "raise error")
        for helper in ("_set_startup_phase", "attach_startup_failure", "_start_startup_probe",
                       "_startup_wait_check", "_read_startup_hello"):
            self.assertNotIn("self.native", ast.get_source_segment(source, definition(source, helper, "Foreground")))
        run = definition(source, "run_case", "Foreground")
        handlers = [item for item in ast.walk(run) if isinstance(item, ast.ExceptHandler)]
        self.assertEqual(len(handlers), 1)
        self.assertEqual(ast.get_source_segment(source, handlers[0].body[0]), "self.attach_startup_failure(error)")
        self.assertLess(calls(handlers[0], "self", "attach_startup_failure")[0].lineno,
                        calls(handlers[0], "self", "abort")[0].lineno)

        registrations = {
            "scripts/run-release-gate.sh": "python3 -I -B -S " + THIS + " -v -f",
            "scripts/tests/release-workflow-test.sh": 'python3 -I -B -S "$ROOT/' + THIS + '" -v -f',
        }
        for relative, line in registrations.items():
            text = (ROOT / relative).read_text(encoding="utf-8")
            self.assertEqual(text.count(THIS), 1)
            self.assertEqual(text.splitlines().count(line), 1)
        own = ast.parse((ROOT / THIS).read_text(encoding="utf-8"))
        classes = [node for node in own.body if isinstance(node, ast.ClassDef) and node.name == "StartupObservationControls"]
        self.assertEqual(len(classes), 1)
        self.assertEqual({node.name for node in classes[0].body if isinstance(node, ast.FunctionDef)}, {
            "test_finite_projection_and_exact_registration_parser",
            "test_original_ready_first_flow_and_shared_raw_deadline",
            "test_original_one_shot_admin_refusal_and_pre_abort_capture",
            "test_source_phase_boundaries_exact_inverses_and_registrations",
        })


def original_setgroups_launcher(testcase, source):
    """Source DATA only: reverse exactly the three failure-diagnostic literals."""
    testcase.assertIs(type(source), bytes)
    inverse = (
        (
            b"#include <libproc.h>\n#include <limits.h>\n",
            b"#include <libproc.h>\n",
        ),
        (
            b"    EXEC_FAILED = 112,\n"
            b"    SETGROUPS_EINVAL_OVER_SDK_LIMIT = 113,\n"
            b"    SETGROUPS_EINVAL_WITHIN_SDK_LIMIT = 114,\n"
            b"    SETGROUPS_EPERM = 115\n",
            b"    EXEC_FAILED = 112\n",
        ),
        (
            b"    if (setgroups(P2PKIT_GROUP_COUNT, P2PKIT_GROUPS) != 0) {\n"
            b"        const int saved_errno = errno;\n"
            b"        if (saved_errno == EINVAL) {\n"
            b"            refuse(P2PKIT_GROUP_COUNT > NGROUPS_MAX ?\n"
            b"                   SETGROUPS_EINVAL_OVER_SDK_LIMIT : SETGROUPS_EINVAL_WITHIN_SDK_LIMIT);\n"
            b"        }\n"
            b"        if (saved_errno == EPERM) {\n"
            b"            refuse(SETGROUPS_EPERM);\n"
            b"        }\n"
            b"        refuse(SETGROUPS_FAILED);\n"
            b"    }\n",
            b"    if (setgroups(P2PKIT_GROUP_COUNT, P2PKIT_GROUPS) != 0) {\n"
            b"        refuse(SETGROUPS_FAILED);\n"
            b"    }\n",
        ),
    )
    testcase.assertEqual(len(inverse), 3)
    for revised, original in inverse:
        testcase.assertEqual(source.count(revised), 1)
        source = source.replace(revised, original, 1)
    return source


class LauncherSetgroupsDiagnosticControls(unittest.TestCase):
    """Historical source3d diagnostics after reversing only the reviewed repair."""

    def test_failed_setgroups_mapping_is_closed_and_errno_is_captured_first(self):
        source = before_initgroups_launcher(self, (ROOT / "scripts/hosted_dependency_context_launcher.c").read_bytes())
        enumeration = (
            b"enum failure {\n"
            b"    BAD_ENTRY = 100,\n"
            b"    BAD_CONFIG = 101,\n"
            b"    SETGROUPS_FAILED = 102,\n"
            b"    SETGID_FAILED = 103,\n"
            b"    SETUID_FAILED = 104,\n"
            b"    IDENTITY_FAILED = 105,\n"
            b"    GROUPS_FAILED = 106,\n"
            b"    ROOT_REACQUIRED = 107,\n"
            b"    FD_LIST_FAILED = 108,\n"
            b"    FD_CLOSE_FAILED = 109,\n"
            b"    STDIO_FAILED = 110,\n"
            b"    CHDIR_FAILED = 111,\n"
            b"    EXEC_FAILED = 112,\n"
            b"    SETGROUPS_EINVAL_OVER_SDK_LIMIT = 113,\n"
            b"    SETGROUPS_EINVAL_WITHIN_SDK_LIMIT = 114,\n"
            b"    SETGROUPS_EPERM = 115\n"
            b"};\n"
        )
        failure = (
            b"    if (setgroups(P2PKIT_GROUP_COUNT, P2PKIT_GROUPS) != 0) {\n"
            b"        const int saved_errno = errno;\n"
            b"        if (saved_errno == EINVAL) {\n"
            b"            refuse(P2PKIT_GROUP_COUNT > NGROUPS_MAX ?\n"
            b"                   SETGROUPS_EINVAL_OVER_SDK_LIMIT : SETGROUPS_EINVAL_WITHIN_SDK_LIMIT);\n"
            b"        }\n"
            b"        if (saved_errno == EPERM) {\n"
            b"            refuse(SETGROUPS_EPERM);\n"
            b"        }\n"
            b"        refuse(SETGROUPS_FAILED);\n"
            b"    }\n"
        )
        self.assertEqual(source.count(b"#include <limits.h>\n"), 1)
        self.assertEqual(source.count(b"#include <libproc.h>\n#include <limits.h>\n"), 1)
        self.assertEqual(source.count(b"enum failure {\n"), 1)
        self.assertEqual(source.count(enumeration), 1)
        self.assertEqual(source.count(failure), 1)
        self.assertEqual(source.count(b"    check_stdio();\n" + failure +
                                      b"    if (setgid(P2PKIT_GID) != 0) {\n"), 1)
        self.assertEqual(source.count(b"setgroups("), 1)
        self.assertEqual(source.count(b"saved_errno"), 3)
        self.assertEqual(source.count(b"NGROUPS_MAX"), 1)
        self.assertEqual(re.findall(rb"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", failure),
                         [b"if", b"setgroups", b"if", b"refuse", b"if", b"refuse", b"refuse"])

    def test_diagnostic_delta_reverses_to_original_complete_launcher(self):
        source = before_initgroups_launcher(self, (ROOT / "scripts/hosted_dependency_context_launcher.c").read_bytes())
        restored = original_setgroups_launcher(self, source)
        self.assertEqual(hashlib.sha256(restored).hexdigest(),
                         "91e07782141b85b181a9a143c8a717b92b023a22719f7255a005d034cf03c814")


def before_initgroups_module(testcase, source):
    """Reverse approved window DATA, then the unchanged two initgroups deletions."""
    testcase.assertIs(type(source), bytes)
    # POLICY_WINDOW_RENEWAL_MODULE_INVERSE_BEGIN
    # Keep the old initgroups inverse and every historical result pin unchanged.
    renewal_inverse = (
        (
            b'POLICY_SHA256 = "a1e4cc4862d46d7887b9cf41e73127939f41342042afe0aee00c3b603b38953b"\n',
            b'POLICY_SHA256 = "2e90a1ed038d5bb6759d8d22e1bb5468331b49274a6956df470c1e785691f521"\n',
        ),
        (
            b'POLICY_EXPIRES = 1792520760\n',
            b'POLICY_EXPIRES = 1791158400\n',
        ),
    )
    for revised, original in renewal_inverse:
        testcase.assertEqual(source.count(revised), 1)
        source = source.replace(revised, original, 1)
    testcase.assertEqual(hashlib.sha256(source).hexdigest(),
                         "a4e12e68f7943d4fdffe631635ce5c317d0f57448d3d3a9b5e059f8386d797e9")
    # POLICY_WINDOW_RENEWAL_MODULE_INVERSE_END
    inverse = (
        (
            b"    username = getattr(context, \"username\", None)\n"
            b"    require(type(username) is str and re.fullmatch(r\"[A-Za-z_][A-Za-z0-9_-]{0,63}\", username),\n"
            b"            \"IDENTITY\", \"IDENTITY_CHANGED\")\n"
            b"    try:\n"
            b"        records = (pwd.getpwuid(context.account[\"uid\"]), pwd.getpwnam(username))\n"
            b"    except (KeyError, OSError):\n"
            b"        raise ContextError(\"IDENTITY\", \"IDENTITY_CHANGED\") from None\n"
            b"    # Rejoin the captured name; never adopt replacement numeric account values.\n"
            b"    for record in records:\n"
            b"        name, uid, gid = (getattr(record, field, None) for field in (\"pw_name\", \"pw_uid\", \"pw_gid\"))\n"
            b"        require(type(name) is str and name == username and\n"
            b"                type(uid) is int and uid == context.account[\"uid\"] and\n"
            b"                type(gid) is int and gid == context.account[\"gid\"], \"IDENTITY\", \"IDENTITY_CHANGED\")\n",
            b"",
        ),
        (
            b"            \"static const char P2PKIT_USERNAME[] = \" + literal(username) + \";\",\n",
            b"",
        ),
    )
    testcase.assertEqual(len(inverse), 2)
    for revised, original in inverse:
        testcase.assertEqual(source.count(revised), 1)
        source = source.replace(revised, original, 1)
    testcase.assertEqual(hashlib.sha256(source).hexdigest(),
                         "8dcc0f5f3cfd5d48f0fe5f2ba844a1406085f53efb9e48b4b3ec751d8977af60")
    return source


def before_policy_window_tests(testcase, shared, startup):
    """Close only the reviewed renewal adapters as DATA before historical inverses."""
    testcase.assertIs(type(shared), bytes)
    testcase.assertIs(type(startup), bytes)
    begin = b"                    # POLICY_WINDOW_RENEWAL_SHARED_INVERSE_BEGIN\n"
    end = b"                    # POLICY_WINDOW_RENEWAL_SHARED_INVERSE_END\n"
    testcase.assertEqual(startup.count(begin), 1)
    testcase.assertEqual(startup.count(end), 1)
    start, finish = startup.index(begin), startup.index(end) + len(end)
    testcase.assertLess(start, finish)
    adapter = startup[start:finish]
    testcase.assertEqual(len(adapter), 4238)
    testcase.assertEqual(hashlib.sha256(adapter).hexdigest(),
                         "3d77ec29b522b5383e60c6a31821930226b86777012ad402de4973efbf0161d6")
    testcase.assertEqual(startup.count(
        b'                if relative == "scripts/tests/hosted-dependency-update-context-test.py":\n' + begin), 1)
    testcase.assertEqual(startup.count(adapter + b"                    # INITGROUPS_SHARED_INVERSE_BEGIN\n"), 1)
    assignments = [node for node in ast.walk(ast.parse(startup.decode("utf-8"))) if isinstance(node, ast.Assign) and
                   len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and
                   node.targets[0].id == "renewal_shared_inverse"]
    testcase.assertEqual(len(assignments), 1)
    inverse = ast.literal_eval(assignments[0].value)
    testcase.assertIs(type(inverse), tuple)
    testcase.assertEqual(len(inverse), 4)
    for pair in inverse:
        testcase.assertIs(type(pair), tuple)
        testcase.assertEqual(len(pair), 2)
        revised, original = pair
        testcase.assertIs(type(revised), str)
        testcase.assertIs(type(original), str)
        testcase.assertTrue(revised)
        revised, original = revised.encode("utf-8"), original.encode("utf-8")
        testcase.assertEqual(shared.count(revised), 1)
        shared = shared.replace(revised, original, 1)
    testcase.assertEqual(hashlib.sha256(shared).hexdigest(),
                         "ae473ff2033784eb39b622ed2a6d2fd587ae17de245932122c47242a9f5f7403")
    restored_startup = startup[:start] + startup[finish:]
    revised = b"        self.assertEqual(B.POLICY_EXPIRES, 1792520760)\n"
    original = b"        self.assertEqual(B.POLICY_EXPIRES, 1791158400)\n"
    testcase.assertEqual(restored_startup.count(revised), 1)
    restored_startup = restored_startup.replace(revised, original, 1)
    testcase.assertEqual(hashlib.sha256(restored_startup).hexdigest(),
                         "9410f39b9c7ad205aa28df4c684b97099c2089729463413a8c33c6a05cab2a27")
    return shared, restored_startup


def before_initgroups_tests(testcase, shared, startup):
    """Read the exact inverse table as DATA; neither control suite is imported."""
    testcase.assertIs(type(shared), bytes)
    testcase.assertIs(type(startup), bytes)
    shared, startup = before_policy_window_tests(testcase, shared, startup)
    begin = b"                    # INITGROUPS_SHARED_INVERSE_BEGIN\n"
    end = b"                    # INITGROUPS_SHARED_INVERSE_END\n"
    testcase.assertEqual(startup.count(begin), 1)
    testcase.assertEqual(startup.count(end), 1)
    start, finish = startup.index(begin), startup.index(end) + len(end)
    testcase.assertLess(start, finish)
    adapter = startup[start:finish]
    # This is the new reviewed adapter's byte binding, never a replacement for
    # the immediate source3d or historical acceptance pins below.
    testcase.assertEqual(len(adapter), 17690)
    testcase.assertEqual(hashlib.sha256(adapter).hexdigest(),
                         "175c1a25b5ac98b73c7e0ed09bfa03f598b2a08dd75ebfed814fa59f8ca50a44")
    testcase.assertEqual(startup.count(
        b'                if relative == "scripts/tests/hosted-dependency-update-context-test.py":\n' + begin), 1)
    testcase.assertEqual(startup.count(adapter +
        b'                    begin = b"        # STARTUP_OBSERVATION_INVERSE_BEGIN\\n"\n'), 1)
    restored_startup = startup[:start] + startup[finish:]
    testcase.assertEqual(hashlib.sha256(restored_startup).hexdigest(),
                         "c2b1ac01f06f95be2e1be093a9ce99ee4b042b91c9a9630dd3aeb815604d0d27")
    assignments = [node for node in ast.walk(ast.parse(startup.decode("utf-8"))) if isinstance(node, ast.Assign) and
                   len(node.targets) == 1 and isinstance(node.targets[0], ast.Name) and
                   node.targets[0].id == "initgroups_shared_inverse"]
    testcase.assertEqual(len(assignments), 1)
    inverse = ast.literal_eval(assignments[0].value)
    testcase.assertIs(type(inverse), tuple)
    testcase.assertEqual(len(inverse), 7)
    for pair in inverse:
        testcase.assertIs(type(pair), tuple)
        testcase.assertEqual(len(pair), 2)
        revised, original = pair
        testcase.assertIs(type(revised), str)
        testcase.assertIs(type(original), str)
        testcase.assertTrue(revised)
        revised, original = revised.encode("utf-8"), original.encode("utf-8")
        testcase.assertEqual(shared.count(revised), 1)
        shared = shared.replace(revised, original, 1)
    testcase.assertEqual(hashlib.sha256(shared).hexdigest(),
                         "079310f8dc129f56ed8b719c1498f6084a7b279b46d78841b43cfca142ffdbb7")
    return shared, restored_startup


def before_initgroups_launcher(testcase, source):
    """Exact full current-to-source3d inverse; no C evaluation or native claim."""
    testcase.assertIs(type(source), bytes)
    inverse = (
        (
            b" * Privileged lookups use only fixed supported account/group APIs and the trusted\n"
            b" * configured OS resolver/IPC path. No arbitrary network command, project\n"
            b" * interpreter, project file or caller-selected command is entered as root.\n"
            b" * Every failure exits without cleanup or diagnostics.\n",
            b" * No project interpreter, project file, network or caller-selected command is\n"
            b" * entered while privileged. Every failure exits without cleanup or diagnostics.\n",
        ),
        (
            b"#include <fcntl.h>\n#include <grp.h>\n#include <libproc.h>\n#include <limits.h>\n#include <pwd.h>\n",
            b"#include <fcntl.h>\n#include <libproc.h>\n#include <limits.h>\n",
        ),
        (
            b"    SETGROUPS_EPERM = 115,\n    ACCOUNT_LOOKUP_FAILED = 116,\n    INITGROUPS_FAILED = 117\n",
            b"    SETGROUPS_EPERM = 115\n",
        ),
        (
            b"_Static_assert(sizeof(P2PKIT_USERNAME) > 1 && sizeof(P2PKIT_USERNAME) <= 65,\n"
            b"               \"The bound account name must contain one to 64 bytes\");\n",
            b"",
        ),
        (
            b"    if (strlen(P2PKIT_USERNAME) != sizeof(P2PKIT_USERNAME) - 1) {\n"
            b"        refuse(BAD_CONFIG);\n    }\n",
            b"",
        ),
        (
            b"static void\ncheck_account(void)\n{\n"
            b"    char buffer[16 * 1024];\n"
            b"    struct passwd record = {0};\n"
            b"    struct passwd *result = NULL;\n\n"
            b"    /* Observe each record before reusing storage; these joins are not atomic. */\n"
            b"    if (getpwuid_r(P2PKIT_UID, &record, buffer, sizeof(buffer), &result) != 0 ||\n"
            b"        result == NULL || result->pw_name == NULL || result->pw_uid != P2PKIT_UID ||\n"
            b"        result->pw_gid != P2PKIT_GID || strcmp(result->pw_name, P2PKIT_USERNAME) != 0) {\n"
            b"        refuse(ACCOUNT_LOOKUP_FAILED);\n    }\n"
            b"    result = NULL;\n"
            b"    if (getpwnam_r(P2PKIT_USERNAME, &record, buffer, sizeof(buffer), &result) != 0 ||\n"
            b"        result == NULL || result->pw_name == NULL || result->pw_uid != P2PKIT_UID ||\n"
            b"        result->pw_gid != P2PKIT_GID || strcmp(result->pw_name, P2PKIT_USERNAME) != 0) {\n"
            b"        refuse(ACCOUNT_LOOKUP_FAILED);\n    }\n}\n\n",
            b"",
        ),
        (
            b"    /* All application lookup calls precede this fail-closed close/recheck.\n"
            b"     * OS libraries may retain internal threads, handlers or other resources.\n"
            b"     * This application introduces no close retries.\n     */\n",
            b"    /* This prelude creates no threads, handlers or descriptors. No retries. */\n",
        ),
        (
            b"    check_account();\n"
            b"    if (initgroups(P2PKIT_USERNAME, P2PKIT_GID) != 0) {\n"
            b"        refuse(INITGROUPS_FAILED);\n    }\n",
            b"    if (setgroups(P2PKIT_GROUP_COUNT, P2PKIT_GROUPS) != 0) {\n"
            b"        const int saved_errno = errno;\n"
            b"        if (saved_errno == EINVAL) {\n"
            b"            refuse(P2PKIT_GROUP_COUNT > NGROUPS_MAX ?\n"
            b"                   SETGROUPS_EINVAL_OVER_SDK_LIMIT : SETGROUPS_EINVAL_WITHIN_SDK_LIMIT);\n"
            b"        }\n"
            b"        if (saved_errno == EPERM) {\n"
            b"            refuse(SETGROUPS_EPERM);\n"
            b"        }\n"
            b"        refuse(SETGROUPS_FAILED);\n    }\n",
        ),
        (
            b"    check_ids(P2PKIT_UID, P2PKIT_GID, IDENTITY_FAILED);\n"
            b"    check_account();\n    check_groups();\n",
            b"    check_ids(P2PKIT_UID, P2PKIT_GID, IDENTITY_FAILED);\n    check_groups();\n",
        ),
    )
    testcase.assertEqual(len(inverse), 9)
    for revised, original in inverse:
        testcase.assertEqual(source.count(revised), 1)
        source = source.replace(revised, original, 1)
    testcase.assertEqual(hashlib.sha256(source).hexdigest(),
                         "ef10c1e1aee66dee56d14158e6ad81b1a5d565bd61cdf0b33d3f66302f8b89de")
    return source


class LauncherInitgroupsControls(unittest.TestCase):
    """Inert account/header behavior and C source, never OS lookup qualification."""

    def context(self, username="runner"):
        return types.SimpleNamespace(
            profile=B.STARTUP, account={**ACCOUNT, "groups": list(range(20, 37))}, username=username,
            groupname="staff", interpreter={"path": B.INTERPRETER}, operation=Path("/controlled/operation"),
            tools={"PATH": "/approved/bin", "JAVA_HOME": "/approved/jdk17",
                   "P2PKIT_AUDIT_JDK21": "/approved/jdk21", "DEVELOPER_DIR": B.XCODE_DEVELOPER})

    def record(self, username="runner", uid=501, gid=20):
        # No password, home, shell, directory service or private field exists.
        return types.SimpleNamespace(pw_name=username, pw_uid=uid, pw_gid=gid)

    def test_header_binds_canonical_name_and_all_seventeen_groups(self):
        for username in ("runner", "_Runner-9", "r" * 64):
            context = self.context(username)
            captured = copy.deepcopy(context.account)
            directory = context.operation / "bridge/cases/STARTUP"
            with self.subTest(username_length=len(username)), \
                    patch.object(B, "account", return_value=copy.deepcopy(captured)), \
                    patch.object(B.os, "getuid", return_value=501), \
                    patch.object(B.pwd, "getpwuid", return_value=self.record(username)) as by_uid, \
                    patch.object(B.pwd, "getpwnam", return_value=self.record(username)) as by_name:
                raw = B.launcher_header(context, directory)
                by_uid.assert_called_once_with(501)
                by_name.assert_called_once_with(username)
                environment = B.child_environment(B.STARTUP, context.operation, context.tools)
            self.assertEqual(context.account, captured)
            self.assertEqual(set(context.account), {"uid", "euid", "gid", "egid", "groups"})
            self.assertEqual(raw.count(b"P2PKIT_USERNAME"), 1)
            rows = raw.splitlines()
            name_literal = b'"' + b"".join(("\\%03o" % value).encode("ascii") for value in username.encode("ascii")) + b'"'
            self.assertEqual(rows[1:6], [
                b"#define P2PKIT_UID ((uid_t)501U)", b"#define P2PKIT_GID ((gid_t)20U)",
                b"static const char P2PKIT_USERNAME[] = " + name_literal + b";",
                b"#define P2PKIT_GROUP_COUNT 17",
                b"static const gid_t P2PKIT_GROUPS[256] = {" +
                b", ".join(("(gid_t)" + str(value) + "U").encode("ascii") for value in captured["groups"]) + b"};",
            ])
            literals = re.findall(rb'"((?:\\[0-7]{3})*)"', raw)
            decoded = [bytes(int(value[index + 1:index + 4], 8) for index in range(0, len(value), 4)).decode("utf-8")
                       for value in literals]
            self.assertEqual(decoded, [username, str(ROOT), *B.service_arguments(B.STARTUP, B.INTERPRETER, directory),
                                       *(key + "=" + environment[key] for key in sorted(environment))])
            self.assertLessEqual(len(raw), B.STREAM_BYTES)

    def test_header_refuses_malformed_names_and_missing_or_mismatched_lookup_records(self):
        context = self.context()
        directory = context.operation / "bridge/cases/STARTUP"
        with patch.object(B, "account", return_value=copy.deepcopy(context.account)), \
                patch.object(B.os, "getuid", return_value=501):
            names = (None, True, 1, b"runner", StringSubclass("runner"), Unprintable(), "", "1runner",
                     "runner.name", "runner name", "runner\n", "runner\0", "runnér", "r" * 65)
            for index, name in enumerate(names):
                changed = types.SimpleNamespace(**{**vars(context), "username": name})
                with self.subTest(name_case=index), patch.object(B.pwd, "getpwuid") as by_uid, \
                        patch.object(B.pwd, "getpwnam") as by_name, self.assertRaises(B.ContextError) as caught:
                    B.launcher_header(changed, directory)
                self.assertEqual((caught.exception.stage, caught.exception.reason), ("IDENTITY", "IDENTITY_CHANGED"))
                by_uid.assert_not_called()
                by_name.assert_not_called()
            absent_name = types.SimpleNamespace(**{key: value for key, value in vars(context).items() if key != "username"})
            with patch.object(B.pwd, "getpwuid") as by_uid, patch.object(B.pwd, "getpwnam") as by_name, \
                    self.assertRaises(B.ContextError):
                B.launcher_header(absent_name, directory)
            by_uid.assert_not_called()
            by_name.assert_not_called()

            records = [None, types.SimpleNamespace(), self.record("other"), self.record(uid=502), self.record(gid=21)]
            for field in ("pw_name", "pw_uid", "pw_gid"):
                records.append(types.SimpleNamespace(**{key: value for key, value in vars(self.record()).items()
                                                       if key != field}))
                invalid_values = ((None, True, "501") if field != "pw_name" else
                                  (None, True, StringSubclass("runner")))
                for invalid in invalid_values:
                    records.append(types.SimpleNamespace(**{**vars(self.record()), field: invalid}))
            for endpoint in ("getpwuid", "getpwnam"):
                for index, record in enumerate(records):
                    returns = {"getpwuid": self.record(), "getpwnam": self.record(), endpoint: record}
                    with self.subTest(endpoint=endpoint, record_case=index), \
                            patch.object(B.pwd, "getpwuid", return_value=returns["getpwuid"]) as by_uid, \
                            patch.object(B.pwd, "getpwnam", return_value=returns["getpwnam"]) as by_name, \
                            self.assertRaises(B.ContextError) as caught:
                        B.launcher_header(context, directory)
                    self.assertEqual((caught.exception.stage, caught.exception.reason), ("IDENTITY", "IDENTITY_CHANGED"))
                    by_uid.assert_called_once_with(501)
                    by_name.assert_called_once_with("runner")
                for failure in (KeyError, OSError):
                    with self.subTest(endpoint=endpoint, failure=failure.__name__), \
                            patch.object(B.pwd, "getpwuid", return_value=self.record()) as by_uid, \
                            patch.object(B.pwd, "getpwnam", return_value=self.record()) as by_name, \
                            self.assertRaises(B.ContextError) as caught:
                        (by_uid if endpoint == "getpwuid" else by_name).side_effect = failure
                        B.launcher_header(context, directory)
                    self.assertEqual((caught.exception.stage, caught.exception.reason), ("IDENTITY", "IDENTITY_CHANGED"))
                    by_uid.assert_called_once_with(501)
                    if endpoint == "getpwuid":
                        by_name.assert_not_called()
                    else:
                        by_name.assert_called_once_with("runner")

    def test_repeated_header_refuses_account_drift_and_preserves_compiler_binding_order(self):
        mutations = (
            ("getpwuid", self.record("renamed")), ("getpwuid", self.record(uid=502)),
            ("getpwuid", self.record(gid=21)), ("getpwnam", self.record("renamed")),
            ("getpwnam", self.record(uid=502)), ("getpwnam", self.record(gid=21)),
            ("groups", None),
        )
        for index, (endpoint, replacement) in enumerate(mutations):
            context = self.context()
            captured = copy.deepcopy(context.account)
            directory = context.operation / "bridge/cases/STARTUP"
            with self.subTest(drift=index), patch.object(B, "account", return_value=copy.deepcopy(captured)) as account, \
                    patch.object(B.os, "getuid", return_value=501), \
                    patch.object(B.pwd, "getpwuid", return_value=self.record()) as by_uid, \
                    patch.object(B.pwd, "getpwnam", return_value=self.record()) as by_name:
                first = B.launcher_header(context, directory)
                self.assertIn(b"#define P2PKIT_GROUP_COUNT 17", first)
                by_uid.reset_mock()
                by_name.reset_mock()
                if endpoint == "groups":
                    account.return_value = {**captured, "groups": captured["groups"][:-1]}
                else:
                    (by_uid if endpoint == "getpwuid" else by_name).return_value = replacement
                with self.assertRaises(B.ContextError) as caught:
                    B.launcher_header(context, directory)
                self.assertEqual((caught.exception.stage, caught.exception.reason), ("IDENTITY", "IDENTITY_CHANGED"))
                self.assertEqual(context.account, captured)
                if endpoint == "groups":
                    by_uid.assert_not_called()
                    by_name.assert_not_called()
                else:
                    by_uid.assert_called_once_with(501)
                    by_name.assert_called_once_with("runner")

        source = (ROOT / BRIDGE).read_bytes()
        restored = before_initgroups_module(self, source).decode("utf-8")
        current = source.decode("utf-8")
        prepare = definition(current, "prepare_launcher")
        body = ast.get_source_segment(current, prepare)
        self.assertEqual(body, ast.get_source_segment(restored, definition(restored, "prepare_launcher")))
        calls = sorted((node for node in ast.walk(prepare) if isinstance(node, ast.Call) and
                        isinstance(node.func, ast.Name) and node.func.id == "launcher_header"), key=lambda node: node.lineno)
        self.assertEqual(len(calls), 2)
        self.assertTrue(all(ast.get_source_segment(current, node) == "launcher_header(context, directory)" for node in calls))
        self.assertLess(body.index("header = launcher_header(context, directory)"), body.index("common = [str(compiler)"))
        self.assertLess(body.index("command([*common, \"--ld-path=\""), body.index("launcher_header(context, directory) == header"))
        self.assertIn("read_file(directory / \"launcher.c\") == source and read_file(directory / LAUNCHER_HEADER) == header", body)

    def test_native_lookup_guards_single_initgroups_and_complete_drop_inverse(self):
        source = (ROOT / "scripts/hosted_dependency_context_launcher.c").read_bytes()
        restored = before_initgroups_launcher(self, source)
        # The original diagnostic/full-drop source remains independently bound.
        self.assertEqual(hashlib.sha256(original_setgroups_launcher(self, restored)).hexdigest(),
                         "91e07782141b85b181a9a143c8a717b92b023a22719f7255a005d034cf03c814")
        text = source.decode("ascii")
        self.assertEqual(text.count("static void\ncheck_account(void)\n"), 1)
        helper = text.split("static void\ncheck_account(void)\n", 1)[1].split("\nstatic void\ncheck_ids", 1)[0]
        self.assertEqual(helper.count("char buffer[16 * 1024];"), 1)
        self.assertEqual(helper.count("struct passwd record = {0};"), 1)
        self.assertEqual(helper.count("result = NULL;"), 2)
        for function, identity in (("getpwuid_r", "P2PKIT_UID"), ("getpwnam_r", "P2PKIT_USERNAME")):
            guard = ("    if (" + function + "(" + identity + ", &record, buffer, sizeof(buffer), &result) != 0 ||\n"
                     "        result == NULL || result->pw_name == NULL || result->pw_uid != P2PKIT_UID ||\n"
                     "        result->pw_gid != P2PKIT_GID || strcmp(result->pw_name, P2PKIT_USERNAME) != 0) {\n"
                     "        refuse(ACCOUNT_LOOKUP_FAILED);\n    }")
            self.assertEqual(helper.count(guard), 1)
        # All nonzero return codes, including ERANGE, refuse; these are source
        # predicates, not simulated successful libc calls or measured latency.
        self.assertEqual(set(re.findall(r"result->(pw_[A-Za-z0-9_]+)", helper)), {"pw_name", "pw_uid", "pw_gid"})
        self.assertFalse(re.search(r"\b(for|while|malloc|realloc|calloc|setgroups|socket|connect)\s*\(", helper))
        self.assertIn("sizeof(P2PKIT_USERNAME) > 1 && sizeof(P2PKIT_USERNAME) <= 65", text)
        self.assertIn("strlen(P2PKIT_USERNAME) != sizeof(P2PKIT_USERNAME) - 1", text)
        self.assertEqual(len(re.findall(r"\binitgroups\s*\(", text)), 1)
        self.assertFalse(re.search(r"\bsetgroups\s*\(", text))
        main = text.split("\nmain(int argc, char **argv)\n", 1)[1]
        self.assertEqual(main.count("check_account();"), 2)
        fragments = ["argc != 1", "check_ids(0, 0, BAD_ENTRY)", "check_config()", "check_stdio()", "check_account()",
                     "initgroups(P2PKIT_USERNAME, P2PKIT_GID) != 0", "refuse(INITGROUPS_FAILED)",
                     "setgid(P2PKIT_GID) != 0", "setuid(P2PKIT_UID) != 0",
                     "check_ids(P2PKIT_UID, P2PKIT_GID, IDENTITY_FAILED)", "check_account()", "check_groups()",
                     "setuid(0) != -1 || errno != EPERM", "seteuid(0) != -1 || errno != EPERM",
                     "check_ids(P2PKIT_UID, P2PKIT_GID, IDENTITY_FAILED)", "check_groups()", "close_extra_fds()",
                     "check_stdio()", "chdir(P2PKIT_SOURCE_DIRECTORY) != 0",
                     "execve(P2PKIT_D_ARGV[0], P2PKIT_D_ARGV, P2PKIT_D_ENV)", "refuse(EXEC_FAILED)"]
        position = 0
        for fragment in fragments:
            position = main.index(fragment, position) + len(fragment)
        self.assertEqual(main.count("check_groups();"), 2)
        self.assertIn("count < 0 || count != P2PKIT_GROUP_COUNT", text)
        self.assertIn("actual[i] != P2PKIT_GROUPS[i]", text)
        self.assertEqual(len(re.findall(r"\bexecve\s*\(", text)), 1)
        self.assertFalse(re.search(r"\b(fork|vfork|system|popen|dlopen|socket|connect|open|fopen|execvp)\s*\(", text))


if __name__ == "__main__":
    unittest.main()
