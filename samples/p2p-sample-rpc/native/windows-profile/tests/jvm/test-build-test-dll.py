#!/usr/bin/env python3
"""Deterministic compiler-budget regressions; no compiler, DLL or native call executes."""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).with_name("build-test-dll.py")
SPEC = importlib.util.spec_from_file_location("test_dll_compiler", SCRIPT)
COMPILER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(COMPILER)


class BudgetTests(unittest.TestCase):
    def progress(self, available=150):
        return {"started": 100, "deadline": 100 + available, "stage": "COMPILE", "timeout": "NONE", "output": None}

    def test_tool_phase_limit_is_not_extended(self):
        with patch.object(COMPILER.time, "monotonic", return_value=100):
            self.assertEqual(COMPILER.remaining(self.progress(), 15), 15)
            self.assertEqual(COMPILER.remaining(self.progress(), 60), 60)

    def test_tool_limit_shrinks_to_original_total_budget(self):
        with patch.object(COMPILER.time, "monotonic", return_value=100):
            self.assertEqual(COMPILER.remaining(self.progress(7), 60), 7)

    def test_exclusive_deadline_refuses_before_launch(self):
        for available in (0, -1):
            progress = self.progress(available)
            with patch.object(COMPILER.time, "monotonic", return_value=100), \
                    patch.object(COMPILER.subprocess, "run") as run:
                with self.assertRaises(TimeoutError):
                    COMPILER.git(progress, "rev-parse", "HEAD")
                run.assert_not_called()
                self.assertEqual(progress["timeout"], "CUMULATIVE")

    def test_git_uses_its_unchanged_phase_cap(self):
        with patch.object(COMPILER.time, "monotonic", return_value=100), \
                patch.object(COMPILER.subprocess, "run", return_value=
                             subprocess.CompletedProcess([], 0, b"source\n", b"")) as run:
            self.assertEqual(COMPILER.git(self.progress(), "rev-parse", "HEAD"), b"source\n")
            self.assertEqual(run.call_args.kwargs["timeout"], 15)

    def test_git_phase_timeout_is_recorded(self):
        progress = self.progress()
        with patch.object(COMPILER.time, "monotonic", return_value=100), \
                patch.object(COMPILER.subprocess, "run", side_effect=subprocess.TimeoutExpired(["git"], 15)):
            with self.assertRaises(subprocess.TimeoutExpired):
                COMPILER.git(progress, "rev-parse", "HEAD")
        self.assertEqual(progress["timeout"], "PHASE")

    def test_git_total_timeout_is_recorded(self):
        progress = self.progress(3)
        with patch.object(COMPILER.time, "monotonic", return_value=100), \
                patch.object(COMPILER.subprocess, "run", side_effect=subprocess.TimeoutExpired(["git"], 3)) as run:
            with self.assertRaises(subprocess.TimeoutExpired):
                COMPILER.git(progress, "rev-parse", "HEAD")
            self.assertEqual(run.call_args.kwargs["timeout"], 3)
        self.assertEqual(progress["timeout"], "CUMULATIVE")

    def test_successful_git_after_total_deadline_is_not_accepted(self):
        progress = self.progress(3)
        with patch.object(COMPILER.time, "monotonic", side_effect=[100, 103]), \
                patch.object(COMPILER.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"ok", b"")):
            with self.assertRaises(TimeoutError):
                COMPILER.git(progress, "rev-parse", "HEAD")
        self.assertEqual(progress["timeout"], "CUMULATIVE")

    def test_hash_checks_the_total_budget_between_chunks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inert.bin"
            path.write_bytes(b"x" * 65537)
            progress = self.progress(2)
            with patch.object(COMPILER.time, "monotonic", side_effect=[100, 101, 102]):
                with self.assertRaises(TimeoutError):
                    COMPILER.digest(path, progress)
            self.assertEqual(progress["timeout"], "CUMULATIVE")

    def test_bounded_hash_still_returns_the_original_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "inert.bin"
            path.write_bytes(b"fixture")
            with patch.object(COMPILER.time, "monotonic", return_value=100):
                self.assertEqual(COMPILER.digest(path, self.progress()),
                                 {"bytes": 7, "sha256": hashlib.sha256(b"fixture").hexdigest()})

    def test_failure_retains_private_detail_and_closed_public_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            original = b'{"original":"receipt"}\n'
            (output / "compiler-receipt.json").write_bytes(original)

            def refuse(progress):
                self.assertEqual(progress["deadline"] - progress["started"], 150)
                progress.update(stage="COMPILE", timeout="PHASE", output=output)
                raise RuntimeError("SYNTHETIC_PRIVATE_DETAIL")

            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.object(COMPILER, "compile_fixture", side_effect=refuse), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(COMPILER.main(), 1)
            self.assertEqual(stdout.getvalue(), "")
            self.assertEqual(stderr.getvalue(), "WINDOWS_TEST_DLL_COMPILE_REFUSED stage=COMPILE timeout=PHASE\n")
            self.assertEqual((output / "compiler-receipt.json").read_bytes(), original)
            self.assertIn("SYNTHETIC_PRIVATE_DETAIL", (output / "compiler-failure-detail.log").read_text())

    def test_pre_receipt_failure_creates_only_a_failure_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)

            def refuse(progress):
                progress["output"] = output
                raise ValueError("synthetic")

            with patch.object(COMPILER, "compile_fixture", side_effect=refuse), \
                    contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(COMPILER.main(), 1)
            receipt = json.loads((output / "compiler-receipt.json").read_text())
            self.assertEqual(receipt["result"], "FAIL")
            self.assertEqual(receipt["nativeExecution"], "NOT_PERFORMED")
            self.assertNotIn("dll", receipt)

    def test_only_compiler_wrapper_has_a_distinct_total_budget(self):
        root = SCRIPT.resolve().parents[6]
        checker = ast.parse((root / "scripts/tests/check-rpc-windows-loader-jdk21.py").read_text())
        run = next(node for node in ast.walk(checker) if isinstance(node, ast.FunctionDef) and node.name == "run")
        self.assertEqual(run.args.args[-1].arg, "timeout")
        self.assertEqual(ast.literal_eval(run.args.defaults[-1]), 60)
        overrides = [(node, key) for node in ast.walk(checker) if isinstance(node, ast.Call) and
                     isinstance(node.func, ast.Name) and node.func.id == "run"
                     for key in node.keywords if key.arg == "timeout"]
        self.assertEqual(len(overrides), 1)
        self.assertEqual(ast.literal_eval(overrides[0][0].args[0]), "compile-deny-storage-dll")
        self.assertEqual(ast.literal_eval(overrides[0][1].value), 180)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(BudgetTests)
    transcript = io.StringIO()
    result = unittest.TextTestRunner(stream=transcript).run(suite)
    if not result.wasSuccessful():
        print(transcript.getvalue())
        raise SystemExit(1)
    print("WINDOWS_TEST_DLL_BUDGET_CONTROLS_PASS tests=12 scope=INERT_CLOCK_NO_COMPILER_OR_NATIVE_EXECUTION")
