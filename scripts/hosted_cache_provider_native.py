#!/usr/bin/env python3
"""Fixed credential-free native helpers for the bootstrap provider Action.

This command is not a workflow, initial-recipient exception or activation.
Trusted-main admission and the distinct initial public-child route never fall
back to one another. Initial source/HTTP acquisition is in its owned fixed
children, not a token held by this native helper.
All stdout is a PRIVATE child pipe, never a runner command/log stream. A helper
return remains provisional until its original child exit/EOF/close is observed.
No provider, network download, credential acquisition or application runs here.
"""
from __future__ import annotations

import argparse
import base64
from dataclasses import dataclass
import hashlib
import importlib.util
import math
import os
from pathlib import Path
import sys
import time

SCRIPTS = Path(__file__).absolute().parent
sys.path.insert(0, str(SCRIPTS))
# The fixed CLI and per-use checker must share THIS helper registry. Importing
# its ordinary spelling later must not create another module/owner graph.
if __name__ == "__main__":
    sys.modules["hosted_cache_provider_native"] = sys.modules[__name__]
import hosted_cache_provider_prepare as materializer
import hosted_cache_provider_readback as readback

L = materializer.L
B = None
P = None
_ORIGIN = None
_INITIAL_PARENTS = {}
_INITIAL_ENTRY = None
SOURCE_NAME = "provider-source.cjs"
PREPARED_NAME = "provider-prepared.json"
READBACK_NAME = "provider-readback.json"
WORKER_MARGIN_SECONDS = 30  # Inside the old end, not an added retirement budget.
_BASE_CLAIMS = readback.BASE_CLAIMS
_LOOKUP_CLAIMS = readback.LOOKUP_CLAIMS


def _bootstrap():
    global B, _ORIGIN
    L.require(_ORIGIN in (None, "trusted-main"), "PROVIDER_NATIVE_CROSS_ORIGIN")
    _ORIGIN = "trusted-main"
    if B is None:
        spec = importlib.util.spec_from_file_location("fixed_provider_bootstrap", SCRIPTS / "run-hosted-cache-bootstrap.py")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        B = module
    return B


def _initial_bootstrap():
    """Choose the ONE initial C/N/B graph BEFORE allocating any resources."""
    global B, P, _ORIGIN
    L.require(_ORIGIN in (None, "initial-recipient"), "PROVIDER_NATIVE_CROSS_ORIGIN")
    if P is None:
        import hosted_initial_recipient_productive as productive
        P = productive
    L.require(B is None or B is P.B, "PROVIDER_NATIVE_DUPLICATE_INITIAL_GRAPH")
    B, _ORIGIN = P.B, "initial-recipient"
    L.require(P.C.N is P.N and P.N.native is B and P.C.native is B, "PROVIDER_NATIVE_INITIAL_GRAPH")
    return B


def _initial_host_inputs(role):
    # Common actual host/event/selection predicates only, not old Admission or
    # an adopted old directory. The initial directory comes from N.location.
    b = _initial_bootstrap()
    selection, _ordinary_path, event = b.host_inputs(role)
    kind, path = P.N.location()
    L.require(kind == "worker" and P.ROOT == b.ROOT, "PROVIDER_NATIVE_INITIAL_WORKER")
    return selection, path, event


class _Fence:
    """Owner API adapter for the existing provider RAW/LOCAL interval only."""
    def __init__(self, first, issued, end, environment, *, readback_only=False):
        L.require(type(readback_only) is bool, "PROVIDER_NATIVE_FENCE_MODE")
        self.window = L._Window(first, issued, end, end)
        self.environment = environment
        self.clock, self.hard_end = first.clock, end
        # Success-only readback follows the actual supervisor close. It spends
        # the remaining shared final45, not a new allowance. Owner's ordinary
        # end/read/write still check cancellation and original failure state.
        self.work_end = end if readback_only else end - 45 * L.clocks.NS
        self._binding = self.window, environment, self.clock, end, self.work_end

    @property
    def local_end(self):
        return self.window.local_end

    def _local_cap(self, cap):
        # Round the subtracted interval outward, then the resulting deadline
        # inward. This uses the original conversion, never a fresh allowance.
        delta = math.nextafter((self.hard_end - cap) / L.clocks.NS, math.inf)
        return math.nextafter(self.window.local_end - delta, -math.inf)

    def now(self, *, final=False, minimum=0, limit=None):
        L.require(type(final) is bool and
                  (self.window, self.environment, self.clock, self.hard_end, self.work_end) == self._binding,
                  "PROVIDER_NATIVE_FENCE_CHANGED")
        if not final:
            self.environment()
        observed = self.window.check()
        cap = self.hard_end if final else self.work_end
        if limit is not None:
            cap = min(cap, L.clocks.integer(limit))
        L.require(observed >= L.clocks.integer(minimum) and observed < cap and
                  self.window.local_highest < self._local_cap(cap), "PROVIDER_NATIVE_ORIGINAL_END")
        if not final:
            self.environment()
            return self.now(final=True, minimum=observed, limit=cap)
        return observed

    def deadline(self, maximum, *, final=False, limit=None):
        L.require(type(maximum) in (int, float) and math.isfinite(maximum) and maximum > 0,
                  "PROVIDER_NATIVE_MAXIMUM")
        self.now(final=final, limit=limit)
        cap = self.hard_end if final else self.work_end
        if limit is not None:
            cap = min(cap, L.clocks.integer(limit))
        return min(self._local_cap(cap), math.nextafter(self.window.local_highest + maximum, -math.inf))


class _Reader:
    """Only the existing bound-file reader interface on the same live Owner."""
    def __init__(self, owner):
        self.owner = owner

    def end(self, *, new=False):
        return self.owner.end()

    def check(self):
        self.owner.end()

    def acquire(self, label, factory):
        return self.owner.acquire(label, factory)

    def error(self, stage, error):
        self.owner.error(stage, error)

    def close_one(self, value):
        L.require(not self.owner.unknown, "PROVIDER_NATIVE_READER_UNKNOWN")
        self.owner.close_one(value)
        if self.owner.original is not None:
            raise self.owner.original
        L.require(not self.owner.unknown, "PROVIDER_NATIVE_READER_UNKNOWN")


