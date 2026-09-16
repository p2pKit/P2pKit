#!/usr/bin/env python3
"""Synthetic offline resource controls; no live host admission/network/builds."""
from __future__ import annotations

import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("hosted_resources", ROOT / "scripts/hosted_lock_resources.py")
R = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(R)

VM = "Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free: 43.\nSwapouts: 2.\n"
NET = ("Name Mtu Network Address Ipkts Ierrs Ibytes Opkts Oerrs Obytes Coll\n"
       "lo0 16384 <Link#1> 12 0 999999 12 0 999999 0\n"
       "en0 1500 <Link#6> 00:11:22:33:44:55 42 0 4294967299 50 0 37 0\n"
       "en0 1500 192.0.2 192.0.2.1 42 - 4294967299 50 - 37 -\n"
       "utun0* 1280 <Link#7> 1 0 19 2 0 11 0\n")


def fast(**overrides):
    now = time.monotonic()
    return {"startedLocalMonotonic": now, "observedLocalMonotonic": now,
            "pressure": 1, "pageSize": 16384, "swapoutBytes": 32768,
            "availableBytes": R.START_FREE, **overrides}


def network(counters=None):
    now = time.monotonic()
    return {"startedLocalMonotonic": now, "observedLocalMonotonic": now,
            "counters": counters if counters is not None else {("en0", "<Link#6>"): 10}}


