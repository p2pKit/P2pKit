"""Dormant dependency-cache contracts and a bounded H-to-empty-S snapshot.

No CLI, workflow activation, provider call, extraction, subprocess, deletion or
network I/O. Pure action observations validate declared inputs, not hosted facts.
The future caller must bind genuine original outcomes and native/job authority.
"""
from __future__ import annotations

from pathlib import Path
import re
import time

import hosted_dependency_seed_files as files


ACTION_PIN = "caa296126883cff596d87d8935842f9db880ef25"
PLAN_SCOPE = "DEPENDENCY_CACHE_PLAN_V1"
EXPORT_SCOPE = "DEPENDENCY_CACHE_EXPORT_V1"
SAVE_SET_SCOPE = "DEPENDENCY_CACHE_SAVE_SET_V1"
OBSERVATION_SCOPE = "DEPENDENCY_CACHE_PROVIDER_OBSERVATION_V1"
EXPORT_KNOWN = ("KNOWN_EMPTY", "KNOWN_PARTIAL", "KNOWN_EXPORTED")
MODES = ("consume", "bootstrap")
OUTCOMES = ("success", "failure", "cancelled", "skipped", "")
RESTORE_OUTPUTS = {"cache-primary-key", "cache-matched-key", "cache-hit"}
PLAN_KEYS = {"schema", "scope", "mode", "profile", "role", "source", "github", "admissionSha256",
             "stagingSha256", "session", "restoreHome", "path", "inputs", "key", "provider"}


def require(value, reason):
    files.require(value, reason)


def _sha(value):
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _profile(profile, role):
    require(type(profile) is str and profile in ("desktop", "full") and type(role) is str and
            role in ("linux-x64", "windows-x64", "macos-arm64", "macos-x64") and
            (profile != "full" or role.startswith("macos-")), "CACHE_PROFILE_ROLE")


def cache_key(profile, role, allowlist_sha256, wrapper_properties_sha256):
    """Reusable byte cohort, deliberately NOT a source/test-result identity."""
    _profile(profile, role)
    require(_sha(allowlist_sha256) and _sha(wrapper_properties_sha256), "CACHE_KEY_INPUT")
    return ("p2pkit-dependency-files-v1-" + profile + "-" + role + "-" +
            allowlist_sha256 + "-" + wrapper_properties_sha256)


def _provider():
    return {"restore": "actions/cache/restore@" + ACTION_PIN, "save": "actions/cache/save@" + ACTION_PIN,
            "restoreKeys": [], "enableCrossOsArchive": False}


def _inputs(value, compiled):
    require(type(compiled) is files.authority.Allowlist and type(value) is dict and
            set(value) == {"files", "allowlistSha256", "artifacts", "components", "policy"} and
            type(value["files"]) is dict and set(value["files"]) == set(files.INPUTS) and
            all(_sha(sha) for sha in value["files"].values()) and
            value["files"][files.INPUTS[0]] == compiled.source_sha256 and
            value["allowlistSha256"] == compiled.authority_sha256 and
            type(value["artifacts"]) is int and value["artifacts"] == len(compiled.artifacts) and
            type(value["components"]) is int and value["components"] == compiled.component_count and
            files.encoded(value["policy"]) == files.encoded(files.policy()), "CACHE_ALLOWLIST_BINDING")


