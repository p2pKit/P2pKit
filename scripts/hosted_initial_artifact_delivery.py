"""Closed terminal delivery DATA, never native, HTTP, Step or Release authority.

The fixed U/A controller owns the actual K readers, current clock/boot, original
child/pipe returns and public GitHub observations. These predicates only bind
their supplied bytes. They cannot restore B/K owners, Recipient objects, source
queries or a retired lease. No file, network, process, clock or key operation is
performed by this module.
"""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
import re

import hosted_initial_artifact_zip as Z
import hosted_initial_recipient_tail_handoff as H
import hosted_initial_recipient_tail_carrier as R


T, B, E = H.T, H.B, H.T.original
I, S, O = T.I, T.S, E.acquisition.origin
NS = B.clocks.NS
LIMIT = 16 * 1024
READY_SCOPE = "INITIAL_ARTIFACT_NATIVE_READY_PENDING_SERVICE_AND_STREAM_V1"
FINAL_SCOPE = "INITIAL_ARTIFACT_NATIVE_STREAM_CLOSED_FILES_PENDING_PROCESS_V1"
UPLOAD_SCOPE = "INITIAL_ARTIFACT_UPLOAD_PENDING_ORIGINAL_STEP_RETURN_V1"
AFTER_SCOPE = "INITIAL_ARTIFACT_DELIVERY_PENDING_ORIGINAL_STEP_RETURN_V1"
UPLOAD_FILE = "upload-pending.json"
AFTER_FILE = "delivery-pending.json"
UPLOAD_HASH_ENV = "P2PKIT_INITIAL_UPLOAD_SHA256"
UPLOAD_OUTCOME_ENV = "P2PKIT_INITIAL_UPLOAD_OUTCOME"
STEPS = (*B.STEP_NAMES, ("upload", "P2pKit initial custody upload"),
    ("after", "P2pKit initial after-upload custody"))
INPUT_LIMITS = {H.FILE: H.LIMIT, H.PRIVATE_CARRIER_CLOSE: R.LIMIT, "context.json": H.LIMIT,
    "event.json": I.EVENT_LIMIT, "candidate-policy.json": I.POLICY_LIMIT,
    "original-match.json": S.LIMIT, "before-match.json": S.LIMIT}
CONTEXT_FIELDS = {"schema", "scope", "kind", "root", "session", "job", "observed", "originalWindow", "deadline",
    "caps", "parentFirstNs", "parentFirstLocal", "beforeClosedNs", "originalServiceJob", "predecessors",
    "filesSha256", "directories", "inheritedContext", "budgetAcceptance", "exportSaveAuthority"}
HTTP_LIMIT = 1024 * 1024


class DeliveryError(ValueError):
    """Source-owned finite refusal only; never a private input transcript."""


def require(value, code):
    if not value:
        raise DeliveryError("INITIAL_ARTIFACT_DELIVERY_" + code)


def fields(value, names):
    require(type(value) is dict and all(type(name) is str for name in value) and set(value) == set(names), "FIELDS")


def integer(value, low=0, high=B.clocks.UINT64):
    require(type(value) is int and low <= value <= high, "INTEGER")
    return value


def digest(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "DIGEST")
    return value


def sha(raw):
    require(type(raw) is bytes, "ORIGINAL_BYTES")
    return hashlib.sha256(raw).hexdigest()


def canonical(raw, maximum=LIMIT):
    require(type(raw) is bytes and 0 < len(raw) <= maximum, "RECORD_BOUND")
    value = I.parse(raw, maximum)
    require(O.encoded(value) == raw, "CANONICAL")
    return value


def encoded(value, maximum=LIMIT):
    raw = O.encoded(value)
    require(0 < len(raw) <= maximum, "RECORD_BOUND")
    return raw


def upload_caps(seed, first):
    """Original RAW arithmetic only. Calling this does not observe FIRST."""
    _hash, seal, _clock, _boot = B.continuity.seal_deadline_data(seed)
    integer(first)
    close = min(integer(first + 60 * NS), integer(seal + 60 * NS))
    work = close - 5 * NS
    # Retain the already-reviewed transport's strict feasible interval. An
    # early invocation with no such interval refuses; it does not wait/rebase.
    require(first < seal < work < close, "UPLOAD_ORIGINAL_INTERVAL")
    return seal, work, close


def after_caps(seed, first):
    _hash, seal, _clock, _boot = B.continuity.seal_deadline_data(seed)
    integer(first)
    upload, after = integer(seal + 60 * NS), integer(seal + 75 * NS)
    require(first < upload, "AFTER_FIRST_EXPIRED")
    end = min(integer(first + 15 * NS), after)
    require(first < end, "AFTER_ORIGINAL_INTERVAL")
    return upload, end


def _match(raw, *, kind, source, observed, policy_raw, policy, now):
    require(type(raw) is bytes and 0 < len(raw) <= S.LIMIT, "MATCH_BYTES")
    value = I.parse(raw, S.LIMIT)
    require(I.encoded(value) == raw, "MATCH_CANONICAL")
    E._graph(value)
    fields(value, E.COMMON_MATCH | ({"stage", "selector", "workerAdmission", "qualificationAcceptance"}
        if kind == "gate" else set()))
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] ==
        ("NONPRODUCTIVE_ELIGIBILITY" if kind == "gate" else S.STAGE1 + "_MATCH_ONLY_NOT_ADMISSION") and
        value["originalBase"] == S.BASE and value["source"] == value["reviewed"] == source and
        source["commit"] != S.BASE["commit"] and source["tree"] != S.BASE["tree"], "MATCH_SOURCE_SCOPE")
    start, first, end = (integer(value[name], 1, 253402300799) for name in ("notBefore", "firstUseAt", "expiresAt"))
    require(policy["notBefore"] <= start <= first <= now < end <= policy["expiresAt"] and
        end - start <= 14 * 86400, "MATCH_CURRENT_WINDOW")
    blob = hashlib.sha1(b"blob " + str(len(policy_raw)).encode("ascii") + b"\0" + policy_raw).hexdigest()
    require(value["policy"] == {"origin": "reviewed-head", "commit": source["commit"], "blob": blob,
        "path": I.POLICY_PATH, "sha256": S.POLICY_SHA256}, "MATCH_POLICY_ORIGIN")
    author = value["authority"]
    fields(author, {"id", "url", "bodySha256", "owner", "ownerId", "createdAt"})
    integer(author["id"], 1, 10 ** 20 - 1)
    digest(author["bodySha256"])
    require(author["owner"] == S.joint.OWNER_LOGIN and type(author["ownerId"]) is int and
        author["ownerId"] == S.joint.OWNER_ID and author["url"] ==
        "https://github.com/" + I.REPOSITORY + "/issues/437#issuecomment-" + str(author["id"]) and
        0 < S.joint.timestamp(author["createdAt"]) <= first, "MATCH_PERSONAL_AUTHORITY")
    S.environment(value["environment"])
    github = dict(observed["github"])
    if kind == "worker":
        github.update(profile=S.bootstrap.PROFILE, selection=observed["inputs"]["selection"])
    require(value["github"] == github, "MATCH_JOB")
    if kind == "gate":
        require(value["stage"] == "stage1" and value["workerAdmission"] == "NOT_PERFORMED" and
            value["qualificationAcceptance"] == "NOT_ESTABLISHED_BY_GATE", "NONPRODUCTIVE_GATE")
        expected = {"schema": 1, "scope": "INITIAL_RECIPIENT_SELECTED_APPROVAL_ONLY", "stage": "stage1",
            "runId": github["runId"], "runAttempt": github["runAttempt"], "commentId": author["id"],
            "bodySha256": author["bodySha256"], "environmentId": value["environment"]["id"],
            "environmentName": S.ENVIRONMENT, "approvalLine": "AUTHORIZE_INITIAL_RECIPIENT stage1 " +
            github["runId"] + "/" + github["runAttempt"] + " " + str(author["id"]) + " " + author["bodySha256"],
            "owner": {"login": S.joint.OWNER_LOGIN, "id": S.joint.OWNER_ID}}
        require(E._graph(value["selector"])[1] == E._graph(expected)[1], "MATCH_GATE_SELECTOR")
    return value


