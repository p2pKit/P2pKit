"""Original productive-final parent/child/collect ownership, never DATA admission.

This controller uses the one canonical P graph in each real process. Native
transport carries bounded historical records, never a recreated live registry.
All new operations remain fixed and original-Step success remains external.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import base64
import hashlib
import math
import os
from pathlib import Path
import re
import stat
import time
import uuid

import hosted_initial_recipient_productive as P
import hosted_initial_recipient_productive_custody_data as CD
import hosted_initial_recipient_productive_adapter as A
import hosted_cache_compatibility as compatibility


C, N, B, O = P.C, P.N, P.B, P.O
D, Q, ROOT, NS = A.D, P.Q, P.ROOT, P.O.NS
_PINS, _STATES, _CLOCKS, _CHILDREN, _VIEWS, _CAPS = {}, {}, {}, {}, {}, {}
_ATTEMPTS, _RESULTS, _OUTPUTS, _NATIVE_SEEDS = {}, {}, {}, {}
_FAILURES, _SPANS, _OWNER_CLOSES, _PROVENANCE, _PIN_FAILURES = {}, {}, {}, {}, {}
_QUARANTINE = []


def require(value, reason):
    O.require(value, "INITIAL_PRODUCTIVE_CUSTODY_" + reason)


def _track(value):
    require(id(value) not in _PINS and type(value.__dict__) is dict, "REGISTER_ONCE")
    _PINS[id(value)] = value, type(value), value.__dict__, tuple(value.__dict__.items())
    return value


def _pin(value):
    saved = _PINS.get(id(value))
    failed = _PIN_FAILURES.get(id(value))
    if failed is not None:
        require(failed[0] is value, "PIN_FAILURE_ALIAS")
        raise failed[1]
    try:
        require(type(saved) is tuple and saved[0] is value and type(value) is saved[1] and
            value.__dict__ is saved[2] and tuple(value.__dict__) == tuple(name for name, _ in saved[3]) and
            all(value.__dict__[name] is original for name, original in saved[3]), "ORIGINAL_OBJECT_CHANGED")
        return value
    except BaseException as error:
        if type(saved) is tuple and saved[0] is value:
            _PIN_FAILURES[id(value)] = value, error
        raise


def _update(value, **changes):
    _pin(value)
    require(set(changes).issubset(value.__dict__), "UPDATE_FIELDS")
    for name, item in changes.items():
        object.__setattr__(value, name, item)
    _PINS[id(value)] = value, type(value), value.__dict__, tuple(value.__dict__.items())


def _methods(value, names):
    pins = []
    for name in names:
        method = getattr(value, name)
        descriptor = next((base.__dict__[name] for base in type(value).__mro__ if name in base.__dict__), None)
        dictionary = getattr(value, "__dict__", None)
        slot = None if dictionary is None else dictionary.get(name)
        function = getattr(method, "__func__", None)
        bound = getattr(method, "__self__", None)
        # A builtin bound method is freshly allocated at each attribute read;
        # retain its descriptor/self/name and original instance slot instead.
        pins.append((name, type(value), descriptor, dictionary, slot, function, bound,
            getattr(method, "__name__", None), method if function is None and bound is None else None))
    return tuple(pins)


def _methods_current(value, pins):
    for name, kind, descriptor, dictionary, slot, function, bound, method_name, ordinary in pins:
        current = getattr(value, name)
        require(type(value) is kind and
            next((base.__dict__[name] for base in type(value).__mro__ if name in base.__dict__), None) is descriptor and
            getattr(value, "__dict__", None) is dictionary and
            (dictionary is None or dictionary.get(name) is slot) and
            getattr(current, "__func__", None) is function and getattr(current, "__self__", None) is bound and
            (bound is None or bound is value) and getattr(current, "__name__", None) == method_name and
            (ordinary is None or current is ordinary), "ORIGINAL_METHOD_CHANGED")


@dataclass(frozen=True, repr=False)
class ParentFinal:
    """No constructor authority; only this call's private registry admits it."""


@dataclass(frozen=True, repr=False)
class ChildFinal:
    """Child-local currency; never sent to or reconstructed by the parent."""


@dataclass(frozen=True, repr=False)
class ChildArchiveBinding30:
    """Only the actual child read30/index close may register this empty handle."""


@dataclass(frozen=True, repr=False)
class CollectPrepared:
    """Fresh later process, not a restored ParentFinal/ChildFinal."""


@dataclass(frozen=True, repr=False)
class ParentReturnedCrypto:
    output_values: tuple
    fence: object
    hard_end_ns: int


@dataclass(frozen=True, repr=False)
class CollectReturn:
    output_values: tuple
    fence: object
    hard_end_ns: int


@dataclass(frozen=True, repr=False)
class ChildSourceBinding:
    job_id: str
    observed_raw: bytes
    event_sha256: str
    context_sha256: str
    start_sha256: str


@dataclass(frozen=True, repr=False)
class ValidationCaps:
    clock: object
    first: object
    firstLocal: float
    workEndNs: int
    workEndLocal: float
    operationFinishEndNs: int
    operationFinishEndLocal: float
    finishReserveNs: int
    operationLimitNs: int


@dataclass(frozen=True, repr=False)
class ArchiveCaps:
    clock: object
    first: object
    firstLocal: float
    workEndNs: int
    workEndLocal: float
    operationFinishEndNs: int
    operationFinishEndLocal: float
    finishReserveNs: int
    operationLimitNs: int


@dataclass(frozen=True, repr=False)
class ValidationView:
    child: object
    role: str
    work: object
    public_key_raw: bytes
    policy_raw: bytes
    original_match_raw: bytes
    source: object
    caps: object


@dataclass(frozen=True, repr=False)
class ArchiveView:
    child: object
    archive: object
    recipient: object
    role: str
    payload: object
    output: object
    payload_root: object
    partitions: tuple
    index: object
    lineage: object
    caps: object
    public_inputs: bytes


@dataclass(frozen=True, repr=False)
class PartitionView:
    ordinal: int
    group: str
    root: object
    members: tuple
    map: object


@dataclass(frozen=True, repr=False)
class ExpectedNode:
    relative: str
    kind: str
    bytes: object
    sha256: object
    native: tuple
    provenance: object


@dataclass(eq=False, repr=False)
class _ClockState:
    first: object
    local: float
    boot: str
    cancelled: object
    names: tuple
    ends: tuple
    locals: tuple
    fence: object
    graph: tuple
    phase: int = 0
    last: int = 0
    last_local: float = 0.0
    reading: object = None
    started: tuple = ()
    issued: float = 0.0
    busy: bool = False
    failure: object = None
    proposal: object = None
    attempt: object = None
    reading_graph: tuple = ()


@dataclass(eq=False, repr=False)
class _State:
    handle: object
    operation: str
    clock: object
    claims_raw: bytes
    actual_raw: bytes
    first_graph: tuple
    failure: object = None
    busy: bool = False
    owner: object = None
    owners: tuple = ()
    handoff: object = None
    inputs: object = None
    authority: object = None
    partitions: tuple = ()
    context_raw: object = None
    start_raw: object = None
    native_return: object = None
    outputs: tuple = ()
    result: object = None
    closed: object = None
    auxiliary: tuple = ()
    phase_caps: tuple = ()
    source: object = None
    validation: object = None
    validation_return: object = None
    validation_completed: object = None
    archive: object = None
    archive_view: object = None
    backend_return: object = None
    export_completed: object = None
    root: object = None
    payload: object = None
    work: object = None
    output: object = None
    index: object = None
    lineage: object = None
    public_inputs: object = None
    reader_seed: object = None
    authority_seed: object = None
    crypto_seed: object = None
    specs: tuple = ()
    transport: object = None
    observations: tuple = ()
    union: tuple = ()
    readback: tuple = ()
    copied: tuple = ()
    paths: tuple = ()
    claims: tuple = ()
    metadata_close: object = None
    metadata_last: object = None
    outer_roots: tuple = ()
    final_records: tuple = ()
    manifest_raw: object = None
    artifact: object = None
    accounting: tuple = ()
    total_bytes: int = 0
    total_nodes: int = 0
    crypto_facts: object = None
    ciphertext: tuple = ()
    host_path: object = None
    host_event_raw: object = None
    host_observed_raw: object = None
    abort_started: bool = False
    stage: str = "created"


@dataclass(eq=False, repr=False)
class _Attempt:
    operation: str
    functions: tuple
    registries: tuple
    fence: object = None
    handle: object = None
    failure: object = None


def _attempt_functions():
    return (time.monotonic, O.clocks.observe, O.clocks.validate_reading, O.clocks.validate_identity,
        C.C.boot_digest, N._history_graph, N._check_history, N.acquisition._context,
        C._PrimaryOwner, C._PrimaryOwner.structural, C._PrimaryOwner.guard, C._PrimaryOwner.acquire,
        C._PrimaryOwner.close_one, C._PrimaryOwner.finish, C._private, C._snapshot, C._snapshot_reader,
        C._consume, C._recipient_inventory, C.productive_crypto_native, A.F.public_root,
        B.Owner, B.Owner.end, B.Owner.close_one, B.Owner.close, _FinalOutputFence.now, _ChildAckFence.now,
        _Fence.now, _SpanFence.now, _FinalOutputFence, _ChildAckFence, _observe, _advance, _pin,
        _checked_native_crypto, _crypto_phase_data, _final_return_passive, _check_union, B.posix._ciphertext_stream,
        _attempt_functions, _attempt_current, _registry_roots, _methods, _methods_current, Q._file_info,
        _shorten_clock, _shorten_clock_once, _advance_once, _ack_passive)


def _registry_roots():
    return (_PINS, _STATES, _CLOCKS, _CHILDREN, _VIEWS, _CAPS, _ATTEMPTS, _RESULTS, _OUTPUTS, _NATIVE_SEEDS,
        _FAILURES, _SPANS, _OWNER_CLOSES, _PROVENANCE, _PIN_FAILURES, _AUTHORITIES, _ACKS, _COPIES, _GROUPS,
        _BUDGETS, _READ_PARTITIONS, _FILE_READS, _LINEAGES, _VALIDATION_INVENTORIES, _SOURCES, _CRYPTO_FACTS,
        _CIPHER_STREAMS, _CIPHERTEXT_READS, _COLLECT_HISTORIES, C._PRODUCTIVE_NATIVE_OWNERS, C._PRIMARY_OWNERS,
        C._CRYPTO_NATIVE_RETURNS, A._FINAL_INPUTS, A._FINAL_PEEKS, A._FINAL_FAILURES)


def _attempt_current(attempt):
    _pin(attempt)
    failure = _FAILURES.get(id(attempt))
    if failure is not None:
        raise failure[1]
    current, registries = _attempt_functions(), _registry_roots()
    require(_ATTEMPTS.get(attempt.operation) is attempt and attempt.failure is None and
        len(current) == len(attempt.functions) and len(registries) == len(attempt.registries) and
        all(current is original for current, original in zip(current, attempt.functions)) and
        all(current is original for current, original in zip(registries, attempt.registries)),
        "ORIGINAL_ATTEMPT_SUPPLIERS")


def _fail(state, error):
    original = _PINS.get(id(state))
    require(type(original) is tuple and original[0] is state, "FAILURE_ORIGINAL_STATE")
    previous = _FAILURES.get(id(state))
    if previous is None:
        previous = state, error
        _FAILURES[id(state)] = previous
        _owned_slot(state, "failure", error)
    require(previous[0] is state, "FAILURE_STATE_ALIAS")
    return previous[1]


def _owned_slot(state, name, value):
    """Never adopt/repair a substituted dictionary while recording failure."""
    saved = _PINS[id(state)]
    require(any(key == name for key, _value in saved[3]), "OWNED_SLOT")
    saved[2][name] = value
    _PINS[id(state)] = state, saved[1], saved[2], tuple(
        (key, value if key == name else item) for key, item in saved[3])


def _state(handle):
    value = _STATES.get(id(handle))
    require(type(value) is _State and value.handle is handle, "ORIGINAL_STATE")
    failed = _FAILURES.get(id(value))
    if failed is not None:
        raise failed[1]
    try:
        _pin(handle)
        _pin(value)
        if value.failure is not None:
            raise value.failure
        N._check_history(value.first_graph)
        return value
    except BaseException as error:
        raise _fail(value, error)


def _clock(fence):
    state = _CLOCKS.get(id(fence))
    require(type(fence) is _Fence and type(state) is _ClockState and state.fence is fence, "ORIGINAL_CLOCK")
    failed = _FAILURES.get(id(state))
    if failed is not None:
        raise failed[1]
    try:
        _pin(state)
        if state.failure is not None:
            raise state.failure
        if state.attempt is not None:
            _attempt_current(state.attempt)
        N._check_history(state.graph)
        N._check_history(state.reading_graph)
        return state
    except BaseException as error:
        raise _fail(state, error)


class _Fence:
    __slots__ = ()

    @property
    def clock(self):
        return _clock(self).first.clock

    @property
    def last(self):
        return _clock(self).last

    @property
    def work(self):
        state = _clock(self)
        return state.ends[state.phase]

    @property
    def final(self):
        return self.work

    def now(self, *, final=False, minimum=0, limit=None):
        state = _clock(self)
        return _observe(state, state.ends[state.phase], state.locals[state.phase], final, minimum, limit)

    def deadline(self, seconds, *, final=False, minimum=0, limit=None):
        self.now(final=final, minimum=minimum, limit=limit)
        state = _clock(self)
        return _local_deadline(state, seconds, state.ends[state.phase], state.locals[state.phase], limit)


def _observe(state, end, local_end, final, minimum, limit):
    """LOCAL-before-RAW at both checks, over the SAME original high waters."""
    try:
        require(type(final) is bool and not state.busy, "CLOCK_REENTRY")
        _update(state, busy=True)
        floor = max(state.last, CD.integer(minimum))
        if limit is not None:
            end = min(end, CD.integer(limit))
        local_end = min(local_end, O.wire._directed_deadline(state.local, 900, end, state.first.nanoseconds))
        for index in range(2):
            before = CD.local(time.monotonic())
            if state.attempt is not None:
                _attempt_current(state.attempt)
            _pin(state)
            require(state.last_local <= before < local_end, "LOCAL_BACKWARDS_OR_EXPIRED")
            _update(state, last_local=before)
            reading = O.clocks.validate_reading(O.clocks.observe())
            if state.attempt is not None:
                _attempt_current(state.attempt)
            _pin(state)
            require(reading.clock == state.first.clock and floor <= reading.nanoseconds < end,
                "CLOCK_CHANGED_BACKWARDS_OR_EXPIRED")
            _update(state, last=reading.nanoseconds, reading=reading, reading_graph=N._history_graph(reading))
            floor = reading.nanoseconds
            if index == 0:
                require(C.C.boot_digest(reading.clock.role) == state.boot, "BOOT_CHANGED")
                _pin(state)
                state.cancelled()
                if state.attempt is not None:
                    _attempt_current(state.attempt)
                _pin(state)
                require(state.failure is None and state.busy and id(state) not in _FAILURES,
                    "CLOCK_CALLBACK_FAILED")
                N._check_history(state.reading_graph)
        after = CD.local(time.monotonic())
        require(state.last_local <= after < local_end, "FINAL_LOCAL_EXPIRED")
        _update(state, last_local=after)
        return state.last
    except BaseException as error:
        raise _fail(state, error)
    finally:
        _owned_slot(state, "busy", False)


def _local_deadline(state, seconds, end, local_end, limit):
    require(type(seconds) in (int, float) and not isinstance(seconds, bool) and
        math.isfinite(seconds) and 0 < seconds <= 900, "LOCAL_DEADLINE_SECONDS")
    if limit is not None:
        end = min(end, CD.integer(limit))
    value = min(local_end, O.wire._directed_deadline(state.last_local, seconds, end, state.last))
    require(state.last_local < value, "NO_LOCAL_INTERVAL")
    return value


@dataclass(frozen=True, repr=False)
class _Span:
    clock: object
    work: int
    final: int
    work_local: float
    final_local: float
    purpose: str
    work_phase: int
    final_phase: int


class _SpanFence:
    """Native spans use the original basis, never a second encrypt210/close45."""
    __slots__ = ()

    def _binding(self):
        span = _SPANS.get(id(self))
        require(type(span) is _Span, "ORIGINAL_SPAN")
        _pin(span)
        return span, _clock(span.clock)

    clock = property(lambda self: self._binding()[1].first.clock)
    last = property(lambda self: self._binding()[1].last)
    work = property(lambda self: min(self._binding()[0].work,
        self._binding()[1].ends[self._binding()[0].work_phase]))
    final = property(lambda self: min(self._binding()[0].final,
        self._binding()[1].ends[self._binding()[0].final_phase]))

    def now(self, *, final=False, minimum=0, limit=None):
        span, state = self._binding()
        phase = span.final_phase if final else span.work_phase
        return _observe(state, min(span.final if final else span.work, state.ends[phase]),
            min(span.final_local if final else span.work_local, state.locals[phase]), final, minimum, limit)

    def deadline(self, seconds, *, final=False, minimum=0, limit=None):
        self.now(final=final, minimum=minimum, limit=limit)
        span, state = self._binding()
        phase = span.final_phase if final else span.work_phase
        return _local_deadline(state, seconds, min(span.final if final else span.work, state.ends[phase]),
            min(span.final_local if final else span.work_local, state.locals[phase]), limit)


def _span(fence, work, final, purpose):
    state = _clock(fence)
    require(state.last < CD.integer(work) <= CD.integer(final) <= state.ends[-1] and
        purpose in ("reader", "authority-pre", "authority-post", "crypto-native", "authority-child", "child-outer", "metadata"),
        "SPAN_LIMITS")
    work_phase = 1 if purpose in ("crypto-native", "child-outer") else state.phase
    final_phase = 2 if purpose == "crypto-native" else work_phase
    local_work = min(state.locals[work_phase], O.wire._directed_deadline(state.local, 900, work, state.first.nanoseconds))
    local_final = min(state.locals[final_phase], O.wire._directed_deadline(state.local, 900, final, state.first.nanoseconds))
    result = _SpanFence()
    _SPANS[id(result)] = _track(_Span(fence, work, final, local_work, local_final, purpose, work_phase, final_phase))
    result.now()
    return result


def _new_clock(cancelled, names, *, caps=None, declared_clock=None, boot=None, minimum=0, attempt=None):
    local = CD.local(time.monotonic())
    first = O.clocks.validate_reading(O.clocks.observe())
    if attempt is not None:
        _attempt_current(attempt)
    require(first.nanoseconds >= CD.integer(minimum) and callable(cancelled), "ORIGINAL_FIRST")
    actual_boot = CD.sha(C.C.boot_digest(first.clock.role))
    if attempt is not None:
        _attempt_current(attempt)
    require((declared_clock is None or declared_clock == first.clock) and (boot is None or actual_boot == boot),
        "ORIGINAL_CLOCK_BOOT")
    cumulative, ends, locals_ = 0, [], []
    for index, (_name, seconds) in enumerate(names):
        cumulative += seconds
        end = CD.integer(first.nanoseconds + cumulative * NS)
        if caps is not None:
            end = min(end, CD.integer(caps[index]))
        ends.append(end)
        locals_.append(O.wire._directed_deadline(local, cumulative, end, first.nanoseconds))
    require(ends and first.nanoseconds < ends[0] and ends == sorted(ends), "ORIGINAL_PHASE_FENCES")
    fence = _Fence()
    state = _track(_ClockState(first, local, actual_boot, cancelled, names, tuple(ends), tuple(locals_), fence,
        N._history_graph(first), last=first.nanoseconds, last_local=local, reading=first,
        started=((first.nanoseconds, local),), issued=locals_[0], attempt=attempt, reading_graph=N._history_graph(first)))
    _CLOCKS[id(fence)] = state
    if attempt is not None:
        _update(attempt, fence=fence)
    fence.now()
    return fence


def _shorten_clock(fence, proposal):
    state = _clock(fence)
    try:
        return _shorten_clock_once(fence, proposal)
    except BaseException as error:
        raise _fail(state, error)


def _shorten_clock_once(fence, proposal):
    state = _clock(fence)
    require(state.phase == 0 and state.proposal is None, "ORIGINAL_PROPOSAL_BIND_ONCE")
    ends = tuple(min(end, CD.integer(proposal["phaseFencesNs"][name]),
        CD.integer(proposal["proposedJobEndNs"])) for end, (name, _seconds) in zip(state.ends, state.names))
    locals_ = tuple(min(local, O.wire._directed_deadline(state.local, 900, end, state.first.nanoseconds))
        for local, end in zip(state.locals, ends))
    _update(state, ends=ends, locals=locals_, proposal=O.encoded(proposal),
        graph=N._history_graph(state.first, ends, locals_))
    fence.now()


def _advance(fence, name):
    state = _clock(fence)
    try:
        return _advance_once(fence, name)
    except BaseException as error:
        raise _fail(state, error)


def _advance_once(fence, name):
    state = _clock(fence)
    require(state.phase + 1 < len(state.names) and state.names[state.phase + 1][0] == name, "FIXED_PHASE_ORDER")
    # The read phase is entered while the original final cap is still live.
    fence.now(final=True)
    state = _clock(fence)
    local = CD.local(time.monotonic())
    first = O.clocks.validate_reading(O.clocks.observe())
    _pin(state)
    require(first.clock == state.first.clock and state.last <= first.nanoseconds < state.ends[state.phase] and
        state.last_local <= local < state.locals[state.phase],
        "PHASE_ORDER")
    index, seconds = state.phase + 1, state.names[state.phase + 1][1]
    end = min(state.ends[index], CD.integer(first.nanoseconds + seconds * NS))
    local_end = min(state.locals[index], O.wire._directed_deadline(local, seconds, end, first.nanoseconds))
    _update(state, phase=index, ends=(*state.ends[:index], end, *state.ends[index + 1:]),
        locals=(*state.locals[:index], local_end, *state.locals[index + 1:]),
        started=(*state.started, (first.nanoseconds, local)), last=first.nanoseconds, last_local=local, reading=first,
        reading_graph=N._history_graph(first))
    fence.now()


def _source_current(source):
    _pin(source)
    require(type(source) is ChildSourceBinding, "CHILD_SOURCE_KIND")
    CD.job(source.job_id)
    CD.canonical(source.observed_raw, CD.PUBLIC_LIMIT)
    for digest in (source.event_sha256, source.context_sha256, source.start_sha256):
        CD.sha(digest)
    saved = _SOURCES.get(id(source))
    require(type(saved) is tuple and saved[0] is source and _STATES.get(id(saved[1])).source is source and
        source.context_sha256 == O.digest(saved[2]) and source.start_sha256 == O.digest(saved[3]) and
        source.event_sha256 == O.digest(saved[4]), "ORIGINAL_CHILD_SOURCE_RECORDS")
    context = CD.crypto_context(saved[2])
    require(source.job_id == context["job"] and source.observed_raw == O.encoded(context["observed"]),
        "ORIGINAL_CHILD_SOURCE_CONTEXT")


def _operation_caps(state, cls):
    require(type(state.handle) is ChildFinal and cls in (ValidationCaps, ArchiveCaps), "CHILD_OPERATION")
    child_clock = _clock(state.clock)
    state.clock.now()
    local = CD.local(time.monotonic())
    first = O.clocks.validate_reading(O.clocks.observe())
    require(first.clock == child_clock.first.clock and local >= child_clock.last_local and
        first.nanoseconds >= child_clock.last, "OPERATION_FIRST")
    _update(child_clock, last=first.nanoseconds, last_local=local, reading=first, reading_graph=N._history_graph(first))
    limit = 60 if cls is ValidationCaps else 240
    phase = state.phase_caps[0 if cls is ValidationCaps else 1]
    finish = min(CD.integer(first.nanoseconds + limit * NS), phase, state.phase_caps[5], state.clock.work)
    reserve = 30 if os.name == "nt" else 0
    work = finish - reserve * NS
    require(first.nanoseconds < work and finish > reserve * NS, "OPERATION_RESERVE")
    finish_local = min(child_clock.locals[child_clock.phase],
        O.wire._directed_deadline(child_clock.local, 900, finish, child_clock.first.nanoseconds),
        O.wire._directed_deadline(local, limit, finish, first.nanoseconds))
    work_local = min(math.nextafter(finish_local - reserve, -math.inf),
        O.wire._directed_deadline(child_clock.local, 900, work, child_clock.first.nanoseconds))
    require(local < work_local <= finish_local, "OPERATION_LOCAL_RESERVE")
    caps = _track(cls(first.clock, first, local, work, work_local, finish, finish_local, reserve * NS, limit * NS))
    _CAPS[id(caps)] = caps, state.handle, N._history_graph(first), _PINS[id(caps)]
    return caps


def _caps_current(caps, child):
    _pin(caps)
    saved = _CAPS.get(id(caps))
    require(type(saved) is tuple and saved[0] is caps and saved[1] is child and
        saved[3] is _PINS[id(caps)] and type(caps) in (ValidationCaps, ArchiveCaps) and caps.clock is caps.first.clock,
        "ORIGINAL_OPERATION_CAPS")
    N._check_history(saved[2])
    for name in ("firstLocal", "workEndLocal", "operationFinishEndLocal"):
        CD.local(getattr(caps, name))
    for name in ("workEndNs", "operationFinishEndNs", "finishReserveNs", "operationLimitNs"):
        CD.integer(getattr(caps, name))
    return caps


def _child_active(child):
    state = _state(child)
    require(type(child) is ChildFinal and _CHILDREN.get(id(child)) is state and state.closed is None and
        state.owner is not None and not state.owner.finished, "CHILD_NOT_ACTIVE")
    state.owner.structural()
    require(state.owner.failure is None and not state.owner.owner.unknown, "CHILD_OWNER_FAILED")
    _child_roots_current(state)
    _source_current(state.source)
    _environment(state)
    state.clock.now()
    return state


def _operation_current(state, caps, completed):
    _caps_current(caps, state.handle)
    if completed is None:
        state.clock.now(limit=caps.operationFinishEndNs)
        require(_clock(state.clock).last_local < caps.operationFinishEndLocal, "OPERATION_FINISH_LOCAL")
    else:
        _pin(completed)
        N._check_history(completed.graph)
        require(completed.caps is caps and completed.reading.clock == caps.clock and
            completed.raw == completed.reading.nanoseconds < caps.operationFinishEndNs and
            caps.first.nanoseconds <= completed.raw and caps.firstLocal <= completed.local < caps.operationFinishEndLocal,
            "ORIGINAL_OPERATION_COMPLETION")


@dataclass(frozen=True, repr=False)
class _Completed:
    caps: object
    returned: object
    raw: int
    local: float
    reading: object
    graph: tuple


def _complete_operation(state, caps, returned):
    state.clock.now(limit=caps.operationFinishEndNs)
    clock = _clock(state.clock)
    require(clock.last_local < caps.operationFinishEndLocal, "ACTUAL_OPERATION_RETURN_LATE")
    return _track(_Completed(caps, returned, clock.last, clock.last_local, clock.reading,
        N._history_graph(clock.reading)))


def checked_child_validation(child):
    state = _child_active(child)
    try:
        if state.validation is None:
            require(state.archive is None and state.validation_return is None and
                _clock(state.clock).names[_clock(state.clock).phase][0] == "custody-freeze", "VALIDATION_BEGIN_ONCE")
            caps = _operation_caps(state, ValidationCaps)
            raws = dict(state.auxiliary)
            view = _track(ValidationView(child, state.source and _clock(state.clock).first.clock.role, state.work,
                raws["recipient-public.asc"], raws["candidate-policy.json"], raws["original-match.json"], state.source, caps))
            _VIEWS[id(view)] = view, child, _PINS[id(view)]
            _update(state, validation=view)
        return check_child_validation(state.validation)
    except BaseException as error:
        raise _fail(state, error)


def check_child_validation(view):
    _pin(view)
    require(type(view) is ValidationView, "VALIDATION_VIEW")
    state = _child_active(view.child)
    try:
        saved = _VIEWS.get(id(view))
        require(type(saved) is tuple and saved[0] is view and saved[1] is view.child and
            saved[2] is _PINS[id(view)] and state.validation is view and view.work is state.work and
            view.source is state.source, "ORIGINAL_VALIDATION_VIEW")
        _operation_current(state, view.caps, state.validation_completed)
        return view
    except BaseException as error:
        raise _fail(state, error)