def make_plan(admitted_raw, staging_raw, compiled, inputs, *, session, profile, role, mode):
    """Pure plan from independently admitted source/stage inputs, not admission."""
    _profile(profile, role)
    require(type(mode) is str and mode in MODES, "CACHE_EXPLICIT_MODE_REQUIRED")
    cohort = files.validate_cohort(admitted_raw, profile, role)
    require(cohort is None or mode == "bootstrap", "CACHE_BOOTSTRAP_CANNOT_CONSUME")
    session = Path(session)
    require(session.is_absolute() and ".." not in session.parts and len(session.parts) > 2,
            "CACHE_SESSION_PATH")
    _inputs(inputs, compiled)
    admitted, staging = files.record(admitted_raw), files.record(staging_raw)
    context = {"session": str(session), "profile": profile, "role": role}
    files.validate_retained_stage(staging, admitted_raw, context, inputs)
    require(staging_raw == files.encoded(staging), "CACHE_STAGE_NOT_CANONICAL")
    source, github = admitted["source"], admitted["github"]
    require(type(source) is dict and set(source) == {"commit", "tree"} and all(
            type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value) for value in source.values()) and
            type(github) is dict and all(type(github.get(key)) is str and
            re.fullmatch(r"[1-9][0-9]{0,19}", github[key]) for key in ("runId", "runAttempt")),
            "CACHE_ORIGINAL_SOURCE_RUN")
    home = files.stage_path(session, profile, role) / "restore-home"
    return files.record(files.encoded({
        "schema": 1, "scope": PLAN_SCOPE, "mode": mode, "profile": profile, "role": role,
        "source": source, "github": github, "admissionSha256": files.digest(admitted_raw),
        "stagingSha256": files.digest(staging_raw), "session": str(session), "restoreHome": str(home),
        "path": str(home.joinpath(*files.PREFIX)), "inputs": inputs,
        "key": cache_key(profile, role, compiled.authority_sha256, inputs["files"][files.INPUTS[1]]),
        "provider": _provider()}))


def validate_plan(value, admitted_raw, staging_raw, compiled, inputs, *, session, profile, role, mode):
    expected = make_plan(admitted_raw, staging_raw, compiled, inputs, session=session,
                         profile=profile, role=role, mode=mode)
    require(type(value) is dict and files.encoded(value) == files.encoded(expected), "CACHE_PLAN_CHANGED")
    return value


def _plan_shape(plan):
    # Original bytes/source/staging must ALSO be checked by validate_plan in a
    # real caller. This structural guard cannot authenticate caller-supplied data.
    require(type(plan) is dict and set(plan) == PLAN_KEYS and type(plan["schema"]) is int and
            plan["schema"] == 1 and plan["scope"] == PLAN_SCOPE and plan["mode"] in MODES,
            "CACHE_PLAN_GRAMMAR")
    _profile(plan["profile"], plan["role"])
    require(_sha(plan["admissionSha256"]) and _sha(plan["stagingSha256"]) and
            plan["key"] == cache_key(plan["profile"], plan["role"], plan["inputs"]["allowlistSha256"],
                                     plan["inputs"]["files"][files.INPUTS[1]]) and
            files.encoded(plan["provider"]) == files.encoded(_provider()), "CACHE_PLAN_POLICY")
    files.encoded(plan)


def provider_observation(plan, phase, *, original_outcome, outputs):
    """Classify declarations; never invoke a provider or authorize its execution.

    Standalone save declares NO outputs and can succeed without storing anything.
    Restore's primary key is provisional; false/blank hit is not proven absence.
    Require byte-equal primary/matched keys even when the action says hit=true.
    """
    _plan_shape(plan)
    require(type(phase) is str and phase in (("restore",) if plan["mode"] == "consume" else ("save", "lookup")),
            "CACHE_PHASE_FORBIDDEN_IN_MODE")
    require(type(original_outcome) is str and original_outcome in OUTCOMES, "CACHE_ORIGINAL_OUTCOME")
    require(type(outputs) is dict and set(outputs) == (set() if phase == "save" else RESTORE_OUTPUTS),
            "CACHE_PROVIDER_OUTPUT_ROSTER")
    require(all(type(value) is str and len(value) <= 512 and all(32 <= ord(c) < 127 for c in value)
                for value in outputs.values()), "CACHE_PROVIDER_OUTPUT_VALUE")
    if phase != "save":
        require(outputs["cache-hit"] in ("", "true", "false"), "CACHE_PROVIDER_HIT_VALUE")
    if original_outcome != "success":
        status = "STEP_NOT_SUCCESSFUL"
    elif phase == "save":
        status = "SAVE_SUCCEEDED_STORAGE_UNPROVEN"
    elif (outputs["cache-primary-key"] == plan["key"] == outputs["cache-matched-key"] and
          outputs["cache-hit"] == "true"):
        status = "REPORTED_EXACT_HIT"
    else:
        status = "NO_QUALIFIED_EXACT_HIT"
    return {"schema": 1, "scope": OBSERVATION_SCOPE, "planSha256": files.digest(files.encoded(plan)),
            "phase": phase, "originalOutcome": original_outcome, "outputs": dict(outputs), "status": status}