def _claims(phase):
    L.require(phase in ("save", "lookup"), "PROVIDER_NATIVE_PHASE")
    return {name: os.environ.get("P2PKIT_BOOTSTRAP_" + name)
            for name in _BASE_CLAIMS + (_LOOKUP_CLAIMS if phase == "lookup" else ())}


def _descriptor(raw, expected_hash, phase, first, directory):
    return _descriptor_origin("trusted-main", raw, expected_hash, phase, first, directory)


def _initial_descriptor(raw, expected_hash, phase, first, directory):
    return _descriptor_origin("initial-recipient", raw, expected_hash, phase, first, directory)


def _descriptor_origin(origin_kind, raw, expected_hash, phase, first, directory):
    """Read old issuance for early denial, NOT native admission or rederivation."""
    L.require(origin_kind in ("trusted-main", "initial-recipient"), "PROVIDER_NATIVE_DESCRIPTOR_ORIGIN")
    L.require(type(raw) is bytes and hashlib.sha256(raw).hexdigest() == expected_hash,
              "PROVIDER_NATIVE_PREPARATION_HASH")
    value = L.transport._parse(raw, materializer.PREPARATION_LIMIT)
    prefix = "SAVE" if phase == "save" else "PROBE"
    scope_prefix = "BOOTSTRAP_" if origin_kind == "trusted-main" else "INITIAL_RECIPIENT_BOOTSTRAP_"
    L.require(raw == L.files.encoded(value) and value.get("scope") ==
        scope_prefix + prefix + "_PREPARATION_PENDING_ORIGINAL_STEP_RETURN_V1" and
        value.get("directory") == str(directory.path) and value.get("directoryIdentity") == list(directory.identity)
        and value.get("clock") == {"role": first.clock.role, "domain": first.clock.domain,
                                  "ticksPerSecond": first.clock.ticks_per_second}, "PROVIDER_NATIVE_DESCRIPTOR")
    window = value.get("providerWindow")
    L.require(type(window) is dict and set(window) == {"issuedNs", "hardEndNs", "actualProviderStart"} and
              window["actualProviderStart"] == "NOT_OBSERVED", "PROVIDER_NATIVE_WINDOW")
    issued, end = (L.clocks.integer(window[name]) for name in ("issuedNs", "hardEndNs"))
    L.require(issued <= first.nanoseconds < end <= issued + 180 * L.clocks.NS and
              issued + 45 * L.clocks.NS < end, "PROVIDER_NATIVE_ORIGINAL_END")
    contract = L.cache.bootstrap_provider_contract(value["plan"], phase)
    L.require(value.get("providerRequest") == contract["request"] and value["plan"]["role"] == first.clock.role,
              "PROVIDER_NATIVE_REQUEST")
    return value, issued, end, contract


