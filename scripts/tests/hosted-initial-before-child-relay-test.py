#!/usr/bin/env python3
"""Nonroot synthetic POSIX reader controls, not native/hosted qualification.

Exercise the actual BEFORE-child diagnostic reader against owned synthetic
0700/0600 files with the original writer still open. Only the process scope is
an explicit in-memory seam; no process is launched, polled, signalled or retired.
Fault seams test one-use descriptor bookkeeping, not genuine ambiguous OS close
behavior. No private evidence, credentials, network, authority or provider runs.
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
REFUSAL = b"INITIAL_RECIPIENT_CUSTODY_NOT_ACCEPTED\n"
VALUE = {"schema": 1, "scope": "INITIAL_RECIPIENT_BEFORE_AUTHORITY_CHILD_FAILURE_SITES_V1",
    "operation": "_before-authority", "origin": "FINAL_CATCH", "kind": "UNAVAILABLE",
    "stage": "UNAVAILABLE", "sites": [{"module": "CUSTODY", "line": 1}], "truncated": False}
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
        raise AssertionError("BEFORE_RELAY_TEST_FORBIDDEN_EFFECT")


argparse.ArgumentParser(add_help=False).parse_args([])
sys.dont_write_bytecode = True
sys.addaudithook(offline)


def setUpModule():
    global N, SCRATCH, NATIVE_TREE
    if os.name != "posix" or os.getuid() == 0 or os.geteuid() == 0:
        raise AssertionError("requires actual nonroot POSIX execution; no root model or skip")
    if not (sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.flags.dont_write_bytecode == 1):
        raise AssertionError("use python3 -I -B -S")
    # Root is allocated by the external source-bound execution packet. No
    # arbitrary parent search, caches, pre-existing evidence or recursive cleanup.
    supplied = os.environ.get("P2PKIT_RELAY_TEST_ROOT")
    if supplied is None:
        raise AssertionError("source-bound packet must supply a fresh owned P2PKIT_RELAY_TEST_ROOT")
    SCRATCH = Path(supplied)
    if not SCRATCH.is_absolute() or SCRATCH != SCRATCH.resolve(strict=True):
        raise AssertionError("synthetic root must be canonical")
    info = SCRATCH.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
        raise AssertionError("synthetic root must be owned0700")
    if list(SCRATCH.iterdir()):
        raise AssertionError("synthetic root must initially be empty")
    spec = importlib.util.spec_from_file_location("before_child_relay_original_native",
        SCRIPTS / "run-hosted-cache-bootstrap.py")
    NATIVE_TREE = ast.parse((SCRIPTS / "run-hosted-cache-bootstrap.py").read_text(encoding="utf-8"))
    N = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = N
    spec.loader.exec_module(N)


def tearDownModule():
    if BLOCKED:
        raise AssertionError("a swallowed forbidden effect occurred")
    if SCRATCH is not None and list(SCRATCH.iterdir()):
        raise AssertionError("synthetic fixture leaves remain")


class SyntheticFailure(BaseException):
    def __str__(self):
        raise AssertionError("must not format private-like synthetic failure")

    def __repr__(self):
        raise AssertionError("must not repr private-like synthetic failure")


class FakeLinuxScope:
    """Explicit process metadata seam, NEVER a real process ownership claim."""
    name = "linux-proc-pidfd"

    def __init__(self, child, preparer):
        self.leaders = [child]
        self.preparer = dict(preparer)
        self._closed = False
        self._retirement_error = None
        self.discovery_errors = set()
        self.pending_discoveries = {}
        self.survivors = []
        self.discovery_calls = 0
        self.identity_calls = 0
        self.job = "a" * 32
        self.invocation = "b" * 32
        self.handles = {}
        self.known = {}
        self.launches = []

    def _identity(self, pid):
        self.identity_calls += 1
        if pid != self.preparer["pid"]:
            raise AssertionError("only original preparer metadata may be observed")
        return {**self.preparer, "live": True}

    def discover(self):
        self.discovery_calls += 1
        if self._retirement_error is not None:
            raise self._retirement_error
        if self._closed:
            raise SyntheticFailure()
        return list(self.survivors)

    def description(self):
        return {"backend": self.name, "scope": "controlled-marker-inheriting-descendants",
            "job": self.job, "invocation": self.invocation, "discoveryErrors": sorted(self.discovery_errors)}

    def forbidden(self, *args, **kwargs):
        raise AssertionError("no process launch/poll/signal/drain/close in synthetic relay")

    spawn = signal_all = drain = close = forbidden


class ReaderComposition(unittest.TestCase):
    """Actual files/reader; only native process metadata and faults are supplied."""

    packet = SYNTHETIC

    def setUp(self):
        global ADOPTING_WRITER
        self.assertEqual(BLOCKED, [])
        self.stack = ExitStack()
        self.case = SCRATCH / self._testMethodName
        self.case.mkdir(mode=0o700)
        self.path = self.case / "service"
        self.path.mkdir(mode=0o700)
        self.directory = N.query._PosixDirectory(self.path)
        self.end = time.monotonic() + 30.0  # Synthetic original prelaunch ceiling only.
        self.assertIsNone(ADOPTING_WRITER)
        ADOPTING_WRITER = self.path / "stderr.log"
        try:
            self.writer = self.directory.create_file("stderr.log", max_bytes=N.STDERR_LIMIT, deadline=self.end)
        finally:
            ADOPTING_WRITER = None
        self.writer.write(self.packet)
        self.writer.sync()
        self.child = SimpleNamespace(returncode=125, pid=424242)
        self.child.poll = lambda: self.fail("relay must not directly repoll child")
        self.preparer = {"pid": os.getpid(), "startTicks": 1}
        self.scope = FakeLinuxScope(self.child, self.preparer)
        self.stack.enter_context(patch.object(N.processes, "LinuxScope", FakeLinuxScope))
        self.holds = []
        self.stack.enter_context(patch.object(N, "_BEFORE_CHILD_DIAGNOSTIC_HOLDS", self.holds))
        self.context = {"scope": N.INITIAL_BEFORE_AUTHORITY_CONTEXT_SCOPE, "kind": "gate"}
        self.state = self.bind()
        self.assertIsNotNone(self.state)
        self.opened, self.reads, self.closes = [], [], []

    def tearDown(self):
        self.stack.close()
        self.writer.close()
        self.directory.close()
        # Exactly this control's synthetic files, including modeled aliases.
        for base in (self.case / "service", self.case / "old-service"):
            if base.exists():
                for name in ("stderr.log", "old-stderr.log", "hardlink.log"):
                    path = base / name
                    if path.exists() or path.is_symlink():
                        path.unlink()
                base.rmdir()
        self.case.rmdir()
        self.assertEqual(BLOCKED, [])

    def bind(self, **changes):
        values = {"context": self.context, "role": "linux-x64", "directory": self.directory,
            "writer": self.writer, "scope": self.scope, "capture_end": self.end,
            "preparer": self.preparer, "unknown": False}
        values.update(changes)
        return N._before_child_diagnostic_binding(**values)

    def relay(self, code=125, state=None):
        return N._before_child_diagnostic(self.state if state is None else state, code, self.child)

    def io_tracking(self, *, reading=None, closing=None, after_open=None):
        def opened(path, flags, *args, **kwargs):
            self.assertEqual(Path(path), self.path / "stderr.log")
            self.assertEqual(flags, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
            descriptor = RAW_OPEN(path, flags, *args, **kwargs)
            self.opened.append(descriptor)
            if after_open is not None:
                after_open()
            return descriptor
        def read(descriptor, maximum):
            self.assertIn(descriptor, self.opened)
            self.reads.append((descriptor, maximum))
            return RAW_READ(descriptor, maximum) if reading is None else reading(descriptor, maximum)
        def close(descriptor):
            self.assertIn(descriptor, self.opened)
            self.closes.append(descriptor)
            return RAW_CLOSE(descriptor) if closing is None else closing(descriptor)
        stack = ExitStack()
        stack.enter_context(patch.object(N.os, "open", opened))
        stack.enter_context(patch.object(N.os, "read", read))
        stack.enter_context(patch.object(N.os, "close", close))
        return stack

    def assert_known_closed(self):
        self.assertEqual(len(self.opened), 1)
        self.assertEqual(self.closes, self.opened)
        self.assertIs(self.state.consumed, True)
        self.assertIs(self.state.closeAttempted, True)
        self.assertIs(self.state.closed, True)
        self.assertIsNone(self.state.fd)
        self.assertIs(self.state.unknown, False)
        self.assertEqual(self.holds, [])
        # Only known-closed descriptors may be probed by this test. UNKNOWN
        # branches below never probe or retry their retained numeric descriptor.
        with self.assertRaises(OSError) as caught:
            RAW_FSTAT(self.opened[0])
        self.assertEqual(caught.exception.errno, errno.EBADF)
        self.assertFalse(self.writer.closed)
        self.writer.verify()

    def test_real_open_writer_finite_projection_known_reader_close(self):
        with self.io_tracking():
            self.assertEqual(self.relay(), LINE)
        self.assertEqual([count for _fd, count in self.reads], [N.STDERR_LIMIT + 1, 1])
        self.assert_known_closed()
        self.assertGreater(self.scope.discovery_calls, 0)
        self.writer.write(b"")  # Reader did not close the original writer.

    def test_route_and_original_unknown_refuse_binding(self):
        for changes in ({"role": "windows-x64"}, {"role": "macos-arm64"},
                {"context": {"scope": self.context["scope"], "kind": "worker"}},
                {"context": {"scope": "OTHER", "kind": "gate"}}, {"unknown": True}):
            with self.subTest(fields=tuple(changes)):
                self.assertIsNone(self.bind(**changes))

    def test_only_exact_integer125_reads_and_permission_is_once(self):
        for code in (0, 1, 137, True, 125.0, "125", None):
            state = self.bind()
            with patch.object(N.os, "open", side_effect=AssertionError("ineligible read")):
                self.assertIsNone(self.relay(code, state))
        with self.io_tracking():
            self.assertEqual(self.relay(), LINE)
            self.assertIsNone(self.relay())
        self.assert_known_closed()

    def test_live_descendant_and_discovery_uncertainty_withhold_read(self):
        for field, value in (("survivors", [{"pid": 424243}]), ("discovery_errors", {"SYNTHETIC"}),
                ("_retirement_error", SyntheticFailure()), ("_closed", True)):
            state = self.bind()
            old = getattr(self.scope, field)
            setattr(self.scope, field, value)
            try:
                with patch.object(N.os, "open", side_effect=AssertionError("uncertain scope read")):
                    self.assertIsNone(self.relay(state=state))
            finally:
                setattr(self.scope, field, old)

    def test_original_preparer_change_withholds_read(self):
        self.scope.preparer["startTicks"] += 1
        with patch.object(N.os, "open", side_effect=AssertionError("changed preparer read")):
            self.assertIsNone(self.relay())

    def test_exact0600_rejects0400_and0640(self):
        for mode in (0o400, 0o640):
            state = self.bind()
            os.chmod(self.path / "stderr.log", mode)
            try:
                self.assertIsNone(self.relay(state=state))
            finally:
                os.chmod(self.path / "stderr.log", 0o600)
        self.assertFalse(self.writer.closed)

    def test_actual_hardlink_refuses_original_file(self):
        os.link(self.path / "stderr.log", self.path / "hardlink.log")
        self.assertIsNone(self.relay())
        self.assertEqual(self.holds, [])

    def test_actual_symlink_replacement_refuses(self):
        original = self.path / "old-stderr.log"
        (self.path / "stderr.log").rename(original)
        os.symlink(str(original), self.path / "stderr.log")
        self.assertIsNone(self.relay())
        self.assertEqual(self.holds, [])

    def test_actual_regular_inode_replacement_refuses(self):
        (self.path / "stderr.log").rename(self.path / "old-stderr.log")
        descriptor = RAW_OPEN(self.path / "stderr.log", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(descriptor, SYNTHETIC)
        finally:
            RAW_CLOSE(descriptor)
        self.assertIsNone(self.relay())
        self.assertEqual(self.holds, [])

    def test_actual_parent_identity_replacement_refuses(self):
        self.path.rename(self.case / "old-service")
        self.path.mkdir(mode=0o700)
        self.assertIsNone(self.relay())
        self.assertEqual(self.holds, [])

    def test_actual_oversized_original_refuses(self):
        os.write(self.writer.fileno(), b"x" * (N.STDERR_LIMIT + 1))
        self.assertIsNone(self.relay())
        self.assertEqual(self.holds, [])

    def test_original_deadline_expiry_withholds_read(self):
        with patch.object(N.time, "monotonic", return_value=self.end), \
                patch.object(N.os, "open", side_effect=AssertionError("expired reader open")):
            self.assertIsNone(self.relay())
        self.assertEqual(self.holds, [])

    def test_actual_metadata_growth_after_read_refuses_and_closes(self):
        def grow(descriptor, maximum):
            value = RAW_READ(descriptor, maximum)
            if maximum != 1:
                os.write(self.writer.fileno(), b"x")
            return value
        with self.io_tracking(reading=grow):
            self.assertIsNone(self.relay())
        self.assert_known_closed()

    def test_actual_truncation_after_read_refuses_and_closes(self):
        def truncate(descriptor, maximum):
            value = RAW_READ(descriptor, maximum)
            if maximum != 1:
                os.truncate(self.path / "stderr.log", 0)
            return value
        with self.io_tracking(reading=truncate):
            self.assertIsNone(self.relay())
        self.assert_known_closed()

    def test_short_read_refuses_without_retry_or_eof_probe(self):
        with self.io_tracking(reading=lambda descriptor, maximum: RAW_READ(descriptor, 1)):
            self.assertIsNone(self.relay())
        self.assertEqual([maximum for _fd, maximum in self.reads], [N.STDERR_LIMIT + 1])
        self.assert_known_closed()

    def test_nonempty_eof_refuses_without_third_read(self):
        def extra(descriptor, maximum):
            return b"x" if maximum == 1 else RAW_READ(descriptor, maximum)
        with self.io_tracking(reading=extra):
            self.assertIsNone(self.relay())
        self.assertEqual([maximum for _fd, maximum in self.reads], [N.STDERR_LIMIT + 1, 1])
        self.assert_known_closed()

    def test_open_refusal_never_closes_unreturned_descriptor(self):
        failure = SyntheticFailure()
        with patch.object(N.os, "open", side_effect=failure) as opening, \
                patch.object(N.os, "close", side_effect=AssertionError("no descriptor returned")):
            self.assertIsNone(self.relay())
        self.assertEqual(opening.call_count, 1)
        self.assertIsNone(self.state.fd)
        self.assertFalse(self.state.closeAttempted)
        self.assertEqual(self.holds, [])

    def test_read_failure_preserves_returned_descriptor_close(self):
        failure = SyntheticFailure()
        def refused(descriptor, maximum):
            raise failure
        with self.io_tracking(reading=refused):
            self.assertIsNone(self.relay())
        self.assert_known_closed()

    def test_deadline_after_open_preserves_returned_descriptor_close(self):
        observed = [self.end - 1.0]
        def expire():
            observed[0] = self.end
        with patch.object(N.time, "monotonic", side_effect=lambda: observed[0]), \
                self.io_tracking(after_open=expire):
            self.assertIsNone(self.relay())
        self.assertEqual(self.reads, [])
        self.assert_known_closed()

    def test_postclose_deadline_expiry_withholds_finite_projection(self):
        observed = [self.end - 1.0]
        def expire_after_close(descriptor):
            RAW_CLOSE(descriptor)
            observed[0] = self.end
        with patch.object(N.time, "monotonic", side_effect=lambda: observed[0]), \
                self.io_tracking(closing=expire_after_close):
            self.assertIsNone(self.relay())
        self.assert_known_closed()

    def test_decoder_return_after_original_deadline_is_not_emitted(self):
        observed = [self.end - 1.0]
        decode = N.initial_before._before_child_failure_projection
        seen = []
        def slow(raw):
            seen.append(raw)
            result = decode(raw)
            observed[0] = self.end
            return result
        with patch.object(N.time, "monotonic", side_effect=lambda: observed[0]), \
                patch.object(N.initial_before, "_before_child_failure_projection", side_effect=slow), \
                self.io_tracking():
            self.assertIsNone(self.relay())
        self.assertEqual(seen, [SYNTHETIC])
        self.assert_known_closed()

    def test_postopen_mode_change_preserves_actual_descriptor_close(self):
        def change():
            os.chmod(self.path / "stderr.log", 0o400)
        with self.io_tracking(after_open=change):
            self.assertIsNone(self.relay())
        os.chmod(self.path / "stderr.log", 0o600)
        self.assertEqual(self.reads, [])
        self.assert_known_closed()

    def test_injected_postclose_ambiguity_retains_terminal_obligation_once(self):
        failure = SyntheticFailure()
        def ambiguous(descriptor):
            # Explicit MODEL: the real close succeeds, then the seam reports
            # uncertainty. We never force an ambiguous kernel close or inspect
            # the descriptor afterward, since its number could be reused.
            RAW_CLOSE(descriptor)
            raise failure
        with self.io_tracking(closing=ambiguous):
            self.assertIsNone(self.relay())
            self.assertIsNone(self.relay())
        self.assertEqual(len(self.opened), 1)
        self.assertEqual(self.closes, self.opened)
        self.assertIs(self.state.fd, self.opened[0])
        self.assertTrue(self.state.consumed)
        self.assertTrue(self.state.closeAttempted)
        self.assertFalse(self.state.closed)
        self.assertTrue(self.state.unknown)
        self.assertIs(self.state.fault, failure)
        self.assertTrue(any(value is self.state for value in self.holds))
        self.assertFalse(self.writer.closed)
        # No fstat/read/close of state.fd occurs here or in teardown.

    def test_malformed_finite_bytes_refuse_after_known_reader_close(self):
        os.truncate(self.path / "stderr.log", 0)
        os.lseek(self.writer.fileno(), 0, os.SEEK_SET)
        os.write(self.writer.fileno(), REFUSAL + b"not-json\n")
        with self.io_tracking():
            self.assertIsNone(self.relay())
        self.assert_known_closed()


class FalseyFailure(SyntheticFailure):
    def __bool__(self):
        return False


class HandlerControls(unittest.TestCase):
    """Execute exact source snippets, not a constructed operative B capability.

    These small snippets deliberately exclude launch/clock/resource/finally
    machinery. They prove exception/report ordering only, not native retirement.
    """

    def setUp(self):
        self.assertEqual(BLOCKED, [])
        functions = [node for node in NATIVE_TREE.body if isinstance(node, ast.FunctionDef) and
            node.name == "_phase_owned"]
        self.assertEqual(len(functions), 1)
        self.phase = functions[0]

    def tearDown(self):
        self.assertEqual(BLOCKED, [])

    def poll_try(self):
        candidates = [node for node in ast.walk(self.phase) if isinstance(node, ast.Try) and
            len(node.body) == 1 and isinstance(node.body[0], ast.Expr) and
            isinstance(node.body[0].value, ast.Call) and
            ast.unparse(node.body[0].value.func) == "require" and
            len(node.body[0].value.args) == 2 and
            isinstance(node.body[0].value.args[1], ast.Constant) and
            node.body[0].value.args[1].value == "BOOTSTRAP_SERVICE_CHILD_FAILED"]
        self.assertEqual(len(candidates), 1)
        return candidates[0]

    def compile_nodes(self, nodes):
        tree = ast.Module(body=nodes, type_ignores=[])
        return compile(ast.fix_missing_locations(tree), "<actual-native-before-diagnostic-snippet>", "exec")

    def run_poll(self, fault, original=None, code=125):
        events, captured, emitted = [], [], []
        state = SimpleNamespace(binding=(None,) * 6 + (17.0,), unknown=False)
        secondary = SyntheticFailure()
        def check(value, name):
            self.assertEqual(name, "BOOTSTRAP_SERVICE_CHILD_FAILED")
            events.append("require")
            if original is not None:
                self.assertIs(value, False)
                captured.append(original)
                raise original
            try:
                N.require(value, name)
            except BaseException as error:
                captured.append(error)
                raise
        def stage(name, returned=None):
            def call(*args, **kwargs):
                events.append(name)
                if name == "remember":
                    self.assertIs(args[0], captured[0])
                if fault == name:
                    raise secondary
                if name == "print":
                    emitted.append(args[0])
                    self.assertEqual(args[0], LINE)
                return returned
            return call
        namespace = {"require": check, "code": code, "child": object(), "before_diagnostic": state,
            "initial_before": SimpleNamespace(_tail_failure_remember=stage("remember")),
            "_before_child_diagnostic": stage("helper", LINE),
            "posix": SimpleNamespace(_deadline=stage("deadline")), "print": stage("print"), "sys": sys}
        program = self.compile_nodes([self.poll_try()])
        if code == 0:
            exec(program, namespace)
            self.assertEqual(events, ["require"])
            self.assertEqual(captured, [])
            self.assertEqual(emitted, [])
            return
        with self.assertRaises(BaseException) as caught:
            exec(program, namespace)
        self.assertEqual(len(captured), 1)
        self.assertIs(caught.exception, captured[0])
        self.assertIsNot(caught.exception, secondary)
        self.assertEqual(events[0], "require")
        self.assertEqual(events[1], "remember")
        return events, emitted

    def test_actual_failed_poll_preserves_require_exception_under_optional_faults(self):
        for fault in (None, "remember", "helper", "deadline", "print"):
            with self.subTest(fault=fault):
                events, emitted = self.run_poll(fault)
                self.assertEqual(events.count("helper"), 1)
                self.assertEqual(len(emitted), 1 if fault in (None, "remember") else 0)

    def test_falsey_unprintable_baseexceptions_are_reraised_by_identity(self):
        for failure in (SyntheticFailure(), FalseyFailure()):
            for fault in ("remember", "helper", "deadline", "print"):
                with self.subTest(kind=type(failure).__name__, fault=fault):
                    self.run_poll(fault, original=failure)

    def test_successful_status_never_enters_optional_diagnostic(self):
        self.run_poll(None, code=0)

    def test_optional_prelaunch_binding_fault_cannot_refuse_launch(self):
        candidates = [node for node in ast.walk(self.phase) if isinstance(node, ast.Try) and
            len(node.body) == 1 and isinstance(node.body[0], ast.Assign) and
            isinstance(node.body[0].value, ast.Call) and
            ast.unparse(node.body[0].value.func) == "_before_child_diagnostic_binding"]
        self.assertEqual(len(candidates), 1)
        supplied = object()
        for raises in (False, True):
            seen = []
            def binding(*args):
                seen.append(args)
                if raises:
                    raise SyntheticFailure()
                return supplied
            namespace = {"_before_child_diagnostic_binding": binding, "context": {},
                "start": {"role": "linux-x64"},
                "directory": object(), "err": object(), "scope": object(), "capture_end": 17.0,
                "row": {"preparerIdentity": {}}, "owner": SimpleNamespace(unknown=False)}
            exec(self.compile_nodes([candidates[0]]), namespace)
            self.assertEqual(len(seen), 1)
            self.assertIs(namespace["before_diagnostic"], None if raises else supplied)

    def test_original_phase_finally_is_unchanged_from_reviewed_ae3(self):
        # Independently supplied by the root's original Git-blob comparison,
        # NOT regenerated from this candidate to satisfy this assertion.
        # ae3 native blob SHA256:
        # 4fd2b55c17a2ded3969461ef2d515957b2129592a8a9f3b24e905bc2f7df119d
        candidates = [node for node in self.phase.body if isinstance(node, ast.Try) and
            any(isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call) and
                ast.unparse(statement.value.func) == "owner.error" and statement.value.args and
                isinstance(statement.value.args[0], ast.Constant) and statement.value.args[0].value == "service"
                for handler in node.handlers for statement in handler.body)]
        self.assertEqual(len(candidates), 1)
        exact = ast.dump(ast.Module(body=candidates[0].finalbody, type_ignores=[]),
            include_attributes=False).encode()
        self.assertEqual(hashlib.sha256(exact).hexdigest(),
            "6a3108fc67cd8ffc1c98d26da307e02e222c4776bdc5c4c4e613acde7014acac")

    def test_secondary_unknown_follows_original_install_even_if_report_fails(self):
        handlers = [node for node in ast.walk(self.phase) if isinstance(node, ast.ExceptHandler) and
            any(isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call) and
                ast.unparse(statement.value.func) == "owner.error" and
                statement.value.args and isinstance(statement.value.args[0], ast.Constant) and
                statement.value.args[0].value == "service" for statement in node.body)]
        self.assertEqual(len(handlers), 1)
        program = self.compile_nodes([ast.Try(
            body=[ast.Raise(exc=ast.Name(id="original", ctx=ast.Load()), cause=None)],
            handlers=[handlers[0]], orelse=[], finalbody=[])])
        for report_fault, setter_fault in ((False, False), (True, False), (True, True)):
            with self.subTest(report_fault=report_fault, setter_fault=setter_fault):
                original, secondary, events = FalseyFailure(), SyntheticFailure(), []
                class SuppliedOwner:
                    first = None
                    _unknown = False

                    @property
                    def unknown(self):
                        return self._unknown

                    @unknown.setter
                    def unknown(self, value):
                        events.append("unknown")
                        if setter_fault:
                            raise secondary
                        self._unknown = value

                    def error(self, stage, error, *, unknown=False):
                        events.append(stage)
                        if self.first is None:
                            self.first = error
                        if stage == "before-child-diagnostic-close" and report_fault:
                            raise secondary
                        if unknown:
                            self.unknown = True
                owner = SuppliedOwner()
                namespace = {"original": original, "custody_phase": None, "owner": owner,
                    "before_diagnostic": SimpleNamespace(unknown=True), "origin": N.origin}
                exec(program, namespace)
                self.assertIs(owner.first, original)
                self.assertEqual(events[:2], ["service", "before-child-diagnostic-close"])
                self.assertEqual(events.count("before-child-diagnostic-close"), 1)
                self.assertEqual(events.count("unknown"), 1)
                if not setter_fault:
                    self.assertTrue(owner.unknown)


class FirstFailureReader(unittest.TestCase):
    """One new origin through the unchanged real reader, not a native launch."""

    line = json.dumps({**VALUE, "origin": "FIRST_FAILURE"}, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False)
    packet = REFUSAL + line.encode("ascii") + b"\n"
    setUp = ReaderComposition.setUp
    tearDown = ReaderComposition.tearDown
    bind = ReaderComposition.bind
    relay = ReaderComposition.relay
    io_tracking = ReaderComposition.io_tracking
    assert_known_closed = ReaderComposition.assert_known_closed

    def test_first_failure_finite_packet_known_reader_close(self):
        with self.io_tracking():
            self.assertEqual(self.relay(), self.line)
        self.assertEqual([count for _fd, count in self.reads], [N.STDERR_LIMIT + 1, 1])
        self.assert_known_closed()
        self.assertGreater(self.scope.discovery_calls, 0)
        self.writer.write(b"")


if __name__ == "__main__":
    unittest.main(failfast=True)
