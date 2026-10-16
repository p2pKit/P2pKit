"""Dormant bootstrap-only staging and read-only known-empty seed suppliers.

No CLI, workflow, restore, dependency copier, producer, export/save or deletion.
The caller supplies original initializer/phase evidence and an existing live
owner. Consistent supplied evidence cannot authenticate that predecessor, its
return or single use: the same-call parent bridge is deliberately still absent.
Ordinary seed/export/save entry points and their bootstrap refusals are unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from pathlib import Path
import re
import time

import hosted_cache_bootstrap_allocation as allocation
import hosted_cache_bootstrap_initialization as initialization
import hosted_dependency_cache as cache
import hosted_dependency_seed_files as files
import hosted_initial_recipient_productive_data as initial


origin = allocation.origin
NS = origin.NS
ROOT = Path(__file__).resolve().parents[1]
STAGE_SCOPE = "BOOTSTRAP_EMPTY_STAGING_LEAF_V1"
SEED_SCOPE = "BOOTSTRAP_KNOWN_EMPTY_SEED_LEAF_V1"
EMPTY = "KNOWN_EMPTY_OBSERVED"
# Separate bootstrap provenance; do not widen files.INPUTS or the provider key.
BOOTSTRAP_INPUTS = (
    "scripts/hosted_cache_bootstrap_staging.py", "scripts/hosted_cache_bootstrap_allocation.py",
    "scripts/hosted_cache_bootstrap_service_time.py", "scripts/hosted_cache_bootstrap_origin.py",
    "scripts/hosted_cache_bootstrap_initialization.py", "scripts/hosted_cache_bootstrap_canonical.py",
    "scripts/hosted_cache_bootstrap_producer.py", "scripts/run-hosted-cache-bootstrap.py",
    "scripts/hosted_job_clock.py",
)
DIRECTORIES = ("session", "state", "gradle-home", "evidence", "cancellations")
COUNTERS = ("prehashBytes", "outputBytes", "sourceNames", "destinationMembers", "sha256Rejected", "layoutRejected")


def require(value, reason):
    files.require(value, reason)


def _local(value):
    require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
            "BOOTSTRAP_SEED_LOCAL_CLOCK")
    return float(value)


def _identity(value, role):
    require(type(value) in (list, tuple) and files._identity(list(value)), "BOOTSTRAP_SEED_DIRECTORY_IDENTITY")
    require(type(value[1]) is (str if role == "windows-x64" else int), "BOOTSTRAP_SEED_NATIVE_IDENTITY")
    return tuple(value)


def _clock(value):
    origin.clocks.validate_identity(value)
    return value.role, value.domain, value.ticks_per_second


def _bytes(raw, maximum=files.RECEIPT_LIMIT):
    require(type(raw) is bytes and 0 < len(raw) <= maximum, "BOOTSTRAP_SEED_ORIGINAL_BYTES")
    return raw


@dataclass(frozen=True)
class Originals:
    """Supplied original data, NOT an initializer/next-phase authority token."""
    admitted: object = field(repr=False)
    responses: dict = field(repr=False)
    invocation: str = field(repr=False)
    clock: object = field(repr=False)
    runner_name: str = field(repr=False)
    proposal_raw: bytes = field(repr=False)
    original_session: str = field(repr=False)
    initializer_context_raw: bytes = field(repr=False)
    canonical_raw: bytes = field(repr=False)
    properties_raw: bytes = field(repr=False)
    directories: dict = field(repr=False)
    initializer_closed_raw: bytes = field(repr=False)
    initializer_checked_ns: int = field(repr=False)
    initializer_checked_local: float = field(repr=False)


@dataclass(frozen=True)
class PhaseStart:
    """Original first observations, supplied before this leaf; never renewed."""
    first: object = field(repr=False)
    local_started: float = field(repr=False)


@dataclass(frozen=True)
class LeafEvidence:
    """Return evidence only. A copied/mutated object grants no execution rights."""
    raw: bytes = field(repr=False)
    staging_raw: bytes = field(repr=False)
    checked_ns: int = field(repr=False)
    local_started: float = field(repr=False)
    checked_local: float = field(repr=False)


def _capture(value):
    """Independent immutable scalars/bytes BEFORE clocks, owners or callbacks."""
    require(type(value) is Originals and type(value.admitted) is origin.bootstrap.ordinary.Admission,
            "BOOTSTRAP_SEED_ORIGINAL_INPUTS")
    admitted = value.admitted
    admission = tuple(_bytes(getattr(admitted, name)) for name in
                      ("record", "original_event", "original_policy", "public_key"))
    require(type(admitted.fingerprint) is str and type(admitted.key_sha256) is str and
            type(admitted.expires_at) is int, "BOOTSTRAP_SEED_ADMISSION_FIELDS")
    admission += (admitted.fingerprint, admitted.key_sha256, admitted.expires_at)
    clock = _clock(value.clock)
    require(type(value.responses) is dict and set(value.responses) == {"attempt", "jobs"} and
            type(value.directories) is dict and set(value.directories) == set(DIRECTORIES),
            "BOOTSTRAP_SEED_ORIGINAL_ROSTER")
    responses = tuple((name, _bytes(value.responses[name])) for name in ("attempt", "jobs"))
    directories = tuple((name, _identity(value.directories[name], clock[0])) for name in DIRECTORIES)
    require(type(value.invocation) is str and re.fullmatch(r"[0-9a-f]{32}", value.invocation) and
            type(value.runner_name) is str and type(value.original_session) is str,
            "BOOTSTRAP_SEED_ORIGINAL_LABELS")
    return (admission, responses, value.invocation, clock, value.runner_name, _bytes(value.proposal_raw),
            value.original_session, _bytes(value.initializer_context_raw), _bytes(value.canonical_raw),
            _bytes(value.properties_raw, 16384), directories, _bytes(value.initializer_closed_raw),
            origin.integer(value.initializer_checked_ns), _local(value.initializer_checked_local))


def _capture_phase(value):
    require(type(value) is PhaseStart, "BOOTSTRAP_SEED_ORIGINAL_PHASE")
    origin.clocks.validate_reading(value.first)
    return _clock(value.first.clock), value.first.nanoseconds, _local(value.local_started)


def _capture_evidence(value):
    require(type(value) is LeafEvidence, "BOOTSTRAP_SEED_STAGE_RETURN_REQUIRED")
    return (_bytes(value.raw), _bytes(value.staging_raw), origin.integer(value.checked_ns),
            _local(value.local_started), _local(value.checked_local))


class _Inputs:
    def __init__(self, published, snapshot):
        self.published, self.snapshot = published, snapshot
        (admission, responses, self.invocation, clock, self.runner, self.proposal_raw,
         original_session, self.context_raw, self.canonical_raw, self.properties_raw, directories,
         self.closed_raw, self.previous_ns, self.previous_local) = snapshot
        # Fresh private data objects, not the caller's nominally frozen objects.
        self.admitted = origin.bootstrap.ordinary.Admission(*admission)
        self.clock = origin.clocks.ClockIdentity(*clock)
        self.responses, self.directories = dict(responses), dict(directories)
        self.proposal = allocation.validate_proposal(self.proposal_raw, self.admitted, self.responses,
                                                    self.invocation, self.clock, self.runner)
        self.admission = origin.admitted_value(self.admitted)
        self.profile, self.role = origin.bootstrap.cache_cohort(self.admitted.record)
        github = self.admission["github"]
        original = initialization.producer._path(original_session, self.role)
        require(original.name == "p2pkit-cache-originals-" + github["runId"] + "-" + github["runAttempt"] +
                "-" + self.admission["selection"], "BOOTSTRAP_SEED_INITIALIZER_LAYOUT")
        self.session = original.with_name(original.name + "-productive") / "initializer"
        self.state, self.home = self.session / "state", self.session / "state/gradle-home"
        self.root = str(ROOT)
        self.container = files.stage_path(self.session, self.profile, self.role, admitted_raw=self.admitted.record)
        self.restore = self.container / "restore-home"
        context = origin.parse(self.context_raw)
        require(set(context) == {"schema", "scope", "job", "previousSha256", "requestSha256",
                "admissionSha256", "clock", "directories", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"}
                and type(context["schema"]) is int and context["schema"] == 1 and
                context["scope"] == "BOOTSTRAP_INITIALIZER_PARENT_CONTEXT_V1" and
                context["admissionSha256"] == files.digest(self.admitted.record) and
                context["clock"] == origin.clock_value(self.clock) and
                context["budgetAcceptance"] == "NOT_ADMITTED" and context["testAcceptance"] == "NOT_PERFORMED" and
                context["exportSaveAuthority"] is False and self.context_raw == origin.encoded(context),
                "BOOTSTRAP_SEED_INITIALIZER_CONTEXT")
        require(all(type(context[name]) is str and re.fullmatch(r"[0-9a-f]{64}", context[name])
                    for name in ("previousSha256", "requestSha256")) and
                type(context["directories"]) is dict and set(context["directories"]) ==
                {"session", "canonical-init", "control-home", "temporary"}, "BOOTSTRAP_SEED_INITIALIZER_DIRECTORIES")
        initial_ids = {name: _identity(value, self.role) for name, value in context["directories"].items()}
        require(initial_ids["session"] == self.directories["session"] and
                len(set((*initial_ids.values(), *[self.directories[name] for name in DIRECTORIES[1:]]))) == 8,
                "BOOTSTRAP_SEED_INITIALIZER_ALIASES")
        canonical = initialization.producer.parse(self.canonical_raw)
        require(type(canonical.get("javaHomes")) is list and all(type(home) is str for home in canonical["javaHomes"]),
                "BOOTSTRAP_SEED_CANONICAL_HOMES")
        self.canonical = initialization.context_record(self.canonical_raw, admitted_raw=self.admitted.record,
            root=self.root, state=str(self.state), role=self.role, outer_job=context["job"],
            homes=tuple(canonical["javaHomes"]), policy_raw=self.properties_raw)
        # Canonical initialize() emits indented JSON. Hash/reread EXACT bytes,
        # never require the compact encoding used by our own leaf records.
        closed = origin.parse(self.closed_raw)
        require(set(closed) == {"schema", "scope", "recipientClosedSha256", "pendingSha256", "window", "closedNs",
                "resourceCount", "parentResourceClose", "childReturn", "nextPhaseAuthority", "budgetAcceptance",
                "testAcceptance", "exportSaveAuthority"} and type(closed["schema"]) is int and closed["schema"] == 1 and
                closed["scope"] == "BOOTSTRAP_INITIALIZER_PREFIX_CLOSED_NO_EXECUTION_V1" and
                closed["recipientClosedSha256"] == context["previousSha256"] and
                type(closed["pendingSha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", closed["pendingSha256"]) and
                type(closed["resourceCount"]) is int and closed["resourceCount"] > 0 and
                closed["parentResourceClose"] == "KNOWN_RESOURCE_CLOSE_ONLY" and
                closed["childReturn"] == "INITIALIZED_CONTEXT_NOT_PRODUCT_RECEIPT" and
                closed["nextPhaseAuthority"] is False and closed["exportSaveAuthority"] is False and
                closed["budgetAcceptance"] == "NOT_ADMITTED" and closed["testAcceptance"] == "NOT_PERFORMED" and
                self.closed_raw == origin.encoded(closed), "BOOTSTRAP_SEED_INITIALIZER_CLOSED_RECORD")
        window = closed["window"]
        require(type(window) is dict and set(window) == {"clock", "firstNs", "workEndNs", "nativeEndNs",
                "prefixEndNs", "finalStartedNs", "finalEndNs", "readStartedNs", "readEndNs", "budgetAcceptance"} and
                window["clock"] == origin.clock_value(self.clock) and window["budgetAcceptance"] == "NOT_ADMITTED",
                "BOOTSTRAP_SEED_INITIALIZER_WINDOW")
        for name in ("firstNs", "workEndNs", "nativeEndNs", "prefixEndNs", "finalStartedNs", "finalEndNs",
                     "readStartedNs", "readEndNs"):
            origin.integer(window[name])
        fences = self.proposal["phaseFencesNs"]
        require(window["workEndNs"] == min(window["firstNs"] + 120 * NS, fences["canonical-init"]) and
                window["nativeEndNs"] == min(window["firstNs"] + 165 * NS, fences["canonical-init-final"]) and
                window["prefixEndNs"] == min(window["firstNs"] + 195 * NS, fences["canonical-init-read"]) and
                self.proposal["serviceTimeBasis"]["service"]["lastNs"] <= window["firstNs"] <
                window["workEndNs"] <= window["nativeEndNs"] <= window["prefixEndNs"] and
                window["firstNs"] <= window["finalStartedNs"] < window["finalEndNs"] ==
                min(window["nativeEndNs"], window["finalStartedNs"] + 45 * NS) and
                window["finalStartedNs"] <= window["readStartedNs"] < window["finalEndNs"] and
                window["readEndNs"] == min(window["prefixEndNs"], window["readStartedNs"] + 30 * NS) and
                window["readStartedNs"] <= origin.integer(closed["closedNs"]) <= self.previous_ns < window["readEndNs"] and
                self.previous_ns >= self.proposal["serviceTimeBasis"]["service"]["lastNs"],
                "BOOTSTRAP_SEED_INITIALIZER_CHRONOLOGY")

    def unchanged(self):
        require(_capture(self.published) == self.snapshot, "BOOTSTRAP_SEED_CALLER_INPUT_CHANGED")

    def binding(self):
        return {"admissionSha256": files.digest(self.admitted.record), "proposalSha256": files.digest(self.proposal_raw),
                "responsesSha256": {name: files.digest(raw) for name, raw in self.responses.items()},
                "invocation": self.invocation, "runnerName": self.runner, "clock": origin.clock_value(self.clock),
                "initializerContextSha256": files.digest(self.context_raw),
                "canonicalContextSha256": files.digest(self.canonical_raw), "propertiesSha256": files.digest(self.properties_raw),
                "initializerClosedSha256": files.digest(self.closed_raw), "initializerCheckedNs": self.previous_ns,
                "initializerDirectories": {name: list(identity) for name, identity in self.directories.items()},
                "session": str(self.session), "state": str(self.state), "home": str(self.home),
                "container": str(self.container), "restoreHome": str(self.restore)}


class _Window:
    def __init__(self, inputs, phase, phase_snapshot, previous, name):
        self.inputs, self.phase, self.phase_snapshot = inputs, phase, phase_snapshot
        self.name, (clock, self.first, self.local_start) = name, phase_snapshot
        self.previous_raw, self.previous_ns, self.previous_local = previous
        require(clock == _clock(inputs.clock) and self.first >= self.previous_ns and
                self.local_start >= self.previous_local, "BOOTSTRAP_SEED_PREDECESSOR_CLOCK")
        self.hard = min(origin.integer(self.first + 120 * NS), inputs.proposal["phaseFencesNs"][name],
                        inputs.proposal["proposedJobEndNs"])
        seconds = 90 if name == "empty-seed" else 120
        self.soft = min(self.hard, origin.integer(self.first + seconds * NS))
        require(self.first < self.soft, "BOOTSTRAP_SEED_ORIGINAL_PHASE_EXPIRED")
        self.local_hard = origin.wire._directed_deadline(self.local_start, 120, self.hard, self.first)
        self.local_soft = origin.wire._directed_deadline(self.local_start, seconds, self.soft, self.first)
        self.last, self.local_last, self.last_new = self.first, self.local_start, self.first

    def sample(self, *, new=False):
        self.inputs.unchanged()
        require(_capture_phase(self.phase) == self.phase_snapshot, "BOOTSTRAP_SEED_PHASE_CHANGED")
        local = _local(time.monotonic())
        require(local >= self.local_last, "BOOTSTRAP_SEED_LOCAL_BACKWARDS")
        self.local_last = local  # Keep even the late high-water on failure.
        actual = origin.clocks.observe()
        origin.clocks.validate_reading(actual)
        require(_clock(actual.clock) == _clock(self.inputs.clock) and actual.nanoseconds >= self.last,
                "BOOTSTRAP_SEED_RAW_CLOCK_CHANGED_OR_BACKWARDS")
        self.last = actual.nanoseconds
        if new:
            self.last_new = self.last
        # The RAW supplier itself may return late. Its pre-call LOCAL sample
        # cannot qualify a later return, especially the final successful one.
        local = _local(time.monotonic())
        require(local >= self.local_last, "BOOTSTRAP_SEED_LOCAL_BACKWARDS")
        self.local_last = local
        require(self.last < (self.soft if new else self.hard) and
                local < (self.local_soft if new else self.local_hard), "BOOTSTRAP_SEED_ORIGINAL_PHASE_EXPIRED")
        self.inputs.unchanged()
        require(_capture_phase(self.phase) == self.phase_snapshot, "BOOTSTRAP_SEED_PHASE_CHANGED")

    def record(self):
        return {"phase": self.name, "clock": origin.clock_value(self.inputs.clock), "firstNs": self.first,
                "hardEndNs": self.hard, "softEndNs": self.soft, "lastNewWorkNs": self.last_new,
                "finishedNs": self.last, "predecessorSha256": files.digest(self.previous_raw),
                "predecessorCheckedNs": self.previous_ns, "proposalSha256": files.digest(self.inputs.proposal_raw)}


class _Leaf:
    """Close only leaf acquisitions; enclosing owner retirement stays outside."""
    def __init__(self, parent, window):
        self.parent, self.window = parent, window
        self.ledger, self.cancelled = parent.resources, parent.cancelled
        require(type(self.ledger) is list and callable(self.cancelled), "BOOTSTRAP_SEED_PARENT_PROTOCOL")
        self.resources = []  # Independently retained even on post-allocation failure.

    @property
    def unknown(self):
        return self.parent.unknown

    def error(self, stage, error, *, unknown=False):
        self.parent.error(stage, error, unknown=unknown)

    def state(self):
        require(self.parent.closed is False and self.parent.unknown is False and
                self.parent.resources is self.ledger and self.parent.cancelled is self.cancelled,
                "BOOTSTRAP_SEED_PARENT_NOT_LIVE")
        if self.parent.original is not None:
            raise self.parent.original

    def check(self, *, new=False):
        self.state()
        self.window.sample(new=new)
        self.cancelled()
        self.window.sample(new=new)
        self.state()

    def end(self, *, new=False):
        self.check(new=new)
        parent_end = self.parent.end()
        self.check(new=new)
        raw_end = origin.wire._directed_deadline(self.window.local_last, 120, self.window.hard, self.window.last)
        return min(parent_end, self.window.local_hard, raw_end)

    def acquire(self, label, factory):
        self.check(new=True)
        prior_rows = tuple(self.ledger)
        prior_resources = tuple(row["owner"] for row in prior_rows)
        captured = []
        def retain():
            value = factory()
            captured.append(value)  # Before parent.acquire's fallible post-return clock.
            return value
        try:
            result = self.parent.acquire("bootstrap-leaf-" + label, retain)
        finally:
            for resource in captured:
                # A rejected duplicate factory return is NOT a new allocation.
                # Its existing caller/earlier-leaf cleanup obligation stays put.
                if any(resource is value for value in prior_resources):
                    continue
                rows = [row for row in self.ledger if row.get("owner") is resource and
                        not any(row is previous for previous in prior_rows)]
                self.resources.append((resource, rows[0] if len(rows) == 1 else None))
                if len(rows) != 1:
                    self.error("bootstrap-leaf-registration", files.SeedError("BOOTSTRAP_SEED_RESOURCE_NOT_REGISTERED"),
                               unknown=True)
        require(len(captured) == 1 and result is captured[0], "BOOTSTRAP_SEED_ACQUIRE_RETURN_CHANGED")
        require(not any(result is value for value in prior_resources), "BOOTSTRAP_SEED_BORROWED_RESOURCE")
        self.check()
        return result

    def close_one(self, resource):
        row = next(row for value, row in self.resources if value is resource)
        require(row is not None and self.parent.resources is self.ledger and
                any(item is row for item in self.ledger) and row.get("owner") is resource,
                "BOOTSTRAP_SEED_CLOSE_BINDING_CHANGED")
        require(self.parent.unknown is False, "BOOTSTRAP_SEED_RETIREMENT_UNKNOWN")
        self.parent.close_one(resource)
        require(row.get("attempted") is True and row.get("closed") is True and self.parent.unknown is False,
                "BOOTSTRAP_SEED_RETIREMENT_UNKNOWN")
        # Owner.close_one may retain a (possibly falsey) clock error without raising.
        if self.parent.original is not None:
            raise self.parent.original

    def close(self):
        for resource, row in reversed(self.resources):
            if self.parent.unknown:
                break
            if row is not None and row.get("attempted") is True:
                continue
            try:
                self.close_one(resource)
            except BaseException as error:
                self.error("bootstrap-leaf-close", error)
        if self.parent.original is not None:
            raise self.parent.original
        require(not self.parent.unknown and all(row is not None and row.get("attempted") is True and
                row.get("closed") is True for _resource, row in self.resources), "BOOTSTRAP_SEED_RETIREMENT_UNKNOWN")


def _read(leaf, directory, name, *, expected=None, binding=None, maximum=files.RECEIPT_LIMIT):
    end = leaf.end(new=True)
    reader = leaf.acquire("reader", lambda: directory.open_file(name, max_bytes=maximum, deadline=end))
    try:
        before = reader.initial_info
        retained = files._info_binding(before)
        require(binding is None or retained == binding, "BOOTSTRAP_SEED_FILE_REPLACED")
        raw = bytearray()
        while len(raw) < before.size:
            leaf.check()
            part = reader.read(min(files.BLOCK, before.size - len(raw)))
            require(type(part) is bytes and 0 < len(part) <= before.size - len(raw), "BOOTSTRAP_SEED_SHORT_READ")
            raw.extend(part)
        require(reader.read(1) == b"" and reader.verify() == before, "BOOTSTRAP_SEED_FILE_CHANGED")
        raw = bytes(raw)
        require(expected is None or raw == expected, "BOOTSTRAP_SEED_ORIGINAL_FILE_CHANGED")
    except BaseException as error:
        leaf.error("bootstrap-leaf-read", error)
        raise
    finally:
        leaf.close_one(reader)
    leaf.check()
    return raw, retained


def _names(leaf, directory, expected):
    end = leaf.end(new=True)
    require(directory.names(max_names=32, deadline=end) == tuple(sorted(expected)),
            "BOOTSTRAP_SEED_DIRECTORY_NOT_EMPTY_OR_CHANGED")
    leaf.check()


def _initialized(leaf, inputs):
    handles = {"session": leaf.acquire("initializer-session", lambda: files.private_root(inputs.session))}
    for name in DIRECTORIES[1:]:
        parent = handles["session"] if name == "state" else handles["state"]
        end = leaf.end(new=True)
        handles[name] = leaf.acquire("initializer-directory", lambda: parent.open_directory(name, deadline=end))
    for name, directory in handles.items():
        require(tuple(directory.verify().identity) == inputs.directories[name], "BOOTSTRAP_SEED_INITIALIZER_REPLACED")
    return handles


def _initialized_readback(leaf, inputs, handles, bindings=None):
    _names(leaf, handles["state"], ("context.json", "gradle-home", "evidence", "cancellations"))
    _names(leaf, handles["gradle-home"], ("gradle.properties",))
    for name in ("evidence", "cancellations"):
        _names(leaf, handles[name], ())
    found = {}
    for key, directory, name, raw in (("initializer-context", handles["session"], "initializer-context.json", inputs.context_raw),
            ("canonical-context", handles["state"], "context.json", inputs.canonical_raw),
            ("properties", handles["gradle-home"], "gradle.properties", inputs.properties_raw)):
        _raw, found[key] = _read(leaf, directory, name, expected=raw,
                                 binding=None if bindings is None else bindings[key])
    require(len({tuple(row["identity"]) for row in found.values()}) == len(found), "BOOTSTRAP_SEED_FILE_ALIASES")
    for name, directory in handles.items():
        require(tuple(directory.verify().identity) == inputs.directories[name], "BOOTSTRAP_SEED_INITIALIZER_REPLACED")
    return found


def _bootstrap_sources(inputs):
    # This is a DATA provenance roster, not a polymorphic authority decision.
    # Every public leaf wrapper still constructs its exact origin input type.
    return BOOTSTRAP_INPUTS + (initial.INITIAL_SOURCE_INPUTS if isinstance(inputs, initial.InitialInputs) else ())


def _sources(leaf, inputs):
    bound, compiled = files.source_inputs(leaf, inputs.root, leaf.end(new=True), leaf.check)
    opened, extra = {}, {}
    try:
        opened[()] = leaf.acquire("bootstrap-source", lambda: files.public_root(inputs.root))
        for relative in _bootstrap_sources(inputs):
            parts = tuple(relative.split("/"))
            for count in range(1, len(parts)):
                prefix = parts[:count]
                if prefix not in opened:
                    parent, end = opened[prefix[:-1]], leaf.end(new=True)
                    opened[prefix] = leaf.acquire("bootstrap-source-parent", lambda: parent.open_directory(
                        prefix[-1], deadline=end))
            raw, _binding = _read(leaf, opened[parts[:-1]], parts[-1], maximum=files.authority.MAX_XML_BYTES)
            extra[relative] = files.digest(raw)
        for directory in opened.values():
            directory.verify()
    except BaseException as error:
        # Close may also fail. Retain the first verification/deadline failure
        # before finally so the enclosing owner cannot replace it with cleanup.
        leaf.error("bootstrap-leaf-sources", error)
        raise
    finally:
        for directory in reversed(tuple(opened.values())):
            leaf.close_one(directory)
    leaf.check()
    return bound, compiled, extra


def _write_stage(leaf, container, raw):
    end = leaf.end(new=True)
    writer = leaf.acquire("staging-writer", lambda: container.create_file("staging.json", max_bytes=len(raw), deadline=end))
    try:
        offset = 0
        while offset < len(raw):
            leaf.check()
            count = writer.write(raw[offset:offset + files.BLOCK])
            require(type(count) is int and 0 < count <= min(files.BLOCK, len(raw) - offset), "BOOTSTRAP_SEED_SHORT_WRITE")
            offset += count
        writer.sync()
        require(writer.verify().size == len(raw), "BOOTSTRAP_SEED_WRITE_CHANGED")
    except BaseException as error:
        leaf.error("bootstrap-leaf-write", error)
        raise
    finally:
        leaf.close_one(writer)
    return _read(leaf, container, "staging.json", expected=raw)[1]


def _stage_evidence(inputs, captured):
    raw, staging_raw, checked, local_start, local_last = captured
    value, stage = files.record(raw), files.record(staging_raw)
    require(set(value) == {"schema", "scope", "binding", "inputs", "bootstrapInputs", "stagingSha256", "plan",
                "seedIntent", "fileBindings", "window", "status", "completed", "leafHandleClose", "enclosingOwnerRetirement",
                "nextPhaseAuthority", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"} and
            type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == STAGE_SCOPE and
            value["binding"] == inputs.binding() and raw == files.encoded(value) and staging_raw == files.encoded(stage),
            "BOOTSTRAP_SEED_STAGE_EVIDENCE_CHANGED")
    require(value["status"] == EMPTY and value["completed"] is True and value["leafHandleClose"] == "KNOWN" and
            value["enclosingOwnerRetirement"] == "NOT_OBSERVED_HERE" and value["nextPhaseAuthority"] is False and
            value["budgetAcceptance"] == "NOT_ADMITTED" and value["testAcceptance"] == "NOT_PERFORMED" and
            value["exportSaveAuthority"] is False and value["stagingSha256"] == files.digest(staging_raw),
            "BOOTSTRAP_SEED_STAGE_NOT_COMPLETED")
    files.validate_retained_stage(stage, inputs.admitted.record,
        {"session": str(inputs.session), "profile": inputs.profile, "role": inputs.role}, value["inputs"])
    require(type(value["bootstrapInputs"]) is dict and set(value["bootstrapInputs"]) == set(_bootstrap_sources(inputs)) and
            all(cache._sha(sha) for sha in value["bootstrapInputs"].values()) and
            type(value["fileBindings"]) is dict and set(value["fileBindings"]) ==
            {"initializer-context", "canonical-context", "properties", "staging"} and
            all(files._file_binding(binding) for binding in value["fileBindings"].values()),
            "BOOTSTRAP_SEED_STAGE_BINDINGS")
    window = value["window"]
    require(type(window) is dict and set(window) == {"phase", "clock", "firstNs", "hardEndNs", "softEndNs",
            "lastNewWorkNs", "finishedNs", "predecessorSha256", "predecessorCheckedNs", "proposalSha256"},
            "BOOTSTRAP_SEED_STAGE_WINDOW")
    for name in ("firstNs", "hardEndNs", "softEndNs", "lastNewWorkNs", "finishedNs", "predecessorCheckedNs"):
        origin.integer(window[name])
    require(window["phase"] == "dependency-stage" and window["clock"] == origin.clock_value(inputs.clock) and
            window["predecessorSha256"] == files.digest(inputs.closed_raw) and
            window["predecessorCheckedNs"] == inputs.previous_ns and window["proposalSha256"] == files.digest(inputs.proposal_raw) and
            inputs.previous_ns <= window["firstNs"] <= window["lastNewWorkNs"] <= window["finishedNs"] <= checked <
            window["hardEndNs"] == window["softEndNs"] == min(window["firstNs"] + 120 * NS,
                inputs.proposal["phaseFencesNs"]["dependency-stage"], inputs.proposal["proposedJobEndNs"]) and
            inputs.previous_local <= local_start <= local_last <
            origin.wire._directed_deadline(local_start, 120, window["hardEndNs"], window["firstNs"]),
            "BOOTSTRAP_SEED_STAGE_RETURN_CLOCK")
    return value, stage


def _run(parent, originals, phase, previous_stage):
    # No callback sees the caller's containers as the only copy of originals.
    captured, phase_snapshot = _capture(originals), _capture_phase(phase)
    stage_capture = None if previous_stage is None else _capture_evidence(previous_stage)
    inputs = _Inputs(originals, captured)
    return _run_inputs(parent, inputs, phase, phase_snapshot, previous_stage, stage_capture)


def _run_initial(parent, originals, phase, previous_stage):
    captured, phase_snapshot = initial.capture_originals(originals), _capture_phase(phase)
    stage_capture = None if previous_stage is None else _capture_evidence(previous_stage)
    inputs = initial.InitialInputs(originals, captured)
    return _run_inputs(parent, inputs, phase, phase_snapshot, previous_stage, stage_capture)


def _run_inputs(parent, inputs, phase, phase_snapshot, previous_stage, stage_capture):
    # Only the fixed origin wrappers construct the detached input view. Native
    # creation/readback/close and the original leaf limits stay shared.
    previous = ((inputs.closed_raw, inputs.previous_ns, inputs.previous_local) if stage_capture is None else
                (stage_capture[0], stage_capture[2], stage_capture[4]))
    window = _Window(inputs, phase, phase_snapshot, previous, "dependency-stage" if stage_capture is None else "empty-seed")
    leaf = _Leaf(parent, window)
    result = {"schema": 1, "scope": STAGE_SCOPE if stage_capture is None else SEED_SCOPE,
              "binding": inputs.binding(), "status": "FAILED", "completed": False, "leafHandleClose": "PENDING",
              "enclosingOwnerRetirement": "NOT_OBSERVED_HERE", "nextPhaseAuthority": False,
              "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
    staging_raw = None
    try:
        leaf.check(new=True)
        stage_value, stage = (None, None) if stage_capture is None else _stage_evidence(inputs, stage_capture)
        handles = _initialized(leaf, inputs)
        bindings = _initialized_readback(leaf, inputs, handles, None if stage_value is None else stage_value["fileBindings"])
        source_inputs, compiled, extra = _sources(leaf, inputs)
        result.update(inputs=source_inputs, bootstrapInputs=extra)
        if stage_value is not None:
            require(source_inputs == stage_value["inputs"] and extra == stage_value["bootstrapInputs"],
                    "BOOTSTRAP_SEED_SOURCE_INPUTS_CHANGED")
        container = leaf.acquire("container", lambda: files.private_root(inputs.container, create=stage_value is None))
        end = leaf.end(new=True)
        source = leaf.acquire("restore-home", lambda: (container.create_directory if stage_value is None else
            container.open_directory)("restore-home", deadline=end))
        root_info, source_info = container.verify(), source.verify()
        require(len({*inputs.directories.values(), tuple(root_info.identity), tuple(source_info.identity)}) == 7,
                "BOOTSTRAP_SEED_DIRECTORY_ALIASES")
        _names(leaf, source, ())
        if stage_value is None:
            _names(leaf, container, ("restore-home",))
            stage = files.stage_record(inputs.admitted.record, inputs.profile, inputs.role, inputs.container,
                                       root_info, source_info, source_inputs)
            staging_raw = files.encoded(stage)
            bindings["staging"] = _write_stage(leaf, container, staging_raw)
        else:
            staging_raw = stage_capture[1]
            files.validate_stage(stage, inputs.admitted.record, inputs.profile, inputs.role, inputs.container,
                                 root_info, source_info, source_inputs)
            _, bindings["staging"] = _read(leaf, container, "staging.json", expected=staging_raw,
                                           binding=stage_value["fileBindings"]["staging"])
        plan = cache.make_plan(inputs.admitted.record, staging_raw, compiled, source_inputs,
                               session=inputs.session, profile=inputs.profile, role=inputs.role, mode="bootstrap")
        intent = files.seed_intent(inputs.admitted.record, inputs.profile, inputs.role, inputs.container,
                                   staging_raw, source_inputs)
        result.update(stagingSha256=files.digest(staging_raw), plan=plan, seedIntent=intent, fileBindings=bindings)
        if stage_value is not None:
            require(plan == stage_value["plan"] and intent == stage_value["seedIntent"], "BOOTSTRAP_SEED_STAGE_PLAN_CHANGED")
            result.update(stageEvidenceSha256=files.digest(stage_capture[0]), stageReturnBindingSha256=files.digest(
                files.encoded({"rawSha256": files.digest(stage_capture[0]), "checkedNs": stage_capture[2],
                               "localStarted": stage_capture[3], "localChecked": stage_capture[4]})),
                counts={name: 0 for name in COUNTERS}, admitted=[],
                misses=[{"index": index, "reason": "ABSENT", "rejected": 0} for index in range(len(compiled.artifacts))],
                sourceIdentity=list(source_info.identity), homeIdentity=list(inputs.directories["gradle-home"]),
                byteScope="DEPENDENCY_BYTES_ONLY_METADATA_IO_OCCURRED")
        # Full S emptiness, exact properties-only H and complete metadata are
        # checked again. No copier's budget omission is classified as ABSENT.
        require(_sources(leaf, inputs)[::2] == (source_inputs, extra), "BOOTSTRAP_SEED_SOURCE_INPUTS_CHANGED")
        _initialized_readback(leaf, inputs, handles, bindings)
        _read(leaf, container, "staging.json", expected=staging_raw, binding=bindings["staging"])
        _names(leaf, container, ("restore-home", "staging.json"))
        _names(leaf, source, ())
        files.validate_stage(stage, inputs.admitted.record, inputs.profile, inputs.role, inputs.container,
                             container.verify(), source.verify(), source_inputs)
        if stage_capture is not None:
            require(_capture_evidence(previous_stage) == stage_capture, "BOOTSTRAP_SEED_STAGE_RETURN_CHANGED")
            files._validate_inventory({**result, "status": EMPTY}, compiled, statuses=(EMPTY, "UNREACHABLE", "UNREACHABLE"))
        leaf.close()
        leaf.check()
        result.update(status=EMPTY, completed=True, leafHandleClose="KNOWN", window=window.record())
        raw = files.encoded(result)
        leaf.check()  # Serialization/closure/cancellation all spend original time.
        if stage_capture is not None:
            require(_capture_evidence(previous_stage) == stage_capture, "BOOTSTRAP_SEED_STAGE_RETURN_CHANGED")
        return LeafEvidence(raw, staging_raw, window.last, window.local_start, window.local_last)
    except BaseException as error:
        first = error if parent.original is None else parent.original
        leaf.error("bootstrap-leaf", first)
        try:
            leaf.close()
        except BaseException as secondary:
            if secondary is not first:
                leaf.error("bootstrap-leaf-final", secondary)
        result.update(status="UNKNOWN" if parent.unknown else "FAILED", completed=False,
                      leafHandleClose="UNKNOWN" if parent.unknown else "FAILED", window=window.record())
        # No new failure owner/file or optimistic cleanup. Keep actual partial
        # references as well as the first error, even after final serialization.
        first.bootstrap_leaf_result = result
        first.bootstrap_leaf_resources = tuple(leaf.resources)
        raise first


def stage_empty(parent, originals, phase):
    """Exclusive new S/container; reject even an existing empty container."""
    return _run(parent, originals, phase, None)


def observe_empty_seed(parent, originals, phase, stage_evidence):
    """Read-only proof of zero transferable bytes, not a dependency writer."""
    require(stage_evidence is not None, "BOOTSTRAP_SEED_STAGE_RETURN_REQUIRED")
    return _run(parent, originals, phase, stage_evidence)


def stage_initial_recipient_empty(parent, originals, phase):
    """Initial-origin DATA setup, same exclusive original S/container engine."""
    return _run_initial(parent, originals, phase, None)


def observe_initial_recipient_empty_seed(parent, originals, phase, stage_evidence):
    """Initial-origin DATA setup; never an ordinary Admission or seed writer."""
    require(stage_evidence is not None, "BOOTSTRAP_SEED_STAGE_RETURN_REQUIRED")
    return _run_initial(parent, originals, phase, stage_evidence)
