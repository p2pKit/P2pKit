#!/usr/bin/env python3
"""Native-scope models with Windows sharing/tiny POSIX files, NOT qualification."""
from __future__ import annotations

from dataclasses import FrozenInstanceError
import importlib.util
import os
from pathlib import Path, PureWindowsPath
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))

SPEC = importlib.util.spec_from_file_location("provider_lifecycle_sharing_models",
    Path(__file__).with_name("hosted-windows-provider-command-test.py"))
sharing = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = sharing
SPEC.loader.exec_module(sharing)
# The retained sharing fixture explicitly installs its source backend module.
# Import the new owner afterwards so exact-type checks use THAT same backend,
# rather than two separately loaded classes from identical source bytes.
import hosted_cache_provider_lifecycle as lifecycle
files, processes, clocks = sharing.files, lifecycle.processes, lifecycle.clocks
assert files is lifecycle.files.windows_files


class FalseyFailure(RuntimeError):
    def __bool__(self):
        raise AssertionError("MODEL_EXCEPTION_MUST_NOT_BE_TRUTH_TESTED")


class FalseyCancellation(BaseException):
    def __bool__(self):
        raise AssertionError("MODEL_CANCELLATION_MUST_NOT_BE_TRUTH_TESTED")


def caught(call):
    try:
        call()
    except BaseException as error:
        return error
    raise AssertionError("MODEL_EXPECTED_FAILURE")


