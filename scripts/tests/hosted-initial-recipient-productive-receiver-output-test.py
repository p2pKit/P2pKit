#!/usr/bin/env python3
"""New R seal-append connection models, NOT original native/custody acceptance.

Real C/RD/writer and R append/guard/state machinery; prior seal registration,
clocks, paths/stat/fds are explicit in-memory models. No old test method runs.
Neither successful DATA nor modeled file close can qualify a hosted Step.
"""
from __future__ import annotations

from contextlib import ExitStack
import ctypes
import importlib.util
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ACTIVE = False
BLOCKED = []
WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND | getattr(os, "O_TMPFILE", 0)


def offline(event, args):
    write_open = event == "open" and (isinstance(args[1], str) and any(letter in args[1] for letter in "wax+") or
        isinstance(args[2], int) and args[2] & WRITE_FLAGS != 0)
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv", "os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.link", "os.symlink",
            "os.truncate", "os.chmod", "os.chown", "os.utime", "os.chdir") or write_open or \
            ACTIVE and event in ("open", "os.listdir", "os.scandir"):
        BLOCKED.append(event)
        raise AssertionError("RECEIVER_OUTPUT_MODEL_REAL_EFFECT")


sys.dont_write_bytecode = True
sys.addaudithook(offline)
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
# Deliberately exercise the cycle-sensitive BEFORE-first source import order.
import hosted_initial_recipient_before as BEFORE
import hosted_initial_recipient_continuity as C
import hosted_initial_recipient_productive_receiver_data as RD
import hosted_initial_recipient_productive_receiver as R

# Reuse only ModelCase fixture methods. No prior test class is inherited or run.
spec = importlib.util.spec_from_file_location("receiver_output_prior_model_fixture",
    ROOT / "scripts/tests/hosted-initial-recipient-productive-receiver-test.py")
BASE = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = BASE
spec.loader.exec_module(BASE)

FIELDS = ("initialProductiveSealSha256", "initialProductiveSealEndNs", "initialProductiveSealClockRole",
    "initialProductiveSealClockDomain", "initialProductiveSealClockTicksPerSecond", "initialProductiveSealBootSha256")
DOMAINS = {
    "linux-x64": "linux.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "windows-x64": "windows.QueryPerformanceCounter/QueryPerformanceFrequency.floor_ns",
    "macos-arm64": "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
    "macos-x64": "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
}
NS = 1000000000
FAILURES = (ValueError, RuntimeError)


def rows(role="linux-x64", *, checksum="a" * 64, end=220 * NS):
    frequency = 10000000 if role == "windows-x64" else NS
    return tuple(zip(FIELDS, (checksum, str(end), role, DOMAINS[role], str(frequency), "b" * 64)))


def change(values, number, value):
    return tuple((name, value if index == number else old) for index, (name, old) in enumerate(values))


def expected_bytes(values):
    return "".join(name + "=" + value + "\n" for name, value in values).encode("ascii")


def guarded(function, *args, **kwargs):
    global ACTIVE
    previous, count = ACTIVE, len(BLOCKED)
    ACTIVE = True
    try:
        return BASE.guarded(function, *args, **kwargs)
    finally:
        ACTIVE = previous
        if len(BLOCKED) != count:
            raise AssertionError("RECEIVER_OUTPUT_MODEL_REAL_EFFECT")


class ModelFailure(RuntimeError):
    pass


class MemoryPath:
    """Only lexical paths/stat observations, never a filesystem capability."""
    def __init__(self, model, value):
        self.model, self.value = model, PurePosixPath(value)

    def __eq__(self, other):
        return type(other) is MemoryPath and self.model is other.model and self.value == other.value

    def __truediv__(self, value):
        return MemoryPath(self.model, self.value / value)

    def is_absolute(self):
        return self.value.is_absolute()

    parts = property(lambda self: self.value.parts)
    name = property(lambda self: self.value.name)
    parent = property(lambda self: MemoryPath(self.model, self.value.parent))
    parents = property(lambda self: tuple(MemoryPath(self.model, value) for value in self.value.parents))

    def lstat(self):
        return self.model.lstat(str(self.value))


