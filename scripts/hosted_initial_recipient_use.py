"""Closed Stage1 per-use contracts and original bounded clock, not admission.

Only the fixed productive/provider drivers install these windows. A supplied
binding, frame, site or clock is not an original parent or an execution grant.
Native file/process ownership stays in the one custody/native module graph.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
import time

import hosted_cache_bootstrap_origin as O
import hosted_initial_recipient_continuity as continuity
import hosted_initial_recipient_public_origin as public


PRIVATE_CONTEXT = "INITIAL_RECIPIENT_PRODUCTIVE_USE_CONTEXT_V1"
PUBLIC_CONTEXT = "INITIAL_RECIPIENT_PROVIDER_PUBLIC_USE_CONTEXT_V1"
PRIVATE_ACK = "INITIAL_RECIPIENT_PRODUCTIVE_USE_POST_CLOSE_ACK_V1"
PUBLIC_ACK = "INITIAL_RECIPIENT_PROVIDER_PUBLIC_USE_POST_CLOSE_ACK_V1"
PRIVATE_CHILD = "INITIAL_RECIPIENT_PRODUCTIVE_USE_PENDING_CHILD_CLOSE_V1"
PUBLIC_CHILD = "INITIAL_RECIPIENT_PROVIDER_PUBLIC_USE_PENDING_CHILD_CLOSE_V1"
WINDOW_SCOPE = "INITIAL_RECIPIENT_ORIGINAL_PER_USE_WINDOW_V1"
RETURN_SCOPE = "INITIAL_RECIPIENT_ORIGINAL_PER_USE_CLOSED_RETURN_V1"
PRODUCTIVE_SITES = (
    "dependency-stage/readmission", "empty-seed/readmission", "custody-prepare/readmission",
    "configuration/prelaunch", "custody-collect/readmission", "custody-uninstall/observation",
    "dependency-export/copy", "save-set-before/observation", "producer-handoff/retention",
)
STEP_SITES = tuple(command + "/" + edge for command in
    ("prepare-save", "after-save", "prepare-probe", "after-probe") for edge in ("begin", "final"))
PRIVATE_SITES = PRODUCTIVE_SITES + STEP_SITES
SITES = PRIVATE_SITES + public.SITES
SEED_NAMES = ("site", "parentFirstNs", "parentWorkEndNs", "firstNs", "workEndNs", "nativeFinalEndNs",
              "originalBootDigest")
PHASE_NAMES = ("startedNs", "workEndNs", "finalEndNs")
_WINDOWS = {}


def require(value, code):
    O.require(value, "INITIAL_USE_" + code)


def local_value(value):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0, "LOCAL_CLOCK")
    return float(value)


def site_scope(site):
    require(type(site) is str and site in SITES, "FIXED_SITE")
    return PUBLIC_CONTEXT if site in public.SITES else PRIVATE_CONTEXT


def site_leaf(site):
    site_scope(site)
    return "use-" + str(SITES.index(site) + 1).zfill(2) + "-" + site.replace("/", "-")


def seed(site, parent_first, parent_work, first, boot):
    """Supplied arithmetic only. The driver separately pins the actual parent."""
    site_scope(site)
    parent_first, parent_work, first = (O.integer(value) for value in (parent_first, parent_work, first))
    require(parent_first <= first < parent_work and type(boot) is str and re.fullmatch(r"[0-9a-f]{64}", boot),
        "ORIGINAL_PARENT_CAP")
    return {"site": site, "parentFirstNs": parent_first, "parentWorkEndNs": parent_work, "firstNs": first,
        "workEndNs": min(parent_work, O.integer(first + 75 * O.NS)),
        "nativeFinalEndNs": min(parent_work, O.integer(first + 120 * O.NS)), "originalBootDigest": boot}


def checked_seed(value):
    require(type(value) is dict and set(value) == set(SEED_NAMES), "SEED_FIELDS")
    expected = seed(value["site"], value["parentFirstNs"], value["parentWorkEndNs"], value["firstNs"],
        value["originalBootDigest"])
    require(O.encoded(value) == O.encoded(expected), "SEED_ARITHMETIC")
    return value


def phase_caps(value, caps):
    checked_seed(value)
    require(type(caps) is tuple and len(caps) == 3 and all(type(value) is int for value in caps), "PHASE_CAPS")
    began, work, final = (O.integer(value) for value in caps)
    require(value["firstNs"] <= began < work and work == min(value["workEndNs"], began + 45 * O.NS) and
        final == min(value["nativeFinalEndNs"], work + 45 * O.NS), "ORIGINAL_PHASE_CAPS")
    return caps


def frame(value, clock):
    checked_seed(value)
    O.clocks.validate_identity(clock)
    return {"schema": 1, "scope": WINDOW_SCOPE, "clock": O.clock_value(clock), **value}


def checked_frame(value):
    require(type(value) is dict and set(value) == {"schema", "scope", "clock", *SEED_NAMES} and
        type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == WINDOW_SCOPE, "WINDOW_FIELDS")
    clock = O.wire.clock_identity(value["clock"])
    original = checked_seed({name: value[name] for name in SEED_NAMES})
    require(O.encoded(value) == O.encoded(frame(original, clock)), "WINDOW_ENCODING")
    return clock, original


@dataclass(frozen=True, repr=False)
class ParentBinding:
    """The fixed adapter's registered original view; construction is not proof.

    checked_use_parent must return this SAME instance from its original parent
    registry and check its real phase, predecessors, source, cancellation and
    owner state. There is no callable field or caller-selected phase duration.
    """
    parent: object
    site: str
    first: object
    local_first: float
    work_end_ns: int
    local_work_end: float
    original_boot: str
    prefix: object
    identity: object
    history: bytes
    proposal: bytes
    source_records: tuple
    initializer: object
    initializer_identity: tuple


@dataclass(eq=False, repr=False)
class _Anchor:
    handle: object
    bound: tuple
    first_dictionary: dict
    clock_dictionary: dict
    first_values: tuple
    last: int
    local_last: float
    busy: bool = False
    failure: object = None


class UseWindow:
    """One real first RAW/LOCAL, original parent cap and irreversible failure.

    The private and public drivers supply their fixed original-parent check;
    this class never decides whether a parent exists or grants source authority.
    Child creation uses the actual inherited seed/caps before its first file
    read, so even refused metadata cannot start a replacement local45 interval.
    """
    __slots__ = ("_bound",)

    def __init__(self, first, local, boot, value, current, *, side, parent_local_end=None, caps=None):
        require(type(self) is UseWindow and id(self) not in _WINDOWS, "WINDOW_NOT_NEW")
        O.clocks.validate_reading(first)
        local = local_value(local)
        checked_seed(value)
        require(type(side) is str and side in ("parent", "child") and callable(current) and
            boot == value["originalBootDigest"], "WINDOW_BINDING")
        if side == "parent":
            require(caps is None and first.nanoseconds == value["firstNs"], "PARENT_FIRST")
            ceiling = local_value(parent_local_end)
            work, final = value["workEndNs"], value["nativeFinalEndNs"]
        else:
            phase_caps(value, caps)
            require(parent_local_end is None and caps[0] <= first.nanoseconds < caps[1], "CHILD_FIRST")
            # Success, its output and all child owner close remain in native
            # WORK. The parent's final45 is for observing/draining this child,
            # not an extra grant for a late HTTP/acquisition return.
            work = final = min(caps[1], O.integer(first.nanoseconds + 45 * O.NS))
            ceiling = O.wire._directed_deadline(local, 45, work, first.nanoseconds)
        require(first.nanoseconds < work <= final <= value["parentWorkEndNs"], "WINDOW_END")
        locals_ = tuple(min(ceiling, O.wire._directed_deadline(local, 120, end, first.nanoseconds))
            for end in (work, final))
        require(local < min(locals_), "WINDOW_LOCAL_END")
        raw = O.encoded(frame(value, first.clock))
        self._bound = (first, local, boot, raw, work, final, locals_, current, side, caps)
        _WINDOWS[id(self)] = _Anchor(self, self._bound, first.__dict__, first.clock.__dict__,
            (first.clock, first.nanoseconds, first.clock.role, first.clock.domain, first.clock.ticks_per_second),
            first.nanoseconds, local)

    def _anchor(self):
        anchor = _WINDOWS.get(id(self))
        require(type(self) is UseWindow and type(anchor) is _Anchor and anchor.handle is self, "WINDOW_ORIGINAL")
        return anchor

    def _view(self):
        anchor = self._anchor()
        try:
            require(self._bound is anchor.bound and _WINDOWS.get(id(self)) is anchor, "WINDOW_BINDING_CHANGED")
            first = anchor.bound[0]
            require(first.__dict__ is anchor.first_dictionary and first.clock.__dict__ is anchor.clock_dictionary and
                set(first.__dict__) == {"clock", "nanoseconds"} and set(first.clock.__dict__) ==
                {"role", "domain", "ticks_per_second"} and
                (first.clock, first.nanoseconds, first.clock.role, first.clock.domain, first.clock.ticks_per_second) ==
                anchor.first_values and first.clock is anchor.first_values[0], "WINDOW_FIRST_CHANGED")
            O.clocks.validate_reading(first)
            return anchor
        except BaseException as error:
            raise self.fail(error)

    def fail(self, error):
        anchor = self._anchor()
        if anchor.failure is None:
            anchor.failure = error
        return anchor.failure

    clock = property(lambda self: self._view().bound[0].clock)
    first = property(lambda self: self._view().bound[0].nanoseconds)
    work = property(lambda self: self._view().bound[4])
    final = property(lambda self: self._view().bound[5])
    local_end = property(lambda self: self._view().bound[6][1])
    last = property(lambda self: self._view().last)
    local_last = property(lambda self: self._view().local_last)
    raw = property(lambda self: self._view().bound[3])
    side = property(lambda self: self._view().bound[8])

    def _begin(self):
        anchor = self._view()
        if anchor.failure is not None:
            raise anchor.failure
        try:
            require(not anchor.busy, "WINDOW_REENTRY")
            anchor.busy = True
            return anchor
        except BaseException as error:
            raise self.fail(error)

    def _observe(self, anchor, final, minimum, limit):
        require(type(final) is bool, "WINDOW_MODE")
        bound = anchor.bound
        end, local_end = bound[5 if final else 4], bound[6][int(final)]
        if limit is not None:
            end = min(end, O.integer(limit))
        latest = max(anchor.last, O.integer(minimum))
        for index in range(2):
            self._view()
            local = local_value(time.monotonic())
            require(anchor.local_last <= local < local_end, "WINDOW_LOCAL_EXPIRED_OR_BACKWARDS")
            anchor.local_last = local
            bound[7]()
            self._view()
            observed = O.clocks.checked_now(bound[0].clock, minimum_ns=latest)
            anchor.last = latest = O.integer(observed, latest)
            self._view()
            require(latest < end and anchor.failure is None and anchor.busy, "WINDOW_RAW_EXPIRED_OR_CHANGED")
            boot = continuity.boot_digest(bound[0].clock.role)
            self._view()
            require(boot == bound[2], "WINDOW_BOOT_CHANGED")
            if index == 0:
                bound[7]()
                self._view()
                require(anchor.last == latest and anchor.local_last == local and
                    anchor.failure is None and anchor.busy, "WINDOW_CALLBACK_CHANGED")
        local = local_value(time.monotonic())
        require(anchor.local_last <= local < local_end, "WINDOW_FINAL_LOCAL")
        anchor.local_last = local
        self._view()
        require(anchor.failure is None and anchor.busy and anchor.last == latest, "WINDOW_FRONTIER_CHANGED")
        return latest

    def now(self, *, final=False, minimum=0, limit=None):
        anchor = self._begin()
        try:
            return self._observe(anchor, final, minimum, limit)
        except BaseException as error:
            raise self.fail(error)
        finally:
            anchor.busy = False

    def deadline(self, maximum, *, final=False, limit=None):
        anchor = self._begin()
        try:
            require(type(maximum) in (int, float) and math.isfinite(maximum) and 0 < maximum <= 900,
                "WINDOW_OPERATION_MAXIMUM")
            local = local_value(time.monotonic())
            require(local >= anchor.local_last, "WINDOW_LOCAL_BACKWARDS")
            anchor.local_last = local
            observed = self._observe(anchor, final, 0, limit)
            end = anchor.bound[5 if final else 4]
            if limit is not None:
                end = min(end, O.integer(limit))
            return min(anchor.bound[6][int(final)], O.wire._directed_deadline(local, maximum, end, observed))
        except BaseException as error:
            raise self.fail(error)
        finally:
            anchor.busy = False