def _node_current(node):
    _pin(node)
    require(type(node) is ExpectedNode, "EXPECTED_NODE_TYPE")
    CD.relative(node.relative, empty=True)
    CD.native(node.native, directory=node.kind == "directory")
    if node.kind == "directory":
        require(node.bytes is node.sha256 is None, "DIRECTORY_SENTINEL")
    else:
        require(node.kind == "file", "EXPECTED_NODE_KIND")
        CD.integer(node.bytes, 0, CD.MAX_BYTES)
        CD.sha(node.sha256)
    _pin(node.provenance)
    origin = node.provenance
    require(type(origin) is _NodeOrigin and _PROVENANCE.get(id(origin)) is origin and
        type(origin.path) is type(ROOT) and origin.path.is_absolute(), "ORIGINAL_NODE_PROVENANCE")
    if origin.close is not None:
        _pin(origin.close)


def _partition_current(partition, ordinal, *, whole):
    _pin(partition)
    require(type(partition) is PartitionView and type(partition.ordinal) is int and partition.ordinal == ordinal and
        partition.group == CD.GROUPS[ordinal - 1] and type(partition.members) is tuple and
        0 < len(partition.members) < CD.MAX_NODES, "FIXED_PARTITION")
    if whole:
        for node in (partition.root, *partition.members, partition.map):
            _node_current(node)
        require(partition.root.relative == partition.group and partition.root.kind == "directory" and
            partition.map.relative == "map-" + partition.group + ".json" and
            all(node.relative == partition.group + "/" + CD.member_name(index)
                for index, node in enumerate(partition.members)), "PARTITION_ROSTER")


def checked_child_archive(child, archive, recipient):
    state = _child_active(child)
    try:
        require(type(archive) is ChildArchiveBinding30 and state.archive is archive and state.validation_return is not None and
            state.validation_completed is not None and state.validation_return.recipient is recipient and
            type(state.partitions) is tuple and len(state.partitions) == 30 and state.index is not None,
            "CHILD_FINAL_ARCHIVE_REQUIRED")
        _pin(archive)
        if state.archive_view is None:
            caps = _operation_caps(state, ArchiveCaps)
            view = _track(ArchiveView(child, archive, recipient, _clock(state.clock).first.clock.role,
                state.payload, state.output, state.root, state.partitions, state.index, state.lineage, caps, state.public_inputs))
            _VIEWS[id(view)] = view, child, _PINS[id(view)]
            _update(state, archive_view=view)
        require(state.archive_view.recipient is recipient, "ORIGINAL_RECIPIENT")
        return check_child_archive(state.archive_view)
    except BaseException as error:
        raise _fail(state, error)


def archive_liveness(view):
    _pin(view)
    require(type(view) is ArchiveView, "ARCHIVE_VIEW")
    state = _child_active(view.child)
    try:
        saved = _VIEWS.get(id(view))
        require(type(saved) is tuple and saved[0] is view and saved[1] is view.child and
            saved[2] is _PINS[id(view)] and state.archive_view is view and state.archive is view.archive and
            state.partitions is view.partitions and state.payload is view.payload and state.output is view.output and
            state.root is view.payload_root and state.index is view.index and state.lineage is view.lineage and
            state.public_inputs is view.public_inputs and len(view.partitions) == 30, "ORIGINAL_ARCHIVE_VIEW")
        _pin(view.archive)
        _pin(view.lineage)
        require(state.validation_return.recipient is view.recipient, "SAME_VALIDATED_RECIPIENT")
        for ordinal, partition in enumerate(view.partitions, 1):
            _partition_current(partition, ordinal, whole=False)
        _operation_current(state, view.caps, state.export_completed)
        return view.caps
    except BaseException as error:
        raise _fail(state, error)


def check_child_archive(view):
    archive_liveness(view)
    state = _state(view.child)
    try:
        for ordinal, partition in enumerate(view.partitions, 1):
            _partition_current(partition, ordinal, whole=True)
        _node_current(view.payload_root)
        _node_current(view.index)
        require(view.payload_root.relative == "" and view.payload_root.kind == "directory" and
            view.index.relative == "copy-index.json" and view.index.kind == "file", "FINAL_ROOT_INDEX")
        CD.canonical(view.public_inputs, CD.PUBLIC_LIMIT)
        _check_union(state)
        return view
    except BaseException as error:
        raise _fail(state, error)


def _child_retired(child):
    state = _state(child)
    require(type(child) is ChildFinal and _CHILDREN.get(id(child)) is state and state.closed is not None,
        "ORIGINAL_OUTER_CLOSE_REQUIRED")
    _check_owner_close(state.closed)
    require(state.closed.owner is state.owner, "SAME_OUTER_OWNER_CLOSE")
    _child_roots_current(state)
    _source_current(state.source)
    return state


def checked_retired_child_validation(child):
    state = _child_retired(child)
    view = state.validation
    require(type(view) is ValidationView and state.validation_return is not None and state.validation_completed is not None,
        "ORIGINAL_VALIDATION_RETURN")
    _pin(view)
    _pin(state.validation_completed)
    _caps_current(view.caps, child)
    _operation_current(state, view.caps, state.validation_completed)
    _pin(state.validation_return)
    require(view.child is child and view.source is state.source and view.work is state.work and
        state.validation_completed.returned is state.validation_return, "RETIRED_VALIDATION_BINDING")
    return view


def check_retired_child_archive(view):
    _pin(view)
    require(type(view) is ArchiveView, "RETIRED_ARCHIVE_KIND")
    state = _child_retired(view.child)
    require(state.archive_view is view and state.archive is view.archive and state.partitions is view.partitions and
        state.index is view.index and state.root is view.payload_root and state.backend_return is not None and
        state.export_completed is not None and state.export_completed.returned is state.backend_return,
        "RETIRED_ARCHIVE_BINDING")
    _pin(state.export_completed)
    _caps_current(view.caps, view.child)
    _operation_current(state, view.caps, state.export_completed)
    _pin(state.backend_return)
    for ordinal, partition in enumerate(view.partitions, 1):
        _partition_current(partition, ordinal, whole=True)
    _check_union(state, retired=True)
    return view


# Fixed controller-owned native bridges. A seed is never a transport DTO.
@dataclass(frozen=True, repr=False)
class _NativeSeed:
    pass


@dataclass(eq=False, repr=False)
class _NativeState:
    seed: object
    parent: object
    purpose: str
    fence: object
    first: object
    cancelled: object
    end: float
    owner: object = None
    methods: tuple = ()
    private: object = None
    context_raw: object = None
    before: object = None
    phase: tuple = ()
    check: object = None
    failure: object = None
    launch: tuple = ()
    completion: tuple = ()


@dataclass(frozen=True, repr=False)
class _OwnerClose:
    owner: object
    anchor: object
    rows: tuple
    raw: bytes
    # Immutable exhaustive (original row, bounded row graph) pairs, not one ledger graph.
    graph: tuple
    methods: tuple


def _froot():
    return C._paths("worker")[2] / "productive-final"


def _fixed_paths():
    root = _froot()
    return (("root", root), *((name, root / name) for name in
        ("payload", "public-crypto", "export-output", "returned", "authority-pre-export", "authority-post-export")),
        *((name, root / "returned" / name) for name in ("control-home", "temporary", "crypto-service")))


def _path(state, name):
    require(type(state.paths) is tuple and state.paths, "ORIGINAL_FIXED_PATHS")
    return dict(state.paths)[name]


def _claims(*, collect=False):
    values = {name: os.environ.get("P2PKIT_BOOTSTRAP_" + name) for name in CD.FINAL_CLAIMS}
    for name, value in values.items():
        require(value == "success" if name.endswith("OUTCOME") else
            type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None, "ORIGINAL_STEP_INPUT")
    if collect:
        for name in CD.EXPORT_CLAIMS:
            value = os.environ.get(name)
            require(value == "success" if name.endswith("OUTCOME") else
                type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None, "ORIGINAL_EXPORT_STEP_INPUT")
            values[name] = value
    return values


def _environment(state):
    P._credential_free()
    require(P.C is C and C.N is N and C.native is B and P.B is B and P.O is O and A.P is P and
        A.C is C and A.B is B and ROOT == D.ROOT == C.ROOT == N.ROOT and
        not B.QUARANTINE and not Q.QUARANTINE and not B.diagnostics._QUARANTINE and not _QUARANTINE,
        "CANONICAL_GRAPH_OR_PRIOR_UNKNOWN")
    if state.host_path is not None:
        require(os.environ.get("GITHUB_EVENT_PATH") == str(state.host_path), "ORIGINAL_EVENT_PATH_CHANGED")
        if state.host_event_raw is not None:
            observed = CD.canonical(state.host_observed_raw, CD.PUBLIC_LIMIT)
            require(N.acquisition._context(dict(os.environ), state.host_event_raw, "worker", observed["firstUseAt"]) == observed,
                "ORIGINAL_EVENT_CONTEXT_CHANGED")
    if type(state.handle) in (ParentFinal, CollectPrepared):
        require(O.encoded(_claims(collect=type(state.handle) is CollectPrepared)) == state.claims_raw,
            "ORIGINAL_CLAIMS_CHANGED")
    if state.handoff is not None:
        history = CD.canonical(state.handoff.history)
        event = state.handoff.identity.original_event
        observed = N.acquisition._context(dict(os.environ), event, "worker", history["firstUseAt"])
        require(observed == history["observed"] and observed["kind"] == "worker" and
            observed["role"] == _clock(state.clock).first.clock.role and
            os.environ.get("GITHUB_WORKSPACE") == str(ROOT), "ACTUAL_HOST_CHANGED")
        D.checked_worker(state.handoff.identity)
    elif type(state.handle) is ChildFinal and state.source is not None:
        _source_current(state.source)
        observed = CD.canonical(state.source.observed_raw, CD.PUBLIC_LIMIT)
        event = dict(state.auxiliary)["event.json"]
        require(N.acquisition._context(dict(os.environ), event, "worker", observed["firstUseAt"]) == observed and
            os.environ.get("GITHUB_WORKSPACE") == str(ROOT), "CURRENT_CHILD_HOST")
        N.I._policy(dict(state.auxiliary)["candidate-policy.json"], int(time.time()))
    _pin(state)


def _new_state(kind, operation, cancelled, names, *, caps=None, declared_clock=None, boot=None, minimum=0):
    prior = _ATTEMPTS.get(operation)
    if prior is not None:
        raise _fail(prior, O.OriginError("INITIAL_PRODUCTIVE_CUSTODY_ORIGINAL_ATTEMPT_ONCE"))
    # Even failure to observe the first time burns this actual process's entry.
    attempt = _track(_Attempt(operation, _attempt_functions(), _registry_roots()))
    _ATTEMPTS[operation] = attempt
    try:
        fence = _new_clock(cancelled, names, caps=caps, declared_clock=declared_clock, boot=boot, minimum=minimum, attempt=attempt)
        handle = _track(kind())
        _update(attempt, handle=handle)
        claims = _claims(collect=kind is CollectPrepared) if kind in (ParentFinal, CollectPrepared) else {}
        state = _track(_State(handle, operation, fence, O.encoded(claims), b"", N._history_graph(_clock(fence).first),
            paths=_fixed_paths(), claims=tuple(sorted(claims.items()))))
        _STATES[id(handle)] = state
        if kind is ChildFinal:
            _CHILDREN[id(handle)] = state
        _environment(state)
        return state
    except BaseException as error:
        raise _fail(attempt, error)


def _native_seed(state, purpose, fence):
    require(purpose in ("reader", "authority-pre", "authority-post", "crypto-native", "authority-child"), "SEED_PURPOSE")
    _state(state.handle)
    base = _clock(state.clock)
    first = base.first
    N._check_history(N._history_graph(first))
    end = fence.deadline(900, final=True)
    seed = _track(_NativeSeed())
    saved = _track(_NativeState(seed, state.handle, purpose, fence, first, base.cancelled, end))
    _NATIVE_SEEDS[id(seed)] = saved
    return seed


def _native_state(seed):
    _pin(seed)
    value = _NATIVE_SEEDS.get(id(seed))
    require(type(seed) is _NativeSeed and type(value) is _NativeState and value.seed is seed, "ORIGINAL_NATIVE_SEED")
    _pin(value)
    _state(value.parent)
    if value.failure is not None:
        raise value.failure
    return value


def _checked_native_owner_seed(seed):
    value = _native_state(seed)
    require(value.owner is None, "NATIVE_SEED_CONSUMED")
    return value.fence, value.first, value.cancelled, value.end


def _attach_native_owner(seed, owner):
    value = _native_state(seed)
    require(type(owner) is C._ProductiveNativeOwner and value.owner is None and owner.fence is value.fence and
        owner.first is value.first and owner.cancelled is value.cancelled and owner.local_end == value.end,
        "NATIVE_OWNER_ACTUAL_ATTACH")
    _update(value, owner=owner, methods=_methods(owner, ("end", "acquire", "read", "write", "open", "child",
        "close_one", "close", "check", "freeze", "known", "enter_final_productive_phase", "leave_final_productive_phase")))


def _native_boundary(owner):
    original = C._PRODUCTIVE_NATIVE_OWNERS.get(id(owner))
    require(type(original) is tuple and original[0] is owner, "NATIVE_BOUNDARY_OWNER")
    value = _native_state(original[1])
    state = _state(value.parent)
    try:
        require(value.owner is owner and owner._anchor() is original[2], "NATIVE_OWNER_SUBSTITUTED")
        _methods_current(owner, value.methods)
        owner.check()
        _environment(state)
        # Resource lifetime was reserved to its original final ceiling, but
        # every actual effect also remains in the current operative envelope.
        state.clock.now(final=True)
    except BaseException as error:
        raise _fail(state, error)


