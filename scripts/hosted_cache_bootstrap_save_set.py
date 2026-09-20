"""Bootstrap before-save observation; no provider, workflow or atomic snapshot.

The same-call parent must supply its original successful export return. These
supplied-data checks do not authenticate that return or grant save authority.
Ordinary cache.save_set and its bootstrap-refusal guards remain unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import hosted_cache_bootstrap_export as dependency_export


custody = dependency_export.custody
staging, files, origin = custody.staging, custody.files, custody.origin
SCOPE = "BOOTSTRAP_SAVE_SET_BEFORE_LEAF_V1"
STATUSES = ("KNOWN_FROZEN",)


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


def before_save(parent, inputs, window, export_raw):
    """Check every original exported file and ancestor; never a partial freeze.

Streams per-file hashes with depth-bounded handles. No Windows aggregate
Snapshot, deletion, provider call or ordinary execution context is used.
"""
    origin.require(type(inputs) is custody._Inputs and type(window) is _Window and window.inputs is inputs and
                   type(export_raw) is bytes and 0 < len(export_raw) <= files.RECEIPT_LIMIT,
                   "BOOTSTRAP_SAVE_INPUT_WINDOW")
    leaf = staging._Leaf(parent, window)
    exported = origin.parse(export_raw)
    result = {"schema": 1, "scope": SCOPE, "binding": inputs.binding(), "predecessors": inputs.predecessors(),
        "exportSha256": files.digest(export_raw), "plan": inputs.stage_value["plan"], "phase": "before-save",
        "beforeSaveSha256": None, "status": "FAILED", "completed": False, "retirement": "PENDING", "errors": [],
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
        origin.require(previous.get("scope") == "BOOTSTRAP_EXPORT_PARENT_CLOSED_OBSERVATIONS_V1" and
                       previous.get("leafSha256") == files.digest(export_raw) and
                       origin.integer(exported["window"]["finishedNs"]) <= window.previous_ns <= window.first,
                       "BOOTSTRAP_SAVE_EXPORT_PREDECESSOR")
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
        result.update(status=STATUSES[0], completed=True, retirement="KNOWN", window=window.record())
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
