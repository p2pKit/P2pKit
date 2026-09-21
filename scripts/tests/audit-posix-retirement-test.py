#!/usr/bin/env python3
"""Offline POSIX lifetime models: no real pidfds, processes, signals or /proc reads."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_processes as P
import hosted_windows_evidence as evidence


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class FalseyCancellation(KeyboardInterrupt):
    def __bool__(self):
        return False


class PosixRetirementModels(unittest.TestCase):
    def setUp(self):
        # Replace the module's syscall supplier, not the interpreter's os module.
        self.os = SimpleNamespace(pidfd_open=Mock(return_value=71), close=Mock(),
                                  getpid=lambda: 1, getuid=lambda: 1000)
        self.signal = SimpleNamespace(pidfd_send_signal=Mock())
        self.addCleanup(patch.stopall)
        patch.object(P, "os", self.os).start()
        patch.object(P, "signal", self.signal).start()
        self.identity = {"pid": 7, "startTicks": 11, "uid": 1000, "live": True}

    def scope(self):
        # Run the maintained initialization, with admission/census explicitly modeled.
        with patch.object(P.LinuxScope, "_admit"), patch.object(P.LinuxScope, "_pids", return_value=[]):
            scope = P.LinuxScope("MODEL_JOB", "MODEL_INVOCATION", "/model/state", "/model/home")
        scope._identity = Mock(side_effect=lambda _pid: dict(self.identity))
        return scope

    def caught(self, call):
        try:
            call()
        except BaseException as error:
            return error
        self.fail("MODELED_OPERATION_UNEXPECTEDLY_SUCCEEDED")

    def unknown(self, error):
        details = P.retirement_details(error)
        self.assertEqual(details.get("status"), "UNKNOWN")
        self.assertTrue(details["resources"])
        self.assertTrue(all(set(row) == {"phase", "resource", "status", "error"} and
                            row["status"] == "UNKNOWN" and row["phase"].startswith("posix-")
                            for row in details["resources"]))
        self.assertIn("POSIX resource retirement UNKNOWN", P.format_ownership_error(error))
        json.dumps(details)
        return details

    def test_exact_lifetime_transfers_without_premature_close(self):
        scope = self.scope()
        self.assertEqual(scope._acquire(self.identity), 71)
        self.os.pidfd_open.assert_called_once_with(7, 0)
        scope._identity.assert_called_once_with(7)
        self.os.close.assert_not_called()
        self.assertEqual(scope.handles, {})  # Transfer goes to the caller, not a fabricated registration.

    def test_allocation_failure_does_not_reinspect_or_close_an_unowned_number(self):
        scope = self.scope()
        original = OSError("MODEL_OPEN_FAILURE")
        self.os.pidfd_open.side_effect = original
        self.assertIs(self.caught(lambda: scope._acquire(self.identity)), original)
        scope._identity.assert_not_called()
        self.os.close.assert_not_called()

    def test_missing_nonrunning_and_replaced_lifetimes_retire_once(self):
        for current in (None, {**self.identity, "live": False}, {**self.identity, "startTicks": 12}):
            with self.subTest(current=current):
                scope = self.scope()
                scope._identity = Mock(return_value=current)
                self.os.close.reset_mock()
                error = self.caught(lambda: scope._acquire(self.identity))
                self.assertIsInstance(error, ProcessLookupError)
                self.assertEqual(P.retirement_details(error), {})
                self.os.close.assert_called_once_with(71)
                scope.close()
                self.os.close.assert_called_once_with(71)

    def test_postallocation_identity_failures_and_cancellation_preserve_original(self):
        for original in (OSError("MODEL_IDENTITY_FAILURE"), ValueError("MODEL_MALFORMED_STAT"),
                         FalseyFailure("MODEL_FALSEY_FAILURE"), FalseyCancellation("MODEL_CANCEL")):
            with self.subTest(kind=type(original).__name__):
                scope = self.scope()
                scope._identity.side_effect = original
                self.os.close.reset_mock()
                self.assertIs(self.caught(lambda: scope._acquire(self.identity)), original)
                self.os.close.assert_called_once_with(71)

    def test_both_fallible_key_checks_retire_the_provisional_descriptor(self):
        for position in (0, 1):
            with self.subTest(position=position):
                scope = self.scope()
                original = KeyError("MODEL_LIFETIME_KEY_FAILURE")
                scope._key = Mock(side_effect=[original] if position == 0 else [(7, 11), original])
                self.os.close.reset_mock()
                self.assertIs(self.caught(lambda: scope._acquire(self.identity)), original)
                self.os.close.assert_called_once_with(71)

    def test_provisional_close_failure_before_or_after_release_is_unknown_without_retry(self):
        for released in (False, True):
            with self.subTest(released=released):
                scope = self.scope()
                original = FalseyCancellation("MODEL_IDENTITY_CANCEL")
                original.__cause__ = ValueError("MODEL_EXISTING_CAUSE")
                cause, args = original.__cause__, original.args
                scope._identity.side_effect = original
                physical = []

                def close(_handle):
                    if released:
                        physical.append("MODEL_PHYSICAL_RELEASE")
                    raise OSError("MODEL_AMBIGUOUS_CLOSE")

                self.os.close = Mock(side_effect=close)
                self.assertIs(self.caught(lambda: scope._acquire(self.identity)), original)
                self.unknown(original)
                self.assertIs(original.__cause__, cause)
                self.assertEqual(original.args, args)
                self.assertEqual(physical, ["MODEL_PHYSICAL_RELEASE"] if released else [])
                self.assertIs(self.caught(scope.close), original)
                self.assertIs(self.caught(scope.close), original)
                self.os.close.assert_called_once_with(71)

    def test_changed_lifetime_with_uncertain_close_does_not_become_disappearance(self):
        scope = self.scope()
        scope._pids = Mock(return_value=[7])
        scope._identity.side_effect = [dict(self.identity), None]
        scope._inspect_environment, scope._ours = Mock(return_value={}), Mock(return_value=True)
        scope._discovery_resolved = Mock()
        self.os.close.side_effect = OSError("MODEL_CLOSE_UNKNOWN")
        error = self.caught(scope.discover)
        self.assertIsInstance(error, ProcessLookupError)
        self.unknown(error)
        scope._discovery_resolved.assert_not_called()
        self.assertEqual(scope.known, {})
        self.assertEqual(scope.handles, {})
        self.os.close.assert_called_once_with(71)

    def test_real_discovery_drain_composition_cannot_swallow_unknown_process_lookup(self):
        scope = self.scope()
        original = ProcessLookupError("MODEL_IDENTITY_LOOKUP")
        scope._pids = Mock(side_effect=[[7], [], [], []])
        scope._identity.side_effect = [dict(self.identity), original]
        scope._inspect_environment, scope._ours = Mock(return_value={}), Mock(return_value=True)
        self.os.close.side_effect = OSError("MODEL_CLOSE_UNKNOWN")
        clock = SimpleNamespace(now=100.0)

        def sleep(duration):
            clock.now += duration

        with patch.object(P, "time", SimpleNamespace(monotonic=lambda: clock.now, sleep=sleep)):
            self.assertIs(self.caught(lambda: scope.drain(0.5, 0.5, deadline=101.0)), original)
        self.unknown(original)
        self.os.close.assert_called_once_with(71)
        self.signal.pidfd_send_signal.assert_not_called()
        self.assertEqual(scope._pids.call_count, 1)

    def test_disappearance_with_known_close_still_allows_three_quiet_censuses(self):
        scope = self.scope()
        scope._pids = Mock(side_effect=[[7], [], []])
        scope._identity.side_effect = [dict(self.identity), None]
        scope._inspect_environment, scope._ours = Mock(return_value={}), Mock(return_value=True)
        clock = SimpleNamespace(now=100.0)
        with patch.object(P, "time", SimpleNamespace(monotonic=lambda: clock.now,
                          sleep=lambda duration: setattr(clock, "now", clock.now + duration))):
            self.assertEqual(scope.drain(0.5, 0.5, deadline=101.0), [])
        self.assertEqual(scope._pids.call_count, 3)
        self.os.close.assert_called_once_with(71)
        self.signal.pidfd_send_signal.assert_not_called()

    def test_successful_admission_probe_releases_its_unreturned_descriptor(self):
        scope = self.scope()
        scope._admit()
        self.signal.pidfd_send_signal.assert_called_once_with(71, 0)
        self.os.close.assert_called_once_with(71)
        self.assertEqual(scope.handles, {})

    def test_probe_failure_with_known_close_preserves_exact_primary(self):
        for original in (OSError("MODEL_PROBE_ERROR"), FalseyCancellation("MODEL_PROBE_CANCEL")):
            with self.subTest(kind=type(original).__name__):
                scope = self.scope()
                self.signal.pidfd_send_signal.side_effect = original
                self.os.close.reset_mock()
                self.assertIs(self.caught(scope._admit), original)
                self.assertEqual(P.retirement_details(original), {})
                self.os.close.assert_called_once_with(71)

    def test_failed_constructor_retains_original_probe_and_unknown_close(self):
        for original in (OSError("MODEL_PROBE_ERROR"), FalseyCancellation("MODEL_PROBE_CANCEL")):
            with self.subTest(kind=type(original).__name__):
                self.signal.pidfd_send_signal.side_effect = original
                self.os.close = Mock(side_effect=OSError("MODEL_CLOSE_AFTER_PROBE"))
                original.__cause__ = ValueError("MODEL_EXISTING_CAUSE")
                cause, args = original.__cause__, original.args
                with patch.object(P.LinuxScope, "_identity", return_value=dict(self.identity)), \
                     patch.object(P.LinuxScope, "_pids", side_effect=AssertionError("MODEL_BASELINE_MUST_NOT_RUN")):
                    self.assertIs(self.caught(lambda: P.LinuxScope("MODEL_JOB", "MODEL_ID", "/state", "/home")),
                                  original)
                self.unknown(original)
                self.assertIs(original.__cause__, cause)
                self.assertEqual(original.args, args)
                self.os.close.assert_called_once_with(71)

    def test_successful_probe_with_failed_close_is_not_admission(self):
        scope = self.scope()
        original = FalseyFailure("MODEL_PROBE_CLOSE_FAILURE")
        self.os.close.side_effect = original
        self.assertIs(self.caught(scope._admit), original)
        self.unknown(original)
        self.assertIs(self.caught(scope.close), original)
        self.os.close.assert_called_once_with(71)

    def populate(self, scope, *, failed_index=None, original=None):
        events = []
        scope.handles = {(7, 11): 0, (8, 12): 71, (9, 13): 72}

        def release(label):
            events.append(label)
            if len(events) - 1 == failed_index:
                raise original

        scope._release = lambda handle: release(("handle", handle))
        scope.leaders = [SimpleNamespace(close=lambda: release(("leader", 1))),
                         SimpleNamespace(close=lambda: release(("leader", 2)))]
        return events

    def test_successful_scope_close_is_once_only_including_descriptor_zero(self):
        scope = self.scope()
        events = self.populate(scope)
        scope.close()
        self.assertEqual(events, [("handle", 0), ("handle", 71), ("handle", 72), ("leader", 1), ("leader", 2)])
        self.assertEqual(scope.handles, {})
        self.assertEqual(scope.leaders, [])
        scope.close()
        self.assertEqual(len(events), 5)

    def test_every_known_close_is_attempted_after_first_middle_or_last_failure(self):
        for position in range(5):
            for kind in (OSError, FalseyFailure, FalseyCancellation):
                with self.subTest(position=position, kind=kind.__name__):
                    scope = self.scope()
                    original = kind("MODEL_SCOPE_RELEASE_FAILURE")
                    events = self.populate(scope, failed_index=position, original=original)
                    self.assertIs(self.caught(scope.close), original)
                    self.assertEqual(len(events), 5)
                    self.assertEqual(len(self.unknown(original)["resources"]), 1)
                    self.assertEqual(scope.handles, {})
                    self.assertEqual(scope.leaders, [])
                    self.assertIs(self.caught(scope.close), original)
                    self.assertEqual(len(events), 5)

    def test_multiple_close_failures_keep_first_falsey_failure_and_all_diagnostics(self):
        scope = self.scope()
        first, second = FalseyFailure("MODEL_FIRST"), FalseyCancellation("MODEL_LATER_CANCEL")
        scope.handles = {(7, 11): 71, (8, 12): 72}
        scope._release = Mock(side_effect=[first, second])
        leader = Mock()
        scope.leaders = [SimpleNamespace(close=leader)]
        self.assertIs(self.caught(scope.close), first)
        self.assertEqual(len(self.unknown(first)["resources"]), 2)
        leader.assert_called_once_with()
        self.assertIs(self.caught(scope.close), first)
        self.assertEqual(scope._release.call_count, 2)
        leader.assert_called_once_with()

    def test_closed_or_unknown_scope_refuses_operational_reuse_before_syscalls(self):
        for unknown in (False, True):
            with self.subTest(unknown=unknown):
                scope = self.scope()
                if unknown:
                    scope.handles = {(7, 11): 71}
                    scope._release = Mock(side_effect=FalseyFailure("MODEL_SCOPE_UNKNOWN"))
                    failure = self.caught(scope.close)
                else:
                    failure = None
                    scope.close()
                scope._pids = Mock(side_effect=AssertionError("MODEL_NO_CENSUS_AFTER_CLOSE"))
                scope._identity.reset_mock()
                self.os.pidfd_open.reset_mock()
                self.signal.pidfd_send_signal.reset_mock()
                for call in (scope.discover, lambda: scope.spawn(["/model/tool"], "/model", {}),
                             lambda: scope.signal_all(15), lambda: scope.drain(0, 0, deadline=101),
                             lambda: scope._acquire(self.identity), lambda: scope._send(self.identity, 71, 15)):
                    error = self.caught(call)
                    self.assertTrue(error is failure if unknown else isinstance(error, P.OwnershipError))
                self.assertEqual(scope.launches, [])
                scope._pids.assert_not_called()
                scope._identity.assert_not_called()
                self.os.pidfd_open.assert_not_called()
                self.signal.pidfd_send_signal.assert_not_called()

    def test_default_windows_retirement_carrier_bytes_are_unchanged(self):
        original = OSError("MODEL_WINDOWS_CLOSE")
        outcomes, failures = P._retire_actions([("handle", Mock(side_effect=original))], "scope-close")
        self.assertEqual(outcomes, [{"phase": "scope-close", "resource": "handle", "status": "UNKNOWN",
                                     "error": "OSError: MODEL_WINDOWS_CLOSE"}])
        P._finish_retirement(failures, original)
        self.assertIn("Windows resource retirement UNKNOWN (scope-close/handle): OSError: MODEL_WINDOWS_CLOSE",
                      P.format_ownership_error(original))
        self.assertEqual(P.retirement_details(original)["resources"], outcomes)

    def test_closed_darwin_overrides_refuse_before_drain_records_or_native_work(self):
        for failure in (None, FalseyFailure("MODEL_DARWIN_CLOSE_UNKNOWN")):
            with self.subTest(failed=failure is not None):
                scope = P.DarwinScope.__new__(P.DarwinScope)
                scope._closed, scope._retirement_error = True, failure
                # No native libraries, token supplier or active-drain fields exist.
                for call in (lambda: scope.signal_all(15), lambda: scope.drain(0, 0, deadline=101)):
                    error = self.caught(call)
                    self.assertTrue(error is failure if failure is not None else isinstance(error, P.OwnershipError))

    def test_reentrant_close_during_identity_check_cannot_transfer_the_raw_pidfd(self):
        scope = self.scope()

        def identity(_pid):
            scope.close()
            return dict(self.identity)

        scope._identity.side_effect = identity
        self.assertIsInstance(self.caught(lambda: scope._acquire(self.identity)), P.OwnershipError)
        self.os.close.assert_called_once_with(71)

    def test_actual_private_evidence_reader_retains_the_complete_posix_retirement_row(self):
        scope = self.scope()
        original = FalseyFailure("MODEL_PIDFD_CLOSE_UNKNOWN")
        scope.handles, scope._release = {(7, 11): 71}, Mock(side_effect=original)
        self.assertIs(self.caught(scope.close), original)
        detail = evidence._exception_detail(original)
        self.assertTrue(detail["retirementUnknown"])
        self.assertFalse(detail["incomplete"])
        self.assertEqual(detail["nodes"][0]["retirement"], P.retirement_details(original)["resources"])

    def test_private_evidence_reader_still_rejects_an_extra_carrier_member(self):
        original = OSError("MODEL_UNSUPPORTED_CARRIER")
        original._p2pkit_retirement = {"status": "UNKNOWN", "omitted": 0, "resources": [
            {"phase": "posix-scope-close", "resource": "handle:0", "status": "UNKNOWN",
             "error": "MODEL_CLOSE_FAILURE", "backend": "POSIX"}]}
        detail = evidence._exception_detail(original)
        self.assertTrue(detail["retirementUnknown"])
        self.assertTrue(detail["incomplete"])
        self.assertEqual(detail["nodes"][0]["retirement"], [{"error": "<uninspectable resource>"}])


class DarwinTokenRetirementModels(unittest.TestCase):
    """Opaque-token/Mach-call models, never a Darwin/native execution."""

    caught = PosixRetirementModels.caught
    unknown = PosixRetirementModels.unknown

    def setUp(self):
        self.addCleanup(patch.stopall)
        self.clock = SimpleNamespace(value=100.0)
        self.sleep = Mock(side_effect=lambda duration: setattr(self.clock, "value", self.clock.value + duration))
        self.monotonic = Mock(side_effect=lambda: self.clock.value)
        patch.object(P, "time", SimpleNamespace(monotonic=self.monotonic, sleep=self.sleep)).start()
        patch.object(P, "os", SimpleNamespace(getpid=lambda: 1, getuid=lambda: 1000)).start()
        self.identity = {"pid": 7, "uid": 1000, "live": True, "uniqueId": 11,
                         "startSeconds": 12, "startMicroseconds": 13, "pidVersion": 14}

    def scope(self):
        with patch.object(P.DarwinScope, "_admit"), patch.object(P.DarwinScope, "_pids", return_value=[]):
            scope = P.DarwinScope("MODEL_JOB", "MODEL_INVOCATION", "/model/state", "/model/home")
        scope.observation_reconciliations, scope.drain_reconciliations, scope.active_drain = [], [], None
        scope.self_port = 3

        def task_name(_self, _pid, port):
            port._obj.value = 71  # Synthetic port number; token contents remain opaque.
            return 0

        scope.system = SimpleNamespace(task_name_for_pid=Mock(side_effect=task_name),
            task_info=Mock(return_value=0), mach_port_deallocate=Mock(return_value=0))
        scope.proc = SimpleNamespace(proc_signal_with_audittoken=Mock(return_value=0))
        scope._identity = Mock(side_effect=lambda _pid, **_kw: dict(self.identity))
        scope._pids = Mock(return_value=[7])
        return scope

    def fail_unknown(self, scope, original):
        # Explicit fault injection through the actual carrier producer, not a
        # fabricated successful syscall or native-retirement observation.
        scope._retire_resources([("MODEL_RESOURCE", Mock(side_effect=OSError("MODEL_CLOSE_UNKNOWN")))],
                                "model-route", original=original)
        raise original

    def test_success_keeps_opaque_token_and_exact_native_call_order(self):
        scope = self.scope()
        events = []

        def name(task, pid, output):
            events.append(("name", task, pid))
            output._obj.value = 71
            return 0

        def info(port, flavor, token, count):
            self.assertIs(type(token._obj), P.AuditToken)
            events.append(("info", port.value, flavor, count._obj.value))
            return 0

        scope.system.task_name_for_pid.side_effect = name
        scope.system.task_info.side_effect = info
        scope.system.mach_port_deallocate.side_effect = lambda task, port: events.append(("close", task, port.value)) or 0
        self.assertIs(type(scope._acquire_once(self.identity)), P.AuditToken)
        self.assertEqual(events, [("name", 3, 7), ("info", 71, 15, 8), ("close", 3, 71)])
        scope.close()
        self.assertEqual(scope.system.mach_port_deallocate.call_count, 1)

    def test_zero_port_failure_never_deallocates_an_unowned_right(self):
        scope = self.scope()
        scope.system.task_name_for_pid.side_effect = lambda *_args: 5
        error = self.caught(lambda: scope._acquire_once(self.identity))
        self.assertIsInstance(error, P.DarwinObservationError)
        self.assertEqual(P.retirement_details(error), {})
        scope.system.task_info.assert_not_called()
        scope.system.mach_port_deallocate.assert_not_called()

    def test_partial_task_name_allocation_preserves_falsey_cancellation(self):
        scope = self.scope()
        original = FalseyCancellation("MODEL_TASK_NAME_CANCEL")
        original.__cause__ = ValueError("MODEL_PRIOR_CAUSE")
        cause, args = original.__cause__, original.args

        def name(_task, _pid, output):
            output._obj.value = 71
            raise original

        scope.system.task_name_for_pid.side_effect = name
        scope.system.mach_port_deallocate.side_effect = OSError("MODEL_RELEASE_AMBIGUOUS")
        self.assertIs(self.caught(lambda: scope._acquire_once(self.identity)), original)
        self.assertIs(original.__cause__, cause)
        self.assertEqual(original.args, args)
        self.unknown(original)
        scope.system.task_info.assert_not_called()
        self.assertIs(self.caught(scope.close), original)
        scope.system.mach_port_deallocate.assert_called_once()

    def test_failed_task_info_or_size_with_known_close_still_recovers(self):
        for failure in ("result", "size"):
            with self.subTest(failure=failure):
                scope = self.scope()

                def info(_port, _flavor, _token, count):
                    if scope.system.task_info.call_count == 1:
                        if failure == "result":
                            return 5
                        count._obj.value = 7
                    return 0

                scope.system.task_info.side_effect = info
                self.assertIs(type(scope._acquire(self.identity)), P.AuditToken)
                self.assertEqual(scope.system.mach_port_deallocate.call_count, 2)
                self.assertEqual(scope.observation_reconciliations[-1]["outcome"], "recovered")
                self.assertEqual(scope.observation_reconciliations[-1]["attempts"], 2)

    def test_ambiguous_deallocation_preserves_primary_and_never_retries(self):
        for released in (False, True):
            with self.subTest(released=released):
                scope = self.scope()
                original = P.DarwinObservationError("MODEL_TASK_INFO_FAILURE")
                scope.system.task_info.side_effect = original
                physical = []

                def deallocate(*_args):
                    if released:
                        physical.append("MODEL_RIGHT_RELEASED")
                    raise FalseyFailure("MODEL_RELEASE_UNKNOWN")

                scope.system.mach_port_deallocate.side_effect = deallocate
                self.assertIs(self.caught(lambda: scope._acquire(self.identity)), original)
                self.unknown(original)
                self.assertEqual(physical, ["MODEL_RIGHT_RELEASED"] if released else [])
                self.assertIs(self.caught(lambda: scope._acquire(self.identity)), original)
                self.assertIs(self.caught(scope.close), original)
                scope.system.task_name_for_pid.assert_called_once()
                scope.system.mach_port_deallocate.assert_called_once()
                self.sleep.assert_not_called()

    def test_nonzero_deallocation_result_cannot_release_a_successful_token(self):
        scope = self.scope()
        scope.system.mach_port_deallocate.return_value = 5
        error = self.caught(lambda: scope._send(self.identity, None, 15))
        self.assertIsInstance(error, P.OwnershipError)
        self.unknown(error)
        self.assertIs(self.caught(lambda: scope._acquire_once(self.identity)), error)
        scope.system.mach_port_deallocate.assert_called_once()
        scope.proc.proc_signal_with_audittoken.assert_not_called()

    def test_incoming_unknown_refuses_before_stringification_or_clock(self):
        class Unprintable(P.DarwinObservationError):
            def __str__(self):
                raise AssertionError("MODEL_UNKNOWN_MUST_NOT_BE_STRINGIFIED")

        scope = self.scope()
        original = Unprintable()
        row = {"phase": "posix-model-route", "resource": "MODEL_RESOURCE", "status": "UNKNOWN", "error": "MODEL_CLOSE"}
        P._finish_retirement([(row, OSError("MODEL_CLOSE"))], original)
        action = Mock()
        self.assertIs(self.caught(lambda: scope._observe(self.identity, "MODEL", action, initial_error=original)), original)
        self.monotonic.assert_not_called()
        action.assert_not_called()
        self.assertIs(self.caught(scope.close), original)

    def test_first_pass_success_still_needs_no_observation_record(self):
        scope = self.scope()
        scope.observation_reconciliations = [{} for _ in range(1024)]
        token = P.AuditToken()
        self.assertIs(scope._observe(self.identity, "MODEL", lambda _identity: token), token)
        self.assertEqual(len(scope.observation_reconciliations), 1024)

    def test_record_append_failure_preserves_primary_cancellation_before_or_after_append(self):
        for appended in (False, True):
            with self.subTest(appended=appended):
                scope = self.scope()
                original, secondary = FalseyCancellation("MODEL_ACTION_CANCEL"), OSError("MODEL_RECORD_UNKNOWN")
                original.__cause__ = ValueError("MODEL_PRIOR_CAUSE")
                cause, args = original.__cause__, original.args

                class Records(list):
                    calls = 0
                    def append(self, row):
                        self.calls += 1
                        if appended:
                            super().append(row)
                        raise secondary

                records = scope.observation_reconciliations = Records()
                action = Mock(side_effect=[P.DarwinObservationError("MODEL_TRANSIENT"), original])
                self.assertIs(self.caught(lambda: scope._observe(self.identity, "MODEL", action)), original)
                details = self.unknown(original)
                self.assertEqual(details["resources"][0]["phase"], "posix-darwin-observation-record")
                self.assertIs(original.__cause__, cause)
                self.assertEqual(original.args, args)
                self.assertEqual((records.calls, len(records), action.call_count), (1, int(appended), 2))
                self.assertIs(self.caught(lambda: scope._observe(self.identity, "MODEL", action)), original)
                self.assertEqual(records.calls, 1)

    def test_record_failure_after_recovery_is_fatal_without_fabricated_return(self):
        scope = self.scope()
        original = FalseyFailure("MODEL_RECORD_FAILURE")

        class Records(list):
            def append(self, _row):
                raise original

        scope.observation_reconciliations = Records()
        action = Mock(side_effect=[P.DarwinObservationError("MODEL_TRANSIENT"), P.AuditToken()])
        self.assertIs(self.caught(lambda: scope._observe(self.identity, "MODEL", action)), original)
        self.unknown(original)
        self.assertIs(self.caught(scope.close), original)

    def test_record_cap_preserves_exhaustion_and_is_not_a_new_retry_allowance(self):
        scope = self.scope()
        scope.observation_reconciliations = [{} for _ in range(1024)]
        action = Mock(side_effect=P.DarwinObservationError("MODEL_ACCESS_DENIED"))
        error = self.caught(lambda: scope._observe(self.identity, "MODEL", action))
        self.assertIsInstance(error, P.DarwinObservationExhausted)
        self.unknown(error)
        self.assertEqual(len(scope.observation_reconciliations), 1024)
        self.assertLessEqual(action.call_count, 26)
        self.assertLessEqual(self.clock.value, 100.25)
        self.assertIs(self.caught(scope.close), error)

    def test_discovery_cannot_swallow_any_supported_unknown_environment_error(self):
        for kind in (PermissionError, P.OwnershipError, P.DarwinObservationExhausted, ProcessLookupError):
            with self.subTest(kind=kind.__name__):
                scope, original = self.scope(), kind("MODEL_ENVIRONMENT_PRIMARY")
                scope._inspect_environment = Mock(side_effect=lambda _identity: self.fail_unknown(scope, original))
                self.assertIs(self.caught(scope.discover), original)
                self.assertEqual(scope.discovery_errors, set())
                self.assertEqual(scope.pending_discoveries, {})
                scope.system.task_name_for_pid.assert_not_called()

    def test_identity_reconciliation_cannot_convert_unknown_to_absence(self):
        scope, original = self.scope(), ProcessLookupError("MODEL_IDENTITY_PRIMARY")
        scope._observe = Mock(side_effect=lambda *_a, **_kw: self.fail_unknown(scope, original))
        self.assertIs(self.caught(lambda: scope._reconcile_identity(self.identity, P.DarwinObservationError())), original)

    def test_active_signal_drain_cannot_defer_unknown_or_reconcile_it_to_exit(self):
        for kind in (ProcessLookupError, P.DarwinObservationExhausted):
            with self.subTest(kind=kind.__name__):
                scope, original = self.scope(), kind("MODEL_SIGNAL_PRIMARY")
                scope.discover = Mock(return_value=[dict(self.identity)])
                scope.handles = {scope._key(self.identity): P.AuditToken()}
                scope.active_drain = {"deadline": 101.0, "pending": {}, "record": {"signalReconciliations": []}}
                scope._reconcile_drain_signals = Mock()
                scope._send = Mock(side_effect=lambda *_a, **_kw: self.fail_unknown(scope, original))
                self.assertIs(self.caught(lambda: scope.signal_all(15, deadline=101.0)), original)
                scope._reconcile_drain_signals.assert_called_once()
                self.assertEqual(scope.active_drain["pending"], {})
                self.assertEqual(scope.active_drain["record"]["signalReconciliations"], [])

    def test_neither_drain_implementation_can_escalate_an_unknown_deadline_error(self):
        for darwin in (False, True):
            with self.subTest(darwin=darwin):
                scope, original = self.scope(), P.DrainDeadlineExceeded("MODEL_DEADLINE_PRIMARY")
                scope.discover = Mock(side_effect=lambda: self.fail_unknown(scope, original))
                call = (lambda: scope.drain(0.1, 0.1, deadline=100.2)) if darwin else (
                    lambda: P._bounded_drain(scope, 0.1, 0.1, 100.2, quiet_required=3))
                self.assertIs(self.caught(call), original)
                scope.discover.assert_called_once()
                if darwin:
                    self.assertEqual(scope.drain_reconciliations[-1]["outcome"], "failed")
                    self.assertEqual(len(scope.drain_reconciliations[-1]["phases"]), 1)
                    self.assertIsNone(scope.active_drain)

    def test_closed_token_helpers_refuse_before_new_clock_or_native_work(self):
        scope = self.scope()
        scope.close()
        for call in (lambda: scope._acquire(self.identity), lambda: scope._acquire_once(self.identity),
                     lambda: scope._observe(self.identity, "MODEL", Mock())):
            self.assertIsInstance(self.caught(call), P.OwnershipError)
        self.monotonic.assert_not_called()
        scope._identity.assert_not_called()
        scope.system.task_name_for_pid.assert_not_called()

    def test_drain_record_cannot_mask_unprintable_unknown_primary(self):
        class Unprintable(P.DarwinObservationExhausted):
            def __str__(self):
                raise AssertionError("MODEL_UNKNOWN_STRING_UNAVAILABLE")

        scope, original = self.scope(), Unprintable()
        scope.discover = Mock(side_effect=lambda: self.fail_unknown(scope, original))
        self.assertIs(self.caught(lambda: scope.drain(0.1, 0.1, deadline=100.2)), original)
        self.assertEqual(scope.drain_reconciliations[-1]["outcome"], "failed")
        self.assertIn("<exception message unavailable>", scope.drain_reconciliations[-1]["error"])
        self.assertIsNone(scope.active_drain)


if __name__ == "__main__":
    unittest.main()