def validate_provider_observation(value, plan, phase):
    require(type(value) is dict and set(value) == {"schema", "scope", "planSha256", "phase",
            "originalOutcome", "outputs", "status"}, "CACHE_OBSERVATION_GRAMMAR")
    expected = provider_observation(plan, phase, original_outcome=value["originalOutcome"], outputs=value["outputs"])
    require(files.encoded(value) == files.encoded(expected), "CACHE_OBSERVATION_CHANGED_OR_REPLAYED")
    return value


def _export_inputs(plan, staging_raw, seed_raw, context_raw, canonical_raw, admitted_raw, compiled):
    files.require_connected_execution(admitted_raw)
    context, canonical, previous = map(files.record, (context_raw, canonical_raw, seed_raw))
    intent = context["dependencySeed"]
    validate_plan(plan, admitted_raw, staging_raw, compiled, intent["inputs"], session=context["session"],
                  profile=context["profile"], role=context["role"], mode="bootstrap")
    files.validate_receipt(previous, intent, staging_raw, context_raw, canonical_raw, admitted_raw, compiled)
    require(seed_raw == files.encoded(previous) and previous["status"] == "KNOWN_MISS" and
            not previous["admitted"], "CACHE_BOOTSTRAP_REQUIRES_EMPTY_ORIGINAL_SEED")
    return context, canonical, previous


def _interval(value, context, *, finished):
    require(type(value) is dict and set(value) == {"clock", "startedNs", "hardEndNs", "softEndNs",
            "finishedNs", "jobBudgetSha256"}, "CACHE_EXPORT_WINDOW_GRAMMAR")
    full = context["profile"] == "full"
    expected = files.window(value["startedNs"], value["hardEndNs"], value["softEndNs"], raw=full,
                            job_budget=context["jobBudgetSha256"] if full else None)
    if finished:
        require(type(value["finishedNs"]) is int and
                value["startedNs"] <= value["finishedNs"] < value["hardEndNs"], "CACHE_EXPORT_LATE_FINALIZATION")
        expected["finishedNs"] = value["finishedNs"]
    require(files.encoded(value) == files.encoded(expected), "CACHE_EXPORT_WINDOW_CHANGED")
    if full:
        require(_sha(context["jobBudgetSha256"]) and
                value["hardEndNs"] <= context["primaryAbiAccounting"]["productiveCutoffRawNs"],
                "CACHE_EXPORT_ORIGINAL_PRODUCTIVE_CUTOFF")


def _export_binding(plan, staging_raw, seed_raw, context_raw, canonical_raw, previous):
    return {"schema": 1, "scope": EXPORT_SCOPE, "planSha256": files.digest(files.encoded(plan)),
            "seedManifestSha256": files.digest(seed_raw), "stagingSha256": files.digest(staging_raw),
            "contextSha256": files.digest(context_raw), "canonicalContextSha256": files.digest(canonical_raw),
            "source": plan["source"], "github": plan["github"], "profile": plan["profile"], "role": plan["role"],
            "home": previous["home"], "restoreHome": plan["restoreHome"], "inputs": plan["inputs"],
            "sourceIdentity": previous["homeIdentity"], "destinationIdentity": previous["sourceIdentity"],
            "propertiesSha256": previous["propertiesSha256"], "policy": files.policy(), "wrapper": files.WRAPPER}