def _close_owner(owner):
    """Register only the actual call's successful normal close, never row DATA."""
    require(id(owner) not in _OWNER_CLOSES, "OWNER_CLOSE_ONCE")
    if type(owner) is C._PrimaryOwner:
        methods = _methods(owner, ("structural", "guard", "acquire", "close_one", "finish"))
        anchor = owner._anchor()
        raw = owner.finish()
        rows = anchor.rows
        owner.structural()
        require(owner.finished and owner.owner.closed and not owner.owner.unknown and owner.failure is None and
            owner.owner.original is None and not owner.errors and all(a and c for _row, _label, _r, a, c in rows),
            "ACTUAL_FILE_OWNER_CLOSE")
    else:
        require(type(owner) is C._ProductiveNativeOwner, "CLOSE_ORIGINAL_OWNER_TYPE")
        methods = _native_state(C._PRODUCTIVE_NATIVE_OWNERS[id(owner)][1]).methods
        owner.freeze()
        owner.close()
        anchor = owner.known()
        rows = anchor.rows
        raw = O.encoded({"schema": 1, "scope": "INITIAL_PRODUCTIVE_FINAL_NATIVE_OWNER_CLOSE_V1",
            "resources": [{"ordinal": index, "label": label, "closeAttempted": attempted, "closed": ended}
                for index, (_row, label, _resource, attempted, ended) in enumerate(rows)],
            "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False})
    _methods_current(owner, methods)
    require(type(rows) is tuple and 0 < len(rows) <= CD.MAX_NODES and len(raw) <= CD.LIMIT, "OWNER_CLOSE_BOUND")
    graph = tuple((row, N._history_graph(row)) for row in rows)
    closed = _track(_OwnerClose(owner, anchor, rows, raw, graph, methods))
    _OWNER_CLOSES[id(owner)] = closed
    _check_owner_close(closed)
    return closed


def _check_owner_close(closed):
    saved = _PINS.get(id(closed))
    try:
        _pin(closed)
        require(type(closed) is _OwnerClose and _OWNER_CLOSES.get(id(closed.owner)) is closed, "ORIGINAL_OWNER_CLOSE")
        owner = closed.owner
        _methods_current(owner, closed.methods)
        require(type(closed.graph) is tuple and len(closed.graph) == len(closed.rows), "ORIGINAL_CLOSE_HISTORY")
        for row, history in zip(closed.rows, closed.graph):
            require(type(history) is tuple and len(history) == 2 and history[0] is row and
                type(history[1]) is tuple, "ORIGINAL_CLOSE_HISTORY_ROW")
            N._check_history(history[1])
        require(owner._anchor() is closed.anchor and owner._anchor().rows is closed.rows, "ORIGINAL_CLOSE_ROWS")
        if type(owner) is C._PrimaryOwner:
            owner.structural()
            require(owner.finished and owner.owner.closed and not owner.owner.unknown and owner.failure is None and
                owner.owner.original is None and owner.errors == [], "RETIRED_FILE_OWNER_UNKNOWN")
        else:
            require(type(owner) is C._ProductiveNativeOwner and owner.known() is closed.anchor, "RETIRED_NATIVE_OWNER_UNKNOWN")
        require(all(row["owner"] is resource and row["attempted"] is row["closed"] is attempted is ended is True
            for row, _label, resource, attempted, ended in closed.rows), "ACTUAL_CLOSE_FLAGS")
        return closed
    except BaseException as error:
        if type(saved) is tuple and len(saved) == 4 and saved[0] is closed and saved[1] is _OwnerClose:
            failed = _PIN_FAILURES.setdefault(id(closed), (closed, error))
            require(failed[0] is closed, "PIN_FAILURE_ALIAS")
            raise failed[1]
        raise


def _abort_owner(owner, error):
    if owner is None:
        return
    if type(owner) is C._PrimaryOwner:
        owner.remember(error)
        if not owner.finished and not owner.owner.unknown:
            try:
                owner.finish()
            except BaseException:
                pass
        unknown = owner.owner.unknown
    else:
        owner.error("productive-final-abort", error)
        try:
            owner.close()
        except BaseException:
            pass
        unknown = owner._anchor().unknown
    if unknown and not any(original is owner for original in _QUARANTINE):
        _QUARANTINE.append(owner)


def _abort_state(state, error):
    """Cleanup only actual original resources, once; never mint a close return."""
    original = _PINS.get(id(state))
    require(type(original) is tuple and original[0] is state, "ABORT_ORIGINAL_STATE")
    values = dict(original[3])
    first = _fail(state, error)
    if values["abort_started"]:
        return
    _owned_slot(state, "abort_started", True)
    owners = list(values["owners"])
    for name in ("reader_seed", "authority_seed", "crypto_seed"):
        seed = values[name]
        native = _NATIVE_SEEDS.get(id(seed))
        if native is not None:
            saved = _PINS.get(id(native))
            if saved is not None:
                owner = dict(saved[3])["owner"]
                if owner is not None:
                    owners.append(owner)
    if values["owner"] is not None:
        owners.append(values["owner"])
    seen = set()
    for owner in reversed(owners):
        if id(owner) in seen or id(owner) in _OWNER_CLOSES:
            continue
        seen.add(id(owner))
        try:
            _abort_owner(owner, first)
        except BaseException:
            if not any(kept is owner for kept in _QUARANTINE):
                _QUARANTINE.append(owner)


def _file_owner(state, fence=None, *, ciphertext=False):
    _state(state.handle)
    require(type(ciphertext) is bool, "FILE_OWNER_PURPOSE")
    basis = _clock(state.clock)
    if fence is None:
        fence, end = state.clock, basis.locals[basis.phase]
    else:
        require(type(fence) is _SpanFence and fence._binding()[0].clock is state.clock, "SAME_FILE_OWNER_CLOCK")
        end = fence.deadline(900, final=True)
    actual = B.Owner(end, fence, first=basis.first, cancelled=basis.cancelled)
    owner = C._PrimaryOwner(actual)
    budget = _track(_Budget(owner, state.handle, purpose="ciphertext" if ciphertext else "archive"))
    _BUDGETS[id(owner)] = budget
    _update(state, owners=(*state.owners, owner), accounting=(*state.accounting, budget))
    owner.guard()
    return owner


def _final_reader_binding(parent):
    state = _state(parent)
    require(type(parent) is ParentFinal and state.reader_seed is not None and state.closed is None,
        "FINAL_READER_ORIGINAL_PARENT")
    saved = _native_state(state.reader_seed)
    require(saved.purpose == "reader" and saved.owner is not None, "FINAL_READER_REGISTERED")
    _native_boundary(saved.owner)
    saved.owner.end()
    return saved.owner, saved.first, CD.canonical(state.claims_raw)


def _checked_final_reader_owner(owner, first, claims, *, retired=False):
    require(type(retired) is bool and type(owner) is C._ProductiveNativeOwner, "FINAL_READER_OWNER_TYPE")
    registered = C._PRODUCTIVE_NATIVE_OWNERS.get(id(owner))
    require(type(registered) is tuple and registered[0] is owner, "FINAL_READER_ACTUAL_OWNER")
    value = _native_state(registered[1])
    state = _state(value.parent)
    require(type(state.handle) is ParentFinal and state.reader_seed is value.seed and value.purpose == "reader" and
        value.owner is owner and first is value.first and O.encoded(claims) == state.claims_raw,
        "FINAL_READER_PARENT_BINDING")
    _methods_current(owner, value.methods)
    if retired:
        _check_owner_close(_OWNER_CLOSES[id(owner)])
    else:
        owner.check()
        require(not owner.closed and not owner.unknown and owner.original is None, "FINAL_READER_NOT_LIVE")
    return owner


def _bind_final_reader_proposal(owner, proposal_raw):
    registered = C._PRODUCTIVE_NATIVE_OWNERS.get(id(owner))
    require(type(registered) is tuple and registered[0] is owner, "PROPOSAL_ACTUAL_READER")
    value = _native_state(registered[1])
    state = _state(value.parent)
    require(type(state.handle) is ParentFinal and state.reader_seed is value.seed and value.purpose == "reader" and
        state.handoff is None, "PROPOSAL_DENIAL_POSITION")
    _shorten_clock(state.clock, CD.canonical(proposal_raw))


def _final_reader_authority(parent):
    state = _state(parent)
    require(type(parent) is ParentFinal and state.authority is not None, "FINAL_CURRENT_AUTHORITY_REQUIRED")
    authority = _checked_authority(state.authority, state)
    require(authority.post is False, "FINAL_PRE_AUTHORITY_REQUIRED")
    return authority.identity, authority


def _checked_authority_phase(seed, owner, private, context_raw, fence, before, *, post):
    value = _native_state(seed)
    require(type(post) is bool and value.purpose == ("authority-post" if post else "authority-pre") and
        value.owner is owner and value.private is private and value.context_raw is context_raw and value.before is before and
        value.fence is fence and type(before) is N.SourceReturn and
        owner.initial_sources.get(str(private.path / "source-before")) is before, "AUTHORITY_BRIDGE_ORIGINALS")
    _native_boundary(owner)
    context = (CD.authority_post_context if post else CD.authority_pre_context)(context_raw)
    require(context["session"] == str(_froot() / ("authority-post-export" if post else "authority-pre-export")) ==
        str(private.path) and context["root"] == str(ROOT) and context["sourceReturnSha256"] == O.digest(before.raw) and
        context["sourceReturnedNs"] == CD.canonical(before.raw)["returnedNs"], "AUTHORITY_FIXED_CONTEXT")
    return post


def _checked_authority_phase_seed(seed, owner, private, context_raw, fence, before):
    value = _native_state(seed)
    require(value.purpose in ("authority-pre", "authority-post"), "AUTHORITY_ROUTE")
    return _checked_authority_phase(seed, owner, private, context_raw, fence, before, post=value.purpose == "authority-post")


def _checked_native_authority_bridge(seed, owner, private, context_raw, fence, *, post):
    value = _native_state(seed)
    return _checked_authority_phase(seed, owner, private, context_raw, fence, value.before, post=post)


def _check_native_phase_entry(seed, owner, context_raw, started, work, final):
    value = _native_state(seed)
    state = _state(value.parent)
    require(value.owner is owner and owner.fence is value.fence and value.context_raw is context_raw and not value.phase and
        type(started) is int and started == value.fence.last, "ACTUAL_NATIVE_PHASE_ENTRY")
    for number in (started, work, final):
        CD.integer(number)
    seconds = 210 if value.purpose == "crypto-native" else 45
    require(value.purpose in ("authority-pre", "authority-post", "crypto-native") and
        work == min(value.fence.work, started + seconds * NS) and
        final == min(value.fence.final, work + 45 * NS) and started < work <= final, "ORIGINAL_NATIVE_PHASE_CAPS")
    if value.purpose == "crypto-native":
        require(started < _clock(state.clock).ends[0], "NATIVE_LAUNCH_DURING_FREEZE")
        CD.crypto_caps((*state.phase_caps[:4], started, work, final))
    else:
        context = (CD.authority_post_context if value.purpose == "authority-post" else CD.authority_pre_context)(context_raw)
        cap = tuple(context["authorityWindow"][name] for name in CD.FINAL_AUTHORITY_CAP_FIELDS[:3])
        CD.authority_caps((*cap, started, work, final), context["authorityWindow"])
        require(context["sourceReturnedNs"] <= started, "NATIVE_AFTER_ACTUAL_SOURCE_RETURN")
    _update(value, phase=(started, work, final))
    if value.purpose == "crypto-native":
        # Parent waiting-envelope transition only. This says NOTHING about the
        # child's later metadata/validation/copy/index freeze completion.
        _advance(state.clock, "custody-encrypt")


def _command(operation, context_raw, caps, clock, boot, minimum=None, *, interpreter=None):
    require(operation in ("_final-authority-pre", "_final-authority-post", "_final-crypto"), "FIXED_NATIVE_OPERATION")
    crypto = operation == "_final-crypto"
    (CD.crypto_caps if crypto else CD.authority_caps)(caps)
    O.clocks.validate_identity(clock)
    CD.sha(boot)
    # Actual construction selects the maintained interpreter. Historical joins
    # use its retained lexical spelling, not a post-retirement filesystem read.
    if interpreter is None:
        interpreter = B.initial_command(O.digest(context_raw))[0]
    require(type(interpreter) is str and Path(interpreter).is_absolute() and ".." not in Path(interpreter).parts,
        "FIXED_INTERPRETER_DATA")
    argv = [interpreter, "-I", "-B", "-S", str(P.SCRIPTS / "run-hosted-initial-recipient-productive.py"),
        operation, "--context-sha256", O.digest(context_raw)]
    if minimum is not None:
        argv += ["--minimum-ns", str(CD.integer(minimum))]
    flags = CD.FINAL_CRYPTO_CAP_FLAGS if crypto else CD.FINAL_AUTHORITY_CAP_FLAGS
    for flag, cap in zip(flags, caps):
        argv += [flag, str(cap)]
    return argv + ["--original-boot-digest", boot, "--clock-role", clock.role, "--clock-domain", clock.domain,
        "--clock-ticks-per-second", str(clock.ticks_per_second)]


def _native_argv(seed, context_raw, phase, minimum=None):
    value = _native_state(seed)
    state = _state(value.parent)
    require(value.context_raw is context_raw and type(phase) is tuple and phase == value.phase, "ORIGINAL_PHASE_COMMAND")
    basis = _clock(state.clock)
    if value.purpose == "crypto-native":
        caps, operation = (*state.phase_caps[:4], *phase), "_final-crypto"
        if minimum is not None:
            require(phase[0] <= CD.integer(minimum) < state.phase_caps[0], "ACTUAL_LAUNCH_MUST_SPEND_FREEZE")
    else:
        post = value.purpose == "authority-post"
        require(value.purpose in ("authority-pre", "authority-post"), "AUTHORITY_COMMAND_ROUTE")
        context = (CD.authority_post_context if post else CD.authority_pre_context)(context_raw)
        caps = (*(context["authorityWindow"][name] for name in CD.FINAL_AUTHORITY_CAP_FIELDS[:3]), *phase)
        operation = "_final-authority-post" if post else "_final-authority-pre"
    return _command(operation, context_raw, caps, basis.first.clock, basis.boot, minimum)


@dataclass(frozen=True, repr=False)
class _AuthorityChild:
    pass


@dataclass(frozen=True, repr=False)
class _Authority:
    parent: object
    post: bool
    seed: object
    owner: object
    close: object
    before: object
    after: object
    phase: object
    identity: object
    match: object
    captured: tuple
    chain_raw: bytes
    raw: bytes
    index_raw: bytes
    originals: tuple
    pins: tuple
    graphs: tuple


_AUTHORITIES = {}


def _authority_host(context_raw, first, boot, event, path, *, post):
    context = (CD.authority_post_context if post else CD.authority_pre_context)(context_raw)
    window = context["authorityWindow"]
    require(context["session"] == str(path) and context["root"] == str(ROOT) and
        window["clock"] == O.clock_value(first.clock) and window["originalBootDigest"] == boot,
        "AUTHORITY_ACTUAL_CONTEXT")
    require(type(event) is bytes and len(event) <= N.I.EVENT_LIMIT, "AUTHORITY_ORIGINAL_EVENT_DATA")
    observed = N.acquisition._context(dict(os.environ), event, "worker", context["observed"]["firstUseAt"])
    require(context["observed"] == observed and observed["kind"] == "worker" and
        observed["role"] == first.clock.role and context["eventSha256"] == O.digest(event), "AUTHORITY_ACTUAL_HOST")
    N.initial_identity._match(context["expectedMatch"])
    expected = N.acquisition.stages.BootstrapMatch(O.encoded(context["expectedMatch"]))
    require(context["history"]["firstUseAt"] == observed["firstUseAt"] and
        context["history"]["originalJobBasisNs"] == window["originalJobBasisNs"] and
        context["history"]["matchSha256"] == O.digest(expected.record), "AUTHORITY_HISTORY_BINDING")
    B.directory_identity(context["directoryIdentity"], first.clock.role)
    inherited = context["inheritedContext"]
    require(all(type(key) is str and type(value) is str for key, value in inherited.items()) and
        (set(inherited).issubset({"GRADLE_USER_HOME"}) or set(inherited) == set(Q._CONTEXT)), "AUTHORITY_ANCESTORS")
    return context, expected, event


def _authority_start(context_raw, start_raw, caps, first, boot, event, path, *, post):
    context, expected, event = _authority_host(context_raw, first, boot, event, path, post=post)
    CD.authority_caps(caps, context["authorityWindow"])
    start = CD.fields(CD.canonical(start_raw), B.START_FIELDS)
    operation = "_final-authority-post" if post else "_final-authority-pre"
    require(type(start["argv"]) is list and start["argv"], "AUTHORITY_ORIGINAL_ARGV")
    require(type(start["schema"]) is int and start["schema"] == 1 and start["scope"] == B.PHASE_SCOPE and
        start["argv"] == _command(operation, context_raw, caps, first.clock, boot, interpreter=start["argv"][0]) and
        start["contextSha256"] == O.digest(context_raw) and start["cwd"] == str(ROOT) and
        start["role"] == first.clock.role and start["job"] == context["job"] and start["state"] == str(path) and
        start["home"] == str(path / "control-home") and start["exitCode"] is None and
        start["launchAttempted"] is start["scopeAttempted"] is False and start["retirement"] == "UNKNOWN" and
        tuple(start[name] for name in ("startedNs", "workEndNs", "finalEndNs")) == caps[3:] and
        context["sourceReturnedNs"] <= caps[3], "AUTHORITY_ACTUAL_START")
    CD.job(start["invocation"])
    inherited = B.processes.ownership_environment(context["inheritedContext"], context["job"], start["invocation"],
        str(path), str(path / "control-home"), allow_new_context=True)
    require(start["inheritedContext"] == {name: inherited[name] for name in Q._CONTEXT}, "AUTHORITY_START_ANCESTORS")
    return context, start, expected, event


def _phase_closed(context_raw, records, child_raw, caps, first, boot, private_pin, service_pin, event, path, *, post):
    """Pure native-chain DATA join; only the caller has the actual return/owner."""
    require(type(records) is dict and set(records) == B.PHASE_FILES and all(type(raw) is bytes for raw in records.values()),
        "PHASE_ORIGINAL_RECORDS")
    context, start, _expected, _event = _authority_start(context_raw, records["start.json"], caps, first, boot, event, path, post=post)
    row = CD.fields(CD.canonical(records["result.json"]), B.TERMINAL_FIELDS)
    birth = CD.fields(CD.canonical(records["native-start.json"]), "ownership leader preparerIdentity observedNs")
    changed = {"exitCode", "launchAttempted", "scopeAttempted", "retirement"}
    require({name: value for name, value in start.items() if name not in changed} ==
        {name: row[name] for name in start if name not in changed} and type(row["exitCode"]) is int and
        row["exitCode"] == 0 and row["launchAttempted"] is row["scopeAttempted"] is row["scopeCloseAttempted"] is
        row["scopeClosed"] is True and row["retirement"] == "KNOWN" and row["errors"] == row["survivors"] == [] and
        row["nativeStartSha256"] == O.digest(records["native-start.json"]) and
        row["baselineSha256"] == O.digest(records["baseline.json"]) and row["leader"] == birth["leader"] and
        records["stderr.log"] == b"", "NATIVE_ACTUAL_RETURN")
    operation = "_final-authority-post" if post else "_final-authority-pre"
    argv = _command(operation, context_raw, caps, first.clock, boot, CD.integer(row["launchMinimumNs"], caps[3]),
        interpreter=start["argv"][0])
    require(row["launchArgv"] == argv, "ACTUAL_LAUNCH_COMMAND")
    B.native_record(row["ownership"], start, row["leader"], argv)
    B.native_record(birth["ownership"], start, row["leader"], argv, terminal=False)
    require(birth["ownership"]["launches"] == row["ownership"]["launches"], "ACTUAL_BIRTH_LAUNCH")
    preparer = B.closed_lifetime(row["preparerIdentity"], first.clock.role)
    require(preparer == B.closed_lifetime(birth["preparerIdentity"], first.clock.role) and
        preparer["pid"] != row["leader"]["pid"], "ACTUAL_PREPARER")
    baseline = B.baseline_record(records["baseline.json"], first.clock.role)
    if baseline["baseline"] is not None:
        leader = B.lifetime(row["leader"], first.clock.role)
        require(list(leader[:4] if first.clock.role.startswith("macos-") else leader) not in baseline["baseline"],
            "NATIVE_LEADER_PREEXISTED")
    require(row["captureOutcomes"] == {name: {key: True for key in
        ("synced", "verified", "closeAttempted", "closed", "readback")} for name in ("stdout", "stderr")} and
        row["captures"] == {name: {"sha256": O.digest(records[name + ".log"]), "bytes": len(records[name + ".log"])}
            for name in ("stdout", "stderr")}, "ACTUAL_NATIVE_CAPTURES")
    child = CD.fields(CD.canonical(child_raw), "schema scope contextSha256 startSha256 invocation clock bootDigest launchMinimumNs "
        "beganNs metadataLastNs acquiredNs queryReturnedNs querySessionSha256 originalsSha256 matchSha256 directoryIdentities "
        "metadataClose completedNs retirement errors")
    ack = CD.fields(CD.canonical(records["stdout.log"], 16384), "schema scope invocation terminalSha256 clock closedNs")
    require(type(child["schema"]) is type(ack["schema"]) is int and child["schema"] == ack["schema"] == 1 and
        child["scope"] == (CD.AUTHORITY_POST_CHILD_SCOPE if post else CD.AUTHORITY_PRE_CHILD_SCOPE) and
        ack["scope"] == (CD.AUTHORITY_POST_ACK_SCOPE if post else CD.AUTHORITY_PRE_ACK_SCOPE) and
        child["contextSha256"] == O.digest(context_raw) and child["startSha256"] == O.digest(records["start.json"]) and
        child["invocation"] == ack["invocation"] == start["invocation"] and
        child["clock"] == ack["clock"] == O.clock_value(first.clock) and child["bootDigest"] == boot and
        child["launchMinimumNs"] == row["launchMinimumNs"] and child["retirement"] == "PENDING_CHILD_CLOSE" and
        child["errors"] == [] and ack["terminalSha256"] == O.digest(child_raw) and
        child["directoryIdentities"] == {".": list(private_pin), "service": list(service_pin)}, "AUTHORITY_CHILD_ACK")
    close = C._collect_file_close(O.encoded(child["metadataClose"]))
    require(close["resources"] == [{"ordinal": index, "label": label, "closeAttempted": True, "closed": True}
        for index, label in enumerate(("directory", "directory", "reader", "reader"))], "CHILD_ORIGINAL_METADATA_CLOSE")
    CD.fields(child["originalsSha256"], N.ORIGINAL_KEYS)
    for digest in (child["querySessionSha256"], child["matchSha256"], *child["originalsSha256"].values()):
        CD.sha(digest)
    order = [row["launchMinimumNs"], *(child[name] for name in
        ("beganNs", "metadataLastNs", "acquiredNs", "queryReturnedNs", "completedNs")), ack["closedNs"],
        row["completedNs"], row["finalizedNs"]]
    require(all(CD.integer(value) == value for value in order) and order == sorted(order) and caps[3] <= order[0] and
        ack["closedNs"] < caps[4] and row["completedNs"] < caps[4] and row["finalizedNs"] < caps[5] and
        row["launchMinimumNs"] <= CD.integer(birth["observedNs"]) <= row["completedNs"], "ACTUAL_PHASE_ORDER")
    return context, start, row, birth, child, ack


def productive_authority_pre_child(context_sha256, minimum_ns, caps, original_clock, original_boot_digest, cancelled):
    return _authority_child(context_sha256, minimum_ns, caps, original_clock, original_boot_digest, cancelled, post=False)


def productive_authority_post_child(context_sha256, minimum_ns, caps, original_clock, original_boot_digest, cancelled):
    return _authority_child(context_sha256, minimum_ns, caps, original_clock, original_boot_digest, cancelled, post=True)


def _authority_child(context_hash, minimum, caps, original_clock, boot, cancelled, *, post):
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    state = metadata = owner = None
    try:
        CD.authority_caps(caps)
        CD.sha(context_hash)
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) is not None and
            caps[3] <= CD.integer(minimum) < caps[4], "AUTHORITY_CHILD_TOKEN_OR_MINIMUM")
        state = _new_state(_AuthorityChild, "authority-post-child" if post else "authority-pre-child", cancelled,
            (("authority-child", 45),), caps=(min(caps[1], caps[4]),), declared_clock=original_clock, boot=boot, minimum=minimum)
        basis = _clock(state.clock)
        metadata = _file_owner(state)
        path = _froot() / ("authority-post-export" if post else "authority-pre-export")
        private = C._private(metadata, path)
        service = C._private(metadata, path / "service")
        private_pin, service_pin = tuple(private.identity), tuple(service.identity)
        _charge(metadata, nodes=2)
        context_raw, context_native = _read_native(metadata, private, "context.json", CD.LIMIT)
        start_raw, start_native = _read_native(metadata, service, "start.json", CD.LIMIT)
        require(O.digest(context_raw) == context_hash, "AUTHORITY_CHILD_CONTEXT_HASH")
        metadata_close = _close_owner(metadata)
        metadata_last = state.clock.now()
        context = (CD.authority_post_context if post else CD.authority_pre_context)(context_raw)
        observed = _actual_host(state, context["observed"], None)
        context, start, expected, event = _authority_start(context_raw, start_raw, caps, basis.first, basis.boot,
            observed.raw, path, post=post)
        require(start["argv"][0] == B.initial_command(context_hash)[0], "AUTHORITY_CHILD_ACTUAL_INTERPRETER")
        metadata_reads = tuple(_track(_FileRead(state.handle, target, raw, stamp, metadata_close))
            for target, raw, stamp in ((path / "context.json", context_raw, context_native),
                (path / "service" / "start.json", start_raw, start_native)))
        for read in metadata_reads:
            _FILE_READS[id(read)] = read
        _update(state, metadata_close=metadata_close, observations=(*state.observations, *metadata_reads),
            union=(*state.union, *((read.path, read.native) for read in metadata_reads)))
        require(tuple(context["directoryIdentity"]) == private_pin and minimum >= start["startedNs"] and
            basis.first.nanoseconds < caps[4], "CHILD_CONTEXT_ORIGINAL_METADATA")
        inherited = Q._inherited_context()
        require(inherited == start["inheritedContext"], "AUTHORITY_ACTUAL_CHILD_ENVIRONMENT")
        domain = B.processes.ownership_domains(inherited[B.processes.CHAIN_ENV], inherited[B.processes.DOMAINS_ENV])[-1]
        require(domain["id"] == start["invocation"] and domain["job"] == context["job"] and
            domain["state"] == str(path) and domain["home"] == str(path / "control-home"), "CHILD_ACTUAL_DOMAIN")
        original_graph = N._history_graph(context, start, inherited, expected, basis.first)
        seed = _native_seed(state, "authority-child", state.clock)
        owner = C._ProductiveNativeOwner(seed)
        _update(state, owner=owner, context_raw=context_raw, start_raw=start_raw)
        private = owner.open(path)
        service = owner.child(private, "service")
        require(tuple(private.identity) == private_pin and tuple(service.identity) == service_pin and
            owner.read(private, "context.json") == context_raw and owner.read(service, "start.json") == start_raw,
            "CHILD_METADATA_REOPEN")
        supplier = None
        failure = None
        try:
            supplier = N.query_owner(owner, state.clock, path / "acquisition-queries")
            N._initial_service_query_git(supplier)
            supplier.native_host_matches_actions()
            def retain(name, raw, *, failed):
                require(name in N.ORIGINAL_KEYS and type(raw) is bytes and type(failed) is bool, "CHILD_FIXED_ORIGINAL")
                owner.end(final=failed)
                supplier._write(supplier.private, name + ".bin", raw)
                owner.end(final=failed)
            match, originals = N.acquisition.acquire_bootstrap(ROOT, kind="worker", query_runner=supplier,
                invocation=domain["id"], token=token, retain=retain, fence=state.clock, original_work_end=caps[4],
                first_use_at=context["observed"]["firstUseAt"], expected=expected)
            token = None
            acquired = state.clock.now()
            require(type(match) is type(expected) and match.record == expected.record and type(originals) is tuple and
                tuple(name for name, _raw in originals) == N.ORIGINAL_KEYS and
                all(type(raw) is bytes for _name, raw in originals) and dict(originals)["event"] == event,
                "CHILD_ACTUAL_MATCH_ORIGINALS")
            match_pin = C._custody_match_pin(match, "worker")
            returned_graph = N._history_graph(originals, match)
        except BaseException as error:
            failure = error
        finally:
            token = None
            C._custody_finish_queries(owner, supplier, failure)
        returned = state.clock.now()
        queries = owner.open(path / "acquisition-queries")
        session = N.query_session(owner, queries)
        require(all(owner.read(queries, name + ".bin") == raw for name, raw in originals), "CHILD_QUERY_READBACK")
        C._collect_query_index(path / "acquisition-queries", session, dict(originals), context["observed"])
        N._check_history(original_graph)
        N._check_history(returned_graph)
        C._custody_match_check(match_pin)
        terminal_raw = owner.write(service, "child-result.json", {"schema": 1,
            "scope": CD.AUTHORITY_POST_CHILD_SCOPE if post else CD.AUTHORITY_PRE_CHILD_SCOPE,
            "contextSha256": context_hash, "startSha256": O.digest(start_raw), "invocation": domain["id"],
            "clock": O.clock_value(basis.first.clock), "bootDigest": basis.boot, "launchMinimumNs": minimum,
            "beganNs": basis.first.nanoseconds, "metadataLastNs": metadata_last, "acquiredNs": acquired,
            "queryReturnedNs": returned, "querySessionSha256": O.digest(session),
            "originalsSha256": {name: O.digest(raw) for name, raw in originals}, "matchSha256": O.digest(match.record),
            "directoryIdentities": {".": list(private_pin), "service": list(service_pin)},
            "metadataClose": CD.canonical(metadata_close.raw), "completedNs": state.clock.now(),
            "retirement": "PENDING_CHILD_CLOSE", "errors": []})
        close = _close_owner(owner)
        _update(state, closed=close, actual_raw=terminal_raw, auxiliary=(original_graph, returned_graph, match_pin),
            stage="authority-child-closed")
        closed = state.clock.now(limit=caps[4])
        fence = _child_ack_fence(state, caps[4])
        return {"schema": 1, "scope": CD.AUTHORITY_POST_ACK_SCOPE if post else CD.AUTHORITY_PRE_ACK_SCOPE,
            "invocation": domain["id"], "terminalSha256": O.digest(terminal_raw), "clock": O.clock_value(basis.first.clock),
            "closedNs": closed}, fence, caps[4]
    except BaseException as error:
        _abort_owner(owner, error)
        if metadata is not None and not metadata.finished:
            _abort_owner(metadata, error)
        raise _fail(state, error) if state is not None else error
    finally:
        token = None


def _authority_read(state, seed):
    value = _native_state(seed)
    owner, private, before = value.owner, value.private, value.before
    post = value.purpose == "authority-post"
    basis = _clock(state.clock)
    phase = owner.phase_originals
    require(type(phase) is B.OriginalPhase and phase.context is value.context_raw and type(phase.records) is tuple,
        "AUTHORITY_ACTUAL_PHASE_REQUIRED")
    graph = N._history_graph(before, phase)
    context = (CD.authority_post_context if post else CD.authority_pre_context)(value.context_raw)
    caps = (*(context["authorityWindow"][name] for name in CD.FINAL_AUTHORITY_CAP_FIELDS[:3]), *value.phase)
    require(owner.read(private, "context.json") == value.context_raw, "AUTHORITY_CONTEXT_REREAD")
    source = N.source_readback(owner, private.path / "source-before", before)
    C._collect_query_index(private.path / "source-before", before.session, source, context["observed"], source=before)
    service = owner.child(private, "service")
    for name, raw in phase.records:
        maximum = B.ACK_LIMIT if name == "stdout.log" else B.STDERR_LIMIT if name == "stderr.log" else CD.LIMIT
        require(owner.read(service, name, maximum) == raw, "AUTHORITY_PHASE_REREAD")
    child_raw = owner.read(service, "child-result.json")
    parsed = _phase_closed(value.context_raw, dict(phase.records), child_raw, caps, basis.first, basis.boot,
        tuple(private.identity), tuple(service.identity), state.handoff.identity.original_event, private.path, post=post)
    _context, start, row, birth, child, ack = parsed
    queries = owner.open(private.path / "acquisition-queries")
    session = N.query_session(owner, queries)
    originals = tuple((name, owner.read(queries, name + ".bin")) for name in N.ORIGINAL_KEYS)
    raw = dict(originals)
    require(child["querySessionSha256"] == O.digest(session) and child["originalsSha256"] ==
        {name: O.digest(blob) for name, blob in originals} and child["matchSha256"] == O.digest(raw["match"]) and
        raw["event"] == state.handoff.identity.original_event and raw["match"] == O.encoded(context["expectedMatch"]) and
        {name: raw[name] for name in N.SOURCE_KEYS} == source == dict(state.handoff.source_records),
        "AUTHORITY_ORIGINAL_SOURCE_CHAIN")
    C._collect_query_index(private.path / "acquisition-queries", session, raw, context["observed"])
    match, service_time = N.retained_match(context, raw, start["invocation"], basis.first.clock, caps[3], caps[4])
    captured = (value.context_raw, originals, start["invocation"], caps[3], caps[4])
    require(match.record == raw["match"] and list(N._service_job(captured, basis.first.clock)) ==
        context["history"]["serviceJob"], "AUTHORITY_CURRENT_JOB")
    identity = N.initial_identity.bind_worker_match(match, event_raw=raw["event"], policy_raw=raw["candidate_policy_raw"],
        now=int(time.time()))
    require(D.worker_values(identity) == D.worker_values(state.handoff.identity), "AUTHORITY_CURRENT_IDENTITY")
    minimum = N._service_chain_minimum(basis.first.nanoseconds, context["sourceReturnedNs"], start, row, birth,
        child, service_time, ack)
    checked = state.clock.now(minimum=minimum)
    N._check_history(graph)
    owner.check()
    chain = {"phaseSha256": {name: O.digest(blob) for name, blob in phase.records},
        "childSha256": O.digest(child_raw), "querySessionSha256": O.digest(session),
        "originalsSha256": {name: O.digest(blob) for name, blob in originals}, "checkedNs": checked}
    return identity, match, captured, chain, child_raw, session


