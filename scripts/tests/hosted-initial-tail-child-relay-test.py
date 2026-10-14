#!/usr/bin/env python3
"""K finite failure relay controls with explicitly synthetic nonroot files.

No hosted/native qualification: scope, Popen and custody-anchor ownership are
in-memory seams. Actual source reader opens/closes only fresh owned test files.
No private evidence, credentials, processes, network or accepted-suite reruns.
"""
from __future__ import annotations

import argparse
import ast
from contextlib import ExitStack
import ctypes
import errno
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
STDLIB = Path(os.__file__).resolve().parent
THIS = Path(__file__).resolve()
SCRATCH = None
ADOPTING_WRITER = None
BLOCKED = []
RAW_OPEN, RAW_READ, RAW_CLOSE, RAW_FSTAT = os.open, os.read, os.close, os.fstat
REFUSAL = b"INITIAL_RECIPIENT_K_TAIL_NOT_ACCEPTED\n"
VALUE = {"schema": 1, "scope": "INITIAL_RECIPIENT_TAIL_FAILURE_SITES_V1",
    "operation": "_tail-child", "origin": "FINAL_CATCH", "kind": "UNAVAILABLE",
    "stage": "CHILD_WORK", "sites": [{"module": "CUSTODY", "line": 1}], "truncated": False}
LINE = json.dumps(VALUE, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)
SYNTHETIC = REFUSAL + LINE.encode("ascii") + b"\n"


# Exact selected-fatal-catch diagnostic inverse; all historical supplier pins remain unchanged.
_SELECTED_FAILURE_BASELINES = {'hosted_initial_recipient_before.py': '47a2a51ff38f101704111152dcb8ea1c53e2f768bdb2230ff45a4770ef903fa0', 'run-hosted-initial-recipient-tail.py': 'ea13cc5fae9c1d23eeb60a563d21e5eb3aa2becff283dca684828193d46512be'}
_SELECTED_FAILURE_DELTAS = {'hosted_initial_recipient_before.py': [(b'def _tail_failure_clear():\n', b'def _tail_child_selected_failure(error, stage):\n    """Snapshot one fatal catch\'s chosen error before its following cleanup."""\n    try:\n        state = _TAIL_FAILURE\n        if type(state) is not dict or type(state.get("operation")) is not str or \\\n                type(state.get("kind")) is not str or state.get("operation") != "_tail-child" or \\\n                state.get("kind") != "UNAVAILABLE" or "childPreCleanup" in state or \\\n                type(stage) is not str or stage not in ("CHILD_ENTRY", "CHILD_WORK"):\n            return\n        state["childPreCleanup"] = None  # First attempt wins even if observation fails.\n        if not isinstance(error, BaseException):\n            return\n        sites, truncated = _tail_failure_sites(BaseException.__traceback__.__get__(error))\n        value = {"schema": 1, "scope": "INITIAL_RECIPIENT_TAIL_FAILURE_SITES_V1",\n            "operation": "_tail-child", "kind": "UNAVAILABLE", "stage": stage,\n            "origin": "PRE_CLEANUP_SELECTED", "sites": sites, "truncated": truncated}\n        line = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)\n        state["childPreCleanup"] = _tail_child_failure_projection(\n            b"INITIAL_RECIPIENT_K_TAIL_NOT_ACCEPTED\\n" + line.encode("ascii") + b"\\n")\n    except BaseException:\n        pass  # Optional DATA cannot alter the selected error or following cleanup.\n\n\ndef _tail_child_selected_failure_line():\n    """Validate saved DATA before the existing final-catch path consumes state."""\n    try:\n        state = _TAIL_FAILURE\n        if type(state) is not dict or type(state.get("operation")) is not str or \\\n                type(state.get("kind")) is not str or state.get("operation") != "_tail-child" or \\\n                state.get("kind") != "UNAVAILABLE":\n            return None\n        line = state.get("childPreCleanup")\n        if type(line) is not str or not 0 < len(line) <= 2048:\n            return None\n        value = _tail_child_failure_projection(\n            b"INITIAL_RECIPIENT_K_TAIL_NOT_ACCEPTED\\n" + line.encode("ascii") + b"\\n")\n        if value is not None and json.loads(value)["origin"] == "PRE_CLEANUP_SELECTED":\n            return value\n    except BaseException:\n        pass\n    return None\n\n\ndef _tail_failure_clear():\n'), (b'value["origin"] not in ("FIRST_FAILURE", "FINAL_CATCH")', b'value["origin"] not in ("FIRST_FAILURE", "FINAL_CATCH", "PRE_CLEANUP_SELECTED")')], 'run-hosted-initial-recipient-tail.py': [(b'    except BaseException as error:\n        failure = error if owner is None else owner.remember(error)\n    finally:\n', b'    except BaseException as error:\n        failure = error if owner is None else owner.remember(error)\n        try:\n            B._tail_child_selected_failure(failure, "CHILD_WORK")\n        except BaseException:\n            pass  # Snapshot failure cannot change the chosen error or cleanup.\n    finally:\n'), (b'    except BaseException as error:\n        failure = error if owner is None else owner.remember(error)\n    finally:\n', b'    except BaseException as error:\n        failure = error if owner is None else owner.remember(error)\n        try:\n            B._tail_child_selected_failure(failure, "CHILD_ENTRY")\n        except BaseException:\n            pass  # Snapshot failure cannot change the chosen error or cleanup.\n    finally:\n'), (b'        diagnostic = None\n        try:\n            B._tail_failure_remember(error, origin="FINAL_CATCH")\n', b'        diagnostic = selected = None\n        try:\n            if args.operation == "_tail-child":\n                selected = B._tail_child_selected_failure_line()\n        except BaseException:\n            pass  # Retrieval cannot alter the final exception or exit125.\n        try:\n            B._tail_failure_remember(error, origin="FINAL_CATCH")\n'), (b'        except BaseException:\n            pass  # An unavailable memo cannot prevent separate actual-catch DATA.\n        try:\n            if diagnostic is None:\n', b'        except BaseException:\n            pass  # An unavailable memo cannot prevent separate actual-catch DATA.\n        try:\n            if selected is not None and (diagnostic is None or diagnostic["origin"] != "FIRST_FAILURE"):\n                diagnostic = json.loads(selected)\n        except BaseException:\n            pass  # Keep the existing final-catch fallback when selected DATA fails.\n        try:\n            if diagnostic is None:\n')]}


