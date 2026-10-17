#!/usr/bin/env python3
"""Closed receipt/one-shot handshake controls; no compiler, Windows calls or fixture creation."""
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
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
        self.timeout = False

    def poll(self):
        return self.code

    def wait(self, timeout):
        if self.timeout:
            raise subprocess.TimeoutExpired("inert", timeout)
        self.code = 0
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
    if not result.wasSuccessful() or result.testsRun != 26:
        sys.stderr.write(captured.getvalue())
        sys.exit(1)
    print("WINDOWS_PROTECTED_DLL_FIXTURE_CONTROLS_PASS tests=26 scope=INERT_RECEIPT_AND_HANDSHAKE_NOT_NATIVE_CUSTODY_OR_AUTHORITY")
