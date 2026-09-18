#!/usr/bin/env python3
"""Offline legacy-reader split, NOT a new productive reader or hosted evidence.

The existing original acquisition/readmission fixtures model native, service,
clock and hosted identity suppliers. Only tiny ordinary-UID POSIX files are
real. An explicit loader excludes every inherited test method.
"""
from __future__ import annotations

from contextlib import ExitStack
import copy
from dataclasses import FrozenInstanceError, replace
import importlib.util
import inspect
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("bootstrap_reader_close_models",
    Path(__file__).with_name("hosted-cache-bootstrap-close-test.py"))
C = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = C
spec.loader.exec_module(C)
S, O, H = C.S, C.O, C.S.history
M = C.E.H.M


class ReaderViewTests(M.OfflineCase):
    def setUp(self):
        super().setUp()
        self.stack.enter_context(patch.object(S, "QUARANTINE", []))
        first = O.clocks.Reading(self.clock, self.fence.first)
        self.owner = S.Owner(self.fence.deadline(120, final=True), self.fence, first=first)
        self.addCleanup(self.owner.close)
        self.reader = S._LegacyOriginalReader(self.owner, self.fence)

    def test_constructor_derives_history_and_first_without_creating_an_owner(self):
        with ExitStack() as guards:
            for target, name in ((O.clocks, "observe"), (S.Owner, "__init__"),
                                 (S.Owner, "read"), (S.Owner, "acquire"), (S, "admit")):
                guards.enter_context(patch.object(target, name, side_effect=AssertionError("NO_ACQUISITION")))
            reader = S._LegacyOriginalReader(self.owner, self.fence)
            self.assertIs(reader.checked(), reader)
        self.assertIs(reader.owner, self.owner)
        self.assertIs(reader.current, self.fence)
        self.assertIs(reader.first, self.owner.first)
        self.assertEqual(reader.past, H.HistoricalPrelude(self.fence.raw))
        self.assertEqual(self.owner.resources, [])
        self.assertEqual(repr(reader), "_LegacyOriginalReader()")

    def test_constructor_has_no_caller_clock_history_first_or_budget_inputs(self):
        self.assertEqual(list(inspect.signature(S._LegacyOriginalReader).parameters), ["owner", "current"])
        for name, value in (("past", self.reader.past), ("first", self.owner.first),
                            ("clock", self.clock), ("budget", {})):
            with self.subTest(name=name), self.assertRaises(TypeError):
                S._LegacyOriginalReader(self.owner, self.fence, **{name: value})

    def test_other_owner_or_clock_kinds_cannot_select_a_future_reader(self):
        inputs = ((SimpleNamespace(fence=self.fence), self.fence),
                  (self.owner, self.reader.past), (self.owner, copy.copy(self.fence)),
                  (self.owner, SimpleNamespace(clock=self.clock)), (self.owner, None))
        with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_FOREIGN_CLOCK")):
            for owner, current in inputs:
                with self.subTest(kind=type(current).__name__), self.assertRaisesRegex(
                        O.OriginError, "LEGACY_READER_OWNER"):
                    S._LegacyOriginalReader(owner, current)

    def test_frozen_view_and_equal_copy_do_not_transfer_or_clone_ownership(self):
        with self.assertRaises(FrozenInstanceError):
            self.reader.current = copy.copy(self.fence)
        duplicate = replace(self.reader)
        self.assertIsNot(duplicate, self.reader)
        self.assertIs(duplicate.owner, self.owner)
        self.assertIs(duplicate.current, self.fence)
        self.assertEqual(duplicate.past, self.reader.past)
        self.assertEqual(self.owner.resources, [])
        for name in ("budget", "exportSaveAuthority", "claim", "close", "new", "deadline"):
            self.assertFalse(hasattr(duplicate, name))

    def test_changed_owner_fence_or_equal_replaced_first_is_not_the_captured_view(self):
        for name, value in (("fence", copy.copy(self.fence)), ("first", replace(self.owner.first))):
            saved = getattr(self.owner, name)
            try:
                setattr(self.owner, name, value)
                with self.subTest(name=name), patch.object(O.clocks, "observe",
                        side_effect=AssertionError("NO_CHANGED_OWNER_CLOCK")), \
                        self.assertRaisesRegex(O.OriginError, "LEGACY_READER_CHANGED"):
                    self.reader.checked()
            finally:
                setattr(self.owner, name, saved)

    def test_internally_replaced_history_is_rejected_not_adopted(self):
        raw = O.encoded(O.prelude(O.clocks.Reading(self.clock, self.fence.first + 1)))
        object.__setattr__(self.reader, "past", H.HistoricalPrelude(raw))
        with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_CHANGED_HISTORY_CLOCK")), \
                self.assertRaisesRegex(O.OriginError, "LEGACY_READER_HISTORY_CHANGED"):
            self.reader.checked()

    def test_changed_original_limit_is_not_rederived_as_new_history(self):
        saved = self.fence.work
        try:
            self.fence.work += 1
            with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_CHANGED_LIMIT_CLOCK")), \
                    self.assertRaisesRegex(O.OriginError, "HISTORY_FENCE_CHANGED"):
                self.reader.checked()
        finally:
            self.fence.work = saved

    def test_current_observation_retains_original_fence_highwater_only(self):
        past, before = self.reader.past, self.fence.last
        observed = self.reader.observe(final=False, minimum=before)
        self.assertGreater(observed, before)
        self.assertEqual(observed, self.fence.last)
        self.assertIs(self.reader.past, past)
        self.assertEqual((past.first, past.work, past.final), (1000 * O.NS, 1075 * O.NS, 1120 * O.NS))
        self.assertFalse(hasattr(past, "last"))

    def test_original75_expiry_cannot_be_recovered_by_valid_history(self):
        self.nanoseconds = self.fence.work
        self.assertIs(self.reader.checked(), self.reader)
        with self.assertRaisesRegex(O.OriginError, "ORIGINAL_FENCE_EXPIRED"):
            self.reader.observe(final=False, minimum=0)
        self.assertGreaterEqual(self.fence.last, self.fence.work)
        self.assertEqual(self.reader.past.work, self.fence.work)

    def test_original120_final_expiry_is_not_a_new_reader_allowance(self):
        self.nanoseconds = self.fence.final
        with self.assertRaisesRegex(O.OriginError, "ORIGINAL_FENCE_EXPIRED"):
            self.reader.observe(final=True, minimum=0)
        self.assertGreaterEqual(self.fence.last, self.fence.final)

    def test_clock_reversal_preserves_the_previous_highwater(self):
        before = self.fence.last
        self.nanoseconds = before - 2000
        with self.assertRaisesRegex(O.clocks.ClockError, "JOB_CLOCK_BACKWARDS"):
            self.reader.observe(final=False, minimum=0)
        self.assertEqual(self.fence.last, before)

    def test_changed_native_clock_identity_does_not_select_another_backend(self):
        self.clock = M.model_admission("desktop-windows-x64")[1]
        with self.assertRaisesRegex(O.clocks.ClockError, "JOB_CLOCK_IDENTITY_CHANGED"):
            self.reader.observe(final=False, minimum=0)
        self.assertEqual(self.reader.past.clock.role, "linux-x64")

    def test_cancellation_preserves_the_actual_observation_and_original_exception(self):
        failure = KeyboardInterrupt("SYNTHETIC_READER_CANCEL")
        self.fence.cancelled = lambda: (_ for _ in ()).throw(failure)
        before = self.fence.last
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.reader.observe(final=False, minimum=before)
        self.assertIs(caught.exception, failure)
        self.assertGreater(self.fence.last, before)

    def test_closed_owner_cannot_observe_more_time_through_its_old_view(self):
        self.owner.close()
        before = self.fence.last
        with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_POST_CLOSE_CLOCK")), \
                self.assertRaisesRegex(O.OriginError, "LEGACY_READER_NOT_LIVE"):
            self.reader.observe(final=True, minimum=0)
        self.assertEqual(self.fence.last, before)

    def test_unknown_owner_cannot_observe_or_acquire_even_for_finalization(self):
        self.owner.error("synthetic-reader", OSError("SYNTHETIC_UNKNOWN"), unknown=True)
        with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_UNKNOWN_CLOCK")), \
                self.assertRaisesRegex(O.OriginError, "LEGACY_READER_NOT_LIVE"):
            self.reader.observe(final=True, minimum=0)
        with self.assertRaisesRegex(O.OriginError, "RETIREMENT_UNKNOWN"):
            self.owner.close()
        self.assertIs(S.QUARANTINE[0], self.owner)

    def test_known_first_error_precludes_work_without_destroying_bounded_final_observation(self):
        failure = OSError("SYNTHETIC_FIRST_FAILURE")
        self.owner.error("synthetic-reader", failure)
        with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_FAILED_WORK_CLOCK")), \
                self.assertRaisesRegex(O.OriginError, "LEGACY_READER_NOT_LIVE"):
            self.reader.observe(final=False, minimum=0)
        self.reader.observe(final=True, minimum=0)
        self.assertIs(self.owner.original, failure)


