#!/usr/bin/env python3
"""New finite U clock/pipe models and source-order controls ONLY.

The clock readings, pipe wrappers, descriptor operations and environment below
are explicitly supplied unit models. They are NOT real native resources or
hosted observations. No old fixture/test is imported; no actual pipe, file
owner, process, socket, key, upload or clock observation is acquired. The AST
checks prove only this source's ordering, not that any operation ran on a host.
"""
from __future__ import annotations

import ast
from contextlib import contextmanager, ExitStack
import ctypes
import errno
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


GUARDED = False


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen",
            "os.putenv", "os.unsetenv") or GUARDED and event in ("open", "os.listdir", "os.scandir"):
        raise AssertionError("U_STREAM_MODEL_SIDE_EFFECT")


sys.dont_write_bytecode = True
sys.addaudithook(offline)
SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
SOURCE_PATH = SCRIPTS / "run-hosted-initial-recipient-upload.py"
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")
if len(SOURCE.encode("utf-8")) > 128 * 1024:
    raise AssertionError("U_STREAM_SOURCE_BOUND")
TREE = ast.parse(SOURCE, filename=str(SOURCE_PATH))
SPEC = importlib.util.spec_from_file_location("_new_u_stream_controls", SOURCE_PATH)
U = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = U
SPEC.loader.exec_module(U)
NS = 1_000_000_000


def seed():
    return {"initialSealSha256": "1" * 64, "initialSealEndNs": str(346 * NS),
        "initialSealClockRole": "linux-x64",
        "initialSealClockDomain": "linux.clock_gettime_ns(CLOCK_MONOTONIC_RAW)",
        "initialSealClockTicksPerSecond": str(NS), "initialSealBootSha256": "2" * 64}


@contextmanager
def clock_model(cancelled=lambda: None):
    global GUARDED
    with ExitStack() as stack:
        attempts, environment, actual_environment = {}, {"MODEL": "only"}, {"MODEL": "only"}
        latch = U.K.B.EntryLatch(attempts)  # A DATA latch, not B or native authority.
        stack.enter_context(patch.object(U, "_ATTEMPTS", attempts))
        stack.enter_context(patch.object(U, "_ENTRY", latch))
        stack.enter_context(patch.object(U, "_CLOCKS", {}))
        stack.enter_context(patch.object(U.os, "environ", actual_environment))
        stack.enter_context(patch.object(U.time, "monotonic", return_value=101.0))
        stack.enter_context(patch.object(U.time, "time", return_value=1000.0))
        stack.enter_context(patch.object(U.O.clocks, "checked_now", return_value=341 * NS))
        stack.enter_context(patch.object(U.K.continuity, "boot_digest", return_value="2" * 64))
        entry = latch.begin(attempts)
        identity = U.O.clocks.ClockIdentity("linux-x64", "linux.clock_gettime_ns(CLOCK_MONOTONIC_RAW)", NS)
        first = U.O.clocks.Reading(identity, 340 * NS)
        original_graph = U.N._history_graph(first)
        previous, GUARDED = GUARDED, True
        try:
            clock = U._Clock(first, 100.0, "2" * 64, cancelled, environment, seed(), entry,
                first_graph=original_graph, latch=latch, attempts=attempts)
            yield clock, latch, attempts, entry, actual_environment
        finally:
            GUARDED = previous


class PipePart:
    def __init__(self):
        self.closed = False


class PipeModel(PipePart):
    def __init__(self, number):
        super().__init__()
        self.number, self.buffer, self.raw = number, PipePart(), PipePart()
        self.tag, self.close_calls, self.close_error = 1, 0, None

    def close(self):
        self.close_calls += 1
        if self.close_error is not None:
            raise self.close_error
        self.closed = self.buffer.closed = self.raw.closed = True


