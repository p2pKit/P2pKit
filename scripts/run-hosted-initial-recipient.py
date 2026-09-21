#!/usr/bin/env python3
"""Dormant Stage1 native original acquisition; no Admission or execution grant.

The gate and populate worker use their actual identities. This fixed parent
owns the HTTP child and its nested read-only Git queries, reuses the maintained
native phase/finalization, and retains originals before returning a provisional
digest. No workflow invokes it. A successful command is not provider, recipient
crypto, budget, export or Stage2 qualification; original step outcome is still
required by any future caller. Both ordinary HOLDs remain separate.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass, field, replace
import importlib.util
import math
import os
from pathlib import Path
import re
import stat
import sys
import threading
import time
import uuid

sys.dont_write_bytecode = True
SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))
import hosted_initial_recipient_originals as acquisition
import hosted_initial_recipient_bootstrap_identity as initial_identity

# One fixed maintained controller, not a caller-selected plugin/command.
_spec = importlib.util.spec_from_file_location("_initial_recipient_native_owner", SCRIPTS / "run-hosted-cache-bootstrap.py")
native = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = native
_spec.loader.exec_module(native)

I, O, Q = acquisition.identity, acquisition.origin, native.query
SOURCE_KEYS = ("base_policy_entry", "ancestry_raw", "candidate_policy_entry", "candidate_policy_raw")
HTTP_KEYS = ("attempt", "jobs", "approvals", "comment", "environment", "branches", "main", "reviewed_ref")
ORIGINAL_KEYS = ("event", *SOURCE_KEYS, *HTTP_KEYS, "observation", "match")
CONTEXT_FIELDS = {"schema", "scope", "prelude", "observed", "eventSha256", "root", "session", "job",
                  "inheritedContext", "sourceReturnSha256", "sourceReturnedNs", "budgetAcceptance", "exportSaveAuthority"}
SOURCE_SCOPE = "INITIAL_RECIPIENT_SOURCE_QUERIES_RETURNED_V1"
CHILD_SCOPE = "INITIAL_RECIPIENT_ACQUISITION_PENDING_CHILD_CLOSE_V1"
RESULT_SCOPE = "INITIAL_RECIPIENT_ORIGINALS_PENDING_OWNER_CLOSE_V1"
OUTPUT_SCOPE = "INITIAL_RECIPIENT_ORIGINALS_PENDING_STEP_RETURN_V1"
TIME_SCOPE = "INITIAL_RECIPIENT_BOOTSTRAP_SERVICE_TIME_BASIS_V1"
ALLOCATION_SCOPE = "INITIAL_RECIPIENT_BOOTSTRAP_ALLOCATION_PROPOSAL_V1"
ENTRY_WINDOW_SCOPE = "INITIAL_RECIPIENT_READMISSION_SOURCE_CAP_V1"
ENTRY_CHILD_SCOPE = "INITIAL_RECIPIENT_READMISSION_PENDING_CHILD_CLOSE_V1"
ENTRY_PENDING_SCOPE = "INITIAL_RECIPIENT_READMISSION_PENDING_OWNER_CLOSE_V1"
READMISSION_SCOPE = "INITIAL_RECIPIENT_CLOSED_NONPRODUCTIVE_READMISSION_V1"
ENTRY_CONTEXT_FIELDS = (CONTEXT_FIELDS - {"prelude"}) | {"entryWindow", "expectedMatch", "originalProposal"}
_PREPARED_RETURNS = {}
_WORKER_USE_LOCK = threading.Lock()
_WORKER_USES, _WORKER_CLAIMS, _ENTRY_WINDOWS, _READMISSION_RETURNS = {}, {}, {}, {}
_READMISSION_ATTEMPTS = {}


@dataclass(frozen=True)
class SourceReturn:
    """Registered original call only; never populated from a disk receipt."""
    records: tuple
    session: bytes
    raw: bytes


@dataclass(frozen=True)
class _OriginalPreparation:
    """Same-call original return; never reconstructed from a digest or disk.

    The optional worker identity does not admit a producer/exporter, a new
    owner, an extended budget or another authority acquisition episode.
    """
    raw: bytes = field(repr=False)
    identity: object = field(repr=False)
    service_time_raw: object = field(repr=False)
    proposal_raw: object = field(repr=False)
    _owner: object = field(repr=False, compare=False)
    _fence: object = field(repr=False, compare=False)
    _cancelled: object = field(repr=False, compare=False)
    _match: object = field(repr=False)


@dataclass(frozen=True, repr=False)
class _PreparationBinding:
    """Independently retained values, not a comparison of the mutable graph to itself.

    This is a private same-call contract, not a Python sandbox against replacing
    this registry or executable code. No disk record can populate the registry.
    """
    original: _OriginalPreparation
    raw: bytes
    identity: object
    identity_fields: object
    match: object
    match_raw: bytes
    owner: object
    fence: object
    prelude_raw: bytes
    local_end: float
    cancelled: object
    cancel_check: object
    last_ns: int
    worker_originals: object
    service_time_raw: object
    proposal_raw: object


def _worker_fields(value):
    require(type(value) is initial_identity.InitialBootstrapIdentity, "WORKER_IDENTITY_ONLY")
    names = ("record", "original_event", "original_policy", "public_key", "fingerprint", "key_sha256", "expires_at")
    fields = tuple(getattr(value, name) for name in names)
    require(tuple(type(item) for item in fields) == (bytes, bytes, bytes, bytes, str, str, int),
            "WORKER_IDENTITY_TYPES")
    return fields


def _original_limits(owner, fence, prelude_raw, local_end, cancel_check):
    require(type(fence.raw) is bytes and fence.raw == prelude_raw and
            type(owner.local_end) is float and owner.local_end == local_end and
            fence.cancelled is cancel_check, "ORIGINAL_FENCE_CHANGED")
    native.history.snapshot(fence)  # Also checks clock/first/work/final against original raw bytes.


def _preparation_binding(original):
    """Data-only original-return check; no clock, callback or I/O."""
    binding = _PREPARED_RETURNS.get(id(original))
    require(type(original) is _OriginalPreparation and type(binding) is _PreparationBinding and
            binding.original is original and original._owner is binding.owner and original._fence is binding.fence and
            type(original._owner) is native.Owner and type(original._fence) is O.Fence and
            original._owner.closed is True and original._owner.unknown is False and original._owner.original is None and
            original._owner.fence is original._fence, "NOT_ORIGINAL_PREPARATION_RETURN")
    return binding


def _worker_binding_value(original, binding):
    """Compare to independently saved values, including after final observations."""
    require(original._cancelled is binding.cancelled, "ORIGINAL_CANCELLATION_CHANGED")
    require(type(original.identity) is initial_identity.InitialBootstrapIdentity and
            type(original._match) is acquisition.stages.BootstrapMatch, "WORKER_IDENTITY_ONLY")
    value = original.identity
    fields = _worker_fields(value)
    require(value is binding.identity and fields == binding.identity_fields and original._match is binding.match and
            type(original._match.record) is bytes and original._match.record == binding.match_raw and
            type(original.raw) is bytes and original.raw == binding.raw, "ORIGINAL_BINDING_CHANGED")
    pending = I.parse(binding.raw, I.EVENT_LIMIT)
    require(pending["matchSha256"] == O.digest(binding.match_raw) and
            pending["workerIdentitySha256"] == O.digest(value.record), "ORIGINAL_RESULT_CHANGED")
    require(type(original.service_time_raw) is bytes and type(original.proposal_raw) is bytes and
            original.service_time_raw == binding.service_time_raw and original.proposal_raw == binding.proposal_raw and
            pending["serviceTimeBasisSha256"] == O.digest(binding.service_time_raw) and
            pending["allocationProposalSha256"] == O.digest(binding.proposal_raw), "ORIGINAL_TIME_BINDING_CHANGED")
    _original_limits(binding.owner, binding.fence, binding.prelude_raw, binding.local_end, binding.cancel_check)
    O.integer(binding.fence.last, binding.last_ns)
    return value


def _checked_worker_identity(original):
    """Original live check; its caller owns the short in-call use reservation."""
    binding = _preparation_binding(original)
    native.cancellation(binding.cancelled)
    value = _worker_binding_value(original, binding)
    rechecked = initial_identity.bind_worker_match(original._match, event_raw=value.original_event,
        policy_raw=value.original_policy, now=int(time.time()))
    require(rechecked == value, "WORKER_IDENTITY_CHANGED")
    require(_worker_time_records(value, binding.worker_originals, binding.fence.clock) ==
            (binding.service_time_raw, binding.proposal_raw), "WORKER_TIME_RECORDS_CHANGED")
    try:
        binding.fence.now(final=True, minimum=binding.last_ns)
    finally:
        # Fence.now retains a validated observation even on expiry. A later
        # field mutation must not erase that high-water or renew a failed end.
        binding = replace(binding, last_ns=binding.fence.last)
        _PREPARED_RETURNS[id(original)] = binding
    native.posix._deadline(binding.local_end)
    native.cancellation(binding.cancelled)
    # The final observations/cancellation boundary can expose changed data.
    # Recheck against saved originals without another callback or clock read;
    # do not return an identity whose fields changed after its earlier check.
    require(_preparation_binding(original) is binding, "ORIGINAL_RETURN_BINDING_CHANGED")
    require(_worker_binding_value(original, binding) is value and binding.fence.last == binding.last_ns,
            "ORIGINAL_FINAL_BINDING_CHANGED")
    return value


def _begin_worker_use(original, *, consume=False):
    # Invalid/copy/gate inputs cannot consume an original. No callback, parser,
    # clock or I/O is invoked while the registry lock is held.
    binding = _preparation_binding(original)
    _worker_binding_value(original, binding)
    marker = object()
    with _WORKER_USE_LOCK:
        require(_PREPARED_RETURNS.get(id(original)) is binding, "WORKER_ORIGINAL_USE_CHANGED")
        require(id(original) not in _WORKER_CLAIMS, "WORKER_ORIGINAL_ALREADY_CLAIMED")
        require(id(original) not in _WORKER_USES, "WORKER_ORIGINAL_USE_IN_PROGRESS")
        _WORKER_USES[id(original)] = marker
        if consume:
            _WORKER_CLAIMS[id(original)] = (original, marker)  # Irreversible, including failed validation.
    return marker


def _end_worker_use(original, marker):
    with _WORKER_USE_LOCK:
        require(_WORKER_USES.get(id(original)) is marker, "WORKER_ORIGINAL_USE_CHANGED")
        del _WORKER_USES[id(original)]


def original_worker_identity(original):
    """An original read cannot overlap a claim or advance an already retired fence."""
    marker = _begin_worker_use(original)
    try:
        return _checked_worker_identity(original)
    finally:
        _end_worker_use(original, marker)


def original_worker_time_records(original):
    """Original first-acquisition proposal bytes, NOT current authority or a lease.

    The same original return/ceilings must still be valid. A later productive
    claim/readmission needs separate ownership; this accessor renews nothing.
    """
    binding = _preparation_binding(original)
    records = binding.service_time_raw, binding.proposal_raw
    original_worker_identity(original)
    return records  # Never reload mutable return fields after their validation.


@dataclass(frozen=True, repr=False)
class _ReadmissionClaim:
    original: _OriginalPreparation
    binding: _PreparationBinding
    service_job: tuple


def _service_job(captured, clock):
    """Stable job identity from original bytes, not a new Date/budget anchor."""
    context_raw, originals, invocation, _began, _end = captured
    context, raw = O.parse(context_raw), dict(originals)
    github = context["observed"]["github"]
    path = acquisition.API + "/actions/runs/" + github["runId"] + "/attempts/" + github["runAttempt"]
    _, attempt, _ = O.response_bytes(raw["attempt"], path, invocation, clock)
    _, jobs, date = O.response_bytes(raw["jobs"], path + "/jobs?per_page=100&page=1", invocation, clock)
    job = acquisition._run(context["observed"], I.parse(attempt, O.wire.BODY_LIMIT),
                           I.parse(jobs, O.wire.BODY_LIMIT), date)
    return job["id"], job["started_at"], job["runner_name"], job["runner_id"]


def _claim_worker(original):
    marker = _begin_worker_use(original, consume=True)
    try:
        identity = _checked_worker_identity(original)
        binding = _preparation_binding(original)
        # The live accessor just checked policy/RAW/LOCAL/cancellation. Everything
        # from here on is data-only; never advance/reopen the old fence/owner.
        service_job = _service_job(binding.worker_originals, binding.fence.clock)
        require(_preparation_binding(original) is binding and _worker_binding_value(original, binding) is identity and
                binding.fence.last == binding.last_ns, "CLAIM_ORIGINAL_CHANGED")
        claim = _ReadmissionClaim(original, binding, service_job)
        with _WORKER_USE_LOCK:
            held = _WORKER_CLAIMS.get(id(original))
            require(_WORKER_USES.get(id(original)) is marker and
                    type(held) is tuple and len(held) == 2 and held[0] is original and held[1] is marker,
                    "WORKER_CLAIM_CHANGED")
            _WORKER_CLAIMS[id(original)] = claim
        return claim
    finally:
        _end_worker_use(original, marker)


def _retired_worker(claim):
    """Frozen history only: NEVER observe/reopen the original fence or owner."""
    require(type(claim) is _ReadmissionClaim, "NOT_WORKER_CLAIM")
    with _WORKER_USE_LOCK:
        registered = _WORKER_CLAIMS.get(id(claim.original))
    require(registered is claim and _preparation_binding(claim.original) is claim.binding,
            "NOT_ORIGINAL_WORKER_CLAIM")
    _worker_binding_value(claim.original, claim.binding)
    require(claim.binding.fence.last == claim.binding.last_ns and
            _service_job(claim.binding.worker_originals, claim.binding.fence.clock) == claim.service_job,
            "RETIRED_WORKER_HISTORY_CHANGED")
    return claim.binding


def _begin_readmission(claim):
    original = _retired_worker(claim)
    with _WORKER_USE_LOCK:
        require(_WORKER_CLAIMS.get(id(claim.original)) is claim, "NOT_ORIGINAL_WORKER_CLAIM")
        require(id(claim) not in _READMISSION_ATTEMPTS, "ENTRY_ALREADY_ATTEMPTED")
        _READMISSION_ATTEMPTS[id(claim)] = claim  # Irreversible before even the first new clock/owner.
    return original


def _entry_limits(first, productive_end, job_end):
    first, productive_end, job_end = (O.integer(value) for value in (first, productive_end, job_end))
    final = min(O.integer(first + 120 * O.NS), productive_end, job_end)
    work = min(O.integer(first + 75 * O.NS), O.integer(final - 45 * O.NS))
    require(first < work, "ENTRY_NO_WORK_INTERVAL")
    return work, final


def _entry_frame(raw):
    """Closed supplied frame; only the original parent establishes provenance."""
    value = O.parse(raw)
    require(type(raw) is bytes and raw == O.encoded(value) and set(value) == {
        "schema", "scope", "clock", "firstNs", "previousNs", "workEndNs", "finalEndNs", "firstUseAt",
        "originalProductiveEntryEndNs", "originalProposedJobEndNs", "originalPreparationSha256",
        "workerIdentitySha256", "originalProposalSha256", "budgetAcceptance", "exportSaveAuthority"} and
        type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == ENTRY_WINDOW_SCOPE and
        value["budgetAcceptance"] == "NOT_ADMITTED" and value["exportSaveAuthority"] is False, "ENTRY_FRAME")
    clock = O.wire.clock_identity(value["clock"])
    first = O.integer(value["firstNs"], O.integer(value["previousNs"]))
    work, final = _entry_limits(first, value["originalProductiveEntryEndNs"], value["originalProposedJobEndNs"])
    require(type(value["workEndNs"]) is int and type(value["finalEndNs"]) is int and
            (value["workEndNs"], value["finalEndNs"]) == (work, final), "ENTRY_FRAME_FENCES")
    O.integer(value["firstUseAt"], 1)
    require(all(type(value[name]) is str and re.fullmatch(r"[0-9a-f]{64}", value[name]) for name in
        ("originalPreparationSha256", "workerIdentitySha256", "originalProposalSha256")), "ENTRY_FRAME_BINDINGS")
    return value, clock, first, work, final


@dataclass(frozen=True, repr=False)
class _EntryWindowBinding:
    window: object
    raw: bytes
    clock: object
    first: int
    work: int
    final: int
    cancelled: object
    last: int
    owner: object = None
    phase: object = None
    resources: tuple = ()
    terminal: bool = False
    busy: bool = False
    failed: bool = False


class _ReadmissionWindow:
    """One distinct nonproductive episode; neither O.Fence nor job Admission."""
    def __init__(self, raw, *, minimum, cancelled):
        _value, clock, first, work, final = _entry_frame(raw)
        require(callable(cancelled), "ENTRY_CANCELLATION")
        self.raw, self.clock, self.first, self.work, self.final = raw, clock, first, work, final
        self.last, self.cancelled = O.integer(minimum, first), cancelled
        require(self.last < work, "ENTRY_FIRST_EXPIRED")
        _ENTRY_WINDOWS[id(self)] = _EntryWindowBinding(self, raw, clock, first, work, final, cancelled, self.last)

    def checked(self):
        binding = _ENTRY_WINDOWS.get(id(self))
        require(type(self) is _ReadmissionWindow and type(binding) is _EntryWindowBinding and binding.window is self,
                "ENTRY_WINDOW_NOT_ORIGINAL")
        if binding.owner is not None:
            owner, local, first, resources, errors, sources = binding.owner
            # Capture returned resources before any later clock/callback. A
            # malformed replacement remains referenced, but cannot be accepted.
            seen = {id(row): resource for row, _label, resource in binding.resources}
            additions = []
            require(type(owner.resources) is list, "ENTRY_OWNER_ROSTER")
            for row in owner.resources:
                label, resource = (row.get("label"), row.get("owner")) if type(row) is dict else (None, None)
                if id(row) not in seen or seen[id(row)] is not resource:
                    additions.append((row, label, resource))
                    seen[id(row)] = resource
            if additions:
                binding = replace(binding, resources=binding.resources + tuple(additions))
                _ENTRY_WINDOWS[id(self)] = binding
            require(owner.resources is resources and len(resources) == len(binding.resources) and
                    owner.errors is errors and owner.initial_sources is sources and owner.fence is self and
                    owner.first is first and owner.early_last == binding.first and
                    owner.cancelled is binding.cancelled and type(owner.local_end) is float and owner.local_end == local,
                    "ENTRY_OWNER_CHANGED")
            O.clocks.validate_reading(first)
            require(first.clock == binding.clock and first.nanoseconds == binding.first, "ENTRY_FIRST_CHANGED")
            limits = (None, None) if binding.phase is None else binding.phase
            require(all(type(a) is type(b) and a == b for a, b in
                        zip((owner.work_limit, owner.final_limit), limits)), "ENTRY_PHASE_LIMITS_CHANGED")
            for current, (row, label, resource) in zip(resources, binding.resources):
                require(current is row and type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
                    row["label"] == label and label in ("directory", "writer", "stdout", "stderr", "native-scope") and
                    row["owner"] is resource and type(row["attempted"]) is bool and type(row["closed"]) is bool and
                    (not row["closed"] or row["attempted"]), "ENTRY_OWNER_ROSTER")
        require(type(self.raw) is bytes and self.raw == binding.raw and self.clock is binding.clock and
            all(type(a) is int and a == b for a, b in zip((self.first, self.work, self.final, self.last),
                (binding.first, binding.work, binding.final, binding.last))) and self.cancelled is binding.cancelled,
            "ENTRY_WINDOW_CHANGED")
        O.clocks.validate_identity(self.clock)
        require(_entry_frame(binding.raw)[1:] == (binding.clock, binding.first, binding.work, binding.final),
                "ENTRY_WINDOW_FRAME_CHANGED")
        return binding

    def bind_owner(self, owner, first):
        binding = self.checked()
        require(binding.owner is None and type(owner) is native.Owner and owner.fence is self and
                owner.first is first and first.clock == self.clock and first.nanoseconds == self.first and
                owner.resources == [] and owner.errors == [] and owner.initial_sources == {}, "ENTRY_OWNER_BINDING")
        _ENTRY_WINDOWS[id(self)] = replace(binding, owner=(owner, owner.local_end, first,
            owner.resources, owner.errors, owner.initial_sources))
        self.checked()

    def enter_phase(self, owner, started):
        binding = self.checked()
        require(binding.owner is not None and binding.owner[0] is owner and binding.phase is None and
                not binding.terminal and not binding.failed and not binding.busy and
                self.first <= O.integer(started) == binding.last < self.work, "ENTRY_PHASE_OWNER")
        limits = min(self.work, started + 45 * O.NS), min(self.final, min(self.work, started + 45 * O.NS) + 45 * O.NS)
        owner.work_limit, owner.final_limit = limits
        _ENTRY_WINDOWS[id(self)] = replace(binding, phase=limits)
        self.checked()
        return limits

    def leave_phase(self, owner):
        binding = self.checked()
        require(binding.owner is not None and binding.owner[0] is owner and binding.phase is not None, "ENTRY_PHASE_OWNER")
        owner.work_limit = owner.final_limit = None
        _ENTRY_WINDOWS[id(self)] = replace(binding, phase=None)
        self.checked()

    def now(self, *, final=False, minimum=0, limit=None):
        binding = self.checked()
        require(type(final) is bool and not binding.terminal and not binding.busy, "ENTRY_WINDOW_RETIRED_OR_BUSY")
        require(final or not binding.failed, "ENTRY_WINDOW_FAILED")
        if binding.owner is not None and not final:
            owner = binding.owner[0]
            require(not owner.closed and not owner.unknown and owner.original is None, "ENTRY_OWNER_NOT_LIVE")
        _ENTRY_WINDOWS[id(self)] = replace(binding, busy=True)
        now, failure = None, False
        try:
            now = O.clocks.checked_now(binding.clock, minimum_ns=max(binding.last, O.integer(minimum)))
            current = self.checked()  # Detect mutations made by the observation; retain new pins.
            self.last = now
            _ENTRY_WINDOWS[id(self)] = replace(current, last=now)
            ceiling = binding.final if final else binding.work
            if limit is not None:
                ceiling = min(ceiling, O.integer(limit))
            require(now < ceiling, "ENTRY_WINDOW_EXPIRED")
            if not final:
                binding.cancelled()
            self.checked()
            return now
        except BaseException:
            failure = True
            try:
                self.checked()  # Preserve any returned/replaced pins; never mask the first failure.
            except BaseException:
                pass
            raise
        finally:
            # Never replace a post-observation binding with the stale preimage:
            # that could erase resource returns or a newer validated high-water.
            current = _ENTRY_WINDOWS[id(self)]
            _ENTRY_WINDOWS[id(self)] = replace(current, busy=False, failed=current.failed or failure,
                last=current.last if now is None else max(current.last, now))

    def deadline(self, maximum, *, final=False, limit=None):
        require(type(maximum) in (int, float) and math.isfinite(maximum) and maximum > 0, "ENTRY_OPERATION_MAXIMUM")
        self.checked()  # Capture resource returns before even LOCAL can fail.
        local = time.monotonic()
        now = self.now(final=final, limit=limit)
        ceiling = self.final if final else self.work
        if limit is not None:
            ceiling = min(ceiling, O.integer(limit))
        result = O.wire._directed_deadline(local, maximum, ceiling, now)
        self.checked()
        return result


def require(value, code):
    I.require(value, "INITIAL_NATIVE_" + code)


def location(*, entry=False):
    require(type(entry) is bool, "LOCATION_SCOPE")
    job = os.environ.get("GITHUB_JOB")
    require(job in (acquisition.gate.JOB, acquisition.stages.bootstrap.JOB), "ACTUAL_JOB")
    kind = "gate" if job == acquisition.gate.JOB else "worker"
    require(not entry or kind == "worker", "ENTRY_WORKER_ONLY")
    run, attempt = os.environ.get("GITHUB_RUN_ID"), os.environ.get("GITHUB_RUN_ATTEMPT")
    acquisition.stages.joint.run({"runId": run, "runAttempt": attempt})
    parent = Path(os.environ.get("RUNNER_TEMP", ""))
    require(parent.is_absolute() and ".." not in parent.parts and parent == parent.resolve(strict=True) and
            parent.is_dir() and parent != ROOT and ROOT not in parent.parents and parent not in ROOT.parents,
            "PRIVATE_PARENT")
    for path in (parent, *parent.parents):
        info = path.lstat()
        require(not stat.S_ISLNK(info.st_mode) and not getattr(info, "st_file_attributes", 0) & 0x400, "PARENT_ALIAS")
    return kind, parent / ("p2pkit-initial-recipient-" + run + "-" + attempt + "-" + kind + ("-entry" if entry else ""))


def host_context(first_use_at, *, entry=False):
    kind, path = location(entry=entry)
    env = dict(os.environ)
    require(env.get("GITHUB_WORKSPACE") == str(ROOT) and ROOT == ROOT.resolve(strict=True), "WORKSPACE")
    event = I.read_regular(Path(env.get("GITHUB_EVENT_PATH", "")), I.EVENT_LIMIT)
    return acquisition._context(env, event, kind, first_use_at), path, event


def query_owner(owner, fence, path):
    owner.end()
    require(owner.fence is fence, "QUERY_ORIGINAL_FENCE")
    work = min(owner.local_end, fence.deadline(O.WORK_SECONDS, limit=owner.work_limit))
    final = min(owner.local_end, fence.deadline(O.PRELUDE_SECONDS, final=True, limit=owner.final_limit))
    return Q.NativeGitQueries(ROOT, path, check_cancel=lambda: fence.now(limit=owner.work_limit),
                              owner_deadlines=(min(work, final), final))


def finish_queries(owner, supplier, failure):
    """Preserve actual finalizer failure; a provisional session is insufficient."""
    if supplier is not None:
        try:
            supplier._finalize(failure)
        except BaseException as error:
            failure = failure or error
    if (supplier is not None and supplier.unknown) or Q.QUARANTINE or native.diagnostics._QUARANTINE:
        error = failure or O.OriginError("INITIAL_NATIVE_QUERY_UNKNOWN")
        owner.error("initial-query", error, unknown=True)
        failure = failure or error
    if failure is not None:
        raise failure


def query_session(owner, directory):
    raw = owner.read(directory, "session-result.json")
    value = O.parse(raw)
    require(set(value) == {"schema", "scope", "job", "queries", "result", "retirement", "firstError", "errors", "readbacks"}
            and type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == "ORDINARY_GIT_QUERIES_ONLY"
            and value["result"] == "READY_FOR_CALLER_SEAL" and value["retirement"] == "KNOWN" and
            value["firstError"] is None and value["errors"] == [] and type(value["queries"]) is list and
            type(value["readbacks"]) is list and type(value["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", value["job"]),
            "QUERY_SESSION")
    return raw


def source_queries(owner, fence, context, path):
    """Actual closed native Git call, before/after the separate HTTP phase."""
    supplier = result = None
    failure = None
    try:
        supplier = query_owner(owner, fence, path)
        supplier.native_host_matches_actions()
        result = acquisition._source(I.GitView(ROOT, dict(os.environ), supplier), context, owner.end)
        for name in SOURCE_KEYS:
            # The maintained query writer supports the genuine empty ls-tree
            # stdout, without replacing absence by invented nonempty JSON.
            supplier._write(supplier.private, name + ".bin", result[name])
        owner.end()
    except BaseException as error:
        failure = error
    finally:
        finish_queries(owner, supplier, failure)
    owner.end()
    directory = owner.open(path)
    session = query_session(owner, directory)
    require(set(result) == set(SOURCE_KEYS) and all(owner.read(directory, name + ".bin") == result[name]
            for name in SOURCE_KEYS), "SOURCE_ORIGINALS_CHANGED")
    raw = owner.write(directory, "source-return.json", {"schema": 1, "scope": SOURCE_SCOPE,
        "originalsSha256": {name: O.digest(result[name]) for name in SOURCE_KEYS}, "sessionSha256": O.digest(session),
        "clock": O.clock_value(fence.clock), "returnedNs": fence.now(limit=owner.work_limit)})
    owner.end()
    returned = SourceReturn(tuple((name, result[name]) for name in SOURCE_KEYS), session, raw)
    require(str(path) not in owner.initial_sources, "SOURCE_QUERY_REUSE")
    owner.initial_sources[str(path)] = returned
    return returned


def source_readback(owner, path, original):
    require(type(original) is SourceReturn and owner.initial_sources.get(str(path)) is original, "NOT_ORIGINAL_SOURCE_RETURN")
    directory = owner.open(path)
    require(owner.read(directory, "source-return.json") == original.raw and
            query_session(owner, directory) == original.session and all(owner.read(directory, name + ".bin") == raw
            for name, raw in original.records), "SOURCE_RETURN_CHANGED")
    owner.end()
    return dict(original.records)


def context_record(raw, path, fence):
    value = O.parse(raw)
    entry = type(fence) is _ReadmissionWindow
    require(entry or type(fence) is O.Fence, "CONTEXT_WINDOW")
    scope = native.INITIAL_ENTRY_CONTEXT_SCOPE if entry else native.INITIAL_CONTEXT_SCOPE
    require(set(value) == (ENTRY_CONTEXT_FIELDS if entry else CONTEXT_FIELDS) and raw == O.encoded(value) and
            type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == scope and
            value["entryWindow" if entry else "prelude"] == O.parse(fence.raw) and
            value["root"] == str(ROOT) and value["session"] == str(path)
            and value["budgetAcceptance"] == "NOT_ADMITTED" and value["exportSaveAuthority"] is False, "CONTEXT")
    require(type(value["observed"]) is dict, "CONTEXT_OBSERVATION")
    observed, actual_path, event = host_context(value["observed"].get("firstUseAt"), entry=entry)
    require(value["observed"] == observed and observed["role"] == fence.clock.role and actual_path == path and
            value["eventSha256"] == O.digest(event), "ACTUAL_CONTEXT_CHANGED")
    require(type(value["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", value["job"]) and
            type(value["sourceReturnSha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", value["sourceReturnSha256"]),
            "CONTEXT_BINDINGS")
    require(fence.first <= O.integer(value["sourceReturnedNs"]) < fence.work, "SOURCE_RETURN_TIME")
    inherited = value["inheritedContext"]
    require(type(inherited) is dict and all(type(x) is str for x in inherited.values()) and
            (set(inherited).issubset({"GRADLE_USER_HOME"}) or set(inherited) == set(Q._CONTEXT)), "PARENT_CONTEXT")
    if entry:
        frame = _entry_frame(fence.raw)[0]
        expected, proposal = value["expectedMatch"], value["originalProposal"]
        initial_identity._match(expected)
        require(type(proposal) is dict and proposal.get("scope") == ALLOCATION_SCOPE and
                O.digest(O.encoded(proposal)) == frame["originalProposalSha256"] and
                proposal["workerIdentitySha256"] == frame["workerIdentitySha256"] and
                proposal["clock"] == frame["clock"] and proposal["source"] == observed["source"] and
                proposal["firstUseAt"] == expected["firstUseAt"] == observed["firstUseAt"] == frame["firstUseAt"] and
                proposal["phaseFencesNs"]["productive-entry"] == frame["originalProductiveEntryEndNs"] and
                proposal["proposedJobEndNs"] == frame["originalProposedJobEndNs"], "ENTRY_CONTEXT_BINDINGS")
    return value, event


def _entry_phase_start(fence, source_returned_ns, start):
    binding = fence.checked()
    returned = O.integer(source_returned_ns, binding.first)
    began = O.integer(start["startedNs"], returned)
    require(began < binding.work and type(start["workEndNs"]) is int and type(start["finalEndNs"]) is int and
            start["workEndNs"] == min(binding.work, began + 45 * O.NS) and
            start["finalEndNs"] == min(binding.final, start["workEndNs"] + 45 * O.NS), "ENTRY_PHASE_FENCES")
    return began


def _entry_chain_minimum(fence, returned, start, row, birth, child, service, ack):
    _entry_phase_start(fence, returned, start)
    times = [fence.first, returned, start["startedNs"], row["launchMinimumNs"], child["beganNs"],
        child["metadataLastNs"], service["firstNs"], service["lastNs"], child["acquiredNs"], child["queryReturnedNs"],
        child["completedNs"], ack["closedNs"], row["completedNs"], row["finalizedNs"]]
    require(all(type(x) is int and 0 <= x <= O.clocks.UINT64 for x in times) and times == sorted(times) and
            row["completedNs"] < start["workEndNs"] and row["finalizedNs"] < start["finalEndNs"] and
            row["launchMinimumNs"] <= O.integer(birth["observedNs"]) <= row["completedNs"], "ENTRY_CLOCK_CHAIN")
    return max(*times, birth["observedNs"])


def start_record(raw, context_raw, context, path, fence):
    value = O.parse(raw)
    require(set(value) == native.START_FIELDS and raw == O.encoded(value) and type(value["schema"]) is int and
            value["schema"] == 1 and value["scope"] == native.PHASE_SCOPE and
            value["contextSha256"] == O.digest(context_raw) and
            value["argv"] == native.phase_command(context_raw) and value["cwd"] == str(ROOT) and
            value["role"] == fence.clock.role and value["job"] == context["job"] and value["state"] == str(path) and
            value["home"] == str(path / "control-home") and value["exitCode"] is None and value["launchAttempted"] is False and
            value["scopeAttempted"] is False and value["retirement"] == "UNKNOWN" and
            type(value["invocation"]) is str and re.fullmatch(r"[0-9a-f]{32}", value["invocation"]), "PRELAUNCH")
    if type(fence) is _ReadmissionWindow:
        _entry_phase_start(fence, context["sourceReturnedNs"], value)
    else:
        native.history.phase_start(native.history.snapshot(fence), context["sourceReturnedNs"], value)
    env = native.processes.ownership_environment(context["inheritedContext"], context["job"], value["invocation"],
        str(path), str(path / "control-home"), allow_new_context=True)
    require(value["inheritedContext"] == {name: env[name] for name in Q._CONTEXT}, "ORIGINAL_ANCESTORS")
    return value


def service_child(context_hash, minimum, cancelled, *, entry=False):
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    owner = fence = directory = result_raw = None
    supplier = None
    try:
        local_end = time.monotonic() + O.wire.ACQUIRE_SECONDS
        first = O.clocks.validate_reading(O.clocks.observe())
        require(first.nanoseconds >= O.integer(minimum), "CHILD_PRECEDES_LAUNCH")
        owner = native.Owner(local_end, first=first, cancelled=lambda: native.cancellation(cancelled))
        _, path = location(entry=entry)
        private = owner.open(path)
        context_raw = owner.read(private, "context.json")
        require(O.digest(context_raw) == context_hash, "CHILD_CONTEXT_CHANGED")
        context = O.parse(context_raw)
        check_cancel = lambda: native.cancellation(cancelled)
        fence = (_ReadmissionWindow(O.encoded(context["entryWindow"]), minimum=first.nanoseconds, cancelled=check_cancel)
                 if entry else O.Fence(context["prelude"], minimum=first.nanoseconds, cancelled=check_cancel))
        require(first.clock == fence.clock, "CHILD_CLOCK_CHANGED")
        context, event = context_record(context_raw, path, fence)
        directory = owner.child(private, "service")
        start_raw = owner.read(directory, "start.json")
        start = start_record(start_raw, context_raw, context, path, fence)
        inherited = Q._inherited_context()
        require(set(inherited) == set(Q._CONTEXT) and inherited == start["inheritedContext"], "CHILD_NATIVE_CONTEXT")
        domain = native.processes.ownership_domains(inherited[native.processes.CHAIN_ENV],
            inherited[native.processes.DOMAINS_ENV])[-1]
        require(domain == {"id": start["invocation"], "job": start["job"], "state": start["state"], "home": start["home"]}
                and start["startedNs"] <= minimum <= first.nanoseconds < start["workEndNs"], "CHILD_ORIGINAL_LAUNCH")
        owner.bind(fence, work_limit=start["workEndNs"], final_limit=start["finalEndNs"])
        failure = None
        try:
            supplier = query_owner(owner, fence, path / "acquisition-queries")
            supplier.native_host_matches_actions()
            def retain(name, raw, *, failed):
                require(name in ORIGINAL_KEYS and type(raw) is bytes, "ORIGINAL_NAME")
                owner.end(final=failed)
                supplier._write(supplier.private, name + ".bin", raw)
                owner.end(final=failed)
            match, originals = acquisition.acquire_bootstrap(ROOT, kind=context["observed"]["kind"],
                query_runner=supplier, invocation=domain["id"], token=token, retain=retain, fence=fence,
                original_work_end=start["workEndNs"], first_use_at=context["observed"]["firstUseAt"],
                expected=acquisition.stages.BootstrapMatch(O.encoded(context["expectedMatch"])) if entry else None)
            token = None
            acquired = fence.now(limit=start["workEndNs"])
            require(dict(originals)["event"] == event, "CHILD_EVENT_CHANGED")
        except BaseException as error:
            failure = error
        finally:
            token = None
            finish_queries(owner, supplier, failure)
        # Only this actual successful finalizer return precedes the readback.
        returned = fence.now(limit=start["workEndNs"])
        queries = owner.open(path / "acquisition-queries")
        session = query_session(owner, queries)
        require(set(dict(originals)) == set(ORIGINAL_KEYS) and len(originals) == len(ORIGINAL_KEYS) and
                all(owner.read(queries, name + ".bin") == raw for name, raw in originals), "CHILD_ORIGINALS_CHANGED")
        result_raw = owner.write(directory, "child-result.json", {"schema": 1, "scope": ENTRY_CHILD_SCOPE if entry else CHILD_SCOPE,
            "contextSha256": context_hash, "startSha256": O.digest(start_raw), "invocation": domain["id"],
            "clock": O.clock_value(fence.clock), "launchMinimumNs": minimum, "beganNs": first.nanoseconds,
            "metadataLastNs": owner.early_last, "acquiredNs": acquired, "queryReturnedNs": returned,
            "querySessionSha256": O.digest(session), "originalsSha256": {name: O.digest(raw) for name, raw in originals},
            "matchSha256": O.digest(match.record), "completedNs": fence.now(limit=start["workEndNs"]),
            "retirement": "KNOWN", "errors": []})
    except BaseException as error:
        if owner is None:
            raise
        owner.error("initial-service-child", error)
        if directory is not None and not owner.unknown:
            try:
                owner.write(directory, "child-failure.json", {"schema": 1, "result": "HOLD", "errors": owner.errors,
                    "retirement": "PENDING_OWNER_CLOSE", "budgetAcceptance": "NOT_ADMITTED"}, final=True)
            except BaseException as secondary:
                owner.error("initial-child-failure-retention", secondary)
    finally:
        token = None
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                owner.error("initial-child-close", error)
    if owner.original is not None:
        raise owner.original
    require(fence is not None and result_raw is not None and not owner.unknown, "CHILD_NO_ORIGINALS")
    native.posix._deadline(owner.local_end)
    closed = fence.now(limit=start["workEndNs"])
    return {"schema": 1, "scope": native.INITIAL_ENTRY_ACK_SCOPE if entry else native.INITIAL_ACK_SCOPE, "invocation": domain["id"],
            "terminalSha256": O.digest(result_raw), "clock": O.clock_value(fence.clock), "closedNs": closed}, fence, start["workEndNs"]


def retained_match(context, raw, invocation, clock, work_start, work_end):
    """Recheck exact retained originals; only the native parent supplies origin."""
    observed = context["observed"]
    github = observed["github"]
    base = acquisition.API + "/actions/runs/" + github["runId"]
    attempt_path = base + "/attempts/" + github["runAttempt"]
    bodies, times, dates = {}, [], []
    def body(name, path):
        response, data, date = O.response_bytes(raw[name], path, invocation, clock)
        _, headers = O.wire.headers(base64.b64decode(response["headersBase64"], validate=True))
        require("link" not in headers and work_start <= response["startedNs"] <= response["finishedNs"] < work_end and
                (not times or times[-1] <= response["startedNs"]), "HTTP_ORIGINAL_INTERVAL")
        require(not dates or dates[-1] <= date and 0 <= date - dates[0] <=
                math.ceil((response["finishedNs"] - work_start) / O.NS) + O.wire.CACHE_SECONDS + 1, "HTTP_SERVICE_DATE")
        times.extend((response["startedNs"], response["finishedNs"]))
        dates.append(date)
        bodies[name] = data
        return data
    attempt = I.parse(body("attempt", attempt_path), O.wire.BODY_LIMIT)
    jobs = I.parse(body("jobs", attempt_path + "/jobs?per_page=100&page=1"), O.wire.BODY_LIMIT)
    job = acquisition._run(observed, attempt, jobs, dates[-1])
    jobs_started, jobs_date = times[-2], dates[-1]
    approval = body("approvals", base + "/approvals")
    selected = acquisition.gate.select(stage="stage1", run_id=github["runId"], attempt=github["runAttempt"], approvals_raw=approval)
    selector = I.parse(selected.record, acquisition.stages.LIMIT)
    comment = body("comment", acquisition.API + "/issues/comments/" + str(selector["commentId"]))
    declaration, _, _ = acquisition.stages.statement(acquisition.stages.STAGE1, comment,
        selector["commentId"], selector["bodySha256"])
    require(selector["environmentId"] == declaration["environment"]["id"], "ENVIRONMENT_CHANGED")
    env_path = acquisition.API + "/environments/" + acquisition.stages.ENVIRONMENT
    env_raw = body("environment", env_path)
    branches = body("branches", env_path + "/deployment-branch-policies?per_page=100&page=1")
    acquisition.gate.check_environment(declaration["environment"], env_raw, branches)
    for name, branch, commit in (("main", "main", acquisition.stages.BASE["commit"]),
            ("reviewed_ref", acquisition.stages.SOURCE_REF.removeprefix("refs/heads/"), observed["source"]["commit"])):
        acquisition._ref(I.parse(body(name, acquisition.API + "/git/ref/heads/" + branch), acquisition.stages.LIMIT), branch, commit)
    observation = {"repository": I.REPOSITORY, "base": dict(acquisition.stages.BASE), "reviewed": observed["source"],
        "source": observed["source"], "firstUseAt": observed["firstUseAt"], "github": dict(github)}
    args = {name: raw[name] for name in SOURCE_KEYS}
    if observed["kind"] == "gate":
        observation["inputs"] = observed["inputs"]
        result = acquisition.gate.eligible(stage="stage1", approvals_raw=approval, comment_raw=comment,
            environment_raw=env_raw, branches_raw=branches, observation_raw=I.encoded(observation), now=int(time.time()),
            expected=acquisition.gate.GateEligibility(raw["match"]), **args)
    else:
        observation["github"].update(profile=acquisition.stages.bootstrap.PROFILE, selection=observed["inputs"]["selection"])
        result = acquisition.stages.match_bootstrap(comment_raw=comment, comment_id=selector["commentId"],
            body_sha256=selector["bodySha256"], observation_raw=I.encoded(observation), now=int(time.time()),
            expected=acquisition.stages.BootstrapMatch(raw["match"]), **args)
    require(raw["observation"] == I.encoded(observation), "OBSERVATION_CHANGED")
    return result, {"firstNs": times[0], "lastNs": times[-1], "numericJobId": job["id"],
        "runnerName": observed["runnerName"],
        "selector": acquisition.GATE_SELECTOR if observed["kind"] == "gate" else O.SERVICE_SELECTORS[clock.role],
        "jobStartedAt": job["started_at"], "originDateEpochSeconds": jobs_date,
        "jobsRequestStartedNs": jobs_started,
        "originalsSha256": {name: O.digest(raw[name]) for name in HTTP_KEYS},
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}


def _worker_time_records(identity, captured, clock):
    """Rederive from the parent's exact retained inputs, not a supplied basis.

    Only read_phase supplies these to the original preparation's registry.
    This retained-record recheck neither reacquires authority nor admits proposed5400.
    """
    _worker_fields(identity)
    require(type(captured) is tuple and len(captured) == 5, "WORKER_TIME_ORIGINALS")
    context_raw, originals, invocation, began, end = captured
    require(type(context_raw) is bytes and type(originals) is tuple and len(originals) == len(ORIGINAL_KEYS) and
            all(type(row) is tuple and len(row) == 2 and type(row[0]) is str and type(row[1]) is bytes
                for row in originals) and tuple(name for name, _ in originals) == ORIGINAL_KEYS, "WORKER_TIME_ORIGINALS")
    O.clocks.validate_identity(clock)
    context = O.parse(context_raw)
    require(context["observed"]["kind"] == "worker" and context["observed"]["role"] == clock.role,
            "WORKER_TIME_CONTEXT")
    raw = dict(originals)
    match, service = retained_match(context, raw, invocation, clock, O.integer(began), O.integer(end))
    rechecked = initial_identity.bind_worker_match(match, event_raw=raw["event"],
        policy_raw=raw["candidate_policy_raw"], now=int(time.time()))
    require(_worker_fields(rechecked) == _worker_fields(identity), "WORKER_TIME_IDENTITY_CHANGED")
    value = I.parse(identity.record, I.EVENT_LIMIT)
    shared = {"schema": 1, "profile": value["profile"], "selection": value["selection"],
        "cacheCohort": value["cacheCohort"], "source": value["source"], "github": value["github"],
        "workerIdentitySha256": O.digest(identity.record), "clock": O.clock_value(clock),
        "firstUseAt": value["initialRecipient"]["firstUseAt"], "budgetAcceptance": "NOT_ADMITTED",
        "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
    basis = {**shared, "scope": TIME_SCOPE, "invocation": invocation, "service": service,
        "policy": native.service_time.policy(), **native.service_time.basis_arithmetic(
            service["jobsRequestStartedNs"], O.wire.utc_epoch(service["jobStartedAt"]),
            service["originDateEpochSeconds"])}
    basis_raw = O.encoded(basis)
    proposal = {**shared, "scope": ALLOCATION_SCOPE, "serviceTimeBasis": basis,
        "serviceTimeBasisSha256": O.digest(basis_raw), "policy": native.allocation.policy(),
        **native.allocation.fence_arithmetic(basis["jobStartBasisNs"]), "productiveOwner": "NOT_CREATED"}
    return basis_raw, O.encoded(proposal)


def read_phase(owner, private, context_raw, source, phase, fence):
    require(type(phase) is native.OriginalPhase and owner.phase_originals is phase and phase.context == context_raw and
            owner.fence is fence and any(x["owner"] is private and not x["attempted"] for x in owner.resources),
            "NOT_ORIGINAL_PHASE_RETURN")
    entry = type(fence) is _ReadmissionWindow
    require(owner.read(private, "context.json") == context_raw and
            owner.read(private, "entry-window.json" if entry else "prelude.json") == fence.raw,
            "ORIGINAL_CONTEXT_CHANGED")
    context, event = context_record(context_raw, private.path, fence)
    policy = source_readback(owner, private.path / "source-before", source)
    require(context["sourceReturnSha256"] == O.digest(source.raw) and
            context["sourceReturnedNs"] == O.parse(source.raw)["returnedNs"], "SOURCE_CONTEXT_CHANGED")
    records = dict(phase.records)
    require(len(phase.records) == len(native.PHASE_FILES) and set(records) == native.PHASE_FILES, "PHASE_FILES")
    directory = owner.child(private, "service")
    for name, raw in records.items():
        require(type(raw) is bytes and owner.read(directory, name) == raw, "PHASE_FILE_CHANGED")
    start = start_record(records["start.json"], context_raw, context, private.path, fence)
    row, birth = (O.parse(records[name]) for name in ("result.json", "native-start.json"))
    native.baseline_record(records["baseline.json"], fence.clock.role)
    require(set(row) == native.TERMINAL_FIELDS and set(birth) == {"ownership", "leader", "preparerIdentity", "observedNs"},
            "NATIVE_FIELDS")
    preparer = native.closed_lifetime(row["preparerIdentity"], fence.clock.role)
    require(preparer == native.closed_lifetime(birth["preparerIdentity"], fence.clock.role) and
            preparer["pid"] != row["leader"]["pid"], "PREPARER_CHANGED")
    require(all(row.get(name) == start[name] for name in set(start) - {"exitCode", "launchAttempted", "scopeAttempted", "retirement"})
            and type(row["exitCode"]) is int and row["exitCode"] == 0 and row["launchAttempted"] is True and
            row["scopeAttempted"] is True and row["scopeCloseAttempted"] is True and row["scopeClosed"] is True and
            row["retirement"] == "KNOWN" and row["survivors"] == [] and row["errors"] == [] and records["stderr.log"] == b""
            and row["nativeStartSha256"] == O.digest(records["native-start.json"]) and
            row["baselineSha256"] == O.digest(records["baseline.json"]) and row["leader"] == birth["leader"], "NATIVE_RETURN")
    argv = native.phase_command(context_raw, O.integer(row["launchMinimumNs"], start["startedNs"]))
    require(row["launchArgv"] == argv, "EXECUTED_COMMAND")
    native.native_record(row["ownership"], start, row["leader"], argv)
    native.native_record(birth["ownership"], start, row["leader"], argv, terminal=False)
    require(birth["ownership"]["launches"] == row["ownership"]["launches"], "NATIVE_BIRTH_CHANGED")
    require(row["captureOutcomes"] == {name: {"synced": True, "verified": True, "closeAttempted": True, "closed": True,
            "readback": True} for name in ("stdout", "stderr")} and all(type(x) is bool for value in row["captureOutcomes"].values()
            for x in value.values()) and row["captures"] == {name: {"sha256": O.digest(records[name + ".log"]),
            "bytes": len(records[name + ".log"])} for name in ("stdout", "stderr")}, "CAPTURE_RETIREMENT")
    child_raw = owner.read(directory, "child-result.json")
    child, ack = O.parse(child_raw), O.parse(records["stdout.log"])
    require(records["stdout.log"] == O.encoded(ack) and set(ack) == {"schema", "scope", "invocation", "terminalSha256", "clock", "closedNs"}
            and type(ack["schema"]) is int and ack["schema"] == 1 and
            ack["scope"] == (native.INITIAL_ENTRY_ACK_SCOPE if entry else native.INITIAL_ACK_SCOPE) and
            ack["invocation"] == start["invocation"] and ack["terminalSha256"] == O.digest(child_raw) and
            ack["clock"] == O.clock_value(fence.clock), "CHILD_ACK")
    require(set(child) == {"schema", "scope", "contextSha256", "startSha256", "invocation", "clock", "launchMinimumNs", "beganNs",
            "metadataLastNs", "acquiredNs", "queryReturnedNs", "querySessionSha256", "originalsSha256", "matchSha256", "completedNs",
            "retirement", "errors"} and type(child["schema"]) is int and child["schema"] == 1 and
            child["scope"] == (ENTRY_CHILD_SCOPE if entry else CHILD_SCOPE) and
            child["contextSha256"] == O.digest(context_raw) and child["startSha256"] == O.digest(records["start.json"]) and
            child["invocation"] == start["invocation"] and child["clock"] == O.clock_value(fence.clock) and
            child["launchMinimumNs"] == row["launchMinimumNs"] and child["retirement"] == "KNOWN" and child["errors"] == [], "CHILD_RESULT")
    queries = owner.open(private.path / "acquisition-queries")
    session = query_session(owner, queries)
    raw = {name: owner.read(queries, name + ".bin") for name in ORIGINAL_KEYS}
    require(child["querySessionSha256"] == O.digest(session) and child["originalsSha256"] ==
            {name: O.digest(data) for name, data in raw.items()} and child["matchSha256"] == O.digest(raw["match"])
            and raw["event"] == event and {name: raw[name] for name in SOURCE_KEYS} == policy, "ORIGINAL_BYTES_CHANGED")
    match, service = retained_match(context, raw, start["invocation"], fence.clock, start["startedNs"], start["workEndNs"])
    if entry:
        require(type(match) is acquisition.stages.BootstrapMatch and
                match.record == O.encoded(context["expectedMatch"]), "ENTRY_MATCH_CHANGED")
    require(child["acquiredNs"] <= O.integer(child["queryReturnedNs"]) <= child["completedNs"], "QUERY_RETURN_TIME")
    minimum = (_entry_chain_minimum(fence, context["sourceReturnedNs"], start, row, birth, child, service, ack)
        if entry else native.history.chain_minimum(native.history.snapshot(fence), context["sourceReturnedNs"],
            start, row, birth, child, service, ack))
    checked = fence.now(minimum=minimum)
    result = match, {"phaseSha256": {name: O.digest(data) for name, data in records.items()},
        "childSha256": O.digest(child_raw), "querySessionSha256": O.digest(session), "originalsSha256": child["originalsSha256"],
        "checkedNs": checked}, (context_raw, tuple((name, raw[name]) for name in ORIGINAL_KEYS),
                               start["invocation"], start["startedNs"], start["workEndNs"])
    # Preserve the original preparation's three-value contract. Only the
    # distinct entry window also returns its complete child/session originals.
    return (*result, (child_raw, session)) if entry else result


def _prepare_with_token(cancelled, token):
    """Borrow only the outer parent's stack reference; never reinstall ambient credentials."""
    owner = None
    private = result_raw = worker_identity = worker_originals = service_time_raw = proposal_raw = None
    try:
        first = O.clocks.validate_reading(O.clocks.observe())
        cancel_check = lambda: native.cancellation(cancelled)
        fence = O.Fence(O.prelude(first), minimum=first.nanoseconds, cancelled=cancel_check)
        prelude_raw = fence.raw
        owner = native.Owner(fence.deadline(O.PRELUDE_SECONDS, final=True), fence)
        local_end = owner.local_end
        owner.initial_sources = {}
        require(not native.QUARANTINE and not Q.QUARANTINE and not native.diagnostics._QUARANTINE, "PRIOR_UNKNOWN")
        observed, path, event = host_context(int(time.time()))
        require(observed["role"] == first.clock.role, "ACTUAL_NATIVE_ROLE")
        inherited = Q._inherited_context()
        native.child_environment(path)  # Reject ambient execution overrides before allocation.
        private = owner.new(path)
        owner.write(private, "prelude.json", fence.raw)
        owner.child(private, "control-home", create=True)
        owner.child(private, "temporary", create=True)
        before = source_queries(owner, fence, observed, path / "source-before")
        context_raw = owner.write(private, "context.json", {"schema": 1, "scope": native.INITIAL_CONTEXT_SCOPE,
            "prelude": O.parse(fence.raw), "observed": observed, "eventSha256": O.digest(event), "root": str(ROOT),
            "session": str(path), "job": uuid.uuid4().hex, "inheritedContext": inherited,
            "sourceReturnSha256": O.digest(before.raw), "sourceReturnedNs": O.parse(before.raw)["returnedNs"],
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        _, phase = native.phase(owner, private, context_raw, token, fence)
        token = None
        match, chain, _ = read_phase(owner, private, context_raw, before, phase, fence)
        after = source_queries(owner, fence, observed, path / "source-after")
        require(source_readback(owner, path / "source-after", after) == dict(before.records), "SOURCE_CHANGED_AFTER_CHILD")
        match, chain, captured = read_phase(owner, private, context_raw, before, phase, fence)
        if observed["kind"] == "worker":
            require(observed["github"]["job"] == acquisition.stages.bootstrap.JOB and
                    type(match) is acquisition.stages.BootstrapMatch, "WORKER_MATCH_ONLY")
            worker_identity = initial_identity.bind_worker_match(match, event_raw=event,
                policy_raw=dict(after.records)["candidate_policy_raw"], now=int(time.time()))
            owner.write(private, "worker-identity.json", worker_identity.record)
            worker_originals = captured  # Immutable bytes/scalars, saved before close.
            service_time_raw, proposal_raw = _worker_time_records(worker_identity, worker_originals, fence.clock)
            owner.write(private, "worker-service-time.json", service_time_raw)
            owner.write(private, "worker-allocation-proposal.json", proposal_raw)
        else:
            require(observed["kind"] == "gate" and type(match) is acquisition.gate.GateEligibility,
                    "GATE_CANNOT_MINT_WORKER_IDENTITY")
        result_raw = owner.write(private, "initial-result.json", {"schema": 1, "scope": RESULT_SCOPE,
            "contextSha256": O.digest(context_raw), "sourceBeforeSha256": O.digest(before.raw), "sourceAfterSha256": O.digest(after.raw),
            "matchSha256": O.digest(match.record), "originalChain": chain, "retainedNs": fence.now(),
            "retirement": "PENDING_OWNER_CLOSE", "budgetAcceptance": "NOT_ADMITTED", "workerAdmission": "NOT_PERFORMED",
            "workerIdentitySha256": None if worker_identity is None else O.digest(worker_identity.record),
            "serviceTimeBasisSha256": None if service_time_raw is None else O.digest(service_time_raw),
            "allocationProposalSha256": None if proposal_raw is None else O.digest(proposal_raw),
            "qualificationAcceptance": "NOT_ESTABLISHED", "exportSaveAuthority": False})
    except BaseException as error:
        if owner is None:
            raise
        owner.error("initial-originals", error)
        if private is not None and not owner.unknown:
            try:
                owner.write(private, "initial-failure.json", {"schema": 1, "result": "HOLD", "errors": owner.errors,
                    "retirement": "PENDING_OWNER_CLOSE", "budgetAcceptance": "NOT_ADMITTED"}, final=True)
            except BaseException as secondary:
                owner.error("initial-failure-retention", secondary)
    finally:
        token = None
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                owner.error("initial-owner-close", error)
    if owner.original is not None:
        raise owner.original
    require(result_raw is not None and not owner.unknown, "MISSING_ORIGINALS")
    if worker_identity is not None:
        # A valid pre-close identity cannot survive policy/exception expiry
        # during the actual close. This does not reacquire remote authority or
        # renew firstUseAt; the future productive owner still needs that step.
        require(worker_identity == initial_identity.bind_worker_match(match, event_raw=event,
            policy_raw=worker_identity.original_policy, now=int(time.time())), "WORKER_IDENTITY_CHANGED")
    _original_limits(owner, fence, prelude_raw, local_end, cancel_check)
    fence.now(final=True)
    native.posix._deadline(local_end)
    native.cancellation(cancelled)
    original = _OriginalPreparation(result_raw, worker_identity, service_time_raw, proposal_raw, owner, fence, cancelled, match)
    _PREPARED_RETURNS[id(original)] = _PreparationBinding(original, result_raw, worker_identity,
        None if worker_identity is None else _worker_fields(worker_identity), match, match.record, owner, fence,
        prelude_raw, local_end, cancelled, cancel_check, fence.last, worker_originals, service_time_raw, proposal_raw)
    return original


@dataclass(frozen=True, repr=False)
class _ReadmissionReturn:
    """One actual closed, nonproductive return; no disk/CLI reconstruction."""
    raw: bytes
    claim: _ReadmissionClaim
    owner: object
    window: _ReadmissionWindow
    path: Path
    service_time_raw: bytes
    proposal_raw: bytes


@dataclass(frozen=True, repr=False)
class _ReadmissionBinding:
    returned: _ReadmissionReturn
    raw: bytes
    claim: _ReadmissionClaim
    owner: object
    window: _ReadmissionWindow
    path: Path
    evidence: tuple
    resources: tuple
    preclose_ns: int
    closed_ns: int


def _source_pin(value):
    require(type(value) is SourceReturn and type(value.records) is tuple and
            tuple(name for name, _raw in value.records) == SOURCE_KEYS and
            all(type(row) is tuple and len(row) == 2 and type(row[0]) is str and type(row[1]) is bytes
                for row in value.records) and type(value.session) is bytes and type(value.raw) is bytes, "ENTRY_SOURCE_PIN")
    return value, value.records, value.session, value.raw


def _phase_pin(value):
    require(type(value) is native.OriginalPhase and type(value.context) is bytes and type(value.records) is tuple and
            len(value.records) == len(native.PHASE_FILES) and
            all(type(row) is tuple and len(row) == 2 and type(row[0]) is str and type(row[1]) is bytes
                for row in value.records) and set(dict(value.records)) == native.PHASE_FILES, "ENTRY_PHASE_PIN")
    return value, value.context, value.records


def _readmission_known(owner, window, resources):
    state = window.checked()
    require(state.owner is not None and state.owner[0] is owner and state.resources is resources and
            len(owner.resources) == len(resources) and owner.closed is True, "ENTRY_CLOSE_ROSTER")
    for current, (row, label, resource) in zip(owner.resources, resources):
        require(current is row and row["label"] == label and row["owner"] is resource and
                row["attempted"] is True and row["closed"] is True, "ENTRY_CLOSE_ROSTER")


def _readmission_record(claim, window_raw, pending_raw, preclose_ns, closed_ns, count):
    original = claim.binding
    return {"schema": 1, "scope": READMISSION_SCOPE, "originalPreparationSha256": O.digest(original.raw),
        "workerIdentitySha256": O.digest(original.identity_fields[0]), "pendingSha256": O.digest(pending_raw),
        "serviceTimeBasisSha256": O.digest(original.service_time_raw), "allocationProposalSha256": O.digest(original.proposal_raw),
        "window": O.parse(window_raw), "firstUseAt": O.parse(original.match_raw)["firstUseAt"],
        "preCloseNs": preclose_ns, "closedNs": closed_ns, "resourceCount": count,
        "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "budgetAcceptance": "NOT_ADMITTED", "workerAdmission": "NOT_PERFORMED",
        "qualificationAcceptance": "NOT_ESTABLISHED", "exportSaveAuthority": False}


def _readmission_content(binding):
    """Final data-only check against pre-close originals, never a new observation."""
    result, claim, owner, window = binding.returned, binding.claim, binding.owner, binding.window
    original = _retired_worker(claim)
    require(type(original.cancelled) is list and len(original.cancelled) == 0, "ENTRY_FINAL_CANCELLED")
    require(type(result) is _ReadmissionReturn and result.claim is claim and result.owner is owner and
            result.window is window and type(result.path) is type(binding.path) and result.path == binding.path and
            type(result.service_time_raw) is bytes and result.service_time_raw == original.service_time_raw and
            type(result.proposal_raw) is bytes and result.proposal_raw == original.proposal_raw, "ENTRY_RETURN_CHANGED")
    _readmission_known(owner, window, binding.resources)
    state = window.checked()
    require(state.terminal and not state.busy and not state.failed and state.phase is None and
            owner.original is None and owner.unknown is False and owner.errors == [], "ENTRY_RETURN_NOT_SUCCESSFUL")
    frame_raw, context_raw, before, after, phase, captured, child, session, match, match_raw, chain_raw, pending_raw = binding.evidence
    require(frame_raw == state.raw and owner.phase_originals is phase[0] and
            _phase_pin(phase[0])[1:] == phase[1:] and phase[1] == context_raw and
            set(owner.initial_sources) == {str(binding.path / "source-before"), str(binding.path / "source-after")},
            "ENTRY_ORIGINAL_GRAPH_CHANGED")
    for name, saved in (("source-before", before), ("source-after", after)):
        require(owner.initial_sources[str(binding.path / name)] is saved[0] and _source_pin(saved[0])[1:] == saved[1:],
                "ENTRY_SOURCE_RETURN_CHANGED")
    require(type(match) is acquisition.stages.BootstrapMatch and type(match.record) is bytes and
            match.record == match_raw == original.match_raw and _service_job(captured, state.clock) == claim.service_job,
            "ENTRY_ORIGINAL_JOB_OR_MATCH_CHANGED")
    chain = O.parse(chain_raw)
    require(chain["childSha256"] == O.digest(child) and chain["querySessionSha256"] == O.digest(session) and
            chain["originalsSha256"] == {name: O.digest(raw) for name, raw in captured[1]} and
            chain["phaseSha256"] == {name: O.digest(raw) for name, raw in phase[2]}, "ENTRY_ORIGINAL_BYTES_CHANGED")
    times = (state.first, chain["checkedNs"], O.parse(pending_raw)["retainedNs"], binding.preclose_ns, binding.closed_ns)
    require(all(type(x) is int and 0 <= x <= O.clocks.UINT64 for x in times) and list(times) == sorted(times) and
            binding.preclose_ns < state.work and binding.closed_ns == state.last < state.final, "ENTRY_RETURN_CLOCK")
    raw = O.encoded(_readmission_record(claim, frame_raw, pending_raw, binding.preclose_ns, binding.closed_ns,
                                       len(binding.resources)))
    require(type(result.raw) is bytes and result.raw == binding.raw == raw, "ENTRY_RETURN_BYTES_CHANGED")
    return result


def check_readmission_return(result):
    """Exact historical in-call return only: no live authority, I/O, renewal or grant."""
    binding = _READMISSION_RETURNS.get(id(result))
    require(type(result) is _ReadmissionReturn and type(binding) is _ReadmissionBinding and binding.returned is result,
            "NOT_ORIGINAL_READMISSION_RETURN")
    return _readmission_content(binding)


def _readmit_worker(claim, token):
    """Fresh actual source/HTTP/native enclosure, clamped to the first proposal.

    Only the private two-acquisition parent supplies the token. No old handle is
    reopened and no old fence is observed, even during failure cleanup.
    """
    owner = window = private = evidence = preclose_ns = None
    resources = ()
    try:
        original = _begin_readmission(claim)
        native.cancellation(original.cancelled)
        local = time.monotonic()  # LOCAL before RAW; never reissue this ceiling.
        first = O.clocks.validate_reading(O.clocks.observe())
        O.clocks.elapsed_ns(O.clocks.Reading(original.fence.clock, original.last_ns), first)
        proposal = O.parse(original.proposal_raw)
        work, final = _entry_limits(first.nanoseconds, proposal["phaseFencesNs"]["productive-entry"], proposal["proposedJobEndNs"])
        raw = O.encoded({"schema": 1, "scope": ENTRY_WINDOW_SCOPE, "clock": O.clock_value(first.clock),
            "firstNs": first.nanoseconds, "previousNs": original.last_ns, "workEndNs": work, "finalEndNs": final,
            "firstUseAt": O.parse(original.match_raw)["firstUseAt"],
            "originalProductiveEntryEndNs": proposal["phaseFencesNs"]["productive-entry"],
            "originalProposedJobEndNs": proposal["proposedJobEndNs"], "originalPreparationSha256": O.digest(original.raw),
            "workerIdentitySha256": O.digest(original.identity_fields[0]), "originalProposalSha256": O.digest(original.proposal_raw),
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        cancel_check = lambda: native.cancellation(original.cancelled)
        window = _ReadmissionWindow(raw, minimum=first.nanoseconds, cancelled=cancel_check)
        local_end = O.wire._directed_deadline(local, 120, final, first.nanoseconds)
        owner = native.Owner(local_end, window, first=first, cancelled=cancel_check)
        owner.initial_sources = {}
        window.bind_owner(owner, first)
        require(not native.QUARANTINE and not Q.QUARANTINE and not native.diagnostics._QUARANTINE, "PRIOR_UNKNOWN")
        current = initial_identity.bind_worker_match(original.match, event_raw=original.identity_fields[1],
            policy_raw=original.identity_fields[2], now=int(time.time()))
        require(_worker_fields(current) == original.identity_fields, "ENTRY_POLICY_CHANGED")
        observed, path, event = host_context(O.parse(original.match_raw)["firstUseAt"], entry=True)
        require(event == original.identity_fields[1] and observed == O.parse(original.worker_originals[0])["observed"],
                "ENTRY_ACTUAL_CONTEXT_CHANGED")
        inherited = Q._inherited_context()
        native.child_environment(path)
        private = owner.new(path)  # Exclusive fixed sibling; no retry/overwrite/migration.
        owner.write(private, "entry-window.json", raw)
        owner.child(private, "control-home", create=True)
        owner.child(private, "temporary", create=True)
        before = source_queries(owner, window, observed, path / "source-before")
        before_pin = _source_pin(before)
        require(dict(before.records) == {name: dict(original.worker_originals[1])[name] for name in SOURCE_KEYS},
                "ENTRY_ORIGINAL_SOURCE_CHANGED")
        context_raw = owner.write(private, "context.json", {"schema": 1, "scope": native.INITIAL_ENTRY_CONTEXT_SCOPE,
            "entryWindow": O.parse(raw), "expectedMatch": O.parse(original.match_raw), "originalProposal": proposal,
            "observed": observed, "eventSha256": O.digest(event), "root": str(ROOT), "session": str(path),
            "job": uuid.uuid4().hex, "inheritedContext": inherited, "sourceReturnSha256": O.digest(before.raw),
            "sourceReturnedNs": O.parse(before.raw)["returnedNs"], "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        _, phase = native.phase(owner, private, context_raw, token, window)
        token = None
        phase_pin = _phase_pin(phase)
        match, _chain, captured, _child = read_phase(owner, private, context_raw, before, phase, window)
        require(match.record == original.match_raw and _service_job(captured, window.clock) == claim.service_job,
                "ENTRY_JOB_OR_MATCH_CHANGED")
        after = source_queries(owner, window, observed, path / "source-after")
        after_pin = _source_pin(after)
        require(source_readback(owner, path / "source-after", after) == dict(before.records), "SOURCE_CHANGED_AFTER_CHILD")
        match, chain, captured, (child_raw, session) = read_phase(owner, private, context_raw, before, phase, window)
        require(match.record == original.match_raw and _service_job(captured, window.clock) == claim.service_job,
                "ENTRY_JOB_OR_MATCH_CHANGED")
        current = initial_identity.bind_worker_match(match, event_raw=event,
            policy_raw=dict(after.records)["candidate_policy_raw"], now=int(time.time()))
        require(_worker_fields(current) == original.identity_fields, "ENTRY_IDENTITY_CHANGED")
        pending = owner.write(private, "entry-pending.json", {"schema": 1, "scope": ENTRY_PENDING_SCOPE,
            "originalPreparationSha256": O.digest(original.raw), "windowSha256": O.digest(raw),
            "contextSha256": O.digest(context_raw), "sourceBeforeSha256": O.digest(before.raw),
            "sourceAfterSha256": O.digest(after.raw), "matchSha256": O.digest(match.record), "originalChain": chain,
            "retainedNs": window.now(), "retirement": "PENDING_OWNER_CLOSE", "budgetAcceptance": "NOT_ADMITTED",
            "workerAdmission": "NOT_PERFORMED", "qualificationAcceptance": "NOT_ESTABLISHED", "exportSaveAuthority": False})
        # Keep originals and source/phase object references BEFORE closing. Hash
        # dictionaries alone cannot preserve the byte or return provenance.
        evidence = (raw, context_raw, before_pin, after_pin, phase_pin, captured,
                    child_raw, session, match, match.record, O.encoded(chain), pending)
        require(owner.read(private, "entry-pending.json") == pending, "ENTRY_PENDING_CHANGED")
        _retired_worker(claim)
        preclose_ns = window.now()
    except BaseException as error:
        if owner is None:
            raise
        owner.error("initial-readmission", error)
        if private is not None and not owner.unknown:
            try:
                owner.write(private, "entry-failure.json", {"schema": 1, "result": "HOLD", "errors": owner.errors,
                    "retirement": "PENDING_OWNER_CLOSE", "budgetAcceptance": "NOT_ADMITTED"}, final=True)
            except BaseException as secondary:
                owner.error("entry-failure-retention", secondary)
    finally:
        token = None
        if owner is not None:
            try:
                resources = window.checked().resources
            except BaseException as error:
                resources = _ENTRY_WINDOWS[id(window)].resources
                owner.error("entry-resource-snapshot", error, unknown=True)
            try:
                owner.close()
            except BaseException as error:
                owner.error("entry-owner-close", error)
    try:
        _readmission_known(owner, window, resources)
    except BaseException as error:
        owner.error("entry-owner-close-return", error, unknown=True)
    if owner.unknown and not any(value is owner for value in native.QUARANTINE):
        native.QUARANTINE.append(owner)  # Window registry also retains the independently saved resources.
    if owner.original is not None:
        raise owner.original
    try:
        require(evidence is not None and preclose_ns is not None, "ENTRY_INCOMPLETE")
        current = initial_identity.bind_worker_match(original.match, event_raw=original.identity_fields[1],
            policy_raw=original.identity_fields[2], now=int(time.time()))
        require(_worker_fields(current) == original.identity_fields, "ENTRY_FINAL_POLICY_CHANGED")
        closed = window.now(final=True, minimum=preclose_ns)
        native.posix._deadline(local_end)
        native.cancellation(original.cancelled)
        state = window.checked()  # Last boundary was above; only data checks follow.
        _ENTRY_WINDOWS[id(window)] = replace(state, terminal=True)
        raw = O.encoded(_readmission_record(claim, evidence[0], evidence[-1], preclose_ns, closed, len(resources)))
        returned = _ReadmissionReturn(raw, claim, owner, window, path, original.service_time_raw, original.proposal_raw)
        binding = _ReadmissionBinding(returned, raw, claim, owner, window, path, evidence, resources, preclose_ns, closed)
        _readmission_content(binding)
        _READMISSION_RETURNS[id(returned)] = binding
        return returned
    except BaseException as error:
        owner.error("entry-final-return", error)
        raise owner.original


def _prepare_and_readmit_worker(cancelled):
    """Dormant two-acquisition stack; never a workflow/CLI execution entry."""
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    try:
        location(entry=True)  # Gate/foreign inputs refuse before the first acquisition.
        original = _prepare_with_token(cancelled, token)
        claim = _claim_worker(original)
        return _readmit_worker(claim, token)
    finally:
        token = None


def _prepare_originals(cancelled):
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    try:
        return _prepare_with_token(cancelled, token)
    finally:
        token = None


def prepare_originals(cancelled):
    original = _prepare_originals(cancelled)
    # The CLI still emits only a pending-step digest. It does not serialize or
    # transfer the original-call capability or issue productive Admission.
    return native.public_result(OUTPUT_SCOPE, "initialOriginalsSha256", original.raw), original._fence, original._fence.final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    commands.add_parser("prepare-originals")
    for name in ("_service", "_service-entry"):
        child = commands.add_parser(name)
        child.add_argument("--context-sha256", required=True)
        child.add_argument("--minimum-ns", required=True)
    args = parser.parse_args()
    try:
        require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode, "ISOLATED_INTERPRETER")
        if args.operation == "prepare-originals":
            native.guarded(prepare_originals)
        else:
            require(re.fullmatch(r"0|[1-9][0-9]{0,19}", args.minimum_ns), "LAUNCH_MINIMUM")
            minimum = O.integer(int(args.minimum_ns))
            entry = args.operation == "_service-entry"
            command = native.initial_entry_command if entry else native.initial_command
            command(args.context_sha256, minimum)
            native.guarded(lambda cancelled: service_child(args.context_sha256, minimum, cancelled, entry=entry))
        return 0
    except BaseException:
        print("INITIAL_RECIPIENT_ORIGINALS_NOT_ACCEPTED", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
