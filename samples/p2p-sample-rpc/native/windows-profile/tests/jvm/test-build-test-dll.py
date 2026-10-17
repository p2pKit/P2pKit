#!/usr/bin/env python3
"""Deterministic compiler-budget regressions; no compiler, DLL or native call executes."""
import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

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
                # Fractional clocks need not round-trip through subtraction exactly.
                # Check the actual unchanged deadline contract, not float cancellation.
                self.assertEqual(progress["started"], 106.1)
                self.assertEqual(progress["deadline"], progress["started"] + 150)
                progress.update(stage="COMPILE", timeout="PHASE", output=output)
                raise RuntimeError("SYNTHETIC_PRIVATE_DETAIL")

            stdout, stderr = io.StringIO(), io.StringIO()
            with patch.object(COMPILER.time, "monotonic", return_value=106.1), \
                    patch.object(COMPILER, "compile_fixture", side_effect=refuse), \
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

    def test_compiler_environment_is_direct_and_never_inherits_or_mutates_ambient_setup(self):
        # The former child-only telemetry opt-out is superseded: no VS setup or its telemetry runs at all.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sdk = {"bin": root / "sdk/bin", "include": [root / "sdk/include"], "lib": [root / "sdk/lib"]}
            hostile = {"PATH": "UNTRUSTED", "CL": "@private.rsp", "_CL_": "/unsafe", "LINK": "/unsafe",
                       "_LINK_": "/unsafe", "INCLUDE": "UNTRUSTED", "LIB": "UNTRUSTED",
                       "LIBPATH": "UNTRUSTED", "VSCMD_SKIP_SENDTELEMETRY": "0"}
            with patch.dict(os.environ, hostile, clear=True):
                before = dict(os.environ)
                environment = COMPILER.child_environment(root / "system", root / "output", root / "vc", sdk)
                self.assertEqual(dict(os.environ), before)
            self.assertEqual(environment["PATH"].split(";"),
                             [str(root / "vc/bin/Hostx64/x64"), str(root / "sdk/bin"), str(root / "system/System32")])
            self.assertEqual(environment["INCLUDE"], str(root / "vc/include") + ";" + str(root / "sdk/include"))
            self.assertEqual(environment["LIB"], str(root / "vc/lib/x64") + ";" + str(root / "sdk/lib"))
            for name in ("CL", "_CL_", "LINK", "_LINK_", "LIBPATH", "ComSpec", "VSCMD_SKIP_SENDTELEMETRY"):
                self.assertNotIn(name, environment)

    def test_only_two_fixed_compiler_wrappers_have_distinct_total_budgets(self):
        root = SCRIPT.resolve().parents[6]
        checker = ast.parse((root / "scripts/tests/check-rpc-windows-loader-jdk21.py").read_text())
        run = next(node for node in ast.walk(checker) if isinstance(node, ast.FunctionDef) and node.name == "run")
        self.assertEqual(run.args.args[-1].arg, "timeout")
        self.assertEqual(ast.literal_eval(run.args.defaults[-1]), 60)
        overrides = [(node, key) for node in ast.walk(checker) if isinstance(node, ast.Call) and
                     isinstance(node.func, ast.Name) and node.func.id == "run"
                     for key in node.keywords if key.arg == "timeout"]
        self.assertEqual(len(overrides), 2)
        self.assertEqual({ast.literal_eval(node.args[0]): ast.literal_eval(key.value)
                          for node, key in overrides},
                         {"compile-deny-storage-dll": 180, "compile-protected-dll-helper": 180})


class SelectionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        clock = patch.object(COMPILER.time, "monotonic", return_value=100)
        clock.start()
        self.addCleanup(clock.stop)
        self.progress = {"started": 100, "deadline": 250, "stage": "INVENTORY", "timeout": "NONE"}

    def sdk(self, version, complete=True):
        root = self.root / "sdk"
        include = root / "Include" / version
        include.mkdir(parents=True)
        if complete:
            for relative in ("ucrt/stdio.h", "shared/ntdef.h", "um/Windows.h"):
                path = include / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"inert-header")
            for kind, name in (("ucrt", "libucrt.lib"), ("um", "kernel32.lib")):
                path = root / "Lib" / version / kind / "x64" / name
                path.parent.mkdir(parents=True)
                path.write_bytes(b"inert-library")
            (root / "bin" / version / "x64").mkdir(parents=True)
        return root

    def vc(self, version="14.44.35207"):
        root = self.root / "vs"
        selection = root / "VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt"
        selection.parent.mkdir(parents=True)
        selection.write_text(version + "\n", encoding="ascii")
        tools = root / "VC/Tools/MSVC" / version
        for relative in ("bin/Hostx64/x64/cl.exe", "bin/Hostx64/x64/link.exe", "include/vcruntime.h",
                         "lib/x64/libcmt.lib", "lib/x64/libvcruntime.lib", "lib/x64/oldnames.lib"):
            path = tools / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"inert-not-executable")
        return root, selection, tools

    def test_default_vc_version_selects_only_exact_host_x64_tools(self):
        root, selection, tools = self.vc()
        observed = COMPILER.selected_vc(root, self.progress)
        self.assertEqual(observed["root"], tools)
        self.assertEqual(observed["version"], "14.44.35207")
        self.assertIn(selection, observed["inputs"])
        self.assertIn(tools / "bin/Hostx64/x64/cl.exe", observed["inputs"])

    def test_default_vc_version_refuses_malformed_or_unbounded_selection(self):
        root, selection, _ = self.vc()
        for value in ("../elsewhere", "14.44", "014.44.35207", "14.44.35207.0", "14.44.65536", "1" * 129):
            selection.write_text(value, encoding="ascii")
            with self.assertRaises(ValueError):
                COMPILER.selected_vc(root, self.progress)

    def test_default_vc_missing_original_linker_is_not_a_path_fallback(self):
        root, _, tools = self.vc()
        (tools / "bin/Hostx64/x64/link.exe").unlink()
        with self.assertRaises(FileNotFoundError):
            COMPILER.selected_vc(root, self.progress)

    def test_default_vc_selection_must_match_the_original_hashed_bytes(self):
        root, _, _ = self.vc()
        with patch.object(COMPILER, "digest", return_value={"bytes": 12, "sha256": "0" * 64}):
            with self.assertRaisesRegex(ValueError, "bytes changed before selection"):
                COMPILER.selected_vc(root, self.progress)

    def test_sdk_numeric_selection_is_not_lexicographic(self):
        self.sdk("10.0.9.0")
        root = self.sdk("10.0.10.0")
        result = COMPILER.selected_sdk(root, self.progress)
        self.assertEqual(result["version"], "10.0.10.0")
        self.assertEqual([path.name for path in result["include"]], ["ucrt", "shared", "um"])
        self.assertEqual([path.parent.name for path in result["lib"]], ["ucrt", "um"])

    def test_sdk_skips_incomplete_newer_installation_but_records_it(self):
        self.sdk("10.0.10.0")
        root = self.sdk("10.0.11.0", complete=False)
        result = COMPILER.selected_sdk(root, self.progress)
        self.assertEqual(result["version"], "10.0.10.0")
        self.assertEqual(result["inventory"], [{"version": "10.0.10.0", "complete": True},
                                             {"version": "10.0.11.0", "complete": False}])

    def test_sdk_requires_one_complete_installed_version(self):
        root = self.sdk("10.0.10.0", complete=False)
        with self.assertRaises(ValueError):
            COMPILER.selected_sdk(root, self.progress)

    def test_sdk_rejects_malformed_version_names_without_using_lower_fallback(self):
        root = self.sdk("10.0.10.0")
        for value in ("10.0.010.0", "10.0.10.0-preview", "11.0.10.0", "10.0.65536.0"):
            malformed = root / "Include" / value
            malformed.mkdir()
            with self.assertRaises(ValueError):
                COMPILER.selected_sdk(root, self.progress)
            malformed.rmdir()

    def test_sdk_duplicate_numeric_observations_are_ambiguous(self):
        root = self.sdk("10.0.10.0")
        entry = SimpleNamespace(path=str(root / "Include/10.0.10.0"))
        with patch.object(COMPILER.os, "scandir", return_value=contextlib.nullcontext(iter([entry, entry]))):
            with self.assertRaises(ValueError):
                COMPILER.selected_sdk(root, self.progress)

    def test_sdk_inventory_is_bounded_before_unlimited_directory_work(self):
        root = self.sdk("10.0.10.0")
        entry = SimpleNamespace(path=str(root / "Include/10.0.10.0"))
        with patch.object(COMPILER.os, "scandir", return_value=contextlib.nullcontext(iter([entry] * 65))):
            with self.assertRaisesRegex(ValueError, "inventory exceeds"):
                COMPILER.selected_sdk(root, self.progress)

    def test_sdk_selection_preserves_original_total_deadline(self):
        root = self.sdk("10.0.10.0")
        self.progress["deadline"] = 100
        with self.assertRaises(TimeoutError):
            COMPILER.selected_sdk(root, self.progress)
        self.assertEqual(self.progress["timeout"], "CUMULATIVE")

    def test_registered_roots_allow_missing_view_but_never_disagreement_or_bad_values(self):
        root = self.sdk("10.0.10.0")
        other = self.root / "other"
        other.mkdir()
        self.assertEqual(COMPILER.reconcile_sdk_roots([str(root)]), root)
        self.assertEqual(COMPILER.reconcile_sdk_roots([str(root), str(root)]), root)
        for values in ([], [str(root), str(other)], [None], ["relative"], [str(root) + "\x00"]):
            with self.assertRaises(ValueError):
                COMPILER.reconcile_sdk_roots(values)

    def test_reparsed_installed_directory_is_not_accepted(self):
        path = Mock()
        path.lstat.return_value = SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        path.is_symlink.return_value = False
        with self.assertRaises(ValueError):
            COMPILER.directory(path)

    def test_registered_root_reparse_is_refused_before_resolution(self):
        path = MagicMock()
        path.__str__.return_value = "/inert"
        path.is_absolute.return_value = True
        path.lstat.return_value = SimpleNamespace(st_mode=stat.S_IFDIR, st_file_attributes=0x400)
        path.is_symlink.return_value = False
        with patch.object(COMPILER, "Path", return_value=path):
            with self.assertRaises(ValueError):
                COMPILER.reconcile_sdk_roots(["/inert"])
        path.resolve.assert_not_called()

    def test_fixed_registry_queries_only_request_both_read_only_views(self):
        root = self.sdk("10.0.10.0")
        registry = SimpleNamespace(HKEY_LOCAL_MACHINE=1, KEY_QUERY_VALUE=2, KEY_WOW64_64KEY=4,
                                   KEY_WOW64_32KEY=8, REG_SZ=10)
        registry.OpenKey = Mock(side_effect=lambda *args: contextlib.nullcontext("key"))
        registry.QueryValueEx = Mock(return_value=(str(root), registry.REG_SZ))
        with patch.dict(sys.modules, {"winreg": registry}):
            self.assertEqual(COMPILER.registered_sdk_root(), root)
        self.assertEqual(registry.OpenKey.call_args_list,
                         [unittest.mock.call(1, r"SOFTWARE\Microsoft\Windows Kits\Installed Roots", 0, 6),
                          unittest.mock.call(1, r"SOFTWARE\Microsoft\Windows Kits\Installed Roots", 0, 10)])
        self.assertEqual(registry.QueryValueEx.call_args_list,
                         [unittest.mock.call("key", "KitsRoot10")] * 2)

    def test_registry_query_refuses_expandable_strings_instead_of_environment_expansion(self):
        registry = SimpleNamespace(HKEY_LOCAL_MACHINE=1, KEY_QUERY_VALUE=2, KEY_WOW64_64KEY=4,
                                   KEY_WOW64_32KEY=8, REG_SZ=10)
        registry.OpenKey = Mock(side_effect=lambda *args: contextlib.nullcontext("key"))
        registry.QueryValueEx = Mock(return_value=("%UNTRUSTED%", 11))
        with patch.dict(sys.modules, {"winreg": registry}):
            with self.assertRaisesRegex(ValueError, "not an exact string"):
                COMPILER.registered_sdk_root()

    def test_compiler_is_direct_argv_and_never_a_shell_or_setup_script(self):
        source = ast.parse(SCRIPT.read_text())
        calls = [node for node in ast.walk(source) if isinstance(node, ast.Call)]
        compile_call = next(node for node in calls if isinstance(node.func, ast.Name) and node.func.id == "run" and
                            node.args and isinstance(node.args[0], ast.Constant) and node.args[0].value == "compile-dll")
        self.assertEqual(compile_call.args[1].id, "recipe")
        self.assertEqual(len(compile_call.args), 2)
        self.assertEqual(compile_call.keywords, [])
        direct = next(node for node in calls if isinstance(node.func, ast.Attribute) and node.func.attr == "run" and
                      any(key.arg == "env" for key in node.keywords))
        self.assertIs(ast.literal_eval(next(key.value for key in direct.keywords if key.arg == "shell")), False)
        self.assertFalse(any(isinstance(node, ast.FunctionDef) and node.name in ("batch", "quoted")
                             for node in ast.walk(source)))
        strings = [node.value for node in ast.walk(source) if isinstance(node, ast.Constant) and
                   isinstance(node.value, str)]
        self.assertFalse(any("VsDevCmd" in value or "cmd.exe" in value for value in strings))


if __name__ == "__main__":
    suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(case)
                               for case in (BudgetTests, SelectionTests))
    transcript = io.StringIO()
    result = unittest.TextTestRunner(stream=transcript).run(suite)
    if not result.wasSuccessful() or result.testsRun != 30:
        print(transcript.getvalue())
        raise SystemExit(1)
    print("WINDOWS_TEST_DLL_BUDGET_CONTROLS_PASS tests=30 scope=INERT_CLOCK_NO_COMPILER_OR_NATIVE_EXECUTION")
