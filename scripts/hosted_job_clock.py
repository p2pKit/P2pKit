#!/usr/bin/env python3
"""Dormant same-host elapsed clocks for future ordinary job-budget callers.

Readings are observations, not source/run admission or scheduling authority.
No workflow, existing FULL clock, process owner or timeout is changed here.
Importing this module reads no clock and loads no Windows library. There is no
wall-clock/process-local-epoch fallback, configurable backend, CLI or launcher.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
from functools import lru_cache
import math
import sys
import time

import audit_processes as processes

NS = 1_000_000_000
UINT64, INT64 = (1 << 64) - 1, (1 << 63) - 1
# The Darwin-only resource supplier cannot be imported on Windows. Pin its
# existing domain without loading it; the selected reader checks it again.
DARWIN_DOMAIN = "darwin.clock_gettime_ns(CLOCK_MONOTONIC_RAW)"
LINUX_DOMAIN = "linux.clock_gettime_ns(CLOCK_MONOTONIC_RAW)"
WINDOWS_DOMAIN = "windows.QueryPerformanceCounter/QueryPerformanceFrequency.floor_ns"
DOMAINS = {
    "macos-arm64": DARWIN_DOMAIN,
    "macos-x64": DARWIN_DOMAIN,
    "linux-x64": LINUX_DOMAIN,
    "windows-x64": WINDOWS_DOMAIN,
}


class ClockError(ValueError):
    """Finite source-owned reason; no native exception text or host identifiers."""


def require(value, code):
    if not value:
        raise ClockError(code)


def integer(value, maximum=UINT64):
    require(type(value) is int and 0 <= value <= maximum, "JOB_CLOCK_INTEGER")
    return value


@dataclass(frozen=True)
class ClockIdentity:
    role: str
    domain: str
    ticks_per_second: int


@dataclass(frozen=True)
class Reading:
    clock: ClockIdentity
    nanoseconds: int


def validate_identity(value):
    """Validate supplied data only; an identity does not attest an actual host."""
    require(type(value) is ClockIdentity and type(value.role) is str and value.role in DOMAINS and
            type(value.domain) is str and value.domain == DOMAINS[value.role], "JOB_CLOCK_IDENTITY")
    frequency = integer(value.ticks_per_second, INT64)
    require(frequency > 0 and (value.role == "windows-x64" or frequency == NS), "JOB_CLOCK_FREQUENCY")
    return value


def validate_reading(value):
    require(type(value) is Reading, "JOB_CLOCK_READING")
    validate_identity(value.clock)
    integer(value.nanoseconds)
    return value


def elapsed_ns(before, after):
    """Same admitted machine/boot is a caller obligation, not proved by labels."""
    validate_reading(before)
    validate_reading(after)
    require(before.clock == after.clock, "JOB_CLOCK_IDENTITY_CHANGED")
    require(after.nanoseconds >= before.nanoseconds, "JOB_CLOCK_BACKWARDS")
    return after.nanoseconds - before.nanoseconds


class _Qpc:
    """One lazy process-lifetime reference to the fixed system library; no HANDLE."""
    def __init__(self):
        require(sys.platform == "win32" and callable(getattr(ctypes, "WinDLL", None)),
                "JOB_CLOCK_QPC_UNAVAILABLE")
        # Never a caller path or DLL search through the workspace/current PATH.
        self.library = ctypes.WinDLL("kernel32.dll", use_last_error=True, winmode=0x00000800)
        self.counter = self.library.QueryPerformanceCounter
        self.frequency = self.library.QueryPerformanceFrequency
        for function in (self.counter, self.frequency):
            function.argtypes = [ctypes.POINTER(ctypes.c_longlong)]
            function.restype = ctypes.c_int

    def read(self):
        frequency, ticks = ctypes.c_longlong(), ctypes.c_longlong()
        require(self.frequency(ctypes.byref(frequency)) != 0, "JOB_CLOCK_QPC_FREQUENCY_FAILED")
        hz = integer(frequency.value, INT64)
        require(hz > 0, "JOB_CLOCK_FREQUENCY")
        require(self.counter(ctypes.byref(ticks)) != 0, "JOB_CLOCK_QPC_READ_FAILED")
        count = integer(ticks.value, INT64)
        # Integer floor, never floating-point seconds, preserves counter precision.
        return integer(count * NS // hz), hz


@lru_cache(maxsize=1)
def _qpc():
    return _Qpc()


def _darwin_raw_ns():
    require(sys.platform == "darwin", "JOB_CLOCK_PLATFORM")
    # Lazy import is necessary: this unchanged Mac resource observer also owns
    # Unix-only defaults unrelated to reading time. Never import it for QPC.
    import hosted_lock_resources as darwin
    require(darwin.RAW_CLOCK_DOMAIN == DARWIN_DOMAIN, "JOB_CLOCK_DARWIN_DOMAIN")
    return darwin.shared_raw_ns()


def observe():
    """Read the actual interpreter's closed role; no environment-selected epoch.

    Reuse host_role()'s native architecture/translation checks; complete native
    owner/toolchain admission remains separate. Linux/Darwin clocks exclude suspended time;
    QPC's OS-defined suspend accounting is not normalized to those clocks. Never
    compare readings across roles, machines or boots.
    """
    try:
        role = processes.host_role()
        require(type(role) is str and role in DOMAINS, "JOB_CLOCK_ROLE")
        if role.startswith("macos-"):
            require(sys.platform == "darwin", "JOB_CLOCK_PLATFORM")
            value, frequency = _darwin_raw_ns(), NS
        elif role == "linux-x64":
            require(sys.platform == "linux", "JOB_CLOCK_PLATFORM")
            function, kind = getattr(time, "clock_gettime_ns", None), getattr(time, "CLOCK_MONOTONIC_RAW", None)
            require(callable(function) and type(kind) is int, "JOB_CLOCK_LINUX_RAW_UNAVAILABLE")
            value, frequency = function(kind), NS
        else:
            require(sys.platform == "win32", "JOB_CLOCK_PLATFORM")
            value, frequency = _qpc().read()
        return validate_reading(Reading(ClockIdentity(role, DOMAINS[role], frequency), value))
    except ClockError:
        raise
    except Exception:
        raise ClockError("JOB_CLOCK_READ_FAILED") from None


def checked_now(expected, *, minimum_ns=0):
    """Check a new actual reading against an original bound identity/minimum."""
    validate_identity(expected)
    integer(minimum_ns)
    actual = observe()
    elapsed_ns(Reading(expected, minimum_ns), actual)
    return actual.nanoseconds


def local_deadline(expected, fence_ns, maximum_seconds, *, minimum_ns=0):
    """Convert a bound shared fence to a shorter LOCAL, never serialized deadline.

    Sampling local time before the shared clock charges conversion work against
    the allowance. Directed rounding does not add time. Callers must still check
    the original shared fence at return/ownership boundaries; this utility cannot
    cancel a blocking OS call or turn a failed retirement into success.
    """
    validate_identity(expected)
    integer(fence_ns)
    integer(minimum_ns)
    require(type(maximum_seconds) in (int, float), "JOB_CLOCK_OPERATION_LIMIT")
    try:
        maximum = float(maximum_seconds)
    except (OverflowError, ValueError):
        raise ClockError("JOB_CLOCK_OPERATION_LIMIT") from None
    require(math.isfinite(maximum) and maximum > 0, "JOB_CLOCK_OPERATION_LIMIT")
    try:
        local = time.monotonic()
    except Exception:
        raise ClockError("JOB_CLOCK_LOCAL_SAMPLE") from None
    require(type(local) in (int, float) and math.isfinite(local) and local >= 0, "JOB_CLOCK_LOCAL_SAMPLE")
    now = checked_now(expected, minimum_ns=minimum_ns)
    require(now < fence_ns, "JOB_CLOCK_FENCE_EXPIRED")
    remaining = math.nextafter((fence_ns - now) / NS, 0.0)
    result = math.nextafter(local + min(maximum, remaining), -math.inf)
    require(math.isfinite(result) and result > local, "JOB_CLOCK_LOCAL_DEADLINE")
    return result
