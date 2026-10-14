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