def _graph(owner, fence, phase, claims, first, selection, original_path, event, runner_name,
           prepared_directory, preparation_raw, target):
    """Rederive the fixed graph with the maintained native admission/readers.

    SAVE/PROBE success is never manufactured. Lookup alone consumes the genuine
    preceding save/after-save originals; no later outcome is a preparation input.
    """
    b = _bootstrap()
    session = original_path.with_name(original_path.name + "-productive") / "initializer"
    initializer = owner.open(session)
    handoff_directory = owner.child(initializer, "dependency-save-handoff")
    handoff_raw = owner.read(handoff_directory, "save-handoff.json")
    L.require(b.origin.digest(handoff_raw) == claims["HANDOFF_SHA256"], "PROVIDER_NATIVE_HANDOFF_HASH")
    index = b.origin.parse(handoff_raw)
    proposal_raw = owner.read(handoff_directory, "allocation-proposal.json")
    row = index["blobs"]["allocation-proposal.json"]
    L.require(type(row["bytes"]) is int and row["bytes"] == len(proposal_raw) and
              row["sha256"] == b.origin.digest(proposal_raw), "PROVIDER_NATIVE_PROPOSAL_HASH")
    producer_raw = owner.read(initializer, "producer-function-return.json")
    b._producer_return_record(producer_raw, handoff_raw, claims["PRODUCER_RETURN_SHA256"], first,
                              initializer, handoff_directory)
    admitted, _ = b.admit(owner, fence, target.path / "admission")
    L.require(admitted.original_event == event, "PROVIDER_NATIVE_EVENT_CHANGED")
    owner.write(target, "admission-return.json", owner.admissions[str(target.path / "admission")][2])
    actual_raw, supplied = b._read_save_handoff(owner, initializer, handoff_directory, admitted,
        producer_outcome=claims["PRODUCER_OUTCOME"], expected_sha256=claims["HANDOFF_SHA256"])
    blobs = dict(supplied)
    L.require(actual_raw == handoff_raw and blobs["allocation-proposal.json"] == proposal_raw,
              "PROVIDER_NATIVE_HANDOFF_CHANGED")
    references = []
    reader = _Reader(owner)

    def reference(directory, label, name, *, bound):
        item = index["references"][label]
        L.require(type(item) is dict and set(item) == {"directory", "directoryIdentity", "name", "maximumBytes",
            "bytes", "sha256", "fileBinding", "bindingScope"} and item["directory"] == str(directory.path) and
            item["name"] == name and type(item["maximumBytes"]) is int and item["maximumBytes"] == b.LIMIT and
            type(item["bytes"]) is int and 0 < item["bytes"] <= b.LIMIT and b.staging.cache._sha(item["sha256"]),
            "PROVIDER_NATIVE_REFERENCE")
        b._new_entry_owned(owner, directory, directory.path, item["directoryIdentity"])
        if bound:
            L.require(item["fileBinding"] is not None and item["bindingScope"] == "ORIGINAL_FILE_BINDING",
                      "PROVIDER_NATIVE_REFERENCE_BINDING")
            raw, _ = b.staging._read(reader, directory, name, binding=item["fileBinding"], maximum=item["bytes"])
        else:
            L.require(item["fileBinding"] is None and item["bindingScope"] ==
                "ORIGINAL_DIRECTORY_AND_BYTES_OR_HASH_ONLY_NOT_FILE_IDENTITY", "PROVIDER_NATIVE_REFERENCE_BINDING")
            raw = owner.read(directory, name, item["bytes"])
        L.require(len(raw) == item["bytes"] and b.origin.digest(raw) == item["sha256"], "PROVIDER_NATIVE_REFERENCE_CHANGED")
        references.append((directory, name, item, raw, bound))
        return raw

    service = owner.open(original_path / "service")
    responses = {name: reference(service, "service/" + name, name + ".json", bound=False) for name in ("attempt", "jobs")}
    L.require(index["binding"]["runnerName"] == runner_name, "PROVIDER_NATIVE_RUNNER_CHANGED")
    proposal = b.allocation.validate_proposal(proposal_raw, admitted, responses,
        index["binding"]["invocation"], first.clock, runner_name)
    phase_name = "provider-save" if phase == "save" else "provider-probe"
    L.require(fence.hard_end <= proposal["phaseFencesNs"][phase_name] and
              fence.hard_end <= proposal["proposedJobEndNs"], "PROVIDER_NATIVE_PROPOSAL_END")
    inputs, compiled = b.staging.files.source_inputs(owner, b.ROOT, owner.end(), owner.end)
    profile, role = b.bootstrap.cache_cohort(admitted.record)
    container_path = b.staging.files.stage_path(session, profile, role, admitted_raw=admitted.record)
    container = owner.acquire("provider-stage-container", lambda: b.staging.files.private_root(container_path))
    staging_raw = reference(container, "staging/staging", "staging.json", bound=True)
    deadline = owner.end()
    source = owner.acquire("provider-stage-source", lambda: container.open_directory("restore-home", deadline=deadline))
    stage = b.origin.parse(staging_raw)
    b.staging.files.validate_stage(stage, admitted.record, profile, role, container_path,
                                  container.verify(), source.verify(), inputs)
    plan = b.staging.cache.validate_plan(index["plan"], admitted.record, staging_raw, compiled, inputs,
                                        session=session, profile=profile, role=role, mode="bootstrap")
    b._save_original_inventory(index, blobs, compiled, stage, index["references"]["staging/staging"]["fileBinding"], proposal)
    after_directory = after_raw = after_originals = saved_directory = None
    if phase == "save":
        b._save_preparation_record(preparation_raw, claims["SAVE_PREPARATION_SHA256"], admitted,
            handoff_raw, producer_raw, proposal, first, prepared_directory)
    else:
        after_directory = owner.open(original_path.with_name(original_path.name + "-after-save"))
        saved_directory = owner.open(original_path.with_name(original_path.name + "-save"))
        after_raw, after_originals = b._probe_after_save_records(owner, after_directory, claims["AFTER_SAVE_SHA256"],
            claims, admitted, index, blobs, producer_raw, proposal, first, saved_directory)
        prepared = b._probe_preparation_record(preparation_raw, claims["PROBE_PREPARATION_SHA256"], claims,
            admitted, plan, proposal, first, prepared_directory)
        L.require(b.origin.parse(after_raw)["returnWindow"]["firstNs"] <= prepared["firstNs"],
                  "PROVIDER_NATIVE_PROBE_PREDECESSOR")

    def final_readback():
        final, _ = b.admit(owner, fence, target.path / "final-admission", expected=admitted)
        L.require(final == admitted and b.host_inputs(role) == (selection, original_path, event) and
                  os.environ.get("RUNNER_NAME") == runner_name, "PROVIDER_NATIVE_FINAL_ADMISSION_CHANGED")
        fence.environment()
        b.child_environment(original_path)
        owner.write(target, "final-admission-return.json", owner.admissions[str(target.path / "final-admission")][2])
        L.require(owner.read(handoff_directory, "save-handoff.json") == handoff_raw and
                  owner.read(initializer, "producer-function-return.json") == producer_raw,
                  "PROVIDER_NATIVE_FINAL_ORIGINALS_CHANGED")
        for directory, name, item, raw, bound in references:
            b._new_entry_owned(owner, directory, directory.path, item["directoryIdentity"])
            if bound:
                b.staging._read(reader, directory, name, expected=raw, binding=item["fileBinding"], maximum=len(raw))
            else:
                L.require(owner.read(directory, name) == raw, "PROVIDER_NATIVE_FINAL_REFERENCE_CHANGED")
        if phase == "lookup":
            b._new_entry_owned(owner, after_directory, after_directory.path, b.origin.parse(after_raw)["directoryIdentity"])
            for name, raw in after_originals.items():
                L.require(owner.read(after_directory, name) == raw, "PROVIDER_NATIVE_AFTER_SAVE_CHANGED")
            L.require(owner.read(saved_directory, "save-preparation.json") == after_originals["save-preparation.json"],
                      "PROVIDER_NATIVE_SAVE_PREPARATION_CHANGED")
        fence.now()

    return plan, final_readback


@dataclass(frozen=True, repr=False)
class _InitialProviderParent:
    """An original fixed-helper handle. Its constructor is not authority."""


@dataclass(eq=False, repr=False)
class _InitialParentState:
    parent: object
    owner: object
    fence: object
    first: object
    local_first: float
    work_end: int
    local_work_end: float
    phase: str
    claims: dict
    host: tuple
    runner_name: str
    handoff: object
    target: object
    registration: tuple
    owner_binding: tuple
    graph: tuple
    original_boot: str
    uses: tuple = ()
    site: object = None
    use_binding: object = None
    use_roster: tuple = ()
    use_graph: tuple = ()
    materialized: object = None
    materialized_ns: object = None
    materialized_pin: tuple = ()
    inputs: object = None
    inputs_pin: tuple = ()
    chain: object = None


def _initial_state(parent):
    """Passive registration: compare every field with independent original pins."""
    try:
        saved = _INITIAL_PARENTS.get(id(parent))
        L.require(type(parent) is _InitialProviderParent and type(saved) is tuple and len(saved) == 3,
            "PROVIDER_NATIVE_ORIGINAL_INITIAL_PARENT")
        value, dictionary, items = saved
        L.require(type(value) is _InitialParentState and value.__dict__ is dictionary and
            value.parent is parent and value.registration is _INITIAL_ENTRY and value.registration[3] is parent and
            tuple(dictionary) == tuple(name for name, _original in items) and
            all(dictionary[name] is original for name, original in items),
            "PROVIDER_NATIVE_ORIGINAL_INITIAL_PARENT")
        value.registration[0].check(value.registration[1], value.registration[2])
        return value
    except BaseException as error:
        if _INITIAL_ENTRY is not None:
            raise _INITIAL_ENTRY[0].fail(error)
        raise


