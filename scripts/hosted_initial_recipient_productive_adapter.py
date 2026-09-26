"""Fixed initial productive9/Step8 original-call adapter; no workflow activation.

Only this module's registered calls own phases. Supplied DATA, a constructed
parent, or an old close record cannot create or renew a call. Initial source
identity never becomes ordinary Admission. Native/file engines remain the
maintained suppliers; the original proposal is still unadmitted/unmeasured.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
import hashlib
import math
import os
from pathlib import Path
import time
import uuid

import hosted_initial_recipient_productive as P
import hosted_initial_recipient_productive_data as D
import hosted_cache_bootstrap_staging as staging
import hosted_cache_bootstrap_custody as custody
import hosted_cache_bootstrap_producer as producer
import hosted_cache_bootstrap_producer_command as producer_command
import hosted_cache_bootstrap_collect_files as collection
import hosted_cache_bootstrap_no_loader as no_loader
import hosted_cache_bootstrap_export as dependency_export
import hosted_cache_bootstrap_save_set as save_set


C, N, B, O, U = P.C, P.N, P.B, P.O, P.U
F, ROOT, NS = staging.files, P.ROOT, O.NS
_RUNS, _PARENTS, _WINDOWS, _OWNERS, _RETURNS = {}, {}, {}, {}, {}
_HANDOFFS, _READERS, _INPUTS = {}, {}, {}
_DERIVES = {}
_OUTPUTS = {}
_PINS, _RUN_LATCHES, _FAILURES, _CHILD_RETURNS, _OWNER_RETURNS = {}, {}, {}, {}, {}
_LEAF_RETURNS = {}
_OPERATIONS = ("produce", "prepare-save", "after-save", "prepare-probe", "after-probe")
_STEPS = {"prepare-save": "save-transition", "after-save": "save-readmission",
          "prepare-probe": "probe-transition", "after-probe": "custody-readmission"}
_PHASES = {
    "dependency-stage": (("dependency-stage", 120, 120),),
    "empty-seed": (("empty-seed", 120, 90),),
    "custody-prepare": (("custody-prepare", 120, 120),),
    "configuration": (("producer-work", 600, 600), ("producer-return", 225, 0),
                      ("producer-final", 45, 0), ("producer-read", 30, 30)),
    "custody-collect": (("custody-collect", 120, 120), ("custody-collect-final", 45, 0),
                        ("custody-collect-read", 30, 0)),
    "custody-uninstall": (("custody-uninstall", 90, 90), ("custody-uninstall-final", 45, 0),
                          ("custody-uninstall-read", 30, 0)),
    "dependency-export": (("dependency-export", 120, 90),),
    "save-set-before": (("save-set-before", 120, 90),),
    "producer-owner-return": (("producer-owner-return", 45, 45),),
    **{name: ((name, seconds, seconds),) for name, seconds in
       (("save-transition", 30), ("save-readmission", 120), ("save-observation", 30),
        ("save-owner-return", 45), ("probe-transition", 30), ("custody-readmission", 120),
        ("provider-observation", 30))},
    "save-set-after": (("save-set-after", 120, 90),),
}
_PRODUCTIVE_PHASES = tuple(_PHASES)[:9]
_SEQUENCES = {"produce": _PRODUCTIVE_PHASES, "prepare-save": ("save-transition",),
    "after-save": ("save-readmission", "save-set-after", "save-observation", "save-owner-return"),
    "prepare-probe": ("probe-transition",), "after-probe": ("custody-readmission", "provider-observation")}
_BASE_CLAIMS = ("PRODUCER_OUTCOME", "HANDOFF_SHA256", "PRODUCER_RETURN_SHA256")
_SAVE_CLAIMS = (*_BASE_CLAIMS, "SAVE_PREPARE_OUTCOME", "SAVE_PREPARATION_SHA256",
                "SAVE_OUTCOME", "SAVE_READBACK_SHA256")
_PROBE_CLAIMS = (*_SAVE_CLAIMS, "AFTER_SAVE_OUTCOME", "AFTER_SAVE_SHA256")
_AFTER_PROBE_CLAIMS = (*_PROBE_CLAIMS, "PROBE_PREPARE_OUTCOME", "PROBE_PREPARATION_SHA256",
                       "PROBE_OUTCOME", "PROBE_READBACK_SHA256")
_OUTPUT_NAMES = (("cache-primary-key", "PRIMARY_KEY"), ("cache-matched-key", "MATCHED_KEY"), ("cache-hit", "HIT"))


def require(value, reason):
    O.require(value, "INITIAL_ADAPTER_" + reason)


@dataclass(frozen=True, repr=False)
class _Parent:
    """Empty handle. Only the private original registry grants a live site."""


@dataclass(eq=False, repr=False)
class _Run:
    operation: str
    entry: object
    attempts: dict
    attempt: dict
    cancelled: object
    claims: dict
    outputs: dict
    prefix: object
    graph: tuple
    history: object = None
    current: object = None
    phases: tuple = ()
    failure: object = None
    terminal: object = None
    originals: object = None
    initial_files: tuple = ()
    starting: bool = False


@dataclass(eq=False, repr=False)
class _ParentState:
    parent: object
    run: object
    name: str
    first: object
    local: float
    boot: str
    proposal: object
    predecessor: object
    first_graph: tuple
    ends: tuple
    local_ends: tuple
    window: object
    graph: tuple = ()
    phase: int = 0
    starts: tuple = ()
    last: int = 0
    last_reading: object = None
    local_last: float = 0.0
    issued: float = 0.0
    failure: object = None
    sampling: bool = False
    advancing: bool = False
    owner: object = None
    owner_starting: bool = False
    owners: tuple = ()
    site: object = None
    binding: object = None
    use_graph: tuple = ()
    uses: tuple = ()
    returned: object = None
    inputs: object = None
    files: tuple = ()
    native: object = None


def _fail(run, error):
    anchor = _RUN_LATCHES.get(id(run))
    require(type(anchor) is tuple and anchor[0] is run, "ORIGINAL_RUN_LATCH_REQUIRED")
    key = id(run)
    if key not in _FAILURES:
        _FAILURES[key] = anchor[1].fail(error)
    first = _FAILURES[key]
    _poison(run, "failure", first)
    return first


def _data_pins(*roots):
    """Closed DATA records only, including their ORIGINAL dictionary objects.

    N's historical graph deliberately treats this adapter's new records as
    opaque. Passing only their dictionaries would not detect replacing a
    record's entire __dict__. These finite pins carry no call authority and
    never traverse live parent/owner/native internals.
    """
    kinds = (_Return, _PrefixFloor, PendingHandoff, ProductiveHandoff, _StepReturn, _StepMetadata,
        HandoffInputs, ProviderInputs, _Configuration, D.InitialOriginals, D.InitialInputs, custody._InitialInputs,
        custody.StagedEvidence, staging.PhaseStart, staging.LeafEvidence, custody.ReservationEvidence,
        collection.FileCollectionEvidence, no_loader.AbsenceEvidence, dependency_export.ExportEvidence,
        save_set.SaveSetEvidence)
    pending, seen, records = list(roots), set(), []
    while pending:
        value = pending.pop()
        if type(value) not in (*kinds, dict, tuple, list) or id(value) in seen:
            continue
        seen.add(id(value))
        require(len(seen) <= 10000, "DATA_PIN_LIMIT")
        if type(value) in kinds:
            dictionary = value.__dict__
            records.append((value, dictionary, tuple(dictionary.items())))
            pending.append(dictionary)
        elif type(value) is dict:
            pending.extend(value.values())
        else:
            pending.extend(value)
    return tuple(records), N._history_graph(*(value for value, _dictionary, _items in records),
        *(dictionary for _value, dictionary, _items in records))


def _check_data_pins(saved):
    records, graph = saved
    for value, dictionary, items in records:
        require(value.__dict__ is dictionary and tuple(dictionary) == tuple(name for name, _old in items) and
            all(dictionary[name] is old for name, old in items), "ORIGINAL_DATA_RECORD_CHANGED")
    N._check_history(graph)


def _pin_parts(value):
    """Nested mutable DATA only; do not snapshot live native owner internals."""
    mappings, records, graph, roots = (), (), (), ()
    if type(value) is _ReadState:
        mappings = (tuple(value.files.items()), tuple(value.directories.items()))
        graph = N._history_graph(value.first, value.claims,
            tuple((path, name, raw, stamp, maximum) for (path, name), (raw, stamp, maximum) in value.files.items()),
            tuple((path, directory, kind, pin, label) for path, (directory, kind, pin, _row, label)
                  in value.directories.items()), value.large)
        roots = (value.handoff,)
    elif type(value) is _OwnerState:
        records = value.resources
    elif type(value) is _Native:
        records = value.captures
        graph = N._history_graph(value.handles, value.directory_identity, value.environment)
    elif type(value) is _ParentState:
        roots = value.predecessor, value.inputs, value.returned
        graph = N._history_graph(value.last_reading)
    elif type(value) is _HandoffState:
        roots = value.pending, value.result
    elif type(value) is _Run:
        roots = value.prefix, value.originals, value.terminal
    pins = tuple((row, row.__dict__, tuple(row.__dict__.items())) for row in records)
    data, data_graph = _data_pins(*roots)
    # Resource/capture dictionaries are checked directly above; their actual
    # record TYPES must also stay original, including after __class__ edits.
    return mappings, (*pins, *data), (*graph, *N._history_graph(*records), *data_graph)


def _track(value):
    require(type(value) in (_Run, _ParentState, _OwnerState, _Native, _HandoffState, _ReadState) and
            id(value) not in _PINS, "STATE_NOT_NEW")
    _PINS[id(value)] = value, value.__dict__, tuple(value.__dict__.items()), _pin_parts(value)
    return value


def _pin(value):
    saved = _PINS.get(id(value))
    require(type(value) in (_Run, _ParentState, _OwnerState, _Native, _HandoffState, _ReadState) and
        type(saved) is tuple and saved[0] is value and value.__dict__ is saved[1] and
        tuple(value.__dict__) == tuple(name for name, _old in saved[2]) and
        all(value.__dict__[name] is old for name, old in saved[2]), "ORIGINAL_STATE_CHANGED")
    mappings, records, graph = saved[3]
    if mappings:
        for current, items in zip((value.files, value.directories), mappings):
            require(tuple(current) == tuple(key for key, _old in items) and
                all(current[key] is old for key, old in items), "ORIGINAL_READ_MAP_CHANGED")
    for row, dictionary, items in records:
        require(row.__dict__ is dictionary and tuple(dictionary) == tuple(name for name, _old in items) and
            all(dictionary[name] is old for name, old in items), "ORIGINAL_RESOURCE_OR_CAPTURE_CHANGED")
    N._check_history(graph)
    # Progress may replace a graph only AFTER the old nested originals pass.
    # Pointer equality alone would silently bless an in-place callback edit.
    for name in ("graph", "first_graph", "use_graph", "completed_graph"):
        if name in value.__dict__:
            N._check_history(value.__dict__[name])
    return value


def _progress(value, **updates):
    """Fixed source-owned progress, checked before any previous pins are replaced."""
    _pin(value)
    allowed = {
        _Run: "prefix graph history current phases failure terminal originals initial_files starting",
        _ParentState: "proposal graph ends local_ends phase starts last last_reading local_last issued failure sampling advancing "
                      "owner owner_starting owners site binding use_graph uses returned inputs files native",
        _OwnerState: "resources returned original unknown closed acquiring",
        _Native: "scope_attempted launch_attempted child child_kind child_pid preparer baseline birth leader terminal "
                 "exit_code completed work_accepted retired drain_attempted cancellation_attempted cancellation_raw captures finalized",
        _HandoffState: "complete_attempted result completed_graph return_raw",
        _ReadState: "directories files large handoff graph failure",
    }
    require(updates and set(updates).issubset(allowed[type(value)].split()), "FIXED_PROGRESS_FIELDS")
    value.__dict__.update(updates)
    _PINS[id(value)] = value, value.__dict__, tuple(value.__dict__.items()), _pin_parts(value)
    return value


def _original(value, name):
    saved = _PINS.get(id(value))
    require(type(saved) is tuple and saved[0] is value, "ORIGINAL_STATE_REQUIRED")
    return dict(saved[2])[name]


def _poison(value, name, failure):
    """Keep first failure without adopting other fields changed by a callback."""
    saved = _PINS.get(id(value))
    require(type(saved) is tuple and saved[0] is value and name == "failure", "FAILURE_SLOT")
    value.__dict__[name] = failure
    items = tuple((key, failure if key == name else old) for key, old in saved[2])
    _PINS[id(value)] = value, saved[1], items, saved[3]


def _state(parent):
    saved = _PARENTS.get(id(parent))
    require(type(saved) is _ParentState, "NOT_ORIGINAL_PARENT")
    try:
        _pin(saved)
        require(type(parent) is _Parent and saved.parent is parent, "NOT_ORIGINAL_PARENT")
        _pin(saved.run)
        return saved
    except BaseException as error:
        raise _fail(_original(saved, "run"), error)


def _run_claims(operation):
    names = {"produce": (), "prepare-save": _BASE_CLAIMS, "after-save": _SAVE_CLAIMS,
             "prepare-probe": _PROBE_CLAIMS, "after-probe": _AFTER_PROBE_CLAIMS}[operation]
    return {name: os.environ.get("P2PKIT_BOOTSTRAP_" + name) for name in names}


def _environment(run):
    P._credential_free()
    require(P.C is C and C.N is N and N.native is B and C.native is B and P.ROOT == D.ROOT == staging.ROOT == ROOT,
            "CANONICAL_MODULE_GRAPH")
    require(not B.QUARANTINE and not B.query.QUARANTINE and not B.diagnostics._QUARANTINE, "PRIOR_UNKNOWN")
    require(_run_claims(run.operation) == run.claims, "ORIGINAL_CLAIMS_CHANGED")
    for name, value in run.claims.items():
        require(value == "success" if name.endswith("OUTCOME") else
                type(value) is str and producer.re.fullmatch(r"[0-9a-f]{64}", value), "ORIGINAL_STEP_CLAIMS")
    if run.operation == "after-probe":
        require(run.outputs == {name: os.environ.get("P2PKIT_BOOTSTRAP_PROBE_" + suffix)
            for name, suffix in _OUTPUT_NAMES} and all(type(value) is str and len(value) <= 512 and
            all(32 <= ord(char) < 127 for char in value) for value in run.outputs.values()), "ORIGINAL_LOOKUP_OUTPUTS")
    if run.history is not None:
        observed, path, event = N.host_context(run.history["firstUseAt"])
        require(observed == run.history["observed"] and observed["kind"] == "worker" and
                path == N.location()[1] and event == run.prefix.identity.original_event, "ORIGINAL_HOST_CHANGED")
        B.child_environment(N._receiving_path())  # Fixed ambient refusal, no launch.


def _current(state, *, cleanup=False):
    run = state.run
    require(_state(state.parent) is state and _RUNS.get(run.operation) is run, "ORIGINAL_REGISTRATION_CHANGED")
    N._check_history(state.first_graph)
    N._check_history(state.graph)
    N._check_history(run.graph)
    if state.native is not None:
        require(type(state.native) is _Native, "ORIGINAL_NATIVE_STATE")
        _pin(state.native)
    if cleanup:
        return state  # No failed/retired parent's current callback in cleanup.
    if run.failure is not None:
        raise run.failure
    if state.failure is not None:
        raise state.failure
    if run.terminal is None:
        run.entry.check(run.attempts, run.attempt)
    else:
        run.entry.returned(run.attempts, run.attempt, run.terminal)
    require(run.current is state and state.returned is None, "PHASE_NO_LONGER_CURRENT")
    _environment(run)
    if run.operation == "produce":
        require(C.checked_retired_primary(run.prefix) is run.prefix, "RETIRED_PREFIX_CHANGED")
    elif run.prefix is not None:
        # Passive only. Full file reads are explicit seams, never a callback's
        # recursive reread of its own owner or of an expired old window.
        _checked_handoff(run.prefix)
    for old in run.phases:
        _closed_return(old)
    for use in state.uses:
        P.checked_consumed_use(use, state.parent, use.site)
    if state.owner is not None:
        _owner_state(state.owner, allow_closed=True)
    require(N.continuity.boot_digest(state.first.clock.role) == state.boot, "ORIGINAL_BOOT_CHANGED")
    run.cancelled()
    _environment(run)
    N._check_history(state.first_graph)
    N._check_history(state.graph)
    if run.failure is not None:
        raise run.failure
    return state


class _Window:
    __slots__ = ()

    def _state(self):
        saved = _WINDOWS.get(id(self))
        require(type(saved) is _ParentState, "NOT_ORIGINAL_WINDOW")
        try:
            state = _state(_original(saved, "parent"))
            require(type(self) is _Window and state.window is self, "NOT_ORIGINAL_WINDOW")
            return state
        except BaseException as error:
            raise _fail(_original(saved, "run"), error)

    @property
    def clock(self):
        return self._state().first.clock

    @property
    def hard_end(self):
        state = self._state()
        return state.starts[state.phase][2]

    def _sample(self, state, minimum, limit, *, new):
        before = D.local(time.monotonic())
        require(before >= state.local_last, "LOCAL_BACKWARDS")
        _progress(state, local_last=before)
        actual = O.clocks.validate_reading(O.clocks.observe())
        require(actual.clock == state.first.clock and actual.nanoseconds >= max(state.last, O.integer(minimum)),
                "RAW_CLOCK_CHANGED_OR_BACKWARDS")
        _progress(state, last=actual.nanoseconds, last_reading=actual)
        after = D.local(time.monotonic())
        require(after >= state.local_last, "LOCAL_BACKWARDS")
        _progress(state, local_last=after)
        started, local, end, local_end = state.starts[state.phase]
        seconds, soft_seconds = _PHASES[state.name][state.phase][1:]
        cap = end if limit is None else min(end, O.integer(limit))
        if new:
            require(soft_seconds > 0, "NO_NEW_WORK_IN_CLEANUP")
            cap = min(cap, O.integer(started + soft_seconds * NS))
            local_end = min(local_end, O.wire._directed_deadline(local, soft_seconds, cap, started))
        # A new-work observation may DENY at SOFT without shortening the
        # already admitted candidate's unchanged HARD close/readback interval.
        _progress(state, issued=min(state.issued, state.starts[state.phase][3],
            O.wire._directed_deadline(before, seconds, end, state.last)))
        require(state.last < cap and state.local_last < min(state.issued, local_end), "ORIGINAL_PHASE_EXPIRED")
        return state.last

    def now(self, *, final=False, minimum=0, limit=None, new=False):
        state = self._state()
        entered = False
        try:
            require(type(final) is bool and type(new) is bool and not state.sampling, "CLOCK_REENTRY")
            _progress(state, sampling=True)
            entered = True
            _current(state, cleanup=final)
            self._sample(state, minimum, limit, new=new)
            _current(state, cleanup=final)
            result = self._sample(state, minimum, limit, new=new)
            N._check_history(state.first_graph)
            return result
        except BaseException as error:
            first = _fail(_original(state, "run"), error)
            if _original(state, "failure") is None:
                _poison(state, "failure", first)
            raise first
        finally:
            if entered:
                try:
                    _progress(state, sampling=False)
                except BaseException as error:
                    raise _fail(_original(state, "run"), error)

    def deadline(self, maximum, *, final=False, limit=None):
        require(type(maximum) in (int, float) and math.isfinite(maximum) and 0 < maximum <= 900,
                "DEADLINE_MAXIMUM")
        self.now(final=final, limit=limit)
        state = self._state()
        return min(state.issued, state.local_last + maximum)

    def advance(self):
        state = self._state()
        entered = False
        try:
            require(not state.advancing and not state.sampling and state.phase + 1 < len(_PHASES[state.name]),
                    "PHASE_REENTRY")
            _progress(state, advancing=True)
            entered = True
            previous = state.starts[state.phase]
            _progress(state, phase=state.phase + 1, starts=(*state.starts, (None, None, 0, 0.0)), issued=0.0)
            _current(state, cleanup=True)
            require(previous[0] is not None and previous[2] > 0, "PRIOR_PHASE_START_FAILED")
            local = D.local(time.monotonic())
            require(local >= state.local_last, "LOCAL_BACKWARDS")
            _progress(state, local_last=local)
            actual = O.clocks.validate_reading(O.clocks.observe())
            require(actual.clock == state.first.clock and actual.nanoseconds >= state.last, "PHASE_RAW_BACKWARDS")
            _progress(state, last=actual.nanoseconds, last_reading=actual)
            seconds = _PHASES[state.name][state.phase][1]
            end = min(state.ends[state.phase], O.integer(state.last + seconds * NS))
            local_end = min(state.local_ends[state.phase], O.wire._directed_deadline(local, seconds, end, state.last))
            # READ starts only after actual final close, before the original FINAL
            # expires; its different cap cannot accept a failed final boundary.
            if state.phase == len(_PHASES[state.name]) - 1:
                require(state.last < previous[2] and local < previous[3], "READ_START_AFTER_FINAL")
            _progress(state, starts=(*state.starts[:-1], (state.last, local, end, local_end)), issued=local_end)
            self.now(final=True)
        except BaseException as error:
            first = _fail(_original(state, "run"), error)
            if entered:
                try:
                    _progress(state, starts=(*state.starts[:-1], (state.last, state.local_last, 0, 0.0)), issued=0.0)
                except BaseException:
                    pass  # Original failure is irreversible; never adopt changed fields.
            raise first
        finally:
            if entered:
                try:
                    _progress(state, advancing=False)
                except BaseException as error:
                    raise _fail(_original(state, "run"), error)

    def record(self):
        state = self._state()
        return {"phase": state.name, "clock": O.clock_value(state.first.clock), "originalBootDigest": state.boot,
            "firstNs": state.first.nanoseconds, "localStarted": state.local,
            "globalEndsNs": list(state.ends), "phases": [
                {"name": row[0], "startedNs": start, "localStarted": local, "endNs": end}
                for row, (start, local, end, _local_end) in zip(_PHASES[state.name], state.starts)],
            "budgetAcceptance": "NOT_ADMITTED"}


@dataclass(frozen=True, repr=False)
class _Resource:
    row: dict
    label: str
    value: object
    kind: type
    close_method: object
    attempted: bool = False
    closed: bool = False


@dataclass(eq=False, repr=False)
class _OwnerState:
    owner: object
    phase: object
    binding: tuple
    resources: tuple = ()
    returned: tuple = ()
    original: object = None
    unknown: bool = False
    closed: bool = False
    acquiring: bool = False


def _owner_state(owner, *, allow_closed=False):
    saved = _OWNERS.get(id(owner))
    require(type(owner) is _Owner and type(saved) is _OwnerState and saved.owner is owner,
            "NOT_ORIGINAL_FILE_OWNER")
    _pin(saved)
    dictionary, ledger, errors, first, window, callback, end = saved.binding
    require(set(dictionary) == {"local_end", "fence", "work_limit", "final_limit", "first", "early_last", "cancelled",
        "resources", "errors", "original", "unknown", "closed", "phase_originals", "admissions", "entry_original",
        "entry_close_attempted", "entry_close_original", "entry_close_snapshot"} and
        owner.__dict__ is dictionary and owner.resources is ledger and owner.errors is errors and
        owner.first is first and owner.fence is window and owner.cancelled is callback and owner.local_end == end and
        owner.early_last == first.nanoseconds and type(owner.early_last) is int and
        owner.work_limit is owner.final_limit is None and owner.original is saved.original and
        owner.unknown is saved.unknown and owner.closed is saved.closed and
        owner.phase_originals is None and owner.admissions == {} and owner.entry_original is None and
        owner.entry_close_attempted is False and owner.entry_close_original is owner.entry_close_snapshot is None,
        "FILE_OWNER_BINDING_CHANGED")
    require(_OWNER_RETURNS.get(id(owner)) is saved.returned and len(saved.returned) == len(saved.resources) and
        all(label == pin.label and value is pin.value
        for (label, value), pin in zip(saved.returned, saved.resources)), "FILE_RETURN_REFERENCE_ROSTER")
    require(len(ledger) == len(saved.resources) and all(row is pin.row and set(row) ==
        {"label", "owner", "attempted", "closed"} and row["label"] == pin.label and row["owner"] is pin.value and
        type(pin.value) is pin.kind and row["attempted"] is pin.attempted and row["closed"] is pin.closed and
        getattr(pin.kind, "close") is pin.close_method for row, pin in zip(ledger, saved.resources)), "FILE_OWNER_ROSTER_CHANGED")
    require(allow_closed or not saved.closed, "FILE_OWNER_CLOSED")
    return saved


class _Owner(B.Owner):
    """Maintained file backends, independently retained actual-return ledger."""
    def end(self, *, final=False):
        try:
            saved = _owner_state(self)
            require(final is False and not saved.unknown and saved.original is None, "NO_FAILED_OR_FINAL_ACQUISITION")
            require(_PHASES[saved.phase.name][saved.phase.phase][2] > 0, "NO_CLEANUP_ACQUISITION")
            return saved.phase.window.deadline(900)
        except BaseException as error:
            self.error("file-end", error)
            raise _original(_OWNERS[id(self)], "original")

    def _work_mode(self, final):
        try:
            require(final is False, "NO_FINAL_FILE_OPERATION")
        except BaseException as error:
            self.error("file-mode", error)
            raise _original(_OWNERS[id(self)], "original")

    def error(self, stage, error, *, unknown=False):
        saved = _OWNERS[id(self)]
        phase = _original(saved, "phase")
        first = _fail(_original(phase, "run"), error)
        original = _original(saved, "original")
        if original is None:
            original = first
        uncertain = _original(saved, "unknown") or unknown is not False

        def retain_failure():
            # Failure reporting never blesses any other mutated field/pin.
            pin = _PINS[id(saved)]
            saved.__dict__.update(original=original, unknown=uncertain)
            items = tuple((name, original if name == "original" else uncertain if name == "unknown" else old)
                          for name, old in pin[2])
            _PINS[id(saved)] = saved, pin[1], items, pin[3]
            self.original, self.unknown = original, uncertain

        retain_failure()
        try:
            detail = B.diagnostics._exception_detail(error)
            uncertain |= detail["retirementUnknown"]
            errors = _original(saved, "binding")[2]
            if len(errors) < 64:
                errors.append({"stage": stage, "detail": detail})
            else:
                uncertain = True
        except BaseException:
            uncertain = True
        retain_failure()

    def _retain(self, label, value):
        saved = _OWNERS[id(self)]
        require(not any(old is value for _label, old in _OWNER_RETURNS[id(self)]), "DUPLICATE_RESOURCE")
        # Retain the raw actual return before even looking up its close method.
        returned = (*_OWNER_RETURNS[id(self)], (label, value))
        _OWNER_RETURNS[id(self)] = returned
        _progress(saved, returned=returned)
        row = {"label": label, "owner": value, "attempted": False, "closed": False}
        pin = _Resource(row, label, value, type(value), getattr(type(value), "close"))
        _progress(saved, resources=(*saved.resources, pin))
        saved.binding[1].append(row)
        return value

    def acquire(self, label, factory, *, final=False):
        saved = _OWNERS[id(self)]
        entered = False
        try:
            _owner_state(self)
            require(final is False and not saved.acquiring, "FILE_ACQUISITION_REENTRY")
            self.end()
            saved.phase.window.now(new=True)
            _progress(saved, acquiring=True)
            entered = True
            try:
                value = factory()
            except BaseException as error:
                self.error(label + "-allocation", error, unknown=True)
                raise
            try:
                self._retain(label, value)
            except BaseException as error:
                self.error(label + "-return-registration", error, unknown=True)
                raise
            self.end()
            return value
        except BaseException as error:
            self.error(label + "-acquisition", error)
            raise self.original
        finally:
            if entered:
                try:
                    _progress(saved, acquiring=False)
                except BaseException as error:
                    self.error(label + "-acquisition-return", error, unknown=True)

    def new(self, path):
        return self.acquire("directory", lambda: F.private_root(path, create=True))

    def open(self, path, *, final=False):
        self._work_mode(final)
        return self.acquire("directory", lambda: F.private_root(path))

    def child(self, parent, name, *, create=False, final=False):
        self._work_mode(final)
        end = self.end()
        return self.acquire("directory", lambda: (parent.create_directory if create else parent.open_directory)(name, deadline=end))

    def read(self, parent, name, maximum=D.LIMIT, *, final=False):
        self._work_mode(final)
        return staging._read(_Reader(self), parent, name, maximum=maximum)[0]

    def close_fence(self):
        saved = _OWNERS[id(self)]
        try:
            saved.phase.window.now(final=True)
        except BaseException as error:
            self.error("file-close-fence", error)

    def close_one(self, value):
        saved = _OWNERS[id(self)]
        pin = next((pin for pin in saved.resources if pin.value is value), None)
        if pin is None:
            self.error("foreign-close", O.OriginError("INITIAL_ADAPTER_FOREIGN_RESOURCE"), unknown=True)
            return
        if pin.attempted:
            return
        try:
            _owner_state(self, allow_closed=True)
            require(not saved.unknown, "FILE_CLOSE_UNKNOWN")
        except BaseException as error:
            self.error("file-close-binding", error, unknown=True)
            return
        self._close_pin(pin)

    def _close_pin(self, pin):
        saved = _OWNERS[id(self)]
        if next(row for row in saved.resources if row.value is pin.value).attempted:
            return
        self.close_fence()
        _progress(saved, resources=tuple(replace(row, attempted=True) if row.value is pin.value else row for row in saved.resources))
        pin.row["attempted"] = True
        try:
            # Use only the actual returned resource's original method, once.
            require(type(pin.value) is pin.kind and getattr(pin.kind, "close") is pin.close_method, "CLOSE_RESOURCE_CHANGED")
            pin.close_method(pin.value)
            _progress(saved, resources=tuple(replace(row, closed=True) if row.value is pin.value else row for row in saved.resources))
            pin.row["closed"] = True
        except BaseException as error:
            self.error(pin.label + "-close", error, unknown=True)
        self.close_fence()

    def close(self):
        saved = _OWNERS[id(self)]
        if _original(saved, "closed"):
            return
        try:
            _owner_state(self)
        except BaseException as error:
            self.error("file-owner-close-binding", error, unknown=True)
        try:
            _progress(saved, closed=True)
            self.closed = True
            self.close_fence()
            for pin in reversed(_original(saved, "resources")):
                if _original(saved, "unknown"):
                    break
                self.close_one(pin.value)
            self.close_fence()
        except BaseException as error:
            self.error("file-owner-close", error, unknown=True)
        if _original(saved, "unknown"):
            if not any(value is self for value in B.QUARANTINE):
                B.QUARANTINE.append(self)
            raise _original(saved, "original")


class _Reader:
    """Small bound-file engine adapter; this is NOT owner/phase authority."""
    def __init__(self, owner):
        self.owner = owner

    def end(self, *, new=False):
        if new and type(self.owner) is _Owner:
            _owner_state(self.owner).phase.window.now(new=True)
        return self.owner.end()

    def check(self, *, new=False):
        self.end(new=new)

    def acquire(self, label, factory):
        return self.owner.acquire(label, factory)

    def error(self, stage, error, *, unknown=False):
        self.owner.error(stage, error, unknown=unknown)

    def close_one(self, value):
        self.owner.close_one(value)
        if self.owner.original is not None:
            raise self.owner.original
        require(not self.owner.unknown, "BOUND_READER_CLOSE_UNKNOWN")


def _new_owner(state):
    owner = None
    try:
        require(_state(state.parent) is state and not state.owner_starting and
            (state.owner is None or _owner_state(state.owner, allow_closed=True).closed), "PREVIOUS_OWNER_STILL_LIVE")
        _progress(state, owner_starting=True)
        state.window.now()
        end = state.local_ends[-1]  # Original whole span; each operation still uses its current phase.
        owner = _Owner(end, state.window, first=state.first, cancelled=state.run.cancelled)
        saved = _track(_OwnerState(owner, state, (owner.__dict__, owner.resources, owner.errors, owner.first,
            owner.fence, owner.cancelled, owner.local_end)))
        _OWNERS[id(owner)] = saved
        _OWNER_RETURNS[id(owner)] = saved.returned
        _progress(state, owner=owner, owners=(*state.owners, owner), owner_starting=False)
        owner.end()
        return owner
    except BaseException as error:
        first = _fail(_original(state, "run"), error)
        if owner is not None:
            try:
                first.initial_returned_file_owner = owner
            except BaseException:
                pass
        raise first


def _known(owner):
    saved = _owner_state(owner, allow_closed=True)
    if saved.original is not None:
        raise saved.original
    require(saved.closed and not saved.unknown and not saved.binding[2] and
            all(pin.attempted and pin.closed for pin in saved.resources), "ORIGINAL_CLOSE_NOT_KNOWN")
    return saved


def _new_run(operation, cancelled, prefix=None):
    require(operation in _OPERATIONS and callable(cancelled), "FIXED_OPERATION")
    previous = _RUNS.get(operation)
    if previous is not None:
        anchor = _RUN_LATCHES[id(previous)]
        anchor[1].begin(anchor[2])
        raise O.OriginError("INITIAL_ADAPTER_RUN_REENTRY")
    attempts = {}
    entry = C.B.EntryLatch(attempts)
    attempt = entry.begin(attempts)
    claims = _run_claims(operation)
    outputs = ({name: os.environ.get("P2PKIT_BOOTSTRAP_PROBE_" + suffix) for name, suffix in _OUTPUT_NAMES}
               if operation == "after-probe" else {})
    run = _track(_Run(operation, entry, attempts, attempt, cancelled, claims, outputs, prefix,
               N._history_graph(claims, outputs)))
    _RUN_LATCHES[id(run)] = run, entry, attempts, attempt
    _RUNS[operation] = run
    try:
        if operation == "produce":
            require(C.checked_retired_primary(prefix) is prefix, "RETIRED_PREFIX_REQUIRED")
            _progress(run, history=D.canonical(prefix.history))
        else:
            require(prefix is None, "STEP_NO_C_PREFIX")
        _environment(run)
        return run
    except BaseException as error:
        raise _fail(run, error)


def _new_phase(run, name, proposal, predecessor=None):
    try:
        _pin(run)
        run.entry.check(run.attempts, run.attempt)
        sequence = _SEQUENCES[run.operation]
        require(not run.starting and run.failure is run.terminal is None and
            len(run.phases) < len(sequence) and name == sequence[len(run.phases)] and
            (run.current is None or run.current.returned is not None), "PHASE_ENTRY")
        if run.current is not None:
            require(predecessor is run.current.returned, "PHASE_ORIGINAL_PREDECESSOR")
            _closed_return(predecessor)
        elif run.operation == "produce":
            require(type(predecessor) is _PrefixFloor and predecessor.raw == run.prefix.raw and
                predecessor.checked_ns == run.prefix.retired_ns and predecessor.checked_local == run.prefix.retired_local,
                "ORIGINAL_RETIRED_FLOOR")
        else:
            require(predecessor is None and proposal is None, "NEW_STEP_ORIGINAL_FIRST")
        _progress(run, starting=True)  # Consume before a supplier can reenter.
        local = D.local(time.monotonic())
        first = O.clocks.validate_reading(O.clocks.observe())
        boot = D.sha(N.continuity.boot_digest(first.clock.role))
        _pin(run)
        run.entry.check(run.attempts, run.attempt)
        if run.history is not None:
            require(O.clock_value(first.clock) == run.history["clock"] and boot == run.history["originalBootDigest"],
                    "PHASE_ORIGINAL_CLOCK_OR_BOOT")
        if predecessor is not None:
            require(first.nanoseconds >= predecessor.checked_ns and local >= predecessor.checked_local,
                    "PHASE_RETURN_BACKWARDS")
        cumulative, ends, locals_ = 0, [], []
        for phase, seconds, _soft in _PHASES[name]:
            cumulative += seconds
            end = O.integer(first.nanoseconds + cumulative * NS)
            if proposal is not None:
                end = min(end, proposal["phaseFencesNs"][phase], proposal["proposedJobEndNs"])
            ends.append(end)
            locals_.append(O.wire._directed_deadline(local, cumulative, end, first.nanoseconds))
        require(first.nanoseconds < ends[0] and ends == sorted(ends), "NO_ORIGINAL_PHASE_INTERVAL")
        parent, window = _Parent(), _Window()
        state = _track(_ParentState(parent, run, name, first, local, boot, proposal, predecessor,
            N._history_graph(first), tuple(ends), tuple(locals_), window,
            graph=N._history_graph(proposal, predecessor.__dict__ if predecessor is not None else None),
            starts=((first.nanoseconds, local, ends[0], locals_[0]),), last=first.nanoseconds,
            last_reading=first, local_last=local, issued=locals_[0]))
        _PARENTS[id(parent)], _WINDOWS[id(window)] = state, state
        _progress(run, current=state, starting=False)
        window.now()
        return state
    except BaseException as error:
        raise _fail(run, error)


def _shorten(state, proposal):
    """Persisted deadlines may only deny before fresh original source acquisition."""
    require(state.proposal is None and state.phase == 0 and len(state.starts) == 1, "PHASE_SHORTEN_ONCE")
    phase, seconds, _soft = _PHASES[state.name][0]
    hard = min(state.ends[0], O.integer(proposal["phaseFencesNs"][phase]), O.integer(proposal["proposedJobEndNs"]))
    end = min(state.local_ends[0], O.wire._directed_deadline(state.local, seconds, hard, state.first.nanoseconds))
    _progress(state, proposal=proposal, ends=(hard,), local_ends=(end,),
        starts=((state.first.nanoseconds, state.local, hard, end),), issued=min(state.issued, end),
        graph=N._history_graph(proposal))
    state.window.now()


def checked_use_parent(parent, site):
    state = _state(parent)
    try:
        _current(state)
        require(site in U.PRIVATE_SITES and state.site == site and type(state.binding) is U.ParentBinding and
                state.binding.parent is parent and state.binding.site == site and state.phase == 0 and
                state.owner is not None and not _owner_state(state.owner).closed, "FIXED_LIVE_SITE_REQUIRED")
        require(state.name == (_PRODUCTIVE_PHASES[U.PRODUCTIVE_SITES.index(site)] if state.run.operation == "produce"
                else _STEPS[state.run.operation]), "NO_PRIVATE_USE_IN_LATER_STEP_PHASE")
        N._check_history(state.use_graph)
        state.window.now(new=True)
        N._check_history(state.use_graph)
        return state.binding
    except BaseException as error:
        raise _fail(state.run, error)


def _use(state, site, token):
    try:
        require(_state(state.parent) is state, "ORIGINAL_USE_PARENT")
        return _use_fixed(state, site, token)
    except BaseException as error:
        raise _fail(_original(state, "run"), error)


def _use_fixed(state, site, token):
    require(state.site is state.binding is None and state.phase == 0 and site in U.PRIVATE_SITES,
            "USE_SITE_REENTRY")
    prefix = state.run.prefix
    require(prefix is not None, "ORIGINAL_PREFIX_REQUIRED")
    require(state.run.operation == "produce" or state.name == _STEPS[state.run.operation],
            "NO_PRIVATE_USE_IN_LATER_STEP_PHASE")
    expected = (U.PRODUCTIVE_SITES[_PRODUCTIVE_PHASES.index(state.name)] if state.run.operation == "produce" else
                state.run.operation + ("/begin" if len(state.uses) == 0 else "/final"))
    require(site == expected and len(state.uses) < (1 if state.run.operation == "produce" else 2), "USE_SITE_ORDER")
    state.window.now(new=True)
    _, _seconds, soft = _PHASES[state.name][0]
    work = min(state.ends[0], state.first.nanoseconds + soft * NS)
    local_work = min(state.local_ends[0], O.wire._directed_deadline(state.local, soft, work, state.first.nanoseconds))
    records = (tuple((name, dict(prefix.originals)["P/acquisition-queries/" + name + ".bin"]) for name in N.SOURCE_KEYS)
               if state.run.operation == "produce" else prefix.source_records)
    initializer_identity = (dict((name, pin) for name, pin, _provenance in prefix.initializer_directories)["I"]
                            if state.run.operation == "produce" else prefix.initializer_identity)
    binding = U.ParentBinding(state.parent, site, state.first, state.local, work, local_work, state.boot,
        prefix, prefix.identity, prefix.history, prefix.proposal, records, prefix.initializer, initializer_identity)
    _progress(state, site=site, binding=binding,
        use_graph=N._history_graph(binding.__dict__, prefix.identity.__dict__))
    returned = P.acquire_private(state.parent, site, token)
    fresh = P.consume_use(returned, state.parent, site)
    _progress(state, uses=(*state.uses, returned), site=None, binding=None, use_graph=())
    P.checked_consumed_use(returned, state.parent, site)
    state.window.now(new=True)
    return fresh


@dataclass(frozen=True, repr=False)
class _Return:
    raw: bytes
    leaf: object
    checked_ns: int
    checked_local: float


def _closed_return(result):
    saved = _RETURNS.get(id(result))
    require(type(result) is _Return and type(saved) is tuple and saved[0] is result, "NOT_ORIGINAL_PHASE_RETURN")
    _result, state, graph, last, local = saved
    _state(_original(state, "parent"))
    if state.run.failure is not None:
        raise state.run.failure
    run = state.run
    if run.terminal is None:
        run.entry.check(run.attempts, run.attempt)
    else:
        run.entry.returned(run.attempts, run.attempt, run.terminal)
    require(state.returned is result and state.failure is None and state.last == last == result.checked_ns and
            state.local_last == local == result.checked_local and state.site is state.binding is None,
            "CLOSED_PHASE_RETURN_CHANGED")
    N._check_history(graph)
    N._check_history(state.first_graph)
    N._check_history(state.graph)
    for owner in state.owners:
        _known(owner)
    for use in state.uses:
        P.checked_consumed_use(use, state.parent, use.site)
    return result


def _finish_phase(state, raw, leaf):
    for owner in state.owners:
        _known(owner)
    state.window.now()
    return _publish_return(state, raw, leaf)


def _publish_return(state, raw, leaf):
    require(state.returned is None and state.last_reading.nanoseconds == state.last, "ORIGINAL_CLOSE_FRONTIER")
    result = _Return(D.raw_bytes(raw), leaf, state.last, state.local_last)
    graph = N._history_graph(result.__dict__, leaf.__dict__ if leaf is not None else None, state.files,
        None if state.native is None else state.native.__dict__,
        () if state.native is None else tuple(row.__dict__ for row in state.native.captures))
    _progress(state, returned=result)
    _RETURNS[id(result)] = result, state, graph, state.last, state.local_last
    _progress(state.run, phases=(*state.run.phases, result))
    _closed_return(result)
    return result


def _abort(state, error):
    run = _original(state, "run")
    first = _fail(run, error)
    owner = _original(state, "owner")
    if owner is not None:
        owner.error("initial-original-phase", first)
        if _original(state, "name") in ("custody-collect", "custody-uninstall") and _original(state, "phase") == 0:
            try:
                _original(state, "window").advance()
            except BaseException:
                pass
        try:
            owner.close()
        except BaseException:
            pass
    try:
        first.initial_productive_parent = _original(state, "parent")
        first.initial_productive_resources = tuple((owner, _OWNER_RETURNS[id(owner)])
            for owner in _original(state, "owners"))
        first.initial_productive_leaf = _LEAF_RETURNS.get(id(state))
        native = _original(state, "native")
        first.initial_productive_child = None if native is None else _CHILD_RETURNS.get(id(native))
    except BaseException:
        pass
    return first


def _original_inputs(prefix):
    require(C.checked_retired_primary(prefix) is prefix, "ORIGINAL_INPUT_PREFIX")
    available = dict(prefix.originals)
    sources = tuple((name, available["P/acquisition-queries/" + name + ".bin"]) for name in N.SOURCE_KEYS)
    result = D.InitialOriginals(prefix.identity, prefix.history, prefix.proposal, prefix.raw, sources,
        str(prefix.initializer), prefix.initializer_originals, prefix.initializer_directories,
        prefix.retired_ns, prefix.retired_local)
    D.InitialInputs(result, D.capture_originals(result))
    return result


def _directory(owner, path, identity=None):
    directory = owner.open(path)
    pin = tuple(directory.verify().identity)
    require(identity is None or pin == tuple(identity), "ORIGINAL_DIRECTORY_REPLACED")
    owner.end()
    return directory


def _read_initializer(state, inputs):
    """Read the twelve REAL files/eight native directories, never a relocated copy."""
    owner, previous = state.owner, dict(state.run.initial_files)
    directories = {}
    for name, pin, _provenance in inputs.initializer_directories:
        path = inputs.session.joinpath(*name.split("/")[1:])
        directories[name] = _directory(owner, path, pin)
    found = []
    for name, raw in inputs.initializer_originals:
        parent, leaf = name.rsplit("/", 1)
        _, binding = staging._read(_Reader(owner), directories[parent], leaf, expected=raw,
            binding=previous.get(name), maximum=D.LIMIT)
        found.append((name, binding))
    require(len({tuple(binding["identity"]) for _name, binding in found}) == 12, "INITIALIZER_FILE_ALIAS")
    for name, pin, _provenance in inputs.initializer_directories:
        require(tuple(directories[name].verify().identity) == pin, "INITIALIZER_DIRECTORY_CHANGED")
    for directory in reversed(tuple(directories.values())):
        owner.close_one(directory)
    if owner.original is not None:
        raise owner.original
    if not previous:
        _progress(state.run, initial_files=tuple(found))
    else:
        D.same(dict(found), previous, "INITIALIZER_ORIGINAL_FILE_BINDINGS_CHANGED")
    owner.end()


def _artifact(state, key, directory, name, raw):
    require(not any(old[0] == key for old in state.files), "ORIGINAL_FILE_REENTRY")
    D.raw_bytes(raw, empty=False)
    state.owner.write(directory, name, raw)
    actual, binding = staging._read(_Reader(state.owner), directory, name, expected=raw)
    pin = tuple(directory.verify().identity)
    record = (key, str(directory.path), pin, name, actual, O.encoded(binding))
    _progress(state, files=(*state.files, record))
    state.owner.end()
    return record


def _phase_directory(state, inputs):
    owner = state.owner
    parent = _directory(owner, inputs.session, inputs.directories["session"])
    number = _PRODUCTIVE_PHASES.index(state.name) + 1
    directory = owner.child(parent, "initial-product-" + str(number).zfill(2), create=True)
    require(tuple(directory.identity) not in inputs.directories.values(), "PHASE_DIRECTORY_ALIAS")
    return directory


def _staged_inputs(originals, stage, seed):
    staged = custody.StagedEvidence(seed.raw, stage.raw, stage.leaf, seed.leaf,
        seed.checked_ns, seed.checked_local)
    return custody._InitialInputs(originals, D.capture_originals(originals), staged, custody._capture_staged(staged))


def _phase_record(state, leaf, previous, pending):
    window = state.window
    closed = window.now()
    if state.name in ("dependency-stage", "empty-seed"):
        leaf_value = D.canonical(leaf.raw)
        saved = leaf_value["window"]
        return O.encoded({"schema": 1, "scope": D.STAGING_PARENT_SCOPE, "phase": state.name,
            "window": {**{name: saved[name] for name in ("phase", "clock", "firstNs", "softEndNs", "hardEndNs")},
                       "budgetAcceptance": "NOT_ADMITTED"},
            "pendingSha256": O.digest(pending), "predecessorSha256": O.digest(previous.raw),
            "predecessorCheckedNs": previous.checked_ns, "leafSha256": O.digest(leaf.raw),
            "leafCheckedNs": leaf.checked_ns, "closedNs": closed,
            "resourceCount": len(_OWNERS[id(state.owner)].resources), "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY",
            "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "exportSaveAuthority": False})
    raw = {"schema": 1, "scope": D.PARENT_SCOPE, "phase": state.name, "window": window.record(),
        "clock": O.clock_value(state.first.clock), "firstNs": state.first.nanoseconds,
        "hardEndNs": state.ends[0], "softEndNs": min(state.ends[0], state.first.nanoseconds +
            _PHASES[state.name][0][2] * NS), "predecessorSha256": O.digest(previous.raw),
        "predecessorCheckedNs": previous.checked_ns, "pendingSha256": O.digest(pending),
        "leafSha256": O.digest(leaf.raw), "leafCheckedNs": getattr(leaf, "checked_ns", state.last),
        "closedNs": closed, "resourceCount": len(_OWNERS[id(state.owner)].resources),
        "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "freshUseSha256": O.digest(state.uses[0].raw),
        "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
        "exportSaveAuthority": False}
    if state.name == "save-set-before":
        raw["exportParentSha256"] = O.digest(previous.raw)
    return O.encoded(raw)


@dataclass(frozen=True, repr=False)
class _PrefixFloor:
    raw: bytes
    checked_ns: int
    checked_local: float


def _leaf_phase(run, name, token, previous, inputs):
    state = _new_phase(run, name, inputs.proposal, previous)
    try:
        owner = _new_owner(state)
        _progress(state, inputs=inputs, graph=N._history_graph(state.proposal, inputs.__dict__, inputs.published.__dict__))
        _read_initializer(state, inputs)
        phase = staging.PhaseStart(state.first, state.local)
        _use(state, U.PRODUCTIVE_SITES[_PRODUCTIVE_PHASES.index(name)], token)
        directory = _phase_directory(state, inputs)
        if name == "dependency-stage":
            leaf = staging.stage_initial_recipient_empty(owner, run.originals, phase)
        elif name == "empty-seed":
            leaf = staging.observe_initial_recipient_empty_seed(owner, run.originals, phase, previous.leaf)
        elif name == "custody-prepare":
            leaf = custody.reserve_initial_recipient_configuration(owner, run.originals, phase, inputs.staged)
        elif name == "dependency-export":
            window = dependency_export._InitialWindow(inputs, phase, (previous.raw, previous.checked_ns, previous.checked_local))
            leaf = dependency_export.export_initial_recipient_snapshot(owner, inputs, window)
        elif name == "save-set-before":
            window = save_set._InitialWindow(inputs, phase, (previous.raw, previous.checked_ns, previous.checked_local))
            leaf = save_set.before_initial_recipient_save(owner, inputs, window, previous.leaf.raw)
        elif name in ("custody-collect", "custody-uninstall"):
            configured = next(value for value in run.phases if _RETURNS[id(value)][1].name == "configuration")
            native = configured.leaf
            if name == "custody-collect":
                originals = collection.FileOriginals(native.request_raw, inputs.admitted.record, inputs.canonical_raw,
                    native.start_raw, native.receipt_raw, native.manifest_raw, 0, native.evidence_identity,
                    native.retained_identity, native.metadata_bindings_raw)
                leaf = collection.collect_initial_recipient_inventory(owner, originals)
            else:
                originals = no_loader.HomeOriginals(native.request_raw, inputs.admitted.record, inputs.canonical_raw,
                    inputs.directories["gradle-home"])
                leaf = no_loader.observe_initial_recipient_absence(owner, originals)
        else:
            raise O.OriginError("INITIAL_ADAPTER_NOT_FIXED_LEAF")
        # The assignment above retains the actual leaf return before any
        # fallible post-return checks or owner close; no file substitutes it.
        _LEAF_RETURNS[id(state)] = leaf
        leaf_graph = _data_pins(leaf)
        state.window.now()
        _read_initializer(state, inputs)
        pending = O.encoded({"schema": 1, "scope": "INITIAL_RECIPIENT_PRODUCTIVE_LEAF_PENDING_OWNER_CLOSE_V1",
            "phase": name, "binding": inputs.binding(), "leafSha256": O.digest(leaf.raw),
            "useSha256": O.digest(state.uses[0].raw), "window": state.window.record(),
            "ownerClose": D.PENDING, "nextPhaseAuthority": False, "exportSaveAuthority": False})
        _artifact(state, "pending", directory, "leaf-return-pending.json", pending)
        if name in ("custody-collect", "custody-uninstall"):
            state.window.advance()  # Original FINAL45 is close-only.
        owner.close()
        _known(owner)
        if name in ("custody-collect", "custody-uninstall"):
            state.window.advance()  # Post-close READ30 admits no acquisitions.
        _check_data_pins(leaf_graph)
        raw = _phase_record(state, leaf, previous, pending)
        return _finish_phase(state, raw, leaf)
    except BaseException as error:
        raise _abort(state, error)


@dataclass(eq=False, repr=False)
class _Native:
    descriptor: bytes
    environment: tuple
    start_raw: bytes
    directory: object
    directory_identity: tuple
    handles: dict
    outer: str
    scope_attempted: bool = False
    launch_attempted: bool = False
    child: object = None
    child_kind: object = None
    child_pid: object = None
    preparer: object = None
    baseline: object = None
    birth: object = None
    leader: object = None
    terminal: object = None
    exit_code: object = None
    completed: object = None
    work_accepted: bool = False
    retired: bool = False
    drain_attempted: bool = False
    cancellation_attempted: bool = False
    cancellation_raw: object = None
    captures: tuple = ()
    finalized: object = None


@dataclass(frozen=True, repr=False)
class _Capture:
    name: str
    stream: object
    identity: tuple
    highwater: int
    stamp: object = None
    readback: object = None


@dataclass(frozen=True, repr=False)
class _Configuration:
    raw: bytes
    request_raw: bytes
    start_raw: bytes
    receipt_raw: bytes
    manifest_raw: bytes
    observation_raw: bytes
    command_raw: bytes
    native_raw: bytes
    evidence_identity: tuple
    retained_identity: tuple
    metadata_bindings_raw: bytes


def _native_pin(state, label):
    owner = _original(state, "owner")
    rows = [pin for pin in _original(_OWNERS[id(owner)], "resources") if pin.label == label]
    require(len(rows) <= 1, "NATIVE_RESOURCE_DUPLICATE")
    return rows[0] if rows else None


def _native_scope(state):
    """Only independently proven native ownership; not the unrelated file ledger."""
    pin = _native_pin(state, "native-scope")
    require(pin is not None and type(pin.value) is pin.kind and not pin.attempted and
            getattr(pin.kind, "close") is pin.close_method, "ORIGINAL_NATIVE_SCOPE_REQUIRED")
    scope, start = pin.value, D.canonical(state.native.start_raw)
    if state.first.clock.role == "windows-x64":
        require((scope.job_id, scope.invocation) == (start["job"], start["invocation"]), "NATIVE_SCOPE_CHANGED")
    else:
        require((scope.job, scope.invocation, scope.state, scope.home) ==
            (start["job"], start["invocation"], start["state"], start["home"]), "NATIVE_SCOPE_CHANGED")
    return scope


def _producer_command(state, inputs, reservation, outer):
    base = B.child_environment(inputs.session)
    inherited = B.processes.ownership_domains(base.get(B.processes.CHAIN_ENV, ""), base.get(B.processes.DOMAINS_ENV, ""))
    invocation = reservation["owner"]["productInvocation"]
    require(len(inherited) <= 30 and producer._uuid(invocation) and producer._uuid(outer) and outer not in
        {invocation, inputs.invocation, inputs.canonical["id"], D.canonical(inputs.context_raw)["job"],
         *(row["id"] for row in inherited)} and invocation not in {row["id"] for row in inherited},
        "PRODUCER_ORIGINAL_ANCESTRY_COLLISION")
    environment = B.processes.ownership_environment(base, inputs.canonical["id"], outer,
        str(inputs.state), str(inputs.home), allow_new_context=True)
    domains = B.processes.ownership_domains(environment[B.processes.CHAIN_ENV], environment[B.processes.DOMAINS_ENV])
    require(domains[:-1] == inherited and domains[-1] == {"id": outer, "job": inputs.canonical["id"],
        "state": str(inputs.state), "home": str(inputs.home)}, "PRODUCER_DOMAIN_CHANGED")
    raw = producer_command.initial_recipient_command_request(inputs.admitted.record, inputs.canonical_raw,
        invocation=invocation, ancestor_invocations=tuple(row["id"] for row in domains))
    state.window.now()
    return raw, tuple(sorted(environment.items()))


def _producer_state(state, inputs, reservation, *, before):
    owner, leaf = state.owner, _Reader(state.owner)
    _read_initializer(state, inputs)
    handles = staging._initialized(leaf, inputs)
    if before:
        staging._initialized_readback(leaf, inputs, handles, inputs.seed_value["fileBindings"])
    else:
        for name, directory in handles.items():
            require(tuple(directory.verify().identity) == inputs.directories[name], "PRODUCER_ORIGINAL_STATE_CHANGED")
        staging._names(leaf, handles["state"], ("context.json", "gradle-home", "evidence", "cancellations"))
        staging._names(leaf, handles["evidence"], (reservation["owner"]["productInvocation"],))
        staging._names(leaf, handles["cancellations"], ())
    directory = _directory(owner, inputs.directory, reservation["directories"]["custody"])
    retained = owner.child(directory, "retained")
    require(list(retained.verify().identity) == reservation["directories"]["retained"], "ORIGINAL_RETAINED_DIRECTORY")
    staging._read(leaf, directory, "request.json", expected=O.encoded(reservation))
    staging._names(leaf, directory, ("request.json", "retained"))
    staging._names(leaf, retained, ())
    container = _directory(owner, inputs.container, inputs.stage["containerIdentity"])
    restore = owner.child(container, "restore-home")
    custody._stage_readback(leaf, inputs, container, restore)
    require(custody._sources(leaf, inputs) == {name: reservation[name] for name in
        ("inputs", "bootstrapInputs", "custodyInputs")}, "PRODUCER_SOURCES_CHANGED")
    return handles


def _captures(state, *, cleanup=False):
    native, role = state.native, state.first.clock.role
    require(tuple(row.name for row in native.captures) == ("stdout", "stderr") and
            len({row.identity for row in native.captures}) == 2, "ORIGINAL_CAPTURE_ROSTER")
    for capture in native.captures:
        state.window.now(final=cleanup)
        pin = _native_pin(state, capture.name)
        stream = capture.stream
        require(pin is not None and pin.value is stream and type(stream) is pin.kind and not pin.attempted and
            stream.path == native.directory.path / (capture.name + ".log"), "ORIGINAL_CAPTURE_CHANGED")
        maximum, deadline = ((stream.max_bytes, stream._deadline) if role == "windows-x64" else
                             (stream.maximum, stream.deadline))
        require(type(maximum) is int and maximum == 67174400 and deadline == state.local_ends[2], "CAPTURE_ORIGINAL_CAP")
        info = stream.observe_live_output() if role == "windows-x64" else stream.verify()
        stamp = B._producer_stamp(info, role)
        require(stamp[0] == capture.identity and capture.highwater <= stamp[1] <= 67174400, "CAPTURE_SHRANK_OR_OVERFLOWED")
        _progress(native, captures=tuple(replace(row, highwater=stamp[1]) if row.name == capture.name else row
                                        for row in native.captures))
        state.window.now(final=cleanup)
    require(sum(row.highwater for row in native.captures) <= 134348800, "CAPTURE_AGGREGATE")


def _producer_cancel(state):
    """Exactly one four-field request, not a general RETURN acquisition API."""
    native, owner = state.native, state.owner
    require(state.phase == 1 and state.run.failure is not None and not native.cancellation_attempted,
            "CANCELLATION_REQUEST_REENTRY")
    _progress(native, cancellation_attempted=True)
    writer = reader = None
    try:
        require(not _OWNERS[id(owner)].unknown and native.child is not None and native.leader is not None and
            type(native.child) is native.child_kind and native.child.pid == native.child_pid, "CANCEL_ORIGINAL_CHILD")
        _native_scope(state)
        start, descriptor = D.canonical(native.start_raw), D.canonical(native.descriptor)
        request = producer.parse(descriptor["requestBytes"].encode("ascii"))
        B.native_record(producer.parse(native.birth), start, producer.parse(native.leader), descriptor["argv"], terminal=False)
        for name in ("state", "gradle-home", "cancellations"):
            directory = native.handles[name]
            require(tuple(directory.verify().identity) == state.inputs.directories[name], "CANCEL_ORIGINAL_HOME_CHANGED")
        directory = native.handles["cancellations"]
        require(directory.path == Path(descriptor["state"]) / "cancellations" and start["home"] == request["gradleHome"] and
            start["job"] == request["jobId"] and start["invocation"] != request["id"], "CANCEL_FIXED_TARGET")
        label = datetime.now(timezone.utc).isoformat()
        producer._utc(label)
        _progress(native, cancellation_raw=O.encoded({"schema": 1, "id": request["id"],
            "jobId": request["jobId"], "requestedUtc": label}))
        raw = native.cancellation_raw
        require(len(raw) <= 512, "CANCEL_BYTES")
        end = state.window.deadline(225, final=True)
        try:
            writer = directory.create_file(request["id"] + ".json", max_bytes=len(raw), deadline=end)
            owner._retain("cancellation-writer", writer)  # Retain BEFORE fallible observation.
        except BaseException as error:
            owner.error("producer-cancellation-writer-allocation", error, unknown=True)
            raise
        state.window.now(final=True)
        count = writer.write(raw)
        require(type(count) is int and count == len(raw), "CANCEL_SHORT_WRITE")
        state.window.now(final=True)
        writer.sync()
        info = writer.verify()
        require(info.size == len(raw), "CANCEL_WRITE_CHANGED")
        binding = F._info_binding(info)
        owner.close_one(writer)
        require(_native_pin(state, "cancellation-writer").closed, "CANCEL_WRITER_NOT_CLOSED")
        end = state.window.deadline(225, final=True)
        try:
            reader = directory.open_file(request["id"] + ".json", max_bytes=len(raw), deadline=end)
            owner._retain("cancellation-reader", reader)
        except BaseException as error:
            owner.error("producer-cancellation-reader-allocation", error, unknown=True)
            raise
        state.window.now(final=True)
        before = reader.initial_info
        require(F._info_binding(before) == binding and before.size == len(raw), "CANCEL_READBACK_REPLACED")
        actual = reader.read(len(raw))
        state.window.now(final=True)
        require(type(actual) is bytes and actual == raw and reader.read(1) == b"" and reader.verify() == before,
                "CANCEL_READBACK_CHANGED")
        owner.close_one(reader)
        require(_native_pin(state, "cancellation-reader").closed, "CANCEL_READER_NOT_CLOSED")
        state.window.now(final=True)
    except BaseException as error:
        owner.error("producer-cancellation-request", error)
    finally:
        for resource in (reader, writer):
            if resource is not None:
                owner.close_one(resource)


def _producer_final(state):
    native, owner = state.native, state.owner
    try:
        state.window.advance()  # RETURN225 includes existing canonical stop120 and tail.
        if native.child is not None and native.leader is not None:
            if state.run.failure is not None and not _OWNERS[id(owner)].unknown:
                _producer_cancel(state)
            while not _OWNERS[id(owner)].unknown and native.exit_code is None:
                state.window.now(final=True)
                require(type(native.child) is native.child_kind and native.child.pid == native.child_pid,
                        "RETURN_CHILD_CHANGED")
                _captures(state, cleanup=True)
                code = native.child.poll()
                if code is not None:
                    _progress(native, exit_code=code)  # A late zero never changes work_accepted.
                state.window.now(final=True)
                _native_scope(state).discover()
                state.window.now(final=True)
                if code is None:
                    time.sleep(.025)
    except BaseException as error:
        owner.error("producer-return", error)
    ready = False
    try:
        state.window.advance()  # FINAL45 contains original drain and capture close only.
        ready = True
    except BaseException as error:
        owner.error("producer-final-start", error)
    pin = _native_pin(state, "native-scope")
    if pin is not None:
        end = None
        try:
            scope = _native_scope(state)
            require(ready, "NATIVE_FINAL_START_FAILED")
            end = state.window.deadline(45, final=True)
            local = D.local(time.monotonic())
            require(local >= state.local_last, "NATIVE_FINAL_LOCAL_BACKWARDS")
            _progress(state, local_last=local)
            remaining = max(0, end - local)
            require(not native.drain_attempted, "NATIVE_DRAIN_REENTRY")
            _progress(native, drain_attempted=True)
            grace = min(5, remaining)
            survivors = scope.drain(grace=grace, kill_wait=min(5, max(0, remaining - grace)), deadline=end)
            _progress(native, terminal=O.encoded(scope.description()))
            require(survivors == [] and producer.parse(native.terminal).get("discoveryErrors") == [], "NATIVE_DRAIN_UNKNOWN")
            if native.preparer is not None:
                require(O.encoded(B.preparer_identity(scope, state.first.clock.role)) == native.preparer, "PREPARER_CHANGED")
            if native.leader is not None:
                B.native_record(producer.parse(native.terminal), D.canonical(native.start_raw),
                    producer.parse(native.leader), D.canonical(native.descriptor)["argv"])
                require(producer.parse(native.terminal)["launches"] == producer.parse(native.birth)["launches"],
                        "NATIVE_ORIGINAL_LAUNCH_CHANGED")
            state.window.now(final=True)
            B.posix._deadline(end)
            _progress(native, retired=True)
        except BaseException as error:
            owner.error("producer-native-drain", error, unknown=True)
        try:
            # The original scope separately proves its own lifetime/close duty.
            # An unrelated file UNKNOWN never redirects or abandons this scope.
            _native_scope(state)
            owner._close_pin(pin)
        except BaseException as error:
            owner.error("producer-native-close", error, unknown=True)
        if not _native_pin(state, "native-scope").closed:
            _progress(native, retired=False)
        if end is not None:
            try:
                state.window.now(final=True)
                B.posix._deadline(end)
            except BaseException as error:
                _progress(native, retired=False)
                owner.error("producer-native-close-return", error, unknown=True)
    elif native.scope_attempted:
        owner.error("producer-native-allocation", O.OriginError("INITIAL_ADAPTER_SCOPE_UNKNOWN"), unknown=True)
    else:
        _progress(native, retired=True)
    if native.retired and not _OWNERS[id(owner)].unknown:
        for capture in native.captures:
            try:
                state.window.now(final=True)
                capture.stream.sync()
                stamp = B._producer_stamp(capture.stream.verify(), state.first.clock.role)
                require(stamp[0] == capture.identity and capture.highwater <= stamp[1] <= 67174400,
                        "FINAL_CAPTURE_CHANGED")
                _progress(native, captures=tuple(replace(row, stamp=stamp, highwater=stamp[1]) if row.name == capture.name
                                                else row for row in native.captures))
                state.window.now(final=True)
            except BaseException as error:
                owner.error("producer-capture-final", error)
            owner.close_one(capture.stream)
        for name in ("stdout", "stderr"):
            capture_pin = _native_pin(state, name)
            if capture_pin is not None:
                owner.close_one(capture_pin.value)  # Includes returns before a failed initial capture observation.
    try:
        _progress(native, finalized=state.window.now(final=True))
    except BaseException as error:
        owner.error("producer-final-return", error)


def _launch_producer(state, inputs, reservation):
    owner, native = state.owner, state.native
    descriptor = D.canonical(native.descriptor)
    role = state.first.clock.role
    try:
        output = owner.acquire("direct-output", lambda: B.windows.open_private_directory(native.directory.path)
            if role == "windows-x64" else B.query._PosixDirectory(native.directory.path))
        require(tuple(output.verify().identity) == native.directory_identity if role == "windows-x64" else
                tuple(output.identity) == native.directory_identity, "DIRECT_OUTPUT_DIRECTORY_CHANGED")
        for name in ("stdout", "stderr"):
            stream = owner.acquire(name, lambda name=name: output.create_file(name + ".log",
                max_bytes=67174400, deadline=state.local_ends[2]))
            info = stream.observe_live_output() if role == "windows-x64" else stream.verify()
            stamp = B._producer_stamp(info, role)
            require(type(stamp[1]) is int and stamp[1] == 0, "ORIGINAL_CAPTURE_NOT_EMPTY")
            _progress(native, captures=(*native.captures, _Capture(name, stream, stamp[0], 0)))
            state.window.now()
        start = D.canonical(native.start_raw)
        _progress(native, scope_attempted=True)
        scope = owner.acquire("native-scope", lambda: B.processes.make_scope(start["job"], start["invocation"],
            start["state"], start["home"]))
        require(_native_scope(state) is scope, "NATIVE_SCOPE_RETURN_CHANGED")
        _progress(native, preparer=O.encoded(B.preparer_identity(scope, role)))
        _progress(native, baseline=O.encoded({"role": role,
            "baseline": sorted(scope.baseline) if hasattr(scope, "baseline") else None, "kernelJob": role == "windows-x64"}))
        B.baseline_record(native.baseline, role)
        _artifact(state, "baseline", native.directory, "baseline.json", native.baseline)
        _read_initializer(state, inputs)
        require(_producer_command(state, inputs, reservation, native.outer) == (native.descriptor, native.environment),
                "NATIVE_LAUNCH_COMMAND_CHANGED")
        minimum = state.window.now()
        _progress(native, launch_attempted=True)
        child = scope.spawn(descriptor["argv"], str(ROOT), dict(native.environment),
            stdout=_native_pin(state, "stdout").value, stderr=_native_pin(state, "stderr").value)
        _CHILD_RETURNS[id(native)] = child  # Before even the first post-spawn pin/type check.
        _progress(native, child=child, child_kind=type(child))
        require(child.stdout is child.stderr is None, "PRIVATE_NATIVE_SINKS_REQUIRED")
        _progress(native, child_pid=child.pid)
        require(type(native.child_pid) is int and 0 < native.child_pid <= 2**32 - 1, "ORIGINAL_CHILD_PID")
        _progress(native, birth=O.encoded(scope.description()))
        leaders = [row for row in producer.parse(native.birth).get("startedIdentities", []) if row.get("pid") == native.child_pid]
        require(len(leaders) == 1, "ORIGINAL_NATIVE_BIRTH")
        B.native_record(producer.parse(native.birth), start, leaders[0], descriptor["argv"], terminal=False)
        _progress(native, leader=O.encoded(leaders[0]))
        require(producer.parse(native.preparer)["pid"] != native.child_pid, "CONTROLLER_NOT_PARENT")
        baseline = B.baseline_record(native.baseline, role)
        if baseline["baseline"] is not None:
            leader = B.lifetime(leaders[0], role)
            require(list(leader[:4] if role.startswith("macos-") else leader) not in baseline["baseline"],
                    "PREEXISTING_LEADER")
        observed = state.window.now(minimum=minimum)
        _artifact(state, "native-start", native.directory, "native-start.json", O.encoded({
            "ownership": producer.parse(native.birth), "leader": leaders[0],
            "preparerIdentity": producer.parse(native.preparer), "observedNs": observed}))
        while True:
            state.window.now()
            _captures(state)
            code = child.poll()
            if code is not None:
                _progress(native, exit_code=code)
            state.window.now()
            require(type(child) is native.child_kind and child.pid == native.child_pid, "ORIGINAL_CHILD_CHANGED")
            survivors = scope.discover()
            state.window.now()
            _captures(state)
            if code is not None:
                require(type(code) is int and code == 0 and survivors == [], "CANONICAL_WORK_EXIT_OR_DESCENDANTS")
                _progress(native, completed=state.window.now())
                _progress(native, work_accepted=True)
                break
            time.sleep(.025)
    except BaseException as error:
        owner.error("producer-native-work", error)
    finally:
        _producer_final(state)
    if state.run.failure is not None:
        raise state.run.failure


def _read_captures(state):
    owner, native = state.owner, state.native
    require(state.phase == 2 and native.work_accepted and native.retired and len(native.captures) == 2 and
        all(row.stamp is not None for row in native.captures) and
        all(_native_pin(state, name).closed for name in ("native-scope", "stdout", "stderr")), "READ_BEFORE_ORIGINAL_CLOSE")
    state.window.advance()
    for capture in native.captures:
        reader = owner.acquire("reader", lambda: native.directory.open_file(capture.name + ".log",
            max_bytes=67174400, deadline=owner.end()))
        try:
            before = reader.initial_info
            require(B._producer_stamp(before, state.first.clock.role) == capture.stamp, "CLOSED_CAPTURE_REPLACED")
            count, digest = 0, hashlib.sha256()
            while count < before.size:
                owner.end()
                part = reader.read(min(65536, before.size - count))
                require(type(part) is bytes and 0 < len(part) <= before.size - count, "CAPTURE_SHORT_READ")
                count += len(part)
                require(count <= 67174400, "CAPTURE_OVERFLOW")
                digest.update(part)
                owner.end()
            require(reader.read(1) == b"" and reader.verify() == before and count == before.size, "CAPTURE_READ_CHANGED")
        except BaseException as error:
            owner.error("producer-capture-read", error)
            raise
        finally:
            owner.close_one(reader)
        if owner.original is not None:
            raise owner.original
        observed = state.window.now()
        _progress(native, captures=tuple(replace(row, readback=(count, digest.hexdigest(), observed,
            O.encoded(F._info_binding(before)))) if row.name == capture.name else row for row in native.captures))
    require(sum(row.readback[0] for row in native.captures) <= 134348800, "CLOSED_CAPTURE_AGGREGATE")


def _configuration_phase(run, token, previous, inputs):
    state = _new_phase(run, "configuration", inputs.proposal, previous)
    try:
        owner = _new_owner(state)
        _progress(state, inputs=inputs, graph=N._history_graph(inputs.__dict__, inputs.published.__dict__, state.proposal))
        reservation = D.canonical(previous.leaf.request_raw)
        require(reservation["binding"] == inputs.binding() and reservation["scope"] == custody.REQUEST_SCOPE and
            reservation["owner"]["job"] == inputs.canonical["id"] and
            reservation["owner"]["sameHomeStopInvocation"] == reservation["owner"]["productInvocation"], "ORIGINAL_RESERVATION")
        handles = _producer_state(state, inputs, reservation, before=True)
        _use(state, "configuration/prelaunch", token)
        directory = _phase_directory(state, inputs)
        chosen = uuid.uuid4()
        require(type(chosen) is uuid.UUID and chosen.version == 4, "PRODUCER_UUID_SUPPLIER")
        descriptor_raw, environment = _producer_command(state, inputs, reservation, chosen.hex)
        descriptor = D.canonical(descriptor_raw)
        request_raw = descriptor["requestBytes"].encode("ascii")
        request = producer.parse(request_raw)
        start_raw = O.encoded({"schema": 1, "scope": "INITIAL_RECIPIENT_CONFIGURATION_PARENT_PRELAUNCH_V1",
            "contextSha256": descriptor["canonicalContextSha256"], "argv": descriptor["argv"], "cwd": str(ROOT),
            "role": inputs.role, "job": request["jobId"], "invocation": chosen.hex, "state": str(inputs.state),
            "home": str(inputs.home), "inheritedContext": {name: dict(environment)[name] for name in B.query._CONTEXT},
            "startedNs": state.first.nanoseconds, "workEndNs": state.ends[0], "finalEndNs": state.ends[2],
            "exitCode": None, "launchAttempted": False, "scopeAttempted": False, "retirement": "UNKNOWN"})
        native = _track(_Native(descriptor_raw, environment, start_raw, directory, tuple(directory.identity), handles, chosen.hex))
        _progress(state, native=native)
        _artifact(state, "command", directory, "command.json", descriptor_raw)
        _artifact(state, "request", directory, "request.json", request_raw)
        _artifact(state, "outer-start", directory, "outer-start.json", start_raw)
        _launch_producer(state, inputs, reservation)
        _read_captures(state)
        _producer_state(state, inputs, reservation, before=False)
        evidence = _directory(owner, inputs.state / "evidence" / request["id"])
        original_raw, bindings = {}, {}
        for name in collection.METADATA:
            original_raw[name], bindings[name] = staging._read(_Reader(owner), evidence, name, maximum=producer.LIMIT)
        start, receipt, manifest = (original_raw[name] for name in collection.METADATA)
        require(all(type(producer.parse(raw).get("controllerPid")) is int and
            producer.parse(raw)["controllerPid"] == native.child_pid for raw in (start, receipt)), "CANONICAL_CONTROLLER_CHANGED")
        observation = producer.encoded(producer.observe_initial_recipient_canonical(request_raw, inputs.admitted.record,
            inputs.canonical_raw, start, receipt, original_exit_code=native.exit_code))
        collection.inventory.describe_initial_recipient_inventory(request_raw, inputs.admitted.record,
            inputs.canonical_raw, start, receipt, manifest, original_exit_code=native.exit_code)
        require(_producer_command(state, inputs, reservation, native.outer) == (native.descriptor, native.environment),
                "POST_RETURN_COMMAND_CHANGED")
        for name in collection.METADATA:
            staging._read(_Reader(owner), evidence, name, expected=original_raw[name], binding=bindings[name], maximum=producer.LIMIT)
        native_raw = O.encoded({"schema": 1, "scope": "INITIAL_RECIPIENT_CONFIGURATION_ORIGINAL_NATIVE_V1",
            "start": D.canonical(start_raw), "baseline": producer.parse(native.baseline),
            "birth": producer.parse(native.birth), "leader": producer.parse(native.leader),
            "preparer": producer.parse(native.preparer), "terminal": producer.parse(native.terminal),
            "window": state.window.record(), "originalExitCode": native.exit_code,
            "workCompletedNs": native.completed, "finalizedNs": native.finalized,
            "captures": {row.name: {"bytes": row.readback[0], "sha256": row.readback[1], "readNs": row.readback[2],
                "identity": list(row.identity), "fileBinding": O.parse(row.readback[3])} for row in native.captures},
            "directory": str(directory.path), "directoryIdentity": list(directory.identity),
            "nativeClose": "ORIGINAL_SCOPE_CLOSED_BEFORE_READ", "providerExecution": "NOT_PERFORMED",
            "exportSaveAuthority": False})
        # Large captures stay fixed original references, never Snapshot or DATA copies.
        _artifact(state, "native-result", directory, "native-result.json", native_raw)
        _artifact(state, "canonical-observation", directory, "canonical-observation.json", observation)
        leaf = _Configuration(observation, request_raw, start, receipt, manifest, observation, descriptor_raw,
            native_raw, tuple(evidence.identity), tuple(reservation["directories"]["retained"]), O.encoded(bindings))
        _LEAF_RETURNS[id(state)] = leaf
        graph = _data_pins(leaf)
        owner.close()
        _known(owner)
        closed = state.window.now()
        raw = O.encoded({"schema": 1, "scope": D.PARENT_SCOPE, "phase": "configuration",
            "window": state.window.record(), "predecessorSha256": O.digest(previous.raw),
            "predecessorCheckedNs": previous.checked_ns,
            "requestSha256": O.digest(request_raw), "observationSha256": O.digest(observation),
            "commandSha256": O.digest(descriptor_raw), "nativeSha256": O.digest(native_raw),
            "leafSha256": O.digest(observation), "closedNs": closed, "originalExitCode": native.exit_code,
            "nativeRetirement": "KNOWN_ORIGINAL_SCOPE_CLOSE", "resourceCount": len(_OWNERS[id(owner)].resources),
            "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "freshUseSha256": O.digest(state.uses[0].raw),
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "nextPhaseAuthority": False, "exportSaveAuthority": False})
        _check_data_pins(graph)
        return _finish_phase(state, raw, leaf)
    except BaseException as error:
        if state.native is not None and state.phase == 0:
            state.owner.error("producer-prelaunch", error)
            _producer_final(state)
        raise _abort(state, error)


def _use_data(result):
    P.checked_consumed_use(result, result.parent, result.site)
    originals = dict(result.originals)
    return {"site": result.site, "root": str(result.path), "return": D.canonical(result.raw),
        "inventory": D.canonical(result.inventory), "window": D.canonical(originals["use-window.json"]),
        "returnSha256": O.digest(result.raw), "inventorySha256": O.digest(result.inventory),
        "originalsSha256": {name: O.digest(raw) for name, raw in result.originals}}


def _return_data(returned):
    _closed_return(returned)
    state = _RETURNS[id(returned)][1]
    leaf = returned.leaf
    data = {"rawSha256": O.digest(returned.raw), "checkedNs": returned.checked_ns, "checkedLocal": returned.checked_local}
    if leaf is not None:
        data["leaf"] = {"rawSha256": O.digest(leaf.raw), "checkedNs": getattr(leaf, "checked_ns", returned.checked_ns),
            "localStarted": getattr(leaf, "local_started", state.local),
            "checkedLocal": getattr(leaf, "checked_local", returned.checked_local)}
    return data


@dataclass(frozen=True, repr=False)
class PendingHandoff:
    """An original producer function result, not proof it or its Step returned."""
    raw: bytes
    checked_ns: int
    checked_local: float


@dataclass(frozen=True, repr=False)
class ProductiveHandoff:
    public_result: dict
    fence: object
    hard_end_ns: int


@dataclass(frozen=True, repr=False)
class _StepReturn:
    public_result: dict
    fence: object
    hard_end_ns: int


class _OutputFence:
    """Successful output still uses the original live window, NEVER cleanup mode."""
    __slots__ = ()

    def _checked(self):
        saved = _OUTPUTS.get(id(self))
        require(type(self) is _OutputFence and type(saved) is tuple and saved[0] is self, "ORIGINAL_OUTPUT_REQUIRED")
        _fence, result, state, _raw, graph = saved
        try:
            _state(_original(state, "parent"))
            require(type(result) is (ProductiveHandoff if state.run.operation == "produce" else _StepReturn) and
                state.run.terminal is result and state.run.current is state and result.fence is self and
                result.hard_end_ns == state.ends[0] and state.returned is None, "ORIGINAL_OUTPUT_CHANGED")
            N._check_history(graph)
            for owner in state.owners:
                _known(owner)
            if state.run.operation == "produce":
                handoff = _HANDOFFS.get(id(result))
                require(type(handoff) is _HandoffState and handoff.result is result, "ORIGINAL_HANDOFF_OUTPUT")
                _pending(handoff.pending, handoff.prefix)
                N._check_history(handoff.completed_graph)
            return result, state
        except BaseException as error:
            raise _fail(_original(state, "run"), error)

    @property
    def clock(self):
        return self._checked()[1].first.clock

    @property
    def hard_end(self):
        return self._checked()[0].hard_end_ns

    def now(self, *, final=False, minimum=0, limit=None):
        result, state = self._checked()
        try:
            require(type(final) is bool, "OUTPUT_MODE")
            observed = state.window.now(minimum=minimum, limit=limit)
            checked, current = self._checked()
            require(checked is result and current is state, "ORIGINAL_OUTPUT_CHANGED")
            return observed
        except BaseException as error:
            raise _fail(_original(state, "run"), error)


def _register_output(state, result, raw):
    require(type(result.fence) is _OutputFence and id(result.fence) not in _OUTPUTS and
        state.run.terminal is None and state.returned is None and
        state.name == _SEQUENCES[state.run.operation][-1], "OUTPUT_REGISTRATION")
    for owner in state.owners:
        _known(owner)
    state.window.now()
    _OUTPUTS[id(result.fence)] = (result.fence, result, state, D.raw_bytes(raw),
        N._history_graph(result.__dict__, result.public_result, state.files))
    _progress(state.run, terminal=result)
    state.run.entry.complete(state.run.attempts, state.run.attempt, result)


@dataclass(eq=False, repr=False)
class _HandoffState:
    pending: object
    phase: object
    prefix: object
    path: object
    identity: tuple
    initial_identity: tuple
    graph: tuple
    blobs: tuple
    complete_attempted: bool = False
    result: object = None
    completed_graph: tuple = ()
    return_raw: object = None


def _handoff_blobs(state, inputs):
    phases = { _RETURNS[id(row)][1].name: row for row in state.run.phases }
    configured = phases["configuration"].leaf
    blobs = {}
    for key, phase in (("stage", "dependency-stage"), ("seed", "empty-seed"), ("custody", "custody-prepare"),
                       ("collection", "custody-collect"), ("no-loader", "custody-uninstall"),
                       ("export", "dependency-export"), ("before", "save-set-before")):
        blobs[key + "-parent.json"] = phases[phase].raw
        blobs[key + "-leaf.json"] = phases[phase].leaf.raw
    blobs.update({"custody-request.json": phases["custody-prepare"].leaf.request_raw,
        "producer-parent.json": phases["configuration"].raw, "producer-request.json": configured.request_raw,
        "producer-observation.json": configured.observation_raw, "producer-command.json": configured.command_raw,
        "producer-native.json": configured.native_raw, "collection-inventory.json": phases["custody-collect"].leaf.inventory_raw,
        "retired-prefix.json": inputs.closed_raw, "worker-identity.json": inputs.admitted.record,
        "history.json": inputs.history_raw, "allocation-proposal.json": inputs.proposal_raw,
        **{name + ".bin": raw for name, raw in inputs.source_records},
        "initial-inputs.json": O.encoded({"schema": 1, "scope": D.INPUT_SCOPE, "binding": inputs.binding(),
            "initializerCheckedLocal": inputs.previous_local}),
        "productive-use-index.json": O.encoded({"schema": 1, "scope": "INITIAL_RECIPIENT_PRODUCTIVE_ORIGINAL_USE_INDEX_V1",
            "sites": [_use_data(use) for old in (*state.run.phases, None) for use in
                (state.uses if old is None else _RETURNS[id(old)][1].uses)],
            "inputProvenance": "HISTORICAL_CONSUMED_RETURNS_NOT_CURRENT_AUTHORITY", "exportSaveAuthority": False})})
    require(set(blobs) == set(D.BLOB_NAMES) and len(blobs) == 31 < 32, "HANDOFF_FIXED_BLOB_ROSTER")
    for name, raw in blobs.items():
        D.raw_bytes(raw, empty=name.endswith(".bin"))
    chain = {"scope": "INITIAL_RECIPIENT_ORIGINAL_PRODUCTIVE_CLOSED_CHAIN_V1",
        "returns": {name: _return_data(row) for name, row in phases.items()},
        "referenceScope": "RETAINED_ORIGINAL_BINDINGS_NOT_PROVIDER_OR_STEP_RESULT"}
    # The maintained DATA inventory checker selects the historical before edge
    # by this fixed short name. No new authority or old ordinary parent exists.
    chain["returns"]["before"] = chain["returns"]["save-set-before"]
    references = {"initializerFiles": {name: {"bytes": len(raw), "sha256": O.digest(raw),
        "fileBinding": dict(state.run.initial_files)[name]} for name, raw in inputs.initializer_originals},
        "staging": {"directory": str(inputs.container), "directoryIdentity": inputs.stage["containerIdentity"],
            "name": "staging.json", "bytes": len(inputs.staging_raw), "sha256": O.digest(inputs.staging_raw),
            "fileBinding": inputs.stage_value["fileBindings"]["staging"]},
        "phaseOriginals": {name: [{"key": key, "directory": directory, "directoryIdentity": list(identity),
            "name": leaf, "bytes": len(raw), "sha256": O.digest(raw), "fileBinding": D.canonical(binding)}
            for key, directory, identity, leaf, raw, binding in _RETURNS[id(row)][1].files]
            for name, row in phases.items()}}
    return tuple((name, blobs[name]) for name in D.BLOB_NAMES), chain, references


def produce(prefix, token, cancelled):
    """Run productive9 only. No Step/provider/native-crypto result is invented."""
    run = _new_run("produce", cancelled, prefix)
    state = None
    try:
        _progress(run, originals=_original_inputs(prefix))
        basic = D.InitialInputs(run.originals, D.capture_originals(run.originals))
        _progress(run, graph=N._history_graph(run.claims, run.outputs, run.originals.__dict__, basic.admitted.__dict__))
        floor = _PrefixFloor(prefix.raw, prefix.retired_ns, prefix.retired_local)
        stage = _leaf_phase(run, "dependency-stage", token, floor, basic)
        seed = _leaf_phase(run, "empty-seed", token, stage, basic)
        inputs = _staged_inputs(run.originals, stage, seed)
        reserved = _leaf_phase(run, "custody-prepare", token, seed, inputs)
        configured = _configuration_phase(run, token, reserved, inputs)
        collected = _leaf_phase(run, "custody-collect", token, configured, inputs)
        absent = _leaf_phase(run, "custody-uninstall", token, collected, inputs)
        exported = _leaf_phase(run, "dependency-export", token, absent, inputs)
        before = _leaf_phase(run, "save-set-before", token, exported, inputs)
        state = _new_phase(run, "producer-owner-return", inputs.proposal, before)
        owner = _new_owner(state)
        _progress(state, inputs=inputs, graph=N._history_graph(inputs.__dict__, run.initial_files))
        _use(state, "producer-handoff/retention", token)
        _read_initializer(state, inputs)
        blobs, chain, references = _handoff_blobs(state, inputs)
        initial = _directory(owner, inputs.session, inputs.directories["session"])
        directory = owner.child(initial, "dependency-save-handoff", create=True)
        pin = tuple(directory.verify().identity)
        require(pin not in inputs.directories.values() and pin not in
            (tuple(inputs.stage["containerIdentity"]), tuple(inputs.stage["sourceIdentity"])), "HANDOFF_DIRECTORY_ALIAS")
        value = {"schema": 1, "scope": D.HANDOFF_SCOPE, "binding": inputs.binding(),
            **{name: inputs.admission[name] for name in ("source", "github", "selection", "cacheCohort")},
            "plan": inputs.stage_value["plan"], "planSha256": O.digest(O.encoded(inputs.stage_value["plan"])),
            "directory": str(directory.path), "directoryIdentity": list(pin),
            "blobs": {name: {"bytes": len(raw), "sha256": O.digest(raw)} for name, raw in blobs},
            "references": references, "chain": chain,
            "window": {"phase": "producer-owner-return", "clock": O.clock_value(state.first.clock),
                "originalBootDigest": state.boot, "firstNs": state.first.nanoseconds, "localStarted": state.local,
                "hardEndNs": state.ends[0], "predecessorCheckedNs": before.checked_ns,
                "predecessorSha256": O.digest(before.raw)},
            "writerReturn": D.PENDING, "providerExecution": "NOT_PERFORMED", "nextPhaseAuthority": False,
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        raw = D.raw_bytes(O.encoded(value))
        for name, blob in (*blobs, ("save-handoff.json", raw)):
            # Empty original source stdout is retained without inventing a
            # nonempty record. The same native writer/reader still owns it.
            _write_blob(owner, directory, name, blob)
        _names(owner, directory, (*D.BLOB_NAMES, "save-handoff.json"))
        for name, blob in (*blobs, ("save-handoff.json", raw)):
            require(owner.read(directory, name) == blob, "HANDOFF_ORIGINAL_READBACK_CHANGED")
        _names(owner, directory, (*D.BLOB_NAMES, "save-handoff.json"))
        require(tuple(directory.verify().identity) == pin and tuple(initial.verify().identity) == inputs.directories["session"],
                "HANDOFF_DIRECTORY_CHANGED")
        owner.close()
        _known(owner)
        state.window.now()
        result = PendingHandoff(raw, state.last, state.local_last)
        saved = _track(_HandoffState(result, state, prefix, directory.path, pin, inputs.directories["session"],
            N._history_graph(result.__dict__, blobs, chain, references, run.initial_files), blobs))
        _HANDOFFS[id(result)] = saved
        return result  # Completion must be invoked only after this actual function return.
    except BaseException as error:
        if state is not None:
            raise _abort(state, error)
        raise _fail(run, error)
    finally:
        token = None


def _names(owner, directory, expected):
    end = owner.end()
    require(directory.names(max_names=32, deadline=end) == tuple(sorted(expected)), "FIXED_DIRECTORY_ROSTER")
    directory.verify()
    owner.end()


def _write_blob(owner, directory, name, raw):
    D.raw_bytes(raw, empty=name.endswith(".bin"))
    if raw:
        return owner.write(directory, name, raw)
    writer = owner.acquire("empty-original-writer", lambda: directory.create_file(name, max_bytes=0, deadline=owner.end()))
    try:
        writer.sync()
        require(writer.verify().size == 0, "EMPTY_ORIGINAL_WRITE_CHANGED")
        owner.end()
    except BaseException as error:
        owner.error("empty-original-write", error)
        raise
    finally:
        owner.close_one(writer)
    require(owner.read(directory, name) == b"", "EMPTY_ORIGINAL_READ_CHANGED")
    return raw


def _pending(result, prefix):
    saved = _HANDOFFS.get(id(result))
    require(type(saved) is _HandoffState and
        _original(saved, "pending") is result, "NOT_ORIGINAL_HANDOFF_RETURN")
    state = _original(saved, "phase")
    try:
        require(type(result) is PendingHandoff, "ORIGINAL_PENDING_KIND_CHANGED")
        _pin(saved)
        require(saved.prefix is prefix and C.checked_retired_primary(prefix) is prefix, "NOT_ORIGINAL_HANDOFF_PREFIX")
        _state(state.parent)
        N._check_history(saved.graph)
        for owner in state.owners:
            _known(owner)
        for row in state.run.phases:
            _closed_return(row)
        return saved
    except BaseException as error:
        raise _fail(_original(state, "run"), error)


def complete_productive_handoff(pending, prefix):
    saved = _pending(pending, prefix)
    state = saved.phase
    try:
        require(not saved.complete_attempted and saved.result is None, "HANDOFF_COMPLETION_REENTRY")
        _progress(saved, complete_attempted=True)
        state.window.now(minimum=pending.checked_ns)
        observed, observed_local = state.last, state.local_last
        owner = _new_owner(state)  # SAME original45, not a new first/LOCAL/end.
        initial = _directory(owner, prefix.initializer, saved.initial_identity)
        directory = owner.child(initial, "dependency-save-handoff")
        require(tuple(directory.verify().identity) == saved.identity and
            owner.read(directory, "save-handoff.json") == pending.raw, "HANDOFF_AFTER_RETURN_CHANGED")
        raw = O.encoded({"schema": 1, "scope": D.RETURN_SCOPE, "handoffSha256": O.digest(pending.raw),
            "handoffDirectory": str(saved.path), "handoffDirectoryIdentity": list(saved.identity),
            "initializerIdentity": list(saved.initial_identity), "clock": O.clock_value(state.first.clock),
            "originalBootDigest": state.boot, "firstNs": state.first.nanoseconds, "hardEndNs": state.ends[0],
            "handoffReturnedNs": pending.checked_ns, "handoffReturnedLocal": pending.checked_local,
            "observedAfterReturnNs": observed, "observedAfterReturnLocal": observed_local,
            "observationScope": "HANDOFF_FUNCTION_RETURN_ONLY", "recordWriterReturn": D.PENDING,
            "producerStepOutcome": D.PENDING, "providerExecution": "NOT_PERFORMED",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        owner.write(initial, "producer-function-return.json", raw)
        require(owner.read(initial, "producer-function-return.json") == raw and
            owner.read(directory, "save-handoff.json") == pending.raw, "HANDOFF_RETURN_READBACK_CHANGED")
        owner.close()
        _known(owner)
        state.window.now(minimum=observed)
        value = B.public_result(D.OUTPUT_SCOPE, "producerReturnSha256", raw)
        value["handoffSha256"] = O.digest(pending.raw)
        result = ProductiveHandoff(value, _OutputFence(), state.ends[0])
        _progress(saved, return_raw=raw, result=result, completed_graph=N._history_graph(result.__dict__, value))
        _HANDOFFS[id(result)] = saved
        _register_output(state, result, raw)
        return result
    except BaseException as error:
        raise _abort(state, error)


def checked_productive_handoff(result, prefix):
    saved = _HANDOFFS.get(id(result))
    require(type(saved) is _HandoffState and
        _original(saved, "result") is result, "NOT_COMPLETED_PRODUCTIVE_HANDOFF")
    try:
        require(type(result) is ProductiveHandoff, "ORIGINAL_COMPLETED_KIND_CHANGED")
        _pin(saved)
        require(saved.prefix is prefix and saved.complete_attempted, "ORIGINAL_HANDOFF_COMPLETION")
        _pending(saved.pending, prefix)
        N._check_history(saved.completed_graph)
        require(saved.phase.run.terminal is result and type(result.fence) is _OutputFence and
                result.hard_end_ns == saved.phase.ends[0], "ORIGINAL_OUTPUT_FENCE_CHANGED")
        result.fence.now(minimum=saved.pending.checked_ns)
        N._check_history(saved.completed_graph)
        return result
    except BaseException as error:
        raise _abort(saved.phase, error)


@dataclass(frozen=True, repr=False)
class HandoffInputs:
    """Registered actual-read DATA. Not a recreated C/producer capability."""
    raw: bytes
    identity: object
    history: bytes
    proposal: bytes
    source_records: tuple
    initializer: object
    initializer_identity: tuple
    producer_return_raw: bytes
    blobs: tuple
    originals: object


@dataclass(eq=False, repr=False)
class _ReadState:
    owner: object
    first: object
    claims: dict
    binding: tuple
    directories: dict = field(default_factory=dict)
    files: dict = field(default_factory=dict)
    large: tuple = ()
    handoff: object = None
    graph: tuple = ()
    failure: object = None


def _reader_state(owner, first, claims):
    require(type(owner) in (_Owner, B.Owner) and owner.first is first and owner.fence is not None and
        type(claims) is dict and set(_BASE_CLAIMS).issubset(claims), "ORIGINAL_READER_OWNER")
    O.clocks.validate_reading(first)
    require(owner.original is None and owner.unknown is owner.closed is False, "READER_OWNER_NOT_LIVE")
    if type(owner) is _Owner:
        _owner_state(owner)
    binding = (owner.__dict__, owner.resources, owner.errors, owner.fence, owner.cancelled, owner.local_end,
               owner.work_limit, owner.final_limit)
    return _track(_ReadState(owner, first, dict(claims), binding))


def _reader_passive(reader, *, allow_closed=True):
    _pin(reader)
    owner = reader.owner
    dictionary, ledger, errors, fence, callback, local, work, final = reader.binding
    require(type(owner) in (_Owner, B.Owner) and owner.__dict__ is dictionary and owner.resources is ledger and
        owner.errors is errors and owner.first is reader.first and owner.fence is fence and owner.cancelled is callback and
        owner.local_end == local and owner.work_limit == work and owner.final_limit == final and
        owner.original is None and not owner.unknown and errors == [] and reader.failure is None,
        "ORIGINAL_READ_OWNER_CHANGED")
    if owner.closed:
        require(allow_closed and type(owner) is _Owner, "READER_CLOSED")
        _known(owner)
    elif type(owner) is _Owner:
        _owner_state(owner)
    for path, (directory, kind, pin, row, label) in reader.directories.items():
        require(type(directory) is kind and directory.path == path and tuple(directory.identity) == pin and
            any(value is row for value in ledger) and row.get("owner") is directory and row.get("label") == label and
            row.get("attempted") is owner.closed and row.get("closed") is owner.closed,
            "ORIGINAL_READ_DIRECTORY_PIN_CHANGED")
    N._check_history(reader.graph)
    return reader


def _read_root(reader, path, identity=None):
    owner = reader.owner
    owner.end()
    require(type(path) is type(ROOT) and path.is_absolute() and ".." not in path.parts, "FIXED_READ_ROOT")
    expected = None if identity is None else D.native_identity(identity, reader.first.clock.role)
    if path not in reader.directories:
        directory = owner.acquire("initial-handoff-reader-directory", lambda: F.private_root(path))
        row = next(row for row in owner.resources if row["owner"] is directory)
        pin = D.native_identity(tuple(directory.verify().identity), reader.first.clock.role)
        require(all(pin != old[2] for old in reader.directories.values()) and
            all(pin != tuple(old[1]["identity"]) for old in reader.files.values()) and
            all(pin != tuple(D.canonical(old[4])["identity"]) for old in reader.large), "ORIGINAL_READ_DIRECTORY_ALIAS")
        _progress(reader, directories={**reader.directories, path: (directory, type(directory), pin, row, row["label"])})
    directory, _kind, pin, _row, _label = reader.directories[path]
    require(directory.path == path and tuple(directory.verify().identity) == pin and
            (expected is None or pin == expected), "FIXED_READ_ROOT_REPLACED")
    owner.end()
    return directory


def _read_file(reader, path, name, maximum=D.LIMIT, *, expected=None, binding=None):
    require(type(name) is str and name not in ("", ".", "..") and "/" not in name and "\\" not in name,
            "FIXED_READ_NAME")
    key = path, name
    if key in reader.files:
        previous, previous_binding, original_maximum = reader.files[key]
        require(expected is None or expected == previous, "ORIGINAL_READER_EXPECTATION_CHANGED")
        require(binding is None or binding == previous_binding, "ORIGINAL_READER_FILE_BINDING_CHANGED")
        expected, binding, maximum = previous, previous_binding, original_maximum
    directory = _read_root(reader, path)
    raw, stamp = staging._read(_Reader(reader.owner), directory, name, expected=expected, binding=binding, maximum=maximum)
    if key not in reader.files:
        pin = D.native_identity(stamp["identity"], reader.first.clock.role)
        require(all(pin != tuple(old[1]["identity"]) for old in reader.files.values()) and
            all(pin != old[2] for old in reader.directories.values()) and
            all(pin != tuple(D.canonical(old[4])["identity"]) for old in reader.large), "ORIGINAL_READ_FILE_ALIAS")
        _progress(reader, files={**reader.files, key: (raw, stamp, maximum)})
    return raw


def _read_capture_original(reader, path, name, count, digest, binding_raw):
    """Stream one fixed original capture, never a whole-cohort Snapshot/buffer."""
    require(name in ("stdout.log", "stderr.log") and type(count) is int and 0 <= count <= 67174400,
            "ORIGINAL_CAPTURE_FILE")
    D.sha(digest)
    binding = D.canonical(binding_raw)
    require(F._file_binding(binding), "ORIGINAL_CAPTURE_FILE_BINDING")
    original = path, name, count, digest, binding_raw
    old = next((row for row in reader.large if row[:2] == original[:2]), None)
    require(old is None or old == original, "ORIGINAL_CAPTURE_READER_CHANGED")
    directory = _read_root(reader, path)
    owner = reader.owner
    stream = owner.acquire("initial-capture-original-reader", lambda: directory.open_file(
        name, max_bytes=67174400, deadline=owner.end()))
    try:
        info = stream.initial_info
        require(info.size == count and F._info_binding(info) == binding, "ORIGINAL_CAPTURE_REPLACED")
        hashed, consumed = hashlib.sha256(), 0
        while consumed < count:
            owner.end()
            part = stream.read(min(65536, count - consumed))
            require(type(part) is bytes and 0 < len(part) <= count - consumed, "ORIGINAL_CAPTURE_SHORT_READ")
            consumed += len(part)
            hashed.update(part)
            owner.end()
        require(stream.read(1) == b"" and stream.verify() == info and hashed.hexdigest() == digest,
                "ORIGINAL_CAPTURE_BYTES_CHANGED")
    except BaseException as error:
        owner.error("initial-capture-original", error)
        raise
    finally:
        _Reader(owner).close_one(stream)
    if old is None:
        pin = D.native_identity(binding["identity"], reader.first.clock.role)
        require(all(pin != tuple(item[1]["identity"]) for item in reader.files.values()) and
            all(pin != item[2] for item in reader.directories.values()) and
            all(pin != tuple(D.canonical(item[4])["identity"]) for item in reader.large), "ORIGINAL_CAPTURE_FILE_ALIAS")
        _progress(reader, large=(*reader.large, original))
    owner.end()


def _productive_window(value, phase, proposal, clock, boot):
    D.fields(value, "phase clock originalBootDigest firstNs localStarted globalEndsNs phases budgetAcceptance")
    require(value["phase"] == phase and value["clock"] == clock and value["originalBootDigest"] == boot and
            value["budgetAcceptance"] == "NOT_ADMITTED" and type(value["localStarted"]) is float,
            "PRODUCTIVE_HISTORY_WINDOW")
    first, local = O.integer(value["firstNs"]), D.local(value["localStarted"])
    cumulative, expected, local_ends = 0, [], []
    for name, seconds, _soft in _PHASES[phase]:
        cumulative += seconds
        end = min(O.integer(first + cumulative * NS), proposal["phaseFencesNs"][name], proposal["proposedJobEndNs"])
        expected.append(end)
        local_ends.append(O.wire._directed_deadline(local, cumulative, end, first))
    D.same(value["globalEndsNs"], expected, "PRODUCTIVE_ORIGINAL_GLOBAL_CAPS")
    require(type(value["phases"]) is list and len(value["phases"]) == len(expected), "PRODUCTIVE_COMPLETE_PHASES")
    previous_ns, previous_local, prior_end, prior_local_end = first, local, None, None
    for number, (row, (name, seconds, _soft)) in enumerate(zip(value["phases"], _PHASES[phase])):
        D.fields(row, "name startedNs localStarted endNs")
        began, end = O.integer(row["startedNs"]), O.integer(row["endNs"])
        began_local = D.local(row["localStarted"])
        require(row["name"] == name and type(row["localStarted"]) is float and
            previous_ns <= began < end == min(expected[number], began + seconds * NS) and previous_local <= began_local and
            (number != 0 or (began == first and began_local == local)), "PRODUCTIVE_PHASE_ORDER_AND_CAP")
        local_end = min(local_ends[number], O.wire._directed_deadline(began_local, seconds, end, began))
        if number and number == len(expected) - 1:
            require(began < prior_end and began_local < prior_local_end, "PRODUCTIVE_READ_BEFORE_FINAL_END")
        previous_ns, previous_local, prior_end, prior_local_end = began, began_local, end, local_end
    return expected[0], prior_end, prior_local_end


def _productive_history(reader, blobs, inputs, uses, originals):
    """Connect actual phase metadata/use files, not merely consistent blob hashes."""
    index = D.canonical(reader.handoff.raw)
    returns = index["chain"]["returns"]
    clock, boot = O.clock_value(inputs.clock), inputs.history["originalBootDigest"]
    previous_raw, previous_ns, previous_local = inputs.closed_raw, inputs.previous_ns, inputs.previous_local
    keys = ("stage", "seed", "custody", "producer", "collection", "no-loader", "export", "before")
    for phase, key, use in zip(D.PRODUCTIVE_PHASES, keys, uses):
        parent = D.canonical(blobs[key + "-parent.json"])
        returned = returns[phase]
        leaf_raw = blobs["producer-observation.json" if phase == "configuration" else key + "-leaf.json"]
        leaf = D.canonical(leaf_raw)
        require(type(parent["schema"]) is int and parent["schema"] == 1 and parent["phase"] == phase and
            parent["scope"] == (D.STAGING_PARENT_SCOPE if key in ("stage", "seed") else D.PARENT_SCOPE) and
            parent["predecessorSha256"] == O.digest(previous_raw) and
            O.integer(parent["predecessorCheckedNs"]) == previous_ns and
            parent["leafSha256"] == O.digest(leaf_raw) and
            parent["parentResourceClose"] == "KNOWN_RESOURCE_CLOSE_ONLY" and
            type(parent["resourceCount"]) is int and 0 < parent["resourceCount"] <= F.MEMBER_LIMIT and
            parent["nextPhaseAuthority"] is False, "PRODUCTIVE_ORIGINAL_PARENT")
        D.nonacceptance(parent)
        if phase == "configuration":
            D.fields(parent, "schema scope phase window predecessorSha256 predecessorCheckedNs requestSha256 observationSha256 "
                "commandSha256 nativeSha256 leafSha256 closedNs originalExitCode nativeRetirement resourceCount "
                "parentResourceClose freshUseSha256 budgetAcceptance testAcceptance nextPhaseAuthority exportSaveAuthority")
            for field, name in (("requestSha256", "producer-request.json"), ("observationSha256", "producer-observation.json"),
                                ("commandSha256", "producer-command.json"), ("nativeSha256", "producer-native.json")):
                require(parent[field] == O.digest(blobs[name]), "PRODUCTIVE_CANONICAL_ORIGINAL_HASH")
            require(type(parent["originalExitCode"]) is int and parent["originalExitCode"] == 0 and
                parent["nativeRetirement"] == "KNOWN_ORIGINAL_SCOPE_CLOSE", "PRODUCTIVE_NATIVE_RETURN")
            window = parent["window"]
        else:
            pending_raw = originals[phase, "pending"]
            pending = D.fields(D.canonical(pending_raw), "schema scope phase binding leafSha256 useSha256 window "
                "ownerClose nextPhaseAuthority exportSaveAuthority")
            require(type(pending["schema"]) is int and pending["schema"] == 1 and
                pending["scope"] == "INITIAL_RECIPIENT_PRODUCTIVE_LEAF_PENDING_OWNER_CLOSE_V1" and pending["phase"] == phase and
                pending["leafSha256"] == O.digest(leaf_raw) and pending["useSha256"] == use["returnSha256"] and
                pending["ownerClose"] == D.PENDING and pending["nextPhaseAuthority"] is pending["exportSaveAuthority"] is False and
                parent["pendingSha256"] == O.digest(pending_raw), "PRODUCTIVE_ORIGINAL_PENDING_FILE")
            D.same(pending["binding"], inputs.binding(), "PRODUCTIVE_PENDING_INITIAL_BINDING")
            window = pending["window"] if key in ("stage", "seed") else parent["window"]
            D.same(pending["window"], {**window, "phases": window["phases"][:1]}, "PRODUCTIVE_PENDING_WORK_ONLY")
            fields = ("schema scope phase window pendingSha256 predecessorSha256 predecessorCheckedNs leafSha256 leafCheckedNs "
                "closedNs resourceCount parentResourceClose nextPhaseAuthority budgetAcceptance testAcceptance exportSaveAuthority")
            if key not in ("stage", "seed"):
                fields += " clock firstNs hardEndNs softEndNs freshUseSha256"
            if phase == "save-set-before":
                fields += " exportParentSha256"
                require(parent["exportParentSha256"] == O.digest(previous_raw), "PRODUCTIVE_BEFORE_EXPORT_PARENT")
            D.fields(parent, fields)
            require(O.integer(parent["leafCheckedNs"]) <= O.integer(parent["closedNs"]), "PRODUCTIVE_LEAF_BEFORE_CLOSE")
        work, hard, local_end = _productive_window(window, phase, inputs.proposal, clock, boot)
        began, local = window["firstNs"], window["localStarted"]
        soft = min(work, began + _PHASES[phase][0][2] * NS)
        require(previous_ns <= began and previous_local <= local and
            O.integer(use["window"]["parentFirstNs"]) == began and O.integer(use["window"]["parentWorkEndNs"]) == soft and
            use["return"]["closedNs"] <= returned["leaf"]["checkedNs"] <= returned["checkedNs"] and
            began <= O.integer(parent["closedNs"]) <= returned["checkedNs"] < hard and
            local <= D.local(returned["checkedLocal"]) < local_end, "PRODUCTIVE_ORIGINAL_CONTAINMENT")
        if key in ("stage", "seed"):
            D.same(parent["window"], {"phase": phase, "clock": clock, "firstNs": began, "softEndNs": soft,
                "hardEndNs": work, "budgetAcceptance": "NOT_ADMITTED"}, "PRODUCTIVE_STAGE_WINDOW")
        else:
            require(parent["freshUseSha256"] == use["returnSha256"], "PRODUCTIVE_PARENT_FRESH_USE")
            if phase != "configuration":
                D.same({name: parent[name] for name in ("clock", "firstNs", "hardEndNs", "softEndNs")},
                    {"clock": clock, "firstNs": began, "hardEndNs": work, "softEndNs": soft}, "PRODUCTIVE_PARENT_WORK")
        if "window" in leaf:
            require(leaf["window"]["firstNs"] == began and leaf["window"]["clock"] == clock and
                use["return"]["closedNs"] <= O.integer(leaf["window"]["finishedNs"]) <= returned["leaf"]["checkedNs"],
                "PRODUCTIVE_USE_BEFORE_LEAF")
        previous_raw, previous_ns, previous_local = blobs[key + "-parent.json"], returned["checkedNs"], returned["checkedLocal"]
    handoff_use = uses[-1]
    require(handoff_use["window"]["parentFirstNs"] == index["window"]["firstNs"] and
        handoff_use["window"]["parentWorkEndNs"] == index["window"]["hardEndNs"] and
        previous_ns <= index["window"]["firstNs"] and previous_local <= index["window"]["localStarted"] and
        handoff_use["return"]["closedNs"] <= D.canonical(reader.handoff.producer_return_raw)["handoffReturnedNs"],
        "PRODUCTIVE_HANDOFF_FRESH_USE")
    native = D.fields(D.canonical(blobs["producer-native.json"]), "schema scope start baseline birth leader preparer terminal "
        "window originalExitCode workCompletedNs finalizedNs captures directory directoryIdentity nativeClose providerExecution exportSaveAuthority")
    path = inputs.session / "initial-product-04"
    require(type(native["schema"]) is int and native["schema"] == 1 and
        native["scope"] == "INITIAL_RECIPIENT_CONFIGURATION_ORIGINAL_NATIVE_V1" and
        native["directory"] == str(path) and type(native["originalExitCode"]) is int and native["originalExitCode"] == 0 and
        native["nativeClose"] == "ORIGINAL_SCOPE_CLOSED_BEFORE_READ" and native["providerExecution"] == "NOT_PERFORMED" and
        native["exportSaveAuthority"] is False, "PRODUCTIVE_ORIGINAL_NATIVE_RECORD")
    _read_root(reader, path, D.native_identity(native["directoryIdentity"], inputs.role))
    parent = D.canonical(blobs["producer-parent.json"])
    require(native["window"] == parent["window"] and type(native["captures"]) is dict and
            set(native["captures"]) == {"stdout", "stderr"}, "PRODUCTIVE_NATIVE_WINDOW_AND_CAPTURES")
    command = D.canonical(blobs["producer-command.json"])
    require(originals["configuration", "command"] == blobs["producer-command.json"] and
        originals["configuration", "request"] == blobs["producer-request.json"] and
        originals["configuration", "outer-start"] == O.encoded(native["start"]) and
        originals["configuration", "baseline"] == O.encoded(native["baseline"]) and
        originals["configuration", "native-result"] == blobs["producer-native.json"] and
        originals["configuration", "canonical-observation"] == blobs["producer-observation.json"] and
        command["scope"] == producer_command.INITIAL_SCOPE and command["requestBytes"].encode("ascii") ==
        blobs["producer-request.json"], "PRODUCTIVE_NATIVE_ACTUAL_FILES")
    start = D.fields(native["start"], "schema scope contextSha256 argv cwd role job invocation state home inheritedContext "
        "startedNs workEndNs finalEndNs exitCode launchAttempted scopeAttempted retirement")
    require(type(start["schema"]) is int and start["schema"] == 1 and
        start["scope"] == "INITIAL_RECIPIENT_CONFIGURATION_PARENT_PRELAUNCH_V1" and start["exitCode"] is None and
        start["launchAttempted"] is start["scopeAttempted"] is False and start["retirement"] == "UNKNOWN",
        "PRODUCTIVE_ORIGINAL_PRELAUNCH")
    native_start = D.fields(D.canonical(originals["configuration", "native-start"]), "ownership leader preparerIdentity observedNs")
    require(native_start["ownership"] == native["birth"] and native_start["leader"] == native["leader"] and
        native_start["preparerIdentity"] == native["preparer"] and
        uses[3]["return"]["closedNs"] <= O.integer(native_start["observedNs"]) <= O.integer(native["workCompletedNs"]) <
        native["window"]["phases"][0]["endNs"] and
        native["workCompletedNs"] <= native["window"]["phases"][1]["startedNs"] and
        native["window"]["phases"][2]["startedNs"] <= O.integer(native["finalizedNs"]) <=
        native["window"]["phases"][3]["startedNs"] and
        start["startedNs"] == native["window"]["firstNs"] and start["workEndNs"] == native["window"]["globalEndsNs"][0] and
        start["finalEndNs"] == native["window"]["globalEndsNs"][2] and start["argv"] == command["argv"] and
        start["cwd"] == str(ROOT) and start["state"] == str(inputs.state) and start["home"] == str(inputs.home) and
        start["contextSha256"] == O.digest(inputs.canonical_raw) and start["role"] == inputs.role and
        start["job"] == inputs.canonical["id"], "PRODUCTIVE_NATIVE_ACTUAL_ORDER")
    B.native_record(native["birth"], start, native["leader"], command["argv"], terminal=False)
    B.native_record(native["terminal"], start, native["leader"], command["argv"])
    require(native["birth"]["launches"] == native["terminal"]["launches"] and
        B.closed_lifetime(native["preparer"], inputs.role)["pid"] != native["leader"]["pid"], "PRODUCTIVE_NATIVE_LIFETIME")
    B.baseline_record(O.encoded(native["baseline"]), inputs.role)
    total, identities = 0, set()
    for name in ("stdout", "stderr"):
        row = D.fields(native["captures"][name], "bytes sha256 readNs identity fileBinding")
        pin = D.native_identity(row["identity"], inputs.role)
        require(pin not in identities and row["fileBinding"]["identity"] == list(pin) and
            native["window"]["phases"][3]["startedNs"] <= O.integer(row["readNs"]) <= parent["closedNs"],
            "PRODUCTIVE_CLOSED_CAPTURE_REFERENCE")
        identities.add(pin)
        _read_capture_original(reader, path, name + ".log", row["bytes"], row["sha256"], O.encoded(row["fileBinding"]))
        total += row["bytes"]
    require(total <= 134348800, "PRODUCTIVE_CAPTURE_AGGREGATE")


def _read_use(reader, row, site, prefix_hash, worker, history_raw):
    """Historical38 original files + full281 declarations, not full native custody."""
    import hosted_cache_provider_readback as readback
    D.fields(row, "site root return inventory window returnSha256 inventorySha256 originalsSha256")
    path = P._path(site)  # No JSON root/relative path is ever used as a native path.
    require(row["site"] == site and row["root"] == str(path) and
        row["returnSha256"] == O.digest(O.encoded(row["return"])) and
        row["inventorySha256"] == O.digest(O.encoded(row["inventory"])), "HISTORICAL_USE_BINDING")
    clock, window = U.checked_frame(row["window"])
    returned = D.fields(row["return"], "schema scope site windowSha256 workerIdentitySha256 inventorySha256 "
        "pendingSha256 originalChain preCloseNs closedNs resourceCount retirement budgetAcceptance exportSaveAuthority")
    history = D.canonical(history_raw)
    require(type(returned["schema"]) is int and returned["schema"] == 1 and returned["scope"] == U.RETURN_SCOPE and
        returned["site"] == site and returned["windowSha256"] == O.digest(O.encoded(row["window"])) and
        returned["workerIdentitySha256"] == O.digest(worker.record) and
        returned["inventorySha256"] == row["inventorySha256"] and
        returned["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and returned["budgetAcceptance"] == "NOT_ADMITTED" and
        returned["exportSaveAuthority"] is False and clock == reader.first.clock and
        window["originalBootDigest"] == history["originalBootDigest"] and
        window["firstNs"] <= O.integer(returned["preCloseNs"]) <= O.integer(returned["closedNs"]) < window["workEndNs"] and
        returned["closedNs"] <= reader.first.nanoseconds and type(returned["resourceCount"]) is int and
        0 < returned["resourceCount"] <= F.MEMBER_LIMIT, "HISTORICAL_USE_RETURN")
    readback._initial_use_index(row["inventory"], path, site, row["window"], returned)
    indexed = {value["relative"]: value for value in row["inventory"]["files"]}
    pins = {value["relative"]: value["identity"] for value in row["inventory"]["directories"] if value["identity"] is not None}
    names = ("use-window.json", "context.json", "service/child-result.json", "acquisition-queries/session-result.json",
        *("service/" + name for name in sorted(B.PHASE_FILES)),
        *("acquisition-queries/" + name + ".bin" for name in N.ORIGINAL_KEYS),
        *(section + "/" + name for section in ("source-before", "source-after") for name in
          ("source-return.json", "session-result.json", *(key + ".bin" for key in N.SOURCE_KEYS))), "use-pending.json")
    require(len(names) == len(set(names)) == 38 and type(row["originalsSha256"]) is dict and
            set(row["originalsSha256"]) == set(names), "FIXED_USE_ORIGINALS_ROSTER")
    for relative in (".", "control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries"):
        _read_root(reader, path if relative == "." else path / relative, pins[relative])
    originals = {}
    for name in names:
        parts = name.split("/")
        record = indexed[name]
        maximum = (B.ACK_LIMIT if name == "service/stdout.log" else B.STDERR_LIMIT if name == "service/stderr.log" else
                   P.Q.MAX_RECEIPT_BYTES if parts[0] in ("source-before", "source-after", "acquisition-queries") and
                       parts[-1] != "source-return.json" else B.LIMIT)
        raw = _read_file(reader, path.joinpath(*parts[:-1]), parts[-1], maximum)
        require(len(raw) == record["bytes"] and O.digest(raw) == record["sha256"] == row["originalsSha256"][name],
                "ORIGINAL_USE_FILE_CHANGED")
        originals[name] = raw
    require(originals["use-window.json"] == O.encoded(row["window"]), "USE_ORIGINAL_WINDOW_CHANGED")
    context, expected, event = P._context(originals["context.json"], path, reader.first,
        history["originalBootDigest"], site, window)
    pending = D.fields(D.canonical(originals["use-pending.json"]), "schema scope site windowSha256 prefixSha256 "
        "workerIdentitySha256 matchSha256 filesSha256 originalChain retainedNs retirement exportSaveAuthority")
    require(context["scope"] == U.site_scope(site) and context["site"] == site and context["window"] == row["window"] and
        context["session"] == str(path) and context["root"] == str(ROOT) and
        context["prefixSha256"] == pending["prefixSha256"] == prefix_hash and
        context["history"] == history and context["expectedMatch"] == D.canonical(worker.record)["initialRecipient"] and
        event == worker.original_event and context["eventSha256"] == O.digest(event) and
        context["initializer"] == str(reader.handoff.initializer) and
        context["initializerIdentity"] == list(reader.handoff.initializer_identity) and context["directoryIdentity"] == pins["."] and
        O.encoded(context["originalProposal"]) == reader.handoff.proposal and type(pending["schema"]) is int and
        pending["schema"] == 1 and pending["scope"] == "INITIAL_RECIPIENT_PER_USE_PENDING_OWNER_CLOSE_V1" and
        pending["site"] == site and pending["windowSha256"] == returned["windowSha256"] and
        pending["workerIdentitySha256"] == returned["workerIdentitySha256"] and
        pending["matchSha256"] == O.digest(expected.record) and pending["originalChain"] == returned["originalChain"] and
        pending["retirement"] == "PENDING_OWNER_CLOSE" and pending["exportSaveAuthority"] is False and
        pending["filesSha256"] == {name: O.digest(raw) for name, raw in originals.items() if name != "use-pending.json"},
        "HISTORICAL_USE_CONTEXT_CHANGED")
    start, terminal, birth, child, ack = C.productive_use_phase_bytes(originals["context.json"], path, clock,
        {name: originals["service/" + name] for name in B.PHASE_FILES}, originals["service/child-result.json"],
        tuple(pins["."]), tuple(pins["service"]))
    # Exact original query order and maxima come from the three ACTUAL retained
    # sessions, not from arbitrary query-directory names in an index. The
    # maintained historical helper is DATA-only and creates no SourceReturn.
    query_view = {"session": str(path), "root": str(ROOT), "observed": context["observed"], "originalWindow": row["window"]}
    declared, declared_directories = [], [".", "control-home", "temporary", "service"]
    for side in ("source-before", "acquisition-queries", "source-after"):
        rows, directories = C._historical_query_index(query_view, side, originals)
        declared.extend(rows)
        declared_directories.extend(directories)
    for name in ("use-window.json", "context.json", "use-pending.json", "service/child-result.json",
                 *("service/" + name for name in B.PHASE_FILES)):
        raw = originals[name]
        maximum = B.ACK_LIMIT if name == "service/stdout.log" else B.STDERR_LIMIT if name == "service/stderr.log" else B.LIMIT
        declared.append((name, maximum, len(raw), O.digest(raw)))
    require(len(declared) == len({name for name, *_rest in declared}) == 281 and
        len(declared_directories) == len(set(declared_directories)) == 58 and
        sorted(declared_directories) == [entry["relative"] for entry in row["inventory"]["directories"]] and
        row["inventory"]["files"] == [{"relative": name, "maximum": maximum, "bytes": count, "sha256": digest,
            "provenance": "ACTUAL_RETAINED_BYTES" if name in originals else "ORIGINAL_QUERY_DECLARATION"}
            for name, maximum, count, digest in sorted(declared)], "EXACT_HISTORICAL_USE_QUERY_INDEX")
    raw = {name: originals["acquisition-queries/" + name + ".bin"] for name in N.ORIGINAL_KEYS}
    source = dict(reader.handoff.source_records)
    require(raw["event"] == event and raw["match"] == expected.record and
        {name: raw[name] for name in N.SOURCE_KEYS} == source and
        all({name: originals[side + "/" + name + ".bin"] for name in N.SOURCE_KEYS} == source
            for side in ("source-before", "source-after")) and
        child["querySessionSha256"] == O.digest(originals["acquisition-queries/session-result.json"]) and
        child["originalsSha256"] == returned["originalChain"]["originalsSha256"], "HISTORICAL_USE_SOURCE_BYTES")
    supplied = (N._public_provider_match_inputs if site in U.public.SITES else N._retained_match_inputs)(
        context, raw, start["invocation"], clock, start["startedNs"], start["workEndNs"])
    match, service = N._retained_match_at(supplied, now=history["firstUseAt"])
    captured = (originals["context.json"], tuple(raw.items()), start["invocation"], start["startedNs"], start["workEndNs"])
    job = (N._public_provider_service_job if site in U.public.SITES else N._service_job)(captured, clock)
    before, after = (D.canonical(originals[side + "/source-return.json"]) for side in ("source-before", "source-after"))
    minimum = N._service_chain_minimum(window["firstNs"], context["sourceReturnedNs"], start, terminal, birth, child, service, ack)
    require(match.record == expected.record and list(job) == history["serviceJob"] and
        context["sourceReturnSha256"] == O.digest(originals["source-before/source-return.json"]) and
        context["sourceReturnedNs"] == before["returnedNs"] and window["firstNs"] <= O.integer(before["returnedNs"]) and
        minimum <= O.integer(after["returnedNs"]) <= O.integer(returned["originalChain"]["checkedNs"]) <=
        O.integer(pending["retainedNs"]) <= returned["preCloseNs"], "HISTORICAL_USE_CHAIN_TIME")
    reader.owner.end()
    return originals


def _read_productive_graph(reader, blobs, inputs):
    index = D.canonical(reader.handoff.raw)
    refs = D.fields(index["references"], "initializerFiles staging phaseOriginals")
    require(type(refs["initializerFiles"]) is dict and set(refs["initializerFiles"]) == set(D.INITIALIZER_FILES),
            "INITIAL_ORIGINAL_FILES_REQUIRED")
    for name, raw in inputs.initializer_originals:
        row = D.fields(refs["initializerFiles"][name], "bytes sha256 fileBinding")
        require(type(row["bytes"]) is int and row["bytes"] == len(raw) and row["sha256"] == O.digest(raw) and
                F._file_binding(row["fileBinding"]), "INITIAL_ORIGINAL_REFERENCE")
        parts = name.split("/")[1:]
        _read_file(reader, inputs.session.joinpath(*parts[:-1]), parts[-1], expected=raw, binding=row["fileBinding"])
    phase_files = {name: (("pending", "leaf-return-pending.json"),) for name in D.PRODUCTIVE_PHASES}
    phase_files["configuration"] = (("command", "command.json"), ("request", "request.json"), ("outer-start", "outer-start.json"),
        ("baseline", "baseline.json"), ("native-start", "native-start.json"), ("native-result", "native-result.json"),
        ("canonical-observation", "canonical-observation.json"))
    require(type(refs["phaseOriginals"]) is dict and set(refs["phaseOriginals"]) == set(phase_files), "PHASE_REFERENCE_ROSTER")
    actuals = {}
    for number, phase in enumerate(D.PRODUCTIVE_PHASES, 1):
        directory = inputs.session / ("initial-product-" + str(number).zfill(2))
        rows = refs["phaseOriginals"][phase]
        require(type(rows) is list and len(rows) == len(phase_files[phase]), "PHASE_ORIGINAL_FILES")
        for row, (key, name) in zip(rows, phase_files[phase]):
            D.fields(row, "key directory directoryIdentity name bytes sha256 fileBinding")
            require(row["key"] == key and row["directory"] == str(directory) and row["name"] == name and
                    F._file_binding(row["fileBinding"]), "PHASE_ORIGINAL_PATH")
            _read_root(reader, directory, row["directoryIdentity"])
            raw = _read_file(reader, directory, name, binding=row["fileBinding"])
            require(type(row["bytes"]) is int and row["bytes"] == len(raw) and row["sha256"] == O.digest(raw), "PHASE_BYTES_CHANGED")
            actuals[phase, key] = raw
    uses = D.fields(D.canonical(blobs["productive-use-index.json"]), "schema scope sites inputProvenance exportSaveAuthority")
    require(type(uses["schema"]) is int and uses["schema"] == 1 and
        uses["scope"] == "INITIAL_RECIPIENT_PRODUCTIVE_ORIGINAL_USE_INDEX_V1" and
        uses["inputProvenance"] == "HISTORICAL_CONSUMED_RETURNS_NOT_CURRENT_AUTHORITY" and
        uses["exportSaveAuthority"] is False and type(uses["sites"]) is list and len(uses["sites"]) == 9,
        "PRODUCTIVE_ORIGINAL_USE_ROSTER")
    for row, site in zip(uses["sites"], U.PRODUCTIVE_SITES):
        _read_use(reader, row, site, O.digest(inputs.closed_raw), inputs.admitted, inputs.history_raw)
    _productive_history(reader, blobs, inputs, uses["sites"], actuals)
    return refs


def read_productive_handoff(owner, first, claims):
    """ONE actual fixed read graph for all initial Step/provider parents."""
    if id(owner) in _READERS:
        original = _READERS[id(owner)]
        error = O.OriginError("INITIAL_ADAPTER_HANDOFF_READER_REENTRY")
        owner.error("initial-handoff-reader-reentry", error)
        _poison(original, "failure", owner.original if owner.original is not None else error)
        raise original.failure
    reader = _reader_state(owner, first, claims)
    _READERS[id(owner)] = reader
    try:
        path = N._receiving_path()
        initial = _read_root(reader, path)
        directory = _read_root(reader, path / "dependency-save-handoff")
        raw = _read_file(reader, directory.path, "save-handoff.json")
        index = D.canonical(raw)
        require(index.get("scope") == D.HANDOFF_SCOPE and O.digest(raw) == claims["HANDOFF_SHA256"] and
                claims["PRODUCER_OUTCOME"] == "success", "ORIGINAL_HANDOFF_CLAIMS")
        proposal_raw = _read_file(reader, directory.path, "allocation-proposal.json")
        D.same(index["blobs"]["allocation-proposal.json"],
            {"bytes": len(proposal_raw), "sha256": O.digest(proposal_raw)}, "EARLY_ORIGINAL_PROPOSAL_HASH")
        if type(owner) is _Owner:
            state = _owner_state(owner).phase
            require(state.run.operation in _STEPS and state.name == _STEPS[state.run.operation] and
                    state.first is first and state.run.prefix is None, "STEP_INITIAL_READER_POSITION")
            # Denial only. Later exact original source/service rederivation
            # MUST match these bytes; they cannot grant or extend this first.
            _shorten(state, D.canonical(proposal_raw))
        blobs = {name: _read_file(reader, directory.path, name) for name in D.BLOB_NAMES}
        history = D.canonical(blobs["history.json"])
        observed, _primary, event = N.host_context(history["firstUseAt"])
        require(observed == history["observed"] and observed["kind"] == "worker", "HANDOFF_ORIGINAL_HOST")
        worker_value = D.canonical(blobs["worker-identity.json"])
        worker = N.initial_identity.bind_worker_match(N.acquisition.stages.BootstrapMatch(O.encoded(worker_value["initialRecipient"])),
            event_raw=event, policy_raw=blobs["candidate_policy_raw.bin"], now=history["firstUseAt"])
        require(worker.record == blobs["worker-identity.json"], "HANDOFF_INITIAL_IDENTITY_CHANGED")
        original = D.fields(D.canonical(blobs["initial-inputs.json"]), "schema scope binding initializerCheckedLocal")
        require(type(original["schema"]) is int and original["schema"] == 1 and original["scope"] == D.INPUT_SCOPE,
                "HANDOFF_INITIAL_INPUTS")
        binding = original["binding"]
        pins = binding["allInitializerDirectories"]
        require(type(pins) is dict and set(pins) == set(D.INITIALIZER_DIRECTORIES), "HANDOFF_INITIAL_DIRECTORIES")
        directories = tuple((name, D.native_identity(pins[name]["identity"], first.clock.role), pins[name]["provenance"])
                            for name in sorted(pins))
        for name, pin, _provenance in directories:
            _read_root(reader, path.joinpath(*name.split("/")[1:]), pin)
        originals = tuple((name, _read_file(reader, path.joinpath(*name.split("/")[1:-1]), name.split("/")[-1]))
                          for name in D.INITIALIZER_FILES)
        dto = D.InitialOriginals(worker, blobs["history.json"], blobs["allocation-proposal.json"], blobs["retired-prefix.json"],
            tuple((name, blobs[name + ".bin"]) for name in N.SOURCE_KEYS), str(path), originals, directories,
            binding["initializerCheckedNs"], original["initializerCheckedLocal"])
        inputs = D.InitialInputs(dto, D.capture_originals(dto))
        D.same(inputs.binding(), binding, "HANDOFF_INPUTS_CHANGED")
        D.handoff_record(raw, blobs, inputs, first, claims, directory.path, tuple(directory.identity))
        return_raw = _read_file(reader, path, "producer-function-return.json")
        D.producer_return_record(return_raw, raw, inputs, first, claims["PRODUCER_RETURN_SHA256"], tuple(directory.identity))
        result = HandoffInputs(raw, worker, dto.history_raw, dto.proposal_raw, dto.source_records, path,
            tuple(initial.identity), return_raw, tuple((name, blobs[name]) for name in D.BLOB_NAMES), dto)
        _progress(reader, handoff=result)
        _read_productive_graph(reader, blobs, inputs)
        _names(owner, directory, (*D.BLOB_NAMES, "save-handoff.json"))
        _progress(reader, graph=N._history_graph(result.__dict__, worker.__dict__, dto.__dict__, reader.claims, reader.first,
            tuple((key, raw, stamp, maximum) for key, (raw, stamp, maximum) in reader.files.items())))
        checked_handoff_inputs(owner, result)
        owner.end()
        return result
    except BaseException as error:
        raise _reader_failure(reader, "initial-handoff-reader", error)


def _checked_handoff(handoff):
    matches = [reader for reader in _READERS.values() if _original(reader, "handoff") is handoff]
    require(len(matches) == 1, "NOT_ORIGINAL_HANDOFF_INPUTS")
    reader = matches[0]
    try:
        require(type(handoff) is HandoffInputs, "ORIGINAL_HANDOFF_INPUT_KIND_CHANGED")
        _reader_passive(reader)
        require(reader.handoff is handoff, "HANDOFF_INPUTS_CHANGED")
        return reader
    except BaseException as error:
        raise _reader_failure(reader, "initial-handoff-original", error)


def checked_handoff_inputs(owner, handoff):
    """Passive original reader/graph check ONLY; no old owner.end/window.now."""
    reader = _checked_handoff(handoff)
    require(reader.owner is owner and _READERS.get(id(owner)) is reader, "HANDOFF_INPUTS_FOREIGN_OWNER")
    return handoff


@dataclass(frozen=True, repr=False)
class ProviderInputs:
    plan: dict
    inputs: object
    handoff: object
    source_inputs: dict
    staging_raw: bytes


def _historical_inputs(handoff, staging_raw):
    blobs, index = dict(handoff.blobs), D.canonical(handoff.raw)
    returns = index["chain"]["returns"]
    def leaf(phase, name):
        row = returns[phase]["leaf"]
        return staging.LeafEvidence(blobs[name], staging_raw, row["checkedNs"], row["localStarted"], row["checkedLocal"])
    staged = custody.StagedEvidence(blobs["seed-parent.json"], blobs["stage-parent.json"],
        leaf("dependency-stage", "stage-leaf.json"), leaf("empty-seed", "seed-leaf.json"),
        returns["empty-seed"]["checkedNs"], returns["empty-seed"]["checkedLocal"])
    return custody._InitialInputs(handoff.originals, D.capture_originals(handoff.originals), staged, custody._capture_staged(staged))


def rederive_provider_inputs(owner, handoff, fresh_identity):
    """Explicit fresh identity + actual source/staging/initial-input rederivation."""
    reader = _checked_handoff(handoff)
    try:
        require(reader.owner is owner and id(handoff) not in _DERIVES and id(handoff) not in _INPUTS and
                not owner.closed, "PROVIDER_INPUT_REENTRY_OR_OWNER")
        _DERIVES[id(handoff)] = handoff, owner, fresh_identity  # Consume BEFORE callbacks or rederivation.
        _fresh_begin(reader, fresh_identity)
        return _rederive_inputs(reader, fresh_identity)
    except BaseException as error:
        raise _reader_failure(reader, "initial-input-rederivation", error)


def _reader_failure(reader, stage, error):
    owner = _original(reader, "owner")
    original = _original(reader, "failure")
    if original is None:
        original = owner.original if owner.original is not None else error
        _poison(reader, "failure", original)
    owner.error(stage, original)
    return original


def _fresh_begin(reader, fresh_identity):
    """Equality of a supplied identity is NEVER evidence of a fresh begin-use."""
    owner, handoff = reader.owner, reader.handoff
    _reader_passive(reader, allow_closed=False)
    if type(owner) is _Owner:
        state = _owner_state(owner).phase
        _current(state)
        require(state.run.operation in _STEPS and state.name == _STEPS[state.run.operation] and
            state.run.prefix is handoff and state.first is reader.first and state.owner is owner and
            state.site is state.binding is state.inputs is None and len(state.uses) == 1,
            "ACTUAL_STEP_BEGIN_REQUIRED")
        site, parent, uses = state.run.operation + "/begin", state.parent, state.uses
    else:
        import hosted_cache_provider_native as provider
        entry = provider._INITIAL_ENTRY
        require(type(entry) is tuple and len(entry) == 4 and provider.P is P and provider.B is B,
                "ACTUAL_PROVIDER_REGISTRY_REQUIRED")
        state = provider._initial_state(entry[3])
        provider._initial_parent_current(state)
        require(state.owner is owner and state.handoff is handoff and state.first is reader.first and
            len(state.uses) == 1 and state.site is state.use_binding is state.materialized is state.chain is
            state.inputs is None, "ACTUAL_PROVIDER_BEGIN_REQUIRED")
        site = ("provider-save" if state.phase == "save" else "provider-probe") + "/native-prepare/begin"
        parent, uses = state.parent, state.uses
    result = uses[0]
    require(result.site == site and result.identity is fresh_identity and
        P.checked_consumed_use(result, parent, site) is result, "SAME_AUTHENTIC_CONSUMED_BEGIN_REQUIRED")
    require(D.worker_values(fresh_identity) == D.worker_values(handoff.identity), "FRESH_INITIAL_IDENTITY_CHANGED")


def _rederive_inputs(reader, fresh_identity):
    owner, handoff = reader.owner, reader.handoff
    require(D.worker_values(fresh_identity) == D.worker_values(handoff.identity), "FRESH_INITIAL_IDENTITY_CHANGED")
    basic = D.InitialInputs(handoff.originals, D.capture_originals(handoff.originals))
    index, blobs = D.canonical(handoff.raw), dict(handoff.blobs)
    proposal = D.original_proposal(handoff.proposal, fresh_identity, handoff.history, reader.first.clock)
    reference = D.fields(index["references"]["staging"], "directory directoryIdentity name bytes sha256 fileBinding")
    require(reference["directory"] == str(basic.container) and reference["name"] == "staging.json" and
            F._file_binding(reference["fileBinding"]), "ORIGINAL_STAGING_REFERENCE")
    container = _read_root(reader, basic.container, reference["directoryIdentity"])
    staging_raw = _read_file(reader, basic.container, "staging.json", binding=reference["fileBinding"])
    require(type(reference["bytes"]) is int and reference["bytes"] == len(staging_raw) and
            reference["sha256"] == O.digest(staging_raw), "ORIGINAL_STAGING_CHANGED")
    inputs = _historical_inputs(handoff, staging_raw)
    sources, compiled, extra = staging._sources(_Reader(owner), inputs)
    require(sources == inputs.stage_value["inputs"] and extra == inputs.stage_value["bootstrapInputs"], "ORIGINAL_SOURCE_INPUTS_CHANGED")
    restore = _read_root(reader, inputs.restore, inputs.stage["sourceIdentity"])
    F.validate_stage(inputs.stage, inputs.admitted.record, inputs.profile, inputs.role, inputs.container,
        container.verify(), restore.verify(), sources)
    plan = staging.cache.validate_plan(index["plan"], fresh_identity.record, staging_raw, compiled, sources,
        session=inputs.session, profile=inputs.profile, role=inputs.role, mode="bootstrap")
    # Maintained pure whole-inventory predicate, not a fake old transition.
    B._save_original_inventory(index, blobs, compiled, inputs.stage, reference["fileBinding"], proposal)
    request = producer.parse(blobs["producer-request.json"])
    expected = producer.make_initial_recipient_request(fresh_identity.record, inputs.canonical_raw,
        invocation=request["id"], ancestor_invocations=request["ancestorInvocationIds"])
    require(blobs["producer-request.json"] == O.encoded(expected), "ORIGINAL_INITIAL_PRODUCER_REQUEST")
    require(producer_command.initial_recipient_command_request(fresh_identity.record, inputs.canonical_raw,
        invocation=request["id"], ancestor_invocations=request["ancestorInvocationIds"]) == blobs["producer-command.json"],
        "ORIGINAL_INITIAL_PRODUCER_COMMAND")
    evidence = inputs.state / "evidence" / request["id"]
    originals = {name: _read_file(reader, evidence, name, producer.LIMIT) for name in collection.METADATA}
    start, receipt, manifest = (originals[name] for name in collection.METADATA)
    producer.validate_initial_recipient_observation(producer.parse(blobs["producer-observation.json"]),
        blobs["producer-request.json"], fresh_identity.record, inputs.canonical_raw, start, receipt, original_exit_code=0)
    collection.inventory.validate_initial_recipient_inventory(blobs["collection-inventory.json"],
        blobs["producer-request.json"], fresh_identity.record, inputs.canonical_raw, start, receipt, manifest, original_exit_code=0)
    native = D.canonical(blobs["producer-native.json"])
    require(native["scope"] == "INITIAL_RECIPIENT_CONFIGURATION_ORIGINAL_NATIVE_V1" and
        type(native["originalExitCode"]) is int and native["originalExitCode"] == 0 and
        native["nativeClose"] == "ORIGINAL_SCOPE_CLOSED_BEFORE_READ" and native["providerExecution"] == "NOT_PERFORMED" and
        native["exportSaveAuthority"] is False, "ORIGINAL_NATIVE_DATA")
    require(producer.parse(start)["controllerPid"] == producer.parse(receipt)["controllerPid"] == native["leader"]["pid"],
            "ORIGINAL_CANONICAL_CONTROLLER")
    B.native_record(native["birth"], native["start"], native["leader"], native["start"]["argv"], terminal=False)
    B.native_record(native["terminal"], native["start"], native["leader"], native["start"]["argv"])
    B.baseline_record(O.encoded(native["baseline"]), inputs.role)
    result = ProviderInputs(plan, inputs, handoff, sources, staging_raw)
    graph = N._history_graph(result.__dict__, inputs.__dict__, inputs.staged.__dict__, fresh_identity.__dict__)
    _INPUTS[id(handoff)] = result, reader, graph, fresh_identity, _data_pins(result)
    recheck_provider_inputs(owner, result)
    return result


def recheck_provider_inputs(owner, inputs):
    matches = [saved for saved in _INPUTS.values() if saved[0] is inputs]
    require(len(matches) == 1, "NOT_ORIGINAL_PROVIDER_INPUTS")
    saved = matches[0]
    _result, reader, graph, _fresh, records = saved
    try:
        require(type(inputs) is ProviderInputs, "PROVIDER_INPUT_KIND")
        _check_data_pins(records)
        require(saved[1].owner is owner and _INPUTS.get(id(inputs.handoff)) is saved, "ORIGINAL_PROVIDER_INPUT_OWNER")
        return _recheck_inputs(reader, inputs, graph)
    except BaseException as error:
        raise _reader_failure(reader, "initial-input-recheck", error)


def _recheck_inputs(reader, inputs, graph):
    owner = reader.owner
    _reader_passive(reader, allow_closed=False)
    N._check_history(graph)
    for (path, name), (raw, binding, maximum) in tuple(reader.files.items()):
        _read_file(reader, path, name, maximum, expected=raw, binding=binding)
    for path, name, count, digest, binding_raw in reader.large:
        _read_capture_original(reader, path, name, count, digest, binding_raw)
    source, _compiled, extra = staging._sources(_Reader(owner), inputs.inputs)
    require(source == inputs.source_inputs and extra == inputs.inputs.stage_value["bootstrapInputs"], "FINAL_SOURCE_INPUTS_CHANGED")
    for directory, _kind, pin, _row, _label in reader.directories.values():
        require(tuple(directory.verify().identity) == pin, "FINAL_READ_DIRECTORY_CHANGED")
    owner.end()
    N._check_history(graph)


def _step_path(operation):
    require(operation in _STEPS, "FIXED_STEP_PATH")
    kind, primary = N.location()
    require(kind == "worker", "STEP_WORKER_ONLY")
    suffix = {"prepare-save": "save", "after-save": "after-save",
              "prepare-probe": "probe", "after-probe": "after-probe"}[operation]
    return primary.with_name(primary.name + "-" + suffix)


def _provider_inputs(owner, handoff, inputs):
    reader = _checked_handoff(handoff)
    try:
        require(reader.owner is owner and type(inputs) is ProviderInputs and inputs.handoff is handoff,
                "PREPARATION_ORIGINAL_INPUTS")
        saved = _INPUTS.get(id(handoff))
        derived = _DERIVES.get(id(handoff))
        require(type(saved) is tuple and saved[0] is inputs and saved[1] is reader and type(derived) is tuple and
            derived[0] is handoff and derived[1] is owner and derived[2] is saved[3], "PREPARATION_REGISTERED_INPUTS")
        _reader_passive(reader, allow_closed=False)
        N._check_history(saved[2])
        _check_data_pins(saved[4])
        return reader
    except BaseException as error:
        raise _reader_failure(reader, "initial-provider-originals", error)


def _private_chain_files(reader, path, handoff, inputs, operation, first, work):
    originals = {name: _read_file(reader, path, name) for name in D.STEP_USE_FILES}
    chain = D.private_chain_record(originals["private-use-chain.json"], inputs.inputs, handoff.raw, operation, first, work)
    for row, edge in zip(chain["uses"], ("begin", "final")):
        require(O.encoded(row["return"]) == originals[edge + "-use.json"] and
            O.encoded(row["inventory"]) == originals[edge + "-use-index.json"], "PRIVATE_CHAIN_ACTUAL_FILES")
        _read_use(reader, row, operation + "/" + edge, O.digest(handoff.raw), handoff.identity, handoff.history)
    return originals, chain


def _validate_preparation(reader, handoff, inputs, phase, claims, directory, raw, first):
    """Fixed native reads; `first` may be old hash-bound DATA only internally."""
    require(phase in ("save", "lookup"), "PREPARATION_PHASE")
    operation, prefix, name = (("prepare-save", "SAVE", "save-preparation.json") if phase == "save" else
                              ("prepare-probe", "PROBE", "probe-preparation.json"))
    path = _step_path(operation)
    require(directory.path == path and first.clock == reader.first.clock and first.nanoseconds <= reader.first.nanoseconds,
            "FIXED_ORIGINAL_PREPARATION_DIRECTORY_OR_FIRST")
    _read_root(reader, path, tuple(directory.identity))
    require(_read_file(reader, path, name, expected=raw) == raw and claims[prefix + "_PREPARE_OUTCOME"] == "success",
            "ORIGINAL_PREPARATION_OUTCOME")
    value = D.canonical(raw)
    originals, _chain = _private_chain_files(reader, path, handoff, inputs, operation,
        O.integer(value["firstNs"]), O.integer(value["hardEndNs"]))
    contract = staging.cache.bootstrap_provider_contract(inputs.plan, phase)
    result = D.preparation_record(raw, inputs.inputs, handoff.raw, handoff.producer_return_raw, first, phase,
        claims[prefix + "_PREPARATION_SHA256"], path, tuple(directory.identity), originals["private-use-chain.json"],
        contract, after_save_hash=claims.get("AFTER_SAVE_SHA256"))
    if phase == "lookup":
        history = _after_save_history(reader, handoff, inputs, claims)
        require(history["returned"]["recordedNs"] <= result["firstNs"], "PROBE_AFTER_ORIGINAL_SAVE_RETURN")
    reader.owner.end()
    return result


def validate_provider_preparation(owner, handoff, inputs, phase, claims, prepared_directory, preparation_raw, first):
    """Shared initial-only provider seam. Never closes its borrowed owner."""
    reader = _provider_inputs(owner, handoff, inputs)
    try:
        require(first is reader.first and claims == reader.claims, "PREPARATION_ORIGINAL_READER_FIRST")
        return _validate_preparation(reader, handoff, inputs, phase, claims, prepared_directory, preparation_raw, first)
    except BaseException as error:
        raise _reader_failure(reader, "initial-provider-preparation", error)


def _read_preparation(reader, handoff, inputs, phase, claims, first):
    operation, name = (("prepare-save", "save-preparation.json") if phase == "save" else
                       ("prepare-probe", "probe-preparation.json"))
    path = _step_path(operation)
    directory = _read_root(reader, path)
    raw = _read_file(reader, path, name)
    value = _validate_preparation(reader, handoff, inputs, phase, claims, directory, raw, first)
    return raw, value


def _action_originals(reader, handoff, inputs, phase, claims, preparation_raw, first, outputs):
    """Read actual ACK-bound packets AND their five actual native-use files.

    The public native episodes get the same38-file/full281-index validation as
    every private site. The five-file packet alone is never their native copy.
    """
    import hosted_cache_provider_readback as readback
    require(phase in ("save", "lookup") and first.clock == reader.first.clock and
        first.nanoseconds <= reader.first.nanoseconds, "ACTION_HISTORICAL_FIRST")
    path = _step_path("prepare-save" if phase == "save" else "prepare-probe")
    original = {name: _read_file(reader, path, name, 16384) for name in readback.ACTION_FILES}
    native_path = path / "native-preparation"
    native = {name: _read_file(reader, native_path, name) for name in readback.INITIAL_USE_FILES}
    readback.validate_initial_action_return(original, preparation_raw, claims, first,
        phase=phase, outputs=outputs, use_originals=native)
    chain = D.canonical(native["initial-use-chain.json"])
    require(chain["handoffSha256"] == O.digest(handoff.raw) and
        chain["producerReturnSha256"] == O.digest(handoff.producer_return_raw) and
        chain["workerIdentitySha256"] == O.digest(handoff.identity.record) and
        chain["originalBootDigest"] == inputs.inputs.history["originalBootDigest"] and
        O.integer(chain["checkedNs"]) <= O.integer(D.canonical(original["provider-readback.json"])["checkedNs"]),
        "ACTION_ORIGINAL_INITIAL_CHAIN")
    _read_root(reader, native_path, D.native_identity(chain["directoryIdentity"], first.clock.role))
    _names(reader.owner, _read_root(reader, native_path), readback.INITIAL_USE_FILES)
    for use, edge in zip(chain["uses"], ("begin", "final")):
        returned, inventory = (D.canonical(native[edge + name]) for name in ("-use.json", "-use-index.json"))
        row = {**use, "return": returned, "inventory": inventory,
            "originalsSha256": {entry["relative"]: entry["sha256"] for entry in inventory["files"]
                                 if entry["provenance"] == "ACTUAL_RETAINED_BYTES"}}
        site = ("provider-save" if phase == "save" else "provider-probe") + "/native-prepare/" + edge
        _read_use(reader, row, site, O.digest(handoff.raw), handoff.identity, handoff.history)
    reader.owner.end()
    return original, native


def _after_save_history(reader, handoff, inputs, claims):
    path = _step_path("after-save")
    directory = _read_root(reader, path)
    raw = _read_file(reader, path, "after-save-return.json")
    observations_raw = _read_file(reader, path, "save-observations.json")
    retained = {name: _read_file(reader, path, name, 16384 if name in
        ("provider-prepared.json", "provider-readback.json") else D.LIMIT) for name in D.AFTER_SAVE_FILES}
    returned, observed, readmission, parent = D.after_save_records(raw, observations_raw, retained, inputs.inputs,
        handoff.raw, handoff.producer_return_raw, claims, reader.first, path, tuple(directory.identity))
    _private_chain_files(reader, path, handoff, inputs, "after-save", readmission["window"]["firstNs"],
                         readmission["window"]["hardEndNs"])
    # DATA only: no historic owner, _parent, now(), wall time or LOCAL epoch is
    # reconstructed. All the native reads still use THIS reader's live owner.
    historical_first = O.clocks.Reading(reader.first.clock, observed["firstPostProviderNs"])
    old_claims = {name: claims[name] for name in _SAVE_CLAIMS}
    preparation_raw, prepared = _read_preparation(reader, handoff, inputs, "save", old_claims, historical_first)
    require(preparation_raw == retained["save-preparation.json"] and
        prepared["providerWindow"]["hardEndNs"] == observed["providerEndNs"], "AFTER_SAVE_ORIGINAL_PROVIDER_WINDOW")
    action, native = _action_originals(reader, handoff, inputs, "save", old_claims, preparation_raw, historical_first, {})
    require(all(retained[name] == raw for name, raw in action.items()), "AFTER_SAVE_ORIGINAL_ACTION_FILES")
    classified = staging.cache.provider_observation(inputs.plan, "save", original_outcome=old_claims["SAVE_OUTCOME"], outputs={})
    require(classified["status"] == "SAVE_SUCCEEDED_STORAGE_UNPROVEN" and
        retained["provider-save.json"] == O.encoded(classified), "AFTER_SAVE_ORIGINAL_CLASSIFICATION")
    blobs = dict(handoff.blobs)
    D.after_save_leaf(retained["after-leaf.json"], blobs["before-leaf.json"], blobs["before-parent.json"],
        D.canonical(handoff.raw), parent, handoff.proposal)
    _names(reader.owner, directory, (*D.AFTER_SAVE_FILES, "save-observations.json", "after-save-return.json"))
    return {"raw": raw, "returned": returned, "observations": observed, "files": retained,
            "observations_raw": observations_raw, "action": action, "native": native}


def _step_window(state):
    require(state.name in D.STEP_CAPS and len(state.starts) == 1 and state.phase == 0, "ORIGINAL_STEP_WINDOW")
    return {"phase": state.name, "clock": O.clock_value(state.first.clock), "originalBootDigest": state.boot,
        "firstNs": state.first.nanoseconds, "softEndNs": min(state.ends[0],
            state.first.nanoseconds + D.STEP_CAPS[state.name][1] * NS), "hardEndNs": state.ends[0],
        "localStarted": state.local, "localScope": "THIS_COMMAND_ONLY"}


def _start_step(run):
    state = _new_phase(run, _STEPS[run.operation], None)
    try:
        owner = _new_owner(state)
        handoff = read_productive_handoff(owner, state.first, run.claims)
        require(O.encoded(state.proposal) == handoff.proposal, "STEP_EARLY_PROPOSAL_REDERIVATION")
        _progress(run, prefix=handoff, history=D.canonical(handoff.history),
            graph=N._history_graph(run.claims, run.outputs, handoff.__dict__, handoff.identity.__dict__))
        require(state.first.clock == O.wire.clock_identity(run.history["clock"]) and
            state.boot == run.history["originalBootDigest"], "STEP_ORIGINAL_CLOCK_OR_BOOT")
        state.window.now()
        reader = _checked_handoff(handoff)
        if run.operation in ("after-save", "after-probe"):
            phase = "save" if run.operation == "after-save" else "probe"
            path = _step_path("prepare-save" if phase == "save" else "prepare-probe")
            raw = _read_file(reader, path, phase + "-preparation.json")
            require(O.digest(raw) == run.claims[phase.upper() + "_PREPARATION_SHA256"] and
                state.first.nanoseconds < O.integer(D.canonical(raw)["providerWindow"]["hardEndNs"]),
                "EARLIEST_POST_PROVIDER_DENIAL")
        target = owner.new(_step_path(run.operation))
        require(tuple(target.verify().identity) not in (handoff.initializer_identity,
            tuple(D.canonical(handoff.raw)["directoryIdentity"])), "STEP_TARGET_ALIAS")
        state.window.now(new=True)
        return state, reader, target
    except BaseException as error:
        raise _abort(state, error)


def _step_inputs(state, token):
    identity = _use(state, state.run.operation + "/begin", token)
    result = rederive_provider_inputs(state.owner, state.run.prefix, identity)
    _progress(state, inputs=result, graph=N._history_graph(state.proposal, result.__dict__, result.inputs.__dict__))
    return result


def _step_final_use(state, inputs, token):
    identity = _use(state, state.run.operation + "/final", token)
    require(D.worker_values(identity) == D.worker_values(state.uses[0].identity), "STEP_FINAL_IDENTITY_CHANGED")
    recheck_provider_inputs(state.owner, inputs)
    state.window.now(new=True)


def _write_private_chain(state, target):
    require(state.name == _STEPS[state.run.operation] and len(state.uses) == 2 and
            state.site is state.binding is None, "STEP_PRIVATE_CHAIN_POSITION")
    uses = [_use_data(result) for result in state.uses]
    checked = state.window.now()
    raw = O.encoded({"schema": 1, "scope": D.STEP_CHAIN_SCOPE, "operation": state.run.operation,
        "clock": O.clock_value(state.first.clock), "originalBootDigest": state.boot,
        "firstNs": state.first.nanoseconds, "workEndNs": state.ends[0],
        "handoffSha256": O.digest(state.run.prefix.raw), "uses": uses, "checkedNs": checked,
        "ownerClose": D.PENDING, "providerExecution": "NOT_PERFORMED", "exportSaveAuthority": False})
    D.private_chain_record(raw, state.inputs.inputs, state.run.prefix.raw, state.run.operation,
        state.first.nanoseconds, state.ends[0])
    originals = {"private-use-chain.json": raw}
    for use, edge in zip(state.uses, ("begin", "final")):
        originals[edge + "-use.json"], originals[edge + "-use-index.json"] = use.raw, use.inventory
    for name in D.STEP_USE_FILES:
        _artifact(state, name, target, name, originals[name])
    return raw


def _step_finish(state, inputs, previous_raw, previous_ns, *, chain_raw=None, leaf=None, historical_before=None):
    if leaf is not None:
        _LEAF_RETURNS[id(state)] = leaf
    records = _data_pins(leaf)
    state.owner.close()
    for owner in state.owners:
        _known(owner)
    state.window.now()
    _check_data_pins(records)
    raw = O.encoded({"schema": 1, "scope": D.STEP_CLOSE_SCOPE, "window": _step_window(state),
        "predecessorSha256": O.digest(previous_raw), "predecessorCheckedNs": previous_ns,
        "privateUseChainSha256": None if chain_raw is None else O.digest(chain_raw),
        "leafSha256": None if leaf is None else O.digest(leaf.raw),
        "leafCheckedNs": None if leaf is None else leaf.checked_ns,
        "leafCheckedLocal": None if leaf is None else leaf.checked_local, "historicalBefore": historical_before,
        "closedNs": state.last, "closedLocal": state.local_last,
        "resourceCount": sum(len(_OWNERS[id(owner)].resources) for owner in state.owners),
        "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY", "nextPhaseAuthority": False,
        "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
    D.step_close_record(raw, inputs.inputs, state.name)
    return _publish_return(state, raw, leaf)


def _step_output(state, scope, name, raw):
    state.owner.close()
    for owner in state.owners:
        _known(owner)
    state.window.now()
    result = _StepReturn(B.public_result(scope, name, raw), _OutputFence(), state.ends[0])
    _register_output(state, result, raw)
    result.fence.now()
    return result.public_result, result.fence, result.hard_end_ns


def _artifact_reader(state):
    require(id(state.owner) not in _READERS and state.name != _STEPS[state.run.operation], "LATER_READER_ORIGINAL_OWNER")
    reader = _reader_state(state.owner, state.first, state.run.claims)
    _READERS[id(state.owner)] = reader
    return reader


def _reread_artifacts(reader, phases):
    for phase in phases:
        for _key, directory, identity, name, raw, binding in phase.files:
            path = Path(directory)
            _read_root(reader, path, identity)
            _read_file(reader, path, name, expected=raw, binding=D.canonical(binding))
    _reader_passive(reader, allow_closed=False)


def _reread_action_files(reader, phase, preparation_raw, action, native):
    operation, name = (("prepare-save", "save-preparation.json") if phase == "save" else
                       ("prepare-probe", "probe-preparation.json"))
    path = _step_path(operation)
    _read_file(reader, path, name, expected=preparation_raw)
    for name, raw in action.items():
        _read_file(reader, path, name, 16384, expected=raw)
    for name, raw in native.items():
        _read_file(reader, path / "native-preparation", name, expected=raw)


@dataclass(frozen=True, repr=False)
class _StepMetadata:
    raw: bytes
    checked_ns: int
    local_started: float
    checked_local: float


def _provider_markers(state):
    return {"clock": O.clock_value(state.first.clock), "originalBootDigest": state.boot,
        "providerStorage": "UNPROVEN", "providerDeadlineEnforcement": "NOT_ESTABLISHED",
        "providerRetirement": "NOT_OBSERVED", "writerReturn": D.PENDING,
        "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}


def prepare_save(token, cancelled):
    return _prepare_step("prepare-save", token, cancelled)


def prepare_probe(token, cancelled):
    return _prepare_step("prepare-probe", token, cancelled)


def _prepare_step(operation, token, cancelled):
    require(operation in ("prepare-save", "prepare-probe"), "FIXED_PREPARATION_COMMAND")
    run = _new_run(operation, cancelled)
    state = None
    try:
        state, reader, target = _start_step(run)
        inputs = _step_inputs(state, token)
        history = _after_save_history(reader, run.prefix, inputs, run.claims) if operation == "prepare-probe" else None
        _step_final_use(state, inputs, token)
        chain_raw = _write_private_chain(state, target)
        handoff = run.prefix
        phase, provider, name, scope, output = (("save", "provider-save", "save-preparation.json",
            D.SAVE_PREPARATION_SCOPE, "savePreparationSha256") if operation == "prepare-save" else
            ("lookup", "provider-probe", "probe-preparation.json", D.PROBE_PREPARATION_SCOPE, "probePreparationSha256"))
        issued = state.window.now(minimum=D.canonical(handoff.producer_return_raw)["observedAfterReturnNs"])
        actual_issued = state.last_reading  # Actual Reading, not a fabricated new first or authority.
        end = min(O.integer(issued + 180 * NS), state.proposal["phaseFencesNs"][provider], state.proposal["proposedJobEndNs"])
        require(issued < end, "ORIGINAL_PROVIDER_WINDOW_EXHAUSTED")
        contract = staging.cache.bootstrap_provider_contract(inputs.plan, phase)
        value = {"schema": 1, "scope": scope,
            **{name: inputs.inputs.admission[name] for name in ("source", "github", "selection", "cacheCohort")},
            "directory": str(target.path), "directoryIdentity": list(target.identity),
            "handoffSha256": O.digest(handoff.raw), "producerReturnSha256": O.digest(handoff.producer_return_raw),
            "producerOriginalOutcome": "success", "workerIdentitySha256": O.digest(handoff.identity.record),
            "privateUseChainSha256": O.digest(chain_raw), "proposalSha256": O.digest(handoff.proposal),
            "plan": inputs.plan, "planSha256": O.digest(O.encoded(inputs.plan)),
            "clock": O.clock_value(state.first.clock), "originalBootDigest": state.boot,
            "firstNs": state.first.nanoseconds, "hardEndNs": state.ends[0],
            "producerObservedAfterReturnNs": D.canonical(handoff.producer_return_raw)["observedAfterReturnNs"],
            "providerWindow": {"issuedNs": issued, "hardEndNs": end, "actualProviderStart": "NOT_OBSERVED"},
            "providerRequest": contract["request"], "writerReturn": D.PENDING, "providerExecution": "NOT_PERFORMED",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
        if history is not None:
            require(history["returned"]["recordedNs"] <= state.first.nanoseconds, "PREPARE_PROBE_AFTER_SAVE_ORDER")
            value["afterSaveSha256"] = O.digest(history["raw"])
        raw = O.encoded(value)
        D.preparation_record(raw, inputs.inputs, handoff.raw, handoff.producer_return_raw, actual_issued, phase,
            O.digest(raw), target.path, tuple(target.identity), chain_raw, contract,
            after_save_hash=None if history is None else O.digest(history["raw"]))
        _artifact(state, name, target, name, raw)
        _names(state.owner, target, (*D.STEP_USE_FILES, name))
        recheck_provider_inputs(state.owner, inputs)
        return _step_output(state, scope, output, raw)
    except BaseException as error:
        raise _abort(state, error) if state is not None else _fail(run, error)
    finally:
        token = None


def after_save(token, cancelled):
    """Two uses in readmission120, whole after90/120, observation30, return45."""
    run = _new_run("after-save", cancelled)
    state = None
    try:
        state, reader, target = _start_step(run)
        readmission_state, target_pin = state, tuple(target.identity)
        inputs = _step_inputs(state, token)
        handoff, blobs = run.prefix, dict(run.prefix.blobs)
        preparation_raw, prepared = _read_preparation(reader, handoff, inputs, "save", run.claims, state.first)
        action, native = _action_originals(reader, handoff, inputs, "save", run.claims, preparation_raw, state.first, {})
        _progress(state, graph=N._history_graph(state.proposal, inputs.__dict__, inputs.inputs.__dict__, action, native, prepared))
        _step_final_use(state, inputs, token)
        chain_raw = _write_private_chain(state, target)
        readmission = _step_finish(state, inputs, handoff.producer_return_raw,
            D.canonical(handoff.producer_return_raw)["observedAfterReturnNs"], chain_raw=chain_raw)

        state = _new_phase(run, "save-set-after", inputs.inputs.proposal, readmission)
        after_state = state
        _new_owner(state)
        later = _artifact_reader(state)
        target = _read_root(later, _step_path("after-save"), target_pin)
        _reread_artifacts(later, (readmission_state,))
        prior = D.canonical(handoff.raw)["chain"]["returns"]["before"]
        current_floor = staging.PhaseStart(readmission_state.last_reading, readmission.checked_local)
        window = save_set._InitialAfterWindow(inputs.inputs, staging.PhaseStart(state.first, state.local),
            (blobs["before-parent.json"], prior["checkedNs"], prior["checkedLocal"]), current_process_floor=current_floor)
        _progress(state, inputs=inputs, graph=N._history_graph(inputs.__dict__, inputs.inputs.__dict__, current_floor))
        leaf = save_set.after_initial_recipient_save(state.owner, inputs.inputs, window,
            blobs["export-leaf.json"], blobs["before-leaf.json"])
        _LEAF_RETURNS[id(state)] = leaf
        leaf_graph = _data_pins(leaf)
        _artifact(state, "after-leaf.json", target, "after-leaf.json", leaf.raw)
        _reread_artifacts(later, (readmission_state, after_state))
        _check_data_pins(leaf_graph)
        old_before = {"rawSha256": O.digest(blobs["before-parent.json"]), "checkedNs": prior["checkedNs"],
            "checkedLocal": prior["checkedLocal"],
            "localScope": "ORIGINAL_PRODUCER_PROCESS_ONLY_NOT_COMPARED_WITH_THIS_COMMAND"}
        after_return = _step_finish(state, inputs, readmission.raw, readmission.checked_ns,
            leaf=leaf, historical_before=old_before)
        D.after_save_leaf(leaf.raw, blobs["before-leaf.json"], blobs["before-parent.json"], D.canonical(handoff.raw),
            D.canonical(after_return.raw), handoff.proposal)

        state = _new_phase(run, "save-observation", inputs.inputs.proposal, after_return)
        observation_state = state
        _new_owner(state)
        later = _artifact_reader(state)
        target = _read_root(later, _step_path("after-save"), target_pin)
        _reread_artifacts(later, (readmission_state, after_state))
        _reread_action_files(later, "save", preparation_raw, action, native)
        provider = staging.cache.provider_observation(inputs.plan, "save", original_outcome=run.claims["SAVE_OUTCOME"], outputs={})
        require(provider["status"] == "SAVE_SUCCEEDED_STORAGE_UNPROVEN", "SAVE_CLASSIFICATION_ONLY")
        additional = {"save-preparation.json": preparation_raw, "provider-save.json": O.encoded(provider),
            "readmission-close.json": readmission.raw, "after-parent-close.json": after_return.raw, **action}
        for name, raw in additional.items():
            _artifact(state, name, target, name, raw)
        retained = {name: _read_file(later, target.path, name, 16384 if name in action else D.LIMIT)
                    for name in D.AFTER_SAVE_FILES}
        observations_raw = O.encoded({"schema": 1, "scope": D.SAVE_OBSERVATIONS_SCOPE,
            **{name: inputs.inputs.admission[name] for name in ("source", "github", "selection", "cacheCohort")},
            "originalClaims": run.claims, "planSha256": O.digest(O.encoded(inputs.plan)),
            "firstPostProviderNs": readmission_state.first.nanoseconds, "firstPostProviderLocal": readmission_state.local,
            "providerEndNs": prepared["providerWindow"]["hardEndNs"],
            "providerTimeScope": "POST_ACTION_UPPER_BOUND_ONLY_REQUIRES_TRUSTED_SEQUENTIAL_ORIGINAL_OUTCOME",
            "files": {name: O.digest(raw) for name, raw in retained.items()}, "window": _step_window(state),
            **_provider_markers(state)})
        _artifact(state, "save-observations.json", target, "save-observations.json", observations_raw)
        state.window.now()
        metadata = _StepMetadata(observations_raw, state.last, state.local, state.local_last)
        observed_return = _step_finish(state, inputs, after_return.raw, after_return.checked_ns, leaf=metadata)

        state = _new_phase(run, "save-owner-return", inputs.inputs.proposal, observed_return)
        _new_owner(state)
        later = _artifact_reader(state)
        target = _read_root(later, _step_path("after-save"), target_pin)
        _reread_artifacts(later, (readmission_state, after_state, observation_state))
        state.window.now()
        raw = O.encoded({"schema": 1, "scope": D.AFTER_SAVE_SCOPE,
            **{name: inputs.inputs.admission[name] for name in ("source", "github", "selection", "cacheCohort")},
            "directory": str(target.path), "directoryIdentity": list(target_pin), "originalClaims": run.claims,
            "planSha256": O.digest(O.encoded(inputs.plan)), "observationsSha256": O.digest(observations_raw),
            "observationOwnerReturn": D.canonical(observed_return.raw), "returnWindow": _step_window(state),
            "recordedNs": state.last, "recordedLocal": state.local_last, **_provider_markers(state)})
        # This writer cannot validate or invent its own later Step success.
        # after_save_records is used only by a later original sequential caller.
        _artifact(state, "after-save-return.json", target, "after-save-return.json", raw)
        _names(state.owner, target, (*D.AFTER_SAVE_FILES, "save-observations.json", "after-save-return.json"))
        return _step_output(state, D.AFTER_SAVE_SCOPE, "afterSaveSha256", raw)
    except BaseException as error:
        raise _abort(state, error) if state is not None else _fail(run, error)
    finally:
        token = None


def after_probe(token, cancelled):
    """Two uses only in custody-readmission120, then fixed observation30."""
    run = _new_run("after-probe", cancelled)
    state = None
    try:
        state, reader, target = _start_step(run)
        readmission_state, target_pin = state, tuple(target.identity)
        inputs = _step_inputs(state, token)
        handoff = run.prefix
        preparation_raw, prepared = _read_preparation(reader, handoff, inputs, "lookup", run.claims, state.first)
        action, native = _action_originals(reader, handoff, inputs, "lookup", run.claims,
            preparation_raw, state.first, run.outputs)
        _progress(state, graph=N._history_graph(state.proposal, inputs.__dict__, inputs.inputs.__dict__, prepared, action, native))
        _step_final_use(state, inputs, token)
        chain_raw = _write_private_chain(state, target)
        readmission = _step_finish(state, inputs, preparation_raw, prepared["providerWindow"]["issuedNs"], chain_raw=chain_raw)

        state = _new_phase(run, "provider-observation", inputs.inputs.proposal, readmission)
        _new_owner(state)
        later = _artifact_reader(state)
        target = _read_root(later, _step_path("after-probe"), target_pin)
        _reread_artifacts(later, (readmission_state,))
        _reread_action_files(later, "lookup", preparation_raw, action, native)
        provider = staging.cache.provider_observation(inputs.plan, "lookup", original_outcome=run.claims["PROBE_OUTCOME"],
            outputs=run.outputs)
        require(provider["status"] == "REPORTED_EXACT_HIT", "PROBE_REPORTED_EXACT_HIT_REQUIRED")
        retained = {"probe-preparation.json": preparation_raw, "provider-probe.json": O.encoded(provider),
                    "readmission-close.json": readmission.raw, **action}
        for name, raw in retained.items():
            _artifact(state, name, target, name, raw)
        raw = O.encoded({"schema": 1, "scope": D.PROBE_RESULT_SCOPE,
            **{name: inputs.inputs.admission[name] for name in ("source", "github", "selection", "cacheCohort")},
            "directory": str(target.path), "directoryIdentity": list(target_pin), "originalClaims": run.claims,
            "planSha256": O.digest(O.encoded(inputs.plan)), "afterSaveSha256": run.claims["AFTER_SAVE_SHA256"],
            "firstPostProviderNs": readmission_state.first.nanoseconds, "firstPostProviderLocal": readmission_state.local,
            "providerEndNs": prepared["providerWindow"]["hardEndNs"],
            "providerTimeScope": "POST_ACTION_UPPER_BOUND_ONLY_REQUIRES_TRUSTED_SEQUENTIAL_ORIGINAL_OUTCOME",
            "privateUseChainSha256": O.digest(chain_raw), "readmissionCloseSha256": O.digest(readmission.raw),
            "files": {name: O.digest(value) for name, value in retained.items()}, "window": _step_window(state),
            "reportedExactHit": True, "cacheContentsVerified": False, "resolverVerified": False,
            **_provider_markers(state)})
        _artifact(state, "probe-result.json", target, "probe-result.json", raw)
        _names(state.owner, target, (*D.STEP_USE_FILES, *retained, "probe-result.json"))
        return _step_output(state, D.PROBE_RESULT_SCOPE, "probeSha256", raw)
    except BaseException as error:
        raise _abort(state, error) if state is not None else _fail(run, error)
    finally:
        token = None