class ReaderIntegrationTests(C.CloseModels):
    def reader(self, call):
        return S._LegacyOriginalReader(call.owner, call.fence)

    def read_prepared(self, call, reader=None):
        return S._read_prepared(reader or self.reader(call), call.private,
                                call.entry.handoff_original, call.entry.context_original)

    def expired_close(self, call):
        # Repeated original close-fence failures across the retained roster
        # still saturate the existing 64-error policy. No time rewind/retry.
        with self.assertRaisesRegex(O.OriginError, "RETIREMENT_UNKNOWN"):
            call.owner.close()
        self.assertTrue(call.owner.unknown)
        self.assertTrue(any(owner is call.owner for owner in S.QUARANTINE))

    def test_actual_legacy_reader_retains_historical_first_and_current_revalidation(self):
        with self.live() as call:
            reader = self.reader(call)
            admitted, context, checked = self.read_prepared(call, reader)
            self.assertEqual(admitted, call.entry.admitted)
            self.assertEqual(context, O.parse(call.entry.context_original))
            self.assertIs(reader.first, call.owner.first)
            self.assertEqual(reader.first.nanoseconds, O.parse(call.entry.raw)["window"]["adopterFirstNs"])
            self.assertTrue(S.same_preparation(checked, O.parse(call.entry.preparation_original)))
            self.assertGreater(checked["originalChain"]["revalidatedNs"], reader.first.nanoseconds)
            self.assertIs(call.owner.entry_original, call.entry)
            self.assertIsNone(call.owner.phase_originals)
            self.assertEqual((len(self.requests), len(self.scopes)), (2, 1))

    def test_history_record_helpers_do_not_observe_clock_perform_owned_reads_or_register_returns(self):
        with self.live() as call:
            past = H.snapshot(call.fence)
            context_raw = call.entry.context_original
            context = O.parse(context_raw)
            start_raw = (call.path / "service/start.json").read_bytes()
            registry = dict(call.owner.admissions)
            with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_HISTORY_CLOCK")), \
                    patch.object(S.Owner, "read", side_effect=AssertionError("NO_HISTORY_OWNER_IO")):
                self.assertEqual(S._context_history_record(context_raw, call.entry.admitted, call.path, past), context)
                self.assertEqual(S._start_history_record(start_raw, context_raw, context, call.path, past),
                                 O.parse(start_raw))
                returned, _ = S._admission_history_content(call.entry.admitted, call.entry.session_original,
                                                           call.entry.return_original, past)
                self.assertLess(returned["returnedNs"], past.work)
            self.assertEqual(call.owner.admissions, registry)

    def test_context_lower_bound_and_historical_admission_upper_bound_stay_distinct(self):
        with self.live() as call:
            past = H.snapshot(call.fence)
            context = {**O.parse(call.entry.context_original), "admissionReturnedNs": past.work}
            self.assertEqual(S._context_history_record(O.encoded(context), call.entry.admitted, call.path, past), context)
            returned = {**O.parse(call.entry.return_original), "returnedNs": past.work}
            with self.assertRaisesRegex(O.OriginError, "ORIGINAL_ADMISSION_RETURN"):
                S._admission_history_content(call.entry.admitted, call.entry.session_original, O.encoded(returned), past)

    def test_historical_helpers_keep_closed_context_fields_and_canonical_bytes(self):
        with self.live() as call:
            past, raw = H.snapshot(call.fence), call.entry.context_original
            for candidate in (raw + b" ", O.encoded({**O.parse(raw), "jobBudget": "ADMITTED"})):
                with self.subTest(candidate_bytes=len(candidate)), self.assertRaisesRegex(
                        O.OriginError, "ORIGINAL_CONTEXT"):
                    S._context_history_record(candidate, call.entry.admitted, call.path, past)

    def test_source_owned_command_failure_is_not_replaced_by_temporal_or_supplied_argv_logic(self):
        with self.live() as call:
            failure = OSError("SYNTHETIC_READER_COMMAND_RESOLUTION")
            with patch.object(S, "command", side_effect=failure), \
                    patch.object(H, "phase_start", side_effect=AssertionError("NO_PHASE_AFTER_COMMAND_ERROR")), \
                    self.assertRaises(OSError) as caught:
                self.read_prepared(call)
            self.assertIs(caught.exception, failure)

    def test_actual_observation_remains_after_the_pure_chain_minimum(self):
        with self.live() as call:
            original, minima = H.chain_minimum, []
            def minimum(*args):
                value = original(*args)
                minima.append(value)
                return value
            with patch.object(H, "chain_minimum", side_effect=minimum):
                _, _, result = self.read_prepared(call)
            self.assertEqual(len(minima), 1)
            self.assertGreater(result["originalChain"]["revalidatedNs"], minima[0])
            self.assertLessEqual(result["originalChain"]["revalidatedNs"], call.fence.last)

    def test_original_response_byte_change_is_still_refused(self):
        with self.live() as call:
            path = call.path / "service/jobs.json"
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(O.OriginError, "ORIGINAL_RESPONSES_CHANGED"):
                self.read_prepared(call)

    def test_original_prelude_byte_change_cannot_be_hidden_by_the_reader_snapshot(self):
        with self.live() as call:
            reader = self.reader(call)
            path = call.path / "prelude.json"
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(O.OriginError, "ADOPTION_ORIGINALS_CHANGED"):
                self.read_prepared(call, reader)

    def test_late_original75_after_history_is_failure_with_unchanged_cleanup_policy(self):
        with self.live() as call:
            original = H.chain_minimum
            def minimum(*args):
                value = original(*args)
                self.nanoseconds = call.fence.work
                return value
            with patch.object(H, "chain_minimum", side_effect=minimum), \
                    self.assertRaisesRegex(O.OriginError, "ORIGINAL_FENCE_EXPIRED"):
                self.read_prepared(call)
            self.assertGreaterEqual(call.fence.last, call.fence.work)
            self.expired_close(call)

    def test_current_local45_expiry_is_not_relaxed_by_historical_validation(self):
        with self.live() as call:
            reader = self.reader(call)
            self.nanoseconds = int(call.owner.local_end * O.NS) + 1
            self.assertLess(self.nanoseconds, call.fence.work)
            with self.assertRaises(S.posix.EvidenceError):
                self.read_prepared(call, reader)
            self.expired_close(call)

    def test_cancellation_after_history_is_the_original_failure_not_a_recovery(self):
        with self.live() as call:
            original, failure = H.chain_minimum, KeyboardInterrupt("SYNTHETIC_READER_CHAIN_CANCEL")
            def minimum(*args):
                value = original(*args)
                call.fence.cancelled = lambda: (_ for _ in ()).throw(failure)
                return value
            with patch.object(H, "chain_minimum", side_effect=minimum), self.assertRaises(KeyboardInterrupt) as caught:
                self.read_prepared(call)
            self.assertIs(caught.exception, failure)

    def test_arbitrary_reader_object_is_refused_before_owned_io(self):
        with self.live() as call:
            fake = SimpleNamespace(owner=call.owner, current=call.fence, past=H.snapshot(call.fence), first=call.first)
            with patch.object(S.Owner, "read", side_effect=AssertionError("NO_ARBITRARY_READER_IO")), \
                    self.assertRaisesRegex(O.OriginError, "ADOPTION_READER"):
                S._read_prepared(fake, call.private, call.entry.handoff_original, call.entry.context_original)

    def test_view_cannot_supply_an_equal_entry_missing_outer_provenance(self):
        with self.live() as call:
            self.reader(call).checked()
            with self.assertRaisesRegex(O.OriginError, "ENTRY_CLOSE_NOT_CURRENT_ENTRY"):
                S.close_entry_transition(call.owner, call.target, replace(call.entry), call.fence)
            self.assertFalse(call.owner.closed)
            self.assertFalse(call.owner.entry_close_attempted)

    def test_closed_transition_cannot_be_reopened_through_a_prior_reader_view(self):
        with self.live() as call:
            reader = self.reader(call)
            result = self.close(call)
            checked = result._checked_ns
            with self.assertRaisesRegex(O.OriginError, "OWNER_NOT_LIVE"):
                self.read_prepared(call, reader)
            with self.assertRaisesRegex(O.OriginError, "LEGACY_READER_NOT_LIVE"):
                reader.observe(final=True, minimum=checked)
            self.assertEqual(call.fence.last, checked)
            value = S.check_closed_entry_transition(result)
            self.assertEqual(value["productiveOwner"], "NOT_CREATED")
            self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
            self.assertIs(value["exportSaveAuthority"], False)

    def test_reader_does_not_invoke_a_producer_cache_or_allocation(self):
        with self.live() as call, ExitStack() as guards:
            for target, name in ((C.cache, "export_snapshot"), (C.cache, "save_set"),
                                 (C.cache, "provider_observation"), (S.allocation, "derive")):
                guards.enter_context(patch.object(target, name, side_effect=AssertionError("NO_EXECUTION")))
            _, _, result = self.read_prepared(call)
            self.assertEqual(result["originalChain"]["budgetAcceptance"], "NOT_ADMITTED")
            self.assertIs(result["originalChain"]["exportSaveAuthority"], False)

    def test_original_public_wrapper_signatures_have_no_new_bypass_parameters(self):
        expected = {"context_record": "(raw, admitted, path, fence)",
                    "start_record": "(raw, context_raw, context, path, fence)",
                    "admission_content": "(admitted, session, returned, fence)",
                    "chain_content": "(owner, private, context_raw, admitted, records, returned, admission_hashes, fence, *, final)",
                    "prepared_content": "(owner, private, handoff_raw, context_raw, fence)"}
        for name, signature in expected.items():
            with self.subTest(name=name):
                self.assertEqual(str(inspect.signature(getattr(S, name))), signature)


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(cls(name) for cls in (ReaderViewTests, ReaderIntegrationTests)
                              for name in sorted(cls.__dict__) if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