def retained_inputs(raws, *, environment, kind, seed, before_sha256, now):
    """Exact K postimages as historical DATA; actual readers/BEFORE are external.

    In particular, context and hashes are not fresh Git/source observations.
    The fixed workflow and subsequent original public job bind that boundary.
    """
    fields(raws, INPUT_LIMITS)
    require(type(environment) is dict and kind in ("gate", "worker"), "CONTEXT")
    integer(now, 1, 253402300799)
    for name, maximum in INPUT_LIMITS.items():
        require(type(raws[name]) is bytes and 0 < len(raws[name]) <= maximum, "INPUT_BOUND")
    digest(before_sha256)
    require(sha(raws[H.FILE]) == before_sha256, "ORIGINAL_BEFORE_HASH")
    pending, carrier = H.parse_pending(raws[H.FILE]), R.parse_close(raws[H.PRIVATE_CARRIER_CLOSE])
    require(pending["kind"] == carrier["kind"] == kind and pending["deadline"] == carrier["deadline"] == seed and
        pending["knownCloses"]["carrierCloseSha256"] == sha(raws[H.PRIVATE_CARRIER_CLOSE]), "CARRIER_HASH_KIND_SEED")
    for name in ("selection", "source", "github", "originalWindow", "predecessors", "manifests", "cutMapSha256",
            "totalBytes", "zipBytes"):
        require(E._graph(pending[name])[1] == E._graph(carrier[name])[1], "CARRIER_ORIGINAL_BINDING")
    require(pending["members"] == [{name: row[name] for name in ("name", "bytes", "sha256")}
        for row in carrier["files"]] and all(pending["times"][name] == carrier["times"][name]
        for name in H.TIME_FIELDS[:-1]), "CARRIER_MEMBERS_OR_TIMES")
    require(Z.zip_bytes(pending["members"]) == pending["zipBytes"], "EXACT_COMPLETE_ZIP")
    context = canonical(raws["context.json"], H.LIMIT)
    fields(context, CONTEXT_FIELDS)
    require(sha(raws["context.json"]) == carrier["nativeClose"]["contextSha256"] and
        context.get("schema") == 1 and type(context["schema"]) is int and
        context.get("scope") == "INITIAL_RECIPIENT_K_TAIL_CHILD_CONTEXT_V1" and
        context.get("kind") == kind and context.get("originalWindow") == pending["originalWindow"] and
        context.get("deadline") == seed and context.get("predecessors") == pending["predecessors"] and
        context["budgetAcceptance"] == "NOT_ADMITTED" and context["exportSaveAuthority"] is False, "K_CONTEXT")
    policy_raw = raws["candidate-policy.json"]
    policy, _public = I._policy(policy_raw, now)
    require(sha(policy_raw) == S.POLICY_SHA256 == pending["originals"]["policySha256"] and
        policy["retrievalOwner"] == S.joint.OWNER_LOGIN and sha(raws["event.json"]) ==
        pending["originals"]["eventSha256"] and sha(raws["original-match.json"]) ==
        pending["originals"]["matchSha256"], "ORIGINAL_POLICY_EVENT_MATCH")
    # No refreshed firstUseAt: B's original exact-match contract retained the
    # same source/owner/window, rather than issuing a new lease for delivery.
    require(raws["before-match.json"] == raws["original-match.json"], "BEFORE_MATCH_SUBSTITUTION")
    original = I.parse(raws["original-match.json"], S.LIMIT)
    observed = E.acquisition._context(environment, raws["event.json"], kind, original.get("firstUseAt"))
    require(observed == context.get("observed") and observed["source"] == pending["source"] and
        observed["inputs"]["selection"] == pending["selection"] and observed["role"] == pending["github"]["role"] and
        all(observed["github"][name] == pending["github"][name] for name in ("runId", "runAttempt", "job")),
        "ACTUAL_CONTEXT_ORIGINAL_LINK")
    match = _match(raws["original-match.json"], kind=kind, source=pending["source"], observed=observed,
        policy_raw=policy_raw, policy=policy, now=now)
    declared = context.get("filesSha256")
    require(type(declared) is dict and all(declared.get(name) == sha(raws[name]) for name in
        ("event.json", "candidate-policy.json", "original-match.json", "before-match.json")), "K_INPUT_LINKS")
    return pending, carrier, context, observed, policy, match


def manifests(pending, p0_raw, tail_raw, *, policy, match):
    """Read declarations completely; this is neither GPG nor encrypted-byte proof."""
    require(sha(p0_raw) == pending["manifests"]["p0Sha256"] and
        sha(tail_raw) == pending["manifests"]["tailSha256"], "MANIFEST_HASHES")
    p0 = T._p0(p0_raw)
    require((p0["kind"], p0["selection"], p0["source"]) ==
        (pending["kind"], pending["selection"], pending["source"]), "P0_SOURCE")
    github = dict(match["github"])
    github.update(repository=I.REPOSITORY, eventSha256=pending["originals"]["eventSha256"])
    recipient = policy["recipient"]
    require(p0["github"] == github and p0["policy"] == {**match["policy"], "fingerprint": recipient["fingerprint"],
        "keySha256": recipient["sha256"], "expiresAt": policy["expiresAt"], "retentionDays": 14}, "P0_JOB_POLICY")
    expected = {"authority": match["authority"], "environment": match["environment"],
        "originalBase": match["originalBase"], "reviewed": match["reviewed"], "firstUseAt": match["firstUseAt"],
        "notBefore": match["notBefore"], "expiresAt": match["expiresAt"],
        "matchSha256": pending["originals"]["matchSha256"],
        "freshReturnSha256": p0["initialRecipient"].get("freshReturnSha256")}
    digest(expected["freshReturnSha256"])
    require(p0["initialRecipient"] == expected, "P0_ORIGINAL_AUTHORITY")
    fields(p0["recipient"], {"fingerprint", "encryptionFingerprint", "keySha256", "expiresAt"})
    require(p0["recipient"]["fingerprint"] == recipient["fingerprint"] and
        p0["recipient"]["keySha256"] == recipient["sha256"] and
        type(p0["recipient"]["encryptionFingerprint"]) is str and
        re.fullmatch(r"[0-9A-F]{40}", p0["recipient"]["encryptionFingerprint"]), "P0_RECIPIENT")
    integer(p0["recipient"]["expiresAt"], policy["expiresAt"], 253402300799)
    tail = canonical(tail_raw, T.MANIFEST_LIMIT)
    artifact = T._artifact(tail.get("artifact"))
    cut = tail.get("cut")
    fields(cut, T.CUT_FIELDS | {"mapName"})
    require(cut["mapName"] == T.MAP_NAME and cut["mapSha256"] == pending["cutMapSha256"], "TAIL_MAP")
    current = {name: value for name, value in p0.items() if name != "artifact"}
    expected_tail = T._manifest(p0, p0_raw, current, pending["github"]["jobId"], pending["predecessors"],
        {name: cut[name] for name in T.CUT_FIELDS})
    expected_tail["artifact"] = artifact
    require(E._graph(tail)[1] == E._graph(expected_tail)[1], "TAIL_COMPLETE_DECLARATION")
    expected_members = [
        {"name": Z.MEMBERS[0], "bytes": p0["artifact"]["size"], "sha256": p0["artifact"]["sha256"]},
        {"name": Z.MEMBERS[1], "bytes": len(p0_raw), "sha256": sha(p0_raw)},
        {"name": Z.MEMBERS[2], "bytes": artifact["size"], "sha256": artifact["sha256"]},
        {"name": Z.MEMBERS[3], "bytes": len(tail_raw), "sha256": sha(tail_raw)},
    ]
    require(pending["members"] == expected_members and Z.zip_bytes(expected_members) == pending["zipBytes"],
        "MANIFEST_MEMBER_ROSTER")
    return p0, tail