class PipeOperations:
    def __init__(self):
        self.originals = tuple(PipeModel(number) for number in range(3))
        self.pins, self.blocking, self.reads, self.writes = [], {0: True, 1: True}, [], []
        self.pin_failure = self.nonblocking_failure = self.false_close = None

    def identity(self, stream, number):
        self.pins.append(number)
        if self.pin_failure == number:
            raise RuntimeError("SUPPLIED_PIN_FAILURE")
        if stream is not self.originals[number] or stream.closed:
            raise RuntimeError("SUPPLIED_WRAPPER_REPLACED")
        return stream, stream.buffer, stream.raw, number, (1, number + 1, stream.tag), None

    def set_blocking(self, number, value):
        if self.nonblocking_failure == number:
            raise RuntimeError("SUPPLIED_NONBLOCKING_FAILURE")
        self.blocking[number] = value

    def fstat(self, number):
        if self.originals[number].closed and self.false_close != number:
            raise OSError(errno.EBADF, "SUPPLIED_CLOSED")
        return object()

    def read(self, number, count):
        if number != 0 or count != 1 or not self.reads:
            raise AssertionError("UNEXPECTED_MODEL_READ")
        value = self.reads.pop(0)
        if isinstance(value, BaseException):
            raise value
        return value

    def write(self, number, data):
        if number != 1:
            raise AssertionError("UNEXPECTED_MODEL_WRITE")
        self.writes.append(bytes(data))
        return len(data)


@contextmanager
def pipe_model(cancelled=lambda: None):
    global GUARDED
    model = PipeOperations()
    with clock_model(cancelled) as (clock, latch, attempts, entry, _environment), ExitStack() as stack:
        model.clock, model.latch, model.attempts, model.entry = clock, latch, attempts, entry
        stack.enter_context(patch.object(U, "_PIPES", {}))
        stack.enter_context(patch.object(U, "_QUARANTINE", []))
        for name, original in zip(("stdin", "stdout", "stderr"), model.originals):
            stack.enter_context(patch.object(U.sys, name, original))
        stack.enter_context(patch.object(U, "_pipe_identity", side_effect=model.identity))
        stack.enter_context(patch.object(U.os, "set_blocking", side_effect=model.set_blocking))
        stack.enter_context(patch.object(U.os, "get_blocking", side_effect=lambda number: model.blocking[number]))
        stack.enter_context(patch.object(U.os, "fstat", side_effect=model.fstat))
        stack.enter_context(patch.object(U.os, "read", side_effect=model.read))
        stack.enter_context(patch.object(U.os, "write", side_effect=model.write))
        stack.enter_context(patch.object(U.time, "sleep", return_value=None))
        previous, GUARDED = GUARDED, True
        try:
            yield U._Pipes(clock), model
        finally:
            GUARDED = previous


