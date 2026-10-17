#!/usr/bin/env python3
"""Closed receipt/one-shot handshake controls; no compiler, Windows calls or fixture creation."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

spec = importlib.util.spec_from_file_location("protected_fixture", Path(__file__).with_name("protected-dll-fixture.py"))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


def compiler():
    return {"source": "a" * 40, "tree": "b" * 40,
            "dll": {"path": r"C:\test\p2pkit-windows-profile.dll", "bytes": 512, "sha256": "c" * 64}}


def ready():
    value = compiler()
    nonce = "01234567-89ab-cdef-0123-456789abcdef"
    return {"schema": 1, "scope": fixture.SCOPE, "phase": "READY", "stage": "READY", "error": 0,
            "nonce": nonce, "path": "C:\\Program Files\\P2pKit-Rpc-ReadFixture-" + nonce + "\\" + fixture.DLL,
            "source": value["source"], "tree": value["tree"], "sha256": value["dll"]["sha256"],
            "bytes": 512, "created": True, "owner": "BUILTIN_ADMINISTRATORS", "volume": "1" * 16,
            "directoryId": "2" * 32, "fileId": "3" * 32}


def cleaned(original):
    return {**original, "phase": "CLEANED", "stage": "CLEANED"}


class Pipe:
    def __init__(self):
        self.closed = False
        self.data = b""
        self.short = False

    def write(self, data):
        if self.closed:
            raise ValueError("Closed inert pipe")
        self.data += data
        return len(data) - int(self.short)

    def flush(self):
        pass

    def close(self):
        self.closed = True


class Process:
    def __init__(self):
        self.stdin = Pipe()
        self.code = None
        self.wait_code = 0
        self.timeout = False

    def poll(self):
        return self.code

    def wait(self, timeout):
        if self.timeout:
            raise subprocess.TimeoutExpired("inert", timeout)
        self.code = self.wait_code
        return self.code


def owner():
    value = fixture.ProtectedDllFixture(Path("inert-only"), compiler())
    value._ready = ready()
    value._state = "READY"
    value._process = Process()
    value._out = Pipe()
    value._err = Pipe()
    value._lines = lambda: [(json.dumps(row) + "\n").encode("ascii")
                            for row in (value._ready, cleaned(value._ready))]
    return value


class Controls(unittest.TestCase):
    def refusal(self, row):
        with self.assertRaises(ValueError):
            fixture.validate_ready(row, compiler())

    def test_ready_copy(self):
        original = ready()
        observed = fixture.validate_ready(original, compiler())
        observed["bytes"] = 1024
        self.assertEqual(original["bytes"], 512)
        observed_owner = owner()
        observed_owner.receipt["path"] = "not-original"
        self.assertEqual(observed_owner.path, ready()["path"])

    def test_dynamic_fields(self):
        self.refusal({**ready(), "authority": True})

    def test_duplicate_json(self):
        with self.assertRaises(ValueError):
            fixture.parse(b'{"scope":"first","scope":"second"}', 1024)

    def test_oversize(self):
        with self.assertRaises(ValueError):
            fixture.parse(b" " * 16385, 16384)

    def test_closed_labels(self):
        for key in ("scope", "phase", "stage", "owner"):
            for change in (lambda value: "prefix" + value, lambda value: value + "suffix"):
                with self.subTest(key=key):
                    self.refusal({**ready(), key: change(ready()[key])})

    def test_numeric_types(self):
        for key in ("schema", "error", "bytes"):
            for value in (True, False, 1.0, "512"):
                with self.subTest(key=key, value=value):
                    self.refusal({**ready(), key: value})
        self.refusal({**ready(), "created": 1})

    def test_nonce(self):
        for value in ("", ready()["nonce"].upper(), ready()["nonce"] + "\n", "0" * 36):
            self.refusal({**ready(), "nonce": value})

    def test_path_nonce_substitution(self):
        self.refusal({**ready(), "nonce": "11234567-89ab-cdef-0123-456789abcdef"})
        self.refusal({**ready(), "path": ready()["path"].replace("ReadFixture", "OtherFixture")})
        self.refusal({**ready(), "path": ready()["path"].replace(fixture.DLL, "other.dll")})

    def test_path_boundaries(self):
        for component in ("..", "COM1", "LPT9.ext", "nul .txt", "_start", "end.", "end ", "x" * 260):
            self.refusal({**ready(), "path": ready()["path"].replace("Program Files", component)})
        for path in (r"\\server\share\file.dll", "C:/Program Files/file.dll", "C:\\" + "x" * 300):
            self.assertFalse(fixture.path_valid(path))

    def test_identity(self):
        for key in ("volume", "fileId", "directoryId"):
            for value in ("0" * len(ready()[key]), "x" * len(ready()[key]), ready()[key] + "0", 123):
                self.refusal({**ready(), key: value})
        self.refusal({**ready(), "fileId": ready()["directoryId"]})

    def test_sha_binding(self):
        self.refusal({**ready(), "sha256": "d" * 64})

    def test_source_binding(self):
        for key in ("source", "tree"):
            self.refusal({**ready(), key: "d" * 40})

    def test_length_binding(self):
        for value in (0, 511, 513, fixture.MAXIMUM_DLL + 1):
            self.refusal({**ready(), "bytes": value})

    def test_cleaned_copy(self):
        original = ready()
        observed = fixture.validate_cleaned(cleaned(original), original)
        observed["fileId"] = "4" * 32
        self.assertEqual(original["fileId"], "3" * 32)

    def test_cleanup_substitution(self):
        original = ready()
        for key in fixture.FIELDS - {"phase", "stage", "error"}:
            with self.subTest(key=key), self.assertRaises(ValueError):
                fixture.validate_cleaned({**cleaned(original), key: "changed"}, original)
        with self.assertRaises(ValueError):
            fixture.validate_cleaned({**cleaned(original), "error": False}, original)

    def test_cleanup_closed_labels(self):
        for key in ("phase", "stage"):
            with self.assertRaises(ValueError):
                fixture.validate_cleaned({**cleaned(ready()), key: "CLEANED-extra"}, ready())
        with self.assertRaises(ValueError):
            fixture.validate_cleaned({**cleaned(ready()), "dynamic": True}, ready())

    def test_one_shot(self):
        value = owner()
        self.assertEqual(value.finish_after_reader_run(), cleaned(ready()))
        command = ("CLEANUP " + ready()["nonce"] + "\n").encode("ascii")
        self.assertEqual(value._process.stdin.data, command)
        self.assertTrue(value._out.closed and value._err.closed)
        with self.assertRaises(ValueError):
            value.finish_after_reader_run()
        value.abandon()
        self.assertEqual(value._process.stdin.data, command)

    def test_abandon_never_cleans(self):
        value = owner()
        value.abandon()
        self.assertEqual(value._process.stdin.data, b"")
        self.assertFalse(value._out.closed or value._err.closed)
        with self.assertRaises(ValueError):
            value.finish_after_reader_run()
        with self.assertRaises(ValueError):
            _ = value.path
        self.assertIn(value, fixture._OWNERS)

    def test_exited_helper_never_cleans(self):
        value = owner()
        value._process.code = 3
        with self.assertRaises(ValueError):
            value.finish_after_reader_run()
        self.assertEqual(value._process.stdin.data, b"")

    def test_unknown_return_retains(self):
        value = owner()
        value._process.timeout = True
        with self.assertRaises(subprocess.TimeoutExpired):
            value.finish_after_reader_run()
        before = value._process.stdin.data
        with self.assertRaises(ValueError):
            value.finish_after_reader_run()
        value.abandon()
        self.assertEqual(value._process.stdin.data, before)
        self.assertFalse(value._out.closed or value._err.closed)
        self.assertIn(value, fixture._OWNERS)

    def test_wrong_thread_before_effects(self):
        value = owner()
        value._thread = -1
        with self.assertRaises(ValueError):
            value.finish_after_reader_run()
        self.assertEqual(value._process.stdin.data, b"")
        self.assertEqual(value._state, "READY")

    def test_short_write_is_terminal(self):
        value = owner()
        value._process.stdin.short = True
        with self.assertRaises(ValueError):
            value.finish_after_reader_run()
        before = value._process.stdin.data
        with self.assertRaises(ValueError):
            value.finish_after_reader_run()
        value.abandon()
        self.assertEqual(value._process.stdin.data, before)
        self.assertFalse(value._out.closed or value._err.closed)

    def test_failed_projection_closed_stages(self):
        original = ready()
        for stage, error, code in (("READY", 0, 1), ("DELETE_FILE", 32, 1),
                                   ("DELETE_DIRECTORY", 65535, 1), ("PRESERVED", 0, 3)):
            lines = [(json.dumps(row) + "\n").encode("ascii") for row in
                     (original, {**original, "phase": "LEFT", "stage": stage, "error": error})]
            self.assertEqual(fixture.failed_cleanup_projection(lines, original, compiler(), code), (stage, error))

    def test_directory_substage_projection_requires_original_bindings(self):
        for stage in ("QUERY_DIRECTORY_ID", "OPEN_DIRECTORY_ID", "DISPOSE_DIRECTORY"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                value = owner()
                value._output = Path(directory)
                value._process.wait_code = 1
                terminal = {**ready(), "phase": "LEFT", "stage": stage, "error": 87}
                value._lines = lambda: [(json.dumps(row) + "\n").encode("ascii") for row in (ready(), terminal)]
                with self.assertRaisesRegex(ValueError, "Original cleanup failed") as failed:
                    value.finish_after_reader_run()
                self.assertIs(value._failure, failed.exception)
                diagnostic = value._output / ("protected-fixture-failure-" + stage + "-87.json")
                self.assertEqual(json.loads(diagnostic.read_text()),
                                 {"schema": 1, "scope": fixture.FAILURE_SCOPE, "stage": stage, "error": 87})
                for field, changed in (("stage", stage + "/private"), ("stage", "prefix" + stage),
                                       ("fileId", "4" * 32), ("path", ready()["path"] + "private")):
                    lines = [(json.dumps(row) + "\n").encode("ascii") for row in
                             (ready(), {**terminal, field: changed})]
                    with self.assertRaises(ValueError):
                        fixture.failed_cleanup_projection(lines, ready(), compiler(), 1)
                with self.assertRaises(ValueError):
                    fixture.failed_cleanup_projection(value._lines(), ready(), compiler(), 3)

    def test_directory_path_stages_retain_closed_original_failure(self):
        for stage in ("QUERY_DIRECTORY_PATH", "OPEN_DIRECTORY_PATH", "VERIFY_DIRECTORY_PATH"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                value = owner()
                value._output = Path(directory)
                value._process.wait_code = 1
                terminal = {**ready(), "phase": "LEFT", "stage": stage, "error": 0}
                value._lines = lambda: [(json.dumps(row) + "\n").encode("ascii") for row in (ready(), terminal)]
                with self.assertRaisesRegex(ValueError, "Original cleanup failed") as failed:
                    value.finish_after_reader_run()
                self.assertIs(value._failure, failed.exception)
                diagnostic = value._output / ("protected-fixture-failure-" + stage + "-0.json")
                self.assertEqual(json.loads(diagnostic.read_text()),
                                 {"schema": 1, "scope": fixture.FAILURE_SCOPE, "stage": stage, "error": 0})
                for field, changed in (("stage", stage + "-private"), ("stage", "../" + stage),
                                       ("directoryId", "4" * 32), ("path", ready()["path"] + "private")):
                    lines = [(json.dumps(row) + "\n").encode("ascii") for row in
                             (ready(), {**terminal, field: changed})]
                    with self.assertRaises(ValueError):
                        fixture.failed_cleanup_projection(lines, ready(), compiler(), 1)
                with self.assertRaises(ValueError):
                    fixture.failed_cleanup_projection(value._lines(), ready(), compiler(), 3)

    def test_failed_projection_rejects_private_substitution(self):
        original = ready()
        left = {**original, "phase": "LEFT", "stage": "DELETE_DIRECTORY", "error": 5}
        changed = [{**left, key: "private-path-or-identity"} for key in fixture.FIELDS - {"phase", "stage", "error"}]
        changed += [{**left, "stage": value} for value in (original["path"], "../escape", "DELETE_FILE-extra", 3, None)]
        changed += [{**left, "error": value} for value in (-1, 65536, True, 1.0, original["fileId"])]
        changed += [{**left, "phase": "CLEANED"}, {**left, "extra": original["nonce"]}]
        for row in changed:
            lines = [(json.dumps(value) + "\n").encode("ascii") for value in (original, row)]
            with self.assertRaises(ValueError):
                fixture.failed_cleanup_projection(lines, original, compiler(), 1)

    def test_failed_projection_requires_original_ready_and_terminal(self):
        original = ready()
        left = {**original, "phase": "LEFT", "stage": "DELETE_DIRECTORY", "error": 5}
        lines = [(json.dumps(row) + "\n").encode("ascii") for row in (original, left)]
        for code in (None, 0, 3, 4, True):
            with self.assertRaises(ValueError):
                fixture.failed_cleanup_projection(lines, original, compiler(), code)
        altered = {**original, "fileId": "4" * 32}
        with self.assertRaises(ValueError):
            fixture.failed_cleanup_projection([(json.dumps(altered) + "\n").encode(), lines[1]], original, compiler(), 1)
        for invalid in (lines[:1], lines + lines[:1], [lines[0], lines[1].rstrip(b"\n")]):
            with self.assertRaises(ValueError):
                fixture.failed_cleanup_projection(invalid, original, compiler(), 1)

    def test_failed_cleanup_emits_only_closed_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            value = owner()
            value._output = Path(directory)
            value._process.wait_code = 1
            value._lines = lambda: [(json.dumps(row) + "\n").encode("ascii") for row in
                                   (ready(), {**ready(), "phase": "LEFT", "stage": "DELETE_DIRECTORY", "error": 5})]
            with self.assertRaisesRegex(ValueError, "Original cleanup failed") as failed:
                value.finish_after_reader_run()
            self.assertIs(value._failure, failed.exception)
            self.assertIsNone(value._diagnostic_failure)
            diagnostic = value._output / "protected-fixture-failure-DELETE_DIRECTORY-5.json"
            self.assertEqual(json.loads(diagnostic.read_text()),
                             {"schema": 1, "scope": fixture.FAILURE_SCOPE, "stage": "DELETE_DIRECTORY", "error": 5})
            data = diagnostic.read_text()
            for field in ("path", "nonce", "volume", "fileId", "directoryId", "sha256", "source", "tree"):
                self.assertNotIn(field, data)
                self.assertNotIn(ready()[field], data)
            command = value._process.stdin.data
            with self.assertRaises(ValueError):
                value.finish_after_reader_run()
            self.assertEqual(list(value._output.iterdir()), [diagnostic])
            self.assertEqual(value._process.stdin.data, command)

    def test_unknown_wait_never_reads_unfinished_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            value = owner()
            value._output = Path(directory)
            original = subprocess.TimeoutExpired("private-ignored-command", 10)
            def waiting(timeout):
                raise original
            value._process.wait = waiting
            value._lines = lambda: self.fail("Unfinished capture must never be read")
            with self.assertRaises(subprocess.TimeoutExpired) as failed:
                value.finish_after_reader_run()
            self.assertIs(failed.exception, original)
            self.assertIs(value._failure, original)
            self.assertFalse(value._out.closed or value._err.closed)
            diagnostic = value._output / "protected-fixture-failure-UNKNOWN-0.json"
            self.assertEqual(json.loads(diagnostic.read_text())["stage"], "UNKNOWN")
            self.assertIsNone(value._diagnostic_failure)

    def test_invalid_protocol_exports_unknown_only(self):
        with tempfile.TemporaryDirectory() as directory:
            value = owner()
            value._output = Path(directory)
            value._process.wait_code = 1
            value._lines = lambda: [(json.dumps(row) + "\n").encode("ascii") for row in
                                   (ready(), {**ready(), "phase": "LEFT", "stage": "../private-path", "error": 5})]
            with self.assertRaises(ValueError):
                value.finish_after_reader_run()
            files = list(value._output.iterdir())
            self.assertEqual([path.name for path in files], ["protected-fixture-failure-UNKNOWN-0.json"])
            self.assertNotIn("private", files[0].read_text())

    def test_diagnostic_write_failure_preserves_original(self):
        with tempfile.TemporaryDirectory() as directory:
            value = owner()
            value._output = Path(directory)
            target = value._output / "protected-fixture-failure-UNKNOWN-0.json"
            target.write_text("original-create-only-evidence")
            value._process.stdin.short = True
            with self.assertRaisesRegex(ValueError, "Incomplete cleanup handshake") as failed:
                value.finish_after_reader_run()
            self.assertIs(value._failure, failed.exception)
            self.assertIsInstance(value._diagnostic_failure, FileExistsError)
            self.assertEqual(target.read_text(), "original-create-only-evidence")

    def test_exited_unretired_helper_does_not_read_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            value = owner()
            value._output = Path(directory)
            value._process.code = 1
            value._lines = lambda: self.fail("Unretired capture must never be read")
            with self.assertRaisesRegex(ValueError, "Original helper exited"):
                value.finish_after_reader_run()
            self.assertEqual(value._process.stdin.data, b"")
            self.assertFalse(value._out.closed or value._err.closed)
            self.assertTrue((value._output / "protected-fixture-failure-UNKNOWN-0.json").is_file())


    def test_selected_sdk_header_roots(self):
        roots = [Path("ucrt"), Path("shared"), Path("um")]
        expected = [roots[2] / "aclapi.h", roots[1] / "bcrypt.h", roots[2] / "shlobj.h"]
        calls = []
        class Tools:
            @staticmethod
            def regular(path):
                calls.append(path)
                if path not in expected:
                    raise FileNotFoundError()
        self.assertEqual(fixture.selected_headers(roots, Tools), expected)
        self.assertEqual(len(calls), 9)
        self.assertEqual({path.parent for path in calls}, set(roots))

    def test_missing_sdk_header(self):
        class Tools:
            @staticmethod
            def regular(path):
                raise FileNotFoundError()
        with self.assertRaises(ValueError):
            fixture.selected_headers([Path("ucrt"), Path("shared"), Path("um")], Tools)

    def test_ambiguous_sdk_header(self):
        class Tools:
            @staticmethod
            def regular(path):
                return None
        with self.assertRaises(ValueError):
            fixture.selected_headers([Path("ucrt"), Path("shared"), Path("um")], Tools)

    def test_invalid_present_header_not_skipped(self):
        calls = []
        class Tools:
            @staticmethod
            def regular(path):
                calls.append(path)
                raise ValueError("Inert reparse refusal")
        with self.assertRaises(ValueError):
            fixture.selected_headers([Path("ucrt"), Path("shared"), Path("um")], Tools)
        self.assertEqual(calls, [Path("ucrt/aclapi.h")])



if __name__ == "__main__":
    captured = io.StringIO()
    result = unittest.TextTestRunner(stream=captured).run(unittest.defaultTestLoader.loadTestsFromTestCase(Controls))
    if not result.wasSuccessful() or result.testsRun != 36:
        sys.stderr.write(captured.getvalue())
        sys.exit(1)
    print("WINDOWS_PROTECTED_DLL_FIXTURE_CONTROLS_PASS tests=36 scope=INERT_RECEIPT_AND_HANDSHAKE_NOT_NATIVE_CUSTODY_OR_AUTHORITY")