def ready(pending, context, *, policy, match, first_raw, before_sha256, carrier_sha256, now):
    start, work, close = upload_caps(pending["deadline"], first_raw)
    require(start == pending["originalWindow"]["sealEndNs"] and
        close <= pending["originalWindow"]["uploadEndNs"], "READY_ORIGINAL_WINDOW")
    digest(before_sha256)
    digest(carrier_sha256)
    integer(now, 1, 253402300799)
    require(type(policy) is dict and type(match) is dict, "READY_ORIGINAL_VALIDITY")
    bounds = {"policyNotBefore": integer(policy.get("notBefore"), 1, 253402300799),
        "policyExpiresAt": integer(policy.get("expiresAt"), 1, 253402300799),
        "authorityNotBefore": integer(match.get("notBefore"), 1, 253402300799),
        "authorityExpiresAt": integer(match.get("expiresAt"), 1, 253402300799)}
    require(bounds["policyNotBefore"] <= bounds["authorityNotBefore"] <= now <
        bounds["authorityExpiresAt"] <= bounds["policyExpiresAt"], "READY_ORIGINAL_VALIDITY")
    # jobOriginal is PRIVATE pipe DATA for exact job/runner comparison. It must
    # not be copied into the public receipt or a workflow summary/log.
    value = {"schema": 1, "scope": READY_SCOPE, "kind": pending["kind"], "selection": pending["selection"],
        "source": E._copy(pending["source"]), "github": E._copy(pending["github"]),
        "beforeSha256": before_sha256, "carrierCloseSha256": carrier_sha256,
        "firstRawNs": str(first_raw), "deadline": E._copy(pending["deadline"]),
        "originalWindow": E._copy(pending["originalWindow"]), "workEndNs": str(work), "closeEndNs": str(close),
        "members": E._copy(pending["members"]), "zipBytes": pending["zipBytes"],
        "originals": E._copy(pending["originals"]), "jobOriginal": E._copy(context["originalServiceJob"]),
        **bounds, "observedAt": now, "nativeFileRetirement": "PENDING_ORIGINAL_READERS",
        "originalStepOutcome": "NOT_OBSERVED", "qualification": "NOT_ESTABLISHED"}
    E._graph(value)
    return encoded(value)


def stream_final(*, before_sha256, ready_raw, zip_result, close_raw, closed_ns):
    original = canonical(ready_raw)
    require(original.get("scope") == READY_SCOPE and original.get("beforeSha256") == before_sha256,
        "FINAL_READY_LINK")
    require(type(zip_result) is dict and zip_result.get("scope") == Z.SCOPE and
        zip_result.get("zipBytes") == original["zipBytes"] and
        [{name: row[name] for name in ("name", "bytes", "sha256")} for row in zip_result.get("members", [])] ==
        original["members"], "FINAL_ZIP_OBSERVATION")
    digest(zip_result["zipSha256"])
    integer(closed_ns, int(original["firstRawNs"]), int(original["workEndNs"]) - 1)
    require(type(close_raw) is bytes and 0 < len(close_raw) <= H.LIMIT, "FINAL_CLOSE_BYTES")
    return encoded({"schema": 1, "scope": FINAL_SCOPE, "beforeSha256": before_sha256,
        "readySha256": sha(ready_raw), "zipBytes": zip_result["zipBytes"], "zipSha256": zip_result["zipSha256"],
        "nativeCloseSha256": sha(close_raw), "closedNs": str(closed_ns), "nativeFileRetirement": "KNOWN_NATIVE_CLOSE",
        "originalReaderOutcome": "PENDING_ENCLOSING_PROCESS_CLOSE", "qualification": "NOT_ESTABLISHED"})


def public_headers(vector):
    """An original Node raw-header VECTOR, not reconstructed HTTP wire bytes."""
    require(type(vector) is list and 0 < len(vector) <= 128 and len(vector) % 2 == 0, "HEADER_VECTOR")
    result, size = {}, 0
    for name, value in zip(vector[::2], vector[1::2]):
        require(type(name) is str and re.fullmatch(r"[!#$%&'*+.^_`|~0-9A-Za-z-]+", name) and
            type(value) is str and re.fullmatch(r"[\t\x20-\x7e]*", value) and
            len(name) + len(value) + 2 <= 2048 and name.lower() not in result, "HEADER_FIELDS")
        result[name.lower()] = value.strip()
        size += len(name) + len(value) + 4
    require(size <= 16 * 1024, "HEADER_BOUND")
    date = E.acquisition.origin.public_provider.freshness(result)
    vector_hash = sha(json.dumps(vector, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))
    return result, date, vector_hash


def service_steps(job, date, stage):
    """Complete real service Step DATA; U and A have distinct current frontiers.

    The existing B grammar remains unchanged. This terminal grammar retains
    its complete-row/number/name/timestamp rules but requires B (and then U)
    to be successfully completed, not incorrectly still in progress.
    """
    require(stage in ("upload", "after") and type(job) is dict, "STEP_STAGE")
    integer(date, 1, 253402300799)
    began = B.wire.utc_epoch(job.get("started_at"))
    rows, previous, names, selected = job.get("steps"), 0, set(), {}
    require(began <= date and type(rows) is list and 0 < len(rows) <= 256, "STEP_COMPLETE_ARRAY")
    required = STEPS[:5] if stage == "upload" else STEPS
    for row in rows:
        fields(row, B.STEP_FIELDS)
        name, number, status, conclusion = (row[key] for key in ("name", "number", "status", "conclusion"))
        require(type(name) is str and 0 < len(name) <= 256 and name not in names and
            not any(ord(char) < 32 or ord(char) == 127 for char in name) and type(status) is str and
            status in ("queued", "in_progress", "completed"), "STEP_NAME_OR_STATUS")
        previous = integer(number, previous + 1, 2147483647)
        names.add(name)
        start, end = row["started_at"], row["completed_at"]
        if status == "queued":
            require(conclusion is None and start is None and end is None, "STEP_QUEUED")
        elif status == "in_progress":
            require(conclusion is None and end is None and began <= B.wire.utc_epoch(start) <= date, "STEP_RUNNING")
        else:
            require(type(conclusion) is str and conclusion in B.CONCLUSIONS, "STEP_CONCLUSION")
            if start is None or end is None:
                require(conclusion == "skipped" and start is None and end is None, "STEP_MISSING_TIMES")
            else:
                require(began <= B.wire.utc_epoch(start) <= B.wire.utc_epoch(end) <= date, "STEP_TIMES")
        for role, expected in required:
            if name == expected:
                require(role not in selected, "STEP_AMBIGUOUS")
                selected[role] = E._copy(row)
    require(set(selected) == {role for role, _name in required}, "STEP_MISSING")
    ordered = [selected[role] for role, _name in required]
    require(all(row["status"] == "completed" and row["conclusion"] == "success" and
        type(row["started_at"]) is str and type(row["completed_at"]) is str for row in ordered[:-1]) and
        ordered[-1]["status"] == "in_progress", "STEP_REQUIRED_SUCCESS_OR_CURRENT")
    require([row["number"] for row in ordered] == sorted(row["number"] for row in ordered) and
        all(B.wire.utc_epoch(left["completed_at"]) <= B.wire.utc_epoch(right["started_at"])
            for left, right in zip(ordered, ordered[1:])), "STEP_ORDER")
    # B's last current-source check must flow directly into U; no arbitrary
    # completed writer may be inserted between the reviewed terminal Steps.
    require(selected["upload"]["number"] == selected["before"]["number"] + 1 and
        (stage == "upload" or selected["after"]["number"] == selected["upload"]["number"] + 1),
        "STEP_TERMINAL_ADJACENCY")
    current = ordered[-1]["number"]
    require(all(row["status"] == ("completed" if row["number"] < current else "queued")
        for row in rows if row["number"] != current), "STEP_UNIQUE_CURRENT_FRONTIER")
    return selected


def service_job(pending, context, raw, headers, *, stage, now):
    """Bind supplied exact-job originals, not a new source/recipient acquisition."""
    require(type(raw) is bytes and 0 < len(raw) <= HTTP_LIMIT, "JOB_BODY_BOUND")
    values, date, header_hash = public_headers(headers)
    integer(now, 1, 253402300799)
    require(date <= now <= date + B.wire.CACHE_SECONDS, "JOB_CURRENT_SERVICE_DATE")
    job = I.parse(raw, HTTP_LIMIT)
    require(type(job) is dict, "JOB_OBJECT")
    github, source = pending["github"], pending["source"]
    for name, expected in (("id", github["jobId"]), ("run_id", int(github["runId"])),
            ("run_attempt", int(github["runAttempt"]))):
        require(type(job.get(name)) is int and job[name] == expected, "JOB_IDENTITY")
    require(job.get("name") == github["job"] and job.get("head_sha") == source["commit"] and
        job.get("head_branch") == S.SOURCE_REF.removeprefix("refs/heads/") and
        job.get("url") == B.wire.ORIGIN + "/repos/" + I.REPOSITORY + "/actions/jobs/" + str(github["jobId"]) and
        job.get("run_url") == B.wire.ORIGIN + "/repos/" + I.REPOSITORY + "/actions/runs/" + github["runId"] and
        job.get("status") == "in_progress" and "conclusion" in job and job["conclusion"] is None and
        "completed_at" in job and job["completed_at"] is None, "JOB_SOURCE_OR_CURRENT")
    original = context["originalServiceJob"]
    require(type(original) is list and len(original) == 4 and
        [job["id"], job.get("started_at"), job.get("runner_name"), job.get("runner_id")] == original and
        type(job.get("runner_id")) is int and job["runner_id"] > 0 and
        job.get("runner_name") == context["observed"]["runnerName"], "ORIGINAL_RUNNER_CONTINUITY")
    selector = E.acquisition.GATE_SELECTOR if pending["kind"] == "gate" else O.SERVICE_SELECTORS[github["role"]]
    require(job.get("labels") == [selector] and type(job.get("runner_group_id")) is int and
        job["runner_group_id"] == 0 and job.get("runner_group_name") == "GitHub Actions", "ORIGINAL_HOSTED_SELECTOR")
    if "content-length" in values:
        require(re.fullmatch(r"[0-9]{1,7}", values["content-length"]) and
            int(values["content-length"]) == len(raw), "JOB_CONTENT_LENGTH")
    selected = service_steps(job, date, stage)
    return {"jobId": job["id"], "bodySha256": sha(raw), "rawHeaderVectorSha256": header_hash,
        "serviceDate": values["date"], "serviceEpoch": date, "steps": selected}


