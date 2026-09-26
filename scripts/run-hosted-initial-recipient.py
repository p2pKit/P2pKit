#!/usr/bin/env python3
"""Dormant Stage1 native original acquisition; no Admission or execution grant.

The gate and populate worker use their actual identities. This fixed parent
owns the HTTP child and its nested read-only Git queries, reuses the maintained
native phase/finalization, and retains originals before returning a provisional
digest. The prepared bootstrap workflow connects only the nonproductive gate;
its productive job remains held. A successful command is not provider, recipient
crypto, budget, export or Stage2 qualification; original step outcome is still
required by any future caller. Both ordinary HOLDs remain separate.
"""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
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
import hosted_initial_recipient_continuity as continuity

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
RECEIVING_WINDOW_SCOPE = "INITIAL_RECIPIENT_RECEIVING_INIT120_SOURCE_CAP_V1"
RECEIVING_AUTHORITY_WINDOW_SCOPE = "INITIAL_RECIPIENT_RECEIVING_AUTHORITY_SOURCE_CAP_V1"
RECEIVING_CHILD_SCOPE = "INITIAL_RECIPIENT_RECEIVING_AUTHORITY_PENDING_CHILD_CLOSE_V1"
RECEIVING_OUTCOME_ENV = "P2PKIT_INITIAL_RECIPIENT_OUTCOME"
RECEIVING_HASH_ENV = "P2PKIT_INITIAL_RECIPIENT_SENDER_SHA256"
RECEIVING_CRYPTO_HASH_ENV = "P2PKIT_INITIAL_RECIPIENT_CRYPTO_ORIGINALS_SHA256"
_PREPARED_RETURNS = {}
_WORKER_USE_LOCK = threading.Lock()
_WORKER_USES, _WORKER_CLAIMS, _ENTRY_WINDOWS, _READMISSION_RETURNS = {}, {}, {}, {}
_READMISSION_ATTEMPTS = {}
_RECIPIENT_USE_LOCK = threading.Lock()
_READMISSION_USES, _RECIPIENT_ATTEMPTS, _RECIPIENT_CLAIMS = {}, {}, {}
_RECIPIENT_WINDOWS, _AUTHORITY_WINDOWS, _AUTHORITY_RETURNS, _RECIPIENT_RETURNS = {}, {}, {}, {}
_RECIPIENT_NATIVE_RETURNS = {}
_RECIPIENT_CRYPTO_ORIGINALS = {}
_RECIPIENT_SENDERS = {}
_RECEIVING_WINDOWS = {}
_RECEIVING_CONTINUATIONS = {}
_SENDER_STEP_ATTEMPTS = {}
_RECEIVING_INIT_ATTEMPTS = {}
_RECEIVING_INIT_RETURNS = {}
_RECEIVING_CLOSED_RETURNS = {}
_GATE_CAPTURES = {}
_GATE_RETURNS = {}
_GATE_HANDOFF_ATTEMPTS = {}
_GATE_USE_LOCK = threading.Lock()
_WORKER_READER_CAPTURES = {}
_WORKER_AUTHORITY_CAPTURES = {}
_WORKER_AUTHORITY_RETURNS = {}
_WORKER_CRYPTO_CAPTURES = {}
_WORKER_ORIGINAL_CAPTURES = {}
_WORKER_HANDOFF_ATTEMPTS = {}
_WORKER_HANDOFF_LOCK = threading.Lock()
GATE_INVENTORY_SCOPE = "INITIAL_RECIPIENT_GATE_ORIGINAL_INDEX_V1"
GATE_HANDOFF_SCOPE = "INITIAL_RECIPIENT_GATE_ORIGINALS_PENDING_HANDOFF_CLOSE_V1"
GATE_HANDOFF_FILE = "gate-originals.json"
WORKER_INVENTORY_SCOPE = "INITIAL_RECIPIENT_WORKER_ORIGINAL_INDEX_V1"
WORKER_HANDOFF_SCOPE = "INITIAL_RECIPIENT_WORKER_ORIGINALS_PENDING_HANDOFF_CLOSE_V1"
WORKER_HANDOFF_FILE = "worker-originals.json"


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
    return _service_job_transport(captured, clock, "private")


def _public_provider_service_job(captured, clock):
    """Distinct public original reader; never relabel public bytes as PRIVATE."""
    return _service_job_transport(captured, clock, "public-provider")


def _service_job_transport(captured, clock, transport):
    require(type(transport) is str and transport in ("private", "public-provider"), "SERVICE_JOB_TRANSPORT")
    context_raw, originals, invocation, _began, _end = captured
    context, raw = O.parse(context_raw), dict(originals)
    if transport == "public-provider":
        require(context["scope"] == native.INITIAL_PROVIDER_PUBLIC_CONTEXT_SCOPE and
            native.initial_use.site_scope(context["site"]) == native.INITIAL_PROVIDER_PUBLIC_CONTEXT_SCOPE,
            "SERVICE_JOB_PUBLIC_SCOPE")
    github = context["observed"]["github"]
    path = acquisition.API + "/actions/runs/" + github["runId"] + "/attempts/" + github["runAttempt"]
    reader = O.response_bytes if transport == "private" else O.initial_provider_response_bytes
    _, attempt, _ = reader(raw["attempt"], path, invocation, clock)
    _, jobs, date = reader(raw["jobs"], path + "/jobs?per_page=100&page=1", invocation, clock)
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
            if failure is None:
                failure = error
    if (supplier is not None and supplier.unknown) or Q.QUARANTINE or native.diagnostics._QUARANTINE:
        error = failure if failure is not None else O.OriginError("INITIAL_NATIVE_QUERY_UNKNOWN")
        owner.error("initial-query", error, unknown=True)
        if failure is None:
            failure = error
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


def _initial_service_phase(owner, private, context_raw, token, fence, before):
    """Carry the Git selected by ORIGINAL parent queries into the fixed child.

    This is same-call tool routing, not a new authority/receipt reader. No tool
    is discovered from PATH here and no original capability is reconstructed.
    """
    try:
        owner.end()
        path = private.path / "source-before"
        require(type(before) is SourceReturn and owner.initial_sources.get(str(path)) is before and
            type(before.raw) is bytes and type(before.session) is bytes and type(before.records) is tuple and
            tuple(name for name, _raw in before.records) == SOURCE_KEYS and
            all(type(name) is str and type(raw) is bytes for name, raw in before.records), "SERVICE_GIT_ORIGINAL")
        pin = before.records, before.session, before.raw
        context, returned, session = O.parse(context_raw), O.parse(before.raw), O.parse(before.session)
        require(context["scope"] in (native.INITIAL_CONTEXT_SCOPE, native.INITIAL_ENTRY_CONTEXT_SCOPE,
            native.INITIAL_AUTHORITY_CONTEXT_SCOPE, native.INITIAL_RECEIVING_CONTEXT_SCOPE,
            native.INITIAL_CUSTODY_AUTHORITY_CONTEXT_SCOPE, native.INITIAL_COLLECT_AUTHORITY_CONTEXT_SCOPE,
            native.INITIAL_TAIL_AUTHORITY_CONTEXT_SCOPE, native.INITIAL_BEFORE_AUTHORITY_CONTEXT_SCOPE,
            native.INITIAL_PRODUCTIVE_USE_CONTEXT_SCOPE, native.INITIAL_PROVIDER_PUBLIC_CONTEXT_SCOPE) and
            context["root"] == str(ROOT) and context["session"] == str(private.path) and
            context["sourceReturnSha256"] == O.digest(before.raw) and
            context["sourceReturnedNs"] == returned["returnedNs"] and
            type(context["sourceReturnedNs"]) is int, "SERVICE_GIT_CONTEXT")
        originals = dict(before.records)
        require(set(returned) == {"schema", "scope", "originalsSha256", "sessionSha256", "clock", "returnedNs"} and
            type(returned["schema"]) is int and returned["schema"] == 1 and returned["scope"] == SOURCE_SCOPE and
            returned["sessionSha256"] == O.digest(before.session) and
            returned["originalsSha256"] == {name: O.digest(raw) for name, raw in before.records} and
            before.raw == O.encoded(returned), "SERVICE_GIT_RETURN")
        require(set(session) == {"schema", "scope", "job", "queries", "result", "retirement", "firstError", "errors", "readbacks"} and
            type(session["schema"]) is int and session["schema"] == 1 and session["scope"] == "ORDINARY_GIT_QUERIES_ONLY" and
            session["result"] == "READY_FOR_CALLER_SEAL" and session["retirement"] == "KNOWN" and
            session["firstError"] is None and session["errors"] == [] and type(session["readbacks"]) is list and
            type(session["job"]) is str and re.fullmatch(r"[0-9a-f]{32}", session["job"]) and
            type(session["queries"]) is list and len(session["queries"]) == 12 and
            before.session == Q.encoded(session), "SERVICE_GIT_SESSION")
        source = context["observed"]["source"]["commit"]
        I.sha(source)
        entry = re.fullmatch(rb"100644 blob ([0-9a-f]{40})\t" + re.escape(I.POLICY_PATH.encode("ascii")) + rb"\x00",
            originals["candidate_policy_entry"])
        require(entry is not None, "SERVICE_GIT_POLICY_ENTRY")
        blob = entry.group(1).decode("ascii")
        # Closed counterpart of acquisition._source, not a replay/acquirer.
        commands = (("rev-parse", "--show-toplevel"), ("status", "--porcelain=v1", "--untracked-files=all"),
            ("rev-parse", "--verify", "HEAD^{commit}"), ("rev-parse", "--verify", source + "^{tree}"),
            ("rev-parse", "--is-shallow-repository"), ("rev-parse", "--verify", "refs/remotes/origin/main^{commit}"),
            ("rev-parse", "--verify", acquisition.stages.BASE["commit"] + "^{tree}"),
            ("ls-tree", "-z", acquisition.stages.BASE["commit"], "--", I.POLICY_PATH),
            ("merge-base", acquisition.stages.BASE["commit"], source), ("ls-tree", "-z", source, "--", I.POLICY_PATH),
            ("cat-file", "-s", blob), ("cat-file", "blob", blob))
        selected = None
        for row, command in zip(session["queries"], commands):
            require(type(row) is dict and type(row.get("argv")) is list and row["argv"] and
                type(row["argv"][0]) is str, "SERVICE_GIT_QUERY")
            if selected is None:
                selected = row["argv"][0]
            require(row["argv"] == [selected, "--no-replace-objects", "--no-pager", "-c", "core.fsmonitor=false",
                "-C", str(ROOT), *command] and row.get("job") == session["job"] and row.get("state") == str(path) and
                row.get("home") == str(path / "query-home") and row.get("cwd") == str(ROOT) and
                row.get("launchAttempted") is True and row.get("scopeAttempted") is True and
                type(row.get("waitExitCode")) is int and row["waitExitCode"] == 0 and
                row.get("retirement") == "KNOWN" and row.get("result") == "READY_FOR_CALLER_SEAL" and
                row.get("errors") == [] and row.get("ownedSurvivors") == [], "SERVICE_GIT_QUERY")
        owner.end()
        require(owner.initial_sources.get(str(path)) is before and
            (before.records, before.session, before.raw) == pin, "SERVICE_GIT_ORIGINAL_CHANGED")
        return native.phase(owner, private, context_raw, token, fence, initial_git=selected)
    finally:
        token = None  # Also clear this stack reference on prelaunch refusal.


def _initial_service_query_git(supplier):
    """Refuse resolver/CWD/PATHEXT shadows before the service's first Git launch.

    The native parent supplied this single search directory from its original
    query return. This is not a public executable override or admission API.
    GitView's later independent selection is also fenced by the unchanged
    NativeGitQueries exact argv-prefix check before it can launch anything.
    """
    search = os.environ.get("PATH")
    require(type(search) is str and 0 < len(search) <= 4096 and os.pathsep not in search and
        not any(ord(char) < 32 or ord(char) == 127 for char in search), "SERVICE_GIT_SEARCH")
    directory = Path(search)
    require(directory.is_absolute() and ".." not in directory.parts and str(directory) == search and
        directory.resolve(strict=True) == directory, "SERVICE_GIT_SEARCH")
    name = "git.exe" if os.name == "nt" else "git"
    expected = directory / name
    require(expected.resolve(strict=True) == expected and expected.is_file() and
        type(supplier.executable) is str and supplier.executable == str(expected), "SERVICE_GIT_SELECTION")
    if os.name == "nt":
        require(os.environ.get("PATHEXT") == ".EXE" and
            os.environ.get("NoDefaultCurrentDirectoryInExePath") == "1", "SERVICE_GIT_WINDOWS_SEARCH")