class ResourceControls(unittest.TestCase):
    def setUp(self):
        self.output, self.errors = io.StringIO(), io.StringIO()
        self.streams = R.Streams(self.output, self.errors)
        # These remain offline controls on Linux as well as macOS. Native clock
        # semantics are not inferred from their synthetic value.
        for item in (patch.object(R.sys, "platform", "darwin"),
                     patch.object(R.time, "CLOCK_MONOTONIC_RAW", 4, create=True),
                     patch.object(R.time, "clock_gettime_ns", return_value=30_000_000_000, create=True)):
            item.start()
            self.addCleanup(item.stop)

    def reject(self, code, function, *args, **kwargs):
        with self.assertRaises(R.ResourceError) as caught:
            function(*args, **kwargs)
        self.assertEqual(caught.exception.code, code)
        return caught.exception

    def test_pressure_and_swap_parse_original_field_units(self):
        self.assertEqual([R.parse_pressure(str(x) + "\n") for x in (1, 2, 4)], [1, 2, 4])
        self.assertEqual(R.parse_vm(VM), {"pageSize": 16384, "swapoutBytes": 32768})
        for value in ("", "0\n", "3\n", "1\n1\n", " 1\n"):
            self.reject("PRESSURE_FORMAT", R.parse_pressure, value)
        for raw in (VM + "Swapouts: 1.\n", VM.replace("Swapouts:", "Swapins:")):
            self.reject("VM_FIELDS", R.parse_vm, raw)
        self.reject("VM_PAGE", R.parse_vm, VM.replace("16384", "16385"))
        self.reject("VM_COUNTER", R.parse_vm, VM.replace("Swapouts: 2.", "Swapouts: 18446744073709551615."))

    def test_network_uses_link_rows_only_with_and_without_address(self):
        self.assertEqual(R.parse_netstat(NET), {("en0", "<Link#6>"): 4294967299, ("utun0", "<Link#7>"): 19})
        self.assertEqual(R.parse_netstat(NET.replace("4294967299", str(R.UINT64)))[("en0", "<Link#6>")], R.UINT64)

    def test_network_malformed_duplicate_missing_and_overflow_refused(self):
        self.reject("NETWORK_HEADER", R.parse_netstat, NET.replace("Ibytes", "Bytes"))
        self.reject("NETWORK_HEADER", R.parse_netstat, NET + NET)
        self.reject("NETWORK_DUPLICATE_LINK", R.parse_netstat, NET + NET.splitlines()[2] + "\n")
        self.reject("NETWORK_LINK_ROW", R.parse_netstat, NET.replace("<Link#6>", "<Link#0>"))
        self.reject("NETWORK_COUNTER", R.parse_netstat, NET.replace("4294967299", str(R.UINT64 + 1)))
        self.reject("NETWORK_COUNTER", R.parse_netstat, NET.replace("4294967299", "-"))
        self.reject("NETWORK_NO_NONLO_LINK", R.parse_netstat, "\n".join(NET.splitlines()[:2]))

    def test_fast_requires_normal_admission_then_warn_is_permitted(self):
        for level in (2, 4):
            self.reject("MEMORY_PRESSURE", R.FastPolicy().accept, fast(pressure=level))
        policy = R.FastPolicy()
        self.assertTrue(policy.accept(fast())["admitted"])
        self.assertFalse(policy.accept(fast(pressure=2, availableBytes=R.FREE_FLOOR))["admitted"])
        self.reject("MEMORY_PRESSURE", policy.accept, fast(pressure=4))

    def test_fast_floor_swap_limit_and_reset_never_erase_baseline(self):
        self.reject("DISK_FLOOR", R.FastPolicy().accept, fast(availableBytes=R.START_FREE - 1))
        policy = R.FastPolicy()
        policy.accept(fast())
        self.reject("DISK_FLOOR", policy.accept, fast(availableBytes=R.FREE_FLOOR - 1))
        self.reject("SWAP_COUNTER_RESET", policy.accept, fast(swapoutBytes=1))
        self.reject("SWAP_COUNTER_RESET", policy.accept, fast(pageSize=4096))
        self.assertEqual(policy.accept(fast(swapoutBytes=32768 + R.SWAP_LIMIT - 1))["swapoutIncreaseBytes"], R.SWAP_LIMIT - 1)
        error = self.reject("SWAP_LIMIT", policy.accept, fast(swapoutBytes=32768 + R.SWAP_LIMIT))
        self.assertEqual(error.sample["swapoutIncreaseBytes"], R.SWAP_LIMIT)

    def test_network_new_interface_counts_entire_first_counter(self):
        policy = R.NetworkPolicy()
        self.assertEqual(policy.accept(network())["inboundIncreaseBytes"], 0)
        row = policy.accept(network({("en0", "<Link#6>"): 14, ("bridge0", "<Link#8>"): 100}))
        self.assertEqual((row["inboundIncreaseBytes"], row["newInterfaceCount"]), (104, 1))
        self.assertEqual(policy.accept(network({("en0", "<Link#6>"): 16, ("bridge0", "<Link#8>"): 107}))[
            "inboundIncreaseBytes"], 113)
        self.assertNotIn("counters", row)

    def test_network_disappearance_replacement_reset_and_limit_fail(self):
        policy = R.NetworkPolicy()
        policy.accept(network())
        self.reject("NETWORK_INTERFACE_DISAPPEARED", policy.accept, network({}))
        self.reject("NETWORK_INTERFACE_DISAPPEARED", policy.accept, network({("en0", "<Link#9>"): 12}))
        self.reject("NETWORK_COUNTER_RESET", policy.accept, network({("en0", "<Link#6>"): 9}))
        self.assertEqual(policy.accept(network({("en0", "<Link#6>"): 10 + R.INBOUND_LIMIT - 1}))[
            "inboundIncreaseBytes"], R.INBOUND_LIMIT - 1)
        self.reject("NETWORK_LIMIT", policy.accept, network({("en0", "<Link#6>"): 10 + R.INBOUND_LIMIT}))

    def test_query_originals_precede_timeout_nonzero_decode_and_size_failures(self):
        cases = [
            ("QUERY_TIMEOUT", subprocess.TimeoutExpired(["synthetic"], 2, output=b"partial\x00", stderr=b"note\xff")),
            ("QUERY_EXIT", SimpleNamespace(returncode=7, stdout=b"before", stderr=b"failure")),
            ("QUERY_ENCODING", SimpleNamespace(returncode=0, stdout=b"\xff", stderr=b"")),
            ("QUERY_SIZE", SimpleNamespace(returncode=0, stdout=b"x" * (R.TOOL_BYTES + 1), stderr=b"")),
        ]
        for code, value in cases:
            with self.subTest(code=code):
                output, errors = io.StringIO(), io.StringIO()
                streams = R.Streams(output, errors)
                def call(argv, **kwargs):
                    self.assertNotIn("env", kwargs)  # Ownership markers inherited unchanged.
                    self.assertEqual(kwargs["timeout"], 2)
                    if isinstance(value, Exception):
                        raise value
                    return value
                self.reject(code, R.query, "synthetic", ["/not-executed"], 2, streams, call, lambda: 0)
                record = json.loads(errors.getvalue())["nativeQuery"]
                self.assertEqual(record["timedOut"], code == "QUERY_TIMEOUT")
                self.assertEqual(record["truncated"], code == "QUERY_SIZE")
                self.assertEqual(output.getvalue(), "")
                if code == "QUERY_TIMEOUT":
                    self.assertEqual(base64.b64decode(record["stdoutBase64"]), b"partial\x00")
                    self.assertIsNone(record["exitCode"])

    def test_fast_queries_share_one_two_second_deadline(self):
        now, calls = [0.0], []
        def call(argv, **kwargs):
            calls.append((argv, kwargs["timeout"]))
            now[0] += 0.75
            return SimpleNamespace(returncode=0, stdout=b"1\n" if len(calls) == 1 else VM.encode(), stderr=b"")
        path = Path("/synthetic-not-read")
        with patch.object(R, "physical_directory", return_value=(1, 2)):
            result = R.fast_frame({path: (1, 2)}, self.streams, call,
                                  lambda _: SimpleNamespace(f_frsize=4096, f_bavail=R.START_FREE // 4096), lambda: now[0])
        self.assertEqual([row[1] for row in calls], [2.0, 1.25])
        self.assertEqual(result["observedLocalMonotonic"], 1.5)
        self.assertEqual(result["availableBytes"], R.START_FREE)

    def test_successful_native_exit_after_deadline_is_not_a_valid_sample(self):
        now = [0.0]
        def late(argv, **kwargs):
            now[0] = 3
            return SimpleNamespace(returncode=0, stdout=b"1\n", stderr=b"")
        self.reject("QUERY_DEADLINE", R.query, "synthetic", ["/not-executed"], 2, self.streams, late, lambda: now[0])
        self.assertEqual(json.loads(self.errors.getvalue())["nativeQuery"]["exitCode"], 0)

    def test_each_lane_needs_its_own_completed_fresh_sample(self):
        R.check_stale({"fast": 5, "network": 2}, 0, 10)
        error = self.reject("LANE_STALE", R.check_stale, {"fast": 4.9, "network": 10}, 0, 10)
        self.assertEqual(error.sample["staleLane"], "fast")
        error = self.reject("LANE_STALE", R.check_stale, {"fast": 10, "network": 1.9}, 0, 10)
        self.assertEqual(error.sample["staleLane"], "network")
        self.reject("LANE_STALE", R.check_stale, {}, 0, 5.1)
        self.reject("LANE_STALE", R.check_stale, {"fast": 11, "network": 10}, 0, 10)

    def test_network_frame_uses_fixed_tool_and_no_other_child(self):
        commands = []
        def call(argv, **kwargs):
            commands.append((argv, kwargs))
            return SimpleNamespace(returncode=0, stdout=NET.encode(), stderr=b"")
        row = R.network_frame(self.streams, call, lambda: 100)
        self.assertEqual(commands[0][0], ["/usr/sbin/netstat", "-ibn"])
        self.assertEqual(len(commands), 1)
        self.assertNotIn("env", commands[0][1])
        self.assertEqual(row["counters"], R.parse_netstat(NET))


class ResourceRawClockControls(unittest.TestCase):
    """Call real frame producers with fake system tools and an explicit fake RAW clock."""
    def setUp(self):
        self.streams = R.Streams(io.StringIO(), io.StringIO())
        self.patches = [patch.object(R.sys, "platform", "darwin"),
                        patch.object(R.time, "CLOCK_MONOTONIC_RAW", 4, create=True),
                        patch.object(R.time, "clock_gettime_ns", return_value=30_000_000_000, create=True)]
        for item in self.patches:
            value = item.start()
            self.addCleanup(item.stop)
        self.raw = value

    def network_frame(self):
        def call(argv, **kwargs):
            return SimpleNamespace(returncode=0, stdout=NET.encode(), stderr=b"")
        return R.network_frame(self.streams, call, lambda: 1.0)

    def assert_stamp(self, row):
        self.assertEqual(row["clockDomain"], "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)")
        self.assertEqual(row["observedRawNs"], 30_000_000_000)
        self.assertEqual(row["observedLocalMonotonic"], 1.0)
        self.assertNotIn("observedMonotonic", row)
        self.raw.assert_called_once_with(4)

    def test_network_frame_stamps_completed_sample_with_explicit_raw_clock(self):
        self.assert_stamp(self.network_frame())

    def test_fast_frame_stamps_completed_sample_with_explicit_raw_clock(self):
        def call(argv, **kwargs):
            raw = b"1\n" if argv[0] == "/usr/sbin/sysctl" else VM.encode()
            return SimpleNamespace(returncode=0, stdout=raw, stderr=b"")
        path = Path("/synthetic-not-read")
        with patch.object(R, "physical_directory", return_value=(1, 2)):
            row = R.fast_frame({path: (1, 2)}, self.streams, call,
                               lambda _: SimpleNamespace(f_frsize=4096, f_bavail=R.START_FREE // 4096), lambda: 1.0)
        self.assert_stamp(row)

    def test_raw_clock_is_unavailable_off_darwin_without_fallback(self):
        with patch.object(R.sys, "platform", "linux"), self.assertRaises(ValueError):
            self.network_frame()
        self.raw.assert_not_called()

    def test_missing_raw_api_or_clock_id_fails_closed(self):
        for name in ("clock_gettime_ns", "CLOCK_MONOTONIC_RAW"):
            with self.subTest(name=name), patch.object(R.time, name, None), self.assertRaises(ValueError):
                self.network_frame()

    def test_raw_clock_values_must_be_uint64_nanoseconds_not_coerced(self):
        for value in (True, -1, 0.5, "30000000000", 1 << 64):
            with self.subTest(value=value):
                self.raw.return_value = value
                with self.assertRaises(ValueError):
                    self.network_frame()

    def test_raw_clock_read_failure_never_uses_local_time(self):
        self.raw.side_effect = OSError("synthetic clock read failure")
        with self.assertRaises(OSError):
            self.network_frame()

    def test_new_records_use_new_schema_not_relabelled_old_timestamps(self):
        # The real observer serializes accepted policy rows, not the raw frame's
        # tuple-keyed interface counters.
        row = R.NetworkPolicy().accept(self.network_frame())
        self.streams.sample({"kind": "resource-sample", "lane": "network", **row})
        row = json.loads(self.streams.output.getvalue())
        self.assertEqual(row["schema"], 2)
        self.assert_stamp(row)


class OwnedSyntheticPaths(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="p2pkit-resource-synthetic-")
        self.base = Path(self.temporary.name).resolve()
        self.root, self.state = self.base / "source", self.base / "state"
        self.root.mkdir(mode=0o700)
        self.state.mkdir(mode=0o700)
        (self.state / "gradle-home").mkdir(mode=0o700)
        self.stop = self.state / "resource-stop"
        self.env = R.audit_processes.ownership_environment({}, "1" * 32, "2" * 32,
                                                           str(self.state), str(self.state / "gradle-home"))

    def tearDown(self):
        self.temporary.cleanup()  # Only this test's wholly synthetic files.

    def test_state_binding_missing_domain_existing_stop_and_link_rejected(self):
        self.assertEqual(set(R.validate_paths(self.root, self.state, self.stop, self.env)), {self.root, self.state})
        with self.assertRaises(R.ResourceError):
            R.validate_paths(self.root, self.state, self.stop, {})
        self.stop.write_bytes(b"")
        self.stop.chmod(0o600)
        self.assertTrue(R.stop_requested(self.stop))
        with self.assertRaises(R.ResourceError):
            R.validate_paths(self.root, self.state, self.stop, self.env)
        self.stop.unlink()
        self.stop.symlink_to(self.root)
        with self.assertRaises(R.ResourceError):
            R.stop_requested(self.stop)

    def test_foreign_context_linked_ancestor_and_root_overlap_rejected(self):
        foreign = R.audit_processes.ownership_environment({}, "3" * 32, "4" * 32,
                                                          str(self.root), str(self.root / "gradle-home"))
        with self.assertRaises(R.ResourceError):
            R.validate_paths(self.root, self.state, self.stop, foreign)
        alias = self.base / "alias"
        alias.symlink_to(self.state, target_is_directory=True)
        with self.assertRaises(R.ResourceError):
            R.validate_paths(self.root, alias, alias / "resource-stop", self.env)
        nested = self.root / "nested"
        nested.mkdir()
        with self.assertRaises(R.ResourceError):
            R.validate_paths(self.root, nested, nested / "resource-stop", self.env)

    def test_stop_requires_empty_private_single_link_regular_file(self):
        self.assertFalse(R.stop_requested(self.stop))
        self.stop.write_bytes(b"not a control")
        self.stop.chmod(0o600)
        with self.assertRaises(R.ResourceError):
            R.stop_requested(self.stop)
        self.stop.write_bytes(b"")
        self.stop.chmod(0o644)
        with self.assertRaises(R.ResourceError):
            R.stop_requested(self.stop)
        self.stop.chmod(0o600)
        os.link(self.stop, self.state / "other-link")
        with self.assertRaises(R.ResourceError):
            R.stop_requested(self.stop)

    def test_independent_synthetic_lanes_ready_then_both_retire(self):
        output, errors = io.StringIO(), io.StringIO()
        streams = R.Streams(output, errors)
        original = streams.sample
        lanes = set()
        def emit(row):
            original(row)
            if row["kind"] == "resource-sample":
                lanes.add(row["lane"])
            if row["kind"] == "resource-ready":
                self.stop.write_bytes(b"")
                self.stop.chmod(0o600)
        streams.sample = emit
        code = R.observe(R.validate_paths(self.root, self.state, self.stop, self.env), self.stop, streams,
                         samplers={"fast": fast, "network": network})
        records = [json.loads(line) for line in output.getvalue().splitlines()]
        self.assertEqual(code, 0)
        self.assertEqual(lanes, {"fast", "network"})
        self.assertEqual([row["kind"] for row in records[-2:]], ["resource-ready", "resource-stopped"])
        self.assertFalse(any(thread.name.startswith("hosted-resource-") for thread in threading.enumerate()))
        self.assertEqual(errors.getvalue(), "")

    def test_failure_in_either_lane_is_terminal_not_ready_or_stopped(self):
        for lane in ("fast", "network"):
            with self.subTest(lane=lane):
                output = io.StringIO()
                def failed():
                    raise R.ResourceError("SYNTHETIC_FAILURE")
                samplers = {"fast": fast, "network": network, lane: failed}
                code = R.observe(R.validate_paths(self.root, self.state, self.stop, self.env), self.stop,
                                 R.Streams(output, io.StringIO()), samplers=samplers)
                records = [json.loads(line) for line in output.getvalue().splitlines()]
                self.assertEqual(code, 125)
                self.assertTrue(any(row.get("code") == "SYNTHETIC_FAILURE" for row in records))
                self.assertFalse(any(row["kind"] in ("resource-ready", "resource-stopped") for row in records))
                self.assertFalse(any(thread.name.startswith("hosted-resource-") for thread in threading.enumerate()))

    def test_cancelled_observer_cannot_report_success(self):
        output = io.StringIO()
        code = R.observe(R.validate_paths(self.root, self.state, self.stop, self.env), self.stop,
                         R.Streams(output, io.StringIO()), cancelled=[15], samplers={"fast": fast, "network": network})
        self.assertEqual(code, 125)
        self.assertNotIn('"kind": "resource-stopped"', output.getvalue())

    def test_wrong_native_role_rejected_before_observations(self):
        output = io.StringIO()
        with patch.object(R.audit_processes, "host_role", return_value="macos-x64"), \
                patch.object(R, "observe") as observe, patch.object(R.sys, "stdout", output):
            code = R.main(["observe", "--root", str(self.root), "--state", str(self.state), "--stop-file", str(self.stop),
                           "--expected-host", "macos-arm64"])
        self.assertEqual(code, 125)
        observe.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["code"], "HOST_ROLE")

    def test_each_selected_native_role_reaches_observer_without_weakening_path_admission(self):
        roots = R.validate_paths(self.root, self.state, self.stop, self.env)
        for role in ("macos-arm64", "macos-x64"):
            with self.subTest(role=role):
                with patch.object(R.audit_processes, "host_role", return_value=role), \
                        patch.object(R.os, "geteuid", return_value=501), patch.dict(R.os.environ, self.env, clear=True), \
                        patch.object(R, "observe", return_value=0) as observe, patch.object(R.signal, "signal"):
                    code = R.main(["observe", "--root", str(self.root), "--state", str(self.state),
                                   "--stop-file", str(self.stop), "--expected-host", role])
                self.assertEqual(code, 0)
                self.assertEqual(observe.call_args.args[:2], (roots, self.stop))

    def test_selected_intel_rejects_arm_and_unsupported_actual_hosts(self):
        for actual in ("macos-arm64", "linux-x64", "windows-x64"):
            output = io.StringIO()
            with self.subTest(actual=actual):
                with patch.object(R.audit_processes, "host_role", return_value=actual), \
                        patch.object(R, "validate_paths") as paths, patch.object(R, "observe") as observe, \
                        patch.object(R.sys, "stdout", output):
                    code = R.main(["observe", "--root", str(self.root), "--state", str(self.state),
                                   "--stop-file", str(self.stop), "--expected-host", "macos-x64"])
                self.assertEqual(code, 125)
                self.assertEqual(json.loads(output.getvalue())["code"], "HOST_ROLE")
                paths.assert_not_called()
                observe.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
