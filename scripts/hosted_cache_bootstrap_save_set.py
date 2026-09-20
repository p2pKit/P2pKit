"""Bootstrap pre/post save observations; no provider, workflow or atomic snapshot.

The caller must retain the original successful export and before-save bytes.
These supplied-data checks do not authenticate them or grant save authority.
The post check does not establish that a provider ran between observations.
Ordinary cache.save_set and its bootstrap-refusal guards remain unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import hosted_cache_bootstrap_export as dependency_export


custody = dependency_export.custody
staging, files, origin = custody.staging, custody.files, custody.origin
SCOPE = "BOOTSTRAP_SAVE_SET_BEFORE_LEAF_V1"
STATUSES = ("KNOWN_FROZEN",)
AFTER_SCOPE = "BOOTSTRAP_SAVE_SET_AFTER_LEAF_V1"
AFTER_STATUS = "KNOWN_UNCHANGED"


@dataclass(frozen=True)
class SaveSetEvidence:
    """Complete read-only observation, not provider/archive acceptance."""
    raw: bytes = field(repr=False)
    checked_ns: int
    local_started: float
    checked_local: float


class _Window(staging._Window):
    def __init__(self, inputs, phase, previous):
        super().__init__(inputs, phase, staging._capture_phase(phase), previous, "save-set-before")
        self.soft = min(self.hard, origin.integer(self.first + 90 * origin.NS))
        self.local_soft = origin.wire._directed_deadline(self.local_start, 90, self.soft, self.first)


class _AfterWindow(staging._Window):
    def __init__(self, inputs, phase, previous, *, current_process_floor=None):
        # Default supplied same-process chronology is unchanged. A new command
        # supplies its own actual first pair, not a replacement historical LOCAL.
        self.current_process_floor = current_process_floor
        self.current_process_snapshot = (None if current_process_floor is None else
                                         staging._capture_phase(current_process_floor))
        snapshot = staging._capture_phase(phase)
        if current_process_floor is None:
            super().__init__(inputs, phase, snapshot, previous, "save-set-after")
        else:
            self.inputs, self.phase, self.phase_snapshot = inputs, phase, snapshot
            self.name, (clock, self.first, self.local_start) = "save-set-after", snapshot
            self.previous_raw, self.previous_ns, self.previous_local = previous
            # Retain/validate the old scalar only as data from its old process.
            staging._local(self.previous_local)
            start_clock, start_ns, start_local = self.current_process_snapshot
            origin.require(clock == start_clock == staging._clock(inputs.clock) and
                           origin.integer(self.previous_ns) <= start_ns <= self.first and
                           start_local <= self.local_start, "BOOTSTRAP_SAVE_AFTER_NEW_PROCESS_CLOCK")
            self.hard = min(origin.integer(self.first + 120 * origin.NS),
                            inputs.proposal["phaseFencesNs"]["save-set-after"], inputs.proposal["proposedJobEndNs"])
            self.local_hard = origin.wire._directed_deadline(self.local_start, 120, self.hard, self.first)
            self.last, self.local_last, self.last_new = self.first, self.local_start, self.first
        self.soft = min(self.hard, origin.integer(self.first + 90 * origin.NS))
        origin.require(self.first < self.soft, "BOOTSTRAP_SEED_ORIGINAL_PHASE_EXPIRED")
        self.local_soft = origin.wire._directed_deadline(self.local_start, 90, self.soft, self.first)

    def sample(self, *, new=False):
        if self.current_process_snapshot is not None:
            origin.require(staging._capture_phase(self.current_process_floor) == self.current_process_snapshot,
                           "BOOTSTRAP_SAVE_AFTER_NEW_PROCESS_CHANGED")
        else:
            origin.require(self.current_process_floor is None, "BOOTSTRAP_SAVE_AFTER_NEW_PROCESS_CHANGED")
        super().sample(new=new)


def before_save(parent, inputs, window, export_raw):
    """Observe the complete original export, under its own before-save window."""
    return _observe(parent, inputs, window, export_raw, None)


def after_save(parent, inputs, window, export_raw, frozen_raw):
    """Recheck original before-save bytes, not a substituted live baseline.

    The caller still owes original provider outcomes, NEW ownership and custody.
    A consistent supplied predecessor is not original-call or provider authority.
    """
    origin.require(type(frozen_raw) is bytes and 0 < len(frozen_raw) <= files.RECEIPT_LIMIT,
                   "BOOTSTRAP_SAVE_BEFORE_BYTES_REQUIRED")
    return _observe(parent, inputs, window, export_raw, frozen_raw)


def _observe(parent, inputs, window, export_raw, frozen_raw):
    """Check every original exported file and ancestor; never a partial freeze.