def _initial_progress(parent, **updates):
    """Fixed caller updates only; no callback/time/native use or parent creation.

    Check the complete previous snapshot, apply the caller's already-computed
    progress and retain its new independent tuple without an intervening call.
    Immutable parent fields can never be changed through this seam.
    """
    state = _initial_state(parent)
    try:
        L.require(updates and set(updates).issubset({"uses", "site", "use_binding", "use_roster", "use_graph",
            "materialized", "materialized_ns", "materialized_pin", "inputs", "inputs_pin", "chain"}),
            "PROVIDER_NATIVE_INITIAL_PROGRESS_FIELDS")
        for name, value in updates.items():
            state.__dict__[name] = value
        _INITIAL_PARENTS[id(parent)] = (state, state.__dict__, tuple(state.__dict__.items()))
        return state
    except BaseException as error:
        raise _INITIAL_ENTRY[0].fail(error)


def _initial_live_owner(state):
    """Passive actual helper-owner binding; no clock/callback/native operation."""
    owner = state.owner
    dictionary, saved_first, saved_fence, callback, ledger, errors, local, work, final = state.owner_binding
    L.require(type(owner) is B.Owner and type(state.fence) is _Fence and owner.__dict__ is dictionary and
        owner.first is saved_first is state.first and owner.fence is saved_fence is state.fence and
        owner.cancelled is callback and owner.resources is ledger and owner.errors is errors and
        type(owner.local_end) is float and owner.local_end == local and owner.work_limit == work and
        owner.final_limit == final and owner.original is None and owner.unknown is False and owner.closed is False and
        errors == [] and owner.phase_originals is None and owner.admissions == {} and owner.entry_original is None and
        owner.entry_close_attempted is False and owner.entry_close_original is owner.entry_close_snapshot is None,
        "PROVIDER_NATIVE_INITIAL_OWNER_CHANGED")


def _initial_parent_current(state):
    """Real helper clocks/owner/context, not another public HTTP acquisition."""
    import hosted_initial_recipient_productive_adapter as adapter
    entry, attempts, attempt, _parent = _INITIAL_ENTRY
    try:
        entry.check(attempts, attempt)
        L.require(_initial_state(state.parent) is state and _ORIGIN == "initial-recipient" and B is P.B,
            "PROVIDER_NATIVE_INITIAL_PARENT_CHANGED")
        owner, fence, first = state.owner, state.fence, state.first
        _initial_live_owner(state)
        P.N._check_history(state.graph)
        for result, pin in ((state.inputs, state.inputs_pin), (state.materialized, state.materialized_pin)):
            if result is not None:
                L.require(type(pin) is tuple and len(pin) == 2 and result.__dict__ is pin[0],
                    "PROVIDER_NATIVE_INITIAL_RETURN_CHANGED")
                P.N._check_history(pin[1])
        L.require(_claims(state.phase) == state.claims and
            _initial_host_inputs(first.clock.role) == state.host and os.environ.get("RUNNER_NAME") == state.runner_name and
            adapter.checked_handoff_inputs(owner, state.handoff) is state.handoff and
            P.N.continuity.boot_digest(first.clock.role) == state.original_boot,
            "PROVIDER_NATIVE_INITIAL_CONTEXT_CHANGED")
        fence.now(limit=state.work_end)
        L.require(time.monotonic() < state.local_work_end, "PROVIDER_NATIVE_INITIAL_HELPER45")
        entry.check(attempts, attempt)
        P.N._check_history(state.graph)
        L.require(_initial_state(state.parent) is state, "PROVIDER_NATIVE_INITIAL_PARENT_CHANGED")
        _initial_live_owner(state)
        return state
    except BaseException as error:
        raise entry.fail(error)


def _new_initial_parent(owner, fence, phase, claims, first, local_first, host, runner_name, handoff, target):
    global _INITIAL_ENTRY
    if _INITIAL_ENTRY is not None:
        _INITIAL_ENTRY[0].begin(_INITIAL_ENTRY[1])  # Reentry poisons the actual original, not a new attempt.
        raise P.O.OriginError("PROVIDER_NATIVE_INITIAL_REENTRY")
    parent = _InitialProviderParent()
    attempts = {}
    entry = P.C.B.EntryLatch(attempts)
    attempt = entry.begin(attempts)
    registration = entry, attempts, attempt, parent
    _INITIAL_ENTRY = registration
    try:
        history = P.C.canonical(handoff.history)
        observed, path, event = P.N.host_context(history["firstUseAt"])
        L.require(phase in ("save", "lookup") and observed == history["observed"] and
            path == host[1] and event == host[2] == handoff.identity.original_event and
            history["clock"] == P.O.clock_value(first.clock), "PROVIDER_NATIVE_INITIAL_ORIGINAL_HISTORY")
        boot = P.C.digest(P.N.continuity.boot_digest(first.clock.role))
        L.require(boot == history["originalBootDigest"], "PROVIDER_NATIVE_INITIAL_ORIGINAL_BOOT")
        work = min(fence.work_end, P.O.integer(first.nanoseconds + 45 * P.O.NS))
        local_end = min(owner.local_end, fence._local_cap(work),
            P.O.wire._directed_deadline(local_first, 45, work, first.nanoseconds))
        L.require(first.nanoseconds < work and local_first < local_end, "PROVIDER_NATIVE_INITIAL_ORIGINAL_WORK")
        binding = (owner.__dict__, owner.first, owner.fence, owner.cancelled, owner.resources, owner.errors,
            owner.local_end, owner.work_limit, owner.final_limit)
        graph = P.N._history_graph(first, host, claims,
            (handoff.raw, handoff.history, handoff.proposal, handoff.source_records,
             handoff.identity.__dict__, handoff.initializer, handoff.initializer_identity))
        state = _InitialParentState(parent, owner, fence, first, local_first, work, local_end, phase, claims,
            host, runner_name, handoff, target, registration, binding, graph, boot)
        _INITIAL_PARENTS[id(parent)] = (state, state.__dict__, tuple(state.__dict__.items()))
        _initial_parent_current(state)
        return parent
    except BaseException as error:
        raise entry.fail(error)


