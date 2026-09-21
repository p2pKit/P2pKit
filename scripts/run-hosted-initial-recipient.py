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
AUTHORITY_WINDOW_SCOPE = "INITIAL_RECIPIENT_USE_AUTHORITY_SOURCE_CAP_V1"
AUTHORITY_CHILD_SCOPE = "INITIAL_RECIPIENT_USE_AUTHORITY_PENDING_CHILD_CLOSE_V1"
AUTHORITY_CONTEXT_FIELDS = (CONTEXT_FIELDS - {"prelude"}) | {"authorityWindow", "expectedMatch", "originalProposal"}
RECIPIENT_WINDOW_SCOPE = "INITIAL_RECIPIENT_VALIDATION_SOURCE_CAP_V1"
RECIPIENT_CONTEXT_SCOPE = "INITIAL_RECIPIENT_VALIDATION_CHILD_CONTEXT_V1"
RECIPIENT_START_SCOPE = "INITIAL_RECIPIENT_VALIDATION_PRELAUNCH_V1"
RECIPIENT_CHILD_SCOPE = "INITIAL_RECIPIENT_VALIDATION_PENDING_CHILD_CLOSE_V1"
RECIPIENT_RETURN_SCOPE = "INITIAL_RECIPIENT_VALIDATION_CLOSED_HISTORY_V1"
RECIPIENT_SENDER_SCOPE = "INITIAL_RECIPIENT_SENDER_PENDING_OWNER_CLOSE_V1"
RECIPIENT_OUTPUT_SCOPE = "INITIAL_RECIPIENT_SENDER_PENDING_STEP_RETURN_V1"
_PREPARED_RETURNS = {}
_WORKER_USE_LOCK = threading.Lock()
_WORKER_USES, _WORKER_CLAIMS, _ENTRY_WINDOWS, _READMISSION_RETURNS = {}, {}, {}, {}
_READMISSION_ATTEMPTS = {}
_RECIPIENT_USE_LOCK = threading.Lock()
_READMISSION_USES, _RECIPIENT_ATTEMPTS, _RECIPIENT_CLAIMS = {}, {}, {}
_RECIPIENT_WINDOWS, _AUTHORITY_WINDOWS, _AUTHORITY_RETURNS, _RECIPIENT_RETURNS = {}, {}, {}, {}
_RECIPIENT_NATIVE_RETURNS = {}
_RECIPIENT_SENDERS = {}


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
    authority = type(fence) is _RecipientAuthorityWindow
    require(entry or authority or type(fence) is O.Fence, "CONTEXT_WINDOW")
    scope = (native.INITIAL_AUTHORITY_CONTEXT_SCOPE if authority else
             native.INITIAL_ENTRY_CONTEXT_SCOPE if entry else native.INITIAL_CONTEXT_SCOPE)
    fields = AUTHORITY_CONTEXT_FIELDS if authority else ENTRY_CONTEXT_FIELDS if entry else CONTEXT_FIELDS
    frame_key = "authorityWindow" if authority else "entryWindow" if entry else "prelude"
    require(set(value) == fields and raw == O.encoded(value) and
            type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == scope and
            value[frame_key] == O.parse(fence.raw) and
            value["root"] == str(ROOT) and value["session"] == str(path)
            and value["budgetAcceptance"] == "NOT_ADMITTED" and value["exportSaveAuthority"] is False, "CONTEXT")
    require(type(value["observed"]) is dict, "CONTEXT_OBSERVATION")
    if authority:
        observed, actual_path, event = _recipient_host(value["observed"].get("firstUseAt"))
        actual_path /= "authority"
    else:
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
    elif authority:
        _authority_context_bindings(value, fence)
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
    return _service_chain_minimum(fence.first, returned, start, row, birth, child, service, ack)


