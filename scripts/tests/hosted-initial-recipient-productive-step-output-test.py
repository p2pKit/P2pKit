#!/usr/bin/env python3
"""Five-route output models, NOT native/cache/custody or hosted acceptance.

The unchanged P token-frame helpers execute against explicit in-memory
acquisition/adapter suppliers. Adapter classes are real; their original-run
checks and RAW/LOCAL observations are MODELS. Model load anchors are installed
BEFORE entry, then later substitutions must fail. No real token, kernel boot,
provider, process, key, old reader, fixture generator or native window runs.
One test uses only the unchanged writer and a tiny ordinary-UID owned file.
"""
from __future__ import annotations

import ast
from contextlib import ExitStack
import ctypes
import dataclasses
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise AssertionError("PRODUCTIVE_STEP_OUTPUT_MODEL_SIDE_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_productive as P
import hosted_initial_recipient_productive_adapter as A
import hosted_initial_recipient_productive_data as D

C, N = P.C.C, P.N
ORIGINAL_LOAD = P._STEP_OUTPUT_LOAD
ORIGINAL_WRITER = C._append_output_bytes
SOURCE = ast.parse((ROOT / "scripts/hosted_initial_recipient_productive.py").read_text())
CLI = ast.parse((ROOT / "scripts/run-hosted-initial-recipient-productive.py").read_text())
ROUTES = (
    ("produce", D.OUTPUT_SCOPE, ("handoffSha256", "producerReturnSha256")),
    ("prepare-save", D.SAVE_PREPARATION_SCOPE, ("savePreparationSha256",)),
    ("after-save", D.AFTER_SAVE_SCOPE, ("afterSaveSha256",)),
    ("prepare-probe", D.PROBE_PREPARATION_SCOPE, ("probePreparationSha256",)),
    ("after-probe", D.PROBE_RESULT_SCOPE, ("probeSha256",)),
)
END = 1000000
TOKEN_MODEL = "EXPLICIT_NONSECRET_MODEL_NOT_A_GITHUB_TOKEN"


class FirstFailure(RuntimeError):
    pass


class OutputModel:
    """Closed test substitute, not a source or original-native authority grant."""
    def __init__(self, case, operation="produce", *, real_writer=False):
        self.case, self.operation, self.stack = case, operation, ExitStack()
        self.source_action = self.checked_action = self.clock_action = self.write_action = lambda: None
        self.cancel_action = lambda: None
        self.source_calls, self.writes, self.now_calls = 0, [], 0
        self.raw, self.active, self.cancelled, self.return_override = 100, False, None, None
        self.primary, self.authority, self.prefix = object(), object(), object()
        for name in ("_STEP_OUTPUTS", "_STEP_OUTPUT_CALLS", "_STEP_OUTPUT_RESULTS"):
            self.stack.enter_context(patch.object(P, name, {}))
        self.stack.enter_context(patch.object(P, "_STEP_OUTPUT_ADAPTER", []))
        self.stack.enter_context(patch.object(A, "_OUTPUTS", {}))
        self.stack.enter_context(patch.object(C, "QUARANTINE", []))
        self.stack.enter_context(patch.dict(os.environ, {}, clear=True))
        self.stack.enter_context(patch.object(P.C, "copy_primary", self.copy_primary))
        self.stack.enter_context(patch.object(P.C, "custody_authority", self.custody_authority))
        self.stack.enter_context(patch.object(P.C, "retire_primary_for_productive", self.retire))
        self.stack.enter_context(patch.object(A, "produce", self.produce))
        self.stack.enter_context(patch.object(A, "complete_productive_handoff", self.complete))
        self.stack.enter_context(patch.object(A, "checked_productive_handoff", self.complete))
        for route in ("prepare-save", "after-save", "prepare-probe", "after-probe"):
            def step(token, cancelled, route=route):
                self.case.assertEqual(route, self.operation)
                return self.supply(token, cancelled)
            self.stack.enter_context(patch.object(A, route.replace("-", "_"), step))
        def checked(fence):
            self.checked_action()
            row = A._OUTPUTS.get(id(fence))
            P.require(type(row) is tuple and row[0] is fence and fence is self.adapter_fence,
                "EXPLICIT_MODEL_OUTPUT_REGISTRATION")
            N._check_history(self.original_graph)
            return row[1], row[2]
        def now(fence, *, final=False, minimum=0, limit=None):
            self.case.assertIs(fence, self.adapter_fence)
            self.case.assertIs(final, True)
            self.case.assertEqual((minimum, limit), (0, END))
            self.now_calls += 1
            if self.cancelled is not None:
                self.cancelled()
            self.clock_action()
            return self.raw  # Explicit RAW/LOCAL model, never actual timing evidence.
        self.stack.enter_context(patch.object(A._OutputFence, "_checked", checked))
        self.stack.enter_context(patch.object(A._OutputFence, "now", now))
        self.stack.enter_context(patch.object(C, "_append_output_bytes", ORIGINAL_WRITER if real_writer else self.write))
        # This declared MODEL baseline is deliberately distinct from production
        # load custody. No callback may amend it after the fixture entry.
        self.stack.enter_context(patch.object(P, "_STEP_OUTPUT_LOAD",
            tuple((owner, name, getattr(owner, name)) for owner, name, _original in ORIGINAL_LOAD)))
        scope, names = next((scope, names) for route, scope, names in ROUTES if route == operation)
        self.public = {"scope": scope, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "exportSaveAuthority": False, **{name: character * 64 for name, character in zip(names, "ab")}}
        self.adapter_fence = A._OutputFence()
        self.run = A._Run(operation, object(), {}, {}, None, {}, {}, None, ())
        self.state = A._ParentState(A._Parent(), self.run, A._SEQUENCES[operation][-1], object(), 0.0, "b" * 64,
            None, None, (), (END,), (1.0,), object())
        kind = A.ProductiveHandoff if operation == "produce" else A._StepReturn
        self.result = kind(self.public, self.adapter_fence, END)
        self.run.current, self.run.terminal = self.state, self.result
        self.registration = (self.adapter_fence, self.result, self.state, b"EXPLICIT_MODEL_ONLY\n", ())
        A._OUTPUTS[id(self.adapter_fence)] = self.registration
        self.original_graph = N._history_graph(self.result.__dict__, self.public)
        self.returned = (self.public, self.adapter_fence, END)
        self.fence = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.stack.close()

    def copy_primary(self, kind, *, cancelled):
        self.case.assertEqual(kind, "worker")
        cancelled()
        return self.primary

    def custody_authority(self, primary, token):
        self.case.assertIs(primary, self.primary)
        self.case.assertEqual(token, TOKEN_MODEL)
        return self.authority

    def retire(self, primary, authority):
        self.case.assertIs(primary, self.primary)
        self.case.assertIs(authority, self.authority)
        return self.prefix

    def produce(self, prefix, token, cancelled):
        self.case.assertIs(prefix, self.prefix)
        self.supply(token, cancelled)
        return self.result

    def complete(self, result, prefix):
        self.case.assertIs(result, self.result)
        self.case.assertIs(prefix, self.prefix)
        return result

    def supply(self, token, cancelled):
        self.case.assertEqual(token, TOKEN_MODEL)
        self.case.assertTrue(P._STEP_OUTPUT_ADAPTER, "adapter anchors must precede ALL productive callbacks")
        self.case.assertNotIn(P.O.wire.TOKEN_ENV, os.environ)
        self.active, self.cancelled = True, cancelled
        self.source_calls += 1
        try:
            cancelled()
            self.source_action()
            return self.returned if self.return_override is None else self.return_override
        finally:
            self.active = False

    def write(self, raw, check):
        self.case.assertFalse(self.active)
        self.case.assertNotIn(P.O.wire.TOKEN_ENV, os.environ)
        # Verify the original private helper frames have ACTUALLY returned;
        # merely clearing an environment variable while retaining the frame is
        # insufficient for this model's output boundary.
        frame = sys._getframe()
        while frame is not None:
            self.case.assertFalse(frame.f_code in (P.productive.__code__, P.step.__code__))
            frame = frame.f_back
        check()
        self.write_action()
        check()
        self.writes.append(raw)
        check()

    def begin(self):
        self.fence = P._StepOutputFence(self.operation, lambda: self.cancel_action())
        return self.fence

    def invoke(self):
        if self.fence is None:
            self.begin()
        os.environ[P.O.wire.TOKEN_ENV] = TOKEN_MODEL
        return self.fence.run()

    def late(self):
        return self.fence.now(final=True, minimum=0, limit=END)

    def expected(self):
        names = next(names for route, _scope, names in ROUTES if route == self.operation)
        return b"".join(name.encode() + b"=" + self.public[name].encode() + b"\n" for name in sorted(names))


class StepOutputControls(unittest.TestCase):
    def test_all_five_original_routes_append_once_then_two_late_checks(self):
        for operation, scope, _names in ROUTES:
            with self.subTest(operation=operation), OutputModel(self, operation) as model:
                public, fence, end = model.invoke()
                self.assertIs(public, model.public)
                self.assertIs(fence, model.fence)
                self.assertEqual(end, END)
                self.assertEqual(public["scope"], scope)
                self.assertEqual(public["budgetAcceptance"], "NOT_ADMITTED")
                self.assertEqual(public["testAcceptance"], "NOT_PERFORMED")
                self.assertIs(public["exportSaveAuthority"], False)
                self.assertEqual(model.writes, [model.expected()])
                self.assertEqual(model.source_calls, 1)
                self.assertNotIn(P.O.wire.TOKEN_ENV, os.environ)
                self.assertEqual((model.late(), model.late()), (100, 100))
                with self.assertRaises(Exception):
                    model.late()
                self.assertEqual(model.writes, [model.expected()])

    def test_exact_wrapper_functions_dispatch_only_their_route(self):
        for operation, _scope, _names in ROUTES:
            with self.subTest(operation=operation), OutputModel(self, operation) as model:
                os.environ[P.O.wire.TOKEN_ENV] = TOKEN_MODEL
                value = P.productive_outputs(lambda: None) if operation == "produce" else P.step_outputs(operation, lambda: None)
                self.assertIs(value[0], model.public)
                self.assertEqual(model.writes, [model.expected()])

    def test_original_helpers_require_and_clear_private_token_without_append_on_failure(self):
        with OutputModel(self) as model:
            model.begin()
            with self.assertRaises(Exception):
                model.fence.run()
            self.assertEqual((model.source_calls, model.writes), (0, []))
            self.assertNotIn(P.O.wire.TOKEN_ENV, os.environ)

    def test_wrong_scope_hash_set_or_acceptance_data_is_rejected(self):
        mutations = (
            lambda public: public.__setitem__("scope", "WRONG_SCOPE"),
            lambda public: public.__setitem__("savePreparationSha256", "A" * 64),
            lambda public: public.__setitem__("savePreparationSha256", True),
            lambda public: public.pop("savePreparationSha256"),
            lambda public: public.__setitem__("unexpectedSha256", "a" * 64),
            lambda public: public.__setitem__("budgetAcceptance", "ACCEPTED"),
            lambda public: public.__setitem__("testAcceptance", "PASS"),
            lambda public: public.__setitem__("exportSaveAuthority", True),
        )
        for number, mutate in enumerate(mutations):
            with self.subTest(case=number), OutputModel(self, "prepare-save") as model:
                # Establish malformed model input before graph creation, so this
                # exercises the new public grammar, not just a mutation guard.
                mutate(model.public)
                model.original_graph = N._history_graph(model.result.__dict__, model.public)
                with self.assertRaises(Exception):
                    model.invoke()
                self.assertEqual(model.writes, [])

    def test_list_equal_tuple_subclass_or_missing_return_field_is_rejected(self):
        class TupleAlias(tuple):
            pass
        for kind in (list, TupleAlias, lambda value: value[:2]):
            with self.subTest(kind=kind.__name__), OutputModel(self, "prepare-save") as model:
                model.return_override = kind(model.returned)
                with self.assertRaises(Exception):
                    model.invoke()
                self.assertEqual(model.writes, [])

    def test_unregistered_or_subclass_adapter_fence_cannot_be_adopted(self):
        class FenceAlias(A._OutputFence):
            __slots__ = ()
        for kind in (A._OutputFence, FenceAlias):
            with self.subTest(kind=kind.__name__), OutputModel(self, "prepare-save") as model:
                model.return_override = model.public, kind(), END
                with self.assertRaises(Exception):
                    model.invoke()
                self.assertEqual(model.writes, [])

    def test_equal_result_clone_or_parent_clone_is_not_original_terminal(self):
        for field in (1, 2):
            with self.subTest(field=field), OutputModel(self, "prepare-save") as model:
                changed = list(model.registration)
                changed[field] = dataclasses.replace(changed[field])
                A._OUTPUTS[id(model.adapter_fence)] = tuple(changed)
                with self.assertRaises(Exception):
                    model.invoke()
                self.assertEqual(model.writes, [])

    def test_nonoriginal_end_boolean_or_equal_new_integer_cannot_be_adopted(self):
        for end in (True, END - 1, float(END), int(str(END))):
            with self.subTest(kind=type(end).__name__), OutputModel(self, "prepare-save") as model:
                self.assertIsNot(end, model.result.hard_end_ns)
                model.return_override = model.public, model.adapter_fence, end
                with self.assertRaises(Exception):
                    model.invoke()
                self.assertEqual(model.writes, [])

    def test_early_adoption_and_append_cannot_assert_helper_return(self):
        for name in ("_adopt", "append"):
            with self.subTest(name=name), OutputModel(self) as model:
                fence = model.begin()
                with self.assertRaises(Exception):
                    fence._adopt(model.returned) if name == "_adopt" else fence.append()
                with self.assertRaises(Exception):
                    model.invoke()
                self.assertEqual(model.writes, [])

    def test_pre_entry_p_method_or_writer_substitution_is_not_a_load_baseline(self):
        for owner, name in ((P, "productive"), (P, "require"), (P, "_credential_free"), (C, "_append_output_bytes")):
            with self.subTest(name=name), OutputModel(self) as model:
                with patch.object(owner, name, lambda *_args, **_kwargs: None), self.assertRaises(Exception):
                    model.begin()
                self.assertEqual(model.writes, [])

    def test_callback_adapter_method_registry_or_supplier_replacement_is_rejected(self):
        for owner, name in ((A, "prepare_save"), (A._OutputFence, "_checked"), (A._OutputFence, "now"),
                (A._Window, "_sample"), (A._Window, "_state"), (A, "_PHASES"), (A, "_WINDOWS"),
                (A, "_OUTPUTS"), (A, "_PINS"), (A, "P"), (C, "_append_output_bytes"),
                (P._StepOutputFence, "_static"), (P, "_step_output_bytes")):
            with self.subTest(name=name), OutputModel(self, "prepare-save") as model:
                original = getattr(owner, name)
                replacement = {} if type(original) is dict else (lambda *_args, **_kwargs: None)
                model.source_action = lambda: model.stack.enter_context(patch.object(owner, name, replacement))
                with self.assertRaises(Exception):
                    model.invoke()
                self.assertEqual(model.writes, [])

    def test_precall_adapter_anchor_also_protects_cancellation_callback(self):
        with OutputModel(self) as model:
            def change():
                model.stack.enter_context(patch.object(A, "_SEQUENCES", dict(A._SEQUENCES)))
            model.cancel_action = change
            with self.assertRaises(Exception):
                model.invoke()
            self.assertEqual((model.source_calls, model.writes), (0, []))

    def test_same_reference_sequence_mutation_is_detected(self):
        with OutputModel(self, "prepare-save") as model:
            original = A._SEQUENCES["prepare-save"]
            try:
                model.source_action = lambda: A._SEQUENCES.__setitem__("prepare-save", ("changed",))
                with self.assertRaises(Exception):
                    model.invoke()
                self.assertEqual(model.writes, [])
            finally:
                A._SEQUENCES["prepare-save"] = original

    def test_same_reference_phase_budget_mutation_is_detected(self):
        with OutputModel(self, "prepare-save") as model:
            original = A._PHASES["save-transition"]
            try:
                model.source_action = lambda: A._PHASES.__setitem__("save-transition", (("save-transition", 31, 31),))
                with self.assertRaises(Exception):
                    model.invoke()
                self.assertEqual(model.writes, [])
            finally:
                A._PHASES["save-transition"] = original

    def test_changed_public_dictionary_end_or_return_binding_denies_late_stdout(self):
        for field in ("public_result", "__dict__", "hard_end_ns", "bridge-binding", "public-data", "equal-hash", "emitted-hash"):
            with self.subTest(field=field), OutputModel(self) as model:
                model.invoke()
                if field == "bridge-binding":
                    model.fence._binding = tuple(list(model.fence._binding))
                elif field == "public-data":
                    model.public["handoffSha256"] = "c" * 64
                elif field in ("equal-hash", "emitted-hash"):
                    target = model.public if field == "equal-hash" else model.fence._binding[12]
                    original = target["handoffSha256"]
                    replacement = original.encode().decode()
                    self.assertEqual(replacement, original)
                    self.assertIsNot(replacement, original)
                    target["handoffSha256"] = replacement
                else:
                    value = dict(model.result.public_result) if field == "public_result" else (
                        dict(model.result.__dict__) if field == "__dict__" else int(str(END)))
                    object.__setattr__(model.result, field, value)
                with self.assertRaises(Exception):
                    model.late()
                self.assertEqual(len(model.writes), 1)

    def test_replaced_bridge_registry_or_result_registration_denies_late_stdout(self):
        for registry in ("_STEP_OUTPUTS", "_STEP_OUTPUT_CALLS", "_STEP_OUTPUT_RESULTS"):
            with self.subTest(registry=registry), OutputModel(self) as model:
                model.invoke()
                with patch.object(P, registry, dict(getattr(P, registry))), self.assertRaises(Exception):
                    model.late()

    def test_same_operation_attempt_reuse_poisons_original_without_second_source_call(self):
        with OutputModel(self) as model:
            model.invoke()
            with self.assertRaises(Exception):
                P._StepOutputFence("produce", lambda: None)
            with self.assertRaises(Exception):
                model.late()
            self.assertEqual((model.source_calls, len(model.writes)), (1, 1))

    def test_registered_result_reuse_is_rejected_before_append(self):
        with OutputModel(self) as model:
            fence = model.begin()
            saved = P._STEP_OUTPUTS[id(fence)]
            P._STEP_OUTPUT_RESULTS[id(model.result)] = (saved, model.result)
            with self.assertRaises(Exception):
                model.invoke()
            with self.assertRaises(Exception):
                fence.append()
            self.assertEqual(model.writes, [])

    def test_subclass_result_state_and_run_do_not_grant_original_identity(self):
        class ResultAlias(A._StepReturn):
            pass
        class StateAlias(A._ParentState):
            pass
        class RunAlias(A._Run):
            pass
        for field, kind in (("result", ResultAlias), ("state", StateAlias), ("run", RunAlias)):
            with self.subTest(field=field), OutputModel(self, "prepare-save") as model:
                object.__setattr__(getattr(model, field), "__class__", kind)
                with self.assertRaises(Exception):
                    model.invoke()
                self.assertEqual(model.writes, [])

    def test_append_or_run_replay_is_sticky_without_reinvoking_helpers(self):
        for method in ("append", "run"):
            with self.subTest(method=method), OutputModel(self) as model:
                model.invoke()
                with self.assertRaises(Exception):
                    getattr(model.fence, method)()
                with self.assertRaises(Exception):
                    model.late()
                self.assertEqual((model.source_calls, len(model.writes)), (1, 1))

    def test_caught_source_callback_reentry_stays_poisoned(self):
        with OutputModel(self, "prepare-save") as model:
            def reenter():
                try:
                    model.fence.run()
                except Exception:
                    pass
            model.source_action = reenter
            with self.assertRaises(Exception):
                model.invoke()
            model.source_action = lambda: None
            with self.assertRaises(Exception):
                model.fence.append()
            self.assertEqual((model.source_calls, model.writes), (1, []))

    def test_caught_cancellation_reentry_stays_poisoned(self):
        with OutputModel(self) as model:
            def reenter():
                try:
                    model.fence._cancelled()
                except Exception:
                    pass
            model.cancel_action = reenter
            with self.assertRaises(Exception):
                model.invoke()
            model.cancel_action = lambda: None
            with self.assertRaises(Exception):
                model.fence.append()
            self.assertEqual(model.writes, [])

    def test_original_cancellation_first_failure_is_sticky(self):
        with OutputModel(self, "prepare-save") as model:
            first = FirstFailure("EXPLICIT_MODEL_CANCELLED")
            def fail():
                raise first
            model.cancel_action = fail
            with self.assertRaises(FirstFailure) as caught:
                model.invoke()
            self.assertIs(caught.exception, first)
            model.cancel_action = lambda: None
            with self.assertRaises(FirstFailure) as caught:
                model.fence.run()
            self.assertIs(caught.exception, first)
            self.assertEqual(model.writes, [])
            self.assertNotIn(P.O.wire.TOKEN_ENV, os.environ)

    def test_append_failure_stays_poisoned_even_after_supplier_recovers(self):
        with OutputModel(self) as model:
            first = FirstFailure("EXPLICIT_MODEL_APPEND")
            def fail():
                raise first
            model.write_action = fail
            with self.assertRaises(FirstFailure) as caught:
                model.invoke()
            self.assertIs(caught.exception, first)
            model.write_action = lambda: None
            with self.assertRaises(FirstFailure) as caught:
                model.late()
            self.assertIs(caught.exception, first)
            self.assertEqual(model.writes, [])

    def test_original_end_expiry_before_during_or_after_append_has_no_new_window(self):
        for when in ("before", "during", "after"):
            with self.subTest(when=when), OutputModel(self) as model:
                if when == "before":
                    model.raw = END
                elif when == "during":
                    model.write_action = lambda: setattr(model, "raw", END)
                if when == "after":
                    model.invoke()
                    model.raw = END
                    with self.assertRaises(Exception):
                        model.late()
                else:
                    with self.assertRaises(Exception):
                        model.invoke()
                    self.assertEqual(model.writes, [])
                model.raw = 100
                with self.assertRaises(Exception):
                    model.late()

    def test_raw_rollback_after_success_is_rejected_and_cannot_recover(self):
        with OutputModel(self) as model:
            model.invoke()
            model.raw = 99
            with self.assertRaises(Exception):
                model.late()
            model.raw = 101
            with self.assertRaises(Exception):
                model.late()

    def test_exact_late_mode_limit_and_two_calls_only(self):
        for kwargs in ({}, {"final": False, "limit": END}, {"final": True, "minimum": True, "limit": END},
                {"final": True, "minimum": 1, "limit": END}, {"final": True, "limit": END + 1},
                {"final": True, "limit": float(END)}):
            with self.subTest(kwargs=kwargs), OutputModel(self) as model:
                model.invoke()
                with self.assertRaises(Exception):
                    model.fence.now(**kwargs)
                with self.assertRaises(Exception):
                    model.late()

    def test_credential_reappearing_after_helper_or_during_append_is_rejected(self):
        for when in ("after-helper", "during-append", "late"):
            with self.subTest(when=when), OutputModel(self) as model:
                leak = lambda: os.environ.__setitem__("GH_TOKEN", TOKEN_MODEL)
                if when == "after-helper":
                    model.source_action = leak
                elif when == "during-append":
                    model.write_action = leak
                else:
                    model.invoke()
                    leak()
                    with self.assertRaises(Exception):
                        model.late()
                    continue
                with self.assertRaises(Exception):
                    model.invoke()
                self.assertEqual(model.writes, [])

    def test_original_tiny_owned_writer_is_called_by_the_new_bridge(self):
        self.assertTrue(hasattr(os, "geteuid") and os.geteuid() != 0,
            "tiny owned-file control requires a genuine ordinary POSIX UID")
        with OutputModel(self, "prepare-save", real_writer=True) as model, tempfile.TemporaryDirectory(
                prefix="p2pkit-step-output-model-") as temporary:
            base = Path(temporary).resolve()
            directory = base / "_runner_file_commands"
            directory.mkdir(mode=0o700)
            output = directory / "set_output_00112233-4455-6677-8899-aabbccddeeff"
            output.touch(mode=0o600)
            os.environ.update(GITHUB_OUTPUT=str(output), RUNNER_TEMP=str(base))
            public, fence, end = model.invoke()
            self.assertIs(public, model.public)
            self.assertIs(fence, model.fence)
            self.assertEqual(end, END)
            self.assertEqual(output.read_bytes(), model.expected())
            self.assertEqual(C.QUARANTINE, [])
            self.assertEqual((model.late(), model.late()), (100, 100))


class GrammarAndSourceControls(unittest.TestCase):
    def test_exact_five_disjoint_grammar_sets_reject_legacy_final_and_extra_data(self):
        for operation, _scope, names in ROUTES:
            values = {name: "a" * 64 for name in names}
            expected = b"".join(name.encode() + b"=" + b"a" * 64 + b"\n" for name in sorted(names))
            self.assertEqual(P._step_output_bytes(operation, values), expected)
            for bad in ({}, {**values, "initializationSha256": "b" * 64}, {**values, "outcome": "success"},
                    {name: "A" * 64 for name in names}, {name: "a" * 63 for name in names},
                    {name: True for name in names}):
                with self.subTest(operation=operation), self.assertRaises(Exception):
                    P._step_output_bytes(operation, bad)
            with self.assertRaises(Exception):
                C._output_bytes(values)
            with self.assertRaises(Exception):
                C._productive_output_bytes(values)
        for operation in ("custody-export", "custody-collect", "seal", "upload", None):
            with self.assertRaises(Exception):
                P._step_output_bytes(operation, {"probeSha256": "a" * 64})

    def test_load_anchor_roster_includes_preexisting_helpers_writer_and_every_bridge_method(self):
        actual = {(id(owner), name) for owner, name, _value in ORIGINAL_LOAD}
        for owner, names in ((P, ("productive", "step", "_credential_free", "_step_output_modules", "_STEP_OUTPUT_CALLS")),
                (C, ("_append_output_bytes", "_output_bytes", "_productive_output_bytes")),
                (P._StepOutputFence, ("_static", "_begin", "_poison", "_cancelled", "run", "_adopt", "_current", "_append_guard", "append", "now"))):
            for name in names:
                self.assertIn((id(owner), name), actual)

    def test_pre_callback_anchors_and_real_helper_return_precede_adoption_and_append(self):
        bridge = next(node for node in SOURCE.body if isinstance(node, ast.ClassDef) and node.name == "_StepOutputFence")
        methods = {node.name: node for node in bridge.body if isinstance(node, ast.FunctionDef)}
        calls = lambda node: sorted((call.lineno, ast.unparse(call.func)) for call in ast.walk(node) if isinstance(call, ast.Call))
        initialize = calls(methods["__init__"])
        self.assertTrue(any(name == "_step_output_modules" for _line, name in initialize))
        self.assertFalse(any(name in ("productive", "step", "cancelled") for _line, name in initialize))
        run = calls(methods["run"])
        position = lambda name: next(line for line, item in run if item == name)
        self.assertLess(position("self._static"), position("productive"))
        self.assertLess(position("step"), position("_credential_free"))
        self.assertLess(position("_credential_free"), position("self._adopt"))
        self.assertLess(position("self._adopt"), position("self.append"))
        self.assertNotIn("TOKEN_ENV", ast.unparse(bridge))
        self.assertFalse(any(name.endswith(("._Window", ".Window", ".observe", ".deadline", ".boot_digest"))
            for _line, name in calls(bridge)))
        self.assertEqual([name for _line, name in calls(methods["append"]) if "append_output" in name], ["C.C._append_output_bytes"])

    def test_unchanged_token_frames_clear_tokens_in_finally_and_cli_only_switches_five_routes(self):
        functions = {node.name: node for node in SOURCE.body if isinstance(node, ast.FunctionDef)}
        for name in ("productive", "step"):
            node = functions[name]
            self.assertTrue(any(isinstance(item, ast.Try) and any(isinstance(tail, ast.Assign) and
                ast.unparse(tail) == "token = None" for tail in item.finalbody) for item in ast.walk(node)))
        calls = [ast.unparse(node.func) for node in ast.walk(CLI) if isinstance(node, ast.Call)]
        for name in ("P.productive_outputs", "P.step_outputs", "P.custody_export", "P.custody_collect", "P.service_child"):
            self.assertEqual(calls.count(name), 1)
        self.assertNotIn("P.productive", calls)
        self.assertNotIn("P.step", calls)
        self.assertIn("PC.productive_crypto_child", ast.unparse(CLI))
        self.assertIn("PC.productive_authority_pre_child", ast.unparse(CLI))
        self.assertIn("PC.productive_authority_post_child", ast.unparse(CLI))


if __name__ == "__main__":
    unittest.main(failfast=True)