class FileModel:
    """Explicit bounded external observations for the UNCHANGED real C writer."""
    def __init__(self):
        self.parent = "/model/receiver-output"
        self.target = self.parent + "/_runner_file_commands/set_output_00112233-4455-6677-8899-aabbccddeeff"
        self.raw = bytearray()
        self.fd = 71
        self.offset = 0
        self.opened = self.closed = False
        self.events = []
        self.action = lambda _event: None
        self.file_changes, self.directory_changes, self.descriptor_changes = {}, {}, {}
        self.short_write = self.bad_readback = False
        self.write_failure = self.fsync_failure = self.close_failure = None

    def event(self, name):
        self.events.append(name)
        self.action(name)

    def info(self, path, *, descriptor=False):
        file = path == self.target
        inode = 100 if file else 200 + len(PurePosixPath(path).parts)
        values = dict(st_dev=1, st_ino=inode, st_mode=(stat.S_IFREG | 0o600) if file else (stat.S_IFDIR | 0o700),
            st_uid=12345, st_gid=12345, st_nlink=1 if file else 2, st_size=len(self.raw) if file else 0,
            st_file_attributes=0)
        values.update(self.file_changes if file else self.directory_changes)
        if descriptor:
            values.update(self.descriptor_changes)
        return SimpleNamespace(**values)

    def lstat(self, path):
        self.event("lstat-file" if path == self.target else "lstat-parent")
        return self.info(path)

    def open(self, path, flags):
        assert type(path) is MemoryPath and str(path.value) == self.target
        assert not self.opened and flags & C.os.O_APPEND and flags & C.os.O_RDWR
        self.opened = True
        self.event("open")
        return self.fd

    def require_fd(self, fd):
        assert fd == self.fd and self.opened and not self.closed

    def fstat(self, fd):
        self.require_fd(fd)
        self.event("fstat")
        return self.info(self.target, descriptor=True)

    def write(self, fd, raw):
        self.require_fd(fd)
        assert type(raw) is bytes and len(raw) <= 1024
        self.event("write")
        if self.write_failure is not None:
            raise self.write_failure
        count = len(raw) - 1 if self.short_write else len(raw)
        self.raw.extend(raw[:count])
        return count

    def fsync(self, fd):
        self.require_fd(fd)
        self.event("fsync")
        if self.fsync_failure is not None:
            raise self.fsync_failure

    def lseek(self, fd, offset, origin):
        self.require_fd(fd)
        assert offset == 0 and origin == C.os.SEEK_SET
        self.event("seek")
        self.offset = 0
        return 0

    def read(self, fd, size):
        self.require_fd(fd)
        assert size == len(self.raw) + 1
        self.event("read")
        return b"MODEL_WRONG_READBACK" if self.bad_readback else bytes(self.raw)

    def close(self, fd):
        self.require_fd(fd)
        self.event("close")
        if self.close_failure is not None:
            raise self.close_failure  # No actual OS descriptor exists or is abandoned.
        self.closed = True

    def install(self, stack):
        stack.enter_context(patch.object(C, "Path", lambda value: MemoryPath(self, value)))
        stack.enter_context(patch.object(C.os, "environ", {"RUNNER_TEMP": self.parent, "GITHUB_OUTPUT": self.target}))
        stack.enter_context(patch.object(C.os, "name", "posix"))
        stack.enter_context(patch.object(C.os, "geteuid", lambda: 12345, create=True))
        for name in ("open", "fstat", "write", "fsync", "lseek", "read", "close"):
            stack.enter_context(patch.object(C.os, name, getattr(self, name)))
        return self