def artifact_name(pending):
    H.pending_value(pending)
    return "initial-recipient-custody-" + pending["github"]["runId"] + "-" + \
        pending["github"]["runAttempt"] + "-" + pending["kind"] + "-" + pending["selection"]


def decimal(value):
    require(type(value) is str and re.fullmatch(r"0|[1-9][0-9]{0,19}", value), "DECIMAL")
    return integer(int(value))

# Fixed finite-mode records. These predicates bind supplied original bytes;
# the native/Node owners, not a dictionary or digest, prove actual custody.
INPUT_BYTES = 2 * 1024 * 1024 - 5  # The five-byte I header is charged separately.
FINISH_INPUT_SCOPE = "INITIAL_ARTIFACT_FINISH_ORIGINALS_INPUT_V1"
AFTER_INPUT_SCOPE = "INITIAL_ARTIFACT_AFTER_ORIGINALS_INPUT_V1"
AFTER_READY_SCOPE = "INITIAL_ARTIFACT_AFTER_READY_PENDING_PUBLIC_OBSERVATION_V1"
FINISH_CLOSED_SCOPE = "INITIAL_ARTIFACT_FINISH_CLOSED_PENDING_PROCESS_V1"
AFTER_CLOSED_SCOPE = "INITIAL_ARTIFACT_AFTER_CLOSED_PENDING_PROCESS_V1"
UPLOAD_DIRECTORY_ENV = "P2PKIT_INITIAL_UPLOAD_DIRECTORY_SHA256"
UPLOAD_METADATA_ENV = "P2PKIT_INITIAL_UPLOAD_FILE_METADATA_SHA256"
UPLOAD_CLOSE_ENV = "P2PKIT_INITIAL_UPLOAD_OWNER_CLOSE_SHA256"
UTC_FIELDS = ("policyNotBefore", "policyExpiresAt", "authorityNotBefore", "authorityExpiresAt")
READY_FIELDS = {"schema", "scope", "kind", "selection", "source", "github", "beforeSha256",
    "carrierCloseSha256", "firstRawNs", "deadline", "originalWindow", "workEndNs", "closeEndNs", "members",
    "zipBytes", "originals", "jobOriginal", *UTC_FIELDS, "observedAt", "nativeFileRetirement",
    "originalStepOutcome", "qualification"}
STREAM_FIELDS = {"schema", "scope", "beforeSha256", "readySha256", "zipBytes", "zipSha256",
    "nativeCloseSha256", "closedNs", "nativeFileRetirement", "originalReaderOutcome", "qualification"}
READER_FLAGS = ("originalChildCloseObserved", "originalExitZeroObserved", "stdinFinishObserved",
    "stdinEndCallbackObserved", "stdoutEndObserved", "stderrEndObserved")
READER_FIELDS = {"scope", "transport", "code", "preSpawnLocalNs", "returnedLocalNs", *READER_FLAGS,
    "originalPipeCloses", "stderrBytes", "readySha256", "finalSha256", "zipBytes", "zipSha256",
    "nativeFileRetirement", "originalStepOutcome", "qualification"}
OBSERVER_FLAGS = ("requestFinishObserved", "requestEndCallbackObserved", "tlsSecureConnectObserved",
    "tlsAuthorizedObserved", "responseEndObserved", "requestCloseObserved", "responseCloseObserved",
    "socketCloseObserved")
OBSERVER_ROW_FIELDS = {"kind", "id", "startedNs", "endNs", "closedNs", "status", "bodyBytes", "bodySha256",
    "rawHeaderVectorSha256", "date", "dateEpochSeconds", *OBSERVER_FLAGS}
OBSERVER_FIELDS = {"scope", "stage", "transport", "code", "requestSha256", "jobId", "artifactId", "enteredNs",
    "lastObservationNs", "agentDestroyReturned", "originalResourceCount", "requests", "originalStepOutcome",
    "qualification"}
TRANSPORT_FLAGS = ("requestFinished", "requestEndCallback", "responseEndObserved", "requestCloseObserved",
    "responseCloseObserved", "socketCloseObserved")
TRANSPORT_ROW_FIELDS = {"kind", "startNs", "status", "bodyBytes", "responseBytes", *TRANSPORT_FLAGS}
TRANSPORT_FIELDS = {"scope", "transport", "code", "requestSha256", "artifactName", "inputBytes", "sentBytes",
    "observedZipSha256", "submittedFinalizeHash", "artifactId", "createInvokedAt", "requestedExpiresAt",
    "requestedRetentionDays", "enteredNs", "returnedObservationNs", "inputEndObserved", "inputCloseObserved",
    "requests", "serviceDigest", "actualServiceExpiry", "nativeFileRetirement", "originalRunnerOutcome",
    "qualification"}
PENDING_COMMON = {"schema", "scope", "kind", "selection", "source", "github", "beforeSha256", "readySha256",
    "originalWindow", "deadline", "originals", "members", *UTC_FIELDS, "observedAt", "artifact", "times",
    "observations", "writerReturn", "originalHelperOutcome", "originalStepOutcome", "qualification",
    "privateOriginals"}
ARTIFACT_FIELDS = {"id", "name", "zipBytes", "zipSha256", "createInvokedAt", "requestedExpiresAt",
    "requestedRetentionDays"}
UPLOAD_TIMES = {"firstRawNs", "streamClosedNs", "finishFirstRawNs", "pendingPreparedNs", "workEndNs", "closeEndNs",
    "readerPreSpawnLocalNs", "readerReturnedLocalNs", "beforeEnteredLocalNs", "beforeReturnedLocalNs",
    "transportEnteredLocalNs", "transportReturnedLocalNs"}
UPLOAD_HASHES = {"streamFinalSha256", "readerClosedSha256", "transportClosedSha256", "beforeClosedSha256",
    "beforeBodySha256", "beforeHeaderVectorSha256"}
UPLOAD_OBSERVATIONS = UPLOAD_HASHES | {"beforeServiceEpoch", "beforeStepNumber", "uploadStepNumber",
    "transportRequestCount"}
AFTER_TIMES = {"firstRawNs", "endNs", "pendingPreparedNs", "observerEnteredLocalNs", "observerReturnedLocalNs"}
AFTER_HASHES = {"afterClosedSha256", "jobBodySha256", "jobHeaderVectorSha256", "artifactBodySha256",
    "artifactHeaderVectorSha256"}
AFTER_OBSERVATIONS = AFTER_HASHES | {"jobServiceEpoch", "artifactServiceEpoch", "beforeStepNumber",
    "uploadStepNumber", "afterStepNumber", "observerRequestCount"}
CARRIER_FIELDS = {"directoryIdentitySha256", "fileMetadataSha256", "fileOwnerCloseSha256"}
AFTER_READY_FIELDS = {"schema", "scope", "kind", "selection", "source", "github", "beforeSha256", "uploadSha256",
    "deadline", "originalWindow", "firstRawNs", "endNs", "artifactId", *UTC_FIELDS, "observedAt",
    "originalStepOutcome", "qualification"}
FINITE_FIELDS = {"schema", "scope", "kind", "selection", "source", "github", "beforeSha256", "readySha256",
    "inputSha256", "pending", "pendingSha256", *CARRIER_FIELDS, "closedNs", "artifactId",
    "originalHelperOutcome", "originalStepOutcome", "qualification"}


def _same(left, right, code):
    require(O.encoded(left) == O.encoded(right), code)