def selected_failure_preimage(name, raw):
    name = name.removeprefix("scripts/")
    if name not in _SELECTED_FAILURE_BASELINES:
        return raw
    if type(raw) is not bytes:
        raise AssertionError("SELECTED_FAILURE_SOURCE_BYTES")
    if hashlib.sha256(raw).hexdigest() == _SELECTED_FAILURE_BASELINES[name]:
        return raw  # An exact original supplied by another inverse is not a new layer.
    for before, after in reversed(_SELECTED_FAILURE_DELTAS[name]):
        if raw.count(after) != 1:
            raise AssertionError("SELECTED_FAILURE_EXACT_CONTEXT")
        raw = raw.replace(after, before, 1)
    if hashlib.sha256(raw).hexdigest() != _SELECTED_FAILURE_BASELINES[name]:
        raise AssertionError("SELECTED_FAILURE_WHOLE_3CEA_PREIMAGE")
    return raw


def inside_scratch(value):
    if SCRATCH is None or not isinstance(value, (str, bytes, os.PathLike)):
        return False
    path = Path(os.fsdecode(value))
    return path.is_absolute() and ".." not in path.parts and (path == SCRATCH or SCRATCH in path.parents)


def offline(event, args):
    denied = event.startswith(("subprocess.", "socket.")) or event in {
        "os.system", "os.exec", "os.posix_spawn", "os.spawn", "os.fork", "os.forkpty", "pty.spawn",
        "os.kill", "os.killpg", "ctypes.dlopen", "ctypes.dlsym", "os.putenv", "os.unsetenv",
        "os.chdir", "os.chown", "os.setuid", "os.seteuid", "os.setgid", "os.setegid", "os.setgroups",
        "os.setreuid", "os.setregid", "os.setresuid", "os.setresgid",
    }
    if event == "open":
        path = Path(os.fsdecode(args[0])) if isinstance(args[0], (str, bytes)) else None
        public = path is not None and ".." not in path.parts and (
            path == THIS or path.parent == SCRIPTS and path.suffix == ".py" or
            path.parent == SCRIPTS / "__pycache__" and path.suffix == ".pyc" or
            STDLIB in path.parents and path.suffix in (".py", ".pyc"))
        writing = isinstance(args[1], str) and any(char in args[1] for char in "wax+") or (
            type(args[2]) is int and args[2] & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
        # The fixture's unchanged _PosixSink uses os.fdopen after os.open.
        # Admit that one descriptor-adoption seam only while creating the
        # declared stderr writer, and prove it names that exact synthetic file.
        # Other numeric descriptors (including stdin/out/err) remain forbidden.
        adoption = False
        if type(args[0]) is int and args[0] >= 0 and args[1] in ("w", "wb") and \
                ADOPTING_WRITER is not None and inside_scratch(ADOPTING_WRITER):
            try:
                named, opened = ADOPTING_WRITER.lstat(), RAW_FSTAT(args[0])
                adoption = all(stat.S_ISREG(info.st_mode) and stat.S_IMODE(info.st_mode) == 0o600 and
                    info.st_uid == os.getuid() and info.st_nlink == 1 for info in (named, opened)) and \
                    os.path.samestat(named, opened)
            except OSError:
                pass
        denied |= not adoption and not inside_scratch(args[0]) and (not public or bool(writing))
    if event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.truncate", "os.utime"):
        denied |= not inside_scratch(args[0])
    if event in ("os.rename", "os.link", "os.symlink"):
        denied |= not all(inside_scratch(value) for value in args[:2])
    if event in ("os.listdir", "os.scandir"):
        # FileFinder may list the fixed public source/stdlib import roots.
        # This grants read-only metadata access, never source writes, arbitrary
        # private directories or descriptor-based recursive fixture cleanup.
        path = Path(os.fsdecode(args[0])) if isinstance(args[0], (str, bytes)) else None
        public_import = path is not None and ".." not in path.parts and (
            path == SCRIPTS or path == SCRIPTS / "__pycache__" or path == STDLIB or STDLIB in path.parents or
            path == STDLIB.parent / f"python{sys.version_info.major}{sys.version_info.minor}.zip")
        denied |= not inside_scratch(args[0]) and not public_import
    if denied:
        BLOCKED.append(event)  # Never retain a path, payload or environment value.
        raise AssertionError("TAIL_RELAY_TEST_FORBIDDEN_EFFECT")


argparse.ArgumentParser(add_help=False).parse_args([])
sys.dont_write_bytecode = True
sys.addaudithook(offline)


def setUpModule():
    global K, SCRATCH, NATIVE_TREE
    if os.name != "posix" or os.getuid() == 0 or os.geteuid() == 0:
        raise AssertionError("requires actual nonroot POSIX execution; no root model or skip")
    if not (sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.flags.dont_write_bytecode == 1):
        raise AssertionError("use python3 -I -B -S")
    # Root is allocated by the external source-bound execution packet. No
    # arbitrary parent search, caches, pre-existing evidence or recursive cleanup.
    supplied = os.environ.get("P2PKIT_TAIL_RELAY_TEST_ROOT")
    if supplied is None:
        raise AssertionError("source-bound packet must supply a fresh owned P2PKIT_TAIL_RELAY_TEST_ROOT")
    SCRATCH = Path(supplied)
    if not SCRATCH.is_absolute() or SCRATCH != SCRATCH.resolve(strict=True):
        raise AssertionError("synthetic root must be canonical")
    info = SCRATCH.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise AssertionError("synthetic root must be owned0700")
    if list(SCRATCH.iterdir()):
        raise AssertionError("synthetic root must initially be empty")
    spec = importlib.util.spec_from_file_location("tail_child_relay_original_native",
        SCRIPTS / "run-hosted-initial-recipient-tail.py")
    NATIVE_TREE = ast.parse((SCRIPTS / "run-hosted-initial-recipient-tail.py").read_text(encoding="utf-8"))
    K = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = K
    spec.loader.exec_module(K)


def tearDownModule():
    if BLOCKED:
        raise AssertionError("a swallowed forbidden effect occurred")
    if SCRATCH is not None and list(SCRATCH.iterdir()):
        raise AssertionError("synthetic fixture leaves remain")


class SyntheticFailure(BaseException):
    def __str__(self):
        raise AssertionError("must not format failure")


class FakePopen:
    returncode = 125


class FakePosixProcess:
    def __init__(self):
        self.process = FakePopen()

    def poll(self):
        raise AssertionError("no diagnostic repoll")


class FakeLinuxScope:
    def __init__(self):
        self.leaders, self.handles, self.discovery_errors = [], {}, set()
        self._closed, self._retirement_error = False, None

    def forbidden(self, *args, **kwargs):
        raise AssertionError("no diagnostic process operation")

    discover = description = drain = close = spawn = forbidden


class ReaderControls(unittest.TestCase):
    def setUp(self):
        global ADOPTING_WRITER
        self.stack = ExitStack()
        self.path = SCRATCH / self._testMethodName
        self.path.mkdir(mode=0o700)
        self.directory = K.Q._PosixDirectory(self.path)
        self.end = time.monotonic() + 30.0  # One synthetic original bound; never reset.
        ADOPTING_WRITER = self.path / "stderr.log"
        try:
            self.writer = self.directory.create_file("stderr.log", max_bytes=K.native.STDERR_LIMIT, deadline=self.end)
        finally:
            ADOPTING_WRITER = None
        self.writer.write(SYNTHETIC)
        self.writer.sync()
        self.stack.enter_context(patch.object(K.native.processes, "LinuxScope", FakeLinuxScope))
        self.stack.enter_context(patch.object(K.native.processes, "PosixProcess", FakePosixProcess))
        self.stack.enter_context(patch.object(K.native.processes.subprocess, "Popen", FakePopen))
        self.holds, self.registry = [], {}
        self.stack.enter_context(patch.object(K, "_TAIL_CHILD_DIAGNOSTIC_HOLDS", self.holds))
        self.stack.enter_context(patch.object(K.C, "_CUSTODY_OWNERS", self.registry))
        self.scope, self.child = FakeLinuxScope(), FakePosixProcess()
        owner = SimpleNamespace()
        self.anchor = K.C._CustodyOwnerAnchor(owner, owner.__dict__, (), ())
        self.registry[id(owner)] = self.anchor
        self.scope_row, self.stderr_row = {}, {}
        self.anchor.rows = ((self.scope_row, "native-scope", self.scope, False, False),
            (self.stderr_row, "stderr", self.writer, False, False))
        self.preparer = {"pid": os.getpid(), "startTicks": 1}
        self.row = {"launchAttempted": False, "captureOutcomes": {"stderr": {"synced": False, "verified": False}}}
        self.context = {"scope": K.CONTEXT_SCOPE, "kind": "gate"}
        self.state = self.bind()
        self.assertIsNotNone(self.state)
        self.scope.leaders = [self.child]
        K._tail_child_diagnostic_launched(self.state, self.child)
        # Explicit supplied retirement, not a process/scope execution.
        self.scope.leaders, self.scope._closed = [], True
        self.anchor.rows = ((self.scope_row, "native-scope", self.scope, True, True), self.anchor.rows[1])
        self.anchor.failure = SyntheticFailure()
        self.row.update(launchAttempted=True, survivors=[], ownership={"discoveryErrors": []},
            preparerIdentity=self.preparer, scopeCloseAttempted=True, scopeClosed=True)
        self.row["captureOutcomes"]["stderr"].update(synced=True, verified=True)
        self.opens, self.closes = [], []

    def tearDown(self):
        self.stack.close()
        self.writer.close()
        self.directory.close()
        for name in ("stderr.log", "old.log", "link.log"):
            path = self.path / name
            if path.exists() or path.is_symlink():
                path.unlink()
        self.path.rmdir()
        self.assertEqual(BLOCKED, [])

    def bind(self, **changes):
        args = dict(context=self.context, role="linux-x64", directory=self.directory, writer=self.writer,
            scope=self.scope, end=self.end, preparer=self.preparer, anchor=self.anchor, row=self.row)
        args.update(changes)
        return K._tail_child_diagnostic_binding(**args)

    def tracking(self, read=None, close=None, after_open=None):
        def opened(path, flags):
            self.assertEqual(path, self.writer.path)
            self.assertEqual(flags, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
            fd = RAW_OPEN(path, flags)
            self.opens.append(fd)
            if after_open is not None:
                after_open()
            return fd
        def closed(fd):
            self.closes.append(fd)
            return RAW_CLOSE(fd) if close is None else close(fd)
        stack = ExitStack()
        stack.enter_context(patch.object(K.os, "open", opened))
        stack.enter_context(patch.object(K.os, "close", closed))
        if read is not None:
            stack.enter_context(patch.object(K.os, "read", read))
        return stack

    def test_exact_packet_original_open_writer_one_reader_close_and_once(self):
        with self.tracking():
            self.assertEqual(K._tail_child_diagnostic(self.state), LINE)
            self.assertIsNone(K._tail_child_diagnostic(self.state))
        self.assertEqual(len(self.opens), 1)
        self.assertEqual(self.opens, self.closes)
        self.assertTrue(self.state.closed)
        self.assertIsNone(self.state.fd)
        self.assertEqual(self.holds, [])
        self.assertFalse(self.writer.closed)
        self.writer.verify()
        cost = K._tail_cost_begin()
        K._tail_cost_event(cost, "FAILURE")
        self.assertEqual(json.loads(K._tail_cost_line(cost, self.state))["postScopeCloseCode"], 125)
        self.row["scopeClosed"] = False
        self.assertIsNone(json.loads(K._tail_cost_line(cost, self.state))["postScopeCloseCode"])
        self.row["scopeClosed"] = True
        self.anchor.rows = ((self.scope_row, "native-scope", self.scope, True, False), self.anchor.rows[1])
        self.assertIsNone(json.loads(K._tail_cost_line(cost, self.state))["postScopeCloseCode"])

    def test_wrong_route_or_original_binding_refuses_without_open(self):
        for changes in ({"context": {"scope": "BEFORE", "kind": "gate"}}, {"role": "windows-x64"},
                {"context": {"scope": K.CONTEXT_SCOPE, "kind": "worker"}}, {"end": self.end + 1}):
            with self.subTest(changes=tuple(changes)):
                self.assertIsNone(self.bind(**changes))
        self.child.process = FakePopen()
        with self.tracking():
            self.assertIsNone(K._tail_child_diagnostic(self.state))
        self.assertEqual(self.opens, [])

    def test_unknown_retirement_or_missing_actual125_never_reads(self):
        mutations = ((self.row, "scopeClosed", False), (self.row, "survivors", [1]),
            (self.row, "ownership", {"discoveryErrors": ["synthetic"]}))
        for target, key, value in mutations:
            old = target[key]
            target[key] = value
            self.state.consumed = False  # Separate synthetic invocation, not production retry.
            with self.tracking():
                self.assertIsNone(K._tail_child_diagnostic(self.state))
            target[key] = old
        for code in (None, 0, -9, True, 125.0):
            self.state.consumed = False
            self.child.process.returncode = code
            with self.tracking():
                self.assertIsNone(K._tail_child_diagnostic(self.state))
        self.assertEqual(self.opens, [])

    def test_unverified_sink_and_expired_original_bound_never_reads(self):
        self.row["captureOutcomes"]["stderr"]["verified"] = False
        with self.tracking():
            self.assertIsNone(K._tail_child_diagnostic(self.state))
        self.assertEqual(self.opens, [])
        self.state.consumed = False
        self.row["captureOutcomes"]["stderr"]["verified"] = True
        with patch.object(K.native.posix, "_deadline", side_effect=SyntheticFailure()), self.tracking():
            self.assertIsNone(K._tail_child_diagnostic(self.state))
        self.assertEqual(self.opens, [])

    def test_changed_private_file_metadata_refuses_without_read(self):
        self.writer.path.chmod(0o644)
        with self.tracking():
            self.assertIsNone(K._tail_child_diagnostic(self.state))
        self.assertEqual(self.opens, [])
        self.writer.path.chmod(0o600)

    def test_read_failure_and_nonempty_eof_close_exactly_once(self):
        with patch.object(K.os, "open", side_effect=SyntheticFailure()):
            self.assertIsNone(K._tail_child_diagnostic(self.state))
        self.assertFalse(self.state.close_attempted)
        self.assertEqual(self.holds, [])
        for mode in ("failure", "extra", "short", "after-open-size", "after-read-size"):
            self.state.consumed, self.state.fault = False, None
            self.state.closed = False
            self.opens.clear(); self.closes.clear()
            def read(fd, maximum):
                if mode == "failure":
                    raise SyntheticFailure()
                data = RAW_READ(fd, maximum)
                if maximum != 1 and mode == "short":
                    return data[:-1]
                if maximum != 1 and mode == "after-read-size":
                    os.truncate(self.writer.path, 0)
                return b"x" if maximum == 1 and mode == "extra" else data
            mutation = (lambda: os.truncate(self.writer.path, 0)) if mode == "after-open-size" else None
            with self.tracking(read=read, after_open=mutation):
                self.assertIsNone(K._tail_child_diagnostic(self.state))
            self.assertEqual(len(self.opens), 1)
            self.assertEqual(self.opens, self.closes)
            self.assertEqual(self.holds, [])
            self.writer.stream.seek(0)
            os.truncate(self.writer.path, 0)
            self.writer.write(SYNTHETIC)
            self.writer.sync()

    def test_ambiguous_close_terminal_hold_no_probe_or_reclose(self):
        def close(fd):
            RAW_CLOSE(fd)  # Model error AFTER release; do not probe this number again.
            raise SyntheticFailure()
        with self.tracking(close=close):
            self.assertIsNone(K._tail_child_diagnostic(self.state))
            self.assertIsNone(K._tail_child_diagnostic(self.state))
        self.assertEqual(self.opens, self.closes)
        self.assertTrue(self.state.unknown)
        self.assertEqual(self.holds, [self.state])

    def test_empty_or_malformed_packet_has_no_child_output(self):
        for raw in (b"", b"synthetic-not-a-packet\n"):
            self.writer.stream.seek(0)
            os.truncate(self.writer.path, 0)
            self.writer.write(raw)
            self.writer.sync()
            self.state.consumed, self.state.fault, self.state.closed = False, None, False
            with self.tracking():
                self.assertIsNone(K._tail_child_diagnostic(self.state))
            self.assertEqual(self.holds, [])

    def test_codec_fault_cannot_leak_reader_or_replace_failure(self):
        original = self.anchor.failure
        with patch.object(K.B, "_tail_child_failure_projection", side_effect=SyntheticFailure()), self.tracking():
            self.assertIsNone(K._tail_child_diagnostic(self.state))
        self.assertIs(self.anchor.failure, original)
        self.assertEqual(self.opens, self.closes)
        self.assertEqual(self.holds, [])


class RetirementControls(unittest.TestCase):
    """Actual cleanup statements/owner ledger; explicitly synthetic clock/scope.

    No native child is launched or claimed retired. The synthetic owner bypasses
    allocation admission only to exercise unchanged check/error/close methods.
    """
    BASE_SHA256 = "9deae813fa1b7c4a853935ddb3e769692c8c6b80d7397a8f0ce20691c3eca8a7"
    DELTAS = (
        ('    clock = parent.clock\n    retirement_role = clock.clock.role  # Original admitted role; cleanup must not reacquire a failed clock view.\n    inputs = _input_values(parent)\n',
         '    clock = parent.clock\n    inputs = _input_values(parent)\n'),
        ('native.preparer_identity(scope, retirement_role) ==\n                        row["preparerIdentity"], "NATIVE_DRAIN_IDENTITY")',
         'native.preparer_identity(scope, clock.clock.role) ==\n                        row["preparerIdentity"], "NATIVE_DRAIN_IDENTITY")'),
    )

    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(K.C, "_CUSTODY_OWNERS", {}))
        self.stack.enter_context(patch.object(K.native, "QUARANTINE", []))
        self.local = self.stack.enter_context(patch.object(K.time, "monotonic", return_value=100.0))
        self.source = (SCRIPTS / "run-hosted-initial-recipient-tail.py").read_text()
        self.method = self.native_method(self.source)
        self.original = selected_failure_preimage("run-hosted-initial-recipient-tail.py",
            self.source.encode()).decode()
        for after, before in self.DELTAS:
            self.assertEqual(self.original.count(after), 1)
            self.original = self.original.replace(after, before, 1)
        self.assertEqual(hashlib.sha256(self.original.encode()).hexdigest(), self.BASE_SHA256)

    @staticmethod
    def native_method(source):
        return next(node for node in ast.parse(source).body
            if isinstance(node, ast.FunctionDef) and node.name == "_native_tail")

    def fragment(self, method, predicate):
        nodes = [node for node in ast.walk(method) if predicate(node)]
        self.assertEqual(len(nodes), 1)
        return compile(ast.Module(body=nodes, type_ignores=[]), str(SCRIPTS / "run-hosted-initial-recipient-tail.py"), "exec")

    def fixture(self, *, capture=True):
        class Clock:
            role = "linux-x64"
            failure = None

            def __init__(self):
                self.views, self.observations = 0, []

            @property
            def clock(self):
                self.views += 1
                if self.failure is not None:
                    raise self.failure
                return SimpleNamespace(role=self.role)

            def now(self, **kwargs):
                self.observations.append(kwargs)
                if self.failure is not None:
                    raise self.failure
                return 100

        class Scope:
            name = K.native.BACKENDS["linux-x64"]
            drain_error = close_error = identity_error = None
            start_ticks = 1

            def __init__(self):
                self.drains, self.closes, self.identities = [], 0, []
                self.survivors, self.discovery_errors = [], []

            def drain(self, **kwargs):
                self.drains.append(kwargs)
                if self.drain_error is not None:
                    raise self.drain_error
                return self.survivors

            def description(self):
                return {"discoveryErrors": self.discovery_errors}

            def _identity(self, pid):
                self.identities.append(pid)
                if self.identity_error is not None:
                    raise self.identity_error
                return {"pid": pid, "startTicks": self.start_ticks, "live": True}

            def close(self):
                self.closes += 1
                if self.close_error is not None:
                    raise self.close_error

        clock, scope = Clock(), Scope()
        owner = object.__new__(K.C._CustodyOwner)
        K.native.Owner.__init__(owner, 200.0, clock)
        owner.early_last = 100  # Explicit synthetic admission; real custody binding requires an integer.
        owner.initial_sources = {}
        binding = (owner.first, owner.fence, owner.cancelled, owner.local_end, owner.resources,
            owner.errors, owner.initial_sources, owner.admissions, owner.early_last,
            owner.entry_original, owner.entry_close_attempted, owner.entry_close_original, owner.entry_close_snapshot)
        anchor = K.C._CustodyOwnerAnchor(owner, owner.__dict__, binding,
            K.N._history_graph(owner.first), error_graph=K.N._history_graph(owner.errors))
        K.C._CUSTODY_OWNERS[id(owner)] = anchor
        resource = {"label": "native-scope", "owner": scope, "attempted": False, "closed": False}
        owner.resources.append(resource)
        anchor.rows = ((resource, "native-scope", scope, False, False),)
        owner.check()  # Real passive binding/ledger checks, not modeled flags.
        row = {"scopeAttempted": True, "launchAttempted": True,
            "preparerIdentity": {"pid": os.getpid(), "startTicks": 1}}
        values = {"clock": clock, "scope": scope, "owner": owner, "owner_anchor": anchor,
            "row": row, "capture_end": 200.0, "caps": (0, 150, 200), "native_known": False,
            "native": K.native, "time": K.time, "require": K.require, "O": K.O}
        if capture:
            self.capture(values)
        return values

    def capture(self, values):
        code = self.fragment(self.method, lambda node: isinstance(node, ast.Assign) and
            any(isinstance(target, ast.Name) and target.id == "retirement_role" for target in node.targets))
        exec(code, values)

    def poison(self, values):
        error = K.O.OriginError("SYNTHETIC_WORK_EXPIRED")
        values["clock"].failure = error
        values["owner"].error("k-native", error)
        return error

    def cleanup(self, values, *, original=False):
        method = self.native_method(self.original) if original else self.method
        code = self.fragment(method, lambda node: isinstance(node, ast.If) and
            ast.unparse(node.test) == "scope is not None")
        exec(code, values)

    def test_exact_two_site_inverse_and_original_role_before_work(self):
        capture = next(node for node in self.method.body if isinstance(node, ast.Assign) and
            any(isinstance(target, ast.Name) and target.id == "retirement_role" for target in node.targets))
        self.assertEqual(ast.unparse(capture.value), "clock.clock.role")
        inputs = next(node for node in self.method.body if isinstance(node, ast.Assign) and
            ast.unparse(node.value) == "_input_values(parent)")
        self.assertLess(capture.lineno, inputs.lineno)
        self.assertEqual(self.source.count("retirement_role"), 2)
        # The same live property reads remain; only one post-drain read moved.
        current_roles = [node.lineno for node in ast.walk(self.method)
            if isinstance(node, ast.Attribute) and ast.unparse(node) == "clock.clock.role"]
        old_method = self.native_method(self.original)
        old_roles = [node for node in ast.walk(old_method)
            if isinstance(node, ast.Attribute) and ast.unparse(node) == "clock.clock.role"]
        self.assertEqual(len(current_roles), len(old_roles))
        self.assertEqual(min(current_roles), capture.lineno)

    def test_poisoned_view_saved_drain_closes_but_original_failure_stays(self):
        value = self.fixture()
        error = self.poison(value)
        self.cleanup(value)
        self.assertTrue(value["native_known"] and value["row"]["scopeClosed"])
        self.assertFalse(value["owner_anchor"].unknown)
        self.assertEqual(value["scope"].closes, 1)
        self.assertEqual(value["clock"].views, 1)
        self.assertEqual(value["scope"].drains, [{"grace": 5, "kill_wait": 5, "deadline": 200.0}])
        self.assertIs(value["owner_anchor"].failure, error)
        # Execute the unchanged final failure gates, not a synthetic PASS flag.
        for expression in ("row['launchAttempted'] and owner_anchor.failure is not None",
                "owner_anchor.failure is not None"):
            code = self.fragment(self.method, lambda node: isinstance(node, ast.If) and
                ast.unparse(node.test) == expression)
            if expression.startswith("row["):
                exec(code, value)
            else:
                with self.assertRaises(K.O.OriginError) as caught:
                    exec(code, value)
                self.assertIs(caught.exception, error)
        self.assertTrue(value["owner_anchor"].unknown)
        old = self.fixture()
        old_error = self.poison(old)
        self.cleanup(old, original=True)
        self.assertTrue(old["owner_anchor"].unknown)
        self.assertFalse(old["native_known"] or old["row"]["scopeClosed"])
        self.assertEqual(old["scope"].closes, 0)
        self.assertIs(old["owner_anchor"].failure, old_error)

    def test_role_capture_refuses_initial_failure_and_never_adopts_mutation(self):
        initial = self.fixture(capture=False)
        error = self.poison(initial)
        with self.assertRaises(K.O.OriginError) as caught:
            self.capture(initial)
        self.assertIs(caught.exception, error)
        self.assertNotIn("retirement_role", initial)
        self.assertEqual(initial["scope"].drains, [])
        for change in ("view", "backend", "preparer"):
            with self.subTest(change=change):
                value = self.fixture()
                original = self.poison(value)
                value["clock"].role = "windows-x64"
                if change == "backend":
                    value["scope"].name = K.native.BACKENDS["windows-x64"]
                elif change == "preparer":
                    value["scope"].start_ticks = 2
                self.cleanup(value)
                self.assertEqual(value["retirement_role"], "linux-x64")
                self.assertEqual(value["clock"].views, 1)
                self.assertEqual(value["row"]["scopeClosed"], change == "view")
                self.assertEqual(value["owner_anchor"].unknown, change != "view")
                self.assertIs(value["owner_anchor"].failure, original)

    def test_drain_survivors_discovery_and_identity_failure_cannot_close(self):
        for failure in ("drain", "survivors", "discovery", "identity"):
            with self.subTest(failure=failure):
                value = self.fixture()
                original = self.poison(value)
                scope = value["scope"]
                if failure == "drain":
                    scope.drain_error = K.O.OriginError("SYNTHETIC_DRAIN_FAILURE")
                elif failure == "survivors":
                    scope.survivors = [{"pid": os.getpid()}]
                elif failure == "discovery":
                    scope.discovery_errors = ["SYNTHETIC_DISCOVERY_FAILURE"]
                else:
                    scope.identity_error = K.O.OriginError("SYNTHETIC_IDENTITY_FAILURE")
                self.cleanup(value)
                self.assertFalse(value["native_known"] or value["row"]["scopeClosed"])
                self.assertTrue(value["owner_anchor"].unknown)
                self.assertEqual(scope.closes, 0)
                self.assertIs(value["owner_anchor"].failure, original)

    def test_expired_saved_deadline_and_close_failure_never_gain_known_close(self):
        for failure in ("deadline", "close"):
            with self.subTest(failure=failure):
                value = self.fixture()
                original = self.poison(value)
                if failure == "deadline":
                    self.local.return_value = 201.0
                else:
                    value["scope"].close_error = K.O.OriginError("SYNTHETIC_CLOSE_FAILURE")
                try:
                    self.cleanup(value)
                finally:
                    self.local.return_value = 100.0
                self.assertEqual(value["scope"].drains[0]["deadline"], 200.0)
                self.assertEqual(value["scope"].drains[0]["grace"], 0 if failure == "deadline" else 5)
                self.assertFalse(value["native_known"] or value["row"]["scopeClosed"])
                self.assertTrue(value["owner_anchor"].unknown)
                self.assertEqual(value["row"]["scopeCloseAttempted"], failure == "close")
                self.assertIs(value["owner_anchor"].failure, original)

    def test_successful_cleanup_retains_final_clock_deadline_and_identity_checks(self):
        results = []
        for original in (False, True):
            value = self.fixture()
            self.cleanup(value, original=original)
            self.assertTrue(value["native_known"] and value["row"]["scopeClosed"])
            self.assertIsNone(value["owner_anchor"].failure)
            self.assertFalse(value["owner_anchor"].unknown)
            self.assertEqual(value["clock"].observations, [{"final": True, "limit": 200},
                {"final": True, "limit": None}, {"final": True, "limit": None}])
            self.assertEqual(value["scope"].identities, [os.getpid()])
            results.append((value["scope"].drains, value["scope"].closes,
                value["row"], value["owner"].errors))
        self.assertEqual(results[0], results[1])


class SelectedFailureControls(unittest.TestCase):
    def tearDown(self):
        K.B._tail_failure_clear()

    def begin(self, operation="_tail-child", kind="UNAVAILABLE"):
        K.B._tail_failure_clear()
        K.B._tail_failure_begin(operation, kind)

    def failure_at(self, line=17):
        error = SyntheticFailure()
        self.prepend(error, line)
        return error

    def prepend(self, error, line):
        # Synthetic executable source coordinates only; no native code executes.
        code = compile("\n" * (line - 1) + "raise error\n",
            str(SCRIPTS / "run-hosted-initial-recipient-tail.py"), "exec")
        try:
            exec(code, {"error": error})
        except BaseException as actual:
            self.assertIs(actual, error)

    def selected_catch(self, name):
        method = next(node for node in NATIVE_TREE.body
            if isinstance(node, ast.FunctionDef) and node.name == name)
        handlers = [node for node in ast.walk(method) if isinstance(node, ast.ExceptHandler) and
            node.body and isinstance(node.body[0], ast.Assign) and
            ast.unparse(node.body[0]) == "failure = error if owner is None else owner.remember(error)"]
        self.assertEqual(len(handlers), 1)
        template = ast.parse("def selected_catch(owner, raised, trace):\n"
            "    failure = None\n    try:\n        raise raised\n"
            "    except BaseException as error:\n        pass\n"
            "    finally:\n        trace.append(failure)\n    return failure\n")
        template.body[0].body[1].handlers[0].body = handlers[0].body
        namespace = {"B": K.B}
        exec(compile(ast.fix_missing_locations(template), str(THIS), "exec"), namespace)
        return namespace["selected_catch"]

    def final_catch(self, error, operation="_tail-child"):
        method = next(node for node in NATIVE_TREE.body
            if isinstance(node, ast.FunctionDef) and node.name == "main")
        handlers = [node for node in ast.walk(method) if isinstance(node, ast.ExceptHandler) and
            any(isinstance(item, ast.Return) and isinstance(item.value, ast.Constant) and
                item.value.value == 125 for item in node.body)]
        self.assertEqual(len(handlers), 1)
        template = ast.parse("def final_catch(error, args):\n    pass\n")
        template.body[0].body = handlers[0].body
        output = io.StringIO()
        namespace = {"B": K.B, "sys": SimpleNamespace(stderr=output), "json": json}
        exec(compile(ast.fix_missing_locations(template), str(THIS), "exec"), namespace)
        self.assertEqual(namespace["final_catch"](error, SimpleNamespace(operation=operation, kind="gate")), 125)
        lines = output.getvalue().splitlines()
        self.assertEqual(lines[0], "INITIAL_RECIPIENT_K_TAIL_NOT_ACCEPTED")
        self.assertEqual(len(lines), 2)
        return json.loads(lines[1])

    def test_exact_lineage_and_actual_selected_catch_before_cleanup(self):
        for name, baseline in _SELECTED_FAILURE_BASELINES.items():
            raw = (SCRIPTS / name).read_bytes()
            original = selected_failure_preimage(name, raw)
            self.assertEqual(hashlib.sha256(original).hexdigest(), baseline)
            self.assertEqual(selected_failure_preimage(name, original), original)
            self.assertNotEqual(raw, original)
            for before, after in _SELECTED_FAILURE_DELTAS[name]:
                self.assertEqual(raw.count(after), 1)
                for changed in (raw.replace(after, before, 1), raw + after,
                        raw.replace(after, b"", 1) + after,
                        raw.replace(after, after + b" ", 1)):
                    self.assertNotEqual(changed, raw)
                    with self.assertRaisesRegex(AssertionError, "SELECTED_FAILURE_"):
                        selected_failure_preimage(name, changed)
            with self.assertRaisesRegex(AssertionError, "SELECTED_FAILURE_"):
                selected_failure_preimage(name, raw + b"\n# outside approved delta\n")
        for name, stage in (("_child_work", "CHILD_WORK"), ("tail_child", "CHILD_ENTRY")):
            self.begin()
            actual, chosen, events = self.failure_at(17), self.failure_at(23), []
            def remember(error):
                self.assertIs(error, actual)
                events.append("REMEMBER")
                return chosen
            method = self.selected_catch(name)
            self.assertIs(method(SimpleNamespace(remember=remember), actual, events), chosen)
            self.assertEqual(events, ["REMEMBER", chosen])
            saved = json.loads(K.B._tail_child_selected_failure_line())
            self.assertEqual(saved["stage"], stage)
            self.assertIn({"module": "TAIL", "line": 23}, saved["sites"])
            self.assertNotIn({"module": "TAIL", "line": 17}, saved["sites"])
            self.begin()
            with patch.object(K.B, "_tail_child_selected_failure", side_effect=SyntheticFailure()):
                self.assertIs(method(None, actual, events), actual)
            self.assertIs(events[-1], actual)

    def test_precleanup_snapshot_survives_more_than_32_cleanup_frames(self):
        self.begin()
        chosen = self.failure_at(17)
        K.B._tail_child_selected_failure(chosen, "CHILD_WORK")
        saved = K.B._tail_child_selected_failure_line()
        for _ in range(40):
            self.prepend(chosen, 29)
        self.assertEqual(K.B._tail_child_selected_failure_line(), saved)
        value = json.loads(saved)
        self.assertEqual(value["origin"], "PRE_CLEANUP_SELECTED")
        self.assertIn({"module": "TAIL", "line": 17}, value["sites"])
        final = K.B._tail_failure_final_catch(chosen, "_tail-child", "UNAVAILABLE")
        self.assertTrue(final["truncated"])
        self.assertNotIn({"module": "TAIL", "line": 17}, final["sites"])
        self.assertEqual(self.final_catch(chosen), value)

    def test_nested_selection_first_attempt_and_observation_faults(self):
        self.begin()
        inner, outer = self.failure_at(17), self.failure_at(23)
        K.B._tail_child_selected_failure(inner, "CHILD_WORK")
        first = K.B._tail_child_selected_failure_line()
        K.B._tail_child_selected_failure(outer, "CHILD_ENTRY")
        self.assertEqual(K.B._tail_child_selected_failure_line(), first)
        for target in ("_tail_failure_sites", "_tail_child_failure_projection"):
            self.begin()
            with patch.object(K.B, target, side_effect=SyntheticFailure()):
                K.B._tail_child_selected_failure(inner, "CHILD_WORK")
            self.assertIn("childPreCleanup", K.B._TAIL_FAILURE)
            self.assertIsNone(K.B._TAIL_FAILURE["childPreCleanup"])
            K.B._tail_child_selected_failure(outer, "CHILD_ENTRY")
            self.assertIsNone(K.B._tail_child_selected_failure_line())

    def test_child_cli_identity_mismatch_and_first_failure_preference(self):
        self.begin()
        chosen, final = self.failure_at(17), self.failure_at(23)
        K.B._tail_failure_remember(chosen)
        K.B._tail_child_selected_failure(chosen, "CHILD_WORK")
        value = self.final_catch(final)
        self.assertEqual((value["origin"], value["stage"]), ("PRE_CLEANUP_SELECTED", "CHILD_WORK"))
        self.assertIn({"module": "TAIL", "line": 17}, value["sites"])
        self.begin()
        K.B._tail_failure_remember(final)
        K.B._tail_child_selected_failure(chosen, "CHILD_WORK")
        self.assertEqual(self.final_catch(final)["origin"], "FIRST_FAILURE")
        self.begin()
        K.B._tail_child_selected_failure(chosen, "CHILD_WORK")
        with patch.object(K.B, "_tail_child_selected_failure_line", side_effect=SyntheticFailure()):
            self.assertEqual(self.final_catch(final)["origin"], "FINAL_CATCH")

    def test_inactive_parent_reentry_and_unavailable_fallback(self):
        error = self.failure_at()
        for mode in ("inactive", "parent", "reentered"):
            K.B._tail_failure_clear()
            if mode == "parent":
                K.B._tail_failure_begin("before-and-tail", "gate")
            elif mode == "reentered":
                K.B._tail_failure_begin("_tail-child", "UNAVAILABLE")
                K.B._tail_failure_begin("_tail-child", "UNAVAILABLE")
            K.B._tail_child_selected_failure(error, "CHILD_WORK")
            self.assertIsNone(K.B._tail_child_selected_failure_line())
        self.begin("before-and-tail", "gate")
        K.B._tail_child_selected_failure(error, "CHILD_WORK")
        self.assertEqual(self.final_catch(error, "before-and-tail")["origin"], "FINAL_CATCH")
        self.begin()
        self.assertEqual(self.final_catch(error)["origin"], "FINAL_CATCH")
        self.begin()
        K.B._tail_child_selected_failure(error, "CHILD_ENTRY")
        K.B._tail_failure_clear()
        self.assertIsNone(K.B._tail_child_selected_failure_line())

    def test_selected_codec_malformed_and_fault_no_false_data(self):
        equality_calls = []
        class UnexpectedEquality:
            def __eq__(self, other):
                equality_calls.append(True)
                raise AssertionError("diagnostic context must not invoke equality")
        for key in ("operation", "kind"):
            self.begin()
            K.B._TAIL_FAILURE[key] = UnexpectedEquality()
            K.B._tail_child_selected_failure(self.failure_at(), "CHILD_WORK")
            self.assertNotIn("childPreCleanup", K.B._TAIL_FAILURE)
            self.assertIsNone(K.B._tail_child_selected_failure_line())
            self.assertEqual(equality_calls, [])
        for stage in ("CHILD_ENTRY", "CHILD_WORK"):
            value = {**VALUE, "origin": "PRE_CLEANUP_SELECTED", "stage": stage}
            line = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            self.assertEqual(K.B._tail_child_failure_projection(REFUSAL + line.encode() + b"\n"), line)
        for key, value in (("stage", "UNAVAILABLE"), ("stage", "K_NATIVE"),
                ("operation", "before-and-tail"), ("kind", "gate"), ("private", "NO_OUTPUT")):
            row = {**VALUE, "origin": "PRE_CLEANUP_SELECTED", key: value}
            raw = REFUSAL + json.dumps(row, sort_keys=True, separators=(",", ":")).encode() + b"\n"
            self.assertIsNone(K.B._tail_child_failure_projection(raw))
        self.begin()
        K.B._tail_child_selected_failure(self.failure_at(), "CHILD_WORK")
        good = K.B._TAIL_FAILURE["childPreCleanup"]
        for value in (None, b"bytes", "x" * 2049, good.replace('"schema":1', '"schema":true'),
                good.replace('"schema":1', '"schema":1,"schema":1'),
                good.replace("PRE_CLEANUP_SELECTED", "FIRST_FAILURE"), good + "\n"):
            K.B._TAIL_FAILURE["childPreCleanup"] = value
            self.assertIsNone(K.B._tail_child_selected_failure_line())
        K.B._TAIL_FAILURE["childPreCleanup"] = good
        with patch.object(K.B, "_tail_child_failure_projection", side_effect=SyntheticFailure()):
            self.assertIsNone(K.B._tail_child_selected_failure_line())


class DataControls(unittest.TestCase):
    def test_exact_child_codec_and_closed_finite_refusals(self):
        self.assertEqual(K.B._tail_child_failure_projection(SYNTHETIC), LINE)
        for origin, stage in (("FIRST_FAILURE", "CHILD_ENTRY"), ("FIRST_FAILURE", "CHILD_WORK"),
                ("FINAL_CATCH", "UNAVAILABLE")):
            value = {**VALUE, "origin": origin, "stage": stage}
            line = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            self.assertEqual(K.B._tail_child_failure_projection(REFUSAL + line.encode("ascii") + b"\n"), line)
        values = []
        for key, replacement in (("operation", "before-and-tail"), ("kind", "gate"), ("stage", "K_NATIVE"),
                ("origin", "OTHER"), ("schema", True), ("sites", [{"module": "PRIVATE", "line": 1}]),
                ("sites", [{"module": "TAIL", "line": True}]), ("extra", "not-output")):
            value = dict(VALUE); value[key] = replacement
            values.append(REFUSAL + json.dumps(value, sort_keys=True, separators=(",", ":")).encode() + b"\n")
        values += [SYNTHETIC + b"extra\n", SYNTHETIC.replace(b'"schema":1', b'"schema":1,"schema":1'),
            SYNTHETIC.replace(b'"schema":1', b'"schema":NaN'), SYNTHETIC.replace(b'"schema":1', b'"schema": 1'),
            b"x" * 65537, SYNTHETIC[:-1], b"", SYNTHETIC.decode()]
        for raw in values:
            with self.subTest(case=values.index(raw)):
                self.assertIsNone(K.B._tail_child_failure_projection(raw))

    def test_fixed_cost_first_failure_and_actual_poll_provenance(self):
        with patch.object(K.time, "monotonic_ns", side_effect=[0, 10_000_000, 40_000_000, 50_000_000, 60_000_000]), \
                patch.object(K.time, "process_time_ns", side_effect=[0, 1_000_000, 11_000_000, 12_000_000, 13_000_000]):
            state = K._tail_cost_begin()
            K._tail_cost_event(state, "CURRENCY")
            K._tail_cost_event(state, "PRE_POLL_CLOCK")
            K._tail_cost_event(state, "POST_POLL_CLOCK", 125)
            K._tail_cost_event(state, "FAILURE")
        value = json.loads(K._tail_cost_line(state))
        self.assertEqual((value["loops"], value["completedCurrencies"], value["polls"]), (1, 1, 1))
        self.assertEqual((value["loopWallMs"], value["loopCpuMs"], value["completedCurrencyWallMs"],
            value["completedCurrencyCpuMs"]), (60, 13, 30, 10))
        self.assertEqual(value["lastObservedPollCode"], 125)
        self.assertIsNone(value["postScopeCloseCode"])
        self.assertEqual(value["childCause"], "UNKNOWN")
        before = K._tail_cost_line(state)
        K._tail_cost_event(state, "FAILURE")
        self.assertEqual(K._tail_cost_line(state), before)

    def test_cost_missing_output_backward_faults_and_finite_encoding(self):
        with patch.object(K.time, "monotonic_ns", side_effect=SyntheticFailure()):
            self.assertIsNone(K._tail_cost_begin())
        for sample in (-1, float("nan"), True):
            with patch.object(K.time, "monotonic_ns", return_value=10), patch.object(K.time, "process_time_ns", return_value=10):
                state = K._tail_cost_begin()
            with patch.object(K.time, "monotonic_ns", return_value=sample), patch.object(K.time, "process_time_ns", return_value=10):
                K._tail_cost_event(state, "FAILURE")
            self.assertIsNone(K._tail_cost_line(state))
        state = K._tail_cost_begin()
        self.assertIsNone(K._tail_cost_line(state))
        K._tail_cost_event(state, "FAILURE")
        state["snapshot"]["injected"] = "never-emit"
        self.assertIsNone(K._tail_cost_line(state))

    def test_cost_saturation_is_explicit_not_a_granted_window(self):
        with patch.object(K.time, "monotonic_ns", return_value=0), patch.object(K.time, "process_time_ns", return_value=0):
            state = K._tail_cost_begin()
        state["loops"] = 1_000_001
        with patch.object(K.time, "monotonic_ns", return_value=901_000_000_000), \
                patch.object(K.time, "process_time_ns", return_value=901_000_000_000):
            K._tail_cost_event(state, "FAILURE")
        value = json.loads(K._tail_cost_line(state))
        self.assertTrue(value["timesClamped"] and value["countsClamped"])
        self.assertEqual((value["loops"], value["loopWallMs"]), (1_000_000, 900000))

    def test_original_poll_cleanup_failure_and_success_topology_is_preserved(self):
        source = (SCRIPTS / "run-hosted-initial-recipient-tail.py").read_text()
        tree = ast.parse(source)
        method = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "_native_tail")
        calls = [(node.lineno, ast.unparse(node.func)) for node in ast.walk(method) if isinstance(node, ast.Call)]
        by = lambda name: sorted(line for line, function in calls if function == name)
        self.assertEqual(len(by("child.poll")), 1)
        self.assertLess(by("scope.spawn")[0], by("_tail_child_diagnostic_launched")[0])
        self.assertLess(by("scope.drain")[0], by("_tail_child_diagnostic")[0])
        self.assertLess(by("_tail_child_diagnostic")[0], by("_tail_cost_line")[0])
        self.assertIn('owner.error("k-native-child-return", owner_anchor.failure, unknown=True)', source)
        self.assertIn('if owner_anchor.failure is not None:\n            raise owner_anchor.failure', source)
        self.assertIn('require(captures["stderr"] == b"", "NATIVE_STDERR_NOT_EMPTY")', source)
        self.assertIn('work == min(started + 210 * NS, seal_end - 45 * NS)', source)
        self.assertIn('remaining > required, "NATIVE_VALIDATION_FINISH_CANNOT_FIT"', source)
        self.assertIn('grace = min(5, remaining)', source)
        self.assertIn('kill_wait=min(5, max(0, remaining - grace)), deadline=capture_end', source)


if __name__ == "__main__":
    unittest.main(verbosity=2, failfast=True)