def checked_initial_use_parent(parent, site):
    """Return the SAME fixed-site binding of this genuine native helper owner."""
    state = _initial_state(parent)
    entry, attempts, attempt, _parent = state.registration
    try:
        _initial_parent_current(state)
        L.require(site in P.U.public.SITES and state.site == site and type(state.use_binding) is P.U.ParentBinding and
            state.use_binding.parent is parent and state.use_binding.site == site and state.chain is None,
            "PROVIDER_NATIVE_INITIAL_CURRENT_SITE")
        ledger = state.owner.resources
        L.require(len(ledger) == len(state.use_roster) and all(row is saved and
            set(row) == {"label", "owner", "attempted", "closed"} and row["label"] == label and
            row["owner"] is resource and row["attempted"] is attempted and row["closed"] is closed
            for row, (saved, label, resource, attempted, closed) in zip(ledger, state.use_roster)),
            "PROVIDER_NATIVE_INITIAL_USE_OWNER_ROSTER")
        P.N._check_history(state.use_graph)
        entry.check(attempts, attempt)
        return state.use_binding
    except BaseException as error:
        raise entry.fail(error)


def _initial_use(parent, edge):
    state = _initial_state(parent)
    entry, attempts, attempt, _parent = state.registration
    try:
        _initial_parent_current(state)
        L.require(edge in ("begin", "final") and state.site is state.use_binding is None and
            len(state.uses) == (0 if edge == "begin" else 1) and state.chain is None and
            (state.materialized is None if edge == "begin" else type(state.materialized) is materializer.PreparedProvider),
            "PROVIDER_NATIVE_INITIAL_SITE_ORDER")
        site = ("provider-save" if state.phase == "save" else "provider-probe") + "/native-prepare/" + edge
        handoff = state.handoff
        binding = P.U.ParentBinding(parent, site, state.first, state.local_first, state.work_end,
            state.local_work_end, state.original_boot, handoff, handoff.identity, handoff.history, handoff.proposal,
            handoff.source_records, handoff.initializer, handoff.initializer_identity)
        roster = tuple((row, row["label"], row["owner"], row["attempted"], row["closed"])
            for row in state.owner.resources)
        _initial_progress(parent, site=site, use_binding=binding, use_roster=roster,
            use_graph=P.N._history_graph(binding.__dict__))
        result = P.acquire_public(parent, site)
        current = P.consume_use(result, parent, site)
        # A consumed historical result cannot serve the other seam.
        _initial_progress(parent, uses=(*state.uses, result), site=None, use_binding=None,
            use_roster=(), use_graph=())
        P.checked_consumed_use(result, parent, site)
        state.owner.write(state.target, edge + "-use.json", result.raw)
        state.owner.write(state.target, edge + "-use-index.json", result.inventory)
        _initial_parent_current(state)
        return current
    except BaseException as error:
        raise entry.fail(error)


def _initial_graph(owner, fence, phase, claims, first, local_first, selection, original_path, event,
                   runner_name, prepared_directory, preparation_raw, target):
    """Initial native admission sites around the SAME maintained materializer."""
    import hosted_initial_recipient_productive_adapter as adapter
    handoff = adapter.read_productive_handoff(owner, first, claims)
    parent = _new_initial_parent(owner, fence, phase, claims, first, local_first,
        (selection, original_path, event), runner_name, handoff, target)
    state = _initial_state(parent)
    admitted = _initial_use(parent, "begin")
    inputs = adapter.rederive_provider_inputs(owner, handoff, admitted)
    _initial_progress(parent, inputs=inputs, inputs_pin=(inputs.__dict__, P.N._history_graph(inputs.__dict__)))
    adapter.validate_provider_preparation(owner, handoff, inputs, phase, claims,
        prepared_directory, preparation_raw, first)
    plan = inputs.plan
    proposal = P._proposal(handoff.proposal, admitted, P.C.canonical(handoff.history), first.clock)
    phase_name = "provider-save" if phase == "save" else "provider-probe"
    L.require(fence.hard_end <= proposal["phaseFencesNs"][phase_name] and
        fence.hard_end <= proposal["proposedJobEndNs"], "PROVIDER_NATIVE_INITIAL_PROPOSAL_END")

    def final_readback(materialized):
        entry, attempts, attempt, _parent = state.registration
        try:
            # Retain the actual materializer return BEFORE the first callback.
            L.require(type(materialized) is materializer.PreparedProvider and type(materialized.__dict__) is dict,
                "PROVIDER_NATIVE_INITIAL_MATERIALIZER_TYPE")
            materialized_pin = materialized.__dict__, P.N._history_graph(materialized.__dict__)
            _initial_parent_current(state)
            L.require(state.materialized is None and type(materialized) is materializer.PreparedProvider and
                materialized.__dict__ is materialized_pin[0] and materialized.preparation_sha256 ==
                hashlib.sha256(preparation_raw).hexdigest() and state.inputs is inputs and
                materialized.scope == "PROVIDER_NATIVE_FILES_PENDING_ORIGINAL_OWNER_CLOSE_V1" and
                materialized.enclosing_owner_close == "NOT_OBSERVED" and materialized.provider_execution == "NOT_PERFORMED" and
                materialized.provider_acceptance == "NOT_ESTABLISHED",
                "PROVIDER_NATIVE_INITIAL_MATERIALIZER_RETURN")
            P.N._check_history(materialized_pin[1])
            context, _contract = readback.outer._context(materialized.request)
            L.require(context["phase"] == phase and context["plan"] == plan and
                context["directory"] == str(prepared_directory.path / "provider"),
                "PROVIDER_NATIVE_INITIAL_MATERIALIZER_BINDING")
            materialized_ns = fence.now(limit=state.work_end)
            P.N._check_history(materialized_pin[1])
            L.require(materialized.__dict__ is materialized_pin[0] and
                first.nanoseconds <= L.clocks.integer(materialized.checked_ns) <= materialized_ns,
                "PROVIDER_NATIVE_INITIAL_MATERIALIZER_TIME")
            _initial_progress(parent, materialized=materialized, materialized_ns=materialized_ns,
                materialized_pin=materialized_pin)
            final = _initial_use(parent, "final")
            L.require(P.N._worker_fields(final) == P.N._worker_fields(admitted),
                "PROVIDER_NATIVE_INITIAL_FINAL_IDENTITY_CHANGED")
            adapter.recheck_provider_inputs(owner, inputs)
            adapter.validate_provider_preparation(owner, handoff, inputs, phase, claims,
                prepared_directory, preparation_raw, first)
            _initial_parent_current(state)
            B.child_environment(original_path)
            uses = []
            for result in state.uses:
                P.checked_consumed_use(result, parent, result.site)
                window_raw = dict(result.originals)["use-window.json"]
                uses.append({"site": result.site, "root": str(result.path), "window": P.C.canonical(window_raw),
                    "returnSha256": P.O.digest(result.raw), "inventorySha256": P.O.digest(result.inventory)})
            chain = {"schema": 1, "scope": "INITIAL_RECIPIENT_PROVIDER_ORIGINAL_USE_CHAIN_V1", "phase": phase,
                "clock": P.O.clock_value(first.clock), "originalBootDigest": state.original_boot,
                "helperFirstNs": first.nanoseconds, "helperWorkEndNs": state.work_end,
                "providerIssuedNs": fence.window.issued, "providerHardEndNs": fence.hard_end,
                "handoffSha256": claims["HANDOFF_SHA256"], "producerReturnSha256": claims["PRODUCER_RETURN_SHA256"],
                "preparationSha256": hashlib.sha256(preparation_raw).hexdigest(),
                "workerIdentitySha256": P.O.digest(admitted.record), "directory": str(target.path),
                "directoryIdentity": list(target.identity), "source": plan["source"], "github": plan["github"],
                "materializedNs": state.materialized_ns, "uses": uses, "checkedNs": fence.now(limit=state.work_end),
                "helperOwnerClose": "PENDING_NOT_OBSERVABLE_BY_THIS_FILE", "providerExecution": "NOT_PERFORMED",
                "exportSaveAuthority": False}
            raw = owner.write(target, "initial-use-chain.json", chain)
            _initial_parent_current(state)
            _initial_progress(parent, chain=raw)
            entry.complete(attempts, attempt, raw)
            return hashlib.sha256(raw).hexdigest()
        except BaseException as error:
            raise entry.fail(error)

    return plan, final_readback


