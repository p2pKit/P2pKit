#!/usr/bin/python3
"""Real-file limits and bounded-read contracts for all metadata entry points."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "scripts/validate-gradle-plugin-metadata.py"
SPEC = importlib.util.spec_from_file_location("plugin_metadata", SOURCE)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)


class ObservedReader:
    """Observe real file IO without permitting a whole-file allocation."""

    def __init__(self, stream, maximum, before_read=None):
        self.stream = stream
        self.maximum = maximum
        self.before_read = before_read
        self.requests = []

    def __enter__(self):
        return self

    def __exit__(self, *exception):
        self.stream.close()

    def read(self, size=-1):
        self.requests.append(size)
        if not 0 < size <= self.maximum + 1:
            raise AssertionError(f"metadata read request must be bounded, got {size}")
        if self.before_read:
            self.before_read()
        return self.stream.read(size)


class ValidatorInputTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="p2pkit-plugin-input.")
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "candidate"

    def cases(self):
        return (
            ("marker", 64 * 1024, "plugin marker POM", VALIDATOR.validate_marker,
             [str(self.path), "example.plugin", "example.plugin.gradle.plugin", "1.0", "entries", "lock"]),
            ("module", 1024 * 1024, "Gradle module metadata", VALIDATOR.validate_module,
             [str(self.path), "example.plugin", "plugin", "1.0", "a" * 64, "entries", "lock"]),
            ("attestation", 8 * 1024 * 1024, "attestation result", VALIDATOR.validate_attestation,
             [str(self.path), "a" * 64, "example/upstream", "example/upstream/.github/workflows/release.yml",
              "refs/tags/v1.0", "b" * 40]),
        )

    def write_size(self, size):
        # Sparse fixtures keep disk use small; no large buffer is needed to
        # exercise the real filesystem/reader behavior.
        with self.path.open("wb") as stream:
            if size:
                stream.write(b"x")
            stream.truncate(size)

    def test_nonempty_and_exact_size_boundaries(self):
        for _, maximum, label, _, _ in self.cases():
            for size in (0, 1, maximum - 1, maximum, maximum + 1):
                with self.subTest(label=label, size=size):
                    self.write_size(size)
                    if size == 0 or size > maximum:
                        with self.assertRaisesRegex(ValueError, re.escape(
                            f"{label} must contain between 1 and {maximum} bytes"
                        )):
                            VALIDATOR.read_bounded(str(self.path), maximum, label)
                    else:
                        data = VALIDATOR.read_bounded(str(self.path), maximum, label)
                        self.assertEqual(data, b"x" + b"\0" * (size - 1))

    def test_each_validator_bounds_read_and_rejects_before_parsing(self):
        self.write_size(16 * 1024 * 1024)
        for _, maximum, label, validate, arguments in self.cases():
            with self.subTest(label=label):
                reader = ObservedReader(self.path.open("rb"), maximum)
                self.addCleanup(reader.stream.close)
                with mock.patch.object(Path, "open", return_value=reader), \
                        mock.patch.object(VALIDATOR.ET, "fromstring") as xml, \
                        mock.patch.object(json, "loads") as json_parser:
                    with self.assertRaisesRegex(ValueError, re.escape(
                        f"{label} must contain between 1 and {maximum} bytes"
                    )):
                        validate(arguments)
                self.assertEqual(reader.requests, [maximum + 1])
                self.assertTrue(reader.stream.closed)
                xml.assert_not_called()
                json_parser.assert_not_called()

    def test_bounded_success_closes_stream(self):
        self.path.write_bytes(b"owned bytes")
        reader = ObservedReader(self.path.open("rb"), 11)
        self.addCleanup(reader.stream.close)
        with mock.patch.object(Path, "open", return_value=reader):
            self.assertEqual(VALIDATOR.read_bounded(str(self.path), 11, "fixture"), b"owned bytes")
        self.assertEqual(reader.requests, [12])
        self.assertTrue(reader.stream.closed)

    def test_growth_after_open_cannot_escape_read_bound(self):
        self.path.write_bytes(b"x")

        def grow():
            with open(self.path, "ab") as output:
                output.write(b"x" * 64)

        reader = ObservedReader(self.path.open("rb"), 16, grow)
        self.addCleanup(reader.stream.close)
        with mock.patch.object(Path, "open", return_value=reader):
            with self.assertRaisesRegex(ValueError, "between 1 and 16 bytes"):
                VALIDATOR.read_bounded(str(self.path), 16, "growing fixture")
        self.assertEqual(reader.requests, [17])
        self.assertTrue(reader.stream.closed)

    def test_read_failure_closes_stream_and_preserves_error(self):
        self.path.write_bytes(b"x")
        error = OSError("synthetic read failure")

        def fail_read():
            raise error

        reader = ObservedReader(self.path.open("rb"), 16, fail_read)
        self.addCleanup(reader.stream.close)
        with mock.patch.object(Path, "open", return_value=reader):
            with self.assertRaises(OSError) as caught:
                VALIDATOR.read_bounded(str(self.path), 16, "fixture")
        self.assertIs(caught.exception, error)
        self.assertTrue(reader.stream.closed)

    def test_missing_file_remains_an_oserror(self):
        with self.assertRaises(FileNotFoundError):
            VALIDATOR.read_bounded(str(self.path), 16, "missing fixture")

    def test_cli_rejects_empty_and_oversized_inputs_with_size_diagnostic(self):
        for mode, maximum, label, _, arguments in self.cases():
            for size in (0, maximum + 1):
                with self.subTest(mode=mode, size=size):
                    self.write_size(size)
                    result = subprocess.run(
                        [sys.executable, "-B", str(SOURCE), mode, *arguments],
                        capture_output=True, text=True, timeout=10,
                    )
                    self.assertEqual(result.returncode, 1)
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, f"FATAL: {label} must contain between 1 and {maximum} bytes\n")


if __name__ == "__main__":
    unittest.main(verbosity=2)