class ClockControls(unittest.TestCase):
    def sticky(self, clock, latch, attempts, entry, operation):
        with self.assertRaises((ValueError, RuntimeError)) as first:
            operation()
        self.assertIs(clock._anchor().failure, first.exception)
        with self.assertRaises((ValueError, RuntimeError)) as again:
            latch.check(attempts, entry)
        self.assertIs(first.exception, again.exception)
        return first.exception

    def test_supplied_clock_keeps_original_raw_and_local_caps(self):
        with clock_model() as (clock, _latch, _attempts, _entry, _env):
            self.assertEqual((clock.first, clock.work, clock.final), (340 * NS, 395 * NS, 400 * NS))
            self.assertLessEqual(clock.local_end, 160.0)
            self.assertEqual(clock.now(), 341 * NS)

    def test_public_current_is_a_fresh_detached_scalar_snapshot_not_an_anchor(self):
        with clock_model() as (clock, _latch, _attempts, _entry, _env):
            original = clock.current()
            self.assertIsNot(original, clock.current())
            self.assertNotIn("binding", original)
            self.assertNotIn("latch", original)
            self.assertNotIn("returns", original)
            with self.assertRaises(TypeError):
                original["first"] = 0
            copied = dict(original)
            copied.update(first=0, failure=None, binding=(), retainedReturns=100)
            clock.retain({"synthetic": 1})
            self.assertEqual(original["retainedReturns"], 0)
            self.assertEqual(clock.current()["retainedReturns"], 1)
            self.assertEqual(clock.first, 340 * NS)

    def test_snapshot_mutation_cannot_clear_caught_clock_failure(self):
        with clock_model() as (clock, latch, attempts, entry, environment):
            copied = dict(clock.current())
            environment["MODEL"] = "changed"
            error = self.sticky(clock, latch, attempts, entry, clock.current)
            copied.update(failure=None, binding=clock._binding)
            environment["MODEL"] = "only"
            with self.assertRaises(ValueError) as again:
                clock.current()
            self.assertIs(again.exception, error)

    def test_caught_restored_binding_failure_stays_on_original_entry(self):
        with clock_model() as (clock, latch, attempts, entry, _env):
            original = clock._binding
            clock._binding = tuple(list(original))
            error = self.sticky(clock, latch, attempts, entry, lambda: clock.seed)
            clock._binding = original
            with self.assertRaises((ValueError, RuntimeError)) as again:
                clock.current()
            self.assertIs(again.exception, error)

    def test_replaced_global_latch_is_not_failure_authority(self):
        with clock_model() as (clock, latch, attempts, entry, _env):
            replacement = U.K.B.EntryLatch({})
            with patch.object(U, "_ENTRY", replacement):
                error = self.sticky(clock, latch, attempts, entry, lambda: clock.first)
            self.assertIsNone(replacement._original()[4])
            with self.assertRaises((ValueError, RuntimeError)) as again:
                clock.now()
            self.assertIs(again.exception, error)

    def test_replaced_attempt_table_cannot_revive_after_restore(self):
        with clock_model() as (clock, latch, attempts, entry, _env):
            with patch.object(U, "_ATTEMPTS", {"entry": entry}):
                self.sticky(clock, latch, attempts, entry, clock.current)
            with self.assertRaises((ValueError, RuntimeError)):
                clock.local_end

    def test_environment_change_and_restore_does_not_clear_failure(self):
        with clock_model() as (clock, latch, attempts, entry, environment):
            environment["MODEL"] = "changed"
            self.sticky(clock, latch, attempts, entry, clock.current)
            environment["MODEL"] = "only"
            with self.assertRaises((ValueError, RuntimeError)):
                clock.current()

    def test_first_return_graph_is_not_a_late_current_snapshot(self):
        with clock_model() as (clock, latch, attempts, entry, _env):
            first = clock.reading
            object.__setattr__(first, "nanoseconds", 339 * NS)
            self.sticky(clock, latch, attempts, entry, clock.current)
            object.__setattr__(first, "nanoseconds", 340 * NS)
            with self.assertRaises((ValueError, RuntimeError)):
                clock.clock

    def test_retained_input_nested_mutation_poisoned_before_later_use(self):
        with clock_model() as (clock, latch, attempts, entry, _env):
            parsed = ({"members": [{"bytes": 1}]}, {}, {}, {},
                {"notBefore": 1, "expiresAt": 2000}, {"notBefore": 1, "expiresAt": 2000})
            clock.bind_content({"original": b"synthetic"}, parsed, (("original", b"metadata", b"synthetic"),))
            parsed[0]["members"][0]["bytes"] = 2
            self.sticky(clock, latch, attempts, entry, clock.current)

    def test_retained_zip_return_mutation_is_not_reacquired_after_close(self):
        with clock_model() as (clock, latch, attempts, entry, _env):
            returned = {"members": [{"sha256": "3" * 64}], "zipBytes": 556}
            clock.retain(returned)
            returned["members"][0]["sha256"] = "4" * 64
            self.sticky(clock, latch, attempts, entry, clock.current)

    def test_direct_invalid_attach_is_sticky_without_native_acquisition(self):
        with clock_model() as (clock, latch, attempts, entry, _env):
            self.sticky(clock, latch, attempts, entry, lambda: clock.attach(object()))

    def test_direct_duplicate_content_binding_is_sticky(self):
        with clock_model() as (clock, latch, attempts, entry, _env):
            parsed = ({}, {}, {}, {}, {"notBefore": 1, "expiresAt": 2000}, {"notBefore": 1, "expiresAt": 2000})
            clock.bind_content({}, parsed, ())
            self.sticky(clock, latch, attempts, entry, lambda: clock.bind_content({}, parsed, ()))

    def test_policy_expiration_is_checked_on_direct_property_access(self):
        with clock_model() as (clock, latch, attempts, entry, _env):
            parsed = ({}, {}, {}, {}, {"notBefore": 1, "expiresAt": 1001}, {"notBefore": 1, "expiresAt": 2000})
            clock.bind_content({}, parsed, ())
            with patch.object(U.time, "time", return_value=1001.0):
                self.sticky(clock, latch, attempts, entry, lambda: clock.work)

    def test_raw_end_and_backwards_observations_refuse(self):
        for raw in (339 * NS, 395 * NS, 400 * NS):
            with clock_model() as (clock, latch, attempts, entry, _env):
                with patch.object(U.O.clocks, "checked_now", return_value=raw):
                    self.sticky(clock, latch, attempts, entry, clock.now)

    def test_local_end_and_backwards_observations_refuse(self):
        for local in (99.0, 155.0, 160.0):
            with clock_model() as (clock, latch, attempts, entry, _env):
                with patch.object(U.time, "monotonic", return_value=local):
                    self.sticky(clock, latch, attempts, entry, clock.now)

    def test_changed_boot_never_rebases_the_original_clock(self):
        with clock_model() as (clock, latch, attempts, entry, _env):
            with patch.object(U.K.continuity, "boot_digest", return_value="9" * 64):
                self.sticky(clock, latch, attempts, entry, clock.now)

    def test_callback_cannot_swallow_then_repair_a_direct_property_failure(self):
        handle = []
        def changed():
            clock = handle[0]
            original = clock._binding
            clock._binding = ()
            try:
                clock.clock
            except (ValueError, RuntimeError):
                pass
            clock._binding = original
        with clock_model(changed) as (clock, latch, attempts, entry, _env):
            handle.append(clock)
            self.sticky(clock, latch, attempts, entry, clock.now)


