#!/usr/bin/env python3
"""Offline historical data and existing-reader controls, not a new live reader.

Pure chronology uses supplied records, not observed service/native facts. The
existing wrapper fixtures use tiny ordinary-UID POSIX files and explicitly
modelled clocks/query/native/HTTP suppliers; no inherited tests are counted.
"""
from __future__ import annotations

from contextlib import ExitStack
import copy
from dataclasses import FrozenInstanceError, replace
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
spec = importlib.util.spec_from_file_location("bootstrap_history_close_models",
    Path(__file__).with_name("hosted-cache-bootstrap-close-test.py"))
C = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = C
spec.loader.exec_module(C)
S, O, H = C.S, C.O, C.S.history
M = C.E.H.M


class HistoryDataTests(M.OfflineCase):
    def setUp(self):
        super().setUp()
        self.frame = H.HistoricalPrelude(self.fence.raw)

    def chain(self, frame=None):
        frame = frame or self.frame
        first = frame.first
        start = {"startedNs": first + 2, "workEndNs": min(frame.work, first + 2 + 45 * O.NS)}
        start["finalEndNs"] = min(frame.final, start["workEndNs"] + 45 * O.NS)
        return [frame, first + 1, start,
            {"launchMinimumNs": first + 3, "completedNs": first + 11, "finalizedNs": first + 12},
            {"observedNs": first + 9},
            {"beganNs": first + 4, "metadataLastNs": first + 5,
             "acquiredNs": first + 8, "completedNs": first + 9},
            {"firstNs": first + 6, "lastNs": first + 7}, {"closedNs": first + 10}]

    def adopter(self):
        return [self.frame, *[self.frame.first + i for i in range(20, 27)]]

    def test_frame_derives_only_fixed_original_preparation_limits(self):
        self.assertEqual(self.frame.raw, self.fence.raw)
        self.assertEqual((self.frame.first, self.frame.work, self.frame.final),
                         (1000 * O.NS, 1075 * O.NS, 1120 * O.NS))
        self.assertEqual(self.frame.clock, self.clock)
        self.assertEqual(repr(self.frame), "HistoricalPrelude()")
        self.assertEqual(set(vars(self.frame)), {"raw", "clock", "first", "work", "final"})
        for name in ("now", "deadline", "cancelled", "owner", "last", "budget", "exportSaveAuthority"):
            self.assertFalse(hasattr(self.frame, name))

    def test_frame_is_frozen_and_copies_are_only_equal_data(self):
        with self.assertRaises(FrozenInstanceError):
            self.frame.work += O.NS
        clone = replace(self.frame)
        self.assertIsNot(clone, self.frame)
        self.assertEqual(H.checked(clone), self.frame)
        self.assertEqual(H.chain_minimum(*self.chain(clone)), self.frame.first + 12)

    def test_all_native_clock_data_remains_separate_from_host_admission(self):
        selections = ("desktop-linux-x64", "desktop-windows-x64", "desktop-macos-arm64", "desktop-macos-x64",
                      "full-macos-arm64", "full-macos-x64")
        for selection in selections:
            _, clock, _ = M.model_admission(selection)
            raw = O.encoded(O.prelude(O.clocks.Reading(clock, 0)))
            with self.subTest(selection=selection):
                frame = H.HistoricalPrelude(raw)
                self.assertEqual(frame.clock, clock)
                self.assertEqual((frame.first, frame.work, frame.final), (0, 75 * O.NS, 120 * O.NS))
                self.assertNotIn("selection", vars(frame))

    def test_exact_uint64_last_representable_prelude_has_no_float_rounding(self):
        first = O.clocks.UINT64 - 120 * O.NS
        frame = H.HistoricalPrelude(O.encoded(O.prelude(O.clocks.Reading(self.clock, first))))
        self.assertEqual(frame.first, first)
        self.assertEqual(frame.final, O.clocks.UINT64)
        self.assertEqual(H.chain_minimum(*self.chain(frame)), first + 12)

    def test_prelude_overflow_and_mistyped_first_are_rejected(self):
        for first in (True, -1, O.clocks.UINT64 - 120 * O.NS + 1, 1.0, None):
            row = O.parse(self.frame.raw)
            row["firstNs"] = first
            with self.subTest(first=first), self.assertRaises(ValueError):
                H.HistoricalPrelude(O.encoded(row))

    def test_canonical_bytes_cannot_be_replaced_by_equivalent_json(self):
        row = O.parse(self.frame.raw)
        raws = (self.frame.raw + b" ", json.dumps(row).encode(),
                O.encoded(dict(reversed(list(row.items())))).replace(b'"schema":1', b'"schema":1,"schema":1'),
                bytearray(self.frame.raw), self.frame.raw.decode(), b"[]")
        for raw in raws:
            with self.subTest(kind=type(raw).__name__), self.assertRaises((ValueError, TypeError)):
                H.HistoricalPrelude(raw)

    def test_changed_policy_fields_and_extra_budget_do_not_form_a_history_frame(self):
        for field, value in (("workEndNs", self.frame.work + 1), ("finalEndNs", self.frame.final + 1),
                ("workEndNs", True), ("finalEndNs", float(self.frame.final)), ("schema", True),
                ("scope", "BOOTSTRAP_JOB"), ("budgetAcceptance", "ADMITTED"), ("exportSaveAuthority", True),
                ("jobSeconds", 5400), ("policy", "QUALIFIED")):
            row = O.parse(self.frame.raw)
            row[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                H.HistoricalPrelude(O.encoded(row))

    def test_clock_role_domain_frequency_and_fields_remain_exact(self):
        for field, value in (("role", "windows-x64"), ("domain", "time.monotonic"),
                             ("ticksPerSecond", True), ("ticksPerSecond", 1), ("extra", 0)):
            row = O.parse(self.frame.raw)
            row["clock"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                H.HistoricalPrelude(O.encoded(row))

    def test_snapshot_does_not_observe_or_copy_live_state(self):
        last, before = self.fence.last, self.nanoseconds
        with patch.object(self.fence, "now", side_effect=AssertionError("NO_CLOCK")), \
                patch.object(self.fence, "deadline", side_effect=AssertionError("NO_DEADLINE")), \
                patch.object(self.fence, "cancelled", side_effect=AssertionError("NO_CALLBACK")):
            self.assertEqual(H.snapshot(self.fence), self.frame)
        self.assertEqual((self.fence.last, self.nanoseconds), (last, before))
        self.assertEqual(H.snapshot(copy.copy(self.fence)), self.frame)

    def test_expired_fence_data_does_not_renew_its_live_clock(self):
        self.nanoseconds = self.fence.final
        self.assertEqual(H.snapshot(self.fence), self.frame)
        self.assertEqual(H.chain_minimum(*self.chain()), self.frame.first + 12)
        with self.assertRaisesRegex(O.OriginError, "ORIGINAL_FENCE_EXPIRED"):
            self.fence.now(final=True)
        self.assertGreaterEqual(self.fence.last, self.fence.final)

    def test_snapshot_refuses_incoherent_original_fields_without_touching_clock(self):
        for name, value in (("first", True), ("work", self.fence.work + 1),
                            ("final", self.fence.final + 1), ("raw", self.fence.raw + b" "),
                            ("clock", M.model_admission("desktop-windows-x64")[1])):
            clone = copy.copy(self.fence)
            setattr(clone, name, value)
            before = self.nanoseconds
            with self.subTest(field=name), self.assertRaises(ValueError):
                H.snapshot(clone)
            self.assertEqual(self.nanoseconds, before)
        for other in (self.frame, {}, None):
            with self.assertRaisesRegex(O.OriginError, "NOT_ORIGINAL_PRELUDE"):
                H.snapshot(other)

    def test_unchecked_field_mutation_of_a_frozen_object_is_detected(self):
        for name, value in (("first", True), ("work", self.frame.work + 1), ("final", self.frame.final - 1),
                            ("clock", M.model_admission("desktop-windows-x64")[1])):
            frame = replace(self.frame)
            object.__setattr__(frame, name, value)
            with self.subTest(field=name), self.assertRaises(ValueError):
                H.checked(frame)
        with self.assertRaisesRegex(O.OriginError, "HISTORY_FRAME"):
            H.checked(self.fence)

    def test_all_data_helpers_perform_no_path_environment_clock_or_owner_operations(self):
        chain, adopter = self.chain(), self.adopter()
        with ExitStack() as guards:
            for target, name in ((Path, "resolve"), (Path, "open"), (S.os, "getenv"),
                    (O.clocks, "observe"), (O.time, "monotonic"), (S, "command"),
                    (S.Owner, "__init__"), (S, "admit"), (S, "phase")):
                guards.enter_context(patch.object(target, name, side_effect=AssertionError("DATA_ONLY")))
            frame = H.HistoricalPrelude(self.frame.raw)
            self.assertEqual(H.checked(frame), self.frame)
            self.assertEqual(H.snapshot(self.fence), self.frame)
            self.assertEqual(H.context_return(frame, frame.first), frame.first)
            self.assertIs(H.admission_return(frame, frame.first), True)
            self.assertEqual(H.phase_start(frame, chain[1], chain[2]), chain[2]["startedNs"])
            self.assertEqual(H.chain_minimum(*chain), frame.first + 12)
            self.assertEqual(H.adopter_first(*adopter), frame.first + 26)

    def test_context_lower_bound_is_not_an_admission_upper_bound(self):
        self.assertEqual(H.context_return(self.frame, self.frame.work), self.frame.work)
        with self.assertRaisesRegex(O.OriginError, "ORIGINAL_ADMISSION_RETURN"):
            H.admission_return(self.frame, self.frame.work)
        with self.assertRaises(ValueError):
            H.context_return(self.frame, self.frame.first - 1)

    def test_admission_returns_require_original_integer_work_interval(self):
        for value in (self.frame.first, self.frame.work - 1):
            self.assertIs(H.admission_return(self.frame, value), True)
        for value in (True, -1, self.frame.first - 1, self.frame.work, self.frame.final, O.clocks.UINT64 + 1, 1.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                H.admission_return(self.frame, value)

    def test_phase_cap_is_clamped_to_the_original_not_new_first(self):
        start = {"startedNs": self.frame.work - 1, "workEndNs": self.frame.work, "finalEndNs": self.frame.final}
        self.assertEqual(H.phase_start(self.frame, self.frame.first, start), self.frame.work - 1)
        for name, value in (("startedNs", self.frame.work), ("workEndNs", self.frame.work + 1),
                            ("finalEndNs", self.frame.final + 1), ("workEndNs", float(self.frame.work))):
            with self.subTest(field=name), self.assertRaises(ValueError):
                H.phase_start(self.frame, self.frame.first, {**start, name: value})

    def test_phase_cannot_precede_its_original_admission(self):
        start = self.chain()[2]
        for returned in (True, self.frame.first - 1, start["startedNs"] + 1):
            with self.subTest(returned=returned), self.assertRaises(ValueError):
                H.phase_start(self.frame, returned, start)

    def test_chain_minimum_is_historical_and_does_not_mutate_input_records(self):
        arguments = self.chain()
        before = copy.deepcopy(arguments)
        result = H.chain_minimum(*arguments)
        self.assertEqual(result, self.frame.first + 12)
        self.assertEqual(arguments, before)
        self.assertIs(type(result), int)
        self.assertLess(result, self.frame.work)

    def test_every_historical_chain_time_rejects_boolean_substitution(self):
        fields = ((2, "startedNs"), (3, "launchMinimumNs"), (3, "completedNs"), (3, "finalizedNs"),
                  (4, "observedNs"), (5, "beganNs"), (5, "metadataLastNs"), (5, "acquiredNs"),
                  (5, "completedNs"), (6, "firstNs"), (6, "lastNs"), (7, "closedNs"),
                  (2, "workEndNs"), (2, "finalEndNs"))
        for index, name in fields:
            arguments = self.chain()
            arguments[index][name] = True
            with self.subTest(field=name), self.assertRaises(ValueError):
                H.chain_minimum(*arguments)
        arguments = self.chain(); arguments[1] = True
        with self.assertRaises(ValueError):
            H.chain_minimum(*arguments)

    def test_chain_rejects_reversal_even_if_a_later_time_recovers(self):
        for index, name in ((5, "beganNs"), (5, "metadataLastNs"), (5, "acquiredNs"),
                            (6, "firstNs"), (7, "closedNs"), (3, "finalizedNs")):
            arguments = self.chain()
            arguments[index][name] = self.frame.first
            with self.subTest(field=name), self.assertRaisesRegex(O.OriginError, "ORIGINAL_CLOCK_CHAIN"):
                H.chain_minimum(*arguments)

    def test_birth_is_concurrent_parent_observation_not_the_child_start(self):
        for observed in (self.frame.first + 3, self.frame.first + 11):
            arguments = self.chain(); arguments[4]["observedNs"] = observed
            self.assertEqual(H.chain_minimum(*arguments), self.frame.first + 12)
        for observed in (self.frame.first + 2, self.frame.first + 12):
            arguments = self.chain(); arguments[4]["observedNs"] = observed
            with self.assertRaises(ValueError):
                H.chain_minimum(*arguments)

    def test_original_native_work_and_final_equality_are_expired(self):
        for name, limit in (("completedNs", "workEndNs"), ("finalizedNs", "finalEndNs")):
            arguments = self.chain()
            arguments[3][name] = arguments[2][limit]
            if name == "completedNs":
                arguments[3]["finalizedNs"] = arguments[3][name] + 1
            with self.subTest(field=name), self.assertRaisesRegex(O.OriginError, "ORIGINAL_CLOCK_CHAIN"):
                H.chain_minimum(*arguments)

    def test_adopter_uses_original_first_not_a_future_reader_observation(self):
        arguments = self.adopter()
        self.assertEqual(H.adopter_first(*arguments), self.frame.first + 26)
        arguments[-1] = self.frame.work
        with self.assertRaisesRegex(O.OriginError, "ADOPTION_PREDECESSOR_CLOCK"):
            H.adopter_first(*arguments)

    def test_all_adopter_times_are_typed_and_ordered_within_original_history(self):
        for index in range(1, 8):
            for value in (True, self.frame.first - 1, O.clocks.UINT64 + 1):
                arguments = self.adopter(); arguments[index] = value
                with self.subTest(index=index, value=value), self.assertRaises(ValueError):
                    H.adopter_first(*arguments)

    def test_exact_zero_history_and_equal_valid_observations_are_representable(self):
        frame = H.HistoricalPrelude(O.encoded(O.prelude(O.clocks.Reading(self.clock, 0))))
        self.assertIs(H.admission_return(frame, 0), True)
        self.assertEqual(H.adopter_first(frame, 0, 0, 0, 0, 0, 0, 0), 0)


class HistoryWrapperTests(C.CloseModels):
    def prepared(self, call):
        return S.prepared_content(call.owner, call.private, call.entry.handoff_original,
                                  call.entry.context_original, call.fence)

    def close_after_local_expiry(self, call):
        # The retained roster's repeated failed close fences saturate the
        # unchanged64-error cap. Do not rewind time to manufacture retirement.
        with self.assertRaisesRegex(O.OriginError, "RETIREMENT_UNKNOWN"):
            call.owner.close()
        self.assertTrue(call.owner.unknown)
        self.assertTrue(any(owner is call.owner for owner in S.QUARANTINE))

    def test_pure_minimum_is_followed_by_the_actual_reader_observation(self):
        with self.live() as call:
            original, minima = H.chain_minimum, []
            def minimum(*args):
                value = original(*args); minima.append(value)
                return value
            with patch.object(H, "chain_minimum", side_effect=minimum):
                _, _, result = self.prepared(call)
            self.assertEqual(len(minima), 1)
            self.assertGreater(result["originalChain"]["revalidatedNs"], minima[0])
            self.assertLessEqual(result["originalChain"]["revalidatedNs"], call.fence.last)
            self.assertEqual(result["originalChain"]["budgetAcceptance"], "NOT_ADMITTED")
            self.assertIsNone(call.owner.phase_originals)
            self.assertIs(call.owner.entry_original, call.entry)

    def test_original_work_expiry_still_rejects_before_history(self):
        with self.live() as call:
            self.nanoseconds = call.fence.work
            with patch.object(H, "chain_minimum", side_effect=AssertionError("NO_LATE_HISTORY")), \
                    self.assertRaisesRegex(O.OriginError, "ORIGINAL_FENCE_EXPIRED"):
                self.prepared(call)
            self.assertGreaterEqual(call.fence.last, call.fence.work)
            self.close_after_local_expiry(call)

    def test_passing_history_cannot_replace_a_failed_actual_observation(self):
        with self.live() as call:
            original = H.chain_minimum
            def expire(*args):
                value = original(*args)
                self.nanoseconds = call.fence.work
                return value
            with patch.object(H, "chain_minimum", side_effect=expire), \
                    self.assertRaisesRegex(O.OriginError, "ORIGINAL_FENCE_EXPIRED"):
                self.prepared(call)
            self.assertGreaterEqual(call.fence.last, call.fence.work)
            self.close_after_local_expiry(call)

    def test_cancellation_after_pure_history_is_not_swallowed(self):
        with self.live() as call:
            original, failure = H.chain_minimum, KeyboardInterrupt("SYNTHETIC_HISTORY_CANCEL")
            def minimum(*args):
                result = original(*args)
                call.fence.cancelled = lambda: (_ for _ in ()).throw(failure)
                return result
            with patch.object(H, "chain_minimum", side_effect=minimum), self.assertRaises(KeyboardInterrupt) as caught:
                self.prepared(call)
            self.assertIs(caught.exception, failure)

    def test_local45_expiry_is_still_distinct_from_original75_and120(self):
        with self.live() as call:
            self.nanoseconds = int(call.owner.local_end * O.NS) + 1
            self.assertLess(self.nanoseconds, call.fence.work)
            with self.assertRaises(S.posix.EvidenceError):
                self.prepared(call)
            self.close_after_local_expiry(call)

    def test_source_command_binding_remains_outside_the_pure_temporal_check(self):
        with self.live() as call:
            context_raw = call.entry.context_original
            context = O.parse(context_raw)
            start_raw = (call.path / "service/start.json").read_bytes()
            failure = OSError("SYNTHETIC_SOURCE_COMMAND_RESOLUTION")
            with patch.object(S, "command", side_effect=failure), \
                    patch.object(H, "phase_start", side_effect=AssertionError("NO_TEMPORAL_REPLACEMENT")), \
                    self.assertRaises(OSError) as caught:
                S.start_record(start_raw, context_raw, context, call.path, call.fence)
            self.assertIs(caught.exception, failure)

    def test_original_response_reserialization_still_rejects(self):
        with self.live() as call:
            path = call.path / "service/jobs.json"
            path.write_bytes(path.read_bytes() + b" ")
            with self.assertRaisesRegex(O.OriginError, "ORIGINAL_RESPONSES_CHANGED"):
                self.prepared(call)

    def test_final_close_still_returns_only_its_exact_old_owner_provenance(self):
        with self.live() as call:
            result = self.close(call)
            value = S.check_closed_entry_transition(result)
            self.assertIs(call.owner.entry_close_original, result)
            self.assertEqual(value["productiveOwner"], "NOT_CREATED")
            self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
            self.assertIs(value["exportSaveAuthority"], False)
            self.assertTrue(all(row["attempted"] is True and row["closed"] is True for row in call.owner.resources))


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(cls(name) for cls in (HistoryDataTests, HistoryWrapperTests)
                              for name in sorted(cls.__dict__) if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