class HelperModels(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        # A new MODEL quarantine, not clearing a genuine original resource.
        self.quarantine = []
        self.stack.enter_context(patch.object(C, "QUARANTINE", self.quarantine))
        self.model = FileModel().install(self.stack)
        self.calls = 0
        self.action = lambda: None

    def check(self):
        self.calls += 1
        self.model.events.append("guard")
        self.action()

    def append(self, values=None, check=None):
        return guarded(C.append_productive_receiver_outputs, rows() if values is None else values,
            self.check if check is None else check)

    def refuses(self, function, *args):
        with self.assertRaises(FAILURES) as caught:
            guarded(function, *args)
        return caught.exception

    def test_before_first_import_and_actual_singleton_connection(self):
        self.assertIs(R.N.continuity, C)
        self.assertIs(R.C.C, C)
        self.assertIs(R.RD, RD)
        self.assertIs(RD.B, BEFORE)
        self.assertIs(BEFORE.continuity, C)
        self.assertEqual(RD.OUTPUT_FIELDS, FIELDS)
        self.assertTrue(callable(C.append_productive_receiver_outputs))

    def test_exact_real_codec_writer_bytes_five_original_guards_and_known_close(self):
        values = rows()
        self.assertIsNone(self.append(values))
        self.assertEqual(bytes(self.model.raw), expected_bytes(values))
        self.assertEqual(self.calls, 5)
        self.assertEqual([event for event in self.model.events if event in
            ("guard", "open", "write", "fsync", "seek", "read", "close")],
            ["guard", "guard", "open", "guard", "write", "fsync", "guard", "seek", "read", "close", "guard"])
        self.assertTrue(self.model.closed)
        self.assertFalse(self.quarantine)

    def test_all_four_role_grammars_reach_actual_writer_without_native_clock(self):
        for role in DOMAINS:
            with self.subTest(role=role), ExitStack() as stack:
                model = FileModel().install(stack)
                calls = []
                values = rows(role)
                guarded(C.append_productive_receiver_outputs, values, lambda: calls.append(True))
                self.assertEqual(bytes(model.raw), expected_bytes(values))
                self.assertEqual(len(calls), 5)
                self.assertTrue(model.closed)

    def test_declared_integer_upper_edges_are_data_not_clock_observations(self):
        values = (rows(end=(1 << 64) - 1), change(rows("windows-x64"), 4, str((1 << 63) - 1)))
        for supplied in values:
            with self.subTest(values=supplied), ExitStack() as stack:
                model = FileModel().install(stack)
                guarded(C.append_productive_receiver_outputs, supplied, lambda: None)
                self.assertEqual(bytes(model.raw), expected_bytes(supplied))
                self.assertTrue(model.closed)

    def test_closed_tuple_names_order_count_and_exact_slot_types_before_any_effect(self):
        class TupleSubclass(tuple):
            pass
        class StringSubclass(str):
            pass
        good = rows()
        bad = (list(good), dict(good), good[:-1], (*good, ("closedNs", "1")), tuple(reversed(good)),
            (good[0], good[0], *good[2:]), TupleSubclass(good), (list(good[0]), *good[1:]),
            (TupleSubclass(good[0]), *good[1:]), ((), *good[1:]), ((*good[0], "extra"), *good[1:]),
            ((StringSubclass(good[0][0]), good[0][1]), *good[1:]),
            (("rawPrivateOriginal", good[0][1]), *good[1:]), change(good, 0, StringSubclass("a" * 64)))
        for values in bad:
            with self.subTest(shape=type(values).__name__):
                self.refuses(C.append_productive_receiver_outputs, values, self.check)
        self.assertEqual(self.model.events, [])
        self.assertEqual(self.calls, 0)

    def test_hash_integer_clock_and_value_negatives_cannot_open_output(self):
        good = rows()
        changes = ((0, "A" * 64), (5, "b" * 63), (0, "private\nextra=value"), (0, True),
            (1, "0"), (1, "01"), (1, "-1"), (1, "1.0"), (1, str(1 << 64)), (1, "١"),
            (4, "0"), (4, str(1 << 63)), (4, str(NS + 1)), (2, "linux"), (3, "model.clock"))
        for number, value in changes:
            with self.subTest(number=number, value=value):
                self.refuses(C.append_productive_receiver_outputs, change(good, number, value), self.check)
        self.assertEqual(self.model.events, [])

    def test_legacy_and_final_two_hash_grammars_remain_disjoint(self):
        for encoder in (C._output_bytes, C._productive_output_bytes):
            self.refuses(encoder, dict(rows()))
        for values in ({"initialSealSha256": "a" * 64},
                {"initialProductiveExportTransferSha256": "a" * 64, "initialProductiveManifestSha256": "b" * 64}):
            self.refuses(C.append_productive_receiver_outputs, tuple(values.items()), self.check)
        self.assertEqual(guarded(C._output_bytes, {"initialSealSha256": "a" * 64}),
            b"initialSealSha256=" + b"a" * 64 + b"\n")
        self.assertEqual(guarded(C._productive_output_bytes, {"initialProductiveCollectCloseSha256": "a" * 64,
            "initialProductiveManifestSha256": "b" * 64}),
            b"initialProductiveCollectCloseSha256=" + b"a" * 64 + b"\ninitialProductiveManifestSha256=" + b"b" * 64 + b"\n")
        self.assertFalse(self.model.events)

    def test_noncallable_original_check_is_not_hidden_by_a_callable_wrapper(self):
        for check in (None, False, 0, object()):
            with self.subTest(check=type(check).__name__):
                error = self.refuses(C.append_productive_receiver_outputs, rows(), check)
                self.assertIsInstance(error, C.ContinuityError)
                self.assertEqual(str(error), "STEP_OUTPUT_FIELDS")
        self.assertEqual(self.model.events, [])

    def test_existing_quarantine_refuses_without_reset_or_writer_effect(self):
        original = object()
        self.quarantine.append(original)
        self.refuses(C.append_productive_receiver_outputs, rows(), self.check)
        self.assertEqual(self.quarantine, [original])
        self.assertEqual(self.model.events, [])

    def test_c_load_owned_suppliers_cannot_be_rebaselined_at_entry(self):
        original = C.append_productive_receiver_outputs
        for name in ("require", "_append_output_bytes", "_receiver_output_current",
                "append_productive_receiver_outputs", "clocks"):
            invoked = []
            def replacement(*_args):
                invoked.append(True)
                raise AssertionError("REPLACED_C_SUPPLIER_WAS_CALLED")
            with self.subTest(name=name), patch.object(C, name, replacement):
                self.refuses(original, rows(), self.check)
            self.assertFalse(invoked)
        self.assertFalse(self.model.events)

    def test_c_load_anchor_replacement_at_entry_cannot_supply_a_new_checker(self):
        original, anchor, invoked = C.append_productive_receiver_outputs, C._RECEIVER_OUTPUT_SOURCE, []
        def replacement(*_args):
            invoked.append(True)
            raise AssertionError("REPLACED_C_ANCHOR_SUPPLIER_WAS_CALLED")
        for value in (tuple(list(anchor)), (*anchor[:4], replacement, replacement, replacement, original)):
            with self.subTest(anchor=value), patch.object(C, "_RECEIVER_OUTPUT_SOURCE", value):
                error = self.refuses(original, rows(), self.check)
                self.assertEqual(str(error), "RECEIVER_OUTPUT_SOURCE_CHANGED")
        self.assertFalse(invoked)
        self.assertFalse(self.model.events)

    def test_c_supplier_swaps_at_each_existing_guard_use_only_load_owned_checks(self):
        original = C.append_productive_receiver_outputs
        for name in ("require", "_append_output_bytes", "_receiver_output_current",
                "append_productive_receiver_outputs", "clocks"):
            for at in range(1, 6):
                with self.subTest(name=name, guard=at), ExitStack() as stack:
                    model = FileModel().install(stack)
                    calls, invoked = [], []
                    def replacement(*_args):
                        invoked.append(True)
                        raise AssertionError("REPLACED_C_SUPPLIER_WAS_CALLED")
                    def check():
                        calls.append(True)
                        if len(calls) == at:
                            stack.enter_context(patch.object(C, name, replacement))
                    error = self.refuses(original, rows(), check)
                    self.assertEqual(str(error), "RECEIVER_OUTPUT_SOURCE_CHANGED")
                    self.assertFalse(invoked)
                    self.assertEqual(len(calls), at)
                    if at == 1:
                        self.assertEqual(model.events, [])
                    if at <= 2:
                        self.assertNotIn("open", model.events)
                    if at <= 3:
                        self.assertNotIn("write", model.events)
                    if at <= 4:
                        self.assertNotIn("read", model.events)
                    if model.opened:
                        self.assertEqual(model.events.count("close"), 1)

    def test_codec_replacement_at_each_existing_guard_is_not_adopted_or_called(self):
        original = C.append_productive_receiver_outputs
        for at in range(1, 6):
            with self.subTest(guard=at), ExitStack() as stack:
                model = FileModel().install(stack)
                calls, invoked = [], []
                def replacement(_values):
                    invoked.append(True)
                    raise AssertionError("REPLACED_CODEC_WAS_CALLED")
                def check():
                    calls.append(True)
                    if len(calls) == at:
                        stack.enter_context(patch.object(RD, "encode_output_values", replacement))
                self.refuses(original, rows(), check)
                self.assertFalse(invoked)
                self.assertEqual(len(calls), at)
                if at == 1:
                    self.assertEqual(model.events, [])
                if at <= 2:
                    self.assertNotIn("open", model.events)
                if at <= 3:
                    self.assertNotIn("write", model.events)
                if at <= 4:
                    self.assertNotIn("read", model.events)
                if model.opened:
                    self.assertEqual(model.events.count("close"), 1)

    def test_append_local_codec_module_predicate_fields_and_graph_changes_refuse(self):
        targets = ((RD, "output_values"), (RD, "OUTPUT_FIELDS"), (RD, "B"), (RD, "CD"), (RD, "O"),
            (BEFORE, "continuity"), (RD.CD, "O"), (RD.O, "clocks"))
        for module, name in targets:
            with self.subTest(name=name), ExitStack() as stack:
                invoked = []
                def replacement(*_args):
                    invoked.append(True)
                    raise AssertionError("REPLACED_CODEC_DEPENDENCY_WAS_CALLED")
                def check():
                    stack.enter_context(patch.object(module, name, replacement))
                self.refuses(C.append_productive_receiver_outputs, rows(), check)
                self.assertFalse(invoked)
        self.assertFalse(self.model.events)
        with ExitStack() as stack:
            def check():
                stack.enter_context(patch.dict(sys.modules,
                    {"hosted_initial_recipient_productive_receiver_data": object()}))
            error = self.refuses(C.append_productive_receiver_outputs, rows(), check)
            self.assertEqual(str(error), "RECEIVER_OUTPUT_CODEC_CHANGED")
        self.assertFalse(self.model.events)

    def test_c_runtime_and_canonical_module_identity_changes_during_guard_refuse(self):
        with ExitStack() as stack:
            def check():
                stack.enter_context(patch.object(C, "sys", SimpleNamespace(modules=sys.modules)))
            error = self.refuses(C.append_productive_receiver_outputs, rows(), check)
            self.assertEqual(str(error), "RECEIVER_OUTPUT_SOURCE_CHANGED")
        with ExitStack() as stack:
            def check():
                stack.enter_context(patch.dict(sys.modules, {"hosted_initial_recipient_continuity": object()}))
            error = self.refuses(C.append_productive_receiver_outputs, rows(), check)
            self.assertEqual(str(error), "RECEIVER_OUTPUT_SOURCE_CHANGED")
        with ExitStack() as stack:
            def check():
                stack.enter_context(patch.object(sys, "modules", dict(sys.modules)))
            error = self.refuses(C.append_productive_receiver_outputs, rows(), check)
            self.assertEqual(str(error), "RECEIVER_OUTPUT_SOURCE_CHANGED")
        self.assertEqual(self.model.events, [])

    def test_source_anchor_and_quarantine_replacement_during_guard_refuse(self):
        original = C._RECEIVER_OUTPUT_SOURCE
        with ExitStack() as stack:
            def check():
                stack.enter_context(patch.object(C, "_RECEIVER_OUTPUT_SOURCE", tuple(list(original))))
            self.refuses(C.append_productive_receiver_outputs, rows(), check)
        with ExitStack() as stack:
            def check():
                stack.enter_context(patch.object(C, "QUARANTINE", []))
            self.refuses(C.append_productive_receiver_outputs, rows(), check)
        self.assertEqual(self.model.events, [])

    def test_original_guard_failure_before_open_is_unchanged(self):
        first = ModelFailure("MODEL_GUARD_FIRST")
        def fail():
            raise first
        self.assertIs(self.refuses(C.append_productive_receiver_outputs, rows(), fail), first)
        self.assertFalse(self.model.events)

    def test_original_guard_failure_after_write_still_closes_exactly_once(self):
        first = ModelFailure("MODEL_GUARD_AFTER_FSYNC")
        def fail():
            if self.calls == 4:
                raise first
        self.action = fail
        self.assertIs(self.refuses(C.append_productive_receiver_outputs, rows(), self.check), first)
        self.assertEqual(bytes(self.model.raw), expected_bytes(rows()))
        self.assertTrue(self.model.closed)
        self.assertEqual(self.model.events.count("close"), 1)
        self.assertNotIn("read", self.model.events)

    def test_original_guard_failure_after_open_closes_without_writing(self):
        first = ModelFailure("MODEL_GUARD_AFTER_OPEN")
        def fail():
            if self.calls == 3:
                raise first
        self.action = fail
        self.assertIs(self.refuses(C.append_productive_receiver_outputs, rows(), self.check), first)
        self.assertTrue(self.model.closed)
        self.assertNotIn("write", self.model.events)
        self.assertEqual(self.model.events.count("close"), 1)

    def test_post_close_guard_failure_is_not_a_successful_file_command(self):
        first = ModelFailure("MODEL_POST_CLOSE_GUARD")
        def fail():
            if self.calls == 5:
                raise first
        self.action = fail
        self.assertIs(self.refuses(C.append_productive_receiver_outputs, rows(), self.check), first)
        self.assertTrue(self.model.closed)
        self.assertEqual(self.model.events.count("close"), 1)

    def test_unsafe_nonempty_and_changed_file_observations_are_not_originals(self):
        for changes in ({"st_mode": stat.S_IFLNK | 0o777}, {"st_nlink": 2}, {"st_uid": 9},
                {"st_size": 1}, {"st_file_attributes": 0x400}):
            with self.subTest(changes=changes), ExitStack() as stack:
                model = FileModel().install(stack)
                model.file_changes = changes
                self.refuses(C.append_productive_receiver_outputs, rows(), lambda: None)
                self.assertNotIn("open", model.events)
        self.model.descriptor_changes["st_ino"] = 999
        self.refuses(C.append_productive_receiver_outputs, rows(), self.check)
        self.assertTrue(self.model.closed)
        self.assertNotIn("write", self.model.events)

    def test_wrong_output_path_and_unsafe_parent_refuse_before_open(self):
        for target in ("relative", "/model/not-a-runner-output", self.model.target + "-extra"):
            with self.subTest(target=target), patch.object(C.os, "environ",
                    {"RUNNER_TEMP": self.model.parent, "GITHUB_OUTPUT": target}):
                self.refuses(C.append_productive_receiver_outputs, rows(), self.check)
        self.model.directory_changes["st_file_attributes"] = 0x400
        self.refuses(C.append_productive_receiver_outputs, rows(), self.check)
        self.assertNotIn("open", self.model.events)

    def test_short_write_and_wrong_readback_keep_original_close_path(self):
        for mode in ("short_write", "bad_readback"):
            with self.subTest(mode=mode), ExitStack() as stack:
                model = FileModel().install(stack)
                setattr(model, mode, True)
                self.refuses(C.append_productive_receiver_outputs, rows(), lambda: None)
                self.assertTrue(model.closed)
                self.assertEqual(model.events.count("write"), 1)
                self.assertEqual(model.events.count("close"), 1)

    def test_fsync_failure_is_original_and_not_replaced_by_a_close_failure(self):
        first = ModelFailure("MODEL_FSYNC_FIRST")
        second = ModelFailure("MODEL_CLOSE_SECOND")
        self.model.fsync_failure, self.model.close_failure = first, second
        self.assertIs(self.refuses(C.append_productive_receiver_outputs, rows(), self.check), first)
        self.assertIs(first.__cause__, second)
        self.assertEqual(self.quarantine, [self.model.fd])
        self.assertEqual(self.model.events.count("close"), 1)
        self.assertFalse(self.model.closed)
        self.refuses(C.append_productive_receiver_outputs, rows(), self.check)
        self.assertEqual(self.model.events.count("open"), 1)

    def test_original_write_failure_reaches_known_close_without_fsync_or_retry(self):
        first = ModelFailure("MODEL_WRITE_FIRST")
        self.model.write_failure = first
        self.assertIs(self.refuses(C.append_productive_receiver_outputs, rows(), self.check), first)
        self.assertTrue(self.model.closed)
        self.assertEqual(self.model.events.count("write"), 1)
        self.assertNotIn("fsync", self.model.events)
        self.assertEqual(bytes(self.model.raw), b"")

    def test_unknown_close_alone_retains_model_descriptor_and_denies_return(self):
        self.model.close_failure = ModelFailure("MODEL_CLOSE_UNKNOWN")
        error = self.refuses(C.append_productive_receiver_outputs, rows(), self.check)
        self.assertEqual(str(error), "STEP_OUTPUT_CLOSE_UNKNOWN")
        self.assertEqual(self.quarantine, [self.model.fd])
        self.assertFalse(self.model.closed)
        self.assertEqual(self.calls, 4)

    def test_parent_identity_change_after_write_cannot_pass_readback(self):
        def change_parent(event):
            if event == "write":
                self.model.directory_changes["st_ino"] = 999
        self.model.action = change_parent
        error = self.refuses(C.append_productive_receiver_outputs, rows(), self.check)
        self.assertEqual(str(error), "STEP_OUTPUT_PARENT_CHANGED")
        self.assertTrue(self.model.closed)


class ReceiverAppendModels(BASE.ModelCase):
    """Actual seal append path; only PRIOR registration/acquisition is modeled."""
    def setUp(self):
        super().setUp()
        self.original_return = None
        # This explicit predecessor seam is installed BEFORE the real R entry
        # pins its methods. No C load-owned source pin is patched into a pass.
        self.install(R, "_registered", self.registered_model)
        self.model = FileModel().install(self.stack)

    def check(self, function, *args, **kwargs):
        return guarded(function, *args, **kwargs)

    def registered_model(self, result, *, complete=False):
        saved = self.original_return
        R.require(type(complete) is bool and type(saved) is R._Return and saved.result is result and
            R._RETURNS.get(id(result)) is saved and saved.state.result is result,
            "MODEL_PRIOR_SEAL_REGISTRATION_ONLY")
        R._pin(saved)
        R._pin(result)
        R._pin(saved.state)
        R._entry_check(saved.state.entry)
        if complete:
            entry = saved.state.entry
            entry.latch.returned(entry.table, entry.attempt, result)
        return saved

    def output(self):
        state = self.state("seal")
        # MODEL of a previously acquired/clipped seal. This is not a real
        # closed-metadata transition or a fabricated actual authority return.
        self.check(R._update, state.clock, phase="SEAL", seal_first=self.raw, seal_end=self.raw + 120 * NS)
        result = self.check(R._track, R._SealReturn(b"MODEL_SEAL_NOT_NATIVE", b"MODEL_WRITER", b"MODEL_CIPHERTEXT"))
        self.check(R._update, state, result=result)
        self.original_return = self.check(R._track, R._Return(state, result, None, (), (), ()))
        R._RETURNS[id(result)] = self.original_return
        values = rows(checksum=R.O.digest(result.raw), end=state.clock.seal_end)
        value = {"schema": 1, "scope": RD.SEAL_OUTPUT_SCOPE, **dict(values),
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        fence = self.check(R._output_fence, result, value, outputs=values)
        return state, result, values, value, fence

    def append_complete(self):
        state, result, values, value, fence = self.output()
        returned = self.check(fence.append)
        self.check(state.entry.latch.complete, state.entry.table, state.entry.attempt, result)
        self.assertIs(returned[0], value)
        self.assertIs(returned[1], fence)
        self.assertEqual(returned[2], state.clock.work)
        return state, result, values, value, fence

    def test_real_seal_append_connection_then_exact_two_original_late_checks(self):
        state, result, values, value, fence = self.append_complete()
        self.assertIs(type(result), R._SealReturn)
        saved = R._OUTPUTS[id(fence)]
        self.assertFalse(saved.child)
        self.assertEqual(saved.phase, "OUTPUT")
        self.assertEqual(bytes(self.model.raw), expected_bytes(values))
        self.assertEqual(self.callbacks, 6)  # Five actual writer checks, then the original R append guard.
        self.assertTrue(self.model.closed)
        self.assertEqual(self.model.events.count("write"), 1)
        self.assertEqual(self.check(fence.now, final=True, limit=state.clock.work), self.raw)
        self.assertEqual(self.check(fence.now, final=True, limit=state.clock.work), self.raw)
        self.assertEqual(saved.checks, 2)
        self.assertFalse(value["exportSaveAuthority"])
        self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")

    def test_late_output_before_append_refuses_without_a_writer_effect(self):
        state, _result, _values, _value, fence = self.output()
        first = self.refuses(fence.now, final=True, limit=state.clock.work)
        self.assertIs(self.refuses(fence.append), first)
        self.assertFalse(self.model.events)

    def test_second_append_and_later_stdout_retain_the_first_failure(self):
        state, _result, _values, _value, fence = self.append_complete()
        first = self.refuses(fence.append)
        self.assertIs(self.refuses(fence.now, final=True, limit=state.clock.work), first)
        self.assertEqual(self.model.events.count("open"), 1)
        self.assertEqual(self.model.events.count("write"), 1)

    def test_third_late_check_is_not_an_extra_fresh_window(self):
        state, _result, _values, _value, fence = self.append_complete()
        self.check(fence.now, final=True, limit=state.clock.work)
        self.check(fence.now, final=True, limit=state.clock.work)
        first = self.refuses(fence.now, final=True, limit=state.clock.work)
        self.assertIs(self.refuses(fence.now, final=True, limit=state.clock.work), first)

    def test_original_raw_equality_before_first_writer_guard_refuses(self):
        state, _result, _values, _value, fence = self.output()
        self.raw = state.clock.work
        first = self.refuses(fence.append)
        self.raw -= NS
        self.assertIs(self.refuses(fence.append), first)
        self.assertFalse(self.model.events)

    def test_original_local_equality_before_first_writer_guard_refuses(self):
        state, _result, _values, _value, fence = self.output()
        self.local = state.clock.final_local
        first = self.refuses(fence.append)
        self.local -= 1
        self.assertIs(self.refuses(fence.append), first)
        self.assertFalse(self.model.events)

    def test_original_cancellation_is_not_swallowed_before_open(self):
        state, _result, _values, _value, fence = self.output()
        first = ModelFailure("MODEL_ORIGINAL_CANCEL")
        def cancelled():
            raise first
        self.action = cancelled
        self.assertIs(self.refuses(fence.append), first)
        self.action = lambda: None
        self.assertIs(self.refuses(fence.now, final=True, limit=state.clock.work), first)
        self.assertFalse(self.model.events)

    def test_raw_expiry_after_write_closes_but_cannot_transition_to_output(self):
        state, _result, _values, _value, fence = self.output()
        def expire(event):
            if event == "write":
                self.raw = state.clock.work
        self.model.action = expire
        first = self.refuses(fence.append)
        self.assertTrue(self.model.closed)
        self.assertEqual(R._OUTPUTS[id(fence)].phase, "APPENDING")
        self.raw -= NS
        self.assertIs(self.refuses(fence.now, final=True, limit=state.clock.work), first)

    def test_local_expiry_after_fsync_retains_known_close_and_failure(self):
        state, _result, _values, _value, fence = self.output()
        def expire(event):
            if event == "fsync":
                self.local = state.clock.final_local
        self.model.action = expire
        first = self.refuses(fence.append)
        self.assertTrue(self.model.closed)
        self.local -= 1
        self.assertIs(self.refuses(fence.append), first)

    def test_raw_expiry_after_actual_model_close_cannot_return_success(self):
        state, _result, _values, _value, fence = self.output()
        def expire(event):
            if event == "close":
                self.raw = state.clock.work
        self.model.action = expire
        first = self.refuses(fence.append)
        self.assertTrue(self.model.closed)
        self.assertEqual(self.model.events.count("close"), 1)
        self.assertIs(self.refuses(fence.now, final=True, limit=state.clock.work), first)

    def test_raw_expiry_at_readback_is_rejected_after_known_model_close(self):
        state, _result, _values, _value, fence = self.output()
        def expire(event):
            if event == "read":
                self.raw = state.clock.work
        self.model.action = expire
        first = self.refuses(fence.append)
        self.assertTrue(self.model.closed)
        self.assertEqual(self.model.events.count("read"), 1)
        self.raw -= NS
        self.assertIs(self.refuses(fence.now, final=True, limit=state.clock.work), first)

    def test_local_expiry_at_close_keeps_the_original_limit_and_known_close(self):
        state, _result, _values, _value, fence = self.output()
        def expire(event):
            if event == "close":
                self.local = state.clock.final_local
        self.model.action = expire
        first = self.refuses(fence.append)
        self.assertTrue(self.model.closed)
        self.local -= 1
        self.assertIs(self.refuses(fence.now, final=True, limit=state.clock.work), first)

    def test_original_cancel_after_write_still_closes_without_readback(self):
        state, _result, _values, _value, fence = self.output()
        first = ModelFailure("MODEL_CANCEL_AFTER_WRITE")
        def cancelled():
            raise first
        def arm(event):
            if event == "write":
                self.action = cancelled
        self.model.action = arm
        self.assertIs(self.refuses(fence.append), first)
        self.assertTrue(self.model.closed)
        self.assertNotIn("read", self.model.events)
        self.action = lambda: None
        self.assertIs(self.refuses(fence.now, final=True, limit=state.clock.work), first)

    def test_original_cancel_after_readback_is_not_lost_at_known_close(self):
        state, _result, _values, _value, fence = self.output()
        first = ModelFailure("MODEL_CANCEL_AFTER_READBACK")
        def cancelled():
            raise first
        def arm(event):
            if event == "read":
                self.action = cancelled
        self.model.action = arm
        self.assertIs(self.refuses(fence.append), first)
        self.assertTrue(self.model.closed)
        self.assertEqual(self.model.events.count("read"), 1)
        self.action = lambda: None
        self.assertIs(self.refuses(fence.now, final=True, limit=state.clock.work), first)

    def test_original_r_final_append_guard_cannot_extend_the_writer_window(self):
        state, _result, _values, _value, fence = self.output()
        def expire():
            if self.callbacks == 6:
                self.raw = state.clock.work
        self.action = expire
        first = self.refuses(fence.append)
        self.assertEqual(self.callbacks, 6)
        self.assertTrue(self.model.closed)
        self.assertEqual(R._OUTPUTS[id(fence)].phase, "APPENDING")
        self.raw -= NS
        self.action = lambda: None
        self.assertIs(self.refuses(fence.now, final=True, limit=state.clock.work), first)

    def test_nonfinal_late_stdout_check_does_not_skip_the_original_contract(self):
        state, _result, _values, _value, fence = self.append_complete()
        first = self.refuses(fence.now, final=False, limit=state.clock.work)
        self.assertIs(self.refuses(fence.now, final=True, limit=state.clock.work), first)

    def test_late_stdout_cannot_use_later_seal_end_after_original_output_limit(self):
        state, _result, _values, _value, fence = self.append_complete()
        self.assertLess(state.clock.work, state.clock.seal_end)
        first = self.refuses(fence.now, final=True, limit=state.clock.seal_end)
        self.assertIs(self.refuses(fence.now, final=True, limit=state.clock.work), first)

    def test_caught_reentrant_append_cannot_repair_the_original_latch(self):
        _state, _result, _values, _value, fence = self.output()
        caught = []
        def reenter():
            try:
                fence.append()
            except FAILURES as error:
                caught.append(error)
        self.action = reenter
        first = self.refuses(fence.append)
        self.assertTrue(caught)
        self.assertIs(first, caught[0])
        self.action = lambda: None
        self.assertIs(self.refuses(fence.append), first)
        self.assertFalse(self.model.events)

    def test_original_public_data_mutation_is_sticky_after_value_restoration(self):
        _state, _result, _values, value, fence = self.output()
        original = value[FIELDS[0]]
        self.action = lambda: value.__setitem__(FIELDS[0], "0" * 64)
        first = self.refuses(fence.append)
        value[FIELDS[0]] = original
        self.action = lambda: None
        self.assertIs(self.refuses(fence.append), first)
        self.assertFalse(self.model.events)

    def test_equal_output_tuple_replacement_is_not_the_original_pin(self):
        _state, _result, _values, _value, fence = self.output()
        saved = R._OUTPUTS[id(fence)]
        original = saved.outputs
        object.__setattr__(saved, "outputs", tuple(list(original)))
        first = self.refuses(fence.append)
        object.__setattr__(saved, "outputs", original)
        self.assertIs(self.refuses(fence.append), first)
        self.assertFalse(self.model.events)

    def test_c_writer_swap_inside_actual_r_guard_never_invokes_replacement(self):
        state, _result, _values, _value, fence = self.output()
        invoked = []
        original = C._append_output_bytes
        def replaced(*_args):
            invoked.append(True)
            raise AssertionError("REPLACED_WRITER_CALLED")
        def swap():
            self.stack.enter_context(patch.object(C, "_append_output_bytes", replaced))
        self.action = swap
        first = self.refuses(fence.append)
        self.action = lambda: None
        self.stack.enter_context(patch.object(C, "_append_output_bytes", original))
        self.assertIs(self.refuses(fence.now, final=True, limit=state.clock.work), first)
        self.assertFalse(invoked)
        self.assertFalse(self.model.events)

    def test_readback_failure_blocks_r_output_and_both_late_checks(self):
        state, _result, _values, _value, fence = self.output()
        self.model.bad_readback = True
        first = self.refuses(fence.append)
        self.assertEqual(str(first), "STEP_OUTPUT_READBACK")
        self.assertTrue(self.model.closed)
        self.model.bad_readback = False
        self.assertIs(self.refuses(fence.now, final=True, limit=state.clock.work), first)
        self.assertEqual(self.model.events.count("write"), 1)

    def test_unknown_model_close_cannot_be_replaced_by_later_r_output(self):
        state, _result, _values, _value, fence = self.output()
        self.model.close_failure = ModelFailure("MODEL_R_CLOSE_UNKNOWN")
        first = self.refuses(fence.append)
        self.assertEqual(str(first), "STEP_OUTPUT_CLOSE_UNKNOWN")
        self.assertEqual(C.QUARANTINE, [self.model.fd])
        self.assertFalse(self.model.closed)
        self.assertIs(self.refuses(fence.append), first)
        self.assertIs(self.refuses(fence.now, final=True, limit=state.clock.work), first)
        self.assertEqual(self.model.events.count("close"), 1)


if __name__ == "__main__":
    unittest.main(failfast=True)