def _service_chain_minimum(first, returned, start, row, birth, child, service, ack):
    """Only shared HTTP timestamp arithmetic; callers validate their exact frame."""
    times = [first, returned, start["startedNs"], row["launchMinimumNs"], child["beganNs"],
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
    elif type(fence) is _RecipientAuthorityWindow:
        _authority_phase_start(fence, context["sourceReturnedNs"], value)
    else:
        native.history.phase_start(native.history.snapshot(fence), context["sourceReturnedNs"], value)
    env = native.processes.ownership_environment(context["inheritedContext"], context["job"], value["invocation"],
        str(path), str(path / "control-home"), allow_new_context=True)
    require(value["inheritedContext"] == {name: env[name] for name in Q._CONTEXT}, "ORIGINAL_ANCESTORS")
    return value


def service_child(context_hash, minimum, cancelled, *, entry=False, authority=False):
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    owner = fence = directory = result_raw = None
    supplier = None
    try:
        require(type(entry) is bool and type(authority) is bool and not (entry and authority), "SERVICE_OPERATION")
        local_start = time.monotonic()
        local_end = local_start + O.wire.ACQUIRE_SECONDS
        first = O.clocks.validate_reading(O.clocks.observe())
        require(first.nanoseconds >= O.integer(minimum), "CHILD_PRECEDES_LAUNCH")
        owner = native.Owner(local_end, first=first, cancelled=lambda: native.cancellation(cancelled))
        if authority:
            path = _recipient_path() / "authority"
        else:
            _, path = location(entry=entry)
        private = owner.open(path)
        context_raw = owner.read(private, "context.json")
        require(O.digest(context_raw) == context_hash, "CHILD_CONTEXT_CHANGED")
        context = O.parse(context_raw)
        check_cancel = lambda: native.cancellation(cancelled)
        fence = (_RecipientAuthorityWindow.child(O.encoded(context["authorityWindow"]), first, local_start, check_cancel)
                 if authority else
                 _ReadmissionWindow(O.encoded(context["entryWindow"]), minimum=first.nanoseconds, cancelled=check_cancel)
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
                expected=acquisition.stages.BootstrapMatch(O.encoded(context["expectedMatch"])) if entry or authority else None)
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
        result_raw = owner.write(directory, "child-result.json", {"schema": 1,
            "scope": AUTHORITY_CHILD_SCOPE if authority else ENTRY_CHILD_SCOPE if entry else CHILD_SCOPE,
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
    return {"schema": 1, "scope": (native.INITIAL_AUTHORITY_ACK_SCOPE if authority else
            native.INITIAL_ENTRY_ACK_SCOPE if entry else native.INITIAL_ACK_SCOPE), "invocation": domain["id"],
            "terminalSha256": O.digest(result_raw), "clock": O.clock_value(fence.clock), "closedNs": closed}, fence, start["workEndNs"]


def _retained_match_inputs(context, raw, invocation, clock, work_start, work_end):
    """Interpret supplied HTTP/source bytes, without a clock or authority acquisition."""
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
        args.update(stage="stage1", approvals_raw=approval, comment_raw=comment,
            environment_raw=env_raw, branches_raw=branches, observation_raw=I.encoded(observation),
            expected=acquisition.gate.GateEligibility(raw["match"]))
    else:
        require(observed["kind"] == "worker", "RETAINED_MATCH_KIND")
        observation["github"].update(profile=acquisition.stages.bootstrap.PROFILE, selection=observed["inputs"]["selection"])
        args.update(comment_raw=comment, comment_id=selector["commentId"],
            body_sha256=selector["bodySha256"], observation_raw=I.encoded(observation),
            expected=acquisition.stages.BootstrapMatch(raw["match"]))
    require(raw["observation"] == I.encoded(observation), "OBSERVATION_CHANGED")
    return observed["kind"], args, {"firstNs": times[0], "lastNs": times[-1], "numericJobId": job["id"],
        "runnerName": observed["runnerName"],
        "selector": acquisition.GATE_SELECTOR if observed["kind"] == "gate" else O.SERVICE_SELECTORS[clock.role],
        "jobStartedAt": job["started_at"], "originDateEpochSeconds": jobs_date,
        "jobsRequestStartedNs": jobs_started,
        "originalsSha256": {name: O.digest(raw[name]) for name in HTTP_KEYS},
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}


def _retained_match_at(inputs, *, now):
    """Supplied-time predicate only; it cannot establish original/current currency."""
    kind, args, service = inputs
    require(kind in ("gate", "worker"), "RETAINED_MATCH_KIND")
    matcher = acquisition.gate.eligible if kind == "gate" else acquisition.stages.match_bootstrap
    return matcher(now=now, **args), service


def retained_match(context, raw, invocation, clock, work_start, work_end):
    """Live callers still sample wall time AFTER interpreting all original records."""
    inputs = _retained_match_inputs(context, raw, invocation, clock, work_start, work_end)
    return _retained_match_at(inputs, now=int(time.time()))


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
    return _worker_time_values(identity, service, clock, invocation)


def _worker_time_values(identity, service, clock, invocation):
    """Pure basis/proposal encoding; supplied service data is not provenance or a budget."""
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
    authority = type(fence) is _RecipientAuthorityWindow
    frame_name = "authority-window.json" if authority else "entry-window.json" if entry else "prelude.json"
    require(owner.read(private, "context.json") == context_raw and
            owner.read(private, frame_name) == fence.raw,
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
            ack["scope"] == (native.INITIAL_AUTHORITY_ACK_SCOPE if authority else
                            native.INITIAL_ENTRY_ACK_SCOPE if entry else native.INITIAL_ACK_SCOPE) and
            ack["invocation"] == start["invocation"] and ack["terminalSha256"] == O.digest(child_raw) and
            ack["clock"] == O.clock_value(fence.clock), "CHILD_ACK")
    require(set(child) == {"schema", "scope", "contextSha256", "startSha256", "invocation", "clock", "launchMinimumNs", "beganNs",
            "metadataLastNs", "acquiredNs", "queryReturnedNs", "querySessionSha256", "originalsSha256", "matchSha256", "completedNs",
            "retirement", "errors"} and type(child["schema"]) is int and child["schema"] == 1 and
            child["scope"] == (AUTHORITY_CHILD_SCOPE if authority else ENTRY_CHILD_SCOPE if entry else CHILD_SCOPE) and
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
    if entry or authority:
        require(type(match) is acquisition.stages.BootstrapMatch and
                match.record == O.encoded(context["expectedMatch"]), "ENTRY_MATCH_CHANGED")
    require(child["acquiredNs"] <= O.integer(child["queryReturnedNs"]) <= child["completedNs"], "QUERY_RETURN_TIME")
    minimum = (_authority_chain_minimum(fence, context["sourceReturnedNs"], start, row, birth, child, service, ack)
        if authority else _entry_chain_minimum(fence, context["sourceReturnedNs"], start, row, birth, child, service, ack)
        if entry else native.history.chain_minimum(native.history.snapshot(fence), context["sourceReturnedNs"],
            start, row, birth, child, service, ack))
    checked = fence.now(minimum=minimum)
    result = match, {"phaseSha256": {name: O.digest(data) for name, data in records.items()},
        "childSha256": O.digest(child_raw), "querySessionSha256": O.digest(session), "originalsSha256": child["originalsSha256"],
        "checkedNs": checked}, (context_raw, tuple((name, raw[name]) for name in ORIGINAL_KEYS),
                               start["invocation"], start["startedNs"], start["workEndNs"])
    # Preserve the original preparation's three-value contract. Only the
    # distinct entry window also returns its complete child/session originals.
    return (*result, (child_raw, session)) if entry or authority else result


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
    marker, binding = _begin_readmission_use(result)
    try:
        return _readmission_content(binding)
    finally:
        _end_readmission_use(result, marker)


def _begin_readmission_use(result, *, consume=False):
    binding = _READMISSION_RETURNS.get(id(result))
    require(type(result) is _ReadmissionReturn and type(binding) is _ReadmissionBinding and binding.returned is result,
            "NOT_ORIGINAL_READMISSION_RETURN")
    marker = object()
    with _RECIPIENT_USE_LOCK:
        require(_READMISSION_RETURNS.get(id(result)) is binding, "READMISSION_REGISTRY_CHANGED")
        require(id(result) not in _RECIPIENT_ATTEMPTS, "READMISSION_ALREADY_CLAIMED")
        require(id(result) not in _READMISSION_USES, "READMISSION_USE_IN_PROGRESS")
        _READMISSION_USES[id(result)] = marker
        if consume:
            _RECIPIENT_ATTEMPTS[id(result)] = (result, marker)
    return marker, binding


def _end_readmission_use(result, marker):
    with _RECIPIENT_USE_LOCK:
        require(_READMISSION_USES.get(id(result)) is marker, "READMISSION_USE_CHANGED")
        del _READMISSION_USES[id(result)]


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


def _recipient_path():
    kind, path = location()
    require(kind == "worker", "RECIPIENT_WORKER_ONLY")
    return path.with_name(path.name + "-recipient")


def _recipient_host(first_use_at):
    observed, _path, event = host_context(first_use_at)
    require(observed["kind"] == "worker", "RECIPIENT_WORKER_ONLY")
    return observed, _recipient_path(), event


def _history_graph(*roots):
    """Finite pins of the closed Stage1 records, not a live reader or object codec."""
    records = (_ReadmissionReturn, _ReadmissionBinding, _ReadmissionClaim, _PreparationBinding,
        _OriginalPreparation, _EntryWindowBinding, _ReadmissionWindow, SourceReturn, native.Owner,
        native.OriginalPhase, O.Fence, O.clocks.Reading, O.clocks.ClockIdentity,
        initial_identity.InitialBootstrapIdentity, acquisition.stages.BootstrapMatch,
        _AuthorityReturn, _AuthorityState, _RecipientRoster, _RecipientNativeReturn, _RecipientValidationReturn,
        _RecipientState)
    scalars = (type(None), bool, int, float, str, bytes)
    pending, seen, nodes = list(roots), set(), []
    while pending:
        value = pending.pop()
        kind = type(value)
        if kind in scalars or id(value) in seen:
            continue
        seen.add(id(value))
        require(len(seen) <= 10000, "RECIPIENT_HISTORY_LIMIT")
        if kind is dict:
            saved, mode = tuple(value.items()), "mapping"
            require(all(type(key) in scalars for key, _ in saved), "RECIPIENT_HISTORY_KEY")
            pending.extend(item for pair in saved for item in pair)
        elif kind in (tuple, list):
            saved, mode = tuple(value), "sequence"
            pending.extend(saved)
        elif kind in records:
            saved, mode = object.__getattribute__(value, "__dict__"), "record"
            pending.append(saved)
        elif kind is type(ROOT):
            saved, mode = (str(value), value.parts, value.drive, value.root), "path"
        else:
            saved, mode = None, "opaque"  # Callbacks/retired resources: reference only, never invoked.
        nodes.append((value, kind, mode, saved))
    return tuple(nodes)


def _check_history(nodes):
    scalars = (type(None), bool, int, float, str, bytes)
    def same(value, saved):
        return value is saved or type(value) is type(saved) and type(saved) in scalars and value == saved
    for value, kind, mode, saved in nodes:
        require(type(value) is kind, "RECIPIENT_HISTORY_CHANGED")
        if mode == "record":
            valid = object.__getattribute__(value, "__dict__") is saved
        elif mode == "mapping":
            valid = len(value) == len(saved) and all(same(key, old_key) and same(item, old_item)
                for (key, item), (old_key, old_item) in zip(value.items(), saved))
        elif mode == "sequence":
            valid = len(value) == len(saved) and all(same(item, old) for item, old in zip(value, saved))
        elif mode == "path":
            valid = (str(value), value.parts, value.drive, value.root) == saved
        else:
            valid = mode == "opaque"
        require(valid, "RECIPIENT_HISTORY_CHANGED")


@dataclass(frozen=True, repr=False)
class _RecipientClaim:
    original: _ReadmissionReturn


def _claim_recipient(result):
    marker, binding = _begin_readmission_use(result, consume=True)
    try:
        _readmission_content(binding)
        original = binding.claim.binding
        entry_state = _ENTRY_WINDOWS[id(binding.window)]
        nodes = _history_graph(result, binding, original, entry_state)
        claim = _RecipientClaim(result)
        # These independent tuples, not the published claim's mutable fields,
        # retain the first basis, clock, cancellation and the closed record graph.
        saved = (claim, result, binding, original, entry_state, nodes,
            _READMISSION_RETURNS, _PREPARED_RETURNS, _ENTRY_WINDOWS, _WORKER_CLAIMS)
        with _RECIPIENT_USE_LOCK:
            require(_READMISSION_USES.get(id(result)) is marker and
                    _RECIPIENT_ATTEMPTS.get(id(result)) == (result, marker), "RECIPIENT_CLAIM_CHANGED")
            _RECIPIENT_ATTEMPTS[id(result)] = (result, claim)
            _RECIPIENT_CLAIMS[id(claim)] = saved
        _recipient_claim(claim)
        return claim
    finally:
        _end_readmission_use(result, marker)


def _recipient_claim(claim):
    saved = _RECIPIENT_CLAIMS.get(id(claim))
    require(type(claim) is _RecipientClaim and type(saved) is tuple and len(saved) == 10 and saved[0] is claim and
            claim.original is saved[1] and _RECIPIENT_ATTEMPTS.get(id(saved[1])) == (saved[1], claim),
            "NOT_ORIGINAL_RECIPIENT_CLAIM")
    _, result, binding, original, entry_state, nodes, returns, prepared, windows, workers = saved
    require(returns is _READMISSION_RETURNS and returns.get(id(result)) is binding and
            prepared is _PREPARED_RETURNS and prepared.get(id(original.original)) is original and
            windows is _ENTRY_WINDOWS and windows.get(id(binding.window)) is entry_state and
            workers is _WORKER_CLAIMS and workers.get(id(original.original)) is binding.claim,
            "RECIPIENT_HISTORY_REGISTRY_CHANGED")
    _check_history(nodes)  # No old fence/owner observation, parsing, callback or I/O.
    require(type(original.cancelled) is list and original.cancelled == [], "RECIPIENT_CANCELLED")
    return binding, original


class _RecipientRoster:
    """Original resource references for one new Owner, including failed returns."""
    def __init__(self, owner, window, first):
        require(type(owner) is native.Owner and owner.fence is window and owner.first is first and
                owner.resources == [] and owner.errors == [], "RECIPIENT_OWNER_BINDING")
        self.owner, self.window, self.first = owner, window, first
        self.local, self.cancelled = owner.local_end, owner.cancelled
        self.rows, self.errors, self.sources = owner.resources, owner.errors, owner.initial_sources
        self.seen, self.frozen = [], None

    def check(self, limits=(None, None)):
        owner = self.owner
        seen = {(id(row), id(resource)) for row, _label, resource, _a, _c in self.seen}
        for rows in (self.rows,) if owner.resources is self.rows else (self.rows, owner.resources):
            if type(rows) is list:
                for row in rows:
                    label, resource = (row.get("label"), row.get("owner")) if type(row) is dict else (None, None)
                    if (id(row), id(resource)) not in seen:
                        self.seen.append((row, label, resource, False, False))
                        seen.add((id(row), id(resource)))
        try:
            require(owner.resources is self.rows and len(self.rows) == len(self.seen) and
                    owner.errors is self.errors and owner.initial_sources is self.sources and
                    owner.fence is self.window and owner.first is self.first and owner.cancelled is self.cancelled and
                    type(owner.local_end) is float and owner.local_end == self.local and
                    owner.early_last == self.first.nanoseconds and
                    all(type(a) is type(b) and a == b for a, b in zip((owner.work_limit, owner.final_limit), limits)),
                    "RECIPIENT_OWNER_CHANGED")
            if self.frozen is not None:
                require(len(self.rows) == len(self.frozen) and all(row is saved for row, saved in
                        zip(self.rows, self.frozen)), "RECIPIENT_CLOSE_ROSTER_CHANGED")
            for index, (row, label, resource, attempted, closed) in enumerate(self.seen):
                require(self.rows[index] is row and type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"}
                    and row["owner"] is resource and row["label"] == label and
                    label in ("directory", "writer", "stdout", "stderr", "native-scope") and
                    type(row["attempted"]) is bool and type(row["closed"]) is bool and
                    (not row["closed"] or row["attempted"]) and (not attempted or row["attempted"]) and
                    (not closed or row["closed"]), "RECIPIENT_RESOURCE_CHANGED")
                if (attempted, closed) != (row["attempted"], row["closed"]):
                    self.seen[index] = (row, label, resource, row["attempted"], row["closed"])
        except BaseException as error:
            owner.error("recipient-resource-binding", error, unknown=True)
            raise

    def freeze(self):
        self.check()
        require(self.frozen is None and not self.owner.closed, "RECIPIENT_CLOSE_REENTRY")
        self.frozen = tuple(self.rows)

    def known(self):
        self.check()
        require(self.frozen is not None and self.owner.closed and not self.owner.unknown and
                all(attempted and closed for _row, _label, _resource, attempted, closed in self.seen),
                "RECIPIENT_CLOSE_INCOMPLETE")


def _recipient_frame(raw):
    value = O.parse(raw)
    require(type(raw) is bytes and raw == O.encoded(value) and set(value) == {"schema", "scope", "clock", "firstNs",
        "previousNs", "workEndNs", "finalEndNs", "readEndNs", "firstUseAt", "originalReadmissionSha256",
        "workerIdentitySha256", "originalProposalSha256", "originalFencesNs", "originalProposedJobEndNs",
        "budgetAcceptance", "exportSaveAuthority"} and type(value["schema"]) is int and value["schema"] == 1 and
        value["scope"] == RECIPIENT_WINDOW_SCOPE and value["budgetAcceptance"] == "NOT_ADMITTED" and
        value["exportSaveAuthority"] is False, "RECIPIENT_FRAME")
    clock = O.wire.clock_identity(value["clock"])
    first = O.integer(value["firstNs"], O.integer(value["previousNs"]))
    fences = value["originalFencesNs"]
    require(type(fences) is dict and set(fences) == {"recipient-validation", "recipient-final", "recipient-read"},
            "RECIPIENT_FRAME_FENCES")
    ends = tuple(min(O.integer(first + seconds * O.NS), O.integer(fences[name]),
        O.integer(value["originalProposedJobEndNs"])) for seconds, name in
        ((240, "recipient-validation"), (285, "recipient-final"), (315, "recipient-read")))
    require(first < ends[0] <= ends[1] <= ends[2] and all(type(value[name]) is int and value[name] == end
        for name, end in zip(("workEndNs", "finalEndNs", "readEndNs"), ends)), "RECIPIENT_FRAME_FENCES")
    O.integer(value["firstUseAt"], 1)
    require(all(type(value[name]) is str and re.fullmatch(r"[0-9a-f]{64}", value[name]) for name in
        ("originalReadmissionSha256", "workerIdentitySha256", "originalProposalSha256")), "RECIPIENT_FRAME_HASHES")
    return value, clock, first, ends


@dataclass(frozen=True, repr=False)
class _RecipientState:
    window: object
    claim: _RecipientClaim
    raw: bytes
    clock: object
    first: int
    ends: tuple
    locals: tuple
    local_start: float
    cancelled: object
    last: int
    local_last: float
    roster: object = None
    phase: str = "WORK"
    final_start: object = None
    final_end: int = 0
    final_local: float = 0.0
    read_start: object = None
    read_end: int = 0
    read_local: float = 0.0
    read_attempted: bool = False
    busy: bool = False
    failed: bool = False
    terminal: bool = False


class _RecipientUseWindow:
    """Fixed work240/final45/read30 episode; no writable clock/cap aliases."""
    __slots__ = ()

    def __init__(self, claim, local, first):
        binding, original = _recipient_claim(claim)
        O.clocks.elapsed_ns(O.clocks.Reading(original.fence.clock, binding.closed_ns), first)
        proposal = O.parse(original.proposal_raw)
        ends = tuple(min(O.integer(first.nanoseconds + seconds * O.NS), proposal["phaseFencesNs"][name],
            proposal["proposedJobEndNs"]) for seconds, name in
            ((240, "recipient-validation"), (285, "recipient-final"), (315, "recipient-read")))
        raw = O.encoded({"schema": 1, "scope": RECIPIENT_WINDOW_SCOPE, "clock": O.clock_value(first.clock),
            "firstNs": first.nanoseconds, "previousNs": binding.closed_ns, "workEndNs": ends[0], "finalEndNs": ends[1],
            "readEndNs": ends[2], "firstUseAt": O.parse(original.match_raw)["firstUseAt"],
            "originalReadmissionSha256": O.digest(binding.raw), "workerIdentitySha256": O.digest(original.identity_fields[0]),
            "originalProposalSha256": O.digest(original.proposal_raw), "originalFencesNs": {name: proposal["phaseFencesNs"][name]
                for name in ("recipient-validation", "recipient-final", "recipient-read")},
            "originalProposedJobEndNs": proposal["proposedJobEndNs"], "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        _recipient_frame(raw)
        locals_ = tuple(O.wire._directed_deadline(local, seconds, end, first.nanoseconds)
            for seconds, end in zip((240, 285, 315), ends))
        _RECIPIENT_WINDOWS[id(self)] = _RecipientState(self, claim, raw, first.clock, first.nanoseconds, ends,
            locals_, local, lambda: native.cancellation(original.cancelled), first.nanoseconds, local)

    def state(self, *, cleanup=False):
        value = _RECIPIENT_WINDOWS.get(id(self))
        require(type(self) is _RecipientUseWindow and type(value) is _RecipientState and value.window is self,
                "RECIPIENT_WINDOW_NOT_ORIGINAL")
        if value.roster is not None:
            value.roster.check()
        if not cleanup:
            _recipient_claim(value.claim)
            require(not native.QUARANTINE and not Q.QUARANTINE and not native.diagnostics._QUARANTINE,
                    "RECIPIENT_PRIOR_UNKNOWN")
        return value

    raw = property(lambda self: self.state(cleanup=True).raw)
    clock = property(lambda self: self.state(cleanup=True).clock)
    first = property(lambda self: self.state(cleanup=True).first)
    work = property(lambda self: self.state(cleanup=True).ends[0])
    final = property(lambda self: self.state(cleanup=True).final_end)
    last = property(lambda self: self.state(cleanup=True).last)
    local_end = property(lambda self: self.state(cleanup=True).locals[2])
    cancelled = property(lambda self: self.state(cleanup=True).cancelled)

    def bind(self, owner, first):
        state = self.state()
        require(state.roster is None, "RECIPIENT_OWNER_REBIND")
        _RECIPIENT_WINDOWS[id(self)] = replace(state, roster=_RecipientRoster(owner, self, first))

    def _sample(self, minimum=0):
        state = self.state(cleanup=True)
        local = time.monotonic()
        require(type(local) in (int, float) and math.isfinite(local) and local >= state.local_last,
                "RECIPIENT_LOCAL_CLOCK")
        _RECIPIENT_WINDOWS[id(self)] = replace(state, local_last=local)
        observed = O.clocks.checked_now(state.clock, minimum_ns=max(state.last, O.integer(minimum)))
        current = _RECIPIENT_WINDOWS[id(self)]
        _RECIPIENT_WINDOWS[id(self)] = replace(current, last=observed)
        after = time.monotonic()
        require(type(after) in (int, float) and math.isfinite(after) and after >= local, "RECIPIENT_LOCAL_CLOCK")
        _RECIPIENT_WINDOWS[id(self)] = replace(_RECIPIENT_WINDOWS[id(self)], local_last=after)
        self.state(cleanup=True)
        return local, observed

    def _cap(self):
        value = self.state(cleanup=True)
        return ((value.ends[0], value.locals[0]) if value.phase == "WORK" else
                (value.final_end, value.final_local) if value.phase == "FINAL" else (value.read_end, value.read_local))

    def now(self, *, final=False, minimum=0, limit=None):
        state = self.state(cleanup=final)
        require(type(final) is bool and not state.terminal and not state.busy and
                (final or not state.failed and state.phase != "FINAL"), "RECIPIENT_WINDOW_NOT_LIVE")
        _RECIPIENT_WINDOWS[id(self)] = replace(state, busy=True)
        failed = False
        try:
            end, local_end = self._cap()
            if limit is not None:
                end = min(end, O.integer(limit))
            for index in range(1 if final else 2):
                local, observed = self._sample(minimum)
                require(observed < end and self.state(cleanup=True).local_last < local_end, "RECIPIENT_WINDOW_EXPIRED")
                if not final and index == 0:
                    state.cancelled()
                self.state(cleanup=final)
            return observed
        except BaseException:
            failed = True
            raise
        finally:
            current = _RECIPIENT_WINDOWS[id(self)]
            _RECIPIENT_WINDOWS[id(self)] = replace(current, busy=False, failed=current.failed or failed)

    def deadline(self, maximum, *, final=False, limit=None):
        require(type(maximum) in (int, float) and math.isfinite(maximum) and 0 < maximum <= 315,
                "RECIPIENT_OPERATION_MAXIMUM")
        self.state()  # Unlike cleanup observations, new I/O always checks the original history.
        local = time.monotonic()
        observed = self.now(final=final, minimum=0, limit=limit)
        end, cap = self._cap()
        if limit is not None:
            end = min(end, O.integer(limit))
        result = min(cap, O.wire._directed_deadline(local, maximum, end, observed))
        self.state()
        return result

    def begin_final(self):
        state = self.state(cleanup=True)
        require(state.phase == "WORK" and not state.terminal and not state.busy, "RECIPIENT_FINAL_REENTRY")
        _RECIPIENT_WINDOWS[id(self)] = replace(state, phase="FINAL")  # Expired sentinel if observation fails.
        local, observed = self._sample()
        end = min(state.ends[1], O.integer(observed + 45 * O.NS))
        cap = min(state.locals[1], O.wire._directed_deadline(local, 45, end, observed))
        current = self.state(cleanup=True)
        _RECIPIENT_WINDOWS[id(self)] = replace(current, final_start=observed, final_end=end, final_local=cap)
        self.now(final=True)

    def begin_read(self, scope, captures):
        state = self.state()
        require(state.phase == "FINAL" and not state.read_attempted and state.roster is not None and
                state.roster.owner.original is None and not state.roster.owner.unknown, "RECIPIENT_READ_NOT_READY")
        resources = state.roster.rows
        require(len(captures) == 2 and all(any(row["owner"] is value and row["attempted"] and row["closed"]
                for row in resources) for value in (scope, *captures)), "RECIPIENT_READ_BEFORE_RETIREMENT")
        _RECIPIENT_WINDOWS[id(self)] = replace(state, read_attempted=True)
        self.now(final=True)
        local, observed = self._sample()
        require(observed < state.final_end and self.state().local_last < state.final_local, "RECIPIENT_READ_START_EXPIRED")
        end = min(state.ends[2], O.integer(observed + 30 * O.NS))
        cap = min(state.locals[2], O.wire._directed_deadline(local, 30, end, observed))
        current = self.state()
        _RECIPIENT_WINDOWS[id(self)] = replace(current, phase="READ", read_start=observed, read_end=end, read_local=cap)
        self.now()


def _authority_frame(raw):
    value = O.parse(raw)
    require(type(raw) is bytes and raw == O.encoded(value) and set(value) == {"schema", "scope", "recipientWindow",
        "workEndNs", "finalEndNs"} and type(value["schema"]) is int and value["schema"] == 1 and
        value["scope"] == AUTHORITY_WINDOW_SCOPE, "AUTHORITY_FRAME")
    episode, clock, first, ends = _recipient_frame(O.encoded(value["recipientWindow"]))
    final = min(O.integer(first + 120 * O.NS), ends[0])
    work = min(O.integer(first + 75 * O.NS), O.integer(final - 45 * O.NS))
    require(first < work and type(value["workEndNs"]) is int and type(value["finalEndNs"]) is int and
            (value["workEndNs"], value["finalEndNs"]) == (work, final), "AUTHORITY_FRAME_FENCES")
    return episode, clock, first, work, final


@dataclass(frozen=True, repr=False)
class _AuthorityState:
    window: object
    raw: bytes
    clock: object
    first: int
    work: int
    final: int
    local_end: float
    cancelled: object
    last: int
    local_last: float
    episode: object = None
    roster: object = None
    limits: tuple = (None, None)
    terminal: bool = False
    busy: bool = False
    failed: bool = False


class _RecipientAuthorityWindow:
    """New exact HTTP75/120 suboperation, wholly inside recipient WORK240."""
    __slots__ = ()

    @classmethod
    def parent(cls, episode):
        require(type(episode) is _RecipientUseWindow, "AUTHORITY_EPISODE")
        outer = episode.state()
        require(outer.phase == "WORK", "AUTHORITY_OUTSIDE_WORK")
        final = min(outer.first + 120 * O.NS, outer.ends[0])
        raw = O.encoded({"schema": 1, "scope": AUTHORITY_WINDOW_SCOPE, "recipientWindow": O.parse(outer.raw),
            "workEndNs": min(outer.first + 75 * O.NS, final - 45 * O.NS), "finalEndNs": final})
        require(outer.roster is not None, "AUTHORITY_PARENT_OWNER")
        value = cls._new(raw, outer.roster.first, outer.local_start, outer.cancelled, episode)
        return value

    @classmethod
    def child(cls, raw, first, local, cancelled):
        return cls._new(raw, first, local, cancelled, None)

    @classmethod
    def _new(cls, raw, first_reading, local, cancelled, episode):
        require(cls is _RecipientAuthorityWindow and callable(cancelled), "AUTHORITY_WINDOW_TYPE")
        _frame, clock, first, work, final = _authority_frame(raw)
        O.clocks.validate_reading(first_reading)
        require(first_reading.clock == clock and first <= first_reading.nanoseconds < work, "AUTHORITY_FIRST_CLOCK")
        local_end = O.wire._directed_deadline(local, 120, final, first_reading.nanoseconds)
        if episode is not None:
            local_end = min(local_end, episode.state().locals[0])
        value = cls()
        _AUTHORITY_WINDOWS[id(value)] = _AuthorityState(value, raw, first_reading.clock, first, work, final,
            local_end, cancelled, first_reading.nanoseconds, local, episode)
        return value

    def checked(self, *, cleanup=False):
        value = _AUTHORITY_WINDOWS.get(id(self))
        require(type(self) is _RecipientAuthorityWindow and type(value) is _AuthorityState and value.window is self,
                "AUTHORITY_WINDOW_NOT_ORIGINAL")
        if value.roster is not None:
            value.roster.check(value.limits)
        if value.episode is not None and not value.terminal:
            require(value.episode.state(cleanup=cleanup).phase == "WORK", "AUTHORITY_OUTSIDE_WORK")
        return value

    raw = property(lambda self: self.checked(cleanup=True).raw)
    clock = property(lambda self: self.checked(cleanup=True).clock)
    first = property(lambda self: self.checked(cleanup=True).first)
    work = property(lambda self: self.checked(cleanup=True).work)
    final = property(lambda self: self.checked(cleanup=True).final)
    last = property(lambda self: self.checked(cleanup=True).last)

    def bind(self, owner, first):
        state = self.checked()
        require(state.roster is None and state.episode is not None, "AUTHORITY_OWNER_REBIND")
        _AUTHORITY_WINDOWS[id(self)] = replace(state, roster=_RecipientRoster(owner, self, first))

    def enter_phase(self, owner, started):
        state = self.checked()
        require(state.roster is not None and state.roster.owner is owner and state.limits == (None, None) and
                not state.terminal and not state.failed and state.last == O.integer(started) < state.work,
                "AUTHORITY_PHASE_OWNER")
        work = min(state.work, started + 45 * O.NS)
        limits = work, min(state.final, work + 45 * O.NS)
        owner.work_limit, owner.final_limit = limits
        _AUTHORITY_WINDOWS[id(self)] = replace(state, limits=limits)
        return limits

    def leave_phase(self, owner):
        state = self.checked(cleanup=True)
        require(state.roster is not None and state.roster.owner is owner and state.limits != (None, None),
                "AUTHORITY_PHASE_OWNER")
        owner.work_limit = owner.final_limit = None
        _AUTHORITY_WINDOWS[id(self)] = replace(state, limits=(None, None))

    def now(self, *, final=False, minimum=0, limit=None):
        state = self.checked(cleanup=final)
        require(type(final) is bool and not state.terminal and not state.busy and (final or not state.failed),
                "AUTHORITY_WINDOW_NOT_LIVE")
        _AUTHORITY_WINDOWS[id(self)] = replace(state, busy=True)
        failed = False
        try:
            end = state.final if final else state.work
            if limit is not None:
                end = min(end, O.integer(limit))
            local = time.monotonic()
            require(type(local) in (int, float) and math.isfinite(local) and local >= state.local_last,
                    "AUTHORITY_LOCAL_CLOCK")
            _AUTHORITY_WINDOWS[id(self)] = replace(_AUTHORITY_WINDOWS[id(self)], local_last=local)
            observed = (state.episode.now(final=final, minimum=max(state.last, minimum), limit=end)
                if state.episode is not None else O.clocks.checked_now(state.clock, minimum_ns=max(state.last, O.integer(minimum))))
            _AUTHORITY_WINDOWS[id(self)] = replace(_AUTHORITY_WINDOWS[id(self)], last=observed)
            require(observed < end and local < state.local_end, "AUTHORITY_WINDOW_EXPIRED")
            if not final and state.episode is None:
                state.cancelled()
                observed = O.clocks.checked_now(state.clock, minimum_ns=observed)
                _AUTHORITY_WINDOWS[id(self)] = replace(_AUTHORITY_WINDOWS[id(self)], last=observed)
                require(observed < end, "AUTHORITY_WINDOW_EXPIRED")
            after = time.monotonic()
            require(type(after) in (int, float) and math.isfinite(after) and after >= local, "AUTHORITY_LOCAL_CLOCK")
            _AUTHORITY_WINDOWS[id(self)] = replace(_AUTHORITY_WINDOWS[id(self)], local_last=after)
            require(after < state.local_end, "AUTHORITY_WINDOW_EXPIRED")
            self.checked(cleanup=final)
            return observed
        except BaseException:
            failed = True
            raise
        finally:
            current = _AUTHORITY_WINDOWS[id(self)]
            high = current.last if state.episode is None else max(current.last, _RECIPIENT_WINDOWS[id(state.episode)].last)
            _AUTHORITY_WINDOWS[id(self)] = replace(current, busy=False, failed=current.failed or failed, last=high)

    def deadline(self, maximum, *, final=False, limit=None):
        require(type(maximum) in (int, float) and math.isfinite(maximum) and 0 < maximum <= 120,
                "AUTHORITY_OPERATION_MAXIMUM")
        state = self.checked()
        local = time.monotonic()
        observed = self.now(final=final, limit=limit)
        end = state.final if final else state.work
        if limit is not None:
            end = min(end, O.integer(limit))
        result = min(state.local_end, O.wire._directed_deadline(local, maximum, end, observed))
        self.checked()
        return result


def _authority_context_bindings(value, window):
    frame = _authority_frame(window.raw)[0]
    expected, proposal, observed = value["expectedMatch"], value["originalProposal"], value["observed"]
    initial_identity._match(expected)
    require(type(proposal) is dict and proposal.get("scope") == ALLOCATION_SCOPE and
        O.digest(O.encoded(proposal)) == frame["originalProposalSha256"] and
        proposal["workerIdentitySha256"] == frame["workerIdentitySha256"] and proposal["clock"] == frame["clock"] and
        proposal["source"] == observed["source"] and proposal["firstUseAt"] == expected["firstUseAt"] ==
        observed["firstUseAt"] == frame["firstUseAt"] and proposal["proposedJobEndNs"] == frame["originalProposedJobEndNs"] and
        {name: proposal["phaseFencesNs"][name] for name in frame["originalFencesNs"]} == frame["originalFencesNs"],
        "AUTHORITY_CONTEXT_BINDINGS")


def _authority_phase_start(window, returned, start):
    value = window.checked(cleanup=True)
    began = O.integer(start["startedNs"], O.integer(returned, value.first))
    require(began < value.work and type(start["workEndNs"]) is int and type(start["finalEndNs"]) is int and
        start["workEndNs"] == min(value.work, began + 45 * O.NS) and
        start["finalEndNs"] == min(value.final, start["workEndNs"] + 45 * O.NS), "AUTHORITY_PHASE_FENCES")


def _authority_chain_minimum(window, returned, start, row, birth, child, service, ack):
    _authority_phase_start(window, returned, start)
    return _service_chain_minimum(window.first, returned, start, row, birth, child, service, ack)


@dataclass(frozen=True, repr=False)
class _AuthorityReturn:
    """Historical return of this actual authority call, not a remote lease."""
    raw: bytes


def _authority_return(value, episode):
    saved = _AUTHORITY_RETURNS.get(id(value))
    require(type(value) is _AuthorityReturn and type(saved) is tuple and len(saved) == 6 and
            saved[0] is value and value.raw == saved[1] and saved[2] is episode, "NOT_ORIGINAL_AUTHORITY_RETURN")
    _check_history(saved[4])
    state = saved[3].checked()
    require(state.terminal and not state.failed and not state.busy and state.limits == (None, None) and
            state.roster.owner.original is None and state.roster.owner.errors == [], "AUTHORITY_RETURN_CHANGED")
    state.roster.known()
    return saved[5]


def _recipient_authority(episode, token):
    """Third original acquisition: every return/close still spends outer WORK."""
    binding, original = _recipient_claim(episode.state().claim)
    owner = window = private = evidence = None
    try:
        window = _RecipientAuthorityWindow.parent(episode)
        state = window.checked()
        first = episode.state().roster.first
        owner = native.Owner(state.local_end, window, first=first, cancelled=state.cancelled)
        owner.initial_sources = {}
        window.bind(owner, first)
        observed, root, event = _recipient_host(O.parse(original.match_raw)["firstUseAt"])
        require(observed == O.parse(original.worker_originals[0])["observed"] and event == original.identity_fields[1],
                "AUTHORITY_ACTUAL_CONTEXT_CHANGED")
        path = root / "authority"
        private = owner.new(path)
        owner.write(private, "authority-window.json", window.raw)
        owner.child(private, "control-home", create=True)
        owner.child(private, "temporary", create=True)
        before = source_queries(owner, window, observed, path / "source-before")
        before_pin = _source_pin(before)
        require(dict(before.records) == {name: dict(original.worker_originals[1])[name] for name in SOURCE_KEYS},
                "AUTHORITY_SOURCE_CHANGED")
        context_raw = owner.write(private, "context.json", {"schema": 1, "scope": native.INITIAL_AUTHORITY_CONTEXT_SCOPE,
            "authorityWindow": O.parse(window.raw), "expectedMatch": O.parse(original.match_raw),
            "originalProposal": O.parse(original.proposal_raw), "observed": observed, "eventSha256": O.digest(event),
            "root": str(ROOT), "session": str(path), "job": uuid.uuid4().hex, "inheritedContext": Q._inherited_context(),
            "sourceReturnSha256": O.digest(before.raw), "sourceReturnedNs": O.parse(before.raw)["returnedNs"],
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        _, phase = native.phase(owner, private, context_raw, token, window)
        phase_pin = _phase_pin(phase)
        token = None
        match, _chain, captured, _child = read_phase(owner, private, context_raw, before, phase, window)
        require(match.record == original.match_raw and _service_job(captured, window.clock) == binding.claim.service_job,
                "AUTHORITY_JOB_OR_MATCH_CHANGED")
        after = source_queries(owner, window, observed, path / "source-after")
        after_pin = _source_pin(after)
        require(source_readback(owner, path / "source-after", after) == dict(before.records), "AUTHORITY_SOURCE_CHANGED")
        match, chain, captured, (child, session) = read_phase(owner, private, context_raw, before, phase, window)
        require(match.record == original.match_raw and _service_job(captured, window.clock) == binding.claim.service_job,
                "AUTHORITY_JOB_OR_MATCH_CHANGED")
        current = initial_identity.bind_worker_match(match, event_raw=event,
            policy_raw=dict(after.records)["candidate_policy_raw"], now=int(time.time()))
        require(_worker_fields(current) == original.identity_fields, "AUTHORITY_IDENTITY_CHANGED")
        files = [("authority-window.json", window.raw), ("context.json", context_raw),
            ("service/child-result.json", child), ("acquisition-queries/session-result.json", session)]
        files.extend(("service/" + name, raw) for name, raw in phase.records)
        files.extend(("acquisition-queries/" + name + ".bin", raw) for name, raw in captured[1])
        for name, returned in (("source-before", before), ("source-after", after)):
            files.extend(((name + "/source-return.json", returned.raw), (name + "/session-result.json", returned.session)))
            files.extend((name + "/" + label + ".bin", raw) for label, raw in returned.records)
        originals = tuple(files)
        pending = owner.write(private, "authority-pending.json", {"schema": 1,
            "scope": "INITIAL_RECIPIENT_USE_AUTHORITY_PENDING_CLOSE_V1", "recipientWindowSha256": O.digest(episode.raw),
            "originalReadmissionSha256": O.digest(binding.raw), "filesSha256": {name: O.digest(raw) for name, raw in originals},
            "originalChain": chain, "retainedNs": window.now(), "retirement": "PENDING_OWNER_CLOSE"})
        evidence = (originals, pending, before, after, phase, captured, match)
        graph = _history_graph(before, after, phase, match, owner.initial_sources)
        require(_source_pin(before)[1:] == before_pin[1:] and _source_pin(after)[1:] == after_pin[1:] and
                _phase_pin(phase)[1:] == phase_pin[1:] and owner.phase_originals is phase and
                set(owner.initial_sources) == {str(path / "source-before"), str(path / "source-after")} and
                owner.initial_sources[str(path / "source-before")] is before and
                owner.initial_sources[str(path / "source-after")] is after, "AUTHORITY_ORIGINAL_RETURN_CHANGED")
        _recipient_claim(episode.state().claim)
        preclose = window.now()
    except BaseException as error:
        if owner is None:
            raise
        owner.error("recipient-authority", error)
    finally:
        token = None
        if owner is not None:
            try:
                window.checked(cleanup=True).roster.freeze()
            except BaseException as error:
                owner.error("authority-close-roster", error, unknown=True)
            try:
                owner.close()
            except BaseException as error:
                owner.error("authority-owner-close", error)
    try:
        window.checked(cleanup=True).roster.known()
    except BaseException as error:
        owner.error("authority-close-return", error, unknown=True)
    if owner.original is not None:
        raise owner.original
    require(evidence is not None, "AUTHORITY_INCOMPLETE")
    _check_history(graph)
    require(owner.phase_originals is phase, "AUTHORITY_ORIGINAL_RETURN_CHANGED")
    current = initial_identity.bind_worker_match(original.match, event_raw=original.identity_fields[1],
        policy_raw=original.identity_fields[2], now=int(time.time()))
    require(_worker_fields(current) == original.identity_fields, "AUTHORITY_FINAL_POLICY_CHANGED")
    closed = window.now(final=True, minimum=preclose)
    episode.now(minimum=closed)  # Outer WORK, not outer FINAL45, includes the actual owner return.
    _check_history(graph)
    require(owner.phase_originals is phase, "AUTHORITY_ORIGINAL_RETURN_CHANGED")
    state = window.checked()
    _AUTHORITY_WINDOWS[id(window)] = replace(state, terminal=True)
    raw = O.encoded({"schema": 1, "scope": "INITIAL_RECIPIENT_USE_AUTHORITY_CLOSED_HISTORY_V1",
        "recipientWindowSha256": O.digest(episode.raw), "originalReadmissionSha256": O.digest(binding.raw),
        "workerIdentitySha256": O.digest(original.identity_fields[0]), "matchSha256": O.digest(original.match_raw),
        "serviceTimeBasisSha256": O.digest(original.service_time_raw), "originalProposalSha256": O.digest(original.proposal_raw),
        "filesSha256": {name: O.digest(data) for name, data in evidence[0]}, "pendingSha256": O.digest(evidence[1]),
        "originalChain": chain, "preCloseNs": preclose, "closedNs": closed, "resourceCount": len(state.roster.rows),
        "retirement": "KNOWN_RESOURCE_CLOSE_ONLY", "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
    result = _AuthorityReturn(raw)
    nodes = _history_graph(result, _AUTHORITY_WINDOWS[id(window)], evidence)
    _AUTHORITY_RETURNS[id(result)] = (result, raw, episode, window, nodes, evidence[0])
    _authority_return(result, episode)
    return result


def _recipient_command(context_hash, minimum=None):
    result = native.initial_command(context_hash, minimum)
    result[5] = "_recipient"
    return result


RECIPIENT_FILES = ("recipient-window.json", "worker-identity.json", "worker-match.json", "worker-policy.json",
                   "worker-proposal.json", "recipient-public.asc", "authority-return.json")
RECIPIENT_DIRECTORIES = ("control-home", "temporary", "crypto", "recipient-validation")
RECIPIENT_CONTEXT_FIELDS = {"schema", "scope", "root", "session", "observed", "eventSha256", "filesSha256",
                            "job", "inheritedContext", "directories", "budgetAcceptance", "exportSaveAuthority"}


def _recipient_inputs(owner, context_hash, minimum):
    """Child consistency, never reconstruction of the parent's authority return."""
    require(O.wire.TOKEN_ENV not in os.environ and not any(name in os.environ for name in
        ("GITHUB_TOKEN", "GH_TOKEN", "ACTIONS_RUNTIME_TOKEN", "ACTIONS_CACHE_URL", "ACTIONS_RESULTS_URL")),
        "RECIPIENT_CHILD_CREDENTIAL")
    native.recipient_environment(_recipient_path())
    private = owner.open(_recipient_path())
    context_raw = owner.read(private, "recipient-context.json")
    context = O.parse(context_raw)
    require(O.digest(context_raw) == context_hash and context_raw == O.encoded(context) and
        set(context) == RECIPIENT_CONTEXT_FIELDS and type(context["schema"]) is int and context["schema"] == 1 and
        context["scope"] == RECIPIENT_CONTEXT_SCOPE and context["root"] == str(ROOT) and
        context["session"] == str(private.path) and context["budgetAcceptance"] == "NOT_ADMITTED" and
        context["exportSaveAuthority"] is False, "RECIPIENT_CONTEXT")
    raw = {name: owner.read(private, name) for name in RECIPIENT_FILES}
    require(context["filesSha256"] == {name: O.digest(data) for name, data in raw.items()}, "RECIPIENT_FILES_CHANGED")
    frame, clock, first, ends = _recipient_frame(raw["recipient-window.json"])
    observed, path, event = _recipient_host(frame["firstUseAt"])
    require(path == private.path and context["observed"] == observed and context["eventSha256"] == O.digest(event) and
        observed["role"] == clock.role == owner.first.clock.role and clock == owner.first.clock, "RECIPIENT_ACTUAL_CONTEXT")
    match = acquisition.stages.BootstrapMatch(raw["worker-match.json"])
    identity = initial_identity.bind_worker_match(match, event_raw=event, policy_raw=raw["worker-policy.json"], now=int(time.time()))
    require(identity.record == raw["worker-identity.json"] and identity.public_key == raw["recipient-public.asc"] and
        O.digest(identity.record) == frame["workerIdentitySha256"] and
        O.digest(raw["worker-proposal.json"]) == frame["originalProposalSha256"], "RECIPIENT_IDENTITY_CHANGED")
    proposal = O.parse(raw["worker-proposal.json"])
    require(proposal["scope"] == ALLOCATION_SCOPE and proposal["workerIdentitySha256"] == frame["workerIdentitySha256"] and
        proposal["clock"] == frame["clock"] and proposal["firstUseAt"] == frame["firstUseAt"] and
        proposal["proposedJobEndNs"] == frame["originalProposedJobEndNs"] and
        {name: proposal["phaseFencesNs"][name] for name in frame["originalFencesNs"]} == frame["originalFencesNs"],
        "RECIPIENT_PROPOSAL_CHANGED")
    handles = {"session": private}
    require(type(context["directories"]) is dict and set(context["directories"]) == set(RECIPIENT_DIRECTORIES),
            "RECIPIENT_DIRECTORIES")
    for name in RECIPIENT_DIRECTORIES:
        directory = owner.child(private, name)
        directory.verify()
        require(list(directory.identity) == context["directories"][name], "RECIPIENT_DIRECTORY_CHANGED")
        handles[name] = directory
    start_raw = owner.read(handles["recipient-validation"], "start.json")
    start = O.parse(start_raw)
    require(set(start) == native.START_FIELDS and start_raw == O.encoded(start) and type(start["schema"]) is int and
        start["schema"] == 1 and start["scope"] == RECIPIENT_START_SCOPE and start["contextSha256"] == context_hash and
        start["argv"] == _recipient_command(context_hash) and start["cwd"] == str(ROOT) and start["role"] == clock.role and
        start["job"] == context["job"] and start["state"] == str(path) and start["home"] == str(path / "control-home") and
        type(start["invocation"]) is str and re.fullmatch(r"[0-9a-f]{32}", start["invocation"]) and
        start["exitCode"] is None and start["launchAttempted"] is False and start["scopeAttempted"] is False and
        start["retirement"] == "UNKNOWN" and start["workEndNs"] == ends[0] and start["finalEndNs"] == ends[1] and
        first <= O.integer(start["startedNs"]) <= O.integer(minimum) <= owner.first.nanoseconds < ends[0], "RECIPIENT_START")
    inherited = native.processes.ownership_environment(context["inheritedContext"], context["job"], start["invocation"],
        str(path), str(path / "control-home"), allow_new_context=True)
    require(start["inheritedContext"] == {name: inherited[name] for name in Q._CONTEXT} == Q._inherited_context(),
            "RECIPIENT_NATIVE_CONTEXT")
    authority = O.parse(raw["authority-return.json"])
    require(authority["scope"] == "INITIAL_RECIPIENT_USE_AUTHORITY_CLOSED_HISTORY_V1" and
        authority["recipientWindowSha256"] == O.digest(raw["recipient-window.json"]) and
        authority["originalReadmissionSha256"] == frame["originalReadmissionSha256"] and
        authority["workerIdentitySha256"] == O.digest(identity.record) and authority["matchSha256"] == O.digest(match.record) and
        authority["originalProposalSha256"] == frame["originalProposalSha256"] and
        first <= O.integer(authority["preCloseNs"]) <= O.integer(authority["closedNs"]) <= start["startedNs"],
        "RECIPIENT_AUTHORITY_BINDING")
    authority_dir = owner.child(private, "authority")
    authority_context = owner.read(authority_dir, "context.json")
    authority_window = owner.read(authority_dir, "authority-window.json")
    require(_authority_frame(authority_window)[0] == frame and
        authority["closedNs"] < _authority_frame(authority_window)[-1] <= ends[0], "RECIPIENT_AUTHORITY_WINDOW")
    queries = owner.child(authority_dir, "acquisition-queries")
    originals = {name: owner.read(queries, name + ".bin") for name in ORIGINAL_KEYS}
    service = owner.child(authority_dir, "service")
    service_start_raw = owner.read(service, "start.json")
    service_start = O.parse(service_start_raw)
    checked_match, _service = retained_match(O.parse(authority_context), originals, service_start["invocation"], clock,
        service_start["startedNs"], service_start["workEndNs"])
    require(checked_match.record == match.record and originals["event"] == event and
        originals["candidate_policy_raw"] == identity.original_policy and
        authority["filesSha256"]["context.json"] == O.digest(authority_context) and
        authority["filesSha256"]["authority-window.json"] == O.digest(authority_window) and
        authority["filesSha256"]["service/start.json"] == O.digest(service_start_raw) and
        all(authority["filesSha256"]["acquisition-queries/" + name + ".bin"] == O.digest(data)
            for name, data in originals.items()), "RECIPIENT_AUTHORITY_ORIGINALS_CHANGED")
    owner.end()
    return {"context": context, "start": start, "identity": identity, "match": match, "handles": handles,
        "binding": (context_raw, tuple(raw.items()), start_raw, authority_context, authority_window,
                    tuple(originals.items()), service_start_raw), "source": {name: originals[name] for name in SOURCE_KEYS}}


def _recipient_object_fields(recipient):
    kind = native.diagnostics.Recipient if os.name == "nt" else native.posix.Recipient
    require(type(recipient) is kind, "RECIPIENT_SUPPLIER_TYPE")
    return tuple((name, getattr(recipient, name)) for name in kind.__dataclass_fields__)


def _recipient_child(context_hash, minimum, cancelled):
    """Only the maintained synchronous60 validator, under the parent's native cap."""
    _recipient_command(context_hash, minimum)
    local = time.monotonic()
    first = O.clocks.validate_reading(O.clocks.observe())
    require(first.nanoseconds >= O.integer(minimum), "RECIPIENT_CHILD_PRECEDES_LAUNCH")
    callback = lambda: native.cancellation(cancelled)
    meta_window = native._RecipientWindow(first, first.nanoseconds, local, None, callback, metadata=True)
    metadata = native.Owner(meta_window.local_end, meta_window, first=first, cancelled=callback)
    metadata.initial_sources = {}
    owner, window, target, recipient, fields, raw, failure = metadata, None, None, None, None, None, None
    try:
        initial = _recipient_inputs(metadata, context_hash, minimum)
        metadata.close()
        if metadata.original is not None:
            raise metadata.original
        require(not metadata.unknown and all(row["attempted"] and row["closed"] for row in metadata.resources),
                "RECIPIENT_METADATA_CLOSE")
        window = native._RecipientWindow(first, meta_window.last, local, initial["start"]["workEndNs"], callback)
        owner = native.Owner(window.local_end, window, first=first, cancelled=callback)
        owner.initial_sources = {}
        current = _recipient_inputs(owner, context_hash, minimum)
        require(current["binding"] == initial["binding"], "RECIPIENT_METADATA_CHANGED")
        target, work = current["handles"]["recipient-validation"], current["handles"]["crypto"]
        checked = current["identity"]
        before = source_queries(owner, window, current["context"]["observed"], target.path / "source-before")
        require(dict(before.records) == current["source"], "RECIPIENT_SOURCE_CHANGED")
        identity_fields = _worker_fields(checked)
        window.now()
        if os.name == "nt":
            recipient = native.diagnostics.validate_recipient(checked.public_key, checked.fingerprint, work,
                job_id=current["context"]["job"])
        else:
            recipient = native.posix.validate_recipient(current["handles"]["session"].path / "recipient-public.asc",
                checked.fingerprint, work.path)
        # Save the ACTUAL returned object and fields before a clock or callback.
        fields = _recipient_object_fields(recipient)
        require(not native.diagnostics._QUARANTINE and not Q.QUARANTINE, "RECIPIENT_SUPPLIER_UNKNOWN")
        returned = window.now()
        supplier = native._recipient_supplier_record(recipient, work, checked, current["context"]["job"])
        after = source_queries(owner, window, current["context"]["observed"], target.path / "source-after")
        require(dict(after.records) == current["source"] and _worker_fields(checked) == identity_fields and
            _recipient_inputs(owner, context_hash, minimum)["binding"] == initial["binding"] and
            _recipient_object_fields(recipient) == fields, "RECIPIENT_POST_SUPPLIER_CHANGED")
        raw = owner.write(target, "child-result.json", {"schema": 1, "scope": RECIPIENT_CHILD_SCOPE,
            "contextSha256": context_hash, "startSha256": O.digest(initial["binding"][2]),
            "identitySha256": O.digest(checked.record), "authoritySha256": O.digest(dict(initial["binding"][1])["authority-return.json"]),
            "recipient": supplier, "clock": O.clock_value(window.clock), "invocation": current["start"]["invocation"],
            "launchMinimumNs": minimum, "beganNs": first.nanoseconds, "metadataLastNs": meta_window.last,
            "sourceBeforeSha256": O.digest(before.raw), "sourceAfterSha256": O.digest(after.raw),
            "supplierReturnedNs": returned, "completedNs": window.now(minimum=returned), "supplierReturned": True,
            "childResourceClose": "PENDING_CLOSE", "parentRetirement": "NOT_OBSERVED_HERE",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        require(owner.read(target, "child-result.json") == raw and _recipient_object_fields(recipient) == fields and
                _recipient_inputs(owner, context_hash, minimum)["binding"] == initial["binding"], "RECIPIENT_CHILD_RESULT_CHANGED")
    except BaseException as error:
        failure = error if owner.original is None else owner.original
        unknown = bool(native.diagnostics._QUARANTINE or Q.QUARANTINE) or (
            isinstance(error, native.diagnostics.WindowsEvidenceError) and error.retirement_unknown is not False)
        owner.error("initial-recipient-child", error, unknown=unknown)
    finally:
        for actual in (owner,) if owner is metadata else (owner, metadata):
            try:
                actual.close()
            except BaseException as error:
                if failure is None:
                    failure = actual.original if actual.original is not None else error
            if failure is None:
                failure = actual.original
    if failure is not None:
        raise failure
    require(window is not None and raw is not None and not owner.unknown and
        all(row["attempted"] and row["closed"] for row in owner.resources), "RECIPIENT_CHILD_INCOMPLETE")
    current_identity = initial_identity.bind_worker_match(current["match"], event_raw=checked.original_event,
        policy_raw=checked.original_policy, now=int(time.time()))
    require(_worker_fields(current_identity) == identity_fields, "RECIPIENT_CHILD_FINAL_POLICY")
    native.cancellation(cancelled)
    closed = window.now()
    require(_recipient_object_fields(recipient) == fields and _worker_fields(checked) == identity_fields and
            type(cancelled) is list and cancelled == [], "RECIPIENT_CHILD_FINAL_CHANGED")
    return {"schema": 1, "scope": native.INITIAL_RECIPIENT_ACK_SCOPE, "invocation": current["start"]["invocation"],
        "terminalSha256": O.digest(raw), "clock": O.clock_value(window.clock), "closedNs": closed}, window, window.final


@dataclass(frozen=True, repr=False)
class _RecipientNativeReturn:
    context: bytes
    records: tuple
    child: bytes


def _recipient_native(owner, private, context_raw, window, authority):
    """One fixed credential-free child, using native primitives, not phase()."""
    require(type(window) is _RecipientUseWindow and window.state().roster.owner is owner and
            window.state().phase == "WORK", "RECIPIENT_NATIVE_OWNER")
    _authority_return(authority, window)
    context = O.parse(context_raw)
    require(O.wire.TOKEN_ENV not in os.environ, "RECIPIENT_PARENT_READ_TOKEN")
    started = window.now()
    invocation = uuid.uuid4().hex
    environment = native.processes.ownership_environment(native.recipient_environment(private.path), context["job"], invocation,
        str(private.path), str(private.path / "control-home"), allow_new_context=True)
    start = {"schema": 1, "scope": RECIPIENT_START_SCOPE, "contextSha256": O.digest(context_raw),
        "argv": _recipient_command(O.digest(context_raw)), "cwd": str(ROOT), "role": window.clock.role,
        "job": context["job"], "invocation": invocation, "state": str(private.path), "home": str(private.path / "control-home"),
        "inheritedContext": {name: environment[name] for name in Q._CONTEXT}, "startedNs": started,
        "workEndNs": window.work, "finalEndNs": window.state().ends[1], "exitCode": None, "launchAttempted": False,
        "scopeAttempted": False, "retirement": "UNKNOWN"}
    directory = owner.child(private, "recipient-validation")
    start_raw = owner.write(directory, "start.json", start)
    row = dict(start)
    row["captureOutcomes"] = {name: {"synced": False, "verified": False, "closeAttempted": False,
        "closed": False, "readback": False} for name in ("stdout", "stderr")}
    scope = out = err = child = baseline_raw = birth_raw = None
    native_known = False
    resource_start = len(window.state().roster.seen)
    try:
        # Inherited sinks live only to the original R+285 cap, never a new IO45.
        end = window.state().locals[1]
        out = owner.acquire("stdout", lambda: directory.create_file("stdout.log", max_bytes=native.ACK_LIMIT, deadline=end))
        err = owner.acquire("stderr", lambda: directory.create_file("stderr.log", max_bytes=native.STDERR_LIMIT, deadline=end))
        row["scopeAttempted"] = True
        scope = owner.acquire("native-scope", lambda: native.processes.make_scope(context["job"], invocation,
            str(private.path), str(private.path / "control-home")))
        row["preparerIdentity"] = native.preparer_identity(scope, window.clock.role)
        baseline_raw = owner.write(directory, "baseline.json", {"role": window.clock.role,
            "baseline": sorted(scope.baseline) if hasattr(scope, "baseline") else None,
            "kernelJob": window.clock.role == "windows-x64"})
        row["baselineSha256"] = O.digest(baseline_raw)
        _authority_return(authority, window)
        row["launchMinimumNs"] = window.now()
        argv = _recipient_command(O.digest(context_raw), row["launchMinimumNs"])
        row["launchArgv"], row["launchAttempted"] = argv, True
        child = scope.spawn(argv, str(ROOT), environment, stdout=out, stderr=err)
        require(child.stdout is None and child.stderr is None, "RECIPIENT_PRIVATE_SINKS")
        birth = scope.description()
        leaders = [value for value in birth.get("startedIdentities", []) if value.get("pid") == child.pid]
        require(len(leaders) == 1, "RECIPIENT_NATIVE_BIRTH")
        row["leader"] = dict(leaders[0])
        native.lifetime(row["leader"], window.clock.role)
        birth_raw = owner.write(directory, "native-start.json", {"ownership": birth, "leader": row["leader"],
            "preparerIdentity": row["preparerIdentity"], "observedNs": window.now()})
        row["nativeStartSha256"] = O.digest(birth_raw)
        while True:
            window.now()
            if window.clock.role == "windows-x64":
                out.observe_live_output()
                err.observe_live_output()
            else:
                out.verify()
                err.verify()
            code = child.poll()
            if code is not None:
                row["exitCode"] = code
            observed = window.now()
            if code is not None:
                row["completedNs"] = observed
                require(type(code) is int and code == 0, "RECIPIENT_CHILD_FAILED")
                require(not scope.discover(), "RECIPIENT_LEFT_DESCENDANTS")
                window.now()
                break
            scope.discover()
            native.time.sleep(.025)
    except BaseException as error:
        owner.error("initial-recipient-native", error)
    finally:
        # Returned resources were pinned by Owner.acquire BEFORE post-return
        # observations. Recover those exact references, never retry allocation.
        roster = _RECIPIENT_WINDOWS[id(window)].roster
        saved = roster.seen[resource_start:]
        scope = scope if scope is not None else next((resource for _row, label, resource, _a, _c in saved if label == "native-scope"), None)
        out = out if out is not None else next((resource for _row, label, resource, _a, _c in saved if label == "stdout"), None)
        err = err if err is not None else next((resource for _row, label, resource, _a, _c in saved if label == "stderr"), None)
        try:
            window.begin_final()
        except BaseException as error:
            owner.error("recipient-final-start", error)
        if scope is not None:
            drain_end = None
            try:
                window.now(final=True)
                drain_end = window.state(cleanup=True).final_local
                remaining = max(0, drain_end - time.monotonic())
                grace = min(5, remaining)
                kill_wait = min(5, max(0, remaining - grace))
                row["survivors"] = scope.drain(grace=grace, kill_wait=kill_wait, deadline=drain_end)
                require(row["survivors"] == [], "RECIPIENT_SURVIVORS")
                row["ownership"] = scope.description()
                require(row["ownership"].get("discoveryErrors") == [], "RECIPIENT_DRAIN_IDENTITY")
                # Allocation can return a real scope before its post-return
                # clock fails. Do not invent an unperformed preparer reading.
                if "preparerIdentity" in row:
                    require(native.preparer_identity(scope, window.clock.role) == row["preparerIdentity"],
                            "RECIPIENT_DRAIN_IDENTITY")
                window.now(final=True)
                native.posix._deadline(drain_end)
                native_known = True
            except BaseException as error:
                owner.error("recipient-drain", error, unknown=True)
            owner.close_one(scope)
            resource = next(row_ for row_, _label, actual, _a, _c in roster.seen if actual is scope)
            row["scopeCloseAttempted"], row["scopeClosed"] = resource["attempted"], resource["closed"]
            try:
                window.now(final=True)
                if drain_end is not None:
                    native.posix._deadline(drain_end)
                require(resource["closed"] is True, "RECIPIENT_SCOPE_CLOSE")
            except BaseException as error:
                native_known = False
                owner.error("recipient-drain-close", error, unknown=True)
        elif row["scopeAttempted"]:
            owner.error("recipient-scope-construction", O.OriginError("INITIAL_RECIPIENT_SCOPE_UNKNOWN"), unknown=True)
        else:
            native_known = True
        if native_known and not owner.unknown:
            for name, stream in (("stdout", out), ("stderr", err)):
                if stream is None:
                    continue
                outcome = row["captureOutcomes"][name]
                try:
                    window.now(final=True)
                    stream.sync()
                    outcome["synced"] = True
                    stream.verify()
                    outcome["verified"] = True
                    window.now(final=True)
                except BaseException as error:
                    owner.error("recipient-capture", error)
                owner.close_one(stream)
                resource = next(row_ for row_, _label, actual, _a, _c in roster.seen if actual is stream)
                outcome.update(closeAttempted=resource["attempted"], closed=resource["closed"])
        else:
            owner.unknown = True
        # A bounded outer drain cannot establish the failed/late child's
        # supplier return or metadata close. Keep this uncertainty sticky,
        # as in the maintained legacy recipient supervisor; acquire nothing.
        if row["launchAttempted"] and owner.original is not None:
            owner.error("recipient-child-return", owner.original, unknown=True)
    if owner.original is not None:
        raise owner.original
    require(native_known and not owner.unknown and all(outcome[name] is True for outcome in row["captureOutcomes"].values()
        for name in ("synced", "verified", "closeAttempted", "closed")), "RECIPIENT_NATIVE_NOT_RETIRED")
    row["finalizedNs"] = window.now(final=True)
    window.begin_read(scope, (out, err))
    captures = {}
    for name, maximum in (("stdout", native.ACK_LIMIT), ("stderr", native.STDERR_LIMIT)):
        captures[name] = owner.read(directory, name + ".log", maximum, final=True)
        row["captureOutcomes"][name]["readback"] = True
    require(captures["stderr"] == b"", "RECIPIENT_STDERR")
    row.update(retirement="KNOWN", errors=[], captures={name: {"sha256": O.digest(raw), "bytes": len(raw)}
        for name, raw in captures.items()}, finalStartedNs=window.state().final_start, finalEndNs=window.state().final_end,
        readStartedNs=window.state().read_start, readEndNs=window.state().read_end, readbackCompletedNs=window.now())
    row_raw = owner.write(directory, "result.json", row, final=True)
    child_raw = owner.read(directory, "child-result.json", final=True)
    require(owner.phase_originals is None, "RECIPIENT_NATIVE_RETURN_REUSE")
    returned = _RecipientNativeReturn(context_raw, tuple(sorted({"start.json": start_raw, "result.json": row_raw,
        "baseline.json": baseline_raw, "native-start.json": birth_raw, "stdout.log": captures["stdout"],
        "stderr.log": captures["stderr"]}.items())), child_raw)
    owner.phase_originals = returned
    _RECIPIENT_NATIVE_RETURNS[id(returned)] = (returned, owner, window, context_raw, returned.records, child_raw)
    return returned


def _recipient_native_readback(owner, private, returned, window, authority, identity):
    """Original native return plus unchanged bytes; ACK/file presence is insufficient."""
    require(type(returned) is _RecipientNativeReturn and owner.phase_originals is returned and
        window.state().phase == "READ" and owner.fence is window, "NOT_ORIGINAL_RECIPIENT_NATIVE_RETURN")
    saved = _RECIPIENT_NATIVE_RETURNS.get(id(returned))
    require(type(saved) is tuple and len(saved) == 6 and saved[0] is returned and saved[1] is owner and saved[2] is window and
            type(returned.context) is bytes and returned.context == saved[3] and returned.records is saved[4] and
            type(returned.child) is bytes and returned.child == saved[5], "RECIPIENT_NATIVE_RETURN_CHANGED")
    _authority_return(authority, window)
    require(owner.read(private, "recipient-context.json", final=True) == returned.context, "RECIPIENT_CONTEXT_CHANGED")
    context = O.parse(returned.context)
    records = dict(returned.records)
    require(len(returned.records) == len(native.PHASE_FILES) and set(records) == native.PHASE_FILES,
            "RECIPIENT_NATIVE_FILES")
    directory = owner.child(private, "recipient-validation", final=True)
    for name, raw in records.items():
        require(owner.read(directory, name, final=True) == raw, "RECIPIENT_NATIVE_BYTES_CHANGED")
    require(owner.read(directory, "child-result.json", final=True) == returned.child, "RECIPIENT_CHILD_CHANGED")
    start, row, birth = (O.parse(records[name]) for name in ("start.json", "result.json", "native-start.json"))
    require(set(start) == native.START_FIELDS and set(row) == native.TERMINAL_FIELDS |
        {"finalStartedNs", "readStartedNs", "readEndNs", "readbackCompletedNs"} and
        set(birth) == {"ownership", "leader", "preparerIdentity", "observedNs"} and start["scope"] == RECIPIENT_START_SCOPE and
        start["argv"] == _recipient_command(O.digest(returned.context)) and
        start["contextSha256"] == O.digest(returned.context) and start["job"] == context["job"] and
        start["cwd"] == str(ROOT) and start["state"] == str(private.path) and start["home"] == str(private.path / "control-home") and
        start["role"] == window.clock.role and start["workEndNs"] == window.work and
        start["finalEndNs"] == window.state().ends[1], "RECIPIENT_NATIVE_START")
    require(all(row[name] == start[name] for name in set(start) -
        {"exitCode", "launchAttempted", "scopeAttempted", "retirement", "finalEndNs"}) and type(row["exitCode"]) is int and
        row["exitCode"] == 0 and row["launchAttempted"] is True and row["scopeAttempted"] is True and
        row["scopeCloseAttempted"] is True and row["scopeClosed"] is True and row["retirement"] == "KNOWN" and
        row["errors"] == [] and row["survivors"] == [] and records["stderr.log"] == b"" and
        row["baselineSha256"] == O.digest(records["baseline.json"]) and
        row["nativeStartSha256"] == O.digest(records["native-start.json"]) and row["leader"] == birth["leader"],
        "RECIPIENT_NATIVE_RETIREMENT")
    baseline = native.baseline_record(records["baseline.json"], window.clock.role)
    preparer = native.closed_lifetime(row["preparerIdentity"], window.clock.role)
    require(preparer == native.closed_lifetime(birth["preparerIdentity"], window.clock.role) and
            preparer["pid"] != row["leader"]["pid"], "RECIPIENT_PREPARER_CHANGED")
    argv = _recipient_command(O.digest(returned.context), row["launchMinimumNs"])
    require(row["launchArgv"] == argv, "RECIPIENT_LAUNCH_COMMAND")
    native.native_record(row["ownership"], start, row["leader"], argv)
    native.native_record(birth["ownership"], start, row["leader"], argv, terminal=False)
    require(birth["ownership"]["launches"] == row["ownership"]["launches"], "RECIPIENT_NATIVE_BIRTH_CHANGED")
    if baseline["baseline"] is not None:
        lifetime = native.lifetime(row["leader"], window.clock.role)
        require(list(lifetime[:4] if window.clock.role.startswith("macos-") else lifetime) not in baseline["baseline"],
                "RECIPIENT_NATIVE_PREEXISTING_LEADER")
    expected_outcomes = {name: {key: True for key in ("synced", "verified", "closeAttempted", "closed", "readback")}
        for name in ("stdout", "stderr")}
    require(row["captureOutcomes"] == expected_outcomes and all(type(value) is bool for outcome in
        row["captureOutcomes"].values() for value in outcome.values()) and row["captures"] == {
        name: {"sha256": O.digest(records[name + ".log"]), "bytes": len(records[name + ".log"])} for name in ("stdout", "stderr")},
        "RECIPIENT_CAPTURE_RETIREMENT")
    ack, child = O.parse(records["stdout.log"]), O.parse(returned.child)
    require(records["stdout.log"] == O.encoded(ack) and set(ack) ==
        {"schema", "scope", "invocation", "terminalSha256", "clock", "closedNs"} and type(ack["schema"]) is int and
        ack["schema"] == 1 and ack["scope"] == native.INITIAL_RECIPIENT_ACK_SCOPE and ack["invocation"] == start["invocation"] and
        ack["terminalSha256"] == O.digest(returned.child) and ack["clock"] == O.clock_value(window.clock), "RECIPIENT_CHILD_ACK")
    require(set(child) == {"schema", "scope", "contextSha256", "startSha256", "identitySha256", "authoritySha256", "recipient",
        "clock", "invocation", "launchMinimumNs", "beganNs", "metadataLastNs", "sourceBeforeSha256", "sourceAfterSha256",
        "supplierReturnedNs", "completedNs", "supplierReturned", "childResourceClose", "parentRetirement", "budgetAcceptance",
        "testAcceptance", "exportSaveAuthority"} and type(child["schema"]) is int and child["schema"] == 1 and
        child["scope"] == RECIPIENT_CHILD_SCOPE and child["contextSha256"] == O.digest(returned.context) and
        child["startSha256"] == O.digest(records["start.json"]) and child["identitySha256"] == O.digest(identity.record) and
        child["authoritySha256"] == O.digest(authority.raw) and child["clock"] == O.clock_value(window.clock) and
        child["invocation"] == start["invocation"] and child["launchMinimumNs"] == row["launchMinimumNs"] and
        child["supplierReturned"] is True and child["childResourceClose"] == "PENDING_CLOSE" and
        child["parentRetirement"] == "NOT_OBSERVED_HERE" and child["budgetAcceptance"] == "NOT_ADMITTED" and
        child["testAcceptance"] == "NOT_PERFORMED" and child["exportSaveAuthority"] is False, "RECIPIENT_CHILD_RESULT")
    supplier = child["recipient"]
    supplier_fields = {"fingerprint", "encryption_fingerprint", "expires_at", "key_sha256", "work_identity", "executable"}
    if window.clock.role == "windows-x64":
        supplier_fields |= {"executable_sha256", "job_id"}
        require(supplier.get("job_id") == context["job"] and type(supplier.get("executable_sha256")) is str and
                re.fullmatch(r"[0-9a-f]{64}", supplier["executable_sha256"]), "RECIPIENT_WINDOWS_SUPPLIER")
    require(type(supplier) is dict and set(supplier) == supplier_fields and supplier["fingerprint"] == identity.fingerprint and
        type(supplier["encryption_fingerprint"]) is str and re.fullmatch(r"[0-9A-F]{40}", supplier["encryption_fingerprint"]) and
        supplier["key_sha256"] == identity.key_sha256 and supplier["work_identity"] == context["directories"]["crypto"] and
        type(supplier["expires_at"]) is int and (supplier["expires_at"] == 0 or supplier["expires_at"] >= identity.expires_at) and
        type(supplier["executable"]) is str and Path(supplier["executable"]).is_absolute(), "RECIPIENT_SUPPLIER_RECORD")
    times = [window.first, O.parse(authority.raw)["closedNs"], start["startedNs"], row["launchMinimumNs"], child["beganNs"],
        child["metadataLastNs"], child["supplierReturnedNs"], child["completedNs"], ack["closedNs"], row["completedNs"],
        row["finalStartedNs"], row["finalizedNs"], row["readStartedNs"], row["readbackCompletedNs"]]
    state = window.state()
    require(all(type(value) is int and 0 <= value <= O.clocks.UINT64 for value in times) and times == sorted(times) and
        row["completedNs"] < window.work and row["finalizedNs"] <= row["readStartedNs"] < row["finalEndNs"] and
        row["readbackCompletedNs"] < row["readEndNs"] and
        (row["finalStartedNs"], row["finalEndNs"], row["readStartedNs"], row["readEndNs"]) ==
        (state.final_start, state.final_end, state.read_start, state.read_end) and
        row["launchMinimumNs"] <= O.integer(birth["observedNs"]) <= row["completedNs"], "RECIPIENT_NATIVE_CLOCK_CHAIN")
    return window.now(minimum=max(times[-1], birth["observedNs"]))


@dataclass(frozen=True, repr=False)
class _RecipientValidationReturn:
    """Closed historical validation only; not a live Recipient, Admission or lease."""
    raw: bytes


def check_recipient_validation_return(result):
    saved = _RECIPIENT_RETURNS.get(id(result))
    require(type(result) is _RecipientValidationReturn and type(saved) is tuple and len(saved) == 7 and
        saved[0] is result and type(result.raw) is bytes and result.raw == saved[1] and
        _RECIPIENT_WINDOWS.get(id(saved[2])) is saved[3], "NOT_ORIGINAL_RECIPIENT_VALIDATION_RETURN")
    _recipient_claim(saved[3].claim)
    _check_history(saved[4])
    _check_history(saved[5])
    state = saved[2].state(cleanup=True)
    state.roster.known()
    require(state.terminal and not state.busy and not state.failed and state.roster.owner.original is None and
        state.roster.owner.errors == [] and state.roster.owner.phase_originals is saved[6], "RECIPIENT_CLOSED_RETURN_CHANGED")
    return result


def _prepare_and_validate_recipient(cancelled):
    """Dormant real composition; no public productive/workflow entry or token courier."""
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    handlers = ()
    owner = window = private = authority = phase = final_source = pending = graph = None
    failure = None
    try:
        require(type(cancelled) is list and not cancelled, "RECIPIENT_CANCELLATION")
        _recipient_path()  # Refuse gate/foreign roles before original preparation.
        for number in (native.signal.SIGINT, native.signal.SIGTERM,
                       *([native.signal.SIGBREAK] if hasattr(native.signal, "SIGBREAK") else [])):
            previous = native.signal.getsignal(number)
            handlers += ((number, previous),)  # Retain before the fallible install.
            native.signal.signal(number, lambda signum, _frame: cancelled.append(signum))
        prepared = _prepare_with_token(cancelled, token)
        readmission = _readmit_worker(_claim_worker(prepared), token)
        claim = _claim_recipient(readmission)
        binding, original = _recipient_claim(claim)
        local = time.monotonic()  # One LOCAL-before-RAW anchor, before allocation/authority.
        first = O.clocks.validate_reading(O.clocks.observe())
        window = _RecipientUseWindow(claim, local, first)
        owner = native.Owner(window.local_end, window, first=first, cancelled=window.cancelled)
        owner.initial_sources = {}
        window.bind(owner, first)
        observed, path, event = _recipient_host(O.parse(original.match_raw)["firstUseAt"])
        require(observed == O.parse(original.worker_originals[0])["observed"] and event == original.identity_fields[1],
                "RECIPIENT_SOURCE_CONTEXT_CHANGED")
        native.recipient_environment(path)
        private = owner.new(path)
        directories = {}
        for name in RECIPIENT_DIRECTORIES:
            child = owner.child(private, name, create=True)
            child.verify()
            directories[name] = native.directory_identity(list(child.identity), first.clock.role)
        files = {"recipient-window.json": window.raw, "worker-identity.json": original.identity_fields[0],
            "worker-match.json": original.match_raw, "worker-policy.json": original.identity_fields[2],
            "worker-proposal.json": original.proposal_raw, "recipient-public.asc": original.identity_fields[3]}
        for name, raw in files.items():
            owner.write(private, name, raw)
        authority = _recipient_authority(window, token)
        token = None  # Last owning-stack token reference ends BEFORE crypto preparation/launch.
        owner.write(private, "authority-return.json", authority.raw)
        files["authority-return.json"] = authority.raw
        context_raw = owner.write(private, "recipient-context.json", {"schema": 1, "scope": RECIPIENT_CONTEXT_SCOPE,
            "root": str(ROOT), "session": str(path), "observed": observed, "eventSha256": O.digest(event),
            "filesSha256": {name: O.digest(files[name]) for name in RECIPIENT_FILES}, "job": uuid.uuid4().hex,
            "inheritedContext": Q._inherited_context(), "directories": directories,
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        require(all(owner.read(private, name) == raw for name, raw in files.items()), "RECIPIENT_PRELAUNCH_FILES_CHANGED")
        phase = _recipient_native(owner, private, context_raw, window, authority)
        phase_graph = _history_graph(phase)
        _recipient_native_readback(owner, private, phase, window, authority, original.identity)
        final_source = source_queries(owner, window, observed, path / "source-final")
        graph = phase_graph + _history_graph(final_source, authority, owner.initial_sources)
        require(dict(final_source.records) == {name: dict(original.worker_originals[1])[name] for name in SOURCE_KEYS},
                "RECIPIENT_FINAL_SOURCE_CHANGED")
        _recipient_native_readback(owner, private, phase, window, authority, original.identity)
        require(all(owner.read(private, name, final=True) == raw for name, raw in files.items()), "RECIPIENT_FINAL_FILES_CHANGED")
        pending = owner.write(private, "recipient-pending.json", {"schema": 1,
            "scope": "INITIAL_RECIPIENT_VALIDATION_PENDING_OWNER_CLOSE_V1", "windowSha256": O.digest(window.raw),
            "contextSha256": O.digest(context_raw), "authoritySha256": O.digest(authority.raw),
            "phaseSha256": {name: O.digest(raw) for name, raw in phase.records}, "childSha256": O.digest(phase.child),
            "sourceFinalSha256": O.digest(final_source.raw), "retainedNs": window.now(),
            "retirement": "PENDING_OWNER_CLOSE", "liveRecipient": "NOT_TRANSFERRED", "budgetAcceptance": "NOT_ADMITTED",
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}, final=True)
        _check_history(graph)
        require(owner.phase_originals is phase and set(owner.initial_sources) == {str(path / "source-final")} and
            owner.initial_sources[str(path / "source-final")] is final_source, "RECIPIENT_FINAL_ORIGINALS_CHANGED")
        _recipient_claim(claim)
        preclose = window.now()
    except BaseException as error:
        failure = error if owner is None or owner.original is None else owner.original
        if owner is not None:
            owner.error("initial-recipient-parent", error,
                unknown=bool(native.diagnostics._QUARANTINE or Q.QUARANTINE))
    finally:
        token = None
        if owner is not None:
            try:
                if window.state(cleanup=True).phase == "WORK":
                    window.begin_final()
                window.state(cleanup=True).roster.freeze()
            except BaseException as error:
                owner.error("recipient-parent-close-roster", error, unknown=True)
            try:
                owner.close()
            except BaseException as error:
                owner.error("recipient-parent-close", error)
            if failure is None:
                failure = owner.original
        for number, previous in handlers:
            try:
                native.signal.signal(number, previous)
            except BaseException as error:
                if failure is None:
                    failure = error
    if owner is not None:
        try:
            window.state(cleanup=True).roster.known()
        except BaseException as error:
            owner.error("recipient-parent-close-return", error, unknown=True)
        if failure is None:
            failure = owner.original
        if owner.unknown and not any(value is owner for value in native.QUARANTINE):
            native.QUARANTINE.append(owner)
    if failure is not None:
        raise failure
    require(pending is not None and graph is not None and owner is not None, "RECIPIENT_PARENT_INCOMPLETE")
    _check_history(graph)
    _authority_return(authority, window)
    current = initial_identity.bind_worker_match(original.match, event_raw=original.identity_fields[1],
        policy_raw=original.identity_fields[2], now=int(time.time()))
    require(_worker_fields(current) == original.identity_fields and _recipient_host(O.parse(original.match_raw)["firstUseAt"]) ==
        (observed, path, event), "RECIPIENT_FINAL_POLICY_OR_EVENT_CHANGED")
    native.cancellation(cancelled)
    closed = window.now(final=True, minimum=preclose)
    native.posix._deadline(window.state(cleanup=True).read_local)
    native.cancellation(cancelled)
    state = window.state()
    _check_history(graph)
    require(owner.phase_originals is phase and set(owner.initial_sources) == {str(path / "source-final")} and
        owner.initial_sources[str(path / "source-final")] is final_source and
        type(cancelled) is list and cancelled == [], "RECIPIENT_FINAL_ORIGINALS_CHANGED")
    state = replace(state, terminal=True)
    _RECIPIENT_WINDOWS[id(window)] = state
    raw = O.encoded({"schema": 1, "scope": RECIPIENT_RETURN_SCOPE, "window": O.parse(window.raw),
        "originalReadmissionSha256": O.digest(binding.raw), "workerIdentitySha256": O.digest(original.identity_fields[0]),
        "authoritySha256": O.digest(authority.raw), "pendingSha256": O.digest(pending), "preCloseNs": preclose, "closedNs": closed,
        "resourceCount": len(state.roster.rows), "retirement": "KNOWN_RESOURCE_CLOSE_ONLY",
        "liveRecipient": "NOT_TRANSFERRED", "currentRemoteAuthority": "NOT_GRANTED_BY_HISTORY",
        "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
    returned = _RecipientValidationReturn(raw)
    closed_graph = _history_graph(returned, owner, state.roster, state)
    _RECIPIENT_RETURNS[id(returned)] = (returned, raw, window, state, graph, closed_graph, phase)
    return check_recipient_validation_return(returned)


def _retain_recipient_validation(result):
    """One file-only sender, inside the ORIGINAL actual read RAW/LOCAL caps.

    No predecessor method is observed or reopened. The two exact memory-only
    returns become private files; old source/HTTP/crypto files remain references
    for a future authenticated receiver. The manifest cannot certify its own
    later close or step outcome, and no current authority is acquired here.
    """
    check_recipient_validation_return(result)
    returns, attempts = _RECIPIENT_RETURNS, _RECIPIENT_SENDERS
    saved = returns[id(result)]
    state = saved[3]
    binding, original = _recipient_claim(state.claim)
    context = O.parse(saved[6].context)
    recipient_path = Path(context["session"])
    path = recipient_path.with_name(recipient_path.name + "-output")
    clock, hard, local_end = state.clock, state.read_end, state.read_local
    last, local_last, issued_end = state.last, state.local_last, local_end
    require(state.phase == "READ" and state.read_attempted and
        O.integer(hard, O.integer(last) + 1) == hard and type(local_end) is float and
        type(local_last) in (int, float) and math.isfinite(local_last) and
        math.isfinite(local_end) and 0 <= local_last < local_end, "RECIPIENT_SENDER_ORIGINAL_READ_CAP")
    blobs = (("readmission-return.json", binding.raw), ("recipient-return.json", saved[1]))
    require(all(type(raw) is bytes and 0 < len(raw) <= native.LIMIT for _name, raw in blobs),
            "RECIPIENT_SENDER_RECORD_LIMIT")
    owner = roster = private = first = directory_id = None
    path_graph, first_graph, closed_graph = _history_graph(recipient_path, path), None, None
    held = []  # Raw resources and their independent close ledgers, never wrapper attributes.
    windows_handles, windows_rosters = {}, []
    value = manifest_raw = None
    phase, busy, failed, output_checks = "OWNER", False, False, 0
    failure, resource_unknown = None, False
    attempt = None
    cancel = state.cancelled

    def remember(error, *, unknown=False):
        nonlocal failed, failure, resource_unknown
        failed = True
        if failure is None:
            failure = owner.original if owner is not None and owner.original is not None else error
        resource_unknown |= unknown or owner is not None and owner.unknown
        if owner is not None:
            owner.error("recipient-sender", error, unknown=resource_unknown)
            if owner.unknown and not any(item is owner for item in native.QUARANTINE):
                native.QUARANTINE.append(owner)

    def windows_pin(pin):
        # Only a newly returned pin starts here. Existing shared pins retain
        # their ORIGINAL handle/methods and independently witnessed call count.
        require(type(pin.references) is int and pin.references == 1, "RECIPIENT_SENDER_WINDOWS_NEW_PIN_REFERENCES")
        dictionary, info_dictionary, handle = pin.__dict__, pin.info.__dict__, pin.handle
        fields = tuple((name, getattr(pin, name)) for name in ("api", "path", "info", "private",
            "inherited_allowed", "writable", "strict_streams", "immutable", "lock"))
        graph = _history_graph(info_dictionary)
        acquire_raw, release_raw, lock = pin.acquire, pin.release, pin.lock
        require(set(dictionary) == {name for name, _value in fields} | {"references", "handle"} and
            getattr(acquire_raw, "__self__", None) is pin and acquire_raw.__func__ is native.windows._Pin.acquire and
            getattr(release_raw, "__self__", None) is pin and release_raw.__func__ is native.windows._Pin.release,
            "RECIPIENT_SENDER_WINDOWS_NEW_PIN_METHODS")
        count, running, terminal_error = 1, False, None

        def fail(error):
            nonlocal terminal_error
            if terminal_error is None:
                terminal_error = error
            remember(terminal_error, unknown=True)
            return terminal_error

        def data(expected):
            require(type(pin) is native.windows._Pin and pin.__dict__ is dictionary and
                set(dictionary) == {name for name, _value in fields} | {"references", "handle", "acquire", "release"} and
                pin.acquire is acquire_guard and pin.release is release_guard,
                "RECIPIENT_SENDER_WINDOWS_PIN_CHANGED")
            require(all(getattr(pin, name) is value or type(getattr(pin, name)) is type(value) and
                type(value) in (type(None), bool, int, float, str) and getattr(pin, name) == value
                for name, value in fields) and pin.info.__dict__ is info_dictionary,
                "RECIPIENT_SENDER_WINDOWS_PIN_CHANGED")
            _check_history(graph)
            require(type(pin.references) is int and pin.references == expected and
                (type(pin.handle) is type(handle) and pin.handle == handle if expected else pin.handle is None),
                "RECIPIENT_SENDER_WINDOWS_HANDLE_RETIREMENT")

        def checked(expected=None):
            try:
                with lock:
                    if terminal_error is not None:
                        raise terminal_error
                    require(not running, "RECIPIENT_SENDER_WINDOWS_PIN_REENTRY")
                    data(count)
                    require(expected is None or count == expected, "RECIPIENT_SENDER_WINDOWS_HANDLE_RETIREMENT")
            except BaseException as error:
                raise fail(error)

        def change(self, acquiring):
            nonlocal count, running
            try:
                with lock:
                    require(self is pin, "RECIPIENT_SENDER_WINDOWS_PIN_NOT_ORIGINAL")
                    checked()
                    require(count > 0, "RECIPIENT_SENDER_WINDOWS_PIN_RETIRED")
                    # A failed sibling must not prevent healthy-prefix cleanup.
                    # Only THIS pin's sticky failure forbids another native call.
                    running = True  # Attempted before the saved method/native boundary.
                    try:
                        returned = acquire_raw() if acquiring else release_raw()
                        require(returned is (pin if acquiring else None), "RECIPIENT_SENDER_WINDOWS_PIN_RETURN")
                        if terminal_error is not None:
                            raise terminal_error
                        expected = count + (1 if acquiring else -1)
                        data(expected)
                        count = expected  # Never learn a counter from a later public snapshot.
                        return returned
                    finally:
                        running = False
            except BaseException as error:
                raise fail(error)

        def acquire(self):
            return change(self, True)

        def release(self):
            return change(self, False)

        acquire_guard, release_guard = acquire.__get__(pin), release.__get__(pin)
        pin.acquire, pin.release = acquire_guard, release_guard
        checked()
        return pin, checked

    def windows_pins():
        # Stable wrapper boundaries only: temporary readers/clones have already
        # returned/retired. Each still-live returned resource owns exactly one
        # reference to each original pin; a new writer adds one, its close removes
        # one. No post-callback counter/handle recapture can witness native close.
        for pin, checked in windows_handles.values():
            expected = sum(not is_closed() for pins, is_closed in windows_rosters if any(item is pin for item in pins))
            checked(expected)

    def retain(raw, label, intended, intended_graph):
        # The factory has ACTUALLY returned. Retain that reference before any
        # fallible pin/check, and before Owner.acquire's postallocation clocks.
        slot = [raw, None]
        held.append(slot)
        require(len(held) <= 4, "RECIPIENT_SENDER_RESOURCE_LIMIT")  # One directory, three fixed records.
        raw_type, raw_path, row = type(raw), raw.path, None
        windows = clock.role == "windows-x64"
        raw_id = raw.identity if label == "directory" or windows else raw.original
        identity = tuple(native.directory_identity(list(raw_id if label == "directory" or windows else
            (raw_id.st_dev, raw_id.st_ino)), clock.role))
        graph = _history_graph(raw_path, raw_id) + intended_graph
        close_raw, verify_raw = raw.close, raw.verify
        attempted, closed, executing, close_error = False, False, False, None
        closed_pins = None
        if windows:
            require(raw_type is (native.windows.PrivateDirectory if label == "directory" else native.windows.NativeFile),
                "RECIPIENT_SENDER_WINDOWS_RESOURCE_TYPE")
            raw_api, operation_lock, pin_list = raw._api, raw._operation_lock, raw._pins
            require(type(pin_list) is list and 0 < len(pin_list) <= native.windows.MAX_DEPTH + 1 and
                len({id(pin) for pin in pin_list}) == len(pin_list), "RECIPIENT_SENDER_WINDOWS_PIN_ROSTER")
            pins = tuple(pin_list)
            graph += _history_graph(pin_list)
            windows_rosters.append((pins, lambda: closed))  # Independently retain even a later failed return.
            for pin in pins:
                require(type(pin) is native.windows._Pin and type(pin.info) is native.windows.FileInfo and
                    pin.api is raw_api, "RECIPIENT_SENDER_WINDOWS_PIN_TYPE")
                if id(pin) not in windows_handles:
                    windows_handles[id(pin)] = windows_pin(pin)
            if label == "writer":
                maximum, deadline, writable = raw.max_bytes, raw._deadline, raw._writable
                initial_info = raw.initial_info
                initial_dictionary = initial_info.__dict__
                graph += _history_graph(initial_dictionary)
        if label == "writer":
            write_raw, sync_raw = raw.write, raw.sync
            if not windows:
                parent, stream, maximum, deadline = raw.parent, raw.stream, raw.maximum, raw.deadline
        else:
            create_raw, read_raw = raw.create_file, raw.read_bytes
            names_raw = raw.names if windows else None

        def raw_pins(*, retired):
            try:
                _check_history(graph)
                require(type(raw) is raw_type and raw.path is raw_path and raw_path == intended and
                    (raw.identity is raw_id if label == "directory" or windows else raw.original is raw_id),
                    "RECIPIENT_SENDER_RESOURCE_CHANGED")
                require((raw._closed if windows and label == "directory" else raw.closed) is retired,
                    "RECIPIENT_SENDER_RESOURCE_CLOSE_CHANGED")
                if windows:
                    require(raw._api is raw_api and raw._operation_lock is operation_lock and
                        (raw._pins is closed_pins and type(closed_pins) is list and not closed_pins and
                            closed_pins is not pin_list if retired else raw._pins is pin_list),
                        "RECIPIENT_SENDER_WINDOWS_RESOURCE_CHANGED")
                    windows_pins()
                if label == "writer":
                    if windows:
                        require(raw._retired is retired and type(raw.max_bytes) is type(maximum) and raw.max_bytes == maximum and
                            type(raw._deadline) is type(deadline) and raw._deadline == deadline and raw._writable is writable and
                            raw.initial_info is initial_info and initial_info.__dict__ is initial_dictionary,
                            "RECIPIENT_SENDER_WINDOWS_RESOURCE_CHANGED")
                    else:
                        require(raw.parent is parent and raw.stream is stream and type(raw.maximum) is type(maximum) and
                            raw.maximum == maximum and type(raw.deadline) is type(deadline) and raw.deadline == deadline and
                            stream.closed is retired, "RECIPIENT_SENDER_RESOURCE_CHANGED")
            except BaseException as error:
                remember(error, unknown=True)
                raise

        def row_pins(expected=None):
            nonlocal row
            rows = [item for item in owner.resources if type(item) is dict and item.get("owner") is wrapper]
            require(len(rows) == 1, "RECIPIENT_SENDER_RESOURCE_ROSTER")
            if row is None:
                row = rows[0]  # Before the first postallocation callback, in deadline's entry pins.
            require(rows[0] is row and set(row) == {"label", "owner", "attempted", "closed"} and
                row["label"] == label and type(row["attempted"]) is bool and type(row["closed"]) is bool and
                (row["attempted"], row["closed"]) == ((attempted, closed) if expected is None else expected),
                "RECIPIENT_SENDER_RESOURCE_CLOSE_LEDGER")

        def checked():
            row_pins()
            if close_error is not None:
                raise close_error  # Owner.original/errors are not the close witness.
            raw_pins(retired=closed)

        def original(self):
            require(self is wrapper, "RECIPIENT_SENDER_RESOURCE_NOT_ORIGINAL")

        def invoke(self, method, *args, **kwargs):
            nonlocal executing
            try:
                original(self)
                require(phase == "OWNER" and not failed and not executing and not attempted,
                    "RECIPIENT_SENDER_RESOURCE_NOT_LIVE")
                raw_pins(retired=False)
                executing = True
                try:
                    returned = method(*args, **kwargs)
                    raw_pins(retired=False)
                    return returned
                finally:
                    executing = False
            except BaseException as error:
                remember(error)
                raise

        class Resource:
            __slots__ = ()

            path = property(lambda self: (original(self), raw_path)[1])
            identity = property(lambda self: (original(self), identity)[1])
            closed = property(lambda self: (original(self), closed)[1])

            def verify(self):
                return invoke(self, verify_raw)

            def close(self):
                nonlocal attempted, closed, executing, close_error, closed_pins
                try:
                    original(self)
                    require(not attempted and not executing, "RECIPIENT_SENDER_RESOURCE_CLOSE_REUSED")
                    # Only Owner.close_one may have advanced this row. Its
                    # booleans do not witness an actual raw close call/return.
                    row_pins((True, False))
                    raw_pins(retired=False)
                    attempted, executing = True, True
                    try:
                        close_raw()
                        closed = True
                        if windows:
                            closed_pins = raw._pins  # Exact post-release empty list, not a new live roster.
                        raw_pins(retired=True)
                    except BaseException as error:
                        close_error = error
                        raise
                    finally:
                        executing = False
                except BaseException as error:
                    remember(error, unknown=self is wrapper)
                    raise

        class Writer(Resource):
            __slots__ = ()

            def write(self, raw_bytes):
                return invoke(self, write_raw, raw_bytes)

            def sync(self):
                return invoke(self, sync_raw)

        class Directory(Resource):
            __slots__ = ()

            def create_file(self, name, *, max_bytes, deadline):
                nonlocal executing
                try:
                    original(self)
                    require(phase == "OWNER" and not failed and not executing and not attempted,
                        "RECIPIENT_SENDER_RESOURCE_NOT_LIVE")
                    target = raw_path / Q._component(name)
                    target_graph = _history_graph(target)  # Before the factory's own observations.
                    raw_pins(retired=False)
                    executing = True
                    try:
                        child = create_raw(name, max_bytes=max_bytes, deadline=deadline)
                        returned = retain(child, "writer", target, target_graph)
                        raw_pins(retired=False)
                        return returned
                    finally:
                        executing = False
                except BaseException as error:
                    remember(error, unknown=True)
                    raise

            def read_bytes(self, name, *, max_bytes, deadline):
                return invoke(self, read_raw, name, max_bytes=max_bytes, deadline=deadline)

            def names(self, *, max_names, deadline):
                require(names_raw is not None, "RECIPIENT_SENDER_WINDOWS_LIST_ONLY")
                return invoke(self, names_raw, max_names=max_names, deadline=deadline)

        wrapper = Directory() if label == "directory" else Writer()
        slot[1] = checked
        raw_pins(retired=False)
        return wrapper

    def ownership():
        _check_history(path_graph)
        if first_graph is not None:
            _check_history(first_graph)
        if roster is not None:
            try:
                roster.check()
                require(not resource_unknown and len(held) == len(owner.resources) and
                    all(check is not None for _raw, check in held), "RECIPIENT_SENDER_RESOURCE_ROSTER")
                for _raw, check in held:
                    check()
            except BaseException as error:
                remember(error, unknown=True)
                raise

    def pins():
        require(_RECIPIENT_RETURNS is returns and returns.get(id(result)) is saved and
            _RECIPIENT_SENDERS is attempts and attempts.get(id(result)) is attempt,
            "RECIPIENT_SENDER_ORIGINAL_REGISTRY_CHANGED")
        check_recipient_validation_return(result)  # Passive history, not old now()/deadline().
        require(O.wire.TOKEN_ENV not in os.environ, "RECIPIENT_SENDER_READ_TOKEN")
        require(not native.QUARANTINE and not Q.QUARANTINE and not native.diagnostics._QUARANTINE,
                "RECIPIENT_SENDER_PRIOR_UNKNOWN")
        ownership()
        if roster is not None:
            require(owner.original is None and not owner.unknown and owner.errors == [], "RECIPIENT_SENDER_OWNER_FAILED")
        if phase == "OUTPUT":
            require(closed_graph is not None, "RECIPIENT_SENDER_OUTPUT_NOT_ARMED")
            _check_history(closed_graph)
            roster.known()

    class SenderFence:
        # All live state is held by this fixed original-call closure. There are
        # no caller-selected clocks/caps/readers and no writable field aliases.
        __slots__ = ()

        clock = property(lambda _self: clock)
        last = property(lambda _self: last)
        local_end = property(lambda _self: local_end)

        def now(self, *, final=False, minimum=0, limit=None):
            nonlocal last, local_last, busy, failed, phase, output_checks
            if busy:
                error = I.AdmissionError("RECIPIENT_SENDER_REENTRY")
                remember(error)
                raise error
            busy = True
            try:
                require(self is fence and type(final) is bool and phase in ("OWNER", "CLOSING", "OUTPUT") and
                    (phase == "CLOSING" and final or not failed), "RECIPIENT_SENDER_NOT_LIVE")
                require(phase != "OUTPUT" or final, "RECIPIENT_SENDER_OUTPUT_ONLY")
                closing = phase == "CLOSING"
                cap = hard if limit is None else min(hard, O.integer(limit))
                minimum = O.integer(minimum)
                check = ownership if closing else pins
                check()
                for index in range(1 if closing else 2):
                    local = time.monotonic()
                    check()
                    require(type(local) in (int, float) and math.isfinite(local) and local >= local_last,
                            "RECIPIENT_SENDER_LOCAL_BACKWARDS")
                    local_last = local
                    last = O.clocks.checked_now(clock, minimum_ns=max(last, minimum))
                    check()
                    after = time.monotonic()
                    check()
                    require(type(after) in (int, float) and math.isfinite(after) and after >= local_last,
                            "RECIPIENT_SENDER_LOCAL_BACKWARDS")
                    local_last = after
                    require(last < cap and local_last < issued_end, "RECIPIENT_SENDER_EXPIRED")
                    if not closing:
                        pins()
                        if index == 0:
                            cancel()
                require(closing or not failed, "RECIPIENT_SENDER_FAILED")
                if phase == "OUTPUT":
                    output_checks += 1
                    require(output_checks <= 2, "RECIPIENT_SENDER_OUTPUT_REUSED")
                    if output_checks == 2:
                        phase = "COMPLETE"
                return last
            except BaseException as error:
                remember(error)
                raise
            finally:
                busy = False

        def deadline(self, maximum, *, final=False, limit=None):
            nonlocal local_last, issued_end, failed
            try:
                require(self is fence and phase == "OWNER" and type(maximum) in (int, float) and math.isfinite(maximum) and
                    0 < maximum <= 45, "RECIPIENT_SENDER_IO_ONLY")
                pins()  # Bind a just-registered row before the first allocation-return callback.
                local = time.monotonic()
                pins()
                require(type(local) in (int, float) and math.isfinite(local) and local >= local_last,
                        "RECIPIENT_SENDER_LOCAL_BACKWARDS")
                local_last = local
                observed = self.now(final=final, limit=limit)
                cap = hard if limit is None else min(hard, O.integer(limit))
                issued_end = min(issued_end, O.wire._directed_deadline(local, maximum, cap, observed))
                pins()
                return issued_end
            except BaseException as error:
                remember(error)
                raise

    fence = SenderFence()
    attempt = (result, saved, fence)  # Retains the actual owner through its closure, including on failure.
    with _RECIPIENT_USE_LOCK:
        require(_RECIPIENT_RETURNS is returns and returns.get(id(result)) is saved and
            _RECIPIENT_SENDERS is attempts, "RECIPIENT_SENDER_ORIGINAL_REGISTRY_CHANGED")
        require(id(result) not in attempts, "RECIPIENT_SENDER_ALREADY_CLAIMED")
        attempts[id(result)] = attempt  # Irreversible before the first live observation/allocation.
    try:
        first = O.clocks.Reading(clock, fence.now())
        first_graph = _history_graph(first)  # Before Owner construction or any later observation.
        owner = native.Owner(local_end, fence, first=first, cancelled=cancel)
        owner.initial_sources = {}
        roster = _RecipientRoster(owner, fence, first)
        fence.now()
        private = owner.acquire("directory", lambda: retain(Q._new_private_directory(path), "directory", path, path_graph))
        directory_id = tuple(native.directory_identity(list(private.identity), clock.role))
        pins()
        native._new_entry_owned(owner, private, path, directory_id)
        require(not native._initializer_names(owner, private), "RECIPIENT_SENDER_DIRECTORY_NOT_EMPTY")
        for name, raw in blobs:
            require(owner.write(private, name, raw) == raw, "RECIPIENT_SENDER_RETURN_BYTES_CHANGED")
        manifest_raw = owner.write(private, "sender-pending.json", {"schema": 1, "scope": RECIPIENT_SENDER_SCOPE,
            "directory": str(path), "directoryIdentity": list(directory_id),
            "records": {name: {"bytes": len(raw), "sha256": O.digest(raw)} for name, raw in blobs},
            "originalReferences": {"recipientSession": str(recipient_path), "readmissionSession": str(binding.path),
                "scope": "PINNED_CONTEXT_REFERENCES_NOT_CURRENT_FILESYSTEM_OBSERVATIONS",
                "workerIdentitySha256": O.digest(original.identity_fields[0]),
                "serviceTimeBasisSha256": O.digest(original.service_time_raw),
                "originalProposalSha256": O.digest(original.proposal_raw)},
            "readWindow": {"clock": O.clock_value(clock), "previousNs": state.last, "previousLocal": state.local_last,
                "readEndNs": hard, "readLocalCeiling": local_end, "retainedNs": fence.now()},
            "writerReturn": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE", "originalStepOutcome": "NOT_OBSERVED",
            "completeOriginals": "NOT_ESTABLISHED_BY_THIS_BUNDLE", "liveRecipient": "NOT_TRANSFERRED",
            "currentRemoteAuthority": "NOT_GRANTED_BY_HISTORY", "budgetAcceptance": "NOT_ADMITTED",
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        for name, raw in (*blobs, ("sender-pending.json", manifest_raw)):
            require(owner.read(private, name) == raw, "RECIPIENT_SENDER_FINAL_BYTES_CHANGED")
        require(native._initializer_names(owner, private) == tuple(sorted(name for name, _raw in
            (*blobs, ("sender-pending.json", manifest_raw)))), "RECIPIENT_SENDER_FINAL_ROSTER_CHANGED")
        native._new_entry_owned(owner, private, path, directory_id)
        pins()
    except BaseException as error:
        remember(owner.original if failure is None and owner is not None and owner.original is not None else error)
    finally:
        phase = "CLOSING"
        if owner is not None:
            try:
                ownership()
                roster.freeze()
            except BaseException as error:
                remember(error, unknown=owner.unknown)
            try:
                owner.close()
            except BaseException as error:
                remember(error)
            if failure is None:
                failure = owner.original
            if owner.unknown and not any(value is owner for value in native.QUARANTINE):
                native.QUARANTINE.append(owner)
    if failure is not None:
        phase = "FAILED"
        raise failure
    try:
        require(owner is not None and manifest_raw is not None, "RECIPIENT_SENDER_INCOMPLETE")
        roster.known()  # Actual close return, not merely Owner.closed set at close entry.
        pins()
        fence.now(final=True)
        pins()
        require(not failed, "RECIPIENT_SENDER_FAILED")
        value = native.public_result(RECIPIENT_OUTPUT_SCOPE, "recipientSenderSha256", manifest_raw)
        closed_graph = _history_graph(owner, roster, value)
        phase = "OUTPUT"  # Only now may guarded's final=True checks emit a digest.
        return value, fence, hard
    except BaseException as error:
        phase = "FAILED"
        remember(error)
        raise failure


def validate_recipient(cancelled):
    """Dormant fixed sender command, not a productive admission or trusted caller."""
    return _retain_recipient_validation(_prepare_and_validate_recipient(cancelled))


def _read_recipient_sender(owner, directory, *, recipient_outcome, expected_sha256):
    """SUPPLIED_PACKAGE_CONSISTENCY_ONLY; enclosing OWNER_CLOSE_PENDING.

    Borrow the live bounded Owner and its already registered sender directory.
    Return only immutable bytes, never an original-call capability or authority.
    The future trusted caller must supply the actual step outcome and separately
    transported hash. This helper cannot authenticate either input. References
    are NOT traversed: complete originals/current authority remain unestablished.
    Historical clock labels do not attest host/boot; LOCAL history is not a new
    deadline, and retainedNs is not the sender's final return high-water.
    """
    require(type(recipient_outcome) is str and recipient_outcome == "success", "RECIPIENT_READ_STEP_OUTCOME")
    require(type(expected_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", expected_sha256),
            "RECIPIENT_READ_ORIGINAL_HASH")
    require(type(owner) is native.Owner and owner.first is not None and owner.fence is not None and
            type(owner.resources) is list and type(owner.errors) is list, "RECIPIENT_READ_OWNER")
    first, fence, ledger, errors = owner.first, owner.fence, owner.resources, owner.errors
    cancelled, local_end, limits = owner.cancelled, owner.local_end, (owner.work_limit, owner.final_limit)
    O.clocks.validate_reading(first)
    first_ns, clock_raw = first.nanoseconds, O.encoded(O.clock_value(first.clock))
    require(callable(cancelled) and type(local_end) is float and math.isfinite(local_end), "RECIPIENT_READ_OWNER")
    require(all(type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
        type(row["label"]) is str and row["label"] in ("directory", "writer", "stdout", "stderr", "native-scope") and
        type(row["attempted"]) is bool and type(row["closed"]) is bool and (not row["closed"] or row["attempted"])
        for row in ledger), "RECIPIENT_READ_RESOURCE_ROSTER")
    rows = tuple((row, row["label"], row["owner"], row["attempted"], row["closed"]) for row in ledger)
    require(len({id(row) for row, *_rest in rows}) == len(rows) ==
        len({id(resource) for _row, _label, resource, _attempted, _closed in rows}), "RECIPIENT_READ_RESOURCE_ALIAS")

    def roster():
        return owner.resources is ledger and len(ledger) == len(rows) and all(
            row is saved and type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
            type(row["label"]) is str and row["label"] == label and row["owner"] is resource and
            row["attempted"] is attempted and row["closed"] is closed
            for row, (saved, label, resource, attempted, closed) in zip(ledger, rows))

    def pins():
        require(type(owner) is native.Owner and owner.first is first and owner.fence is fence and
            owner.resources is ledger and owner.errors is errors and owner.cancelled is cancelled and
            type(owner.local_end) is float and owner.local_end == local_end and
            all(type(a) is type(b) and a == b for a, b in zip((owner.work_limit, owner.final_limit), limits)) and
            type(first.nanoseconds) is int and first.nanoseconds == first_ns and
            O.encoded(O.clock_value(first.clock)) == clock_raw == O.encoded(O.clock_value(fence.clock)),
            "RECIPIENT_READ_OWNER_CHANGED")
        require(roster(), "RECIPIENT_READ_ROSTER_CHANGED")
        require(owner.closed is False and owner.unknown is False and owner.original is None and errors == [],
            "RECIPIENT_READ_OWNER_NOT_LIVE")
        require(not native.QUARANTINE and not Q.QUARANTINE and not native.diagnostics._QUARANTINE,
            "RECIPIENT_READ_PRIOR_UNKNOWN")

    def checked():
        pins()
        cancelled()  # A bound fence need not forward the borrowed cancellation.
        pins()
        owner.end()
        pins()
        cancelled()
        pins()
        owner.end()  # The cancellation callback also spends the ORIGINAL interval.
        pins()

    def call(function, *args):
        checked()
        value = function(*args)
        checked()
        return value

    def same(actual, expected):
        require(O.encoded(actual) == O.encoded(expected), "RECIPIENT_READ_BINDING")

    def hashes(value, names):
        require(all(type(value[name]) is str and re.fullmatch(r"[0-9a-f]{64}", value[name]) for name in names),
            "RECIPIENT_READ_RECORD_HASHES")

    def record(raw, fields, scope):
        value = O.parse(raw)
        require(type(value) is dict and set(value) == fields and raw == O.encoded(value) and
            type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == scope and
            value["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY" and value["budgetAcceptance"] == "NOT_ADMITTED" and
            value["exportSaveAuthority"] is False, "RECIPIENT_READ_RETURN")
        O.integer(value["resourceCount"], 1)
        return value

    try:
        recipient_path = call(_recipient_path)
        path = recipient_path.with_name(recipient_path.name + "-output")
        entry_path = recipient_path.with_name(recipient_path.name.removesuffix("-recipient") + "-entry")
        require(directory is not None and directory.path == path, "RECIPIENT_READ_LAYOUT")
        directory_id = tuple(native.directory_identity(list(directory.identity), first.clock.role))

        def locations():
            call(native._new_entry_owned, owner, directory, path, directory_id)

        names = ("readmission-return.json", "recipient-return.json")
        expected_roster = tuple(sorted((*names, "sender-pending.json")))
        locations()
        raw = call(owner.read, directory, "sender-pending.json")
        require(type(raw) is bytes and 0 < len(raw) <= native.LIMIT and O.digest(raw) == expected_sha256,
            "RECIPIENT_READ_HASH_CHANGED")
        value = O.parse(raw)
        require(type(value) is dict and set(value) == {"schema", "scope", "directory", "directoryIdentity", "records",
            "originalReferences", "readWindow", "writerReturn", "originalStepOutcome", "completeOriginals",
            "liveRecipient", "currentRemoteAuthority", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"} and
            raw == O.encoded(value) and type(value["schema"]) is int and value["schema"] == 1 and
            value["scope"] == RECIPIENT_SENDER_SCOPE and value["writerReturn"] == "PENDING_NOT_OBSERVABLE_BY_THIS_FILE" and
            value["originalStepOutcome"] == "NOT_OBSERVED" and value["completeOriginals"] == "NOT_ESTABLISHED_BY_THIS_BUNDLE" and
            value["liveRecipient"] == "NOT_TRANSFERRED" and value["currentRemoteAuthority"] == "NOT_GRANTED_BY_HISTORY" and
            value["budgetAcceptance"] == "NOT_ADMITTED" and value["testAcceptance"] == "NOT_PERFORMED" and
            value["exportSaveAuthority"] is False, "RECIPIENT_READ_INDEX")
        require(value["directory"] == str(path) and native.directory_identity(value["directoryIdentity"], first.clock.role) ==
            list(directory_id), "RECIPIENT_READ_DIRECTORY")
        references = value["originalReferences"]
        require(type(references) is dict and set(references) == {"recipientSession", "readmissionSession", "scope",
            "workerIdentitySha256", "serviceTimeBasisSha256", "originalProposalSha256"} and
            references["recipientSession"] == str(recipient_path) and references["readmissionSession"] == str(entry_path) and
            references["scope"] == "PINNED_CONTEXT_REFERENCES_NOT_CURRENT_FILESYSTEM_OBSERVATIONS", "RECIPIENT_READ_REFERENCES")
        require(type(value["records"]) is dict and set(value["records"]) == set(names), "RECIPIENT_READ_RECORD_ROSTER")
        require(call(native._initializer_names, owner, directory) == expected_roster, "RECIPIENT_READ_ROSTER")
        blobs = {}
        for name in names:
            locations()
            row = value["records"][name]
            require(type(row) is dict and set(row) == {"bytes", "sha256"} and type(row["bytes"]) is int and
                0 < row["bytes"] <= native.LIMIT and type(row["sha256"]) is str and
                re.fullmatch(r"[0-9a-f]{64}", row["sha256"]), "RECIPIENT_READ_RECORD_BINDING")
            blob = call(owner.read, directory, name, row["bytes"])
            require(type(blob) is bytes and len(blob) == row["bytes"] and O.digest(blob) == row["sha256"],
                "RECIPIENT_READ_RECORD_CHANGED")
            blobs[name] = blob
        common = {"schema", "scope", "window", "workerIdentitySha256", "pendingSha256", "preCloseNs", "closedNs",
            "resourceCount", "retirement", "budgetAcceptance", "exportSaveAuthority"}
        entry = record(blobs[names[0]], common | {"originalPreparationSha256", "serviceTimeBasisSha256",
            "allocationProposalSha256", "firstUseAt", "workerAdmission", "qualificationAcceptance"}, READMISSION_SCOPE)
        recipient = record(blobs[names[1]], common | {"originalReadmissionSha256", "authoritySha256",
            "liveRecipient", "currentRemoteAuthority", "testAcceptance"}, RECIPIENT_RETURN_SCOPE)
        require(entry["workerAdmission"] == "NOT_PERFORMED" and entry["qualificationAcceptance"] == "NOT_ESTABLISHED" and
            recipient["liveRecipient"] == "NOT_TRANSFERRED" and recipient["currentRemoteAuthority"] == "NOT_GRANTED_BY_HISTORY" and
            recipient["testAcceptance"] == "NOT_PERFORMED", "RECIPIENT_READ_RETURN")
        hashes(entry, ("originalPreparationSha256", "workerIdentitySha256", "pendingSha256",
            "serviceTimeBasisSha256", "allocationProposalSha256"))
        hashes(recipient, ("originalReadmissionSha256", "workerIdentitySha256", "authoritySha256", "pendingSha256"))
        eframe, _eclock, efirst, ework, efinal = _entry_frame(O.encoded(entry["window"]))
        rframe, _rclock, rfirst, rends = _recipient_frame(O.encoded(recipient["window"]))
        same(entry["originalPreparationSha256"], eframe["originalPreparationSha256"])
        same(entry["workerIdentitySha256"], eframe["workerIdentitySha256"])
        same(entry["firstUseAt"], eframe["firstUseAt"])
        same(entry["allocationProposalSha256"], eframe["originalProposalSha256"])
        same(rframe["originalProposedJobEndNs"], eframe["originalProposedJobEndNs"])
        same(rframe["firstUseAt"], entry["firstUseAt"])
        same(rframe["previousNs"], entry["closedNs"])
        for supplied in (rframe["originalReadmissionSha256"], recipient["originalReadmissionSha256"]):
            same(supplied, O.digest(blobs[names[0]]))
        for supplied in (rframe["workerIdentitySha256"], recipient["workerIdentitySha256"], references["workerIdentitySha256"]):
            same(supplied, entry["workerIdentitySha256"])
        for supplied in (rframe["originalProposalSha256"], references["originalProposalSha256"]):
            same(supplied, entry["allocationProposalSha256"])
        same(references["serviceTimeBasisSha256"], entry["serviceTimeBasisSha256"])
        window = value["readWindow"]
        require(type(window) is dict and set(window) == {"clock", "previousNs", "previousLocal", "readEndNs",
            "readLocalCeiling", "retainedNs"}, "RECIPIENT_READ_WINDOW")
        for clock in (eframe["clock"], rframe["clock"], window["clock"]):
            require(O.encoded(clock) == clock_raw, "RECIPIENT_READ_CLOCK")  # Labels only, not same-host proof.
        same(window["previousNs"], recipient["closedNs"])
        ep, ec, rp, rc, retained, end = (O.integer(number) for number in (entry["preCloseNs"], entry["closedNs"],
            recipient["preCloseNs"], recipient["closedNs"], window["retainedNs"], window["readEndNs"]))
        require(efirst <= ep < ework and ep <= ec < efinal and ec <= rfirst <= rp <= rc <= retained < end <= rends[2],
            "RECIPIENT_READ_CHRONOLOGY")
        previous_local, ceiling = window["previousLocal"], window["readLocalCeiling"]
        require(type(previous_local) in (int, float) and type(ceiling) is float and
            math.isfinite(previous_local) and math.isfinite(ceiling) and 0 <= previous_local < ceiling,
            "RECIPIENT_READ_LOCAL_RECORD")
        # Never observe old owners or adopt their historical RAW/LOCAL fences.
        require(call(native._initializer_names, owner, directory) == expected_roster, "RECIPIENT_READ_ROSTER")
        for name in names:
            locations()
            require(call(owner.read, directory, name, len(blobs[name])) == blobs[name], "RECIPIENT_READ_REREAD_CHANGED")
        require(call(owner.read, directory, "sender-pending.json") == raw, "RECIPIENT_READ_INDEX_CHANGED")
        require(call(native._initializer_names, owner, directory) == expected_roster, "RECIPIENT_READ_ROSTER")
        locations()
        checked()
        return raw, tuple((name, blobs[name]) for name in names)
    except BaseException as error:
        original = owner.original if owner.original is not None else error
        try:
            owner.error("recipient-sender-read", error, unknown=not roster())
        except BaseException:
            owner.unknown = True
        raise original  # The caller retains every borrowed resource and owns cleanup.


def _initial_query_record(row, blobs, owner_value):
    """Historical query grammar only; the caller first binds every original byte."""
    fields = {"schema", "scope", "id", "job", "state", "home", "cwd", "argv", "stdoutLimit", "stderrLimit",
        "timeoutSeconds", "launchAttempted", "scopeAttempted", "waitExitCode", "retirement", "result", "errors", "outputs"}
    require(type(row) is dict and set(row) == fields | {"ownedSurvivors", "ownership"} and
        type(row["schema"]) is int and row["schema"] == 1 and row["scope"] == "NATIVE_OWNED_ORDINARY_GIT_QUERY" and
        type(row["id"]) is str and re.fullmatch(r"[0-9a-f]{32}", row["id"]) and
        all(row[name] == owner_value[name] for name in ("job", "state", "home")) and
        row["cwd"] == owner_value["root"] and row["launchAttempted"] is True and row["scopeAttempted"] is True and
        type(row["waitExitCode"]) is int and row["waitExitCode"] == 0 and row["retirement"] == "KNOWN" and
        row["result"] == "READY_FOR_CALLER_SEAL" and row["errors"] == [] and row["ownedSurvivors"] == [],
        "QUERY_ORIGINAL_RESULT")
    argv = row["argv"]
    prefix = [owner_value["git"], "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false", "-C", str(ROOT)]
    require(type(argv) is list and all(type(arg) is str and 0 < len(arg) <= 8192 and "\0" not in arg for arg in argv) and
        argv[:len(prefix)] == prefix and Q._allowed_suffix(tuple(argv[len(prefix):])) and
        type(row["stdoutLimit"]) is int and 0 < row["stdoutLimit"] <= I.EVENT_LIMIT and
        type(row["stderrLimit"]) is int and row["stderrLimit"] == 4096 and
        type(row["timeoutSeconds"]) is int and row["timeoutSeconds"] == 15, "QUERY_ORIGINAL_COMMAND")
    require(blobs["result.json"] == Q.encoded(row), "QUERY_ORIGINAL_RESULT_BYTES")
    start = O.parse(blobs["start.json"])
    require(set(start) == fields | {"environment"} and blobs["start.json"] == Q.encoded(start) and
        all(O.encoded({name: start[name]}) == O.encoded({name: row[name]}) for name in fields -
            {"launchAttempted", "scopeAttempted", "waitExitCode", "retirement", "result", "outputs"}) and
        start["launchAttempted"] is False and start["scopeAttempted"] is False and start["waitExitCode"] is None and
        start["retirement"] == "UNKNOWN" and start["result"] == "HOLD" and start["outputs"] == {},
        "QUERY_ORIGINAL_START")
    environment = start["environment"]
    ancestors = owner_value["ancestorContext"]
    if set(ancestors) == set(Q._CONTEXT):
        require(ancestors[Q.processes.DOMAINS_ENV].isascii(), "QUERY_ORIGINAL_ANCESTOR_CONTEXT")
        domains = Q.processes.ownership_domains(ancestors[Q.processes.CHAIN_ENV], ancestors[Q.processes.DOMAINS_ENV])
        require(domains and ancestors[Q.processes.JOB_ENV] == domains[-1]["job"] and
            ancestors[Q.processes.STATE_ENV] == domains[-1]["state"] and
            ancestors["GRADLE_USER_HOME"] == domains[-1]["home"], "QUERY_ORIGINAL_ANCESTOR_CONTEXT")
    expected = Q.processes.ownership_environment(owner_value["ancestorContext"], row["job"], row["id"],
        row["state"], row["home"], allow_new_context=True)
    require(type(environment) is dict and all(type(value) is str for value in environment.values()) and
        all(environment.get(name) == value for name, value in expected.items()) and
        set(environment) == set(expected) | {"PATH", "LANG", "LC_ALL", "GIT_TERMINAL_PROMPT", "GIT_CONFIG_NOSYSTEM",
            "GIT_CONFIG_GLOBAL", "GIT_NO_LAZY_FETCH", "GIT_NO_REPLACE_OBJECTS", "GIT_OPTIONAL_LOCKS"} |
            ({"SYSTEMROOT"} if owner_value["nativeRole"] == "windows-x64" else set()) and
        all(environment.get(name) == value for name, value in {"LANG": "C", "LC_ALL": "C", "GIT_TERMINAL_PROMPT": "0",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_OPTIONAL_LOCKS": "0"}.items()) and environment.get("PATH") == os.defpath and
        environment.get("GIT_CONFIG_GLOBAL") == os.devnull and
        (owner_value["nativeRole"] != "windows-x64" or bool(environment.get("SYSTEMROOT"))), "QUERY_ORIGINAL_ENVIRONMENT")
    baseline = O.parse(blobs["baseline.json"])
    require(set(baseline) == {"nativeRole", "baseline", "kernelJob"} and
        blobs["baseline.json"] == Q.encoded(baseline) and baseline["nativeRole"] == owner_value["nativeRole"],
        "QUERY_ORIGINAL_BASELINE")
    # Pure schema translation only. All digests remain of original query bytes.
    native.baseline_record(O.encoded({"role": baseline["nativeRole"], "baseline": baseline["baseline"],
        "kernelJob": baseline["kernelJob"]}), owner_value["nativeRole"])
    ownership = row["ownership"]
    require(type(ownership) is dict and type(ownership.get("launches")) is list and len(ownership["launches"]) == 1 and
        type(ownership["launches"][0]) is dict and type(ownership["launches"][0].get("pid")) is int and
        type(ownership.get("startedIdentities")) is list, "QUERY_ORIGINAL_NATIVE_LAUNCH")
    leaders = [item for item in ownership["startedIdentities"] if type(item) is dict and
        type(item.get("pid")) is int and item["pid"] == ownership["launches"][0]["pid"]]
    require(len(leaders) == 1, "QUERY_ORIGINAL_NATIVE_LEADER")
    native.native_record(ownership, {"role": owner_value["nativeRole"], "job": row["job"],
        "invocation": row["id"], "cwd": row["cwd"]}, leaders[0], argv)
    if baseline["baseline"] is not None:
        leader = native.lifetime(leaders[0], owner_value["nativeRole"])
        require(list(leader[:4] if owner_value["nativeRole"].startswith("macos-") else leader) not in baseline["baseline"],
            "QUERY_ORIGINAL_NATIVE_PREEXISTING_LEADER")
    require(type(row["outputs"]) is dict and set(row["outputs"]) == {"stdout", "stderr"}, "QUERY_ORIGINAL_CAPTURES")
    for name in ("stdout", "stderr"):
        capture = row["outputs"][name]
        raw = blobs[name + ".log"]
        require(type(capture) is dict and type(capture.get("bytes")) is int and
            capture["bytes"] == len(raw) <= row[name + "Limit"] and capture.get("sha256") == O.digest(raw) and
            type(capture.get("size")) is int and capture["size"] == len(raw), "QUERY_ORIGINAL_CAPTURE_BYTES")
        if owner_value["nativeRole"] == "windows-x64":
            require(set(capture) == {"identity", "is_directory", "size", "links", "attributes", "creation_100ns",
                "modified_100ns", "change_100ns", "owner_sid", "protected_dacl", "bytes", "sha256"} and
                capture["is_directory"] is False and type(capture["links"]) is int and capture["links"] == 1 and
                capture["protected_dacl"] is True and type(capture["owner_sid"]) is str and
                re.fullmatch(r"S-1-[0-9]+(?:-[0-9]+){1,15}", capture["owner_sid"]), "QUERY_ORIGINAL_CAPTURE_METADATA")
            native.directory_identity(capture["identity"], "windows-x64")
            for field in ("attributes", "creation_100ns", "modified_100ns", "change_100ns"):
                O.integer(capture[field])
            require(not capture["attributes"] & (native.windows.DIRECTORY | native.windows.REPARSE_POINT),
                "QUERY_ORIGINAL_CAPTURE_METADATA")
        else:
            require(set(capture) == {"device", "inode", "size", "mtime_ns", "ctime_ns", "bytes", "sha256"},
                "QUERY_ORIGINAL_CAPTURE_METADATA")
            for field in ("device", "inode", "mtime_ns", "ctime_ns"):
                O.integer(capture[field], 1 if field == "inode" else 0)
    require(blobs["stderr.log"] == b"", "QUERY_ORIGINAL_STDERR")


def _initial_query_commands(queries, captures, originals):
    """Fixed historical command graph, not a GitView/replay runner or source admission."""
    source = I.sha(captures[queries[2]["id"]]["stdout.log"].decode("ascii").strip())
    tree = I.sha(captures[queries[3]["id"]]["stdout.log"].decode("ascii").strip())
    entry = originals["candidate_policy_entry"]
    match = re.fullmatch(rb"100644 blob ([0-9a-f]{40})\t" + re.escape(I.POLICY_PATH.encode("ascii")) + rb"\x00", entry)
    require(match is not None, "QUERY_ORIGINAL_POLICY_ENTRY")
    blob = match.group(1).decode("ascii")
    policy = originals["candidate_policy_raw"]
    require(0 < len(policy) <= I.POLICY_LIMIT and native.hashlib.sha1(b"blob " + str(len(policy)).encode("ascii") +
        b"\0" + policy).hexdigest() == blob and originals["base_policy_entry"] == b"" and
        originals["ancestry_raw"] in (acquisition.stages.BASE["commit"].encode("ascii") + b"\n",
            acquisition.stages.BASE["commit"].encode("ascii") + b"\r\n"), "QUERY_ORIGINAL_POLICY_BYTES")
    commands = (("rev-parse", "--show-toplevel"), ("status", "--porcelain=v1", "--untracked-files=all"),
        ("rev-parse", "--verify", "HEAD^{commit}"), ("rev-parse", "--verify", source + "^{tree}"),
        ("rev-parse", "--is-shallow-repository"), ("rev-parse", "--verify", "refs/remotes/origin/main^{commit}"),
        ("rev-parse", "--verify", acquisition.stages.BASE["commit"] + "^{tree}"),
        ("ls-tree", "-z", acquisition.stages.BASE["commit"], "--", I.POLICY_PATH),
        ("merge-base", acquisition.stages.BASE["commit"], source), ("ls-tree", "-z", source, "--", I.POLICY_PATH),
        ("cat-file", "-s", blob), ("cat-file", "blob", blob))
    for index, row in enumerate(queries):
        position = index % 12
        raw = captures[row["id"]]["stdout.log"]
        limit = I.EVENT_LIMIT if position == 1 else I.POLICY_LIMIT if position == 11 else 4096
        require(tuple(row["argv"][7:]) == commands[position] and row["stdoutLimit"] == limit,
            "QUERY_ORIGINAL_FIXED_SEQUENCE")
        if position == 0:
            require(Path(os.fsdecode(raw.rstrip(b"\r\n"))) == ROOT, "QUERY_ORIGINAL_SOURCE_ROOT")
        elif position in (2, 3, 5, 6):
            expected = {2: source, 3: tree, 5: acquisition.stages.BASE["commit"], 6: acquisition.stages.BASE["tree"]}[position]
            require(I.sha(raw.decode("ascii").strip()) == expected, "QUERY_ORIGINAL_SOURCE_IDENTITY")
        elif position == 4:
            require(raw in (b"false\n", b"false\r\n"), "QUERY_ORIGINAL_FULL_HISTORY")
        elif position == 10:
            require(re.fullmatch(rb"[1-9][0-9]{0,5}\r?\n", raw) and int(raw) == len(policy), "QUERY_ORIGINAL_POLICY_SIZE")
        else:
            expected = {1: b"", 7: originals["base_policy_entry"], 8: originals["ancestry_raw"],
                9: entry, 11: policy}[position]
            require(raw == expected, "QUERY_ORIGINAL_SOURCE_BYTES")


def _check_reader_path_history(nodes):
    """Same saved nodes/predicates; avoid success-only exception-message work.

    Reader pins contain Paths. Preserve the generic check for every other node
    kind, rather than dropping or recategorizing any saved history. The shared
    historical-object checker and its other callers are unchanged.
    """
    for value, kind, mode, saved in nodes:
        if mode == "path":
            if type(value) is not kind:
                require(False, "RECIPIENT_HISTORY_CHANGED")
            if (str(value), value.parts, value.drive, value.root) != saved:
                require(False, "RECIPIENT_HISTORY_CHANGED")
        else:
            _check_history(((value, kind, mode, saved),))


def _read_initial_query_originals(owner, directory, *, expected_session_sha256, expected_source_return_raw=None):
    """SUPPLIED_QUERY_BYTE_GRAPH_ONLY; enclosing OWNER_CLOSE_PENDING.

    Read one of twelve fixed Stage1 roots. The caller separately authenticates
    the session hash and (source roots only) sidecar. No historical authority,
    native acceptance, current source check or original-return object is made.
    All newly opened directories remain borrowed-owner resources for its later
    actual close; no new clock/owner/token, write, command or registry is created.
    """
    require(type(expected_session_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", expected_session_sha256),
        "QUERY_ORIGINAL_EXPECTED_HASH")
    require(type(owner) is native.Owner and owner.first is not None and owner.fence is not None and
        type(owner.resources) is list and type(owner.errors) is list, "QUERY_ORIGINAL_OWNER")
    first, fence, ledger, errors = owner.first, owner.fence, owner.resources, owner.errors
    cancelled, local_end, limits = owner.cancelled, owner.local_end, (owner.work_limit, owner.final_limit)
    O.clocks.validate_reading(first)
    first_ns, clock_raw, role = first.nanoseconds, O.encoded(O.clock_value(first.clock)), first.clock.role
    require(callable(cancelled) and type(local_end) is float and math.isfinite(local_end), "QUERY_ORIGINAL_OWNER")
    require(all(type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
        type(row["label"]) is str and row["label"] in ("directory", "writer", "stdout", "stderr", "native-scope") and
        type(row["attempted"]) is bool and type(row["closed"]) is bool and (not row["closed"] or row["attempted"])
        for row in ledger), "QUERY_ORIGINAL_RESOURCE_ROSTER")
    prefix = tuple((row, row["label"], row["owner"], row["attempted"], row["closed"]) for row in ledger)
    require(len({id(row) for row, *_rest in prefix}) == len(prefix) ==
        len({id(resource) for _row, _label, resource, _a, _c in prefix}), "QUERY_ORIGINAL_RESOURCE_ALIAS")
    methods = tuple((name, getattr(owner, name)) for name in ("end", "read", "acquire"))
    held, new_rows, pins, path_nodes, records = [], [], [], [], []
    missing = object()

    def roster():
        return owner.resources is ledger and len(ledger) == len(prefix) + len(held) and all(
            row is saved and type(row) is dict and len(row) == 4 and
            type(row.get("label")) is str and row.get("label") == label and row.get("owner", missing) is resource and
            row.get("attempted") is attempted and row.get("closed") is closed
            for row, (saved, label, resource, attempted, closed) in zip(ledger, prefix)) and all(
            type(row) is dict and len(row) == 4 and
            row.get("label") == "directory" and row.get("owner", missing) is resource and
            row.get("attempted") is False and row.get("closed") is False
            for row, resource in zip(ledger[len(prefix):], held)) and all(
            row is saved for row, saved in zip(ledger[len(prefix):], new_rows))

    def data():
        require(type(owner) is native.Owner and owner.first is first and owner.fence is fence and
            owner.resources is ledger and owner.errors is errors and owner.cancelled is cancelled and
            type(owner.local_end) is float and owner.local_end == local_end and
            all(type(a) is type(b) and a == b for a, b in zip((owner.work_limit, owner.final_limit), limits)) and
            type(first.nanoseconds) is int and first.nanoseconds == first_ns and
            O.encoded(O.clock_value(first.clock)) == clock_raw == O.encoded(O.clock_value(fence.clock)) and
            all(getattr(owner, name) == method for name, method in methods), "QUERY_ORIGINAL_OWNER_CHANGED")
        require(roster(), "QUERY_ORIGINAL_ROSTER_CHANGED")
        require(owner.closed is False and owner.unknown is False and owner.original is None and errors == [] and
            not native.QUARANTINE and not Q.QUARANTINE and not native.diagnostics._QUARANTINE, "QUERY_ORIGINAL_OWNER_NOT_LIVE")
        # Preserve every original node/check, including repeated paths, without
        # recreating one helper frame per directory at each callback boundary.
        _check_reader_path_history(path_nodes)
        for child, path, identity, original_path in pins:
            if not (child.path is original_path and child.path == path):
                require(False, "QUERY_ORIGINAL_DIRECTORY_CHANGED")
            current = tuple(child.identity)
            # Exact equality to the initially validated scalar types/values also
            # reestablishes their ranges/format; bool/int aliases remain invalid.
            if not (len(current) == 2 and type(current[0]) is int and type(current[1]) is type(identity[1]) and current == identity and
                    (child._closed if role == "windows-x64" else child.closed) is False):
                require(False, "QUERY_ORIGINAL_DIRECTORY_CHANGED")

    def checked():
        data()
        cancelled()
        data()
        owner.end()
        data()
        cancelled()
        data()
        owner.end()  # The last cancellation callback spends the same original interval.
        data()

    def call(function, *args):
        checked()
        result = function(*args)
        checked()
        return result

    def pin(child, path):
        require(type(child) is (native.windows.PrivateDirectory if role == "windows-x64" else Q._PosixDirectory) and
            child.path == path and not any(child is saved or child.path == saved_path
                for saved, saved_path, _identity, _original_path in pins),
            "QUERY_ORIGINAL_DIRECTORY_TYPE")
        pins.append((child, path, tuple(native.directory_identity(list(child.identity), role)), child.path))
        path_nodes.extend(_history_graph(child.path, path))

    def owned(child):
        saved = next(row for row in pins if row[0] is child)
        call(native._new_entry_owned, owner, child, saved[1], saved[2])

    def names(child, expected):
        owned(child)
        end = call(owner.end)
        observed = []
        if role == "windows-x64":
            observed = child.names(max_names=max(1, len(expected)), deadline=end)
        else:
            with os.scandir(child.path) as entries:
                for entry in entries:
                    checked()
                    require(len(observed) < max(1, len(expected)), "QUERY_ORIGINAL_DIRECTORY_LIMIT")
                    observed.append(entry.name)
        checked()
        require(all(type(name) is str for name in observed) and len(observed) == len(set(name.casefold() for name in observed)) and
            tuple(sorted(observed)) == tuple(sorted(expected)), "QUERY_ORIGINAL_DIRECTORY_ROSTER")
        owned(child)

    def child(name):
        owned(directory)
        Q._component(name)
        target = directory.path / name
        target_graph = _history_graph(target)
        end = call(owner.end)

        def acquire():
            raw = (directory.open_directory(name, deadline=end) if role == "windows-x64" else
                Q._PosixDirectory(target))
            held.append(raw)  # Before pins or Owner.acquire's fallible postallocation callbacks.
            _check_history(target_graph)
            pin(raw, target)
            return raw

        checked()
        saved_end, dictionary = owner.end, owner.__dict__
        had_end, end_slot = "end" in dictionary, dictionary.get("end")

        def allocation_end(*, final=False):
            require(owner.__dict__ is dictionary and owner.end is allocation_end, "QUERY_ORIGINAL_END_CHANGED")
            if len(new_rows) < len(held):
                require(len(new_rows) + 1 == len(held) and len(ledger) == len(prefix) + len(held),
                    "QUERY_ORIGINAL_ROSTER_CHANGED")
                # Owner.acquire has just appended this actual row. Pin it BEFORE
                # forwarding the first postallocation deadline/cancellation call.
                new_rows.append(ledger[-1])
            require(roster(), "QUERY_ORIGINAL_ROSTER_CHANGED")
            result = saved_end(final=final)
            require(owner.__dict__ is dictionary and owner.end is allocation_end, "QUERY_ORIGINAL_END_CHANGED")
            require(roster(), "QUERY_ORIGINAL_ROSTER_CHANGED")
            return result

        owner.end = allocation_end
        try:
            result = owner.acquire("directory", acquire)
            require(owner.__dict__ is dictionary and owner.end is allocation_end, "QUERY_ORIGINAL_END_CHANGED")
        finally:
            # Restore only our exact temporary slot, never a callback's changed
            # owner/method or ledger. Preserve an original thrown failure.
            if owner.__dict__ is dictionary and owner.end is allocation_end:
                if had_end:
                    owner.end = end_slot
                else:
                    del owner.end
            else:
                owner.unknown = True
        require(len(new_rows) == len(held), "QUERY_ORIGINAL_ROSTER_CHANGED")
        checked()
        owned(result)
        return result

    def read(parent, name, maximum, expected_hash, expected_bytes):
        owned(parent)
        raw = call(owner.read, parent, name, maximum)
        require(type(raw) is bytes and len(raw) == expected_bytes and O.digest(raw) == expected_hash,
            "QUERY_ORIGINAL_BYTES_CHANGED")
        checked()
        records.append((parent, name, maximum, raw))
        return raw

    try:
        recipient = call(_recipient_path)
        preparation = recipient.with_name(recipient.name.removesuffix("-recipient"))
        paths = {parent / name: name == "acquisition-queries" for parent in
            (preparation, preparation.with_name(preparation.name + "-entry"), recipient / "authority")
            for name in ("source-before", "acquisition-queries", "source-after")}
        paths.update({recipient / "recipient-validation" / name: False for name in ("source-before", "source-after")})
        paths[recipient / "source-final"] = False
        require(directory is not None and directory.path in paths, "QUERY_ORIGINAL_LAYOUT")
        acquisition_root = paths[directory.path]
        require(expected_source_return_raw is None if acquisition_root else type(expected_source_return_raw) is bytes and
            0 < len(expected_source_return_raw) <= native.LIMIT, "QUERY_ORIGINAL_SIDECAR_INPUT")
        pin(directory, directory.path)
        owned(directory)
        raw = call(owner.read, directory, "session-result.json")
        require(type(raw) is bytes and 0 < len(raw) <= Q.MAX_RECEIPT_BYTES and O.digest(raw) == expected_session_sha256,
            "QUERY_ORIGINAL_SESSION_HASH")
        session = O.parse(raw)
        require(set(session) == {"schema", "scope", "job", "queries", "result", "retirement", "firstError", "errors", "readbacks"} and
            raw == Q.encoded(session) and type(session["schema"]) is int and session["schema"] == 1 and
            session["scope"] == "ORDINARY_GIT_QUERIES_ONLY" and type(session["job"]) is str and
            re.fullmatch(r"[0-9a-f]{32}", session["job"]) and session["result"] == "READY_FOR_CALLER_SEAL" and
            session["retirement"] == "KNOWN" and session["firstError"] is None and session["errors"] == [] and
            type(session["queries"]) is list and len(session["queries"]) == (24 if acquisition_root else 12) and
            type(session["readbacks"]) is list, "QUERY_ORIGINAL_SESSION")
        queries, readbacks = session["queries"], session["readbacks"]
        require(all(type(row) is dict and type(row.get("id")) is str and re.fullmatch(r"[0-9a-f]{32}", row["id"])
            for row in queries) and len({row["id"] for row in queries}) == len(queries), "QUERY_ORIGINAL_IDS")
        keys = ORIGINAL_KEYS if acquisition_root else SOURCE_KEYS
        root_names = ("owner.json", "session-result.json", "query-home", *(name + ".bin" for name in keys),
            *("query-" + row["id"] for row in queries), *(("source-return.json",) if not acquisition_root else ()))
        names(directory, root_names)
        query_names = ("start.json", "baseline.json", "stdout.log", "stderr.log", "result.json")
        expected = [(directory.path, "owner.json")]
        if acquisition_root:
            expected.append((directory.path, "event.bin"))
        for index, row in enumerate(queries):
            expected.extend((directory.path / ("query-" + row["id"]), name) for name in query_names)
            if acquisition_root and index == 11:
                expected.extend((directory.path, name + ".bin") for name in (*SOURCE_KEYS, *HTTP_KEYS))
        expected.extend((directory.path, name + ".bin") for name in (("observation", "match") if acquisition_root else SOURCE_KEYS))
        require(len(readbacks) == len(expected), "QUERY_ORIGINAL_READBACK_ROSTER")
        total = len(raw)
        for row, (parent, name) in zip(readbacks, expected):
            require(type(row) is dict and set(row) == {"parent", "name", "maximum", "retirement", "result", "bytes", "sha256"} and
                row["parent"] == str(parent) and row["name"] == name and row["retirement"] == "KNOWN" and
                row["result"] == "RETAINED" and type(row["maximum"]) is int and type(row["bytes"]) is int and
                0 <= row["bytes"] <= row["maximum"] <= Q.MAX_RECEIPT_BYTES and row["maximum"] > 0 and
                type(row["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]), "QUERY_ORIGINAL_READBACK")
            if name.endswith(".log"):
                query = next(item for item in queries if parent.name == "query-" + item["id"])
                require(type(query.get(name[:-4] + "Limit")) is int and row["maximum"] == query[name[:-4] + "Limit"],
                    "QUERY_ORIGINAL_CAPTURE_LIMIT")
            else:
                require(row["maximum"] == max(1, row["bytes"]), "QUERY_ORIGINAL_RECEIPT_LIMIT")
            total += row["bytes"]
            require(total <= Q.MAX_SESSION_BYTES, "QUERY_ORIGINAL_SESSION_LIMIT")
        checked()  # Refuse declared cumulative excess before opening any children or large readbacks.
        directories = {directory.path: directory}
        home = child("query-home")
        names(home, ())
        for row in queries:
            opened = child("query-" + row["id"])
            directories[opened.path] = opened
            names(opened, query_names)
        blobs = {}
        for row, (parent, name) in zip(readbacks, expected):
            blobs[(parent, name)] = read(directories[parent], name, row["maximum"], row["sha256"], row["bytes"])
        owner_raw = blobs[(directory.path, "owner.json")]
        value = O.parse(owner_raw)
        require(set(value) == {"schema", "scope", "job", "state", "home", "root", "nativeRole", "git", "ancestorContext"} and
            owner_raw == Q.encoded(value) and type(value["schema"]) is int and value["schema"] == 1 and
            value["scope"] == "ORDINARY_GIT_QUERIES_ONLY" and value["job"] == session["job"] and
            value["state"] == str(directory.path) and value["home"] == str(home.path) and value["root"] == str(ROOT) and
            value["nativeRole"] == role and type(value["git"]) is str and 0 < len(value["git"]) <= 8192 and
            "\0" not in value["git"] and Path(value["git"]).is_absolute() and ".." not in Path(value["git"]).parts and
            type(value["ancestorContext"]) is dict and all(type(item) is str for item in value["ancestorContext"].values()) and
            (set(value["ancestorContext"]).issubset({"GRADLE_USER_HOME"}) or set(value["ancestorContext"]) == set(Q._CONTEXT)),
            "QUERY_ORIGINAL_OWNER_RECORD")
        captures = {}
        for row in queries:
            contents = {name: blobs[(directory.path / ("query-" + row["id"]), name)] for name in query_names}
            _initial_query_record(row, contents, value)
            captures[row["id"]] = contents
            checked()
        originals = {name: blobs[(directory.path, name + ".bin")] for name in keys}
        _initial_query_commands(queries, captures, originals)
        checked()
        if not acquisition_root:
            sidecar = read(directory, "source-return.json", len(expected_source_return_raw),
                O.digest(expected_source_return_raw), len(expected_source_return_raw))
            require(sidecar == expected_source_return_raw, "QUERY_ORIGINAL_SIDECAR_BYTES")
            side = O.parse(sidecar)
            require(set(side) == {"schema", "scope", "originalsSha256", "sessionSha256", "clock", "returnedNs"} and
                sidecar == O.encoded(side) and type(side["schema"]) is int and side["schema"] == 1 and
                side["scope"] == SOURCE_SCOPE and side["sessionSha256"] == expected_session_sha256 and
                side["originalsSha256"] == {name: O.digest(originals[name]) for name in SOURCE_KEYS} and
                O.encoded(side["clock"]) == clock_raw, "QUERY_ORIGINAL_SIDECAR")
            O.integer(side["returnedNs"])
        names(home, ())
        for opened in directories.values():
            names(opened, root_names if opened is directory else query_names)
        for parent, name, maximum, original in records:
            owned(parent)
            require(call(owner.read, parent, name, maximum) == original, "QUERY_ORIGINAL_REREAD_CHANGED")
        require(call(owner.read, directory, "session-result.json") == raw, "QUERY_ORIGINAL_SESSION_CHANGED")
        names(home, ())
        for opened in directories.values():
            names(opened, root_names if opened is directory else query_names)
        checked()
        return raw, tuple((str(parent.relative_to(directory.path) / name), blobs[(parent, name)]) for parent, name in expected), \
            expected_source_return_raw
    except BaseException as error:
        original = owner.original if owner.original is not None else error
        try:
            owner.error("initial-query-originals", error, unknown=not roster())
        except BaseException:
            owner.unknown = True
        if owner.unknown:
            # Retention only, not a capability registry or a restored/forged ledger.
            native.QUARANTINE.append((owner, prefix, tuple(held), tuple(pins)))
        raise original


def _initial_graph_json(raw, fields=None, scope=None):
    """Canonical supplied bytes only; no original-return or live authority lookup."""
    value = O.parse(raw)
    require(type(raw) is bytes and type(value) is dict and raw == O.encoded(value) and
        (fields is None or set(value) == fields) and (scope is None or
        type(value.get("schema")) is int and value["schema"] == 1 and value.get("scope") == scope),
        "GRAPH_RECORD")
    return value


def _initial_graph_native(context_raw, path, clock, first, work, final, records, child_raw, kind):
    """The four fixed historical native phases; no phase/fence/return is reconstructed."""
    require(kind in ("P", "E", "A", "R") and set(records) == native.PHASE_FILES, "GRAPH_NATIVE_KIND")
    recipient = kind == "R"
    context = _initial_graph_json(context_raw)
    start = _initial_graph_json(records["start.json"], native.START_FIELDS,
        RECIPIENT_START_SCOPE if recipient else native.PHASE_SCOPE)
    command = (_recipient_command(O.digest(context_raw)) if recipient else native.phase_command(context_raw))
    require(start["contextSha256"] == O.digest(context_raw) and start["argv"] == command and
        start["cwd"] == str(ROOT) and start["role"] == clock.role and start["job"] == context["job"] and
        start["state"] == str(path) and start["home"] == str(path / "control-home") and
        type(start["invocation"]) is str and re.fullmatch(r"[0-9a-f]{32}", start["invocation"]) and
        start["exitCode"] is None and start["launchAttempted"] is False and start["scopeAttempted"] is False and
        start["retirement"] == "UNKNOWN", "GRAPH_NATIVE_START")
    began = O.integer(start["startedNs"], first if recipient else O.integer(context["sourceReturnedNs"], first))
    ends = (work, final) if recipient else (min(work, began + 45 * O.NS), min(final, min(work, began + 45 * O.NS) + 45 * O.NS))
    require(began < work and all(type(start[name]) is int and start[name] == end for name, end in
        zip(("workEndNs", "finalEndNs"), ends)), "GRAPH_NATIVE_FENCES")
    inherited = native.processes.ownership_environment(context["inheritedContext"], context["job"], start["invocation"],
        str(path), str(path / "control-home"), allow_new_context=True)
    require(start["inheritedContext"] == {name: inherited[name] for name in Q._CONTEXT}, "GRAPH_NATIVE_ANCESTORS")
    extra = {"finalStartedNs", "readStartedNs", "readEndNs", "readbackCompletedNs"} if recipient else set()
    row = _initial_graph_json(records["result.json"], native.TERMINAL_FIELDS | extra, start["scope"])
    birth = _initial_graph_json(records["native-start.json"], {"ownership", "leader", "preparerIdentity", "observedNs"})
    _initial_graph_json(records["baseline.json"], {"role", "baseline", "kernelJob"})
    baseline = native.baseline_record(records["baseline.json"], clock.role)
    replaced = {"exitCode", "launchAttempted", "scopeAttempted", "retirement"} | ({"finalEndNs"} if recipient else set())
    require(all(O.encoded(row[name]) == O.encoded(start[name]) for name in set(start) - replaced) and
        type(row["exitCode"]) is int and row["exitCode"] == 0 and row["launchAttempted"] is True and
        row["scopeAttempted"] is True and row["scopeCloseAttempted"] is True and row["scopeClosed"] is True and
        row["retirement"] == "KNOWN" and row["errors"] == [] and row["survivors"] == [] and
        records["stderr.log"] == b"" and len(records["stdout.log"]) <= native.ACK_LIMIT and
        row["baselineSha256"] == O.digest(records["baseline.json"]) and
        row["nativeStartSha256"] == O.digest(records["native-start.json"]) and
        O.encoded(row["leader"]) == O.encoded(birth["leader"]),
        "GRAPH_NATIVE_RETIREMENT")
    preparer = native.closed_lifetime(row["preparerIdentity"], clock.role)
    require(preparer == native.closed_lifetime(birth["preparerIdentity"], clock.role) and
        preparer["pid"] != row["leader"]["pid"], "GRAPH_NATIVE_PREPARER")
    minimum = O.integer(row["launchMinimumNs"], began)
    argv = (_recipient_command(O.digest(context_raw), minimum) if recipient else native.phase_command(context_raw, minimum))
    require(row["launchArgv"] == argv, "GRAPH_NATIVE_COMMAND")
    native.native_record(row["ownership"], start, row["leader"], argv)
    native.native_record(birth["ownership"], start, row["leader"], argv, terminal=False)
    require(O.encoded(birth["ownership"]["launches"]) == O.encoded(row["ownership"]["launches"]), "GRAPH_NATIVE_BIRTH")
    if baseline["baseline"] is not None:
        leader = native.lifetime(row["leader"], clock.role)
        require(list(leader[:4] if clock.role.startswith("macos-") else leader) not in baseline["baseline"],
            "GRAPH_NATIVE_PREEXISTING_LEADER")
    outcomes = {name: {key: True for key in ("synced", "verified", "closeAttempted", "closed", "readback")}
        for name in ("stdout", "stderr")}
    captures = {name: {"bytes": len(records[name + ".log"]), "sha256": O.digest(records[name + ".log"])}
        for name in ("stdout", "stderr")}
    require(O.encoded(row["captureOutcomes"]) == O.encoded(outcomes) and
        O.encoded(row["captures"]) == O.encoded(captures), "GRAPH_NATIVE_CAPTURES")
    ack_scope = {"P": native.INITIAL_ACK_SCOPE, "E": native.INITIAL_ENTRY_ACK_SCOPE,
        "A": native.INITIAL_AUTHORITY_ACK_SCOPE, "R": native.INITIAL_RECIPIENT_ACK_SCOPE}[kind]
    ack = _initial_graph_json(records["stdout.log"], {"schema", "scope", "invocation", "terminalSha256", "clock", "closedNs"}, ack_scope)
    require(ack["invocation"] == start["invocation"] and ack["terminalSha256"] == O.digest(child_raw) and
        O.encoded(ack["clock"]) == O.encoded(O.clock_value(clock)), "GRAPH_NATIVE_ACK")
    common = {"schema", "scope", "contextSha256", "startSha256", "clock", "invocation", "launchMinimumNs",
        "beganNs", "metadataLastNs", "completedNs"}
    fields = ({"identitySha256", "authoritySha256", "recipient", "sourceBeforeSha256", "sourceAfterSha256",
        "supplierReturnedNs", "supplierReturned", "childResourceClose", "parentRetirement", "budgetAcceptance",
        "testAcceptance", "exportSaveAuthority"} if recipient else {"acquiredNs", "queryReturnedNs",
        "querySessionSha256", "originalsSha256", "matchSha256", "retirement", "errors"})
    child = _initial_graph_json(child_raw, common | fields,
        {"P": CHILD_SCOPE, "E": ENTRY_CHILD_SCOPE, "A": AUTHORITY_CHILD_SCOPE, "R": RECIPIENT_CHILD_SCOPE}[kind])
    require(child["contextSha256"] == O.digest(context_raw) and child["startSha256"] == O.digest(records["start.json"]) and
        O.encoded(child["clock"]) == O.encoded(O.clock_value(clock)) and child["invocation"] == start["invocation"] and
        type(child["launchMinimumNs"]) is int and child["launchMinimumNs"] == minimum,
        "GRAPH_NATIVE_CHILD")
    if recipient:
        require(child["supplierReturned"] is True and child["childResourceClose"] == "PENDING_CLOSE" and
            child["parentRetirement"] == "NOT_OBSERVED_HERE" and child["budgetAcceptance"] == "NOT_ADMITTED" and
            child["testAcceptance"] == "NOT_PERFORMED" and child["exportSaveAuthority"] is False, "GRAPH_RECIPIENT_CHILD")
    else:
        require(child["retirement"] == "KNOWN" and child["errors"] == [], "GRAPH_SERVICE_CHILD")
    return start, row, birth, child, ack


def _read_initial_recipient_originals(owner, directory, *, recipient_outcome, expected_sha256):
    """SUPPLIED_STAGE1_PUBLISHED_GRAPH_CONSISTENCY_ONLY / OWNER_CLOSE_PENDING.

    Read the fixed P/E/R/A graph rooted in the three-file sender S. Return only
    immutable (relative-name, original-bytes) tuples; A is R/authority. Supplied
    step outcome/hash are NOT authenticated here. Original firstUseAt is solely
    FIRST_USE_DATA_CONSISTENCY_ONLY, not final/current currency or authority.
    Crypto internals are unbound and NOT read. No new Owner, deadline, token,
    registry, live historical object, native supplier or initializer is created.
    The same borrowed interval includes all checks. Success still awaits its
    enclosing owner's actual close and the future genuine receiving authority.
    """
    require(type(owner) is native.Owner and owner.first is not None and owner.fence is not None and
        type(owner.resources) is list and type(owner.errors) is list, "GRAPH_OWNER")
    first, fence, ledger, errors = owner.first, owner.fence, owner.resources, owner.errors
    cancelled, local_end, limits = owner.cancelled, owner.local_end, (owner.work_limit, owner.final_limit)
    O.clocks.validate_reading(first)
    first_ns, clock_raw, role = first.nanoseconds, O.encoded(O.clock_value(first.clock)), first.clock.role
    require(callable(cancelled) and type(local_end) is float and math.isfinite(local_end), "GRAPH_OWNER")
    require(all(type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
        row["label"] in ("directory", "writer", "stdout", "stderr", "native-scope") and
        type(row["attempted"]) is bool and type(row["closed"]) is bool and (not row["closed"] or row["attempted"])
        for row in ledger), "GRAPH_OWNER_ROSTER")
    rows = [(row, row["label"], row["owner"], row["attempted"], row["closed"]) for row in ledger]
    require(len({id(row) for row, *_ in rows}) == len(rows) == len({id(resource) for _, _, resource, _, _ in rows}),
        "GRAPH_RESOURCE_ALIAS")
    prefix_count = len(rows)
    methods = tuple((name, getattr(owner, name)) for name in ("end", "read", "acquire"))
    sender_reader, query_reader = _read_recipient_sender, _read_initial_query_originals
    held, pins, path_nodes, rosters, originals = [], [], [], [], {}
    missing = object()
    prefix_paths = tuple((resource, resource.path, _history_graph(resource.path)) for _, label, resource, _, _ in rows
        if label == "directory")
    used, leaf_failed = 0, False

    def roster(*, tail=False):
        return owner.resources is ledger and (len(ledger) >= len(rows) if tail else len(ledger) == len(rows)) and all(
            actual is saved and type(actual) is dict and len(actual) == 4 and actual.get("label", missing) is not missing and
            actual.get("label") == label and actual.get("owner", missing) is resource and
            actual.get("attempted") is attempted and actual.get("closed") is closed
            for actual, (saved, label, resource, attempted, closed) in zip(ledger, rows))

    def structural(*, tail=False):
        require(type(owner) is native.Owner and owner.first is first and owner.fence is fence and owner.errors is errors and
            owner.cancelled is cancelled and type(owner.local_end) is float and owner.local_end == local_end and
            all(type(a) is type(b) and a == b for a, b in zip((owner.work_limit, owner.final_limit), limits)) and
            type(first.nanoseconds) is int and first.nanoseconds == first_ns and
            O.encoded(O.clock_value(first.clock)) == clock_raw == O.encoded(O.clock_value(fence.clock)) and
            all(getattr(owner, name) == method for name, method in methods) and
            _read_recipient_sender is sender_reader and _read_initial_query_originals is query_reader, "GRAPH_OWNER_CHANGED")
        require(roster(tail=tail), "GRAPH_ROSTER_CHANGED")
        for resource, path, graph in prefix_paths:
            if resource.path is not path:
                require(False, "GRAPH_PREFIX_PATH_CHANGED")
            _check_reader_path_history(graph)
        # Same saved nodes, order and duplicates; avoid one helper setup per pin.
        _check_reader_path_history(path_nodes)
        for resource, path, identity, original_path in pins:
            if not (resource.path is original_path and resource.path == path):
                require(False, "GRAPH_DIRECTORY_CHANGED")
            current = tuple(resource.identity)
            # Pin-time validation established the scalar ranges/format. Exact
            # types and values imply those same predicates at every boundary.
            if not (len(current) == 2 and type(current[0]) is int and type(current[1]) is type(identity[1]) and current == identity and
                    (resource._closed if role == "windows-x64" else resource.closed) is False):
                require(False, "GRAPH_DIRECTORY_CHANGED")

    def data():
        structural()
        require(owner.closed is False and owner.unknown is False and owner.original is None and errors == [] and
            not native.QUARANTINE and not Q.QUARANTINE and not native.diagnostics._QUARANTINE, "GRAPH_OWNER_NOT_LIVE")

    def checked():
        data()
        cancelled()
        data()
        owner.end()
        data()
        cancelled()
        data()
        owner.end()
        data()

    def call(function, *args):
        checked()
        value = function(*args)
        checked()
        return value

    def same(value, expected):
        require(O.encoded(value) == O.encoded(expected), "GRAPH_BINDING")

    def pin(resource, path):
        require(type(resource) is (native.windows.PrivateDirectory if role == "windows-x64" else Q._PosixDirectory) and
            resource.path == path and not any(resource is old or path == old_path for old, old_path, _, _ in pins),
            "GRAPH_DIRECTORY_TYPE")
        pins.append((resource, path, tuple(native.directory_identity(list(resource.identity), role)), resource.path))
        path_nodes.extend(_history_graph(path, resource.path))

    def owned(resource):
        _, path, identity, _ = next(row for row in pins if row[0] is resource)
        call(native._new_entry_owned, owner, resource, path, identity)

    def names(resource, expected):
        owned(resource)
        end = call(owner.end)
        found = []
        if role == "windows-x64":
            found = resource.names(max_names=max(1, len(expected)), deadline=end)
        else:
            with os.scandir(resource.path) as entries:
                for entry in entries:
                    checked()
                    require(len(found) < max(1, len(expected)), "GRAPH_DIRECTORY_LIMIT")
                    found.append(entry.name)
        checked()
        require(all(type(name) is str for name in found) and len(found) == len({name.casefold() for name in found}) and
            tuple(sorted(found)) == tuple(sorted(expected)), "GRAPH_DIRECTORY_ROSTER")
        owned(resource)

    def opened(path, parent=None):
        if parent is not None:
            owned(parent)
            require(path.parent == parent.path, "GRAPH_CHILD_PATH")
            Q._component(path.name)
        target_graph = _history_graph(path)
        end = call(owner.end)
        pending = []

        def factory():
            resource = (native.windows.open_private_directory(path) if parent is None else
                parent.open_directory(path.name, deadline=end)) if role == "windows-x64" else Q._PosixDirectory(path)
            held.append(resource)  # Raw return custody before ANY fallible pin/callback.
            pending.append(resource)
            _check_history(target_graph)
            pin(resource, path)
            return resource

        checked()
        saved_end, dictionary = owner.end, owner.__dict__
        had_end, end_slot = "end" in dictionary, dictionary.get("end")
        before = len(rows)

        def allocation_end(*, final=False):
            require(owner.__dict__ is dictionary and owner.end is allocation_end, "GRAPH_END_CHANGED")
            if pending and len(rows) == before:
                require(len(pending) == 1 and len(ledger) == before + 1, "GRAPH_ROSTER_CHANGED")
                rows.append((ledger[-1], "directory", pending[0], False, False))
            require(roster(), "GRAPH_ROSTER_CHANGED")
            value = saved_end(final=final)
            require(owner.__dict__ is dictionary and owner.end is allocation_end and roster(), "GRAPH_END_CHANGED")
            return value

        owner.end = allocation_end
        try:
            resource = owner.acquire("directory", factory)
            require(owner.__dict__ is dictionary and owner.end is allocation_end, "GRAPH_END_CHANGED")
        finally:
            if owner.__dict__ is dictionary and owner.end is allocation_end:
                if had_end:
                    owner.end = end_slot
                else:
                    del owner.end
            else:
                owner.unknown = True
        require(len(rows) == before + 1, "GRAPH_ROSTER_CHANGED")
        checked()
        owned(resource)
        return resource

    def retain(key, resource, name, raw, maximum):
        nonlocal used
        require(key not in originals and type(raw) is bytes and len(raw) <= maximum and
            used + len(raw) <= Q.MAX_SESSION_BYTES, "GRAPH_BYTE_LIMIT")
        used += len(raw)
        originals[key] = (resource, name, maximum, raw)
        return raw

    def read(key, resource, name, maximum=native.LIMIT):
        owned(resource)
        remaining = Q.MAX_SESSION_BYTES - used
        require(remaining > 0, "GRAPH_BYTE_LIMIT")
        raw = call(owner.read, resource, name, min(maximum, remaining))
        return retain(key, resource, name, raw, maximum)

    def raw(key):
        return originals[key][3]

    def value(key):
        return _initial_graph_json(raw(key))

    def sha(key):
        return O.digest(raw(key))

    def query(key, session_hash, side_hash, ancestor, observed):
        nonlocal leaf_failed
        resource = dirs[key]
        acquisition_root = key.endswith("/acquisition-queries")
        side = None
        if not acquisition_root:
            side = read(key + "/source-return.json", resource, "source-return.json")
            require(O.digest(side) == side_hash, "GRAPH_SOURCE_HASH")
            session_hash = _initial_graph_json(side)["sessionSha256"]
        session_raw = read(key + "/session-result.json", resource, "session-result.json", Q.MAX_RECEIPT_BYTES)
        require(O.digest(session_raw) == session_hash, "GRAPH_QUERY_HASH")
        session = _initial_graph_json(session_raw)
        queries, declarations = session.get("queries"), session.get("readbacks")
        require(type(queries) is list and len(queries) == (24 if acquisition_root else 12) and
            all(type(item) is dict and type(item.get("id")) is str and re.fullmatch(r"[0-9a-f]{32}", item["id"])
                for item in queries) and len({item["id"] for item in queries}) == len(queries), "GRAPH_QUERY_IDS")
        query_names = ("start.json", "baseline.json", "stdout.log", "stderr.log", "result.json")
        expected = [("", "owner.json")]
        if acquisition_root:
            expected.append(("", "event.bin"))
        for index, item in enumerate(queries):
            expected.extend(("query-" + item["id"], name) for name in query_names)
            if acquisition_root and index == 11:
                expected.extend(("", name + ".bin") for name in (*SOURCE_KEYS, *HTTP_KEYS))
        expected.extend(("", name + ".bin") for name in (("observation", "match") if acquisition_root else SOURCE_KEYS))
        require(type(declarations) is list and len(declarations) == len(expected), "GRAPH_QUERY_DECLARATIONS")
        reserved = 0
        for item, (parent, name) in zip(declarations, expected):
            require(type(item) is dict and set(item) == {"parent", "name", "maximum", "retirement", "result", "bytes", "sha256"} and
                item["parent"] == str(resource.path / parent) and item["name"] == name and
                type(item["bytes"]) is int and type(item["maximum"]) is int and
                0 <= item["bytes"] <= item["maximum"] <= Q.MAX_RECEIPT_BYTES and item["maximum"] > 0,
                "GRAPH_QUERY_DECLARATIONS")
            reserved += item["bytes"]
            require(used + reserved <= Q.MAX_SESSION_BYTES, "GRAPH_BYTE_LIMIT")
        checked()  # Reserve the entire fixed leaf BEFORE opening any leaf children.
        before = len(rows)
        try:
            result = query_reader(owner, resource, expected_session_sha256=session_hash, expected_source_return_raw=side)
        except BaseException:
            leaf_failed = True
            raise
        # No outer end guard overlaps the leaf. Pin its authentic successful
        # appended tail BEFORE a callback, clock, hash, parse or path inspection.
        tail = tuple((row, row.get("owner") if type(row) is dict else None) for row in ledger[before:])
        held.extend(resource_ for _, resource_ in tail)
        rows.extend((row, "directory", resource_, False, False) for row, resource_ in tail)
        child_names = ("query-home", *("query-" + item["id"] for item in queries))
        require(len(tail) == len(child_names), "GRAPH_QUERY_TAIL")
        for (_, child), name in zip(tail, child_names):
            pin(child, resource.path / name)
            rosters.append((child, () if name == "query-home" else query_names))
        checked()
        require(type(result) is tuple and len(result) == 3 and result[0] == session_raw and result[2] == side and
            type(result[1]) is tuple and len(result[1]) == len(expected), "GRAPH_QUERY_RETURN")
        root_names = ("owner.json", "session-result.json", *child_names,
            *(name + ".bin" for name in (ORIGINAL_KEYS if acquisition_root else SOURCE_KEYS)),
            *(("source-return.json",) if not acquisition_root else ()))
        rosters.append((resource, root_names))
        children = {"": resource, **{name: child for (_, child), name in zip(tail, child_names)}}
        for returned, item, (parent, name) in zip(result[1], declarations, expected):
            relative = str(Path(parent) / name)
            require(type(returned) is tuple and len(returned) == 2 and returned[0] == relative and
                type(returned[1]) is bytes and len(returned[1]) == item["bytes"], "GRAPH_QUERY_RETURN")
            # Compare the leaf's OS-native spelling, but keep the byte graph's
            # fixed keys slash-separated on every platform (including Windows).
            member = parent + "/" + name if parent else name
            retain(key + "/" + member, children[parent], name, returned[1], item["maximum"])
        owner_value = value(key + "/owner.json")
        same(owner_value["ancestorContext"], ancestor)
        for position, field in ((2, "commit"), (3, "tree")):
            capture = raw(key + "/query-" + queries[position]["id"] + "/stdout.log")
            require(I.sha(capture.decode("ascii").strip()) == observed["source"][field], "GRAPH_QUERY_SOURCE")
        originals_ = {name: raw(key + "/" + name + ".bin") for name in (ORIGINAL_KEYS if acquisition_root else SOURCE_KEYS)}
        if source_originals:
            require({name: originals_[name] for name in SOURCE_KEYS} == source_originals, "GRAPH_SOURCE_CHANGED")
        checked()
        return originals_, None if side is None else _initial_graph_json(side)

    try:
        recipient_path = call(_recipient_path)
        preparation = recipient_path.with_name(recipient_path.name.removesuffix("-recipient"))
        paths_by_key = {"P": preparation, "E": preparation.with_name(preparation.name + "-entry"), "R": recipient_path,
            "S": recipient_path.with_name(recipient_path.name + "-output")}
        pin(directory, paths_by_key["S"])
        checked()
        sender_raw, sender_records = sender_reader(owner, directory, recipient_outcome=recipient_outcome, expected_sha256=expected_sha256)
        checked()
        retain("S/sender-pending.json", directory, "sender-pending.json", sender_raw, native.LIMIT)
        for name, contents in sender_records:
            retain("S/" + name, directory, name, contents, native.LIMIT)
        rosters.append((directory, ("sender-pending.json", "readmission-return.json", "recipient-return.json")))
        entry, recipient, sender = value("S/readmission-return.json"), value("S/recipient-return.json"), value("S/sender-pending.json")
        dirs = {"S": directory}
        for key in ("P", "E", "R"):
            dirs[key] = opened(paths_by_key[key])
        dirs["R/authority"] = opened(recipient_path / "authority", dirs["R"])
        files = {"P": ("prelude.json", "context.json", "worker-identity.json", "worker-service-time.json",
                "worker-allocation-proposal.json", "initial-result.json"),
            "E": ("entry-window.json", "context.json", "entry-pending.json"),
            "R/authority": ("authority-window.json", "context.json", "authority-pending.json"),
            "R": (*RECIPIENT_FILES, "recipient-context.json", "recipient-pending.json")}
        service_dirs = ("control-home", "temporary", "source-before", "service", "acquisition-queries", "source-after")
        children = {key: service_dirs for key in ("P", "E", "R/authority")}
        children["R"] = (*RECIPIENT_DIRECTORIES, "authority", "source-final")
        for key in ("P", "E", "R/authority", "R"):
            names(dirs[key], (*files[key], *children[key]))
            rosters.append((dirs[key], (*files[key], *children[key])))
            for name in files[key]:
                read(key + "/" + name, dirs[key], name, I.POLICY_LIMIT if name == "worker-policy.json" else native.LIMIT)
            for name in children[key]:
                child_key = key + "/" + name
                if child_key not in dirs:
                    dirs[child_key] = opened(dirs[key].path / name, dirs[key])
                if name in ("control-home", "temporary"):
                    names(dirs[child_key], ())
                    rosters.append((dirs[child_key], ()))
        phase_files = ("start.json", "baseline.json", "result.json", "native-start.json", "stdout.log", "stderr.log", "child-result.json")
        for key in ("P/service", "E/service", "R/authority/service", "R/recipient-validation"):
            source_children = ("source-before", "source-after") if key == "R/recipient-validation" else ()
            names(dirs[key], (*phase_files, *source_children))
            rosters.append((dirs[key], (*phase_files, *source_children)))
            for name in phase_files:
                maximum = native.ACK_LIMIT if name == "stdout.log" else native.STDERR_LIMIT if name == "stderr.log" else native.LIMIT
                read(key + "/" + name, dirs[key], name, maximum)
            for name in source_children:
                dirs[key + "/" + name] = opened(dirs[key].path / name, dirs[key])
        require(len(rows) == prefix_count + 29 and len(originals) == 52, "GRAPH_WRAPPER_ROSTER")
        past = native.history.HistoricalPrelude(raw("P/prelude.json"))
        eframe, eclock, efirst, ework, efinal = _entry_frame(raw("E/entry-window.json"))
        rframe, rclock, rfirst, rends = _recipient_frame(raw("R/recipient-window.json"))
        aframe, aclock, afirst, awork, afinal = _authority_frame(raw("R/authority/authority-window.json"))
        require(all(clock == first.clock for clock in (past.clock, eclock, rclock, aclock)), "GRAPH_CLOCK")
        same(eframe, entry["window"])
        same(rframe, recipient["window"])
        same(aframe, rframe)
        pcontext = value("P/context.json")
        observed = pcontext["observed"]
        require(type(observed) is dict and set(observed) == {"kind", "source", "inputs", "firstUseAt", "role", "runnerName", "github"} and
            observed["kind"] == "worker" and observed["role"] == role and type(observed["runnerName"]) is str and
            0 < len(observed["runnerName"]) <= 256 and not any(ord(c) < 32 or ord(c) == 127 for c in observed["runnerName"]),
            "GRAPH_OBSERVED")
        first_use = O.integer(observed["firstUseAt"], 1)
        contexts, phases, services, matches, captures, chains = {}, {}, {}, {}, {}, {}
        source_originals = {}
        for key, kind, frame_name, frame_key, scope, fields, frame, began, work, final in (
            ("P", "P", "prelude.json", "prelude", native.INITIAL_CONTEXT_SCOPE, CONTEXT_FIELDS,
                O.parse(past.raw), past.first, past.work, past.final),
            ("E", "E", "entry-window.json", "entryWindow", native.INITIAL_ENTRY_CONTEXT_SCOPE, ENTRY_CONTEXT_FIELDS,
                eframe, efirst, ework, efinal),
            ("R/authority", "A", "authority-window.json", "authorityWindow", native.INITIAL_AUTHORITY_CONTEXT_SCOPE, AUTHORITY_CONTEXT_FIELDS,
                value("R/authority/authority-window.json"), afirst, awork, afinal)):
            context_raw = raw(key + "/context.json")
            context = _initial_graph_json(context_raw, fields, scope)
            same(context[frame_key], frame)
            same(context["observed"], observed)
            require(context["root"] == str(ROOT) and context["session"] == str(dirs[key].path) and
                context["budgetAcceptance"] == "NOT_ADMITTED" and context["exportSaveAuthority"] is False and
                type(context["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", context["job"]), "GRAPH_CONTEXT")
            inherited = context["inheritedContext"]
            require(type(inherited) is dict and all(type(item) is str for item in inherited.values()) and
                (set(inherited).issubset({"GRADLE_USER_HOME"}) or set(inherited) == set(Q._CONTEXT)), "GRAPH_CONTEXT_ANCESTORS")
            same(inherited, pcontext["inheritedContext"])
            before_originals, before = query(key + "/source-before", None, context["sourceReturnSha256"], inherited, observed)
            same(context["sourceReturnedNs"], before["returnedNs"])
            require(began <= O.integer(before["returnedNs"]) < work, "GRAPH_SOURCE_CHRONOLOGY")
            if not source_originals:
                source_originals = before_originals
            phase = _initial_graph_native(context_raw, dirs[key].path, first.clock, began, work, final,
                {name: raw(key + "/service/" + name) for name in native.PHASE_FILES}, raw(key + "/service/child-result.json"), kind)
            start, row, birth, child, ack = phase
            originals_, _ = query(key + "/acquisition-queries", child["querySessionSha256"], None, start["inheritedContext"], observed)
            require(context["eventSha256"] == O.digest(originals_["event"]) and child["originalsSha256"] ==
                {name: O.digest(originals_[name]) for name in ORIGINAL_KEYS} and child["matchSha256"] == O.digest(originals_["match"]),
                "GRAPH_SERVICE_ORIGINALS")
            inputs = _retained_match_inputs(context, originals_, start["invocation"], first.clock, start["startedNs"], start["workEndNs"])
            match, service = _retained_match_at(inputs, now=first_use)
            minimum = _service_chain_minimum(began, before["returnedNs"], start, row, birth, child, service, ack)
            pending_name = {"P": "initial-result.json", "E": "entry-pending.json", "A": "authority-pending.json"}[kind]
            pending = value(key + "/" + pending_name)
            chain = pending["originalChain"]
            require(type(chain) is dict, "GRAPH_CHAIN")
            checked_ns = O.integer(chain.get("checkedNs"), minimum)
            same(chain, {"phaseSha256": {name: sha(key + "/service/" + name) for name in native.PHASE_FILES},
                "childSha256": sha(key + "/service/child-result.json"), "querySessionSha256": sha(key + "/acquisition-queries/session-result.json"),
                "originalsSha256": {name: O.digest(originals_[name]) for name in ORIGINAL_KEYS}, "checkedNs": checked_ns})
            after_hash = (value("R/authority-return.json")["filesSha256"]["source-after/source-return.json"] if kind == "A" else pending["sourceAfterSha256"])
            _, after = query(key + "/source-after", None, after_hash, inherited, observed)
            require(row["finalizedNs"] <= O.integer(after["returnedNs"]) <= checked_ns <= O.integer(pending["retainedNs"]) < work,
                "GRAPH_SERVICE_CHRONOLOGY")
            captured = (context_raw, tuple((name, originals_[name]) for name in ORIGINAL_KEYS), start["invocation"], start["startedNs"], start["workEndNs"])
            contexts[key], phases[key], services[key], matches[key], captures[key], chains[key] = context, phase, service, match, captured, chain
            if kind != "P":
                require(match.record == matches["P"].record and originals_["event"] == dict(captures["P"][1])["event"] and
                    _service_job(captured, first.clock) == _service_job(captures["P"], first.clock), "GRAPH_ORIGINAL_JOB_OR_MATCH")
                same(context["expectedMatch"], O.parse(matches["P"].record))
                require(O.encoded(context["originalProposal"]) == raw("P/worker-allocation-proposal.json"), "GRAPH_ORIGINAL_PROPOSAL")
        initial_raw = dict(captures["P"][1])
        identity = initial_identity.bind_worker_match(matches["P"], event_raw=initial_raw["event"],
            policy_raw=source_originals["candidate_policy_raw"], now=first_use)
        require(identity.record == raw("P/worker-identity.json"), "GRAPH_WORKER_IDENTITY")
        identity_value = O.parse(identity.record)
        github = {name: identity_value["github"][name] for name in ("event", "ref", "workflow", "workflowSha", "job", "runId", "runAttempt", "runnerOS", "runnerArch")}
        same(observed, {"kind": "worker", "source": identity_value["source"], "inputs": I.parse(initial_raw["event"], I.EVENT_LIMIT)["inputs"],
            "firstUseAt": first_use, "role": role, "runnerName": observed["runnerName"], "github": github})
        require(preparation.name == "p2pkit-initial-recipient-" + github["runId"] + "-" + github["runAttempt"] + "-worker" and
            identity_value["cacheCohort"]["role"] == role, "GRAPH_JOB_PATH")
        basis_raw, proposal_raw = _worker_time_values(identity, services["P"], first.clock, phases["P"][0]["invocation"])
        require(basis_raw == raw("P/worker-service-time.json") and proposal_raw == raw("P/worker-allocation-proposal.json"),
            "GRAPH_ORIGINAL_TIME_BASIS")
        proposal = O.parse(proposal_raw)
        p = value("P/initial-result.json")
        same(p, {"schema": 1, "scope": RESULT_SCOPE, "contextSha256": sha("P/context.json"),
            "sourceBeforeSha256": sha("P/source-before/source-return.json"), "sourceAfterSha256": sha("P/source-after/source-return.json"),
            "matchSha256": O.digest(matches["P"].record), "originalChain": chains["P"], "retainedNs": O.integer(p["retainedNs"]),
            "retirement": "PENDING_OWNER_CLOSE", "budgetAcceptance": "NOT_ADMITTED", "workerAdmission": "NOT_PERFORMED",
            "workerIdentitySha256": O.digest(identity.record), "serviceTimeBasisSha256": O.digest(basis_raw),
            "allocationProposalSha256": O.digest(proposal_raw), "qualificationAcceptance": "NOT_ESTABLISHED", "exportSaveAuthority": False})
        for supplied in (entry["originalPreparationSha256"], eframe["originalPreparationSha256"]):
            same(supplied, sha("P/initial-result.json"))
        same(entry["workerIdentitySha256"], O.digest(identity.record))
        same(entry["serviceTimeBasisSha256"], O.digest(basis_raw))
        same(entry["allocationProposalSha256"], O.digest(proposal_raw))
        same(eframe["originalProductiveEntryEndNs"], proposal["phaseFencesNs"]["productive-entry"])
        same(eframe["originalProposedJobEndNs"], proposal["proposedJobEndNs"])
        same(eframe["firstUseAt"], first_use)
        require(p["retainedNs"] <= eframe["previousNs"] < past.final, "GRAPH_PREPARATION_PREVIOUS")
        ep = value("E/entry-pending.json")
        same(ep, {"schema": 1, "scope": ENTRY_PENDING_SCOPE, "originalPreparationSha256": sha("P/initial-result.json"),
            "windowSha256": sha("E/entry-window.json"), "contextSha256": sha("E/context.json"),
            "sourceBeforeSha256": sha("E/source-before/source-return.json"), "sourceAfterSha256": sha("E/source-after/source-return.json"),
            "matchSha256": O.digest(matches["P"].record), "originalChain": chains["E"], "retainedNs": O.integer(ep["retainedNs"]),
            "retirement": "PENDING_OWNER_CLOSE", "budgetAcceptance": "NOT_ADMITTED", "workerAdmission": "NOT_PERFORMED",
            "qualificationAcceptance": "NOT_ESTABLISHED", "exportSaveAuthority": False})
        require(entry["pendingSha256"] == sha("E/entry-pending.json") and ep["retainedNs"] <= entry["preCloseNs"], "GRAPH_ENTRY_CLOSE")
        same(rframe["originalFencesNs"], {name: proposal["phaseFencesNs"][name] for name in
            ("recipient-validation", "recipient-final", "recipient-read")})
        for name, expected_raw in (("worker-identity.json", identity.record), ("worker-match.json", matches["P"].record),
                ("worker-policy.json", identity.original_policy), ("worker-proposal.json", proposal_raw), ("recipient-public.asc", identity.public_key)):
            require(raw("R/" + name) == expected_raw, "GRAPH_RECIPIENT_IDENTITY")
        authority, ap = value("R/authority-return.json"), value("R/authority/authority-pending.json")
        authority_names = ("authority-window.json", "context.json", "service/child-result.json", "acquisition-queries/session-result.json",
            *("service/" + name for name in sorted(native.PHASE_FILES)), *("acquisition-queries/" + name + ".bin" for name in ORIGINAL_KEYS),
            *(side + "/" + name for side in ("source-before", "source-after") for name in
                ("source-return.json", "session-result.json", *(name + ".bin" for name in SOURCE_KEYS))))
        require(len(authority_names) == 37, "GRAPH_AUTHORITY_ROSTER")
        file_hashes = {name: sha("R/authority/" + name) for name in authority_names}
        same(ap, {"schema": 1, "scope": "INITIAL_RECIPIENT_USE_AUTHORITY_PENDING_CLOSE_V1", "recipientWindowSha256": sha("R/recipient-window.json"),
            "originalReadmissionSha256": sha("S/readmission-return.json"), "filesSha256": file_hashes,
            "originalChain": chains["R/authority"], "retainedNs": O.integer(ap["retainedNs"]), "retirement": "PENDING_OWNER_CLOSE"})
        same(authority, {"schema": 1, "scope": "INITIAL_RECIPIENT_USE_AUTHORITY_CLOSED_HISTORY_V1",
            "recipientWindowSha256": sha("R/recipient-window.json"), "originalReadmissionSha256": sha("S/readmission-return.json"),
            "workerIdentitySha256": O.digest(identity.record), "matchSha256": O.digest(matches["P"].record),
            "serviceTimeBasisSha256": O.digest(basis_raw), "originalProposalSha256": O.digest(proposal_raw), "filesSha256": file_hashes,
            "pendingSha256": sha("R/authority/authority-pending.json"), "originalChain": chains["R/authority"],
            "preCloseNs": O.integer(authority["preCloseNs"], ap["retainedNs"]), "closedNs": O.integer(authority["closedNs"]),
            "resourceCount": O.integer(authority["resourceCount"], 1), "retirement": "KNOWN_RESOURCE_CLOSE_ONLY",
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        require(authority["preCloseNs"] < awork and authority["preCloseNs"] <= authority["closedNs"] < afinal <= rends[0], "GRAPH_AUTHORITY_CLOSE")
        same(recipient["authoritySha256"], sha("R/authority-return.json"))
        rcontext = _initial_graph_json(raw("R/recipient-context.json"), RECIPIENT_CONTEXT_FIELDS, RECIPIENT_CONTEXT_SCOPE)
        same(rcontext, {"schema": 1, "scope": RECIPIENT_CONTEXT_SCOPE, "root": str(ROOT), "session": str(recipient_path),
            "observed": observed, "eventSha256": O.digest(initial_raw["event"]), "filesSha256": {name: sha("R/" + name) for name in RECIPIENT_FILES},
            "job": rcontext["job"], "inheritedContext": pcontext["inheritedContext"],
            "directories": {name: native.directory_identity(list(dirs["R/" + name].identity), role) for name in RECIPIENT_DIRECTORIES},
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        require(type(rcontext["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", rcontext["job"]), "GRAPH_RECIPIENT_JOB")
        # The crypto directory is identity-pinned above, never enumerated/read.
        start, row, birth, child, ack = _initial_graph_native(raw("R/recipient-context.json"), recipient_path, first.clock,
            rfirst, rends[0], rends[1], {name: raw("R/recipient-validation/" + name) for name in native.PHASE_FILES},
            raw("R/recipient-validation/child-result.json"), "R")
        require(child["identitySha256"] == O.digest(identity.record) and child["authoritySha256"] == sha("R/authority-return.json"),
            "GRAPH_RECIPIENT_CHILD_BINDING")
        before, after = (query("R/recipient-validation/" + name, None, child[hash_name], start["inheritedContext"], observed)[1]
            for name, hash_name in (("source-before", "sourceBeforeSha256"), ("source-after", "sourceAfterSha256")))
        rp = value("R/recipient-pending.json")
        _, final_source = query("R/source-final", None, rp["sourceFinalSha256"], rcontext["inheritedContext"], observed)
        supplier = child["recipient"]
        supplier_fields = {"fingerprint", "encryption_fingerprint", "expires_at", "key_sha256", "work_identity", "executable"}
        if role == "windows-x64":
            supplier_fields |= {"executable_sha256", "job_id"}
            require(type(supplier) is dict and supplier.get("job_id") == rcontext["job"] and
                type(supplier.get("executable_sha256")) is str and re.fullmatch(r"[0-9a-f]{64}", supplier["executable_sha256"]), "GRAPH_WINDOWS_SUPPLIER")
        require(type(supplier) is dict and set(supplier) == supplier_fields and supplier["fingerprint"] == identity.fingerprint and
            type(supplier["encryption_fingerprint"]) is str and re.fullmatch(r"[0-9A-F]{40}", supplier["encryption_fingerprint"]) and
            supplier["key_sha256"] == identity.key_sha256 and
            O.encoded(supplier["work_identity"]) == O.encoded(rcontext["directories"]["crypto"]) and
            type(supplier["expires_at"]) is int and (supplier["expires_at"] == 0 or supplier["expires_at"] >= identity.expires_at) and
            type(supplier["executable"]) is str and Path(supplier["executable"]).is_absolute(), "GRAPH_SUPPLIER_RECORD")
        same(rp, {"schema": 1, "scope": "INITIAL_RECIPIENT_VALIDATION_PENDING_OWNER_CLOSE_V1", "windowSha256": sha("R/recipient-window.json"),
            "contextSha256": sha("R/recipient-context.json"), "authoritySha256": sha("R/authority-return.json"),
            "phaseSha256": {name: sha("R/recipient-validation/" + name) for name in native.PHASE_FILES},
            "childSha256": sha("R/recipient-validation/child-result.json"), "sourceFinalSha256": sha("R/source-final/source-return.json"),
            "retainedNs": O.integer(rp["retainedNs"]), "retirement": "PENDING_OWNER_CLOSE", "liveRecipient": "NOT_TRANSFERRED",
            "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        same(recipient["pendingSha256"], sha("R/recipient-pending.json"))
        times = [rfirst, authority["closedNs"], start["startedNs"], row["launchMinimumNs"], child["beganNs"], child["metadataLastNs"],
            before["returnedNs"], child["supplierReturnedNs"], after["returnedNs"], child["completedNs"], ack["closedNs"], row["completedNs"],
            row["finalStartedNs"], row["finalizedNs"], row["readStartedNs"], row["readbackCompletedNs"], final_source["returnedNs"],
            rp["retainedNs"], recipient["preCloseNs"], recipient["closedNs"]]
        require(all(type(item) is int and 0 <= item <= O.clocks.UINT64 for item in times) and times == sorted(times) and
            child["metadataLastNs"] < child["beganNs"] + 45 * O.NS and
            ack["closedNs"] < min(child["beganNs"] + 210 * O.NS, rends[0]) and row["completedNs"] < rends[0] and
            row["launchMinimumNs"] <= O.integer(birth["observedNs"]) <= row["completedNs"], "GRAPH_RECIPIENT_CHRONOLOGY")
        require(type(row["finalEndNs"]) is int and row["finalEndNs"] == min(rends[1], row["finalStartedNs"] + 45 * O.NS) and
            type(row["readEndNs"]) is int and row["readEndNs"] == min(rends[2], row["readStartedNs"] + 30 * O.NS) and
            row["finalizedNs"] <= row["readStartedNs"] < row["finalEndNs"] and recipient["closedNs"] < row["readEndNs"] and
            sender["readWindow"]["readEndNs"] == row["readEndNs"], "GRAPH_ACTUAL_READ_FENCE")
        require(len(rows) == prefix_count + 221 and len(originals) == 1066, "GRAPH_COMPLETE_ROSTER")
        # Recheck earlier leaves after later traversal. Each fixed path is
        # charged once, never deduplicated by content; no second leaf invocation.
        for resource, expected in rosters:
            names(resource, expected)
        for resource, name, _maximum, contents in originals.values():
            owned(resource)
            require(call(owner.read, resource, name, max(1, len(contents))) == contents, "GRAPH_REREAD_CHANGED")
        for resource, expected in rosters:
            names(resource, expected)
        for resource, _path, _identity, _original_path in pins:
            owned(resource)  # Includes crypto's directory identity, never its contents.
        checked()
        return tuple((name, contents) for name, (_resource, _file, _maximum, contents) in originals.items())
    except BaseException as error:
        original = owner.original if owner.original is not None else error
        unknown = False
        try:
            # A failed fixed leaf may legitimately have added rows. Do not
            # adopt them or infer UNKNOWN merely from that longer ledger.
            structural(tail=leaf_failed)
        except BaseException:
            unknown = True
        try:
            owner.error("initial-original-graph", error, unknown=unknown)
        except BaseException:
            owner.unknown = True
        if owner.unknown:
            native.QUARANTINE.append((owner, tuple(rows), tuple(held), tuple(pins), tuple(originals.items())))
        raise original


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
    commands.add_parser("validate-recipient")
    for name in ("_service", "_service-entry", "_service-authority", "_recipient"):
        child = commands.add_parser(name)
        child.add_argument("--context-sha256", required=True)
        child.add_argument("--minimum-ns", required=True)
    args = parser.parse_args()
    try:
        require(sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode, "ISOLATED_INTERPRETER")
        if args.operation == "prepare-originals":
            native.guarded(prepare_originals)
        elif args.operation == "validate-recipient":
            native.guarded(validate_recipient)
        else:
            require(re.fullmatch(r"0|[1-9][0-9]{0,19}", args.minimum_ns), "LAUNCH_MINIMUM")
            minimum = O.integer(int(args.minimum_ns))
            entry, authority = args.operation == "_service-entry", args.operation == "_service-authority"
            command = (_recipient_command if args.operation == "_recipient" else native.initial_authority_command if authority
                       else native.initial_entry_command if entry else native.initial_command)
            command(args.context_sha256, minimum)
            if args.operation == "_recipient":
                native.guarded(lambda cancelled: _recipient_child(args.context_sha256, minimum, cancelled))
            else:
                native.guarded(lambda cancelled: service_child(args.context_sha256, minimum, cancelled, entry=entry, authority=authority))
        return 0
    except BaseException:
        print("INITIAL_RECIPIENT_ORIGINALS_NOT_ACCEPTED", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
