"""Read-only shared Mach clock for the inactive ordinary-CI Apple adapter.

Python 3.9 Darwin monotonic values have a process-local origin. Pure component
tests may run there, but only CPython 3.10+ with the actual shared Mach clock can
supply native deadlines. No clock observation authorizes native execution.
Returned boot/clock observations are private, not public qualification evidence.
"""
from __future__ import annotations

import ctypes
import math
import platform
import re
import sys
import time

from rpc_apple_ci_admission import require


CLOCK = "MACH_ABSOLUTE_NANOSECONDS_V1"
BILLION = 1_000_000_000
MAX_NS = 2**63 - 1
MAX_SAMPLE_SPAN_NS = 50_000_000
MAX_DIVERGENCE_NS = BILLION  # Already charged by plan_envelope; never extra job time.
KEYS = {"schema", "clock", "bootSession", "monotonicNs", "wallNs", "sampleSpanNs"}


def admit_runtime() -> None:
    info = time.get_clock_info("monotonic")
    require(platform.system() == "Darwin" and sys.implementation.name == "cpython" and
            sys.version_info[:2] >= (3, 10) and info.implementation == "mach_absolute_time()" and
            info.monotonic is True and info.adjustable is False,
            "Shared Darwin CPython 3.10+ Mach clock required")


def boot_session() -> str:
    """Read only the fixed kernel boot UUID, with a fixed-size native buffer."""
    system = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
    read = system.sysctlbyname
    read.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
                     ctypes.c_void_p, ctypes.c_size_t]
    read.restype = ctypes.c_int
    value = ctypes.create_string_buffer(37)
    size = ctypes.c_size_t(len(value))
    require(read(b"kern.bootsessionuuid", value, ctypes.byref(size), None, 0) == 0 and
            size.value == 37 and value.raw[-1:] == b"\0", "Kernel boot observation failed")
    try:
        result = value.raw[:-1].decode("ascii").lower()
    except UnicodeError:
        raise ValueError("Kernel boot observation failed") from None
    require(valid_boot(result), "Kernel boot observation failed")
    return result


def valid_boot(value: object) -> bool:
    return (type(value) is str and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value)
            is not None and set(value.replace("-", "")) != {"0"})


def validate_sample(value: dict) -> None:
    require(type(value) is dict and set(value) == KEYS and type(value["schema"]) is int and
            value["schema"] == 1 and value["clock"] == CLOCK and valid_boot(value["bootSession"]),
            "Closed shared clock observation required")
    for key in ("monotonicNs", "wallNs", "sampleSpanNs"):
        require(type(value[key]) is int and 0 <= value[key] <= MAX_NS, "Invalid shared clock number")
    require(value["wallNs"] > 0 and value["sampleSpanNs"] <= MAX_SAMPLE_SPAN_NS and
            value["monotonicNs"] + value["sampleSpanNs"] <= MAX_NS, "Unbounded shared clock sample")


def sample_clock() -> dict:
    admit_runtime()  # Refuse before entering a native function on another supplier/OS.
    before = time.monotonic_ns()
    boot = boot_session()
    wall = time.time_ns()
    boot_after = boot_session()
    after = time.monotonic_ns()
    require(boot_after == boot and after >= before, "Clock continuity changed during observation")
    sample = {"schema": 1, "clock": CLOCK, "bootSession": boot, "monotonicNs": before,
              "wallNs": wall, "sampleSpanNs": after - before}
    validate_sample(sample)
    return sample


def validate_progress(anchor: dict, current: dict) -> None:
    """Same-boot awake time must still agree with the original wall allowance.

    Mach time excludes sleep. Keep the original anchor rather than replacing it
    at each observation; otherwise small clock drifts could renew the job lease.
    Both boot reads and the wall observation lie inside the at-most-50ms bracket.
    Account for that entire uncertainty inside, not beyond, the existing 1s margin.
    Caller deadlines must remain the earlier original cutoffs, not this tolerance.
    """
    validate_sample(anchor)
    validate_sample(current)
    require(current["bootSession"] == anchor["bootSession"], "Boot session changed")
    mono = current["monotonicNs"] - anchor["monotonicNs"]
    wall = current["wallNs"] - anchor["wallNs"]
    difference = wall - mono
    require(mono >= 0 and wall >= 0 and
            difference + anchor["sampleSpanNs"] <= MAX_DIVERGENCE_NS and
            difference - current["sampleSpanNs"] >= -MAX_DIVERGENCE_NS,
            "Original wall and awake clock allowance diverged")


def floor_seconds_ns(value: int | float) -> int:
    """Convert an admitted absolute cutoff without rounding it later in C/JSON."""
    require(type(value) in (int, float), "Numeric cutoff required")
    if type(value) is float:
        require(math.isfinite(value), "Finite cutoff required")
        numerator, denominator = value.as_integer_ratio()
    else:
        numerator, denominator = value, 1
    result = numerator * BILLION // denominator
    require(0 <= result <= MAX_NS, "Cutoff is outside the shared signed-nanosecond domain")
    return result