@dataclass(frozen=True, repr=False)
class _InitialOutputFence:
    """Post-close stdout checks under the SAME helper45, never a new phase."""
    parent: object
    roster: tuple

    def _closed(self, state):
        owner = state.owner
        dictionary, saved_first, saved_fence, callback, ledger, errors, local, work, final = state.owner_binding
        L.require(type(self) is _InitialOutputFence and type(owner) is B.Owner and owner.__dict__ is dictionary and
            owner.fence is saved_fence is state.fence and owner.first is saved_first is state.first and
            owner.cancelled is callback and owner.resources is ledger and owner.errors is errors and
            owner.local_end == local and owner.work_limit == work and owner.final_limit == final and
            owner.original is None and owner.errors == [] and owner.closed is True and owner.unknown is False and
            owner.phase_originals is None and owner.admissions == {} and owner.entry_original is None and
            owner.entry_close_attempted is False and owner.entry_close_original is owner.entry_close_snapshot is None and
            len(ledger) == len(self.roster) and all(row is old and
                set(row) == {"label", "owner", "attempted", "closed"} and row["label"] == label and
                row["owner"] is resource and row["attempted"] is row["closed"] is True
                for row, (old, label, resource) in zip(ledger, self.roster)),
            "PROVIDER_NATIVE_INITIAL_OUTPUT_OWNER")

    def now(self, *, final=False, limit=None):
        entry = _INITIAL_ENTRY[0]
        try:
            state = _initial_state(self.parent)
            L.require(final is True and state.chain is not None and len(state.uses) == 2,
                "PROVIDER_NATIVE_INITIAL_OUTPUT_ONLY")
            entry.returned(state.registration[1], state.registration[2], state.chain)
            self._closed(state)
            end = state.work_end if limit is None else min(state.work_end, L.clocks.integer(limit))
            L.require(P.U.local_value(time.monotonic()) < state.local_work_end, "PROVIDER_NATIVE_INITIAL_HELPER45")
            observed = state.fence.now(final=True, limit=end)
            state.fence.environment()
            for returned in state.uses:
                P.checked_consumed_use(returned, state.parent, returned.site)
            P.N._check_history(state.graph)
            for returned, pin in ((state.inputs, state.inputs_pin), (state.materialized, state.materialized_pin)):
                L.require(returned.__dict__ is pin[0], "PROVIDER_NATIVE_INITIAL_RETURN_CHANGED")
                P.N._check_history(pin[1])
            L.require(_initial_state(self.parent) is state and
                P.U.local_value(time.monotonic()) < state.local_work_end, "PROVIDER_NATIVE_INITIAL_HELPER45")
            observed = state.fence.now(final=True, minimum=observed, limit=end)
            L.require(P.U.local_value(time.monotonic()) < state.local_work_end, "PROVIDER_NATIVE_INITIAL_HELPER45")
            L.require(_initial_state(self.parent) is state, "PROVIDER_NATIVE_INITIAL_PARENT_CHANGED")
            self._closed(state)
            entry.returned(state.registration[1], state.registration[2], state.chain)
            return observed
        except BaseException as error:
            raise entry.fail(error)


def operate(operation, phase, cancelled, *, node=None, tool_path=None, prepared_sha256=None,
            acknowledgement=None, minimum_ns=None):
    """Trusted-main fixed operations; no initial-recipient fallback."""
    return _operate("trusted-main", operation, phase, cancelled, node=node, tool_path=tool_path,
        prepared_sha256=prepared_sha256, acknowledgement=acknowledgement, minimum_ns=minimum_ns)


def operate_initial(operation, phase, cancelled, *, node=None, tool_path=None, prepared_sha256=None,
                    acknowledgement=None, minimum_ns=None):
    """Initial-only fixed operations, with actual public begin AND final uses."""
    return _operate("initial-recipient", operation, phase, cancelled, node=node, tool_path=tool_path,
        prepared_sha256=prepared_sha256, acknowledgement=acknowledgement, minimum_ns=minimum_ns)