def _authority_inventory(owner, path, context_raw, originals, before, after, captured, session, *, post):
    available = dict(originals)
    indexed, directories = [], [path, path / "control-home", path / "temporary", path / "service"]
    context = CD.canonical(context_raw)
    for side, source, session_raw, raw in (("source-before", before, before.session, dict(before.records)),
            ("acquisition-queries", None, session, dict(captured[1])),
            ("source-after", after, after.session, dict(after.records))):
        rows, paths = C._collect_query_index(path / side, session_raw, raw, context["observed"], source=source)
        indexed.extend(rows)
        directories.extend(paths)
    names = ("context.json", *("service/" + name for name in sorted(B.PHASE_FILES)), "service/child-result.json")
    if not post:
        names = (*names, "authority-window.json", "authority-pending.json")
    for name in names:
        raw = available[name]
        maximum = B.ACK_LIMIT if name == "service/stdout.log" else B.STDERR_LIMIT if name == "service/stderr.log" else CD.LIMIT
        require(len(raw) <= maximum, "AUTHORITY_ORIGINAL_LIMIT")
        indexed.append((path / name, maximum, len(raw), O.digest(raw)))
    require(len(indexed) == len({target for target, *_ in indexed}) == (279 if post else 281) and
        len(directories) == len(set(directories)) == 58, "AUTHORITY_COMPLETE_DECLARATIONS")
    pins = N._worker_pins(owner, owner.first.clock.role, {".": path, **{name: path / name for name in
        ("control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries")}})
    identities = {name: identity for name, _row, _directory, _path, identity in pins}
    files = []
    for target, maximum, count, checksum in sorted(indexed):
        name = target.relative_to(path).as_posix()
        require(name not in available or (len(available[name]), O.digest(available[name])) == (count, checksum),
            "AUTHORITY_ORIGINAL_DECLARATION_JOIN")
        files.append({"relative": name, "maximum": maximum, "bytes": count, "sha256": checksum,
            "provenance": "ACTUAL_RETAINED_BYTES" if name in available else "ORIGINAL_QUERY_DECLARATION"})
    require(len(identities) == 7 and len(available) == (36 if post else 38) and
        sum(row["bytes"] for row in files) <= CD.MAX_BYTES, "AUTHORITY_INDEX_BOUND")
    dirs = [{"relative": "." if target == path else target.relative_to(path).as_posix(),
        "identity": None if ("." if target == path else target.relative_to(path).as_posix()) not in identities else
            list(identities["." if target == path else target.relative_to(path).as_posix()]),
        "provenance": "ORIGINAL_NATIVE_PIN" if ("." if target == path else target.relative_to(path).as_posix()) in identities
            else "ORIGINAL_QUERY_DECLARATION"} for target in sorted(directories)]
    raw = O.encoded({"schema": 1, "scope": CD.POST_AUTHORITY_INDEX_SCOPE if post else CD.PRE_AUTHORITY_INDEX_SCOPE,
        "edge": "POST_EXPORT" if post else "PRE_EXPORT", "root": str(path), "clock": O.clock_value(owner.first.clock),
        "contextSha256": O.digest(context_raw), "pendingSha256": None if post else O.digest(available["authority-pending.json"]),
        "files": files, "directories": dirs, "fileCount": len(files), "directoryCount": len(dirs),
        "retainedOriginalCount": len(available), "totalBytes": sum(row["bytes"] for row in files),
        "copyState": "ORIGINAL_BYTES_NOT_COPIED", "writerReturn": CD.PENDING,
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
    CD.canonical(raw)
    return raw, pins


def _predecessor(state, *, post):
    if post:
        return _collect_predecessor(state)
    claims = CD.canonical(state.claims_raw)
    reference = CD.canonical(state.handoff.raw)["references"]["prefixRetention"]
    return {"producerStepOutcome": claims["PRODUCER_OUTCOME"], "producerHandoffSha256": claims["HANDOFF_SHA256"],
        "producerReturnSha256": claims["PRODUCER_RETURN_SHA256"], "afterSaveStepOutcome": claims["AFTER_SAVE_OUTCOME"],
        "afterSaveSha256": claims["AFTER_SAVE_SHA256"], "afterProbeStepOutcome": claims["AFTER_PROBE_OUTCOME"],
        "probeSha256": claims["PROBE_SHA256"], "prefixRetentionSha256": reference["files"]["retention-index.json"]["sha256"]}


def _acquire_authority(state, token, *, post):
    owner = None
    try:
        _environment(state)
        require(type(post) is bool and type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) is not None and
            state.authority is None and state.handoff is not None, "AUTHORITY_ORIGINAL_ENTRY")
        basis = _clock(state.clock)
        require(basis.names[basis.phase][0] == ("ciphertext-verify" if post else "custody-freeze"), "AUTHORITY_PHASE_POSITION")
        authority_first = state.clock.now()
        authority_work = authority_final = basis.ends[basis.phase]
        fence = _span(state.clock, authority_work, authority_final, "authority-post" if post else "authority-pre")
        seed = _native_seed(state, "authority-post" if post else "authority-pre", fence)
        _update(state, authority_seed=seed)
        owner = C._ProductiveNativeOwner(seed)
        root = owner.open(_froot())
        private = owner.child(root, "authority-post-export" if post else "authority-pre-export", create=True)
        owner.child(private, "control-home", create=True)
        owner.child(private, "temporary", create=True)
        history = CD.canonical(state.handoff.history)
        original_proposal = D.original_proposal(state.handoff.proposal, state.handoff.identity,
            state.handoff.history, basis.first.clock)
        window = {"schema": 1, "scope": CD.AUTHORITY_POST_WINDOW_SCOPE if post else CD.AUTHORITY_PRE_WINDOW_SCOPE,
            "clock": O.clock_value(basis.first.clock), "originalBootDigest": basis.boot,
            "originalJobBasisNs": history["originalJobBasisNs"], "originalProposalSha256": O.digest(state.handoff.proposal),
            "phase": basis.names[basis.phase][0], "phaseFirstNs": basis.started[basis.phase][0],
            "phaseEndNs": basis.ends[basis.phase], "authorityFirstNs": authority_first,
            "authorityWorkEndNs": authority_work, "authorityFinalEndNs": authority_final,
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        before = N.source_queries(owner, fence, history["observed"], private.path / "source-before")
        require(N.source_readback(owner, private.path / "source-before", before) == dict(state.handoff.source_records),
            "AUTHORITY_SOURCE_BEFORE_CHANGED")
        context = {"schema": 1, "scope": CD.AUTHORITY_POST_CONTEXT_SCOPE if post else CD.AUTHORITY_PRE_CONTEXT_SCOPE,
            "edge": "POST_EXPORT" if post else "PRE_EXPORT", "kind": "worker", "root": str(ROOT),
            "session": str(private.path), "job": uuid.uuid4().hex, "observed": history["observed"], "history": history,
            "originalProposal": original_proposal, "expectedMatch": CD.canonical(state.handoff.identity.record)["initialRecipient"],
            "eventSha256": O.digest(state.handoff.identity.original_event), "authorityWindow": window,
            "sourceReturnSha256": O.digest(before.raw), "sourceReturnedNs": CD.canonical(before.raw)["returnedNs"],
            "inheritedContext": Q._inherited_context(), "directoryIdentity": list(private.identity),
            "predecessor": _predecessor(state, post=post), "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        context_raw = O.encoded(context)
        (CD.authority_post_context if post else CD.authority_pre_context)(context_raw)
        owner.write(private, "context.json", context_raw)
        if not post:
            owner.write(private, "authority-window.json", window)
        native_state = _native_state(seed)
        _update(native_state, private=private, context_raw=context_raw, before=before)
        bridge = N._productive_authority_post_phase if post else N._productive_authority_pre_phase
        _directory, phase = bridge(seed, owner, private, context_raw, token, fence, before)
        token = None
        require(owner.phase_originals is phase, "AUTHORITY_PHASE_RETURN_NOT_ORIGINAL")
        initial = _authority_read(state, seed)
        after = N.source_queries(owner, fence, history["observed"], private.path / "source-after")
        require(N.source_readback(owner, private.path / "source-after", after) == dict(before.records), "AUTHORITY_SOURCE_AFTER_CHANGED")
        identity, match, captured, chain, child_raw, session = _authority_read(state, seed)
        require(captured == initial[2] and identity.record == initial[0].record and match.record == initial[1].record,
            "AUTHORITY_RETURN_CHANGED")
        chain["sourceAfterSha256"] = O.digest(after.raw)
        # Build explicit immutable originals; no query declaration is a read.
        originals = [("context.json", context_raw), ("service/child-result.json", child_raw),
            ("acquisition-queries/session-result.json", session)]
        originals.extend(("service/" + name, raw) for name, raw in phase.records)
        originals.extend(("acquisition-queries/" + name + ".bin", raw) for name, raw in captured[1])
        for name, source in (("source-before", before), ("source-after", after)):
            originals.extend(((name + "/source-return.json", source.raw), (name + "/session-result.json", source.session)))
            originals.extend((name + "/" + key + ".bin", raw) for key, raw in source.records)
        if not post:
            originals.append(("authority-window.json", O.encoded(window)))
            pending_raw = owner.write(private, "authority-pending.json", {"schema": 1, "scope": CD.AUTHORITY_PENDING_SCOPE,
                "contextSha256": O.digest(context_raw), "originalChain": chain,
                "filesSha256": {name: O.digest(raw) for name, raw in originals}, "retainedNs": state.clock.now(),
                "retirement": "PENDING_OWNER_CLOSE", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
            originals.append(("authority-pending.json", pending_raw))
        originals = tuple(originals)
        index_raw, directory_pins = _authority_inventory(owner, private.path, context_raw, originals, before, after,
            captured, session, post=post)
        before_pin, after_pin, phase_pin = C._collect_source_pin(before), C._collect_source_pin(after), C._collect_phase_pin(phase)
        match_pin = C._custody_match_pin(match, "worker")
        graphs = (N._history_graph(originals), N._history_graph(identity, match, captured, chain))
        preclose = state.clock.now()
        close = _close_owner(owner)
        closed = state.clock.now(minimum=preclose)
        N._check_worker_pins(directory_pins, basis.first.clock.role, closed=True)
        raw = O.encoded({"schema": 1, "scope": CD.POST_AUTHORITY_RETURN_SCOPE if post else CD.PRE_AUTHORITY_RETURN_SCOPE,
            "edge": "POST_EXPORT" if post else "PRE_EXPORT", "contextSha256": O.digest(context_raw),
            "authorityWindow": window, "predecessor": context["predecessor"], "workerIdentitySha256": O.digest(identity.record),
            "matchSha256": O.digest(match.record), "inventorySha256": O.digest(index_raw),
            "filesSha256": {name: O.digest(blob) for name, blob in originals}, "originalChain": chain,
            "preCloseNs": preclose, "closedNs": closed, "ownerClose": CD.canonical(close.raw),
            "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "writerReturn": CD.PENDING,
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        CD.canonical(raw)
        result = _track(_Authority(state.handle, post, seed, owner, close, before, after, phase, identity, match, captured,
            O.encoded(chain), raw, index_raw, originals, (before_pin, after_pin, phase_pin, match_pin, directory_pins), graphs))
        _AUTHORITIES[id(result)] = result, state.handle
        _update(state, authority=result)
        _checked_authority(result, state)
        return result
    except BaseException as error:
        _abort_owner(owner, error)
        raise _fail(state, error)
    finally:
        token = None


def _checked_authority(result, state, *, retired=False):
    _pin(result)
    saved = _AUTHORITIES.get(id(result))
    require(type(result) is _Authority and type(saved) is tuple and saved[0] is result and saved[1] is state.handle and
        result.parent is state.handle and state.authority is result, "ORIGINAL_AUTHORITY_RETURN")
    _check_owner_close(result.close)
    require(result.close.owner is result.owner and result.owner.phase_originals is result.phase and
        result.owner.initial_sources.get(str(_native_state(result.seed).private.path / "source-before")) is result.before and
        result.owner.initial_sources.get(str(_native_state(result.seed).private.path / "source-after")) is result.after,
        "AUTHORITY_ORIGINAL_SUPPLIERS")
    before, after, phase, match, directories = result.pins
    C._collect_source_current(before)
    C._collect_source_current(after)
    C._collect_phase_current(phase)
    C._custody_match_check(match)
    for graph in result.graphs:
        N._check_history(graph)
    N._check_worker_pins(directories, _clock(state.clock).first.clock.role, closed=True)
    if not retired:
        _environment(state)
        context = CD.canonical(result.captured[0])
        current, _service = N.retained_match(context, dict(result.captured[1]), result.captured[2],
            _clock(state.clock).first.clock, result.captured[3], result.captured[4])
        require(current.record == result.match.record, "AUTHORITY_CURRENT_MATCH_EXPIRED")
        state.clock.now()
    return result


@dataclass(eq=False, repr=False)
class _AckState:
    parent: object
    fence: object
    hard_end: int
    close: object
    calls: int = 0
    busy: bool = False
    failure: object = None


_ACKS = {}


class _ChildAckFence:
    __slots__ = ()

    def now(self, *, final=False, minimum=0, limit=None):
        saved = _ACKS.get(id(self))
        require(type(saved) is _AckState and saved.fence is self, "ACTUAL_ACK_FENCE")
        failed = _FAILURES.get(id(saved))
        if failed is not None:
            raise failed[1]
        try:
            _pin(saved)
            require(not saved.busy and saved.calls < 2 and final is True and type(minimum) is int and minimum == 0 and
                type(limit) is int and limit == saved.hard_end, "ACK_TWO_ORIGINAL_LATE_CHECKS")
            _update(saved, busy=True, calls=saved.calls + 1)
            state = _ack_passive(saved)
            result = state.clock.now(final=True, limit=saved.hard_end)
            _pin(saved)
            if saved.failure is not None:
                raise saved.failure
            require(_ack_passive(saved) is state, "ACK_SAME_CHILD_AFTER_CALLBACK")
            return result
        except BaseException as error:
            raise _fail(saved, error)
        finally:
            _owned_slot(saved, "busy", False)


def _ack_passive(saved):
    state = _state(saved.parent)
    require(state.closed is saved.close, "ACK_ACTUAL_CHILD_CLOSE")
    _check_owner_close(saved.close)
    _environment(state)
    if type(saved.parent) is _AuthorityChild:
        N._check_history(state.auxiliary[0])
        N._check_history(state.auxiliary[1])
        C._custody_match_check(state.auxiliary[2])
        _check_union(state, retired=True)
    else:
        require(type(saved.parent) is ChildFinal and state.validation_completed is not None and
            state.export_completed is not None, "ACK_COMPLETE_CHILD")
        checked_retired_child_validation(saved.parent)
        check_retired_child_archive(state.archive_view)
        for node in state.final_records:
            _node_current(node)
            _check_owner_close(node.provenance.close)
    return state


def _child_ack_fence(state, hard_end):
    require(state.closed is not None and not any(saved.parent is state.handle for saved in _ACKS.values()), "ACK_ONCE")
    _check_owner_close(state.closed)
    result = _ChildAckFence()
    _ACKS[id(result)] = _track(_AckState(state.handle, result, CD.integer(hard_end), state.closed))
    return result


@dataclass(frozen=True, repr=False)
class _SourceFile:
    path: object
    relative: str
    maximum: int
    count: int
    checksum: str
    binding_raw: object
    native: object
    embedded: object
    provenance: str


@dataclass(frozen=True, repr=False)
class _Tree:
    path: object
    files: tuple
    directories: tuple
    exact: bool
    root_native: object
    provenance: str


@dataclass(frozen=True, repr=False)
class _Group:
    parent: object
    ordinal: int
    trees: tuple
    embedded: tuple
    witness: object


@dataclass(frozen=True, repr=False)
class _NodeOrigin:
    parent: object
    label: str
    path: object
    raw: object
    close: object


@dataclass(frozen=True, repr=False)
class _Copied:
    parent: object
    partition: object
    map_raw: bytes
    spec: object
    data_close: object
    map_close: object
    source_nodes: tuple
    snapshots: tuple


_COPIES, _GROUPS, _BUDGETS = {}, {}, {}


@dataclass(eq=False, repr=False)
class _Budget:
    owner: object
    parent: object
    bytes: int = 0
    nodes: int = 0
    observations: int = 0
    purpose: str = "archive"


def _charge(owner, count=0, nodes=0):
    require(type(count) is int and count >= 0 and type(nodes) is int and nodes >= 0, "NATIVE_OBSERVATION_CHARGE")
    saved = _BUDGETS.get(id(owner))
    require(type(saved) is _Budget and saved.owner is owner, "ORIGINAL_COPY_BUDGET")
    _pin(saved)
    state = _state(saved.parent)
    total, number = saved.bytes + count, saved.nodes + nodes
    require(saved.purpose in ("archive", "ciphertext") and
        total <= (B.posix.MAX_CIPHERTEXT_BYTES if saved.purpose == "ciphertext" else CD.MAX_BYTES) and
        number <= CD.MAX_NODES, "ORIGINAL_PER_OWNER_CAP")
    _update(saved, bytes=total, nodes=number, observations=saved.observations + 1)
    _update(state, total_bytes=state.total_bytes + count, total_nodes=state.total_nodes + nodes)


def _native_from_metadata(row):
    data = CD.canonical(row[4])
    if "posixStamp" in data:
        result = ("posix", *data["posixStamp"])
    else:
        result = ("windows", *data["identity"], data["is_directory"], data["size"], data["links"], data["attributes"],
            data["creation_100ns"], data["modified_100ns"], data["change_100ns"], data["owner_sid"], data["protected_dacl"])
    return CD.native(result, directory=row[1])


def _native_from_info(info):
    require(type(info) is B.windows.FileInfo, "WINDOWS_ACTUAL_INFO")
    return CD.native(("windows", *info.identity, info.is_directory, info.size, info.links, info.attributes,
        info.creation_100ns, info.modified_100ns, info.change_100ns, info.owner_sid, info.protected_dacl),
        directory=info.is_directory)


def _file_binding(stamp):
    if stamp[0] == "posix":
        data = {"identity": list(stamp[1:3]), "is_directory": stat.S_ISDIR(stamp[3]), "size": stamp[6],
            "mode": stamp[3], "uid": stamp[4], "links": stamp[5], "mtime_ns": stamp[7], "ctime_ns": stamp[8]}
    else:
        data = {"identity": list(stamp[1:3]), "is_directory": stamp[3], "size": stamp[4], "links": stamp[5],
            "attributes": stamp[6], "creation_100ns": stamp[7], "modified_100ns": stamp[8], "change_100ns": stamp[9],
            "owner_sid": stamp[10], "protected_dacl": stamp[11]}
    return {"identity": list(stamp[1:3]), "stampSha256": A.F.digest(A.F.encoded(data))}


def _directory_stamp(directory):
    info = directory.verify()
    if os.name == "nt":
        stamp = _native_from_info(info)
    else:
        stamp = CD.native(("posix", *B.posix._stamp(os.stat(directory.path, follow_symlinks=False))), directory=True)
        require(stamp[1:3] == tuple(directory.identity), "DIRECTORY_ACTUAL_LINK")
    require(stamp[1:3] == tuple(directory.identity), "DIRECTORY_ACTUAL_IDENTITY")
    return stamp


def _origin(state, label, path, raw, close=None):
    value = _track(_NodeOrigin(state.handle, label, path, raw, close))
    _PROVENANCE[id(value)] = value
    return value


def _expected(state, relative, stamp, *, count=None, checksum=None, path=None, raw=None, close=None):
    directory = count is None
    CD.native(stamp, directory=directory)
    value = _track(ExpectedNode(CD.relative(relative, empty=True), "directory" if directory else "file", count, checksum,
        stamp, _origin(state, "ACTUAL_NATIVE_OBSERVATION", path, raw, close)))
    _node_current(value)
    return value


def _data_node(node):
    _node_current(node)
    return {"relative": node.relative, "kind": node.kind, "bytes": node.bytes,
        "sha256": node.sha256, "native": list(node.native)}


def _source_file(path, relative, maximum, count, checksum, provenance, *, binding=None, native=None, embedded=None):
    CD.relative(relative)
    CD.integer(maximum, 1, CD.MAX_BYTES)
    CD.integer(count, 0, maximum)
    CD.sha(checksum)
    require(type(provenance) is str and 0 < len(provenance) <= 256, "SOURCE_PROVENANCE")
    if embedded is not None:
        require(path is None and type(embedded) is bytes and len(embedded) == count and O.digest(embedded) == checksum,
            "ACTUAL_EMBEDDED_ORIGINAL")
    else:
        require(type(path) is type(ROOT) and path.is_absolute() and ".." not in path.parts, "FIXED_SOURCE_PATH")
    if native is not None:
        CD.native(native, directory=False)
    return _track(_SourceFile(path, relative, maximum, count, checksum,
        None if binding is None else O.encoded(binding), native, embedded, provenance))


def _tree(path, files, directories, provenance, *, exact=True, root_native=None):
    require(type(path) is type(ROOT) and path.is_absolute() and type(files) is tuple and type(directories) is tuple and
        type(exact) is bool and all(type(row) is _SourceFile and row.embedded is None for row in files), "FIXED_SOURCE_TREE")
    names = [row.relative for row in files]
    require(len(names) == len(set(names)) == len({name.casefold() for name in names}) and
        all(row.path == path / row.relative for row in files), "SOURCE_FIXED_ROSTER")
    for relative, pin in directories:
        CD.relative(relative, empty=True)
        if pin is not None:
            B.directory_identity(list(pin), B.processes.host_role())
    require(directories and directories[0][0] == "" and len({name for name, _pin in directories}) == len(directories),
        "SOURCE_DIRECTORY_ROSTER")
    return _track(_Tree(path, files, directories, exact, root_native, provenance))


def _indexed_tree(path, index, provenance):
    files = tuple(_source_file(path / row["relative"], row["relative"], row["maximum"], row["bytes"], row["sha256"],
        row["provenance"]) for row in index["files"])
    directories = tuple(("" if row["relative"] == "." else row["relative"],
        None if row["identity"] is None else tuple(row["identity"])) for row in index["directories"])
    return _tree(path, files, directories, provenance)


def _group(state, ordinal, trees, witness, embedded=()):
    require(type(ordinal) is int and 1 <= ordinal <= 30 and type(trees) is tuple and type(embedded) is tuple and
        (trees or embedded) and all(type(tree) is _Tree for tree in trees) and
        all(type(row) is _SourceFile and row.embedded is not None for row in embedded), "FIXED_GROUP_SPEC")
    value = _track(_Group(state.handle, ordinal, trees, embedded, witness))
    _GROUPS[id(value)] = value
    return value


def _selected_from_reader(reader, keys, maxima, extra_directories=()):
    grouped = {}
    large = {(path, name): (count, checksum, binding) for path, name, count, checksum, binding in reader.large}
    for path, name in keys:
        if (path, name) in large:
            count, checksum, binding_raw = large[path, name]
            binding = CD.canonical(binding_raw)
        else:
            require((path, name) in reader.files, "ORIGINAL_SELECTED_READER_FILE")
            raw, binding, _old_maximum = reader.files[path, name]
            count, checksum = len(raw), O.digest(raw)
        maximum = maxima.get((path, name), CD.LIMIT)
        require(path in reader.directories, "ORIGINAL_SELECTED_READER_DIRECTORY")
        grouped.setdefault(path, []).append(_source_file(path / name, name, maximum, count, checksum,
            "AUTHENTIC_ORIGINAL_STEP_NATIVE_CARRIER", binding=binding))
    for path in extra_directories:
        require(path in reader.directories, "ORIGINAL_SELECTED_METADATA_DIRECTORY")
        grouped.setdefault(path, [])
    return tuple(_tree(path, tuple(files), (("", reader.directories[path][2]),),
        "SELECTED_ORIGINAL_FILES_NOT_WHOLE_EVOLVING_TREE", exact=False) for path, files in sorted(grouped.items()))


def _parent_specs(state):
    inputs = A.checked_final_productive_inputs(state.inputs)
    handoff, derived = inputs.handoff, inputs.derived
    reader = A._checked_handoff(handoff)
    blobs = dict(handoff.blobs)
    uses = {row["site"]: row for row in inputs.use_rows}
    require(tuple(sorted(uses)) == tuple(sorted(CD.USE_SITES)), "FIXED21_AUTHENTIC_USES")
    specs = [_group(state, ordinal, (_indexed_tree(P._path(site), uses[site]["inventory"],
        "ACTUAL_FINAL_COPY_OF_HISTORICAL281"),), uses[site]) for ordinal, site in enumerate(CD.USE_SITES, 1)]
    prefix_path = C._paths("worker")[2] / "productive-prefix"
    prefix_raws = {name: reader.files[prefix_path, name][0] for name in D.PREFIX_FILES}
    primary = CD.canonical(prefix_raws["primary-map.json"])
    primary_path = C._paths("worker")[2] / "copied-evidence"
    source_files = []
    for ordinal, row in enumerate(primary["members"]):
        metadata = primary["destinationMetadata"][ordinal + 1]
        native = _native_from_metadata((*metadata[:4], O.encoded(metadata[4])))
        maximum = row.get("originalMaximum", CD.LIMIT)
        source_files.append(_source_file(primary_path / row["member"], row["member"], maximum, row["bytes"], row["sha256"],
            "AUTHENTIC_EARLY_FLAT_COPY_" + row["carrier"], native=native))
    root_metadata = primary["destinationMetadata"][0]
    specs.append(_group(state, 22, (_tree(primary_path, tuple(source_files), (("", tuple(primary["destinationIdentity"])),),
        "AUTHENTIC_EARLY_COPY_NOT_EVOLVED_PRIMARY", root_native=_native_from_metadata((*root_metadata[:4], O.encoded(root_metadata[4])))),),
        prefix_raws["primary-map.json"]))
    keys = tuple((prefix_path, name) for name in D.PREFIX_FILES)
    specs.append(_group(state, 23, _selected_from_reader(reader, keys,
        {(prefix_path, "retention-index.json"): CD.PUBLIC_LIMIT}), prefix_raws["retention-index.json"]))
    old_authority = CD.canonical(prefix_raws["authority-index.json"])
    specs.append(_group(state, 24, (_indexed_tree(C._paths("worker")[2] / "authority-1", old_authority,
        "HISTORICAL_AUTHORITY38_PLUS281_DECLARATIONS_FULLY_COPIED_NOW"),), prefix_raws["authority-index.json"]))
    initial = handoff.initializer
    keys = [(initial / "dependency-save-handoff", name) for name in (*D.BLOB_NAMES, "save-handoff.json")]
    keys.append((initial, "producer-function-return.json"))
    keys.extend((initial.joinpath(*name.split("/")[1:-1]), name.split("/")[-1]) for name in D.INITIALIZER_FILES)
    keys.extend(((derived.inputs.container, "staging.json"), (initial / "configuration-custody", "request.json")))
    for ordinal in range(1, 9):
        path = initial / ("initial-product-" + str(ordinal).zfill(2))
        names = ("command.json", "request.json", "outer-start.json", "baseline.json", "native-start.json",
            "native-result.json", "canonical-observation.json", "stdout.log", "stderr.log") if ordinal == 4 else ("leaf-return-pending.json",)
        keys.extend((path, name) for name in names)
    step_names = {
        "prepare-save": (*D.STEP_USE_FILES, "save-preparation.json", "provider-prepared.json", "provider-readback.json"),
        "prepare-probe": (*D.STEP_USE_FILES, "probe-preparation.json", "provider-prepared.json", "provider-readback.json"),
        "after-save": (*D.AFTER_SAVE_FILES, "save-observations.json", "after-save-return.json"),
        "after-probe": (*D.STEP_USE_FILES, "probe-preparation.json", "provider-probe.json", "readmission-close.json",
            "provider-prepared.json", "provider-readback.json", "probe-result.json"),
    }
    for operation, names in step_names.items():
        path = A._step_path(operation)
        keys.extend((path, name) for name in names)
        if operation in ("prepare-save", "prepare-probe"):
            keys.extend((path / "native-preparation", name) for name in
                ("initial-use-chain.json", "begin-use.json", "begin-use-index.json", "final-use.json", "final-use-index.json"))
    require(len(keys) == len(set(keys)) == 114, "EXACT114_PRODUCTIVE_NATIVE_FILES")
    maxima = {(path, name): 16384 for path, name in keys if name in ("provider-prepared.json", "provider-readback.json")}
    maxima.update({(initial / "canonical-init", "stdout.log"): 16384,
        (initial / "canonical-init", "stderr.log"): 65536, (initial / "state" / "gradle-home", "gradle.properties"): 16384,
        (initial / "initial-product-04", "stdout.log"): 67174400, (initial / "initial-product-04", "stderr.log"): 67174400})
    extra = tuple(initial.joinpath(*name.split("/")[1:]) for name in D.INITIALIZER_DIRECTORIES) + (derived.inputs.restore,)
    specs.append(_group(state, 25, _selected_from_reader(reader, tuple(keys), maxima, extra), inputs))
    request = A.producer.parse(blobs["producer-request.json"])
    source = initial / "state" / "evidence" / request["id"]
    specs.append(_group(state, 26, _selected_from_reader(reader, tuple((source, name) for name in A.collection.METADATA),
        {(source, name): 4 * 1024 * 1024 for name in A.collection.METADATA}), blobs["collection-leaf.json"]))
    collection = CD.canonical(blobs["collection-leaf.json"])
    retained = initial / "configuration-custody" / "retained"
    require(collection["retainedDirectory"] == str(retained) and collection["sourceDirectory"] == str(source) and
        collection["collectionState"] == "COPIED_AND_READ_BACK" and collection["completed"] is True and
        collection["leafHandleClose"] == "KNOWN", "AUTHENTIC_CONFIGURATION_COPY")
    files, directories = [], {""}
    inventory = CD.canonical(blobs["collection-inventory.json"])
    reports = {row["path"] for row in inventory["retainedReports"]}
    allowed = {*A.collection.METADATA, *A.collection.inventory.LOGS, *reports}
    require(len(collection["files"]) == len(allowed) == 7 + len(reports), "COMPLETE_CONFIGURATION_RETAINED_ROSTER")
    for row in collection["files"]:
        name = CD.relative(row["path"])
        require(name in allowed, "CONFIGURATION_SELECTED_REPORT")
        maximum = A.collection.inventory.METADATA_BYTES if name in A.collection.METADATA else (
            A.collection.inventory.LOG_BYTES if name in A.collection.inventory.LOGS else A.collection.inventory.REPORT_BYTES)
        files.append(_source_file(retained / name, name, maximum, row["bytes"], row["sha256"],
            "AUTHENTIC_COLLECTION_DESTINATION_HISTORICAL_SOURCE_BINDING", binding=row["destinationBinding"]))
        parts = name.split("/")[:-1]
        directories.update("/".join(parts[:n]) for n in range(1, len(parts) + 1))
    root_pin = tuple(collection["directoryBindings"]["destination"])
    specs.append(_group(state, 27, (_tree(retained, tuple(sorted(files, key=lambda row: row.relative)),
        tuple((name, root_pin if name == "" else None) for name in sorted(directories)),
        "COMPLETE_RETAINED_CONFIGURATION_NOT_SOURCE_RECOPY"),), blobs["collection-leaf.json"]))
    authority = _checked_authority(state.authority, state)
    specs.append(_group(state, 28, (_indexed_tree(_froot() / "authority-pre-export", CD.canonical(authority.index_raw),
        "NEW_GENUINE_PRE_AUTHORITY281_FULL_NATIVE_COPY"),), authority))
    require(len(specs) == 28 and all(spec.ordinal == ordinal for ordinal, spec in enumerate(specs, 1)), "PARENT28_ONLY")
    _update(state, specs=tuple(specs))
    return state.specs


def _selected_reader(owner, directory, source):
    path = directory.path / source.relative
    require(path == source.path and "/" not in source.relative, "SELECTED_FIXED_NATIVE_PATH")
    end = owner.guard()
    if os.name == "nt":
        reader = owner.acquire("reader", lambda: directory.open_file(source.relative, max_bytes=source.maximum, deadline=end))
        original = reader.initial_info
        stamp = _native_from_info(original)
        def verify():
            require(reader.verify() == original, "SELECTED_WINDOWS_FULL_BINDING")
    else:
        reader = owner.acquire("reader", lambda: C.Q._posix_stream(path, os.O_RDONLY | os.O_NOFOLLOW, "rb"))
        Q._file_info(path, reader, source.maximum)
        stamp = CD.native(("posix", *B.posix._stamp(os.fstat(reader.fileno()))), directory=False)
        def verify():
            Q._file_info(path, reader, source.maximum)
            require(("posix", *B.posix._stamp(os.fstat(reader.fileno()))) == stamp and
                ("posix", *B.posix._stamp(os.stat(path, follow_symlinks=False))) == stamp, "SELECTED_POSIX_FULL_BINDING")
            directory.verify()
    require(source.count == stamp[6 if stamp[0] == "posix" else 4] <= source.maximum and
        (source.native is None or source.native == stamp) and
        (source.binding_raw is None or CD.canonical(source.binding_raw) == _file_binding(stamp)), "ORIGINAL_SELECTED_NATIVE_BINDING")
    verify()
    return reader, verify, stamp


def _write_fixed(state, path, name, raw, maximum=CD.LIMIT):
    """One actual writer, close, independent complete native reread and owner close."""
    require(type(raw) is bytes and 0 < len(raw) <= maximum <= CD.LIMIT, "FIXED_RECORD_BOUND")
    owner = _file_owner(state)
    try:
        directory = C._private(owner, path)
        _charge(owner, nodes=1)
        writer = owner.acquire("writer", lambda: directory.create_file(name, max_bytes=len(raw), deadline=owner.guard()))
        owner.guard()
        require(writer.write(raw) == len(raw), "FIXED_RECORD_SHORT_WRITE")
        _charge(owner, len(raw), 1)
        owner.guard()
        writer.sync()
        info = writer.verify()
        written_raw = O.encoded(info.as_dict())
        require(info.size == len(raw), "FIXED_RECORD_WRITER_SIZE")
        owner.close_one(writer)
        source = _source_file(path / name, name, maximum, len(raw), O.digest(raw), "ACTUAL_NEW_WRITER")
        reader, verify, stamp = _selected_reader(owner, directory, source)
        _charge(owner, len(raw), 1)
        readback = C._consume(owner, reader, len(raw), O.digest(raw), verify, retain=True)
        require(readback == raw, "FIXED_RECORD_COMPLETE_READBACK")
        node = (name, False, stamp[1:3], len(raw), O.encoded({"posixStamp": list(stamp[1:])}) if stamp[0] == "posix" else
            O.encoded({"identity": list(stamp[1:3]), "is_directory": False, "size": stamp[4], "links": stamp[5],
                "attributes": stamp[6], "creation_100ns": stamp[7], "modified_100ns": stamp[8], "change_100ns": stamp[9],
                "owner_sid": stamp[10], "protected_dacl": stamp[11]}))
        C._written_matches(written_raw, node, os.name == "nt")
        close = _close_owner(owner)
        result = _expected(state, name, stamp, count=len(raw), checksum=O.digest(raw), path=path / name, raw=raw, close=close)
        _update(state, union=(*state.union, (path / name, stamp)))
        return result, close
    except BaseException as error:
        _abort_owner(owner, error)
        raise _fail(state, error)


def _copy_group(state, spec):
    child = type(state.handle) is ChildFinal
    require(_GROUPS.get(id(spec)) is spec and spec.parent is state.handle and
        spec.ordinal == (29 + len(state.copied) if child else len(state.partitions) + 1) and
        (not child or not state.partitions and spec.ordinal in (29, 30)), "FIXED_NEXT_GROUP")
    _pin(spec)
    owner = _file_owner(state)
    rows, source_nodes, snapshots = [], [], []
    group = CD.GROUPS[spec.ordinal - 1]
    path = _path(state, "payload") / group
    try:
        destination = C._private(owner, path, create=True)
        _charge(owner, nodes=1)
        for tree in spec.trees:
            _pin(tree)
            directory = C._private(owner, tree.path)
            _charge(owner, nodes=1)
            source = None
            if tree.exact:
                source = C._snapshot(owner, "SOURCE_" + group, directory)
                snapshots.append(source)
                _charge(owner, sum(row[3] for row in source.metadata if not row[1]), len(source.metadata))
                native_rows = {row[0]: row for row in source.metadata}
                require(set(native_rows) == {row.relative for row in tree.files} | {name for name, _pin_ in tree.directories},
                    "EXACT_SOURCE_TREE_ROSTER")
                for name, identity in tree.directories:
                    row = native_rows[name]
                    require(row[1] and (identity is None or row[2] == identity), "SOURCE_ORIGINAL_DIRECTORY_PIN")
                    source_nodes.append((tree.path / name, _native_from_metadata(row), tree.provenance))
                if tree.root_native is not None:
                    require(_native_from_metadata(native_rows[""]) == tree.root_native, "AUTHENTIC_RETAINED_ROOT_FULL_BINDING")
            else:
                require(len(tree.directories) == 1 and tuple(directory.identity) == tree.directories[0][1], "SELECTED_ROOT_PIN")
                source_nodes.append((tree.path, _directory_stamp(directory), tree.provenance))
            for member in tree.files:
                _pin(member)
                _charge(owner, 2 * member.count, 2)
                if source is not None:
                    node = native_rows[member.relative]
                    stamp = _native_from_metadata(node)
                    require(not node[1] and node[3] == member.count and
                        (member.native is None or member.native == stamp) and
                        (member.binding_raw is None or CD.canonical(member.binding_raw) == _file_binding(stamp)),
                        "COPY_AUTHENTIC_SOURCE_BINDING")
                    target, written = C._copy_member(owner, destination, len(rows), member.count, member.checksum,
                        snapshot=source, name=member.relative)
                else:
                    reader, verify, stamp = _selected_reader(owner, directory, member)
                    target = CD.member_name(len(rows))
                    writer = owner.acquire("writer", lambda: destination.create_file(target, max_bytes=member.count,
                        deadline=owner.guard()))
                    checksum, written = C._consume(owner, reader, member.count, member.checksum, verify, writer=writer)
                    require(checksum == member.checksum, "COPY_SELECTED_HASH")
                source_nodes.append((member.path, stamp, member.provenance))
                rows.append((member, target, stamp, written))
            if source is not None:
                repeated = C._snapshot(owner, "SOURCE_RECHECK_" + group, directory)
                _charge(owner, sum(row[3] for row in repeated.metadata if not row[1]), len(repeated.metadata))
                require(repeated.metadata == source.metadata, "FULL_SOURCE_RECHECK_CHANGED")
                snapshots.append(repeated)
            else:
                require(_directory_stamp(directory) == source_nodes[-len(tree.files) - 1][1], "SELECTED_SOURCE_DIRECTORY_CHANGED")
        for member in spec.embedded:
            _pin(member)
            _charge(owner, 2 * member.count, 2)
            target, written = C._copy_member(owner, destination, len(rows), member.count, member.checksum, embedded=member.embedded)
            rows.append((member, target, None, written))
        after = C._snapshot(owner, "DESTINATION_" + group, destination)
        snapshots.append(after)
        _charge(owner, sum(row[3] for row in after.metadata if not row[1]), len(after.metadata))
        require(tuple(row[0] for row in after.metadata) == ("", *(CD.member_name(n) for n in range(len(rows)))) and
            all(not row[1] for row in after.metadata[1:]), "FLAT_GROUP_EXACT_ROSTER")
        for (_source, target, _stamp, written), node in zip(rows, after.metadata[1:]):
            C._written_matches(written, node, after.windows)
            reader, verify = C._snapshot_reader(owner, after, target)
            _charge(owner, _source.count, 1)
            C._consume(owner, reader, _source.count, _source.checksum, verify)
        close = _close_owner(owner)
        root = _expected(state, group, _native_from_metadata(after.metadata[0]), path=path, close=close)
        nodes = tuple(_expected(state, group + "/" + target, _native_from_metadata(node), count=member.count,
            checksum=member.checksum, path=path / target, close=close) for (member, target, _stamp, _written), node in zip(rows, after.metadata[1:]))
        mapped = []
        for index, ((member, _target, stamp, written), node) in enumerate(zip(rows, nodes)):
            mapped.append({"ordinal": index, "source": member.relative if member.embedded is not None else str(member.path),
                "sourceKind": "embedded-not-disk" if member.embedded is not None else "native-file",
                "maximum": member.maximum, "bytes": member.count, "sha256": member.checksum,
                "sourceNative": None if stamp is None else list(stamp), "writerNative": CD.canonical(written),
                "destination": _data_node(node), "provenance": member.provenance})
        map_raw = O.encoded({"schema": 1, "scope": CD.MAP_SCOPE, "ordinal": spec.ordinal, "group": group,
            "root": _data_node(root), "members": mapped, "sourceDirectories": [
                {"path": str(source_path), "native": list(stamp), "provenance": provenance}
                for source_path, stamp, provenance in source_nodes
                if (stat.S_ISDIR(stamp[3]) if stamp[0] == "posix" else stamp[3])],
            "dataBytes": sum(member.count for member, *_ in rows), "dataFiles": len(rows),
            "dataOwnerClose": CD.canonical(close.raw), "writerReturn": CD.PENDING,
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        CD.map_record(map_raw, spec.ordinal)
        map_node, map_close = _write_fixed(state, _path(state, "payload"), "map-" + group + ".json", map_raw)
        partition = _track(PartitionView(spec.ordinal, group, root, nodes, map_node))
        copied = _track(_Copied(state.handle, partition, map_raw, spec, close, map_close, tuple(source_nodes), tuple(snapshots)))
        _COPIES[id(partition)] = copied
        _update(state, copied=(*state.copied, copied))
        if not child:
            _update(state, partitions=(*state.partitions, partition))
        _check_union(state)
        return partition
    except BaseException as error:
        _abort_owner(owner, error)
        raise _fail(state, error)


def _check_union(state, *, retired=False):
    """Full immutable native alias reconciliation, never any live I/O on retirement."""
    paths, identities = {}, {}
    def insert(path, stamp):
        require(type(path) is type(ROOT) and path.is_absolute() and ".." not in path.parts, "UNION_CANONICAL_PATH")
        key = str(path)
        folded = key.casefold() if os.name == "nt" else key
        native_key = CD.native_key(stamp)
        require(native_key not in identities or identities[native_key] == folded, "CROSS_PATH_NATIVE_ALIAS")
        require(folded not in paths or paths[folded] == (key, stamp), "SAME_PATH_FULL_BINDING_CHANGED")
        identities[native_key], paths[folded] = folded, (key, stamp)
    for copied in state.copied:
        partition, ordinal = copied.partition, copied.partition.ordinal
        _partition_current(partition, ordinal, whole=True)
        require(_COPIES.get(id(partition)) is copied and type(copied) is _Copied and
            copied.partition is partition and copied.parent is state.handle, "ORIGINAL_PARTITION_COPY")
        _pin(copied)
        _check_owner_close(copied.data_close)
        _check_owner_close(copied.map_close)
        for source_path, stamp, _provenance in copied.source_nodes:
            insert(source_path, stamp)
        for node in (partition.root, *partition.members, partition.map):
            insert(_path(state, "payload") / node.relative, node.native)
        for snapshot in copied.snapshots:
            N._check_history(snapshot.graph)
    for read in state.readback:
        _check_partition_read(read)
        require(read.parent is state.handle, "ORIGINAL_READ30_PARENT")
        partition = read.partition
        for node in (partition.root, *partition.members, partition.map):
            insert(_path(state, "payload") / node.relative, node.native)
        # These source vectors are authenticated historical parent observations,
        # not newly opened child sources, reconstructed copy currency or charges.
        # They still participate in the complete cross-path native alias union.
        mapped = CD.map_record(read.map_raw, partition.ordinal)
        for row in mapped["sourceDirectories"]:
            insert(Path(row["path"]), tuple(row["native"]))
        for row in mapped["members"]:
            if row["sourceKind"] == "native-file":
                insert(Path(row["source"]), tuple(row["sourceNative"]))
    if state.root is not None and type(state.root) is ExpectedNode:
        _node_current(state.root)
        insert(_path(state, "payload"), state.root.native)
    if state.index is not None:
        _node_current(state.index)
        insert(_path(state, "payload") / "copy-index.json", state.index.native)
    # Only immutable source-owned observations, no reopen/clock/root.verify here.
    for path, stamp in state.union:
        insert(path, stamp)
    for observation in state.observations:
        if type(observation) is _FileRead:
            _check_file_read(observation)
        elif type(observation) is _ValidationInventory:
            _pin(observation)
            require(_VALIDATION_INVENTORIES.get(id(observation)) is observation and
                observation.child is state.handle and observation.returned is state.validation_return and
                observation.completion is state.validation_completed, "ORIGINAL_VALIDATION_INVENTORY")
            _check_owner_close(observation.close)
            N._check_history(observation.snapshot.graph)
    for budget in state.accounting:
        _pin(budget)
        require(_BUDGETS.get(id(budget.owner)) is budget and budget.parent is state.handle and
            budget.purpose in ("archive", "ciphertext") and
            budget.bytes <= (B.posix.MAX_CIPHERTEXT_BYTES if budget.purpose == "ciphertext" else CD.MAX_BYTES) and
            budget.nodes <= CD.MAX_NODES, "ORIGINAL_OBSERVATION_ACCOUNTING")
    if state.lineage is not None:
        _pin(state.lineage)
        require(type(state.lineage) is _Lineage and _LINEAGES.get(id(state.lineage)) is state.lineage and
            state.lineage.child is state.handle and state.lineage.reads is state.readback, "ORIGINAL_FINAL_LINEAGE")
        _check_owner_close(state.lineage.metadata_close)
        _check_owner_close(state.lineage.index_close)
    return paths


@dataclass(frozen=True, repr=False)
class _FileRead:
    parent: object
    path: object
    raw: bytes
    native: tuple
    close: object
    directory_native: object = None


@dataclass(frozen=True, repr=False)
class _PartitionRead:
    parent: object
    partition: object
    map_raw: bytes
    records: tuple
    close: object
    snapshots: tuple
    returned_ns: int
    returned_local: float


@dataclass(frozen=True, repr=False)
class _Lineage:
    child: object
    context_raw: bytes
    start_raw: bytes
    inputs_raw: bytes
    pre_index_raw: bytes
    metadata_close: object
    reads: tuple
    index_close: object


_READ_PARTITIONS, _FILE_READS, _LINEAGES = {}, {}, {}


def _names(owner, directory, maximum=64):
    """One bounded nonrecursive listing; no whole payload C/N graph."""
    end = owner.guard()
    directory.verify()
    if os.name == "nt":
        names = directory.names(max_names=maximum, deadline=end)
    else:
        iterator = owner.acquire("reader", lambda: os.scandir(directory.path))
        names = []
        try:
            for entry in iterator:
                owner.guard()
                require(len(names) < maximum, "FIXED_DIRECTORY_MEMBER_BOUND")
                names.append(entry.name)
        finally:
            if not owner.owner.unknown:
                owner.close_one(iterator)
    require(all(type(name) is str and name not in ("", ".", "..") for name in names) and
        len(names) == len({name.casefold() for name in names}), "FIXED_DIRECTORY_NAMES")
    directory.verify()
    owner.guard()
    _charge(owner, nodes=1 + len(names))
    return tuple(sorted(names))


def _read_native(owner, directory, name, maximum, *, expected=None, native=None, public=False):
    require(type(name) is str and "/" not in name and "\\" not in name and
        CD.relative(name) == name and type(maximum) is int and 0 < maximum <= CD.LIMIT and type(public) is bool,
        "FIXED_NATIVE_READ")
    path, end = directory.path / name, owner.guard()
    if os.name == "nt":
        reader = owner.acquire("reader", lambda: directory.open_file(name, max_bytes=maximum, deadline=end))
        original = reader.initial_info
        stamp = _native_from_info(original)
        def verify():
            require(reader.verify() == original, "ACTUAL_READ_WINDOWS_FULL_BINDING")
            directory.verify()
    else:
        reader = owner.acquire("reader", lambda: Q._posix_stream(path, os.O_RDONLY | os.O_NOFOLLOW, "rb"))
        if not public:
            Q._file_info(path, reader, maximum)
        stamp = CD.native(("posix", *B.posix._stamp(os.fstat(reader.fileno()))), directory=False)
        def verify():
            if not public:
                Q._file_info(path, reader, maximum)
            require(("posix", *B.posix._stamp(os.fstat(reader.fileno()))) == stamp and
                ("posix", *B.posix._stamp(os.stat(path, follow_symlinks=False))) == stamp, "ACTUAL_READ_POSIX_FULL_BINDING")
            directory.verify()
    count = stamp[6 if stamp[0] == "posix" else 4]
    require(count <= maximum and (native is None or stamp == native), "ACTUAL_READ_ORIGINAL_NATIVE")
    verify()
    _charge(owner, count, 1)
    raw = C._consume(owner, reader, count, None if expected is None else O.digest(expected), verify, retain=True)
    require(expected is None or raw == expected, "ACTUAL_READ_ORIGINAL_BYTES")
    return raw, stamp


def _read_files(state, selections, *, fence=None):
    owner = _file_owner(state, fence)
    result, directories = [], {}
    try:
        for path, name, maximum, expected, stamp in selections:
            if path not in directories:
                directories[path] = C._private(owner, path)
                if state.context_raw is not None:
                    declared = CD.crypto_context(state.context_raw)["directories"]
                    for key, original_path in state.paths:
                        if original_path == path and key in declared:
                            require(tuple(directories[path].identity) == tuple(declared[key]), "READ_ORIGINAL_CONTROL_ROOT")
                _charge(owner, nodes=1)
            raw, actual = _read_native(owner, directories[path], name, maximum, expected=expected, native=stamp)
            result.append((path / name, raw, actual, _directory_stamp(directories[path])))
        closed = _close_owner(owner)
        reads = tuple(_track(_FileRead(state.handle, path, raw, stamp, closed, directory_native))
            for path, raw, stamp, directory_native in result)
        for read in reads:
            _FILE_READS[id(read)] = read
        _update(state, observations=(*state.observations, *reads),
            union=(*state.union, *((path, stamp) for path, _raw, stamp, _directory_native in result)))
        return reads, closed
    except BaseException as error:
        _abort_owner(owner, error)
        raise _fail(state, error)


def _check_file_read(read):
    _pin(read)
    require(type(read) is _FileRead and _FILE_READS.get(id(read)) is read and type(read.raw) is bytes and
        read.native[6 if read.native[0] == "posix" else 4] == len(read.raw), "ORIGINAL_FILE_READ")
    _check_owner_close(read.close)
    CD.native(read.native, directory=False)
    if read.directory_native is not None:
        CD.native(read.directory_native, directory=True)
    return read


def _actual_host(state, observed, event_raw):
    """Actual bounded public event read/close; cadence checks use pure context."""
    path = Path(os.environ.get("GITHUB_EVENT_PATH", ""))
    require(path.is_absolute() and ".." not in path.parts and os.environ.get("GITHUB_WORKSPACE") == str(ROOT),
        "ACTUAL_HOST_PATH")
    if state.host_path is None:
        _update(state, host_path=path)
    else:
        require(path == state.host_path and os.environ.get("GITHUB_EVENT_PATH") == str(state.host_path),
            "ACTUAL_ORIGINAL_EVENT_PATH")
    previous = next((read for read in state.observations if type(read) is _FileRead and read.path == path), None)
    owner = _file_owner(state)
    try:
        parent = owner.acquire("directory", lambda: A.F.public_root(path.parent))
        _charge(owner, nodes=1)
        raw, stamp = _read_native(owner, parent, path.name, N.I.EVENT_LIMIT, expected=event_raw,
            native=None if previous is None else previous.native, public=True)
        require(N.acquisition._context(dict(os.environ), raw, "worker", observed["firstUseAt"]) == observed and
            observed["role"] == _clock(state.clock).first.clock.role and
            B.processes.host_role() == observed["role"], "ACTUAL_HOST_EVENT_AND_ROLE")
        close = _close_owner(owner)
        read = _track(_FileRead(state.handle, path, raw, stamp, close))
        _FILE_READS[id(read)] = read
        if state.host_event_raw is None:
            _update(state, host_event_raw=raw, host_observed_raw=O.encoded(observed))
        else:
            require(raw == state.host_event_raw and O.encoded(observed) == state.host_observed_raw,
                "ACTUAL_ORIGINAL_EVENT_BYTES")
        _update(state, observations=(*state.observations, read), union=(*state.union, (path, stamp)))
        return read
    except BaseException as error:
        _abort_owner(owner, error)
        raise _fail(state, error)


def _group_reference(partition):
    _partition_current(partition, partition.ordinal, whole=True)
    return {"ordinal": partition.ordinal, "group": partition.group,
        "map": {"name": partition.map.relative, "bytes": partition.map.bytes, "sha256": partition.map.sha256},
        "dataFiles": len(partition.members), "dataBytes": sum(node.bytes for node in partition.members)}


def _partition_read(state, ordinal, expected):
    """One actual planned partition read. No restored parent copy capability."""
    require(type(state.handle) in (ChildFinal, CollectPrepared) and ordinal == len(state.partitions) + 1,
        "ONE_FIXED_READ30_ORDER")
    owner = _file_owner(state)
    snapshots, records = [], []
    group, payload = CD.GROUPS[ordinal - 1], _path(state, "payload")
    try:
        root = C._private(owner, payload)
        directory = C._private(owner, payload / group)
        _charge(owner, nodes=2)
        map_name = "map-" + group + ".json"
        map_raw, map_stamp = _read_native(owner, root, map_name, CD.LIMIT)
        value = CD.map_record(map_raw, ordinal)
        require(expected["ordinal"] == ordinal and expected["group"] == group and
            expected["map"] == {"name": map_name, "bytes": len(map_raw), "sha256": O.digest(map_raw)} and
            expected["dataFiles"] == value["dataFiles"] and expected["dataBytes"] == value["dataBytes"],
            "READ30_ORIGINAL_MAP_REFERENCE")
        snapshot = C._snapshot(owner, "READ30_" + group, directory)
        snapshots.append(snapshot)
        _charge(owner, sum(row[3] for row in snapshot.metadata if not row[1]), len(snapshot.metadata))
        require(tuple(row[0] for row in snapshot.metadata) ==
            ("", *(CD.member_name(number) for number in range(value["dataFiles"]))) and
            _native_from_metadata(snapshot.metadata[0]) == tuple(value["root"]["native"]), "READ30_COMPLETE_FLAT_ROSTER")
        actual = []
        for row, metadata in zip(value["members"], snapshot.metadata[1:]):
            stamp = _native_from_metadata(metadata)
            require(not metadata[1] and stamp == tuple(row["destination"]["native"]), "READ30_ORIGINAL_FULL_NATIVE")
            stream, verify = C._snapshot_reader(owner, snapshot, metadata[0])
            _charge(owner, row["bytes"], 1)
            # The selected small transport/embedded records are retained from
            # THIS stream; no separate read28 pass or fabricated on-disk return.
            retain = ordinal == 29 or ordinal == 30 and row["sourceKind"] == "embedded-not-disk"
            raw = C._consume(owner, stream, row["bytes"], row["sha256"], verify, retain=retain)
            if retain:
                records.append((row["source"], raw))
            actual.append((row["destination"]["relative"], stamp, row["bytes"], row["sha256"]))
        repeated = C._snapshot(owner, "READ30_RECHECK_" + group, directory)
        snapshots.append(repeated)
        _charge(owner, sum(row[3] for row in repeated.metadata if not row[1]), len(repeated.metadata))
        require(repeated.metadata == snapshot.metadata, "READ30_NATIVE_CHANGED")
        _read_native(owner, root, map_name, CD.LIMIT, expected=map_raw, native=map_stamp)
        closed = _close_owner(owner)
        returned_ns = state.clock.now()
        native_root = _expected(state, group, _native_from_metadata(snapshot.metadata[0]), path=payload / group, close=closed)
        members = tuple(_expected(state, name, stamp, count=count, checksum=checksum, path=payload / name, close=closed)
            for name, stamp, count, checksum in actual)
        map_node = _expected(state, map_name, map_stamp, count=len(map_raw), checksum=O.digest(map_raw),
            path=payload / map_name, raw=map_raw, close=closed)
        partition = _track(PartitionView(ordinal, group, native_root, members, map_node))
        read = _track(_PartitionRead(state.handle, partition, map_raw, tuple(records), closed, tuple(snapshots),
            returned_ns, _clock(state.clock).last_local))
        _READ_PARTITIONS[id(partition)] = read
        _update(state, partitions=(*state.partitions, partition), readback=(*state.readback, read))
        return read
    except BaseException as error:
        _abort_owner(owner, error)
        raise _fail(state, error)


def _check_partition_read(read):
    _pin(read)
    require(type(read) is _PartitionRead and _READ_PARTITIONS.get(id(read.partition)) is read, "ORIGINAL_PARTITION_READ")
    _check_owner_close(read.close)
    _partition_current(read.partition, read.partition.ordinal, whole=True)
    require(read.partition.map.provenance.raw is read.map_raw and
        read.partition.map.provenance.close is read.close, "READ30_ORIGINAL_MAP_READ")
    for snapshot in read.snapshots:
        N._check_history(snapshot.graph)
    for node in (read.partition.root, *read.partition.members, read.partition.map):
        require(node.provenance.parent is read.parent and node.provenance.close is read.close, "READ30_ORIGINAL_NODE")
    return read


def _payload_roster(state, *, indexed):
    owner = _file_owner(state)
    try:
        root = C._private(owner, _path(state, "payload"))
        expected = {*CD.GROUPS, *("map-" + group + ".json" for group in CD.GROUPS)}
        if indexed:
            expected.add("copy-index.json")
        require(set(_names(owner, root)) == expected, "FIXED30_PAYLOAD_ROOT_ROSTER")
        stamp = _directory_stamp(root)
        closed = _close_owner(owner)
        return _expected(state, "", stamp, path=_path(state, "payload"), close=closed)
    except BaseException as error:
        _abort_owner(owner, error)
        raise _fail(state, error)


def _read30(state, expected):
    require(not state.partitions and not state.readback, "READ30_ONCE")
    CD.group_references(expected, 30)
    _payload_roster(state, indexed=type(state.handle) is CollectPrepared)
    for ordinal, row in enumerate(expected, 1):
        _partition_read(state, ordinal, row)
    require(len(state.readback) == len(state.partitions) == 30, "COMPLETE_ORIGINAL_READ30")
    _check_union(state)
    return state.readback


def _close_index(state):
    require(type(state.handle) is ChildFinal and len(state.readback) == 30 and state.index is None and
        _clock(state.clock).phase == 0, "FREEZE_FINAL_INDEX_ONCE")
    groups = [_group_reference(partition) for partition in state.partitions]
    data_files = sum(row["dataFiles"] for row in groups)
    data_bytes = sum(row["dataBytes"] for row in groups)
    map_bytes = sum(row["map"]["bytes"] for row in groups)
    raws = dict(state.auxiliary)
    raw = O.encoded({"schema": 1, "scope": CD.INDEX_SCOPE, "kind": "worker", "groups": groups,
        "dataFiles": data_files, "dataBytes": data_bytes, "mapFiles": 30, "mapBytes": map_bytes, "indexFiles": 0,
        "archiveFilesBeforeIndex": data_files + 30, "archiveNativeNodesBeforeIndex": data_files + 61,
        "plaintextBytesBeforeIndex": data_bytes + map_bytes, "contextSha256": O.digest(state.context_raw),
        "startSha256": O.digest(state.start_raw), "parent28Sha256": O.digest(raws["pre-export-copy-index.json"]),
        "reads": [{"ordinal": read.partition.ordinal, "mapSha256": O.digest(read.map_raw),
            "readCloseSha256": O.digest(read.close.raw), "returnedNs": read.returned_ns} for read in state.readback],
        "writerReturn": CD.PENDING, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
    CD.final_index(raw)
    node, close = _write_fixed(state, _path(state, "payload"), "copy-index.json", raw)
    _update(state, index=node)
    root = _payload_roster(state, indexed=True)
    lineage = _track(_Lineage(state.handle, state.context_raw, state.start_raw, raws["final-inputs.json"],
        raws["pre-export-copy-index.json"], state.metadata_close, state.readback, close))
    _LINEAGES[id(lineage)] = lineage
    archive = _track(ChildArchiveBinding30())
    _update(state, root=root, lineage=lineage, archive=archive)
    _check_union(state)
    state.clock.now(limit=state.phase_caps[0])
    return archive


_EXPORT_PHASES = (("custody-freeze", 180), ("custody-encrypt", 240),
    ("custody-encrypt-final", 45), ("custody-encrypt-read", 30))
_COLLECT_PHASES = (("ciphertext-open", 90), ("ciphertext-verify", 90), ("custody-owner-return", 45))


def _setup_export(state):
    owner = _file_owner(state)
    roots = []
    try:
        for name in ("root", "payload", "public-crypto", "returned", "control-home", "temporary", "crypto-service"):
            directory = C._private(owner, _path(state, name), create=True)
            require(_names(owner, directory) == (), "NEW_FIXED_DIRECTORY_NOT_EMPTY")
            roots.append((name, tuple(directory.identity)))
        if os.name == "nt":
            directory = C._private(owner, _path(state, "export-output"), create=True)
            require(_names(owner, directory) == (), "NEW_WINDOWS_OUTPUT_NOT_EMPTY")
            roots.append(("export-output", tuple(directory.identity)))
        else:
            require(not os.path.lexists(_path(state, "export-output")), "POSIX_OUTPUT_MUST_BE_ABSENT")
        closed = _close_owner(owner)
        require(len({identity for _name, identity in roots}) == len(roots), "NEW_FIXED_DIRECTORY_ALIAS")
        _update(state, outer_roots=tuple(roots), metadata_close=closed)
    except BaseException as error:
        _abort_owner(owner, error)
        raise _fail(state, error)


def prepare_final_export(token, cancelled):
    state = None
    try:
        state = _new_state(ParentFinal, "prepare-final-export", cancelled, _EXPORT_PHASES)
        _setup_export(state)
        basis = _clock(state.clock)
        seed = _native_seed(state, "reader", _span(state.clock, basis.ends[0], basis.ends[0], "reader"))
        _update(state, reader_seed=seed)
        C._ProductiveNativeOwner(seed)
        handoff = A._peek_final_productive_inputs(state.handle)
        _update(state, handoff=handoff, phase_caps=_clock(state.clock).ends)
        _actual_host(state, CD.canonical(handoff.history)["observed"], handoff.identity.original_event)
        require(_clock(state.clock).proposal == handoff.proposal, "SAME_DENIAL_AND_AUTHENTIC_ORIGINAL_PROPOSAL")
        _acquire_authority(state, token, post=False)
        token = None
        inputs = A.read_final_productive_inputs(state.handle)
        _update(state, inputs=inputs, stage="prepared")
        A.checked_final_productive_inputs(inputs)
        _checked_authority(state.authority, state)
        return state.handle
    except BaseException as error:
        if state is not None:
            _abort_state(state, error)
            raise _fail(state, error)
        raise
    finally:
        token = None


def _final_inputs_closed(state):
    """No former reader end/reopen and no refreshed final authority factory."""
    A._final_reader_current(state.handle)
    require(type(state.handle) is ParentFinal and type(state.inputs) is A.FinalInputs and
        state.inputs.parent is state.handle and state.inputs.handoff is state.handoff and
        state.inputs.authority is state.authority and state.inputs.claims_raw == state.claims_raw, "ORIGINAL_FINAL_INPUTS")
    saved = A._FINAL_INPUTS.get(id(state.handle))
    require(type(saved) is tuple and saved[0] is state.handle and saved[1] is state.inputs and saved[3] is state.authority,
        "ORIGINAL_ADAPTER_FINAL_REGISTRY")
    pins = saved[4]
    require(state.inputs.__dict__ is pins[1] and tuple(state.inputs.__dict__) == tuple(name for name, _value in pins[2]) and
        all(state.inputs.__dict__[name] is value for name, value in pins[2]), "ORIGINAL_ADAPTER_FINAL_FIELDS")
    A._check_data_pins(pins[3])
    A.checked_handoff_inputs(saved[2].owner, state.handoff)
    _check_owner_close(_OWNER_CLOSES[id(saved[2].owner)])
    for graph in saved[2].use_pins:
        N._check_history(graph)


def _parent_transport(state):
    _final_inputs_closed(state)
    initial = D.initial_inputs_record(dict(state.handoff.blobs)["initial-inputs.json"],
        D.checked_worker(state.handoff.identity)["source"])
    require(compatibility.encoded(initial["compatibilityInputs"]) == state.inputs.derived.compatibility_raw,
        "FINAL_CLOSED_COMPATIBILITY_ORIGINAL")
    compatibility_digest = compatibility.envelope_digest(initial["compatibilityInputs"])
    authority = _checked_authority(state.authority, state)
    prior = _predecessor(state, post=False)
    groups = [_group_reference(partition) for partition in state.partitions]
    pre_raw = O.encoded({"schema": 1, "scope": CD.PRE_INDEX_SCOPE, "kind": "worker", "groups": groups,
        "dataFiles": sum(row["dataFiles"] for row in groups), "dataBytes": sum(row["dataBytes"] for row in groups),
        "mapFiles": 28, "mapBytes": sum(row["map"]["bytes"] for row in groups),
        "prefixRetentionSha256": prior["prefixRetentionSha256"], "preExportReturnSha256": O.digest(authority.raw),
        "preExportIndexSha256": O.digest(authority.index_raw), "writerReturn": CD.PENDING,
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
    CD.pre_index(pre_raw)
    original_match = O.encoded(CD.canonical(state.handoff.identity.record)["initialRecipient"])
    final_raw = O.encoded({"schema": 1, "scope": CD.FINAL_INPUTS_SCOPE, "kind": "worker",
        "observed": CD.canonical(state.handoff.history)["observed"], "history": CD.canonical(state.handoff.history),
        "originalProposal": CD.canonical(state.handoff.proposal), "claims": CD.canonical(state.claims_raw),
        "workerIdentity": CD.canonical(state.handoff.identity.record), "originalMatchSha256": O.digest(original_match),
        "freshMatchSha256": O.digest(authority.match.record), "producerHandoffSha256": prior["producerHandoffSha256"],
        "producerReturnSha256": prior["producerReturnSha256"], "afterSaveSha256": prior["afterSaveSha256"],
        "probeSha256": prior["probeSha256"], "prefixRetentionSha256": prior["prefixRetentionSha256"],
        "compatibilityInputsSha256": compatibility_digest,
        "preExportReturnSha256": O.digest(authority.raw), "preExportIndexSha256": O.digest(authority.index_raw),
        "preExportCopyIndexSha256": O.digest(pre_raw),
        "sourceRecordsSha256": {name: O.digest(raw) for name, raw in state.handoff.source_records},
        "inputProvenance": "ORIGINAL_FINAL_READER_AND_NEW_PRE_AUTHORITY", "budgetAcceptance": "NOT_ADMITTED",
        "exportSaveAuthority": False})
    CD.final_inputs(final_raw)
    policy_raw = state.handoff.identity.original_policy
    _policy, public_raw = N.I._policy(policy_raw, int(time.time()))
    raws = {"final-inputs.json": final_raw, "pre-export-copy-index.json": pre_raw, "authority-return.json": authority.raw,
        "authority-index.json": authority.index_raw, "original-match.json": original_match,
        "fresh-match.json": authority.match.record, "event.json": state.handoff.identity.original_event,
        "candidate-policy.json": policy_raw, "recipient-public.asc": public_raw}
    nodes = []
    for name, maximum in CD.CRYPTO_INPUTS:
        node, _close = _write_fixed(state, _path(state, "returned"), name, raws[name], maximum)
        nodes.append(node)
    _update(state, auxiliary=tuple((name, raws[name]) for name, _max in CD.CRYPTO_INPUTS), transport=tuple(nodes))
    basis = _clock(state.clock)
    context_raw = O.encoded({"schema": 1, "scope": CD.CRYPTO_CONTEXT_SCOPE, "kind": "worker", "root": str(ROOT),
        "session": str(_path(state, "returned")), "job": uuid.uuid4().hex,
        "observed": CD.canonical(state.handoff.history)["observed"], "history": CD.canonical(state.handoff.history),
        "originalProposal": CD.canonical(state.handoff.proposal), "clock": O.clock_value(basis.first.clock),
        "originalBootDigest": basis.boot, "originalJobBasisNs": CD.canonical(state.handoff.history)["originalJobBasisNs"],
        "phaseFirstNs": basis.started[0][0], "phaseEndsNs": dict(zip(CD.FINAL_CRYPTO_CAP_FIELDS[:4], state.phase_caps)),
        "inputs": {node.relative: {"name": node.relative, "bytes": node.bytes, "sha256": node.sha256} for node in nodes},
        "directories": {name: list(pin) for name, pin in state.outer_roots}, "inheritedContext": Q._inherited_context(),
        "parent28Sha256": O.digest(pre_raw), "finalInputsSha256": O.digest(final_raw),
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
    CD.crypto_context(context_raw)
    _update(state, context_raw=context_raw)
    return context_raw


def _crypto_start_data(context_raw, start, caps, clock, boot):
    context = CD.crypto_context(context_raw)
    CD.crypto_caps(caps)
    CD.fields(start, B.START_FIELDS)
    require(type(start["argv"]) is list and start["argv"], "CRYPTO_ORIGINAL_ARGV")
    require(type(start["schema"]) is int and start["schema"] == 1 and start["scope"] == C._CRYPTO_START_SCOPE and
        start["argv"] == _command("_final-crypto", context_raw, caps, clock, boot, interpreter=start["argv"][0]) and
        start["contextSha256"] == O.digest(context_raw) and start["cwd"] == str(ROOT) and start["role"] == clock.role and
        start["job"] == context["job"] and start["state"] == context["session"] and
        start["home"] == str(Path(context["session"]) / "control-home") and
        start["exitCode"] is None and start["launchAttempted"] is start["scopeAttempted"] is False and
        start["retirement"] == "UNKNOWN" and
        tuple(start[name] for name in ("startedNs", "workEndNs", "finalEndNs")) == caps[4:] and
        tuple(context["phaseEndsNs"][name] for name in CD.FINAL_CRYPTO_CAP_FIELDS[:4]) == caps[:4] and
        context["clock"] == O.clock_value(clock) and context["originalBootDigest"] == boot,
        "CRYPTO_ACTUAL_PRELAUNCH_DATA")
    CD.job(start["invocation"])
    inherited = B.processes.ownership_environment(context["inheritedContext"], context["job"], start["invocation"],
        context["session"], start["home"], allow_new_context=True)
    require(start["inheritedContext"] == {name: inherited[name] for name in Q._CONTEXT}, "CRYPTO_ORIGINAL_ANCESTORS")
    return start


def _checked_crypto_start(seed, context_raw, start):
    saved = _native_state(seed)
    state = _state(saved.parent)
    require(saved.purpose == "crypto-native" and saved.context_raw is context_raw and saved.phase and
        state.crypto_seed is seed, "ACTUAL_CRYPTO_START_SEED")
    _crypto_start_data(context_raw, start, (*state.phase_caps, *saved.phase), _clock(state.clock).first.clock,
        _clock(state.clock).boot)
    require(start["argv"][0] == B.initial_command(O.digest(context_raw))[0], "CRYPTO_ACTUAL_INTERPRETER")
    return start


def _native_crypto_binding(seed):
    saved = _native_state(seed)
    state = _state(saved.parent)
    require(type(state.handle) is ParentFinal and state.crypto_seed is seed and saved.purpose == "crypto-native" and
        saved.owner is state.owner and saved.private.path == _path(state, "returned") and
        saved.context_raw is state.context_raw and saved.check is not None and not saved.phase and
        state.stage == "launch-ready", "ONE_ACTUAL_CRYPTO_NATIVE_CALL")
    _update(state, stage="native-entered")
    _native_work_check(seed)
    return saved.owner, saved.private, saved.context_raw, saved.fence, saved.check


def _native_work_check(seed):
    saved = _native_state(seed)
    state = _state(saved.parent)
    require(saved.purpose == "crypto-native" and state.crypto_seed is seed and state.owner is saved.owner and
        len(state.partitions) == 28 and state.closed is None and state.native_return is None,
        "ORIGINAL_PARENT28_NATIVE_WAIT")
    _native_boundary(saved.owner)
    if not saved.phase:
        state.clock.now()
    else:
        require(_clock(state.clock).phase == 1, "CRYPTO_WAIT_ONLY_IN_ENCRYPT")
        saved.fence.now(limit=saved.phase[1])
    for ordinal, partition in enumerate(state.partitions, 1):
        _partition_current(partition, ordinal, whole=False)
    _environment(state)


def _native_crypto_child_return(seed, scope, child):
    """Called immediately after the actual spawn, before its first fallible check."""
    saved = _native_state(seed)
    require(saved.purpose == "crypto-native" and saved.phase and not saved.launch and
        any(resource is scope and name == "native-scope" and not attempted and not closed
            for _row, name, resource, attempted, closed in saved.owner._anchor().rows), "ACTUAL_NATIVE_SPAWN_OWNER")
    _update(saved, launch=(scope, child, child.pid))


def _native_crypto_final(seed, scope, child, code, completed_ns):
    """C calls only after real code0 and actual empty native discovery under work."""
    saved = _native_state(seed)
    state = _state(saved.parent)
    require(saved.purpose == "crypto-native" and state.crypto_seed is seed and saved.phase and
        _clock(state.clock).phase == 1 and state.native_return is None and not saved.completion and
        saved.launch and saved.launch[0] is scope and saved.launch[1] is child and saved.launch[2] == child.pid and
        type(code) is int and code == 0 and saved.phase[0] <= CD.integer(completed_ns) <= saved.fence.last < saved.phase[1],
        "ACTUAL_NATIVE_FINAL_ONCE")
    saved.fence.now(limit=saved.phase[1])
    clock = _clock(state.clock)
    _update(saved, completion=(scope, child, code, completed_ns, clock.reading, clock.last_local,
        N._history_graph(clock.reading)))
    _advance(state.clock, "custody-encrypt-final")


def _begin_crypto_native(state):
    require(state.stage == "parent28-closed" and len(state.phase_caps) == 4, "PARENT_CRYPTO_POSITION")
    _parent_transport(state)
    _check_union(state)
    seed = _native_seed(state, "crypto-native", _span(state.clock, state.phase_caps[1], state.phase_caps[2], "crypto-native"))
    _update(state, crypto_seed=seed)
    owner = C._ProductiveNativeOwner(seed)
    _update(state, owner=owner)
    private = owner.open(_path(state, "returned"))
    require(tuple(private.identity) == dict(state.outer_roots)["returned"], "ORIGINAL_RETURNED_ROOT")
    require(owner.write(private, "context.json", state.context_raw) is state.context_raw, "ACTUAL_CRYPTO_CONTEXT_WRITE")
    def native_check():
        _native_work_check(seed)
    saved = _native_state(seed)
    _update(saved, private=private, context_raw=state.context_raw, check=native_check)
    _update(state, stage="launch-ready")
    returned = C.productive_crypto_native(seed)
    # First source-owned retained return, before a fallible checker or callback.
    _update(state, native_return=returned)
    _track(returned)
    _checked_native_crypto(state, returned)
    return returned


def export_prepared_final(parent):
    state = _state(parent)
    require(type(parent) is ParentFinal, "EXPORT_ORIGINAL_PARENT_TYPE")
    try:
        require(state.stage == "prepared" and not state.busy and state.result is None, "EXPORT_ONCE")
        _update(state, busy=True, stage="copying-parent28")
        _environment(state)
        for spec in _parent_specs(state):
            _copy_group(state, spec)
        A.checked_final_productive_inputs(state.inputs)
        reader = _native_state(state.reader_seed).owner
        _close_owner(reader)
        _final_inputs_closed(state)
        _update(state, stage="parent28-closed")
        returned = _begin_crypto_native(state)
        native_close = _close_owner(state.owner)
        _update(state, closed=native_close, stage="native-closed")
        _checked_native_crypto(state, returned, retired=True)
        # Native, captures, and the actual original outer owner are already
        # closed; the one read phase is entered BEFORE effective FINAL expires.
        _advance(state.clock, "custody-encrypt-read")
        _parent_returned_records(state)
        result = _register_final_return(state, collect=False)
        _update(state, busy=False, stage="export-returned")
        checked_final_export_return(result)
        return result
    except BaseException as error:
        _abort_state(state, error)
        raise _fail(state, error)


@dataclass(frozen=True, repr=False)
class _ValidationInventory:
    child: object
    returned: object
    completion: object
    snapshot: object
    raw: bytes
    close: object


_VALIDATION_INVENTORIES, _SOURCES = {}, {}


def _caps_data(caps):
    _pin(caps)
    return {"clock": O.clock_value(caps.clock), "firstNs": caps.first.nanoseconds, "firstLocal": caps.firstLocal,
        **{name: getattr(caps, name) for name in ("workEndNs", "workEndLocal", "operationFinishEndNs",
            "operationFinishEndLocal", "finishReserveNs", "operationLimitNs")}}


def _caps_record(value, *, validation, caps, first):
    CD.fields(value, "clock firstNs firstLocal workEndNs workEndLocal operationFinishEndNs operationFinishEndLocal "
        "finishReserveNs operationLimitNs")
    require(value["clock"] == O.clock_value(first.clock), "HISTORICAL_OPERATION_CLOCK")
    for name in ("firstNs", "workEndNs", "operationFinishEndNs", "finishReserveNs", "operationLimitNs"):
        CD.integer(value[name])
    for name in ("firstLocal", "workEndLocal", "operationFinishEndLocal"):
        CD.local(value[name])
    seconds, end = (60, caps[0]) if validation else (240, caps[1])
    reserve = 30 * NS if first.clock.role == "windows-x64" else 0
    require(value["operationLimitNs"] == seconds * NS and value["finishReserveNs"] == reserve and
        value["firstNs"] < value["workEndNs"] <= value["operationFinishEndNs"] - reserve and
        value["operationFinishEndNs"] <= min(end, caps[5], value["firstNs"] + seconds * NS) and
        value["firstLocal"] < value["workEndLocal"] <= value["operationFinishEndLocal"] and
        value["operationFinishEndLocal"] <= value["firstLocal"] + seconds, "HISTORICAL_OPERATION_ENDS")
    return value


def _crypto_inputs_data(context_raw, raws, clock, boot):
    context = CD.crypto_context(context_raw)
    require(set(raws) == {name for name, _maximum in CD.CRYPTO_INPUTS}, "FIXED_CRYPTO_INPUTS9")
    for name, maximum in CD.CRYPTO_INPUTS:
        require(type(raws[name]) is bytes and 0 < len(raws[name]) <= maximum and
            context["inputs"][name] == {"name": name, "bytes": len(raws[name]), "sha256": O.digest(raws[name])},
            "CRYPTO_ACTUAL_INPUT_HASH")
    final, prior = CD.final_inputs(raws["final-inputs.json"]), CD.pre_index(raws["pre-export-copy-index.json"])
    require(final["observed"] == context["observed"] and final["history"] == context["history"] and
        final["originalProposal"] == context["originalProposal"] and
        final["preExportCopyIndexSha256"] == context["parent28Sha256"] == O.digest(raws["pre-export-copy-index.json"]) and
        context["finalInputsSha256"] == O.digest(raws["final-inputs.json"]) and
        final["preExportReturnSha256"] == prior["preExportReturnSha256"] == O.digest(raws["authority-return.json"]) and
        final["preExportIndexSha256"] == prior["preExportIndexSha256"] == O.digest(raws["authority-index.json"]) and
        final["prefixRetentionSha256"] == prior["prefixRetentionSha256"] and
        raws["original-match.json"] == raws["fresh-match.json"] and
        O.digest(raws["original-match.json"]) == final["originalMatchSha256"] == final["freshMatchSha256"] and
        context["clock"] == O.clock_value(clock) and context["originalBootDigest"] == boot,
        "CRYPTO_FINAL_READER_PREDECESSORS")
    match = N.acquisition.stages.BootstrapMatch(raws["original-match.json"])
    identity = N.initial_identity.bind_worker_match(match, event_raw=raws["event.json"],
        policy_raw=raws["candidate-policy.json"], now=int(time.time()))
    require(identity.record == O.encoded(final["workerIdentity"]), "CRYPTO_INITIAL_SOURCE_DATA")
    D.original_proposal(O.encoded(final["originalProposal"]), identity, O.encoded(final["history"]), clock)
    policy, public = N.I._policy(raws["candidate-policy.json"], int(time.time()))
    require(public == raws["recipient-public.asc"] and policy["recipient"]["sha256"] == O.digest(public) and
        final["sourceRecordsSha256"]["candidate_policy_raw"] == O.digest(raws["candidate-policy.json"]),
        "CRYPTO_PUBLIC_KEY_POLICY")
    authority, index = CD.authority_return(raws["authority-return.json"], post=False), CD.authority_index(raws["authority-index.json"], post=False)
    require(authority["contextSha256"] == index["contextSha256"] and authority["inventorySha256"] == O.digest(raws["authority-index.json"]) and
        authority["matchSha256"] == final["originalMatchSha256"] and
        authority["workerIdentitySha256"] == O.digest(identity.record) and
        authority["authorityWindow"]["originalProposalSha256"] == O.digest(O.encoded(final["originalProposal"])) and
        authority["predecessor"] == {name: final["claims"][key] for name, key in
            (("producerStepOutcome", "PRODUCER_OUTCOME"), ("producerHandoffSha256", "HANDOFF_SHA256"),
             ("producerReturnSha256", "PRODUCER_RETURN_SHA256"), ("afterSaveStepOutcome", "AFTER_SAVE_OUTCOME"),
             ("afterSaveSha256", "AFTER_SAVE_SHA256"), ("afterProbeStepOutcome", "AFTER_PROBE_OUTCOME"),
             ("probeSha256", "PROBE_SHA256"))} | {"prefixRetentionSha256": final["prefixRetentionSha256"]},
        "CRYPTO_NEW_PRE_AUTHORITY_DATA")
    return final, prior, identity, policy


def _child_metadata(state, context_hash, minimum, caps):
    basis = _clock(state.clock)
    meta_end = min(basis.ends[0], caps[5], CD.integer(basis.first.nanoseconds + 45 * NS))
    owner = _file_owner(state, _span(state.clock, meta_end, meta_end, "metadata"))
    reads, pins = [], []
    try:
        returned = C._private(owner, _path(state, "returned"))
        service = C._private(owner, _path(state, "crypto-service"))
        pins.extend((("returned", tuple(returned.identity)), ("crypto-service", tuple(service.identity))))
        _charge(owner, nodes=2)
        context_raw, stamp = _read_native(owner, returned, "context.json", CD.PUBLIC_LIMIT)
        reads.append((_path(state, "returned") / "context.json", context_raw, stamp))
        start_raw, stamp = _read_native(owner, service, "start.json", CD.LIMIT)
        reads.append((_path(state, "crypto-service") / "start.json", start_raw, stamp))
        raws = {}
        for name, maximum in CD.CRYPTO_INPUTS:
            raw, stamp = _read_native(owner, returned, name, maximum)
            raws[name] = raw
            reads.append((_path(state, "returned") / name, raw, stamp))
        require(O.digest(context_raw) == context_hash, "ACTUAL_CHILD_CONTEXT_DIGEST")
        close = _close_owner(owner)
        metadata_last = owner.owner.fence.now(limit=meta_end)
        # Only now may historical context bind/shorten the SAME first basis.
        context = CD.crypto_context(context_raw)
        start = _crypto_start_data(context_raw, CD.canonical(start_raw), caps, basis.first.clock, basis.boot)
        require(start["argv"][0] == B.initial_command(context_hash)[0], "CRYPTO_CHILD_ACTUAL_INTERPRETER")
        require(context["session"] == str(_path(state, "returned")) and context["root"] == str(ROOT) and
            all(tuple(context["directories"][name]) == pin for name, pin in pins) and
            caps[4] <= minimum <= basis.first.nanoseconds and minimum < caps[0] and
            Q._inherited_context() == start["inheritedContext"], "CHILD_ACTUAL_METADATA_AND_ANCESTORS")
        final, _pre, _identity, _policy = _crypto_inputs_data(context_raw, raws, basis.first.clock, basis.boot)
        _shorten_clock(state.clock, final["originalProposal"])
        effective = tuple(min(end, caps[5]) for end in basis.ends)
        locals_ = tuple(min(end, O.wire._directed_deadline(basis.local, 900, raw, basis.first.nanoseconds))
            for end, raw in zip(basis.locals, effective))
        _update(basis, ends=effective, locals=locals_)
        source = _track(ChildSourceBinding(context["job"], O.encoded(context["observed"]), O.digest(raws["event.json"]),
            context_hash, O.digest(start_raw)))
        _SOURCES[id(source)] = source, state.handle, context_raw, start_raw, raws["event.json"]
        observations = tuple(_track(_FileRead(state.handle, path, raw, stamp, close)) for path, raw, stamp in reads)
        for observation in observations:
            _FILE_READS[id(observation)] = observation
        _update(state, source=source, context_raw=context_raw, start_raw=start_raw, metadata_close=close,
            metadata_last=metadata_last, phase_caps=caps, auxiliary=tuple((name, raws[name]) for name, _max in CD.CRYPTO_INPUTS),
            observations=observations, union=tuple((path, stamp) for path, _raw, stamp in reads), stage="metadata-closed")
        _actual_host(state, context["observed"], raws["event.json"])
        state.clock.now()
    except BaseException as error:
        if not owner.finished:
            _abort_owner(owner, error)
        raise _fail(state, error)


def _open_child_roots(state):
    require(state.stage == "metadata-closed" and state.owner is None, "ACTUAL_CHILD_OUTER_ONCE")
    context = CD.crypto_context(state.context_raw)
    owner = _file_owner(state, _span(state.clock, state.phase_caps[5], state.phase_caps[5], "child-outer"))
    _update(state, owner=owner)
    roots = []
    for name in ("root", "returned", "control-home", "temporary", "crypto-service", "payload", "public-crypto"):
        directory = C._private(owner, _path(state, name))
        pin = tuple(directory.identity)
        require(pin == tuple(context["directories"][name]), "ACTUAL_CHILD_ORIGINAL_ROOT_PIN")
        roots.append((name, directory, directory.path, pin, _methods(directory, ("verify", "close"))))
        _charge(owner, nodes=1)
    if os.name == "nt":
        directory = C._private(owner, _path(state, "export-output"))
        pin = tuple(directory.identity)
        require(pin == tuple(context["directories"]["export-output"]) and _names(owner, directory) == (), "CHILD_NEW_EMPTY_OUTPUT")
        roots.append(("export-output", directory, directory.path, pin, _methods(directory, ("verify", "close"))))
        output = directory
    else:
        output = _path(state, "export-output")
        require(not os.path.lexists(output), "CHILD_POSIX_OUTPUT_ABSENT_AT_ADMISSION")
    directories = {name: directory for name, directory, _path_, _pin_, _methods_ in roots}
    require(_names(owner, directories["public-crypto"]) == (), "CHILD_NEW_VALIDATION_WORK")
    require(_names(owner, directories["control-home"]) == _names(owner, directories["temporary"]) == (),
        "CHILD_FIXED_EMPTY_CONTROL_ROOTS")
    _update(state, outer_roots=tuple(roots), work=directories["public-crypto"] if os.name == "nt" else directories["public-crypto"].path,
        payload=directories["payload"] if os.name == "nt" else directories["payload"].path, output=output, stage="child-active")


def _child_roots_current(state):
    require(type(state.handle) is ChildFinal and type(state.owner) is C._PrimaryOwner and state.outer_roots, "CHILD_OUTER_ROOTS")
    for name, directory, path, pin, methods in state.outer_roots:
        _methods_current(directory, methods)
        require(directory.path is path and path == _path(state, name) and tuple(directory.identity) == pin,
            "CHILD_BORROWED_ROOT_CHANGED")
        # Do not repeat POSIX output absence after the backend begins its own
        # exclusive reservation; only the SAME original parent/path is ours.
        if state.closed is None:
            directory.verify()
            require(tuple(directory.identity) == pin, "CHILD_BORROWED_ROOT_REPLACED")


def _recipient_summary(state):
    returned = state.validation_return
    _pin(returned)
    require(returned.view is state.validation and state.validation_completed.returned is returned, "SAME_ACTUAL_VALIDATION")
    recipient = returned.recipient
    raw = O.encoded({"schema": 1, "scope": "INITIAL_RECIPIENT_PRODUCTIVE_ACTUAL_RECIPIENT_RETURN_V1",
        "contextSha256": O.digest(state.context_raw), "startSha256": O.digest(state.start_raw),
        "invocation": CD.canonical(state.start_raw)["invocation"], "clock": O.clock_value(_clock(state.clock).first.clock),
        "beganNs": _clock(state.clock).first.nanoseconds, "metadataLastNs": state.metadata_last,
        "validationStartedNs": state.validation.caps.first.nanoseconds, "validationReturnedNs": state.validation_completed.raw,
        "recipient": {"fingerprint": recipient.fingerprint, "encryptionFingerprint": recipient.encryption_fingerprint,
            "keySha256": recipient.key_sha256, "expiresAt": recipient.expires_at},
        "supplierReturned": True, "outerChild": "STILL_LIVE", "exportSaveAuthority": False})
    require(len(raw) <= CD.LIMIT, "ACTUAL_RECIPIENT_SUMMARY_BOUND")
    return raw


def _child_copy_specs(state, summary_raw):
    require(state.validation_completed is not None and not state.copied and not state.partitions, "CHILD_COPY_AFTER_VALIDATION")
    metadata = {read.path: _check_file_read(read) for read in state.observations if type(read) is _FileRead}
    context = CD.crypto_context(state.context_raw)
    files = []
    for name, maximum in CD.CRYPTO_INPUTS:
        read = metadata[_path(state, "returned") / name]
        files.append(_source_file(read.path, name, maximum, len(read.raw), O.digest(read.raw),
            "ACTUAL_CHILD_METADATA_AND_PARENT_TRANSPORT", native=read.native))
    group29 = _group(state, 29, (_tree(_path(state, "returned"), tuple(files),
        (("", tuple(context["directories"]["returned"])),), "FIXED9_TRANSPORT_NOT_WHOLE_RETURNED", exact=False),), state.metadata_close)
    owner = _file_owner(state)
    try:
        work = C._private(owner, _path(state, "public-crypto"))
        _charge(owner, nodes=1)
        snapshot, inventory = C._recipient_inventory(owner, work, dict(state.auxiliary)["recipient-public.asc"])
        # Initial snapshot, complete reads and actual rescan are all charged.
        _charge(owner, 3 * inventory["totalBytes"], 2 * len(snapshot.metadata) + inventory["fileCount"])
        close = _close_owner(owner)
        original = _track(_ValidationInventory(state.handle, state.validation_return, state.validation_completed,
            snapshot, O.encoded(inventory), close))
        _VALIDATION_INVENTORIES[id(original)] = original
        _update(state, observations=(*state.observations, original))
        native = {row[0]: _native_from_metadata(row) for row in snapshot.metadata}
        members = tuple(_source_file(work.path / row["relative"], row["relative"], row["maximum"], row["bytes"], row["sha256"],
            "ACTUAL_SAME_E_VALIDATION_COMPLETED_NATIVE_FILE", native=native[row["relative"]]) for row in inventory["files"])
        tree = _tree(work.path, members, tuple((row["relative"], tuple(row["identity"])) for row in inventory["directories"]),
            "ACTUAL_SAME_E_VALIDATION_COMPLETE_TREE", root_native=native[""])
        trees = [tree]
        for root, name, maximum in (("returned", "context.json", CD.PUBLIC_LIMIT), ("crypto-service", "start.json", CD.LIMIT)):
            read = metadata[_path(state, root) / name]
            member = _source_file(read.path, name, maximum, len(read.raw), O.digest(read.raw),
                "ACTUAL_DISK_CONTEXT_OR_START_NOT_EMBEDDED", native=read.native)
            trees.append(_tree(_path(state, root), (member,), (("", tuple(context["directories"][root])),),
                "ACTUAL_CHILD_METADATA_DISK_CARRIER", exact=False))
        embedded = _source_file(None, "recipient-return.json", CD.LIMIT, len(summary_raw), O.digest(summary_raw),
            "ACTUAL_E_SUPPLIER_RETURN_EMBEDDED_NOT_DISK_OUTER_CHILD_LIVE", embedded=summary_raw)
        group30 = _group(state, 30, tuple(trees), original, (embedded,))
        return group29, group30
    except BaseException as error:
        if not owner.finished:
            _abort_owner(owner, error)
        raise _fail(state, error)


def _public_projection(raws, groups, index):
    final = CD.final_inputs(raws["final-inputs.json"])
    match = CD.canonical(raws["original-match.json"], CD.PUBLIC_LIMIT)
    policy, _public = N.I._policy(raws["candidate-policy.json"], int(time.time()))
    files = sum(row["dataFiles"] for row in groups)
    initial = {name: match[name] for name in ("authority", "environment", "originalBase", "reviewed", "firstUseAt", "notBefore", "expiresAt")}
    initial.update(matchSha256=O.digest(raws["original-match.json"]), preExportReturnSha256=final["preExportReturnSha256"],
        preExportIndexSha256=final["preExportIndexSha256"])
    productive = {name: final[name] for name in ("producerHandoffSha256", "producerReturnSha256", "afterSaveSha256",
        "probeSha256", "prefixRetentionSha256", "compatibilityInputsSha256")}
    productive.update(originalProposalSha256=O.digest(O.encoded(final["originalProposal"])),
        producerStepOutcome=final["claims"]["PRODUCER_OUTCOME"], afterSaveStepOutcome=final["claims"]["AFTER_SAVE_OUTCOME"],
        afterProbeStepOutcome=final["claims"]["AFTER_PROBE_OUTCOME"])
    result = O.encoded({"schema": 1, "scope": "INITIAL_RECIPIENT_PRODUCTIVE_MANIFEST_INPUTS_V1", "kind": "worker",
        "selection": match["github"]["selection"], "source": match["source"],
        "github": {**match["github"], "repository": N.I.REPOSITORY, "eventSha256": O.digest(raws["event.json"])},
        "policy": {**match["policy"], "fingerprint": policy["recipient"]["fingerprint"],
            "keySha256": policy["recipient"]["sha256"], "expiresAt": policy["expiresAt"], "retentionDays": 14},
        "initialRecipient": initial, "productive": productive,
        "copy": {"scope": "INITIAL_RECIPIENT_PRODUCTIVE_FIXED30_ARCHIVE_BINDING_V1", "groups": groups,
            "index": index,
            "dataFiles": files, "mapFiles": 30, "indexFiles": 1, "archiveFiles": files + 31,
            "archiveNativeNodes": files + 62,
            "plaintextBytes": sum(row["dataBytes"] + row["map"]["bytes"] for row in groups) + index["bytes"]}})
    CD.canonical(result, CD.PUBLIC_LIMIT)
    return result


def _public_inputs(state):
    return _public_projection(dict(state.auxiliary), [_group_reference(partition) for partition in state.partitions],
        {"name": "copy-index.json", "bytes": state.index.bytes, "sha256": state.index.sha256})


def productive_crypto_child(context_sha256, minimum_ns, caps, original_clock, original_boot_digest, cancelled):
    state = None
    try:
        CD.crypto_caps(caps)
        CD.sha(context_sha256)
        CD.sha(original_boot_digest)
        require(caps[4] <= CD.integer(minimum_ns) < caps[0], "CHILD_LAUNCH_DURING_FREEZE")
        state = _new_state(ChildFinal, "productive-crypto-child", cancelled, _EXPORT_PHASES, caps=caps[:4],
            declared_clock=original_clock, boot=original_boot_digest, minimum=minimum_ns)
        _child_op = _clock(state.clock)
        _update(state, phase_caps=caps)
        _child_ops = _e_functions()
        _child_metadata(state, context_sha256, minimum_ns, caps)
        _open_child_roots(state)
        returned = _child_ops[0](state.handle)
        _update(state, validation_return=returned)
        _track(returned)
        require(_child_ops[1](returned, state.handle) is returned, "ORIGINAL_E_VALIDATION_RETURN")
        completed = _complete_operation(state, state.validation.caps, returned)
        _update(state, validation_completed=completed)
        _e_functions_current(_child_ops)
        summary = _recipient_summary(state)
        for spec in _child_copy_specs(state, summary):
            _copy_group(state, spec)
        prior = CD.pre_index(dict(state.auxiliary)["pre-export-copy-index.json"])
        expected = [*prior["groups"], *(_group_reference(copy.partition) for copy in state.copied)]
        _read30(state, expected)
        require(dict(state.readback[28].records) ==
            {str(_path(state, "returned") / name): raw for name, raw in state.auxiliary} and
            state.readback[29].records == (("recipient-return.json", summary),), "ACTUAL_READ30_TRANSPORT_AND_EMBEDDED_RETURN")
        archive = _close_index(state)
        freeze_closed = state.clock.now(limit=caps[0])
        _update(state, public_inputs=_public_inputs(state))
        _actual_host(state, CD.canonical(state.source.observed_raw), dict(state.auxiliary)["event.json"])
        _advance(state.clock, "custody-encrypt")
        require(_child_ops[1](returned, state.handle) is returned, "COMPLETED_VALIDATION_STILL_SAME_RETURN")
        exported = _child_ops[2](state.handle, archive, returned.recipient)
        _update(state, backend_return=exported)
        _track(exported)
        require(_child_ops[3](exported, state.archive_view) is exported, "ORIGINAL_E_EXPORT_RETURN")
        exported_close = _complete_operation(state, state.archive_view.caps, exported)
        _update(state, export_completed=exported_close, manifest_raw=exported.manifest_raw, artifact=exported.artifact)
        _track(exported.artifact)
        _e_functions_current(_child_ops)
        manifest = CD.public_manifest(exported.manifest_raw)
        require(manifest["copy"]["index"]["sha256"] == state.index.sha256, "ACTUAL_EXPORTED_INDEX")
        terminal = O.encoded({"schema": 1, "scope": CD.CRYPTO_CHILD_SCOPE,
            "contextSha256": context_sha256, "startSha256": O.digest(state.start_raw),
            "invocation": CD.canonical(state.start_raw)["invocation"], "clock": O.clock_value(_child_op.first.clock),
            "bootDigest": original_boot_digest, "launchMinimumNs": minimum_ns, "beganNs": _child_op.first.nanoseconds,
            "childFirstLocal": _child_op.local, "metadataLastNs": state.metadata_last,
            "metadataCloseSha256": O.digest(state.metadata_close.raw), "validationCaps": _caps_data(state.validation.caps),
            "validationReturnedNs": completed.raw, "freezeClosedNs": freeze_closed,
            "exportCaps": _caps_data(state.archive_view.caps), "exportedNs": exported_close.raw,
            "recipientReturnSha256": O.digest(summary), "copyIndexSha256": state.index.sha256,
            "parent28Sha256": O.digest(dict(state.auxiliary)["pre-export-copy-index.json"]),
            "artifactNative": list(exported.artifact.native),
            "manifest": {"bytes": len(exported.manifest_raw), "sha256": O.digest(exported.manifest_raw),
                "base64": base64.b64encode(exported.manifest_raw).decode("ascii")},
            "retirement": "PENDING_CHILD_CLOSE", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        CD.canonical(terminal)
        node, _close = _write_fixed(state, _path(state, "returned"), "crypto-child-result.json", terminal)
        _update(state, actual_raw=terminal, final_records=(node,))
        check_child_archive(state.archive_view)
        closed = _close_owner(state.owner)
        _update(state, closed=closed, stage="child-retired")
        require(_child_ops[4](returned, state.handle) is returned and
            _child_ops[5](exported, state.archive_view) is exported, "GENUINE_RETIRED_E_RETURNS")
        _e_functions_current(_child_ops)
        checked_retired_child_validation(state.handle)
        check_retired_child_archive(state.archive_view)
        after_close = state.clock.now(limit=caps[5])
        fence = _child_ack_fence(state, caps[5])
        return {"schema": 1, "scope": CD.CRYPTO_ACK_SCOPE, "invocation": CD.canonical(state.start_raw)["invocation"],
            "terminalSha256": O.digest(terminal), "clock": O.clock_value(_child_op.first.clock), "closedNs": after_close}, fence, caps[5]
    except BaseException as error:
        if state is not None:
            _abort_state(state, error)
            raise _fail(state, error)
        raise


def _e_functions():
    import hosted_initial_recipient_evidence as E
    require(C.E is E, "ONE_CANONICAL_E")
    return (E.validate_initial_productive_recipient, E.checked_productive_validation_return,
        E.export_initial_productive_encrypted, E.checked_productive_backend_return,
        E.checked_retired_productive_validation_return, E.checked_retired_productive_backend_return)


def _e_functions_current(functions):
    current = _e_functions()
    require(type(functions) is tuple and len(functions) == len(current) and
        all(actual is original for actual, original in zip(current, functions)), "ORIGINAL_E_SUPPLIERS_CHANGED")


_CRYPTO_CHILD_FIELDS = (
    "schema scope contextSha256 startSha256 invocation clock bootDigest launchMinimumNs beganNs childFirstLocal "
    "metadataLastNs metadataCloseSha256 validationCaps validationReturnedNs freezeClosedNs exportCaps exportedNs "
    "recipientReturnSha256 copyIndexSha256 parent28Sha256 artifactNative manifest retirement budgetAcceptance exportSaveAuthority"
)


def _crypto_phase_data(context_raw, records, child_raw, phase, first, boot):
    """Closed byte predicates only; callers separately supply actual native/Step currency."""
    context = CD.crypto_context(context_raw)
    caps = (*(context["phaseEndsNs"][name] for name in CD.FINAL_CRYPTO_CAP_FIELDS[:4]), *phase)
    CD.crypto_caps(caps)
    require(type(records) is tuple and len(records) == len(B.PHASE_FILES) and
        set(dict(records)) == B.PHASE_FILES and all(type(name) is str and type(raw) is bytes for name, raw in records),
        "CRYPTO_NATIVE_RECORD_ROSTER")
    blobs = dict(records)
    start = _crypto_start_data(context_raw, CD.canonical(blobs["start.json"]), caps, first.clock, boot)
    row = CD.fields(CD.canonical(blobs["result.json"]), B.TERMINAL_FIELDS)
    birth = CD.fields(CD.canonical(blobs["native-start.json"]), "ownership leader preparerIdentity observedNs")
    changed = {"exitCode", "launchAttempted", "scopeAttempted", "retirement"}
    require({name: row[name] for name in start if name not in changed} ==
        {name: value for name, value in start.items() if name not in changed} and
        type(row["exitCode"]) is int and row["exitCode"] == 0 and row["launchAttempted"] is row["scopeAttempted"] is
        row["scopeCloseAttempted"] is row["scopeClosed"] is True and row["retirement"] == "KNOWN" and
        row["errors"] == row["survivors"] == [] and blobs["stderr.log"] == b"" and
        row["nativeStartSha256"] == O.digest(blobs["native-start.json"]) and
        row["baselineSha256"] == O.digest(blobs["baseline.json"]) and row["leader"] == birth["leader"],
        "CRYPTO_NATIVE_TERMINAL")
    minimum = CD.integer(row["launchMinimumNs"], phase[0])
    require(minimum < caps[0] and row["launchArgv"] ==
        _command("_final-crypto", context_raw, caps, first.clock, boot, minimum, interpreter=start["argv"][0]),
        "CRYPTO_EXECUTED_ARGV")
    B.native_record(row["ownership"], start, row["leader"], row["launchArgv"])
    B.native_record(birth["ownership"], start, row["leader"], row["launchArgv"], terminal=False)
    require(birth["ownership"]["launches"] == row["ownership"]["launches"], "CRYPTO_BIRTH_JOIN")
    preparer = B.closed_lifetime(row["preparerIdentity"], first.clock.role)
    require(preparer == B.closed_lifetime(birth["preparerIdentity"], first.clock.role) and
        preparer["pid"] != row["leader"]["pid"], "CRYPTO_ORIGINAL_PREPARER")
    baseline = B.baseline_record(blobs["baseline.json"], first.clock.role)
    if baseline["baseline"] is not None:
        leader = B.lifetime(row["leader"], first.clock.role)
        require(list(leader[:4] if first.clock.role.startswith("macos-") else leader) not in baseline["baseline"],
            "CRYPTO_LEADER_PREEXISTED")
    require(row["captureOutcomes"] == {name: {key: True for key in
        ("synced", "verified", "closeAttempted", "closed", "readback")} for name in ("stdout", "stderr")} and
        row["captures"] == {name: {"sha256": O.digest(blobs[name + ".log"]), "bytes": len(blobs[name + ".log"])}
            for name in ("stdout", "stderr")}, "CRYPTO_CAPTURE_ORIGINAL_CLOSE")
    child = CD.fields(CD.canonical(child_raw), _CRYPTO_CHILD_FIELDS)
    ack = CD.fields(CD.canonical(blobs["stdout.log"], B.ACK_LIMIT), "schema scope invocation terminalSha256 clock closedNs")
    require(type(child["schema"]) is type(ack["schema"]) is int and child["schema"] == ack["schema"] == 1 and
        child["scope"] == CD.CRYPTO_CHILD_SCOPE and ack["scope"] == CD.CRYPTO_ACK_SCOPE and
        child["contextSha256"] == O.digest(context_raw) and child["startSha256"] == O.digest(blobs["start.json"]) and
        child["invocation"] == ack["invocation"] == start["invocation"] and
        child["clock"] == ack["clock"] == O.clock_value(first.clock) and child["bootDigest"] == boot and
        child["launchMinimumNs"] == minimum and ack["terminalSha256"] == O.digest(child_raw) and
        child["retirement"] == "PENDING_CHILD_CLOSE" and child["parent28Sha256"] == context["parent28Sha256"],
        "CRYPTO_CHILD_ORIGINAL_ACK6")
    CD.nonacceptance(child)
    for name in ("metadataCloseSha256", "recipientReturnSha256", "copyIndexSha256"):
        CD.sha(child[name])
    CD.local(child["childFirstLocal"])
    validation = _caps_record(child["validationCaps"], validation=True, caps=caps, first=first)
    exported = _caps_record(child["exportCaps"], validation=False, caps=caps, first=first)
    order = (minimum, child["beganNs"], child["metadataLastNs"], validation["firstNs"], child["validationReturnedNs"],
        child["freezeClosedNs"], exported["firstNs"], child["exportedNs"], ack["closedNs"], row["completedNs"], row["finalizedNs"])
    require(all(CD.integer(value) == value for value in order) and tuple(sorted(order)) == order and
        child["metadataLastNs"] < min(caps[0], caps[5], child["beganNs"] + 45 * NS) and
        child["validationReturnedNs"] < validation["operationFinishEndNs"] and child["freezeClosedNs"] < caps[0] and
        child["exportedNs"] < exported["operationFinishEndNs"] and ack["closedNs"] < caps[5] and
        row["completedNs"] < caps[5] and row["finalizedNs"] < caps[6] and
        minimum <= CD.integer(birth["observedNs"]) <= row["completedNs"] and
        child["childFirstLocal"] <= validation["firstLocal"] <= exported["firstLocal"], "CRYPTO_GENUINE_PHASE_CHRONOLOGY")
    manifest_data = CD.fields(child["manifest"], "bytes sha256 base64")
    require(type(manifest_data["base64"]) is str and len(manifest_data["base64"]) <= 4 * ((CD.PUBLIC_LIMIT + 2) // 3),
        "CRYPTO_MANIFEST_ENCODING_BOUND")
    try:
        manifest_raw = base64.b64decode(manifest_data["base64"], validate=True)
    except (ValueError, TypeError):
        raise O.OriginError("INITIAL_PRODUCTIVE_CUSTODY_CRYPTO_MANIFEST_ENCODING") from None
    manifest = CD.public_manifest(manifest_raw)
    require(base64.b64encode(manifest_raw).decode("ascii") == manifest_data["base64"] and
        len(manifest_raw) == CD.integer(manifest_data["bytes"], 1, CD.PUBLIC_LIMIT) and
        O.digest(manifest_raw) == CD.sha(manifest_data["sha256"]) and
        manifest["copy"]["index"]["sha256"] == child["copyIndexSha256"] and
        manifest["source"] == context["observed"]["source"], "CRYPTO_MANIFEST_NATIVE_JOIN")
    require(type(child["artifactNative"]) is list, "CRYPTO_ARTIFACT_NATIVE_VECTOR")
    stamp = CD.native(tuple(child["artifactNative"]), directory=False)
    require(stamp[6 if stamp[0] == "posix" else 4] == manifest["artifact"]["size"], "CRYPTO_ARTIFACT_NATIVE_SIZE")
    return start, row, child, ack, manifest_raw


@dataclass(frozen=True, repr=False)
class _CryptoFacts:
    parent: object
    native: object
    context_raw: bytes
    records: tuple
    child_raw: bytes
    phase: tuple
    manifest_raw: bytes
    graph: tuple


_CRYPTO_FACTS = {}


def _checked_native_crypto(state, result, *, retired=False):
    require(type(state.handle) is ParentFinal and type(result) is C._CryptoNativeReturn and
        state.native_return is result, "ORIGINAL_PRODUCTIVE_NATIVE_RETURN")
    _pin(result)
    saved = C._CRYPTO_NATIVE_RETURNS.get(id(result))
    require(type(saved) is tuple and len(saved) == 2, "PRODUCTIVE_NATIVE_RETURN_REGISTRY")
    original, graph = saved
    seed = _native_state(state.crypto_seed)
    owner, window = state.owner, seed.fence
    require(type(original) is tuple and len(original) == 14 and original[0] is result and original[1] is owner and
        original[2] is window and original[3] is owner.__dict__ and original[4] is owner._anchor() and
        original[10] is result.records and original[11] is result.child and original[12] is result.phase and
        original[13] is result.__dict__ and owner.phase_originals is result and result.context is state.context_raw and
        result.phase == seed.phase and seed.launch and original[5] is seed.launch[0] and original[8] is seed.launch[1],
        "PRODUCTIVE_NATIVE_ORIGINAL_REFERENCES")
    N._check_history(graph)
    anchor = owner.known() if retired else owner.check()
    require(anchor.failure is None and not anchor.unknown and not anchor.phase_active and
        anchor.phase[:3] == result.phase and owner.local_end == seed.end == anchor.binding[3] and
        original[9] <= seed.end and seed.completion, "PRODUCTIVE_NATIVE_ACTUAL_KNOWN_PHASE")
    for resource, label in zip(original[5:8], ("native-scope", "stdout", "stderr")):
        require(any(actual is resource and name == label and attempted is closed is True
            for _row, name, actual, attempted, closed in anchor.rows), "PRODUCTIVE_NATIVE_ACTUAL_RESOURCE_CLOSE")
    scope, child, code, completed_ns, reading, local, completion_graph = seed.completion
    N._check_history(completion_graph)
    require(scope is original[5] and child is original[8] and code == 0 and reading.clock == window.clock and
        completed_ns <= reading.nanoseconds < result.phase[1] and local < _SPANS[id(window)].work_local,
        "ORIGINAL_SUCCESS_ONLY_FINAL_TRANSITION")
    _methods_current(owner, seed.methods)
    parsed = _crypto_phase_data(result.context, result.records, result.child, result.phase,
        _clock(state.clock).first, _clock(state.clock).boot)
    require(parsed[1]["completedNs"] == completed_ns and parsed[1]["leader"]["pid"] == seed.launch[2],
        "ACTUAL_CHILD_COMPLETION_AND_LEADER")
    if state.crypto_facts is None:
        facts = _track(_CryptoFacts(state.handle, result, result.context, result.records, result.child, result.phase,
            parsed[4], N._history_graph(result.records, result.phase)))
        _CRYPTO_FACTS[id(facts)] = facts
        _update(state, crypto_facts=facts, start_raw=dict(result.records)["start.json"], manifest_raw=parsed[4])
    else:
        _check_crypto_facts(state)
        require(state.crypto_facts.native is result and state.crypto_facts.manifest_raw == parsed[4], "SAME_NATIVE_CRYPTO_FACTS")
    if retired:
        _check_owner_close(state.closed)
        require(state.closed.owner is owner, "ACTUAL_PARENT_NATIVE_OUTER_CLOSE")
    return result


def _check_crypto_facts(state):
    facts = _pin(state.crypto_facts)
    require(type(facts) is _CryptoFacts and _CRYPTO_FACTS.get(id(facts)) is facts and facts.parent is state.handle and
        facts.context_raw is state.context_raw and facts.manifest_raw is state.manifest_raw,
        "ORIGINAL_CRYPTO_DATA_OBSERVATION")
    N._check_history(facts.graph)
    return facts


def _manifest_index_join(state, raw):
    facts = _check_crypto_facts(state)
    index, manifest = CD.final_index(raw), CD.public_manifest(facts.manifest_raw)
    prior = CD.pre_index(dict(state.auxiliary)["pre-export-copy-index.json"])
    require(index["contextSha256"] == O.digest(facts.context_raw) and index["startSha256"] == O.digest(state.start_raw) and
        index["parent28Sha256"] == O.digest(dict(state.auxiliary)["pre-export-copy-index.json"]) and
        index["groups"][:28] == prior["groups"] and index["groups"] == manifest["copy"]["groups"] and
        manifest["copy"]["index"] == {"name": "copy-index.json", "bytes": len(raw), "sha256": O.digest(raw)},
        "ORIGINAL_INDEX_MANIFEST_PARENT28")
    expected = CD.canonical(_public_projection(dict(state.auxiliary), index["groups"], manifest["copy"]["index"]), CD.PUBLIC_LIMIT)
    expected.update(scope="ENCRYPTED_PRIVATE_INITIAL_RECIPIENT_PRODUCTIVE_EVIDENCE_V1",
        recipient=manifest["recipient"], artifact=manifest["artifact"], testAcceptance="NOT_PERFORMED",
        productiveAuthority=False, cacheAuthority=False, exportSaveAuthority=False, budgetAcceptance="NOT_ADMITTED")
    require(O.encoded(expected) == facts.manifest_raw and manifest["recipient"]["fingerprint"] == manifest["policy"]["fingerprint"] and
        manifest["recipient"]["keySha256"] == manifest["policy"]["keySha256"], "COMPLETE_PUBLIC_SOURCE_PROJECTION")
    child = CD.canonical(facts.child_raw)
    times = [read["returnedNs"] for read in index["reads"]]
    require(times == sorted(times) and child["validationReturnedNs"] <= times[0] <= times[-1] <= child["freezeClosedNs"],
        "INDEX_ALL_READS_BEFORE_FREEZE_CLOSE")
    if type(state.handle) is ParentFinal:
        require([_group_reference(partition) for partition in state.partitions] == prior["groups"],
            "SAME_ACTUAL_PARENT28")
    return index, manifest


def _control_roster(state, count, *, post):
    require(count in (0, 2, 5) and type(post) is bool, "FIXED_LATER_FILE_POSITION")
    owner = _file_owner(state)
    try:
        context = CD.crypto_context(state.context_raw)
        root = C._private(owner, _path(state, "root"))
        returned = C._private(owner, _path(state, "returned"))
        service = C._private(owner, _path(state, "crypto-service"))
        output = C._private(owner, _path(state, "export-output"))
        require(all(tuple(directory.identity) == tuple(context["directories"][name]) for name, directory in
            (("root", root), ("returned", returned), ("crypto-service", service))), "ORIGINAL_CONTROL_ROOT_PINS")
        roots = {"payload", "public-crypto", "returned", "export-output", "authority-pre-export"}
        if post:
            roots.add("authority-post-export")
        require(set(_names(owner, root)) == roots and set(_names(owner, service)) == B.PHASE_FILES and
            set(_names(owner, returned)) == {"control-home", "temporary", "crypto-service", "context.json",
                "crypto-child-result.json", *(name for name, _maximum in CD.CRYPTO_INPUTS), *CD.LATER_FILES[:count]} and
            set(_names(owner, output)) == {B.posix.ARTIFACT, B.posix.MANIFEST}, "FIXED_FINAL_CONTROL_ROSTER")
        if os.name == "nt":
            require(tuple(output.identity) == tuple(context["directories"]["export-output"]), "ORIGINAL_WINDOWS_OUTPUT_ROOT")
        for name in ("control-home", "temporary"):
            directory = C._private(owner, _path(state, name))
            require(tuple(directory.identity) == tuple(context["directories"][name]) and _names(owner, directory) == (),
                "ORIGINAL_EMPTY_CONTROL_ROOT")
        _charge(owner, nodes=6)
        return _close_owner(owner)
    except BaseException as error:
        _abort_owner(owner, error)
        raise _fail(state, error)


@dataclass(eq=False, repr=False)
class _CipherInput:
    handle: object
    owner: object
    reader: object
    size: int
    checksum: object
    total: int = 0


_CIPHER_STREAMS, _CIPHERTEXT_READS = {}, {}


class _CipherStream:
    """The maintained packet parser's forward seeks consume/hash actual bytes."""
    __slots__ = ()

    def _binding(self):
        value = _CIPHER_STREAMS.get(id(self))
        require(type(value) is _CipherInput and value.handle is self, "ORIGINAL_CIPHERTEXT_STREAM")
        _pin(value)
        value.owner.guard()
        return value

    def read(self, count):
        value = self._binding()
        require(type(count) is int and 0 <= count <= C.COPY_CHUNK and count <= value.size - value.total + 1,
            "CIPHERTEXT_BOUNDED_READ")
        raw = value.reader.read(count)
        require(type(raw) is bytes and len(raw) <= count and value.total + len(raw) <= value.size, "CIPHERTEXT_SHORT_OR_EXTRA")
        value.checksum.update(raw)
        _update(value, total=value.total + len(raw))
        _charge(value.owner, len(raw))
        value.owner.guard()
        return raw

    def tell(self):
        return self._binding().total

    def seek(self, count, whence):
        value = self._binding()
        require(type(count) is int and 0 <= count <= value.size - value.total and whence == os.SEEK_CUR,
            "CIPHERTEXT_FORWARD_ONLY")
        remaining = count
        while remaining:
            raw = self.read(min(C.COPY_CHUNK, remaining))
            require(raw, "CIPHERTEXT_TRUNCATED")
            remaining -= len(raw)
        return self.tell()


@dataclass(frozen=True, repr=False)
class _CipherRead:
    parent: object
    path: object
    reference_raw: bytes
    native: tuple
    root_native: tuple
    stream: object
    close: object
    reading: object
    graph: tuple
    raw: bytes


def _ciphertext_read(state, manifest, native):
    require(not state.ciphertext, "ONE_ACTUAL_CIPHERTEXT_READ")
    artifact = manifest["artifact"]
    owner = _file_owner(state, ciphertext=True)
    try:
        directory = C._private(owner, _path(state, "export-output"))
        require(set(_names(owner, directory)) == {B.posix.ARTIFACT, B.posix.MANIFEST}, "CIPHERTEXT_OUTPUT_ROSTER")
        root_native = _directory_stamp(directory)
        # Ciphertext is not passed to the512MiB copier or a whole Snapshot.
        end, path = owner.guard(), directory.path / B.posix.ARTIFACT
        if os.name == "nt":
            reader = owner.acquire("reader", lambda: directory.open_file(B.posix.ARTIFACT,
                max_bytes=B.posix.MAX_CIPHERTEXT_BYTES, deadline=end))
            original = reader.initial_info
            stamp = _native_from_info(original)
            def verify():
                require(reader.verify() == original, "CIPHERTEXT_WINDOWS_FULL_BINDING")
                directory.verify()
        else:
            reader = owner.acquire("reader", lambda: Q._posix_stream(path, os.O_RDONLY | os.O_NOFOLLOW, "rb"))
            Q._file_info(path, reader, B.posix.MAX_CIPHERTEXT_BYTES)
            stamp = CD.native(("posix", *B.posix._stamp(os.fstat(reader.fileno()))), directory=False)
            def verify():
                Q._file_info(path, reader, B.posix.MAX_CIPHERTEXT_BYTES)
                require(("posix", *B.posix._stamp(os.fstat(reader.fileno()))) == stamp and
                    ("posix", *B.posix._stamp(os.stat(path, follow_symlinks=False))) == stamp,
                    "CIPHERTEXT_POSIX_FULL_BINDING")
                directory.verify()
        require(stamp == native and artifact["size"] == stamp[6 if stamp[0] == "posix" else 4] and
            32 < artifact["size"] <= B.posix.MAX_CIPHERTEXT_BYTES, "CIPHERTEXT_ORIGINAL_ARTIFACT_NATIVE")
        verify()
        stream = _CipherStream()
        binding = _track(_CipherInput(stream, owner, reader, artifact["size"], hashlib.sha256()))
        _CIPHER_STREAMS[id(stream)] = binding
        B.posix._ciphertext_stream(stream, artifact["size"], manifest["recipient"]["encryptionFingerprint"])
        require(binding.total == artifact["size"] and stream.read(1) == b"" and
            binding.checksum.hexdigest() == artifact["sha256"], "CIPHERTEXT_COMPLETE_HASH_AND_EOF")
        verify()
        _charge(owner, nodes=2)
        owner.close_one(reader)
        require(_directory_stamp(directory) == root_native and
            set(_names(owner, directory)) == {B.posix.ARTIFACT, B.posix.MANIFEST}, "CIPHERTEXT_OUTPUT_CHANGED")
        close = _close_owner(owner)
        state.clock.now()
        reading = _clock(state.clock).reading
        raw = O.encoded({"schema": 1, "scope": "INITIAL_RECIPIENT_PRODUCTIVE_ACTUAL_CIPHERTEXT_READ_V1",
            "artifact": artifact, "native": list(stamp), "directoryNative": list(root_native),
            "readCloseSha256": O.digest(close.raw), "returnedNs": reading.nanoseconds,
            "integrity": "OUTER_PACKET_ONLY_NOT_DECRYPTED", "exportSaveAuthority": False})
        result = _track(_CipherRead(state.handle, path, O.encoded(artifact), stamp, root_native, stream, close, reading,
            N._history_graph(reading), raw))
        _CIPHERTEXT_READS[id(result)] = result
        _update(state, ciphertext=(result,), union=(*state.union, (path, stamp), (directory.path, root_native)))
        return result
    except BaseException as error:
        _abort_owner(owner, error)
        raise _fail(state, error)


def _check_ciphertext_read(result, state):
    _pin(result)
    require(type(result) is _CipherRead and _CIPHERTEXT_READS.get(id(result)) is result and result.parent is state.handle and
        result.path == _path(state, "export-output") / B.posix.ARTIFACT, "ORIGINAL_CIPHERTEXT_READ")
    _check_owner_close(result.close)
    N._check_history(result.graph)
    binding = _CIPHER_STREAMS.get(id(result.stream))
    _pin(binding)
    reference = CD.canonical(result.reference_raw)
    require(binding.handle is result.stream and binding.owner is result.close.owner and binding.total == binding.size ==
        reference["size"] and binding.checksum.hexdigest() == reference["sha256"], "ORIGINAL_CIPHERTEXT_STREAM_RETURN")
    return result


def _parent_returned_records(state):
    require(type(state.handle) is ParentFinal and _clock(state.clock).phase == 3 and state.closed is not None and
        not state.final_records, "PARENT_READ_PHASE_POSITION")
    facts = _check_crypto_facts(state)
    selections = [(_path(state, "returned"), "context.json", CD.PUBLIC_LIMIT, state.context_raw, None),
        (_path(state, "returned"), "crypto-child-result.json", CD.LIMIT, facts.child_raw, None),
        (_path(state, "export-output"), B.posix.MANIFEST, CD.PUBLIC_LIMIT, facts.manifest_raw, None),
        (_path(state, "payload"), "copy-index.json", CD.LIMIT, None, None)]
    selections.extend((_path(state, "returned"), name, maximum, dict(state.auxiliary)[name], None)
        for name, maximum in CD.CRYPTO_INPUTS)
    selections.extend((_path(state, "crypto-service"), name,
        B.ACK_LIMIT if name == "stdout.log" else B.STDERR_LIMIT if name == "stderr.log" else CD.LIMIT, raw, None)
        for name, raw in facts.records)
    reads, _close = _read_files(state, selections)
    index_read = next(read for read in reads if read.path == _path(state, "payload") / "copy-index.json")
    _manifest_index_join(state, index_read.raw)
    _update(state, index=_expected(state, "copy-index.json", index_read.native, count=len(index_read.raw),
        checksum=O.digest(index_read.raw), path=index_read.path, raw=index_read.raw, close=index_read.close))
    manifest = CD.public_manifest(facts.manifest_raw)
    _control_roster(state, 0, post=False)
    _ciphertext_read(state, manifest, tuple(CD.canonical(facts.child_raw)["artifactNative"]))
    _actual_host(state, CD.canonical(state.handoff.history)["observed"], state.handoff.identity.original_event)
    _checked_native_crypto(state, state.native_return, retired=True)
    _final_inputs_closed(state)
    authority = _checked_authority(state.authority, state, retired=True)
    raw = O.encoded({"schema": 1, "scope": CD.CUSTODY_RETURN_SCOPE, "operation": "custody-export",
        "contextSha256": O.digest(state.context_raw), "startSha256": O.digest(state.start_raw),
        "childSha256": O.digest(facts.child_raw), "nativeRecordsSha256": {name: O.digest(blob) for name, blob in facts.records},
        "nativePhase": list(facts.phase), "nativeOwnerClose": CD.canonical(state.closed.raw),
        "manifestSha256": O.digest(facts.manifest_raw), "copyIndexSha256": state.index.sha256,
        "preExportReturnSha256": O.digest(authority.raw), "preExportIndexSha256": O.digest(authority.index_raw),
        "parent28Sha256": O.digest(dict(state.auxiliary)["pre-export-copy-index.json"]), "claims": CD.canonical(state.claims_raw),
        "authorityClosedNs": CD.authority_return(authority.raw, post=False)["closedNs"], "returnedNs": state.clock.now(),
        "writerReturn": CD.PENDING, "originalStepOutcome": "NOT_OBSERVED", "budgetAcceptance": "NOT_ADMITTED",
        "exportSaveAuthority": False})
    CD.custody_return(raw)
    custody, custody_close = _write_fixed(state, _path(state, "returned"), CD.LATER_FILES[0], raw)
    transfer_raw = O.encoded({"schema": 1, "scope": CD.EXPORT_TRANSFER_SCOPE, "operation": "custody-export",
        "custodyReturnSha256": custody.sha256, "manifestSha256": O.digest(facts.manifest_raw),
        "copyIndexSha256": state.index.sha256, "preExportReturnSha256": O.digest(authority.raw),
        "preExportIndexSha256": O.digest(authority.index_raw), "contextSha256": O.digest(state.context_raw),
        "parent28Sha256": O.digest(dict(state.auxiliary)["pre-export-copy-index.json"]),
        "custodyWriterCloseSha256": O.digest(custody_close.raw), "returnedNs": state.clock.now(),
        "originalStepOutcome": "NOT_OBSERVED", "writerReturn": CD.PENDING, "budgetAcceptance": "NOT_ADMITTED",
        "exportSaveAuthority": False})
    CD.export_transfer(transfer_raw)
    transfer, _close = _write_fixed(state, _path(state, "returned"), CD.LATER_FILES[1], transfer_raw)
    _update(state, actual_raw=raw, final_records=(custody, transfer), stage="export-files-closed")
    _control_roster(state, 2, post=False)
    _check_union(state)


@dataclass(frozen=True, repr=False)
class _CollectHistory:
    """Actual freshly read historical DATA, not any earlier A/PC owner return."""
    history: bytes
    proposal: bytes
    identity: object
    source_records: tuple
    raw: bytes
    reads: tuple
    graph: tuple


_COLLECT_HISTORIES = {}


def _original_read(state, path):
    reads = tuple(read for read in state.observations if type(read) is _FileRead and read.path == path)
    require(reads, "ACTUAL_ORIGINAL_FILE_READ_REQUIRED")
    for read in reads:
        _check_file_read(read)
        require(read.parent is state.handle and read.raw == reads[0].raw and read.native == reads[0].native,
            "REPEATED_ORIGINAL_FILE_READ_CHANGED")
    return reads[0]


def _collect_predecessor(state):
    require(type(state.handle) is CollectPrepared, "FRESH_COLLECT_PREDECESSOR")
    custody_read = _original_read(state, _path(state, "returned") / CD.LATER_FILES[0])
    transfer_read = _original_read(state, _path(state, "returned") / CD.LATER_FILES[1])
    custody, transfer = CD.custody_return(custody_read.raw), CD.export_transfer(transfer_read.raw)
    claims = dict(state.claims)
    require(claims[CD.EXPORT_CLAIMS[0]] == "success" and claims[CD.EXPORT_CLAIMS[1]] == O.digest(transfer_read.raw) and
        claims[CD.EXPORT_CLAIMS[2]] == transfer["manifestSha256"] == custody["manifestSha256"] == O.digest(state.manifest_raw) and
        transfer["custodyReturnSha256"] == O.digest(custody_read.raw) and custody["claims"] ==
        {name: claims[name] for name in CD.FINAL_CLAIMS}, "ORIGINAL_EXPORT_STEP_NOT_PENDING_FILE")
    for name in ("copyIndexSha256", "preExportReturnSha256", "preExportIndexSha256", "contextSha256", "parent28Sha256"):
        require(transfer[name] == custody[name], "ORIGINAL_EXPORT_STEP_DIGEST_CHAIN")
    facts = _check_crypto_facts(state)
    require(custody["contextSha256"] == O.digest(facts.context_raw) and custody["startSha256"] == O.digest(state.start_raw) and
        custody["childSha256"] == O.digest(facts.child_raw) and custody["nativeRecordsSha256"] ==
        {name: O.digest(raw) for name, raw in facts.records} and tuple(custody["nativePhase"]) == facts.phase and
        custody["copyIndexSha256"] == state.index.sha256 and
        custody["parent28Sha256"] == O.digest(dict(state.auxiliary)["pre-export-copy-index.json"]) and
        custody["preExportReturnSha256"] == O.digest(dict(state.auxiliary)["authority-return.json"]) and
        custody["preExportIndexSha256"] == O.digest(dict(state.auxiliary)["authority-index.json"]) and
        custody["authorityClosedNs"] == CD.authority_return(dict(state.auxiliary)["authority-return.json"], post=False)["closedNs"] and
        CD.canonical(dict(facts.records)["result.json"])["finalizedNs"] <= custody["returnedNs"] <= transfer["returnedNs"] <=
        _clock(state.clock).first.nanoseconds, "ACTUAL_COLLECT_PREDECESSOR_COMPLETED")
    CD.owner_close(custody["nativeOwnerClose"], native_owner=True)
    return {"step": "custody-export", "stepOutcome": "success", "exportTransferSha256": O.digest(transfer_read.raw),
        "manifestSha256": custody["manifestSha256"], "custodyReturnSha256": O.digest(custody_read.raw),
        **{name: custody[name] for name in ("copyIndexSha256", "preExportReturnSha256", "preExportIndexSha256")}}


def _collect_history(state, final, identity):
    require(type(state.handle) is CollectPrepared and state.handoff is None, "COLLECT_HISTORICAL_DATA_ONCE")
    path = N._receiving_path() / "dependency-save-handoff"
    expected = {"worker-identity.json": identity.record, "history.json": O.encoded(final["history"]),
        "allocation-proposal.json": O.encoded(final["originalProposal"])}
    selections = [(path, "save-handoff.json", CD.LIMIT, None, None)]
    selections.extend((path, name, CD.LIMIT, raw, None) for name, raw in expected.items())
    selections.extend((path, name + ".bin", CD.LIMIT, None, None) for name in D.SOURCE_KEYS)
    reads, _close = _read_files(state, selections)
    handoff = CD.canonical(reads[0].raw)
    require(type(handoff.get("schema")) is int and handoff["schema"] == 2 and handoff.get("scope") == D.HANDOFF_SCOPE and
        O.digest(reads[0].raw) == final["claims"]["HANDOFF_SHA256"] and handoff["directory"] == str(path) and
        D.native_identity(handoff["directoryIdentity"], _clock(state.clock).first.clock.role) == reads[0].directory_native[1:3] and
        handoff["writerReturn"] == D.PENDING and handoff["providerExecution"] == "NOT_PERFORMED" and
        handoff["nextPhaseAuthority"] is False, "ACTUAL_COLLECT_ORIGINAL_HANDOFF_DATA")
    CD.nonacceptance(handoff)
    CD.fields(handoff["blobs"], D.BLOB_NAMES)
    for read in reads[1:]:
        require(handoff["blobs"][read.path.name] == {"bytes": len(read.raw), "sha256": O.digest(read.raw)} and
            read.directory_native[1:3] == reads[0].directory_native[1:3], "COLLECT_ACTUAL_BLOB_HASH_JOIN")
    sources = tuple((name, next(read.raw for read in reads if read.path.name == name + ".bin")) for name in D.SOURCE_KEYS)
    require({name: O.digest(raw) for name, raw in sources} == final["sourceRecordsSha256"] and
        dict(sources)["candidate_policy_raw"] == identity.original_policy and handoff["source"] == final["observed"]["source"] and
        handoff["references"]["prefixRetention"]["files"]["retention-index.json"]["sha256"] == final["prefixRetentionSha256"],
        "COLLECT_ORIGINAL_SOURCE_AND_PREFIX")
    D.original_proposal(expected["allocation-proposal.json"], identity, expected["history.json"], _clock(state.clock).first.clock)
    result = _track(_CollectHistory(expected["history.json"], expected["allocation-proposal.json"], identity, sources,
        reads[0].raw, reads, N._history_graph(identity, sources)))
    _COLLECT_HISTORIES[id(result)] = result, state.handle
    _update(state, handoff=result)
    _shorten_clock(state.clock, final["originalProposal"])
    _update(state, phase_caps=_clock(state.clock).ends)
    _actual_host(state, final["observed"], identity.original_event)
    return result


def _checked_collect_history(state):
    history = _pin(state.handoff)
    saved = _COLLECT_HISTORIES.get(id(history))
    require(type(history) is _CollectHistory and type(saved) is tuple and saved[0] is history and saved[1] is state.handle,
        "ORIGINAL_FRESH_COLLECT_HISTORY")
    N._check_history(history.graph)
    for read in history.reads:
        _check_file_read(read)
    return history


def prepare_final_collect(token, cancelled):
    state = None
    try:
        state = _new_state(CollectPrepared, "prepare-final-collect", cancelled, _COLLECT_PHASES)
        selections = [(_path(state, "returned"), name, CD.PUBLIC_LIMIT if name == "context.json" else CD.LIMIT, None, None)
            for name in ("context.json", "crypto-child-result.json", *CD.LATER_FILES[:2])]
        selections.extend((_path(state, "returned"), name, maximum, None, None) for name, maximum in CD.CRYPTO_INPUTS)
        selections.extend((_path(state, "crypto-service"), name,
            B.ACK_LIMIT if name == "stdout.log" else B.STDERR_LIMIT if name == "stderr.log" else CD.LIMIT, None, None)
            for name in sorted(B.PHASE_FILES))
        selections.extend(((_path(state, "export-output"), B.posix.MANIFEST, CD.PUBLIC_LIMIT, None, None),
            (_path(state, "payload"), "copy-index.json", CD.LIMIT, None, None)))
        reads, _close = _read_files(state, selections)
        by_path = {read.path: read for read in reads}
        context_raw = by_path[_path(state, "returned") / "context.json"].raw
        context = CD.crypto_context(context_raw)
        basis = _clock(state.clock)
        require(context["root"] == str(ROOT) and context["session"] == str(_path(state, "returned")) and
            context["clock"] == O.clock_value(basis.first.clock) and context["originalBootDigest"] == basis.boot,
            "FRESH_COLLECT_ACTUAL_CLOCK_HOST")
        for read in reads:
            for name, path in state.paths:
                if read.path.parent == path and name in context["directories"]:
                    require(read.directory_native[1:3] == tuple(context["directories"][name]), "COLLECT_ORIGINAL_DIRECTORY_PIN")
        raws = {name: by_path[_path(state, "returned") / name].raw for name, _maximum in CD.CRYPTO_INPUTS}
        final, prior, identity, _policy = _crypto_inputs_data(context_raw, raws, basis.first.clock, basis.boot)
        require(final["claims"] == {name: dict(state.claims)[name] for name in CD.FINAL_CLAIMS}, "COLLECT_ORIGINAL_STEP_CLAIMS")
        records = tuple((name, by_path[_path(state, "crypto-service") / name].raw) for name in sorted(B.PHASE_FILES))
        start_raw = dict(records)["start.json"]
        start = CD.canonical(start_raw)
        phase = tuple(start[name] for name in ("startedNs", "workEndNs", "finalEndNs"))
        child_raw = by_path[_path(state, "returned") / "crypto-child-result.json"].raw
        parsed = _crypto_phase_data(context_raw, records, child_raw, phase, basis.first, basis.boot)
        manifest_raw = by_path[_path(state, "export-output") / B.posix.MANIFEST].raw
        require(manifest_raw == parsed[4] and parsed[1]["finalizedNs"] <= basis.first.nanoseconds,
            "COLLECT_ACTUAL_NATIVE_BYTES_NOT_RESTORED_RETURN")
        facts = _track(_CryptoFacts(state.handle, None, context_raw, records, child_raw, phase, manifest_raw,
            N._history_graph(records, phase)))
        _CRYPTO_FACTS[id(facts)] = facts
        index_read = by_path[_path(state, "payload") / "copy-index.json"]
        index = _expected(state, "copy-index.json", index_read.native, count=len(index_read.raw),
            checksum=O.digest(index_read.raw), path=index_read.path, raw=index_read.raw, close=index_read.close)
        _update(state, context_raw=context_raw, start_raw=start_raw, auxiliary=tuple((name, raws[name]) for name, _ in CD.CRYPTO_INPUTS),
            manifest_raw=manifest_raw, crypto_facts=facts, index=index, transport=reads, stage="collect-inputs-closed")
        _collect_predecessor(state)
        _collect_history(state, final, identity)
        index_value, manifest = _manifest_index_join(state, index_read.raw)
        _control_roster(state, 2, post=False)
        _read30(state, index_value["groups"])
        require(dict(state.readback[28].records) == {str(_path(state, "returned") / name): raw for name, raw in state.auxiliary},
            "COLLECT_ACTUAL9_TRANSPORT_STREAMS")
        embedded = state.readback[29].records
        require(len(embedded) == 1 and embedded[0][0] == "recipient-return.json" and
            O.digest(embedded[0][1]) == CD.canonical(child_raw)["recipientReturnSha256"], "COLLECT_ONE_ORIGINAL_EMBEDDED_RETURN")
        _update(state, root=_payload_roster(state, indexed=True))
        _ciphertext_read(state, manifest, tuple(CD.canonical(child_raw)["artifactNative"]))
        _advance(state.clock, "ciphertext-verify")
        _acquire_authority(state, token, post=True)
        token = None
        _checked_collect_history(state)
        _collect_predecessor(state)
        _checked_authority(state.authority, state)
        _check_union(state)
        _update(state, stage="collect-prepared")
        return state.handle
    except BaseException as error:
        if state is not None:
            _abort_state(state, error)
            raise _fail(state, error)
        raise
    finally:
        token = None


def _read_reference(read):
    _check_file_read(read)
    return {"path": str(read.path), "bytes": len(read.raw), "sha256": O.digest(read.raw), "native": list(read.native),
        "readCloseSha256": O.digest(read.close.raw)}


def finish_final_collect(prepared):
    state = _state(prepared)
    try:
        require(type(prepared) is CollectPrepared and state.stage == "collect-prepared" and not state.busy and
            state.result is None and len(state.readback) == 30 and len(state.ciphertext) == 1, "FRESH_COLLECT_FINISH_ONCE")
        _update(state, busy=True)
        _environment(state)
        authority = _checked_authority(state.authority, state)
        require(authority.post, "FRESH_POST_AUTHORITY_REQUIRED")
        prior = _collect_predecessor(state)
        _advance(state.clock, "custody-owner-return")
        # This once-selected actual owner-return45 cap is saved BEFORE writers;
        # no exported first4 exist here and no later callback creates another45.
        _update(state, phase_caps=_clock(state.clock).ends)
        post_return, return_close = _write_fixed(state, _path(state, "returned"), CD.LATER_FILES[2], authority.raw)
        post_index, index_close = _write_fixed(state, _path(state, "returned"), CD.LATER_FILES[3], authority.index_raw)
        CD.authority_return(authority.raw, post=True)
        CD.authority_index(authority.index_raw, post=True)
        # Original small records are natively reopened, fully read and closed.
        # This is not a second read28/read30, nor a replayed child validation.
        _read_files(state, tuple((read.path.parent, read.path.name,
            B.ACK_LIMIT if read.path.name == "stdout.log" else B.STDERR_LIMIT if read.path.name == "stderr.log" else CD.LIMIT,
            read.raw, read.native) for read in state.transport))
        _actual_host(state, CD.canonical(state.handoff.history)["observed"], state.handoff.identity.original_event)
        _checked_collect_history(state)
        _checked_authority(authority, state, retired=True)
        _check_ciphertext_read(state.ciphertext[0], state)
        _check_union(state)
        original_reads = [_read_reference(read) for read in state.transport]
        final_reads = [{"ordinal": read.partition.ordinal, "mapSha256": O.digest(read.map_raw),
            "closeSha256": O.digest(read.close.raw), "returnedNs": read.returned_ns} for read in state.readback]
        closes = [O.digest(_check_owner_close(_OWNER_CLOSES[id(owner)]).raw) for owner in state.owners]
        closes.append(O.digest(authority.close.raw))
        raw = O.encoded({"schema": 1, "scope": CD.COLLECT_CLOSE_SCOPE, "operation": "custody-collect",
            "originalExportStepOutcome": "success", **{name: prior[name] for name in
                ("exportTransferSha256", "manifestSha256", "custodyReturnSha256", "copyIndexSha256", "preExportReturnSha256",
                 "preExportIndexSha256")}, "postExportReturnSha256": post_return.sha256, "postExportIndexSha256": post_index.sha256,
            "postWriterCloseSha256": O.digest(O.encoded([CD.canonical(return_close.raw), CD.canonical(index_close.raw)])),
            "originalReadsSha256": O.digest(O.encoded(original_reads)), "finalRead30Sha256": O.digest(O.encoded(final_reads)),
            "ciphertextReadSha256": O.digest(state.ciphertext[0].raw), "ownerClosesSha256": O.digest(O.encoded(closes)),
            "returnedNs": state.clock.now(), "originalStepOutcome": "NOT_OBSERVED", "writerReturn": CD.PENDING,
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        CD.collect_close(raw)
        closed, _close = _write_fixed(state, _path(state, "returned"), CD.LATER_FILES[4], raw)
        _update(state, actual_raw=raw, final_records=(post_return, post_index, closed), stage="collect-files-closed")
        _control_roster(state, 5, post=True)
        result = _register_final_return(state, collect=True)
        _update(state, busy=False, stage="collect-returned")
        checked_final_collect_return(result)
        return result
    except BaseException as error:
        _abort_state(state, error)
        raise _fail(state, error)


@dataclass(frozen=True, repr=False)
class _FinalReturn:
    parent: object
    result: object
    collect: bool
    records: tuple
    outputs: tuple
    fence: object
    hard_end: int


@dataclass(eq=False, repr=False)
class _OutputState:
    parent: object
    fence: object
    result: object
    hard_end: int
    busy: bool = False
    failure: object = None


def _retired_final_state(state, *, collect):
    require(type(state.handle) is (CollectPrepared if collect else ParentFinal) and state.result is not None and
        not state.abort_started and len(state.ciphertext) == 1 and state.manifest_raw is not None and
        _clock(state.clock).phase == (2 if collect else 3), "FINAL_STATE_ACTUALLY_COMPLETED")
    _check_crypto_facts(state)
    for owner in state.owners:
        require(id(owner) in _OWNER_CLOSES, "ALL_ORIGINAL_FILE_OWNERS_CLOSED")
        _check_owner_close(_OWNER_CLOSES[id(owner)])
    for node in state.final_records:
        _node_current(node)
        _check_owner_close(node.provenance.close)
    _check_ciphertext_read(state.ciphertext[0], state)
    if collect:
        require(len(state.readback) == 30 and state.authority.post is True and state.crypto_facts.native is None,
            "COLLECT_FRESH_READS_NOT_RESTORED_NATIVE_OWNER")
        _checked_collect_history(state)
        _collect_predecessor(state)
    else:
        require(len(state.partitions) == 28 and state.authority.post is False, "EXPORT_ACTUAL_PARENT28")
        _final_inputs_closed(state)
        _checked_native_crypto(state, state.native_return, retired=True)
    _checked_authority(state.authority, state, retired=True)
    _check_union(state, retired=True)


def _final_return_passive(result, *, collect):
    saved = _RESULTS.get(id(result))
    require(type(saved) is _FinalReturn and saved.result is result and type(result) is
        (CollectReturn if collect else ParentReturnedCrypto) and saved.collect is collect, "ORIGINAL_FINAL_RETURN_TYPE")
    _pin(saved)
    _pin(result)
    state = _state(saved.parent)
    require(state.result is result and state.final_records is saved.records and result.output_values is saved.outputs and
        result.fence is saved.fence and result.hard_end_ns is saved.hard_end and state.outputs is saved.outputs and
        saved.hard_end == state.phase_caps[-1], "ORIGINAL_FINAL_RETURN_SLOTS")
    CD.output_values(result.output_values, collect=collect)
    require(saved.outputs[0][1] == state.final_records[-1].sha256 and
        saved.outputs[1][1] == O.digest(state.manifest_raw), "ACTUAL_CLOSED_OUTPUT_HASHES")
    output = _OUTPUTS.get(id(saved.fence))
    require(type(output) is _OutputState and output.parent is state.handle and output.result is result and
        output.fence is saved.fence and output.hard_end is saved.hard_end, "ORIGINAL_FINAL_OUTPUT_FENCE")
    _pin(output)
    if id(output) in _FAILURES:
        raise _FAILURES[id(output)][1]
    _retired_final_state(state, collect=collect)
    return state


class _FinalOutputFence:
    """Every append boundary is checked; only P owns the later two-use counter."""
    __slots__ = ()

    def now(self, *, final=False, minimum=0, limit=None):
        output = _OUTPUTS.get(id(self))
        require(type(output) is _OutputState and output.fence is self, "ORIGINAL_FINAL_OUTPUT")
        failed = _FAILURES.get(id(output))
        if failed is not None:
            raise failed[1]
        try:
            _pin(output)
            require(not output.busy and final is True and type(minimum) is int and minimum == 0 and
                type(limit) is int and limit == output.hard_end, "EXACT_FINAL_OUTPUT_CALL")
            _update(output, busy=True)
            collect = type(output.result) is CollectReturn
            state = _final_return_passive(output.result, collect=collect)
            _environment(state)
            observed = state.clock.now(final=True, limit=output.hard_end)
            require(output.hard_end == state.phase_caps[-1], "SAVED_OUTPUT_HARD_END")
            _final_return_passive(output.result, collect=collect)
            _environment(state)
            return observed
        except BaseException as error:
            raise _fail(output, error)
        finally:
            _owned_slot(output, "busy", False)


def _register_final_return(state, *, collect):
    require(type(collect) is bool and state.result is None and state.stage ==
        ("collect-files-closed" if collect else "export-files-closed") and len(state.final_records) == (3 if collect else 2),
        "ACTUAL_FINAL_RETURN_ONCE")
    state.clock.now(final=True)
    hard_end = state.phase_caps[-1]
    fields = CD.COLLECT_OUTPUT_FIELDS if collect else CD.EXPORT_OUTPUT_FIELDS
    outputs = ((fields[0], state.final_records[-1].sha256), (fields[1], O.digest(state.manifest_raw)))
    CD.output_values(outputs, collect=collect)
    fence = _FinalOutputFence()
    result = _track((CollectReturn if collect else ParentReturnedCrypto)(outputs, fence, hard_end))
    original = _track(_FinalReturn(state.handle, result, collect, state.final_records, outputs, fence, hard_end))
    _RESULTS[id(result)] = original
    _OUTPUTS[id(fence)] = _track(_OutputState(state.handle, fence, result, hard_end))
    _update(state, result=result, outputs=outputs)
    _final_return_passive(result, collect=collect)
    return result


def checked_final_export_return(value):
    return _checked_final_return(value, collect=False)


def checked_final_collect_return(value):
    return _checked_final_return(value, collect=True)


def _checked_final_return(value, *, collect):
    original = _RESULTS.get(id(value))
    try:
        state = _final_return_passive(value, collect=collect)
        value.fence.now(final=True, limit=state.phase_caps[-1])
        return value
    except BaseException as error:
        if type(original) is _FinalReturn and original.result is value:
            state = _STATES.get(id(original.parent))
            if state is not None:
                raise _fail(state, error)
        raise
