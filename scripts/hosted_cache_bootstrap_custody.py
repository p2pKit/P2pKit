"""Dormant, file-only configuration-custody reservation; NOT an executor.

Supplied staged/empty-seed records do not authenticate original parent returns.
The future same-call parent must establish those returns and own its distinct
custody window. No ordinary Test loader, generated command, native/process owner,
collector, uninstall, deletion, provider or workflow is invoked here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import uuid

import hosted_cache_bootstrap_staging as staging


files, origin = staging.files, staging.origin
producer = staging.initialization.producer
ROOT = Path(__file__).resolve().parents[1]
SCOPE = "BOOTSTRAP_CONFIGURATION_CUSTODY_RESERVATION_LEAF_V1"
REQUEST_SCOPE = "BOOTSTRAP_CONFIGURATION_CUSTODY_REQUEST_V1"
CUSTODY_INPUTS = ("scripts/hosted_cache_bootstrap_custody.py",)
PARENT_SCOPE = "BOOTSTRAP_STAGING_PARENT_CLOSED_NO_EXECUTION_V1"


def require(value, reason):
    files.require(value, reason)


@dataclass(frozen=True)
class StagedEvidence:
    """Supplied values corresponding to StagingPrefix, NOT original-call rights."""
    raw: bytes = field(repr=False)
    stage_raw: bytes = field(repr=False)
    stage_leaf: object = field(repr=False)
    seed_leaf: object = field(repr=False)
    checked_ns: int = field(repr=False)
    checked_local: float = field(repr=False)


@dataclass(frozen=True)
class ReservationEvidence:
    """Private returned data; request bytes cannot grant launch/single-use rights."""
    raw: bytes = field(repr=False)
    request_raw: bytes = field(repr=False)
    checked_ns: int = field(repr=False)
    local_started: float = field(repr=False)
    checked_local: float = field(repr=False)


def _capture_staged(value):
    require(type(value) is StagedEvidence, "BOOTSTRAP_CUSTODY_STAGED_EVIDENCE")
    return (staging._bytes(value.raw), staging._bytes(value.stage_raw),
            staging._capture_evidence(value.stage_leaf), staging._capture_evidence(value.seed_leaf),
            origin.integer(value.checked_ns), staging._local(value.checked_local))


def _equal(actual, expected, reason):
    # Canonical bytes distinguish bools from integers and close every field set.
    require(files.encoded(actual) == files.encoded(expected), reason)


def _leaf_window(inputs, captured, previous, name):
    raw, _staging_raw, checked, local_start, local_last = captured
    value, old_raw, old_ns, old_local = files.record(raw), *previous
    window = value["window"]
    require(type(window) is dict and set(window) == {"phase", "clock", "firstNs", "hardEndNs", "softEndNs",
            "lastNewWorkNs", "finishedNs", "predecessorSha256", "predecessorCheckedNs", "proposalSha256"},
            "BOOTSTRAP_CUSTODY_SEED_WINDOW")
    for name_ in ("firstNs", "hardEndNs", "softEndNs", "lastNewWorkNs", "finishedNs", "predecessorCheckedNs"):
        origin.integer(window[name_])
    first = window["firstNs"]
    hard = min(origin.integer(first + 120 * staging.NS), inputs.proposal["phaseFencesNs"][name],
               inputs.proposal["proposedJobEndNs"])
    seconds = 90 if name == "empty-seed" else 120
    soft = min(hard, origin.integer(first + seconds * staging.NS))
    require(window["phase"] == name and window["clock"] == origin.clock_value(inputs.clock) and
            window["predecessorSha256"] == files.digest(old_raw) and window["predecessorCheckedNs"] == old_ns and
            window["proposalSha256"] == files.digest(inputs.proposal_raw) and
            old_ns <= first <= window["lastNewWorkNs"] < soft and
            window["lastNewWorkNs"] <= window["finishedNs"] <= checked < hard and
            window["softEndNs"] == soft and window["hardEndNs"] == hard and
            old_local <= local_start <= local_last < origin.wire._directed_deadline(local_start, 120, hard, first),
            "BOOTSTRAP_CUSTODY_SEED_CHRONOLOGY")
    return window


def _parent_record(inputs, raw, leaf, previous_raw, minimum, name, checked=None):
    value = files.record(raw)
    require(set(value) == {"schema", "scope", "phase", "window", "pendingSha256", "predecessorSha256",
            "predecessorCheckedNs", "leafSha256", "leafCheckedNs", "closedNs", "resourceCount", "parentResourceClose",
            "nextPhaseAuthority", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"} and
            raw == files.encoded(value), "BOOTSTRAP_CUSTODY_PARENT_FIELDS")
    leaf_window = files.record(leaf[0])["window"]
    expected_window = {name_: leaf_window[name_] for name_ in ("phase", "clock", "firstNs", "softEndNs", "hardEndNs")}
    expected_window["budgetAcceptance"] = "NOT_ADMITTED"
    _equal(value["window"], expected_window, "BOOTSTRAP_CUSTODY_PARENT_WINDOW")
    predecessor = origin.integer(value["predecessorCheckedNs"])
    closed = origin.integer(value["closedNs"])
    require(minimum <= predecessor <= leaf_window["firstNs"] <= leaf[2] <= closed < leaf_window["hardEndNs"] and
            (checked is None or closed <= checked < leaf_window["hardEndNs"]) and
            type(value["resourceCount"]) is int and 0 < value["resourceCount"] <= files.MEMBER_LIMIT and
            staging.cache._sha(value["pendingSha256"]), "BOOTSTRAP_CUSTODY_PARENT_CHRONOLOGY")
    parent_scope = staging.initial.STAGING_PARENT_SCOPE if type(inputs) is _InitialInputs else PARENT_SCOPE
    _equal(value, {"schema": 1, "scope": parent_scope, "phase": name, "window": expected_window,
        "pendingSha256": value["pendingSha256"], "predecessorSha256": files.digest(previous_raw),
        "predecessorCheckedNs": predecessor, "leafSha256": files.digest(leaf[0]), "leafCheckedNs": leaf[2],
        "closedNs": closed, "resourceCount": value["resourceCount"], "parentResourceClose": "KNOWN_RESOURCE_CLOSE_ONLY",
        "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
        "exportSaveAuthority": False}, "BOOTSTRAP_CUSTODY_PARENT_BINDING")
    return value


class _StagedInputs:
    def _staged_setup(self, staged, staged_capture):
        self.staged, self.staged_capture = staged, staged_capture
        self.source_root = ROOT
        require(isinstance(self.source_root, Path) and self.source_root == staging.ROOT and
                str(self.source_root) == self.root, "BOOTSTRAP_CUSTODY_SOURCE_ROOT")
        parent_raw, stage_parent_raw, stage, seed, checked, local = staged_capture
        self.stage_value, self.stage = staging._stage_evidence(self, stage)
        self.seed_value = files.record(seed[0])
        self.staging_raw = stage[1]
        require(seed[1] == self.staging_raw and seed[0] == files.encoded(self.seed_value),
                "BOOTSTRAP_CUSTODY_SEED_ORIGINAL_BYTES")
        seed_window = _leaf_window(self, seed, (stage[0], stage[2], stage[4]), "empty-seed")
        extra = {"stageEvidenceSha256": files.digest(stage[0]), "stageReturnBindingSha256": files.digest(files.encoded(
            {"rawSha256": files.digest(stage[0]), "checkedNs": stage[2], "localStarted": stage[3], "localChecked": stage[4]})),
            "counts": {name: 0 for name in staging.COUNTERS}, "admitted": [],
            "sourceIdentity": self.stage["sourceIdentity"], "homeIdentity": list(self.directories["gradle-home"]),
            "byteScope": "DEPENDENCY_BYTES_ONLY_METADATA_IO_OCCURRED"}
        misses = self.seed_value.get("misses")
        require(type(misses) is list and len(misses) <= files.MEMBER_LIMIT,
                "BOOTSTRAP_CUSTODY_SEED_INVENTORY")
        _equal(misses, [{"index": i, "reason": "ABSENT", "rejected": 0} for i in range(len(misses))],
               "BOOTSTRAP_CUSTODY_SEED_INVENTORY")
        _equal(self.seed_value, {**self.stage_value, **extra, "scope": staging.SEED_SCOPE,
                               "window": seed_window, "misses": misses}, "BOOTSTRAP_CUSTODY_SEED_BINDING")
        stage_parent = _parent_record(self, stage_parent_raw, stage, self.closed_raw, self.previous_ns, "dependency-stage")
        require(stage_parent["predecessorCheckedNs"] == self.previous_ns, "BOOTSTRAP_CUSTODY_STAGE_PARENT_PREDECESSOR")
        seed_parent = _parent_record(self, parent_raw, seed, stage_parent_raw, stage_parent["closedNs"], "empty-seed", checked)
        require(seed_parent["predecessorCheckedNs"] < stage_parent["window"]["hardEndNs"] and
                seed[4] <= local < origin.wire._directed_deadline(seed[3], 120, seed_window["hardEndNs"], seed_window["firstNs"]),
                "BOOTSTRAP_CUSTODY_SEED_PARENT_RETURN")
        self.directory = self.session / "configuration-custody"

    def _staged_unchanged(self):
        require(ROOT == self.source_root == staging.ROOT and _capture_staged(self.staged) == self.staged_capture,
                "BOOTSTRAP_CUSTODY_STAGED_INPUT_CHANGED")

    def predecessors(self):
        parent, stage_parent, stage, seed, checked, local = self.staged_capture
        return {"stageParentSha256": files.digest(stage_parent), "stageLeafSha256": files.digest(stage[0]),
                "seedParentSha256": files.digest(parent), "seedLeafSha256": files.digest(seed[0]),
                "seedParentCheckedNs": checked, "seedParentCheckedLocal": local,
                "provenance": "SUPPLIED_DATA_NOT_AUTHENTICATED_PARENT_RETURNS"}


class _Inputs(staging._Inputs, _StagedInputs):
    def __init__(self, originals, captured, staged, staged_capture):
        super().__init__(originals, captured)
        self._staged_setup(staged, staged_capture)

    def unchanged(self):
        super().unchanged()
        self._staged_unchanged()


class _InitialInputs(staging.initial.InitialInputs, _StagedInputs):
    """Exact initial-origin sibling, not an ordinary _Inputs/Admission."""
    def __init__(self, originals, captured, staged, staged_capture):
        super().__init__(originals, captured)
        self._staged_setup(staged, staged_capture)

    def unchanged(self):
        super().unchanged()
        self._staged_unchanged()


def _sources(leaf, inputs):
    bound, compiled, previous = staging._sources(leaf, inputs)
    require(bound == inputs.stage_value["inputs"] and previous == inputs.stage_value["bootstrapInputs"],
            "BOOTSTRAP_CUSTODY_SOURCE_INPUT_CHANGED")
    _equal(inputs.seed_value["misses"], [{"index": i, "reason": "ABSENT", "rejected": 0}
           for i in range(len(compiled.artifacts))], "BOOTSTRAP_CUSTODY_SEED_INVENTORY")
    extra, opened = {}, []
    try:
        root = leaf.acquire("custody-source-root", lambda: files.public_root(inputs.root))
        opened.append(root)
        end = leaf.end(new=True)
        scripts = leaf.acquire("custody-source-scripts", lambda: root.open_directory("scripts", deadline=end))
        opened.append(scripts)
        for name in CUSTODY_INPUTS:
            raw, _binding = staging._read(leaf, scripts, name.removeprefix("scripts/"))
            extra[name] = files.digest(raw)
        for directory in opened:
            directory.verify()
    except BaseException as error:
        leaf.error("bootstrap-custody-source", error)
        raise
    finally:
        for directory in reversed(opened):
            leaf.close_one(directory)
    plan = staging.cache.make_plan(inputs.admitted.record, inputs.staging_raw, compiled, bound,
        session=inputs.session, profile=inputs.profile, role=inputs.role, mode="bootstrap")
    _equal(plan, inputs.stage_value["plan"], "BOOTSTRAP_CUSTODY_PLAN_CHANGED")
    _equal(files.seed_intent(inputs.admitted.record, inputs.profile, inputs.role, inputs.container,
        inputs.staging_raw, bound), inputs.stage_value["seedIntent"], "BOOTSTRAP_CUSTODY_SEED_INTENT_CHANGED")
    return {"inputs": bound, "bootstrapInputs": previous, "custodyInputs": extra}


def _stage_readback(leaf, inputs, container, restore):
    files.validate_stage(inputs.stage, inputs.admitted.record, inputs.profile, inputs.role, inputs.container,
                         container.verify(), restore.verify(), inputs.stage_value["inputs"])
    staging._read(leaf, container, "staging.json", expected=inputs.staging_raw,
                  binding=inputs.stage_value["fileBindings"]["staging"])
    staging._names(leaf, container, ("restore-home", "staging.json"))
    staging._names(leaf, restore, ())
    leaf.check()


def _write_request(leaf, directory, raw):
    end = leaf.end(new=True)
    writer = leaf.acquire("custody-request-writer", lambda: directory.create_file("request.json", max_bytes=len(raw), deadline=end))
    try:
        offset = 0
        while offset < len(raw):
            leaf.check()
            count = writer.write(raw[offset:offset + files.BLOCK])
            require(type(count) is int and 0 < count <= min(files.BLOCK, len(raw) - offset), "BOOTSTRAP_CUSTODY_SHORT_WRITE")
            offset += count
        writer.sync()
        require(writer.verify().size == len(raw), "BOOTSTRAP_CUSTODY_WRITE_CHANGED")
    except BaseException as error:
        leaf.error("bootstrap-custody-write", error)
        raise
    finally:
        leaf.close_one(writer)
    return staging._read(leaf, directory, "request.json", expected=raw)[1]


def reserve_configuration(parent, originals, phase, staged):
    """Reserve one invocation outside canonical evidence/H; create no loader.

    Only the supplied existing parent owns enclosing retirement. A later native
    parent must bind the reserved ID to its actual original ancestor/domain chain;
    no invented ancestry or executable command is accepted or constructed here.
    """
    captured, phase_capture, staged_capture = staging._capture(originals), staging._capture_phase(phase), _capture_staged(staged)
    inputs = _Inputs(originals, captured, staged, staged_capture)
    return _reserve_inputs(parent, inputs, phase, phase_capture, staged_capture)


def reserve_initial_recipient_configuration(parent, originals, phase, staged):
    """Fixed initial input route; no loader, producer or Admission is created."""
    captured = staging.initial.capture_originals(originals)
    phase_capture, staged_capture = staging._capture_phase(phase), _capture_staged(staged)
    inputs = _InitialInputs(originals, captured, staged, staged_capture)
    return _reserve_inputs(parent, inputs, phase, phase_capture, staged_capture)


def _reserve_inputs(parent, inputs, phase, phase_capture, staged_capture):
    window = staging._Window(inputs, phase, phase_capture,
        (staged_capture[0], staged_capture[4], staged_capture[5]), "custody-prepare")
    leaf = staging._Leaf(parent, window)
    result = {"schema": 1, "scope": SCOPE, "binding": inputs.binding(), "predecessors": inputs.predecessors(),
              "status": "FAILED", "completed": False, "leafHandleClose": "PENDING",
              "enclosingOwnerRetirement": "NOT_OBSERVED_HERE", "nextPhaseAuthority": False,
              "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED", "exportSaveAuthority": False}
    try:
        leaf.check(new=True)
        handles = staging._initialized(leaf, inputs)
        bindings = staging._initialized_readback(leaf, inputs, handles, inputs.seed_value["fileBindings"])
        sources = _sources(leaf, inputs)
        container = leaf.acquire("custody-stage-container", lambda: files.private_root(inputs.container))
        end = leaf.end(new=True)
        restore = leaf.acquire("custody-stage-home", lambda: container.open_directory("restore-home", deadline=end))
        _stage_readback(leaf, inputs, container, restore)
        # Exactly one allocation attempt. No retry on collision/failure and no
        # mkdir inside state/evidence: canonical execute owns that exclusive mkdir.
        selected = uuid.uuid4()
        require(type(selected) is uuid.UUID and selected.version == 4, "BOOTSTRAP_CUSTODY_INVOCATION_SUPPLIER")
        invocation = selected.hex
        require(invocation not in (inputs.canonical["id"], inputs.invocation, origin.parse(inputs.context_raw)["job"]),
                "BOOTSTRAP_CUSTODY_INVOCATION_COLLISION")
        leaf.check(new=True)
        end = leaf.end(new=True)
        directory = leaf.acquire("custody-directory", lambda: handles["session"].create_directory("configuration-custody", deadline=end))
        end = leaf.end(new=True)
        retained = leaf.acquire("custody-retained", lambda: directory.create_directory("retained", deadline=end))
        identities = {"custody": list(directory.verify().identity), "retained": list(retained.verify().identity)}
        require(len({*inputs.directories.values(), tuple(container.verify().identity), tuple(restore.verify().identity),
                     *(tuple(value) for value in identities.values())}) == 9, "BOOTSTRAP_CUSTODY_DIRECTORY_ALIASES")
        request_raw = files.encoded({"schema": 1, "scope": REQUEST_SCOPE, "binding": inputs.binding(),
            "predecessors": inputs.predecessors(), **sources, "fileBindings": bindings,
            "directory": str(inputs.directory), "directories": identities,
            "owner": {"job": inputs.canonical["id"], "productInvocation": invocation, "sameHomeStopInvocation": invocation},
            "evidenceDirectory": str(inputs.state / "evidence" / invocation), "evidenceDirectoryOwnership": "NOT_CREATED_HERE",
            "purpose": producer.PURPOSE, "kind": "gradle", "requestedArgv": list(origin.bootstrap.COMMAND),
            "producerScope": origin.bootstrap.PRODUCER_SCOPE, "ancestorDomainChain": "NOT_SYNTHESIZED_OR_ADMITTED",
            "loader": "NOT_INSTALLED_BY_CONFIGURATION_RESERVATION", "sourceAdmission": "NOT_ATTESTED_HERE",
            "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
            "exportSaveAuthority": False})
        staging._names(leaf, directory, ("retained",))
        staging._names(leaf, retained, ())
        request_binding = _write_request(leaf, directory, request_raw)
        require(_sources(leaf, inputs) == sources, "BOOTSTRAP_CUSTODY_SOURCE_INPUT_CHANGED")
        staging._initialized_readback(leaf, inputs, handles, bindings)
        _stage_readback(leaf, inputs, container, restore)
        staging._read(leaf, directory, "request.json", expected=request_raw, binding=request_binding)
        staging._names(leaf, directory, ("request.json", "retained"))
        staging._names(leaf, retained, ())
        require(identities == {"custody": list(directory.verify().identity), "retained": list(retained.verify().identity)},
                "BOOTSTRAP_CUSTODY_DIRECTORY_REPLACED")
        leaf.close()
        leaf.check()
        result.update(status="RESERVED_CONFIGURATION_ONLY", completed=True, leafHandleClose="KNOWN",
                      requestSha256=files.digest(request_raw), requestBinding=request_binding, window=window.record())
        raw = files.encoded(result)
        leaf.check()
        return ReservationEvidence(raw, request_raw, window.last, window.local_start, window.local_last)
    except BaseException as error:
        first = error if parent.original is None else parent.original
        leaf.error("bootstrap-configuration-custody", first)
        try:
            leaf.close()
        except BaseException as secondary:
            if secondary is not first:
                leaf.error("bootstrap-configuration-custody-close", secondary)
        result.update(status="UNKNOWN" if parent.unknown else "FAILED", completed=False,
                      leafHandleClose="UNKNOWN" if parent.unknown else "FAILED", window=window.record())
        # No postclose/failure owner, fallback key or invented encrypted custody.
        # These are private actual references, not a deletion/cleanup permit.
        try:
            first.bootstrap_custody_result = result
            first.bootstrap_custody_resources = tuple(leaf.resources)
        except BaseException:
            pass
        raise first
