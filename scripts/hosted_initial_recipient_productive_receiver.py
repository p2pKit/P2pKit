"""Actual productive seal and same-process BEFORE, with no workflow activation.

Fresh source12/native24/source12 observations are acquired on the ONE P.C/N/B
graph.  Historical productive exports never become current owners.  All
receiver work, BEFORE and its future K consumer share the original seal120
end; the original allocation remains NOT_ADMITTED and must be qualified.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import io
import math
import os
from pathlib import Path
import re
import time
import uuid

import hosted_initial_recipient_productive as P
import hosted_initial_recipient_productive_custody as PC
import hosted_initial_recipient_productive_receiver_data as RD


C, N, B, O, Q = P.C, P.N, P.B, P.O, P.Q
CD, D, NS = RD.CD, RD.D, RD.NS
ROOT, SCRIPTS = P.ROOT, P.SCRIPTS
_ENTRIES, _STATES, _PINS, _CLOSES, _NATIVE_SEEDS, _NATIVE_OWNERS, _RETURNS, _OUTPUTS = {}, {}, {}, {}, {}, {}, {}, {}
_REGISTRIES = (_ENTRIES, _STATES, _PINS, _CLOSES, _NATIVE_SEEDS, _NATIVE_OWNERS, _RETURNS, _OUTPUTS)
_QUARANTINE = []


def require(value, reason):
    O.require(value, "INITIAL_PRODUCTIVE_RECEIVER_" + reason)


def _track(value):
    require(id(value) not in _PINS and type(value.__dict__) is dict, "NEW_TRACKED_VALUE")
    _PINS[id(value)] = value, type(value), value.__dict__, tuple(value.__dict__.items())
    return value


def _pin(value):
    saved = _PINS.get(id(value))
    require(type(saved) is tuple and len(saved) == 4 and saved[0] is value and type(value) is saved[1] and
        value.__dict__ is saved[2] and tuple(value.__dict__) == tuple(name for name, _item in saved[3]) and
        all(value.__dict__[name] is item for name, item in saved[3]), "ORIGINAL_VALUE_CHANGED")
    return value


def _update(value, **changes):
    """Only the source-owned transition replaces a retained identity pin."""
    _pin(value)
    require(set(changes).issubset(value.__dict__), "FIXED_STATE_SLOTS")
    for name, item in changes.items():
        object.__setattr__(value, name, item)
    _PINS[id(value)] = value, type(value), value.__dict__, tuple(value.__dict__.items())
    return value


def _methods(value, names):
    result = []
    dictionary = getattr(value, "__dict__", None)
    require(dictionary is None or type(dictionary) is dict, "SOURCE_METHOD_DICTIONARY")
    for name in names:
        method = getattr(value, name)
        require(getattr(method, "__self__", None) is value and getattr(method, "__func__", None) is
            getattr(type(value), name) and name not in (dictionary or {}), "SOURCE_OWNED_METHOD")
        result.append((name, method.__func__))
    return tuple(result)


def _methods_current(value, methods):
    dictionary = getattr(value, "__dict__", None)
    require(dictionary is None or type(dictionary) is dict, "SOURCE_METHOD_DICTIONARY")
    for name, function in methods:
        method = getattr(value, name)
        require(name not in (dictionary or {}) and getattr(type(value), name) is function and
            getattr(method, "__self__", None) is value and getattr(method, "__func__", None) is function,
            "SOURCE_METHOD_CHANGED")


@dataclass(eq=False, repr=False)
class _Entry:
    edge: str
    latch: object
    table: dict
    attempt: dict
    functions: tuple
    state: object = None


def _entry_functions():
    return (_current, _read_inputs, _read_native, _acquire, _authority_read, _capture, _close_authority,
        _write_file, _close_owner, _checked_close, _child_metadata_readback, _phase_data, _registered, checked_productive_before,
        productive_before, seal, _Fence.now, _Fence.deadline, _ReceiverNativeOwner.end, _pin, _update,
        _authority_child, _output_current, _TwoChecks.now, _TwoChecks.append, _TwoChecks._append_guard,
        _TwoChecks._begin, _TwoChecks._leave, _Fence._view, _Fence._start, _Fence._observe, _stream_ciphertext)


def _entry_check(entry):
    _pin(entry)
    require(type(entry) is _Entry and _ENTRIES.get(entry.edge) is entry and
        all(current is original for current, original in zip(
            (_ENTRIES, _STATES, _PINS, _CLOSES, _NATIVE_SEEDS, _NATIVE_OWNERS, _RETURNS, _OUTPUTS), _REGISTRIES)) and
        len(entry.functions) == len(_entry_functions()) and all(left is right for left, right in
            zip(entry.functions, _entry_functions())), "ORIGINAL_ENTRY_OR_SUPPLIER")
    entry.latch.check(entry.table, entry.attempt)


def _begin(edge):
    require(edge in ("seal", "before", "seal-child", "before-child"), "FIXED_ENTRY")
    previous = _ENTRIES.get(edge)
    if previous is not None:
        raise previous.latch.fail(O.OriginError("INITIAL_PRODUCTIVE_RECEIVER_ENTRY_REUSED"))
    table = {}
    latch = C.B.EntryLatch(table)
    entry = _track(_Entry(edge, latch, table, latch.begin(table), _entry_functions()))
    _ENTRIES[edge] = entry  # Burn before the first fallible time/credential/native callback.
    _entry_check(entry)
    return entry


def _fail(state, error):
    entry = state.entry if type(state) is _State else state
    return entry.latch.fail(error)


@dataclass(eq=False, repr=False)
class _Clock:
    handle: object
    entry: object
    first: object
    first_local: float
    boot: str
    cancelled: object
    first_graph: tuple
    work: int
    final: int
    work_local: float
    final_local: float
    last: int
    local_last: float
    busy: bool = False
    phase: str = "METADATA"
    seal_first: object = None
    seal_end: object = None


@dataclass(eq=False, repr=False)
class _State:
    entry: object
    fence: object
    clock: object
    claims: tuple
    claims_raw: bytes
    owners: tuple = ()
    inputs: tuple = ()
    input_observations: tuple = ()
    input_close: object = None
    final_raws: object = None
    final: object = None
    identity: object = None
    policy_raw: object = None
    match_raw: object = None
    event_raw: object = None
    event_path: object = None
    observed_raw: object = None
    seal_raw: object = None
    seed: object = None
    authority: object = None
    result: object = None
    graphs: tuple = ()


class _Fence:
    """A source-owned live cap; B/K never restart the original separate-seal120."""
    __slots__ = ()

    def _view(self):
        state = _STATES.get(id(self))
        require(type(state) is _State and state.fence is self and state.entry.state is state and
            type(state.clock) is _Clock and state.clock.handle is self and state.clock.entry is state.entry,
            "ORIGINAL_FENCE")
        _pin(state)
        _pin(state.clock)
        _entry_check(state.entry)
        N._check_history(state.clock.first_graph)
        return state.clock

    reading = property(lambda self: self._view().first)
    clock = property(lambda self: self._view().first.clock)
    first = property(lambda self: self._view().first.nanoseconds)
    first_local = property(lambda self: self._view().first_local)
    work = property(lambda self: self._view().work)
    final = property(lambda self: self._view().final)
    local_end = property(lambda self: self._view().final_local)
    last = property(lambda self: self._view().last)
    cancelled = property(lambda self: self._view().cancelled)

    def _start(self):
        try:
            clock = self._view()
            require(not clock.busy, "CLOCK_REENTRY")
            _update(clock, busy=True)
            return clock
        except BaseException as error:
            state = _REGISTRIES[1].get(id(self))
            raise _fail(state, error) if type(state) is _State else error

    def _observe(self, clock, final, minimum, limit):
        require(type(final) is bool, "CLOCK_FINAL_BOOL")
        end = clock.final if final else clock.work
        local_end = clock.final_local if final else clock.work_local
        if limit is not None:
            end = min(end, CD.integer(limit))
        latest = max(clock.last, CD.integer(minimum))
        for number in range(2):
            _current(_STATES[id(self)])
            local = CD.local(time.monotonic())
            require(clock.local_last <= local < local_end, "LOCAL_EXPIRED_OR_BACKWARDS")
            _update(clock, local_last=local)
            now = O.clocks.checked_now(clock.first.clock, minimum_ns=latest)
            latest = CD.integer(now, latest)
            _update(clock, last=latest)
            require(latest < end, "RAW_EXPIRED")
            require(N.continuity.boot_digest(clock.first.clock.role) == clock.boot, "ORIGINAL_BOOT_CHANGED")
            _current(_STATES[id(self)])
            if number == 0:
                clock.cancelled()
                _current(_STATES[id(self)])
                require(clock.busy and clock.local_last == local and clock.last == latest, "CLOCK_CALLBACK_CHANGED")
        local = CD.local(time.monotonic())
        require(clock.local_last <= local < local_end and clock.busy, "LOCAL_FINAL_EXPIRED")
        _update(clock, local_last=local)
        _current(_STATES[id(self)])
        return latest

    def now(self, *, final=False, minimum=0, limit=None):
        clock = self._start()
        try:
            return self._observe(clock, final, minimum, limit)
        except BaseException as error:
            raise _fail(clock.entry, error)
        finally:
            try:
                _update(clock, busy=False)
            except BaseException as error:
                raise _fail(clock.entry, error)

    def deadline(self, maximum, *, final=False, limit=None):
        clock = self._start()
        try:
            require(type(maximum) in (int, float) and math.isfinite(maximum) and 0 < maximum <= 900,
                "ORIGINAL_NATIVE_FILE_MAXIMUM")
            local = CD.local(time.monotonic())
            require(local >= clock.local_last, "LOCAL_DEADLINE_BACKWARDS")
            _update(clock, local_last=local)
            observed = self._observe(clock, final, 0, limit)
            end = clock.final if final else clock.work
            if limit is not None:
                end = min(end, CD.integer(limit))
            return min(clock.final_local if final else clock.work_local,
                O.wire._directed_deadline(local, maximum, end, observed))
        except BaseException as error:
            raise _fail(clock.entry, error)
        finally:
            try:
                _update(clock, busy=False)
            except BaseException as error:
                raise _fail(clock.entry, error)


def _claims(before):
    values = {name: os.environ.get("P2PKIT_BOOTSTRAP_" + name) for name in CD.FINAL_CLAIMS}
    values.update((name, os.environ.get(name)) for name in RD.COLLECT_CLAIMS)
    if before:
        values.update((name, os.environ.get(name)) for name in (RD.SEAL_OUTCOME_ENV, *RD.OUTPUT_ENV))
    return RD.claims(values, before=before)


def _current(state):
    """Passive original graph checks plus current policy/environment, never nested now()."""
    _entry_check(state.entry)
    _pin(state)
    _pin(state.clock)
    require(P.C is C and C.N is N and N.native is B and PC.P is P and PC.C is C and PC.N is N and PC.B is B and
        O is PC.O and ROOT == C.ROOT == N.ROOT == D.ROOT and not B.QUARANTINE and not Q.QUARANTINE and
        not C._PRIMARY_QUARANTINE and not B.diagnostics._QUARANTINE and not N.continuity.QUARANTINE and
        not _QUARANTINE, "ONE_GRAPH_OR_UNKNOWN")
    P._credential_free()
    require(_STATES.get(id(state.fence)) is state and state.entry.state is state, "STATE_ORIGINAL")
    N._check_history(state.clock.first_graph)
    for graph in state.graphs:
        N._check_history(graph)
    if not state.entry.edge.endswith("-child"):
        require(O.encoded(_claims(state.entry.edge == "before")) == state.claims_raw, "ORIGINAL_STEP_CLAIMS_CHANGED")
    if state.event_raw is not None:
        require(os.environ.get("GITHUB_EVENT_PATH") == state.event_path and os.environ.get("GITHUB_WORKSPACE") == str(ROOT),
            "CURRENT_EVENT_PATH")
        observed = CD.canonical(state.observed_raw, CD.PUBLIC_LIMIT)
        require(N.acquisition._context(dict(os.environ), state.event_raw, "worker", observed["firstUseAt"]) == observed,
            "CURRENT_HOST_CONTEXT")
    if state.policy_raw is not None:
        now = int(time.time())
        N.I._policy(state.policy_raw, now)
        match = CD.canonical(state.match_raw, CD.PUBLIC_LIMIT)
        require(match["notBefore"] <= match["firstUseAt"] <= now < match["expiresAt"], "CURRENT_MATCH_EXPIRY")
    for owner, anchor, methods in state.owners:
        require(owner._anchor() is anchor, "ORIGINAL_OWNER_ANCHOR")
        _methods_current(owner, methods)
        if type(owner) is C._PrimaryOwner:
            owner.structural()
            require(owner.failure is None and not owner.owner.unknown and owner.owner.original is None, "FILE_OWNER_FAILED")
        else:
            require(type(owner) is _ReceiverNativeOwner, "ORIGINAL_RECEIVER_OWNER")
            owner.check()
            require(owner.original is None and not owner.unknown, "NATIVE_OWNER_FAILED")
    if state.authority is not None:
        _acquired_passive(state.authority)


def _new_state(entry, cancelled, *, caps=None, declared_clock=None, boot=None, minimum=0):
    require(callable(cancelled), "CANCELLATION")
    local = CD.local(time.monotonic())
    first = O.clocks.validate_reading(O.clocks.observe())
    actual_boot = CD.sha(N.continuity.boot_digest(first.clock.role))
    require(B.processes.host_role() == first.clock.role, "NATIVE_HOST_CLOCK")
    values = {} if entry.edge.endswith("-child") else _claims(entry.edge == "before")
    if caps is not None:
        CD.authority_caps(caps)
        require(declared_clock == first.clock and actual_boot == boot and caps[3] <= CD.integer(minimum) <= first.nanoseconds < caps[4],
            "CHILD_ORIGINAL_LAUNCH")
        end = min(caps[4], CD.integer(first.nanoseconds + 45 * NS))
        maximum = 45
    elif entry.edge == "before":
        output = RD.output_values(tuple((name, values[environment]) for name, environment in zip(RD.OUTPUT_FIELDS, RD.OUTPUT_ENV)))
        clock = O.clocks.ClockIdentity(output[2][1], output[3][1], int(output[4][1]))
        require(clock == first.clock and output[5][1] == actual_boot, "BEFORE_ORIGINAL_SEAL_DOMAIN")
        end, maximum = int(output[1][1]), 120
        require(first.nanoseconds < end, "BEFORE_SAME_SEAL_EXPIRED")
    else:
        end, maximum = CD.integer(first.nanoseconds + 30 * NS), 30
    fence = _Fence()
    local_end = O.wire._directed_deadline(local, maximum, end, first.nanoseconds)
    basis = _track(_Clock(fence, entry, first, local, actual_boot, cancelled, N._history_graph(first), end, end,
        local_end, local_end, first.nanoseconds, local))
    state = _track(_State(entry, fence, basis, tuple(values.items()), O.encoded(values)))
    _STATES[id(fence)] = state
    _update(entry, state=state)
    _current(state)
    return state


def _narrow(state, end):
    clock = state.clock
    require(not clock.busy and CD.integer(end) > clock.last, "NARROW_LIVE_CAP")
    end = min(clock.work, end)
    cap = O.wire._directed_deadline(clock.first_local, 900, end, clock.first.nanoseconds)
    local = min(clock.work_local, clock.final_local, cap)
    _update(clock, work=end, final=end, work_local=local, final_local=local)
    state.fence.now()


def _enter_seal(state):
    clock = state.clock
    require(state.entry.edge == "seal" and clock.phase == "METADATA" and state.input_close is not None and
        clock.seal_first is None and clock.seal_end is None, "SEAL_ENTRY_ONCE")
    _checked_close(state.input_close)
    started = state.fence.now(minimum=state.final[-1]["returnedNs"])
    began_local = clock.local_last
    proposed = state.final[1]["originalProposal"]["phaseFencesNs"]["separate-seal"]
    end = min(CD.integer(proposed), CD.integer(started + 120 * NS))
    require(started < end, "ORIGINAL_SEAL_PHASE_EXPIRED")
    # Only the explicit closed-metadata -> separate-seal transition may advance
    # this cap. No existing owner is retimed; metadata is already known closed.
    local_end = min(O.wire._directed_deadline(clock.first_local, 150, end, clock.first.nanoseconds),
        O.wire._directed_deadline(began_local, 120, end, started))
    _update(clock, phase="SEAL", seal_first=started, seal_end=end, work=end, final=end,
        work_local=local_end, final_local=local_end)
    state.fence.now()


@dataclass(frozen=True, repr=False)
class _OwnerClose:
    owner: object
    anchor: object
    rows: tuple
    raw: bytes
    methods: tuple


def _remember_owner(state, owner, methods):
    require(not any(old is owner for old, _anchor, _methods in state.owners), "NEW_OWNER_ONLY")
    _update(state, owners=(*state.owners, (owner, owner._anchor(), methods)))


def _file_owner(state):
    end = state.fence.deadline(900, final=True)
    owner = C._PrimaryOwner(B.Owner(end, state.fence, first=state.clock.first, cancelled=state.clock.cancelled))
    _remember_owner(state, owner, _methods(owner, ("structural", "guard", "acquire", "close_one", "finish")))
    return owner


def _close_owner(owner):
    require(id(owner) not in _CLOSES, "OWNER_CLOSE_ONCE")
    if type(owner) is C._PrimaryOwner:
        methods = _methods(owner, ("structural", "guard", "acquire", "close_one", "finish"))
        anchor = owner._anchor()
        raw = owner.finish()
    else:
        require(type(owner) is _ReceiverNativeOwner, "NATIVE_CLOSE_TYPE")
        methods = _native_state(_NATIVE_OWNERS[id(owner)][1]).methods
        owner.freeze()
        owner.close()
        anchor = owner.known()
        raw = O.encoded({"schema": 1, "scope": RD.NATIVE_CLOSE_SCOPE,
            "resources": [{"ordinal": number, "label": label, "closeAttempted": attempted, "closed": closed}
                for number, (_row, label, _resource, attempted, closed) in enumerate(anchor.rows)],
            "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "exportSaveAuthority": False})
    RD.known_close(raw, native=type(owner) is _ReceiverNativeOwner)
    result = _track(_OwnerClose(owner, anchor, anchor.rows, raw, methods))
    _CLOSES[id(owner)] = result
    return _checked_close(result)


def _checked_close(result):
    """PASSIVE actual normal close; no clock, root verify or reopened resource."""
    _pin(result)
    require(type(result) is _OwnerClose and _CLOSES.get(id(result.owner)) is result and
        result.owner._anchor() is result.anchor and result.anchor.rows is result.rows, "ORIGINAL_CLOSE_RETURN")
    owner = result.owner
    _methods_current(owner, result.methods)
    if type(owner) is C._PrimaryOwner:
        owner.structural()
        require(owner.finished and owner.owner.closed and not owner.owner.unknown and owner.failure is None and
            owner.owner.original is None and owner.errors == [], "FILE_NORMAL_CLOSE")
    else:
        require(type(owner) is _ReceiverNativeOwner and owner.known() is result.anchor, "NATIVE_NORMAL_CLOSE")
    require(all(row["owner"] is resource and row["attempted"] is row["closed"] is attempted is closed is True
        for row, _label, resource, attempted, closed in result.rows), "ORIGINAL_NORMAL_CLOSE_ROWS")
    return result


def _abort(state, error):
    error = _fail(state, error)
    for owner, _anchor, _methods in reversed(state.owners):
        if type(owner) is C._PrimaryOwner:
            owner.remember(error)
            if not owner.finished and not owner.owner.unknown:
                try:
                    owner.finish()
                except BaseException:
                    pass
            unknown = owner.owner.unknown
        else:
            owner.error("productive-receiver-abort", error)
            try:
                owner.close()
            except BaseException:
                pass
            unknown = owner._anchor().unknown
        if unknown and not any(original is owner for original in _QUARANTINE):
            _QUARANTINE.append(owner)
    return error


@dataclass(frozen=True, repr=False)
class _NativeSeed:
    pass


@dataclass(eq=False, repr=False)
class _NativeState:
    seed: object
    state: object
    edge: str
    fence: object
    end: float
    owner: object = None
    methods: tuple = ()
    private: object = None
    context_raw: object = None
    before: object = None
    phase: tuple = ()


def _native_state(seed):
    _pin(seed)
    value = _NATIVE_SEEDS.get(id(seed))
    require(type(seed) is _NativeSeed and type(value) is _NativeState and value.seed is seed and
        value.state.entry.state is value.state and value.state.fence is value.fence, "ORIGINAL_NATIVE_SEED")
    _pin(value)
    _entry_check(value.state.entry)
    return value


def _native_seed(state, edge):
    _current(state)
    require(edge in ("seal", "before", "seal-child", "before-child") and state.seed is None, "NATIVE_SEED_ONCE")
    end = state.fence.deadline(900, final=True)
    seed = _track(_NativeSeed())
    _NATIVE_SEEDS[id(seed)] = _track(_NativeState(seed, state, edge, state.fence, end))
    _update(state, seed=seed)
    return seed


class _ReceiverNativeOwner(C._CustodyOwner):
    """Distinct registered receiver, sharing actual C native ownership mechanics."""
    def __init__(self, seed):
        value = _native_state(seed)
        require(type(self) is _ReceiverNativeOwner and id(self) not in _NATIVE_OWNERS and value.owner is None,
            "NATIVE_OWNER_ONCE")
        state = value.state
        B.Owner.__init__(self, value.end, value.fence, first=state.clock.first, cancelled=state.clock.cancelled)
        self.initial_sources = {}
        binding = (self.first, self.fence, self.cancelled, self.local_end, self.resources, self.errors,
            self.initial_sources, self.admissions, self.early_last, self.entry_original, self.entry_close_attempted,
            self.entry_close_original, self.entry_close_snapshot)
        anchor = C._CustodyOwnerAnchor(self, self.__dict__, binding, N._history_graph(self.first),
            error_graph=N._history_graph(self.errors))
        _NATIVE_OWNERS[id(self)] = self, seed, anchor
        _update(value, owner=self, methods=_methods(self, ("end", "acquire", "read", "write", "open", "child", "close_one", "close", "check",
            "freeze", "known", "enter_receiver_phase", "leave_receiver_phase")))
        _remember_owner(state, self, value.methods)
        self.check()

    def _anchor(self):
        original = _NATIVE_OWNERS.get(id(self))
        require(type(self) is _ReceiverNativeOwner and type(original) is tuple and original[0] is self and
            type(original[2]) is C._CustodyOwnerAnchor and original[2].owner is self, "NATIVE_OWNER_ORIGINAL")
        return original[2]

    def end(self, *, final=False):
        try:
            saved = _NATIVE_OWNERS.get(id(self))
            require(type(saved) is tuple and saved[0] is self, "NATIVE_BOUNDARY_ORIGINAL")
            value = _native_state(saved[1])
            require(value.owner is self, "NATIVE_OWNER_CHANGED")
            _methods_current(self, value.methods)
            _current(value.state)
            result = C._CustodyOwner.end(self, final=final)
            _current(value.state)
            return result
        except BaseException as error:
            self.error("productive-receiver-native-boundary", error)
            raise self._anchor().failure

    def enter_receiver_phase(self, seed, context_raw, started, work, final):
        value = _native_state(seed)
        require(value.owner is self and value.context_raw is context_raw and not value.phase and
            value.edge in ("seal", "before") and started == value.fence.last, "NATIVE_PHASE_ORIGINAL_ENTRY")
        context = RD.authority_context(context_raw, edge=value.edge)
        CD.authority_caps((*(context["authorityWindow"][name] for name in RD.AUTHORITY_CAP_FIELDS[:3]),
            started, work, final), context["authorityWindow"])
        require(context["sourceReturnedNs"] <= started and work == min(value.fence.work, started + 45 * NS) and
            final == min(value.fence.final, work + 45 * NS), "NATIVE_PHASE_CAP")
        anchor = self.check()
        require(anchor.phase is None and not anchor.closed and not anchor.unknown and anchor.failure is None and
            not anchor.busy and anchor.frozen is None and self.work_limit is self.final_limit is None, "NATIVE_PHASE_ONCE")
        _update(value, phase=(started, work, final))
        anchor.phase = (started, work, final, (None, None))
        anchor.phase_active = True
        self.work_limit, self.final_limit = work, final
        self.check()

    def leave_receiver_phase(self, started, work, final, old_limits):
        anchor = self.check()
        require(type(old_limits) is tuple and old_limits == (None, None) and anchor.phase_active and
            anchor.phase == (started, work, final, old_limits), "NATIVE_PHASE_RETURN")
        self.work_limit = self.final_limit = None
        anchor.phase_active = False
        self.check()


def _checked_authority_phase(seed, owner, private, context_raw, fence, before, *, edge):
    value = _native_state(seed)
    require(edge in ("seal", "before") and value.edge == edge and value.owner is owner and
        type(owner) is _ReceiverNativeOwner and value.private is private and value.context_raw is context_raw and
        value.fence is fence and value.before is before and owner.initial_sources.get(str(private.path / "source-before")) is before,
        "SERVICE_ORIGINAL_BINDING")
    _current(value.state)
    C._collect_source_current(C._collect_source_pin(before))
    RD.authority_context(context_raw, edge=edge)
    return seed


def _checked_authority_phase_seed(seed, owner, private, context_raw, fence, before):
    value = _native_state(seed)
    _checked_authority_phase(seed, owner, private, context_raw, fence, before, edge=value.edge)
    return value.edge


def _checked_native_authority_bridge(seed, owner, private, context_raw, fence, *, edge):
    value = _native_state(seed)
    return _checked_authority_phase(seed, owner, private, context_raw, fence, value.before, edge=edge)


def _command(edge, context_raw, caps, clock, boot, minimum=None, *, interpreter=None):
    require(edge in ("seal", "before"), "FIXED_CHILD_COMMAND")
    CD.authority_caps(caps)
    O.clocks.validate_identity(clock)
    CD.sha(boot)
    if interpreter is None:
        interpreter = B.initial_command(O.digest(context_raw))[0]
    require(type(interpreter) is str and Path(interpreter).is_absolute() and ".." not in Path(interpreter).parts,
        "CHILD_INTERPRETER")
    argv = [interpreter, "-I", "-B", "-S", str(SCRIPTS / "run-hosted-initial-recipient-productive-receiver.py"),
        "_" + edge + "-authority", "--context-sha256", O.digest(context_raw)]
    if minimum is not None:
        require(caps[3] <= CD.integer(minimum) < caps[4], "CHILD_LAUNCH_MINIMUM")
        argv.extend(("--minimum-ns", str(minimum)))
    for flag, cap in zip(RD.AUTHORITY_CAP_FLAGS, caps):
        argv.extend((flag, str(cap)))
    return argv + ["--original-boot-digest", boot, "--clock-role", clock.role, "--clock-domain", clock.domain,
        "--clock-ticks-per-second", str(clock.ticks_per_second)]


def _native_argv(seed, context_raw, phase, minimum=None):
    value = _native_state(seed)
    require(value.context_raw is context_raw and type(phase) is tuple and phase == value.phase and len(phase) == 3,
        "NATIVE_COMMAND_ORIGINAL_PHASE")
    context = RD.authority_context(context_raw, edge=value.edge)
    caps = (*(context["authorityWindow"][name] for name in RD.AUTHORITY_CAP_FIELDS[:3]), *phase)
    return _command(value.edge, context_raw, caps, value.state.clock.first.clock, value.state.clock.boot, minimum)


def _froot():
    return C._paths("worker")[2] / "productive-final"


def _receiver_root():
    return _froot().with_name("productive-receiver")


def _authority_path(edge):
    require(edge in ("seal", "before"), "FIXED_AUTHORITY_PATH")
    return _receiver_root() / edge / "authority"


def _directory_stamp(directory):
    info = directory.verify()
    if os.name == "nt":
        result = _windows_stamp(info)
    else:
        result = CD.native(("posix", *B.posix._stamp(os.stat(directory.path, follow_symlinks=False))), directory=True)
    require(result[1:3] == tuple(directory.identity), "ACTUAL_DIRECTORY_BINDING")
    return result


def _windows_stamp(info):
    require(type(info) is B.windows.FileInfo, "ACTUAL_WINDOWS_INFO")
    return CD.native(("windows", *info.identity, info.is_directory, info.size, info.links, info.attributes,
        info.creation_100ns, info.modified_100ns, info.change_100ns, info.owner_sid, info.protected_dacl),
        directory=info.is_directory)


def _metadata(stamp):
    """Project actual full native DATA into the maintained writer-close grammar."""
    return RD.file_metadata(stamp)


def _names(owner, directory, maximum):
    require(type(maximum) is int and 1 <= maximum <= 64, "DIRECTORY_BOUNDED_NAMES")
    end = owner.guard()
    directory.verify()
    if os.name == "nt":
        names = directory.names(max_names=maximum, deadline=end)
    else:
        reader = owner.acquire("reader", lambda: os.scandir(directory.path))
        names = []
        try:
            for item in reader:
                owner.guard()
                require(len(names) < maximum, "DIRECTORY_ROSTER_BOUND")
                names.append(item.name)
        finally:
            if not owner.owner.unknown:
                owner.close_one(reader)
    require(all(type(name) is str and name not in ("", ".", "..") for name in names) and
        len(names) == len(set(name.casefold() for name in names)), "DIRECTORY_MEMBER_ALIAS")
    directory.verify()
    owner.guard()
    return tuple(sorted(names))


def _members(owner, directory, expected):
    require(type(expected) is tuple and tuple(sorted(expected)) == expected and len(expected) <= 64,
        "FIXED_DIRECTORY_EXPECTATION")
    require(_names(owner, directory, max(1, len(expected))) == expected, "EXACT_DIRECTORY_MEMBERSHIP")


def _stream_ciphertext(owner, reader, count, checksum, verify):
    """Only ciphertext has the separate576MiB bound; no plaintext Snapshot."""
    CD.integer(count, 1, B.posix.MAX_CIPHERTEXT_BYTES)
    CD.sha(checksum)
    hashed, total = hashlib.sha256(), 0
    try:
        while total < count:
            owner.guard()
            maximum = min(C.COPY_CHUNK, count - total)
            piece = reader.read(maximum)
            require(type(piece) is bytes and 0 < len(piece) <= maximum, "CIPHERTEXT_SHORT_READ")
            total += len(piece)
            hashed.update(piece)
            owner.guard()
        owner.guard()
        tail = reader.read(1)
        require(type(tail) is bytes and tail == b"" and total == count and hashed.hexdigest() == checksum,
            "CIPHERTEXT_COMPLETE_HASH_EOF")
        verify()
        owner.guard()
        return hashed.hexdigest()
    except BaseException as error:
        raise owner.remember(error)
    finally:
        if not owner.owner.unknown:
            try:
                owner.close_one(reader)
            except BaseException as error:
                owner.remember(error, unknown=True)
        if owner.failure is not None:
            raise owner.failure


def _read_native(owner, directory, name, maximum, relative, *, expected=None, native=None, retain=True):
    """Actual full-file/EOF/native reads. Never synthesize mode/uid/link metadata."""
    CD.relative(name)
    require("/" not in name and type(retain) is bool and type(maximum) is int and
        0 < maximum <= (CD.LIMIT if retain else B.posix.MAX_CIPHERTEXT_BYTES), "ORIGINAL_FILE_LIMIT")
    path, end = directory.path / name, owner.guard()
    directory_stamp = _directory_stamp(directory)
    if os.name == "nt":
        reader = owner.acquire("reader", lambda: directory.open_file(name, max_bytes=maximum, deadline=end))
        original = reader.initial_info
        stamp = _windows_stamp(original)
        def verify():
            require(reader.verify() == original, "WINDOWS_FULL_READER_METADATA")
            directory.verify()
    else:
        reader = owner.acquire("reader", lambda: Q._posix_stream(path, os.O_RDONLY | os.O_NOFOLLOW, "rb"))
        require(type(reader) is io.BufferedReader, "ACTUAL_POSIX_READER")
        Q._file_info(path, reader, maximum)
        stamp = CD.native(("posix", *B.posix._stamp(os.fstat(reader.fileno()))), directory=False)
        def verify():
            Q._file_info(path, reader, maximum)
            require(("posix", *B.posix._stamp(os.fstat(reader.fileno()))) == stamp and
                ("posix", *B.posix._stamp(os.stat(path, follow_symlinks=False))) == stamp, "POSIX_FULL_READER_METADATA")
            directory.verify()
    ordinal = len(owner.rows) - 1
    count = stamp[6 if stamp[0] == "posix" else 4]
    require(0 <= count <= maximum and (native is None or stamp == native), "ORIGINAL_NATIVE_SIZE")
    if expected is not None:
        require(type(expected) is tuple and len(expected) == 2 and type(expected[0]) is int and expected[0] == count,
            "ORIGINAL_DECLARED_LENGTH")
        CD.sha(expected[1])
    verify()
    require(retain or expected is not None, "CIPHERTEXT_ORIGINAL_HASH_REQUIRED")
    value = (C._consume(owner, reader, count, None if expected is None else expected[1], verify, retain=True) if retain else
        _stream_ciphertext(owner, reader, count, expected[1], verify))
    require(owner.rows[ordinal][2] is reader and owner.rows[ordinal][3:] == (True, True), "ACTUAL_READER_CLOSE")
    checksum = O.digest(value) if retain else value
    observation = {"relative": relative, "maximum": maximum, "bytes": count, "sha256": checksum,
        "native": list(stamp), "directoryNative": list(directory_stamp), "provenance": RD.PROVENANCE,
        "readerOrdinal": ordinal, "retirement": "KNOWN_READER_CLOSE"}
    if retain:
        row = RD.file_row((relative, value, maximum, stamp, directory_stamp, RD.PROVENANCE))
        RD.file_observation(observation)
        return row, observation
    return checksum, stamp, directory_stamp


def _final_roster(owner, handles, context):
    names = {
        "root": ("authority-post-export", "authority-pre-export", "export-output", "payload", "public-crypto", "returned"),
        "returned": tuple(sorted(("control-home", "temporary", "crypto-service", "context.json", "crypto-child-result.json",
            *(name for name, _maximum in CD.CRYPTO_INPUTS), *CD.LATER_FILES))),
        "crypto-service": tuple(sorted(C.B.PHASE_FILES)),
        "export-output": ("evidence.tar.gz.gpg", "manifest.json"),
        "control-home": (), "temporary": (),
        "payload": tuple(sorted((*CD.GROUPS, *("map-" + name + ".json" for name in CD.GROUPS), "copy-index.json"))),
    }
    for key, expected in names.items():
        directory = handles[key]
        if key in context["directories"]:
            require(tuple(directory.identity) == tuple(context["directories"][key]), "FINAL_ORIGINAL_DIRECTORY_PIN")
        _members(owner, directory, expected)


def _open_authority_readback(owner, path, index, *, closed):
    required = tuple(index["requiredFiles"])
    directories = tuple(row["relative"] for row in index["directories"])
    expected = dict(C.B.directory_members(required, directories, closed=closed))
    pins = {row["relative"]: tuple(row["readbackNative"])[1:3] for row in index["directories"]}
    handles = {}
    for relative in sorted(directories, key=lambda item: (item.count("/"), item != ".", item)):
        target = path if relative == "." else path.joinpath(*relative.split("/"))
        directory = C._private(owner, target)
        require(tuple(directory.identity) == pins[relative], "ORIGINAL_AUTHORITY_READBACK_DIRECTORY")
        _members(owner, directory, expected[relative])
        handles[relative] = directory
    return handles, expected


def _bind_originals(state, raws):
    values = dict(state.claims)
    bundle = RD.bind_claims(raws, values, before=state.entry.edge == "before")
    context, final, manifest, _index, custody, _transfer, _post, _collected = bundle
    aux = {name: raws["returned/" + name] for name, _maximum in CD.CRYPTO_INPUTS}
    # This is explicitly ACTIVE current-policy validation, not a call from RD.
    checked_final, _prior, identity, _policy = PC._crypto_inputs_data(raws["returned/context.json"], aux,
        state.clock.first.clock, state.clock.boot)
    require(checked_final == final, "CURRENT_FINAL_POLICY_JOIN")
    phase = tuple(custody["nativePhase"])
    records = tuple((name, raws["returned/crypto-service/" + name]) for name in C.B.PHASE_FILES)
    _start, native_return, _child, _ack, manifest_raw = PC._crypto_phase_data(raws["returned/context.json"], records,
        raws["returned/crypto-child-result.json"], phase, state.clock.first, state.clock.boot)
    require(manifest_raw == raws["export-output/manifest.json"] and native_return["finalizedNs"] <= custody["returnedNs"] and
        manifest["source"] == context["observed"]["source"], "ORIGINAL_CRYPTO_PHASE_JOIN")
    observed, _path, event = N.host_context(context["observed"]["firstUseAt"])
    require(observed == context["observed"] and event == aux["event.json"] and
        observed["role"] == state.clock.first.clock.role, "ACTUAL_WORKER_SOURCE")
    _update(state, final_raws=tuple(raws.items()), final=bundle, identity=identity,
        policy_raw=aux["candidate-policy.json"], match_raw=aux["original-match.json"], event_raw=event,
        event_path=os.environ.get("GITHUB_EVENT_PATH"), observed_raw=O.encoded(observed),
        graphs=(*state.graphs, N._history_graph(bundle, identity)))
    _current(state)
    return bundle


def _read_inputs(state):
    owner = _file_owner(state)
    before = state.entry.edge == "before"
    seal_row = seal_observation = seal_value = None
    # BEFORE's first read already has the supplied original seal end, clock and
    # boot cap. It then binds the real preceding successful Step's actual file.
    if before:
        directory = C._private(owner, _receiver_root() / "seal")
        _members(owner, directory, ("authority", "seal-pending.json"))
        seal_row, seal_observation = _read_native(owner, directory, "seal-pending.json", CD.LIMIT, "seal/seal-pending.json")
        require(O.digest(seal_row[1]) == dict(state.claims)[RD.OUTPUT_ENV[0]], "FIRST_SEAL_ORIGINAL_HASH")
        seal_value = CD.canonical(seal_row[1])
        require(seal_value.get("scope") == RD.SEAL_SCOPE and seal_value.get("clock") == O.clock_value(state.clock.first.clock) and
            seal_value.get("originalBootDigest") == state.clock.boot and
            seal_value.get("sealEndNs") == int(dict(state.claims)[RD.OUTPUT_ENV[1]]), "FIRST_SEAL_ORIGINAL_CAP")
        _narrow(state, CD.integer(seal_value["sealEndNs"]))
    root = _froot()
    handles = {"root": C._private(owner, root), "returned": C._private(owner, root / "returned")}
    row, observation = _read_native(owner, handles["returned"], "context.json", CD.PUBLIC_LIMIT, RD.FINAL_INPUTS[0][0])
    context = CD.crypto_context(row[1])
    if not before:
        ends = RD._proposal(context["originalProposal"], context["history"])
        _narrow(state, ends["seal-transition"])
    rows, observations = [row], [observation]
    for name in ("payload", "export-output"):
        handles[name] = C._private(owner, root / name)
    for name in ("crypto-service", "control-home", "temporary"):
        handles[name] = C._private(owner, root / "returned" / name)
    _final_roster(owner, handles, context)
    for relative, maximum in RD.FINAL_INPUTS[1:]:
        parent, _slash, leaf = relative.rpartition("/")
        key = "crypto-service" if parent == "returned/crypto-service" else parent
        row, observation = _read_native(owner, handles[key], leaf, maximum, relative)
        rows.append(row)
        observations.append(observation)
    raws = {row[0]: row[1] for row in rows}
    _bind_originals(state, raws)
    _final_roster(owner, handles, context)
    if before:
        values = tuple((key, dict(state.claims)[environment]) for key, environment in zip(RD.OUTPUT_FIELDS, RD.OUTPUT_ENV))
        seal_value = RD.seal_record(seal_row[1], raws, values)
        require(seal_value["closedNs"] <= state.clock.first.nanoseconds, "PRECEDING_SEAL_BEFORE_ENTRY")
        _update(state.clock, seal_first=seal_value["sealFirstNs"], seal_end=seal_value["sealEndNs"], phase="BEFORE")
        _update(state, seal_raw=seal_row[1])
        rows.append(seal_row)
        observations.append(seal_observation)
        authority_index = RD.authority_index(O.encoded(seal_value["authorityIndex"]), edge="seal")
        path = _authority_path("seal")
        require(authority_index["root"] == str(path), "FIXED_SEAL_AUTHORITY_ROOT")
        directories, expected = _open_authority_readback(owner, path, authority_index, closed=True)
        originals = []
        for prior in authority_index["files"]:
            parent, _slash, leaf = prior["relative"].rpartition("/")
            row, observation = _read_native(owner, directories[parent or "."], leaf, prior["maximum"],
                "seal/authority/" + prior["relative"], expected=(prior["bytes"], prior["sha256"]), native=tuple(prior["native"]))
            originals.append((prior["relative"], row[1]))
            rows.append(row)
            observations.append(observation)
        require(dict(originals)["authority-close.json"] == O.encoded(seal_value["authority"]), "ACTUAL_SEAL_CLOSE_ORIGINAL")
        prior_rows = tuple((row[0].removeprefix("seal/authority/"), *row[1:]) for row in rows[25:])
        # Canonical bytes from the actual prior seal, not reconstructed close
        # handles. The new receiver retains its own distinct input owner below.
        prior_closes = tuple((name, O.encoded(seal_value["authorityCloseOriginals"][name])) for name in
            ("input", "readback", "native", "writer"))
        RD.authority_bundle(dict(originals)["authority-close.json"], O.encoded(authority_index), prior_rows,
            prior_closes, edge="seal", input_rows=tuple(rows[:24]))
        _historical_authority(state, "seal", dict(originals), authority_index)
        for relative, directory in directories.items():
            _members(owner, directory, expected[relative])
    require(len(rows) == (305 if before else 24) and sum(len(row[1]) for row in rows) <= CD.MAX_BYTES and
        len({row[0] for row in rows}) == len({CD.native_key(row[3]) for row in rows}) == len(rows), "COMPLETE_INPUTS_NO_ALIAS")
    close = _close_owner(owner)
    _update(state, inputs=tuple(rows), input_observations=tuple(observations), input_close=close,
        graphs=(*state.graphs, N._history_graph(tuple(observations))))
    _checked_close(close)
    state.fence.now()
    return state


def _write_file(state, directory, name, raw, *, complete_index=None):
    """New writer, complete readback and actual closes. Its bytes remain pending."""
    require(name in ("seal-pending.json", "authority-close.json") and type(raw) is bytes and 0 < len(raw) <= CD.LIMIT,
        "FIXED_RECEIVER_WRITER")
    owner = _file_owner(state)
    path = directory
    private = C._private(owner, path)
    if complete_index is not None:
        handles, before_members = _open_authority_readback(owner, path, complete_index, closed=False)
        private = handles["."]
    else:
        handles = {".": private}
        before_members = {".": ("authority",)}
        _members(owner, private, before_members["."])
    reader = owner.acquire("embedded-reader", lambda: io.BytesIO(raw))
    end = owner.guard()
    writer = owner.acquire("writer", lambda: private.create_file(name, max_bytes=len(raw), deadline=end))
    writer_ordinal = len(owner.rows) - 1
    def verify():
        require(type(reader) is io.BytesIO and reader.getvalue() == raw, "ORIGINAL_WRITE_BYTES")
    checksum, written_metadata = C._consume(owner, reader, len(raw), O.digest(raw), verify, writer=writer)
    require(checksum == O.digest(raw) and owner.rows[writer_ordinal][2] is writer and
        owner.rows[writer_ordinal][3:] == (True, True), "ACTUAL_WRITE_CLOSE")
    row, observation = _read_native(owner, private, name, CD.LIMIT, name, expected=(len(raw), checksum))
    require(row[1] == raw, "WRITER_COMPLETE_READBACK")
    prewrite = {"bytes": len(raw), "sha256": checksum, "metadata": CD.canonical(written_metadata),
        "writerOrdinal": writer_ordinal, "observation": "PRE_CLOSE_WRITE_VERIFY", "retirement": "KNOWN_WRITER_CLOSE"}
    metadata_policy = C.B.write_close_metadata(state.clock.first.clock.role, prewrite["metadata"], _metadata(row[3]), len(raw))
    for relative, handle in handles.items():
        expected = tuple(sorted((*before_members[relative], name))) if relative == "." else before_members[relative]
        _members(owner, handle, expected)
    close = _close_owner(owner)
    closed = state.fence.now()
    returned = O.encoded({"schema": 1, "scope": RD.WRITER_SCOPE, "relative": name, "bytes": len(raw), "sha256": checksum,
        "preCloseWrite": prewrite, "readback": observation, "metadataPolicy": metadata_policy,
        "ownerClose": RD.known_close(close.raw), "closedNs": closed, "originalStepOutcome": "NOT_OBSERVED",
        "capture": "NOT_K_CAPTURE", "exportSaveAuthority": False})
    if name == "authority-close.json":
        RD.writer_return(CD.canonical(returned))
    return row, observation, close, returned


def _start_data(context_raw, start_raw, clock, boot, edge):
    context = RD.authority_context(context_raw, edge=edge)
    path = _authority_path(edge)
    window = context["authorityWindow"]
    require(context["root"] == str(ROOT) and context["session"] == str(path) and
        window["clock"] == O.clock_value(clock) and window["originalBootDigest"] == boot, "ACTUAL_AUTHORITY_PATH_CLOCK")
    start = CD.fields(CD.canonical(start_raw), B.START_FIELDS)
    caps = (*(window[name] for name in RD.AUTHORITY_CAP_FIELDS[:3]),
        *(start[name] for name in ("startedNs", "workEndNs", "finalEndNs")))
    CD.authority_caps(caps, window)
    require(type(start["argv"]) is list and start["argv"] and type(start["schema"]) is int and start["schema"] == 1 and
        start["scope"] == B.PHASE_SCOPE and start["contextSha256"] == O.digest(context_raw) and
        start["argv"] == _command(edge, context_raw, caps, clock, boot, interpreter=start["argv"][0]) and
        start["cwd"] == str(ROOT) and start["role"] == clock.role and start["job"] == context["job"] and
        start["state"] == str(path) and start["home"] == str(path / "control-home") and
        start["exitCode"] is None and start["launchAttempted"] is start["scopeAttempted"] is False and
        start["retirement"] == "UNKNOWN" and context["sourceReturnedNs"] <= caps[3], "ORIGINAL_AUTHORITY_START")
    CD.job(start["invocation"])
    inherited = B.processes.ownership_environment(context["inheritedContext"], context["job"], start["invocation"],
        str(path), str(path / "control-home"), allow_new_context=True)
    require(start["inheritedContext"] == {name: inherited[name] for name in Q._CONTEXT}, "ORIGINAL_AUTHORITY_ANCESTORS")
    return context, start, caps


def _child_metadata_readback(first, readback, raw, relative, identity):
    """Only the known parent's service entry may change directory timestamps.

    Keep BOTH complete observations. Actual private-directory verification and
    full file bytes/native/EOF/close remain the caller's original native reads;
    this passive join is neither an owner nor a general snapshot relaxation.
    """
    require(type(raw) is bytes and type(relative) is str and relative in ("context.json", "service/start.json") and
        type(identity) is tuple and len(identity) == 2, "CHILD_METADATA_FIXED_ROUTE")
    ordinals = (2, 4) if relative == "context.json" else (3, 5)
    checksum, directories = O.digest(raw), []
    for observed, ordinal in zip((first, readback), ordinals):
        RD.file_observation(observed)
        require(observed["relative"] == relative and observed["maximum"] == CD.LIMIT and
            observed["readerOrdinal"] == ordinal and observed["bytes"] == len(raw) and observed["sha256"] == checksum,
            "CHILD_METADATA_CUSTODY")
        directory = tuple(observed["directoryNative"])
        require(all(type(original) is type(actual) and original == actual for original, actual in
            zip(identity, directory[1:3])), "CHILD_METADATA_ORIGINAL_DIRECTORY")
        if directory[0] == "posix":
            require(not directory[3] & 0o077, "CHILD_METADATA_PRIVATE_DIRECTORY")
        else:
            require(directory[6] & 0x10 and type(directory[10]) is str and
                re.fullmatch(r"S-1-(?:[0-9]+-){1,14}[0-9]+", directory[10]) is not None and
                directory[11] is True, "CHILD_METADATA_PRIVATE_DIRECTORY")
        directories.append(directory)
    require({key: item for key, item in first.items() if key not in ("readerOrdinal", "directoryNative")} ==
        {key: item for key, item in readback.items() if key not in ("readerOrdinal", "directoryNative")},
        "CHILD_METADATA_NATIVE_READBACK")
    initial, later = directories
    if relative == "context.json":
        require(initial == later, "CHILD_METADATA_CONTEXT_DIRECTORY_READBACK")
    elif initial[0] == "posix":
        # Native-start is a regular entry: only size/mtime/ctime may differ.
        require(initial[:6] == later[:6], "CHILD_METADATA_SERVICE_DIRECTORY_READBACK")
    else:
        # Preserve size/links/attributes/creation/owner/DACL, not modified/change.
        require(initial[:8] == later[:8] and initial[10:] == later[10:], "CHILD_METADATA_SERVICE_DIRECTORY_READBACK")


def _phase_data(context_raw, records, child_raw, clock, boot, private_pin, service_pin, *, edge):
    """Declared native-chain DATA. Actual parent owner/return pins are separate."""
    require(type(records) is dict and set(records) == B.PHASE_FILES and all(type(raw) is bytes for raw in records.values()),
        "NATIVE_RECORD_ROSTER")
    context, start, caps = _start_data(context_raw, records["start.json"], clock, boot, edge)
    row = CD.fields(CD.canonical(records["result.json"]), B.TERMINAL_FIELDS)
    birth = CD.fields(CD.canonical(records["native-start.json"]), "ownership leader preparerIdentity observedNs")
    changed = {"exitCode", "launchAttempted", "scopeAttempted", "retirement"}
    require({name: value for name, value in start.items() if name not in changed} ==
        {name: row[name] for name in start if name not in changed} and type(row["exitCode"]) is int and row["exitCode"] == 0 and
        row["launchAttempted"] is row["scopeAttempted"] is row["scopeCloseAttempted"] is row["scopeClosed"] is True and
        row["retirement"] == "KNOWN" and row["errors"] == row["survivors"] == [] and records["stderr.log"] == b"" and
        row["nativeStartSha256"] == O.digest(records["native-start.json"]) and
        row["baselineSha256"] == O.digest(records["baseline.json"]) and row["leader"] == birth["leader"], "ACTUAL_NATIVE_RETURN")
    minimum = CD.integer(row["launchMinimumNs"], caps[3])
    argv = _command(edge, context_raw, caps, clock, boot, minimum, interpreter=start["argv"][0])
    require(row["launchArgv"] == argv, "ACTUAL_EXECUTED_ARGV")
    B.native_record(row["ownership"], start, row["leader"], argv)
    B.native_record(birth["ownership"], start, row["leader"], argv, terminal=False)
    require(birth["ownership"]["launches"] == row["ownership"]["launches"], "ACTUAL_NATIVE_BIRTH")
    preparer = B.closed_lifetime(row["preparerIdentity"], clock.role)
    require(preparer == B.closed_lifetime(birth["preparerIdentity"], clock.role) and preparer["pid"] != row["leader"]["pid"],
        "ORIGINAL_NATIVE_PREPARER")
    baseline = B.baseline_record(records["baseline.json"], clock.role)
    if baseline["baseline"] is not None:
        leader = B.lifetime(row["leader"], clock.role)
        require(list(leader[:4] if clock.role.startswith("macos-") else leader) not in baseline["baseline"], "NATIVE_PREEXISTING_LEADER")
    require(row["captureOutcomes"] == {name: {key: True for key in ("synced", "verified", "closeAttempted", "closed", "readback")}
        for name in ("stdout", "stderr")} and row["captures"] == {name: {"sha256": O.digest(records[name + ".log"]),
            "bytes": len(records[name + ".log"])} for name in ("stdout", "stderr")}, "ORIGINAL_CAPTURE_CLOSES")
    child = CD.fields(CD.canonical(child_raw), "schema scope contextSha256 startSha256 invocation clock bootDigest launchMinimumNs "
        "authorityWindowSha256 beganNs metadataLastNs acquiredNs queryReturnedNs querySessionSha256 originalsSha256 matchSha256 "
        "directoryIdentities serviceSteps metadataReads metadataClose completedNs retirement errors")
    ack = CD.fields(CD.canonical(records["stdout.log"], B.ACK_LIMIT), "schema scope invocation terminalSha256 clock closedNs")
    child_scope = RD.SEAL_CHILD_SCOPE if edge == "seal" else RD.BEFORE_CHILD_SCOPE
    ack_scope = RD.SEAL_ACK_SCOPE if edge == "seal" else RD.BEFORE_ACK_SCOPE
    require(type(child["schema"]) is type(ack["schema"]) is int and child["schema"] == ack["schema"] == 1 and
        child["scope"] == child_scope and ack["scope"] == ack_scope and child["contextSha256"] == O.digest(context_raw) and
        child["startSha256"] == O.digest(records["start.json"]) and child["invocation"] == ack["invocation"] == start["invocation"] and
        child["clock"] == ack["clock"] == O.clock_value(clock) and child["bootDigest"] == boot and
        child["authorityWindowSha256"] == O.digest(O.encoded(context["authorityWindow"])) and
        child["launchMinimumNs"] == minimum and child["retirement"] == "PENDING_CHILD_CLOSE" and child["errors"] == [] and
        ack["terminalSha256"] == O.digest(child_raw) and child["directoryIdentities"] ==
        {".": list(private_pin), "service": list(service_pin)}, "ORIGINAL_CHILD_ACK")
    close = RD.known_close(O.encoded(child["metadataClose"]))
    require(close["resources"] == [{"ordinal": number, "label": label, "closeAttempted": True, "closed": True}
        for number, label in enumerate(("directory", "directory", "reader", "reader", "reader", "reader"))],
        "CHILD_COMPLETE_METADATA_CLOSE")
    require(type(child["metadataReads"]) is list and len(child["metadataReads"]) == 2, "CHILD_METADATA_READS")
    for data, name, raw, relative, identity in zip(child["metadataReads"], ("context.json", "start.json"),
            (context_raw, records["start.json"]), ("context.json", "service/start.json"), (private_pin, service_pin)):
        CD.fields(data, "name first readback")
        require(data["name"] == name, "CHILD_ORIGINAL_METADATA_NAME")
        _child_metadata_readback(data["first"], data["readback"], raw, relative, identity)
    CD.fields(child["originalsSha256"], N.ORIGINAL_KEYS)
    for checksum in (*child["originalsSha256"].values(), child["querySessionSha256"], child["matchSha256"]):
        CD.sha(checksum)
    ordered = (minimum, *(child[name] for name in ("beganNs", "metadataLastNs", "acquiredNs", "queryReturnedNs", "completedNs")),
        ack["closedNs"], row["completedNs"], row["finalizedNs"])
    require(all(CD.integer(number) == number for number in ordered) and ordered == tuple(sorted(ordered)) and
        child["metadataLastNs"] < min(caps[4], child["beganNs"] + 45 * NS) and
        ack["closedNs"] < min(caps[4], child["beganNs"] + 45 * NS) and row["completedNs"] < caps[4] and
        row["finalizedNs"] < caps[5] and minimum <= CD.integer(birth["observedNs"]) <= row["completedNs"],
        "ORIGINAL_NATIVE_CHRONOLOGY")
    return context, start, row, birth, child, ack


def _service_steps(context_raw, originals, invocation, clock, edge):
    context, raw = RD.authority_context(context_raw, edge=edge), dict(originals)
    github = context["observed"]["github"]
    path = N.acquisition.API + "/actions/runs/" + github["runId"] + "/attempts/" + github["runAttempt"]
    _attempt_response, attempt, _attempt_date = O.response_bytes(raw["attempt"], path, invocation, clock)
    response, jobs, date = O.response_bytes(raw["jobs"], path + "/jobs?per_page=100&page=1", invocation, clock)
    job = N.acquisition._run(context["observed"], N.I.parse(attempt, O.wire.BODY_LIMIT), N.I.parse(jobs, O.wire.BODY_LIMIT), date)
    actual = [job["id"], job["started_at"], job["runner_name"], job["runner_id"]]
    require(actual == context["originalServiceJob"] == context["history"]["serviceJob"], "GENUINE_SAME_RUNNER_JOB")
    return {"originalServiceJob": actual, "jobsOriginalSha256": O.digest(raw["jobs"]), "jobsBodySha256": O.digest(jobs),
        "serviceDateEpochSeconds": date, "jobsRequestStartedNs": O.integer(response["startedNs"]),
        "jobsRequestFinishedNs": O.integer(response["finishedNs"]),
        "steps": {role: row for role, row in RD.step_rows(job, date, edge=edge)}}


@dataclass(frozen=True, repr=False)
class _Acquired:
    state: object
    owner: object
    seed: object
    private: object
    context_raw: bytes
    before: object
    after: object
    phase: object
    match: object
    captured: tuple
    child_raw: bytes
    session_raw: bytes
    summary_raw: bytes
    pins: tuple
    graphs: tuple
    job_admission: tuple


def _acquired_passive(result):
    _pin(result)
    require(type(result) is _Acquired and result.state.authority is result and
        result.owner.phase_originals is result.phase and _native_state(result.seed).owner is result.owner and
        result.private is _native_state(result.seed).private, "ACTUAL_AUTHORITY_RETURN")
    result.owner.check()
    require(result.owner.original is None and not result.owner.unknown and result.owner.errors == [] and
        result.owner.initial_sources == {str(result.private.path / "source-before"): result.before,
            str(result.private.path / "source-after"): result.after} and
        result.owner.initial_sources[str(result.private.path / "source-before")] is result.before and
        result.owner.initial_sources[str(result.private.path / "source-after")] is result.after, "ACTUAL_AUTHORITY_OWNER")
    C._collect_source_current(result.pins[0])
    C._collect_source_current(result.pins[1])
    C._collect_phase_current(result.pins[2])
    C._custody_match_check(result.pins[3])
    for graph in result.graphs:
        N._check_history(graph)
    final = result.state.final[1]
    job = N._job_admission(result.job_admission, result.seed, O.encoded(final["originalProposal"]),
        O.encoded(final["workerIdentity"]), result.state.clock.first.clock)
    require(job.values[3] == result.state.clock.boot and job.values[4] == tuple(final["history"]["serviceJob"]) and
        job.values[5] == final["history"]["originalJobBasisNs"] and
        result.state.clock.last < job.end_ns and result.state.clock.final <= job.end_ns,
        "ORIGINAL_JOB_ADMISSION")
    return result


def _authority_read(state, seed):
    value = _native_state(seed)
    owner, private, before = value.owner, value.private, value.before
    phase = owner.phase_originals
    require(type(phase) is B.OriginalPhase and phase.context is value.context_raw, "ACTUAL_NATIVE_PHASE_RETURN")
    context = RD.authority_context(value.context_raw, edge=value.edge)
    require(owner.read(private, "context.json") == value.context_raw, "ACTUAL_AUTHORITY_CONTEXT_READBACK")
    policy = N.source_readback(owner, private.path / "source-before", before)
    C._collect_query_index(private.path / "source-before", before.session, policy, context["observed"], source=before)
    require(policy["candidate_policy_raw"] == state.policy_raw and context["sourceReturnSha256"] == O.digest(before.raw),
        "CURRENT_SOURCE_POLICY")
    service = owner.child(private, "service")
    for name, raw in phase.records:
        maximum = B.ACK_LIMIT if name == "stdout.log" else B.STDERR_LIMIT if name == "stderr.log" else CD.LIMIT
        require(owner.read(service, name, maximum) == raw, "ACTUAL_NATIVE_PHASE_BYTES")
    child_raw = owner.read(service, "child-result.json")
    _context, start, returned, birth, child, ack = _phase_data(value.context_raw, dict(phase.records), child_raw,
        state.clock.first.clock, state.clock.boot, tuple(private.identity), tuple(service.identity), edge=value.edge)
    queries = owner.open(private.path / "acquisition-queries")
    session = N.query_session(owner, queries)
    originals = tuple((name, owner.read(queries, name + ".bin")) for name in N.ORIGINAL_KEYS)
    raw = dict(originals)
    require(child["querySessionSha256"] == O.digest(session) and child["originalsSha256"] ==
        {name: O.digest(blob) for name, blob in originals} and child["matchSha256"] == O.digest(raw["match"]) and
        raw["event"] == state.event_raw and raw["candidate_policy_raw"] == state.policy_raw and
        raw["match"] == state.match_raw and {name: raw[name] for name in N.SOURCE_KEYS} == policy, "CURRENT_NATIVE_ORIGINALS")
    C._collect_query_index(private.path / "acquisition-queries", session, raw, context["observed"])
    match, service_time = N.retained_match(context, raw, start["invocation"], state.clock.first.clock,
        start["startedNs"], start["workEndNs"])
    require(match.record == state.match_raw, "CURRENT_MATCH")
    steps = _service_steps(value.context_raw, originals, start["invocation"], state.clock.first.clock, value.edge)
    require(child["serviceSteps"] == steps, "ACTUAL_CHILD_STEPS")
    minimum = N._service_chain_minimum(state.clock.first.nanoseconds, context["sourceReturnedNs"], start, returned,
        birth, child, service_time, ack)
    observed = state.fence.now(minimum=minimum)
    summary = {"contextSha256": O.digest(value.context_raw), "sourceBeforeSha256": O.digest(before.raw),
        "freshMatchSha256": O.digest(match.record), "originalsSha256": {name: O.digest(blob) for name, blob in originals},
        "querySessionSha256": O.digest(session), "phaseSha256": {name: O.digest(blob) for name, blob in phase.records},
        "childSha256": O.digest(child_raw), "ackSha256": O.digest(dict(phase.records)["stdout.log"]),
        "invocation": start["invocation"], "startedNs": start["startedNs"], "workEndNs": start["workEndNs"],
        "finalEndNs": start["finalEndNs"], "acquiredNs": child["acquiredNs"], "checkedNs": observed, "serviceSteps": steps}
    return match, (value.context_raw, originals, start["invocation"], start["startedNs"], start["workEndNs"]), summary, child_raw, session


def _predecessor(state):
    raw = dict(state.final_raws)
    return {"exportTransferSha256": O.digest(raw["returned/" + CD.LATER_FILES[1]]),
        "collectCloseSha256": O.digest(raw["returned/" + CD.LATER_FILES[4]]),
        "manifestSha256": O.digest(raw["export-output/manifest.json"]),
        "sealSha256": O.digest(state.seal_raw) if state.seal_raw is not None else None,
        "exportOutcome": "success", "collectOutcome": "success", "sealOutcome": "success" if state.seal_raw is not None else "NOT_OBSERVED"}


def _acquire(state, token):
    """The only token-bearing parent helper. No later return retains the token."""
    try:
        _current(state)
        edge = state.entry.edge
        require(edge in ("seal", "before") and type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token),
            "AUTHORITY_CREDENTIAL")
        authority_first = state.fence.now()
        seed = _native_seed(state, edge)
        owner = _ReceiverNativeOwner(seed)
        value = _native_state(seed)
        custody = owner.open(C._paths("worker")[2])
        root = owner.child(custody, "productive-receiver", create=edge == "seal")
        private_parent = owner.child(root, edge, create=True)
        private = owner.child(private_parent, "authority", create=True)
        owner.child(private, "control-home", create=True)
        owner.child(private, "temporary", create=True)
        observed = CD.canonical(state.observed_raw, CD.PUBLIC_LIMIT)
        final = state.final[1]
        window = {"schema": 1, "scope": RD.WINDOW_SCOPE, "edge": edge, "clock": O.clock_value(state.clock.first.clock),
            "originalBootDigest": state.clock.boot, "originalJobBasisNs": final["history"]["originalJobBasisNs"],
            "originalProposalSha256": O.digest(O.encoded(final["originalProposal"])), "sealFirstNs": state.clock.seal_first,
            "sealEndNs": state.clock.seal_end, "authorityFirstNs": authority_first,
            "authorityWorkEndNs": state.fence.work, "authorityFinalEndNs": state.fence.final,
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        RD.authority_window(window)
        before = N.source_queries(owner, state.fence, observed, private.path / "source-before")
        source = N.source_readback(owner, private.path / "source-before", before)
        require(source["candidate_policy_raw"] == state.policy_raw and {name: O.digest(raw) for name, raw in before.records} ==
            final["sourceRecordsSha256"], "ORIGINAL_SOURCE_BEFORE")
        context = {"schema": 1, "scope": RD.SEAL_CONTEXT_SCOPE if edge == "seal" else RD.BEFORE_CONTEXT_SCOPE,
            "edge": edge, "kind": "worker", "root": str(ROOT), "session": str(private.path), "job": uuid.uuid4().hex,
            "observed": observed, "history": final["history"], "originalProposal": final["originalProposal"],
            "expectedMatch": CD.canonical(state.match_raw, CD.PUBLIC_LIMIT), "eventSha256": O.digest(state.event_raw),
            "authorityWindow": window, "sourceReturnSha256": O.digest(before.raw),
            "sourceReturnedNs": CD.canonical(before.raw)["returnedNs"], "inheritedContext": Q._inherited_context(),
            "directoryIdentity": list(private.identity), "predecessor": _predecessor(state),
            "originalServiceJob": final["history"]["serviceJob"], "inputCloseSha256": O.digest(state.input_close.raw),
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
        context_raw = O.encoded(context)
        RD.authority_context(context_raw, edge=edge)
        require(owner.write(private, "context.json", context_raw) == context_raw, "CONTEXT_WRITE")
        _update(value, private=private, context_raw=context_raw, before=before)
        bridge = N._productive_seal_authority_phase if edge == "seal" else N._productive_before_authority_phase
        _service, phase = bridge(seed, owner, private, context_raw, token, state.fence, before)
        token = None
        require(owner.phase_originals is phase, "ORIGINAL_SERVICE_RETURN")
        first = _authority_read(state, seed)
        after = N.source_queries(owner, state.fence, observed, private.path / "source-after")
        require(N.source_readback(owner, private.path / "source-after", after) == source, "ORIGINAL_SOURCE_AFTER")
        match, captured, summary, child_raw, session_raw = _authority_read(state, seed)
        require(first[0].record == match.record and first[1] == captured and first[3:] == (child_raw, session_raw),
            "CURRENT_AUTHORITY_RETURN_CHANGED")
        summary["sourceAfterSha256"] = O.digest(after.raw)
        pins = (C._collect_source_pin(before), C._collect_source_pin(after), C._collect_phase_pin(phase),
            C._custody_match_pin(match, "worker"))
        graphs = (N._history_graph(context), N._history_graph(captured), N._history_graph(summary))
        identity = N.initial_identity.bind_worker_match(match, event_raw=state.event_raw,
            policy_raw=state.policy_raw, now=int(time.time()))
        require(identity.record == O.encoded(final["workerIdentity"]), "ORIGINAL_JOB_WORKER")
        values = N._job_envelope_values(O.encoded(final["originalProposal"]), identity, state.clock.first.clock,
            N._service_job(captured, state.clock.first.clock), state.clock.boot)
        require(values[4] == tuple(final["history"]["serviceJob"]) and
            values[5] == final["history"]["originalJobBasisNs"] and state.fence.now() < values[-1],
            "ORIGINAL_SERVICE_JOB_END")
        job_admission = N._OriginalServiceJobAdmission(seed, values), values
        result = _track(_Acquired(state, owner, seed, private, context_raw, before, after, phase, match, captured,
            child_raw, session_raw, O.encoded(summary), pins, graphs, job_admission))
        _update(state, authority=result)
        _acquired_passive(result)
        return result
    finally:
        token = None


def _pre_metadata(entry, cancelled):
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    try:
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token), "ORIGINAL_PARENT_TOKEN")
        state = _new_state(entry, cancelled)
        _read_inputs(state)
        if entry.edge == "seal":
            _enter_seal(state)
        return _acquire(state, token)
    finally:
        token = None


def _index(result):
    _acquired_passive(result)
    path = result.private.path
    context = RD.authority_context(result.context_raw, edge=result.state.entry.edge)
    rows, directories, identifiers = [], [path, path / "control-home", path / "temporary", path / "service"], []
    groups = (("source-before", result.before, result.before.session, dict(result.before.records)),
        ("acquisition-queries", None, result.session_raw, dict(result.captured[1])),
        ("source-after", result.after, result.after.session, dict(result.after.records)))
    for side, source, raw, originals in groups:
        records, targets = C._collect_query_index(path / side, raw, originals, context["observed"], source=source)
        rows.extend(records)
        directories.extend(targets)
        # Query stream caps belong to this actual original order, never sorted UUID order.
        identifiers.append(tuple(query["id"] for query in CD.canonical(raw, Q.MAX_RECEIPT_BYTES)["queries"]))
    required, directory_names = C.B.member_grammar(*identifiers)
    for name, raw in (("context.json", result.context_raw), ("service/child-result.json", result.child_raw),
            *(("service/" + name, raw) for name, raw in result.phase.records)):
        maximum = B.ACK_LIMIT if name == "service/stdout.log" else B.STDERR_LIMIT if name == "service/stderr.log" else CD.LIMIT
        rows.append((path / name, maximum, len(raw), O.digest(raw)))
    index = tuple(sorted((str(target.relative_to(path)).replace(os.sep, "/"), maximum, count, checksum)
        for target, maximum, count, checksum in rows))
    require(tuple(row[0] for row in index) == tuple(name for name in required if name != "authority-close.json") and
        len(index) == 279 and tuple(sorted(str(target.relative_to(path)).replace(os.sep, "/") for target in directories)) == directory_names and
        sum(row[2] for row in index) <= CD.MAX_BYTES, "ACTUAL279_DECLARATIONS")
    return index, required, directory_names


def _query_originals(context, originals, side, *, phase_start):
    """Closed original query packet joins, without a constructed SourceReturn."""
    raw = originals[side + "/session-result.json"]
    session = CD.fields(CD.canonical(raw, Q.MAX_RECEIPT_BYTES),
        "schema scope job queries result retirement firstError errors readbacks")
    acquisition = side == "acquisition-queries"
    keys, query_count = (N.ORIGINAL_KEYS, 24) if acquisition else (N.SOURCE_KEYS, 12)
    require(type(session["schema"]) is int and session["schema"] == 1 and session["scope"] == "ORDINARY_GIT_QUERIES_ONLY" and
        session["result"] == "READY_FOR_CALLER_SEAL" and session["retirement"] == "KNOWN" and session["firstError"] is None and
        session["errors"] == [] and type(session["queries"]) is list and len(session["queries"]) == query_count and
        type(session["readbacks"]) is list, "ORIGINAL_QUERY_SESSION")
    CD.job(session["job"])
    path = Path(context["session"]) / side
    own = CD.fields(CD.canonical(originals[side + "/owner.json"]),
        "schema scope job state home root nativeRole git ancestorContext")
    inherited = phase_start["inheritedContext"] if acquisition else context["inheritedContext"]
    clock = O.wire.clock_identity(context["authorityWindow"]["clock"])
    require(type(own["schema"]) is int and own["schema"] == 1 and own["scope"] == session["scope"] and own["job"] == session["job"] and
        own["state"] == str(path) and own["home"] == str(path / "query-home") and own["root"] == context["root"] and
        own["nativeRole"] == clock.role and own["ancestorContext"] == inherited, "ORIGINAL_QUERY_OWNER")
    entry_raw = originals[side + "/candidate_policy_entry.bin"]
    match = re.fullmatch(rb"100644 blob ([0-9a-f]{40})\t" + re.escape(N.I.POLICY_PATH.encode("ascii")) + rb"\x00", entry_raw)
    require(match is not None, "ORIGINAL_QUERY_POLICY_BLOB")
    blob = match.group(1).decode("ascii")
    source = context["observed"]["source"]["commit"]
    commands = (("rev-parse", "--show-toplevel"), ("status", "--porcelain=v1", "--untracked-files=all"),
        ("rev-parse", "--verify", "HEAD^{commit}"), ("rev-parse", "--verify", source + "^{tree}"),
        ("rev-parse", "--is-shallow-repository"), ("rev-parse", "--verify", "refs/remotes/origin/main^{commit}"),
        ("rev-parse", "--verify", N.acquisition.stages.BASE["commit"] + "^{tree}"),
        ("ls-tree", "-z", N.acquisition.stages.BASE["commit"], "--", N.I.POLICY_PATH),
        ("merge-base", N.acquisition.stages.BASE["commit"], source), ("ls-tree", "-z", source, "--", N.I.POLICY_PATH),
        ("cat-file", "-s", blob), ("cat-file", "blob", blob))
    expected = [(path, "owner.json", None)]
    if acquisition:
        expected.append((path, "event.bin", None))
    identifiers, totals = [], len(raw)
    for ordinal, query in enumerate(session["queries"]):
        CD.job(query.get("id"))
        require(query["id"] not in identifiers, "ORIGINAL_QUERY_ID_ALIAS")
        identifiers.append(query["id"])
        prefix = side + "/query-" + query["id"] + "/"
        directory = path / ("query-" + query["id"])
        stdout_limit = N.I.EVENT_LIMIT if ordinal % 12 == 1 else N.I.POLICY_LIMIT if ordinal % 12 == 11 else 4096
        require(type(query.get("stdoutLimit")) is int and query["stdoutLimit"] == stdout_limit and
            type(query.get("stderrLimit")) is int and query["stderrLimit"] == 4096 and query.get("argv") ==
            [own["git"], "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false", "-C", context["root"],
                *commands[ordinal % 12]] and query.get("job") == session["job"] and query.get("state") == str(path) and
            query.get("home") == str(path / "query-home") and query.get("cwd") == context["root"] and
            query.get("launchAttempted") is query.get("scopeAttempted") is True and type(query.get("waitExitCode")) is int and
            query["waitExitCode"] == 0 and query.get("retirement") == "KNOWN" and query.get("result") == "READY_FOR_CALLER_SEAL" and
            query.get("errors") == query.get("ownedSurvivors") == [], "ORIGINAL_QUERY_COMMAND_RETURN")
        require(originals[prefix + "result.json"] == Q.encoded(query), "ORIGINAL_QUERY_RESULT_BYTES")
        start = CD.canonical(originals[prefix + "start.json"])
        pending = {name: item for name, item in query.items() if name not in ("ownership", "ownedSurvivors")}
        pending.update(launchAttempted=False, scopeAttempted=False, waitExitCode=None, retirement="UNKNOWN", result="HOLD", errors=[], outputs={})
        require(set(start) == set(pending) | {"environment"} and {name: start[name] for name in pending} == pending and
            type(start["environment"]) is dict and all(type(name) is type(item) is str for name, item in start["environment"].items()) and
            not any(name in start["environment"] for name in P._CREDENTIAL_NAMES), "ORIGINAL_QUERY_PENDING_START")
        baseline = CD.fields(CD.canonical(originals[prefix + "baseline.json"]), "nativeRole baseline kernelJob")
        require(baseline["nativeRole"] == clock.role and baseline["kernelJob"] is (clock.role == "windows-x64") and
            (baseline["baseline"] is None if baseline["kernelJob"] else type(baseline["baseline"]) is list), "ORIGINAL_QUERY_BASELINE")
        for stream, limit in (("stdout", stdout_limit), ("stderr", 4096)):
            payload = originals[prefix + stream + ".log"]
            capture = query["outputs"][stream]
            # The genuine query also retains its native sink metadata. This
            # receiver newly reads that native stream; it must not erase the
            # original metadata by demanding a fictitious two-field output.
            require(type(capture) is dict and len(payload) <= limit and type(capture.get("bytes")) is int and
                capture["bytes"] == len(payload) and capture.get("sha256") == O.digest(payload),
                "ORIGINAL_QUERY_STREAM_BYTES")
        expected.extend((directory, name, stdout_limit if name == "stdout.log" else 4096 if name == "stderr.log" else None)
            for name in C.B.QUERY_FILES)
        if acquisition and ordinal == 11:
            expected.extend((path, name + ".bin", None) for name in (*N.SOURCE_KEYS, *N.HTTP_KEYS))
    expected.extend((path, name + ".bin", None) for name in (("observation", "match") if acquisition else N.SOURCE_KEYS))
    require(len(session["readbacks"]) == len(expected), "ORIGINAL_QUERY_FULL_READBACK_ROSTER")
    declarations = []
    for row, (parent, name, limit) in zip(session["readbacks"], expected):
        CD.fields(row, "parent name maximum retirement result bytes sha256")
        relative = str((parent / name).relative_to(Path(context["session"]))).replace(os.sep, "/")
        payload = originals[relative]
        require(row["parent"] == str(parent) and row["name"] == name and row["retirement"] == "KNOWN" and row["result"] == "RETAINED" and
            type(row["bytes"]) is int and row["bytes"] == len(payload) and type(row["maximum"]) is int and
            0 <= row["bytes"] <= row["maximum"] <= Q.MAX_RECEIPT_BYTES and
            row["maximum"] == (max(1, row["bytes"]) if limit is None else limit) and row["sha256"] == O.digest(payload),
            "ORIGINAL_QUERY_READBACK_BYTES")
        totals += row["bytes"]
        require(totals <= Q.MAX_SESSION_BYTES, "ORIGINAL_QUERY_TOTAL")
        declarations.append((relative, row["maximum"], row["bytes"], row["sha256"]))
    declarations.append((side + "/session-result.json", Q.MAX_RECEIPT_BYTES, len(raw), O.digest(raw)))
    if not acquisition:
        returned_raw = originals[side + "/source-return.json"]
        returned = CD.fields(CD.canonical(returned_raw), "schema scope originalsSha256 sessionSha256 clock returnedNs")
        require(type(returned["schema"]) is int and returned["schema"] == 1 and returned["scope"] == N.SOURCE_SCOPE and
            returned["originalsSha256"] == {name: O.digest(originals[side + "/" + name + ".bin"]) for name in keys} and
            returned["sessionSha256"] == O.digest(raw) and returned["clock"] == context["authorityWindow"]["clock"], "ORIGINAL_SOURCE_RETURN")
        CD.integer(returned["returnedNs"])
        declarations.append((side + "/source-return.json", CD.LIMIT, len(returned_raw), O.digest(returned_raw)))
    return tuple(identifiers), tuple(declarations)


def _historical_authority(state, edge, originals, index):
    """Verify new reads of a prior seal. This never hydrates an earlier owner."""
    require(type(originals) is dict and len(originals) == index["fileCount"] and
        tuple(sorted(originals)) == tuple(index["requiredFiles"]), "HISTORICAL_COMPLETE280")
    for row in index["files"]:
        raw = originals[row["relative"]]
        require(type(raw) is bytes and row["bytes"] == len(raw) and row["sha256"] == O.digest(raw), "HISTORICAL_ORIGINAL_BYTES")
    context_raw = originals["context.json"]
    context = RD.authority_context(context_raw, edge=edge)
    require(context["eventSha256"] == O.digest(state.event_raw) and context["observed"] == CD.canonical(state.observed_raw) and
        O.encoded(context["expectedMatch"]) == state.match_raw and
        context["authorityWindow"]["sealFirstNs"] == state.clock.seal_first and
        context["authorityWindow"]["sealEndNs"] == state.clock.seal_end and index["root"] == context["session"],
        "HISTORICAL_ORIGINAL_SOURCE_AND_CAP")
    directory_pins = {row["relative"]: tuple(row["readbackNative"])[1:3] for row in index["directories"]}
    _context, start, returned, birth, child, ack = _phase_data(context_raw,
        {name: originals["service/" + name] for name in C.B.PHASE_FILES}, originals["service/child-result.json"],
        state.clock.first.clock, state.clock.boot, directory_pins["."], directory_pins["service"], edge=edge)
    declarations, identifiers = [], []
    for side in ("source-before", "acquisition-queries", "source-after"):
        query_ids, declared = _query_originals(context, originals, side, phase_start=start)
        identifiers.append(query_ids)
        declarations.extend(declared)
    required, directories = C.B.member_grammar(*identifiers)
    require(tuple(index["requiredFiles"]) == required and tuple(row["relative"] for row in index["directories"]) == directories,
        "HISTORICAL_ORIGINAL_QUERY_ORDER")
    original = tuple((name, originals["acquisition-queries/" + name + ".bin"]) for name in N.ORIGINAL_KEYS)
    raw = dict(original)
    require(raw["event"] == state.event_raw and raw["match"] == state.match_raw and raw["candidate_policy_raw"] == state.policy_raw and
        child["querySessionSha256"] == O.digest(originals["acquisition-queries/session-result.json"]) and
        child["originalsSha256"] == {name: O.digest(data) for name, data in original}, "HISTORICAL_PRIVATE_ORIGINALS")
    for side in ("source-before", "source-after"):
        require(all(originals[side + "/" + name + ".bin"] == raw[name] for name in N.SOURCE_KEYS), "HISTORICAL_SOURCE12_24_12")
    match, service = N.retained_match(context, raw, start["invocation"], state.clock.first.clock, start["startedNs"], start["workEndNs"])
    require(match.record == state.match_raw and child["serviceSteps"] ==
        _service_steps(context_raw, original, start["invocation"], state.clock.first.clock, edge), "HISTORICAL_CURRENT_POLICY_AND_PRIOR_STEP")
    before_return = CD.canonical(originals["source-before/source-return.json"])
    after_return = CD.canonical(originals["source-after/source-return.json"])
    require(context["sourceReturnSha256"] == O.digest(originals["source-before/source-return.json"]) and
        context["sourceReturnedNs"] == before_return["returnedNs"] and returned["finalizedNs"] <= after_return["returnedNs"] <
        context["authorityWindow"]["sealEndNs"], "HISTORICAL_NATIVE_SOURCE_ORDER")
    for name in ("context.json", "service/child-result.json", *("service/" + name for name in C.B.PHASE_FILES)):
        maximum = B.ACK_LIMIT if name == "service/stdout.log" else B.STDERR_LIMIT if name == "service/stderr.log" else CD.LIMIT
        declarations.append((name, maximum, len(originals[name]), O.digest(originals[name])))
    known = {row["relative"]: (row["maximum"], row["bytes"], row["sha256"]) for row in index["files"]}
    require(len(declarations) == 279 and all(known[name] == (maximum, count, checksum) for name, maximum, count, checksum in declarations),
        "HISTORICAL_ALL279_DECLARATION_JOIN")
    RD.authority_close(originals["authority-close.json"], edge=edge)


def _capture(result, declarations, required, directory_names, original_pins):
    state, path = result.state, result.private.path
    owner = _file_owner(state)
    native_pins = {name: identity for name, _row, _directory, _path, identity in original_pins}
    require(set(native_pins) == set(C.B.DIRECTORY_TARGETS), "SEVEN_LOGICAL_ORIGINAL_PINS")
    members = dict(C.B.directory_members(required, directory_names, closed=False))
    handles, directories, directory_keys = {}, [], set()
    for relative in sorted(directory_names, key=lambda item: (item.count("/"), item != ".", item)):
        target = path if relative == "." else path.joinpath(*relative.split("/"))
        directory = C._private(owner, target)
        stamp = _directory_stamp(directory)
        key = CD.native_key(stamp)
        require(key not in directory_keys and (relative not in native_pins or stamp[1:3] == native_pins[relative]),
            "ACTUAL_DIRECTORY_PIN_OR_ALIAS")
        directory_keys.add(key)
        _members(owner, directory, members[relative])
        handles[relative] = directory
        directories.append({"relative": relative, "path": str(target),
            "originalIdentity": list(native_pins[relative]) if relative in native_pins else None,
            "originalProvenance": "ORIGINAL_AUTHORITY_NATIVE_PIN" if relative in native_pins else "UNPINNED_ORIGINAL_DIRECTORY",
            "readbackNative": list(stamp)})
    rows, observations, total, identities = [], [], 0, set(directory_keys)
    for relative, maximum, size, checksum in declarations:
        parent, _slash, leaf = relative.rpartition("/")
        row, observation = _read_native(owner, handles[parent or "."], leaf, maximum, relative, expected=(size, checksum))
        key = CD.native_key(row[3])
        total += len(row[1])
        require(key not in identities and total <= CD.MAX_BYTES, "ACTUAL279_NATIVE_ALIAS_OR_TOTAL")
        identities.add(key)
        rows.append(row)
        observations.append(observation)
    require(len(rows) == 279, "ACTUAL279_FULL_REREAD")
    originals = {row[0]: row[1] for row in rows}
    context, start, _caps = _start_data(result.context_raw, dict(result.phase.records)["start.json"],
        state.clock.first.clock, state.clock.boot, state.entry.edge)
    for side in ("source-before", "acquisition-queries", "source-after"):
        _query_originals(context, originals, side, phase_start=start)
    for relative, directory in handles.items():
        _members(owner, directory, members[relative])
    _acquired_passive(result)
    N._check_worker_pins(original_pins, state.clock.first.clock.role)
    closed = _close_owner(owner)
    state.fence.now()
    return tuple(rows), tuple(observations), tuple(sorted(directories, key=lambda row: row["relative"])), closed


@dataclass(frozen=True, repr=False)
class _AuthorityClosed:
    acquired: object
    raw: bytes
    index_raw: bytes
    files: tuple
    input_close: object
    readback_close: object
    native_close: object
    writer_close: object
    writer_raw: bytes
    original_pins: tuple


def _close_authority(result):
    """All token-bearing frames returned before the actual279+separate1 work."""
    _acquired_passive(result)
    state, owner, path = result.state, result.owner, result.private.path
    declarations, required, directory_names = _index(result)
    targets = {name: path if name == "." else path / name for name in C.B.DIRECTORY_TARGETS}
    pins = N._worker_pins(owner, state.clock.first.clock.role, targets)
    require(all(label == "directory" or attempted and closed for _row, label, _resource, attempted, closed in owner.check().rows),
        "ALL_ORIGINAL_WRITERS_CLOSED")
    rows, observations, directories, readback_close = _capture(result, declarations, required, directory_names, pins)
    preclose = state.fence.now()
    native_close = _close_owner(owner)
    closed = state.fence.now(minimum=preclose)
    N._check_worker_pins(pins, state.clock.first.clock.role, closed=True)
    context = RD.authority_context(result.context_raw, edge=state.entry.edge)
    raw = O.encoded({"schema": 1, "scope": RD.CLOSE_SCOPE, "edge": state.entry.edge,
        "contextSha256": O.digest(result.context_raw), "authorityWindow": context["authorityWindow"],
        "predecessor": context["predecessor"], "inputCloseSha256": O.digest(state.input_close.raw),
        "authority": CD.canonical(result.summary_raw), "parentClose": RD.known_close(native_close.raw, native=True),
        "preCloseNs": preclose, "closedNs": closed, "requiredFiles": list(required), "requiredFileCount": 280,
        "otherFiles": list(observations), "otherFilesCount": 279, "otherFilesTotalBytes": sum(len(row[1]) for row in rows),
        "directories": list(directories), "directoryCount": 58, "originalReadbackClose": RD.known_close(readback_close.raw),
        "self": {"relative": "authority-close.json", "maximum": CD.LIMIT, "state": "PENDING_SEPARATE_WRITER_READBACK_AND_CLOSE"},
        "writerReturn": CD.PENDING, "originalStepOutcome": "NOT_OBSERVED", "liveRecipient": "NOT_CREATED", "capture": "NOT_K_CAPTURE",
        "upload": "NOT_PERFORMED", "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False, "cacheAuthority": False,
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
    RD.authority_close(raw, edge=state.entry.edge)
    partial_index = {"requiredFiles": list(required), "directories": list(directories)}
    final_row, final_observation, writer_close, writer_raw = _write_file(state, path, "authority-close.json", raw, complete_index=partial_index)
    files = tuple(sorted((*rows, final_row), key=lambda row: row[0]))
    observed = sorted((*observations, final_observation), key=lambda row: row["relative"])
    require(tuple(row[0] for row in files) == required and len(files) == 280 and
        sum(len(row[1]) for row in files) <= CD.MAX_BYTES, "ACTUAL280_COMPLETE")
    index_raw = O.encoded({"schema": 1, "scope": RD.INDEX_SCOPE, "edge": state.entry.edge, "root": str(path),
        "clock": O.clock_value(state.clock.first.clock), "authorityContextSha256": O.digest(result.context_raw),
        "requiredFiles": list(required), "files": observed, "directories": list(directories), "fileCount": 280,
        "directoryCount": 58, "totalBytes": sum(len(row[1]) for row in files), "authorityCloseSha256": O.digest(raw),
        "closeWriterReturn": RD.writer_return(CD.canonical(writer_raw)), "originalReadbackClose": RD.known_close(readback_close.raw),
        "capture": "NOT_K_CAPTURE", "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
        "productiveAuthority": False, "cacheAuthority": False, "exportSaveAuthority": False})
    RD.authority_index(index_raw, edge=state.entry.edge)
    returned = _track(_AuthorityClosed(result, raw, index_raw, files, state.input_close, readback_close, native_close,
        writer_close, writer_raw, pins))
    _closed_authority(returned)
    return returned


def _closed_authority(result):
    _pin(result)
    require(type(result) is _AuthorityClosed, "ORIGINAL_AUTHORITY_CLOSED_TYPE")
    _acquired_passive(result.acquired)
    for close in (result.input_close, result.readback_close, result.native_close, result.writer_close):
        _checked_close(close)
    N._check_worker_pins(result.original_pins, result.acquired.state.clock.first.clock.role, closed=True)
    require(type(result.files) is tuple and len(result.files) == 280, "ORIGINAL_AUTHORITY280")
    for row in result.files:
        RD.file_row(row)
    return result


def _close_originals(result):
    _closed_authority(result)
    return (("input", result.input_close.raw), ("readback", result.readback_close.raw),
        ("native", result.native_close.raw), ("writer", result.writer_raw))


def _seal_ciphertext(state, authority):
    """New whole-ciphertext read, without a decryptor, payload Snapshot or token."""
    _closed_authority(authority)
    owner = _file_owner(state)
    output = C._private(owner, _froot() / "export-output")
    manifest_row = next(row for row in state.inputs if row[0] == "export-output/manifest.json")
    require(tuple(output.identity) == manifest_row[4][1:3], "CIPHERTEXT_ORIGINAL_DIRECTORY")
    _members(owner, output, ("evidence.tar.gz.gpg", "manifest.json"))
    first, _observed = _read_native(owner, output, "manifest.json", CD.PUBLIC_LIMIT, manifest_row[0],
        expected=(len(manifest_row[1]), O.digest(manifest_row[1])), native=manifest_row[3])
    require(first[1] == manifest_row[1], "CIPHERTEXT_MANIFEST_ORIGINAL")
    artifact = state.final[2]["artifact"]
    checksum, native, directory = _read_native(owner, output, artifact["name"], B.posix.MAX_CIPHERTEXT_BYTES,
        "export-output/" + artifact["name"], expected=(artifact["size"], artifact["sha256"]), retain=False)
    require(checksum == artifact["sha256"] and CD.native_key(native) not in {CD.native_key(row[3]) for row in state.inputs},
        "CIPHERTEXT_ORIGINAL_HASH_ALIAS")
    last, _observed = _read_native(owner, output, "manifest.json", CD.PUBLIC_LIMIT, manifest_row[0],
        expected=(len(manifest_row[1]), O.digest(manifest_row[1])), native=manifest_row[3])
    require(last[1] == first[1] == manifest_row[1], "CIPHERTEXT_MANIFEST_UNCHANGED")
    _members(owner, output, ("evidence.tar.gz.gpg", "manifest.json"))
    close = _close_owner(owner)
    closed = state.fence.now()
    _closed_authority(authority)
    value = {"artifact": artifact, "native": list(native), "directoryNative": list(directory), "eof": True,
        "retirement": "KNOWN_READER_CLOSE", "ownerClose": RD.known_close(close.raw), "closedNs": closed}
    return O.encoded(value), close


@dataclass(frozen=True, repr=False)
class ProductiveBefore:
    """Exactly one original same-process BEFORE; never a deserializable grant."""
    first: object
    first_local: float
    boot: str
    deadline_raw: bytes
    inputs: tuple
    input_closes: tuple
    authority_raw: bytes
    authority_index_raw: bytes
    authority_files: tuple
    authority_closes: tuple
    authority_close_originals: tuple
    fence: object


@dataclass(frozen=True, repr=False)
class _SealReturn:
    raw: bytes
    writer_raw: bytes
    ciphertext_raw: bytes


@dataclass(frozen=True, repr=False)
class _ChildReturn:
    raw: bytes
    invocation: str


@dataclass(frozen=True, repr=False)
class _Return:
    state: object
    result: object
    authority: object
    close_originals: tuple
    match_pins: tuple
    graphs: tuple


def _register(state, result, *, authority=None, close_originals=(), match_pins=(), graphs=()):
    require(state.result is None and id(result) not in _RETURNS and type(result) in (ProductiveBefore, _SealReturn, _ChildReturn),
        "RETURN_ONCE")
    _pin(result)
    _update(state, result=result)
    saved = _track(_Return(state, result, authority, close_originals, match_pins, graphs))
    _RETURNS[id(result)] = saved
    _registered(result)
    return result


def _registered(result, *, complete=False):
    """Only original object/known-close checks. No clock, native I/O or policy time."""
    saved = _RETURNS.get(id(result))
    require(type(complete) is bool and type(saved) is _Return and saved.result is result, "RETURN_NOT_ORIGINAL")
    state = saved.state
    try:
        _pin(saved)
        _pin(result)
        _pin(state)
        _pin(state.clock)
        _entry_check(state.entry)
        require(state.result is result and _STATES.get(id(state.fence)) is state and state.entry.state is state and
            type(state.fence) is _Fence and state.fence._view() is state.clock, "RETURN_SAME_SOURCE_STATE")
        N._check_history(state.clock.first_graph)
        for graph in (*state.graphs, *saved.graphs):
            N._check_history(graph)
        for match in saved.match_pins:
            C._custody_match_check(match)
        require(state.owners, "RETURN_REAL_OWNERS_REQUIRED")
        for owner, anchor, methods in state.owners:
            require(owner._anchor() is anchor, "RETURN_OWNER_CHANGED")
            _methods_current(owner, methods)
            close = _CLOSES.get(id(owner))
            require(type(close) is _OwnerClose and close.owner is owner, "RETURN_EVERY_OWNER_KNOWN_CLOSED")
            _checked_close(close)
        if saved.authority is not None:
            _closed_authority(saved.authority)
            require(saved.authority.acquired.state is state and saved.close_originals == _close_originals(saved.authority),
                "RETURN_ACTUAL_AUTHORITY_CLOSE_BYTES")
        if type(result) is ProductiveBefore:
            require(state.entry.edge == "before" and result.first is state.clock.first and
                result.first_local is state.clock.first_local and result.boot is state.clock.boot and
                result.inputs is state.inputs and result.input_closes == (state.input_close,) and
                result.authority_raw is saved.authority.raw and result.authority_index_raw is saved.authority.index_raw and
                result.authority_files is saved.authority.files and result.authority_close_originals is saved.close_originals and
                result.authority_closes == (saved.authority.readback_close, saved.authority.native_close, saved.authority.writer_close) and
                result.fence is state.fence, "BEFORE_EXACT12_ORIGINAL")
        elif type(result) is _SealReturn:
            require(state.entry.edge == "seal" and saved.authority is not None, "SEAL_ACTUAL_RETURN")
        else:
            require(type(result) is _ChildReturn and state.entry.edge in ("seal-child", "before-child") and
                saved.authority is None and len(saved.match_pins) == 2, "CHILD_ACTUAL_RETURN")
        if complete:
            state.entry.latch.returned(state.entry.table, state.entry.attempt, result)
        return saved
    except BaseException as error:
        raise _fail(state, error)


def checked_productive_before(result):
    """PASSIVE exact result checker used by K. Not a new BEFORE or live lease."""
    require(type(result) is ProductiveBefore, "BEFORE_RETURN_TYPE")
    _registered(result, complete=True)
    return result


def _deadline_raw(state):
    require(state.entry.edge == "before" and type(state.seal_raw) is bytes, "DEADLINE_AFTER_REAL_SEAL")
    raw = dict(state.final_raws)
    seal = RD.seal_record(state.seal_raw, raw)
    ends = RD._proposal(state.final[1]["originalProposal"], state.final[1]["history"])
    value = {"schema": 1, "scope": RD.DEADLINE_SCOPE, "kind": "worker",
        **{name: seal[name] for name in ("selection", "source", "github", "policySha256", "originalProposalSha256",
            "originalJobBasisNs", "clock", "originalBootDigest", "sealFirstNs", "sealEndNs")},
        "uploadStartByNs": ends["upload-transition"], "uploadEndNs": ends["evidence-upload"],
        "afterEndNs": ends["upload-after-guard"], "returnEndNs": ends["delivery-return"],
        "collectCloseSha256": O.digest(raw["returned/" + CD.LATER_FILES[4]]),
        "manifestSha256": O.digest(raw["export-output/manifest.json"]), "sealSha256": O.digest(state.seal_raw),
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}
    result = O.encoded(value)
    RD.deadline(result, final=raw, seal_raw=state.seal_raw)
    return result


def productive_before(cancelled):
    """New real BEFORE on the original seal end, returning only to its in-process K."""
    entry = _begin("before")
    try:
        acquired = _pre_metadata(entry, cancelled)
        state = acquired.state
        # The helper's token-bearing frame has returned before actual280 closes,
        # construction of this result and any K/Recipient/crypto operation.
        closed = _close_authority(acquired)
        originals = _close_originals(closed)
        RD.authority_bundle(closed.raw, closed.index_raw, closed.files, originals, edge="before", input_rows=state.inputs)
        deadline_raw = _deadline_raw(state)
        state.fence.now()
        result = _track(ProductiveBefore(state.clock.first, state.clock.first_local, state.clock.boot, deadline_raw,
            state.inputs, (state.input_close,), closed.raw, closed.index_raw, closed.files,
            (closed.readback_close, closed.native_close, closed.writer_close), originals, state.fence))
        _register(state, result, authority=closed, close_originals=originals)
        entry.latch.complete(entry.table, entry.attempt, result)
        return checked_productive_before(result)
    except BaseException as error:
        raise _abort(entry.state, error) if type(entry.state) is _State else _fail(entry, error)


@dataclass(eq=False, repr=False)
class _Output:
    fence: object
    result: object
    state: object
    value: dict
    binding: tuple
    graph: tuple
    limit: int
    outputs: tuple
    child: bool
    phase: str
    expected_closed: object
    checks: int = 0
    busy: bool = False


def _output_current(output):
    _pin(output)
    require(_OUTPUTS.get(id(output.fence)) is output and type(output.fence) is _TwoChecks, "OUTPUT_ORIGINAL_FENCE")
    saved = _registered(output.result, complete=output.phase == "OUTPUT")
    require(saved.state is output.state and output.limit == output.state.clock.work and
        output.limit <= output.state.clock.seal_end, "OUTPUT_SAME_ORIGINAL_END")
    N._check_history(output.graph)
    require(tuple(output.value) == tuple(name for name, _value in output.binding) and
        all(output.value[name] is original for name, original in output.binding if not (output.child and name == "closedNs")),
        "OUTPUT_ORIGINAL_PUBLIC_VALUE")
    if output.child:
        require(type(output.value["closedNs"]) is int and output.value["closedNs"] == output.expected_closed,
            "OUTPUT_ORIGINAL_ACK_OBSERVATION")
    else:
        require(type(output.result) is _SealReturn and output.outputs[0][1] == O.digest(output.result.raw), "OUTPUT_REAL_SEAL_HASH")
        RD.output_values(output.outputs)
    _current(output.state)
    return output


class _TwoChecks:
    """One append (seal only), followed by precisely the two shared stdout checks."""
    __slots__ = ()

    def _begin(self):
        saved = _OUTPUTS.get(id(self))
        require(type(saved) is _Output and saved.fence is self, "OUTPUT_NOT_ORIGINAL")
        try:
            _pin(saved)
            _entry_check(saved.state.entry)
            require(not saved.busy, "OUTPUT_REENTRY")
            _update(saved, busy=True)
            _output_current(saved)
            return saved
        except BaseException as error:
            raise _fail(saved.state, error)

    @staticmethod
    def _leave(saved):
        try:
            _update(saved, busy=False)
        except BaseException as error:
            raise _fail(saved.state, error)

    def _append_guard(self):
        saved = self._begin()
        try:
            require(not saved.child and saved.phase == "APPENDING" and saved.checks == 0, "OUTPUT_APPEND_BOUNDARY")
            saved.state.fence.now(final=True, limit=saved.limit)
            _output_current(saved)
        except BaseException as error:
            raise _fail(saved.state, error)
        finally:
            self._leave(saved)

    def append(self):
        saved = self._begin()
        try:
            require(not saved.child and saved.phase == "NEW" and saved.checks == 0, "OUTPUT_APPEND_ONCE")
            _update(saved, phase="APPENDING")
        except BaseException as error:
            raise _fail(saved.state, error)
        finally:
            self._leave(saved)
        try:
            N.continuity.append_productive_receiver_outputs(saved.outputs, self._append_guard)
            self._append_guard()
            _update(saved, phase="OUTPUT")
            return saved.value, self, saved.limit
        except BaseException as error:
            raise _fail(saved.state, error)

    def now(self, *, final=False, minimum=0, limit=None):
        saved = self._begin()
        try:
            require(saved.phase == "OUTPUT" and final is True and type(minimum) is int and minimum == 0 and
                type(limit) is int and limit == saved.limit and type(saved.checks) is int and saved.checks < 2,
                "OUTPUT_EXACT_TWO_LATE_CHECKS")
            _update(saved, checks=saved.checks + 1)
            observed = saved.state.fence.now(final=True, limit=saved.limit)
            _output_current(saved)
            if saved.child and saved.checks == 1:
                # The shared guarded stdout path, not this pending child,
                # updates closedNs to this just-returned original observation.
                _update(saved, expected_closed=observed)
            return observed
        except BaseException as error:
            raise _fail(saved.state, error)
        finally:
            self._leave(saved)


def _output_fence(result, value, *, outputs=(), child=False):
    saved = _registered(result)
    require(type(child) is bool and not any(row.result is result for row in _OUTPUTS.values()) and
        type(value) is dict and type(outputs) is tuple, "OUTPUT_ONCE")
    fence, state = _TwoChecks(), saved.state
    graph = N._history_graph(tuple((name, item) for name, item in value.items() if not (child and name == "closedNs")))
    output = _track(_Output(fence, result, state, value, tuple(value.items()), graph, state.clock.work, outputs, child,
        "OUTPUT" if child else "NEW", value.get("closedNs") if child else None))
    _OUTPUTS[id(fence)] = output
    _output_current(output)
    return fence


def seal(cancelled):
    """Actual productive seal; pending bytes never claim their own successful Step."""
    entry = _begin("seal")
    try:
        acquired = _pre_metadata(entry, cancelled)
        state = acquired.state
        closed = _close_authority(acquired)
        originals = _close_originals(closed)
        RD.authority_bundle(closed.raw, closed.index_raw, closed.files, originals, edge="seal", input_rows=state.inputs)
        ciphertext_raw, _cipher_close = _seal_ciphertext(state, closed)
        final, manifest = state.final[1], state.final[2]
        raw = O.encoded({"schema": 1, "scope": RD.SEAL_SCOPE, "edge": "SEAL", "kind": "worker",
            "selection": manifest["selection"], "source": manifest["source"], "github": manifest["github"],
            "policySha256": O.digest(state.policy_raw), "originalProposalSha256": O.digest(O.encoded(final["originalProposal"])),
            "originalJobBasisNs": final["history"]["originalJobBasisNs"], "clock": O.clock_value(state.clock.first.clock),
            "originalBootDigest": state.clock.boot, "sealFirstNs": state.clock.seal_first, "sealEndNs": state.clock.seal_end,
            "inputs": list(state.input_observations), "inputClose": RD.known_close(state.input_close.raw),
            "authority": RD.authority_close(closed.raw, edge="seal"), "authorityIndex": RD.authority_index(closed.index_raw, edge="seal"),
            "authorityCloseOriginals": {name: CD.canonical(blob) for name, blob in originals},
            "ciphertext": CD.canonical(ciphertext_raw), "closedNs": state.fence.now(), "writerReturn": CD.PENDING,
            "originalStepOutcome": "NOT_OBSERVED", "testAcceptance": "NOT_PERFORMED", "productiveAuthority": False,
            "cacheAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        RD.seal_record(raw, dict(state.final_raws))
        _row, _observation, _writer_close, writer_raw = _write_file(state, _receiver_root() / "seal", "seal-pending.json", raw)
        result = _track(_SealReturn(raw, writer_raw, ciphertext_raw))
        _register(state, result, authority=closed, close_originals=originals)
        clock = state.clock.first.clock
        outputs = RD.output_values(tuple(zip(RD.OUTPUT_FIELDS, (O.digest(raw), str(state.clock.seal_end), clock.role,
            clock.domain, str(clock.ticks_per_second), state.clock.boot))))
        value = {"schema": 1, "scope": RD.SEAL_OUTPUT_SCOPE, **dict(outputs),
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        output = _output_fence(result, value, outputs=outputs).append()
        entry.latch.complete(entry.table, entry.attempt, result)
        _registered(result, complete=True)
        return output
    except BaseException as error:
        raise _abort(entry.state, error) if type(entry.state) is _State else _fail(entry, error)


def productive_seal_authority_child(context_sha256, minimum_ns, caps, original_clock, original_boot_digest, cancelled):
    return _authority_child(context_sha256, minimum_ns, caps, original_clock, original_boot_digest, cancelled, edge="seal")


def productive_before_authority_child(context_sha256, minimum_ns, caps, original_clock, original_boot_digest, cancelled):
    return _authority_child(context_sha256, minimum_ns, caps, original_clock, original_boot_digest, cancelled, edge="before")


def _authority_child(context_hash, minimum, caps, original_clock, boot, cancelled, *, edge):
    """One fixed genuine eight-GET/native24 child; original helper45/final45 only."""
    entry = _begin(edge + "-child")
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    try:
        CD.sha(context_hash)
        CD.authority_caps(caps)
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token) and caps[3] <= CD.integer(minimum) < caps[4],
            "CHILD_PRIVATE_TOKEN_OR_MINIMUM")
        state = _new_state(entry, cancelled, caps=caps, declared_clock=original_clock, boot=boot, minimum=minimum)
        metadata, path = _file_owner(state), _authority_path(edge)
        private = C._private(metadata, path)
        service = C._private(metadata, path / "service")
        private_pin, service_pin = tuple(private.identity), tuple(service.identity)
        context_row, context_read = _read_native(metadata, private, "context.json", CD.LIMIT, "context.json")
        start_row, start_read = _read_native(metadata, service, "start.json", CD.LIMIT, "service/start.json")
        context_raw, start_raw = context_row[1], start_row[1]
        require(O.digest(context_raw) == context_hash, "CHILD_ACTUAL_CONTEXT_HASH")
        context, start, actual_caps = _start_data(context_raw, start_raw, state.clock.first.clock, state.clock.boot, edge)
        require(actual_caps == caps and start["argv"][0] == B.initial_command(context_hash)[0] and
            tuple(context["directoryIdentity"]) == private_pin, "CHILD_ORIGINAL_COMMAND_CAP_PIN")
        observed, _primary, event = N.host_context(context["observed"]["firstUseAt"])
        require(observed == context["observed"] and O.digest(event) == context["eventSha256"], "CHILD_ACTUAL_SOURCE")
        inherited = Q._inherited_context()
        require(inherited == start["inheritedContext"], "CHILD_INHERITED_DOMAIN")
        domain = B.processes.ownership_domains(inherited[B.processes.CHAIN_ENV], inherited[B.processes.DOMAINS_ENV])[-1]
        require(domain == {"id": start["invocation"], "job": context["job"], "state": str(path),
            "home": str(path / "control-home")}, "CHILD_ORIGINAL_OWNERSHIP")
        N.initial_identity._match(context["expectedMatch"])
        expected = N.acquisition.stages.BootstrapMatch(O.encoded(context["expectedMatch"]))
        expected_pin = C._custody_match_pin(expected, "worker")
        _update(state.clock, phase="AUTHORITY_CHILD", seal_first=context["authorityWindow"]["sealFirstNs"],
            seal_end=context["authorityWindow"]["sealEndNs"])
        _update(state, match_raw=expected.record, event_raw=event, event_path=os.environ.get("GITHUB_EVENT_PATH"),
            observed_raw=O.encoded(observed), graphs=(N._history_graph(context, start, inherited, expected),))
        metadata_reads = []
        for directory, name, initial, first_read, relative, identity in (
                (private, "context.json", context_row, context_read, "context.json", private_pin),
                (service, "start.json", start_row, start_read, "service/start.json", service_pin)):
            row, reread = _read_native(metadata, directory, name, CD.LIMIT, relative,
                expected=(len(initial[1]), O.digest(initial[1])), native=initial[3])
            require(row[1] == initial[1], "CHILD_METADATA_ORIGINAL_READBACK")
            _child_metadata_readback(first_read, reread, initial[1], relative, identity)
            metadata_reads.append({"name": name, "first": first_read, "readback": reread})
        metadata_close = _close_owner(metadata)
        metadata_last = state.fence.now()
        _update(state, input_close=metadata_close, graphs=(*state.graphs, N._history_graph(tuple(metadata_reads))))
        seed = _native_seed(state, edge + "-child")
        owner = _ReceiverNativeOwner(seed)
        private = owner.open(path)
        service = owner.child(private, "service")
        require(tuple(private.identity) == private_pin and tuple(service.identity) == service_pin and
            owner.read(private, "context.json") == context_raw and owner.read(service, "start.json") == start_raw,
            "CHILD_REAL_METADATA_REOPEN")
        supplier = None
        failure = None
        try:
            supplier = N.query_owner(owner, state.fence, path / "acquisition-queries")
            N._initial_service_query_git(supplier)
            supplier.native_host_matches_actions()
            def retain(name, raw, *, failed):
                require(name in N.ORIGINAL_KEYS and type(raw) is bytes and type(failed) is bool, "CHILD_FIXED_ORIGINAL")
                owner.end(final=failed)
                supplier._write(supplier.private, name + ".bin", raw)
                owner.end(final=failed)
            match, originals = N.acquisition.acquire_bootstrap(ROOT, kind="worker", query_runner=supplier,
                invocation=domain["id"], token=token, retain=retain, fence=state.fence, original_work_end=caps[4],
                first_use_at=context["observed"]["firstUseAt"], expected=expected)
            token = None
            acquired = state.fence.now()
            require(type(match) is type(expected) and match.record == expected.record and type(originals) is tuple and
                tuple(name for name, _raw in originals) == N.ORIGINAL_KEYS and all(type(raw) is bytes for _name, raw in originals) and
                dict(originals)["event"] == event, "CHILD_REAL_MATCH_ORIGINALS")
            match_pin = C._custody_match_pin(match, "worker")
            identity = N.initial_identity.bind_worker_match(match, event_raw=event,
                policy_raw=dict(originals)["candidate_policy_raw"], now=int(time.time()))
            RD.original_proposal(context["originalProposal"], context["history"], CD.canonical(identity.record, CD.PUBLIC_LIMIT))
            _update(state, policy_raw=dict(originals)["candidate_policy_raw"],
                identity=identity, graphs=(*state.graphs, N._history_graph(originals, match, identity)))
            _current(state)
        except BaseException as error:
            failure = error
        finally:
            token = None
            C._custody_finish_queries(owner, supplier, failure)
        returned = state.fence.now()
        queries = owner.open(path / "acquisition-queries")
        session = N.query_session(owner, queries)
        require(all(owner.read(queries, name + ".bin") == raw for name, raw in originals), "CHILD_ORIGINAL_QUERY_READBACK")
        C._collect_query_index(path / "acquisition-queries", session, dict(originals), context["observed"])
        steps = _service_steps(context_raw, originals, domain["id"], state.clock.first.clock, edge)
        _current(state)
        C._custody_match_check(expected_pin)
        C._custody_match_check(match_pin)
        terminal_raw = owner.write(service, "child-result.json", {"schema": 1,
            "scope": RD.SEAL_CHILD_SCOPE if edge == "seal" else RD.BEFORE_CHILD_SCOPE,
            "contextSha256": context_hash, "startSha256": O.digest(start_raw), "invocation": domain["id"],
            "clock": O.clock_value(state.clock.first.clock), "bootDigest": state.clock.boot, "launchMinimumNs": minimum,
            "authorityWindowSha256": O.digest(O.encoded(context["authorityWindow"])), "beganNs": state.clock.first.nanoseconds,
            "metadataLastNs": metadata_last, "acquiredNs": acquired, "queryReturnedNs": returned,
            "querySessionSha256": O.digest(session), "originalsSha256": {name: O.digest(raw) for name, raw in originals},
            "matchSha256": O.digest(match.record), "directoryIdentities": {".": list(private_pin), "service": list(service_pin)},
            "serviceSteps": steps, "metadataReads": metadata_reads, "metadataClose": RD.known_close(metadata_close.raw),
            "completedNs": state.fence.now(), "retirement": "PENDING_CHILD_CLOSE", "errors": []})
        _close_owner(owner)
        closed = state.fence.now()
        result = _track(_ChildReturn(terminal_raw, domain["id"]))
        _register(state, result, match_pins=(expected_pin, match_pin))
        entry.latch.complete(entry.table, entry.attempt, result)
        value = {"schema": 1, "scope": RD.SEAL_ACK_SCOPE if edge == "seal" else RD.BEFORE_ACK_SCOPE,
            "invocation": domain["id"], "terminalSha256": O.digest(terminal_raw),
            "clock": O.clock_value(state.clock.first.clock), "closedNs": closed}
        fence = _output_fence(result, value, child=True)
        return value, fence, caps[4]
    except BaseException as error:
        raise _abort(entry.state, error) if type(entry.state) is _State else _fail(entry, error)
    finally:
        token = None
