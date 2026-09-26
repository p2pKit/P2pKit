"""Data-only original-prelude and chronology checks, never live admission.

These checks separate historical original75/120 facts from the caller's current
read/clock operations. They do not check the complete surrounding record grammar
or attest original bytes, native return, current ownership or workflow outcome.
The existing wrappers retain those checks and their actual observations. There
is no new reader, owner, clock, job budget, callback or execution authority here.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import hosted_cache_bootstrap_origin as origin


@dataclass(frozen=True)
class HistoricalPrelude:
    """Canonical supplied historical data, not a live fence or provenance token."""
    raw: bytes = field(repr=False)
    clock: object = field(init=False, repr=False)
    first: int = field(init=False, repr=False)
    work: int = field(init=False, repr=False)
    final: int = field(init=False, repr=False)

    def __post_init__(self):
        origin.require(type(self.raw) is bytes, "BOOTSTRAP_HISTORY_PRELUDE_BYTES")
        value = origin.parse(self.raw)
        clock = origin.validate_prelude(value)
        origin.require(self.raw == origin.encoded(value), "BOOTSTRAP_HISTORY_PRELUDE_BYTES")
        for name, item in (("clock", clock), ("first", value["firstNs"]),
                           ("work", value["workEndNs"]), ("final", value["finalEndNs"])):
            object.__setattr__(self, name, item)


def checked(frame):
    """Recheck only supplied immutable data; copies never gain live authority."""
    origin.require(type(frame) is HistoricalPrelude, "BOOTSTRAP_HISTORY_FRAME")
    expected = HistoricalPrelude(frame.raw)
    origin.require(origin.clock_value(frame.clock) == origin.clock_value(expected.clock) and
                   all(type(getattr(frame, name)) is int and getattr(frame, name) == getattr(expected, name)
                       for name in ("first", "work", "final")), "BOOTSTRAP_HISTORY_FRAME_CHANGED")
    return frame


def snapshot(fence):
    """Read an existing prelude's fields, without observing/advancing its clock.

    This does not transfer any owner, cancellation callback, high-water or local
    deadline. It cannot replace the caller's subsequent live fence checks.
    """
    origin.require(type(fence) is origin.Fence, "BOOTSTRAP_HISTORY_NOT_ORIGINAL_PRELUDE")
    frame = HistoricalPrelude(fence.raw)
    origin.require(origin.clock_value(fence.clock) == origin.clock_value(frame.clock) and
                   all(type(getattr(fence, name)) is int and getattr(fence, name) == getattr(frame, name)
                       for name in ("first", "work", "final")), "BOOTSTRAP_HISTORY_FENCE_CHANGED")
    return frame


def context_return(frame, returned_ns):
    frame = checked(frame)
    # Context alone historically checks only this lower bound. Admission's
    # separate upper-bound check must not be omitted or inferred from it.
    return origin.integer(returned_ns, frame.first)


def admission_return(frame, returned_ns):
    frame = checked(frame)
    origin.require(frame.first <= origin.integer(returned_ns) < frame.work,
                   "BOOTSTRAP_ORIGINAL_ADMISSION_RETURN")
    return True


def phase_start(frame, admission_returned_ns, start):
    frame = checked(frame)
    context_return(frame, admission_returned_ns)
    began = origin.integer(start["startedNs"], admission_returned_ns)
    origin.require(began < frame.work and type(start["workEndNs"]) is int and type(start["finalEndNs"]) is int and
                   start["workEndNs"] == min(frame.work, began + 45 * origin.NS) and
                   start["finalEndNs"] == min(frame.final, start["workEndNs"] + 45 * origin.NS),
                   "BOOTSTRAP_ORIGINAL_PHASE_FENCES")
    return began


def chain_minimum(frame, admission_returned_ns, start, native, birth, child, service, ack):
    """Historical minimum only, NOT the reader's actual revalidatedNs.

    Surrounding record/source/native/argv/byte checks remain in the caller. The
    caller must still take and retain its actual live observation after these
    historical checks; a later good observation cannot repair bad history.
    """
    frame = checked(frame)
    times = [frame.first, admission_returned_ns, start["startedNs"], native["launchMinimumNs"],
             child["beganNs"], child["metadataLastNs"], service["firstNs"], service["lastNs"],
             child["acquiredNs"], child["completedNs"], ack["closedNs"], native["completedNs"], native["finalizedNs"]]
    origin.require(all(type(value) is int and 0 <= value <= origin.clocks.UINT64 for value in times) and
                   times == sorted(times) and
                   type(start["workEndNs"]) is int and type(start["finalEndNs"]) is int and
                   start["workEndNs"] == min(frame.work, start["startedNs"] + 45 * origin.NS) and
                   start["finalEndNs"] == min(frame.final, start["workEndNs"] + 45 * origin.NS) and
                   native["completedNs"] < start["workEndNs"] and native["finalizedNs"] < start["finalEndNs"] and
                   native["launchMinimumNs"] <= origin.integer(birth["observedNs"]) <= native["completedNs"],
                   "BOOTSTRAP_ORIGINAL_CLOCK_CHAIN")
    return max(*times, birth["observedNs"])


def adopter_first(frame, native_final_ns, admission_returned_ns, revalidated_ns,
                  retained_ns, closed_ns, recorded_ns, adopter_first_ns):
    """Original read-only adopter chronology, not a future reader's first time."""
    frame = checked(frame)
    times = (native_final_ns, admission_returned_ns, revalidated_ns, closed_ns, recorded_ns, adopter_first_ns)
    origin.require(all(type(value) is int and 0 <= value <= origin.clocks.UINT64 for value in times) and
                   frame.first <= native_final_ns <= admission_returned_ns <= revalidated_ns <=
                   origin.integer(retained_ns) <= closed_ns <= recorded_ns <= adopter_first_ns < frame.work,
                   "BOOTSTRAP_ADOPTION_PREDECESSOR_CLOCK")
    return adopter_first_ns