def export_snapshot(parent, plan, staging_raw, seed_raw, context_raw, canonical_raw, admitted_raw, compiled,
                    *, end, check, now, interval):
    """Snapshot verified artifact bytes only, without replacing original H or S.

    A real caller must first establish prior producer/worker retirement. This
    function creates files in the original empty S, not a new/restored replacement.
    It retains no authority to run a provider or to save after a failed profile.
    """
    # The supplied liveness callback must not redirect paths or renew an already
    # admitted cutoff by mutating the caller's dictionaries during the copy.
    plan = files.record(files.encoded(plan))
    interval = files.record(files.encoded(interval))
    context, canonical, previous = _export_inputs(
        plan, staging_raw, seed_raw, context_raw, canonical_raw, admitted_raw, compiled)
    _interval(interval, context, finished=False)
    require(type(end) in (int, float) and time.monotonic() < end <= time.monotonic() + files.HARD_SECONDS,
            "CACHE_EXPORT_FILE_WINDOW")
    result = _export_binding(plan, staging_raw, seed_raw, context_raw, canonical_raw, previous)
    result.update(status="FAILED", completed=False, retirement="KNOWN", errors=[], window=dict(interval),
                  counts={"prehashBytes": 0, "outputBytes": 0, "sourceNames": 0, "destinationMembers": 0,
                          "sha256Rejected": 0, "layoutRejected": 0}, admitted=[], misses=[])
    owners, first = files._Owners(parent), None
    def checked():
        check()
        files._deadline(end)
        require(not parent.unknown, "CACHE_EXPORT_RETIREMENT_UNKNOWN")
        current = now()
        require(type(current) is int and interval["startedNs"] <= current < interval["hardEndNs"],
                "CACHE_EXPORT_ORIGINAL_HARD_DEADLINE")
        return current
    try:
        checked()
        staging = files.record(staging_raw)
        container = owners.acquire("export-container", lambda: files.private_root(Path(plan["restoreHome"]).parent))
        require(list(container.identity) == staging["containerIdentity"], "CACHE_EXPORT_CONTAINER_REPLACED")
        source = owners.acquire("export-home", lambda: files.public_root(previous["home"]))
        output = owners.acquire("export-stage", lambda: files.private_root(plan["restoreHome"]))
        require(list(source.identity) == previous["homeIdentity"] and
                list(output.identity) == staging["sourceIdentity"] and source.identity != output.identity,
                "CACHE_EXPORT_ORIGINAL_ROOT_REPLACED")
        require(output.names(max_names=files.NAMES_LIMIT, deadline=end) == (), "CACHE_EXPORT_STAGE_NOT_EMPTY")
        properties = files._small_read(owners, source, "gradle.properties", end, files.RECEIPT_LIMIT, checked)
        require(files.digest(properties) == canonical["gradlePropertiesSha256"], "CACHE_EXPORT_PROPERTIES_CHANGED")
        budget = files.RECEIPT_LIMIT - len(files.encoded(result)) - 512 * 1024
        files._copy_allowlisted(owners, source, output, compiled, result, end, checked, now, interval,
                                budget, empty_destination=True)
        require(files._small_read(owners, source, "gradle.properties", end, files.RECEIPT_LIMIT, checked) == properties,
                "CACHE_EXPORT_PROPERTIES_CHANGED")
        source.verify()
        output.verify()
        checked()
    except BaseException as error:
        first = error
        parent.error("dependency-cache-export", error)
    finally:
        try:
            owners.close()
        except BaseException as error:
            if first is None:
                first = error
            else:
                files._note(first, "cache-export-final", error)
        result["retirement"] = "UNKNOWN" if parent.unknown else "KNOWN"
    if first is None:
        try:
            result["window"]["finishedNs"] = checked()
            result.update(completed=True, status=EXPORT_KNOWN[0] if not result["admitted"] else
                          EXPORT_KNOWN[1] if result["misses"] else EXPORT_KNOWN[2])
            validate_export_receipt(result, plan, staging_raw, seed_raw, context_raw,
                                    canonical_raw, admitted_raw, compiled)
            files.encoded(result)
            checked()  # Validation/encoding cannot turn a late result into success.
        except BaseException as error:
            first = error
            parent.error("dependency-cache-export-final", error)
    if first is not None:
        result.update(completed=False, status="UNKNOWN" if parent.unknown else "FAILED",
                      retirement="UNKNOWN" if parent.unknown else "KNOWN", errors=[type(first).__name__])
        first.cache_export_result = result
        raise first
    return result


