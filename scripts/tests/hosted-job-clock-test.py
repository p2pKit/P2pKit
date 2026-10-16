#!/usr/bin/env python3
"""Offline clock/API models only: no genuine native read, child or network."""
from __future__ import annotations

from contextlib import ExitStack, contextmanager
import ctypes
from dataclasses import FrozenInstanceError
from fractions import Fraction
import importlib.util
import math
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("tested_hosted_job_clock", SCRIPTS / "hosted_job_clock.py")
CLOCK = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CLOCK
SPEC.loader.exec_module(CLOCK)


class NativeFunctionModel:
    def __init__(self, value, status=1):
        self.value, self.status, self.calls = value, status, 0

    def __call__(self, pointer):
        self.calls += 1
        pointer._obj.value = self.value
        return self.status


class KernelModel:
    def __init__(self, ticks=123, frequency=10_000_000):
        self.QueryPerformanceCounter = NativeFunctionModel(ticks)
        self.QueryPerformanceFrequency = NativeFunctionModel(frequency)


class ClockModels(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        # Refuse accidental real role/native/clock access in this offline suite.
        self.role = self.stack.enter_context(mock.patch.object(CLOCK.processes, "host_role", return_value="linux-x64"))
        self.stack.enter_context(mock.patch.object(CLOCK.sys, "platform", "linux"))
        self.raw = self.stack.enter_context(mock.patch.object(CLOCK.time, "clock_gettime_ns", side_effect=AssertionError("unmodeled raw clock"), create=True))
        self.darwin = self.stack.enter_context(mock.patch.object(CLOCK, "_darwin_raw_ns", side_effect=AssertionError("unmodeled Darwin clock")))
        self.local = self.stack.enter_context(mock.patch.object(CLOCK.time, "monotonic", side_effect=AssertionError("unmodeled local clock")))
        self.stack.enter_context(mock.patch.object(CLOCK.time, "time", side_effect=AssertionError("wall clock is not a fallback")))
        self.stack.enter_context(mock.patch.object(CLOCK.time, "perf_counter", side_effect=AssertionError("no implicit QPC fallback")))
        self.stack.enter_context(mock.patch.object(CLOCK.ctypes, "WinDLL", side_effect=AssertionError("unmodeled DLL"), create=True))
        CLOCK._qpc.cache_clear()
        self.addCleanup(CLOCK._qpc.cache_clear)
        self.linux = CLOCK.ClockIdentity("linux-x64", CLOCK.LINUX_DOMAIN, CLOCK.NS)
        self.windows = CLOCK.ClockIdentity("windows-x64", CLOCK.WINDOWS_DOMAIN, 10_000_000)

    def reading(self, ns, identity=None):
        return CLOCK.Reading(identity or self.linux, ns)

    @contextmanager
    def windows_api(self, kernel=None):
        kernel = kernel or KernelModel()
        with mock.patch.object(CLOCK.processes, "host_role", return_value="windows-x64"), \
                mock.patch.object(CLOCK.sys, "platform", "win32"), \
                mock.patch.object(CLOCK.ctypes, "WinDLL", return_value=kernel) as loader:
            yield kernel, loader

    def test_import_reads_no_clocks_native_library_or_role(self):
        name = "clock_import_probe"
        spec = importlib.util.spec_from_file_location(name, SCRIPTS / "hosted_job_clock.py")
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(sys.modules, {name: module}):
            spec.loader.exec_module(module)
        self.role.assert_not_called()
        self.raw.assert_not_called()
        self.darwin.assert_not_called()
        self.local.assert_not_called()

    def test_cold_import_needs_no_unix_api_or_darwin_module(self):
        name = "clock_import_without_unix_api"
        spec = importlib.util.spec_from_file_location(name, SCRIPTS / "hosted_job_clock.py")
        module = importlib.util.module_from_spec(spec)
        with mock.patch.dict(os.__dict__), mock.patch.dict(CLOCK.time.__dict__), \
                mock.patch.dict(sys.modules, {name: module, "hosted_lock_resources": None}):
            os.__dict__.pop("statvfs", None)
            CLOCK.time.__dict__.pop("clock_gettime_ns", None)
            spec.loader.exec_module(module)
        self.role.assert_not_called()
        self.raw.assert_not_called()
        self.darwin.assert_not_called()

    def test_darwin_reader_lazily_uses_exact_original_domain_and_function(self):
        # Load the real reader into a new module, not setUp's blocked reader.
        name = "clock_darwin_reader_probe"
        spec = importlib.util.spec_from_file_location(name, SCRIPTS / "hosted_job_clock.py")
        module = importlib.util.module_from_spec(spec)
        read = mock.Mock(return_value=321)
        supplier = SimpleNamespace(RAW_CLOCK_DOMAIN=CLOCK.DARWIN_DOMAIN, shared_raw_ns=read)
        with mock.patch.dict(sys.modules, {name: module, "hosted_lock_resources": supplier}):
            spec.loader.exec_module(module)
            read.assert_not_called()
            with self.assertRaisesRegex(module.ClockError, "JOB_CLOCK_PLATFORM"):
                module._darwin_raw_ns()
            with mock.patch.object(CLOCK.sys, "platform", "darwin"):
                self.assertEqual(module._darwin_raw_ns(), 321)
                read.assert_called_once_with()
                supplier.RAW_CLOCK_DOMAIN = "changed-domain"
                with self.assertRaisesRegex(module.ClockError, "JOB_CLOCK_DARWIN_DOMAIN"):
                    module._darwin_raw_ns()
                self.assertEqual(read.call_count, 1)

    def test_identity_and_reading_are_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            self.linux.role = "windows-x64"
        value = self.reading(10)
        with self.assertRaises(FrozenInstanceError):
            value.nanoseconds = 20

    def test_closed_identity_types_domains_roles_and_frequency(self):
        for value in (None, {}, CLOCK.ClockIdentity("linux-arm64", CLOCK.LINUX_DOMAIN, CLOCK.NS),
                      CLOCK.ClockIdentity("linux-x64", CLOCK.WINDOWS_DOMAIN, CLOCK.NS),
                      CLOCK.ClockIdentity("linux-x64", CLOCK.LINUX_DOMAIN, 10),
                      CLOCK.ClockIdentity("windows-x64", CLOCK.WINDOWS_DOMAIN, 0),
                      CLOCK.ClockIdentity("windows-x64", CLOCK.WINDOWS_DOMAIN, True),
                      CLOCK.ClockIdentity("windows-x64", CLOCK.WINDOWS_DOMAIN, CLOCK.INT64 + 1)):
            with self.subTest(value=value), self.assertRaises(CLOCK.ClockError):
                CLOCK.validate_identity(value)

    def test_reading_rejects_bool_negative_float_overflow_and_wrong_type(self):
        for value in (True, -1, 1.0, "1", CLOCK.UINT64 + 1):
            with self.subTest(value=value), self.assertRaises(CLOCK.ClockError):
                CLOCK.validate_reading(self.reading(value))
        with self.assertRaises(CLOCK.ClockError):
            CLOCK.validate_reading({"clock": self.linux, "nanoseconds": 1})
        self.assertEqual(CLOCK.validate_reading(self.reading(CLOCK.UINT64)).nanoseconds, CLOCK.UINT64)

    def test_elapsed_uses_only_same_identity_without_reading_a_clock(self):
        self.assertEqual(CLOCK.elapsed_ns(self.reading(10), self.reading(13)), 3)
        self.assertEqual(CLOCK.elapsed_ns(self.reading(10), self.reading(10)), 0)
        self.role.assert_not_called()

    def test_elapsed_rejects_backward_cross_role_domain_and_frequency(self):
        for value in (self.reading(9), self.reading(11, self.windows),
                      self.reading(11, CLOCK.ClockIdentity("linux-x64", CLOCK.WINDOWS_DOMAIN, CLOCK.NS))):
            with self.subTest(value=value), self.assertRaises(CLOCK.ClockError):
                CLOCK.elapsed_ns(self.reading(10), value)
        with self.assertRaisesRegex(CLOCK.ClockError, "IDENTITY_CHANGED"):
            CLOCK.elapsed_ns(self.reading(10, self.windows), self.reading(11,
                CLOCK.ClockIdentity("windows-x64", CLOCK.WINDOWS_DOMAIN, 10_000_001)))

    def test_darwin_delegates_unchanged_raw_supplier_for_both_native_roles(self):
        self.darwin.side_effect = None
        self.darwin.return_value = 321
        for role in ("macos-arm64", "macos-x64"):
            with self.subTest(role=role), mock.patch.object(CLOCK.sys, "platform", "darwin"):
                self.role.return_value = role
                value = CLOCK.observe()
                self.assertEqual(value, CLOCK.Reading(CLOCK.ClockIdentity(role, CLOCK.DARWIN_DOMAIN, CLOCK.NS), 321))
        self.assertEqual(self.darwin.call_count, 2)
        self.raw.assert_not_called()
        self.local.assert_not_called()

    def test_linux_uses_explicit_raw_id_and_exact_nanoseconds(self):
        self.raw.side_effect = None
        self.raw.return_value = (1 << 53) + 1
        with mock.patch.object(CLOCK.time, "CLOCK_MONOTONIC_RAW", 4, create=True):
            self.assertEqual(CLOCK.observe(), self.reading((1 << 53) + 1))
        self.raw.assert_called_once_with(4)
        self.local.assert_not_called()
        self.darwin.assert_not_called()

    def test_linux_missing_raw_source_has_no_monotonic_or_other_clock_fallback(self):
        for value in (None, True, "4"):
            with self.subTest(value=value), mock.patch.object(CLOCK.time, "CLOCK_MONOTONIC_RAW", value, create=True):
                with self.assertRaisesRegex(CLOCK.ClockError, "LINUX_RAW_UNAVAILABLE"):
                    CLOCK.observe()
        with mock.patch.object(CLOCK.time, "clock_gettime_ns", None):
            with self.assertRaisesRegex(CLOCK.ClockError, "LINUX_RAW_UNAVAILABLE"):
                CLOCK.observe()
        self.raw.assert_not_called()
        self.local.assert_not_called()

    def test_linux_bad_values_and_read_failure_refuse(self):
        with mock.patch.object(CLOCK.time, "CLOCK_MONOTONIC_RAW", 4, create=True):
            for value in (-1, True, 1.5, CLOCK.UINT64 + 1):
                self.raw.side_effect = None
                self.raw.return_value = value
                with self.subTest(value=value), self.assertRaises(CLOCK.ClockError):
                    CLOCK.observe()
            self.raw.side_effect = OSError("private native diagnostic")
            with self.assertRaisesRegex(CLOCK.ClockError, "^JOB_CLOCK_READ_FAILED$"):
                CLOCK.observe()

    def test_wrong_role_platform_or_failed_native_admission_cannot_select_clock(self):
        for role in ("windows-x64", "macos-arm64", "macos-x64", "linux-arm64", "unsupported", None):
            self.role.return_value = role
            with self.subTest(role=role), self.assertRaises(CLOCK.ClockError):
                CLOCK.observe()
        self.role.side_effect = CLOCK.processes.OwnershipError("translation refused")
        with self.assertRaisesRegex(CLOCK.ClockError, "^JOB_CLOCK_READ_FAILED$"):
            CLOCK.observe()
        self.raw.assert_not_called()
        self.darwin.assert_not_called()

    def test_windows_fixed_system_dll_signatures_and_lazy_process_reference(self):
        with self.windows_api() as (kernel, loader):
            first, second = CLOCK.observe(), CLOCK.observe()
            self.assertEqual(first, CLOCK.Reading(self.windows, 12300))
            self.assertEqual(first, second)
            loader.assert_called_once_with("kernel32.dll", use_last_error=True, winmode=0x00000800)
            for function in (kernel.QueryPerformanceCounter, kernel.QueryPerformanceFrequency):
                self.assertEqual(function.argtypes, [ctypes.POINTER(ctypes.c_longlong)])
                self.assertIs(function.restype, ctypes.c_int)
                self.assertEqual(function.calls, 2)
        self.raw.assert_not_called()
        self.local.assert_not_called()

    def test_windows_integer_conversion_retains_large_counter_precision_and_floors(self):
        for count, hz in (((1 << 53) + 1, CLOCK.NS), (5, 3), (CLOCK.INT64, CLOCK.INT64), (0, 10_000_000)):
            CLOCK._qpc.cache_clear()
            with self.subTest(count=count, hz=hz), self.windows_api(KernelModel(count, hz)):
                result = CLOCK.observe()
                self.assertEqual(result.nanoseconds, count * CLOCK.NS // hz)
                self.assertEqual(result.clock.ticks_per_second, hz)

    def test_windows_failed_frequency_does_not_read_counter(self):
        with self.windows_api() as (kernel, _):
            kernel.QueryPerformanceFrequency.status = 0
            with self.assertRaisesRegex(CLOCK.ClockError, "QPC_FREQUENCY_FAILED"):
                CLOCK.observe()
            self.assertEqual(kernel.QueryPerformanceCounter.calls, 0)

    def test_windows_zero_or_negative_frequency_does_not_read_counter(self):
        for hz in (0, -1):
            CLOCK._qpc.cache_clear()
            with self.subTest(hz=hz), self.windows_api(KernelModel(frequency=hz)) as (kernel, _):
                with self.assertRaises(CLOCK.ClockError):
                    CLOCK.observe()
                self.assertEqual(kernel.QueryPerformanceCounter.calls, 0)

    def test_windows_counter_failure_negative_counter_and_ns_overflow_refuse(self):
        for ticks, hz, status in ((1, CLOCK.NS, 0), (-1, CLOCK.NS, 1), (CLOCK.INT64, 1, 1)):
            CLOCK._qpc.cache_clear()
            with self.subTest(ticks=ticks, hz=hz, status=status), self.windows_api(KernelModel(ticks, hz)) as (kernel, _):
                kernel.QueryPerformanceCounter.status = status
                with self.assertRaises(CLOCK.ClockError):
                    CLOCK.observe()

    def test_windows_library_failure_is_finite_and_has_no_fallback(self):
        with self.windows_api() as (_, loader):
            loader.side_effect = OSError("private loader path")
            with self.assertRaisesRegex(CLOCK.ClockError, "^JOB_CLOCK_READ_FAILED$"):
                CLOCK.observe()
        self.local.assert_not_called()
        self.raw.assert_not_called()

    def test_qpc_native_entry_refuses_foreign_platform_before_library_access(self):
        with self.assertRaisesRegex(CLOCK.ClockError, "QPC_UNAVAILABLE"):
            CLOCK._Qpc()

    def test_clock_read_does_not_swallow_keyboard_cancellation(self):
        self.role.side_effect = KeyboardInterrupt("cancel")
        with self.assertRaises(KeyboardInterrupt):
            CLOCK.observe()

    def test_checked_now_requires_original_identity_and_non_decreasing_lower_bound(self):
        with mock.patch.object(CLOCK, "observe", return_value=self.reading(100)):
            self.assertEqual(CLOCK.checked_now(self.linux, minimum_ns=99), 100)
            self.assertEqual(CLOCK.checked_now(self.linux, minimum_ns=100), 100)
            with self.assertRaisesRegex(CLOCK.ClockError, "BACKWARDS"):
                CLOCK.checked_now(self.linux, minimum_ns=101)
            with self.assertRaisesRegex(CLOCK.ClockError, "IDENTITY_CHANGED"):
                CLOCK.checked_now(self.windows)

    def test_checked_now_rejects_changed_qpc_frequency(self):
        with self.windows_api() as (kernel, _):
            initial = CLOCK.observe()
            kernel.QueryPerformanceFrequency.value += 1
            with self.assertRaisesRegex(CLOCK.ClockError, "IDENTITY_CHANGED"):
                CLOCK.checked_now(initial.clock, minimum_ns=initial.nanoseconds)

    def test_checked_now_rejects_invalid_input_before_native_read(self):
        with mock.patch.object(CLOCK, "observe") as read:
            for minimum in (True, -1, CLOCK.UINT64 + 1, 1.5):
                with self.subTest(minimum=minimum), self.assertRaises(CLOCK.ClockError):
                    CLOCK.checked_now(self.linux, minimum_ns=minimum)
            with self.assertRaises(CLOCK.ClockError):
                CLOCK.checked_now({})
            read.assert_not_called()

    def test_deadline_samples_local_first_and_never_renews_an_original_fence(self):
        order = []
        self.local.side_effect = lambda: order.append("local") or 1000.0
        def read():
            order.append("shared")
            return self.reading(100 * CLOCK.NS)
        with mock.patch.object(CLOCK, "observe", side_effect=read):
            result = CLOCK.local_deadline(self.linux, 105 * CLOCK.NS, 30)
        self.assertEqual(order, ["local", "shared"])
        self.assertLess(result, 1005.0)
        self.assertGreater(result, 1004.9)

    def test_deadline_clamps_each_local_process_to_same_fence_not_new_allowance(self):
        self.local.side_effect = None
        self.local.return_value = 10.0
        with mock.patch.object(CLOCK, "observe", return_value=self.reading(100 * CLOCK.NS)):
            first = CLOCK.local_deadline(self.linux, 105 * CLOCK.NS, 30)
        # A later process has an unrelated local epoch; remaining shared time is only1s.
        self.local.return_value = 9000.0
        with mock.patch.object(CLOCK, "observe", return_value=self.reading(104 * CLOCK.NS)):
            second = CLOCK.local_deadline(self.linux, 105 * CLOCK.NS, 30)
        self.assertLess(first - 10, 5)
        self.assertLess(second - 9000, 1)

    def test_deadline_honors_smaller_operation_maximum(self):
        self.local.side_effect = None
        self.local.return_value = 20.0
        with mock.patch.object(CLOCK, "observe", return_value=self.reading(0)):
            self.assertLess(CLOCK.local_deadline(self.linux, 100 * CLOCK.NS, 3), 23.0)

    def test_deadline_directed_rounding_cannot_extend_exact_remaining_time(self):
        self.local.side_effect = None
        for local, remaining, maximum in ((0.0, 1, 30), (123.25, 1_000_000_001, 30),
                                           (12.0, 1_234_567_890, .1), (1.0, CLOCK.UINT64, 1e100)):
            self.local.return_value = local
            with self.subTest(local=local, remaining=remaining, maximum=maximum), \
                    mock.patch.object(CLOCK, "observe", return_value=self.reading(0)):
                result = CLOCK.local_deadline(self.linux, remaining, maximum)
                allowed = min(Fraction(remaining, CLOCK.NS), Fraction(maximum))
                self.assertLessEqual(Fraction(result) - Fraction(local), allowed)
                self.assertGreater(result, local)

    def test_expired_shared_fence_is_not_replaced_with_operation_maximum(self):
        self.local.side_effect = None
        self.local.return_value = 10.0
        for now in (100, 101):
            with self.subTest(now=now), mock.patch.object(CLOCK, "observe", return_value=self.reading(now)):
                with self.assertRaisesRegex(CLOCK.ClockError, "FENCE_EXPIRED"):
                    CLOCK.local_deadline(self.linux, 100, 60)

    def test_deadline_rejects_bad_maximum_and_fence_before_any_clock_access(self):
        with mock.patch.object(CLOCK, "observe") as read:
            for maximum in (True, None, "30", 0, -1, math.inf, math.nan, 10 ** 400):
                with self.subTest(maximum=str(maximum)[:32]), self.assertRaises(CLOCK.ClockError):
                    CLOCK.local_deadline(self.linux, 100, maximum)
            for fence in (True, -1, CLOCK.UINT64 + 1, 1.0):
                with self.subTest(fence=fence), self.assertRaises(CLOCK.ClockError):
                    CLOCK.local_deadline(self.linux, fence, 30)
            read.assert_not_called()
            self.local.assert_not_called()

    def test_deadline_refuses_invalid_local_read_or_error_without_shared_read(self):
        with mock.patch.object(CLOCK, "observe") as read:
            self.local.side_effect = None
            for value in (True, -1.0, math.nan, math.inf):
                self.local.return_value = value
                with self.subTest(value=value), self.assertRaisesRegex(CLOCK.ClockError, "LOCAL_SAMPLE"):
                    CLOCK.local_deadline(self.linux, 100, 30)
            self.local.side_effect = OSError("private local read detail")
            with self.assertRaisesRegex(CLOCK.ClockError, "^JOB_CLOCK_LOCAL_SAMPLE$"):
                CLOCK.local_deadline(self.linux, 100, 30)
            read.assert_not_called()

    def test_unrepresentable_short_local_interval_refuses_instead_of_rounding_up(self):
        self.local.side_effect = None
        self.local.return_value = 1e100
        with mock.patch.object(CLOCK, "observe", return_value=self.reading(0)):
            with self.assertRaisesRegex(CLOCK.ClockError, "LOCAL_DEADLINE"):
                CLOCK.local_deadline(self.linux, 1, 30)


if __name__ == "__main__":
    unittest.main()