Streams per-file hashes with depth-bounded handles. No Windows aggregate
Snapshot, deletion, provider call or ordinary execution context is used.
"""
    after = frozen_raw is not None
    origin.require(type(inputs) is custody._Inputs and type(window) is (_AfterWindow if after else _Window) and
                   window.inputs is inputs and
                   type(export_raw) is bytes and 0 < len(export_raw) <= files.RECEIPT_LIMIT,
                   "BOOTSTRAP_SAVE_INPUT_WINDOW")
    leaf = staging._Leaf(parent, window)
    exported = origin.parse(export_raw)
    frozen = origin.parse(frozen_raw) if after else None
    result = {"schema": 1, "scope": AFTER_SCOPE if after else SCOPE,
        "binding": inputs.binding(), "predecessors": inputs.predecessors(),
        "exportSha256": files.digest(export_raw), "plan": inputs.stage_value["plan"],
        "phase": "after-save" if after else "before-save",
        "beforeSaveSha256": files.digest(frozen_raw) if after else None,
        "status": "FAILED", "completed": False, "retirement": "PENDING", "errors": [],
        "container": None, "stagingFile": None, "directories": [], "files": [],
        "counts": {"hashedBytes": 0, "verifiedFiles": 0, "members": 0},
        "inputProvenance": "SUPPLIED_RECORDS_NOT_ORIGINAL_CALL", "atomicSnapshot": False,
        "nextPhaseAuthority": False, "budgetAcceptance": "NOT_ADMITTED", "testAcceptance": "NOT_PERFORMED",
        "exportSaveAuthority": False}
    stamps, identities = {}, set()

    def close(resource, original=None):
        try:
            leaf.close_one(resource)
        except BaseException as failure:
            if original is None:
                raise
            leaf.error("bootstrap-save-close", failure)

    def read(directory, name, row, *, hash_bytes):
        end = leaf.end(new=True)
        reader = leaf.acquire("save-file", lambda: directory.open_file(name, max_bytes=row["size"], deadline=end))
        first = None
        try:
            origin.require(reader.initial_info.size == row["size"] and
                           files._info_binding(reader.verify()) == row["destination"],
                           "BOOTSTRAP_SAVE_FILE_CHANGED")
            if hash_bytes:
                origin.require(result["counts"]["hashedBytes"] + row["size"] <= files.TOTAL_LIMIT,
                               "BOOTSTRAP_SAVE_BYTE_LIMIT")
                result["counts"]["hashedBytes"] += row["size"]
                origin.require(files._hash(reader, row["size"], leaf.check) == (row["sha256"], row["sha1"]),
                               "BOOTSTRAP_SAVE_BYTES_CHANGED")
            origin.require(files._info_binding(reader.verify()) == row["destination"],
                           "BOOTSTRAP_SAVE_FILE_CHANGED")
        except BaseException as failure:
            first = failure
            leaf.error("bootstrap-save-file", failure)
            raise
        finally:
            close(reader, first)
        leaf.check()
        if hash_bytes:
            result["counts"]["verifiedFiles"] += 1

    def observe(directory, parts):
        leaf.check()
        stamp = files._info_binding(directory.verify())
        if parts not in stamps:
            origin.require(stamp["identity"][0] == inputs.stage["sourceIdentity"][0] and
                           tuple(stamp["identity"]) not in identities, "BOOTSTRAP_SAVE_DIRECTORY_ALIAS")
            identities.add(tuple(stamp["identity"]))
            stamps[parts] = {"path": "/".join(parts), "binding": stamp, "names": list(directories[parts])}
        else:
            custody._equal(stamp, stamps[parts]["binding"], "BOOTSTRAP_SAVE_DIRECTORY_CHANGED")
        end = leaf.end(new=True)
        origin.require(directory.names(max_names=files.NAMES_LIMIT, deadline=end) == directories[parts],
                       "BOOTSTRAP_SAVE_ROSTER_CHANGED")
        custody._equal(files._info_binding(directory.verify()), stamp, "BOOTSTRAP_SAVE_DIRECTORY_CHANGED")
        leaf.check()

    def visit(directory, parts, *, hash_bytes):
        observe(directory, parts)
        for name in directories[parts]:
            end = leaf.end(new=True)
            child_parts = (*parts, name)
            if child_parts in directories:
                child = leaf.acquire("save-directory", lambda: directory.open_directory(name, deadline=end))
                first = None
                try:
                    visit(child, child_parts, hash_bytes=hash_bytes)
                except BaseException as failure:
                    first = failure
                    leaf.error("bootstrap-save-directory", failure)
                    raise
                finally:
                    close(child, first)
            else:
                read(directory, name, selected[child_parts], hash_bytes=hash_bytes)
        observe(directory, parts)

    def container_observation(container):
        leaf.check()
        stamp = files._info_binding(container.verify())
        origin.require(stamp["identity"] == inputs.stage["containerIdentity"], "BOOTSTRAP_SAVE_CONTAINER_CHANGED")
        end = leaf.end(new=True)
        origin.require(container.names(max_names=files.NAMES_LIMIT, deadline=end) == ("restore-home", "staging.json"),
                       "BOOTSTRAP_SAVE_CONTAINER_ROSTER")
        custody._equal(files._info_binding(container.verify()), stamp, "BOOTSTRAP_SAVE_CONTAINER_CHANGED")
        leaf.check()
        return {"binding": stamp, "names": ["restore-home", "staging.json"]}

    try:
        leaf.check(new=True)
        source_inputs, compiled, extra = staging._sources(leaf, inputs)
        custody._equal(source_inputs, inputs.stage_value["inputs"], "BOOTSTRAP_SAVE_SOURCE_CHANGED")
        custody._equal(extra, inputs.stage_value["bootstrapInputs"], "BOOTSTRAP_SAVE_SOURCE_CHANGED")
        staging.cache.validate_plan(result["plan"], inputs.admitted.record, inputs.staging_raw, compiled,
            source_inputs, session=inputs.session, profile=inputs.profile, role=inputs.role, mode="bootstrap")
        origin.require(exported.get("scope") == dependency_export.SCOPE and exported.get("completed") is True and
                       exported.get("retirement") == "KNOWN" and exported.get("errors") == [] and
                       exported.get("status") in dependency_export.STATUSES[1:] and
                       exported.get("nextPhaseAuthority") is exported.get("exportSaveAuthority") is False and
                       exported.get("budgetAcceptance") == "NOT_ADMITTED" and
                       exported.get("testAcceptance") == "NOT_PERFORMED", "BOOTSTRAP_SAVE_EXPORT_NOT_KNOWN")
        for name, expected in (("binding", inputs.binding()), ("predecessors", inputs.predecessors()),
                ("plan", result["plan"]), ("destinationIdentity", inputs.stage["sourceIdentity"]),
                ("sourceIdentity", list(inputs.directories["gradle-home"])), ("home", str(inputs.home)),
                ("restoreHome", str(inputs.restore)), ("propertiesSha256", files.digest(inputs.properties_raw)),
                ("policy", files.policy())):
            custody._equal(exported[name], expected, "BOOTSTRAP_SAVE_EXPORT_BINDING")
        files._validate_inventory(exported, compiled, statuses=dependency_export.STATUSES,
                                  destination_identity=inputs.stage["sourceIdentity"])
        previous = origin.parse(window.previous_raw)
        previous_scope = ("BOOTSTRAP_SAVE_SET_PARENT_CLOSED_OBSERVATIONS_V1" if after else
                          "BOOTSTRAP_EXPORT_PARENT_CLOSED_OBSERVATIONS_V1")
        origin.require(previous.get("scope") == previous_scope and
                       previous.get("leafSha256") == files.digest(frozen_raw if after else export_raw) and
                       origin.integer(exported["window"]["finishedNs"]) <= window.previous_ns <= window.first,
                       "BOOTSTRAP_SAVE_EXPORT_PREDECESSOR")
        if after:
            origin.require(type(frozen) is dict and set(frozen) == set(result) | {"saveSetInputs", "window"} and
                           frozen["scope"] == SCOPE and frozen["phase"] == "before-save" and
                           frozen["beforeSaveSha256"] is None and frozen["status"] == STATUSES[0] and
                           frozen["completed"] is True and frozen["retirement"] == "KNOWN" and frozen["errors"] == [],
                           "BOOTSTRAP_SAVE_BEFORE_NOT_KNOWN")
            for name in ("schema", "binding", "predecessors", "exportSha256", "plan", "inputProvenance",
                         "atomicSnapshot", "nextPhaseAuthority", "budgetAcceptance", "testAcceptance", "exportSaveAuthority"):
                custody._equal(frozen[name], result[name], "BOOTSTRAP_SAVE_BEFORE_BINDING")
            original = frozen["window"]
            origin.require(type(original) is dict and set(original) == set(window.record()) and
                           original["phase"] == "save-set-before" and
                           original["proposalSha256"] == files.digest(inputs.proposal_raw) and
                           original["predecessorSha256"] == previous["exportParentSha256"],
                           "BOOTSTRAP_SAVE_BEFORE_WINDOW")
            custody._equal(original["clock"], origin.clock_value(inputs.clock), "BOOTSTRAP_SAVE_BEFORE_CLOCK")
            first, hard, soft, last_new, finished, prior = (origin.integer(original[name]) for name in
                ("firstNs", "hardEndNs", "softEndNs", "lastNewWorkNs", "finishedNs", "predecessorCheckedNs"))
            origin.require(hard == min(origin.integer(first + 120 * origin.NS),
                           inputs.proposal["phaseFencesNs"]["save-set-before"], inputs.proposal["proposedJobEndNs"]) and
                           soft == min(hard, origin.integer(first + 90 * origin.NS)) and
                           exported["window"]["finishedNs"] <= prior <= first <= last_new <= finished < hard and
                           last_new < soft and finished <= origin.integer(previous["closedNs"]) <=
                           origin.integer(window.previous_ns) < hard,
                           "BOOTSTRAP_SAVE_BEFORE_WINDOW")
            for name in ("clock", "firstNs", "softEndNs", "hardEndNs"):
                custody._equal(previous[name], original[name], "BOOTSTRAP_SAVE_BEFORE_PARENT_WINDOW")
        origin.require(0 < exported["counts"]["outputBytes"] <= files.TOTAL_LIMIT,
                       "BOOTSTRAP_SAVE_POSITIVE_EXPORT_REQUIRED")
        directories, selected = staging.cache._save_roster(exported)
        result["files"] = sorted(row["path"] for row in selected.values())
        result["counts"]["members"] = exported["counts"]["destinationMembers"]
        maximum = {"identity": [2**64 - 1, "f" * 32], "stampSha256": "f" * 64}
        reserve = {**result, "directories": [{"path": "/".join(parts), "binding": maximum, "names": list(names)}
                                             for parts, names in sorted(directories.items())]}
        origin.require(len(files.encoded(reserve)) + 4096 <= files.RECEIPT_LIMIT, "BOOTSTRAP_SAVE_RECEIPT_LIMIT")

        root = leaf.acquire("save-source-root", lambda: files.public_root(inputs.root))
        end = leaf.end(new=True)
        scripts = leaf.acquire("save-source-scripts", lambda: root.open_directory("scripts", deadline=end))
        source_hashes = {}
        for name in ("hosted_cache_bootstrap_export.py", "hosted_cache_bootstrap_custody.py", "hosted_dependency_cache.py"):
            raw, _binding = staging._read(leaf, scripts, name)
            source_hashes["scripts/" + name] = files.digest(raw)
        custody._equal(source_hashes, exported["exportInputs"], "BOOTSTRAP_SAVE_EXPORT_SOURCE_CHANGED")
        raw, _binding = staging._read(leaf, scripts, "hosted_cache_bootstrap_save_set.py")
        result["saveSetInputs"] = {**source_hashes, "scripts/hosted_cache_bootstrap_save_set.py": files.digest(raw)}
        scripts.verify()
        root.verify()
        leaf.close_one(scripts)
        leaf.close_one(root)

        container = leaf.acquire("save-container", lambda: files.private_root(inputs.container))
        result["container"] = container_observation(container)
        _, result["stagingFile"] = staging._read(leaf, container, "staging.json", expected=inputs.staging_raw,
                                                binding=inputs.stage_value["fileBindings"]["staging"])
        identities = {tuple(inputs.stage["containerIdentity"]), tuple(result["stagingFile"]["identity"])}
        origin.require(len(identities) == 2 and all(tuple(row["destination"]["identity"]) not in identities
                       for row in selected.values()), "BOOTSTRAP_SAVE_FILE_ALIAS")
        identities.update(tuple(row["destination"]["identity"]) for row in selected.values())
        end = leaf.end(new=True)
        output = leaf.acquire("save-stage", lambda: container.open_directory("restore-home", deadline=end))
        origin.require(list(output.identity) == inputs.stage["sourceIdentity"], "BOOTSTRAP_SAVE_STAGE_CHANGED")
        visit(output, (), hash_bytes=True)
        visit(output, (), hash_bytes=False)  # Fresh membership and original file stamps after early readers close.
        result["directories"] = [stamps[parts] for parts in sorted(stamps)]
        origin.require(len(stamps) == len(directories) and result["counts"]["verifiedFiles"] == len(selected) and
                       result["counts"]["hashedBytes"] == exported["counts"]["outputBytes"],
                       "BOOTSTRAP_SAVE_INCOMPLETE_SET")
        staging._read(leaf, container, "staging.json", expected=inputs.staging_raw, binding=result["stagingFile"])
        custody._equal(container_observation(container), result["container"], "BOOTSTRAP_SAVE_CONTAINER_CHANGED")
        leaf.check()
        leaf.close()
        leaf.check()
        result.update(status=AFTER_STATUS if after else STATUSES[0], completed=True,
                      retirement="KNOWN", window=window.record())
        if after:
            expected = {**result, "scope": SCOPE, "phase": "before-save", "beforeSaveSha256": None,
                        "status": STATUSES[0], "window": frozen["window"]}
            custody._equal(frozen, expected, "BOOTSTRAP_SAVE_FROZEN_SET_CHANGED")
            leaf.check()
        raw = files.encoded(result)
        leaf.check()
        return SaveSetEvidence(raw, window.last, window.local_start, window.local_last)
    except BaseException as failure:
        first = failure if parent.original is None else parent.original
        leaf.error("bootstrap-save-set", first)
        try:
            leaf.close()
        except BaseException as secondary:
            leaf.error("bootstrap-save-set-close", secondary)
        result.update(status="UNKNOWN" if parent.unknown else "FAILED", completed=False,
                      retirement="UNKNOWN" if parent.unknown else "FAILED", errors=[type(first).__name__],
                      window=window.record())
        try:
            first.bootstrap_save_set_result = result
            first.bootstrap_save_set_resources = tuple(leaf.resources)
        except BaseException:
            pass
        raise first
