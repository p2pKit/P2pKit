#!/usr/bin/env python3
"""Pure clock refusal/math controls; mocked OS observations are not runtime proof."""
import copy
import ctypes
import math
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rpc_apple_ci_clock as clock

BOOT = "abcdef12-1234-5678-9abc-abcdef123456"


def sample():
    return {"schema": 1, "clock": clock.CLOCK, "bootSession": BOOT, "monotonicNs": 100 * clock.BILLION,
            "wallNs": 1_700_000_000 * clock.BILLION, "sampleSpanNs": 1_000_000}


class ClockControls(unittest.TestCase):
    def runtime(self, *, system="Darwin", version=(3, 14), name="cpython", **changes):
        info = SimpleNamespace(implementation="mach_absolute_time()", monotonic=True, adjustable=False)
        for key, value in changes.items():
            setattr(info, key, value)
        with patch.object(clock.platform, "system", return_value=system), \
                patch.object(clock.sys, "version_info", version), \
                patch.object(clock.sys, "implementation", SimpleNamespace(name=name)), \
                patch.object(clock.time, "get_clock_info", return_value=info):
            clock.admit_runtime()

    def test_shared_cpython_310_and_newer_are_admitted(self):
        for version in ((3, 10), (3, 11), (3, 14)):
            self.runtime(version=version)

    def test_39_is_refused_even_with_identical_clock_implementation_name(self):
        for version in ((3, 9), (3, 8)):
            with self.subTest(version=version), self.assertRaises(ValueError):
                self.runtime(version=version)

    def test_other_runtime_clock_or_adjustable_clock_is_refused(self):
        for changes in ({"system": "Linux"}, {"name": "pypy"}, {"implementation": "clock_gettime(CLOCK_MONOTONIC)"},
                        {"monotonic": False}, {"monotonic": 1}, {"adjustable": True}, {"adjustable": 0}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.runtime(**changes)

    def test_unsupported_runtime_is_refused_before_native_observation(self):
        with patch.object(clock, "admit_runtime", side_effect=ValueError("refused")), \
                patch.object(clock, "boot_session") as native, self.assertRaises(ValueError):
            clock.sample_clock()
        native.assert_not_called()

    def test_actual_supplier_pairs_wall_between_two_awake_observations(self):
        with patch.object(clock, "admit_runtime"), patch.object(clock, "boot_session", return_value=BOOT), \
                patch.object(clock.time, "monotonic_ns", side_effect=[100, 110]), \
                patch.object(clock.time, "time_ns", return_value=1000):
            result = clock.sample_clock()
        self.assertEqual(result, {"schema": 1, "clock": clock.CLOCK, "bootSession": BOOT,
                                  "monotonicNs": 100, "wallNs": 1000, "sampleSpanNs": 10})

    def test_changed_boot_during_sample_is_refused(self):
        with patch.object(clock, "admit_runtime"), patch.object(clock, "boot_session", side_effect=[BOOT, "other"]), \
                patch.object(clock.time, "monotonic_ns", side_effect=[100, 110]), \
                patch.object(clock.time, "time_ns", return_value=1000), self.assertRaises(ValueError):
            clock.sample_clock()

    def test_complete_native_observation_is_inside_the_clock_bracket(self):
        order = []
        def record(name, value):
            order.append(name)
            return value
        with patch.object(clock, "admit_runtime"), \
                patch.object(clock, "boot_session", side_effect=lambda: record("boot", BOOT)), \
                patch.object(clock.time, "monotonic_ns", side_effect=lambda: record("monotonic", 100)), \
                patch.object(clock.time, "time_ns", side_effect=lambda: record("wall", 1000)):
            clock.sample_clock()
        self.assertEqual(order, ["monotonic", "boot", "wall", "boot", "monotonic"])

    def test_delayed_second_boot_read_is_charged_not_returned_as_fresh(self):
        now = [100]
        reads = [0]
        def delayed_boot():
            reads[0] += 1
            if reads[0] == 2:
                now[0] += clock.MAX_SAMPLE_SPAN_NS + 1
            return BOOT
        with patch.object(clock, "admit_runtime"), patch.object(clock, "boot_session", side_effect=delayed_boot), \
                patch.object(clock.time, "monotonic_ns", side_effect=lambda: now[0]), \
                patch.object(clock.time, "time_ns", return_value=1000), self.assertRaises(ValueError):
            clock.sample_clock()

    def test_slow_or_reversed_sampling_is_refused_not_retried(self):
        for values in ([100, 99], [100, 100 + clock.MAX_SAMPLE_SPAN_NS + 1]):
            with patch.object(clock, "admit_runtime"), patch.object(clock, "boot_session", return_value=BOOT), \
                    patch.object(clock.time, "monotonic_ns", side_effect=values) as mono, \
                    patch.object(clock.time, "time_ns", return_value=1000), self.assertRaises(ValueError):
                clock.sample_clock()
            self.assertEqual(mono.call_count, 2)

    def native_boot(self, raw=None, returned_size=37, code=0):
        raw = BOOT.upper().encode() + b"\0" if raw is None else raw
        def sysctl(name, value, size, new_value, new_size):
            self.assertEqual(name, b"kern.bootsessionuuid")
            self.assertIsNone(new_value)
            self.assertEqual(new_size, 0)
            self.assertEqual(size._obj.value, 37)
            self.assertEqual(len(value), 37)
            ctypes.memmove(value, raw, min(len(raw), 37))
            size._obj.value = returned_size
            return code
        function = Mock(side_effect=sysctl)
        library = SimpleNamespace(sysctlbyname=function)
        with patch.object(clock.ctypes, "CDLL", return_value=library) as load:
            result = clock.boot_session()
        load.assert_called_once_with("/usr/lib/libSystem.B.dylib", use_errno=True)
        function.assert_called_once()
        return result

    def test_native_boot_read_has_fixed_key_size_and_no_write_input(self):
        self.assertEqual(self.native_boot(), BOOT)

    def test_native_boot_failures_short_reads_and_non_uuid_are_refused(self):
        for change in ({"code": -1}, {"returned_size": 36}, {"returned_size": 38},
                       {"raw": b"X" * 37}, {"raw": b"x" * 36 + b"\0"},
                       {"raw": b"\xff" * 36 + b"\0"},
                       {"raw": b"00000000-0000-0000-0000-000000000000\0"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                self.native_boot(**change)

    def test_sample_fields_are_closed_and_do_not_coerce_booleans(self):
        for field in clock.KEYS:
            changed = sample()
            changed.pop(field)
            with self.subTest(field=field), self.assertRaises(ValueError):
                clock.validate_sample(changed)
        for change in ({"schema": True}, {"clock": "systemUptime"}, {"extra": 1}, {"bootSession": None}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                clock.validate_sample({**sample(), **change})
        for field in ("monotonicNs", "wallNs", "sampleSpanNs"):
            for value in (True, -1, "1", 1.0, None, clock.MAX_NS + 1):
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    clock.validate_sample({**sample(), field: value})

    def test_sample_span_and_sum_are_bounded(self):
        for change in ({"wallNs": 0}, {"sampleSpanNs": clock.MAX_SAMPLE_SPAN_NS + 1},
                       {"monotonicNs": clock.MAX_NS, "sampleSpanNs": 1}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                clock.validate_sample({**sample(), **change})

    def test_wall_and_awake_progress_preserve_the_original_anchor(self):
        anchor = sample()
        unchanged = copy.deepcopy(anchor)
        current = {**anchor, "wallNs": anchor["wallNs"] + 3 * clock.BILLION,
                   "monotonicNs": anchor["monotonicNs"] + 3 * clock.BILLION}
        clock.validate_progress(anchor, current)
        self.assertEqual(anchor, unchanged)

    def test_host_sleep_and_accumulating_drift_do_not_renew_original_job(self):
        anchor = sample()
        first = {**anchor, "wallNs": anchor["wallNs"] + 3 * clock.BILLION - anchor["sampleSpanNs"],
                 "monotonicNs": anchor["monotonicNs"] + 2 * clock.BILLION}
        clock.validate_progress(anchor, first)
        late = {**anchor, "wallNs": anchor["wallNs"] + 6 * clock.BILLION,
                "monotonicNs": anchor["monotonicNs"] + 4 * clock.BILLION}
        with self.assertRaises(ValueError):
            clock.validate_progress(anchor, late)

    def test_clock_reversal_or_boot_change_refuses_progress(self):
        anchor = sample()
        for change in ({"wallNs": anchor["wallNs"] - 1}, {"monotonicNs": anchor["monotonicNs"] - 1},
                       {"bootSession": "abcdef12-1234-5678-9abc-abcdef123457"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                clock.validate_progress(anchor, {**anchor, **change})

    def test_exact_existing_divergence_limit_is_not_extended(self):
        anchor = sample()
        for delta in (clock.BILLION, clock.BILLION + 1):
            current = {**anchor, "wallNs": anchor["wallNs"] + 2 * clock.BILLION + delta - anchor["sampleSpanNs"],
                       "monotonicNs": anchor["monotonicNs"] + 2 * clock.BILLION}
            if delta == clock.BILLION:
                clock.validate_progress(anchor, current)
            else:
                with self.assertRaises(ValueError):
                    clock.validate_progress(anchor, current)

    def test_asymmetric_brackets_are_charged_inside_not_beyond_drift_margin(self):
        anchor = {**sample(), "sampleSpanNs": 10_000_000}
        current = {**anchor, "sampleSpanNs": 40_000_000,
                   "monotonicNs": anchor["monotonicNs"] + 5 * clock.BILLION}
        for difference, allowed in ((990_000_000, True), (990_000_001, False),
                                    (-960_000_000, True), (-960_000_001, False),
                                    (clock.BILLION, False), (-clock.BILLION, False)):
            observation = {**current, "wallNs": anchor["wallNs"] + 5 * clock.BILLION + difference}
            with self.subTest(difference=difference):
                if allowed:
                    clock.validate_progress(anchor, observation)
                else:
                    with self.assertRaises(ValueError):
                        clock.validate_progress(anchor, observation)

    def test_cutoff_conversion_floors_exact_ratio_never_rounds_later(self):
        for value in (0, 1, 0.1, math.nextafter(1.0, -math.inf), 123456.123456789, 9_000_000_000.12345):
            numerator, denominator = value.as_integer_ratio()
            expected = numerator * clock.BILLION // denominator
            actual = clock.floor_seconds_ns(value)
            self.assertEqual(actual, expected)
            self.assertLessEqual(actual * denominator, numerator * clock.BILLION)
            self.assertGreater((actual + 1) * denominator, numerator * clock.BILLION)

    def test_invalid_or_overflowing_cutoff_is_not_clamped_to_another_deadline(self):
        for value in (True, None, "1", -1, -0.1, math.nan, math.inf, -math.inf, 10**1000):
            with self.subTest(kind=type(value).__name__), self.assertRaises(ValueError):
                clock.floor_seconds_ns(value)


if __name__ == "__main__":
    unittest.main(verbosity=2)
