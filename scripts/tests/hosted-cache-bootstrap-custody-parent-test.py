#!/usr/bin/env python3
"""Focused third-parent controls, NOT native/bootstrap execution evidence.

Only historical fixture setUp/cleanup is composed, never historical test methods.
Upstream entry/recipient/initializer/stage/seed returns and admission are explicit
typed MODELS. The changed coordinator, third parent/window/file owner and actual
approved reservation leaf execute on tiny ordinary-UID POSIX data. No old leaf,
canonical initializer, generated command, native query, provider or download runs.
"""
from __future__ import annotations

import ast
from dataclasses import replace
import importlib.util
import inspect
import os
from pathlib import Path
import signal
import sys
import textwrap
from types import SimpleNamespace
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("custody_parent_supplied_data_fixtures",
    Path(__file__).with_name("hosted-cache-bootstrap-custody-test.py"))
H = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = H
spec.loader.exec_module(H)
C, B, F, O, NS = H.C, H.B, H.F, H.O, H.NS
S = H.FIXTURES.S


class FalseyFailure(RuntimeError):
    def __bool__(self):
        return False


class CustodyParentModels(unittest.TestCase):
    def setUp(self):
        self.h = H.ReservationModels()
        self.addCleanup(self.h.doCleanups)
        self.h.setUp()
        self.f, self.stack = self.h.f, self.h.f.stack
        for module, name in ((S, "_ENTRY_ATTEMPTS"), (S, "_RECIPIENT_ATTEMPTS"), (S, "_INITIALIZER_ATTEMPTS"),
                             (S, "_PARENT_CONTROLS"), (S, "_STAGING_ATTEMPTS")):
            self.stack.enter_context(patch.object(module, name, {}))
        for module, name in ((S, "QUARANTINE"), (S.query, "QUARANTINE"), (S.diagnostics, "_QUARANTINE")):
            self.stack.enter_context(patch.object(module, name, []))
        self.stack.enter_context(patch.object(S, "ROOT", self.f.root))
        self.events, self.sequences, self.old_parents = [], [], []
        self.on_read = self.on_admit = self.after_seed = lambda parent: None
        self.callback = lambda: None
        self.old_graph = None
        self.make_upstream(reserve=True)
        self.actual_phase = S._run_staging_phase
        self.actual_leaf = C.reserve_configuration
        self.stack.enter_context(patch.object(S, "_capture_staging_initializer", side_effect=self.model_initializer_capture))
        self.stack.enter_context(patch.object(S, "_run_staging_phase", side_effect=self.phase_dispatch))
        self.stack.enter_context(patch.object(S._StagingPhaseParent, "read_originals", lambda parent: self.model_read(parent)))
        self.stack.enter_context(patch.object(S._StagingPhaseParent, "admit", lambda parent: self.model_admit(parent)))
        self.stack.enter_context(patch.object(S._StagingPhaseParent, "host", side_effect=AssertionError("NO_ACTUAL_HOST_PREFIX")))
        self.leaf_calls = self.stack.enter_context(patch.object(C, "reserve_configuration", wraps=self.actual_leaf))
        self.addCleanup(self.close_test_pins)

    @staticmethod
    def poison(*_args, **_kwargs):
        raise AssertionError("NO_CLOSED_PREDECESSOR_METHOD")

    def register_upstream(self, parent, registry, key, record):
        registry[key] = record
        control = S._ParentControl(parent, registry, key, record)
        S._register_parent_control(control)
        S._PARENT_CONTROLS[id(parent)] = control

    def make_upstream(self, *, reserve):
        # These typed records deliberately do NOT represent real native calls.
        attempt = S._EntryAttempt(object(), ())
        attempt.state = "COMPLETE"
        entry = S.NewEntryTransition(b"MODELED_NEW_ENTRY_NOT_EXECUTED", attempt, 1, 2, 3)
        attempt.result = entry
        S._ENTRY_ATTEMPTS[id(attempt.transition)] = (attempt.transition, attempt, attempt.originals, None)
        self.entry, self.attempt = entry, attempt
        self.recipient = S._RecipientParent(entry, ())
        self.recipient.state = "HANDED_OFF"
        record = (entry, self.recipient, self.recipient.originals, None, True, True, reserve)
        self.register_upstream(self.recipient, S._RECIPIENT_ATTEMPTS, id(entry), record)
        self.initializer = S._InitializerParent(entry, ())
        self.initializer.state = "COMPLETE"
        self.initializer.result = S.InitializationPrefix(self.f.originals.initializer_closed_raw,
            b"MODELED_PENDING_NOT_EXECUTED", (), self.f.originals.initializer_checked_ns)
        record = (entry, self.initializer, self.initializer.originals, None, object(), None)
        self.register_upstream(self.initializer, S._INITIALIZER_ATTEMPTS, id(self.recipient), record)

    def model_initializer_capture(self, initializer, returned):
        self.assertIs(initializer, self.initializer)
        S.require(returned is initializer.result, "MODEL_NOT_ORIGINAL_INITIALIZER_RETURN")
        sequence = S._STAGING_ATTEMPTS[id(initializer)][2]
        self.sequences.append(sequence)
        registries = (S._ENTRY_ATTEMPTS, S._RECIPIENT_ATTEMPTS, S._INITIALIZER_ATTEMPTS, S._PARENT_CONTROLS,
            self.attempt, S._entry_attempt_record(self.attempt), S._parent_originals(initializer),
            S._parent_originals(self.recipient))
        graph = S._StagingClosedGraph.capture(initializer, returned, registries)
        paths = (self.f.original, self.f.original.with_name(self.f.original.name + "-adoption"),
                 self.f.original.with_name(self.f.original.name + "-entry"), self.f.session)
        return graph, self.f.originals, B._capture(self.f.originals), (), paths, (lambda: self.callback(),), registries

    def model_closed_phase(self, sequence, previous, name):
        supplied = self.h.staged
        if name == "dependency-stage":
            leaf = supplied.stage_leaf
            raw, checked = supplied.stage_raw, F.record(supplied.raw)["predecessorCheckedNs"]
            checked_local = 500.15
            result = S._StagingPhaseReturn(raw, leaf, checked, checked_local)
            pin = (previous.raw, previous.checked_ns, self.f.originals.initializer_checked_local)
            graph = None
        else:
            self.assertEqual(name, "empty-seed")
            leaf, raw, checked, checked_local = supplied.seed_leaf, supplied.raw, supplied.checked_ns, supplied.checked_local
            result = S.StagingPrefix(raw, previous.raw, previous.leaf, leaf, checked, checked_local)
            pin = (previous.raw, previous.checked_ns, previous.checked_local)
            graph = S._StagingClosedGraph.capture(self.old_parents[0], S._staging_frame(self.old_parents[0]), previous)
        parent = S._StagingPhaseParent(sequence, name, previous)
        S._register_staging_phase(parent, pin, graph)
        window_data = F.record(leaf.raw)["window"]
        first = O.clocks.Reading(self.f.clock, window_data["firstNs"])
        phase = B.PhaseStart(first, leaf.local_started)
        limits = S._StagingLimits(B._clock(first.clock), first.nanoseconds, window_data["softEndNs"],
            window_data["hardEndNs"], leaf.local_started, leaf.local_started + (90 if name == "empty-seed" else 120),
            leaf.local_started + 120)
        window, callback = S._StagingWindow(parent), self.poison
        S._update_staging_frame(parent, first=first, phase_start=phase, phase_pin=B._capture_phase(phase),
            limits=limits, window=window, callback=callback, last=checked, local_last=checked_local)
        owner = S._StagingFileOwner(limits.local_hard, window, first=first, cancelled=callback)
        # Explicit supplied CLOSED model, not an observed old owner retirement.
        owner.closed = True
        for method in ("end", "close", "close_one", "read", "acquire"):
            setattr(owner, method, self.poison)
        for method in ("now", "deadline"):
            object.__setattr__(window, method, self.poison)
        S._update_staging_frame(parent, owner=owner,
            owner_bindings=(owner.resources, owner.errors, owner.admissions, owner.local_end),
            state="COMPLETE", close_roster=(), leaf=leaf, leaf_pin=B._capture_evidence(leaf), result=result)
        parent.first, parent.phase_start, parent.window, parent.callback = first, phase, window, callback
        parent.owner, parent.state, parent.leaf, parent.result = owner, "COMPLETE", leaf, result
        self.old_parents.append(parent)
        self.events.append(("modeled-return", name))
        return result

    def phase_dispatch(self, sequence, previous, name):
        if name != "custody-prepare":
            result = self.model_closed_phase(sequence, previous, name)
            if name == "empty-seed":
                self.old_graph = S._StagingClosedGraph.capture(*self.old_parents,
                    *(S._staging_frame(parent) for parent in self.old_parents), result)
                self.after_seed(self.old_parents[-1])
            return result
        self.events.append(("actual-third-parent", name))
        return self.actual_phase(sequence, previous, name)

    def model_read(self, parent):
        parent.live().end()
        self.events.append(("modeled-original-read", parent.name))
        self.on_read(parent)
        parent.live().end()

    def model_admit(self, parent):
        frame = parent.check()
        self.events.append(("modeled-admission", parent.name, frame.window.deadline(75), frame.window.deadline(120)))
        self.on_admit(parent)
        parent.live().end()

    def sequence(self):
        return self.sequences[-1]

    def parent(self):
        return S._staging_sequence_frame(self.sequence()).phases[-1]

    def run_parent(self):
        return S._stage_after_initialization(self.initializer, self.initializer.result)

    def failed(self, reason=None, *, kind=Exception, unchanged=True):
        assertion = self.assertRaises(kind) if reason is None else self.assertRaisesRegex(kind, reason)
        with assertion as caught:
            self.run_parent()
        self.assertEqual(self.sequence().state, "FAILED")
        self.assertIs(self.sequence().original, caught.exception)
        # Rejected public aliases need not be cleared. Only the private result
        # and the absence of a successful return can establish nonpublication.
        self.assertIsNone(S._staging_sequence_frame(self.sequence()).result)
        if unchanged and self.old_graph is not None:
            self.old_graph.checked()
        return caught.exception

    def close_test_pins(self):
        # Test-owned tiny descriptor cleanup only; never rehabilitate UNKNOWN.
        for sequence in self.sequences:
            for parent in S._staging_sequence_frame(sequence).phases:
                for pin in reversed(S._staging_frame(parent).resources):
                    resource = pin[2]
                    if isinstance(resource, (F.PosixFile, F._PosixDirectory)) and not resource.closed:
                        try:
                            resource.close()
                        except BaseException:
                            pass

    def test_third_parent_reserves_with_exact_originals_one_window_and_known_close(self):
        result = self.run_parent()
        parent, sequence = self.parent(), self.sequence()
        frame, saved = S._staging_frame(parent), S._staging_sequence_frame(sequence)
        self.assertIs(type(result), S.ConfigurationCustodyPrefix)
        self.assertIs(parent.result, result)
        self.assertIs(saved.result, result)
        self.assertIs(sequence.result, result)
        self.assertEqual(sequence.state, "COMPLETE")
        self.assertEqual(saved.plan, ("dependency-stage", "empty-seed", "custody-prepare"))
        self.assertEqual(tuple(p.name for p in saved.phases), saved.plan)
        self.assertIs(result.staged, self.old_parents[1].result)
        self.assertIs(result.custody_leaf, frame.leaf)
        self.leaf_calls.assert_called_once_with(frame.owner, self.f.originals, frame.phase_start, frame.staged)
        self.assertIs(frame.staged.stage_leaf, result.staged.stage_leaf)
        self.assertIs(frame.staged.seed_leaf, result.staged.seed_leaf)
        self.assertTrue(all(frame.owner is not p.owner and frame.window is not p.window for p in self.old_parents))
        self.assertEqual(frame.limits.hard, frame.limits.first + 120 * NS)
        self.assertEqual(frame.limits.soft, frame.limits.hard)
        self.assertEqual(frame.limits.local_soft, frame.limits.local_hard)
        self.assertGreaterEqual(frame.limits.first, result.staged.checked_ns)
        self.assertGreaterEqual(frame.limits.local_start, result.staged.checked_local)
        self.assertGreaterEqual(result.checked_ns, frame.leaf.checked_ns)
        self.assertGreaterEqual(result.checked_local, frame.leaf.checked_local)
        self.assertTrue(frame.owner.closed)
        self.assertFalse(frame.owner.unknown)
        self.assertIsNone(frame.original)
        self.assertTrue(all(row[3] and row[4] for row in frame.resources))
        self.assertEqual(frame.handlers, frame.restored)
        self.old_graph.checked()  # Legal coordinator advancement must not freeze its whole dict.
        target, request = self.f.session / "custody-prepare-parent", self.f.session / "configuration-custody/request.json"
        self.assertEqual(request.read_bytes(), frame.leaf.request_raw)
        self.assertEqual((target / "request-original.json").read_bytes(), frame.leaf.request_raw)
        self.assertEqual((target / "leaf-evidence.json").read_bytes(), frame.leaf.raw)
        self.assertFalse((target / "staging-original.json").exists())
        self.assertEqual({p.name for p in target.iterdir()}, {"request-original.json", "leaf-evidence.json", "pending.json"})
        self.assertEqual(tuple((request.parent / "retained").iterdir()), ())
        self.assertEqual(tuple((self.f.state / "evidence").iterdir()), ())
        self.assertEqual(tuple((self.f.state / "cancellations").iterdir()), ())
        self.assertEqual({p.name for p in self.f.home.iterdir()}, {"gradle.properties"})
        self.assertEqual(tuple(self.f.restore.iterdir()), ())
        for raw in (result.raw, frame.pending_raw, frame.leaf.raw, frame.leaf.request_raw):
            value = F.record(raw)
            self.assertIs(value["nextPhaseAuthority"], False)
            self.assertIs(value["exportSaveAuthority"], False)
            self.assertEqual(value["budgetAcceptance"], "NOT_ADMITTED")
            self.assertEqual(value["testAcceptance"], "NOT_PERFORMED")
        self.assertEqual(F.record(result.raw)["phase"], "custody-prepare")
        self.assertEqual(F.record(result.raw)["scope"], "BOOTSTRAP_CONFIGURATION_CUSTODY_PARENT_CLOSED_NO_EXECUTION_V1")

    def intent_probe(self, operation, expected):
        transition, first = object(), FalseyFailure("STOP_BEFORE_ANY_RECIPIENT_OWNER")
        with patch.object(S, "check_new_entry_transition"), \
                patch.object(S, "_recipient_predecessor_pins", return_value=((), ())), \
                patch.object(S._RecipientPredecessorGraph, "capture", return_value=object()), \
                patch.object(S, "_RecipientParentWindow", side_effect=first), \
                self.assertRaises(FalseyFailure) as caught:
            operation(transition)
        self.assertIs(caught.exception, first)
        row = S._RECIPIENT_ATTEMPTS[id(transition)]
        self.assertEqual(len(row), 7)
        self.assertEqual(row[4:], expected)
        self.assertTrue(all(type(value) is bool for value in row[4:]))
        self.assertIsNone(row[3])
        self.assertIs(row[1].original, first)
        return transition

    def test_existing_wrappers_keep_exact_signatures_and_reservation_false(self):
        for operation, expected in ((S.run_recipient_after_entry, (False, False, False)),
                (S.initialize_after_entry, (True, False, False)), (S.stage_after_entry, (True, True, False))):
            with self.subTest(operation=operation.__name__):
                self.assertEqual(list(inspect.signature(operation).parameters), ["transition"])
                self.intent_probe(operation, expected)
        self.assertEqual(len(S._parent_originals(self.initializer)[4]), 6)

    def test_new_wrapper_fixes_reservation_intent_before_the_original_claim(self):
        self.assertEqual(list(inspect.signature(S.reserve_configuration_after_entry).parameters), ["transition"])
        self.intent_probe(S.reserve_configuration_after_entry, (True, True, True))

    def test_invalid_intents_fail_before_validation_claim_or_suppliers(self):
        with patch.object(S, "check_new_entry_transition") as validation:
            for intent in ((False, True, False), (True, False, True), (False, False, True),
                    (1, True, True), (True, 1, True), (True, True, 1), (True, True, None)):
                with self.subTest(intent=intent), self.assertRaisesRegex(O.OriginError, "RECIPIENT_INTENT"):
                    S._recipient_after_entry(object(), initialize=intent[0], stage=intent[1], reserve=intent[2])
            validation.assert_not_called()

    def test_failed_shared_claim_cannot_retry_with_another_wrapper(self):
        transition = self.intent_probe(S.reserve_configuration_after_entry, (True, True, True))
        with patch.object(S, "check_new_entry_transition"), \
                patch.object(S, "_recipient_predecessor_pins", return_value=((), ())), \
                patch.object(S._RecipientPredecessorGraph, "capture", return_value=object()), \
                patch.object(O.clocks, "observe", side_effect=AssertionError("NO_SECOND_CLOCK")):
            for operation in (S.run_recipient_after_entry, S.initialize_after_entry, S.stage_after_entry,
                              S.reserve_configuration_after_entry):
                with self.subTest(operation=operation.__name__), self.assertRaisesRegex(O.OriginError, "ALREADY_CLAIMED"):
                    operation(transition)

    def test_stage_only_intent_keeps_two_phase_return_and_cannot_upgrade(self):
        self.make_upstream(reserve=False)
        result = self.run_parent()
        saved = S._staging_sequence_frame(self.sequence())
        self.assertIs(type(result), S.StagingPrefix)
        self.assertIs(result, self.old_parents[-1].result)
        self.assertEqual(saved.plan, ("dependency-stage", "empty-seed"))
        self.assertEqual(len(saved.phases), 2)
        self.assertIs(saved.result, result)
        self.leaf_calls.assert_not_called()
        self.assertFalse((self.f.session / "configuration-custody").exists())
        with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_UPGRADE_CLOCK")), \
                self.assertRaisesRegex(O.OriginError, "STAGING_PHASE"):
            self.actual_phase(self.sequence(), result, "custody-prepare")
        self.old_graph.checked()

    def test_completed_reservation_sequence_is_not_replayable(self):
        result = self.run_parent()
        with patch.object(O.clocks, "observe", side_effect=AssertionError("NO_REPLAY_CLOCK")), \
                self.assertRaisesRegex(O.OriginError, "ALREADY_CLAIMED"):
            self.run_parent()
        self.assertIs(self.sequence().result, result)
        self.assertEqual(self.leaf_calls.call_count, 1)

    def test_copied_seed_prefix_is_refused_before_third_registration(self):
        def dispatch(sequence, previous, name):
            return (self.actual_phase(sequence, replace(previous), name) if name == "custody-prepare" else
                    self.phase_dispatch(sequence, previous, name))
        with patch.object(S, "_run_staging_phase", side_effect=dispatch):
            self.failed("NOT_ORIGINAL_SEED_RETURN")
        self.assertEqual(len(S._staging_sequence_frame(self.sequence()).phases), 2)
        self.leaf_calls.assert_not_called()
        self.assertFalse((self.f.session / "custody-prepare-parent").exists())

    def test_seed_leaf_is_not_the_seed_parent_return(self):
        def dispatch(sequence, previous, name):
            return (self.actual_phase(sequence, previous.seed_leaf, name) if name == "custody-prepare" else
                    self.phase_dispatch(sequence, previous, name))
        with patch.object(S, "_run_staging_phase", side_effect=dispatch):
            self.failed("CUSTODY_PHASE_ORDER")
        self.leaf_calls.assert_not_called()

    def test_missing_seed_completion_cannot_start_custody(self):
        self.after_seed = lambda parent: setattr(parent, "state", "RUNNING")
        self.failed("NOT_ORIGINAL_SEED_RETURN", unchanged=False)
        self.leaf_calls.assert_not_called()
        self.assertIsNone(self.old_parents[-1].original)
        self.assertEqual(self.old_parents[-1].state, "RUNNING")  # Test mutation, not parent failure propagation.

    def test_live_coordinator_phase_alias_is_not_accepted(self):
        self.on_admit = lambda parent: setattr(self.sequence(), "phases", tuple(list(self.sequence().phases)))
        self.failed("SEQUENCE_CHANGED")
        frame = S._staging_frame(self.parent())
        self.assertTrue(frame.owner.closed)
        self.assertFalse(frame.unknown)
        self.leaf_calls.assert_not_called()

    def test_live_coordinator_plan_cannot_discard_original_reservation_intent(self):
        self.on_admit = lambda parent: S._update_staging_sequence(self.sequence(), plan=("dependency-stage", "empty-seed"))
        self.failed("PLAN_CHANGED")
        self.leaf_calls.assert_not_called()

    def test_live_coordinator_cannot_publish_a_result_early(self):
        self.on_admit = lambda parent: setattr(self.sequence(), "result", self.old_parents[-1].result)
        self.failed("SEQUENCE_CHANGED")
        # The rejected publication is never returned; the private result stays None.
        self.assertIsNone(S._staging_sequence_frame(self.sequence()).result)

    def registry_alias_failure(self, name):
        def mutate(parent):
            self.stack.enter_context(patch.object(S, name, dict(getattr(S, name))))
        self.on_admit = mutate
        self.failed("REGISTRY_CHANGED|SEQUENCE_CHANGED")
        frame = S._staging_frame(self.parent())
        self.assertTrue(frame.owner.closed)
        self.assertFalse(frame.unknown)
        self.assertTrue(all(row[3] and row[4] for row in frame.resources))

    def test_equal_recipient_registry_alias_cannot_redirect_new_cleanup(self):
        self.registry_alias_failure("_RECIPIENT_ATTEMPTS")

    def test_equal_initializer_registry_alias_cannot_redirect_new_cleanup(self):
        self.registry_alias_failure("_INITIALIZER_ATTEMPTS")

    def test_equal_control_registry_alias_cannot_redirect_new_cleanup(self):
        self.registry_alias_failure("_PARENT_CONTROLS")

    def test_equal_sequence_registry_alias_cannot_redirect_new_cleanup(self):
        self.registry_alias_failure("_STAGING_ATTEMPTS")

    def test_completed_seed_private_frame_identity_is_rechecked(self):
        def mutate(parent):
            old = self.old_parents[1]
            S._update_staging_frame(old, last=S._staging_frame(old).last)
        self.on_admit = mutate
        self.failed("SEED_PARENT_RETURN_CHANGED")
        self.assertEqual(self.old_parents[1].state, "COMPLETE")
        self.assertIsNone(self.old_parents[1].original)

    def test_typed_staged_argument_nested_identity_is_not_opaque(self):
        def mutate(parent):
            staged = S._staging_frame(parent).staged
            object.__setattr__(staged, "seed_leaf", replace(staged.seed_leaf))
        self.on_admit = mutate
        self.failed("CLOSED_GRAPH_CHANGED|STAGED_RETURN_CHANGED")
        self.leaf_calls.assert_not_called()

    def test_nested_original_seed_bytes_are_pinned_before_suppliers(self):
        def mutate(parent):
            object.__setattr__(self.old_parents[1].result.seed_leaf, "raw", b"ALTERED_ORIGINAL_SEED")
        self.on_admit = mutate
        self.failed("CLOSED_GRAPH_CHANGED", unchanged=False)
        self.leaf_calls.assert_not_called()

    def test_nested_original_prefix_checked_scalar_type_is_pinned(self):
        def mutate(parent):
            object.__setattr__(self.old_parents[1].result, "checked_ns", True)
        self.on_admit = mutate
        self.failed("CLOSED_GRAPH_CHANGED|SEED_PARENT_RETURN_CHANGED", unchanged=False)
        self.leaf_calls.assert_not_called()

    def test_first_raw_must_follow_final_seed_parent_not_only_seed_leaf(self):
        self.after_seed = lambda parent: setattr(self.f, "ns", parent.result.checked_ns - 2000)
        self.failed("PREDECESSOR_CLOCK")
        self.assertGreater(self.f.ns, self.h.staged.seed_leaf.checked_ns)
        self.leaf_calls.assert_not_called()

    def test_first_local_must_follow_final_seed_parent_not_only_seed_leaf(self):
        self.after_seed = lambda parent: setattr(self.f, "local", parent.result.checked_local - 0.001)
        self.failed("PREDECESSOR_CLOCK")
        self.assertGreater(self.f.local, self.h.staged.seed_leaf.checked_local)
        self.leaf_calls.assert_not_called()

    def test_original_cumulative_custody_fence_can_only_shorten_120(self):
        end = self.f.proposal["phaseFencesNs"]["custody-prepare"]
        self.after_seed = lambda parent: setattr(self.f, "ns", end - 5 * NS)
        result = self.run_parent()
        frame = S._staging_frame(self.parent())
        self.assertEqual(frame.limits.hard, end)
        self.assertEqual(frame.limits.soft, end)
        self.assertLess(frame.limits.hard, frame.limits.first + 120 * NS)
        self.assertLess(result.checked_ns, end)
        self.assertLess(frame.limits.local_hard, frame.limits.local_start + 120)

    def test_raw_120_equality_fails_without_borrowing_final_or_read_reserve(self):
        self.on_admit = lambda parent: setattr(self.f, "ns", S._staging_frame(parent).limits.hard - 1000)
        self.failed("ORIGINAL_PHASE_EXPIRED")
        frame = S._staging_frame(self.parent())
        self.assertGreaterEqual(frame.last, frame.limits.hard)
        self.assertEqual(tuple(p.name for p in self.sequence().phases), ("dependency-stage", "empty-seed", "custody-prepare"))
        self.leaf_calls.assert_not_called()

    def test_local_120_equality_is_not_a_new_readback_window(self):
        self.on_admit = lambda parent: setattr(self.f, "local", S._staging_frame(parent).limits.local_hard)
        self.failed("ORIGINAL_PHASE_EXPIRED")
        frame = S._staging_frame(self.parent())
        self.assertEqual(frame.local_last, frame.limits.local_hard)
        self.leaf_calls.assert_not_called()

    def test_valid_raw_is_retained_when_later_local_observation_rolls_back(self):
        observed = []
        def mutate(parent):
            def reading():
                value = self.f.observe()
                observed.append(value.nanoseconds)
                self.f.local = 500.9
                return value
            self.stack.enter_context(patch.object(O.clocks, "observe", side_effect=reading))
        self.on_admit = mutate
        self.failed("LOCAL_BACKWARDS")
        self.assertTrue(observed)
        self.assertEqual(S._staging_frame(self.parent()).last, observed[-1])

    def known_new_close(self):
        frame = S._staging_frame(self.parent())
        self.assertTrue(frame.owner.closed)
        self.assertFalse(frame.unknown)
        self.assertFalse(frame.owner.unknown)
        self.assertTrue(all(row[3] and row[4] for row in frame.resources))
        self.assertEqual(frame.handlers, frame.restored)

    def returned_leaf_mutant(self, change):
        def leaf(*args):
            return change(self.actual_leaf(*args))
        self.leaf_calls.side_effect = leaf

    def test_staging_leaf_cannot_substitute_for_custody_request_return(self):
        self.leaf_calls.side_effect = lambda *args: self.h.staged.seed_leaf
        self.failed("CUSTODY_LEAF_KIND")
        self.assertFalse((self.f.session / "configuration-custody").exists())
        self.known_new_close()

    def test_duck_typed_staging_raw_alias_is_not_a_reservation(self):
        self.leaf_calls.side_effect = lambda *args: SimpleNamespace(raw=b"{}", staging_raw=b"{}",
            checked_ns=self.f.ns, local_started=self.f.local, checked_local=self.f.local)
        self.failed("CUSTODY_LEAF_KIND")
        self.known_new_close()

    def test_changed_custody_leaf_scope_is_refused_before_parent_copies(self):
        def change(value):
            raw = F.record(value.raw)
            raw["scope"] = B.SEED_SCOPE
            return replace(value, raw=F.encoded(raw))
        self.returned_leaf_mutant(change)
        self.failed("CUSTODY_RETURN_SCOPE")
        self.assertFalse((self.f.session / "custody-prepare-parent/leaf-evidence.json").exists())
        self.known_new_close()

    def test_changed_request_scope_is_not_accepted_with_a_matching_return_hash(self):
        def change(value):
            request, raw = F.record(value.request_raw), F.record(value.raw)
            request["scope"] = B.STAGE_SCOPE
            request_raw = F.encoded(request)
            raw["requestSha256"] = F.digest(request_raw)
            return replace(value, raw=F.encoded(raw), request_raw=request_raw)
        self.returned_leaf_mutant(change)
        self.failed("CUSTODY_REQUEST_SCOPE")
        self.known_new_close()

    def after_request_copy(self, change):
        changed = []
        def hook(parent):
            if "request-original" not in parent.records or changed:
                return
            request = self.f.session / "configuration-custody/request.json"
            copy = self.f.session / "custody-prepare-parent/request-original.json"
            raw = copy.read_bytes()
            self.assertEqual(request.read_bytes(), raw)
            changed.append((copy, raw))
            change(parent, request, raw)
        self.on_read = hook
        return changed

    def assert_copy_unchanged(self, changed):
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0][0].read_bytes(), changed[0][1])

    def test_actual_request_mutation_after_parent_copy_is_not_masked_by_the_copy(self):
        changed = self.after_request_copy(lambda parent, request, raw: self.f.write(request, raw + b" "))
        self.failed("SEED_FILE_REPLACED|SEED_ORIGINAL_FILE_CHANGED")
        self.assert_copy_unchanged(changed)
        self.known_new_close()

    def test_byte_identical_original_request_replacement_is_refused(self):
        def change(parent, request, raw):
            original = request.stat().st_ino
            request.rename(self.f.base / "saved-original-request.json")
            self.f.write(request, raw)
            self.assertNotEqual(request.stat().st_ino, original)
        changed = self.after_request_copy(change)
        self.failed("SEED_FILE_REPLACED")
        self.assert_copy_unchanged(changed)
        self.known_new_close()

    def test_byte_identical_reservation_in_a_replaced_directory_is_refused(self):
        def change(parent, request, raw):
            original = request.parent.stat().st_ino
            request.parent.rename(self.f.base / "saved-original-reservation")
            request.parent.mkdir(mode=0o700)
            (request.parent / "retained").mkdir(mode=0o700)
            self.f.write(request, raw)
            self.assertNotEqual(request.parent.stat().st_ino, original)
        changed = self.after_request_copy(change)
        self.failed("CUSTODY_REQUEST_DIRECTORY_CHANGED")
        self.assert_copy_unchanged(changed)
        self.known_new_close()

    def test_retained_directory_contamination_is_not_reservation_success(self):
        changed = self.after_request_copy(lambda parent, request, raw:
            self.f.write(request.parent / "retained/unexpected.json", b"{}"))
        self.failed("SEED_DIRECTORY_NOT_EMPTY_OR_CHANGED")
        self.assert_copy_unchanged(changed)
        self.known_new_close()

    def test_mutating_the_captured_return_record_cannot_rebind_original_request(self):
        changed = self.after_request_copy(lambda parent, request, raw:
            object.__setattr__(parent.leaf, "request_raw", raw + b" "))
        self.failed("LEAF_RETURN_CHANGED")
        self.assert_copy_unchanged(changed)
        self.known_new_close()

    def test_only_seven_new_labels_are_phase_specific_in_acquire_and_roster(self):
        expected = frozenset("bootstrap-leaf-custody-" + name for name in (
            "source-root", "source-scripts", "stage-container", "stage-home", "directory", "retained", "request-writer"))
        self.assertEqual(S._CUSTODY_RESOURCE_LABELS - S._STAGING_RESOURCE_LABELS, expected)
        for name in ("dependency-stage", "empty-seed", "custody-prepare"):
            frame = SimpleNamespace(name=name)
            self.assertEqual(S._staging_labels(frame), S._STAGING_RESOURCE_LABELS |
                (expected if name == "custody-prepare" else frozenset()))
        # Parsed actual admission/roster bodies, not an alternate test-owned
        # allowlist. The smoke separately observes all seven real leaf labels.
        for function in (S._StagingFileOwner.acquire, S._StagingPhaseParent.roster):
            body = ast.parse(textwrap.dedent(inspect.getsource(function)))
            self.assertTrue(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and
                node.func.id == "_staging_labels" for node in ast.walk(body)))

    def test_arbitrary_custody_resource_label_refuses_before_factory(self):
        factory = unittest.mock.Mock(side_effect=AssertionError("NO_ARBITRARY_RESOURCE_FACTORY"))
        self.on_admit = lambda parent: parent.live().acquire("bootstrap-leaf-custody-arbitrary", factory)
        self.failed("STAGING_RESOURCE_LABEL")
        factory.assert_not_called()
        self.known_new_close()

    def test_roster_cannot_admit_an_unknown_label_even_when_private_row_matches(self):
        def change(parent):
            frame = S._staging_frame(parent)
            row, label, resource, attempted, closed = frame.resources[-1]
            label = "bootstrap-leaf-custody-arbitrary"
            row["label"] = label
            S._update_staging_frame(parent, resources=(*frame.resources[:-1], (row, label, resource, attempted, closed)))
        self.on_admit = change
        self.failed("STAGING_ROSTER_CHANGED")
        self.assertTrue(S._staging_frame(self.parent()).unknown)

    def test_raw_rollback_is_not_hidden_by_later_recovery(self):
        self.on_admit = lambda parent: setattr(self.f, "ns", S._staging_frame(parent).last - 2000)
        self.failed("CLOCK_BACKWARDS")
        self.leaf_calls.assert_not_called()

    def test_late_actual_leaf_return_cannot_use_its_earlier_checked_clock(self):
        def change(value):
            self.f.ns = S._staging_frame(self.parent()).limits.hard - 1000
            return value
        self.returned_leaf_mutant(change)
        self.failed("ORIGINAL_PHASE_EXPIRED")
        self.assertIsNotNone(S._staging_frame(self.parent()).leaf)
        self.assertFalse((self.f.session / "custody-prepare-parent/leaf-evidence.json").exists())

    def test_falsey_final_serialization_error_is_not_a_successful_closed_return(self):
        encode, first = O.encoded, FalseyFailure("FINAL_RESERVATION_SERIALIZATION")
        def encoded(value):
            if type(value) is dict and value.get("scope") == "BOOTSTRAP_CONFIGURATION_CUSTODY_PARENT_CLOSED_NO_EXECUTION_V1":
                raise first
            return encode(value)
        with patch.object(O, "encoded", encoded):
            self.assertIs(self.failed("FINAL_RESERVATION_SERIALIZATION"), first)
        self.known_new_close()

    def test_late_final_serialization_cannot_borrow_prepare_final_or_read(self):
        encode, serialized = O.encoded, []
        def encoded(value):
            raw = encode(value)
            if type(value) is dict and value.get("scope") == "BOOTSTRAP_CONFIGURATION_CUSTODY_PARENT_CLOSED_NO_EXECUTION_V1":
                serialized.append(raw)
                self.f.ns = S._staging_frame(self.parent()).limits.hard - 1000
            return raw
        with patch.object(O, "encoded", encoded):
            self.failed("ORIGINAL_PHASE_EXPIRED")
        self.assertEqual(len(serialized), 1)
        self.known_new_close()

    def test_final_raw_highwater_survives_a_late_local_sample_after_serialization(self):
        encode, observed, armed = O.encoded, [], []
        def encoded(value):
            raw = encode(value)
            if type(value) is dict and value.get("scope") == "BOOTSTRAP_CONFIGURATION_CUSTODY_PARENT_CLOSED_NO_EXECUTION_V1":
                armed.append(True)
            return raw
        def observe():
            value = self.f.observe()
            if armed:
                self.f.local = S._staging_frame(self.parent()).limits.local_hard
                observed.append(value.nanoseconds)
            return value
        with patch.object(O, "encoded", encoded), patch.object(O.clocks, "observe", side_effect=observe):
            self.failed("ORIGINAL_PHASE_EXPIRED")
        frame = S._staging_frame(self.parent())
        self.assertTrue(observed)
        self.assertEqual(frame.last, observed[-1])
        self.assertEqual(frame.local_last, frame.limits.local_hard)
        self.known_new_close()

    def test_handler_restoration_remains_inside_the_same_custody_window(self):
        original, restored = signal.signal, []
        def setter(number, handler):
            result = original(number, handler)
            if self.sequences and S._staging_frame(self.parent()).state == "CLOSING":
                restored.append(number)
                self.f.local = S._staging_frame(self.parent()).limits.local_hard
            return result
        with patch.object(signal, "signal", setter):
            self.failed("ORIGINAL_PHASE_EXPIRED")
        self.assertTrue(restored)
        self.known_new_close()

    def test_public_owner_alias_cannot_redirect_actual_known_cleanup(self):
        fake = object()
        self.on_admit = lambda parent: setattr(parent, "owner", fake)
        self.failed("PARENT_CHANGED")
        self.assertIs(self.parent().owner, fake)
        self.known_new_close()

    def test_actual_allocation_is_retained_before_fallible_postcheck(self):
        returned, checked = [], []
        first, original_clock = FalseyFailure("AFTER_ACTUAL_CUSTODY_ALLOCATION"), O.clocks.checked_now
        def clock(*args, **kwargs):
            if returned and not checked:
                checked.append(True)
                self.assertEqual(sum(pin[2] is returned[0] for pin in S._staging_frame(self.parent()).resources), 1)
                raise first
            return original_clock(*args, **kwargs)
        def acquire(parent):
            def factory():
                resource = F.private_root(parent.handles["phase"].path)
                returned.append(resource)
                return resource
            parent.live().acquire("bootstrap-leaf-custody-directory", factory)
        self.on_admit = acquire
        with patch.object(O.clocks, "checked_now", clock):
            self.assertIs(self.failed("AFTER_ACTUAL_CUSTODY_ALLOCATION"), first)
        self.assertEqual(checked, [True])
        self.assertTrue(returned[0].closed)
        self.known_new_close()

    def test_forged_public_flags_cannot_attest_actual_close(self):
        forged, first = [], FalseyFailure("BEFORE_FORGED_CUSTODY_FLAGS")
        def change(parent):
            pin = next(pin for pin in S._staging_frame(parent).resources if not pin[3])
            forged.append(pin)
            pin[0].update(attempted=True, closed=True)
            raise first
        self.on_admit = change
        self.assertIs(self.failed("BEFORE_FORGED_CUSTODY_FLAGS"), first)
        frame = S._staging_frame(self.parent())
        self.assertTrue(frame.unknown)
        self.assertFalse(forged[0][2].closed)
        self.assertTrue(any(pin[2] is forged[0][2] and not pin[4] for pin in frame.resources))

    def test_removed_resource_row_is_retained_not_reclassified_as_closed(self):
        removed = []
        self.on_admit = lambda parent: removed.append(parent.owner.resources.pop())
        self.failed("ROSTER_CHANGED")
        frame = S._staging_frame(self.parent())
        self.assertTrue(frame.unknown)
        self.assertTrue(any(pin[0] is removed[0] and not pin[4] for pin in frame.resources))
        self.assertIn(frame.owner, S.QUARANTINE)

    def test_equal_replacement_row_cannot_supply_original_resource_registration(self):
        def change(parent):
            parent.owner.resources[-1] = dict(parent.owner.resources[-1])
        self.on_admit = change
        self.failed("ROSTER_CHANGED")
        frame = S._staging_frame(self.parent())
        self.assertTrue(frame.unknown)
        self.assertEqual(len(frame.foreign_resources), 1)

    def test_foreign_resource_row_never_becomes_new_close_authority(self):
        extra = []
        def change(parent):
            resource = F.private_root(parent.handles["phase"].path)
            self.addCleanup(lambda: None if resource.closed else resource.close())
            extra.append(resource)
            parent.owner.resources.append({"label": "bootstrap-leaf-custody-directory", "owner": resource,
                                           "attempted": False, "closed": False})
        self.on_admit = change
        self.failed("ROSTER_CHANGED")
        frame = S._staging_frame(self.parent())
        self.assertTrue(frame.unknown)
        self.assertFalse(extra[0].closed)
        self.assertTrue(any(pin[2] is extra[0] for pin in frame.foreign_resources))
        self.assertFalse(any(pin[2] is extra[0] for pin in frame.resources))
        frame.owner.resources.pop()
        with self.assertRaisesRegex(O.OriginError, "ROSTER_CHANGED"):
            self.parent().roster()
        self.assertFalse(extra[0].closed)

    def test_unknown_close_keeps_first_failure_and_forbids_new_acquisition(self):
        first, factory = FalseyFailure("UNKNOWN_CUSTODY_CLOSE"), unittest.mock.Mock()
        def change(parent):
            pin = next(pin for pin in S._staging_frame(parent).resources if not pin[3])
            self.stack.enter_context(patch.object(pin[2], "close", side_effect=first))
            parent.owner.close_one(pin[2])
            self.assertTrue(parent.owner.unknown)
            with self.assertRaisesRegex(O.OriginError, "RETIREMENT_UNKNOWN|OWNER_NOT_LIVE"):
                parent.owner.acquire("bootstrap-leaf-custody-directory", factory)
            raise first
        self.on_admit = change
        self.assertIs(self.failed("UNKNOWN_CUSTODY_CLOSE"), first)
        factory.assert_not_called()
        self.assertIs(S._staging_frame(self.parent()).original, first)
        self.assertTrue(S._staging_frame(self.parent()).unknown)

    def test_falsey_first_failure_survives_secondary_close_and_handler_errors(self):
        first, close_error, handler_error = (FalseyFailure("FIRST_CUSTODY_FAILURE"),
            RuntimeError("SECONDARY_CUSTODY_CLOSE"), RuntimeError("SECONDARY_CUSTODY_RESTORE"))
        original_signal, secondary = signal.signal, []
        def change(parent):
            pin = next(pin for pin in S._staging_frame(parent).resources if not pin[3])
            close = pin[2].close
            def failed_close():
                close()
                secondary.append(close_error)
                raise close_error
            self.stack.enter_context(patch.object(pin[2], "close", failed_close))
            raise first
        def setter(number, handler):
            result = original_signal(number, handler)
            if self.sequences and S._staging_frame(self.parent()).state == "CLOSING":
                secondary.append(handler_error)
                raise handler_error
            return result
        self.on_admit = change
        with patch.object(signal, "signal", setter):
            self.assertIs(self.failed("FIRST_CUSTODY_FAILURE"), first)
        frame = S._staging_frame(self.parent())
        self.assertIs(frame.owner.original, first)
        self.assertIn(close_error, secondary)
        self.assertIn(handler_error, secondary)
        self.assertTrue(frame.unknown)
        self.assertTrue(any(row["stage"] == "staging-handler-restore" for row in frame.owner.errors))

    def test_no_cli_workflow_export_save_or_budget_authority_is_added(self):
        source = (ROOT / "scripts/run-hosted-cache-bootstrap.py").read_text()
        body = ast.parse(source)
        self.assertNotIn("reserve_configuration_after_entry", inspect.getsource(S.main))
        self.assertFalse(any(isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and
            node.func.attr in ("export_snapshot", "save_set") for node in ast.walk(body)))
        self.assertFalse((ROOT / ".github/workflows/dependency-cache-bootstrap.yml").exists())
        self.assertFalse((ROOT / ".github/test-evidence-recipient.json").exists())
        self.assertEqual(S.allocation.PROPOSED_JOB_SECONDS, 5400)
        self.assertEqual(S.allocation.policy()["scope"], "CLOSED_SOURCE_PROPOSAL_NOT_ADMITTED_OR_MEASURED_FIT")
        self.assertEqual(S.allocation.policy()["windowsNativeFileSeconds"], 900)
        self.assertEqual(S.windows.MAX_FILE_BYTES, 576 * 1024 * 1024)
        self.assertEqual(S.windows.MAX_SECONDS, 900)
        for name in ("ci.yml", "desktop-cross-host.yml"):
            workflow = (ROOT / ".github/workflows" / name).read_text()
            self.assertIn("ORDINARY_TEST_ACTIVATION=HOLD; QUALIFIED_DEPENDENCY_CACHE_REQUIRED", workflow)
            self.assertIn("exit 125", workflow)


def load_tests(_loader, _tests, _pattern):
    return unittest.TestSuite(CustodyParentModels(name) for name in CustodyParentModels.__dict__ if name.startswith("test_"))


if __name__ == "__main__":
    unittest.main()