def validate_export_receipt(value, plan, staging_raw, seed_raw, context_raw, canonical_raw, admitted_raw, compiled):
    """Check retained original receipt semantics, never later H/S/provider bytes."""
    context, _canonical, previous = _export_inputs(
        plan, staging_raw, seed_raw, context_raw, canonical_raw, admitted_raw, compiled)
    binding = _export_binding(plan, staging_raw, seed_raw, context_raw, canonical_raw, previous)
    require(type(value) is dict and set(value) == set(binding) |
            {"status", "completed", "retirement", "errors", "window", "counts", "admitted", "misses"},
            "CACHE_EXPORT_RECEIPT_GRAMMAR")
    require(files.encoded({key: value[key] for key in binding}) == files.encoded(binding),
            "CACHE_EXPORT_RECEIPT_BINDING_CHANGED")
    require(value["completed"] is True and value["retirement"] == "KNOWN" and value["errors"] == [] and
            value["status"] in EXPORT_KNOWN, "CACHE_EXPORT_RECEIPT_NOT_KNOWN")
    _interval(value["window"], context, finished=True)
    files._validate_inventory(value, compiled, statuses=EXPORT_KNOWN,
                              destination_identity=value["destinationIdentity"])
    files.encoded(value)
    return value


def nonempty_snapshot(value):
    """Summary of an ALREADY validated snapshot, not save/population authority."""
    return (type(value) is dict and value.get("scope") == EXPORT_SCOPE and value.get("completed") is True and
            value.get("retirement") == "KNOWN" and value.get("status") in EXPORT_KNOWN[1:] and
            type(value.get("counts")) is dict and type(value["counts"].get("outputBytes")) is int and
            0 < value["counts"]["outputBytes"] <= files.TOTAL_LIMIT)


def _save_roster(exported):
    """The complete directory/file union, not just the selected file names."""
    directories, selected = {(): set()}, {}
    for row in exported["admitted"]:
        parts = tuple(row["path"].split("/"))
        selected[parts] = row
        for index, name in enumerate(parts):
            directories.setdefault(parts[:index], set()).add(name)
    return {parts: tuple(sorted(names)) for parts, names in directories.items()}, selected


def _save_binding(plan, export_raw, staging_raw, seed_raw, context_raw, canonical_raw, admitted_raw, compiled):
    exported = validate_export_receipt(files.record(export_raw), plan, staging_raw, seed_raw,
                                       context_raw, canonical_raw, admitted_raw, compiled)
    require(nonempty_snapshot(exported), "CACHE_SAVE_POSITIVE_EXPORT_REQUIRED")
    binding = {"schema": 1, "scope": SAVE_SET_SCOPE, "source": plan["source"], "github": plan["github"],
               "profile": plan["profile"], "role": plan["role"], "restoreHome": plan["restoreHome"],
               "key": plan["key"], "policy": files.policy(), "originalsSha256": {
                   name: files.digest(raw) for name, raw in (
                       ("plan", files.encoded(plan)), ("export", export_raw), ("staging", staging_raw),
                       ("seed", seed_raw), ("context", context_raw), ("canonical", canonical_raw),
                       ("admission", admitted_raw))}}
    return binding, exported, files.record(context_raw), files.record(staging_raw)


