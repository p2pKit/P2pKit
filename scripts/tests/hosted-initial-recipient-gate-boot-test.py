#!/usr/bin/env python3
"""New gate boot-link models only; not hosted/native continuity or custody.

The maintained native fixture supplies tiny ordinary-UID files and explicit
source/Git/HTTP/native/clock models. Its older methods and accepted reader do
not run. Kernel boot calls are synthetic; source and every deadline stay real.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


spec = importlib.util.spec_from_file_location("gate_boot_native_models",
    Path(__file__).with_name("hosted-initial-recipient-native-test.py"))
F = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = F
spec.loader.exec_module(F)
N, S, O, I, C = F.N, F.S, F.O, F.I, F.N.continuity


class GateBootControls(unittest.TestCase):
    def setUp(self):
        self.fx = F.NativeModels("runTest")
        self.addCleanup(self.fx.doCleanups)
        self.fx.setUp()

    def sibling(self):
        return self.fx.path.with_name(self.fx.path.name + "-handoff")

    def assert_known(self, owner):
        self.assertIs(owner.closed, True)
        self.assertIs(owner.unknown, False)
        for row in owner.resources:
            self.assertIs(row["attempted"], True)
            self.assertIs(row["closed"], True)

    def test_original_boot_precedes_queries_and_binds_closed_handoff_and_two_final_checks(self):
        query = self.fx.before_query
        def before_query(path):
            self.assertTrue(self.fx.gate_boot_calls)
            return query(path)
        self.fx.before_query = before_query
        original = N._prepare_originals(self.fx.cancelled)
        self.assertEqual(len(self.fx.gate_boot_calls), 3)  # Original, before close, after actual close.
        anchor = N._gate_return(original)[2]
        self.assertEqual(len(anchor), 21)
        self.assertEqual(anchor[20], self.fx.gate_boot)
        self.assertEqual(anchor[0].boot, self.fx.gate_boot)
        self.assert_known(original._owner)
        self.assertLess(self.fx.gate_boot_calls[0][1], original._fence.work)
        value, fence, limit = N._retain_gate_handoff(original)
        raw = (self.sibling() / N.GATE_HANDOFF_FILE).read_bytes()
        handoff = O.parse(raw)
        self.assertEqual(handoff["bootDigest"], anchor[20])
        self.assertEqual(handoff["clock"], O.clock_value(original._fence.clock))
        self.assertEqual((len(handoff["inventory"]["files"]), len(handoff["inventory"]["directories"])), (281, 58))
        self.assertEqual(handoff["writerReturn"], "PENDING_OWNER_CLOSE")
        self.assertEqual(handoff["originalStepOutcome"], "NOT_OBSERVED")
        self.assertEqual(value["gateHandoffSha256"], O.digest(raw))
        self.assertEqual(set(line.split("=")[0] for line in self.fx.output.read_text().splitlines()),
            {"initialOriginalsSha256", "gateHandoffSha256"})
        calls = len(self.fx.gate_boot_calls)
        self.assertLess(fence.now(final=True, limit=limit), limit)
        self.assertLess(fence.now(final=True, limit=limit), limit)
        self.assertEqual(len(self.fx.gate_boot_calls), calls + 2)
        with self.assertRaisesRegex(I.AdmissionError, "GATE_FINAL_OUTPUT_ONLY"):
            fence.now(final=True, limit=limit)

    def test_invalid_original_boot_refuses_before_private_files_queries_or_registration(self):
        self.fx.gate_boot = True
        owners, close = [], S.Owner.close
        def closed(owner):
            close(owner)
            owners.append(owner)
        with patch.object(S.Owner, "close", closed), self.assertRaisesRegex(I.AdmissionError, "GATE_BOOT_CHANGED"):
            N._prepare_originals(self.fx.cancelled)
        self.assertEqual(len(owners), 1)
        self.assert_known(owners[0])
        self.assertFalse(self.fx.path.exists())
        self.assertEqual(self.fx.queries, [])
        self.assertFalse(N._GATE_RETURNS)
        self.assertFalse(N._PREPARED_RETURNS)
        self.assertEqual(self.fx.output.read_bytes(), b"")

    def test_boot_changed_after_acquisition_refuses_and_completes_original_cleanup(self):
        capture, owners = N._capture_gate_originals, []
        def changed(*args):
            result = capture(*args)
            owners.append(args[0])
            self.fx.gate_boot = "b" * 64
            return result
        with patch.object(N, "_capture_gate_originals", changed), self.assertRaisesRegex(I.AdmissionError, "GATE_BOOT_CHANGED"):
            N._prepare_originals(self.fx.cancelled)
        self.assertEqual(len(owners), 1)
        self.assert_known(owners[0])
        self.assertFalse(N._GATE_RETURNS)
        self.assertFalse(N._PREPARED_RETURNS)
        self.assertFalse(self.sibling().exists())
        self.assertEqual(self.fx.output.read_bytes(), b"")

    def test_boot_changed_during_actual_parent_close_cannot_register_a_success(self):
        close, owners = S.Owner.close, []
        def changed(owner):
            close(owner)
            if hasattr(owner, "_gate_capture_anchor"):
                owners.append(owner)
                self.fx.gate_boot = "b" * 64
        with patch.object(S.Owner, "close", changed), self.assertRaisesRegex(I.AdmissionError, "GATE_BOOT_CHANGED"):
            N._prepare_originals(self.fx.cancelled)
        self.assertEqual(len(owners), 1)
        self.assert_known(owners[0])
        self.assertFalse(N._GATE_RETURNS)
        self.assertFalse(N._PREPARED_RETURNS)
        self.assertEqual(self.fx.output.read_bytes(), b"")

    def test_mutated_capture_boot_cannot_replace_independently_retained_original(self):
        original = N._prepare_originals(self.fx.cancelled)
        entry = N._gate_return(original)
        capture = entry[2][0]
        class EqualText(str):
            def __eq__(self, _other):
                return True
        for replacement in ("b" * 64, True, EqualText(self.fx.gate_boot)):
            object.__setattr__(capture, "boot", replacement)
            try:
                with self.subTest(kind=type(replacement).__name__), self.assertRaisesRegex(I.AdmissionError, "GATE_CAPTURE_CHANGED"):
                    N._gate_return(original)
            finally:
                object.__setattr__(capture, "boot", self.fx.gate_boot)
        self.assertIs(N._gate_return(original), entry)
        self.assertEqual(self.fx.output.read_bytes(), b"")

    def test_changed_boot_before_handoff_allocation_consumes_one_shot_without_output(self):
        original = N._prepare_originals(self.fx.cancelled)
        self.fx.gate_boot = "b" * 64
        with self.assertRaisesRegex(I.AdmissionError, "GATE_BOOT_CHANGED"):
            N._retain_gate_handoff(original)
        self.assertFalse(self.sibling().exists())
        self.assertEqual(self.fx.output.read_bytes(), b"")
        self.fx.gate_boot = "a" * 64
        with self.assertRaisesRegex(I.AdmissionError, "GATE_HANDOFF_ALREADY_CONSUMED"):
            N._retain_gate_handoff(original)

    def test_changed_boot_during_handoff_write_closes_new_owner_and_blocks_hashes(self):
        original = N._prepare_originals(self.fx.cancelled)
        write, owners = S.Owner.write, []
        def changed(owner, parent, name, value, **kwargs):
            raw = write(owner, parent, name, value, **kwargs)
            if name == N.GATE_HANDOFF_FILE:
                owners.append(owner)
                self.fx.gate_boot = "b" * 64
            return raw
        with patch.object(S.Owner, "write", changed), self.assertRaisesRegex(I.AdmissionError, "GATE_BOOT_CHANGED"):
            N._retain_gate_handoff(original)
        self.assertEqual(len(owners), 1)
        self.assert_known(owners[0])
        self.assertTrue((self.sibling() / N.GATE_HANDOFF_FILE).is_file())  # Provisional bytes, not successful Step.
        self.assertEqual(self.fx.output.read_bytes(), b"")
        self.fx.gate_boot = "a" * 64
        with self.assertRaisesRegex(I.AdmissionError, "GATE_HANDOFF_ALREADY_CONSUMED"):
            N._retain_gate_handoff(original)

    def test_changed_boot_at_final_output_is_sticky_after_provisional_hash_append(self):
        value, fence, limit = N._retain_gate_handoff(N._prepare_originals(self.fx.cancelled))
        self.assertEqual(len(self.fx.output.read_text().splitlines()), 2)
        self.fx.gate_boot = "b" * 64
        with self.assertRaisesRegex(I.AdmissionError, "GATE_BOOT_CHANGED") as first:
            fence.now(final=True, limit=limit)
        self.fx.gate_boot = "a" * 64
        with self.assertRaises(I.AdmissionError) as second:
            fence.now(final=True, limit=limit)
        self.assertIs(second.exception, first.exception)
        self.assertIs(value["exportSaveAuthority"], False)

    def test_added_boot_observation_stays_inside_original_WORK75_FINAL120_and_LOCAL(self):
        began = self.fx.fixture.ns
        for final in (False, True):
            self.fx.fixture.ns = began
            first = O.clocks.observe()
            frame = O.Fence(O.prelude(first), minimum=first.nanoseconds, cancelled=lambda: None)
            local = frame.deadline(O.PRELUDE_SECONDS, final=True)
            def expired(_role):
                self.fx.fixture.ns = frame.final if final else frame.work
                return "a" * 64
            with self.subTest(final=final), patch.object(C, "boot_digest", side_effect=expired), \
                    self.assertRaises((O.OriginError, S.posix.EvidenceError)):
                N._gate_boot_observe(frame, local, [], "a" * 64, final=final)
        self.fx.fixture.ns = began
        first = O.clocks.observe()
        frame = O.Fence(O.prelude(first), minimum=first.nanoseconds, cancelled=lambda: None)
        local = frame.deadline(O.PRELUDE_SECONDS, final=True)
        later = patch.object(N.time, "monotonic", return_value=local)
        def expired_local(_role):
            later.start()
            return "a" * 64
        try:
            with patch.object(C, "boot_digest", side_effect=expired_local), self.assertRaises(S.posix.EvidenceError):
                N._gate_boot_observe(frame, local, [], "a" * 64)
        finally:
            later.stop()

    def test_cancellation_during_original_boot_still_closes_owner_and_never_starts_queries(self):
        close, owners = S.Owner.close, []
        def cancelled(_role):
            self.fx.cancelled.append(15)
            return "a" * 64
        def closed(owner):
            close(owner)
            owners.append(owner)
        with patch.object(C, "boot_digest", side_effect=cancelled), patch.object(S.Owner, "close", closed), \
                self.assertRaises(KeyboardInterrupt):
            N._prepare_originals(self.fx.cancelled)
        self.assertEqual(len(owners), 1)
        self.assert_known(owners[0])
        self.assertEqual(self.fx.queries, [])
        self.assertFalse(N._GATE_RETURNS)
        self.assertFalse(N._PREPARED_RETURNS)
        self.assertEqual(self.fx.output.read_bytes(), b"")

    def test_boot_supplier_cannot_lower_saved_RAW_with_a_replaced_fence_high_water(self):
        began = self.fx.fixture.ns
        for final in (False, True):
            self.fx.fixture.ns = began
            first = O.clocks.observe()
            frame = O.Fence(O.prelude(first), minimum=first.nanoseconds, cancelled=lambda: None)
            local = frame.deadline(O.PRELUDE_SECONDS, final=True)
            unchanged_local = self.fx.fixture.ns / O.NS
            def lower(_role):
                frame.last -= 10000
                self.fx.fixture.ns = frame.last  # Next RAW adds1000, below pre-boot RAW.
                return "a" * 64
            with self.subTest(final=final), patch.object(N.time, "monotonic", return_value=unchanged_local), \
                    patch.object(C, "boot_digest", side_effect=lower), \
                    self.assertRaisesRegex(O.clocks.ClockError, "JOB_CLOCK_BACKWARDS"):
                N._gate_boot_observe(frame, local, [], "a" * 64, final=final, minimum=first.nanoseconds)

        self.fx.fixture.ns = began
        original = N._prepare_originals(self.fx.cancelled)
        _value, output, limit = N._retain_gate_handoff(original)
        self.assert_known(original._owner)
        unchanged_local = self.fx.fixture.ns / O.NS
        previous = original._fence.last
        def lower_handoff(_role):
            original._fence.last -= 10000
            self.fx.fixture.ns = original._fence.last
            return "a" * 64  # Same boot, no permission to accept backwards RAW.
        with patch.object(N.time, "monotonic", return_value=unchanged_local), \
                patch.object(C, "boot_digest", side_effect=lower_handoff), \
                self.assertRaisesRegex(O.clocks.ClockError, "JOB_CLOCK_BACKWARDS") as first:
            output.now(final=True, limit=limit)
        self.assertLess(original._fence.last, previous)
        self.fx.fixture.ns = previous + 10000
        with self.assertRaises(O.clocks.ClockError) as second:
            output.now(final=True, limit=limit)
        self.assertIs(second.exception, first.exception)
        self.assertEqual(len(self.fx.output.read_text().splitlines()), 2)  # Provisional, not Step success.

    def test_worker_preparation_does_not_acquire_or_invent_gate_boot_authority(self):
        self.fx.choose("worker", "desktop-linux-x64")
        with patch.object(C, "boot_digest", side_effect=AssertionError("UNEXPECTED_GATE_BOOT_FOR_WORKER")):
            original = N._prepare_originals(self.fx.cancelled)
        self.assert_known(original._owner)
        self.assertIsNotNone(original.identity)
        self.assertFalse(N._GATE_CAPTURES)
        self.assertFalse(N._GATE_RETURNS)
        self.assertEqual(self.fx.gate_boot_calls, [])


if __name__ == "__main__":
    unittest.main(failfast=True)
