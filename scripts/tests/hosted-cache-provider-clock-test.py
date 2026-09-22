#!/usr/bin/env python3
"""Offline post-provider-close clock controls; no child/native clock/key access.

Run-path cases use the maintained clock validator with supplied Reading objects.
Loader cases compile only tiny synthetic modules; file cases use owned scratch.
These controls cannot observe an actual provider close or qualify a runner.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import importlib.util
import io
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


SCRIPTS = Path(__file__).resolve().parents[1]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


processes = module("audit_processes", SCRIPTS / "audit_processes.py")
clock = module("provider_clock_control_supplier", SCRIPTS / "hosted_job_clock.py")
C = module("provider_clock_control_subject", SCRIPTS / "hosted_cache_provider_clock.py")


def request(role="linux-x64", frequency=1_000_000_000):
    return {"schema": "P2PKIT_PROVIDER_POST_CLOSE_CLOCK_REQUEST_V1", "invocationSha256": "a" * 64,
            "role": role, "frequency": str(frequency), "minimumNs": "210000000000", "hardEndNs": "280000000000"}


class Sink(io.BytesIO):
    def __init__(self):
        super().__init__()
        self.flushes = 0

    def flush(self):
        self.flushes += 1
        super().flush()


class ClockControls(unittest.TestCase):
    def setUp(self):
        self.request = request()
        self.sink = Sink()
        self.stream = SimpleNamespace(buffer=self.sink)
        self.readings = [220_000_000_000, 221_000_000_000]
        self.observations = []
        self.loads = Mock(return_value=clock)
        self.addCleanup(self.sink.close)

    def reading(self):
        value = self.readings.pop(0)
        if isinstance(value, BaseException):
            raise value
        if type(value) is clock.Reading:
            return value
        role = self.request["role"]
        return clock.Reading(clock.ClockIdentity(role, clock.DOMAINS[role], int(self.request["frequency"])), value)

    def run_clock(self, *, through_main=False, raw=None):
        checked = clock.checked_now
        def observe(expected, *, minimum_ns):
            self.observations.append((expected, minimum_ns))
            return checked(expected, minimum_ns=minimum_ns)
        with patch.object(C, "load_clock", self.loads), patch.object(clock, "observe", self.reading), \
                patch.object(clock, "checked_now", observe), patch.object(sys, "stdout", self.stream), \
                patch.object(sys, "argv", [str(SCRIPTS / "hosted_cache_provider_clock.py"), "{}",
                                          C.encoded(self.request) if raw is None else raw]):
            if through_main:
                return C.main()
            return C.run(sys.argv[1], sys.argv[2])

    def test_four_roles_use_maintained_identity_and_nonrenewed_fence(self):
        for role in C.ROLES:
            with self.subTest(role=role):
                self.request = request(role)
                self.readings[:] = [220_000_000_000, 221_000_000_000]
                self.observations.clear()
                self.sink.seek(0)
                self.sink.truncate()
                self.run_clock()
                expected = {**self.request, "schema": "P2PKIT_PROVIDER_POST_CLOSE_CLOCK_OBSERVATION_V1",
                            "domain": clock.DOMAINS[role], "observedNs": "220000000000"}
                self.assertEqual(self.sink.getvalue(), (C.encoded(expected) + "\n").encode("ascii"))
                self.assertEqual([value for _, value in self.observations], [210_000_000_000, 220_000_000_000])
                self.assertEqual(len(self.readings), 0)
        self.assertEqual(self.sink.flushes, 4)

    def test_full_int64_windows_frequency_is_exact_not_float(self):
        self.request = request("windows-x64", (1 << 63) - 1)
        self.assertEqual(self.run_clock(through_main=True), 0)
        value = C.record(self.sink.getvalue().decode("ascii").rstrip("\n"))
        self.assertEqual(value["frequency"], "9223372036854775807")
        self.assertEqual(self.observations[0][0].ticks_per_second, (1 << 63) - 1)

    def test_invalid_request_refuses_before_loader_or_output(self):
        changes = [("schema", "OTHER"), ("role", "linux-arm64"), ("frequency", "0"),
                   ("frequency", "1000000001"), ("frequency", "9223372036854775808"),
                   ("frequency", 1_000_000_000), ("minimumNs", True), ("minimumNs", "0210000000000"),
                   ("hardEndNs", "210000000000"), ("hardEndNs", "390000000001"),
                   ("hardEndNs", "18446744073709551616"), ("invocationSha256", "A" * 64), ("extra", "value")]
        for name, value in changes:
            with self.subTest(name=name, value=value):
                self.request = {**request(), name: value}
                with self.assertRaises(Exception):
                    self.run_clock()
        self.loads.assert_not_called()
        self.assertEqual(self.sink.getvalue(), b"")

    def test_noncanonical_duplicate_nonfinite_and_nonascii_frames_refuse(self):
        good = C.encoded(request())
        for raw in [" " + good, good + "\n", good[:-1] + ',"role":"linux-x64"}',
                    good.replace('"210000000000"', "NaN"), "[]", '{"x":"\u00e9"}']:
            with self.subTest(raw=raw):
                with self.assertRaises(Exception):
                    self.run_clock(raw=raw)
        self.loads.assert_not_called()
        self.assertEqual(self.sink.getvalue(), b"")

    def test_decimal_width_and_lexical_boundaries(self):
        self.assertEqual(C.decimal(str((1 << 64) - 1), (1 << 64) - 1), (1 << 64) - 1)
        for value in ["-1", "+1", "01", "1.0", "1e1", " 1", "1\n", "", "9" * 21, False, 1]:
            with self.subTest(value=value), self.assertRaises(Exception):
                C.decimal(value, (1 << 64) - 1)

    def test_first_backward_late_or_wrong_identity_never_writes(self):
        for first in [209_999_999_999, 280_000_000_000,
                      clock.Reading(clock.ClockIdentity("windows-x64", clock.WINDOWS_DOMAIN, 1_000_000_000),
                                    220_000_000_000), RuntimeError("MODEL_PRIVATE_CLOCK_ERROR")]:
            with self.subTest(first=first):
                self.readings[:] = [first]
                self.assertEqual(self.run_clock(through_main=True), 66)
                self.assertEqual(self.sink.getvalue(), b"")

    def test_provisional_output_cannot_override_bad_final_native_read(self):
        for final in [219_999_999_999, 280_000_000_000, RuntimeError("MODEL_PRIVATE_FINAL_ERROR")]:
            with self.subTest(final=final):
                self.readings[:] = [220_000_000_000, final]
                self.sink.seek(0)
                self.sink.truncate()
                self.assertEqual(self.run_clock(through_main=True), 66)
                self.assertIn(b'"observedNs":"220000000000"', self.sink.getvalue())
                self.assertNotIn(b"MODEL_PRIVATE", self.sink.getvalue())

    def test_short_boolean_and_failed_writes_cannot_pass(self):
        for value in [0, True, None, RuntimeError("MODEL_PRIVATE_WRITE_ERROR")]:
            with self.subTest(value=value), patch.object(self.sink, "write",
                    side_effect=value if isinstance(value, BaseException) else None,
                    return_value=value):
                self.readings[:] = [220_000_000_000, 221_000_000_000]
                self.assertEqual(self.run_clock(through_main=True), 66)
                self.assertEqual(len(self.readings), 1)
        self.assertEqual(self.sink.flushes, 0)

    def test_failed_flush_and_changed_stdout_cannot_pass(self):
        with patch.object(self.sink, "flush", side_effect=RuntimeError("MODEL_PRIVATE_FLUSH_ERROR")):
            self.assertEqual(self.run_clock(through_main=True), 66)
        self.readings[:] = [220_000_000_000, 221_000_000_000]
        def replace_stream():
            sys.stdout = SimpleNamespace(buffer=self.sink)
        with patch.object(self.sink, "flush", side_effect=replace_stream):
            self.assertEqual(self.run_clock(through_main=True), 66)

    def test_main_refuses_nonisolated_or_bad_argv_without_calling_run(self):
        with patch.object(C, "run") as run:
            with patch.object(sys, "flags", SimpleNamespace(isolated=0, no_site=1)):
                self.assertEqual(C.main(), 66)
            with patch.object(sys, "argv", ["clock"]):
                self.assertEqual(C.main(), 66)
            run.assert_not_called()


class LoaderControls(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="provider-clock-control-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.sources = {"audit_processes": b'MARKER = "MODEL_SOURCE_ONLY"\n',
                        "hosted_lock_resources": b'from audit_processes import MARKER\n',
                        "hosted_job_clock": b'from audit_processes import MARKER\n',
                        C.NAME: b'# MODEL_SELF_BINDING_ONLY\n'}
        for name, raw in self.sources.items():
            (self.root / (name + ".py")).write_bytes(raw)

    @contextmanager
    def isolated_loader(self, role="linux-x64"):
        names = C.roster(role)
        bindings = {name: hashlib.sha256(self.sources[name]).hexdigest() for name in names}
        with patch.dict(sys.modules), patch.object(C, "__file__", str(self.root / (C.NAME + ".py"))):
            for name in names[:-1]:
                sys.modules.pop(name, None)
            yield bindings

    def test_role_roster_excludes_unneeded_native_and_provider_graph(self):
        for role in C.ROLES:
            self.assertEqual(C.roster(role), ("audit_processes",
                *(("hosted_lock_resources",) if role.startswith("macos-") else ()), "hosted_job_clock", C.NAME))
        with self.assertRaises(Exception):
            C.roster("windows-arm64")

    def test_exact_frozen_synthetic_modules_load_without_path_widening(self):
        original, before = sys.path, tuple(sys.path)
        for role in C.ROLES:
            with self.subTest(role=role), self.isolated_loader(role) as bindings:
                result = C.load_clock(bindings, role)
                self.assertEqual(result.MARKER, "MODEL_SOURCE_ONLY")
                self.assertIs(result, sys.modules["hosted_job_clock"])
                self.assertIs(sys.path, original)
                self.assertEqual(tuple(sys.path), before)
                self.assertEqual("hosted_lock_resources" in sys.modules, role.startswith("macos-"))

    def test_missing_extra_wrong_self_and_dependency_hashes_refuse_before_exec(self):
        for change in ["missing", "extra", C.NAME, "audit_processes", "hosted_job_clock"]:
            with self.subTest(change=change), self.isolated_loader() as bindings:
                if change == "missing":
                    bindings.pop(C.NAME)
                elif change == "extra":
                    bindings["hosted_cache_provider_worker"] = "a" * 64
                else:
                    bindings[change] = "0" * 64
                with self.assertRaises(Exception):
                    C.load_clock(bindings, "linux-x64")
                self.assertNotIn("audit_processes", sys.modules)
                self.assertNotIn("hosted_job_clock", sys.modules)

    def test_preloaded_module_cannot_replace_selected_source(self):
        with self.isolated_loader() as bindings:
            sentinel = SimpleNamespace(MARKER="FOREIGN")
            sys.modules["hosted_job_clock"] = sentinel
            with self.assertRaises(Exception):
                C.load_clock(bindings, "linux-x64")
            self.assertIs(sys.modules["hosted_job_clock"], sentinel)
            self.assertNotIn("audit_processes", sys.modules)

    def test_selected_frozen_bytes_are_not_reopened_during_exec(self):
        calls = []
        original = C.read_source
        def read(directory, name):
            raw = original(directory, name)
            calls.append(name)
            if name == C.NAME:
                (self.root / "hosted_job_clock.py").write_bytes(b'MARKER = "LATE_REPLACEMENT"\n')
            return raw
        with self.isolated_loader() as bindings, patch.object(C, "read_source", read):
            self.assertEqual(C.load_clock(bindings, "linux-x64").MARKER, "MODEL_SOURCE_ONLY")
            self.assertEqual(calls, list(C.roster("linux-x64")))

    def test_source_name_size_symlink_and_hardlink_refuse(self):
        with self.assertRaises(Exception):
            C.read_source(self.root, "hosted_cache_provider_worker")
        path = self.root / "hosted_job_clock.py"
        for raw in [b"", b"#" * (C.LIMIT + 1)]:
            path.write_bytes(raw)
            with self.assertRaises(Exception):
                C.read_source(self.root, "hosted_job_clock")
        path.unlink()
        path.symlink_to(self.root / "audit_processes.py")
        with self.assertRaises(Exception):
            C.read_source(self.root, "hosted_job_clock")
        path.unlink()
        C.os.link(self.root / "audit_processes.py", path)
        with self.assertRaises(Exception):
            C.read_source(self.root, "hosted_job_clock")

    def test_failed_read_preserves_original_even_if_close_also_fails(self):
        first, later = OSError("MODEL_PRIVATE_READ_ERROR"), OSError("MODEL_PRIVATE_CLOSE_ERROR")
        closed, close = [], C.os.close
        def close_then_fail(fd):
            closed.append(fd)
            close(fd)
            raise later
        with patch.object(C.os, "read", side_effect=first), patch.object(C.os, "close", close_then_fail):
            with self.assertRaises(OSError) as caught:
                C.read_source(self.root, "hosted_job_clock")
        self.assertIs(caught.exception, first)
        self.assertEqual(len(closed), 1)

    def test_source_mutation_after_descriptor_close_is_rejected(self):
        close = C.os.close
        def replace(fd):
            close(fd)
            (self.root / "hosted_job_clock.py").write_bytes(b"# changed after read\n")
        with patch.object(C.os, "close", replace), self.assertRaises(Exception):
            C.read_source(self.root, "hosted_job_clock")


if __name__ == "__main__":
    unittest.main()