def _validate_save_set(value, binding, exported, context, staging, frozen=None):
    required = set(binding) | {"phase", "beforeSaveSha256", "status", "completed", "retirement", "errors",
                               "window", "container", "stagingFile", "directories", "files", "counts"}
    require(type(value) is dict and set(value) == required and type(value["schema"]) is int and
            files.encoded({key: value[key] for key in binding}) == files.encoded(binding),
            "CACHE_SAVE_ORIGINAL_BINDING_CHANGED")
    require(value["phase"] == ("before-save" if frozen is None else "after-save") and
            value["beforeSaveSha256"] == (None if frozen is None else files.digest(frozen)) and
            value["status"] == ("KNOWN_FROZEN" if frozen is None else "KNOWN_UNCHANGED") and
            value["completed"] is True and value["retirement"] == "KNOWN" and value["errors"] == [],
            "CACHE_SAVE_RESULT_NOT_KNOWN")
    _interval(value["window"], context, finished=True)
    require(value["window"]["startedNs"] >= exported["window"]["finishedNs"],
            "CACHE_SAVE_PRECEDES_EXPORT")
    directories, selected = _save_roster(exported)
    expected_counts = {"hashedBytes": exported["counts"]["outputBytes"], "verifiedFiles": len(selected),
                       "members": exported["counts"]["destinationMembers"]}
    require(type(value["counts"]) is dict and set(value["counts"]) == set(expected_counts) and
            all(type(count) is int for count in value["counts"].values()) and
            value["counts"] == expected_counts and value["files"] == sorted(row["path"] for row in selected.values()),
            "CACHE_SAVE_INCOMPLETE_ROSTER")
    container = value["container"]
    require(type(container) is dict and set(container) == {"binding", "names"} and
            files._file_binding(container["binding"]) and
            container["binding"]["identity"] == staging["containerIdentity"] and
            container["names"] == ["restore-home", "staging.json"] and
            files._file_binding(value["stagingFile"]) and
            value["stagingFile"]["identity"][0] == staging["sourceIdentity"][0] and
            value["stagingFile"]["identity"] not in (staging["containerIdentity"], staging["sourceIdentity"]),
            "CACHE_SAVE_CONTAINER_BINDING")
    rows = value["directories"]
    require(type(rows) is list and len(rows) == len(directories), "CACHE_SAVE_DIRECTORY_ROSTER")
    identities = {tuple(staging["containerIdentity"]), tuple(value["stagingFile"]["identity"])}
    for row, parts in zip(rows, sorted(directories)):
        require(type(row) is dict and set(row) == {"path", "binding", "names"} and
                row["path"] == "/".join(parts) and row["names"] == list(directories[parts]) and
                files._file_binding(row["binding"]) and
                row["binding"]["identity"][0] == staging["sourceIdentity"][0] and
                tuple(row["binding"]["identity"]) not in identities, "CACHE_SAVE_DIRECTORY_BINDING")
        if not parts:
            require(row["binding"]["identity"] == staging["sourceIdentity"], "CACHE_SAVE_STAGE_REPLACED")
        identities.add(tuple(row["binding"]["identity"]))
    require(all(tuple(row["destination"]["identity"]) not in identities for row in selected.values()),
            "CACHE_SAVE_FILE_DIRECTORY_IDENTITY_ALIAS")
    if frozen is not None:
        previous = files.record(frozen)
        _validate_save_set(previous, binding, exported, context, staging)
        require(value["window"]["startedNs"] >= previous["window"]["finishedNs"],
                "CACHE_SAVE_PRECEDES_FROZEN_OBSERVATION")
        require(all(value[key] == previous[key] for key in ("container", "stagingFile", "directories", "files", "counts")),
                "CACHE_SAVE_FROZEN_SET_CHANGED")
    files.encoded(value)
    return value


def validate_save_set_receipt(value, plan, export_raw, staging_raw, seed_raw, context_raw,
                              canonical_raw, admitted_raw, compiled, *, frozen_raw=None):
    """Retained semantics only. Original-byte custody is the caller's authority.

    A wholly substituted record cannot authenticate itself. The eventual
    provider caller must retain the original before-save bytes independently.
    """
    binding, exported, context, staging = _save_binding(
        plan, export_raw, staging_raw, seed_raw, context_raw, canonical_raw, admitted_raw, compiled)
    return _validate_save_set(value, binding, exported, context, staging, frozen_raw)