def _flags(value, names):
    require(all(value[name] is True for name in names), "ORIGINAL_CLOSED_FLAGS")


def _id(value):
    number = decimal(value)
    integer(number, 1, (1 << 63) - 1)
    return value


def _hash_fields(value, names):
    for name in names:
        digest(value[name])


def _millis(value):
    require(type(value) is str and re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z", value), "UTC_MILLISECONDS")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        seconds = B.wire.utc_epoch(value[:19] + "Z")
    except ValueError:
        raise DeliveryError("INITIAL_ARTIFACT_DELIVERY_UTC_MILLISECONDS") from None
    require(parsed.strftime("%Y-%m-%dT%H:%M:%S.") + str(parsed.microsecond // 1000).zfill(3) + "Z" == value,
        "UTC_MILLISECONDS")
    return integer(seconds * 1000 + parsed.microsecond // 1000, 1, 253402300799999)


def _validity(value, now=None):
    start, end, authority_start, authority_end = (integer(value[name], 1, 253402300799) for name in UTC_FIELDS)
    observed = integer(value["observedAt"], 1, 253402300799)
    require(start <= authority_start <= observed < authority_end <= end and
        authority_end - authority_start <= 14 * 86400, "PENDING_VALIDITY")
    if now is not None:
        integer(now, observed, 253402300799)
        require(authority_start <= now < authority_end, "PENDING_CURRENT_VALIDITY")


def _identity(value):
    require(type(value["kind"]) is str and value["kind"] in ("gate", "worker"), "PENDING_KIND")
    _cohort, selected, _system, _arch = S.bootstrap.selection(value["selection"])
    role = "linux-x64" if value["kind"] == "gate" else selected
    S.joint.source(value["source"])
    github = value["github"]
    fields(github, {"repository", "runId", "runAttempt", "job", "jobId", "role"})
    S.joint.run(github)
    integer(github["jobId"], 1, (1 << 63) - 1)
    require(github["repository"] == I.REPOSITORY and github["role"] == role and
        github["job"] == (E.G.JOB if value["kind"] == "gate" else S.bootstrap.JOB), "PENDING_JOB")
    H._window(value["originalWindow"], value["kind"], role, value["deadline"])
    digest(value["beforeSha256"])


def _original_members(value, zip_bytes):
    fields(value["originals"], H.ORIGINAL_FIELDS)
    _hash_fields(value["originals"], H.ORIGINAL_FIELDS)
    require(value["originals"]["policySha256"] == S.POLICY_SHA256, "PENDING_POLICY_PIN")
    _total, expected = H.carrier_bytes(value["members"])
    require(integer(zip_bytes, 1, H.MAX_ZIP_BYTES) == expected, "PENDING_ZIP_BYTES")


def stream_ready(raw):
    value = canonical(raw)
    fields(value, READY_FIELDS)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == READY_SCOPE,
        "READY_SCOPE")
    _identity(value)
    _original_members(value, value["zipBytes"])
    _validity(value)
    digest(value["carrierCloseSha256"])
    first, work, close = (decimal(value[name]) for name in ("firstRawNs", "workEndNs", "closeEndNs"))
    _seal, expected_work, expected_close = upload_caps(value["deadline"], first)
    require((work, close) == (expected_work, expected_close), "READY_ORIGINAL_CAPS")
    job = value["jobOriginal"]
    require(type(job) is list and len(job) == 4 and type(job[0]) is int and job[0] == value["github"]["jobId"] and
        type(job[2]) is str and 0 < len(job[2]) <= 256 and not any(ord(c) < 32 or ord(c) == 127 for c in job[2]),
        "READY_PRIVATE_JOB")
    B.wire.utc_epoch(job[1])
    integer(job[3], 1, (1 << 63) - 1)
    require(value["nativeFileRetirement"] == "PENDING_ORIGINAL_READERS" and
        value["originalStepOutcome"] == "NOT_OBSERVED" and value["qualification"] == "NOT_ESTABLISHED",
        "READY_NOT_ACCEPTANCE")
    return value


def stream_closed(raw, ready_raw):
    original, value = stream_ready(ready_raw), canonical(raw)
    fields(value, STREAM_FIELDS)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == FINAL_SCOPE and
        value["beforeSha256"] == original["beforeSha256"] and value["readySha256"] == sha(ready_raw) and
        type(value["zipBytes"]) is int and value["zipBytes"] == original["zipBytes"] and
        value["nativeFileRetirement"] == "KNOWN_NATIVE_CLOSE" and
        value["originalReaderOutcome"] == "PENDING_ENCLOSING_PROCESS_CLOSE" and
        value["qualification"] == "NOT_ESTABLISHED", "STREAM_CLOSE_BINDING")
    _hash_fields(value, ("zipSha256", "nativeCloseSha256"))
    integer(decimal(value["closedNs"]), decimal(original["firstRawNs"]), decimal(original["workEndNs"]) - 1)
    return value


def _base64_shape(value, maximum):
    require(type(value) is str and 0 < len(value) <= 4 * ((maximum + 2) // 3) and len(value) % 4 == 0 and
        re.fullmatch(r"[A-Za-z0-9+/]*={0,2}", value), "BASE64_BOUND_OR_SHAPE")
    require(0 < len(value) // 4 * 3 - (len(value) - len(value.rstrip("="))) <= maximum, "BASE64_DECODED_BOUND")


def _base64(value, maximum):
    _base64_shape(value, maximum)
    raw = base64.b64decode(value, validate=True)
    require(0 < len(raw) <= maximum and base64.b64encode(raw).decode("ascii") == value, "BASE64_CANONICAL")
    return raw


def control_input(raw, mode):
    """All encoded-size/roster checks precede decoding either original body."""
    require(mode in ("finish", "after"), "FINITE_MODE")
    value = canonical(raw, INPUT_BYTES)
    names = {"schema", "scope", "readerReadyBase64", "readerFinalBase64", "readerClosed", "transportClosed",
        "beforeClosed", "beforeOriginals"} if mode == "finish" else {"schema", "scope", "afterClosed", "afterOriginals"}
    fields(value, names)
    require(type(value["schema"]) is int and value["schema"] == 1 and value["scope"] ==
        (FINISH_INPUT_SCOPE if mode == "finish" else AFTER_INPUT_SCOPE), "CONTROL_SCOPE")
    if mode == "finish":
        _base64_shape(value["readerReadyBase64"], LIMIT)
        _base64_shape(value["readerFinalBase64"], LIMIT)
        fields(value["readerClosed"], READER_FIELDS)
        fields(value["transportClosed"], TRANSPORT_FIELDS)
    observer = value["beforeClosed" if mode == "finish" else "afterClosed"]
    fields(observer, OBSERVER_FIELDS)
    rows = value["beforeOriginals" if mode == "finish" else "afterOriginals"]
    kinds = ("job",) if mode == "finish" else ("job", "artifact")
    require(type(rows) is list and len(rows) == len(kinds), "CONTROL_ORIGINAL_ROSTER")
    for kind, row in zip(kinds, rows):
        fields(row, {"kind", "id", "bodyBase64", "rawHeaderVector"})
        require(row["kind"] == kind, "CONTROL_ORIGINAL_ORDER")
        _id(row["id"])
        _base64_shape(row["bodyBase64"], HTTP_LIMIT)
        public_headers(row["rawHeaderVector"])
    originals = [{"kind": row["kind"], "id": row["id"], "body": _base64(row["bodyBase64"], HTTP_LIMIT),
        "rawHeaderVector": row["rawHeaderVector"]} for row in rows]
    ready_raw = _base64(value["readerReadyBase64"], LIMIT) if mode == "finish" else None
    final_raw = _base64(value["readerFinalBase64"], LIMIT) if mode == "finish" else None
    return value, originals, ready_raw, final_raw


def _local_bounds(ready_value, pre):
    first = decimal(ready_value["firstRawNs"])
    window = ready_value["originalWindow"]
    start = integer(pre + window["sealEndNs"] - first)
    close = min(integer(pre + 60 * NS), integer(pre + window["uploadEndNs"] - first))
    work = close - 5 * NS
    require(pre < start < work < close, "ORIGINAL_LOCAL_MAPPING")
    return start, work, close


def _reader_closed(value, ready_raw, final_raw, ready_value, final):
    fields(value, READER_FIELDS)
    _flags(value, READER_FLAGS)
    fields(value["originalPipeCloses"], {"stdin", "stdout", "stderr"})
    _flags(value["originalPipeCloses"], ("stdin", "stdout", "stderr"))
    require(value["scope"] == "INITIAL_ARTIFACT_FIXED_READER_TRANSPORT_ONLY" and
        value["transport"] == "closed" and value["code"] is None and type(value["stderrBytes"]) is int and
        value["stderrBytes"] == 0 and value["readySha256"] == sha(ready_raw) and
        value["finalSha256"] == sha(final_raw) and type(value["zipBytes"]) is int and
        value["zipBytes"] == ready_value["zipBytes"] and value["zipSha256"] == final["zipSha256"] and
        value["nativeFileRetirement"] == "FIXED_HELPER_RETURN_REQUIRES_CALLER_VALIDATION" and
        value["originalStepOutcome"] == "NOT_OBSERVED" and value["qualification"] == "NOT_ESTABLISHED",
        "READER_COMPLETE_CLOSE")
    pre, returned = decimal(value["preSpawnLocalNs"]), decimal(value["returnedLocalNs"])
    bounds = _local_bounds(ready_value, pre)
    require(pre <= returned < bounds[1], "READER_ORIGINAL_LOCAL_RETURN")
    return bounds


def _observer_closed(value, originals, ready_value, *, stage, request_sha256, phase_end, now):
    fields(value, OBSERVER_FIELDS)
    count = 1 if stage == "before" else 2
    artifact_id = None if stage == "before" else ready_value["artifactId"]
    require(value["scope"] == "INITIAL_ARTIFACT_PUBLIC_TERMINAL_TRANSPORT_ONLY_V1" and value["stage"] == stage and
        value["transport"] == "closed" and value["code"] is None and value["requestSha256"] == request_sha256 and
        value["jobId"] == str(ready_value["github"]["jobId"]) and value["artifactId"] == artifact_id and
        value["agentDestroyReturned"] is True and type(value["originalResourceCount"]) is int and
        value["originalResourceCount"] == 3 * count and value["originalStepOutcome"] == "NOT_OBSERVED" and
        value["qualification"] == "NOT_ESTABLISHED", "OBSERVER_COMPLETE_CLOSE")
    require(type(originals) is list and len(originals) == count and type(value["requests"]) is list and
        len(value["requests"]) == count, "OBSERVER_COMPLETE_ROSTER")
    entered, returned = decimal(value["enteredNs"]), decimal(value["lastObservationNs"])
    if phase_end is None:
        # AFTER's actual pre-spawn LOCAL is owned by Node, not present in this
        # projection. Both rows must still share the same <=15s absolute end.
        fields(value["requests"][0], OBSERVER_ROW_FIELDS)
        phase_end = decimal(value["requests"][0]["endNs"])
        require(entered < phase_end <= integer(entered + 15 * NS), "AFTER_OBSERVER_SHARED_CAP")
    require(entered <= returned < phase_end, "OBSERVER_LOCAL_RETURN")
    previous = entered
    for index, (row, original) in enumerate(zip(value["requests"], originals)):
        fields(row, OBSERVER_ROW_FIELDS)
        kind, identifier = ("job", value["jobId"]) if index == 0 else ("artifact", artifact_id)
        require(original["kind"] == kind and original["id"] == identifier and row["kind"] == kind and
            row["id"] == identifier and type(row["status"]) is int and row["status"] == 200, "OBSERVER_ORIGINAL_ID")
        body, vector = original["body"], original["rawHeaderVector"]
        headers, epoch, header_hash = public_headers(vector)
        require(epoch <= now <= epoch + B.wire.CACHE_SECONDS and
            ("content-length" not in headers or re.fullmatch(r"[0-9]{1,7}", headers["content-length"]) and
             int(headers["content-length"]) == len(body)), "OBSERVER_CURRENT_HTTP")
        require(type(row["bodyBytes"]) is int and row["bodyBytes"] == len(body) and
            row["bodySha256"] == sha(body) and row["rawHeaderVectorSha256"] == header_hash and
            row["date"] == headers["date"] and type(row["dateEpochSeconds"]) is int and
            row["dateEpochSeconds"] == epoch, "OBSERVER_ORIGINAL_BYTES")
        _flags(row, OBSERVER_FLAGS)
        start, end, closed = (decimal(row[name]) for name in ("startedNs", "endNs", "closedNs"))
        require(previous <= start <= closed <= returned and closed < end == min(phase_end, integer(start + 15 * NS)),
            "OBSERVER_REQUEST_CHRONOLOGY")
        previous = closed
    return value


def _transport_closed(value, ready_value, ready_raw, final, reader, before, bounds, now):
    fields(value, TRANSPORT_FIELDS)
    size, name = ready_value["zipBytes"], "initial-recipient-custody-" + ready_value["github"]["runId"] + "-" + \
        ready_value["github"]["runAttempt"] + "-" + ready_value["kind"] + "-" + ready_value["selection"]
    require(value["scope"] == "INITIAL_ARTIFACT_STREAM_TRANSPORT_ONLY" and value["transport"] == "closed" and
        value["code"] is None and value["requestSha256"] == sha(ready_raw) and value["artifactName"] == name and
        type(value["inputBytes"]) is int and value["inputBytes"] == size and type(value["sentBytes"]) is int and
        value["sentBytes"] == size and value["observedZipSha256"] == final["zipSha256"] and
        value["submittedFinalizeHash"] == "sha256:" + final["zipSha256"] and
        type(value["requestedRetentionDays"]) is int and value["requestedRetentionDays"] == 14 and
        value["inputEndObserved"] is True and value["inputCloseObserved"] is True and
        value["serviceDigest"] == value["actualServiceExpiry"] == value["originalRunnerOutcome"] == "NOT_OBSERVED" and
        value["nativeFileRetirement"] == value["qualification"] == "NOT_ESTABLISHED", "TRANSPORT_COMPLETE_CLOSE")
    _id(value["artifactId"])
    create, expiry = _millis(value["createInvokedAt"]), _millis(value["requestedExpiresAt"])
    require(create // 1000 <= now and expiry - create == 14 * 86400000, "TRANSPORT_ORIGINAL_REQUEST_EXPIRY")
    entered, returned = decimal(value["enteredNs"]), decimal(value["returnedObservationNs"])
    require(decimal(before["lastObservationNs"]) <= entered < bounds[0] and
        entered <= decimal(reader["returnedLocalNs"]) <= returned < bounds[2], "TRANSPORT_ORIGINAL_RETURN")
    blocks = (size + 8 * 1024 * 1024 - 1) // (8 * 1024 * 1024)
    rows = value["requests"]
    require(type(rows) is list and len(rows) == blocks + 3 <= 67, "TRANSPORT_EXACT_REQUEST_COUNT")
    # Byte-count formulas only. Empty backend fields plus72 account for two
    # original36-byte GUIDs; this is NOT a reconstructed request/evidence.
    backend = {"workflow_run_backend_id": "", "workflow_job_run_backend_id": "", "name": name}
    create_bytes = len(json.dumps({**backend, "version": 7, "mime_type": "application/zip",
        "expires_at": value["requestedExpiresAt"]}, separators=(",", ":")).encode("ascii")) + 72
    finalize_bytes = len(json.dumps({**backend, "size": str(size), "hash": value["submittedFinalizeHash"]},
        separators=(",", ":")).encode("ascii")) + 72
    blocklist_bytes = len('<?xml version="1.0" encoding="utf-8"?><BlockList></BlockList>') + \
        blocks * (len("<Uncommitted></Uncommitted>") + 8)
    previous = entered
    for index, row in enumerate(rows):
        fields(row, TRANSPORT_ROW_FIELDS)
        kind = "create" if index == 0 else "block" if index <= blocks else "blocklist" if index == blocks + 1 else "finalize"
        service = kind in ("create", "finalize")
        body_bytes = create_bytes if kind == "create" else finalize_bytes if kind == "finalize" else \
            blocklist_bytes if kind == "blocklist" else min(8 * 1024 * 1024, size - (index - 1) * 8 * 1024 * 1024)
        require(row["kind"] == kind and type(row["status"]) is int and row["status"] == (200 if service else 201) and
            type(row["bodyBytes"]) is int and row["bodyBytes"] == body_bytes, "TRANSPORT_REQUEST_IDENTITY")
        integer(row["responseBytes"], 1 if service else 0, 65536 if service else 0)
        _flags(row, TRANSPORT_FLAGS)
        start = decimal(row["startNs"])
        require(previous <= start <= returned and start < bounds[1] and (index != 0 or start < bounds[0]),
            "TRANSPORT_REQUEST_CHRONOLOGY")
        previous = start
    return value


def finish_observations(control, *, now):
    value, originals, ready_raw, final_raw = control
    original, final = stream_ready(ready_raw), stream_closed(final_raw, ready_raw)
    _validity(original, now)
    reader, before, transport = (value[name] for name in ("readerClosed", "beforeClosed", "transportClosed"))
    bounds = _reader_closed(reader, ready_raw, final_raw, original, final)
    _observer_closed(before, originals, original, stage="before", request_sha256=sha(ready_raw),
        phase_end=bounds[0], now=now)
    require(decimal(reader["preSpawnLocalNs"]) <= decimal(before["enteredNs"]), "BEFORE_ORIGINAL_READER_BASIS")
    _transport_closed(transport, original, ready_raw, final, reader, before, bounds, now)
    context = {"originalServiceJob": original["jobOriginal"], "observed": {"runnerName": original["jobOriginal"][2]}}
    job = service_job(original, context, originals[0]["body"], originals[0]["rawHeaderVector"], stage="upload", now=now)
    return original, final, reader, before, transport, job


def _artifact_record(value, binding, *, after):
    fields(value, ARTIFACT_FIELDS | ({"createdAt", "expiresAt", "serviceDigest"} if after else set()))
    _id(value["id"])
    digest(value["zipSha256"])
    _original_members(binding, value["zipBytes"])
    expected_name = "initial-recipient-custody-" + binding["github"]["runId"] + "-" + \
        binding["github"]["runAttempt"] + "-" + binding["kind"] + "-" + binding["selection"]
    require(value["name"] == expected_name and type(value["requestedRetentionDays"]) is int and
        value["requestedRetentionDays"] == 14, "PENDING_ARTIFACT_IDENTITY")
    create, expiry = _millis(value["createInvokedAt"]), _millis(value["requestedExpiresAt"])
    require(create // 1000 <= binding["observedAt"] and expiry - create == 14 * 86400000,
        "PENDING_ORIGINAL_REQUEST_EXPIRY")
    if after:
        created, expires = B.wire.utc_epoch(value["createdAt"]), B.wire.utc_epoch(value["expiresAt"])
        require(create // 1000 <= created <= binding["observedAt"] < expires <= created + 14 * 86400 and
            expires * 1000 <= expiry and value["serviceDigest"] == "sha256:" + value["zipSha256"],
            "ARTIFACT_ORIGINAL_SERVICE_EXPIRY_OR_DIGEST")


def pending_value(value, mode):
    require(mode in ("finish", "after"), "PENDING_MODE")
    after = mode == "after"
    fields(value, PENDING_COMMON | ({"uploadSha256", "uploadCarrier"} if after else {"carrierCloseSha256"}))
    E._graph(value)
    require(type(value["schema"]) is int and value["schema"] == 1 and
        value["scope"] == (AFTER_SCOPE if after else UPLOAD_SCOPE), "PENDING_SCOPE")
    _identity(value)
    _validity(value)
    digest(value["readySha256"])
    digest(value["uploadSha256"] if after else value["carrierCloseSha256"])
    require(value["writerReturn"] == "PENDING_OWNER_CLOSE" and
        value["originalHelperOutcome"] == "PENDING_ENCLOSING_PROCESS_CLOSE" and
        value["originalStepOutcome"] == "NOT_OBSERVED" and value["qualification"] == "NOT_ESTABLISHED" and
        value["privateOriginals"] == "TERMINAL_SELF_TAIL_NOT_DELIVERED", "PENDING_NOT_SELF_ACCEPTANCE")
    _artifact_record(value["artifact"], value, after=after)
    times, observations = value["times"], value["observations"]
    fields(times, AFTER_TIMES if after else UPLOAD_TIMES)
    parsed = {name: decimal(raw) for name, raw in times.items()}
    fields(observations, AFTER_OBSERVATIONS if after else UPLOAD_OBSERVATIONS)
    _hash_fields(observations, AFTER_HASHES if after else UPLOAD_HASHES)
    before_number = integer(observations["beforeStepNumber"], 1, 2147483647)
    require(integer(observations["uploadStepNumber"], 1, 2147483647) == before_number + 1, "PENDING_U_ADJACENCY")
    for field in (("jobServiceEpoch", "artifactServiceEpoch") if after else ("beforeServiceEpoch",)):
        epoch = integer(observations[field], 1, 253402300799)
        require(epoch <= value["observedAt"] <= epoch + B.wire.CACHE_SECONDS, "PENDING_SERVICE_FRESHNESS")
    if after:
        fields(value["uploadCarrier"], CARRIER_FIELDS)
        _hash_fields(value["uploadCarrier"], CARRIER_FIELDS)
        _upload, end = after_caps(value["deadline"], parsed["firstRawNs"])
        require(parsed["endNs"] == end and parsed["firstRawNs"] <= parsed["pendingPreparedNs"] < end and
            parsed["observerEnteredLocalNs"] <= parsed["observerReturnedLocalNs"] <
                parsed["observerEnteredLocalNs"] + 15 * NS and
            integer(observations["afterStepNumber"], 1, 2147483647) == before_number + 2 and
            type(observations["observerRequestCount"]) is int and observations["observerRequestCount"] == 2,
            "PENDING_A_ORIGINAL_TIMES_OR_ROSTER")
    else:
        seal, work, close = upload_caps(value["deadline"], parsed["firstRawNs"])
        require((parsed["workEndNs"], parsed["closeEndNs"]) == (work, close) and
            parsed["firstRawNs"] <= parsed["streamClosedNs"] <= parsed["finishFirstRawNs"] <=
            parsed["pendingPreparedNs"] < work, "PENDING_U_ORIGINAL_TIMES")
        pre = parsed["readerPreSpawnLocalNs"]
        start_local = integer(pre + seal - parsed["firstRawNs"])
        work_local, close_local = (integer(pre + end - parsed["firstRawNs"]) for end in (work, close))
        require(pre <= parsed["beforeEnteredLocalNs"] <= parsed["beforeReturnedLocalNs"] <=
            parsed["transportEnteredLocalNs"] <= parsed["readerReturnedLocalNs"] <= parsed["transportReturnedLocalNs"] and
            parsed["beforeReturnedLocalNs"] < start_local and parsed["readerReturnedLocalNs"] < work_local and
            parsed["transportReturnedLocalNs"] < close_local and type(observations["transportRequestCount"]) is int and
            observations["transportRequestCount"] == 3 + (value["artifact"]["zipBytes"] + 8 * 1024 * 1024 - 1) //
                (8 * 1024 * 1024), "PENDING_U_ORIGINAL_LOCAL_OR_REQUESTS")
    return value


def parse_delivery(raw, mode):
    return pending_value(canonical(raw), mode)


def _pending_base(pending, policy, match, *, ready_sha256, before_sha256, scope, now):
    H.pending_value(pending)
    return {"schema": 1, "scope": scope, **{name: E._copy(pending[name]) for name in
        ("kind", "selection", "source", "github", "originalWindow", "deadline", "originals", "members")},
        "beforeSha256": digest(before_sha256), "readySha256": digest(ready_sha256),
        "policyNotBefore": policy["notBefore"], "policyExpiresAt": policy["expiresAt"],
        "authorityNotBefore": match["notBefore"], "authorityExpiresAt": match["expiresAt"], "observedAt": now,
        "writerReturn": "PENDING_OWNER_CLOSE", "originalHelperOutcome": "PENDING_ENCLOSING_PROCESS_CLOSE",
        "originalStepOutcome": "NOT_OBSERVED", "qualification": "NOT_ESTABLISHED",
        "privateOriginals": "TERMINAL_SELF_TAIL_NOT_DELIVERED"}


def upload_pending(pending, context, *, policy, match, control, observed, finish_first, prepared, now):
    value, _originals, ready_raw, final_raw = control
    original, final, reader, before, transport, job = observed
    expected_ready = ready(pending, context, policy=policy, match=match,
        first_raw=decimal(original["firstRawNs"]), before_sha256=original["beforeSha256"],
        carrier_sha256=original["carrierCloseSha256"], now=original["observedAt"])
    require(expected_ready == ready_raw, "FINISH_CURRENT_K_READY")
    _validity(original, now)
    result = _pending_base(pending, policy, match, ready_sha256=sha(ready_raw),
        before_sha256=original["beforeSha256"], scope=UPLOAD_SCOPE, now=now)
    result.update(carrierCloseSha256=original["carrierCloseSha256"], artifact={"id": transport["artifactId"],
        "name": transport["artifactName"], "zipBytes": transport["inputBytes"],
        "zipSha256": transport["observedZipSha256"], "createInvokedAt": transport["createInvokedAt"],
        "requestedExpiresAt": transport["requestedExpiresAt"], "requestedRetentionDays": 14},
        times={"firstRawNs": original["firstRawNs"], "streamClosedNs": final["closedNs"],
            "finishFirstRawNs": str(integer(finish_first)), "pendingPreparedNs": str(integer(prepared)),
            "workEndNs": original["workEndNs"], "closeEndNs": original["closeEndNs"],
            "readerPreSpawnLocalNs": reader["preSpawnLocalNs"], "readerReturnedLocalNs": reader["returnedLocalNs"],
            "beforeEnteredLocalNs": before["enteredNs"], "beforeReturnedLocalNs": before["lastObservationNs"],
            "transportEnteredLocalNs": transport["enteredNs"], "transportReturnedLocalNs": transport["returnedObservationNs"]},
        observations={"streamFinalSha256": sha(final_raw), "readerClosedSha256": sha(O.encoded(reader)),
            "transportClosedSha256": sha(O.encoded(transport)), "beforeClosedSha256": sha(O.encoded(before)),
            "beforeBodySha256": job["bodySha256"], "beforeHeaderVectorSha256": job["rawHeaderVectorSha256"],
            "beforeServiceEpoch": job["serviceEpoch"], "beforeStepNumber": job["steps"]["before"]["number"],
            "uploadStepNumber": job["steps"]["upload"]["number"], "transportRequestCount": len(transport["requests"])})
    return encoded(pending_value(result, "finish"))


def after_ready(pending, upload_raw, *, policy, match, first, before_sha256, now):
    H.pending_value(pending)
    upload = parse_delivery(upload_raw, "finish")
    for name in ("kind", "selection", "source", "github", "originalWindow", "deadline", "originals", "members"):
        _same(upload[name], pending[name], "AFTER_ORIGINAL_K_LINK")
    require(upload["beforeSha256"] == before_sha256, "AFTER_BEFORE_LINK")
    _validity(upload, now)
    _upload, end = after_caps(pending["deadline"], first)
    result = {"schema": 1, "scope": AFTER_READY_SCOPE, **{name: E._copy(pending[name]) for name in
        ("kind", "selection", "source", "github", "deadline", "originalWindow")},
        "beforeSha256": before_sha256, "uploadSha256": sha(upload_raw), "firstRawNs": str(first), "endNs": str(end),
        "artifactId": upload["artifact"]["id"], "policyNotBefore": policy["notBefore"],
        "policyExpiresAt": policy["expiresAt"], "authorityNotBefore": match["notBefore"],
        "authorityExpiresAt": match["expiresAt"], "observedAt": now,
        "originalStepOutcome": "NOT_OBSERVED", "qualification": "NOT_ESTABLISHED"}
    _validity(result, now)
    for name in UTC_FIELDS:
        require(result[name] == upload[name] and type(result[name]) is int, "AFTER_ORIGINAL_VALIDITY")
    return encoded(result)


def _service_artifact(upload, original, *, now):
    raw, headers = original["body"], original["rawHeaderVector"]
    values, epoch, header_hash = public_headers(headers)
    require(epoch <= now <= epoch + B.wire.CACHE_SECONDS, "ARTIFACT_SERVICE_DATE")
    value = I.parse(raw, HTTP_LIMIT)
    require(type(value) is dict, "ARTIFACT_SERVICE_OBJECT")
    artifact, github, source = upload["artifact"], upload["github"], upload["source"]
    url = B.wire.ORIGIN + "/repos/" + I.REPOSITORY + "/actions/artifacts/" + artifact["id"]
    require(type(value.get("id")) is int and value["id"] == int(artifact["id"]) and
        value.get("name") == artifact["name"] and type(value.get("size_in_bytes")) is int and
        value["size_in_bytes"] == artifact["zipBytes"] and value.get("digest") == "sha256:" + artifact["zipSha256"] and
        value.get("expired") is False and value.get("url") == url and value.get("archive_download_url") == url + "/zip",
        "ARTIFACT_EXACT_SERVICE_IDENTITY")
    run = value.get("workflow_run")
    require(type(run) is dict and type(run.get("id")) is int and run["id"] == int(github["runId"]) and
        run.get("head_sha") == source["commit"] and run.get("head_branch") == S.SOURCE_REF.removeprefix("refs/heads/"),
        "ARTIFACT_ORIGINAL_RUN_SOURCE")
    result = {**E._copy(artifact), "createdAt": value.get("created_at"), "expiresAt": value.get("expires_at"),
        "serviceDigest": value.get("digest")}
    _artifact_record(result, {**upload, "observedAt": now}, after=True)
    return result, {"bodySha256": sha(raw), "rawHeaderVectorSha256": header_hash, "serviceEpoch": epoch}


def delivery_pending(pending, context, upload_raw, ready_raw, *, policy, match, control, carrier, prepared, now):
    value, originals, _unused_ready, _unused_final = control
    original = canonical(ready_raw)
    fields(original, AFTER_READY_FIELDS)
    upload = parse_delivery(upload_raw, "finish")
    first = decimal(original["firstRawNs"])
    require(after_ready(pending, upload_raw, policy=policy, match=match, first=first,
        before_sha256=original["beforeSha256"], now=original["observedAt"]) == ready_raw, "AFTER_CURRENT_READY")
    _validity(original, now)
    after = _observer_closed(value["afterClosed"], originals, original, stage="after", request_sha256=sha(ready_raw),
        phase_end=None, now=now)
    job = service_job(pending, context, originals[0]["body"], originals[0]["rawHeaderVector"], stage="after", now=now)
    artifact, service = _service_artifact(upload, originals[1], now=now)
    fields(carrier, CARRIER_FIELDS)
    _hash_fields(carrier, CARRIER_FIELDS)
    result = _pending_base(pending, policy, match, ready_sha256=sha(ready_raw), before_sha256=original["beforeSha256"],
        scope=AFTER_SCOPE, now=now)
    result.update(uploadSha256=sha(upload_raw), uploadCarrier=E._copy(carrier), artifact=artifact,
        times={"firstRawNs": original["firstRawNs"], "endNs": original["endNs"],
            "pendingPreparedNs": str(integer(prepared)), "observerEnteredLocalNs": after["enteredNs"],
            "observerReturnedLocalNs": after["lastObservationNs"]},
        observations={"afterClosedSha256": sha(O.encoded(after)), "jobBodySha256": job["bodySha256"],
            "jobHeaderVectorSha256": job["rawHeaderVectorSha256"], "artifactBodySha256": service["bodySha256"],
            "artifactHeaderVectorSha256": service["rawHeaderVectorSha256"], "jobServiceEpoch": job["serviceEpoch"],
            "artifactServiceEpoch": service["serviceEpoch"], "beforeStepNumber": job["steps"]["before"]["number"],
            "uploadStepNumber": job["steps"]["upload"]["number"], "afterStepNumber": job["steps"]["after"]["number"],
            "observerRequestCount": len(after["requests"])})
    return encoded(pending_value(result, "after"))


def finite_result(mode, pending_raw, *, ready_raw, input_raw, directory_identity_raw, file_metadata_raw,
        file_owner_close_raw, closed_ns):
    value = parse_delivery(pending_raw, mode)
    integer(closed_ns, decimal(value["times"]["pendingPreparedNs"]),
        decimal(value["times"]["workEndNs" if mode == "finish" else "endNs"]) - 1)
    result = {"schema": 1, "scope": FINISH_CLOSED_SCOPE if mode == "finish" else AFTER_CLOSED_SCOPE,
        **{name: E._copy(value[name]) for name in ("kind", "selection", "source", "github", "beforeSha256")},
        "readySha256": sha(ready_raw), "inputSha256": sha(input_raw), "pending": value,
        "pendingSha256": sha(pending_raw), "directoryIdentitySha256": sha(directory_identity_raw),
        "fileMetadataSha256": sha(file_metadata_raw), "fileOwnerCloseSha256": sha(file_owner_close_raw),
        "closedNs": str(closed_ns), "artifactId": value["artifact"]["id"],
        "originalHelperOutcome": "PENDING_ENCLOSING_PROCESS_CLOSE", "originalStepOutcome": "NOT_OBSERVED",
        "qualification": "NOT_ESTABLISHED"}
    require(result["readySha256"] == value["readySha256"], "FINITE_ORIGINAL_READY_LINK")
    return encoded(result)