class ProviderLifecycleModels(unittest.TestCase):
    def setUp(self):
        self.local, self.raw = 100.0, 100 * clocks.NS
        self.events, self.captures, self.codes = [], [], [0]
        self.on_raw = self.on_native_close = None
        self.clock = clocks.ClockIdentity("windows-x64", clocks.WINDOWS_DOMAIN, 10_000_000)
        self.time = SimpleNamespace(monotonic=lambda: self.local, sleep=self.sleep)
        self.patches = [patch.object(files, "time", self.time), patch.object(lifecycle, "time", self.time),
                        patch.object(clocks, "checked_now", self.now)]
        for binding in self.patches:
            binding.start()
        self.api = sharing.ShareApi()
        self.root = files._root(r"C:\work\private", self.api, create=True)
        self.scope = object.__new__(processes.WindowsScope)
        self.scope.job, self.scope.job_id, self.scope.invocation = 91, "1" * 32, "2" * 32
        self.scope.leaders, self.scope.launches, self.scope.known = [], [], {}
        self.scope.discovery_errors = set()
        self.scope.api = SimpleNamespace(close=self.native_close)
        self.scope.drain = Mock(side_effect=self.drain)
        self.scope.discover = Mock(return_value=[])
        self.factory = patch.object(processes, "make_scope", return_value=self.scope).start()
        self.never_classifier = patch.object(lifecycle.cache, "provider_observation",
            side_effect=AssertionError("MODEL_NATIVE_EXIT_IS_NOT_ORIGINAL_STEP_SUCCESS")).start()

    def tearDown(self):
        # Model-only disposal after inspecting the leaf's UNKNOWN/once-only
        # state. It does not turn any failed leaf into native retirement proof.
        self.on_raw = self.on_native_close = None
        self.api.close_failure = None
        self.local, self.raw = 100.0, 100 * clocks.NS
        for capture in self.captures:
            for name in reversed(capture._NAMES):
                slot = capture._slots[name]
                if type(slot.owner) is files.NativeFile:
                    # Synthetic disposal ONLY, after UNKNOWN/pin assertions.
                    reader = slot.owner._provider_log_reader
                    if reader in self.api.handles:
                        self.api.close(reader)
                    slot.owner._provider_log_reader = None
                    slot.owner._provider_log_unknown = slot.owner._provider_log_active = False
                if slot.owner is not None and not slot.close_attempted:
                    try:
                        slot.owner.close()
                    except BaseException:
                        pass
        self.root.close()
        lifecycle.QUARANTINE.clear()
        patch.stopall()

    def sleep(self, seconds):
        self.events.append(("sleep", seconds))
        self.local += seconds
        self.raw += int(seconds * clocks.NS)

    def now(self, expected, *, minimum_ns):
        self.events.append(("raw", self.raw, self.local))
        clocks.elapsed_ns(clocks.Reading(expected, minimum_ns), clocks.Reading(self.clock, self.raw))
        value = self.raw
        if self.on_raw is not None:
            self.on_raw()
        return value

    def native_close(self, handle):
        self.events.append(("native-close", handle))
        if self.on_native_close is not None:
            self.on_native_close(handle)

    def drain(self, **kwargs):
        self.events.append(("drain", kwargs))
        return []

    def capture(self, phase="save", **changes):
        values = dict(issued_ns=100 * clocks.NS, hard_end_ns=280 * clocks.NS, local_end=270.0,
            phase=phase, job="1" * 32, invocation="2" * 32, home=r"C:\model-provider-home", cancelled=lambda: None)
        values.update(changes)
        capture = lifecycle.ProviderCapture(clocks.Reading(self.clock, 100 * clocks.NS), **values)
        self.captures.append(capture)
        return capture

    def prepare(self, capture):
        capture.take_directory(self.root)
        capture.prepare()

    def command(self, raw):
        node = self.api.nodes[r"C:\work\private\provider-output.txt"]
        handle = self.api.shared_open(node, 2, 7)
        try:
            self.api.seek(handle, len(node.content), 0)
            self.api.write(handle, raw)
        finally:
            self.api.close(handle)

    def lookup_bytes(self):
        delimiter = "ghadelimiter_12345678-1234-4234-8234-123456789abc"
        return "".join(name + "<<" + delimiter + "\r\n" + value + "\r\n" + delimiter + "\r\n"
            for name, value in (("cache-primary-key", "MODEL_KEY"), ("cache-matched-key", "MODEL_KEY"),
                                ("cache-hit", "true"))).encode("ascii")

    def launch(self, capture, command=b""):
        child = processes.WindowsProcess(self.scope.api, 71 + len(self.scope.leaders),
            7 + len(self.scope.leaders), None, None)
        def poll():
            self.events.append(("poll", child.pid))
            return self.codes.pop(0) if len(self.codes) > 1 else self.codes[0]
        child.poll = poll
        self.scope.leaders.append(child)
        self.scope.launches.append({"api": "MODEL_ONLY_NO_PROCESS", "created": True, "pid": child.pid})
        self.scope.known[(child.pid, 19)] = {"pid": child.pid, "creationFileTime": 19, "live": True}
        self.api.write(capture.stdout.native_handle, b"MODEL_PRIVATE_STDOUT")
        self.api.write(capture.stderr.native_handle, b"MODEL_PRIVATE_STDERR")
        if command:
            self.command(command)
        return child

    def run_ok(self, capture, command=b""):
        with capture:
            self.prepare(capture)
            capture.wait(self.launch(capture, command))
        return capture.result

    def assert_no_result(self, capture):
        self.assertIsInstance(caught(lambda: capture.result), lifecycle.ProviderLifecycleError)
        self.never_classifier.assert_not_called()

    def test_inert_construction_entry_and_registration_only_transfer(self):
        before = list(self.events)
        capture = self.capture()
        self.assertEqual(self.events, before)
        capture.__enter__()
        self.assertEqual(self.events, before)
        capture.take_directory(self.root)
        self.assertEqual(self.events, before)
        self.assertIs(capture._slots["directory"].owner, self.root)
        error = FalseyCancellation("MODEL_BODY_STOP_BEFORE_PREPARE")
        self.assertIs(caught(lambda: capture.__exit__(type(error), error, None)), error)
        self.assertTrue(self.root._closed)
        self.factory.assert_not_called()

    def test_complete_lookup_is_an_immutable_provisional_capture(self):
        capture = self.capture("lookup")
        result = self.run_ok(capture, self.lookup_bytes())
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.command, self.lookup_bytes())
        self.assertEqual(result.stdout, b"MODEL_PRIVATE_STDOUT")
        self.assertEqual(result.stderr, b"MODEL_PRIVATE_STDERR")
        self.assertEqual(dict(result.outputs), {"cache-primary-key": "MODEL_KEY", "cache-matched-key": "MODEL_KEY", "cache-hit": "true"})
        self.assertEqual(result.original_step_outcome, "NOT_OBSERVED")
        self.assertEqual(result.enclosing_owner_retirement, "NOT_OBSERVED")
        self.assertEqual(result.provider_acceptance, "NOT_ESTABLISHED")
        self.assertEqual(set(result.closed_resources), set(capture._NAMES) - {"stdout-reader", "stderr-reader"})
        for name in ("stdout-reader", "stderr-reader"):
            slot = capture._slots[name]
            self.assertIsNone(slot.owner)
            self.assertFalse(slot.attempted or slot.close_attempted or slot.closed)
        self.assertIn(b"MODEL_ONLY_NO_PROCESS", result.native_retirement)
        self.assertNotIn("MODEL_PRIVATE", repr(result))
        with self.assertRaises(FrozenInstanceError):
            result.exit_code = 7
        self.assertEqual(self.api.handles, {})
        self.never_classifier.assert_not_called()

    def test_save_empty_and_work_poll_spend_one_fixed_original_end(self):
        self.codes = [None, None, 0]
        capture = self.capture()
        result = self.run_ok(capture)
        self.assertEqual((result.command, result.outputs), (b"", ()))
        self.assertEqual(len([row for row in self.events if row[0] == "sleep"]), 2)
        self.assertEqual(capture._local_end, 270.0)
        self.assertEqual(capture._work_local_end, 225.0)
        self.scope.drain.assert_called_once_with(grace=5.0, kill_wait=5.0, deadline=270.0)
        self.assertEqual(self.api.handles, {})

    def test_original_local_end_only_shortens_and_reservation_never_shrinks(self):
        capture = self.capture(local_end=1000.0)
        self.run_ok(capture)
        self.assertLess(capture._local_end, 280.0)
        self.assertEqual(capture._work_local_end, capture._local_end - 45)
        self.assertLessEqual(self.scope.drain.call_args.kwargs["deadline"], 280.0)

    def test_insufficient_remaining_work_time_closes_transferred_directory_without_launch(self):
        capture = self.capture(local_end=140.0)
        error = caught(lambda: self.run_ok(capture))
        self.assertIsInstance(error, lifecycle.ProviderLifecycleError)
        self.assertIn("EXPIRED", str(error))
        self.assertTrue(capture._slots["directory"].closed)
        self.factory.assert_not_called()
        self.assert_no_result(capture)

    def test_first_verification_failure_cannot_lose_transferred_directory(self):
        capture, original = self.capture(), FalseyFailure("MODEL_VERIFY")
        with patch.object(self.root, "verify", side_effect=original):
            self.assertIs(caught(lambda: self.run_ok(capture)), original)
        self.assertTrue(capture._slots["directory"].closed)
        self.assertEqual(self.api.handles, {})
        self.assert_no_result(capture)

    def test_unknown_scope_construction_quarantines_original_file_owners(self):
        capture, original = self.capture(), FalseyFailure("MODEL_PARTIAL_SCOPE")
        self.factory.side_effect = original
        self.assertIs(caught(lambda: self.run_ok(capture)), original)
        self.assertTrue(capture.unknown)
        self.assertIn(capture, lifecycle.QUARANTINE)
        self.assertTrue(capture._slots["scope"].attempted)
        self.assertIsNone(capture._slots["scope"].owner)
        for name in ("stdout", "stderr", "command", "directory"):
            self.assertIsNotNone(capture._slots[name].owner)
            self.assertFalse(capture._slots[name].close_attempted)
        self.assert_no_result(capture)

    def test_postallocation_failure_keeps_exact_returned_scope_for_once_only_retirement(self):
        capture = self.capture()
        def returned(*args):
            self.local = 230.0  # Work expired; the original final interval remains valid.
            return self.scope
        self.factory.side_effect = returned
        self.assertIsInstance(caught(lambda: self.run_ok(capture)), lifecycle.ProviderLifecycleError)
        self.assertIs(capture._slots["scope"].owner, self.scope)
        self.assertTrue(capture._slots["scope"].closed)
        self.scope.drain.assert_called_once()
        self.assertEqual([row for row in self.events if row == ("native-close", 91)], [("native-close", 91)])
        self.assertFalse(capture.unknown)
        self.assert_no_result(capture)

    def test_body_spawn_failure_still_drains_registered_scope_and_preserves_original(self):
        capture, original = self.capture(), FalseyCancellation("MODEL_SPAWN_PARTIAL")
        original.__cause__ = ValueError("MODEL_PRIOR_CAUSE")
        cause = original.__cause__
        def call():
            with capture:
                self.prepare(capture)
                self.launch(capture)  # Modeled partial spawn already appended the original leader.
                raise original
        self.assertIs(caught(call), original)
        self.assertIs(original.__cause__, cause)
        self.scope.drain.assert_called_once()
        self.assertTrue(capture._slots["scope"].closed)
        self.assertEqual(self.api.handles, {})
        self.assert_no_result(capture)

    def test_caught_wait_failure_is_sticky_and_retains_actual_nonzero_exit(self):
        capture, remembered = self.capture(), []
        self.codes = [7]
        def call():
            with capture:
                self.prepare(capture)
                remembered.append(caught(lambda: capture.wait(self.launch(capture))))
        self.assertIs(caught(call), remembered[0])
        self.assertEqual(capture._exit_code, 7)
        self.assertTrue(capture._slots["scope"].closed)
        self.assert_no_result(capture)

    def test_failed_lookup_retains_private_bytes_after_close_without_parsing_outputs(self):
        capture, reads = self.capture("lookup"), []
        self.codes = [7]
        command = b"MODEL_MALFORMED_BUT_BOUNDED_COMMAND\r\n"
        readback = files.NativeFile.read_provider_log
        def read(writer):
            reads.append(PureWindowsPath(writer.path).name)
            return readback(writer)
        with patch.object(files.NativeFile, "read_provider_log", read), patch.object(
                lifecycle.cache, "provider_command_outputs", side_effect=AssertionError("MODEL_NO_FAILURE_PARSER")) as parser:
            error = caught(lambda: self.run_ok(capture, command))
        self.assertEqual(reads, ["provider-stdout.log", "provider-stderr.log"], "MODEL_FAILURE_LOGS_NOT_RETAINED")
        self.assertIs(error, capture._primary)
        self.assertRegex(str(error), "PROVIDER_CHILD_FAILED")
        result = capture.failure_capture
        self.assertIs(type(result), lifecycle.FailedProviderCapture)
        self.assertEqual((result.exit_code, result.command), (7, command))
        self.assertEqual((result.stdout, result.stderr), (b"MODEL_PRIVATE_STDOUT", b"MODEL_PRIVATE_STDERR"))
        self.assertEqual(result.original_step_outcome, "NOT_OBSERVED")
        self.assertEqual(result.enclosing_owner_retirement, "NOT_OBSERVED")
        self.assertEqual(result.provider_acceptance, "NOT_ESTABLISHED")
        self.assertNotIn("MODEL_PRIVATE", repr(result))
        self.assertEqual(set(result.closed_resources), set(capture._NAMES) - {"stdout-reader", "stderr-reader"})
        self.assertEqual(self.api.handles, {})
        with self.assertRaises(FrozenInstanceError):
            result.exit_code = 0
        parser.assert_not_called()
        self.assert_no_result(capture)

    def test_failed_cancellation_before_poll_retains_none_exit_and_original_falsey_cause(self):
        original = FalseyCancellation("MODEL_CANCEL_BEFORE_POLL")
        cause = original.__cause__ = ValueError("MODEL_ORIGINAL_CAUSE")
        def cancel():
            if capture._child is not None:
                raise original
        capture = self.capture(cancelled=cancel)
        self.assertIs(caught(lambda: self.run_ok(capture)), original)
        self.assertIs(original.__cause__, cause)
        self.assertFalse(any(row[0] == "poll" for row in self.events))
        self.assertIsNone(capture.failure_capture.exit_code)
        self.assertEqual(capture.failure_capture.stdout, b"MODEL_PRIVATE_STDOUT")
        self.assertEqual((capture._raw_end, capture._local_end), (280 * clocks.NS, 270.0))
        self.assert_no_result(capture)

    def test_exit_zero_followed_by_cancellation_is_failure_evidence_not_success(self):
        original = FalseyCancellation("MODEL_CANCEL_AFTER_ZERO_EXIT")
        def cancel():
            if capture._exit_code is not None:
                raise original
        capture = self.capture(cancelled=cancel)
        self.assertIs(caught(lambda: self.run_ok(capture)), original)
        self.assertEqual(capture.failure_capture.exit_code, 0)
        self.assertFalse(capture._waited)
        self.assert_no_result(capture)

    def test_new_caught_reentry_during_failed_retirement_prevents_any_failure_read(self):
        capture = self.capture()
        self.codes = [7]
        def drain(**kwargs):
            self.assertRegex(str(caught(capture.prepare)), "PROVIDER_OPERATION_REENTRY")
            return []
        self.scope.drain.side_effect = drain
        error = caught(lambda: self.run_ok(capture))
        self.assertRegex(str(error), "PROVIDER_CHILD_FAILED")
        self.assertIs(error, capture._primary)
        self.assertEqual(capture._raw_captures, {})
        self.assertFalse(capture._slots["command-reader"].attempted)
        self.assertTrue(capture._slots["scope"].closed)
        self.assertIsInstance(caught(lambda: capture.failure_capture), lifecycle.ProviderLifecycleError)
        self.assert_no_result(capture)

    def test_failed_wait_still_rechecks_the_original_single_leader(self):
        capture, remembered = self.capture(), []
        self.codes = [7]
        def call():
            with capture:
                self.prepare(capture)
                remembered.append(caught(lambda: capture.wait(self.launch(capture))))
                self.scope.leaders.append(self.scope.leaders[0])
        self.assertIs(caught(call), remembered[0])
        self.assertEqual(capture._raw_captures, {})
        self.assertIsInstance(caught(lambda: capture.failure_capture), lifecycle.ProviderLifecycleError)
        self.assert_no_result(capture)

    def test_failed_child_admission_cannot_qualify_empty_provider_captures(self):
        capture = self.capture()
        def call():
            with capture:
                self.prepare(capture)
                child = self.launch(capture)
                self.scope.leaders.append(child)
                capture.wait(child)
        error = caught(call)
        self.assertRegex(str(error), "PROVIDER_ORIGINAL_LEADER")
        self.assertIsNone(capture._child)
        self.assertEqual(capture._raw_captures, {})
        self.assertTrue(capture._slots["scope"].closed)
        self.assertIsInstance(caught(lambda: capture.failure_capture), lifecycle.ProviderLifecycleError)
        self.assert_no_result(capture)

    def test_body_cancellation_before_wait_is_not_an_admitted_provider_return(self):
        capture, original = self.capture(), FalseyCancellation("MODEL_BEFORE_ANY_WAIT")
        def call():
            with capture:
                self.prepare(capture)
                raise original
        self.assertIs(caught(call), original)
        self.assertTrue(capture._slots["scope"].closed)
        self.assertEqual(capture._raw_captures, {})
        self.assertIsInstance(caught(lambda: capture.failure_capture), lifecycle.ProviderLifecycleError)
        self.assert_no_result(capture)

    def test_late_staging_mutation_never_replaces_actual_failure_byte_returns(self):
        capture, changed = self.capture(), []
        self.codes = [7]
        def replace_staging():
            if capture._slots["directory"].closed and not changed:
                changed.append(capture._raw_captures["stdout"])
                capture._raw_captures["stdout"] = b"MODEL_NOT_RETURNED_FROM_READ"
        self.on_raw = replace_staging
        error = caught(lambda: self.run_ok(capture))
        self.assertRegex(str(error), "PROVIDER_CHILD_FAILED")
        self.assertEqual(changed, [b"MODEL_PRIVATE_STDOUT"])
        self.assertEqual(capture.failure_capture.stdout, b"MODEL_PRIVATE_STDOUT")
        self.assert_no_result(capture)

    def test_exit_diagnostics_cannot_rewrite_original_failure_observations(self):
        capture, saved = self.capture(), []
        self.codes = [7]
        classify = lifecycle.diagnostics._exception_detail
        def replace_fields(error):
            if capture._failure_capture_ready and not saved:
                saved.append((capture._native_retirement,
                    tuple(name for name, slot in capture._slots.items() if slot.owner is not None and slot.closed)))
                capture._raw_captures["command"] = b"MODEL_NOT_AN_EMPTY_SAVE_RETURN"
                capture._native_retirement = b"MODEL_NOT_ORIGINAL_NATIVE_RETIREMENT"
                capture._slots["directory"].closed = False
                capture._phase, capture._exit_code = "lookup", 0
            return classify(error)
        with patch.object(lifecycle.diagnostics, "_exception_detail", replace_fields):
            error = caught(lambda: self.run_ok(capture))
        self.assertRegex(str(error), "PROVIDER_CHILD_FAILED")
        result = capture.failure_capture
        self.assertEqual((result.phase, result.exit_code, result.command), ("save", 7, b""))
        self.assertEqual((result.native_retirement, result.closed_resources), saved[0])
        self.assert_no_result(capture)

    def test_failed_command_read_return_is_staged_before_late_postcheck(self):
        capture = self.capture("lookup")
        self.codes = [7]
        read = files.NativeFile.read
        command = b"MODEL_BOUNDED_FAILURE_COMMAND"
        def late(reader, *args):
            raw = read(reader, *args)
            self.raw = 280 * clocks.NS
            return raw
        with patch.object(files.NativeFile, "read", late):
            error = caught(lambda: self.run_ok(capture, command))
        self.assertRegex(str(error), "PROVIDER_CHILD_FAILED")
        self.assertEqual(capture._raw_captures, {"command": command})
        self.assertEqual(capture._verified_captures, set())
        self.assertIsInstance(caught(lambda: capture.failure_capture), lifecycle.ProviderLifecycleError)
        self.assert_no_result(capture)

    def test_failed_log_bytes_remain_private_when_later_writer_close_is_unknown(self):
        capture = self.capture()
        self.codes = [7]
        close = files.NativeFile.close
        def ambiguous(writer):
            name = PureWindowsPath(writer.path).name
            close(writer)
            if name == "provider-stdout.log":
                raise FalseyFailure("MODEL_POST_RELEASE_UNKNOWN")
        with patch.object(files.NativeFile, "close", ambiguous):
            error = caught(lambda: self.run_ok(capture))
        self.assertRegex(str(error), "PROVIDER_CHILD_FAILED")
        self.assertTrue(capture.unknown)
        self.assertEqual(capture._raw_captures, {"command": b"", "stdout": b"MODEL_PRIVATE_STDOUT"})
        self.assertEqual(capture._verified_captures, {"command", "stdout"})
        self.assertFalse(capture._slots["stderr"].close_attempted)
        self.assertIsInstance(caught(lambda: capture.failure_capture), lifecycle.ProviderLifecycleError)
        self.assert_no_result(capture)

    def test_failed_backend_without_return_cannot_invent_partial_stdout(self):
        capture = self.capture()
        self.codes = [7]
        readback = files.NativeFile.read_provider_log
        def no_return(writer):
            readback(writer)
            raise FalseyFailure("MODEL_READ_NEVER_RETURNED_TO_CALLER")
        with patch.object(files.NativeFile, "read_provider_log", no_return):
            error = caught(lambda: self.run_ok(capture))
        self.assertRegex(str(error), "PROVIDER_CHILD_FAILED")
        self.assertEqual(capture._raw_captures, {"command": b""})
        self.assertTrue(capture.unknown)
        self.assertIsInstance(caught(lambda: capture.failure_capture), lifecycle.ProviderLifecycleError)
        self.assert_no_result(capture)

    def test_exit_classification_cannot_replace_equal_failure_prefix_rows(self):
        capture = self.capture()
        self.codes = [7]
        classify = lifecycle.diagnostics._exception_detail
        def replace_prefix(error):
            if capture._failure_capture_ready:
                saved = capture._errors[0]
                capture._errors[0] = tuple(list(saved))
                self.assertIsNot(capture._errors[0], saved)
            return classify(error)
        with patch.object(lifecycle.diagnostics, "_exception_detail", replace_prefix):
            error = caught(lambda: self.run_ok(capture))
        self.assertRegex(str(error), "PROVIDER_CHILD_FAILED")
        self.assertEqual(capture._verified_captures, {"command", "stdout", "stderr"})
        self.assertIsInstance(caught(lambda: capture.failure_capture), lifecycle.ProviderLifecycleError)
        self.assert_no_result(capture)

    def test_exit_classification_itself_spends_the_original_failure_capture_end(self):
        capture = self.capture()
        self.codes = [7]
        classify = lifecycle.diagnostics._exception_detail
        def late(error):
            if capture._failure_capture_ready:
                self.local = 280.0
            return classify(error)
        with patch.object(lifecycle.diagnostics, "_exception_detail", late):
            error = caught(lambda: self.run_ok(capture))
        self.assertRegex(str(error), "PROVIDER_CHILD_FAILED")
        self.assertEqual(capture._verified_captures, {"command", "stdout", "stderr"})
        self.assertTrue(all(slot.closed for slot in capture._slots.values() if slot.owner is not None))
        self.assertIsInstance(caught(lambda: capture.failure_capture), lifecycle.ProviderLifecycleError)
        self.assert_no_result(capture)

    def test_unknown_exit_classification_blocks_otherwise_complete_failure_capture(self):
        capture = self.capture()
        self.codes = [7]
        classify = lifecycle.diagnostics._exception_detail
        def unknown(error):
            if capture._failure_capture_ready:
                raise FalseyFailure("MODEL_EXIT_DIAGNOSTIC_UNKNOWN")
            return classify(error)
        with patch.object(lifecycle.diagnostics, "_exception_detail", unknown):
            error = caught(lambda: self.run_ok(capture))
        self.assertRegex(str(error), "PROVIDER_CHILD_FAILED")
        self.assertTrue(capture.unknown)
        self.assertIn(capture, lifecycle.QUARANTINE)
        self.assertIsInstance(caught(lambda: capture.failure_capture), lifecycle.ProviderLifecycleError)
        self.assert_no_result(capture)

    def test_failure_result_construction_and_later_reentry_cannot_requalify_bytes(self):
        capture = self.capture()
        self.codes = [7]
        construct = lifecycle.FailedProviderCapture
        def late(*args, **kwargs):
            result = construct(*args, **kwargs)
            self.raw = 280 * clocks.NS
            return result
        with patch.object(lifecycle, "FailedProviderCapture", late):
            error = caught(lambda: self.run_ok(capture))
        self.assertRegex(str(error), "PROVIDER_CHILD_FAILED")
        self.assertIsInstance(caught(lambda: capture.failure_capture), lifecycle.ProviderLifecycleError)
        self.assertIs(caught(lambda: capture.__exit__(None, None, None)), error)
        self.assertIsInstance(caught(lambda: capture.failure_capture), lifecycle.ProviderLifecycleError)
        self.assert_no_result(capture)

    def test_exit_observation_precedes_a_late_local_check(self):
        capture = self.capture()
        def call():
            with capture:
                self.prepare(capture)
                child = self.launch(capture)
                def late():
                    self.local = 230.0
                    return 0
                child.poll = late
                capture.wait(child)
        self.assertIsInstance(caught(call), lifecycle.ProviderLifecycleError)
        self.assertEqual(capture._exit_code, 0)
        self.assertFalse(capture._waited)
        self.assert_no_result(capture)

    def test_missing_wait_never_becomes_a_successful_enclosing_outcome(self):
        capture = self.capture()
        def call():
            with capture:
                self.prepare(capture)
                self.launch(capture)
        self.assertRegex(str(caught(call)), "PROVIDER_WAIT_REQUIRED")
        self.assert_no_result(capture)

    def test_second_launch_after_successful_wait_is_rechecked_at_exit(self):
        capture = self.capture()
        def call():
            with capture:
                self.prepare(capture)
                capture.wait(self.launch(capture))
                self.launch(capture)
        self.assertRegex(str(caught(call)), "PROVIDER_ORIGINAL_LEADER")
        self.assert_no_result(capture)

    def test_survivors_block_freeze(self):
        capture = self.capture()
        self.scope.drain.return_value = [{"pid": 7}]
        self.scope.drain.side_effect = None
        error = caught(lambda: self.run_ok(capture))
        self.assertRegex(str(error), "PROVIDER_SURVIVORS")
        self.assertTrue(capture.unknown)
        self.assertIsNone(capture._slots["command-reader"].owner)
        self.assertFalse(capture._slots["command"].close_attempted)
        self.assertTrue(capture._slots["scope"].close_attempted)
        self.assert_no_result(capture)

    def test_discovery_error_refuses_empty_domain_return(self):
        capture = self.capture()
        self.scope.discovery_errors.add("MODEL_DISCOVERY_UNKNOWN")
        self.assertRegex(str(caught(lambda: self.run_ok(capture))), "PROVIDER_DISCOVERY_UNKNOWN")
        self.assertTrue(capture.unknown)
        self.assertIsNone(capture._slots["command-reader"].owner)

    def test_pending_lifetime_refuses_empty_domain_return(self):
        capture = self.capture()
        self.scope.pending_discoveries = {7: "MODEL_UNRESOLVED"}
        self.assertRegex(str(caught(lambda: self.run_ok(capture))), "PROVIDER_DISCOVERY_UNKNOWN")
        self.assertTrue(capture.unknown)
        self.assertIsNone(capture._slots["command-reader"].owner)

    def test_unknown_close_and_expiry_keep_first_cancellation_and_never_retry(self):
        capture, original = self.capture(), FalseyCancellation("MODEL_CANCELLED")
        def bad_close(handle):
            self.local = 280.0
            raise FalseyFailure("MODEL_NATIVE_CLOSE_UNKNOWN")
        self.on_native_close = bad_close
        def call():
            with capture:
                self.prepare(capture)
                self.launch(capture)
                raise original
        self.assertIs(caught(call), original)
        self.assertTrue(capture.unknown)
        self.assertTrue(any(stage == "scope-close" for stage, _ in capture._errors))
        self.assertTrue(any("postclose" in stage for stage, _ in capture._errors))
        before = list(self.events)
        self.assertIs(caught(lambda: capture.__exit__(None, None, None)), original)
        self.assertEqual(self.events, before)
        self.assertFalse(capture._slots["command"].close_attempted)
        self.assert_no_result(capture)

    def test_expired_final_frame_never_falls_back_to_unbounded_drain(self):
        capture, original = self.capture(), FalseyFailure("MODEL_BODY_AT_DEADLINE")
        def call():
            with capture:
                self.prepare(capture)
                self.launch(capture)
                self.local = 280.0
                raise original
        self.assertIs(caught(call), original)
        self.scope.drain.assert_not_called()
        self.assertTrue(capture._slots["scope"].close_attempted)
        self.assertTrue(capture.unknown)
        self.assert_no_result(capture)

    def test_late_drain_refuses_capture(self):
        capture = self.capture()
        def late(**kwargs):
            self.events.append(("drain", kwargs))
            self.local = 280.0
            return []
        self.scope.drain.side_effect = late
        self.assertIsInstance(caught(lambda: self.run_ok(capture)), lifecycle.ProviderLifecycleError)
        self.assertTrue(capture.unknown)
        self.assertTrue(capture._slots["scope"].close_attempted)
        self.assertIsNone(capture._slots["command-reader"].owner)
        self.assert_no_result(capture)

    def test_freeze_follows_domain_drain_and_scope_close(self):
        capture = self.capture()
        original = files._ProviderCommandFile.freeze
        def ordered(command):
            self.assertTrue(capture._slots["scope"].closed)
            self.assertEqual(self.scope.drain.call_count, 1)
            self.events.append(("freeze",))
            return original(command)
        with patch.object(files._ProviderCommandFile, "freeze", ordered):
            self.run_ok(capture)
        self.assertLess(self.events.index(("native-close", 91)), self.events.index(("freeze",)))

    def test_frozen_reader_is_registered_before_fallible_post_return_observation(self):
        capture = self.capture()
        original, failed = capture._check, []
        def check(*, final=False, cleanup=False):
            slot = capture._slots["command-reader"]
            if slot.owner is not None and not failed:
                failed.append(slot.owner)
                raise FalseyFailure("MODEL_AFTER_FREEZE_RETURN")
            return original(final=final, cleanup=cleanup)
        capture._check = check
        error = caught(lambda: self.run_ok(capture))
        self.assertIsInstance(error, FalseyFailure)
        self.assertEqual(len(failed), 1)
        self.assertIs(capture._slots["command-reader"].owner, failed[0])
        self.assertTrue(capture._slots["command-reader"].close_attempted)
        self.assertTrue(capture._slots["command"].close_attempted)
        self.assertTrue(capture._slots["command"].closed)
        self.assertTrue(capture._slots["directory"].closed)
        self.assert_no_result(capture)

    def test_raw_sample_itself_cannot_escape_the_saved_local_end_after_last_close(self):
        capture = self.capture()
        def during_raw():
            if capture._slots["directory"].closed:
                self.local = 280.0
        self.on_raw = during_raw
        self.assertRegex(str(caught(lambda: self.run_ok(capture))), "PROVIDER_LOCAL_EXPIRED")
        self.assertTrue(capture._slots["directory"].closed)
        self.assertEqual(self.api.handles, {})
        self.assert_no_result(capture)

    def test_last_separate_directory_close_must_fit_even_after_reader_closed(self):
        capture = self.capture()
        original = self.api.close
        last = self.root._pins[0].handle
        def late(handle):
            original(handle)
            if handle == last:
                self.assertTrue(capture._slots["command-reader"].closed)
                self.local = 280.0
        with patch.object(self.api, "close", side_effect=late):
            self.assertRegex(str(caught(lambda: self.run_ok(capture))), "PROVIDER_LOCAL_EXPIRED")
        self.assertTrue(capture._slots["directory"].closed)
        self.assertEqual(self.api.handles, {})
        self.assert_no_result(capture)

    def test_final_cancellation_after_all_closes_still_blocks_the_result(self):
        original = FalseyCancellation("MODEL_FINAL_CANCEL")
        capture = self.capture()
        def cancel():
            if capture._slots["directory"].closed:
                raise original
        capture._cancelled = cancel
        self.assertIs(caught(lambda: self.run_ok(capture)), original)
        self.assertTrue(all(slot.closed for slot in capture._slots.values() if slot.owner is not None))
        self.assert_no_result(capture)

    def test_local_rollback_after_cancellation_callback_is_sticky(self):
        capture = self.capture(cancelled=lambda: setattr(self, "local", 99.0))
        error = caught(lambda: self.run_ok(capture))
        self.assertRegex(str(error), "PROVIDER_LOCAL_BACKWARDS_OR_INVALID")
        self.assertFalse(capture._slots["stdout"].attempted)
        self.factory.assert_not_called()
        self.assert_no_result(capture)

    def test_local_rollback_in_sleep_calculation_never_sleeps(self):
        capture, samples = self.capture(), []
        self.codes = [None]
        def local():
            if self.scope.discover.called:
                samples.append(1)
                if len(samples) == 3:  # Two work-check samples, then the sleep calculation.
                    return 99.0
            return self.local
        with patch.object(lifecycle, "time", SimpleNamespace(monotonic=local, sleep=self.sleep)):
            self.assertRegex(str(caught(lambda: self.run_ok(capture))), "PROVIDER_LOCAL_BACKWARDS_OR_INVALID")
        self.assertFalse(any(row[0] == "sleep" for row in self.events))
        self.assert_no_result(capture)

    def test_local_rollback_in_final_remaining_calculation_never_drains(self):
        capture, samples = self.capture(), []
        def local():
            if capture._operation == "exit":
                samples.append(1)
                if len(samples) == 2:
                    return 99.0
            return self.local
        with patch.object(lifecycle, "time", SimpleNamespace(monotonic=local, sleep=self.sleep)):
            self.assertRegex(str(caught(lambda: self.run_ok(capture))), "PROVIDER_LOCAL_BACKWARDS_OR_INVALID")
        self.scope.drain.assert_not_called()
        self.assertTrue(capture._slots["scope"].closed)
        self.assertTrue(capture.unknown)
        self.assertFalse(capture._slots["command"].close_attempted)

    def test_local_high_water_rejects_nonfinite_boolean_and_negative_samples(self):
        capture = self.capture()
        for value in (float("nan"), float("inf"), True, -1.0):
            with self.subTest(value=value), patch.object(lifecycle, "time", SimpleNamespace(monotonic=lambda: value)):
                self.assertRegex(str(caught(capture._local)), "PROVIDER_LOCAL_BACKWARDS_OR_INVALID")
        self.assertEqual(capture._local_highest, 0.0)
        self.factory.assert_not_called()

    def assert_capture_owners_quarantined(self, capture):
        self.assertTrue(capture.unknown)
        self.assertTrue(capture._slots["scope"].closed)
        self.assertIn(capture, lifecycle.QUARANTINE)
        self.assertFalse(capture._slots["command"].close_attempted)
        self.assertFalse(capture._slots["directory"].close_attempted)
        self.assert_no_result(capture)

    def test_scope_close_crossing_local_end_does_not_release_file_owners(self):
        capture = self.capture()
        self.on_native_close = lambda handle: setattr(self, "local", 280.0) if handle == 91 else None
        self.assertRegex(str(caught(lambda: self.run_ok(capture))), "PROVIDER_LOCAL_EXPIRED")
        self.assert_capture_owners_quarantined(capture)

    def test_scope_close_crossing_raw_end_does_not_release_file_owners(self):
        capture = self.capture()
        self.on_native_close = lambda handle: setattr(self, "raw", 280 * clocks.NS) if handle == 91 else None
        self.assertRegex(str(caught(lambda: self.run_ok(capture))), "PROVIDER_RAW_EXPIRED")
        self.assert_capture_owners_quarantined(capture)

    def test_failed_freeze_quarantines_every_remaining_original_file_owner(self):
        capture, original = self.capture(), FalseyFailure("MODEL_FREEZE_FAILED")
        with patch.object(files._ProviderCommandFile, "freeze", side_effect=original):
            self.assertIs(caught(lambda: self.run_ok(capture)), original)
        self.assertTrue(capture._slots["command-reader"].attempted)
        self.assertIsNone(capture._slots["command-reader"].owner)
        self.assert_capture_owners_quarantined(capture)

    def test_failed_log_readback_open_quarantines_original_writer_prior_reader_and_directory(self):
        capture, original = self.capture(), FalseyFailure("MODEL_READER_OPEN_FAILED")
        with patch.object(self.api, "provider_log_reader", side_effect=original):
            self.assertIs(caught(lambda: self.run_ok(capture)), original)
        self.assertTrue(capture.unknown)
        self.assertFalse(capture._slots["stdout"].close_attempted)
        self.assertTrue(capture._slots["stdout"].owner._provider_log_unknown)
        self.assertFalse(capture._slots["stdout-reader"].attempted)
        self.assertIsNotNone(capture._slots["command-reader"].owner)
        self.assertFalse(capture._slots["command-reader"].close_attempted)
        self.assertFalse(capture._slots["stderr"].close_attempted)
        self.assertFalse(capture._slots["directory"].close_attempted)
        self.assert_no_result(capture)

    def test_failed_command_reader_close_stops_later_distinct_owner_closes(self):
        capture, original = self.capture(), FalseyCancellation("MODEL_READER_CLOSE_FAILED")
        close = files.NativeFile.close
        def fail(reader):
            if not reader._writable and str(reader.path).endswith("provider-output.txt"):
                raise original
            return close(reader)
        with patch.object(files.NativeFile, "close", fail):
            self.assertIs(caught(lambda: self.run_ok(capture)), original)
        self.assertTrue(capture.unknown)
        self.assertTrue(capture._slots["command-reader"].close_attempted)
        self.assertFalse(capture._slots["command-reader"].closed)
        self.assertTrue(capture._slots["stdout"].closed and capture._slots["stderr"].closed)
        for name in ("stdout-reader", "stderr-reader", "directory"):
            self.assertFalse(capture._slots[name].close_attempted, name)
        self.assert_no_result(capture)

    def test_unknown_discovered_in_preclose_fence_prevents_that_outer_close(self):
        capture, original = self.capture(), FalseyFailure("MODEL_FENCE_FAILURE")
        original.add_note("MODEL_SUPPLIER_RETIREMENT_UNKNOWN")
        check = capture._postcheck
        def fence(stage):
            if stage == "stdout-preclose":
                capture._failed(stage, original)
                return False
            return check(stage)
        capture._postcheck = fence
        self.assertIs(caught(lambda: self.run_ok(capture)), original)
        self.assertTrue(capture.unknown)
        self.assertFalse(capture._slots["stdout"].close_attempted)
        self.assertFalse(capture._slots["stderr"].close_attempted)
        self.assertFalse(capture._slots["command-reader"].close_attempted)
        self.assertFalse(capture._slots["directory"].close_attempted)
        self.assert_no_result(capture)

    def fail_body(self, capture, original):
        with capture:
            self.prepare(capture)
            self.launch(capture)
            raise original

    def test_note_only_unknown_preserves_falsey_original_and_quarantines(self):
        capture, original = self.capture(), FalseyCancellation("MODEL_BODY_FAILURE")
        original.add_note("MODEL_SUPPLIER_RETIREMENT_UNKNOWN")
        self.assertIs(caught(lambda: self.fail_body(capture, original)), original)
        self.assert_capture_owners_quarantined(capture)

    def test_cause_only_unknown_preserves_original_cause_and_quarantines(self):
        capture, original = self.capture(), FalseyFailure("MODEL_BODY_FAILURE")
        cause = original.__cause__ = ValueError("MODEL_CAUSE_RETIREMENT_UNKNOWN")
        self.assertIs(caught(lambda: self.fail_body(capture, original)), original)
        self.assertIs(original.__cause__, cause)
        self.assert_capture_owners_quarantined(capture)

    def test_raising_carrier_accessor_does_not_interrupt_known_scope_cleanup(self):
        class UnreadableCarrier(FalseyFailure):
            @property
            def _p2pkit_retirement(self):
                raise ValueError("MODEL_BAD_CARRIER_ACCESSOR")
        capture, original = self.capture(), UnreadableCarrier("MODEL_BODY_FAILURE")
        self.assertIs(caught(lambda: self.fail_body(capture, original)), original)
        self.scope.drain.assert_called_once()
        self.assert_capture_owners_quarantined(capture)

    def test_failed_diagnostic_classifier_keeps_primary_and_known_scope_close(self):
        capture, original = self.capture(), FalseyCancellation("MODEL_BODY_FAILURE")
        with patch.object(lifecycle.diagnostics, "_exception_detail", side_effect=ValueError("MODEL_DIAGNOSTIC_FAILURE")):
            self.assertIs(caught(lambda: self.fail_body(capture, original)), original)
        self.assert_capture_owners_quarantined(capture)

    def test_caught_reentrant_exit_cannot_close_resources_beneath_wait(self):
        capture, nested = self.capture(), []
        def cancel():
            if capture._operation == "wait" and not nested:
                before = (capture._active, capture._finished, capture._slots["scope"].close_attempted)
                nested.append(caught(lambda: capture.__exit__(None, None, None)))
                self.assertEqual((capture._active, capture._finished, capture._slots["scope"].close_attempted), before)
        capture._cancelled = cancel
        self.assertIs(caught(lambda: self.run_ok(capture)), nested[0])
        self.assertRegex(str(nested[0]), "PROVIDER_OPERATION_REENTRY")
        self.scope.drain.assert_called_once()
        self.assertTrue(capture._slots["scope"].closed)
        self.assert_no_result(capture)

    def test_caught_reentrant_prepare_failure_stops_outer_allocation(self):
        capture, nested = self.capture(), []
        def cancel():
            if not nested:
                nested.append(caught(capture.prepare))
        capture._cancelled = cancel
        self.assertIs(caught(lambda: self.run_ok(capture)), nested[0])
        self.assertRegex(str(nested[0]), "PROVIDER_OPERATION_REENTRY")
        self.assertFalse(capture._slots["stdout"].attempted)
        self.assertTrue(capture._slots["directory"].closed)
        self.factory.assert_not_called()

    def test_wrong_thread_refusal_does_not_transfer_a_directory(self):
        capture, failures = self.capture(), []
        def call():
            with capture:
                with patch.object(lifecycle, "threading", SimpleNamespace(get_ident=lambda: -1)):
                    failures.append(caught(lambda: capture.take_directory(self.root)))
                self.assertRegex(str(failures[0]), "PROVIDER_OPERATION_REENTRY")
                self.assertIsNone(capture._slots["directory"].owner)
                # The real owner of the untransferred directory remains this fixture.
                self.assertFalse(self.root._closed)
                self.assertIs(caught(capture.prepare), failures[0])
        self.assertIs(caught(call), failures[0])

    def test_late_result_construction_cannot_publish_an_otherwise_complete_capture(self):
        capture, constructor = self.capture(), lifecycle.CapturedProvider
        def late(*args):
            result = constructor(*args)
            self.local = 280.0
            return result
        with patch.object(lifecycle, "CapturedProvider", side_effect=late):
            self.assertRegex(str(caught(lambda: self.run_ok(capture))), "PROVIDER_LOCAL_EXPIRED")
        self.assertTrue(all(slot.closed for slot in capture._slots.values() if slot.owner is not None))
        self.assertIsNone(capture._result)
        self.assert_no_result(capture)

    def test_late_command_read_never_acquires_a_log_reader(self):
        capture, read = self.capture(), files.NativeFile.read
        def late(reader, *args):
            raw = read(reader, *args)
            if str(reader.path).endswith("provider-output.txt"):
                self.raw = 280 * clocks.NS
            return raw
        with patch.object(files.NativeFile, "read", late), \
                patch.object(self.api, "provider_log_reader", wraps=self.api.provider_log_reader) as log_reader:
            self.assertRegex(str(caught(lambda: self.run_ok(capture))), "PROVIDER_RAW_EXPIRED")
        log_reader.assert_not_called()
        self.assertFalse(capture._slots["stdout"].owner._provider_log_started)
        self.assert_no_result(capture)

    def test_windows_log_readback_keeps_original_writer_through_temporary_close(self):
        capture, opener, pairs = self.capture(), self.api.provider_log_reader, []
        def pinned(parent, filename):
            name = "stdout" if filename == "provider-stdout.log" else "stderr"
            writer = capture._slots[name].owner
            original = writer.native_handle
            self.assertTrue(capture._slots["scope"].closed)
            self.assertEqual(self.scope.drain.call_count, 1)
            self.assertFalse(writer.closed)
            self.assertEqual(self.api.modes[original], (2, 1))
            node = self.api.nodes[str(writer.path)]
            # A same-size overwrite needs a conflicting writer: the old
            # close/reopen interval no longer exists in this sharing model.
            with self.assertRaisesRegex(files.FilesystemError, "sharing"):
                self.api.shared_open(node, 2, 7)
            reader = opener(parent, filename)
            pairs.append((original, reader))
            return reader
        close = self.api.close
        def ordered(handle):
            for original, reader in pairs:
                if handle == reader:
                    self.assertIn(original, self.api.handles)
                elif handle == original:
                    self.assertNotIn(reader, self.api.handles)
            close(handle)
        with patch.object(self.root, "open_file", side_effect=AssertionError("MODEL_CLOSE_REOPEN_FORBIDDEN")) as ordinary, \
                patch.object(self.api, "provider_log_reader", pinned), patch.object(self.api, "close", ordered):
            result = self.run_ok(capture)
        ordinary.assert_not_called()
        self.assertEqual(result.stdout, b"MODEL_PRIVATE_STDOUT")
        self.assertEqual(result.stderr, b"MODEL_PRIVATE_STDERR")
        self.assertEqual(len(pairs), 2)
        for original, reader in pairs:
            closes = [row[1] for row in self.api.events if row[0] == "close"]
            self.assertEqual(closes.count(original), 1)
            self.assertEqual(closes.count(reader), 1)
            self.assertLess(closes.index(reader), closes.index(original))
        self.assertEqual(result.provider_acceptance, "NOT_ESTABLISHED")
        self.never_classifier.assert_not_called()

    def test_unnotable_readback_failure_quarantines_before_any_distinct_file_owner_close(self):
        diagnostic = RuntimeError("MODEL_NOTE_FAILED")
        class Unnotable(FalseyCancellation):
            def add_note(self, _message):
                raise diagnostic
        capture, original = self.capture(), Unnotable("MODEL_LOG_READ_FAILED")
        read = self.api.read
        def failure(handle, count):
            if self.api.handles[handle][0].path.endswith("provider-stdout.log"):
                raise original
            return read(handle, count)
        with patch.object(self.api, "read", failure), \
                patch.object(lifecycle.diagnostics, "_exception_detail", return_value={"retirementUnknown": False}):
            self.assertIs(caught(lambda: self.run_ok(capture)), original)
        self.assertFalse(hasattr(original, "__notes__"))
        writer = capture._slots["stdout"].owner
        self.assertTrue(capture.unknown and writer._provider_log_unknown)
        self.assertIn(diagnostic, writer._provider_log_secondary)
        self.assertIsNone(writer._provider_log_reader)  # Actual temporary close is separately known.
        self.assertIn(writer._pins[-1].handle, self.api.handles)
        for name in ("stdout", "stderr", "command-reader", "directory"):
            self.assertFalse(capture._slots[name].close_attempted, name)
        self.assertFalse(capture._slots["stderr"].owner._provider_log_started)
        before = list(self.api.events)
        self.assertIs(caught(lambda: capture.__exit__(None, None, None)), original)
        self.assertEqual(self.api.events, before)
        self.assert_no_result(capture)

    def test_failed_temporary_log_reader_close_retains_writer_and_other_owners(self):
        capture, original = self.capture(), FalseyCancellation("MODEL_TEMP_READER_CLOSE_FAILED")
        close, attempts = self.api.close, []
        def fail(handle):
            if self.api.modes[handle] == (1, 3) and self.api.handles[handle][0].path.endswith("provider-stderr.log"):
                attempts.append(handle)
                raise original
            return close(handle)
        with patch.object(self.api, "close", fail):
            self.assertIs(caught(lambda: self.run_ok(capture)), original)
        self.assertEqual(len(attempts), 1)
        writer = capture._slots["stderr"].owner
        self.assertEqual(writer._provider_log_reader, attempts[0])
        self.assertIn(attempts[0], self.api.handles)
        self.assertTrue(capture.unknown and writer._provider_log_unknown)
        self.assertTrue(capture._slots["stdout"].closed)
        for name in ("stderr", "command-reader", "directory"):
            self.assertFalse(capture._slots[name].close_attempted, name)
        self.assert_no_result(capture)

    def late_temporary_log_close(self, domain):
        capture, close, closed = self.capture(), self.api.close, []
        def late(handle):
            target = self.api.modes[handle] == (1, 3) and self.api.handles[handle][0].path.endswith("provider-stdout.log")
            close(handle)
            if target:
                closed.append(handle)
                if domain == "raw":
                    self.raw = 280 * clocks.NS
                else:
                    self.local = 270.0
        with patch.object(self.api, "close", late):
            error = caught(lambda: self.run_ok(capture))
        self.assertEqual(len(closed), 1)
        self.assertNotIn(closed[0], self.api.handles)
        self.assertIsNone(capture._slots["stdout"].owner._provider_log_reader)
        self.assertFalse(capture._slots["stderr"].owner._provider_log_started)
        self.assertEqual(capture._local_end, 270.0)
        self.assertEqual(capture._raw_end, 280 * clocks.NS)
        self.assert_no_result(capture)
        return capture, error

    def test_temporary_log_close_crossing_raw_end_is_not_successful_capture(self):
        capture, error = self.late_temporary_log_close("raw")
        self.assertRegex(str(error), "PROVIDER_RAW_EXPIRED")
        self.assertTrue(capture._slots["stdout"].closed)

    def test_temporary_log_close_crossing_local_end_keeps_original_writer_unknown(self):
        capture, error = self.late_temporary_log_close("local")
        self.assertRegex(str(error), "deadline")
        self.assertTrue(capture.unknown and capture._slots["stdout"].owner._provider_log_unknown)
        for name in ("stdout", "stderr", "command-reader", "directory"):
            self.assertFalse(capture._slots[name].close_attempted, name)

    def test_log_readback_return_rechecks_full_original_metadata_not_only_size(self):
        capture, readback = self.capture(), files.NativeFile.read_provider_log
        def changed(writer):
            raw = readback(writer)
            self.api.nodes[str(writer.path)].version += 1
            return raw
        with patch.object(files.NativeFile, "read_provider_log", changed):
            self.assertRegex(str(caught(lambda: self.run_ok(capture))), "PROVIDER_CAPTURE_CHANGED")
        self.assertFalse(capture._slots["stderr"].owner._provider_log_started)
        self.assert_no_result(capture)


