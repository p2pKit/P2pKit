#!/usr/bin/env python3
"""Bounded DATA/owned-file controls, not runner/tool or hosted qualification.

Native Node normalization vectors below are independent expected spellings,
not calls to a provider, boot API, shell or downloaded interpreter. The hosted
caller and executable observations are explicitly labelled test models. Only
small ordinary-UID files in the test-owned temporary directory are real I/O.
"""
from __future__ import annotations

import ast
from contextlib import ExitStack
import ctypes
import importlib.util
import io
import os
from pathlib import Path
import stat
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def offline(event, _args):
    if event.startswith(("subprocess.", "socket.")) or event in (
            "os.system", "os.exec", "os.posix_spawn", "os.fork", "os.forkpty", "pty.spawn", "ctypes.dlopen"):
        raise AssertionError("RUNNER_TOOLS_MODEL_SIDE_EFFECT")


sys.addaudithook(offline)
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("runner_tools_models", ROOT / "scripts/initial-recipient-runner-tools.py")
T = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = T
SPEC.loader.exec_module(T)
C = T.C
OUTPUT_NAME = "set_output_00112233-4455-6677-8899-aabbccddeeff"
SOURCE = ast.parse((ROOT / "scripts/initial-recipient-runner-tools.py").read_text())


class NativeSpellingControls(unittest.TestCase):
    def test_posix_absolute_normalized_vectors_preserve_original_spelling(self):
        # Node posix.normalize preserves one trailing slash, unlike normpath.
        for value in ("/", "/usr/bin", "/usr/bin/", "/a b/\u03bb", "/a:b", "/a\\b"):
            with self.subTest(value=value):
                self.assertIs(T._absolute(value, False), value)
        for value in ("", "relative", "./relative", "//", "//server/share", "///usr/bin", "/a//b", "/a//",
                "/a/./b", "/a/../b", "/.", "/..", "/a/.", "/a/.."):
            with self.subTest(value=value), self.assertRaises(C.ContinuityError):
                T._absolute(value, False)

    def test_windows_drive_native_root_unc_and_trailing_separator_vectors(self):
        # A UNC server/share root without its trailing slash is NOT normalized.
        good = ("C:\\", "z:\\tools", "C:\\tools\\", "\\", "\\Windows\\", "\\\\server\\share\\",
            "\\\\server\\share\\tools", "\\\\server\\share\\tools\\", "C:\\space here\\\u03bb")
        for value in good:
            with self.subTest(value=value):
                self.assertIs(T._absolute(value, True), value)
        bad = ("", "C:", "C:relative", "c:/tools", "/c/tools", "\\\\server", "\\\\server\\share",
            "\\\\server\\share\\\\", "\\\\\\server\\share\\", "C:\\\\tools", "C:\\a\\.\\b",
            "C:\\a\\..\\b", "C:\\a\\\\b", "C:\\a\\\\", "\\a\\..", "\\\\server\\share\\a\\.")
        for value in bad:
            with self.subTest(value=value), self.assertRaises(C.ContinuityError):
                T._absolute(value, True)

    def test_all_control_characters_are_refused_in_each_data_field(self):
        for number in (*range(32), 127):
            for windows, executable, tool_path in ((False, "/usr/bin/python3", "/usr/bin"),
                    (True, "C:\\Python\\python.exe", "C:\\Python")):
                with self.subTest(codepoint=number, windows=windows):
                    with self.assertRaises(C.ContinuityError):
                        T._values(executable + chr(number), tool_path, windows)
                    with self.assertRaises(C.ContinuityError):
                        T._values(executable, tool_path + chr(number), windows)

    def test_utf16_length_not_unicode_codepoint_count_and_no_surrogates(self):
        self.assertEqual(T._units("\U0001f600"), 2)
        exact = "/" + "\U0001f600" * 2047 + "a"
        self.assertEqual(T._units(exact), 4096)
        self.assertIs(T._absolute(exact, False), exact)
        for value in (exact + "a", "/" + "a" * 4096, "/\ud800", "/\udfff", None, b"/usr/bin", True):
            with self.subTest(kind=type(value).__name__), self.assertRaises(C.ContinuityError):
                T._absolute(value, False)
        with self.assertRaises(C.ContinuityError):
            T._absolute("/usr/bin", 0)

    def test_exact_python_basename_on_both_native_path_grammars(self):
        for windows, prefix, path in ((False, "/usr/bin/", "/usr/bin:/opt/tools/"),
                (True, "C:\\Python\\", "C:\\Python;C:\\Windows\\")):
            for name in ("python", "python3", "python3.12", "python.exe", "python3.exe", "python3.12.exe"):
                with self.subTest(windows=windows, name=name):
                    self.assertEqual(T._values(prefix + name, path, windows), (("python", prefix + name), ("tool-path", path)))
            for name in ("Python", "python2", "python3.", "python3.12d", "python3.\u0661", "python3x", "bash", "python3/"):
                with self.subTest(windows=windows, name=name), self.assertRaises(C.ContinuityError):
                    T._values(prefix + name, path, windows)

    def test_path_uses_native_delimiter_without_filtering_or_bash_substitution(self):
        bad = ((False, "/usr/bin/python3", "/usr/bin::/opt/tools"),
            (False, "/usr/bin/python3", "/usr/bin:"), (False, "/usr/bin/python3", ":/usr/bin"),
            (False, "/usr/bin/python3", "/usr/bin:relative"),
            (True, "C:\\Python\\python.exe", "C:\\Python;;C:\\Windows"),
            (True, "C:\\Python\\python.exe", "/c/Python:/c/Windows"),
            (True, "C:\\Python\\python.exe", "C:\\Python;relative"))
        for windows, executable, path in bad:
            with self.subTest(windows=windows, path=path), self.assertRaises(C.ContinuityError):
                T._values(executable, path, windows)
        for value in (None, b"/usr/bin", ""):
            with self.assertRaises(C.ContinuityError):
                T._values("/usr/bin/python3", value, False)

    def test_total_path_and_individual_entry_limits_are_both_preserved(self):
        exact = "/a:" * 5461 + "/"
        self.assertEqual(T._units(exact), 16384)
        self.assertEqual(T._values("/usr/bin/python3", exact, False)[1][1], exact)
        for path in (exact + ":/", "/" + "x" * 4096):
            with self.assertRaises(C.ContinuityError):
                T._values("/usr/bin/python3", path, False)

    def test_separate_two_field_encoder_does_not_accept_authority_or_extra_fields(self):
        windows = os.name == "nt"
        executable, path = ("C:\\Python\\python.exe", "C:\\Python;C:\\Windows") if windows else (
            "/usr/bin/python3", "/usr/bin:/opt/tools/")
        good = (("python", executable), ("tool-path", path))
        self.assertEqual(T._encode(good), ("python=" + executable + "\ntool-path=" + path + "\n").encode())
        for value in (list(good), tuple(reversed(good)), (good[0],), (*good, ("success", "true")),
                (good[0], ("tool-path", path), ("initializationSha256", "a" * 64)),
                (good[0], ["tool-path", path])):
            with self.subTest(kind=type(value).__name__), self.assertRaises(C.ContinuityError):
                T._encode(value)
        with self.assertRaises(C.ContinuityError):
            C._output_bytes(dict(good))
        with self.assertRaises(C.ContinuityError):
            C._productive_output_bytes(dict(good))

    def test_native_windows_encoding_retains_semicolons_and_backslashes_as_data(self):
        values = (("python", "C:\\Python\\python.exe"), ("tool-path", "C:\\Python;\\\\server\\share\\tools\\"))
        # Pure encoder model only: no Windows Path, syscall or native ownership.
        with patch.object(T.os, "name", "nt"):
            self.assertEqual(T._encode(values), b"python=C:\\Python\\python.exe\ntool-path=C:\\Python;\\\\server\\share\\tools\\\n")

    def test_source_is_one_original_writer_without_tool_or_clock_construction(self):
        functions = {node.name: node for node in SOURCE.body if isinstance(node, ast.FunctionDef)}
        calls = [ast.unparse(node.func) for node in ast.walk(functions["observe"]) if isinstance(node, ast.Call)]
        self.assertEqual(calls.count("_WRITER"), 1)
        self.assertNotIn("_append_output_bytes", functions)
        self.assertNotIn("boot_digest", calls)
        self.assertNotIn("subprocess", ast.unparse(SOURCE))
        assignments = [node for node in SOURCE.body if isinstance(node, ast.Assign) and
            any(isinstance(target, ast.Name) and target.id == "_WRITER" for target in node.targets)]
        self.assertEqual(len(assignments), 1)
        self.assertEqual(ast.unparse(assignments[0].value), "C._append_output_bytes")
        for name in ("hosted-cache-provider-action.cjs", "hosted-initial-artifact-action.cjs"):
            text = (ROOT / "scripts" / name).read_text()
            self.assertIn("value.length <= 4096", text)
            self.assertIn("path.isAbsolute(value) && path.normalize(value) === value", text)
            self.assertIn(r"/[\x00-\x1f\x7f]/", text)


