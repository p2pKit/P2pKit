"""Closed terminal delivery DATA, never native, HTTP, Step or Release authority.

The fixed U/A controller owns the actual K readers, current clock/boot, original
child/pipe returns and public GitHub observations. These predicates only bind
their supplied bytes. They cannot restore B/K owners, Recipient objects, source
queries or a retired lease. No file, network, process, clock or key operation is
performed by this module.
"""
from __future__ import annotations

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