class PipeControls(unittest.TestCase):
    def sticky(self, pipes, model, operation):
        with self.assertRaises((ValueError, RuntimeError, OSError)) as first:
            operation()
        self.assertTrue(pipes.state()["failure"])
        for again in (pipes.current, model.clock.current,
                lambda: model.latch.check(model.attempts, model.entry)):
            with self.assertRaises((ValueError, RuntimeError, OSError)) as later:
                again()
            self.assertIs(later.exception, first.exception)
        return first.exception

    def test_capture_returns_before_any_pin_or_configuration(self):
        with pipe_model() as (pipes, model):
            self.assertEqual(model.pins, [])
            self.assertEqual(pipes.state()["pins"], (None, None, None))
            self.assertEqual(pipes.state()["originals"][2], id(model.originals[2]))
            with self.assertRaises((ValueError, RuntimeError)):
                pipes.close(RuntimeError("SUPPLIED_BEFORE_CONFIGURE_FAILURE"))
            self.assertEqual([value.close_calls for value in model.originals], [0, 0, 0])
            self.assertEqual(pipes.state()["unknown"], {0, 1, 2})
            self.assertIn(pipes, U._QUARANTINE)

    def test_each_partial_pin_failure_closes_only_proved_originals(self):
        for failed in range(3):
            with pipe_model() as (pipes, model):
                model.pin_failure = failed
                with self.assertRaises(RuntimeError) as first:
                    pipes.configure()
                with self.assertRaises(RuntimeError) as closed:
                    pipes.close(first.exception)
                self.assertIs(first.exception, closed.exception)
                self.assertEqual([value.close_calls for value in model.originals],
                    [int(number < failed) for number in range(3)])
                self.assertEqual(pipes.state()["unknown"], set(range(failed, 3)))
                self.assertIn(pipes, U._QUARANTINE)

    def test_each_nonblocking_failure_keeps_all_original_pins_for_cleanup(self):
        for failed in (0, 1):
            with pipe_model() as (pipes, model):
                model.nonblocking_failure = failed
                with self.assertRaises(RuntimeError) as first:
                    pipes.configure()
                with self.assertRaises(RuntimeError):
                    pipes.close(first.exception)
                self.assertEqual([value.close_calls for value in model.originals], [1, 1, 1])
                self.assertEqual(pipes.state()["closed"], {0, 1, 2})
                self.assertNotIn(pipes, U._QUARANTINE)

    def test_unconfirmed_nonblocking_mode_refuses_without_orphaning_pins(self):
        with pipe_model() as (pipes, model):
            with patch.object(U.os, "get_blocking", return_value=True):
                with self.assertRaises(ValueError) as first:
                    pipes.configure()
            with self.assertRaises(ValueError):
                pipes.close(first.exception)
            self.assertEqual([value.close_calls for value in model.originals], [1, 1, 1])

    def test_changed_original_handle_is_quarantined_not_closed_as_known(self):
        with pipe_model() as (pipes, model):
            pipes.configure()
            model.originals[1].tag += 1
            with self.assertRaises(ValueError) as first:
                pipes.current()
            with self.assertRaises(ValueError):
                pipes.close(first.exception)
            self.assertEqual([value.close_calls for value in model.originals], [1, 0, 1])
            self.assertEqual(pipes.state()["unknown"], {1})
            self.assertIn(pipes, U._QUARANTINE)

    def test_replaced_visible_stdout_does_not_replace_retained_original(self):
        with pipe_model() as (pipes, model):
            pipes.configure()
            replacement = PipeModel(1)
            with patch.object(U.sys, "stdout", replacement):
                with self.assertRaises(ValueError) as first:
                    pipes.current()
                with self.assertRaises(ValueError):
                    pipes.close(first.exception)
            self.assertEqual(replacement.close_calls, 0)
            self.assertEqual([value.close_calls for value in model.originals], [1, 1, 1])

    def test_unknown_original_close_is_never_retried(self):
        with pipe_model() as (pipes, model):
            pipes.configure()
            model.originals[1].close_error = RuntimeError("SUPPLIED_CLOSE_FAILURE")
            model.reads.append(b"")
            pipes.demand(eof=True)
            with self.assertRaises(RuntimeError) as first:
                pipes.close()
            with self.assertRaises(RuntimeError):
                pipes.close(first.exception)
            self.assertEqual([value.close_calls for value in model.originals], [1, 1, 1])
            self.assertEqual(pipes.state()["unknown"], {1})
            self.assertEqual(sum(value is pipes for value in U._QUARANTINE), 1)

    def test_closed_wrapper_without_original_descriptor_close_is_unknown(self):
        with pipe_model() as (pipes, model):
            pipes.configure()
            model.reads.append(b"")
            pipes.demand(eof=True)
            model.false_close = 1
            with self.assertRaises(ValueError):
                pipes.close()
            self.assertEqual(pipes.state()["unknown"], {1})
            self.assertEqual(pipes.state()["closed"], {0, 2})

    def test_complete_model_close_is_not_a_second_successful_close(self):
        with pipe_model() as (pipes, model):
            pipes.configure()
            model.reads.append(b"")
            pipes.demand(eof=True)
            pipes.close()
            self.sticky(pipes, model, pipes.close)
            self.assertEqual([value.close_calls for value in model.originals], [1, 1, 1])

    def test_status_maps_are_detached_immutable_and_never_contain_live_authority(self):
        with pipe_model() as (pipes, model):
            before = pipes.state()
            pipes.configure()
            current = pipes.current()
            self.assertIsNot(current, pipes.current())
            self.assertEqual(current["clock"], id(model.clock))
            self.assertEqual(current["originals"], tuple(id(value) for value in model.originals))
            self.assertEqual(before["pins"], (None, None, None))
            self.assertNotEqual(current["pins"], before["pins"])
            with self.assertRaises(TypeError):
                current["eof"] = True
            with self.assertRaises(AttributeError):
                current["closed"].add(0)
            copied = dict(current)
            copied.update(eof=True, pins=(), originals=(), closed={0, 1, 2}, failure=False, clock=object())
            self.assertFalse(pipes.current()["eof"])
            model.reads.append(b"")
            pipes.demand(eof=True)
            pipes.close()
            self.assertFalse(current["eof"])
            self.assertEqual(current["closed"], frozenset())
            self.assertEqual(pipes.current()["closed"], frozenset((0, 1, 2)))

    def test_caught_handle_failure_cannot_be_erased_using_a_status_copy(self):
        with pipe_model() as (pipes, model):
            pipes.configure()
            status = dict(pipes.state())
            with patch.object(U.sys, "stdout", PipeModel(1)):
                error = self.sticky(pipes, model, pipes.current)
            status.update(failure=False, eof=True, clock=object())
            with self.assertRaises(ValueError) as again:
                pipes.current()
            self.assertIs(again.exception, error)

    def test_configure_entry_error_poisoned_the_original_clock_and_latch(self):
        with pipe_model() as (pipes, model):
            pipes.configure()
            self.sticky(pipes, model, pipes.configure)

    def test_early_eof_bad_next_and_nonempty_final_are_sticky(self):
        for raw, eof in ((b"", False), (b"X", False), (b"N", True), (b"NN", False)):
            with pipe_model() as (pipes, model):
                pipes.configure()
                model.reads.append(raw)
                self.sticky(pipes, model, lambda: pipes.demand(eof=eof))

    def test_invalid_demand_entry_and_os_read_failure_are_sticky(self):
        with pipe_model() as (pipes, model):
            pipes.configure()
            self.sticky(pipes, model, lambda: pipes.demand(eof=1))
        with pipe_model() as (pipes, model):
            pipes.configure()
            model.reads.append(OSError("SUPPLIED_READ_FAILURE"))
            self.sticky(pipes, model, pipes.demand)

    def test_invalid_frame_zero_write_and_os_write_failure_are_sticky(self):
        with pipe_model() as (pipes, model):
            pipes.configure()
            self.sticky(pipes, model, lambda: pipes.frame(b"I", b"invalid"))
        for result in (0, OSError("SUPPLIED_WRITE_FAILURE")):
            with pipe_model() as (pipes, model):
                pipes.configure()
                setting = {"side_effect": result} if isinstance(result, BaseException) else {"return_value": result}
                with patch.object(U.os, "write", **setting):
                    self.sticky(pipes, model, lambda: pipes.frame(b"D", b"a"))

    def test_expired_wait_and_sleep_failure_are_sticky(self):
        with pipe_model() as (pipes, model):
            pipes.configure()
            with patch.object(U.time, "sleep", side_effect=OSError("SUPPLIED_WAIT_FAILURE")):
                self.sticky(pipes, model, pipes.pause)
        with pipe_model() as (pipes, model):
            pipes.configure()
            with patch.object(U.time, "monotonic", return_value=155.0):
                self.sticky(pipes, model, pipes.pause)

    def test_close_without_observed_eof_is_terminal_even_with_three_known_closes(self):
        with pipe_model() as (pipes, model):
            pipes.configure()
            self.sticky(pipes, model, pipes.close)
            self.assertEqual(pipes.state()["closed"], frozenset((0, 1, 2)))
            self.assertFalse(pipes.state()["eof"])

    def test_failed_close_sticks_on_original_u_entry_with_no_retry(self):
        with pipe_model() as (pipes, model):
            pipes.configure()
            model.reads.append(b"")
            pipes.demand(eof=True)
            model.originals[1].close_error = RuntimeError("SUPPLIED_CLOSE_FAILURE")
            error = self.sticky(pipes, model, pipes.close)
            with self.assertRaises(RuntimeError) as again:
                pipes.close(error)
            self.assertIs(again.exception, error)
            self.assertEqual([value.close_calls for value in model.originals], [1, 1, 1])

    def test_swallowed_late_duplicate_close_invalidates_original_clock_return(self):
        handle = []
        def cancelled():
            if handle:
                try:
                    handle[0].close()
                except ValueError:
                    pass
        # The callback is pinned by the ORIGINAL constructor, not injected
        # through a changed clock binding. It fires only after known close.
        with pipe_model(cancelled) as (pipes, model):
            pipes.configure()
            model.reads.append(b"")
            pipes.demand(eof=True)
            pipes.close()
            handle.append(pipes)
            error = self.sticky(pipes, model, model.clock.now)
            with self.assertRaises(ValueError) as again:
                model.latch.complete(model.attempts, model.entry, b"synthetic pending return")
            self.assertIs(again.exception, error)

    def test_pipe_failure_uses_original_latch_despite_replaced_visible_alias(self):
        with pipe_model() as (pipes, model):
            pipes.configure()
            replacement = U.K.B.EntryLatch({})
            with patch.object(U, "_ENTRY", replacement):
                self.sticky(pipes, model, lambda: pipes.frame(b"D", b"a"))
            self.assertIsNone(replacement._original()[4])

    def test_eagain_and_positive_short_writes_preserve_exact_frame(self):
        with pipe_model() as (pipes, _model):
            pipes.configure()
            actual, calls = bytearray(), []
            def write(number, data):
                calls.append(number)
                if len(calls) == 1:
                    raise BlockingIOError()
                count = min(2, len(data))
                actual.extend(data[:count])
                return count
            with patch.object(U.os, "write", side_effect=write):
                pipes.frame(b"D", b"abc")
            self.assertEqual(bytes(actual), b"D\x00\x00\x00\x03abc")

    def test_zero_negative_boolean_and_oversized_write_returns_refuse(self):
        for returned in (0, -1, True, 99999):
            with pipe_model() as (pipes, _model):
                pipes.configure()
                with patch.object(U.os, "write", return_value=returned):
                    with self.assertRaises(ValueError):
                        pipes.frame(b"D", b"a")

    def test_exact_original_demand_and_eof_with_no_extra_demand(self):
        with pipe_model() as (pipes, model):
            pipes.configure()
            model.reads.extend((BlockingIOError(), b"N", b""))
            pipes.demand()
            pipes.demand(eof=True)
            with self.assertRaises(ValueError):
                pipes.demand()
            self.assertEqual(model.reads, [])

    def test_wrong_demand_early_eof_and_nonempty_final_eof_refuse(self):
        for raw, eof in ((b"X", False), (b"", False), (b"N", True), (b"NN", False)):
            with pipe_model() as (pipes, model):
                pipes.configure()
                model.reads.append(raw)
                with self.assertRaises(ValueError):
                    pipes.demand(eof=eof)

    def test_frame_roster_and_bounds_are_checked_before_write(self):
        for kind, raw in ((b"I", b"x"), (b"D", b""), (b"D", b"x" * 65537), (b"F", b"x" * 16385)):
            with pipe_model() as (pipes, model):
                pipes.configure()
                with self.assertRaises(ValueError):
                    pipes.frame(kind, raw)
                self.assertEqual(model.writes, [])

    def test_unregistered_wrapper_is_rejected_before_descriptor_operation(self):
        with patch.object(U.os, "fstat", side_effect=AssertionError("MUST_NOT_TOUCH_DESCRIPTOR")) as operation:
            with self.assertRaises(ValueError):
                U._pipe_identity(object(), 0)
            operation.assert_not_called()