def save_set(parent, plan, export_raw, staging_raw, seed_raw, context_raw, canonical_raw, admitted_raw, compiled,
             *, end, check, now, interval, frozen_raw=None):
    """Read-only live freeze/recheck of the original exported dependency subset.

    Use a separately admitted window for each observation. This neither runs a
    provider nor establishes producer success/retirement, atomicity between
    observations, archived bytes, resolver reuse or a successful bootstrap.
    Only the eventual original-outcome/custody caller can establish those facts.
    """
    plan, interval = files.record(files.encoded(plan)), files.record(files.encoded(interval))
    binding, exported, context, staging = _save_binding(
        plan, export_raw, staging_raw, seed_raw, context_raw, canonical_raw, admitted_raw, compiled)
    _interval(interval, context, finished=False)
    require(interval["startedNs"] >= exported["window"]["finishedNs"], "CACHE_SAVE_PRECEDES_EXPORT")
    frozen = None if frozen_raw is None else files.record(frozen_raw)
    if frozen is not None:
        _validate_save_set(frozen, binding, exported, context, staging)
        require(interval["startedNs"] >= frozen["window"]["finishedNs"],
                "CACHE_SAVE_PRECEDES_FROZEN_OBSERVATION")
    require(type(end) in (int, float) and time.monotonic() < end <= time.monotonic() + files.HARD_SECONDS,
            "CACHE_SAVE_FILE_WINDOW")
    directories, selected = _save_roster(exported)
    result = {**binding, "phase": "before-save" if frozen is None else "after-save",
              "beforeSaveSha256": None if frozen is None else files.digest(frozen_raw),
              "status": "FAILED", "completed": False, "retirement": "KNOWN", "errors": [], "window": interval,
              "container": None, "stagingFile": None, "directories": [],
              "files": sorted(row["path"] for row in selected.values()),
              "counts": {"hashedBytes": 0, "verifiedFiles": 0, "members": exported["counts"]["destinationMembers"]}}
    # Reserve the complete record before opening members. No progressively
    # truncated roster can become positive save authority.
    maximum = {"identity": [2**64 - 1, "f" * 32], "stampSha256": "f" * 64}
    reserve = {**result, "directories": [{"path": "/".join(parts), "binding": maximum, "names": list(names)}
                                          for parts, names in sorted(directories.items())]}
    require(len(files.encoded(reserve)) + 2048 <= files.RECEIPT_LIMIT, "CACHE_SAVE_RECEIPT_BUDGET")
    owners, first, stamps = files._Owners(parent), None, {}
    last = interval["startedNs"]
    def checked(*, new=False):
        nonlocal last
        check()
        files._deadline(end)
        require(not parent.unknown, "CACHE_SAVE_RETIREMENT_UNKNOWN")
        current = now()
        require(type(current) is int and last <= current < interval["hardEndNs"],
                "CACHE_SAVE_CLOCK_OR_HARD_DEADLINE")
        last = current
        require(not new or current < interval["softEndNs"], "CACHE_SAVE_NEW_WORK_CUTOFF")
        return current
    def close(resource, original=None):
        try:
            owners.close_one(resource)
        except BaseException as error:
            if original is None:
                raise
            files._note(original, "save-set-resource", error)
    def read(directory, name, *, size, sha256, expected=None, sha1=None, hash_bytes=True):
        checked(new=True)
        reader = owners.acquire("save-file", lambda: directory.open_file(name, max_bytes=size, deadline=end))
        original = None
        try:
            stamp = files._info_binding(reader.verify())
            require(reader.initial_info.size == size and (expected is None or stamp == expected),
                    "CACHE_SAVE_FILE_STAMP_CHANGED")
            if hash_bytes:
                hashes = files._hash(reader, size, checked)
                require(hashes[0] == sha256 and (sha1 is None or hashes[1] == sha1), "CACHE_SAVE_FILE_BYTES_CHANGED")
            require(files._info_binding(reader.verify()) == stamp, "CACHE_SAVE_FILE_STAMP_CHANGED")
        except BaseException as error:
            original = error
            parent.error("dependency-cache-save-file", error)
            raise
        finally:
            close(reader, original)
        checked()
        return stamp
    def observe(directory, parts):
        checked()
        stamp = files._info_binding(directory.verify())
        if parts in stamps:
            require(stamp == stamps[parts]["binding"], "CACHE_SAVE_DIRECTORY_STAMP_CHANGED")
        else:
            stamps[parts] = {"path": "/".join(parts), "binding": stamp, "names": list(directories[parts])}
        # Always enumerate anew; _SourceLookup's cached listings are NOT a
        # before/after save-set observation. Empty unexpected dirs also fail.
        require(directory.names(max_names=files.NAMES_LIMIT, deadline=end) == directories[parts] and
                files._info_binding(directory.verify()) == stamp, "CACHE_SAVE_DIRECTORY_MEMBERS_CHANGED")
        checked()
    def visit(directory, parts, *, hash_bytes):
        observe(directory, parts)
        for name in directories[parts]:
            checked(new=True)
            child_parts = (*parts, name)
            if child_parts in directories:
                child = owners.acquire("save-directory", lambda: directory.open_directory(name, deadline=end))
                original = None
                try:
                    visit(child, child_parts, hash_bytes=hash_bytes)
                except BaseException as error:
                    original = error
                    # Preserve the first error and poison uncertain cursor
                    # ownership before any nested directory finalizer runs.
                    parent.error("dependency-cache-save-directory", error)
                    raise
                finally:
                    close(child, original)
            else:
                row = selected[child_parts]
                if hash_bytes:
                    require(result["counts"]["hashedBytes"] + row["size"] <= files.TOTAL_LIMIT,
                            "CACHE_SAVE_BYTE_BUDGET")
                    result["counts"]["hashedBytes"] += row["size"]
                read(directory, name, size=row["size"], sha256=row["sha256"], sha1=row["sha1"],
                     expected=row["destination"], hash_bytes=hash_bytes)
                if hash_bytes:
                    result["counts"]["verifiedFiles"] += 1
        observe(directory, parts)
    def container_observation(container):
        checked()
        stamp = files._info_binding(container.verify())
        require(stamp["identity"] == staging["containerIdentity"], "CACHE_SAVE_CONTAINER_REPLACED")
        names = container.names(max_names=files.NAMES_LIMIT, deadline=end)
        require(names == ("restore-home", "staging.json") and
                files._info_binding(container.verify()) == stamp, "CACHE_SAVE_CONTAINER_MEMBERS_CHANGED")
        return {"binding": stamp, "names": list(names)}
    try:
        checked(new=True)
        container = owners.acquire("save-container", lambda: files.private_root(staging["container"]))
        result["container"] = container_observation(container)
        if frozen is not None:
            require(result["container"] == frozen["container"], "CACHE_SAVE_FROZEN_CONTAINER_CHANGED")
            stamps.update((tuple(row["path"].split("/")) if row["path"] else (), row)
                          for row in frozen["directories"])
        result["stagingFile"] = read(container, "staging.json", size=len(staging_raw), sha256=files.digest(staging_raw),
                                     expected=None if frozen is None else frozen["stagingFile"])
        checked(new=True)
        root = owners.acquire("save-stage", lambda: container.open_directory("restore-home", deadline=end))
        require(list(root.identity) == staging["sourceIdentity"], "CACHE_SAVE_STAGE_REPLACED")
        visit(root, (), hash_bytes=True)
        # Streaming keeps descriptors depth-bounded. Reopen original members
        # for final stamps after early readers close; never pin a 2GiB Snapshot.
        visit(root, (), hash_bytes=False)
        result["directories"] = [stamps[parts] for parts in sorted(stamps)]
        read(container, "staging.json", size=len(staging_raw), sha256=files.digest(staging_raw),
             expected=result["stagingFile"])
        require(container_observation(container) == result["container"], "CACHE_SAVE_CONTAINER_CHANGED")
        checked()
    except BaseException as error:
        first = error
        parent.error("dependency-cache-save-set", error)
    finally:
        try:
            owners.close()
        except BaseException as error:
            if first is None:
                first = error
            else:
                files._note(first, "save-set-final", error)
    if first is None:
        try:
            result["window"]["finishedNs"] = checked()
            result.update(completed=True, status="KNOWN_FROZEN" if frozen is None else "KNOWN_UNCHANGED")
            _validate_save_set(result, binding, exported, context, staging, frozen_raw)
            files.encoded(result)
            result["window"]["finishedNs"] = checked()  # Keep the final validation high-water.
        except BaseException as error:
            first = error
            parent.error("dependency-cache-save-set-final", error)
    if first is not None:
        result.update(completed=False, status="UNKNOWN" if parent.unknown else "FAILED",
                      retirement="UNKNOWN" if parent.unknown else "KNOWN", errors=[type(first).__name__])
        first.cache_save_set_result = result
        raise first
    return result
