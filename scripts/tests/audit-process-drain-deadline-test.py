#!/usr/bin/env python3
"""Pure fake-clock/native-call models; no process creation or native qualification."""
from __future__ import annotations

import copy
import errno
from pathlib import Path
import sys
from types import MethodType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_processes as processes


class Clock:
    def __init__(self):
        self.value, self.calls, self.sleeps = 100.0, 0, []
        self.on_now = lambda: None

    def now(self):
        self.calls += 1
        if self.calls > 10000:
            raise AssertionError("Modeled drain exceeded its call bound")
        self.on_now()
        return self.value

    def sleep(self, seconds):
        if not 0 < seconds <= 0.1:
            raise AssertionError("Drain sleep was not capped")
        self.sleeps.append((self.value, seconds))
        self.value += seconds


class DrainDeadlineModels(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.addCleanup(patch.stopall)
        patch.object(processes, "time", SimpleNamespace(monotonic=self.clock.now, sleep=self.clock.sleep)).start()
        self.native_send = patch.object(processes.signal, "pidfd_send_signal", create=True).start()
        self.identity = {"pid": 7, "uid": 1000, "realUid": 1000, "uniqueId": 8,
                         "startSeconds": 9, "startMicroseconds": 10, "pidVersion": 11,
                         "live": True}

    def scope(self, kind):
        cls = {"posix": processes.PosixScope, "darwin": processes.DarwinScope,
               "windows": processes.WindowsScope}[kind]
        scope = cls.__new__(cls)  # Never load a native backend or enumerate real processes.
        scope.discovery_errors, scope.pending_discoveries = set(), {}
        scope.discovery_reconciliations, scope.leaders, scope.launches = [], [], []
        scope.discover = Mock(return_value=[])
        scope.known, scope.handles = {}, {}
        if kind == "windows":
            scope.job = object()
            scope.api = SimpleNamespace(TerminateJobObject=Mock(return_value=1),
                GenerateConsoleCtrlEvent=Mock(return_value=1), check=lambda value, _label: value)
        else:
            if kind == "posix":
                scope._key = lambda row: (row["pid"], row["uniqueId"])
                scope._send = MethodType(processes.LinuxScope._send, scope)
            else:
                scope.active_drain, scope.drain_reconciliations = None, []
                scope.observation_reconciliations = []
                scope._identity = Mock(side_effect=lambda _pid, **_kwargs: dict(self.identity))
                scope._acquire = Mock(return_value=processes.AuditToken())
                scope.proc = SimpleNamespace(proc_signal_with_audittoken=Mock(return_value=0))
            key = scope._key(self.identity)
            scope.known[key], scope.handles[key] = dict(self.identity), 99
        return scope

    def reset_clock(self):
        self.clock.value, self.clock.calls = 100.0, 0
        self.clock.sleeps.clear()
        self.clock.on_now = lambda: None
        self.native_send.reset_mock(side_effect=True)

    def test_invalid_explicit_inputs_refuse_before_discovery_signals_or_drain_records(self):
        cases = [(value, 1, 110) for value in (-1, True, None, "1", float("nan"), float("inf"), 10 ** 1000)]
        cases += [(1, value, 110) for value in (-1, False, None, float("nan"), float("inf"))]
        cases += [(1, 1, value) for value in (True, "110", float("nan"), float("inf"), 100, 99, 10 ** 1000)]
        for kind in ("posix", "darwin", "windows"):
            for grace, kill_wait, end in cases:
                with self.subTest(kind=kind, grace=str(grace)[:20], kill_wait=kill_wait, end=str(end)[:20]):
                    scope = self.scope(kind)
                    with self.assertRaises(processes.OwnershipError):
                        scope.drain(grace=grace, kill_wait=kill_wait, deadline=end)
                    scope.discover.assert_not_called()
                    if kind == "darwin":
                        self.assertEqual(scope.drain_reconciliations, [])
                    if kind == "windows":
                        scope.api.TerminateJobObject.assert_not_called()
                    self.native_send.assert_not_called()

    def test_deadline_is_keyword_only(self):
        for kind in ("posix", "darwin", "windows"):
            with self.subTest(kind=kind), self.assertRaises(TypeError):
                self.scope(kind).drain(1, 1, 110)

    def test_zero_phases_do_no_native_work_and_cannot_establish_retirement(self):
        for kind in ("posix", "darwin", "windows"):
            scope = self.scope(kind)
            with self.subTest(kind=kind), self.assertRaises(processes.OwnershipError):
                scope.drain(grace=0, kill_wait=0, deadline=110)
            scope.discover.assert_not_called()
        self.assertEqual(self.clock.sleeps, [])

    def test_existing_no_keyword_quiet_census_contracts_remain_unchanged(self):
        for kind, count in (("posix", 4), ("darwin", 3), ("windows", 2)):
            self.reset_clock()
            scope = self.scope(kind)
            with self.subTest(kind=kind):
                self.assertEqual(scope.drain(), [])
                self.assertEqual(scope.discover.call_count, count)
                if kind == "darwin":
                    record = scope.drain_reconciliations[-1]
                    self.assertEqual(record["outcome"], "retired")
                    self.assertNotIn("absoluteDeadlineMonotonic", record)

    def test_explicit_none_keeps_legacy_zero_phase_behavior(self):
        for kind, count in (("posix", 3), ("windows", 2)):
            scope = self.scope(kind)
            with self.subTest(kind=kind):
                self.assertEqual(scope.drain(grace=0, kill_wait=0, deadline=None), [])
                self.assertEqual(scope.discover.call_count, count)

    def test_default_signal_route_does_not_pass_a_new_keyword_to_existing_overrides(self):
        for kind in ("posix", "darwin"):
            scope = self.scope(kind)
            scope.discover.return_value = [self.identity]
            seen = []
            scope._send = lambda identity, handle, signum: seen.append((identity, handle, signum))
            with self.subTest(kind=kind):
                scope.signal_all(processes.SIG_TERM)
                self.assertEqual(len(seen), 1)

    def test_explicit_posix_and_darwin_require_three_completed_quiet_censuses(self):
        for kind in ("posix", "darwin"):
            self.reset_clock()
            scope = self.scope(kind)
            with self.subTest(kind=kind):
                self.assertEqual(scope.drain(grace=1, kill_wait=1, deadline=110), [])
                self.assertEqual(scope.discover.call_count, 3)
                self.assertAlmostEqual(self.clock.value, 100.2)

    def test_one_or_two_quiet_censuses_are_not_posix_retirement(self):
        for kind in ("posix", "darwin"):
            for duration, count in ((0.05, 1), (0.15, 2)):
                self.reset_clock()
                scope = self.scope(kind)
                with self.subTest(kind=kind, duration=duration), self.assertRaises(processes.OwnershipError):
                    scope.drain(grace=duration, kill_wait=0, deadline=110)
                self.assertEqual(scope.discover.call_count, count)

    def test_quiet_count_is_not_carried_across_phase_expiry(self):
        for kind in ("posix", "darwin"):
            self.reset_clock()
            scope = self.scope(kind)
            with self.subTest(kind=kind), self.assertRaises(processes.OwnershipError):
                scope.drain(grace=.15, kill_wait=.15, deadline=110)
            self.assertEqual(scope.discover.call_count, 4)
            self.assertAlmostEqual(self.clock.value, 100.3)

    def test_windows_retains_completed_empty_job_census_not_posix_three_quiet_rule(self):
        scope = self.scope("windows")
        self.assertEqual(scope.drain(grace=1, kill_wait=1, deadline=110), [])
        self.assertEqual(scope.discover.call_count, 1)
        self.assertEqual(self.clock.sleeps, [])

    def test_empty_census_completing_at_or_after_end_is_not_retirement_or_a_final_retry(self):
        for kind in ("posix", "darwin", "windows"):
            for late in (101, 101.01):
                self.reset_clock()
                scope = self.scope(kind)
                def discover():
                    self.clock.value = late
                    return []
                scope.discover.side_effect = discover
                with self.subTest(kind=kind, late=late), self.assertRaises(processes.OwnershipError):
                    scope.drain(grace=1, kill_wait=1, deadline=101)
                self.assertEqual(scope.discover.call_count, 1)
                if kind == "darwin":
                    self.assertEqual(scope.drain_reconciliations[-1]["outcome"], "failed")
                    self.assertIsNone(scope.active_drain)

    def test_third_quiet_census_started_before_but_finished_at_end_is_rejected(self):
        for kind in ("posix", "darwin"):
            self.reset_clock()
            scope = self.scope(kind)
            def discover():
                if scope.discover.call_count == 3:
                    self.clock.value = 100.3
                return []
            scope.discover.side_effect = discover
            with self.subTest(kind=kind), self.assertRaises(processes.OwnershipError):
                scope.drain(grace=.3, kill_wait=0, deadline=101)
            self.assertEqual(scope.discover.call_count, 3)

    def test_final_return_check_rejects_expiry_after_timely_empty_observation(self):
        for kind, count in (("posix", 3), ("windows", 1)):
            self.reset_clock()
            scope = self.scope(kind)
            observed_checks = []
            def now():
                if scope.discover.call_count == count:
                    observed_checks.append(True)
                    if len(observed_checks) >= 2:
                        self.clock.value = 101
            self.clock.on_now = now
            with self.subTest(kind=kind), self.assertRaises(processes.OwnershipError):
                scope.drain(grace=1, kill_wait=1, deadline=101)
            self.assertEqual(scope.discover.call_count, count)

    def test_fixed_kill_end_spends_slow_initial_census_without_renewal(self):
        for kind in ("posix", "darwin", "windows"):
            self.reset_clock()
            scope = self.scope(kind)
            calls = []
            def discover():
                calls.append(self.clock.value)
                if len(calls) == 1:
                    self.clock.value = 100.2
                return [self.identity]
            scope.discover.side_effect = discover
            with self.subTest(kind=kind):
                self.assertEqual(scope.drain(grace=.05, kill_wait=.3, deadline=110), [self.identity])
                self.assertAlmostEqual(self.clock.value, 100.35)
                self.assertTrue(all(start < 100.35 for start in calls))
                if kind == "darwin":
                    self.assertEqual([row["deadlineMonotonic"] for row in scope.drain_reconciliations[-1]["phases"]],
                                     [100.05, 100.35])

    def test_slow_term_signal_does_not_renew_kill_grace(self):
        scope = self.scope("posix")
        scope.discover.return_value = [self.identity]
        def send(_handle, signum):
            if signum == processes.SIG_TERM:
                self.clock.value = 100.1875
        self.native_send.side_effect = send
        # Binary-exact phase/overrun values make exactly one remaining KILL
        # sweep intentional. Decimal .3 + .1 can leave a genuine one-ULP
        # pre-end window and permit another sweep without renewing anything.
        self.assertEqual(scope.drain(grace=.125, kill_wait=.125, deadline=110), [self.identity])
        self.assertEqual(self.clock.value, 100.25)
        self.assertEqual([call.args[1] for call in self.native_send.call_args_list],
                         [processes.SIG_TERM, processes.SIG_KILL])

    def test_original_end_can_consume_whole_term_phase_without_granting_late_kill(self):
        scope = self.scope("windows")
        scope.discover.return_value = [self.identity]
        self.assertEqual(scope.drain(grace=1, kill_wait=1, deadline=100.25), [self.identity])
        self.assertAlmostEqual(self.clock.value, 100.25)
        scope.api.TerminateJobObject.assert_not_called()
        self.assertTrue(all(start + duration <= 100.25 for start, duration in self.clock.sleeps))

    def test_windows_sends_at_most_once_per_phase_and_returns_only_observed_survivors(self):
        scope = self.scope("windows")
        child = SimpleNamespace(pid=7, poll=Mock(return_value=None))
        scope.leaders = [child]
        scope.discover.return_value = [self.identity]
        self.assertEqual(scope.drain(grace=.2, kill_wait=.2, deadline=110), [self.identity])
        scope.api.GenerateConsoleCtrlEvent.assert_called_once_with(1, 7)
        scope.api.TerminateJobObject.assert_called_once_with(scope.job, 125)
        self.assertAlmostEqual(self.clock.value, 100.4)

    def test_discovery_errors_or_pending_lifetimes_prevent_empty_success(self):
        for kind in ("posix", "darwin", "windows"):
            for pending in (False, True):
                self.reset_clock()
                scope = self.scope(kind)
                if pending:
                    scope.pending_discoveries[7] = {"identity": self.identity}
                else:
                    scope.discovery_errors.add("original unresolved discovery")
                with self.subTest(kind=kind, pending=pending), self.assertRaises(processes.OwnershipError):
                    scope.drain(grace=.3, kill_wait=0, deadline=101)

    def test_native_census_failure_and_cancellation_keep_original_exception(self):
        for kind in ("posix", "darwin", "windows"):
            for error in (OSError("original census failure"), KeyboardInterrupt("original cancellation")):
                self.reset_clock()
                scope = self.scope(kind)
                scope.discover.side_effect = error
                with self.subTest(kind=kind, error=type(error).__name__), self.assertRaises(type(error)) as caught:
                    scope.drain(deadline=110)
                self.assertIs(caught.exception, error)
                self.assertEqual(scope.discover.call_count, 1)
                if kind == "darwin":
                    self.assertIsNone(scope.active_drain)
                    self.assertEqual(scope.drain_reconciliations[-1]["outcome"], "failed")

    def test_posix_signal_sweep_checks_its_nested_census_before_any_send(self):
        scope = self.scope("posix")
        def discover():
            self.clock.value = 101
            return [self.identity]
        scope.discover.side_effect = discover
        with self.assertRaises(processes.DrainDeadlineExceeded):
            scope.signal_all(processes.SIG_TERM, deadline=101)
        self.native_send.assert_not_called()

    def test_posix_multi_identity_send_stops_when_first_send_consumes_end(self):
        scope = self.scope("posix")
        other = {**self.identity, "pid": 8}
        scope.handles[scope._key(other)] = 100
        scope.discover.return_value = [self.identity, other]
        self.native_send.side_effect = lambda *_args: setattr(self.clock, "value", 101)
        with self.assertRaises(processes.DrainDeadlineExceeded):
            scope.signal_all(processes.SIG_KILL, deadline=101)
        self.native_send.assert_called_once_with(99, processes.SIG_KILL)

    def test_posix_late_esrch_is_not_converted_to_success(self):
        scope = self.scope("posix")
        scope.discover.return_value = [self.identity]
        def vanished(*_args):
            self.clock.value = 101
            raise ProcessLookupError(7)
        self.native_send.side_effect = vanished
        with self.assertRaises(processes.DrainDeadlineExceeded):
            scope.signal_all(processes.SIG_TERM, deadline=101)

    def test_linux_signal_entry_and_postcall_are_guarded(self):
        scope = self.scope("posix")
        with self.assertRaises(processes.DrainDeadlineExceeded):
            scope._send(self.identity, 99, processes.SIG_TERM, deadline=100)
        self.native_send.assert_not_called()
        self.native_send.side_effect = lambda *_args: setattr(self.clock, "value", 101)
        with self.assertRaises(processes.DrainDeadlineExceeded):
            scope._send(self.identity, 99, processes.SIG_TERM, deadline=101)

    def test_darwin_late_token_acquisition_never_reaches_signal_syscall(self):
        scope = self.scope("darwin")
        def acquire(_identity):
            self.clock.value = 101
            return processes.AuditToken()
        scope._acquire.side_effect = acquire
        with self.assertRaises(processes.DrainDeadlineExceeded):
            scope._send(self.identity, 99, processes.SIG_TERM, deadline=101)
        scope.proc.proc_signal_with_audittoken.assert_not_called()

    def test_darwin_actual_observation_returning_late_never_reaches_signal_syscall(self):
        scope = self.scope("darwin")
        scope._acquire = MethodType(processes.DarwinScope._acquire, scope)
        def acquire_once(_identity):
            self.clock.value = 101
            return processes.AuditToken()
        scope._acquire_once = acquire_once
        with self.assertRaises(processes.DrainDeadlineExceeded):
            scope._send(self.identity, 99, processes.SIG_TERM, deadline=101)
        scope.proc.proc_signal_with_audittoken.assert_not_called()
        self.assertEqual(scope._identity.call_count, 2)

    def test_darwin_signal_result_at_cutoff_is_not_esrch_or_success(self):
        for result in (0, errno.ESRCH):
            self.reset_clock()
            scope = self.scope("darwin")
            def native(*_args):
                self.clock.value = 101
                return result
            scope.proc.proc_signal_with_audittoken.side_effect = native
            with self.subTest(result=result), self.assertRaises(processes.DrainDeadlineExceeded):
                scope._send(self.identity, 99, processes.SIG_TERM, deadline=101)

    def test_darwin_timely_token_error_and_native_denial_keep_existing_error_types(self):
        scope = self.scope("darwin")
        scope.proc.proc_signal_with_audittoken.return_value = errno.EPERM
        with self.assertRaisesRegex(processes.OwnershipError, "identity-scoped signal"):
            scope._send(self.identity, 99, processes.SIG_TERM, deadline=101)
        original = processes.DarwinObservationExhausted("original token failure")
        scope._acquire.side_effect = original
        with self.assertRaises(processes.DarwinObservationExhausted) as caught:
            scope._send(self.identity, 99, processes.SIG_TERM, deadline=101)
        self.assertIs(caught.exception, original)

    def test_darwin_late_native_denial_is_fatal_not_normal_phase_escalation(self):
        for result in (errno.EPERM, errno.EACCES, errno.EINVAL):
            self.reset_clock()
            scope = self.scope("darwin")
            # If the fatal denial were hidden as phase expiry, the later empty
            # censuses would manufacture a retired outcome. They must not run.
            scope.discover.side_effect = [[self.identity], [self.identity], [], [], []]
            def native(*_args):
                self.clock.value = 100.125
                return result
            scope.proc.proc_signal_with_audittoken.side_effect = native
            with self.subTest(result=result), self.assertRaisesRegex(processes.OwnershipError, f"errno {result}"):
                scope.drain(grace=.125, kill_wait=1, deadline=102)
            record = scope.drain_reconciliations[-1]
            self.assertEqual(record["outcome"], "failed")
            self.assertIn(f"errno {result}", record["error"])
            self.assertEqual(len(record["phases"]), 1)
            self.assertEqual(scope.discover.call_count, 2)
            self.assertEqual(scope.proc.proc_signal_with_audittoken.call_count, 1)
            self.assertIsNone(scope.active_drain)

    def pending_darwin(self):
        scope = self.scope("darwin")
        key = scope._key(self.identity)
        record = {"identity": dict(self.identity), "outcome": "unresolved", "firstFailure": "original denial"}
        scope.active_drain = {"deadline": 101, "pending": {key: record}, "record": {"signalReconciliations": [record]}}
        return scope, key, record

    def test_darwin_late_pending_reconciliation_never_removes_original_lifetime(self):
        scope, key, record = self.pending_darwin()
        original = copy.deepcopy(record)
        def identity(*_args, **_kwargs):
            self.clock.value = 101
            return None
        scope._identity.side_effect = identity
        with self.assertRaises(processes.DrainDeadlineExceeded):
            scope._reconcile_drain_signals(deadline=101)
        self.assertEqual(scope.active_drain["pending"][key], original)
        scope._identity.assert_called_once_with(7, required=True)

    def test_darwin_late_signal_cannot_mark_pending_access_reconciled(self):
        scope, key, record = self.pending_darwin()
        scope.discover.return_value = [self.identity]
        def send(*_args, **_kwargs):
            self.clock.value = 101
        scope._send = send
        with self.assertRaises(processes.DrainDeadlineExceeded):
            scope.signal_all(processes.SIG_TERM, deadline=101)
        self.assertIn(key, scope.active_drain["pending"])
        self.assertEqual(record["outcome"], "unresolved")

    def test_darwin_late_mocked_esrch_does_not_start_reconciliation(self):
        scope, key, record = self.pending_darwin()
        scope.discover.return_value = [self.identity]
        def send(*_args, **_kwargs):
            self.clock.value = 101
            raise ProcessLookupError(7)
        scope._send = send
        with self.assertRaises(processes.DrainDeadlineExceeded):
            scope.signal_all(processes.SIG_TERM, deadline=101)
        self.assertEqual(scope._identity.call_count, 1)  # Only the original timely pre-send reconciliation.
        self.assertIn(key, scope.active_drain["pending"])
        self.assertEqual(record["outcome"], "unresolved")

    def test_darwin_existing_observation_window_can_overrun_but_cannot_authorize_a_signal(self):
        scope = self.scope("darwin")
        scope.discover.return_value = [self.identity]
        scope._acquire = MethodType(processes.DarwinScope._acquire, scope)
        scope._acquire_once = Mock(side_effect=processes.DarwinObservationError("original task access denial"))
        with self.assertRaises(processes.DarwinObservationExhausted):
            scope.drain(grace=.1, kill_wait=.1, deadline=100.2)
        record = scope.drain_reconciliations[-1]
        self.assertEqual(record["outcome"], "unresolved")
        self.assertIn("original task access denial", record["signalReconciliations"][0]["firstFailure"])
        self.assertEqual(record["signalReconciliations"][0]["outcome"], "unresolved")
        self.assertGreaterEqual(self.clock.value, 100.2)
        self.assertLessEqual(self.clock.value, 100.25)
        scope.proc.proc_signal_with_audittoken.assert_not_called()
        self.assertIsNone(scope.active_drain)

    def test_darwin_late_final_record_cannot_remain_retired(self):
        scope = self.scope("darwin")
        def now():
            if scope.active_drain and scope.active_drain["record"]["outcome"] == "retired":
                self.clock.value = 101
        self.clock.on_now = now
        with self.assertRaises(processes.DrainDeadlineExceeded):
            scope.drain(grace=1, kill_wait=1, deadline=101)
        self.assertEqual(scope.drain_reconciliations[-1]["outcome"], "failed")
        self.assertIsNone(scope.active_drain)

    def test_darwin_final_clock_error_keeps_original_census_failure(self):
        scope = self.scope("darwin")
        original = OSError("original census failure")
        def discover():
            self.clock.on_now = Mock(side_effect=ValueError("final clock failure"))
            raise original
        scope.discover.side_effect = discover
        with self.assertRaises(OSError) as caught:
            scope.drain(deadline=101)
        self.assertIs(caught.exception, original)
        record = scope.drain_reconciliations[-1]
        self.assertEqual(record["error"], "original census failure")
        self.assertEqual(record["finalizationError"], "final clock failure")
        self.assertEqual(record["outcome"], "failed")
        self.assertIsNone(scope.active_drain)

    def test_darwin_later_drain_cannot_rewrite_prior_failed_record(self):
        scope = self.scope("darwin")
        scope.discover.side_effect = OSError("earlier failure")
        with self.assertRaises(OSError):
            scope.drain(deadline=101)
        original = copy.deepcopy(scope.drain_reconciliations[0])
        scope.discover.side_effect = None
        self.assertEqual(scope.drain(deadline=101), [])
        self.assertEqual(scope.drain_reconciliations[0], original)
        self.assertEqual(scope.drain_reconciliations[1]["outcome"], "retired")

    def test_windows_late_poll_never_signals_that_child_or_polls_the_next(self):
        scope = self.scope("windows")
        def poll():
            self.clock.value = 101
            return None
        first = SimpleNamespace(pid=7, poll=Mock(side_effect=poll))
        second = SimpleNamespace(pid=8, poll=Mock(return_value=None))
        scope.leaders = [first, second]
        with self.assertRaises(processes.DrainDeadlineExceeded):
            scope.signal_all(processes.SIG_TERM, deadline=101)
        scope.api.GenerateConsoleCtrlEvent.assert_not_called()
        second.poll.assert_not_called()

    def test_windows_ctrl_break_postcall_expiry_prevents_next_poll(self):
        scope = self.scope("windows")
        first = SimpleNamespace(pid=7, poll=Mock(return_value=None))
        second = SimpleNamespace(pid=8, poll=Mock(return_value=None))
        scope.leaders = [first, second]
        scope.api.GenerateConsoleCtrlEvent.side_effect = lambda *_args: setattr(self.clock, "value", 101)
        with self.assertRaises(processes.DrainDeadlineExceeded):
            scope.signal_all(processes.SIG_TERM, deadline=101)
        scope.api.GenerateConsoleCtrlEvent.assert_called_once_with(1, 7)
        second.poll.assert_not_called()

    def test_windows_terminate_job_is_checked_at_entry_and_after_native_return(self):
        scope = self.scope("windows")
        with self.assertRaises(processes.DrainDeadlineExceeded):
            scope.signal_all(processes.SIG_KILL, deadline=100)
        scope.api.TerminateJobObject.assert_not_called()
        scope.api.TerminateJobObject.side_effect = lambda *_args: setattr(self.clock, "value", 101) or 1
        with self.assertRaises(processes.DrainDeadlineExceeded):
            scope.signal_all(processes.SIG_KILL, deadline=101)
        scope.api.TerminateJobObject.assert_called_once_with(scope.job, 125)


if __name__ == "__main__":
    result = unittest.main(verbosity=2, exit=False).result
    print("NATIVE_PROCESS_RETIREMENT=NOT_RUN (fake-clock/native-call models only)")
    raise SystemExit(0 if result.wasSuccessful() else 1)
