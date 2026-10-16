#!/usr/bin/env python3
"""New productive output models only; no native I/O, token or hosted authority.

PC return/fence and append are explicit in-memory substitutes. These controls
cannot qualify the real PC custody graph, original GitHub Step or native stdout.
"""
from __future__ import annotations

import ast
import ctypes
from contextlib import ExitStack
import dataclasses
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise AssertionError("PRODUCTIVE_OUTPUT_MODEL_SIDE_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import hosted_initial_recipient_productive as P
import hosted_initial_recipient_productive_custody as PC
import hosted_initial_recipient_productive_custody_data as CD

C = P.C.C
SOURCE = ast.parse((ROOT / "scripts/hosted_initial_recipient_productive.py").read_text())


class ModelFence:
    def __init__(self):
        self.raw, self.calls, self.action = 100, 0, lambda: None

    def now(self, *, final=False, minimum=0, limit=None):
        if final is not True or minimum != 0 or limit != 1000000:
            raise AssertionError("MODEL_EXACT_ORIGINAL_FENCE")
        self.calls += 1
        self.action()
        return self.raw


class OutputModels(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(P, "_FINAL_OUTPUTS", {}))
        self.stack.enter_context(patch.object(P, "_FINAL_OUTPUT_RESULTS", {}))
        self.stack.enter_context(patch.object(P, "_credential_free", lambda: None))
        self.stack.enter_context(patch.object(PC, "checked_final_export_return", self.checked))
        self.stack.enter_context(patch.object(PC, "checked_final_collect_return", self.checked))
        self.stack.enter_context(patch.object(C, "append_productive_outputs", self.append))
        self.originals, self.writes = [], []
        self.action = lambda: None
        self.append_action = lambda: None

    def checked(self, value):
        if not any(value is original for original in self.originals):
            raise P.O.OriginError("SYNTHETIC_PC_REJECTS_UNREGISTERED_RETURN")
        self.action()
        return value

    def append(self, values, check):
        check()
        self.append_action()
        check()
        self.writes.append(C._productive_output_bytes(values))
        check()

    def result(self, operation="custody-export"):
        fields = CD.EXPORT_OUTPUT_FIELDS if operation == "custody-export" else CD.COLLECT_OUTPUT_FIELDS
        kind = PC.ParentReturnedCrypto if operation == "custody-export" else PC.CollectReturn
        value = kind(tuple((name, character * 64) for name, character in zip(fields, "ab")), ModelFence(), 1000000)
        self.originals.append(value)
        return value

    def test_both_outputs_append_once_then_exactly_two_late_checks(self):
        for operation in ("custody-export", "custody-collect"):
            value = self.result(operation)
            fence = P._ProductiveOutputFence(value, operation)
            public, returned, end = fence.append()
            self.assertIs(returned, fence)
            self.assertEqual(end, value.hard_end_ns)
            self.assertEqual(public["originalStepOutcome"], "NOT_OBSERVED")
            self.assertEqual(public["testAcceptance"], "NOT_PERFORMED")
            self.assertEqual(public["budgetAcceptance"], "NOT_ADMITTED")
            self.assertNotIn("closedNs", public)
            self.assertTrue(all(public[name] is False for name in
                ("productiveAuthority", "cacheAuthority", "exportSaveAuthority")))
            self.assertEqual(fence.now(final=True, limit=end), 100)
            self.assertEqual(fence.now(final=True, limit=end), 100)
            with self.assertRaises(Exception):
                fence.now(final=True, limit=end)
        self.assertEqual(len(self.writes), 2)

    def test_equal_return_is_not_original(self):
        original = self.result()
        with self.assertRaises(Exception):
            P._ProductiveOutputFence(dataclasses.replace(original), "custody-export")
        self.assertFalse(self.writes)

    def test_second_fence_poisons_original_result_attempt(self):
        original = self.result()
        fence = P._ProductiveOutputFence(original, "custody-export")
        with self.assertRaises(Exception):
            P._ProductiveOutputFence(original, "custody-export")
        with self.assertRaises(Exception):
            fence.append()
        self.assertFalse(self.writes)

    def test_equal_output_tuple_replacement_is_rejected(self):
        original = self.result()
        fence = P._ProductiveOutputFence(original, "custody-export")
        object.__setattr__(original, "output_values", tuple(list(original.output_values)))
        with self.assertRaises(Exception):
            fence.append()

    def test_equal_end_field_replacement_is_rejected(self):
        original = self.result()
        fence = P._ProductiveOutputFence(original, "custody-export")
        object.__setattr__(original, "hard_end_ns", int(str(original.hard_end_ns)))
        with self.assertRaises(Exception):
            fence.append()

    def test_caught_reentry_is_sticky_before_any_append(self):
        fence = P._ProductiveOutputFence(self.result(), "custody-export")
        def reenter():
            try:
                fence.append()
            except Exception:
                pass
        self.action = reenter
        with self.assertRaises(Exception):
            fence.append()
        self.action = lambda: None
        with self.assertRaises(Exception):
            fence.append()
        self.assertFalse(self.writes)

    def test_append_failure_cannot_be_promoted_by_later_output(self):
        fence = P._ProductiveOutputFence(self.result(), "custody-export")
        def fail():
            raise RuntimeError("SYNTHETIC_APPEND_FAILURE")
        self.append_action = fail
        with self.assertRaisesRegex(RuntimeError, "SYNTHETIC_APPEND_FAILURE"):
            fence.append()
        with self.assertRaises(Exception):
            fence.now(final=True, limit=1000000)

    def test_clock_exhaustion_after_append_denies_late_stdout(self):
        original = self.result()
        fence = P._ProductiveOutputFence(original, "custody-export")
        fence.append()
        original.fence.raw = original.hard_end_ns
        with self.assertRaises(Exception):
            fence.now(final=True, limit=original.hard_end_ns)

    def test_changed_pc_checker_is_not_adopted(self):
        fence = P._ProductiveOutputFence(self.result(), "custody-export")
        with patch.object(PC, "checked_final_export_return", lambda value: value), self.assertRaises(Exception):
            fence.append()

    def test_changed_fence_method_is_not_adopted(self):
        fence = P._ProductiveOutputFence(self.result(), "custody-export")
        with patch.object(ModelFence, "now", lambda *_args, **_kwargs: 100), self.assertRaises(Exception):
            fence.append()


class OutputGrammarControls(unittest.TestCase):
    def test_legacy_and_productive_encoders_remain_disjoint(self):
        original = {"initializationSha256": "a" * 64}
        productive = dict(zip(CD.EXPORT_OUTPUT_FIELDS, ("b" * 64, "c" * 64)))
        self.assertEqual(C._output_bytes(original), b"initializationSha256=" + b"a" * 64 + b"\n")
        self.assertEqual(C._productive_output_bytes(productive), b"".join(
            name.encode() + b"=" + productive[name].encode() + b"\n" for name in sorted(productive)))
        with self.assertRaises(Exception):
            C._output_bytes(productive)
        with self.assertRaises(Exception):
            C._productive_output_bytes(original)

    def test_unknown_extra_uppercase_or_nonstring_output_refuses(self):
        good = dict(zip(CD.COLLECT_OUTPUT_FIELDS, ("a" * 64, "b" * 64)))
        for changed in ({**good, "closedNs": 100}, {**good, CD.COLLECT_OUTPUT_FIELDS[0]: "A" * 64},
                {**good, CD.COLLECT_OUTPUT_FIELDS[0]: True}, {**good, CD.COLLECT_OUTPUT_FIELDS[1]: "f" * 63}):
            with self.subTest(changed=tuple(changed)), self.assertRaises(Exception):
                C._productive_output_bytes(changed)

    def test_both_encoders_call_the_one_shared_native_body(self):
        # This regression tests dispatch only, not a synthetic file-command claim.
        values = {"initializationSha256": "a" * 64}
        productive = dict(zip(CD.EXPORT_OUTPUT_FIELDS, ("b" * 64, "c" * 64)))
        check = lambda: None
        with patch.object(C, "_append_output_bytes", return_value="MODEL") as body:
            self.assertEqual(C.append_outputs(values, check), "MODEL")
            self.assertEqual(C.append_productive_outputs(productive, check), "MODEL")
            self.assertEqual(body.call_args_list[0].args, (C._output_bytes(values), check))
            self.assertEqual(body.call_args_list[1].args, (C._productive_output_bytes(productive), check))

    def test_token_helpers_are_separate_returned_frames(self):
        functions = {node.name: node for node in SOURCE.body if isinstance(node, ast.FunctionDef)}
        for operation, helper, effect in (("custody_export", "_prepare_custody_export", "PC.export_prepared_final"),
                ("custody_collect", "_prepare_custody_collect", "PC.finish_final_collect")):
            calls = sorted((node.lineno, ast.unparse(node.func)) for node in ast.walk(functions[operation])
                if isinstance(node, ast.Call))
            self.assertLess(next(line for line, name in calls if name == helper),
                next(line for line, name in calls if name == effect))
            self.assertNotIn("TOKEN_ENV", ast.unparse(functions[operation]))
            self.assertTrue(any(isinstance(node, ast.Try) and node.finalbody for node in ast.walk(functions[helper])))


if __name__ == "__main__":
    unittest.main(failfast=True)
