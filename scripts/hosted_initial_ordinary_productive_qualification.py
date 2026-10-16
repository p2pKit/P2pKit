"""Exact productive Stage1 originals used by the distinct native Stage2 owner.

Readers here accept supplied DATA only. They never issue ordinary Admission,
restore caches, obtain private keys, authenticate native ownership, or lift a
HOLD. The fixed Stage2 controller must acquire every input under its original
native fence, use the maintained productive codecs, and retain/close its real
owners before its separate typed current return may exist.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
import hashlib
from pathlib import PurePosixPath, PureWindowsPath
import re
import struct
from urllib.parse import urlencode
import zlib

import hosted_dependency_cache as cache
import hosted_cache_compatibility as source_compatibility
import hosted_dependency_seed_files as seed
import hosted_initial_artifact_zip as ZIP
import hosted_initial_ordinary_identity as worker
import hosted_initial_ordinary_qualification as references


S, I = references.stages, references.I
API = "/repos/" + I.REPOSITORY
INVENTORY_SCOPE = "INITIAL_PRODUCTIVE_QUALIFICATION_INVENTORY_V1"
COMPATIBILITY_SCOPE = "INITIAL_PRODUCTIVE_QUALIFICATION_COMPATIBILITY_V1"
REVIEW_SCOPE = "INITIAL_PRODUCTIVE_QUALIFICATION_REVIEW_V1"
REVIEW_DECISION = "APPROVE_EXACT_PRODUCTIVE_BOOTSTRAP_QUALIFICATION_ORIGINALS_ONLY"
COMMON = "schema scope repository source selection runId runAttempt completedAt packet"
HISTORY_FIELDS = ("comment", "observation", "basePolicyEntry", "ancestry",
                  "candidatePolicyEntry", "candidatePolicy", "match")
STEP_NAMES = (
    "P2pKit initial productive custody export",
    "P2pKit initial productive post-export custody",
    "P2pKit initial productive custody seal",
    "P2pKit initial productive before-upload custody",
    "P2pKit initial productive custody upload",
    "P2pKit initial productive after-upload custody",
    "P2pKit initial productive receipt originals capture",
    "P2pKit initial productive receipt originals upload",
)
# Source bytes, not a floating provider/npm dependency or a tool install. These
# are read through native source-file owners on H2, then compared with the exact
# H1 input inventory actually examined by the owner inside the qualified packet.
PROVIDER_INPUTS = source_compatibility.PROVIDER_INPUTS
COMPRESSIONS = ("gzip", "zstd-without-long")
QUALIFIED_SCOPE = "INITIAL_ORDINARY_PRODUCTIVE_REFERENCE_QUALIFICATION_ONLY_V1"


@dataclass(frozen=True, repr=False)
class ProductiveQualification:
    """Immutable supplied-DATA output, never a native/current capability."""

    record: bytes = field(repr=False)
    history: S.BootstrapHistory = field(repr=False)


def require(value, code):
    I.require(value, "INITIAL_ORDINARY_QUALIFICATION_" + code)


def canonical(raw, maximum=references.COMMENT_LIMIT):
    require(type(raw) is bytes, "BYTES")
    value = I.parse(raw, maximum)
    require(raw in (I.encoded(value), I.encoded(value).removesuffix(b"\n")), "CANONICAL")
    return value


def same(left, right, code):
    require(I.encoded(left) == I.encoded(right), code)


def digest(raw):
    require(type(raw) is bytes, "DIGEST_INPUT")
    return hashlib.sha256(raw).hexdigest()


def original_bytes(value, maximum, *, empty=False):
    require(type(value) is str and (empty or value) and len(value) <= 4 * ((maximum + 2) // 3), "ORIGINAL_BASE64")
    try:
        raw = base64.b64decode(value, validate=True)
    except (ValueError, UnicodeError):
        raise I.AdmissionError("INITIAL_ORDINARY_QUALIFICATION_ORIGINAL_BASE64") from None
    require((empty or raw) and len(raw) <= maximum and base64.b64encode(raw).decode("ascii") == value,
            "ORIGINAL_BASE64")
    return raw


def _metadata(raw, scope, extra, entry, source):
    value = S.fields(canonical(raw), COMMON + " " + extra, "PRODUCTIVE_METADATA_FIELDS")
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == scope and
            value["repository"] == I.REPOSITORY, "METADATA_SCOPE")
    same(value["source"], source, "METADATA_SOURCE")
    for name in ("selection", "runId", "runAttempt", "completedAt", "packet"):
        same(value[name], entry[name], "METADATA_ORIGINAL_BINDING")
    return value


def public_metadata(originals, entry, declaration, authority_created_at):
    """Bind exact owner bodies, not a search, generic assertion or fake approval."""
    require(type(originals) is dict and set(originals) == {"inventory", "compatibility", "review"}, "METADATA_ROSTER")
    bodies = {name: references.metadata_body(originals[name], entry[name],
        completed_at=entry["completedAt"], authority_created_at=authority_created_at) for name in originals}
    source = declaration["stage1"]["reviewed"]
    inventory = _metadata(bodies["inventory"], INVENTORY_SCOPE,
        "sourceRef members history productiveEvidence", entry, source)
    compatible = _metadata(bodies["compatibility"], COMPATIBILITY_SCOPE,
        "target inventoryBodySha256 inputs provider", entry, source)
    review = _metadata(bodies["review"], REVIEW_SCOPE,
        "target inventoryBodySha256 compatibilityBodySha256 decision inspection", entry, source)
    require(inventory["sourceRef"] == S.SOURCE_REF and review["decision"] == REVIEW_DECISION, "REVIEW_SCOPE")
    target = {"head": declaration["reviewed"], "merge": declaration["firstPullRequest"]["merge"]}
    for row in (compatible, review):
        same(row["target"], target, "REVIEW_TARGET")
        require(row["inventoryBodySha256"] == digest(bodies["inventory"]), "REVIEW_INVENTORY")
    require(review["compatibilityBodySha256"] == digest(bodies["compatibility"]), "REVIEW_COMPATIBILITY")
    # Original contents are mandatory. These declarations remain attested
    # inspection, not a substitute for the later real ZIP/native/service join.
    inspection = S.fields(review["inspection"], "finalPlaintextSha256 tailPlaintextSha256 privateRecordSha256 "
        "originals source nativeRetirement provider resolver custody timing", "INSPECTION_FIELDS")
    for name, value in inspection.items():
        if name.endswith("Sha256"):
            S.digest(value)
        else:
            require(value == "PASS_ORIGINAL_PRIVATE_INSPECTION", "INSPECTION_INCOMPLETE")
    ZIP.checked_members(inventory["members"])
    require(ZIP.zip_bytes(inventory["members"]) == entry["packet"]["bytes"], "INVENTORY_ZIP_BYTES")
    return inventory, compatible, review, tuple((name, bodies[name]) for name in originals)


def historical_originals(inventory, entry, declaration):
    """Preserved safe public originals. Never reconstruct original native owners."""
    value = S.fields(inventory["history"], " ".join(HISTORY_FIELDS), "HISTORICAL_ORIGINAL_FIELDS")
    raw = {name: original_bytes(value[name], I.POLICY_LIMIT if name == "candidatePolicy" else S.LIMIT,
                               empty=name == "basePolicyEntry") for name in HISTORY_FIELDS}
    history = S.BootstrapHistory(raw["comment"], raw["observation"], raw["basePolicyEntry"], raw["ancestry"],
        raw["candidatePolicyEntry"], raw["candidatePolicy"], entry["completedAt"], S.BootstrapMatch(raw["match"]))
    prior = declaration["stage1"]
    checked = S.match_bootstrap(comment_raw=history.comment_raw, comment_id=prior["commentId"],
        body_sha256=prior["bodySha256"], observation_raw=history.observation_raw,
        base_policy_entry=history.base_policy_entry, ancestry_raw=history.ancestry_raw,
        candidate_policy_entry=history.candidate_policy_entry, candidate_policy_raw=history.candidate_policy_raw,
        now=history.completed_at, expected=history.expected)
    result = I.parse(checked.record, S.LIMIT)
    same(result["reviewed"], prior["reviewed"], "HISTORY_H1")
    same(result["environment"], declaration["environment"], "HISTORY_ENVIRONMENT")
    for name in ("selection", "runId", "runAttempt"):
        same(result["github"][name], entry[name], "HISTORY_RUN")
    return history


def completed_job(attempt_raw, jobs_raw, entry, source):
    """Actual original attempt and complete job list, never Step self-success."""
    attempt, jobs = I.parse(attempt_raw, I.EVENT_LIMIT), I.parse(jobs_raw, I.EVENT_LIMIT)
    require(type(attempt.get("id")) is int and attempt["id"] == int(entry["runId"]) and
        type(attempt.get("run_attempt")) is int and attempt["run_attempt"] == int(entry["runAttempt"]) and
        attempt.get("head_sha") == source["commit"] and attempt.get("path") == S.bootstrap.WORKFLOW and
        attempt.get("head_branch") == S.SOURCE_REF.removeprefix("refs/heads/") and
        attempt.get("event") == "workflow_dispatch" and attempt.get("status") == "completed" and
        attempt.get("conclusion") == "success" and attempt.get("pull_requests") == [] and
        I.mapping(attempt.get("repository")).get("full_name") == I.REPOSITORY and
        I.mapping(attempt.get("head_repository")).get("full_name") == I.REPOSITORY, "H1_ATTEMPT")
    rows = jobs.get("jobs")
    require(type(rows) is list and 0 < len(rows) <= 100 and type(jobs.get("total_count")) is int and
        jobs["total_count"] == len(rows) and all(type(row) is dict for row in rows), "H1_JOBS_COMPLETE")
    ids = [S.positive(row.get("id")) for row in rows]
    require(len(set(ids)) == len(ids), "H1_JOB_DUPLICATE")
    productive = [row for row in rows if row.get("name") == S.bootstrap.JOB]
    require(len(productive) == 1, "H1_PRODUCTIVE_JOB")
    job = productive[0]
    _profile, role, _system, _arch = S.bootstrap.selection(entry["selection"])
    import hosted_cache_bootstrap_origin as origin
    require(type(job.get("run_id")) is int and job["run_id"] == int(entry["runId"]) and
        type(job.get("run_attempt")) is int and job["run_attempt"] == int(entry["runAttempt"]) and
        job.get("head_sha") == source["commit"] and job.get("head_branch") == attempt["head_branch"] and
        job.get("status") == "completed" and job.get("conclusion") == "success" and
        job.get("url") == references.API + "/actions/jobs/" + str(job["id"]) and
        job.get("run_url") == references.API + "/actions/runs/" + entry["runId"] and
        job.get("labels") == [origin.SERVICE_SELECTORS[role]] and
        type(job.get("runner_id")) is int and job["runner_id"] > 0 and
        type(job.get("runner_name")) is str and bool(job["runner_name"]) and
        type(job.get("runner_group_id")) is int and job["runner_group_id"] == 0 and
        job.get("runner_group_name") == "GitHub Actions", "H1_PRODUCTIVE_JOB")
    began, ended = S.joint.timestamp(job.get("started_at")), S.joint.timestamp(job.get("completed_at"))
    require(0 < began < ended == entry["completedAt"], "H1_COMPLETION")
    steps = job.get("steps")
    require(type(steps) is list and 0 < len(steps) <= 100 and all(type(step) is dict for step in steps), "H1_STEPS")
    numbers = [step.get("number") for step in steps]
    require(all(type(number) is int and number > 0 for number in numbers) and numbers == sorted(set(numbers)),
            "H1_STEP_NUMBERS")
    selected = []
    for name in STEP_NAMES:
        found = [step for step in steps if step.get("name") == name]
        require(len(found) == 1, "H1_STEP_MISSING_OR_DUPLICATE")
        step = found[0]
        require(step.get("status") == "completed" and step.get("conclusion") == "success", "H1_STEP_FAILED")
        start, finish = S.joint.timestamp(step.get("started_at")), S.joint.timestamp(step.get("completed_at"))
        require(began <= start <= finish <= ended and (not selected or selected[-1]["number"] < step["number"] and
            S.joint.timestamp(selected[-1]["completed_at"]) <= start), "H1_STEP_CHRONOLOGY")
        selected.append(step)
    # Preserve B->U->A explicitly; companion steps must not reinterpret that
    # old suffix check as merely A->capture->publication. Both chains matter.
    require(all(selected[index]["number"] + 1 == selected[index + 1]["number"] for index in (3, 4, 5, 6)),
        "H1_UPLOAD_ADJACENCY")
    return job


def read_stored_zip(reader, members, packet, check):
    """Consume the complete real reader, with exact maintained stored framing.

    The caller owns/pins/closes reader. This return is byte DATA, never proof
    of its native identity or successful close. No extraction or decryption.
    """
    captured = ZIP.checked_members(members)
    S.fields(packet, "artifactId bytes sha256", "ZIP_PACKET_FIELDS")
    S.positive(packet["artifactId"])
    require(type(packet["bytes"]) is int and packet["bytes"] == ZIP.zip_bytes(members), "ZIP_PACKET_SIZE")
    S.digest(packet["sha256"])
    require(callable(check) and callable(getattr(reader, "read", None)), "ZIP_OWNED_READER")
    total, whole, central, manifests = 0, hashlib.sha256(), [], {}

    def read(count):
        nonlocal total
        require(type(count) is int and 0 < count <= ZIP.CHUNK_BYTES, "ZIP_READ_BOUND")
        require(total + count <= packet["bytes"], "ZIP_OVERRUN")
        raw = bytearray()
        while len(raw) < count:
            check()
            part = reader.read(count - len(raw))
            check()
            require(type(part) is bytes and 0 < len(part) <= count - len(raw), "ZIP_TRUNCATED")
            total += len(part)
            whole.update(part)
            raw.extend(part)
        return bytes(raw)

    for index, (name, count, checksum) in enumerate(captured):
        filename, beginning = name.encode("ascii"), total
        expected = struct.pack("<IHHHHHIIIHH", 0x04034B50, 20, 8, 0, 0, 33, 0, 0, 0, len(filename), 0) + filename
        require(read(len(expected)) == expected, "ZIP_LOCAL_HEADER")
        content, crc, size = hashlib.sha256(), 0, 0
        manifest = bytearray()
        while size < count:
            part = read(min(ZIP.CHUNK_BYTES, count - size))
            size += len(part)
            content.update(part)
            crc = zlib.crc32(part, crc)
            if index in (1, 3):
                manifest.extend(part)
        require(content.hexdigest() == checksum, "ZIP_MEMBER_DIGEST")
        require(read(16) == struct.pack("<IIII", 0x08074B50, crc, size, size), "ZIP_DESCRIPTOR")
        central.append(struct.pack("<IHHHHHHIIIHHHHHII", 0x02014B50, 0x0314, 20, 8, 0, 0, 33,
            crc, size, size, len(filename), 0, 0, 0, 0, 0o100600 << 16, beginning) + filename)
        if index in (1, 3):
            manifests[name] = bytes(manifest)
    directory_start = total
    for record in central:
        require(read(len(record)) == record, "ZIP_CENTRAL_DIRECTORY")
    directory_bytes = total - directory_start
    require(read(22) == struct.pack("<IHHHHIIH", 0x06054B50, 0, 0, 4, 4, directory_bytes,
        directory_start, 0), "ZIP_END")
    check()
    require(reader.read(1) == b"", "ZIP_TRAILING_BYTES")
    check()
    require(total == packet["bytes"] and whole.hexdigest() == packet["sha256"], "WHOLE_ZIP_DIGEST")
    return manifests


def _path(value, profile, role):
    require(type(value) is str and 0 < len(value) <= 4096 and
        all(32 <= ord(char) < 127 and char not in "!*?[]{}()" for char in value), "PROVIDER_LITERAL_PATH")
    path = (PureWindowsPath if role == "windows-x64" else PurePosixPath)(value)
    require(path.is_absolute() and str(path) == value and ".." not in path.parts and
        all(part == part.strip() for part in path.parts) and
        path.parts[-5:] == ("p2pkit-dependency-seed-" + profile + "-" + role,
                           "restore-home", "caches", "modules-2", "files-2.1"), "PROVIDER_LITERAL_PATH")
    if role == "windows-x64":
        require(re.fullmatch(r"[A-Za-z]:", path.drive) and
            all(":" not in part and not part.endswith(".") for part in path.parts[1:]), "PROVIDER_LITERAL_PATH")
    else:
        require(path.anchor == "/" and "\\" not in value, "PROVIDER_LITERAL_PATH")
    return value


def checked_inputs(value):
    try:
        return source_compatibility.checked_inputs(value)
    except source_compatibility.CompatibilityError as error:
        raise I.AdmissionError("INITIAL_ORDINARY_QUALIFICATION_" + str(error)) from None


def compatibility(value, inventory, final, declaration, current_inputs):
    """H1 originals and H2 source compatibility, NOT H2 native restore success.

    A Linux gate cannot attest a future Windows worker's compression/native
    path. The exact H1 version/path/compressor is preserved for that worker's
    separate genuine native provider join. Matching key alone is not sufficient.
    """
    same(checked_inputs(value["inputs"]), checked_inputs(current_inputs), "SOURCE_INPUT_BYTES_CHANGED")
    same(final["source"], declaration["stage1"]["reviewed"], "COMPATIBILITY_H1_SOURCE")
    same(value["source"], final["source"], "COMPATIBILITY_METADATA_SOURCE")
    same(inventory["source"], final["source"], "COMPATIBILITY_INVENTORY_SOURCE")
    h1 = source_compatibility.envelope(final["source"], value["inputs"])
    require(source_compatibility.envelope_digest(h1) == S.digest(final["productive"]["compatibilityInputsSha256"]),
        "ORIGINAL_COMPATIBILITY_ENVELOPE")
    profile, role, _system, _arch = S.bootstrap.selection(inventory["selection"])
    provider = S.fields(value["provider"], "schema scope action key literalPath cacheVersion compression "
        "cacheEntry refs afterSaveSha256 probeSha256 nativeRecordSha256 resolverRecordSha256", "PROVIDER_FIELDS")
    require(type(provider["schema"]) is int and provider["schema"] == 1 and provider["scope"] ==
        "INITIAL_PRODUCTIVE_CACHE_COMPATIBILITY_V1", "PROVIDER_SCOPE")
    same(provider["action"], cache._provider(), "FIXED_PROVIDER_ACTION")
    inputs = current_inputs["seed"]
    require(provider["key"] == cache.cache_key(profile, role, inputs["allowlistSha256"],
        inputs["files"][seed.INPUTS[1]]), "PROVIDER_KEY")
    _path(provider["literalPath"], profile, role)
    S.digest(provider["cacheVersion"])
    require(type(provider["compression"]) is str and provider["compression"] in COMPRESSIONS, "PROVIDER_COMPRESSION")
    require(provider["cacheVersion"] == cache.provider_cache_version(provider["literalPath"],
        provider["compression"], role), "PROVIDER_CACHE_VERSION")
    same(provider["refs"], {"savedRef": S.SOURCE_REF, "headRef": S.SOURCE_REF, "baseRef": "refs/heads/main",
        "mergeRef": "refs/pull/" + str(declaration["firstPullRequest"]["number"]) + "/merge"},
        "PROVIDER_REF_VISIBILITY")
    entry = S.fields(provider["cacheEntry"], "id bytes createdAt", "CACHE_ENTRY_FIELDS")
    S.positive(entry["id"])
    require(type(entry["bytes"]) is int and 0 < entry["bytes"] <= seed.TOTAL_LIMIT and
        type(entry["createdAt"]) is int and 0 < entry["createdAt"] <= inventory["completedAt"], "CACHE_ENTRY")
    for name in ("afterSaveSha256", "probeSha256", "nativeRecordSha256", "resolverRecordSha256"):
        S.digest(provider[name])
    for name in ("afterSaveSha256", "probeSha256"):
        require(provider[name] == final["productive"][name], "ORIGINAL_PRODUCTIVE_PROVIDER")
    return provider


def cache_inventory_path(provider, page):
    require(type(provider) is dict and type(page) is int and 1 <= page <= references.PAGE_COUNT,
            "CACHE_PAGE_NUMBER")
    require(type(provider.get("key")) is str and re.fullmatch(r"p2pkit-dependency-files-v1-[a-z0-9-]{1,256}",
        provider["key"]), "CACHE_KEY_PATH")
    return API + "/actions/caches?" + urlencode({"key": provider["key"], "ref": S.SOURCE_REF,
        "per_page": 100, "page": page})


def cache_inventory(pages, provider):
    """Complete current cache metadata. Does not replace actual byte restore."""
    require(type(pages) is tuple and 1 <= len(pages) <= references.PAGE_COUNT, "CACHE_PAGES")
    rows, identifiers, total = [], set(), None
    for number, page in enumerate(pages, 1):
        require(type(page) is tuple and len(page) == 2 and type(page[0]) is str and type(page[1]) is bytes,
                "CACHE_PAGE_ORIGINAL")
        path, raw = page
        require(path == cache_inventory_path(provider, number), "CACHE_PAGE_PATH")
        value = S.fields(I.parse(raw, references.PAGE_LIMIT), "total_count actions_caches", "CACHE_PAGE_FIELDS")
        require(type(value["total_count"]) is int and 0 <= value["total_count"] <= references.PAGE_COUNT * 100,
                "CACHE_PAGE_TOTAL")
        if total is None:
            total = value["total_count"]
        require(total == value["total_count"] and type(value["actions_caches"]) is list and
            len(value["actions_caches"]) <= 100 and (number == len(pages) or len(value["actions_caches"]) == 100),
            "CACHE_PAGE_COMPLETE")
        for row in value["actions_caches"]:
            require(type(row) is dict, "CACHE_ROW")
            identifier = S.positive(row.get("id"))
            require(identifier not in identifiers, "DUPLICATE_CACHE_ENTRY")
            identifiers.add(identifier)
            rows.append(row)
    require(len(rows) == total and len(pages) == max(1, (total + 99) // 100), "CACHE_PAGES_INCOMPLETE")
    # compatibility() has derived this version from the original literal path,
    # selected attainable compressor and role. Check the COMPLETE service
    # tuple before its ID: a different-ID duplicate is not an exact cache hit.
    selected = [row for row in rows if row.get("key") == provider["key"] and
        row.get("ref") == provider["refs"]["savedRef"] and row.get("version") == provider["cacheVersion"]]
    require(len(selected) == 1, "ORIGINAL_CACHE_ABSENT_OR_AMBIGUOUS")
    row = selected[0]
    require(row["id"] == provider["cacheEntry"]["id"] and row.get("ref") == S.SOURCE_REF and row.get("key") == provider["key"] and
        row.get("version") == provider["cacheVersion"] and type(row.get("size_in_bytes")) is int and
        row["size_in_bytes"] == provider["cacheEntry"]["bytes"] and
        S.joint.timestamp(row.get("created_at")) == provider["cacheEntry"]["createdAt"], "ORIGINAL_CACHE_CHANGED")
    return row


def qualify(*, originals, entry, declaration, authority_created_at, attempt_raw, jobs_raw,
            job_raw, job_date, artifact_raw, inventory_pages, cache_pages, manifests, current_inputs, now):
    """Closed supplied-byte composition used only after the complete ZIP reader.

    No configurable/stub verifier exists. The separate productive delivery
    codec is a required maintained import; its absence refuses qualification.
    The native controller must own/recheck these originals, reader and return.
    """
    import hosted_initial_artifact_productive_delivery as productive
    inventory, compatible, review, bodies = public_metadata(originals, entry, declaration, authority_created_at)
    history = historical_originals(inventory, entry, declaration)
    selected = completed_job(attempt_raw, jobs_raw, entry, declaration["stage1"]["reviewed"])
    job = I.parse(job_raw, I.EVENT_LIMIT)
    for name in ("id", "run_id", "run_attempt", "head_sha", "head_branch", "name", "url", "run_url", "status",
                 "conclusion", "labels", "runner_id", "runner_name", "runner_group_id", "runner_group_name",
                 "started_at", "completed_at", "steps"):
        same(job.get(name), selected[name], "ORIGINAL_JOB_DETAIL_CHANGED")
    require(type(job_date) is int and entry["completedAt"] <= job_date <= now, "ORIGINAL_JOB_DATE")
    artifact = references.artifact_reference(artifact_raw, entry["packet"], run_id=entry["runId"],
        reviewed=declaration["stage1"]["reviewed"], now=now)
    require(artifact["name"] == "initial-recipient-productive-custody-" + entry["runId"] + "-" +
        entry["runAttempt"] + "-worker-" + entry["selection"], "PRODUCTIVE_ARTIFACT_NAME")
    rows = references.complete_inventory(inventory_pages, run_id=entry["runId"])
    matched = [row for row in rows if row["id"] == artifact["id"]]
    require(len(matched) == 1, "EXACT_ARTIFACT_NOT_IN_INVENTORY")
    same(matched[0], artifact, "ARTIFACT_CHANGED_DURING_ACQUISITION")
    require(type(manifests) is dict and set(manifests) == {"manifest.json", "custody-tail-manifest.json"},
            "PRODUCTIVE_MANIFESTS")
    evidence = S.fields(inventory["productiveEvidence"], "finalManifestSha256 tailManifestSha256 upload after",
                        "PRODUCTIVE_EVIDENCE_FIELDS")
    require(evidence["finalManifestSha256"] == digest(manifests["manifest.json"]) and
        evidence["tailManifestSha256"] == digest(manifests["custody-tail-manifest.json"]), "PRODUCTIVE_MANIFEST_HASHES")
    upload_raw, after_raw = (original_bytes(evidence[name], 2 * 1024 * 1024) for name in ("upload", "after"))
    final, tail, upload, after, actual_job = productive.qualification_inputs(manifests["manifest.json"],
        manifests["custody-tail-manifest.json"], inventory["members"], upload_raw, after_raw, job_raw, job_date)
    same(actual_job, job, "ORIGINAL_JOB_SUBSTITUTION")
    for returned in (upload, after):
        # The finite U/A transport has a canonical decimal STRING ID; GitHub's
        # artifact JSON and C2 packet reference use an INTEGER. Preserve both
        # closed schemas and compare the exact decimal, never lossy coercion.
        require(returned["artifact"]["id"] == str(entry["packet"]["artifactId"]), "ORIGINAL_UPLOAD_PACKET")
        same({"bytes": returned["artifact"]["zipBytes"], "sha256": returned["artifact"]["zipSha256"]},
            {name: entry["packet"][name] for name in ("bytes", "sha256")}, "ORIGINAL_UPLOAD_PACKET")
        require(returned["artifact"]["name"] == artifact["name"], "ORIGINAL_UPLOAD_NAME")
    for name, original_name in (("createdAt", "created_at"), ("expiresAt", "expires_at"), ("serviceDigest", "digest")):
        same(after["artifact"][name], artifact[original_name], "ORIGINAL_AFTER_ARTIFACT")
    require(final["selection"] == entry["selection"], "FINAL_SELECTION")
    same(final["source"], declaration["stage1"]["reviewed"], "FINAL_SOURCE")
    historical = I.parse(history.expected.record, S.LIMIT)
    for name, value in historical["github"].items():
        same(final["github"][name], value, "FINAL_GITHUB")
    require(final["github"]["repository"] == I.REPOSITORY, "FINAL_REPOSITORY")
    for name in ("authority", "environment", "originalBase", "reviewed", "firstUseAt", "notBefore", "expiresAt"):
        same(final["initialRecipient"][name], historical[name], "FINAL_ORIGINAL_HISTORY")
    require(final["initialRecipient"]["matchSha256"] == digest(history.expected.record), "FINAL_ORIGINAL_MATCH")
    policy, _key = I._policy(history.candidate_policy_raw, now)
    same(final["policy"], {**historical["policy"], "fingerprint": policy["recipient"]["fingerprint"],
        "keySha256": policy["recipient"]["sha256"], "expiresAt": policy["expiresAt"], "retentionDays": 14}, "FINAL_POLICY")
    require(final["recipient"]["fingerprint"] == policy["recipient"]["fingerprint"] and
        final["recipient"]["keySha256"] == policy["recipient"]["sha256"] and
        final["policy"]["retentionDays"] == 14, "FINAL_RECIPIENT")
    provider = compatibility(compatible, inventory, final, declaration, current_inputs)
    # qualification_inputs above has already validated the exact final30
    # groups, map names/ordinals and copy index through the maintained codecs.
    # Bind the owner's private inspection to those ACTUAL map/index originals;
    # these comparisons do not decrypt them or supply the owner's approval.
    require(provider["nativeRecordSha256"] == final["copy"]["groups"][24]["map"]["sha256"],
        "OWNER_ORIGINAL_PRODUCTIVE_MAP")
    require(provider["resolverRecordSha256"] == final["copy"]["groups"][26]["map"]["sha256"],
        "OWNER_ORIGINAL_CONFIGURATION_MAP")
    require(review["inspection"]["privateRecordSha256"] == final["copy"]["index"]["sha256"],
        "OWNER_ORIGINAL_PRIVATE_INDEX")
    same(final["productive"]["compatibilityInputsSha256"], tail["productive"]["compatibilityInputsSha256"],
        "ORIGINAL_FINAL_TAIL_COMPATIBILITY")
    cache_inventory(cache_pages, provider)
    record = I.encoded({"schema": 1, "scope": QUALIFIED_SCOPE, "source": inventory["source"],
        "target": compatible["target"], "selection": entry["selection"], "runId": entry["runId"],
        "runAttempt": entry["runAttempt"], "packet": entry["packet"], "members": inventory["members"],
        "completedAt": entry["completedAt"], "expiresAt": S.joint.timestamp(artifact["expires_at"]),
        "historySha256": digest(history.expected.record), "metadataSha256": {name: digest(raw) for name, raw in bodies},
        "finalManifestSha256": evidence["finalManifestSha256"], "tailManifestSha256": evidence["tailManifestSha256"],
        "uploadSha256": digest(upload_raw), "afterSha256": digest(after_raw), "jobSha256": digest(job_raw),
        "inputs": current_inputs, "provider": provider, "reviewDecision": review["decision"],
        "qualification": "OWNER_REVIEWED_H1_ORIGINALS_WITH_H2_SOURCE_COMPATIBILITY",
        "nativeAuthority": "NOT_ESTABLISHED_BY_SUPPLIED_DATA", "ordinaryAcceptance": "NOT_PERFORMED",
        "h2ProviderAcceptance": "NOT_PERFORMED", "cryptoAcceptance": "NOT_PERFORMED"})
    return ProductiveQualification(record, history)


PUBLIC_RECEIPT_ZIP_LIMIT = 64 * 1024


def public_receipt_artifact(artifact_raw, inventory_pages, entry, source, now):
    """Exact authenticated-original DATA join. No download/owner authority."""
    S.fields(entry, "runId runAttempt selection completedAt packet", "PUBLIC_RECEIPT_ENTRY")
    for name in ("runId", "runAttempt"):
        require(type(entry[name]) is str and I.ID.fullmatch(entry[name]), "PUBLIC_RECEIPT_RUN")
    S.bootstrap.selection(entry["selection"])
    require(type(entry["completedAt"]) is int and 0 < entry["completedAt"] <= now, "PUBLIC_RECEIPT_COMPLETION")
    S.fields(entry["packet"], "artifactId bytes sha256", "PUBLIC_RECEIPT_PRIMARY_PACKET")
    S.positive(entry["packet"]["artifactId"])
    S._reference({key: entry["packet"][key] for key in ("bytes", "sha256")}, maximum=references.PACKET_LIMIT)
    value = I.parse(artifact_raw, references.PAGE_LIMIT)
    require(type(value) is dict and type(value.get("size_in_bytes")) is int and
        0 < value["size_in_bytes"] <= PUBLIC_RECEIPT_ZIP_LIMIT and type(value.get("digest")) is str and
        re.fullmatch(r"sha256:[0-9a-f]{64}", value["digest"]), "PUBLIC_RECEIPT_PACKET_BOUND")
    packet = {"artifactId": S.positive(value.get("id")), "bytes": value["size_in_bytes"],
        "sha256": value["digest"].removeprefix("sha256:")}
    artifact = references.artifact_reference(artifact_raw, packet, run_id=entry["runId"], reviewed=source, now=now)
    name = "initial-recipient-productive-receipts-" + entry["runId"] + "-" + entry["runAttempt"] + "-worker-" + entry["selection"]
    require(artifact["name"] == name and packet["artifactId"] != entry["packet"]["artifactId"] and
        S.joint.timestamp(artifact["created_at"]) <= entry["completedAt"], "PUBLIC_RECEIPT_NAME_OR_ATTEMPT")
    rows = references.complete_inventory(inventory_pages, run_id=entry["runId"])
    selected = [row for row in rows if row.get("name") == name]
    require(len(selected) == 1, "PUBLIC_RECEIPT_INVENTORY_AMBIGUOUS")
    same(selected[0], artifact, "PUBLIC_RECEIPT_INVENTORY_CHANGED")
    primary = [row for row in rows if row.get("id") == entry["packet"]["artifactId"]]
    require(len(primary) == 1, "PUBLIC_RECEIPT_PRIMARY_MISSING")
    references.artifact_reference(I.encoded(primary[0]), entry["packet"], run_id=entry["runId"], reviewed=source, now=now)
    require(primary[0].get("name") == "initial-recipient-productive-custody-" + entry["runId"] + "-" +
        entry["runAttempt"] + "-worker-" + entry["selection"], "PUBLIC_RECEIPT_PRIMARY_NAME")
    return artifact, packet


def read_public_receipt_zip(reader, packet, check):
    """Read exactly one small ordinary ZIP; never extract or parse primary ZIP.

    Local/central records, descriptors, CRCs, inventory and complete archive
    digest are checked. The caller must own/check/close the actual reader. This
    supplied-byte result is not proof of acquisition or native retirement.
    """
    import hosted_initial_artifact_productive_delivery as D
    S.fields(packet, "artifactId bytes sha256", "PUBLIC_RECEIPT_ZIP_PACKET")
    S.positive(packet["artifactId"]); S.digest(packet["sha256"])
    require(type(packet["bytes"]) is int and 22 < packet["bytes"] <= PUBLIC_RECEIPT_ZIP_LIMIT and
        callable(check) and callable(getattr(reader, "read", None)), "PUBLIC_RECEIPT_ZIP_BOUND")
    raw = bytearray()
    while len(raw) < packet["bytes"]:
        check()
        part = reader.read(min(16384, packet["bytes"] - len(raw)))
        check()
        require(type(part) is bytes and 0 < len(part) <= min(16384, packet["bytes"] - len(raw)),
            "PUBLIC_RECEIPT_ZIP_TRUNCATED")
        raw.extend(part)
    check()
    require(reader.read(1) == b"", "PUBLIC_RECEIPT_ZIP_TRAILING")
    check()
    require(digest(bytes(raw)) == packet["sha256"], "PUBLIC_RECEIPT_ZIP_DIGEST")
    signature, disk, central_disk, count_disk, count, central_bytes, central_at, comment = struct.unpack_from(
        "<IHHHHIIH", raw, len(raw) - 22)
    require(signature == 0x06054B50 and disk == central_disk == comment == 0 and count_disk == count == 3 and
        central_at + central_bytes == len(raw) - 22, "PUBLIC_RECEIPT_ZIP_END")
    cursor, entries = central_at, []
    for _index in range(3):
        require(cursor + 46 <= len(raw) - 22, "PUBLIC_RECEIPT_ZIP_CENTRAL_BOUND")
        row = struct.unpack_from("<IHHHHHHIIIHHHHHII", raw, cursor)
        (magic, made, needed, flags, method, modtime, moddate, crc, compressed, expanded,
            namesize, extra, note, start_disk, internal, external, offset) = row
        require(magic == 0x02014B50 and needed <= 20 and flags in (0, 8, 2048, 2056) and method in (0, 8) and
            0 < expanded <= D.LIMIT and 0 < compressed <= PUBLIC_RECEIPT_ZIP_LIMIT and start_disk == note == 0 and
            extra <= 1024 and 0 < namesize <= 64 and cursor + 46 + namesize + extra <= len(raw) - 22 and
            (external >> 16) & 0o170000 in (0, 0o100000) and external & 0x10 == 0,
            "PUBLIC_RECEIPT_ZIP_CENTRAL")
        name = bytes(raw[cursor + 46:cursor + 46 + namesize])
        require(name in tuple(member.encode("ascii") for member in D.PUBLIC_RECEIPT_MEMBERS),
            "PUBLIC_RECEIPT_ZIP_MEMBER")
        entries.append((offset, name, flags, method, modtime, moddate, crc, compressed, expanded))
        cursor += 46 + namesize + extra
    require(cursor == len(raw) - 22 and len({entry[1] for entry in entries}) == 3 and
        len({entry[0] for entry in entries}) == 3, "PUBLIC_RECEIPT_ZIP_INVENTORY")
    entries.sort()
    require(entries[0][0] == 0, "PUBLIC_RECEIPT_ZIP_PREFIX")
    members = {}
    for index, (offset, name, flags, method, modtime, moddate, crc, compressed, expanded) in enumerate(entries):
        check()
        end = entries[index + 1][0] if index < 2 else central_at
        require(offset + 30 <= end <= central_at, "PUBLIC_RECEIPT_ZIP_LOCAL_BOUND")
        local = struct.unpack_from("<IHHHHHIIIHH", raw, offset)
        magic, needed, local_flags, local_method, local_time, local_date, local_crc, local_compressed, local_expanded, namesize, extra = local
        require(magic == 0x04034B50 and needed <= 20 and (local_flags, local_method, local_time, local_date) ==
            (flags, method, modtime, moddate) and namesize == len(name) and extra <= 1024 and
            bytes(raw[offset + 30:offset + 30 + namesize]) == name,
            "PUBLIC_RECEIPT_ZIP_LOCAL_IDENTITY")
        begin = offset + 30 + namesize + extra
        require(begin + compressed <= end, "PUBLIC_RECEIPT_ZIP_PAYLOAD_BOUND")
        if flags & 8:
            require((local_crc, local_compressed, local_expanded) in ((0, 0, 0), (crc, compressed, expanded)),
                "PUBLIC_RECEIPT_ZIP_LOCAL_DESCRIPTOR")
            descriptor = bytes(raw[begin + compressed:end])
            require(descriptor in (struct.pack("<III", crc, compressed, expanded),
                struct.pack("<IIII", 0x08074B50, crc, compressed, expanded)), "PUBLIC_RECEIPT_ZIP_DESCRIPTOR")
        else:
            require((local_crc, local_compressed, local_expanded) == (crc, compressed, expanded) and
                begin + compressed == end, "PUBLIC_RECEIPT_ZIP_LOCAL_SIZES")
        payload = bytes(raw[begin:begin + compressed])
        if method == 8:
            try:
                inflater = zlib.decompressobj(-15)
                payload = inflater.decompress(payload, expanded + 1)
                require(inflater.eof and not inflater.unused_data and not inflater.unconsumed_tail,
                    "PUBLIC_RECEIPT_ZIP_DEFLATE_BOUND")
            except zlib.error:
                require(False, "PUBLIC_RECEIPT_ZIP_DEFLATE")
        require(len(payload) == expanded and zlib.crc32(payload) & 0xffffffff == crc, "PUBLIC_RECEIPT_ZIP_CRC_OR_SIZE")
        members[name.decode("ascii")] = payload
        check()
    D.public_receipt_manifest_inputs(members[D.PUBLIC_RECEIPT_FILE], members[D.UPLOAD_FILE], members[D.AFTER_FILE])
    return members
