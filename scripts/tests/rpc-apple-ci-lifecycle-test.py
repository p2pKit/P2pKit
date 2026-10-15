#!/usr/bin/env python3
"""Pure keeper transitions/refusals only; no native execution or cleanup evidence."""
from dataclasses import FrozenInstanceError, replace
import importlib.util
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("tested_ci_keeper", ROOT / "scripts/rpc_apple_ci_lifecycle.py")
keeper = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = keeper
spec.loader.exec_module(keeper)
BOOT = "abcdef12-1234-5678-9abc-abcdef123456"


def record():
    return {"source": {"commit": "a" * 40, "tree": "b" * 40}, "runId": 123, "runAttempt": 2,
            "jobId": "c" * 32, "invocationId": "d" * 32, "bootSession": BOOT,
            "boundAtMonotonic": 100, "productCutoffMonotonic": 500,
            "finalizationCutoffMonotonic": 700, "jobCutoffMonotonic": 900,
            "cancellationAllowanceSeconds": 200, "terminalAndVerificationReserveSeconds": 45}


def observation(now=110, **changes):
    return {"now": now, "boot_session": BOOT, "facade": "SAME", **changes}


def decision():
    return keeper.KeeperDecision(keeper.KeeperBinding.from_record(record()))


class BindingTests(unittest.TestCase):
    def test_binding_is_immutable_and_does_not_alias_input(self):
        source = record()
        binding = keeper.KeeperBinding.from_record(source)
        source["source"]["commit"] = "e" * 40
        self.assertEqual("a" * 40, binding.commit)
        with self.assertRaises(FrozenInstanceError):
            binding.product_cutoff = 1000
        state = keeper.KeeperDecision(binding)
        with self.assertRaises(AttributeError):
            state.binding = replace(binding, invocation_id="e" * 32)

    def test_binding_and_source_have_closed_exact_keys(self):
        for field in keeper.BINDING_KEYS:
            changed = record()
            changed.pop(field)
            with self.subTest(field=field), self.assertRaises(ValueError):
                keeper.KeeperBinding.from_record(changed)
        for changed in (None, [], {**record(), "extend": True}, {**record(), "source": {"commit": "a" * 40}},
                        {**record(), "source": {**record()["source"], "approved": True}}):
            with self.assertRaises(ValueError):
                keeper.KeeperBinding.from_record(changed)

    def test_source_run_attempt_and_preallocated_ids_are_exact(self):
        for field in ("runId", "runAttempt"):
            for invalid in (True, 0, -1, 1.0, "1", None, 2**63):
                with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                    keeper.KeeperBinding.from_record({**record(), field: invalid})
        for field in ("jobId", "invocationId"):
            for invalid in (True, "0" * 32, "C" * 32, "a" * 31, "a" * 33, "a" * 32 + "\n", None):
                with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                    keeper.KeeperBinding.from_record({**record(), field: invalid})
        for field in ("commit", "tree"):
            for invalid in (True, "0" * 40, "A" * 40, "a" * 39, "HEAD", None):
                source = {**record()["source"], field: invalid}
                with self.subTest(field=field, invalid=invalid), self.assertRaises(ValueError):
                    keeper.KeeperBinding.from_record({**record(), "source": source})
        with self.assertRaises(ValueError):
            keeper.KeeperBinding.from_record({**record(), "source": {"commit": "a" * 40, "tree": "b" * 64}})

    def test_consistent_sha256_source_is_supported_without_relabelling(self):
        source = {"commit": "a" * 64, "tree": "b" * 64}
        binding = keeper.KeeperBinding.from_record({**record(), "source": source})
        self.assertEqual((source["commit"], source["tree"]), (binding.commit, binding.tree))

    def test_boot_is_exact_and_case_normalized_not_optional(self):
        self.assertEqual(BOOT, keeper.KeeperBinding.from_record({**record(), "bootSession": BOOT.upper()}).boot_session)
        for value in (None, True, "unknown", "", "00000000-0000-0000-0000-000000000000"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                keeper.KeeperBinding.from_record({**record(), "bootSession": value})

    def test_all_initial_deadlines_are_finite_typed_and_nonrenewable(self):
        fields = ("boundAtMonotonic", "productCutoffMonotonic", "finalizationCutoffMonotonic", "jobCutoffMonotonic",
                  "cancellationAllowanceSeconds", "terminalAndVerificationReserveSeconds")
        for field in fields:
            for value in (True, -1, "1", None, math.nan, math.inf, -math.inf, 10**1000):
                with self.subTest(field=field, kind=type(value).__name__), self.assertRaises(ValueError):
                    keeper.KeeperBinding.from_record({**record(), field: value})
        for change in ({"productCutoffMonotonic": 100}, {"finalizationCutoffMonotonic": 529.99},
                       {"jobCutoffMonotonic": 699}, {"jobCutoffMonotonic": 3701}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                keeper.KeeperBinding.from_record({**record(), **change})

    def test_cancellation_contract_must_be_supplied_and_reserve_terminal_phase(self):
        for change in ({"cancellationAllowanceSeconds": 301}, {"cancellationAllowanceSeconds": 0},
                       {"cancellationAllowanceSeconds": 45}, {"terminalAndVerificationReserveSeconds": 29},
                       {"terminalAndVerificationReserveSeconds": 201}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                keeper.KeeperBinding.from_record({**record(), **change})

    def test_direct_dataclass_constructor_cannot_bypass_validation(self):
        binding = keeper.KeeperBinding.from_record(record())
        for changes in ({"run_id": True}, {"job_cutoff": 10000}, {"job_id": "bad"}, {"boot_session": None}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(binding, **changes)
        with self.assertRaises(ValueError):
            keeper.KeeperDecision(record())


class LifecycleTests(unittest.TestCase):
    def test_begin_is_single_use_decision_not_actual_execution_authority(self):
        state = decision()
        self.assertTrue(state.begin_product(**observation()))
        with self.assertRaises(ValueError):
            state.begin_product(**observation(120))
        result = state.finish(cleanup_verified=True, **observation(130))
        self.assertIsNone(result["productExitCode"])
        self.assertEqual(125, result["exitCodeDecision"])
        self.assertFalse(result["nativeExecutionAuthorized"])
        self.assertTrue(result["runtimeEvidenceRequired"])

    def test_cancel_before_start_prevents_launch_without_administrative_child(self):
        state = decision()
        self.assertFalse(state.observe(**observation(explicit_cancel=True)))
        self.assertFalse(state.begin_product(**observation(120)))
        callback, clock = Mock(), Mock()
        self.assertEqual("NOT_REQUESTED", state.request_cancellation(callback, clock))
        callback.assert_not_called()
        clock.assert_not_called()

    def test_cancel_between_launch_decision_and_actual_spawn_fences_preallocated_id(self):
        state = decision()
        self.assertTrue(state.begin_product(**observation()))
        state.observe(**observation(120, facade="EOF"))
        callback = Mock(return_value=None)
        clock = Mock(side_effect=[(121, BOOT), (122, BOOT)])
        self.assertEqual("ACKNOWLEDGED_BY_CALLBACK", state.request_cancellation(callback, clock))
        callback.assert_called_once_with(expected_job_id="c" * 32, invocation_id="d" * 32, deadline_monotonic=state.cancellation_request_cutoff)
        result = state.finish(cleanup_verified=True, **observation(123, facade="EOF"))
        self.assertIsNone(result["productExitCode"])
        self.assertEqual(125, result["exitCodeDecision"])

    def test_explicit_eof_and_identity_uncertainty_latch_irreversibly(self):
        for changes, reason in (({"explicit_cancel": True}, "EXPLICIT_CANCEL"),
                                ({"facade": "EOF"}, "FACADE_EOF"),
                                ({"facade": "UNCERTAIN"}, "FACADE_IDENTITY_UNKNOWN"),
                                ({"facade": None}, "FACADE_IDENTITY_UNKNOWN"),
                                ({"explicit_cancel": 1}, "CANCEL_OBSERVATION_UNKNOWN")):
            state = decision()
            self.assertFalse(state.observe(**observation(**changes)))
            self.assertFalse(state.observe(**observation(120)))
            self.assertFalse(state.begin_product(**observation(130)))
            self.assertEqual(reason, state.cancellation_reason)

    def test_first_failure_diagnostic_survives_later_deadline_and_cleanup(self):
        state = decision()
        state.begin_product(**observation())
        state.observe(**observation(120, facade="UNCERTAIN"))
        result = state.finish(cleanup_verified=True, **observation(700, explicit_cancel=True))
        self.assertEqual("FACADE_IDENTITY_UNKNOWN", result["cancellationReason"])
        self.assertEqual("UNKNOWN", result["cleanupObservation"])
        self.assertEqual(125, result["exitCodeDecision"])

    def test_product_completion_cannot_arrive_at_or_after_cutoff(self):
        for now in (500, 501):
            state = decision()
            state.begin_product(**observation())
            state.product_exited(0, **observation(now))
            result = state.finish(cleanup_verified=True, **observation(now + 1))
            self.assertEqual("PRODUCT_DEADLINE", result["cancellationReason"])
            self.assertEqual(0, result["productExitCode"])
            self.assertEqual(125, result["exitCodeDecision"])

    def test_product_deadline_blocks_start_even_without_external_cancel(self):
        state = decision()
        self.assertFalse(state.begin_product(**observation(500)))
        self.assertEqual("PRODUCT_DEADLINE", state.cancellation_reason)

    def test_completed_product_may_use_reserved_cleanup_but_not_new_product_time(self):
        state = decision()
        state.begin_product(**observation())
        state.product_exited(0, **observation(499))
        result = state.finish(cleanup_verified=True, **observation(699))
        self.assertIsNone(result["cancellationReason"])
        self.assertEqual(0, result["exitCodeDecision"])
        self.assertEqual("VERIFIED_BY_CALLER", result["cleanupObservation"])
        self.assertEqual(record()["source"], result["source"])
        for key in ("runId", "runAttempt", "jobId", "invocationId"):
            self.assertEqual(record()[key], result[key])
        self.assertEqual(keeper.SCOPE, result["scope"])
        self.assertTrue(result["runtimeEvidenceRequired"])

    def test_finalization_deadline_rejects_caller_claimed_cleanup(self):
        for now in (700, 701, 900):
            state = decision()
            state.begin_product(**observation())
            state.product_exited(0, **observation(120))
            result = state.finish(cleanup_verified=True, **observation(now))
            self.assertEqual("FINALIZATION_DEADLINE", result["cancellationReason"])
            self.assertEqual(125, result["exitCodeDecision"])
            self.assertEqual("UNKNOWN", result["cleanupObservation"])

    def test_saved_product_zero_never_overrides_cancel_even_with_verified_cleanup(self):
        state = decision()
        state.begin_product(**observation())
        state.product_exited(0, **observation(120))
        result = state.finish(cleanup_verified=True, **observation(130, explicit_cancel=True))
        self.assertEqual(0, result["productExitCode"])
        self.assertEqual(125, result["exitCodeDecision"])
        self.assertEqual("VERIFIED_BY_CALLER", result["cleanupObservation"])
        self.assertEqual("EXPLICIT_CANCEL", result["cancellationReason"])

    def test_missing_cleanup_cannot_inherit_product_success(self):
        state = decision()
        state.begin_product(**observation())
        state.product_exited(0, **observation(120))
        self.assertEqual(125, state.finish(cleanup_verified=False, **observation(130))["exitCodeDecision"])

    def test_failure_codes_are_preserved_and_signals_never_become_success(self):
        for code in (1, 2, 125, 255, -9):
            state = decision()
            state.begin_product(**observation())
            state.product_exited(code, **observation(120))
            result = state.finish(cleanup_verified=True, **observation(130))
            self.assertEqual(code, result["productExitCode"])
            self.assertEqual(code if code >= 0 else 125, result["exitCodeDecision"])

    def test_product_exit_requires_single_launch_decision_and_exact_integer(self):
        with self.assertRaises(ValueError):
            decision().product_exited(0, **observation())
        for code in (True, None, "0", 0.0, 256, -256):
            state = decision()
            state.begin_product(**observation())
            with self.assertRaises(ValueError):
                state.product_exited(code, **observation(120))
        state = decision()
        state.begin_product(**observation())
        state.product_exited(0, **observation(120))
        with self.assertRaises(ValueError):
            state.product_exited(0, **observation(130))

    def test_finalized_core_cannot_restart_reobserve_or_cancel(self):
        state = decision()
        state.finish(cleanup_verified=False, **observation())
        for call in (lambda: state.begin_product(**observation()), lambda: state.observe(**observation()),
                     lambda: state.finish(cleanup_verified=True, **observation()),
                     lambda: state.request_cancellation(Mock(), Mock())):
            with self.assertRaises(ValueError):
                call()

    def test_cleanup_boolean_is_not_truthiness_admission(self):
        for value in (1, "true", None, []):
            with self.assertRaises(ValueError):
                decision().finish(cleanup_verified=value, **observation())


class ClockAndCallbackTests(unittest.TestCase):
    def started_cancelled(self):
        state = decision()
        state.begin_product(**observation())
        state.observe(**observation(120, explicit_cancel=True))
        return state

    def test_first_cancel_latches_earlier_cutoff_and_reserves_terminal_and_verification(self):
        state = self.started_cancelled()
        first, request = state.cancellation_cutoff, state.cancellation_request_cutoff
        self.assertLess(first, 320)
        self.assertLess(request, 275)
        self.assertGreaterEqual(first - request, 45)
        self.assertLess(first, state.binding.finalization_cutoff)
        for now in (121, 150, 200):
            state.observe(**observation(now, explicit_cancel=True))
            self.assertEqual(first, state.cancellation_cutoff)
            self.assertEqual(request, state.cancellation_request_cutoff)
        callback = Mock(return_value=None)
        state.request_cancellation(callback, lambda: (201, BOOT))
        callback.assert_called_once_with(expected_job_id="c" * 32, invocation_id="d" * 32,
                                         deadline_monotonic=request)

    def test_cancellation_never_extends_original_finalization_cutoff(self):
        state = decision()
        state.begin_product(**observation())
        state.product_exited(0, **observation(499))
        state.observe(**observation(650, explicit_cancel=True))
        self.assertEqual(700, state.cancellation_cutoff)
        self.assertLess(state.cancellation_request_cutoff, 655)

    def test_late_callback_cannot_use_reserved_terminal_time_as_its_own_allowance(self):
        state = self.started_cancelled()
        callback = Mock(return_value=None)
        self.assertEqual("LATE_CALLBACK_COMPLETION", state.request_cancellation(
            callback, Mock(side_effect=[(121, BOOT), (280, BOOT)])))
        self.assertLess(280, state.cancellation_cutoff)
        self.assertLess(state.cancellation_request_cutoff, 280)
        result = state.finish(cleanup_verified=True, **observation(300))
        self.assertEqual(125, result["exitCodeDecision"])
        # Only the caller can establish that actual cleanup still completed.
        self.assertEqual("VERIFIED_BY_CALLER", result["cleanupObservation"])

    def test_cleanup_after_cancellation_cutoff_cannot_use_unused_job_time(self):
        state = self.started_cancelled()
        result = state.finish(cleanup_verified=True, **observation(321))
        self.assertLess(321, state.binding.finalization_cutoff)
        self.assertEqual("UNKNOWN", result["cleanupObservation"])
        self.assertEqual(125, result["exitCodeDecision"])

    def test_clock_reversal_nonfinite_unknown_or_boolean_latches_refusal(self):
        for now, reason in ((99, "CLOCK_REVERSED"), (True, "CLOCK_UNKNOWN"), (None, "CLOCK_UNKNOWN"),
                            (math.nan, "CLOCK_UNKNOWN"), (math.inf, "CLOCK_UNKNOWN"), (10**1000, "CLOCK_UNKNOWN")):
            state = decision()
            self.assertFalse(state.observe(**observation(now)))
            self.assertEqual(reason, state.cancellation_reason)
            self.assertFalse(state.begin_product(**observation(120)))

    def test_boot_change_does_not_compare_or_renew_old_monotonic_deadline(self):
        unknown = decision()
        unknown.observe(**observation(1, boot_session="abcdef12-1234-5678-9abc-abcdef123457"))
        self.assertEqual("BOOT_SESSION_CHANGED", unknown.cancellation_reason)
        self.assertIsNone(unknown.cancellation_cutoff)
        self.assertFalse(unknown.begin_product(**observation(120)))
        self.assertIsNone(unknown.cancellation_cutoff)
        state = self.started_cancelled()
        state.observe(**observation(1, boot_session="abcdef12-1234-5678-9abc-abcdef123457"))
        callback = Mock()
        self.assertEqual("REFUSED_CLOCK", state.request_cancellation(callback, lambda: (130, BOOT)))
        callback.assert_not_called()
        result = state.finish(cleanup_verified=True, **observation(140))
        self.assertEqual("UNKNOWN", result["cleanupObservation"])
        self.assertEqual("EXPLICIT_CANCEL", result["cancellationReason"])
        self.assertEqual(700, state.binding.finalization_cutoff)

    def test_invalid_boot_latches_without_later_repair(self):
        for boot in (None, True, "", "unknown"):
            state = decision()
            state.observe(**observation(110, boot_session=boot))
            self.assertEqual("BOOT_SESSION_UNKNOWN", state.cancellation_reason)
            self.assertFalse(state.begin_product(**observation(120)))

    def test_no_callback_without_cancel_or_without_launch_decision(self):
        state = decision()
        state.begin_product(**observation())
        callback, clock = Mock(), Mock()
        self.assertEqual("NOT_REQUESTED", state.request_cancellation(callback, clock))
        callback.assert_not_called()
        clock.assert_not_called()

    def test_cancel_callback_is_at_most_once_including_failure(self):
        for fails in (False, True):
            state = self.started_cancelled()
            callback = Mock(side_effect=RuntimeError("synthetic-private-value")) if fails else Mock(return_value=None)
            clock = Mock(side_effect=[(121, BOOT), (122, BOOT)])
            expected = "FAILED_CALLBACK" if fails else "ACKNOWLEDGED_BY_CALLBACK"
            self.assertEqual(expected, state.request_cancellation(callback, clock))
            self.assertEqual(expected, state.request_cancellation(callback, clock))
            callback.assert_called_once()
            self.assertEqual(2, clock.call_count)
            self.assertNotIn("synthetic-private-value", str(state.finish(cleanup_verified=False, **observation(130))))

    def test_callback_wrong_return_is_not_a_canonical_acknowledgement(self):
        for value in (True, 0, "ok", {}):
            state = self.started_cancelled()
            self.assertEqual("FAILED_CALLBACK", state.request_cancellation(Mock(return_value=value), lambda: (130, BOOT)))

    def test_late_callback_return_is_not_acknowledged_or_retried(self):
        state = self.started_cancelled()
        callback = Mock(return_value=None)
        self.assertEqual("LATE_CALLBACK_COMPLETION", state.request_cancellation(
            callback, Mock(side_effect=[(121, BOOT), (701, BOOT)])))
        self.assertEqual("LATE_CALLBACK_COMPLETION", state.request_cancellation(callback, lambda: (702, BOOT)))
        callback.assert_called_once_with(expected_job_id="c" * 32, invocation_id="d" * 32, deadline_monotonic=state.cancellation_request_cutoff)
        result = state.finish(cleanup_verified=True, **observation(702))
        self.assertEqual(125, result["exitCodeDecision"])
        self.assertEqual("UNKNOWN", result["cleanupObservation"])

    def test_expired_callback_is_refused_before_any_request(self):
        state = self.started_cancelled()
        callback = Mock()
        self.assertEqual("REFUSED_DEADLINE", state.request_cancellation(callback, lambda: (700, BOOT)))
        callback.assert_not_called()

    def test_failed_clock_acquisition_before_callback_never_launches_request(self):
        state = self.started_cancelled()
        callback = Mock()
        self.assertEqual("REFUSED_CLOCK", state.request_cancellation(callback, Mock(side_effect=OSError("private"))))
        callback.assert_not_called()

    def test_lost_clock_or_boot_after_callback_refuses_completion(self):
        for second in ((120, BOOT), (None, BOOT), (122, "abcdef12-1234-5678-9abc-abcdef123457")):
            state = self.started_cancelled()
            callback = Mock(return_value=None)
            self.assertEqual("UNKNOWN_CALLBACK_COMPLETION", state.request_cancellation(
                callback, Mock(side_effect=[(121, BOOT), second])))
            callback.assert_called_once()
            result = state.finish(cleanup_verified=True, **observation(130))
            self.assertEqual(125, result["exitCodeDecision"])
            self.assertEqual("UNKNOWN", result["cleanupObservation"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