class OwnedOutputControls(unittest.TestCase):
    def setUp(self):
        self.assertTrue(hasattr(os, "geteuid") and os.geteuid() != 0,
            "tiny owned-file controls require a genuine ordinary POSIX UID")
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        temporary = self.stack.enter_context(tempfile.TemporaryDirectory(prefix="p2pkit-runner-tools-model-"))
        self.base = Path(temporary).resolve()
        self.commands = self.base / "_runner_file_commands"
        self.commands.mkdir(mode=0o700)
        self.output = self.commands / OUTPUT_NAME
        self.output.touch(mode=0o600)
        self.bin = self.base / "bin"
        self.bin.mkdir(mode=0o700)
        self.executable = self.bin / "python3"
        self.executable.write_bytes(b"MODEL DATA ONLY; NEVER EXECUTED\n")
        self.executable.chmod(0o700)
        self.environment = {"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
            "GITHUB_REPOSITORY": "p2pKit/P2pKit", "RUNNER_OS": "Linux", "PATH": str(self.bin),
            "GITHUB_OUTPUT": str(self.output), "RUNNER_TEMP": str(self.base)}
        self.stack.enter_context(patch.dict(os.environ, self.environment, clear=True))
        self.model_sys = SimpleNamespace(executable=str(self.executable), platform="linux",
            flags=SimpleNamespace(isolated=1, no_site=1, dont_write_bytecode=1),
            argv=[str(ROOT / "scripts/initial-recipient-runner-tools.py")], stderr=io.StringIO())
        self.stack.enter_context(patch.object(T, "sys", self.model_sys))
        self.stack.enter_context(patch.object(C, "QUARANTINE", []))
        self.assertIs(C._append_output_bytes, T._WRITER)

    def expected(self):
        return ("python=" + self.model_sys.executable + "\ntool-path=" + os.environ["PATH"] + "\n").encode()

    def test_actual_small_file_append_fsync_readback_close_and_nonsecret_data_only(self):
        self.assertIsNone(T.observe())
        self.assertEqual(self.output.read_bytes(), self.expected())
        self.assertEqual(self.model_sys.stderr.getvalue(), "")
        self.assertEqual(C.QUARANTINE, [])
        with self.assertRaises(C.ContinuityError):
            T.observe()  # Original target is no longer empty; no append replay.

    def test_legitimate_python_symlink_metadata_does_not_rewrite_emitted_path(self):
        target = self.bin / "actual-interpreter-model"
        self.executable.rename(target)
        self.executable.symlink_to(target)
        T.observe()
        self.assertEqual(self.output.read_bytes(), self.expected())
        self.assertNotIn(str(target).encode(), self.output.read_bytes())

    def test_missing_directory_or_nonexecutable_tool_fails_without_output(self):
        self.executable.unlink()
        with self.assertRaises(OSError):
            T.observe()
        self.executable.mkdir()
        with self.assertRaises(C.ContinuityError):
            T.observe()
        self.executable.rmdir()
        self.executable.write_bytes(b"NOT EXECUTABLE\n")
        self.executable.chmod(0o600)
        with self.assertRaises(C.ContinuityError):
            T.observe()
        self.assertEqual(self.output.read_bytes(), b"")

    def test_actual_caller_identity_flags_and_absolute_argv_are_required(self):
        for field, value in (("GITHUB_ACTIONS", "false"), ("RUNNER_ENVIRONMENT", "self-hosted"),
                ("GITHUB_REPOSITORY", "someone/else"), ("RUNNER_OS", "Windows")):
            with self.subTest(field=field), patch.dict(os.environ, {field: value}), self.assertRaises(C.ContinuityError):
                T.observe()
        for argv in (["scripts/initial-recipient-runner-tools.py"], [self.model_sys.argv[0], "extra"]):
            with patch.object(self.model_sys, "argv", argv), self.assertRaises(C.ContinuityError):
                T.observe()
        for flag in ("isolated", "no_site", "dont_write_bytecode"):
            with patch.object(self.model_sys.flags, flag, 0), self.assertRaises(C.ContinuityError):
                T.observe()
        self.assertEqual(self.output.read_bytes(), b"")

    def test_each_forbidden_credential_name_is_rejected_without_echo(self):
        for name in T._FORBIDDEN:
            with patch.dict(os.environ, {name: "EXPLICIT_NONSECRET_MODEL_NOT_A_TOKEN"}):
                self.assertEqual(T.main(), 125)
        self.assertEqual(self.model_sys.stderr.getvalue(),
            "INITIAL_RECIPIENT_RUNNER_TOOLS_NOT_ACCEPTED\n" * len(T._FORBIDDEN))
        self.assertEqual(self.output.read_bytes(), b"")

    def test_writer_replacement_cannot_become_an_original_supplier(self):
        with patch.object(C, "_append_output_bytes") as substitute, self.assertRaises(C.ContinuityError):
            T.observe()
        substitute.assert_not_called()
        self.assertEqual(self.output.read_bytes(), b"")

    def after_write(self, change):
        original = os.write
        def write(descriptor, raw):
            size = original(descriptor, raw)
            change()
            return size
        return patch.object(C.os, "write", write)

    def test_changed_path_after_write_is_detected_before_success(self):
        with self.after_write(lambda: os.environ.__setitem__("PATH", str(self.base))), self.assertRaises(C.ContinuityError):
            T.observe()
        self.assertNotEqual(self.output.read_bytes(), b"")  # Failed bytes never imply Step success.

    def test_changed_executable_metadata_after_write_is_detected(self):
        with self.after_write(lambda: self.executable.chmod(0o500)), self.assertRaises(C.ContinuityError):
            T.observe()

    def test_new_credential_after_write_is_rejected(self):
        with self.after_write(lambda: os.environ.__setitem__("GH_TOKEN", "EXPLICIT_NONSECRET_MODEL")), self.assertRaises(C.ContinuityError):
            T.observe()

    def test_missing_nonempty_relative_and_outside_runner_target_are_rejected(self):
        self.output.unlink()
        with self.assertRaises(OSError):
            T.observe()
        self.output.write_bytes(b"prior=bytes\n")
        with self.assertRaises(C.ContinuityError):
            T.observe()
        for value in (OUTPUT_NAME, str(self.base / OUTPUT_NAME), str(self.commands / "arbitrary")):
            with patch.dict(os.environ, {"GITHUB_OUTPUT": value}), self.assertRaises(C.ContinuityError):
                T.observe()
        self.assertEqual(self.output.read_bytes(), b"prior=bytes\n")

    def test_symlink_and_multilink_output_are_not_owned_targets(self):
        target = self.base / "other-output-model"
        target.touch(mode=0o600)
        self.output.unlink()
        self.output.symlink_to(target)
        with self.assertRaises(C.ContinuityError):
            T.observe()
        self.output.unlink()
        os.link(target, self.output)
        with self.assertRaises(C.ContinuityError):
            T.observe()
        self.assertEqual(target.read_bytes(), b"")

    def test_symlinked_runner_parent_is_refused(self):
        actual = self.base / "original-commands"
        self.commands.rename(actual)
        self.commands.symlink_to(actual, target_is_directory=True)
        with self.assertRaises(C.ContinuityError):
            T.observe()
        self.assertEqual((actual / OUTPUT_NAME).read_bytes(), b"")

    def test_unowned_and_reparse_file_metadata_models_are_refused(self):
        original = Path.lstat
        for changes in ({"st_uid": os.geteuid() + 1}, {"st_file_attributes": 0x400}):
            def metadata(path, *args, **kwargs):
                value = original(path, *args, **kwargs)
                if path != self.output:
                    return value
                fields = {name: getattr(value, name, 0 if name == "st_file_attributes" else None) for name in T._ATTRIBUTES}
                fields.update(changes)
                return SimpleNamespace(**fields)
            with patch.object(Path, "lstat", metadata), self.assertRaises(C.ContinuityError):
                T.observe()
        self.assertEqual(self.output.read_bytes(), b"")

    def test_replaced_output_inode_after_write_is_refused(self):
        replacement = self.base / "replacement-output-model"
        replacement.touch(mode=0o600)
        with self.after_write(lambda: os.replace(replacement, self.output)), self.assertRaises(C.ContinuityError):
            T.observe()
        self.assertEqual(self.output.read_bytes(), b"")

    def test_short_write_is_failure_not_a_complete_output(self):
        original = os.write
        with patch.object(C.os, "write", lambda descriptor, raw: original(descriptor, raw[:-1])), self.assertRaisesRegex(
                C.ContinuityError, "STEP_OUTPUT_SHORT_WRITE"):
            T.observe()
        self.assertEqual(self.output.read_bytes(), self.expected()[:-1])

    def test_fsync_failure_does_not_escape_as_success(self):
        with patch.object(C.os, "fsync", side_effect=OSError("MODEL_FSYNC")), self.assertRaisesRegex(OSError, "MODEL_FSYNC"):
            T.observe()
        self.assertEqual(C.QUARANTINE, [])

    def test_readback_failure_does_not_escape_as_success(self):
        with patch.object(C.os, "read", return_value=b"MODEL_WRONG_READBACK"), self.assertRaisesRegex(
                C.ContinuityError, "STEP_OUTPUT_READBACK"):
            T.observe()

    def test_unknown_close_is_quarantined_without_retry_or_later_success(self):
        original, closed = os.close, []
        def close(descriptor):
            original(descriptor)  # The tiny TEST descriptor actually closes before UNKNOWN is injected.
            closed.append(descriptor)
            raise OSError("MODEL_CLOSE_RETURN_UNKNOWN")
        with patch.object(C.os, "close", close), self.assertRaisesRegex(C.ContinuityError, "STEP_OUTPUT_CLOSE_UNKNOWN"):
            T.observe()
        self.assertEqual(len(closed), 1)
        self.assertEqual(C.QUARANTINE, closed)
        with self.assertRaises(C.ContinuityError):
            T.observe()


if __name__ == "__main__":
    unittest.main(failfast=True)