class ProviderPosixLifecycleModels(unittest.TestCase):
    """Actual tiny private files; process/clock suppliers are explicit models."""
    def setUp(self):
        self.assertNotEqual(os.geteuid(), 0, "Run tiny-file controls under the guarded ordinary UID")
        self.temporary = tempfile.TemporaryDirectory(prefix="provider-posix-model-")
        self.base = Path(self.temporary.name)
        self.root = lifecycle.files._new_private_directory(self.base / "captures")
        self.local, self.raw = 100.0, 100 * clocks.NS
        self.clock = clocks.ClockIdentity("linux-x64", clocks.LINUX_DOMAIN, clocks.NS)
        self.time = SimpleNamespace(monotonic=lambda: self.local, sleep=lambda _seconds: self.fail("Unexpected model sleep"))
        patch.object(lifecycle, "time", self.time).start()
        patch.object(lifecycle.files.posix_files, "time", self.time).start()
        patch.object(clocks, "checked_now", self.now).start()
        self.scope = self.new_scope(processes.LinuxScope)
        self.factory = patch.object(processes, "make_scope", side_effect=lambda *_args: self.scope).start()
        self.streams, self.opens, self.captures = [], [], []
        self.reader_wrap = self.before_open = None
        self.open_stream = lifecycle.files._posix_stream
        patch.object(lifecycle.files, "_posix_stream", self.stream).start()
        self.never_classifier = patch.object(lifecycle.cache, "provider_observation",
            side_effect=AssertionError("MODEL_CAPTURE_NOT_PROVIDER_ACCEPTANCE")).start()

    def tearDown(self):
        # No real processes were created. Dispose actual tiny model descriptors
        # only after assertions; this is not a production UNKNOWN recovery path.
        patch.stopall()
        for capture in self.captures:
            for slot in capture._slots.values():
                if slot.owner is not None and not slot.close_attempted:
                    try:
                        slot.owner.close()
                    except BaseException:
                        pass
        for stream in self.streams:
            stream.close()
        self.root.close()
        lifecycle.QUARANTINE.clear()
        self.temporary.cleanup()

    def new_scope(self, kind):
        with patch.object(kind, "_admit"), patch.object(kind, "_pids", return_value=[]):
            scope = kind("1" * 32, "2" * 32, str(self.root.path), str(self.base / "home"))
        if kind is processes.DarwinScope:
            scope.observation_reconciliations, scope.drain_reconciliations = [], []
        scope.drain = Mock(return_value=[])
        scope.discover = Mock(return_value=[])
        return scope

    def now(self, expected, *, minimum_ns):
        clocks.elapsed_ns(clocks.Reading(expected, minimum_ns), clocks.Reading(self.clock, self.raw))
        return self.raw

    def stream(self, path, flags, mode):
        if self.before_open is not None:
            self.before_open(path, mode)
        stream = self.open_stream(path, flags, mode)
        self.streams.append(stream)
        self.opens.append((path.name, flags, mode, stream))
        return self.reader_wrap(path, stream) if mode == "rb" and self.reader_wrap is not None else stream

    def capture(self, phase="save"):
        capture = lifecycle.ProviderCapture(clocks.Reading(self.clock, 100 * clocks.NS),
            issued_ns=100 * clocks.NS, hard_end_ns=280 * clocks.NS, local_end=270.0,
            phase=phase, job="1" * 32, invocation="2" * 32, home=str(self.base / "home"), cancelled=lambda: None)
        self.captures.append(capture)
        return capture

    def run_capture(self, capture, command=b""):
        with capture:
            capture.take_directory(self.root)
            capture.prepare()
            for sink, raw in ((capture.stdout, b"MODEL_POSIX_STDOUT"), (capture.stderr, b"MODEL_POSIX_STDERR")):
                # Simulated child writes through the actual owned descriptor.
                self.assertEqual(os.write(sink.fileno(), raw), len(raw))
            if command:
                with Path(capture.command_path).open("ab") as stream:
                    stream.write(command)
            child = processes.PosixProcess(SimpleNamespace(pid=7, stdout=None, stderr=None, poll=lambda: 0))
            self.scope.leaders.append(child)
            self.scope.launches.append({"api": "MODEL_NO_PROCESS", "pid": 7, "created": True})
            capture.wait(child)
        return capture.result

    def assert_failed(self, capture):
        self.assertIsInstance(caught(lambda: capture.result), lifecycle.ProviderLifecycleError)
        self.never_classifier.assert_not_called()

    def test_actual_private_posix_readers_are_no_follow_nonblocking_bounded_and_closed(self):
        capture = self.capture()
        result = self.run_capture(capture)
        self.assertEqual((result.command, result.outputs), (b"", ()))
        self.assertEqual(result.stdout, b"MODEL_POSIX_STDOUT")
        self.assertEqual(result.stderr, b"MODEL_POSIX_STDERR")
        readers = [row for row in self.opens if row[2] == "rb"]
        self.assertEqual([row[0] for row in readers], ["provider-stdout.log", "provider-stderr.log", "provider-output.txt"])
        self.assertTrue(all(row[1] == os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK for row in readers))
        self.assertTrue(all(stream.closed for stream in self.streams))
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o600 for path in self.root.path.iterdir()))
        self.assertEqual(set(result.closed_resources), set(capture._NAMES))
        self.assertEqual(result.provider_acceptance, "NOT_ESTABLISHED")
        self.scope.drain.assert_called_once_with(grace=5.0, kill_wait=5.0, deadline=270.0)

    def test_posix_lookup_retains_exact_lf_bytes_without_inferring_presence(self):
        capture = self.capture("lookup")
        raw = ProviderLifecycleModels.lookup_bytes(self).replace(b"\r\n", b"\n")
        result = self.run_capture(capture, raw)
        self.assertEqual(result.command, raw)
        self.assertEqual(dict(result.outputs)["cache-hit"], "true")
        self.assertEqual(result.original_step_outcome, "NOT_OBSERVED")
        self.never_classifier.assert_not_called()

    def test_failed_posix_provider_retains_actual_tiny_files_without_output_parser(self):
        capture = self.capture("lookup")
        raw = b"MODEL_MALFORMED_FAILURE_COMMAND\n"
        with patch.object(processes.PosixProcess, "poll", return_value=9), patch.object(
                lifecycle.cache, "provider_command_outputs", side_effect=AssertionError("MODEL_NO_FAILURE_PARSER")) as parser:
            error = caught(lambda: self.run_capture(capture, raw))
        self.assertEqual([row[0] for row in self.opens if row[2] == "rb"],
            ["provider-stdout.log", "provider-stderr.log", "provider-output.txt"], "MODEL_FAILURE_LOGS_NOT_RETAINED")
        self.assertRegex(str(error), "PROVIDER_CHILD_FAILED")
        result = capture.failure_capture
        self.assertEqual((result.exit_code, result.command), (9, raw))
        self.assertEqual((result.stdout, result.stderr), (b"MODEL_POSIX_STDOUT", b"MODEL_POSIX_STDERR"))
        self.assertEqual(set(result.closed_resources), set(capture._NAMES))
        self.assertTrue(all(stream.closed for stream in self.streams))
        parser.assert_not_called()
        self.assert_failed(capture)

    def test_failed_posix_read_return_stays_unqualified_after_new_local_expiry(self):
        capture = self.capture()
        def wrap(path, stream):
            def read(maximum):
                raw = stream.read(maximum)
                self.local = 280.0
                return raw
            return SimpleNamespace(fileno=stream.fileno, read=read, close=stream.close)
        self.reader_wrap = wrap
        with patch.object(processes.PosixProcess, "poll", return_value=9):
            error = caught(lambda: self.run_capture(capture))
        self.assertRegex(str(error), "PROVIDER_CHILD_FAILED")
        self.assertEqual(capture._raw_captures, {"stdout": b"MODEL_POSIX_STDOUT"})
        self.assertEqual(capture._verified_captures, set())
        self.assertFalse(capture._slots["stderr-reader"].attempted)
        self.assertIsInstance(caught(lambda: capture.failure_capture), lifecycle.ProviderLifecycleError)
        self.assert_failed(capture)

    def test_darwin_role_uses_same_posix_reader_route_with_modeled_native_scope(self):
        self.clock = clocks.ClockIdentity("macos-arm64", clocks.DARWIN_DOMAIN, clocks.NS)
        self.scope = self.new_scope(processes.DarwinScope)
        capture = self.capture()
        result = self.run_capture(capture)
        self.assertIn(b'"backend":"darwin-libproc-audit-token"', result.native_retirement)
        self.assertEqual(len([row for row in self.opens if row[2] == "rb"]), 3)
        self.assertEqual(result.enclosing_owner_retirement, "NOT_OBSERVED")

    def test_symlink_replacement_is_not_followed_or_retried(self):
        capture = self.capture()
        target = self.base / "model-target"
        target.write_bytes(b"MODEL_NOT_A_PROVIDER_CAPTURE")
        replaced = []
        def substitute(path, mode):
            if mode == "rb" and not replaced:
                replaced.append(path)
                path.unlink()
                path.symlink_to(target)
        self.before_open = substitute
        self.assertIsInstance(caught(lambda: self.run_capture(capture)), OSError)
        self.assertEqual(len(replaced), 1)
        self.assertTrue(capture.unknown)
        self.assertIsNone(capture._slots["stdout-reader"].owner)
        self.assertFalse(capture._slots["directory"].close_attempted)
        self.assert_failed(capture)

    def test_same_content_replacement_fails_original_posix_identity(self):
        capture, replaced = self.capture(), []
        def substitute(path, mode):
            if mode == "rb" and not replaced:
                replaced.append(path)
                raw = path.read_bytes()
                other = path.with_name("replacement.log")
                other.write_bytes(raw)
                other.chmod(0o600)
                other.replace(path)
        self.before_open = substitute
        self.assertRegex(str(caught(lambda: self.run_capture(capture))), "PROVIDER_CAPTURE_REPLACED")
        self.assertTrue(capture._slots["stdout-reader"].closed)
        self.assertTrue(capture._slots["directory"].closed)
        self.assert_failed(capture)

    def test_changed_file_after_read_fails_second_original_stat(self):
        capture = self.capture()
        def wrap(path, stream):
            def read(maximum):
                raw = stream.read(maximum)
                with path.open("ab") as writer:
                    writer.write(b"x")
                return raw
            return SimpleNamespace(fileno=stream.fileno, read=read, close=stream.close)
        self.reader_wrap = wrap
        self.assertRegex(str(caught(lambda: self.run_capture(capture))), "PROVIDER_CAPTURE_CHANGED")
        self.assertTrue(capture._slots["stdout-reader"].closed)
        self.assertTrue(capture._slots["directory"].closed)
        self.assert_failed(capture)

    def test_failed_open_keeps_unknown_and_original_ancestors(self):
        capture, original = self.capture(), FalseyCancellation("MODEL_POSIX_OPEN_CANCEL")
        def refuse(path, mode):
            if mode == "rb":
                raise original
        self.before_open = refuse
        self.assertIs(caught(lambda: self.run_capture(capture)), original)
        self.assertTrue(capture.unknown)
        self.assertTrue(capture._slots["stdout-reader"].attempted)
        self.assertFalse(capture._slots["directory"].close_attempted)
        self.assert_failed(capture)

    def test_read_failure_with_known_reader_close_retains_primary_and_closes_owners(self):
        capture, original = self.capture(), FalseyFailure("MODEL_POSIX_READ_FAILURE")
        def wrap(path, stream):
            return SimpleNamespace(fileno=stream.fileno, read=Mock(side_effect=original), close=stream.close)
        self.reader_wrap = wrap
        self.assertIs(caught(lambda: self.run_capture(capture)), original)
        self.assertTrue(capture._slots["stdout-reader"].closed)
        self.assertTrue(capture._slots["directory"].closed)
        self.assertFalse(capture.unknown)
        self.assert_failed(capture)

    def test_read_failure_plus_ambiguous_close_keeps_first_cause_and_stops_outer_close(self):
        capture, original = self.capture(), FalseyCancellation("MODEL_POSIX_READ_CANCEL")
        cause = original.__cause__ = ValueError("MODEL_ORIGINAL_CAUSE")
        closes = []
        def wrap(path, stream):
            close = Mock(side_effect=FalseyFailure("MODEL_POSIX_CLOSE_FAILURE"))
            closes.append(close)
            return SimpleNamespace(fileno=stream.fileno, read=Mock(side_effect=original), close=close)
        self.reader_wrap = wrap
        self.assertIs(caught(lambda: self.run_capture(capture)), original)
        self.assertIs(original.__cause__, cause)
        self.assertEqual(closes[0].call_count, 1)
        self.assertTrue(capture.unknown)
        self.assertFalse(capture._slots["directory"].close_attempted)
        self.assertFalse(capture._slots["stderr"].close_attempted)
        self.assert_failed(capture)

    def test_reader_close_failure_after_release_is_still_unknown(self):
        capture, original = self.capture(), FalseyFailure("MODEL_AFTER_POSIX_RELEASE")
        def wrap(path, stream):
            def close():
                stream.close()
                raise original
            return SimpleNamespace(fileno=stream.fileno, read=stream.read, close=close)
        self.reader_wrap = wrap
        self.assertIs(caught(lambda: self.run_capture(capture)), original)
        self.assertTrue(capture.unknown)
        self.assertTrue(capture._slots["stderr-reader"].close_attempted)
        self.assertFalse(capture._slots["stdout-reader"].close_attempted)
        self.assertFalse(capture._slots["directory"].close_attempted)
        self.assert_failed(capture)

    def test_late_posix_read_does_not_proceed_to_another_capture(self):
        capture = self.capture()
        def wrap(path, stream):
            def read(maximum):
                raw = stream.read(maximum)
                self.raw = 280 * clocks.NS
                return raw
            return SimpleNamespace(fileno=stream.fileno, read=read, close=stream.close)
        self.reader_wrap = wrap
        self.assertRegex(str(caught(lambda: self.run_capture(capture))), "PROVIDER_RAW_EXPIRED")
        self.assertFalse(capture._slots["stderr-reader"].attempted)
        self.assert_failed(capture)

    def test_separate_posix_directory_close_is_inside_original_final_fence(self):
        capture, close = self.capture(), self.root.close
        def late():
            close()
            self.local = 280.0
        with patch.object(self.root, "close", side_effect=late):
            self.assertRegex(str(caught(lambda: self.run_capture(capture))), "PROVIDER_LOCAL_EXPIRED")
        self.assertTrue(capture._slots["directory"].closed)
        self.assertTrue(all(stream.closed for stream in self.streams))
        self.assert_failed(capture)

    def test_non_native_command_newlines_fail_after_close_without_classifying_provider(self):
        capture = self.capture("lookup")
        raw = ProviderLifecycleModels.lookup_bytes(self)
        self.assertIsInstance(caught(lambda: self.run_capture(capture, raw)), lifecycle.cache.files.SeedError)
        self.assertTrue(all(slot.closed for slot in capture._slots.values() if slot.owner is not None))
        self.assert_failed(capture)


if __name__ == "__main__":
    unittest.main()