def _operate(origin_kind, operation, phase, cancelled, *, node, tool_path, prepared_sha256,
             acknowledgement, minimum_ns):
    """One unchanged native/provider engine behind two closed source routes."""
    L.require(origin_kind in ("trusted-main", "initial-recipient"), "PROVIDER_NATIVE_FIXED_ORIGIN")
    initial = origin_kind == "initial-recipient"
    b = _initial_bootstrap() if initial else _bootstrap()
    host = _initial_host_inputs if initial else b.host_inputs
    native_prefix = "INITIAL_RECIPIENT_" if initial else ""
    L.require(operation in ("window", "prepare", "readback"), "PROVIDER_NATIVE_OPERATION")
    local = time.monotonic()
    first = L.clocks.validate_reading(L.clocks.observe())
    claims = _claims(phase)

    def environment():
        L.require(_claims(phase) == claims and b.origin.wire.TOKEN_ENV not in os.environ and
            not any(name in os.environ for name in (*L.environment.SERVICE_FIELDS, "GH_TOKEN", "GITHUB_TOKEN")),
            "PROVIDER_NATIVE_CREDENTIAL_FREE_CONTEXT")
        if initial:
            P._credential_free()
        L.require(all(type(value) is str and value == "success" for name, value in claims.items() if name.endswith("OUTCOME"))
            and all(type(value) is str and L.re.fullmatch(r"[0-9a-f]{64}", value)
                    for name, value in claims.items() if name.endswith("SHA256")), "PROVIDER_NATIVE_ORIGINAL_CLAIMS")
        b.cancellation(cancelled)

    owner = fence = result = directory = target = None
    failure = None
    try:
        environment()
        L.require(not b.QUARANTINE and not b.query.QUARANTINE and not b.diagnostics._QUARANTINE,
                  "PROVIDER_NATIVE_PRIOR_UNKNOWN")
        selection, original_path, event = host(first.clock.role)
        b.child_environment(original_path)
        runner_name = os.environ.get("RUNNER_NAME")
        # Existing Owner metadata ceiling, immediately shortened by old issuance.
        # It is not a new provider interval, admission or allocation.
        owner = b.Owner(math.nextafter(local + 45, -math.inf), first=first, cancelled=environment)
        suffix, prefix = ("-save", "SAVE") if phase == "save" else ("-probe", "PROBE")
        directory = owner.open(original_path.with_name(original_path.name + suffix))
        filename = "save-preparation.json" if phase == "save" else "probe-preparation.json"
        preparation_raw = owner.read(directory, filename)
        expected_hash = claims[prefix + "_PREPARATION_SHA256"]
        prepared, issued, end, contract = (_initial_descriptor if initial else _descriptor)(
            preparation_raw, expected_hash, phase, first, directory)
        fence = _Fence(first, issued, end, environment, readback_only=operation == "readback")
        cap = end if operation == "readback" else end - 45 * L.clocks.NS
        owner.bind(fence, work_limit=cap, final_limit=end)
        fence.now(final=operation == "readback", limit=cap)
        if operation == "window":
            result = {"scope": native_prefix + "PROVIDER_ORIGINAL_WINDOW_PENDING_HELPER_RETURN_V1", "phase": phase,
                "preparationSha256": expected_hash, "directory": str(directory.path),
                "directoryIdentity": list(directory.identity), "bundle": contract["bundle"],
                "clock": b.origin.clock_value(first.clock), "firstNs": str(first.nanoseconds),
                "issuedNs": str(issued), "hardEndNs": str(end), "providerAdmission": "NOT_ESTABLISHED"}
        elif operation == "prepare":
            target = owner.child(directory, "native-preparation", create=True)
            if initial:
                plan, final_readback = _initial_graph(owner, fence, phase, claims, first, local, selection,
                    original_path, event, runner_name, directory, preparation_raw, target)
            else:
                plan, final_readback = _graph(owner, fence, phase, claims, first, selection, original_path, event,
                    runner_name, directory, preparation_raw, target)
            bundle = owner.read(directory, SOURCE_NAME, contract["bundle"]["bytes"])
            cut = end - WORKER_MARGIN_SECONDS * L.clocks.NS
            materialize = materializer.materialize_initial_recipient if initial else materializer.materialize
            value = materialize(owner, directory, preparation_raw, expected_hash,
                claims[prefix + "_PREPARE_OUTCOME"], phase=phase, plan=plan, bundle_raw=bundle,
                node=node, tool_path=tool_path, worker_cutoff_ns=cut)
            extra = {"initialUseChainSha256": final_readback(value)} if initial else {}
            if not initial:
                final_readback()
            packet = {"scope": native_prefix + "PROVIDER_NATIVE_PREPARATION_PENDING_HELPER_RETURN_V1", "phase": phase,
                "preparationSha256": expected_hash, "request": value.request.decode("ascii"),
                "bindings": dict(value.bindings), "clockBindings": dict(value.clock_bindings),
                "firstNs": str(first.nanoseconds), "originalClaims": claims,
                "providerExecution": "NOT_PERFORMED", "enclosingActionReturn": "NOT_OBSERVED", **extra}
            raw = owner.write(directory, PREPARED_NAME, packet)
            if initial:
                use_originals = {name: owner.read(target, name) for name in readback.INITIAL_USE_FILES}
                readback.validate_initial_use_chain(use_originals, raw, preparation_raw, first, phase=phase)
            result = {**packet, "preparedSha256": hashlib.sha256(raw).hexdigest()}
        else:
            L.require(type(prepared_sha256) is str and L.re.fullmatch(r"[0-9a-f]{64}", prepared_sha256) and
                      type(acknowledgement) is bytes, "PROVIDER_NATIVE_READBACK_INPUT")
            raw = owner.read(directory, PREPARED_NAME)
            L.require(hashlib.sha256(raw).hexdigest() == prepared_sha256, "PROVIDER_NATIVE_PREPARED_HASH")
            packet = b.origin.parse(raw)
            L.require(raw == b.origin.encoded(packet) and packet.get("scope") ==
                native_prefix + "PROVIDER_NATIVE_PREPARATION_PENDING_HELPER_RETURN_V1" and packet.get("phase") == phase and
                packet.get("preparationSha256") == expected_hash and packet.get("originalClaims") == claims and
                packet.get("providerExecution") == "NOT_PERFORMED" and packet.get("enclosingActionReturn") == "NOT_OBSERVED",
                "PROVIDER_NATIVE_PREPARED_BINDING")
            extra = {}
            if initial:
                target = owner.child(directory, "native-preparation")
                use_originals = {name: owner.read(target, name) for name in readback.INITIAL_USE_FILES}
                readback.validate_initial_use_chain(use_originals, raw, preparation_raw, first, phase=phase)
                extra = {"initialUseChainSha256": packet["initialUseChainSha256"]}
            request = packet["request"].encode("ascii")
            context, _ = readback.outer._context(request)
            L.require(context["phase"] == phase and context["plan"] == prepared["plan"] and
                int(context["issuedNs"]) == issued and int(context["hardEndNs"]) == end and
                context["directory"] == str(directory.path / "provider") and
                context["home"] == str(directory.path / "provider-home") and
                int(context["firstNs"]) <= L.clocks.integer(minimum_ns) <= first.nanoseconds,
                "PROVIDER_NATIVE_READBACK_CONTEXT")
            provider_directory = owner.child(directory, "provider")
            value = readback.read_success(owner, provider_directory, request, acknowledgement, 0,
                python=str(L._path(sys.executable, first.clock.role)), bindings=packet["bindings"])
            # Actual fixed-file readback stays private; only checked output fields
            # and binding hashes leave this helper. Acceptance is still external.
            retained = owner.write(directory, READBACK_NAME, {"scope": native_prefix + "PROVIDER_NATIVE_READBACK_PENDING_HELPER_RETURN_V1",
                "phase": phase, "preparedSha256": prepared_sha256, "preparationSha256": expected_hash,
                "acknowledgement": acknowledgement.decode("ascii"),
                "acknowledgementSha256": hashlib.sha256(acknowledgement).hexdigest(),
                "python": str(L._path(sys.executable, first.clock.role)),
                "workerRequestSha256": hashlib.sha256(value.worker_request).hexdigest(),
                "outputs": dict(value.provider.outputs), "checkedNs": str(value.checked_ns),
                "originalClaims": claims, "enclosingActionReturn": "NOT_OBSERVED", "providerAcceptance": "NOT_ESTABLISHED", **extra})
            result = {"scope": native_prefix + "PROVIDER_NATIVE_READBACK_PENDING_HELPER_RETURN_V1", "phase": phase,
                "readbackSha256": hashlib.sha256(retained).hexdigest(), "outputs": dict(value.provider.outputs),
                "providerAcceptance": "NOT_ESTABLISHED"}
        L.require(owner.read(directory, filename) == preparation_raw, "PROVIDER_NATIVE_FINAL_PREPARATION_CHANGED")
        L.require(host(first.clock.role) == (selection, original_path, event) and
                  os.environ.get("RUNNER_NAME") == runner_name, "PROVIDER_NATIVE_FINAL_HOST_CHANGED")
        environment()
        b.child_environment(original_path)
        fence.now(final=operation == "readback", limit=cap)
        ledger, errors = owner.resources, owner.errors
        roster = tuple((row, row["label"], row["owner"]) for row in ledger)
    except BaseException as error:
        failure = owner.original if owner is not None and owner.original is not None else error
        if initial and _INITIAL_ENTRY is not None:
            failure = _INITIAL_ENTRY[0].fail(failure)
        if owner is not None:
            try:
                owner.error("provider-native", error)
            except BaseException:
                owner.unknown = True
    finally:
        if owner is not None:
            try:
                owner.close()
                if owner.original is not None:
                    failure = owner.original
            except BaseException as error:
                failure = owner.original if owner.original is not None else failure or error
    if failure is not None:
        if initial and _INITIAL_ENTRY is not None:
            failure = _INITIAL_ENTRY[0].fail(failure)
        raise failure
    try:
        L.require(owner.closed and not owner.unknown and not errors and owner.resources is ledger and owner.errors is errors
            and len(ledger) == len(roster) and all(row is old and row["label"] == label and row["owner"] is resource and
                row["attempted"] is row["closed"] is True for row, (old, label, resource) in zip(ledger, roster)) and
            not b.QUARANTINE and not b.query.QUARANTINE and not b.diagnostics._QUARANTINE, "PROVIDER_NATIVE_OWNER_CLOSE")
        output_fence = fence
        if initial and operation == "prepare":
            state = _initial_state(_INITIAL_ENTRY[3])
            _INITIAL_ENTRY[0].returned(_INITIAL_ENTRY[1], _INITIAL_ENTRY[2], state.chain)
            L.require(state.owner is owner and state.chain is not None and
                hashlib.sha256(state.chain).hexdigest() == result["initialUseChainSha256"],
                "PROVIDER_NATIVE_INITIAL_CHAIN_CLOSE")
            for result_use in state.uses:
                P.checked_consumed_use(result_use, state.parent, result_use.site)
            output_fence = _InitialOutputFence(state.parent, roster)
            cap = min(cap, state.work_end)
        result["observedNs"] = str(output_fence.now(final=True, limit=cap))
        result["ownerClose"] = "KNOWN_RESOURCE_CLOSE_ONLY"
        result["originalHelperReturn"] = "PENDING"
        environment()
        return result, output_fence, cap
    except BaseException as error:
        if initial and _INITIAL_ENTRY is not None:
            raise _INITIAL_ENTRY[0].fail(error)
        raise


