#!/usr/bin/env python3
"""Tiny original-currency/clock models for the NEW PC controller only.

All observations, owners, paths and output checks in these models are synthetic.
They do not execute a native route, validate a key, copy the declared corpus,
open private evidence or replace hosted/native capacity and timing evidence.
"""
from __future__ import annotations

from contextlib import ExitStack
import ctypes
import dataclasses
import io
from pathlib import Path
import stat
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch


GUARDED = False
EFFECTS = []


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen") or \
            GUARDED and event in ("open", "os.listdir", "os.scandir", "os.mkdir", "os.remove", "os.rmdir"):
        EFFECTS.append(event)
        raise AssertionError("PRODUCTIVE_CUSTODY_MODEL_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_productive_custody as PC

CD, O, NS = PC.CD, PC.O, PC.NS
REFUSALS = (ValueError, RuntimeError)
REGISTRIES = ("_PINS", "_STATES", "_CLOCKS", "_CHILDREN", "_VIEWS", "_CAPS", "_ATTEMPTS", "_RESULTS", "_OUTPUTS",
    "_NATIVE_SEEDS", "_FAILURES", "_SPANS", "_OWNER_CLOSES", "_PROVENANCE", "_PIN_FAILURES", "_AUTHORITIES", "_ACKS",
    "_COPIES", "_GROUPS", "_BUDGETS", "_READ_PARTITIONS", "_FILE_READS", "_LINEAGES", "_VALIDATION_INVENTORIES",
    "_SOURCES", "_CRYPTO_FACTS", "_CIPHER_STREAMS", "_CIPHERTEXT_READS", "_COLLECT_HISTORIES")


def guarded(function, *args, **kwargs):
    global GUARDED
    prior, count = GUARDED, len(EFFECTS)
    GUARDED = True
    try:
        return function(*args, **kwargs)
    finally:
        GUARDED = prior
        if len(EFFECTS) != count:
            raise AssertionError("PRODUCTIVE_CUSTODY_MODEL_EFFECT")


def stamp(number, *, size=3, changed=1):
    return ("posix", 7, number, stat.S_IFREG | 0o600, 0, 1, size, 1, changed)


class ModelCase(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for name in REGISTRIES:
            self.install(PC, name, {})
        self.install(PC, "_QUARANTINE", [])
        self.raw, self.local, self.boot = 100 * NS, 1000.0, "b" * 64
        self.action = lambda: None
        self.observations, self.sequence = [], 0
        self.install(PC, "time", SimpleNamespace(monotonic=lambda: self.local, time=lambda: 1.0))
        self.install(O.clocks, "observe", self.observe)
        self.install(PC.C.C, "boot_digest", lambda _role: self.boot)
        self.install(PC, "_environment", lambda _state: None)
        self.install(PC, "_claims", lambda **_kwargs: {})
        self.install(PC, "_fixed_paths", lambda: (("root", ROOT / "model-final"), ("payload", ROOT / "model-final/payload")))

    def install(self, module, name, value):
        self.stack.enter_context(patch.object(module, name, value))
        return value

    def observe(self):
        # Real Reading TYPE, explicitly supplied model clock rather than a host observation.
        identity = O.clocks.ClockIdentity("linux-x64", O.clocks.DOMAINS["linux-x64"], NS)
        value = O.clocks.Reading(identity, self.raw)
        self.observations.append(value)
        return value

    def cancelled(self):
        self.action()

    def check(self, function, *args, **kwargs):
        return guarded(function, *args, **kwargs)

    def refuses(self, function, *args, **kwargs):
        with self.assertRaises(REFUSALS) as caught:
            self.check(function, *args, **kwargs)
        return caught.exception

    def state(self, kind=PC.ParentFinal, *, operation=None):
        self.sequence += 1
        return self.check(PC._new_state, kind, operation or "model-" + str(self.sequence), self.cancelled, PC._EXPORT_PHASES)


class CurrencyClockModels(ModelCase):
    def test_exact_public_field_shapes_and_empty_handles(self):
        expected = {PC.ValidationView: "child role work public_key_raw policy_raw original_match_raw source caps",
            PC.ArchiveView: "child archive recipient role payload output payload_root partitions index lineage caps public_inputs",
            PC.PartitionView: "ordinal group root members map", PC.ExpectedNode: "relative kind bytes sha256 native provenance",
            PC.ChildSourceBinding: "job_id observed_raw event_sha256 context_sha256 start_sha256",
            PC.ParentReturnedCrypto: "output_values fence hard_end_ns", PC.CollectReturn: "output_values fence hard_end_ns"}
        for kind, names in expected.items():
            self.assertEqual(tuple(item.name for item in dataclasses.fields(kind)), tuple(names.split()))
        for kind in (PC.ParentFinal, PC.ChildFinal, PC.ChildArchiveBinding30, PC.CollectPrepared):
            self.assertEqual(dataclasses.fields(kind), ())
            self.refuses(PC._pin, kind())

    def test_actual_first_reference_and_new_equal_clock_observations(self):
        state = self.state()
        saved = PC._CLOCKS[id(state.clock)]
        self.assertIs(saved.first, self.observations[0])
        self.assertIsNot(saved.first.clock, self.observations[-1].clock)
        self.assertEqual(saved.first.clock, self.observations[-1].clock)
        self.assertEqual(self.check(state.clock.now), self.raw)

    def test_raw_backwards_is_sticky_after_repair(self):
        state = self.state()
        self.raw -= 1
        first = self.refuses(state.clock.now)
        self.raw += 1
        self.assertIs(self.refuses(state.clock.now), first)

    def test_local_backwards_precedes_another_raw_observation(self):
        state = self.state()
        count = len(self.observations)
        self.local -= 1.0
        self.refuses(state.clock.now)
        self.assertEqual(len(self.observations), count)

    def test_original_boot_change_refuses(self):
        state = self.state()
        self.boot = "c" * 64
        first = self.refuses(state.clock.now)
        self.boot = "b" * 64
        self.assertIs(self.refuses(state.clock.now), first)

    def test_original_reading_dictionary_mutation_is_sticky(self):
        state = self.state()
        reading = PC._CLOCKS[id(state.clock)].first
        old = reading.nanoseconds
        object.__setattr__(reading, "nanoseconds", old + 1)
        first = self.refuses(state.clock.now)
        object.__setattr__(reading, "nanoseconds", old)
        self.assertIs(self.refuses(state.clock.now), first)

    def test_caught_clock_reentry_poisons_original_clock(self):
        state = self.state()
        failures = []
        def nested():
            try:
                state.clock.now()
            except REFUSALS as error:
                failures.append(error)
        self.action = nested
        first = self.refuses(state.clock.now)
        self.assertIs(first, failures[0])
        self.action = lambda: None
        self.assertIs(self.refuses(state.clock.now), first)

    def test_first_callback_duplicate_attempt_is_already_reserved(self):
        failures = []
        def nested():
            try:
                PC._new_state(PC.ParentFinal, "first-callback", self.cancelled, PC._EXPORT_PHASES)
            except REFUSALS as error:
                failures.append(error)
        self.action = nested
        first = self.refuses(PC._new_state, PC.ParentFinal, "first-callback", self.cancelled, PC._EXPORT_PHASES)
        self.assertIs(first, failures[0])
        self.assertIsNone(PC._ATTEMPTS["first-callback"].handle)

    def test_caught_supplier_replacement_is_not_adopted(self):
        state = self.state()
        original = O.clocks.observe
        self.action = lambda: setattr(O.clocks, "observe", lambda: self.observe())
        first = self.refuses(state.clock.now)
        O.clocks.observe = original
        self.action = lambda: None
        self.assertIs(self.refuses(state.clock.now), first)

    def test_equal_registry_copy_is_not_the_original_registry(self):
        state = self.state()
        original = PC._STATES
        PC._STATES = dict(original)
        first = self.refuses(state.clock.now)
        PC._STATES = original
        self.assertIs(self.refuses(state.clock.now), first)

    def test_phase_transition_shortens_once_without_changing_upper_tuple(self):
        state = self.state()
        basis = PC._CLOCKS[id(state.clock)]
        upper = basis.ends
        PC._update(state, phase_caps=upper)
        self.raw = 120 * NS
        self.check(PC._advance, state.clock, "custody-encrypt")
        self.assertEqual(basis.ends[1], 360 * NS)
        self.assertIs(state.phase_caps, upper)
        self.raw = 150 * NS
        self.check(PC._advance, state.clock, "custody-encrypt-final")
        self.assertEqual(basis.ends[2], 195 * NS)
        self.raw = 160 * NS
        self.check(PC._advance, state.clock, "custody-encrypt-read")
        self.assertEqual(basis.ends[3], 190 * NS)
        self.assertEqual(state.phase_caps[-1], 595 * NS)
        self.assertEqual(basis.first.nanoseconds, 100 * NS)

    def test_read_entry_cannot_borrow_expired_final(self):
        state = self.state()
        self.check(PC._advance, state.clock, "custody-encrypt")
        self.check(PC._advance, state.clock, "custody-encrypt-final")
        self.raw = PC._CLOCKS[id(state.clock)].ends[2]
        self.refuses(PC._advance, state.clock, "custody-encrypt-read")
        self.assertEqual(PC._CLOCKS[id(state.clock)].phase, 2)

    def test_native_resource_lifetime_is_not_retimed_at_transition(self):
        state = self.state()
        basis = PC._CLOCKS[id(state.clock)]
        span = self.check(PC._span, state.clock, basis.ends[1], basis.ends[2], "crypto-native")
        saved = PC._SPANS[id(span)]
        original = saved.final_local
        self.check(PC._advance, state.clock, "custody-encrypt")
        self.check(PC._advance, state.clock, "custody-encrypt-final")
        self.assertEqual(saved.final_local, original)
        self.assertLess(span.final, saved.final)

    def test_proposal_can_only_shorten_original_mapping_once(self):
        state = self.state()
        basis = PC._CLOCKS[id(state.clock)]
        proposal = {"phaseFencesNs": {name: end - NS for (name, _seconds), end in zip(basis.names, basis.ends)},
            "proposedJobEndNs": basis.ends[-1]}
        first, local = basis.first, basis.local
        self.check(PC._shorten_clock, state.clock, proposal)
        self.assertIs(basis.first, first)
        self.assertEqual(basis.local, local)
        self.refuses(PC._shorten_clock, state.clock, proposal)

    def test_distinct_operation_caps_keep_actual_first_and60_240(self):
        state = self.state(PC.ChildFinal)
        PC._update(state, phase_caps=(*PC._CLOCKS[id(state.clock)].ends, 100 * NS, 310 * NS, 355 * NS))
        caps = self.check(PC._operation_caps, state, PC.ValidationCaps)
        self.assertIs(caps.first, self.observations[-1])
        self.assertIs(caps.clock, caps.first.clock)
        self.assertEqual(caps.operationFinishEndNs, 160 * NS)
        self.assertEqual(caps.operationLimitNs, 60 * NS)
        self.raw = 170 * NS
        self.check(PC._advance, state.clock, "custody-encrypt")
        exported = self.check(PC._operation_caps, state, PC.ArchiveCaps)
        self.assertIs(type(exported), PC.ArchiveCaps)
        self.assertIsNot(type(exported), type(caps))
        self.assertEqual(exported.operationLimitNs, 240 * NS)
        self.assertLessEqual(exported.operationFinishEndNs, 310 * NS)

    def test_windows30_reserve_is_inside_same_operation_finish(self):
        state = self.state(PC.ChildFinal)
        PC._update(state, phase_caps=(*PC._CLOCKS[id(state.clock)].ends, 100 * NS, 310 * NS, 355 * NS))
        self.install(PC, "os", SimpleNamespace(name="nt"))
        caps = self.check(PC._operation_caps, state, PC.ValidationCaps)
        self.assertEqual(caps.finishReserveNs, 30 * NS)
        self.assertLessEqual(caps.workEndNs, caps.operationFinishEndNs - 30 * NS)
        self.assertLess(caps.workEndLocal, caps.operationFinishEndLocal - 30)

    def test_completed_operation_checks_do_not_revive_spent_subcap(self):
        state = self.state(PC.ChildFinal)
        PC._update(state, phase_caps=(*PC._CLOCKS[id(state.clock)].ends, 100 * NS, 310 * NS, 355 * NS))
        caps = self.check(PC._operation_caps, state, PC.ValidationCaps)
        self.raw = 120 * NS
        completed = self.check(PC._complete_operation, state, caps, object())
        self.raw = 170 * NS
        count = len(self.observations)
        self.check(PC._operation_current, state, caps, completed)
        self.assertEqual(len(self.observations), count)

    def test_equal_dataclass_field_replacement_is_sticky(self):
        original = bytes(bytearray(b"original model bytes"))
        value = PC._track(PC.ChildSourceBinding("a" * 32, original, "a" * 64, "b" * 64, "c" * 64))
        replaced = bytes(bytearray(original))
        self.assertIsNot(replaced, original)
        object.__setattr__(value, "observed_raw", replaced)
        first = self.refuses(PC._pin, value)
        object.__setattr__(value, "observed_raw", original)
        self.assertIs(self.refuses(PC._pin, value), first)

    def test_builtin_bound_methods_are_pinned_by_descriptor_self_and_slot(self):
        stream = io.BytesIO(b"tiny")
        self.addCleanup(stream.close)
        methods = self.check(PC._methods, stream, ("read", "close"))
        self.check(PC._methods_current, stream, methods)
        stream.read = lambda _count: b""
        self.refuses(PC._methods_current, stream, methods)

    def test_fake_known_close_data_does_not_register_an_owner(self):
        value = PC._track(PC._OwnerClose(object(), object(), (), b"{}\n", (), ()))
        self.refuses(PC._check_owner_close, value)

    def test_full_native_alias_union_rejects_cross_path_hardlinks(self):
        state = SimpleNamespace(copied=(), readback=(), root=None, index=None, observations=(), accounting=(), lineage=None,
            union=((ROOT / "model-a", stamp(1)), (ROOT / "model-b", stamp(1))))
        self.refuses(PC._check_union, state)

    def test_full_native_alias_union_rejects_same_path_metadata_change(self):
        state = SimpleNamespace(copied=(), readback=(), root=None, index=None, observations=(), accounting=(), lineage=None,
            union=((ROOT / "model-a", stamp(1)), (ROOT / "model-a", stamp(1, changed=2))))
        self.refuses(PC._check_union, state)

    def test_full_native_alias_union_accepts_same_original_observation(self):
        state = SimpleNamespace(copied=(), readback=(), root=None, index=None, observations=(), accounting=(), lineage=None,
            union=((ROOT / "model-a", stamp(1)), (ROOT / "model-a", stamp(1)), (ROOT / "model-b", stamp(2))))
        self.assertEqual(len(self.check(PC._check_union, state)), 2)

    def test_foreign_final_result_cannot_supply_output_currency(self):
        result = PC.ParentReturnedCrypto(tuple((name, "a" * 64) for name in CD.EXPORT_OUTPUT_FIELDS), object(), 1)
        self.refuses(PC.checked_final_export_return, result)
        self.refuses(PC.checked_final_collect_return, result)


class OutputFenceModels(ModelCase):
    """Only fence sequencing is real here; completed-custody checking is modeled."""
    def setUp(self):
        super().setUp()
        self.hard = 1000000
        self.output_action = lambda: None
        self.output_checks = 0
        self.fence = PC._FinalOutputFence()
        self.result = PC.ParentReturnedCrypto(tuple((name, "a" * 64) for name in CD.EXPORT_OUTPUT_FIELDS), self.fence, self.hard)
        self.output = PC._track(PC._OutputState(object(), self.fence, self.result, self.hard))
        PC._OUTPUTS[id(self.fence)] = self.output
        self.model = SimpleNamespace(clock=SimpleNamespace(now=self.output_now), phase_caps=(self.hard,))
        self.install(PC, "_final_return_passive", self.passive)

    def passive(self, result, *, collect):
        PC._pin(self.output)
        failure = PC._FAILURES.get(id(self.output))
        if failure is not None:
            raise failure[1]
        if result is not self.result or collect:
            raise O.OriginError("MODEL_ORIGINAL_RESULT")
        self.output_checks += 1
        return self.model

    def output_now(self, *, final, limit):
        if final is not True or limit != self.hard:
            raise AssertionError("MODEL_OUTPUT_EXACT_FENCE")
        self.output_action()
        return 1

    def test_output_append_checks_do_not_consume_parent_two_use_allowance(self):
        for _number in range(5):
            self.assertEqual(self.check(self.fence.now, final=True, limit=self.hard), 1)
        self.assertEqual(self.output_checks, 10)

    def test_output_wrong_original_hard_end_is_sticky(self):
        first = self.refuses(self.fence.now, final=True, limit=self.hard + 1)
        self.assertIs(self.refuses(self.fence.now, final=True, limit=self.hard), first)

    def test_output_caught_reentry_poison_is_not_repaired(self):
        failures = []
        def nested():
            try:
                self.fence.now(final=True, limit=self.hard)
            except REFUSALS as error:
                failures.append(error)
        self.output_action = nested
        first = self.refuses(self.fence.now, final=True, limit=self.hard)
        self.assertIs(first, failures[0])
        self.output_action = lambda: None
        self.assertIs(self.refuses(self.fence.now, final=True, limit=self.hard), first)

    def test_output_post_callback_currency_is_checked(self):
        self.output_action = lambda: object.__setattr__(self.output, "hard_end", self.hard + 1)
        first = self.refuses(self.fence.now, final=True, limit=self.hard)
        object.__setattr__(self.output, "hard_end", self.hard)
        self.output_action = lambda: None
        self.assertIs(self.refuses(self.fence.now, final=True, limit=self.hard), first)


if __name__ == "__main__":
    unittest.main(failfast=True)