def context_record(raw, path, fence):
    value = O.parse(raw)
    entry = type(fence) is _ReadmissionWindow
    authority = type(fence) is _RecipientAuthorityWindow
    receiving = authority and _receiving_authority_window(fence)
    require(entry or authority or type(fence) is O.Fence, "CONTEXT_WINDOW")
    scope = (native.INITIAL_RECEIVING_CONTEXT_SCOPE if receiving else native.INITIAL_AUTHORITY_CONTEXT_SCOPE if authority else
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
        actual_path = (_receiving_path() if receiving else actual_path) / "authority"
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


def service_child(context_hash, minimum, cancelled, *, entry=False, authority=False, receiving=False):
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    owner = fence = directory = result_raw = None
    supplier = None
    try:
        require(type(entry) is bool and type(authority) is bool and type(receiving) is bool and
                not (entry and authority) and (not receiving or authority), "SERVICE_OPERATION")
        local_start = time.monotonic()
        local_end = local_start + O.wire.ACQUIRE_SECONDS
        first = O.clocks.validate_reading(O.clocks.observe())
        require(first.nanoseconds >= O.integer(minimum), "CHILD_PRECEDES_LAUNCH")
        owner = native.Owner(local_end, first=first, cancelled=lambda: native.cancellation(cancelled))
        if authority:
            path = (_receiving_path() if receiving else _recipient_path()) / "authority"
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
        require(not authority or receiving is _receiving_authority_window(fence), "SERVICE_AUTHORITY_ROUTE")
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
            _initial_service_query_git(supplier)
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
            "scope": RECEIVING_CHILD_SCOPE if receiving else AUTHORITY_CHILD_SCOPE if authority else ENTRY_CHILD_SCOPE if entry else CHILD_SCOPE,
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
    return {"schema": 1, "scope": (native.INITIAL_RECEIVING_ACK_SCOPE if receiving else native.INITIAL_AUTHORITY_ACK_SCOPE if authority else
            native.INITIAL_ENTRY_ACK_SCOPE if entry else native.INITIAL_ACK_SCOPE), "invocation": domain["id"],
            "terminalSha256": O.digest(result_raw), "clock": O.clock_value(fence.clock), "closedNs": closed}, fence, start["workEndNs"]


def _retained_match_inputs(context, raw, invocation, clock, work_start, work_end):
    """Interpret supplied HTTP/source bytes, without a clock or authority acquisition."""
    return _retained_match_transport(context, raw, invocation, clock, work_start, work_end, "private")


def _public_provider_match_inputs(context, raw, invocation, clock, work_start, work_end):
    """Fixed distinct sibling, including the same original public quota debt."""
    return _retained_match_transport(context, raw, invocation, clock, work_start, work_end, "public-provider")


def _retained_match_transport(context, raw, invocation, clock, work_start, work_end, transport):
    require(type(transport) is str and transport in ("private", "public-provider"), "RETAINED_MATCH_TRANSPORT")
    observed = context["observed"]
    if transport == "public-provider":
        require(context["scope"] == native.INITIAL_PROVIDER_PUBLIC_CONTEXT_SCOPE and observed["kind"] == "worker",
            "RETAINED_PUBLIC_PROVIDER_SCOPE")
        debt = native.initial_use.public.request_count(context["site"])
    github = observed["github"]
    base = acquisition.API + "/actions/runs/" + github["runId"]
    attempt_path = base + "/attempts/" + github["runAttempt"]
    bodies, times, dates = {}, [], []
    def body(name, path):
        reader = O.response_bytes if transport == "private" else O.initial_provider_response_bytes
        response, data, date = reader(raw[name], path, invocation, clock)
        _, headers = O.wire.headers(base64.b64decode(response["headersBase64"], validate=True))
        if transport == "public-provider":
            native.initial_use.public.remaining_requests(headers, debt - len(bodies) - 1)
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


def retained_public_provider_match(context, raw, invocation, clock, work_start, work_end):
    """Interpret all distinct public originals, then sample current policy time."""
    inputs = _public_provider_match_inputs(context, raw, invocation, clock, work_start, work_end)
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
    receiving = authority and _receiving_authority_window(fence)
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
            ack["scope"] == (native.INITIAL_RECEIVING_ACK_SCOPE if receiving else native.INITIAL_AUTHORITY_ACK_SCOPE if authority else
                            native.INITIAL_ENTRY_ACK_SCOPE if entry else native.INITIAL_ACK_SCOPE) and
            ack["invocation"] == start["invocation"] and ack["terminalSha256"] == O.digest(child_raw) and
            ack["clock"] == O.clock_value(fence.clock), "CHILD_ACK")
    require(set(child) == {"schema", "scope", "contextSha256", "startSha256", "invocation", "clock", "launchMinimumNs", "beganNs",
            "metadataLastNs", "acquiredNs", "queryReturnedNs", "querySessionSha256", "originalsSha256", "matchSha256", "completedNs",
            "retirement", "errors"} and type(child["schema"]) is int and child["schema"] == 1 and
            child["scope"] == (RECEIVING_CHILD_SCOPE if receiving else AUTHORITY_CHILD_SCOPE if authority else ENTRY_CHILD_SCOPE if entry else CHILD_SCOPE) and
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


def _gate_query_index(path, session_raw, originals, *, source=None):
    """Original session declarations only, NOT a replay or full byte rereader."""
    require(type(session_raw) is bytes and 0 < len(session_raw) <= Q.MAX_RECEIPT_BYTES,
            "GATE_QUERY_SESSION_BYTES")
    session = O.parse(session_raw)
    acquisition_root = source is None
    keys = ORIGINAL_KEYS if acquisition_root else SOURCE_KEYS
    require(type(originals) is dict and tuple(originals) == keys and
        all(type(raw) is bytes for raw in originals.values()), "GATE_QUERY_ORIGINAL_KEYS")
    require(session_raw == Q.encoded(session) and set(session) ==
        {"schema", "scope", "job", "queries", "result", "retirement", "firstError", "errors", "readbacks"} and
        type(session["schema"]) is int and session["schema"] == 1 and
        session["scope"] == "ORDINARY_GIT_QUERIES_ONLY" and type(session["job"]) is str and
        re.fullmatch(r"[0-9a-f]{32}", session["job"]) and session["result"] == "READY_FOR_CALLER_SEAL" and
        session["retirement"] == "KNOWN" and session["firstError"] is None and session["errors"] == [] and
        type(session["queries"]) is list and len(session["queries"]) == (24 if acquisition_root else 12) and
        type(session["readbacks"]) is list, "GATE_QUERY_SESSION")
    queries = session["queries"]
    require(all(type(row) is dict and type(row.get("id")) is str and re.fullmatch(r"[0-9a-f]{32}", row["id"])
        for row in queries) and len({row["id"] for row in queries}) == len(queries), "GATE_QUERY_IDS")
    expected = [(path, "owner.json", None)]
    if acquisition_root:
        expected.append((path, "event.bin", None))
    directories = [path, path / "query-home"]
    for index, query in enumerate(queries):
        target = path / ("query-" + query["id"])
        directories.append(target)
        limit = I.EVENT_LIMIT if index % 12 == 1 else I.POLICY_LIMIT if index % 12 == 11 else 4096
        require(type(query.get("stdoutLimit")) is int and query["stdoutLimit"] == limit and
            type(query.get("stderrLimit")) is int and query["stderrLimit"] == 4096 and
            query.get("job") == session["job"] and query.get("state") == str(path) and
            query.get("home") == str(path / "query-home") and query.get("cwd") == str(ROOT) and
            query.get("launchAttempted") is True and query.get("scopeAttempted") is True and
            type(query.get("waitExitCode")) is int and query["waitExitCode"] == 0 and
            query.get("retirement") == "KNOWN" and query.get("result") == "READY_FOR_CALLER_SEAL" and
            query.get("errors") == [] and query.get("ownedSurvivors") == [], "GATE_QUERY_RETURN")
        expected.extend((target, name, query[name[:-4] + "Limit"] if name.endswith(".log") else None)
            for name in ("start.json", "baseline.json", "stdout.log", "stderr.log", "result.json"))
        if acquisition_root and index == 11:
            expected.extend((path, name + ".bin", None) for name in (*SOURCE_KEYS, *HTTP_KEYS))
    expected.extend((path, name + ".bin", None)
        for name in (("observation", "match") if acquisition_root else SOURCE_KEYS))
    require(len(session["readbacks"]) == len(expected), "GATE_QUERY_READBACK_ROSTER")
    records, total = [], len(session_raw)
    for row, (parent, name, limit) in zip(session["readbacks"], expected):
        require(type(row) is dict and set(row) == {"parent", "name", "maximum", "retirement", "result", "bytes", "sha256"}
            and row["parent"] == str(parent) and row["name"] == name and row["retirement"] == "KNOWN" and
            row["result"] == "RETAINED" and type(row["bytes"]) is int and type(row["maximum"]) is int and
            0 <= row["bytes"] <= row["maximum"] <= Q.MAX_RECEIPT_BYTES and row["maximum"] > 0 and
            type(row["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) and
            row["maximum"] == (max(1, row["bytes"]) if limit is None else limit), "GATE_QUERY_READBACK")
        require(row["bytes"] != 0 or row["sha256"] == O.digest(b""), "GATE_QUERY_EMPTY_DIGEST")
        total += row["bytes"]
        require(total <= Q.MAX_SESSION_BYTES, "GATE_QUERY_SESSION_LIMIT")
        if parent == path and name.endswith(".bin"):
            raw = originals[name[:-4]]
            require(row["bytes"] == len(raw) and row["sha256"] == O.digest(raw), "GATE_QUERY_ORIGINAL_CHANGED")
        records.append((parent / name, row["maximum"], row["bytes"], row["sha256"]))
    records.append((path / "session-result.json", Q.MAX_RECEIPT_BYTES, len(session_raw), O.digest(session_raw)))
    if source is not None:
        require(type(source) is SourceReturn and source.session == session_raw and dict(source.records) == originals,
                "GATE_QUERY_SOURCE_RETURN")
        require(type(source.raw) is bytes and 0 < len(source.raw) <= native.LIMIT, "GATE_QUERY_SOURCE_BYTES")
        side = O.parse(source.raw)
        require(source.raw == O.encoded(side) and set(side) ==
            {"schema", "scope", "originalsSha256", "sessionSha256", "clock", "returnedNs"} and
            type(side["schema"]) is int and side["schema"] == 1 and side["scope"] == SOURCE_SCOPE and
            side["originalsSha256"] == {name: O.digest(raw) for name, raw in originals.items()} and
            side["sessionSha256"] == O.digest(session_raw), "GATE_QUERY_SOURCE_BINDING")
        records.append((path / "source-return.json", native.LIMIT, len(source.raw), O.digest(source.raw)))
    return records, directories


def _gate_inventory(path, prelude_raw, context_raw, before, after, phase, match, chain, captured,
                    child_raw, session_raw, result_raw):
    """Fixed281-file/58-directory metadata index; only seven original native pins exist."""
    require(type(match) is acquisition.gate.GateEligibility and type(match.record) is bytes and
        type(before) is SourceReturn and type(after) is SourceReturn and type(phase) is native.OriginalPhase and
        phase.context == context_raw and type(captured) is tuple and len(captured) == 5 and
        captured[0] == context_raw and type(captured[1]) is tuple and
        tuple(name for name, _raw in captured[1]) == ORIGINAL_KEYS, "GATE_ORIGINAL_INPUTS")
    context, gate, pending = O.parse(context_raw), O.parse(match.record), O.parse(result_raw)
    observed = context["observed"]
    require(observed["kind"] == "gate" and observed["role"] == "linux-x64" and
        observed["github"]["job"] == acquisition.gate.JOB and
        (observed["github"]["runnerOS"], observed["github"]["runnerArch"]) == ("Linux", "X64") and
        context["session"] == str(path) and context["prelude"] == O.parse(prelude_raw) and
        gate["scope"] == "NONPRODUCTIVE_ELIGIBILITY" and gate["stage"] == "stage1" and
        gate["github"] == observed["github"] and gate["source"] == gate["reviewed"] == observed["source"] and
        gate["firstUseAt"] == observed["firstUseAt"] and gate["originalBase"] == acquisition.stages.BASE and
        gate["policy"]["sha256"] == O.digest(dict(after.records)["candidate_policy_raw"]), "GATE_ORIGINAL_CONTEXT")
    require(type(result_raw) is bytes and result_raw == O.encoded(pending) and pending["scope"] == RESULT_SCOPE and
        pending["contextSha256"] == O.digest(context_raw) and pending["matchSha256"] == O.digest(match.record) and
        pending["sourceBeforeSha256"] == O.digest(before.raw) and pending["sourceAfterSha256"] == O.digest(after.raw) and
        pending["originalChain"] == chain and all(pending[name] is None for name in
        ("workerIdentitySha256", "serviceTimeBasisSha256", "allocationProposalSha256")) and
        pending["retirement"] == "PENDING_OWNER_CLOSE" and pending["exportSaveAuthority"] is False,
        "GATE_ORIGINAL_PENDING")
    original = dict(captured[1])
    require(len(original) == len(ORIGINAL_KEYS) and all(type(raw) is bytes for raw in original.values()) and
        original["match"] == match.record and {name: original[name] for name in SOURCE_KEYS} ==
        dict(before.records) == dict(after.records) and
        chain["childSha256"] == O.digest(child_raw) and chain["querySessionSha256"] == O.digest(session_raw) and
        chain["originalsSha256"] == {name: O.digest(raw) for name, raw in original.items()} and
        chain["phaseSha256"] == {name: O.digest(raw) for name, raw in phase.records}, "GATE_ORIGINAL_CHAIN")
    child = O.parse(child_raw)
    require(child["querySessionSha256"] == O.digest(session_raw) and child["matchSha256"] == O.digest(match.record) and
        child["originalsSha256"] == chain["originalsSha256"] and child["invocation"] == captured[2],
        "GATE_ORIGINAL_CHILD")
    records, directories = [], [path, path / "control-home", path / "temporary", path / "service"]
    for name, source, raw, data in (("source-before", before, before.session, dict(before.records)),
            ("acquisition-queries", None, session_raw, original), ("source-after", after, after.session, dict(after.records))):
        rows, paths = _gate_query_index(path / name, raw, data, source=source)
        records.extend(rows)
        directories.extend(paths)
    for name, raw in (("prelude.json", prelude_raw), ("context.json", context_raw), ("initial-result.json", result_raw),
            *(("service/" + name, raw) for name, raw in phase.records), ("service/child-result.json", child_raw)):
        require(type(raw) is bytes and len(raw) <= native.LIMIT, "GATE_ORIGINAL_RECORD_LIMIT")
        records.append((path / name, native.LIMIT, len(raw), O.digest(raw)))
    require(len(records) == len({item[0] for item in records}) == 281 and
        len(directories) == len(set(directories)) == 58, "GATE_ORIGINAL_COMPLETE_ROSTER")
    raw = O.encoded({"schema": 1, "scope": GATE_INVENTORY_SCOPE, "root": str(path),
        "contextSha256": O.digest(context_raw), "initialOriginalsSha256": O.digest(result_raw),
        "gateEligibilitySha256": O.digest(match.record), "source": observed["source"], "github": observed["github"],
        "policy": gate["policy"], "directories": sorted(str(item.relative_to(path)) for item in directories),
        "files": [{"relative": str(target.relative_to(path)), "maximum": maximum, "bytes": count, "sha256": digest}
            for target, maximum, count, digest in sorted(records)],
        "copyState": "ORIGINAL_BYTES_NOT_COPIED", "nestedNativePins": "NOT_CAPTURED", "exportSaveAuthority": False})
    require(len(raw) <= native.LIMIT, "GATE_ORIGINAL_INDEX_LIMIT")
    return raw


class _GateRoster:
    """One frozen full native ledger, not Owner.closed alone or a new worker guardian."""
    def __init__(self, owner):
        require(type(owner) is native.Owner and type(owner.resources) is list and type(owner.errors) is list and
            type(owner.initial_sources) is dict and not owner.closed and not owner.unknown and
            owner.original is None and owner.errors == [], "GATE_CLOSE_OWNER")
        self.owner, self.dictionary = owner, owner.__dict__
        self.rows, self.errors, self.sources = owner.resources, owner.errors, owner.initial_sources
        self.fence, self.cancelled, self.first = owner.fence, owner.cancelled, owner.first
        self.local, self.limits, self.early = owner.local_end, (owner.work_limit, owner.final_limit), owner.early_last
        self.phase = owner.phase_originals
        self.frozen = tuple((row, row.get("label"), row.get("owner"), row.get("attempted"), row.get("closed"))
            for row in self.rows if type(row) is dict)
        self.graph = _history_graph(self.sources, self.phase)
        self._binding = tuple((name, getattr(self, name)) for name in
            ("owner", "dictionary", "rows", "errors", "sources", "fence", "cancelled", "first", "local", "limits", "early",
             "phase", "frozen", "graph"))
        self.check(closed=False)

    def check(self, *, closed):
        require(type(self._binding) is tuple and len(self._binding) == 14 and all(getattr(self, name) is saved
            for name, saved in self._binding), "GATE_CLOSE_SNAPSHOT_CHANGED")
        owner = self.owner
        require(type(owner) is native.Owner and owner.__dict__ is self.dictionary and owner.resources is self.rows and
            owner.errors is self.errors and owner.initial_sources is self.sources and owner.phase_originals is self.phase and
            owner.fence is self.fence and owner.cancelled is self.cancelled and owner.first is self.first and
            type(owner.local_end) is float and owner.local_end == self.local and owner.early_last == self.early and
            all(type(a) is type(b) and a == b for a, b in zip((owner.work_limit, owner.final_limit), self.limits)) and
            owner.closed is closed and owner.unknown is False and owner.original is None and self.errors == [] and
            not native.QUARANTINE and not Q.QUARANTINE and not native.diagnostics._QUARANTINE,
            "GATE_CLOSE_OWNER_CHANGED")
        require(len(self.rows) == len(self.frozen) == len({id(row) for row, *_ in self.frozen}) ==
            len({id(resource) for _row, _label, resource, _a, _c in self.frozen}), "GATE_CLOSE_ROSTER_CHANGED")
        for current, (row, label, resource, attempted, was_closed) in zip(self.rows, self.frozen):
            require(current is row and type(row) is dict and set(row) == {"label", "owner", "attempted", "closed"} and
                type(label) is str and label in ("directory", "writer", "stdout", "stderr", "native-scope") and
                row["label"] == label and row["owner"] is resource and type(attempted) is bool and
                type(was_closed) is bool and (not was_closed or attempted) and
                type(row["attempted"]) is bool and type(row["closed"]) is bool and
                ((row["attempted"] and row["closed"]) if closed else
                 (row["attempted"] == attempted and row["closed"] == was_closed)), "GATE_CLOSE_RESOURCE_CHANGED")
        _check_history(self.graph)


@dataclass(frozen=True, repr=False)
class _GateCapture:
    raw: bytes
    owner: object
    root: object
    match: object
    result_raw: bytes
    pins: tuple
    roster: object
    boot: str


def _gate_boot_observe(fence, local_end, cancelled, expected=None, *, final=False, minimum=0):
    """Original gate process only; ClockIdentity alone is not a boot binding."""
    require(type(fence) is O.Fence and fence.clock.role == "linux-x64" and
        (expected is None or type(expected) is str and re.fullmatch(r"[0-9a-f]{64}", expected)),
        "GATE_BOOT_BINDING")
    native.cancellation(cancelled)
    before = fence.now(final=final, minimum=minimum)
    native.posix._deadline(local_end)
    boot = continuity.boot_digest("linux-x64")
    require(type(boot) is str and re.fullmatch(r"[0-9a-f]{64}", boot) and
        (expected is None or boot == expected), "GATE_BOOT_CHANGED")
    native.posix._deadline(local_end)
    # A fallible boot supplier cannot replace the already validated RAW floor
    # by lowering the mutable fence field. Keep the original minimum locally.
    after = fence.now(final=final, minimum=before)
    O.integer(after, before)
    native.cancellation(cancelled)
    return boot


def _gate_names(owner, directory, expected, *, final=False):
    """Linux gate only; the closed expected roster also bounds the native listing."""
    owner.end(final=final)
    directory.verify()
    names = []
    with os.scandir(directory.path) as entries:
        for entry in entries:
            owner.end(final=final)
            require(len(names) < max(1, len(expected)), "GATE_DIRECTORY_LIMIT")
            names.append(entry.name)
    require(len(names) == len(set(names)) and tuple(sorted(names)) == tuple(sorted(expected)), "GATE_DIRECTORY_ROSTER")
    directory.verify()
    owner.end(final=final)


def _capture_gate_originals(owner, private, context_raw, before, after, phase, match, chain, captured, result_raw, cancelled, boot):
    require(type(owner) is native.Owner and type(owner.fence) is O.Fence and owner.fence.clock.role == "linux-x64" and
        owner.phase_originals is phase and owner.initial_sources ==
        {str(private.path / "source-before"): before, str(private.path / "source-after"): after} and
        owner.initial_sources[str(private.path / "source-before")] is before and
        owner.initial_sources[str(private.path / "source-after")] is after, "GATE_ORIGINAL_OWNER")
    require(type(boot) is str and re.fullmatch(r"[0-9a-f]{64}", boot), "GATE_BOOT_BINDING")
    # Exactly two extra original reads; no query or service operation is replayed.
    service = owner.child(private, "service")
    child_raw = owner.read(service, "child-result.json")
    queries = owner.open(private.path / "acquisition-queries")
    session_raw = owner.read(queries, "session-result.json")
    raw = _gate_inventory(private.path, owner.fence.raw, context_raw, before, after, phase, match, chain, captured,
                          child_raw, session_raw, result_raw)
    inventory = O.parse(raw)
    # Freeze retained originals immediately, before listing/verification callbacks or close.
    graph = _history_graph(before, after, phase, match.__dict__, chain, captured, inventory, private.path)
    pins, identities = [], {}
    expected = {private.path, *(private.path / name for name in
        ("control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries"))}
    for row in tuple(owner.resources):
        if row["label"] != "directory":
            continue
        directory = row["owner"]
        require(type(directory) is Q._PosixDirectory and directory.path in expected and
            row["attempted"] is False and row["closed"] is False, "GATE_ORIGINAL_DIRECTORY")
        target, original_path = directory.path, directory.path
        identity = tuple(native.directory_identity(list(directory.identity), "linux-x64"))
        require(target not in identities or identities[target] == identity, "GATE_ORIGINAL_REPEATED_PIN")
        identities[target] = identity
        pins.append((directory, original_path, str(target), identity))
    require(set(identities) == expected and len(identities) == 7 and
        len(set(identities.values())) == 7, "GATE_ORIGINAL_PIN_ROSTER")
    pin_graph = _history_graph(tuple(path for _directory, path, _text, _identity in pins))
    for target in sorted(expected):
        directory = next(item for item, _path, text, _identity in pins if text == str(target))
        relative = target.relative_to(private.path)
        members = [Path(name).name for name in inventory["directories"] if name != "." and Path(name).parent == relative]
        members.extend(Path(row["relative"]).name for row in inventory["files"] if Path(row["relative"]).parent == relative)
        _gate_names(owner, directory, members)
        _check_history(graph)
        _check_history(pin_graph)
    owner.end()
    native.cancellation(cancelled)
    _check_history(graph)
    _check_history(pin_graph)
    roster = _GateRoster(owner)
    capture = _GateCapture(raw, owner, private.path, match, result_raw, tuple(pins), roster, boot)
    # The pre-close anchor is independent of the later preparation/return registry.
    anchor = (capture, raw, private.path, match, match.record, result_raw, capture.pins, roster, roster.frozen,
        graph, pin_graph, _GATE_CAPTURES, _GATE_RETURNS, _PREPARED_RETURNS, cancelled,
        owner.fence, owner.fence.raw, owner.fence.cancelled, owner.local_end, roster._binding, boot)
    require(id(owner) not in _GATE_CAPTURES and not hasattr(owner, "_gate_capture_anchor"), "GATE_CAPTURE_REUSE")
    owner._gate_capture_anchor = anchor  # Original owner anchor, never learned from a replacement return.
    _GATE_CAPTURES[id(owner)] = anchor
    _check_gate_capture(anchor, closed=False)
    owner.end()  # Collection AND the completed freeze must fit original WORK75, not only FINAL120.
    _check_gate_capture(anchor, closed=False)  # That last fallible clock/cancellation cannot replace the snapshot.
    return anchor


def _check_gate_capture(anchor, *, closed):
    require(type(anchor) is tuple and len(anchor) == 21, "GATE_CAPTURE_BINDING")
    capture, raw, root, match, match_raw, result_raw, pins, roster, frozen, graph, pin_graph, captures, returns, prepared, \
        cancelled, fence, prelude, cancel_check, local, roster_binding, boot = anchor
    require(type(capture) is _GateCapture and type(capture.owner) is native.Owner and
        capture.owner._gate_capture_anchor is anchor and captures is _GATE_CAPTURES and
        captures.get(id(capture.owner)) is anchor and returns is _GATE_RETURNS and prepared is _PREPARED_RETURNS and
        type(capture.raw) is bytes and capture.raw == raw and capture.root is root and capture.match is match and
        type(match.record) is bytes and match.record == match_raw and type(capture.result_raw) is bytes and
        capture.result_raw == result_raw and capture.pins is pins and capture.roster is roster and
        type(roster) is _GateRoster and roster.owner is capture.owner and roster.frozen is frozen and
        roster._binding is roster_binding and type(boot) is str and re.fullmatch(r"[0-9a-f]{64}", boot) and
        type(capture.boot) is str and capture.boot == boot and
        capture.owner.fence is fence and type(cancelled) is list and cancelled == [], "GATE_CAPTURE_CHANGED")
    _original_limits(capture.owner, fence, prelude, local, cancel_check)
    roster.check(closed=closed)
    _check_history(graph)
    _check_history(pin_graph)
    for directory, path, text, identity in pins:
        require(type(directory) is Q._PosixDirectory and directory.path is path and str(path) == text and
            type(directory.identity) is tuple and tuple(directory.identity) == identity and
            all(type(a) is type(b) for a, b in zip(directory.identity, identity)) and directory.closed is closed,
            "GATE_ORIGINAL_PIN_CHANGED")
    return capture


def _register_gate_return(original, anchor, closed_ns):
    capture = _check_gate_capture(anchor, closed=True)
    binding = _preparation_binding(original)
    require(binding.original is original and binding.owner is capture.owner and binding.match is capture.match and
        binding.raw == capture.result_raw and binding.identity is None and binding.worker_originals is None and
        binding.service_time_raw is None and binding.proposal_raw is None and original.raw == capture.result_raw and
        original.identity is None and original.service_time_raw is None and original.proposal_raw is None and
        original._cancelled is anchor[14] and binding.cancelled is anchor[14] and
        binding.last_ns == closed_ns == capture.owner.fence.last, "GATE_PREPARATION_BINDING")
    entry = (original, binding, anchor, O.integer(closed_ns), original.raw, original._match,
        binding.prelude_raw, binding.local_end, binding.cancel_check, _GATE_RETURNS)
    require(id(original) not in _GATE_RETURNS and not hasattr(capture.owner, "_gate_closed_entry"), "GATE_PREPARATION_REUSE")
    capture.owner._gate_closed_entry = entry
    _GATE_RETURNS[id(original)] = entry
    return entry


def _gate_return(original):
    entry = _GATE_RETURNS.get(id(original))
    require(type(entry) is tuple and len(entry) == 10 and entry[0] is original and entry[9] is _GATE_RETURNS and
        _preparation_binding(original) is entry[1], "NOT_ORIGINAL_GATE_RETURN")
    binding, anchor = entry[1], entry[2]
    capture = _check_gate_capture(anchor, closed=True)
    require(capture.owner._gate_closed_entry is entry and binding.owner is capture.owner and
        original._owner is capture.owner and original._fence is anchor[15] and
        original._cancelled is binding.cancelled is anchor[14] and original._match is binding.match is entry[5] is capture.match and
        type(original.raw) is bytes and type(binding.raw) is bytes and original.raw == binding.raw == entry[4] == capture.result_raw and
        type(binding.match_raw) is bytes and binding.match_raw == anchor[4] and binding.identity is None and binding.identity_fields is None and
        binding.worker_originals is None and binding.service_time_raw is None and binding.proposal_raw is None and
        original.identity is None and original.service_time_raw is None and original.proposal_raw is None and
        type(binding.prelude_raw) is bytes and binding.prelude_raw == entry[6] == anchor[16] and
        type(binding.local_end) is float and binding.local_end == entry[7] == anchor[18] and
        binding.cancel_check is entry[8] is anchor[17] and type(binding.last_ns) is int and binding.last_ns == entry[3],
        "GATE_RETURN_CHANGED")
    return entry


def _retain_gate_handoff(original):
    entry = _gate_return(original)
    binding, anchor, closed_ns = entry[1:4]
    capture = anchor[0]
    with _GATE_USE_LOCK:
        require(_GATE_RETURNS.get(id(original)) is entry and id(original) not in _GATE_HANDOFF_ATTEMPTS,
                "GATE_HANDOFF_ALREADY_CONSUMED")
        require(not hasattr(capture.owner, "_gate_handoff_attempt"), "GATE_HANDOFF_ALREADY_CONSUMED")
        marker = object()
        retained = []
        attempt = (original, marker, retained)
        capture.owner._gate_handoff_attempt = attempt
        _GATE_HANDOFF_ATTEMPTS[id(original)] = attempt  # Sticky before callbacks/I/O, also on failure.
    attempts = _GATE_HANDOFF_ATTEMPTS
    fence, local, cancelled = binding.fence, binding.local_end, binding.cancelled
    owner = roster = roster_binding = raw = pin = None
    failure, busy, final_calls, last, local_last = None, False, 0, closed_ns, None
    phase = "METADATA"

    def passive():
        if failure is not None:
            raise failure
        require(_gate_return(original) is entry and attempts is _GATE_HANDOFF_ATTEMPTS and
            attempts.get(id(original)) is attempt and capture.owner._gate_handoff_attempt is attempt,
                "GATE_HANDOFF_CHANGED")
        O.integer(fence.last, last)
        if roster is not None:
            require(roster._binding is roster_binding, "GATE_HANDOFF_CLOSE_BINDING_CHANGED")
            roster.check(closed=True)
        if pin is not None:
            directory, path, identity = pin
            require(directory.path is path and tuple(directory.identity) == identity and
                all(type(a) is type(b) for a, b in zip(directory.identity, identity)) and
                directory.closed is (roster is not None), "GATE_HANDOFF_PIN_CHANGED")

    def check():
        nonlocal failure, busy, last, local_last
        if failure is not None:
            raise failure
        if busy:
            failure = O.OriginError("GATE_HANDOFF_REENTRY")
            raise failure
        busy = True
        try:
            passive()
            native.cancellation(cancelled)
            _gate_boot_observe(fence, local, cancelled, capture.boot, final=True, minimum=last)
            value = O.integer(fence.last, last)
            last = max(last, value)
            sample = time.monotonic()
            require(type(sample) in (int, float) and math.isfinite(sample) and
                (local_last is None or sample >= local_last) and sample < local, "GATE_HANDOFF_LOCAL_EXPIRED")
            local_last = sample
            native.posix._deadline(local)
            native.cancellation(cancelled)
            passive()
            return value
        except BaseException as error:
            failure = error
            raise
        finally:
            # Even a failed final observation cannot be erased to revive this use.
            if type(fence.last) is int:
                last = max(last, fence.last)
            busy = False

    class OutputFence:
        final = fence.final

        def now(self, *, final=False, limit=None):
            nonlocal final_calls, failure
            try:
                require(phase == "OUTPUT" and final is True and type(limit) is int and
                    limit == self.final == fence.final and final_calls < 2, "GATE_FINAL_OUTPUT_ONLY")
                final_calls += 1
                return check()
            except BaseException as error:
                failure = failure or error
                raise failure

    try:
        check()
        owner = native.Owner(local, fence, cancelled=anchor[17])
        retained.append(owner)
        owner.initial_sources = {}
        check()
        path = capture.root.with_name(capture.root.name + "-handoff")
        directory = owner.acquire("directory", lambda: Q._new_private_directory(path), final=True)
        pin = (directory, directory.path, tuple(native.directory_identity(list(directory.identity), "linux-x64")))
        check()
        _gate_names(owner, directory, (), final=True)
        check()
        raw = owner.write(directory, GATE_HANDOFF_FILE, {"schema": 1, "scope": GATE_HANDOFF_SCOPE,
            "directory": str(path), "directoryIdentity": list(pin[2]), "inventory": O.parse(capture.raw),
            "gateEligibility": O.parse(capture.match.record), "originalClosedNs": closed_ns,
            "clock": O.clock_value(fence.clock), "bootDigest": capture.boot,
            "preludeSha256": O.digest(binding.prelude_raw),
            "originalClose": {"retirement": "KNOWN", "resources": [label for _row, label, _resource, _a, _c in capture.roster.frozen]},
            "originalNativeDirectories": [{"path": text, "identity": list(identity)} for text, identity in
                sorted({(text, identity) for _directory, _path, text, identity in capture.pins})],
            "writerReturn": "PENDING_OWNER_CLOSE", "originalStepOutcome": "NOT_OBSERVED",
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False}, final=True)
        check()
        require(owner.read(directory, GATE_HANDOFF_FILE, final=True) == raw, "GATE_HANDOFF_READBACK")
        _gate_names(owner, directory, (GATE_HANDOFF_FILE,), final=True)
        check()
        roster = _GateRoster(owner)
        roster_binding = roster._binding
        retained.append(roster)
    except BaseException as error:
        failure = failure or error
        if owner is not None:
            owner.error("gate-handoff", error)
    finally:
        if owner is not None:
            try:
                owner.close()
            except BaseException as error:
                owner.error("gate-handoff-close", error)
            if failure is None:
                failure = owner.original
    if failure is not None:
        raise failure
    require(owner is not None and roster is not None and raw is not None, "GATE_HANDOFF_INCOMPLETE")
    check()
    continuity.append_outputs({"initialOriginalsSha256": O.digest(original.raw), "gateHandoffSha256": O.digest(raw)}, check)
    check()
    phase = "OUTPUT"
    value = native.public_result(OUTPUT_SCOPE, "initialOriginalsSha256", original.raw)
    value["gateHandoffSha256"] = O.digest(raw)
    return value, OutputFence(), fence.final


def _prepare_with_token(cancelled, token):
    """Borrow only the outer parent's stack reference; never reinstall ambient credentials."""
    owner = None
    private = result_raw = worker_identity = worker_originals = service_time_raw = proposal_raw = gate_anchor = gate_boot = None
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
        if observed["kind"] == "gate":
            # Capture before original source/HTTP work in this SAME process.
            # Worker preparation and shared context/reader schemas are unchanged.
            gate_boot = _gate_boot_observe(fence, local_end, cancelled)
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
        _, phase = _initial_service_phase(owner, private, context_raw, token, fence, before)
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
        if worker_identity is None:
            gate_anchor = _capture_gate_originals(owner, private, context_raw, before, after, phase, match, chain,
                captured, result_raw, cancelled, gate_boot)
            _gate_boot_observe(fence, local_end, cancelled, gate_boot)
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
    if gate_boot is not None:
        _gate_boot_observe(fence, local_end, cancelled, gate_boot, final=True)
    closed_ns = fence.now(final=True)
    native.posix._deadline(local_end)
    native.cancellation(cancelled)
    original = _OriginalPreparation(result_raw, worker_identity, service_time_raw, proposal_raw, owner, fence, cancelled, match)
    _PREPARED_RETURNS[id(original)] = _PreparationBinding(original, result_raw, worker_identity,
        None if worker_identity is None else _worker_fields(worker_identity), match, match.record, owner, fence,
        prelude_raw, local_end, cancelled, cancel_check, fence.last, worker_originals, service_time_raw, proposal_raw)
    if worker_identity is None:
        _register_gate_return(original, gate_anchor, closed_ns)
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
        _, phase = _initial_service_phase(owner, private, context_raw, token, window, before)
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
        _RecipientState, _RecipientCryptoOriginals)
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


def _receiving_path():
    path = _recipient_path()
    return path.with_name(path.name + "-initializer")


def _receiving_frame(raw):
    """Receiving init120 data; never a reconstruction of a live recipient."""
    value = O.parse(raw)
    require(type(raw) is bytes and raw == O.encoded(value) and set(value) == {
        "schema", "scope", "clock", "firstNs", "previousNs", "workEndNs", "firstUseAt", "senderSha256",
        "workerIdentitySha256", "originalProposalSha256", "originalFencesNs", "originalProposedJobEndNs",
        "budgetAcceptance", "exportSaveAuthority"} and type(value["schema"]) is int and value["schema"] == 1 and
        value["scope"] == RECEIVING_WINDOW_SCOPE and value["budgetAcceptance"] == "NOT_ADMITTED" and
        value["exportSaveAuthority"] is False, "RECEIVING_FRAME")
    clock = O.wire.clock_identity(value["clock"])
    first = O.integer(value["firstNs"], O.integer(value["previousNs"]))
    fences = value["originalFencesNs"]
    require(type(fences) is dict and set(fences) == {"canonical-init", "canonical-init-final", "canonical-init-read"},
            "RECEIVING_FRAME_FENCES")
    ends = tuple(O.integer(fences[name]) for name in ("canonical-init", "canonical-init-final", "canonical-init-read"))
    work = min(O.integer(first + 120 * O.NS), ends[0], O.integer(value["originalProposedJobEndNs"]))
    require(first < work and ends[0] <= ends[1] <= ends[2] and type(value["workEndNs"]) is int and
            value["workEndNs"] == work, "RECEIVING_FRAME_FENCES")
    O.integer(value["firstUseAt"], 1)
    require(all(type(value[name]) is str and re.fullmatch(r"[0-9a-f]{64}", value[name]) for name in
        ("senderSha256", "workerIdentitySha256", "originalProposalSha256")), "RECEIVING_FRAME_BINDINGS")
    return value, clock, first, work


@dataclass(frozen=True, repr=False)
class _ReceivingState:
    window: object
    first_reading: object
    clock: object
    clock_raw: bytes
    first: int
    work: int
    local_start: float
    locals: tuple
    cancelled: object
    last: int
    local_last: float
    step: tuple
    roster: object = None
    raw: object = None
    originals: tuple = ()
    observed_raw: object = None
    captured: tuple = ()
    identity_fields: tuple = ()
    match_raw: object = None
    proposal_raw: object = None
    service_job: tuple = ()
    authority: object = None
    step_hash: object = None
    continuity: object = None
    inputs: object = None
    initialization: object = None
    phase: str = "WORK"
    busy: bool = False
    failed: bool = False
    terminal: bool = False


class _ReceivingWindow:
    """One NEW init120 anchor for reads, current acquisition and continuation.

    No native-final/read reservation is available to acquisition. The later
    fixed initializer must reuse these original first/local/proposal values;
    it cannot call the legacy initializer and start another120.
    """
    __slots__ = ()

    def __init__(self, local, first, cancelled, step):
        O.clocks.validate_reading(first)
        require(type(local) is float and math.isfinite(local) and local >= 0 and callable(cancelled) and
            type(step) is tuple and len(step) == 2 and step[0] == "success" and type(step[1]) is str and
            re.fullmatch(r"[0-9a-f]{64}", step[1]), "RECEIVING_FIRST")
        work = O.integer(first.nanoseconds + 120 * O.NS)
        cap = O.wire._directed_deadline(local, 120, work, first.nanoseconds)
        _RECEIVING_WINDOWS[id(self)] = _ReceivingState(self, first, first.clock, O.encoded(O.clock_value(first.clock)),
            first.nanoseconds, work, local, (cap,), cancelled, first.nanoseconds, local, step)

    def state(self, *, cleanup=False):
        state = _RECEIVING_WINDOWS.get(id(self))
        require(type(self) is _ReceivingWindow and type(state) is _ReceivingState and state.window is self,
                "RECEIVING_WINDOW_NOT_ORIGINAL")
        if state.roster is not None:
            state.roster.check()
        require(type(state.first_reading) is O.clocks.Reading and state.first_reading.clock is state.clock and
            type(state.first_reading.nanoseconds) is int and state.first_reading.nanoseconds == state.first and
            O.encoded(O.clock_value(state.clock)) == state.clock_raw, "RECEIVING_FIRST_CHANGED")
        if not cleanup:
            require(state.phase == "WORK" and not state.terminal and
                not native.QUARANTINE and not Q.QUARANTINE and not native.diagnostics._QUARANTINE,
                "RECEIVING_NOT_LIVE")
            if state.roster is not None:
                owner = state.roster.owner
                require(not owner.closed and not owner.unknown and owner.original is None and owner.errors == [],
                        "RECEIVING_OWNER_FAILED")
        return state

    raw = property(lambda self: self.state(cleanup=True).raw)
    clock = property(lambda self: self.state(cleanup=True).clock)
    first = property(lambda self: self.state(cleanup=True).first)
    work = property(lambda self: self.state(cleanup=True).work)
    final = property(lambda self: self.state(cleanup=True).work)
    last = property(lambda self: self.state(cleanup=True).last)
    local_end = property(lambda self: self.state(cleanup=True).locals[0])

    def bind(self, owner):
        state = self.state()
        require(state.roster is None, "RECEIVING_OWNER_REBIND")
        _RECEIVING_WINDOWS[id(self)] = replace(state, roster=_RecipientRoster(owner, self, state.first_reading))

    def now(self, *, final=False, minimum=0, limit=None):
        state = self.state(cleanup=final)
        require(type(final) is bool and not state.terminal and not state.busy and (final or not state.failed),
                "RECEIVING_WINDOW_RETIRED_OR_BUSY")
        _RECEIVING_WINDOWS[id(self)] = replace(state, busy=True)
        failed = False
        try:
            end = state.work if limit is None else min(state.work, O.integer(limit))
            for index in range(1 if final else 2):
                current = self.state(cleanup=final)
                local = time.monotonic()
                require(type(local) in (int, float) and math.isfinite(local) and local >= current.local_last,
                        "RECEIVING_LOCAL_BACKWARDS")
                _RECEIVING_WINDOWS[id(self)] = replace(current, local_last=local)
                observed = O.clocks.checked_now(state.clock, minimum_ns=max(current.last, O.integer(minimum)))
                _RECEIVING_WINDOWS[id(self)] = replace(self.state(cleanup=True), last=observed)
                after = time.monotonic()
                require(type(after) in (int, float) and math.isfinite(after) and after >= local, "RECEIVING_LOCAL_BACKWARDS")
                _RECEIVING_WINDOWS[id(self)] = replace(self.state(cleanup=True), local_last=after)
                require(observed < end and after < state.locals[0], "RECEIVING_INIT120_EXPIRED")
                if not final and index == 0:
                    state.cancelled()
                self.state(cleanup=final)
            return observed
        except BaseException:
            failed = True
            raise
        finally:
            current = _RECEIVING_WINDOWS[id(self)]
            _RECEIVING_WINDOWS[id(self)] = replace(current, busy=False, failed=current.failed or failed)

    def deadline(self, maximum, *, final=False, limit=None):
        require(type(maximum) in (int, float) and math.isfinite(maximum) and 0 < maximum <= 120,
                "RECEIVING_OPERATION_MAXIMUM")
        state = self.state()
        local = time.monotonic()
        observed = self.now(final=final, limit=limit)
        end = state.work if limit is None else min(state.work, O.integer(limit))
        result = min(state.locals[0], O.wire._directed_deadline(local, maximum, end, observed))
        self.state()
        return result


def _bind_receiving_originals(window, originals):
    """Bind the actual fixed reader return, never populate old live registries."""
    state = window.state()
    require(state.raw is None and type(originals) is tuple and len(originals) == 1066 and
        all(type(row) is tuple and len(row) == 2 and type(row[0]) is str and type(row[1]) is bytes for row in originals) and
        len(dict(originals)) == len(originals), "RECEIVING_ORIGINALS")
    raw = dict(originals)
    context = O.parse(raw["P/context.json"])
    sender = O.parse(raw["S/sender-pending.json"])
    require(O.digest(raw["S/sender-pending.json"]) == state.step[1], "RECEIVING_SENDER_CHANGED")
    match_raw = raw["P/acquisition-queries/match.bin"]
    event = raw["P/acquisition-queries/event.bin"]
    match = acquisition.stages.BootstrapMatch(match_raw)
    current = initial_identity.bind_worker_match(match, event_raw=event,
        policy_raw=raw["P/acquisition-queries/candidate_policy_raw.bin"], now=int(time.time()))
    identity_fields = _worker_fields(current)
    require(identity_fields[0] == raw["P/worker-identity.json"], "RECEIVING_WORKER_CHANGED")
    observed, _path, actual_event = _recipient_host(context["observed"]["firstUseAt"])
    require(context["observed"] == observed and event == actual_event and observed["role"] == state.clock.role and
        context["inheritedContext"] == Q._inherited_context(), "RECEIVING_ACTUAL_CONTEXT_CHANGED")
    start = O.parse(raw["P/service/start.json"])
    captured = (raw["P/context.json"], tuple((name, raw["P/acquisition-queries/" + name + ".bin"]) for name in ORIGINAL_KEYS),
        start["invocation"], start["startedNs"], start["workEndNs"])
    service_job = _service_job(captured, state.clock)
    proposal_raw = raw["P/worker-allocation-proposal.json"]
    # The fixed full reader already rederived these from the original service
    # responses. Do not run allocation arithmetic on today's service Date.
    proposal = O.parse(proposal_raw)
    require(proposal["scope"] == ALLOCATION_SCOPE and proposal["workerIdentitySha256"] == O.digest(identity_fields[0]) and
        proposal["clock"] == O.clock_value(state.clock) and proposal["firstUseAt"] == observed["firstUseAt"] and
        proposal["source"] == observed["source"], "RECEIVING_ORIGINAL_PROPOSAL")
    old = sender["readWindow"]
    require(state.first >= O.integer(old["retainedNs"]) and state.local_start >= old["previousLocal"],
            "RECEIVING_PREDECESSOR_ORDER")
    # These inequalities are consistency only. Same boot and the actual last
    # sender return still require the genuine trusted same-job step transport.
    work = min(state.work, proposal["phaseFencesNs"]["canonical-init"], proposal["proposedJobEndNs"])
    frame = O.encoded({"schema": 1, "scope": RECEIVING_WINDOW_SCOPE, "clock": O.clock_value(state.clock),
        "firstNs": state.first, "previousNs": old["retainedNs"], "workEndNs": work,
        "firstUseAt": observed["firstUseAt"], "senderSha256": state.step[1],
        "workerIdentitySha256": O.digest(identity_fields[0]), "originalProposalSha256": O.digest(proposal_raw),
        "originalFencesNs": {name: proposal["phaseFencesNs"][name] for name in
            ("canonical-init", "canonical-init-final", "canonical-init-read")},
        "originalProposedJobEndNs": proposal["proposedJobEndNs"], "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
    _receiving_frame(frame)
    cap = min(state.locals[0], O.wire._directed_deadline(state.local_start, 120, work, state.first))
    # Owner's original local_end is never renewed or replaced; the window only
    # intersects it with the now-read cumulative proposal. A late read refuses.
    _RECEIVING_WINDOWS[id(window)] = replace(state, raw=frame, work=work, locals=(cap,), originals=originals,
        observed_raw=O.encoded(observed), captured=captured, identity_fields=identity_fields, match_raw=match_raw,
        proposal_raw=proposal_raw, service_job=service_job)
    window.now()


def _receiving_current(window):
    state = window.state()
    require(state.raw is not None and (os.environ.get(RECEIVING_OUTCOME_ENV), os.environ.get(RECEIVING_HASH_ENV)) == state.step and
        os.environ.get(continuity.STEP_HASH_ENV) == state.step_hash and
        O.wire.TOKEN_ENV not in os.environ, "RECEIVING_STEP_OR_TOKEN_CHANGED")
    frame = _receiving_frame(state.raw)[0]
    observed, path, event = _recipient_host(frame["firstUseAt"])
    require(O.encoded(observed) == state.observed_raw and event == state.identity_fields[1] and
        O.parse(state.captured[0])["inheritedContext"] == Q._inherited_context(), "RECEIVING_ACTUAL_CONTEXT_CHANGED")
    current = initial_identity.bind_worker_match(acquisition.stages.BootstrapMatch(state.match_raw), event_raw=event,
        policy_raw=state.identity_fields[2], now=int(time.time()))
    require(_worker_fields(current) == state.identity_fields, "RECEIVING_CURRENT_POLICY_CHANGED")
    window.now()
    return observed, path, event


class _ReceivingContinuation:
    """Private lexical original only. No disk restoration, Admission or lease."""
    __slots__ = ()

    def checked(self):
        saved = _RECEIVING_CONTINUATIONS.get(id(self))
        require(type(self) is _ReceivingContinuation and type(saved) is tuple and len(saved) == 3 and saved[0] is self,
                "RECEIVING_CONTINUATION_NOT_ORIGINAL")
        window, authority = saved[1:]
        try:
            state = window.state()
            require(state.authority is authority and state.phase == "WORK", "RECEIVING_CONTINUATION_RETIRED")
            _authority_return(authority, window)
            _receiving_current(window)
            return state.roster.owner, window
        except BaseException as error:
            # An observed failure of THIS original live continuation is sticky.
            # Restoring inputs cannot revive it; copied/unregistered objects
            # refuse above without poisoning the original. Do not edit retired
            # owner history when a continuation is queried after scope exit.
            state = _RECEIVING_WINDOWS.get(id(window))
            if type(state) is _ReceivingState and state.window is window and not state.terminal:
                _RECEIVING_WINDOWS[id(window)] = replace(state, failed=True)
                if state.roster is not None:
                    state.roster.owner.error("receiving-continuation", error)
            raise


@contextmanager
def _receive_initialization(cancelled, *, crypto_sha256=None):
    """One receiving120 scope, including the separate fixed initializer route.

    Fixed env inputs name the future reviewed workflow's separate step outcome
    and recipientSenderSha256 transport. Their mere presence is not genuine
    workflow/boot/step-return qualification. All existing activation HOLDs stay.
    Only the registered fixed initializer may complete inside this original120.
    The old bare seam still refuses success. No supplied callback/success bit,
    restored legacy recipient or second initializer allowance is accepted.
    """
    token = os.environ.pop(O.wire.TOKEN_ENV, None)
    owner = window = continuation = reader_anchor = crypto_anchor = authority = authority_anchor = None
    failure = None

    def original_authority():
        # This lexical tuple is assigned immediately after the genuine call,
        # before any later supplier. A current registry entry cannot replace it.
        if authority_anchor is None:
            require(authority is None, "WORKER_AUTHORITY_RETURN_NOT_CAPTURED")
            return None
        return _worker_authority_return(authority, expected=authority_anchor)

    try:
        step = os.environ.get(RECEIVING_OUTCOME_ENV), os.environ.get(RECEIVING_HASH_ENV)
        require(step[0] == "success" and type(step[1]) is str and re.fullmatch(r"[0-9a-f]{64}", step[1]),
                "RECEIVING_STEP_INPUTS")
        require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token), "RECEIVING_READ_TOKEN")
        step_hash = os.environ.get(continuity.STEP_HASH_ENV)
        require(step_hash is None or type(step_hash) is str and re.fullmatch(r"[0-9a-f]{64}", step_hash),
                "RECEIVING_STEP_HASH")
        local = time.monotonic()  # One original LOCAL-before-RAW anchor, before any original read.
        first = O.clocks.validate_reading(O.clocks.observe())
        window = _ReceivingWindow(local, first, lambda: native.cancellation(cancelled), step)
        _RECEIVING_WINDOWS[id(window)] = replace(window.state(), step_hash=step_hash)
        owner = native.Owner(window.local_end, window, first=first, cancelled=window.state().cancelled)
        owner.initial_sources = {}
        window.bind(owner)
        native.host_inputs(first.clock.role)
        path = _receiving_path()
        native.child_environment(path)  # Reject overrides; token was already removed, never restored.
        private = owner.new(path)  # Exclusive reservation also refuses replay across fresh processes.
        step_original = None
        if step_hash is not None:
            _capture_receiving_step(window)
            step_original = _RECEIVING_WINDOWS[id(window)].continuity
        source = _recipient_path()
        sender = owner.open(source.with_name(source.name + "-output"))
        originals = _read_initial_recipient_originals(owner, sender, recipient_outcome=step[0], expected_sha256=step[1])
        # Pin the ACTUAL return and ledger before bind/current/source suppliers.
        # This supplements, but does not alter or repeat, the accepted reader.
        reader_anchor = _capture_worker_reader(window, owner, private, sender, originals, step_original, original_authority)
        _bind_receiving_originals(window, originals)
        _check_worker_reader(reader_anchor, bound=True)
        owner.write(private, "receiving-window.json", window.raw)
        _receiving_current(window)
        if step_hash is not None:
            _receiving_step_current(window)
            if crypto_sha256 is not None:
                crypto_anchor = _capture_worker_crypto(window, reader_anchor, crypto_sha256)
            _capture_receiving_inputs(window, private)  # BEFORE the unchanged source-before/HTTP/source-after.
        authority = _receiving_authority(window, token)
        authority_anchor = _WORKER_AUTHORITY_RETURNS.get(id(authority))
        require(type(authority_anchor) is tuple and len(authority_anchor) == 6 and authority_anchor[0] is authority,
                "WORKER_AUTHORITY_RETURN_NOT_CAPTURED")
        original_authority()
        token = None  # All current-acquisition frames have returned/closed; no credential crosses yield.
        state = window.state()
        _RECEIVING_WINDOWS[id(window)] = replace(state, authority=authority)
        continuation = _ReceivingContinuation()
        _RECEIVING_CONTINUATIONS[id(continuation)] = (continuation, window, authority)
        continuation.checked()
        _check_worker_reader(reader_anchor, bound=True)
        if crypto_anchor is not None:
            _check_worker_crypto(crypto_anchor)
        yield continuation
        _check_worker_reader(reader_anchor, bound=True)
        if crypto_anchor is not None:
            _check_worker_crypto(crypto_anchor)
        continuation.checked()
        _receiving_initialization_return(continuation)
        _receiving_step_current(window)
        _receiving_inputs_current(window)
    except BaseException as error:
        failure = error if owner is None or owner.original is None else owner.original
        if owner is not None:
            owner.error("receiving-initialization", error)
    finally:
        token = None
        if owner is not None:
            try:
                state = window.state(cleanup=True)
                _RECEIVING_WINDOWS[id(window)] = replace(state, phase="CLOSING")
                state.roster.freeze()
            except BaseException as error:
                owner.error("receiving-close-roster", error, unknown=True)
            try:
                owner.close()
            except BaseException as error:
                owner.error("receiving-owner-close", error)
            try:
                window.state(cleanup=True).roster.known()
                window.now(final=True)
                if reader_anchor is not None:
                    _check_worker_reader(reader_anchor, bound=True, closed=True)
                if crypto_anchor is not None:
                    _check_worker_crypto(crypto_anchor, closed=True)
            except BaseException as error:
                owner.error("receiving-close-return", error, unknown=owner.unknown)
            if failure is None:
                failure = owner.original
            state = _RECEIVING_WINDOWS[id(window)]
            _RECEIVING_WINDOWS[id(window)] = replace(state, terminal=True, failed=state.failed or failure is not None)
            if owner.unknown and not any(value is owner for value in native.QUARANTINE):
                native.QUARANTINE.append(owner)
    if failure is not None:
        raise failure


def _step_path():
    path = _recipient_path()
    return path.with_name(path.name + "-step")


def _step_record(raw):
    value = O.parse(raw)
    require(type(raw) is bytes and 0 < len(raw) <= continuity.STEP_LIMIT and raw == O.encoded(value) and
        set(value) == {"schema", "scope", "directory", "directoryIdentity", "senderSha256", "observed", "serviceJob",
            "workerIdentitySha256", "originalProposalSha256", "clock", "bootSha256", "lowerNs", "lowerLocal",
            "readEndNs", "readLocalCeiling", "sample", "writerReturn", "originalStepOutcome",
            "budgetAcceptance", "exportSaveAuthority"} and type(value["schema"]) is int and value["schema"] == 1 and
        value["scope"] == continuity.STEP_SCOPE and
        value["sample"] == "AFTER_SENDER_FUNCTION_BEFORE_GUARDED_OUTPUT_AND_STEP_RETURN" and
        value["writerReturn"] == "PENDING_OWNER_CLOSE" and value["originalStepOutcome"] == "NOT_OBSERVED" and
        value["budgetAcceptance"] == "NOT_ADMITTED" and value["exportSaveAuthority"] is False, "STEP_RECORD")
    clock = O.wire.clock_identity(value["clock"])
    require(all(type(value[name]) is str and re.fullmatch(r"[0-9a-f]{64}", value[name]) for name in
        ("senderSha256", "workerIdentitySha256", "originalProposalSha256", "bootSha256")), "STEP_RECORD_HASH")
    require(type(value["observed"]) is dict and type(value["serviceJob"]) is list and len(value["serviceJob"]) == 4 and
        type(value["directory"]) is str and Path(value["directory"]).is_absolute(), "STEP_RECORD_IDENTITY")
    native.directory_identity(value["directoryIdentity"], clock.role)
    require(O.integer(value["lowerNs"]) < O.integer(value["readEndNs"]) and
        all(type(value[name]) in (int, float) and math.isfinite(value[name]) for name in
            ("lowerLocal", "readLocalCeiling")) and 0 <= value["lowerLocal"] < value["readLocalCeiling"],
        "STEP_RECORD_BOUNDS")
    return value


@dataclass(frozen=True, repr=False)
class _ReceivingStep:
    raw: bytes
    directory: object
    path: object
    identity: tuple
    boot: str


def _capture_receiving_step(window):
    state = window.state()
    require(state.continuity is None and state.step_hash is not None and not continuity.QUARANTINE,
            "RECEIVING_CONTINUITY_NOT_NEW")
    owner, path = state.roster.owner, _step_path()
    directory = owner.open(path)
    raw = owner.read(directory, continuity.STEP_FILE, continuity.STEP_LIMIT)
    value = _step_record(raw)
    identity = tuple(native.directory_identity(list(directory.identity), state.clock.role))
    native._new_entry_owned(owner, directory, path, identity)
    require(value["directory"] == str(path) and value["directoryIdentity"] == list(identity) and
        O.digest(raw) == state.step_hash and value["senderSha256"] == state.step[1] and
        value["clock"] == O.clock_value(state.clock) and
        native._initializer_names(owner, directory) == (continuity.STEP_FILE,), "RECEIVING_CONTINUITY_BYTES")
    require(state.first >= value["lowerNs"] and state.local_start >= value["lowerLocal"],
            "RECEIVING_STEP_ORDER")
    window.now()
    boot = continuity.boot_digest(state.clock.role)
    window.now()
    require(boot == value["bootSha256"], "RECEIVING_BOOT_CHANGED")
    binding = _ReceivingStep(raw, directory, path, identity, boot)
    _RECEIVING_WINDOWS[id(window)] = replace(window.state(),
        continuity=(binding, _history_graph(binding.__dict__, path)))


def _receiving_step_current(window):
    state = window.state()
    require(state.continuity is not None and state.raw is not None and not continuity.QUARANTINE and
        (os.environ.get(RECEIVING_OUTCOME_ENV), os.environ.get(RECEIVING_HASH_ENV)) == state.step and
        os.environ.get(continuity.STEP_HASH_ENV) == state.step_hash and O.wire.TOKEN_ENV not in os.environ,
        "RECEIVING_CONTINUITY_REQUIRED")
    binding, graph = state.continuity
    require(type(binding) is _ReceivingStep, "RECEIVING_CONTINUITY_BINDING")
    _check_history(graph)
    value = _step_record(binding.raw)
    owner = state.roster.owner
    native._new_entry_owned(owner, binding.directory, _step_path(), binding.identity)
    require(owner.read(binding.directory, continuity.STEP_FILE, continuity.STEP_LIMIT) == binding.raw and
        native._initializer_names(owner, binding.directory) == (continuity.STEP_FILE,) and
        O.digest(binding.raw) == state.step_hash and value["senderSha256"] == state.step[1],
        "RECEIVING_CONTINUITY_CHANGED")
    original = O.parse(dict(state.originals)["S/sender-pending.json"])["readWindow"]
    require(O.encoded(value["observed"]) == state.observed_raw and tuple(value["serviceJob"]) == state.service_job and
        value["workerIdentitySha256"] == O.digest(state.identity_fields[0]) and
        value["originalProposalSha256"] == O.digest(state.proposal_raw) and
        value["clock"] == original["clock"] == O.clock_value(state.clock) and
        value["readEndNs"] == original["readEndNs"] and value["readLocalCeiling"] == original["readLocalCeiling"] and
        original["retainedNs"] <= value["lowerNs"] <= state.first and
        original["previousLocal"] <= value["lowerLocal"] <= state.local_start, "RECEIVING_CONTINUITY_ORIGINALS")
    window.now()
    require(continuity.boot_digest(state.clock.role) == binding.boot == value["bootSha256"], "RECEIVING_BOOT_CHANGED")
    window.now()
    _check_history(graph)


def _capture_receiving_inputs(window, private):
    """Bind source/tool bytes BEFORE their existing source/HTTP authentication."""
    state = window.state()
    require(state.inputs is None and state.continuity is not None, "RECEIVING_INIT_INPUTS_NOT_NEW")
    owner, path = state.roster.owner, _receiving_path()
    native.initialization.stdout_path(str(path / "state"), state.clock.role)
    directories = [("session", private)]
    for name in ("canonical-init", "control-home", "temporary"):
        directories.append((name, owner.child(private, name, create=True)))
    pinned = tuple((name, directory, directory.path,
        tuple(native.directory_identity(list(directory.identity), state.clock.role))) for name, directory in directories)
    require("state" not in {name.casefold() for name in native._initializer_names(owner, private)},
            "RECEIVING_INIT_STATE_EXISTS")
    toolchains = native.initialization.installed_toolchains()
    owner.end()
    interpreter = native.canonical._interpreter()
    request = native.canonical.init_request(state=str(path / "state"),
        expected_commit=O.parse(state.identity_fields[0])["source"]["commit"], role=state.clock.role)
    owner.end()
    environment = native.recipient_environment(path)
    environment.update(toolchains.environment())
    homes = toolchains.homes()
    inputs = native._InitializationInputs(request, interpreter, toolchains, tuple(sorted(environment.items())),
        homes, native.initialization.properties(homes))
    graph = _history_graph(inputs.__dict__, toolchains.__dict__, pinned)
    _RECEIVING_WINDOWS[id(window)] = replace(window.state(), inputs=(inputs, graph, pinned))
    owner.write(dict(directories)["canonical-init"], "request.json", request)
    _receiving_inputs_current(window, absent=True)


def _receiving_inputs_current(window, *, absent=False):
    state = window.state()
    require(state.inputs is not None and state.continuity is not None and O.wire.TOKEN_ENV not in os.environ,
            "RECEIVING_INIT_INPUTS_REQUIRED")
    inputs, graph, directories = state.inputs
    require(type(inputs) is native._InitializationInputs, "RECEIVING_INIT_INPUTS_CHANGED")
    _check_history(graph)
    owner, path = state.roster.owner, _receiving_path()
    for name, directory, target, identity in directories:
        require(target == (path if name == "session" else path / name), "RECEIVING_INIT_PATH_CHANGED")
        native._new_entry_owned(owner, directory, target, identity)
    handles = {name: directory for name, directory, _path, _identity in directories}
    environment = native.recipient_environment(path)
    environment.update(inputs.toolchains.environment())
    require(tuple(sorted(environment.items())) == inputs.environment and native.canonical._interpreter() == inputs.interpreter and
        inputs.toolchains.homes() == inputs.homes and native.initialization.properties(inputs.homes) == inputs.policy,
        "RECEIVING_INIT_INPUTS_CHANGED")
    require(native.canonical.init_request(state=str(path / "state"),
        expected_commit=O.parse(state.identity_fields[0])["source"]["commit"], role=state.clock.role) == inputs.request_raw and
        owner.read(handles["canonical-init"], "request.json") == inputs.request_raw, "RECEIVING_INIT_REQUEST_CHANGED")
    if absent:
        require("state" not in {name.casefold() for name in native._initializer_names(owner, handles["session"])} and
            all(native._initializer_names(owner, handles[name]) == () for name in ("control-home", "temporary")),
            "RECEIVING_INIT_STATE_EXISTS")
    _check_history(graph)
    window.now()
    return inputs, handles


def _receiving_initialize_native(continuation, context_raw):
    """Fixed canonical child, using ONLY the enclosing original WORK120 owner."""
    owner, window = continuation.checked()
    state = window.state()
    inputs, handles = _receiving_inputs_current(window, absent=True)
    directory, path = handles["canonical-init"], _receiving_path()
    context = O.parse(context_raw)
    invocation, argv = uuid.uuid4().hex, O.parse(inputs.request_raw)["argv"]
    environment = native.processes.ownership_environment(dict(inputs.environment), context["job"], invocation,
        str(path), str(path / "control-home"), allow_new_context=True)
    start = {"schema": 1, "scope": "INITIAL_RECIPIENT_CANONICAL_INIT_PRELAUNCH_V1", "contextSha256": O.digest(context_raw),
        "argv": argv, "cwd": str(ROOT), "role": state.clock.role, "job": context["job"], "invocation": invocation,
        "state": str(path), "home": str(path / "control-home"),
        "inheritedContext": {name: environment[name] for name in Q._CONTEXT}, "startedNs": window.now(),
        "workEndNs": state.work, "finalEndNs": state.work, "exitCode": None, "launchAttempted": False,
        "scopeAttempted": False, "retirement": "UNKNOWN"}
    start_raw = owner.write(directory, "start.json", start)
    row = {**start, "captureOutcomes": {name: {"synced": False, "verified": False, "closeAttempted": False,
        "closed": False, "readback": False} for name in ("stdout", "stderr")}}
    scope = out = err = baseline_raw = birth_raw = None
    native_known, resource_start = False, len(state.roster.seen)
    try:
        end = window.deadline(120)
        out = owner.acquire("stdout", lambda: directory.create_file("stdout.log", max_bytes=native.ACK_LIMIT, deadline=end))
        err = owner.acquire("stderr", lambda: directory.create_file("stderr.log", max_bytes=native.STDERR_LIMIT, deadline=end))
        def make_scope():
            row["scopeAttempted"] = True
            return native.processes.make_scope(context["job"], invocation, str(path), str(path / "control-home"))
        scope = owner.acquire("native-scope", make_scope)
        row["preparerIdentity"] = native.preparer_identity(scope, state.clock.role)
        baseline_raw = owner.write(directory, "baseline.json", {"role": state.clock.role,
            "baseline": sorted(scope.baseline) if hasattr(scope, "baseline") else None,
            "kernelJob": state.clock.role == "windows-x64"})
        row["baselineSha256"] = O.digest(baseline_raw)
        native.baseline_record(baseline_raw, state.clock.role)
        continuation.checked()
        _receiving_step_current(window)
        native._initializer_outputs_absent(owner)
        _receiving_inputs_current(window, absent=True)
        require(native.processes.ownership_environment(dict(inputs.environment), context["job"], invocation,
            str(path), str(path / "control-home"), allow_new_context=True) == environment,
            "RECEIVING_INIT_ENVIRONMENT_CHANGED")
        row["launchMinimumNs"] = window.now()
        row["launchArgv"], row["launchAttempted"] = argv, True
        child = scope.spawn(argv, str(ROOT), environment, stdout=out, stderr=err)
        require(child.stdout is None and child.stderr is None, "RECEIVING_INIT_PRIVATE_SINKS")
        birth = O.parse(O.encoded(scope.description()))
        leaders = [value for value in birth.get("startedIdentities", []) if value.get("pid") == child.pid]
        require(len(leaders) == 1, "RECEIVING_INIT_NATIVE_BIRTH")
        row["leader"] = leaders[0]
        native.native_record(birth, start, row["leader"], argv, terminal=False)
        birth_raw = owner.write(directory, "native-start.json", {"ownership": birth, "leader": row["leader"],
            "preparerIdentity": row["preparerIdentity"], "observedNs": window.now()})
        row["nativeStartSha256"] = O.digest(birth_raw)
        while True:
            window.now()
            for stream in (out, err):
                stream.observe_live_output() if state.clock.role == "windows-x64" else stream.verify()
            code = child.poll()
            if code is not None:
                row["exitCode"] = code  # Preserve the ACTUAL return, including a following failed observation.
            observed = window.now()
            if code is not None:
                row["completedNs"] = observed
                require(type(code) is int and code == 0, "RECEIVING_INIT_CHILD_FAILED")
                require(scope.discover() == [], "RECEIVING_INIT_LEFT_DESCENDANTS")
                window.now()
                break
            scope.discover()
            native.time.sleep(.025)
    except BaseException as error:
        owner.error("receiving-canonical-child", error)
    finally:
        # Owner registered each actual return BEFORE its postallocation checks.
        # A failed assignment cannot drop those references or justify a retry.
        roster = _RECEIVING_WINDOWS[id(window)].roster
        try:
            roster.check()  # Capture any original returned row before recovering failed assignments.
        except BaseException as error:
            owner.error("receiving-initializer-resource-roster", error, unknown=True)
        saved = roster.seen[resource_start:]
        scope = scope if scope is not None else next((r for _row, label, r, _a, _c in saved if label == "native-scope"), None)
        out = out if out is not None else next((r for _row, label, r, _a, _c in saved if label == "stdout"), None)
        err = err if err is not None else next((r for _row, label, r, _a, _c in saved if label == "stderr"), None)
        if scope is not None:
            drain_end = None
            try:
                local = time.monotonic()
                row["drainStartedNs"] = window.now(final=True)
                drain_end = min(state.locals[0], O.wire._directed_deadline(local, 120, state.work, row["drainStartedNs"]))
                remaining = max(0, drain_end - time.monotonic())
                grace = min(5, remaining)
                row["survivors"] = scope.drain(grace=grace, kill_wait=min(5, max(0, remaining - grace)), deadline=drain_end)
                row["ownership"] = O.parse(O.encoded(scope.description()))
                require(row["survivors"] == [] and row["ownership"].get("discoveryErrors") == [], "RECEIVING_INIT_DRAIN_UNKNOWN")
                if "preparerIdentity" in row:
                    require(native.preparer_identity(scope, state.clock.role) == row["preparerIdentity"],
                            "RECEIVING_INIT_PREPARER_CHANGED")
                if "leader" in row:
                    native.native_record(row["ownership"], start, row["leader"], argv)
                window.now(final=True)
                native.posix._deadline(drain_end)
                native_known = True
            except BaseException as error:
                owner.error("receiving-initializer-drain", error, unknown=True)
            owner.close_one(scope)
            resource = next(r for r, _label, actual, _a, _c in roster.seen if actual is scope)
            row["scopeCloseAttempted"], row["scopeClosed"] = resource["attempted"], resource["closed"]
            try:
                require(resource["closed"] is True and drain_end is not None, "RECEIVING_INIT_SCOPE_CLOSE")
                window.now(final=True)
                native.posix._deadline(drain_end)
            except BaseException as error:
                native_known = False
                owner.error("receiving-initializer-scope-close", error, unknown=True)
        elif row["scopeAttempted"]:
            owner.error("receiving-initializer-construction", O.OriginError("RECEIVING_INIT_SCOPE_UNKNOWN"), unknown=True)
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
                    owner.error("receiving-initializer-capture", error)
                owner.close_one(stream)
                resource = next(r for r, _label, actual, _a, _c in roster.seen if actual is stream)
                outcome.update(closeAttempted=resource["attempted"], closed=resource["closed"])
                if owner.unknown:
                    break
        else:
            owner.unknown = True
        if row["launchAttempted"] and owner.original is not None:
            # Outer drain cannot prove a failed child's internal supplier close.
            owner.error("receiving-initializer-child-return", owner.original, unknown=True)
    if owner.original is not None:
        raise owner.original
    require(native_known and not owner.unknown and all(outcome[name] is True for outcome in row["captureOutcomes"].values()
        for name in ("synced", "verified", "closeAttempted", "closed")), "RECEIVING_INIT_NATIVE_NOT_RETIRED")
    row["finalizedNs"] = window.now()
    captures = {}
    for name, maximum in (("stdout", native.ACK_LIMIT), ("stderr", native.STDERR_LIMIT)):
        captures[name] = owner.read(directory, name + ".log", maximum)
        row["captureOutcomes"][name]["readback"] = True
    require(captures["stdout"] == native.initialization.stdout_path(str(path / "state"), state.clock.role) and
        captures["stderr"] == b"", "RECEIVING_INIT_STDOUT")
    row.update(retirement="KNOWN", errors=[], captures={name: {"sha256": O.digest(raw), "bytes": len(raw)}
        for name, raw in captures.items()}, readbackCompletedNs=window.now())
    birth, baseline = O.parse(birth_raw), native.baseline_record(baseline_raw, state.clock.role)
    preparer = native.closed_lifetime(row["preparerIdentity"], state.clock.role)
    require(preparer == native.closed_lifetime(birth["preparerIdentity"], state.clock.role) and
        preparer["pid"] != row["leader"]["pid"] and birth["ownership"]["launches"] == row["ownership"]["launches"],
        "RECEIVING_INIT_NATIVE_CHANGED")
    native.native_record(birth["ownership"], start, row["leader"], argv, terminal=False)
    native.native_record(row["ownership"], start, row["leader"], argv)
    if baseline["baseline"] is not None:
        identity = native.lifetime(row["leader"], state.clock.role)
        require(list(identity[:4] if state.clock.role.startswith("macos-") else identity) not in baseline["baseline"],
                "RECEIVING_INIT_PREEXISTING_LEADER")
    times = (state.first, start["startedNs"], row["launchMinimumNs"], birth["observedNs"], row["completedNs"],
        row["drainStartedNs"], row["finalizedNs"], row["readbackCompletedNs"])
    require(all(type(value) is int and 0 <= value < state.work for value in times) and list(times) == sorted(times),
            "RECEIVING_INIT_CHRONOLOGY")
    row_raw = owner.write(directory, "result.json", row)
    result = native.OriginalPhase(context_raw, tuple(sorted({"request.json": inputs.request_raw, "start.json": start_raw,
        "baseline.json": baseline_raw, "native-start.json": birth_raw, "result.json": row_raw,
        "stdout.log": captures["stdout"], "stderr.log": captures["stderr"]}.items())))
    require(owner.phase_originals is None, "RECEIVING_INIT_NATIVE_REUSE")
    owner.phase_originals = result
    return result


@dataclass(frozen=True, repr=False)
class _ReceivingInitialization:
    pending: bytes
    originals: tuple
    native: object


def _initialize_receiving(continuation):
    """Private one-shot canonical initializer; not producer/provider authority."""
    saved = _RECEIVING_CONTINUATIONS.get(id(continuation))
    require(type(continuation) is _ReceivingContinuation and type(saved) is tuple and len(saved) == 3 and
        saved[0] is continuation, "RECEIVING_CONTINUATION_NOT_ORIGINAL")
    window = saved[1]
    state = window.state()
    owner = state.roster.owner
    require(state.inputs is not None and state.continuity is not None and id(continuation) not in _RECEIVING_INIT_ATTEMPTS,
            "RECEIVING_FIXED_INITIALIZER_NOT_CONNECTED_OR_REUSED")
    attempt = (continuation, window, owner, state.authority, state.inputs, state.continuity)
    _RECEIVING_INIT_ATTEMPTS[id(continuation)] = attempt  # Irreversible, BEFORE fallible suppliers.
    child_accepted = False
    try:
        require(continuation.checked() == (owner, window), "RECEIVING_INIT_CONTINUATION_CHANGED")
        _receiving_step_current(window)
        inputs, handles = _receiving_inputs_current(window, absent=True)
        path = _receiving_path()
        context_raw = owner.write(handles["session"], "initializer-context.json", {"schema": 1,
            "scope": "INITIAL_RECIPIENT_CANONICAL_INITIALIZER_CONTEXT_V1", "job": uuid.uuid4().hex,
            "receivingWindowSha256": O.digest(state.raw), "authoritySha256": O.digest(state.authority.raw),
            "senderSha256": state.step[1], "stepSha256": state.step_hash, "requestSha256": O.digest(inputs.request_raw),
            "workerIdentitySha256": O.digest(state.identity_fields[0]), "budgetAcceptance": "NOT_ADMITTED",
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        phase = _receiving_initialize_native(continuation, context_raw)
        files = [(handles["session"], "receiving-window.json", native.LIMIT, state.raw),
            (handles["session"], "initializer-context.json", native.LIMIT, context_raw)]
        files.extend((handles["canonical-init"], name, native.LIMIT, raw) for name, raw in phase.records)
        states = []
        for name in ("state", "gradle-home", "evidence", "cancellations"):
            parent = handles["session"] if name == "state" else states[0][1]
            directory = owner.child(parent, name)
            identity = tuple(native.directory_identity(list(directory.identity), state.clock.role))
            states.append((name, directory, directory.path, identity))
        context = owner.read(states[0][1], "context.json")
        policy = owner.read(states[1][1], "gradle.properties", 16384)
        value = native.initialization.initial_recipient_context_record(context, worker_raw=state.identity_fields[0],
            root=str(ROOT), state=str(path / "state"), role=state.clock.role, outer_job=O.parse(context_raw)["job"],
            homes=inputs.homes, policy_raw=policy)
        require(value["id"] != O.parse(dict(state.originals)["R/recipient-context.json"])["job"],
                "RECEIVING_INIT_CONTEXT_JOB")
        files.extend(((states[0][1], "context.json", native.LIMIT, context),
            (states[1][1], "gradle.properties", 16384, policy)))
        originals = tuple((directory, directory.path,
            tuple(native.directory_identity(list(directory.identity), state.clock.role)), name, maximum, raw)
            for directory, name, maximum, raw in files)
        def reread():
            require(_RECEIVING_INIT_ATTEMPTS.get(id(continuation)) is attempt and window.state().inputs is state.inputs and
                window.state().continuity is state.continuity and owner.phase_originals is phase,
                "RECEIVING_INIT_ORIGINAL_CHANGED")
            for directory, target, identity, name, maximum, raw in originals:
                native._new_entry_owned(owner, directory, target, identity)
                require(owner.read(directory, name, maximum) == raw, "RECEIVING_INIT_ORIGINAL_BYTES_CHANGED")
            for name, directory, target, identity in states:
                native._new_entry_owned(owner, directory, target, identity)
                expected = (("cancellations", "context.json", "evidence", "gradle-home") if name == "state" else
                    ("gradle.properties",) if name == "gradle-home" else ())
                require(native._initializer_names(owner, directory) == expected, "RECEIVING_INIT_STATE_ROSTER")
            require(native._initializer_names(owner, handles["canonical-init"]) == tuple(name for name, _ in phase.records),
                    "RECEIVING_INIT_NATIVE_ROSTER")
            _receiving_step_current(window)
            _receiving_inputs_current(window)
            native._initializer_outputs_absent(owner)
            continuation.checked()
        reread()
        pending = owner.write(handles["session"], "initialization-pending.json", {"schema": 1,
            "scope": "INITIAL_RECIPIENT_CANONICAL_INITIALIZATION_PENDING_OWNER_CLOSE_V1",
            "window": O.parse(state.raw), "stepSha256": state.step_hash, "authoritySha256": O.digest(state.authority.raw),
            "originals": [{"directory": str(target), "directoryIdentity": list(identity), "name": name,
                "sha256": O.digest(raw), "bytes": len(raw)} for _directory, target, identity, name, _maximum, raw in originals],
            "retainedNs": window.now(), "retainedLocal": window.state().local_last,
            "childReturn": "INITIALIZED_CONTEXT_NOT_PRODUCT_RECEIPT", "ownerReturn": "PENDING_OWNER_CLOSE",
            "originalStepOutcome": "NOT_OBSERVED", "budgetAcceptance": "NOT_ADMITTED",
            "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
        reread()
        require(owner.read(handles["session"], "initialization-pending.json") == pending,
                "RECEIVING_INIT_PENDING_CHANGED")
        result = _ReceivingInitialization(pending, originals, phase)
        graph = _history_graph(result.__dict__, originals, phase, state.inputs[0].__dict__, state.continuity[0].__dict__)
        _RECEIVING_INIT_RETURNS[id(result)] = (result, attempt, pending, originals, phase, graph)
        _RECEIVING_WINDOWS[id(window)] = replace(window.state(), initialization=result)
        _receiving_initialization_return(continuation)
        child_accepted = True
        return result
    except BaseException as error:
        owner.error("receiving-fixed-initializer", error, unknown=owner.phase_originals is not None and not child_accepted)
        current = _RECEIVING_WINDOWS.get(id(window))
        if type(current) is _ReceivingState and current.window is window:
            _RECEIVING_WINDOWS[id(window)] = replace(current, failed=True)
        raise owner.original


def _receiving_initialization_return(continuation, *, closed=False):
    saved = _RECEIVING_CONTINUATIONS.get(id(continuation))
    require(type(continuation) is _ReceivingContinuation and type(saved) is tuple and len(saved) == 3 and saved[0] is continuation,
            "RECEIVING_CONTINUATION_NOT_ORIGINAL")
    window, authority = saved[1:]
    state = window.state(cleanup=closed)
    result = state.initialization
    returned = _RECEIVING_INIT_RETURNS.get(id(result))
    require(type(result) is _ReceivingInitialization and type(returned) is tuple and len(returned) == 6 and returned[0] is result,
            "RECEIVING_FIXED_INITIALIZER_NOT_CONNECTED")
    attempt = returned[1]
    require(_RECEIVING_INIT_ATTEMPTS.get(id(continuation)) is attempt and attempt[0] is continuation and attempt[1] is window and
        attempt[2] is state.roster.owner and attempt[3] is authority is state.authority and
        attempt[4] is state.inputs and attempt[5] is state.continuity and
        result.pending == returned[2] and result.originals is returned[3] and result.native is returned[4] and
        state.roster.owner.phase_originals is result.native and not state.failed, "RECEIVING_INIT_RETURN_CHANGED")
    _check_history(returned[5])
    if closed:
        state.roster.known()
        require(state.terminal and not state.busy and state.roster.owner.original is None and state.roster.owner.errors == [],
                "RECEIVING_INIT_CLOSE_NOT_KNOWN")
    else:
        require(not state.terminal, "RECEIVING_INIT_RETIRED")
    return result


def _authority_frame(raw):
    value = O.parse(raw)
    receiving = value.get("scope") == RECEIVING_AUTHORITY_WINDOW_SCOPE
    frame_key = "initializationWindow" if receiving else "recipientWindow"
    require(type(raw) is bytes and raw == O.encoded(value) and set(value) == {"schema", "scope", frame_key,
        "workEndNs", "finalEndNs"} and type(value["schema"]) is int and value["schema"] == 1 and
        value["scope"] == (RECEIVING_AUTHORITY_WINDOW_SCOPE if receiving else AUTHORITY_WINDOW_SCOPE), "AUTHORITY_FRAME")
    if receiving:
        episode, clock, first, end = _receiving_frame(O.encoded(value[frame_key]))
    else:
        episode, clock, first, ends = _recipient_frame(O.encoded(value[frame_key]))
        end = ends[0]
    final = min(O.integer(first + 120 * O.NS), end)
    work = min(O.integer(first + 75 * O.NS), O.integer(final - 45 * O.NS))
    require(first < work and type(value["workEndNs"]) is int and type(value["finalEndNs"]) is int and
            (value["workEndNs"], value["finalEndNs"]) == (work, final), "AUTHORITY_FRAME_FENCES")
    return episode, clock, first, work, final


def _receiving_authority_window(window):
    require(type(window) is _RecipientAuthorityWindow, "AUTHORITY_WINDOW_TYPE")
    return O.parse(window.raw)["scope"] == RECEIVING_AUTHORITY_WINDOW_SCOPE


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
    """Exact HTTP75/120 inside its original recipient240 or receiving-init120."""
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
    def for_receiving(cls, episode):
        require(type(episode) is _ReceivingWindow, "RECEIVING_AUTHORITY_EPISODE")
        outer = episode.state()
        require(outer.phase == "WORK" and outer.raw is not None and outer.roster is not None,
                "RECEIVING_AUTHORITY_NOT_BOUND")
        final = outer.work
        raw = O.encoded({"schema": 1, "scope": RECEIVING_AUTHORITY_WINDOW_SCOPE,
            "initializationWindow": O.parse(outer.raw),
            "workEndNs": min(outer.first + 75 * O.NS, final - 45 * O.NS), "finalEndNs": final})
        return cls._new(raw, outer.roster.first, outer.local_start, outer.cancelled, episode)

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
            outer = (_RECEIVING_WINDOWS if type(state.episode) is _ReceivingWindow else _RECIPIENT_WINDOWS)
            high = current.last if state.episode is None else max(current.last, outer[id(state.episode)].last)
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
        _, phase = _initial_service_phase(owner, private, context_raw, token, window, before)
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


def _receiving_authority(episode, token):
    """Fresh Stage1 source/HTTP acquisition; actual close spends the SAME init120.

    This is a new original native call, not _recipient_authority with a restored
    claim. The historical graph supplies expected values only. All credentials
    stay in the fixed HTTP enclosure and are discarded before continuation.
    """
    require(type(episode) is _ReceivingWindow, "RECEIVING_AUTHORITY_EPISODE")
    outer = episode.state()
    owner = window = evidence = worker_anchor = None
    try:
        observed, _recipient, event = _receiving_current(episode)
        window = _RecipientAuthorityWindow.for_receiving(episode)
        state = window.checked()
        first = outer.first_reading
        owner = native.Owner(state.local_end, window, first=first, cancelled=state.cancelled)
        owner.initial_sources = {}
        window.bind(owner, first)
        path = _receiving_path() / "authority"
        private = owner.new(path)
        owner.write(private, "authority-window.json", window.raw)
        owner.child(private, "control-home", create=True)
        owner.child(private, "temporary", create=True)
        before = source_queries(owner, window, observed, path / "source-before")
        before_pin = _source_pin(before)
        require(dict(before.records) == {name: dict(outer.captured[1])[name] for name in SOURCE_KEYS},
                "RECEIVING_AUTHORITY_SOURCE_CHANGED")
        context_raw = owner.write(private, "context.json", {"schema": 1, "scope": native.INITIAL_RECEIVING_CONTEXT_SCOPE,
            "authorityWindow": O.parse(window.raw), "expectedMatch": O.parse(outer.match_raw),
            "originalProposal": O.parse(outer.proposal_raw), "observed": observed, "eventSha256": O.digest(event),
            "root": str(ROOT), "session": str(path), "job": uuid.uuid4().hex, "inheritedContext": Q._inherited_context(),
            "sourceReturnSha256": O.digest(before.raw), "sourceReturnedNs": O.parse(before.raw)["returnedNs"],
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        _, phase = _initial_service_phase(owner, private, context_raw, token, window, before)
        token = None
        phase_pin = _phase_pin(phase)
        match, _chain, captured, _child = read_phase(owner, private, context_raw, before, phase, window)
        require(match.record == outer.match_raw and _service_job(captured, window.clock) == outer.service_job,
                "RECEIVING_AUTHORITY_JOB_OR_MATCH_CHANGED")
        after = source_queries(owner, window, observed, path / "source-after")
        after_pin = _source_pin(after)
        require(source_readback(owner, path / "source-after", after) == dict(before.records),
                "RECEIVING_AUTHORITY_SOURCE_CHANGED")
        match, chain, captured, (child, session) = read_phase(owner, private, context_raw, before, phase, window)
        require(match.record == outer.match_raw and _service_job(captured, window.clock) == outer.service_job,
                "RECEIVING_AUTHORITY_JOB_OR_MATCH_CHANGED")
        current = initial_identity.bind_worker_match(match, event_raw=event,
            policy_raw=dict(after.records)["candidate_policy_raw"], now=int(time.time()))
        require(_worker_fields(current) == outer.identity_fields, "RECEIVING_AUTHORITY_IDENTITY_CHANGED")
        files = [("authority-window.json", window.raw), ("context.json", context_raw),
            ("service/child-result.json", child), ("acquisition-queries/session-result.json", session)]
        files.extend(("service/" + name, raw) for name, raw in phase.records)
        files.extend(("acquisition-queries/" + name + ".bin", raw) for name, raw in captured[1])
        for name, returned in (("source-before", before), ("source-after", after)):
            files.extend(((name + "/source-return.json", returned.raw), (name + "/session-result.json", returned.session)))
            files.extend((name + "/" + label + ".bin", raw) for label, raw in returned.records)
        originals = tuple(files)
        pending = owner.write(private, "authority-pending.json", {"schema": 1,
            "scope": "INITIAL_RECIPIENT_RECEIVING_AUTHORITY_PENDING_CLOSE_V1", "receivingWindowSha256": O.digest(episode.raw),
            "senderSha256": outer.step[1], "filesSha256": {name: O.digest(raw) for name, raw in originals},
            "originalChain": chain, "retainedNs": window.now(), "retirement": "PENDING_OWNER_CLOSE"})
        evidence = (originals, pending, before, after, phase, captured, match)
        worker_anchor = _capture_worker_authority(episode, window, owner, private, evidence)
        graph = _history_graph(before, after, phase, match, owner.initial_sources)
        require(_source_pin(before)[1:] == before_pin[1:] and _source_pin(after)[1:] == after_pin[1:] and
            _phase_pin(phase)[1:] == phase_pin[1:] and owner.phase_originals is phase and
            set(owner.initial_sources) == {str(path / "source-before"), str(path / "source-after")} and
            owner.initial_sources[str(path / "source-before")] is before and
            owner.initial_sources[str(path / "source-after")] is after, "RECEIVING_AUTHORITY_ORIGINAL_CHANGED")
        _receiving_current(episode)
        preclose = window.now()
    except BaseException as error:
        if owner is None:
            raise
        owner.error("receiving-authority", error)
    finally:
        token = None
        if owner is not None:
            try:
                window.checked(cleanup=True).roster.freeze()
            except BaseException as error:
                owner.error("receiving-authority-close-roster", error, unknown=True)
            try:
                owner.close()
            except BaseException as error:
                owner.error("receiving-authority-owner-close", error)
    try:
        window.checked(cleanup=True).roster.known()
    except BaseException as error:
        owner.error("receiving-authority-close-return", error, unknown=True)
    if owner.original is not None:
        raise owner.original
    require(evidence is not None, "RECEIVING_AUTHORITY_INCOMPLETE")
    _check_history(graph)
    require(owner.phase_originals is phase, "RECEIVING_AUTHORITY_ORIGINAL_CHANGED")
    closed = window.now(final=True, minimum=preclose)
    episode.now(minimum=closed)  # No native FINAL165/READ195 and no fresh120.
    _receiving_current(episode)
    _check_history(graph)
    state = window.checked()
    _AUTHORITY_WINDOWS[id(window)] = replace(state, terminal=True)
    raw = O.encoded({"schema": 1, "scope": "INITIAL_RECIPIENT_RECEIVING_AUTHORITY_CLOSED_HISTORY_V1",
        "receivingWindowSha256": O.digest(episode.raw), "senderSha256": outer.step[1],
        "workerIdentitySha256": O.digest(outer.identity_fields[0]), "matchSha256": O.digest(outer.match_raw),
        "originalProposalSha256": O.digest(outer.proposal_raw), "filesSha256": {name: O.digest(data) for name, data in originals},
        "pendingSha256": O.digest(pending), "originalChain": chain, "preCloseNs": preclose, "closedNs": closed,
        "resourceCount": len(state.roster.rows), "retirement": "KNOWN_RESOURCE_CLOSE_ONLY",
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
    result = _AuthorityReturn(raw)
    require(worker_anchor is not None and not hasattr(owner, "_worker_authority_original_return"),
            "WORKER_AUTHORITY_RETURN_REUSE")
    owner._worker_authority_original_return = (result, raw)
    nodes = _history_graph(result, _AUTHORITY_WINDOWS[id(window)], evidence)
    _AUTHORITY_RETURNS[id(result)] = (result, raw, episode, window, nodes, originals)
    _authority_return(result, episode)
    _register_worker_authority(result, episode, worker_anchor)
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


CRYPTO_ORIGINALS_SCOPE = "INITIAL_RECIPIENT_CRYPTO_ORIGINAL_INVENTORY_V1"
CRYPTO_SIDECAR_SCOPE = "INITIAL_RECIPIENT_CRYPTO_ORIGINALS_PENDING_OWNER_CLOSE_V1"
CRYPTO_ORIGINALS_FILE = "crypto-originals.json"
CRYPTO_ORIGINALS_LIMIT = 16 * 1024 * 1024


@dataclass(frozen=True, repr=False)
class _RecipientCryptoOriginals:
    """Original hashes/pins only; not a live Recipient or a copied evidence tree."""
    raw: bytes
    phase: _RecipientNativeReturn
    directories: tuple


def _capture_recipient_crypto_originals(owner, root, phase, window):
    """Fixed shallow inventory AFTER native readback, inside original READ30.

    The original parent owns root; a later custody owner must copy the actual
    bytes. No retired owner, Snapshot, arbitrary path or recursive scan enters.
    """
    saved = _RECIPIENT_NATIVE_RETURNS.get(id(phase))
    require(type(owner) is native.Owner and owner.fence is window and owner.phase_originals is phase and
        type(phase) is _RecipientNativeReturn and type(saved) is tuple and len(saved) == 6 and
        saved[0] is phase and saved[1] is owner and saved[2] is window and phase.context == saved[3] and
        phase.records is saved[4] and phase.child == saved[5] and window.state().phase == "READ" and
        not owner.closed and not owner.unknown and owner.original is None and owner.errors == [],
        "CRYPTO_ORIGINAL_NATIVE_RETURN")
    context = O.parse(phase.context)
    role = window.clock.role
    require(root.path == Path(context["session"]) / "crypto" and
        tuple(root.identity) == tuple(context["directories"]["crypto"]) and
        any(row["owner"] is root and row["label"] == "directory" and not row["attempted"] and not row["closed"]
            for row in owner.resources), "CRYPTO_ORIGINAL_ROOT")
    names = native._initializer_names(owner, root)
    for name in names:
        Q._component(name)
    windows = role == "windows-x64"
    operations = tuple(name for name in names if re.fullmatch(
        r"gpg-[0-9a-f]{32}" if windows else r"gpg-[a-z0-9_]+", name))
    results = tuple(name for name in names if re.fullmatch(r"recipient-validation-result-[0-9a-f]{32}\.json", name))
    require(len(operations) == (3 if windows else 2) and len(results) == (1 if windows else 0) and
        set(names) == {"recipient.asc", "recipient.gpg", "gnupg", "tmp", *operations, *results},
        "CRYPTO_ORIGINAL_ROOT_ROSTER")
    pins, records, total = [], [], 0

    def pin(relative, directory, roster):
        directory.verify()
        identity = tuple(native.directory_identity(list(directory.identity), role))
        pins.append((relative, directory, str(directory.path), identity, roster))

    def read(directory, name, maximum):
        owner.end(final=True)
        Q._component(name)
        # Do not open-first to classify a FIFO. Native read still performs its
        # original per-open identity/privacy/size/close checks on regular files.
        if not windows:
            require(stat.S_ISREG((directory.path / name).lstat().st_mode), "CRYPTO_ORIGINAL_REGULAR_FILE")
        return owner.read(directory, name, maximum, final=True)

    def record(relative, directory, name, maximum):
        nonlocal total
        raw = read(directory, name, maximum)
        if relative == "recipient.asc":
            require(O.digest(raw) == O.parse(phase.child)["recipient"]["key_sha256"], "CRYPTO_ORIGINAL_KEY_CHANGED")
        elif relative == "recipient.gpg":
            require(len(raw) > 0, "CRYPTO_ORIGINAL_EMPTY_RING")
        total += len(raw)
        require(total <= CRYPTO_ORIGINALS_LIMIT, "CRYPTO_ORIGINAL_TOTAL_LIMIT")
        records.append((relative, len(raw), O.digest(raw), directory, name, maximum))

    pin("", root, names)
    for name in ("recipient.asc", "recipient.gpg"):
        record(name, root, name, native.posix.MAX_KEY_BYTES)
    for name in results:
        record(name, root, name, native.diagnostics.MAX_RECORD_BYTES)
    for name in ("gnupg", "tmp", *operations):
        directory = owner.child(root, name, final=True)
        roster = native._initializer_names(owner, directory)
        if name in ("gnupg", "tmp"):
            require(not windows or roster == (), "CRYPTO_ORIGINAL_WINDOWS_HOME_NOT_EMPTY")
        else:
            require(roster == tuple(sorted(("stdout", "stderr") if windows else
                ("stdout", "stderr", "status", "process.json"))), "CRYPTO_ORIGINAL_OPERATION_ROSTER")
        pin(name, directory, roster)
        for member in roster:
            maximum = native.LIMIT if name in ("gnupg", "tmp") or member == "process.json" else native.posix.MAX_DIAGNOSTIC_BYTES
            record(name + "/" + member, directory, member, maximum)
    for _relative, directory, path, identity, roster in pins:
        require(str(directory.path) == path and tuple(directory.identity) == identity and
            native._initializer_names(owner, directory) == roster, "CRYPTO_ORIGINAL_DIRECTORY_CHANGED")
    for _relative, count, digest, directory, name, maximum in records:
        raw = read(directory, name, maximum)
        require(len(raw) == count and O.digest(raw) == digest, "CRYPTO_ORIGINAL_BYTES_CHANGED")
    for _relative, directory, path, identity, roster in pins:
        require(str(directory.path) == path and tuple(directory.identity) == identity and
            native._initializer_names(owner, directory) == roster, "CRYPTO_ORIGINAL_DIRECTORY_CHANGED")
    require(_RECIPIENT_NATIVE_RETURNS.get(id(phase)) is saved and owner.phase_originals is phase and
        phase.context == saved[3] and phase.records is saved[4] and phase.child == saved[5],
        "CRYPTO_ORIGINAL_NATIVE_RETURN_CHANGED")
    raw = O.encoded({"schema": 1, "scope": CRYPTO_ORIGINALS_SCOPE, "root": str(root.path),
        "contextSha256": O.digest(phase.context), "childSha256": O.digest(phase.child),
        "phaseSha256": {name: O.digest(data) for name, data in phase.records}, "clock": O.clock_value(window.clock),
        "readEndNs": window.state().read_end, "readLocalCeiling": window.state().read_local, "capturedNs": window.now(),
        "directories": [{"relative": relative, "identity": list(identity), "members": list(roster)}
            for relative, _directory, _path, identity, roster in pins],
        "files": [{"relative": relative, "bytes": count, "sha256": digest}
            for relative, count, digest, _directory, _name, _maximum in sorted(records)], "totalBytes": total,
        "copyState": "ORIGINAL_BYTES_NOT_COPIED", "liveRecipient": "NOT_TRANSFERRED",
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
    return _RecipientCryptoOriginals(raw, phase, tuple(pins))


def _checked_recipient_crypto_originals(result):
    """Passive successful-return binding; never observe/reopen a retired owner."""
    check_recipient_validation_return(result)
    saved = _RECIPIENT_CRYPTO_ORIGINALS.get(id(result))
    require(type(saved) is tuple and len(saved) == 7 and saved[0] is result and
        _RECIPIENT_RETURNS.get(id(result)) is saved[1] and type(saved[2]) is _RecipientCryptoOriginals and
        type(saved[2].raw) is bytes and saved[2].raw == saved[3] and saved[2].phase is saved[4] is saved[1][6] and
        saved[2].directories is saved[5], "CRYPTO_ORIGINAL_RETURN_CHANGED")
    require(sum(node[0] is saved[2] and node[1] is _RecipientCryptoOriginals and node[2] == "record"
        for node in saved[1][4]) == 1, "CRYPTO_ORIGINAL_PARENT_BINDING")
    _check_history(saved[6])
    for _relative, directory, path, identity, _roster in saved[5]:
        require(str(directory.path) == path and tuple(directory.identity) == identity, "CRYPTO_ORIGINAL_PIN_CHANGED")
    return saved[3]


def _crypto_originals_path():
    path = _recipient_path()
    return path.with_name(path.name + "-crypto-originals")


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
    crypto = crypto_originals = crypto_graph = None
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
            if name == "crypto":
                crypto = child  # Original parent resource, not a later path-only reopen.
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
        crypto_originals = _capture_recipient_crypto_originals(owner, crypto, phase, window)
        crypto_graph = _history_graph(crypto_originals)  # Freeze the actual return before another fallible supplier.
        final_source = source_queries(owner, window, observed, path / "source-final")
        graph = phase_graph + crypto_graph + _history_graph(final_source, authority, owner.initial_sources)
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
    check_recipient_validation_return(returned)
    require(type(crypto_originals) is _RecipientCryptoOriginals and crypto_originals.phase is phase,
            "CRYPTO_ORIGINAL_PARENT_INCOMPLETE")
    _RECIPIENT_CRYPTO_ORIGINALS[id(returned)] = (returned, _RECIPIENT_RETURNS[id(returned)], crypto_originals,
        crypto_originals.raw, phase, crypto_originals.directories, crypto_graph)
    _checked_recipient_crypto_originals(returned)
    return returned


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


def _sender_step(cancelled):
    """Prepare a private lower-bound sidecar BEFORE guarded's two final checks."""
    native.cancellation(cancelled)
    boot = continuity.boot_digest(O.clocks.processes.host_role())
    returned = validate_recipient(cancelled)  # Accepted sender body and its final-only fence are unchanged.
    return _retain_sender_step(returned, cancelled, boot)


def _retain_sender_step(returned, cancelled, initial_boot):
    require(type(returned) is tuple and len(returned) == 3, "STEP_SENDER_ORIGINAL_RETURN")
    value, sender, hard = returned
    candidates = [row for row in _RECIPIENT_SENDERS.values() if type(row) is tuple and len(row) == 3 and row[2] is sender]
    require(len(candidates) == 1, "STEP_SENDER_NOT_ORIGINAL")
    original_attempt = candidates[0]
    result, saved, _ = original_attempt
    crypto_raw = _checked_recipient_crypto_originals(result)
    crypto_registry, crypto_binding = _RECIPIENT_CRYPTO_ORIGINALS, _RECIPIENT_CRYPTO_ORIGINALS[id(result)]
    state = saved[3]
    _binding, original = _recipient_claim(state.claim)
    clock, last, cap = sender.clock, O.integer(sender.last), sender.local_end
    require(clock is state.clock and type(hard) is int and hard == state.read_end and last < hard and
        type(cap) is float and cap == state.read_local and math.isfinite(cap) and
        type(value) is dict and set(value) == {"scope", "recipientSenderSha256", "budgetAcceptance", "testAcceptance",
            "exportSaveAuthority"} and value["scope"] == RECIPIENT_OUTPUT_SCOPE and
        value["budgetAcceptance"] == "NOT_ADMITTED" and value["testAcceptance"] == "NOT_PERFORMED" and
        value["exportSaveAuthority"] is False and re.fullmatch(r"[0-9a-f]{64}", value["recipientSenderSha256"]),
        "STEP_SENDER_BINDINGS")
    value_graph = _history_graph(value, clock)
    claim = (returned, original_attempt, cancelled, clock, hard, cap, value_graph)
    require(id(sender) not in _SENDER_STEP_ATTEMPTS, "STEP_SENDER_ALREADY_CLAIMED")
    _SENDER_STEP_ATTEMPTS[id(sender)] = claim  # Before metadata/clock/native suppliers.
    local_last = state.local_last
    owner = roster = None
    phase, busy, failed, final_checks = "METADATA", False, False, 0
    failure, closed_graph = None, None

    def remember(error):
        nonlocal failed, failure
        failed = True
        if failure is None:
            failure = owner.original if owner is not None and owner.original is not None else error
        if owner is not None:
            owner.error("sender-step", error)

    def pins(*, closing=False):
        if roster is not None:
            roster.check()
        if closing:
            return
        require(_SENDER_STEP_ATTEMPTS.get(id(sender)) is claim and _RECIPIENT_SENDERS.get(id(result)) is original_attempt and
            _RECIPIENT_RETURNS.get(id(result)) is saved and sender.clock is clock and sender.local_end == cap and
            not failed and O.wire.TOKEN_ENV not in os.environ and not continuity.QUARANTINE and
            not native.QUARANTINE and not Q.QUARANTINE and not native.diagnostics._QUARANTINE,
            "STEP_SENDER_BINDING_CHANGED")
        require(_RECIPIENT_CRYPTO_ORIGINALS is crypto_registry and crypto_registry.get(id(result)) is crypto_binding and
            _checked_recipient_crypto_originals(result) == crypto_raw, "STEP_CRYPTO_ORIGINALS_CHANGED")
        _check_history(value_graph)
        if owner is not None:
            require(owner.original is None and not owner.unknown and owner.errors == [], "STEP_METADATA_OWNER_FAILED")
        if phase in ("FILE_OUTPUT", "HANDOFF", "COMPLETE"):
            roster.known()
            require(closed_graph is not None, "STEP_METADATA_CLOSE_REQUIRED")
            _check_history(closed_graph)

    def local_sample():
        nonlocal local_last
        local = time.monotonic()
        require(type(local) in (int, float) and math.isfinite(local) and local >= local_last,
                "STEP_LOCAL_BACKWARDS")
        local_last = local
        require(local < cap, "STEP_ORIGINAL_READ_EXPIRED")
        return local

    class StepFence:
        __slots__ = ()
        clock = property(lambda _self: clock)
        last = property(lambda _self: last)
        local_end = property(lambda _self: cap)

        def now(self, *, final=False, minimum=0, limit=None):
            nonlocal last, busy, phase, final_checks
            require(self is fence, "STEP_METADATA_NOT_ORIGINAL")
            if busy:
                error = I.AdmissionError("STEP_METADATA_REENTRY")
                remember(error)
                raise error
            busy = True
            try:
                require(type(final) is bool and phase != "COMPLETE" and
                    (phase == "CLOSING" and final or not failed), "STEP_METADATA_NOT_LIVE")
                end = hard if limit is None else min(hard, O.integer(limit))
                minimum = max(last, O.integer(minimum))
                pins(closing=phase == "CLOSING")
                local_sample()
                if phase == "HANDOFF":
                    require(final and final_checks < 2, "STEP_SENDER_FINAL_ONLY")
                    # Exactly the ORIGINAL two OUTPUT calls. Never its deadline,
                    # a third now, or any state restoration after guarded.
                    final_checks += 1
                    observed = sender.now(final=True, minimum=minimum, limit=end)
                    require(type(observed) is int and minimum <= observed < end, "STEP_SENDER_HIGHWATER")
                    last = observed
                    local_sample()
                    pins()
                    if final_checks == 2:
                        phase = "COMPLETE"
                    return observed
                for index in range(1 if final else 2):
                    last = O.clocks.checked_now(clock, minimum_ns=max(last, minimum))
                    local_sample()
                    require(last < end, "STEP_ORIGINAL_READ_EXPIRED")
                    pins(closing=phase == "CLOSING")
                    if not final and index == 0:
                        state.cancelled()
                        native.cancellation(cancelled)
                        local_sample()
                return last
            except BaseException as error:
                remember(error)
                raise
            finally:
                busy = False

        def deadline(self, maximum, *, final=False, limit=None):
            require(self is fence, "STEP_METADATA_NOT_ORIGINAL")
            try:
                require(phase == "METADATA" and type(maximum) in (int, float) and
                    math.isfinite(maximum) and 0 < maximum <= 45, "STEP_METADATA_IO_ONLY")
                local = local_sample()
                observed = self.now(final=final, limit=limit)
                end = hard if limit is None else min(hard, O.integer(limit))
                return min(cap, O.wire._directed_deadline(local, maximum, end, observed))
            except BaseException as error:
                remember(error)  # A failed original deadline cannot revive as final sender handoff.
                raise

    fence = StepFence()
    raw = crypto_sidecar = None
    try:
        fence.now()
        require(continuity.boot_digest(clock.role) == initial_boot, "STEP_SENDER_BOOT_CHANGED")
        fence.now()
        first = O.clocks.Reading(clock, last)
        owner = native.Owner(cap, fence, first=first, cancelled=state.cancelled)
        owner.initial_sources = {}
        roster = _RecipientRoster(owner, fence, first)
        path = _step_path()
        directory = owner.new(path)
        identity = tuple(native.directory_identity(list(directory.identity), clock.role))
        native._new_entry_owned(owner, directory, path, identity)
        require(native._initializer_names(owner, directory) == (), "STEP_METADATA_NOT_EMPTY")
        observed, _recipient, event = _recipient_host(O.parse(original.match_raw)["firstUseAt"])
        require(observed == O.parse(original.worker_originals[0])["observed"] and event == original.identity_fields[1],
                "STEP_SENDER_HOST_CHANGED")
        service_job = _service_job(original.worker_originals, clock)
        lower = fence.now()
        raw = O.encoded({"schema": 1, "scope": continuity.STEP_SCOPE, "directory": str(path),
            "directoryIdentity": list(identity), "senderSha256": value["recipientSenderSha256"], "observed": observed,
            "serviceJob": list(service_job), "workerIdentitySha256": O.digest(original.identity_fields[0]),
            "originalProposalSha256": O.digest(original.proposal_raw), "clock": O.clock_value(clock),
            "bootSha256": initial_boot, "lowerNs": lower, "lowerLocal": local_last, "readEndNs": hard,
            "readLocalCeiling": cap, "sample": "AFTER_SENDER_FUNCTION_BEFORE_GUARDED_OUTPUT_AND_STEP_RETURN",
            "writerReturn": "PENDING_OWNER_CLOSE", "originalStepOutcome": "NOT_OBSERVED",
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        _step_record(raw)
        owner.write(directory, continuity.STEP_FILE, raw)
        require(owner.read(directory, continuity.STEP_FILE, continuity.STEP_LIMIT) == raw and
            native._initializer_names(owner, directory) == (continuity.STEP_FILE,), "STEP_METADATA_CHANGED")
        native._new_entry_owned(owner, directory, path, identity)
        crypto_path = _crypto_originals_path()
        crypto_directory = owner.new(crypto_path)
        crypto_identity = tuple(native.directory_identity(list(crypto_directory.identity), clock.role))
        native._new_entry_owned(owner, crypto_directory, crypto_path, crypto_identity)
        require(native._initializer_names(owner, crypto_directory) == (), "STEP_CRYPTO_DIRECTORY_NOT_EMPTY")
        crypto_sidecar = owner.write(crypto_directory, CRYPTO_ORIGINALS_FILE, {"schema": 1, "scope": CRYPTO_SIDECAR_SCOPE,
            "directory": str(crypto_path), "directoryIdentity": list(crypto_identity),
            "recipientValidationSha256": O.digest(result.raw), "recipientSenderSha256": value["recipientSenderSha256"],
            "recipientStepSha256": O.digest(raw), "inventory": O.parse(crypto_raw),
            "writerReturn": "PENDING_OWNER_CLOSE", "originalStepOutcome": "NOT_OBSERVED",
            "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
        require(owner.read(crypto_directory, CRYPTO_ORIGINALS_FILE) == crypto_sidecar and
            native._initializer_names(owner, crypto_directory) == (CRYPTO_ORIGINALS_FILE,), "STEP_CRYPTO_ORIGINALS_CHANGED")
        native._new_entry_owned(owner, crypto_directory, crypto_path, crypto_identity)
        pins()
    except BaseException as error:
        remember(error)
    finally:
        phase = "CLOSING"
        if owner is not None:
            try:
                roster.freeze()
            except BaseException as error:
                owner.error("step-close-roster", error, unknown=True)
                remember(error)
            try:
                owner.close()
                roster.known()
            except BaseException as error:
                owner.error("step-close", error, unknown=True)
                remember(error)
            if failure is None:
                failure = owner.original
            if owner.unknown and not any(value is owner for value in native.QUARANTINE):
                native.QUARANTINE.append(owner)
    if failure is not None:
        raise failure
    try:
        require(owner is not None and raw is not None and crypto_sidecar is not None and not failed, "STEP_METADATA_INCOMPLETE")
        closed_graph = _history_graph(owner, roster)
        phase = "FILE_OUTPUT"
        continuity.append_outputs({"recipientSenderSha256": value["recipientSenderSha256"],
            "recipientStepSha256": O.digest(raw), "recipientCryptoOriginalsSha256": O.digest(crypto_sidecar)}, fence.now)
        pins()
        phase = "HANDOFF"
        return value, fence, hard
    except BaseException as error:
        remember(error)
        raise failure


def _worker_registries():
    # Container identity, not a mutable registry's assertion about itself.
    return (_RECEIVING_WINDOWS, _RECEIVING_CONTINUATIONS, _RECEIVING_INIT_ATTEMPTS, _RECEIVING_INIT_RETURNS,
        _RECEIVING_CLOSED_RETURNS, _AUTHORITY_WINDOWS, _AUTHORITY_RETURNS, _WORKER_READER_CAPTURES,
        _WORKER_AUTHORITY_CAPTURES, _WORKER_AUTHORITY_RETURNS, _WORKER_CRYPTO_CAPTURES,
        _WORKER_ORIGINAL_CAPTURES, _WORKER_HANDOFF_ATTEMPTS)


def _worker_owner_binding(owner, roster):
    """Save references only; the existing roster owns allocation/close flags."""
    return (owner.__dict__, roster.__dict__, owner.resources, owner.errors, owner.initial_sources, roster.seen,
        owner.first, owner.cancelled, owner.local_end, owner.early_last)


def _worker_owner_current(owner, window, roster, binding, *, closed=False, cleanup=False):
    dictionary, roster_dictionary, rows, errors, sources, seen, first, cancel, local, early = binding
    require(type(owner) is native.Owner and type(roster) is _RecipientRoster and owner.__dict__ is dictionary and
        roster.__dict__ is roster_dictionary and owner.resources is rows is roster.rows and
        owner.errors is errors is roster.errors and owner.initial_sources is sources is roster.sources and
        roster.seen is seen and roster.owner is owner and owner.fence is window is roster.window and
        owner.first is first is roster.first and owner.cancelled is cancel is roster.cancelled and
        type(owner.local_end) is float and owner.local_end == local == roster.local and
        type(owner.early_last) is int and owner.early_last == early and
        owner.work_limit is None and owner.final_limit is None, "WORKER_ORIGINAL_OWNER_CHANGED")
    roster.check()
    if cleanup:
        return  # Preserve actual cleanup even after an earlier non-ownership failure.
    require(owner.closed is closed and owner.unknown is False and owner.original is None and errors == [],
            "WORKER_ORIGINAL_OWNER_FAILED")
    if closed:
        roster.known()


def _worker_pins(owner, role, targets):
    """Actual ledger pins only; never open a declared/closed query directory."""
    found, pins = {}, []
    for row in tuple(owner.resources):
        require(type(row) is dict, "WORKER_ORIGINAL_RESOURCE_ROW")
        if row.get("label") != "directory":
            continue
        directory = row["owner"]
        require(type(directory) is (native.windows.PrivateDirectory if role == "windows-x64" else Q._PosixDirectory),
                "WORKER_ORIGINAL_DIRECTORY_TYPE")
        matches = [key for key, path in targets.items() if directory.path == path]
        if not matches:
            continue
        require(len(matches) == 1 and row["attempted"] is False and row["closed"] is False,
                "WORKER_ORIGINAL_DIRECTORY_LIVE")
        key, path = matches[0], directory.path
        identity = tuple(native.directory_identity(list(directory.identity), role))
        require(key not in found or found[key] == identity, "WORKER_ORIGINAL_REPEATED_PIN")
        found[key] = identity
        pins.append((key, row, directory, path, identity))
    require(set(found) == set(targets) and len(set(found.values())) == len(found), "WORKER_ORIGINAL_PIN_ROSTER")
    return tuple(pins)


def _check_worker_pins(pins, role, *, closed=False):
    for _key, row, directory, path, identity in pins:
        current = tuple(directory.identity)
        require(type(directory) is (native.windows.PrivateDirectory if role == "windows-x64" else Q._PosixDirectory) and
            row["label"] == "directory" and row["owner"] is directory and directory.path is path and
            len(current) == len(identity) == 2 and current == identity and
            all(type(a) is type(b) for a, b in zip(current, identity)) and
            (directory._closed if role == "windows-x64" else directory.closed) is closed and
            row["attempted"] is closed and row["closed"] is closed, "WORKER_ORIGINAL_PIN_CHANGED")


def _worker_relative(name):
    require(type(name) is str and name.split("/", 1)[0] in ("P", "E", "R", "S", "I", "T", "C"),
            "WORKER_ORIGINAL_LOGICAL_PATH")
    for part in name.split("/")[1:]:
        Q._component(part)
    return name


def _worker_file(name, maximum, count, digest, provenance):
    _worker_relative(name)
    require("/" in name and type(maximum) is int and type(count) is int and
        0 <= count <= maximum <= native.LIMIT and maximum > 0 and
        type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) and
        (count != 0 or digest == O.digest(b"")) and provenance in
        ("ACTUAL_RETAINED_BYTES", "ORIGINAL_AUTHORITY_QUERY_DECLARATION", "AUTHENTICATED_CRYPTO_DECLARATION"),
        "WORKER_ORIGINAL_FILE")
    return {"relative": name, "parent": name.rsplit("/", 1)[0], "maximum": max(1, count),
        "bytes": count, "sha256": digest, "provenance": provenance}


@dataclass(frozen=True, repr=False)
class _WorkerReaderCapture:
    # Opaque to _history_graph(owner): future ledger additions must stay live.
    owner: object
    window: object
    originals: tuple
    roots: tuple
    directories: tuple
    pins: tuple
    prefix: tuple
    step: object
    authority_check: object


def _capture_worker_reader(window, owner, private, sender, originals, step, authority_check):
    """Called immediately after the one accepted1066 return, without live I/O."""
    state, registries = _RECEIVING_WINDOWS.get(id(window)), _worker_registries()
    require(type(state) is _ReceivingState and state.window is window and state.roster.owner is owner and
        state.raw is None and state.originals == () and state.continuity is step, "WORKER_READER_NOT_NEW")
    roster, binding = state.roster, _worker_owner_binding(owner, state.roster)
    prefix = tuple((row, row.get("label"), row.get("owner")) for row in owner.resources if type(row) is dict)
    require(callable(authority_check), "WORKER_READER_AUTHORITY_CHECK")
    step_pin = None
    if step is not None:
        require(type(step) is tuple and len(step) == 2 and type(step[0]) is _ReceivingStep,
                "WORKER_READER_STEP")
        original_step = step[0]
        step_pin = (original_step, original_step.__dict__, original_step.raw, original_step.directory,
            original_step.path, original_step.identity, original_step.boot)
    # This is the original tuple object, not an equality-tested copy. Freeze it
    # and the original first/step/path graph before parsing or any later supplier.
    graph = _history_graph(originals, state.first_reading, private.path, sender.path,
        () if step is None else step[0].__dict__)
    require(type(originals) is tuple and len(originals) == 1066 and
        all(type(row) is tuple and len(row) == 2 and type(row[0]) is str and type(row[1]) is bytes for row in originals) and
        len(dict(originals)) == 1066 and sum(len(raw) for _key, raw in originals) <= Q.MAX_SESSION_BYTES,
        "WORKER_READER_ORIGINAL_TUPLE")
    recipient = sender.path.with_name(sender.path.name.removesuffix("-output"))
    preparation = recipient.with_name(recipient.name.removesuffix("-recipient"))
    roots = (("P", preparation), ("E", preparation.with_name(preparation.name + "-entry")), ("R", recipient),
        ("S", sender.path), ("I", private.path), ("T", recipient.with_name(recipient.name + "-step")),
        ("C", recipient.with_name(recipient.name + "-crypto-originals")))
    require(sender.path.name == recipient.name + "-output" and recipient.name == preparation.name + "-recipient" and
        private.path == recipient.with_name(recipient.name + "-initializer"), "WORKER_READER_ROOTS")
    raw = dict(originals)
    require(O.parse(raw["P/context.json"])["session"] == str(preparation) and
        O.parse(raw["R/recipient-context.json"])["session"] == str(recipient), "WORKER_READER_CONTEXT_ROOTS")
    counts = {key: 0 for key in ("P", "E", "R", "S")}
    for name, data in originals:
        _worker_relative(name)
        require(name.split("/", 1)[0] in counts and "/" in name and len(data) <= native.LIMIT,
                "WORKER_READER_FILE")
        counts[name.split("/", 1)[0]] += 1
    require(counts == {"P": 284, "E": 281, "R": 498, "S": 3} and
        len({key.casefold() for key in raw}) == 1066, "WORKER_READER_GROUPS")
    query_roots = tuple(group + "/" + name for group in ("P", "E", "R/authority")
        for name in ("source-before", "acquisition-queries", "source-after")) + (
        "R/recipient-validation/source-before", "R/recipient-validation/source-after", "R/source-final")
    directories = {name.rsplit("/", 1)[0] for name in raw}
    directories.update(group + "/" + name for group in ("P", "E", "R/authority", "R")
        for name in ("control-home", "temporary"))
    directories.update(name + "/query-home" for name in query_roots)
    directories.add("R/crypto")
    directories = tuple(sorted(directories))
    require(len(directories) == 222 and all(name + "/session-result.json" in raw for name in query_roots) and
        {key: sum(name.split("/", 1)[0] == key for name in directories) for key in counts} ==
        {"P": 58, "E": 58, "R": 105, "S": 1}, "WORKER_READER_DIRECTORY_ROSTER")
    paths = dict(roots)
    targets = {name: paths[name.split("/", 1)[0]].joinpath(*name.split("/")[1:]) for name in directories}
    targets["I"] = private.path
    if step is not None:
        require(type(step) is tuple and len(step) == 2 and type(step[0]) is _ReceivingStep, "WORKER_READER_STEP")
        targets["T"] = paths["T"]
    pins = _worker_pins(owner, state.clock.role, targets)
    require(len(pins) == len(targets) and len(prefix) == len(owner.resources), "WORKER_READER_PIN_COUNT")
    graph += _history_graph(roots, directories, tuple(path for _key, _row, _dir, path, _id in pins))
    capture = _WorkerReaderCapture(owner, window, originals, roots, directories, pins, prefix, step, authority_check)
    anchor = (capture, owner, window, originals, roots, directories, pins, prefix, step, roster, binding, graph,
        registries, state.first_reading, state.clock, state.clock_raw, state.local_start, state.step, state.step_hash,
        step_pin, authority_check)
    require(id(window) not in _WORKER_READER_CAPTURES and not hasattr(owner, "_worker_reader_capture"),
            "WORKER_READER_REUSE")
    owner._worker_reader_capture = capture
    _WORKER_READER_CAPTURES[id(window)] = anchor
    _check_worker_reader(anchor, bound=False)
    return anchor


def _check_worker_reader(anchor, *, bound=True, closed=False):
    require(type(anchor) is tuple and len(anchor) == 21, "WORKER_READER_BINDING")
    capture, owner, window, originals, roots, directories, pins, prefix, step, roster, binding, graph, registries, \
        first, clock, clock_raw, local_start, original_step, step_hash, step_pin, authority_check = anchor
    require(type(capture) is _WorkerReaderCapture and owner._worker_reader_capture is capture and
        _WORKER_READER_CAPTURES.get(id(window)) is anchor and
        len(registries) == len(_worker_registries()) and
        all(current is saved for current, saved in zip(_worker_registries(), registries)) and
        capture.owner is owner and capture.window is window and capture.originals is originals and capture.roots is roots and
        capture.directories is directories and capture.pins is pins and capture.prefix is prefix and capture.step is step and
        capture.authority_check is authority_check and callable(authority_check),
        "WORKER_READER_CAPTURE_CHANGED")
    if step is None:
        require(step_pin is None, "WORKER_READER_STEP_CHANGED")
    else:
        saved, dictionary, raw, directory, path, identity, boot = step_pin
        require(type(step) is tuple and len(step) == 2 and step[0] is saved and type(saved) is _ReceivingStep and
            saved.__dict__ is dictionary and set(dictionary) == {"raw", "directory", "path", "identity", "boot"} and
            type(saved.raw) is bytes and saved.raw == raw and saved.directory is directory and saved.path is path and
            saved.identity is identity and type(saved.boot) is str and saved.boot == boot,
            "WORKER_READER_STEP_CHANGED")
    state = _RECEIVING_WINDOWS.get(id(window))
    require(type(state) is _ReceivingState and state.window is window and state.roster is roster and
        state.first_reading is first and state.clock is clock and type(state.clock_raw) is bytes and state.clock_raw == clock_raw and
        type(state.local_start) is float and state.local_start == local_start and state.continuity is step and
        state.step is original_step and state.step_hash == step_hash and
        (os.environ.get(RECEIVING_OUTCOME_ENV), os.environ.get(RECEIVING_HASH_ENV)) == original_step and
        os.environ.get(continuity.STEP_HASH_ENV) == step_hash and O.wire.TOKEN_ENV not in os.environ,
        "WORKER_READER_RECEIVING_CHANGED")
    _worker_owner_current(owner, window, roster, binding, closed=closed)
    require(len(owner.resources) >= len(prefix) and all(row is saved and row["label"] == label and row["owner"] is resource
        for row, (saved, label, resource) in zip(owner.resources, prefix)), "WORKER_READER_LEDGER_CHANGED")
    _check_history(graph)
    _check_worker_pins(pins, clock.role, closed=closed)
    authority_check()  # None only before the genuine authority call returns.
    if bound:
        require(state.originals is originals and type(state.raw) is bytes, "WORKER_READER_TUPLE_REPLACED")
        frame, bound_clock, began, work = _receiving_frame(state.raw)
        raw = dict(originals)
        require(bound_clock == clock and began == first.nanoseconds == state.first and work == state.work and
            state.locals == (min(binding[8], O.wire._directed_deadline(local_start, 120, work, began)),) and
            frame["senderSha256"] == O.digest(raw["S/sender-pending.json"]) == original_step[1] and
            frame["workerIdentitySha256"] == O.digest(raw["P/worker-identity.json"]) and
            state.identity_fields[:4] == (raw["P/worker-identity.json"], raw["P/acquisition-queries/event.bin"],
                raw["P/acquisition-queries/candidate_policy_raw.bin"], raw["R/recipient-public.asc"]) and
            state.match_raw == raw["P/acquisition-queries/match.bin"] and
            state.proposal_raw == raw["P/worker-allocation-proposal.json"] and
            state.observed_raw == O.encoded(O.parse(raw["P/context.json"])["observed"]), "WORKER_READER_BOUND_ORIGINALS")
    return capture


@dataclass(frozen=True, repr=False)
class _WorkerAuthorityCapture:
    owner: object
    window: object
    episode: object
    evidence: tuple
    files: tuple
    directories: tuple
    pins: tuple


def _capture_worker_authority(episode, window, owner, private, evidence):
    """281 declarations/available raws from THIS authority, before its close."""
    state, registries = _AUTHORITY_WINDOWS[id(window)], _worker_registries()
    roster, binding = state.roster, _worker_owner_binding(owner, state.roster)
    originals, pending, before, after, phase, captured, match = evidence
    graph = _history_graph(evidence, private.path, state.roster.first)
    path = private.path
    require(state.episode is episode and owner.phase_originals is phase and type(evidence) is tuple and
        type(pending) is bytes and 0 < len(pending) <= native.LIMIT and
        type(originals) is tuple and len(originals) == len(dict(originals)) == 37 and
        type(before) is SourceReturn and type(after) is SourceReturn and type(phase) is native.OriginalPhase and
        phase.context == dict(originals)["context.json"] and captured[0] == phase.context and
        type(match) is acquisition.stages.BootstrapMatch and match.record == episode.state().match_raw,
        "WORKER_AUTHORITY_ORIGINALS")
    _source_pin(before)
    _source_pin(after)
    _phase_pin(phase)
    context = O.parse(phase.context)
    child_raw, session_raw = dict(originals)["service/child-result.json"], dict(originals)["acquisition-queries/session-result.json"]
    child, value = O.parse(child_raw), O.parse(pending)
    require(context["session"] == str(path) and context["scope"] == native.INITIAL_RECEIVING_CONTEXT_SCOPE and
        context["authorityWindow"] == O.parse(window.raw) and path == dict(_check_worker_reader(
            _WORKER_READER_CAPTURES[id(episode)]).roots)["I"] / "authority" and
        owner.initial_sources.get(str(path / "source-before")) is before and
        owner.initial_sources.get(str(path / "source-after")) is after and len(owner.initial_sources) == 2 and
        pending == O.encoded(value) and value["scope"] == "INITIAL_RECIPIENT_RECEIVING_AUTHORITY_PENDING_CLOSE_V1" and
        value["filesSha256"] == {name: O.digest(raw) for name, raw in originals} and
        value["receivingWindowSha256"] == O.digest(episode.raw) and
        value["senderSha256"] == episode.state().step[1] and value["retirement"] == "PENDING_OWNER_CLOSE",
        "WORKER_AUTHORITY_PENDING")
    data = dict(captured[1])
    chain = value["originalChain"]
    require(tuple(data) == ORIGINAL_KEYS and data["match"] == match.record and
        {name: data[name] for name in SOURCE_KEYS} == dict(before.records) == dict(after.records) and
        chain["childSha256"] == O.digest(child_raw) and chain["querySessionSha256"] == O.digest(session_raw) and
        chain["phaseSha256"] == {name: O.digest(raw) for name, raw in phase.records} and
        chain["originalsSha256"] == {name: O.digest(raw) for name, raw in data.items()} and
        child["querySessionSha256"] == O.digest(session_raw) and child["matchSha256"] == O.digest(match.record) and
        child["originalsSha256"] == chain["originalsSha256"] and child["invocation"] == captured[2],
        "WORKER_AUTHORITY_CHAIN")
    indexed, directories = [], [path, path / "control-home", path / "temporary", path / "service"]
    for name, source, raw, values in (("source-before", before, before.session, dict(before.records)),
            ("acquisition-queries", None, session_raw, data), ("source-after", after, after.session, dict(after.records))):
        rows, paths = _gate_query_index(path / name, raw, values, source=source)
        indexed.extend(rows)
        directories.extend(paths)
    available = dict((*originals, ("authority-pending.json", pending)))
    for name in ("authority-window.json", "context.json", "authority-pending.json",
            *("service/" + name for name in sorted(native.PHASE_FILES)), "service/child-result.json"):
        raw = available[name]
        maximum = native.ACK_LIMIT if name == "service/stdout.log" else native.STDERR_LIMIT if name == "service/stderr.log" else native.LIMIT
        require(type(raw) is bytes and len(raw) <= maximum, "WORKER_AUTHORITY_RAW_LIMIT")
        indexed.append((path / name, maximum, len(raw), O.digest(raw)))
    require(len(indexed) == len({row[0] for row in indexed}) == 281 and
        len(directories) == len(set(directories)) == 58, "WORKER_AUTHORITY_COMPLETE_ROSTER")
    files = []
    for target, maximum, count, digest in indexed:
        relative = target.relative_to(path).as_posix()
        if relative in available:
            require(type(available[relative]) is bytes and count == len(available[relative]) and
                digest == O.digest(available[relative]), "WORKER_AUTHORITY_RAW_CHANGED")
        files.append(_worker_file("I/authority/" + relative, maximum, count, digest,
            "ACTUAL_RETAINED_BYTES" if relative in available else "ORIGINAL_AUTHORITY_QUERY_DECLARATION"))
    require(sum(row["provenance"] == "ACTUAL_RETAINED_BYTES" for row in files) == 38,
            "WORKER_AUTHORITY_AVAILABLE_ROSTER")
    directories = tuple(sorted("I/authority" + ("/" + item.relative_to(path).as_posix() if item != path else "")
        for item in directories))
    targets = {"I/authority": path, **{"I/authority/" + name: path / name for name in
        ("control-home", "temporary", "service", "source-before", "source-after", "acquisition-queries")}}
    pins = _worker_pins(owner, state.clock.role, targets)
    files = tuple(sorted(files, key=lambda row: row["relative"]))
    graph += _history_graph(files, directories, tuple(target for _key, _row, _dir, target, _id in pins))
    capture = _WorkerAuthorityCapture(owner, window, episode, evidence, files, directories, pins)
    anchor = (capture, owner, window, episode, evidence, files, directories, pins, roster, binding, graph, registries)
    require(id(owner) not in _WORKER_AUTHORITY_CAPTURES and not hasattr(owner, "_worker_authority_capture"),
            "WORKER_AUTHORITY_CAPTURE_REUSE")
    owner._worker_authority_capture = capture
    _WORKER_AUTHORITY_CAPTURES[id(owner)] = anchor
    _check_worker_authority(anchor, closed=False)
    return anchor


def _check_worker_authority(anchor, *, closed):
    require(type(anchor) is tuple and len(anchor) == 12, "WORKER_AUTHORITY_BINDING")
    capture, owner, window, episode, evidence, files, directories, pins, roster, binding, graph, registries = anchor
    require(type(capture) is _WorkerAuthorityCapture and owner._worker_authority_capture is capture and
        _WORKER_AUTHORITY_CAPTURES.get(id(owner)) is anchor and
        len(registries) == len(_worker_registries()) and
        all(current is saved for current, saved in zip(_worker_registries(), registries)) and
        capture.owner is owner and capture.window is window and capture.episode is episode and capture.evidence is evidence and
        capture.files is files and capture.directories is directories and capture.pins is pins and
        _AUTHORITY_WINDOWS[id(window)].roster is roster and _AUTHORITY_WINDOWS[id(window)].episode is episode,
        "WORKER_AUTHORITY_CAPTURE_CHANGED")
    _worker_owner_current(owner, window, roster, binding, closed=closed)
    _check_history(graph)
    _check_worker_pins(pins, binding[6].clock.role, closed=closed)
    require(owner.phase_originals is evidence[4] and
        owner.initial_sources.get(str(next(path for key, _row, _dir, path, _id in pins
            if key == "I/authority/source-before"))) is evidence[2] and
        owner.initial_sources.get(str(next(path for key, _row, _dir, path, _id in pins
            if key == "I/authority/source-after"))) is evidence[3], "WORKER_AUTHORITY_SOURCE_REPLACED")
    return capture


def _register_worker_authority(result, episode, anchor):
    capture = _check_worker_authority(anchor, closed=True)
    saved, terminal = _AUTHORITY_RETURNS.get(id(result)), _AUTHORITY_WINDOWS[id(capture.window)]
    require(type(result) is _AuthorityReturn and type(result.raw) is bytes and 0 < len(result.raw) <= native.LIMIT and
        type(saved) is tuple and len(saved) == 6 and saved[0] is result and saved[1] == result.raw and
        saved[2] is episode is capture.episode and saved[3] is capture.window and saved[5] is capture.evidence[0] and
        _authority_return(result, episode) is capture.evidence[0], "WORKER_AUTHORITY_ORIGINAL_RETURN")
    value = O.parse(result.raw)
    require(value["filesSha256"] == {name: O.digest(raw) for name, raw in capture.evidence[0]} and
        value["pendingSha256"] == O.digest(capture.evidence[1]) and
        value["scope"] == "INITIAL_RECIPIENT_RECEIVING_AUTHORITY_CLOSED_HISTORY_V1" and
        value["retirement"] == "KNOWN_RESOURCE_CLOSE_ONLY", "WORKER_AUTHORITY_CLOSED_RAW")
    returned = (result, result.raw, saved, terminal, anchor, _history_graph(result))
    require(id(result) not in _WORKER_AUTHORITY_RETURNS and
        capture.owner._worker_authority_original_return[0] is result and
        capture.owner._worker_authority_original_return[1] == result.raw, "WORKER_AUTHORITY_RETURN_REUSE")
    _WORKER_AUTHORITY_RETURNS[id(result)] = returned
    return returned


def _worker_authority_return(result, expected=None):
    returned = _WORKER_AUTHORITY_RETURNS.get(id(result))
    require(type(returned) is tuple and len(returned) == 6 and returned[0] is result and
        (expected is None or returned is expected), "WORKER_AUTHORITY_NOT_ORIGINAL_RETURN")
    value, raw, saved, terminal, anchor, graph = returned
    capture = _check_worker_authority(anchor, closed=True)
    require(value is result and type(result.raw) is bytes and result.raw == raw and
        capture.owner._worker_authority_original_return[0] is result and
        capture.owner._worker_authority_original_return[1] == raw and
        _AUTHORITY_RETURNS.get(id(result)) is saved and _AUTHORITY_WINDOWS.get(id(capture.window)) is terminal and
        saved[0] is result and saved[1] == raw and saved[2] is capture.episode and saved[3] is capture.window and
        saved[5] is capture.evidence[0] and _authority_return(result, capture.episode) is capture.evidence[0],
        "WORKER_AUTHORITY_CLOSED_BINDING_CHANGED")
    _check_history(graph)
    return returned


def _worker_crypto_index(raw, reader, pin, expected_hash):
    """Validate the existing shallow inventory; do not reread crypto or run GPG."""
    _check_worker_reader(reader)
    captured = reader[0]
    state = _RECEIVING_WINDOWS[id(captured.window)]
    old, roots = dict(captured.originals), dict(captured.roots)
    require(type(raw) is bytes and 0 < len(raw) <= native.LIMIT and O.digest(raw) == expected_hash,
            "WORKER_CRYPTO_TRANSPORT_HASH")
    side = O.parse(raw)
    require(raw == O.encoded(side) and set(side) == {"schema", "scope", "directory", "directoryIdentity",
        "recipientValidationSha256", "recipientSenderSha256", "recipientStepSha256", "inventory", "writerReturn",
        "originalStepOutcome", "budgetAcceptance", "exportSaveAuthority"} and
        type(side["schema"]) is int and side["schema"] == 1 and side["scope"] == CRYPTO_SIDECAR_SCOPE and
        side["writerReturn"] == "PENDING_OWNER_CLOSE" and side["originalStepOutcome"] == "NOT_OBSERVED" and
        side["budgetAcceptance"] == "NOT_ADMITTED" and side["exportSaveAuthority"] is False,
        "WORKER_CRYPTO_SIDECAR_SCHEMA")
    require(captured.step is not None and side["directory"] == str(roots["C"]) == str(pin[3]) and
        native.directory_identity(side["directoryIdentity"], state.clock.role) == list(pin[4]) and
        side["recipientValidationSha256"] == O.digest(old["S/recipient-return.json"]) and
        side["recipientSenderSha256"] == state.step[1] == O.digest(old["S/sender-pending.json"]) and
        side["recipientStepSha256"] == state.step_hash == O.digest(captured.step[0].raw), "WORKER_CRYPTO_SIDECAR_BINDINGS")
    value = side["inventory"]
    require(type(value) is dict and set(value) == {"schema", "scope", "root", "contextSha256", "childSha256",
        "phaseSha256", "clock", "readEndNs", "readLocalCeiling", "capturedNs", "directories", "files", "totalBytes",
        "copyState", "liveRecipient", "budgetAcceptance", "exportSaveAuthority"} and
        type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == CRYPTO_ORIGINALS_SCOPE and
        value["root"] == str(roots["R"] / "crypto") and value["copyState"] == "ORIGINAL_BYTES_NOT_COPIED" and
        value["liveRecipient"] == "NOT_TRANSFERRED" and value["budgetAcceptance"] == "NOT_ADMITTED" and
        value["exportSaveAuthority"] is False, "WORKER_CRYPTO_INVENTORY_SCHEMA")
    context = O.parse(old["R/recipient-context.json"])
    child = O.parse(old["R/recipient-validation/child-result.json"])
    native_result = O.parse(old["R/recipient-validation/result.json"])
    sender, step = O.parse(old["S/sender-pending.json"]), _step_record(captured.step[0].raw)
    validation, pending = O.parse(old["S/recipient-return.json"]), O.parse(old["R/recipient-pending.json"])
    source = O.parse(old["R/source-final/source-return.json"])
    require(value["contextSha256"] == O.digest(old["R/recipient-context.json"]) and
        value["childSha256"] == O.digest(old["R/recipient-validation/child-result.json"]) and
        value["phaseSha256"] == {name: O.digest(old["R/recipient-validation/" + name]) for name in native.PHASE_FILES} and
        context["session"] == str(roots["R"]) and context["root"] == str(ROOT) and
        context["observed"] == O.parse(old["P/context.json"])["observed"] and
        O.encoded(value["clock"]) == O.encoded(child["clock"]) == O.encoded(sender["readWindow"]["clock"]) ==
        O.encoded(step["clock"]) == O.encoded(source["clock"]) == state.clock_raw, "WORKER_CRYPTO_ORIGINAL_LINKS")
    O.wire.clock_identity(value["clock"])
    require(type(value["readEndNs"]) is int and value["readEndNs"] == native_result["readEndNs"] ==
        sender["readWindow"]["readEndNs"] == step["readEndNs"] and
        type(value["readLocalCeiling"]) is float and math.isfinite(value["readLocalCeiling"]) and
        value["readLocalCeiling"] == sender["readWindow"]["readLocalCeiling"] == step["readLocalCeiling"] and
        0 <= sender["readWindow"]["previousLocal"] <= step["lowerLocal"] < value["readLocalCeiling"] and
        step["lowerLocal"] <= state.local_start, "WORKER_CRYPTO_ORIGINAL_CAPS")
    chronology = (native_result["readbackCompletedNs"], value["capturedNs"], source["returnedNs"], pending["retainedNs"],
        validation["preCloseNs"], validation["closedNs"], sender["readWindow"]["previousNs"],
        sender["readWindow"]["retainedNs"], step["lowerNs"])
    require(all(type(item) is int and 0 <= item < value["readEndNs"] for item in chronology) and
        tuple(sorted(chronology)) == chronology and chronology[-1] <= state.first, "WORKER_CRYPTO_CHRONOLOGY")
    windows = state.clock.role == "windows-x64"
    directories, rows = value["directories"], value["files"]
    require(type(directories) is list and len(directories) == (6 if windows else 5) and
        all(type(row) is dict and set(row) == {"relative", "identity", "members"} and type(row["relative"]) is str and
            type(row["members"]) is list and len(row["members"]) <= 32 and
            all(type(name) is str for name in row["members"]) and row["members"] == sorted(row["members"]) and
            len({name.casefold() for name in row["members"]}) == len(row["members"]) for row in directories),
        "WORKER_CRYPTO_DIRECTORIES")
    members = directories[0]["members"]
    for directory in directories:
        native.directory_identity(directory["identity"], state.clock.role)
        for name in directory["members"]:
            Q._component(name)
    operations = tuple(name for name in members if re.fullmatch(r"gpg-[0-9a-f]{32}" if windows else r"gpg-[a-z0-9_]+", name))
    results = tuple(name for name in members if re.fullmatch(r"recipient-validation-result-[0-9a-f]{32}\.json", name))
    require(len(operations) == (3 if windows else 2) and len(results) == (1 if windows else 0) and
        set(members) == {"recipient.asc", "recipient.gpg", "gnupg", "tmp", *operations, *results} and
        tuple(row["relative"] for row in directories) == ("", "gnupg", "tmp", *operations) and
        len({tuple(row["identity"]) for row in directories}) == len(directories), "WORKER_CRYPTO_DIRECTORY_GRAMMAR")
    original_root = next(identity for name, _row, _directory, _path, identity in captured.pins if name == "R/crypto")
    require(directories[0]["identity"] == list(original_root) == context["directories"]["crypto"] ==
        child["recipient"]["work_identity"], "WORKER_CRYPTO_ORIGINAL_ROOT_IDENTITY")
    expected = {name: native.posix.MAX_KEY_BYTES for name in ("recipient.asc", "recipient.gpg")}
    expected.update({name: native.diagnostics.MAX_RECORD_BYTES for name in results})
    for directory in directories[1:]:
        name, members = directory["relative"], directory["members"]
        if name in ("gnupg", "tmp"):
            require(not windows or members == [], "WORKER_CRYPTO_WINDOWS_HOME_NOT_EMPTY")
        else:
            require(members == sorted(("stdout", "stderr") if windows else ("stdout", "stderr", "status", "process.json")),
                    "WORKER_CRYPTO_OPERATION_ROSTER")
        for member in members:
            expected[name + "/" + member] = (native.LIMIT if name in ("gnupg", "tmp") or member == "process.json"
                else native.posix.MAX_DIAGNOSTIC_BYTES)
    require(type(rows) is list and len(rows) == len(expected) and
        (len(rows) == 9 if windows else 10 <= len(rows) <= 74) and
        all(type(row) is dict and set(row) == {"relative", "bytes", "sha256"} and type(row["relative"]) is str
            for row in rows) and tuple(row["relative"] for row in rows) == tuple(sorted(expected)),
        "WORKER_CRYPTO_FILE_ROSTER")
    files, total = [], 0
    for row in rows:
        files.append(_worker_file("R/crypto/" + row["relative"], expected[row["relative"]], row["bytes"], row["sha256"],
            "AUTHENTICATED_CRYPTO_DECLARATION"))
        total += row["bytes"]
        require(total <= CRYPTO_ORIGINALS_LIMIT, "WORKER_CRYPTO_TOTAL_LIMIT")
        if row["relative"] == "recipient.asc":
            require(row["bytes"] == len(old["R/recipient-public.asc"]) > 0 and
                row["sha256"] == O.digest(old["R/recipient-public.asc"]) == child["recipient"]["key_sha256"],
                "WORKER_CRYPTO_KEY_CHANGED")
        elif row["relative"] == "recipient.gpg":
            require(row["bytes"] > 0, "WORKER_CRYPTO_EMPTY_RING")
    require(type(value["totalBytes"]) is int and value["totalBytes"] == total, "WORKER_CRYPTO_TOTAL_BYTES")
    return tuple(files), tuple(("R/crypto/" + row["relative"], tuple(row["identity"])) for row in directories[1:])


@dataclass(frozen=True, repr=False)
class _WorkerCryptoCapture:
    reader: object
    raw: bytes
    pin: tuple
    files: tuple
    directories: tuple
    sha256: str


def _capture_worker_crypto(window, reader, expected_hash):
    require(type(expected_hash) is str and re.fullmatch(r"[0-9a-f]{64}", expected_hash) and
        os.environ.get(RECEIVING_CRYPTO_HASH_ENV) == expected_hash, "WORKER_CRYPTO_INPUT_REQUIRED")
    original = _check_worker_reader(reader)
    owner, path = original.owner, dict(original.roots)["C"]
    require(original.window is window and original.step is not None and id(window) not in _WORKER_CRYPTO_CAPTURES and
        not hasattr(owner, "_worker_crypto_capture"), "WORKER_CRYPTO_CAPTURE_REUSE")
    directory = owner.open(path)
    pin = _worker_pins(owner, window.clock.role, {"C": path})
    require(len(pin) == 1 and pin[0][2] is directory, "WORKER_CRYPTO_READER_PIN")
    pin = pin[0]
    path_graph = _history_graph(path, pin[3])
    _check_worker_reader(reader)
    native._new_entry_owned(owner, directory, path, pin[4])
    raw = owner.read(directory, CRYPTO_ORIGINALS_FILE, native.LIMIT)
    files, directories = _worker_crypto_index(raw, reader, pin, expected_hash)
    # Independently save bytes, declarations, native pin and env hash before
    # the later listing/initializer/source suppliers can change any of them.
    capture = _WorkerCryptoCapture(reader, raw, pin, files, directories, expected_hash)
    graph = path_graph + _history_graph(files, directories)
    anchor = (capture, reader, raw, pin, files, directories, expected_hash, graph, _WORKER_CRYPTO_CAPTURES)
    owner._worker_crypto_capture = capture
    _WORKER_CRYPTO_CAPTURES[id(window)] = anchor
    require(native._initializer_names(owner, directory) == (CRYPTO_ORIGINALS_FILE,), "WORKER_CRYPTO_SIDECAR_ROSTER")
    native._new_entry_owned(owner, directory, path, pin[4])
    _check_worker_crypto(anchor)
    return anchor


def _check_worker_crypto(anchor, *, closed=False):
    require(type(anchor) is tuple and len(anchor) == 9, "WORKER_CRYPTO_CAPTURE_BINDING")
    capture, reader, raw, pin, files, directories, sha256, graph, registry = anchor
    original = _check_worker_reader(reader, closed=closed)
    require(type(capture) is _WorkerCryptoCapture and original.owner._worker_crypto_capture is capture and
        registry is _WORKER_CRYPTO_CAPTURES and registry.get(id(original.window)) is anchor and
        capture.reader is reader and type(capture.raw) is bytes and capture.raw == raw and capture.pin is pin and
        capture.files is files and capture.directories is directories and capture.sha256 == sha256 and
        os.environ.get(RECEIVING_CRYPTO_HASH_ENV) == sha256 and O.digest(raw) == sha256,
        "WORKER_CRYPTO_CAPTURE_CHANGED")
    _check_history(graph)
    _check_worker_pins((pin,), reader[14].role, closed=closed)
    return capture


@dataclass(frozen=True, repr=False)
class _WorkerOriginalCapture:
    continuation: object
    result: object
    raw: bytes
    reader: object
    authority: object
    crypto: object
    pins: tuple


def _capture_worker_originals(continuation, result):
    """Freeze the complete fixed logical index at the actual initializer return."""
    # Keep the exact successful call/registry entries BEFORE checks or suppliers.
    saved = _RECEIVING_CONTINUATIONS.get(id(continuation))
    attempt = _RECEIVING_INIT_ATTEMPTS.get(id(continuation))
    returned = _RECEIVING_INIT_RETURNS.get(id(result))
    registries = _worker_registries()
    require(type(continuation) is _ReceivingContinuation and type(saved) is tuple and len(saved) == 3 and
        saved[0] is continuation and type(result) is _ReceivingInitialization and
        type(returned) is tuple and len(returned) == 6 and returned[0] is result and returned[1] is attempt,
        "WORKER_INITIALIZER_ORIGINAL_RETURN")
    window, authority_result = saved[1:]
    state = _RECEIVING_WINDOWS[id(window)]
    graph = _history_graph(result.__dict__, result.originals, result.native)
    fields = tuple((name, getattr(state, name)) for name in ("raw", "originals", "observed_raw", "captured",
        "identity_fields", "match_raw", "proposal_raw", "service_job", "authority", "inputs", "continuity", "initialization"))
    reader, crypto = _WORKER_READER_CAPTURES[id(window)], _WORKER_CRYPTO_CAPTURES[id(window)]
    original = _check_worker_reader(reader)
    crypto_original = _check_worker_crypto(crypto)
    authority = original.authority_check()
    require(type(authority) is tuple and len(authority) == 6 and authority[0] is authority_result,
            "WORKER_INITIALIZER_AUTHORITY_ORIGINAL")
    authority_original = authority[4][0]
    require(_receiving_initialization_return(continuation) is result and crypto_original.reader is reader and
        authority_original.episode is window and type(result.originals) is tuple and len(result.originals) == 11 and
        type(result.pending) is bytes and 0 < len(result.pending) <= native.LIMIT,
        "WORKER_INITIALIZER_CAPTURE_BINDINGS")
    owner, roots, role = original.owner, dict(original.roots), state.clock.role
    expected_i = ("I", "I/canonical-init", "I/control-home", "I/temporary", "I/state", "I/state/gradle-home",
        "I/state/evidence", "I/state/cancellations")
    targets = {name: roots["I"].joinpath(*name.split("/")[1:]) for name in expected_i}
    pins = _worker_pins(owner, role, targets)
    require(len(pins) == 8 and next(pin[2] for pin in pins if pin[0] == "I") is
        next(pin[2] for pin in original.pins if pin[0] == "I"), "WORKER_INITIALIZER_PIN_ROSTER")
    by_path = {path: (key, directory, identity) for key, _row, directory, path, identity in pins}
    for name, directory, target, identity in state.inputs[2]:
        key = "I" if name == "session" else "I/" + name
        require(by_path[target] == (key, directory, identity), "WORKER_INITIALIZER_INPUT_PIN_CHANGED")
    files = [_worker_file(name, max(1, len(raw)), len(raw), O.digest(raw), "ACTUAL_RETAINED_BYTES")
        for name, raw in original.originals]
    files.extend(dict(row) for row in authority_original.files)
    i_names = {"I/receiving-window.json", "I/initializer-context.json", "I/initialization-pending.json",
        "I/state/context.json", "I/state/gradle-home/gradle.properties",
        *("I/canonical-init/" + name for name in (*native.PHASE_FILES, "request.json"))}
    i_files = []
    for directory, target, identity, name, maximum, raw in result.originals:
        require(target in by_path and by_path[target][1] is directory and by_path[target][2] == identity and
            type(raw) is bytes and type(maximum) is int, "WORKER_INITIALIZER_ORIGINAL_FILE")
        key = by_path[target][0] + "/" + name
        limit = (16384 if key == "I/state/gradle-home/gradle.properties" else native.ACK_LIMIT if
            key == "I/canonical-init/stdout.log" else native.STDERR_LIMIT if key == "I/canonical-init/stderr.log" else native.LIMIT)
        i_files.append(_worker_file(key, min(limit, maximum), len(raw), O.digest(raw), "ACTUAL_RETAINED_BYTES"))
    i_files.append(_worker_file("I/initialization-pending.json", native.LIMIT,
        len(result.pending), O.digest(result.pending), "ACTUAL_RETAINED_BYTES"))
    require(len(i_files) == 12 and {row["relative"] for row in i_files} == i_names, "WORKER_INITIALIZER_FILE_ROSTER")
    files.extend(i_files)
    for key, name, raw, maximum in (("T", continuity.STEP_FILE, original.step[0].raw, continuity.STEP_LIMIT),
            ("C", CRYPTO_ORIGINALS_FILE, crypto_original.raw, native.LIMIT)):
        files.append(_worker_file(key + "/" + name, maximum, len(raw), O.digest(raw), "ACTUAL_RETAINED_BYTES"))
    files.extend(dict(row) for row in crypto_original.files)
    directories = []
    def directory_row(key, identity, provenance):
        _worker_relative(key)
        path = roots[key.split("/", 1)[0]].joinpath(*key.split("/")[1:])
        directories.append({"relative": key, "parent": None if "/" not in key else key.rsplit("/", 1)[0],
            "path": str(path), "identity": None if identity is None else native.directory_identity(list(identity), role),
            "provenance": provenance})
    old_pins = {name: identity for name, _row, _directory, _path, identity in original.pins}
    for key in original.directories:
        directory_row(key, old_pins[key], "RECEIVER_READBACK_NATIVE_PIN")
    authority_pins = {name: identity for name, _row, _directory, _path, identity in authority_original.pins}
    for key in authority_original.directories:
        directory_row(key, authority_pins.get(key), "ORIGINAL_AUTHORITY_NATIVE_PIN" if key in authority_pins
            else "ORIGINAL_AUTHORITY_DECLARED_DIRECTORY")
    for key, _row, _directory, _path, identity in pins:
        directory_row(key, identity, "ORIGINAL_INITIALIZER_NATIVE_PIN")
    directory_row("T", old_pins["T"], "SENDER_STEP_RECEIVER_READBACK_NATIVE_PIN")
    directory_row("C", crypto_original.pin[4], "CRYPTO_SIDECAR_RECEIVER_READBACK_NATIVE_PIN")
    for key, identity in crypto_original.directories:
        directory_row(key, identity, "AUTHENTICATED_ORIGINAL_CRYPTO_NATIVE_PIN")
    windows, crypto_count = role == "windows-x64", len(crypto_original.files)
    file_counts = {key: sum(row["relative"].split("/", 1)[0] == key for row in files) for key in roots}
    directory_counts = {key: sum(row["relative"].split("/", 1)[0] == key for row in directories) for key in roots}
    require(file_counts == {"P": 284, "E": 281, "R": 498 + crypto_count, "S": 3, "I": 293, "T": 1, "C": 1} and
        len(files) == 1361 + crypto_count and (len(files) == 1370 if windows else 1371 <= len(files) <= 1435) and
        directory_counts == {"P": 58, "E": 58, "R": 110 if windows else 109, "S": 1, "I": 66, "T": 1, "C": 1} and
        len(directories) == (295 if windows else 294), "WORKER_COMPLETE_COUNTS")
    file_names, directory_names = {row["relative"] for row in files}, {row["relative"] for row in directories}
    all_names = tuple(file_names | directory_names)
    require(len(file_names) == len(files) and len(directory_names) == len(directories) and
        file_names.isdisjoint(directory_names) and len({name.casefold() for name in all_names}) == len(all_names) and
        all(row["parent"] in directory_names for row in files) and
        all(row["parent"] is None or row["parent"] in directory_names for row in directories) and
        len({row["path"].casefold() for row in directories}) == len(directories), "WORKER_COMPLETE_NAMES")
    identities = [tuple(row["identity"]) for row in directories if row["identity"] is not None]
    require(len(identities) == len(set(identities)) and
        sum(row["identity"] is None for row in directories) == 51, "WORKER_COMPLETE_PIN_PROVENANCE")
    owned = {id(directory) for _key, _row, directory, _path, _identity in (*original.pins, *pins, crypto_original.pin)}
    require(len(owned) == 232 and {id(row["owner"]) for row in owner.resources if row["label"] == "directory"} == owned,
            "WORKER_COMPLETE_RECEIVING_LEDGER")
    observed = O.parse(state.observed_raw)
    raw = O.encoded({"schema": 1, "scope": WORKER_INVENTORY_SCOPE,
        "roots": [{"group": key, "path": str(path)} for key, path in original.roots],
        "source": observed["source"], "github": observed["github"], "clock": O.clock_value(state.clock),
        "senderSha256": state.step[1], "recipientStepSha256": state.step_hash,
        "recipientCryptoOriginalsSha256": crypto_original.sha256, "initializationSha256": O.digest(result.pending),
        "authoritySha256": O.digest(authority[1]), "workerIdentitySha256": O.digest(state.identity_fields[0]),
        "files": sorted(files, key=lambda row: row["relative"]), "fileCount": len(files), "fileCounts": file_counts,
        "directories": sorted(directories, key=lambda row: row["relative"]),
        "directoryCount": len(directories), "directoryCounts": directory_counts,
        "totalBytes": sum(row["bytes"] for row in files), "copyState": "ORIGINAL_BYTES_NOT_COPIED",
        "liveRecipient": "NOT_TRANSFERRED", "budgetAcceptance": "NOT_ADMITTED",
        "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False})
    require(len(raw) <= native.LIMIT, "WORKER_COMPLETE_INDEX_LIMIT")
    graph += _history_graph(tuple(path for _key, _row, _directory, path, _identity in pins))
    capture = _WorkerOriginalCapture(continuation, result, raw, reader, authority, crypto, pins)
    anchor = (capture, continuation, result, raw, reader, authority, crypto, pins, saved, attempt, returned, fields, graph, registries)
    require(id(continuation) not in _WORKER_ORIGINAL_CAPTURES and not hasattr(owner, "_worker_original_capture"),
            "WORKER_COMPLETE_CAPTURE_REUSE")
    owner._worker_original_capture = capture
    _WORKER_ORIGINAL_CAPTURES[id(continuation)] = anchor
    _check_worker_originals(anchor, closed=False)
    return anchor


def _check_worker_originals(anchor, *, closed):
    require(type(anchor) is tuple and len(anchor) == 14, "WORKER_COMPLETE_BINDING")
    capture, continuation, result, raw, reader, authority, crypto, pins, saved, attempt, returned, fields, graph, registries = anchor
    original = _check_worker_reader(reader, closed=closed)
    require(type(capture) is _WorkerOriginalCapture and original.owner._worker_original_capture is capture and
        _WORKER_ORIGINAL_CAPTURES.get(id(continuation)) is anchor and
        len(registries) == len(_worker_registries()) and
        all(current is previous for current, previous in zip(_worker_registries(), registries)) and
        capture.continuation is continuation and capture.result is result and type(capture.raw) is bytes and capture.raw == raw and
        capture.reader is reader and capture.authority is authority and capture.crypto is crypto and capture.pins is pins and
        _RECEIVING_CONTINUATIONS.get(id(continuation)) is saved and saved[1] is original.window and
        _RECEIVING_INIT_ATTEMPTS.get(id(continuation)) is attempt and _RECEIVING_INIT_RETURNS.get(id(result)) is returned and
        returned[0] is result and returned[1] is attempt, "WORKER_COMPLETE_CAPTURE_CHANGED")
    state = _RECEIVING_WINDOWS[id(original.window)]
    require(all(getattr(state, name) is value for name, value in fields) and
        _receiving_initialization_return(continuation, closed=closed) is result and
        _worker_authority_return(saved[2], authority) is authority and
        _check_worker_crypto(crypto, closed=closed).reader is reader, "WORKER_COMPLETE_RETURN_CHANGED")
    _check_history(graph)
    _check_worker_pins(pins, state.clock.role, closed=closed)
    return capture


def _worker_handoff_record(path, identity, inventory_raw, authority_raw, initialization_raw):
    """Two embedded MEMORY originals, not invented files or an evidence archive."""
    embedded = []
    for name, raw in (("receiving-authority-return.json", authority_raw), ("initialization-history.json", initialization_raw)):
        require(type(raw) is bytes and 0 < len(raw) <= native.LIMIT, "WORKER_EMBEDDED_ORIGINAL_LIMIT")
        encoded = base64.b64encode(raw).decode("ascii")
        require(base64.b64decode(encoded, validate=True) == raw and
            base64.b64encode(base64.b64decode(encoded, validate=True)).decode("ascii") == encoded,
            "WORKER_EMBEDDED_ORIGINAL_ENCODING")
        embedded.append({"name": name, "bytes": len(raw), "sha256": O.digest(raw), "rawBase64": encoded})
    raw = O.encoded({"schema": 1, "scope": WORKER_HANDOFF_SCOPE, "directory": str(path),
        "directoryIdentity": list(identity), "inventory": O.parse(inventory_raw), "embeddedOriginals": embedded,
        "originalClose": {"authority": "KNOWN_RESOURCE_CLOSE_ONLY", "receiving": "KNOWN_RESOURCE_CLOSE_ONLY"},
        "writerReturn": "PENDING_OWNER_CLOSE", "originalStepOutcome": "NOT_OBSERVED",
        "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
    require(len(raw) <= native.LIMIT, "WORKER_HANDOFF_RECORD_LIMIT")
    return raw


def _retain_worker_handoff(continuation, result, original_anchor, cancelled):
    """One exclusive metadata sibling, still inside the ORIGINAL receiving120."""
    original = _check_worker_originals(original_anchor, closed=True)
    require(original.continuation is continuation and original.result is result and
        _receiving_initialization_return(continuation, closed=True) is result, "RECEIVING_INIT_CLOSED_RETURN")
    window = original.reader[0].window
    terminal = _RECEIVING_WINDOWS[id(window)]
    last, local_last, hard, cap = terminal.last, terminal.local_last, terminal.work, terminal.locals[0]
    require(type(last) is int and last < O.integer(hard) and type(cap) is float and math.isfinite(cap) and
        type(local_last) in (int, float) and math.isfinite(local_last) and 0 <= local_last < cap,
        "WORKER_HANDOFF_ORIGINAL_CAP")
    path = dict(original.reader[0].roots)["I"]
    path = path.with_name(path.name + "-handoff")
    path_graph = _history_graph(path)
    registries, attempts = _worker_registries(), _WORKER_HANDOFF_ATTEMPTS
    marker, retained = object(), []
    attempt = (continuation, result, original_anchor, marker, retained)
    original_owner = terminal.roster.owner
    with _WORKER_HANDOFF_LOCK:
        require(_WORKER_HANDOFF_ATTEMPTS is attempts and id(continuation) not in attempts and
            not hasattr(original_owner, "_worker_handoff_marker") and
            id(continuation) not in _RECEIVING_CLOSED_RETURNS, "WORKER_HANDOFF_ALREADY_CLAIMED")
        original_owner._worker_handoff_marker = marker
        attempts[id(continuation)] = attempt  # Sticky BEFORE any metadata observation/allocation/callback.
    closed = O.encoded({"schema": 1, "scope": "INITIAL_RECIPIENT_CLOSED_INITIALIZATION_HISTORY_V1",
        "pendingSha256": O.digest(result.pending), "closedNs": terminal.last, "closedLocal": terminal.local_last,
        "resourceCount": len(terminal.roster.rows), "ownerReturn": "KNOWN_RESOURCE_CLOSE_ONLY",
        "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "exportSaveAuthority": False})
    closed_return = (continuation, result, terminal, closed)
    _RECEIVING_CLOSED_RETURNS[id(continuation)] = closed_return  # Existing four-field shape, original bytes retained below.
    graph = _history_graph(terminal.__dict__, original_owner, terminal.roster)
    owner = roster = owner_binding = first_graph = pin = pin_graph = closed_graph = value_graph = None
    raw = value = failure = None
    phase, busy, io_busy, failed, checks, issued_end = "METADATA", False, False, False, 0, cap

    def remember(error):
        nonlocal failure, failed
        failed = True
        if failure is None:
            failure = owner.original if owner is not None and owner.original is not None else error
        if owner is not None:
            owner.error("worker-originals-handoff", error)
            if owner.unknown and not any(item is owner for item in native.QUARANTINE):
                native.QUARANTINE.append(owner)

    def pins(*, cleanup=False):
        if roster is not None:
            _worker_owner_current(owner, metadata, roster, owner_binding,
                closed=phase in ("FILE_OUTPUT", "OUTPUT", "COMPLETE"), cleanup=cleanup)
            _check_history(first_graph)
        if pin is not None:
            _check_history(pin_graph)
            _check_worker_pins((pin,), terminal.clock.role, closed=pin[1]["closed"] if cleanup else
                phase in ("FILE_OUTPUT", "OUTPUT", "COMPLETE"))
        if cleanup:
            return
        require(not failed and _WORKER_HANDOFF_ATTEMPTS is attempts and attempts.get(id(continuation)) is attempt and
            original_owner._worker_handoff_marker is marker and
            len(registries) == len(_worker_registries()) and
            all(current is saved for current, saved in zip(_worker_registries(), registries)) and
            _RECEIVING_WINDOWS.get(id(window)) is terminal and _RECEIVING_CLOSED_RETURNS.get(id(continuation)) is closed_return and
            _check_worker_originals(original_anchor, closed=True) is original and
            not continuity.QUARANTINE and not native.QUARANTINE and not Q.QUARANTINE and not native.diagnostics._QUARANTINE,
            "RECEIVING_INIT_OUTPUT_CHANGED")
        _check_history(graph)
        _check_history(path_graph)
        if phase in ("FILE_OUTPUT", "OUTPUT", "COMPLETE"):
            require(owner is not None and closed_graph is not None, "WORKER_HANDOFF_CLOSE_REQUIRED")
            _check_history(closed_graph)
            _check_history(value_graph)

    def observe(minimum=0, limit=None):
        # Direct original-clock observations, never terminal.now()/deadline().
        nonlocal last, local_last, busy
        if busy:
            error = I.AdmissionError("RECEIVING_INIT_OUTPUT_REENTRY")
            remember(error)
            raise error
        busy = True
        try:
            cleanup = phase == "CLOSING"
            pins(cleanup=cleanup)
            terminal.cancelled()
            native.cancellation(cancelled)
            local = time.monotonic()
            require(type(local) in (int, float) and math.isfinite(local) and local >= local_last,
                    "RECEIVING_INIT_OUTPUT_LOCAL_BACKWARDS")
            local_last = local
            end = hard if limit is None else min(hard, O.integer(limit))
            last = O.clocks.checked_now(terminal.clock, minimum_ns=max(last, O.integer(minimum)))
            require(last < end and local < cap, "RECEIVING_INIT120_OUTPUT_EXPIRED")
            require(continuity.boot_digest(terminal.clock.role) == terminal.continuity[0].boot,
                    "RECEIVING_INIT_OUTPUT_BOOT_CHANGED")
            last = O.clocks.checked_now(terminal.clock, minimum_ns=last)
            after = time.monotonic()
            require(type(after) in (int, float) and math.isfinite(after) and after >= local_last,
                    "RECEIVING_INIT_OUTPUT_LOCAL_BACKWARDS")
            local_last = after
            require(last < end and after < cap, "RECEIVING_INIT120_OUTPUT_EXPIRED")
            pins(cleanup=cleanup)
            return last
        except BaseException as error:
            remember(error)
            raise
        finally:
            busy = False

    class MetadataFence:
        __slots__ = ()
        clock = property(lambda _self: terminal.clock)
        last = property(lambda _self: last)
        local_end = property(lambda _self: cap)

        def now(self, *, final=False, minimum=0, limit=None):
            try:
                require(self is metadata and not io_busy and type(final) is bool and
                    (phase == "METADATA" or phase == "CLOSING" and final), "WORKER_HANDOFF_METADATA_ONLY")
                return observe(minimum, limit)
            except BaseException as error:
                remember(error)
                raise

        def deadline(self, maximum, *, final=False, limit=None):
            nonlocal local_last, issued_end, io_busy
            try:
                require(self is metadata and phase == "METADATA" and not busy and not io_busy and type(final) is bool and
                    type(maximum) in (int, float) and
                    math.isfinite(maximum) and 0 < maximum <= 45, "WORKER_HANDOFF_METADATA_IO_ONLY")
                io_busy = True
                pins()
                local = time.monotonic()
                require(type(local) in (int, float) and math.isfinite(local) and local >= local_last,
                        "RECEIVING_INIT_OUTPUT_LOCAL_BACKWARDS")
                local_last = local
                observed = observe(limit=limit)
                end = hard if limit is None else min(hard, O.integer(limit))
                # Owner's existing per-operation maximum only NARROWS the
                # inherited ceiling; it never creates another work/final phase.
                issued_end = min(issued_end, O.wire._directed_deadline(local, maximum, end, observed))
                pins()
                return issued_end
            except BaseException as error:
                remember(error)
                raise
            finally:
                io_busy = False

    class ClosedOutput:
        __slots__ = ()
        def now(self, *, final=False, minimum=0, limit=None):
            nonlocal checks, phase
            try:
                require(self is fence and phase == "OUTPUT" and final is True and checks < 2,
                        "RECEIVING_INIT_OUTPUT_FINAL_ONLY")
                checks += 1  # Exactly native.guarded's two final checks, not an owner interface.
                observed = observe(minimum, limit)
                if checks == 2:
                    phase = "COMPLETE"
                return observed
            except BaseException as error:
                remember(error)
                raise

    metadata, fence = MetadataFence(), ClosedOutput()
    try:
        observe()
        first = O.clocks.Reading(terminal.clock, last)
        first_graph = _history_graph(first)
        owner = native.Owner(cap, metadata, first=first, cancelled=terminal.cancelled)
        retained.append(owner)
        owner.initial_sources = {}
        roster = _RecipientRoster(owner, metadata, first)
        retained.append(roster)
        owner_binding = _worker_owner_binding(owner, roster)
        directory = owner.new(path)
        pin = _worker_pins(owner, terminal.clock.role, {"I-handoff": path})
        require(len(pin) == 1 and pin[0][2] is directory, "WORKER_HANDOFF_DIRECTORY_PIN")
        pin = pin[0]
        pin_graph = _history_graph(pin[3])
        native._new_entry_owned(owner, directory, path, pin[4])
        require(native._initializer_names(owner, directory) == (), "WORKER_HANDOFF_DIRECTORY_NOT_EMPTY")
        raw = _worker_handoff_record(path, pin[4], original.raw, original.authority[1], closed)
        written = owner.write(directory, WORKER_HANDOFF_FILE, raw)
        readback = owner.read(directory, WORKER_HANDOFF_FILE, native.LIMIT)
        require(type(written) is bytes and written == raw and type(readback) is bytes and readback == raw and
            native._initializer_names(owner, directory) == (WORKER_HANDOFF_FILE,), "WORKER_HANDOFF_READBACK")
        native._new_entry_owned(owner, directory, path, pin[4])
        pins()
    except BaseException as error:
        remember(error)
    finally:
        phase = "CLOSING"
        if owner is not None:
            try:
                pins(cleanup=True)
                roster.freeze()
            except BaseException as error:
                owner.error("worker-handoff-close-roster", error, unknown=True)
                remember(error)
            try:
                owner.close()
                roster.known()
            except BaseException as error:
                owner.error("worker-handoff-close", error, unknown=True)
                remember(error)
            if failure is None:
                failure = owner.original
            if owner.unknown and not any(item is owner for item in native.QUARANTINE):
                native.QUARANTINE.append(owner)
    if failure is not None:
        raise failure
    try:
        require(owner is not None and raw is not None and pin is not None and not failed, "WORKER_HANDOFF_INCOMPLETE")
        closed_graph = _history_graph(owner, roster)
        value = native.public_result("INITIAL_RECIPIENT_INITIALIZATION_PENDING_STEP_RETURN_V1", "initializationSha256", result.pending)
        value["workerHandoffSha256"] = O.digest(raw)
        value_graph = _history_graph(value)
        phase = "FILE_OUTPUT"
        observe()
        continuity.append_outputs({"initializationSha256": value["initializationSha256"],
            "workerHandoffSha256": value["workerHandoffSha256"]}, observe)
        pins()
        phase = "OUTPUT"
        return value, fence, hard
    except BaseException as error:
        remember(error)
        raise failure


def _initialize_step(cancelled):
    """Fixed completing Step: one closed handoff, not producer/custody authority."""
    require(type(os.environ.get(continuity.STEP_HASH_ENV)) is str and
        re.fullmatch(r"[0-9a-f]{64}", os.environ[continuity.STEP_HASH_ENV]), "RECEIVING_FIXED_STEP_REQUIRED")
    crypto_hash = os.environ.get(RECEIVING_CRYPTO_HASH_ENV)
    require(type(crypto_hash) is str and re.fullmatch(r"[0-9a-f]{64}", crypto_hash), "RECEIVING_FIXED_CRYPTO_HASH_REQUIRED")
    with _receive_initialization(cancelled, crypto_sha256=crypto_hash) as continuation:
        result = _initialize_receiving(continuation)
        original = _capture_worker_originals(continuation, result)
    return _retain_worker_handoff(continuation, result, original, cancelled)


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


_READER_PATH_CHECK = _check_reader_path_history
_READER_PATH_CODE = _check_reader_path_history.__code__


class _ReaderPathHistory:
    """Private saved-metadata plan, never a cache of current observations.

    Only an immutable prefix or our own unexposed accumulation list is planned.
    Every current type/field/comparison is still observed at every boundary.
    Interception, reentrancy or unsupported metadata permanently selects the
    original live-container helper, including after a helper is restored.
    Like the surrounding private pins, this is not a Python code/frame sandbox.
    """
    __slots__ = ("_nodes", "_pairs", "_kind", "_fallback", "_building")

    def __init__(self, nodes):
        self._nodes, self._pairs, self._kind = nodes, [], None
        self._fallback, self._building = type(nodes) is not tuple, True
        try:
            if not self._fallback and not self._append_plan(nodes):
                self._fallback = True
        except BaseException:
            self._fallback = True
            raise
        finally:
            self._building = False

    @classmethod
    def accumulating(cls):
        value = cls(())
        value._nodes = []  # No supplied mutable container can enter the fast path.
        return value

    def _append_plan(self, nodes):
        for node in nodes:
            # Inspect only immutable routing metadata. Invalid/custom shapes
            # must fail in the original helper, not earlier during planning.
            if not (type(node) is tuple and len(node) == 4 and type(node[2]) is str and node[2] == "path"):
                return False
            value, kind, _mode, saved = node
            if self._pairs and kind is not self._kind:
                return False
            self._kind = kind
            self._pairs.append((value, saved))  # Same references, order and duplicates.
        return True

    def extend(self, nodes):
        building, self._building = self._building, True
        if building:
            self._fallback = True
        try:
            before = len(self._nodes)
            self._nodes.extend(nodes)  # Preserve partial extension and its original exception.
            if not self._fallback and not self._append_plan(self._nodes[before:]):
                self._fallback = True
        except BaseException:
            self._fallback = True
            raise
        finally:
            self._building = building

    def check(self):
        checker = _check_reader_path_history
        if not (not self._fallback and not self._building and checker is _READER_PATH_CHECK and
                checker.__code__ is _READER_PATH_CODE):
            self._fallback = True
            # Drop duplicate references before a helper can expose/mutate the
            # original container; removed nodes must retain original lifetimes.
            self._pairs.clear()
            self._kind = None
            return checker(self._nodes)
        kind = self._kind
        for value, saved in self._pairs:
            if type(value) is not kind:
                require(False, "RECIPIENT_HISTORY_CHANGED")
            if (str(value), value.parts, value.drive, value.root) != saved:
                require(False, "RECIPIENT_HISTORY_CHANGED")


def _query_reader_roster(owner, ledger, prefix, held, new_rows, missing):
    # Preserve the original generator scopes: a tail row's finalizer can
    # change the live ledger before the next phase constructs its fresh slice.
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


def _graph_reader_roster(owner, ledger, rows, missing, *, tail=False):
    if not (owner.resources is ledger and (len(ledger) >= len(rows) if tail else len(ledger) == len(rows))):
        return False
    for actual, (saved, label, resource, attempted, closed) in zip(ledger, rows):
        valid = (actual is saved and type(actual) is dict and len(actual) == 4 and actual.get("label", missing) is not missing and
            actual.get("label") == label and actual.get("owner", missing) is resource and
            actual.get("attempted") is attempted and actual.get("closed") is closed)
        try:
            if not valid:
                return False
        finally:
            del valid
    return True


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
    held, new_rows, pins, records = [], [], [], []
    path_nodes = _ReaderPathHistory.accumulating()
    missing = object()

    def roster():
        return _query_reader_roster(owner, ledger, prefix, held, new_rows, missing)

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
        path_nodes.check()
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


def _reread_initial_graph_originals(owner, pins, originals, checked):
    """Share adjacent final-reread guards; the caller owns failure/close custody."""
    checked()
    for resource, name, _maximum, contents in originals.values():
        _, path, identity, _ = next(row for row in pins if row[0] is resource)
        native._new_entry_owned(owner, resource, path, identity)
        checked()
        current = owner.read(resource, name, max(1, len(contents)))
        checked()
        # retain() already pinned exact bytes. Refuse custom equality/finalizers
        # before sharing this guard with the next ownership operation.
        require(type(current) is bytes and current == contents, "GRAPH_REREAD_CHANGED")
        del current  # No successful reread result lives across the next I/O.


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
    held, pins, rosters, originals = [], [], [], {}
    path_nodes = _ReaderPathHistory.accumulating()
    missing = object()
    prefix_paths = tuple((resource, resource.path, _ReaderPathHistory(_history_graph(resource.path))) for _, label, resource, _, _ in rows
        if label == "directory")
    used, leaf_failed = 0, False

    def roster(*, tail=False):
        return _graph_reader_roster(owner, ledger, rows, missing, tail=tail)

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
            graph.check()
        # Same saved nodes, order and duplicates; avoid one helper setup per pin.
        path_nodes.check()
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
        _reread_initial_graph_originals(owner, pins, originals, checked)
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
    if original.identity is None:
        return _retain_gate_handoff(original)
    # The CLI still emits only a pending-step digest. It does not serialize or
    # transfer the original-call capability or issue productive Admission.
    return native.public_result(OUTPUT_SCOPE, "initialOriginalsSha256", original.raw), original._fence, original._fence.final


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="operation", required=True)
    commands.add_parser("prepare-originals")
    commands.add_parser("validate-recipient")
    commands.add_parser("sender-step")
    commands.add_parser("initialize-step")
    for name in ("_service", "_service-entry", "_service-authority", "_service-receiving-authority", "_recipient"):
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
        elif args.operation == "sender-step":
            native.guarded(_sender_step)
        elif args.operation == "initialize-step":
            native.guarded(_initialize_step)
        else:
            require(re.fullmatch(r"0|[1-9][0-9]{0,19}", args.minimum_ns), "LAUNCH_MINIMUM")
            minimum = O.integer(int(args.minimum_ns))
            entry = args.operation == "_service-entry"
            receiving = args.operation == "_service-receiving-authority"
            authority = args.operation == "_service-authority" or receiving
            command = (_recipient_command if args.operation == "_recipient" else native.initial_receiving_command if receiving else native.initial_authority_command if authority
                       else native.initial_entry_command if entry else native.initial_command)
            command(args.context_sha256, minimum)
            if args.operation == "_recipient":
                native.guarded(lambda cancelled: _recipient_child(args.context_sha256, minimum, cancelled))
            else:
                native.guarded(lambda cancelled: service_child(args.context_sha256, minimum, cancelled,
                    entry=entry, authority=authority, receiving=receiving))
        return 0
    except BaseException:
        print("INITIAL_RECIPIENT_ORIGINALS_NOT_ACCEPTED", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