def node(name, owner=None):
    parent = TREE if owner is None else next(value for value in TREE.body
        if isinstance(value, ast.ClassDef) and value.name == owner)
    return next(value for value in parent.body if isinstance(value, ast.FunctionDef) and value.name == name)


def source(name, owner=None):
    return ast.get_source_segment(SOURCE, node(name, owner))


class SourceOrderControls(unittest.TestCase):
    def test_ast_first_is_pinned_before_boot_and_environment_callbacks(self):
        value = source("stream")
        self.assertLess(value.index("first = O.clocks.observe()"), value.index("first_graph = N._history_graph(first)"))
        self.assertLess(value.index("first_graph = N._history_graph(first)"), value.index("boot = K.continuity.boot_digest"))
        self.assertEqual(value.count("N._check_history(first_graph)"), 2)

    def test_ast_pipe_registration_returns_before_fallible_configuration(self):
        constructor, caller = source("__init__", "_Pipes"), source("stream")
        self.assertNotIn("_pipe_identity(", constructor)
        self.assertNotIn("os.set_blocking(", constructor)
        self.assertLess(caller.index("pipes = _Pipes(clock)"), caller.index("pipes.configure()"))
        self.assertIn("pipes.close(failure)", caller)

    def test_ast_parsed_inputs_and_zip_return_pinned_before_next_callbacks(self):
        inputs, caller = source("_inputs"), source("stream")
        self.assertLess(inputs.index("clock.bind_content(raws, parsed, observations)"), inputs.index("K._context("))
        self.assertLess(inputs.index("clock.bind_content(raws, parsed, observations)"), inputs.index("D.manifests("))
        self.assertLess(caller.index("clock.retain(zip_result)"), caller.index("for name, metadata, expected in observations"))
        self.assertLess(caller.index("clock.retain(zip_result)"), caller.index("owner.finish()"))

    def test_ast_native_file_close_precedes_f_and_original_pipe_close_precedes_return(self):
        value = source("stream")
        ordered = ("close_raw = owner.finish()", "K._closed_files(owner)", "closed_ns = clock.now()",
            'pipes.frame(b"F", final_raw)', "pipes.demand(eof=True)", "pipes.close()",
            "latch.complete(attempts, entry, final_raw)", "latch.returned(attempts, entry, final_raw)")
        positions = [value.index(item) for item in ordered]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("failure = latch.fail(error)", value)
        self.assertIn("anchor.latch.fail(error)", source("fail", "_Clock"))
        self.assertNotIn("_ENTRY.fail(", SOURCE)


if __name__ == "__main__":
    unittest.main()