def main():
    try:
        L.require(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode and
            os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted" and
            os.environ.get("GITHUB_REPOSITORY") == "p2pKit/P2pKit", "PROVIDER_NATIVE_ACTUAL_HOSTED_CALLER")
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("operation", choices=("window", "prepare", "readback",
            "initial-window", "initial-prepare", "initial-readback"))
        parser.add_argument("phase", choices=("save", "lookup"))
        parser.add_argument("--node")
        parser.add_argument("--tool-path")
        parser.add_argument("--prepared-sha256")
        parser.add_argument("--acknowledgement")
        parser.add_argument("--minimum-ns")
        args = parser.parse_args()
        ack = None if args.acknowledgement is None else base64.b64decode(args.acknowledgement, validate=True)
        minimum = None if args.minimum_ns is None else L._ns(args.minimum_ns)
        initial = args.operation in ("initial-window", "initial-prepare", "initial-readback")
        b = _initial_bootstrap() if initial else _bootstrap()
        operation = args.operation.removeprefix("initial-") if initial else args.operation
        fixed = operate_initial if initial else operate
        b.guarded(lambda cancelled: fixed(operation, args.phase, cancelled, node=args.node,
            tool_path=args.tool_path, prepared_sha256=args.prepared_sha256, acknowledgement=ack, minimum_ns=minimum))
        return 0
    except BaseException as error:
        if _ORIGIN == "initial-recipient" and _INITIAL_ENTRY is not None:
            _INITIAL_ENTRY[0].fail(error)
        print("CACHE_PROVIDER_NATIVE_NOT_ACCEPTED", file=sys.stderr)
        return 125


if __name__ == "__main__":
    raise SystemExit(main())
