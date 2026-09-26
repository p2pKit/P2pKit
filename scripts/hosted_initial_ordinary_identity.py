"""Distinct Stage2 worker binding; reference-only, NOT ordinary Admission.

This does not turn a supplied OrdinaryMatch or successful gate into productive
qualification. The actual native caller must separately prove current original
acquisition, known return, recipient validation and all four genuine compatible
bootstrap packets. This increment has no native/workflow/controller caller.
No trusted-base fallback, Stage1/bootstrap cast or publication intent exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import re

import hosted_initial_recipient_stages as stages


I = stages.identity
SCOPE = "ORDINARY_INITIAL_RECIPIENT_IDENTITY_V1"
MATCH_SCOPE = stages.STAGE2 + "_MATCH_ONLY_NOT_ADMISSION"
FIELDS = {"schema", "scope", "profile", "suites", "source", "github", "policy", "initialRecipient", "firstPullRequest"}
MATCH_FIELDS = {"schema", "scope", "authority", "originalBase", "reviewed", "source", "github", "policy",
    "firstUseAt", "notBefore", "expiresAt", "environment", "stage1", "qualifications", "historicalRecords",
    "qualificationAcceptance"}


@dataclass(frozen=True)
class InitialOrdinaryIdentity:
    """Serializable binding only. Native/live ownership is NOT reconstructible."""
    record: bytes = field(repr=False)
    original_event: bytes = field(repr=False)
    original_policy: bytes = field(repr=False)
    public_key: bytes = field(repr=False)
    fingerprint: str
    key_sha256: str
    expires_at: int


def require(value, code):
    I.require(value, "INITIAL_ORDINARY_IDENTITY_" + code)


def _declaration(match, first):
    return {"schema": 1, "scope": stages.STAGE2, "repository": I.REPOSITORY,
        "base": dict(stages.BASE), "reviewed": match["reviewed"], "sourceRef": stages.SOURCE_REF,
        "policySha256": stages.POLICY_SHA256, "notBefore": match["notBefore"], "expiresAt": match["expiresAt"],
        "environment": match["environment"], "firstPullRequest": first,
        "stage1": match["stage1"], "qualifications": match["qualifications"]}


def _match(value, first):
    """Closed retained-record checks, not current authority or packet acceptance."""
    require(type(value) is dict and set(value) == MATCH_FIELDS and type(value["schema"]) is int and
            value["schema"] == 1 and value["scope"] == MATCH_SCOPE and
            value["qualificationAcceptance"] == "NOT_ESTABLISHED_BY_REFERENCE_MATCH", "MATCH_FIELDS")
    require(value["originalBase"] == stages.BASE, "ORIGINAL_BASE")
    reviewed, source = stages.joint.source(value["reviewed"]), stages.joint.source(value["source"])
    require(reviewed["commit"] != stages.BASE["commit"] and reviewed["tree"] != stages.BASE["tree"], "REVIEWED_SOURCE")
    stages.environment(value["environment"])
    authority = stages.fields(value["authority"], "id url bodySha256 owner ownerId createdAt", "AUTHORITY_FIELDS")
    stages.positive(authority["id"])
    stages.digest(authority["bodySha256"])
    require(authority["owner"] == stages.joint.OWNER_LOGIN and type(authority["ownerId"]) is int and
            authority["ownerId"] == stages.joint.OWNER_ID and authority["url"] ==
            "https://github.com/" + I.REPOSITORY + "/issues/437#issuecomment-" + str(authority["id"]), "AUTHORITY")
    created = stages.joint.timestamp(authority["createdAt"])
    start, began, end = (value[name] for name in ("notBefore", "firstUseAt", "expiresAt"))
    require(all(type(x) is int for x in (start, began, end)) and 0 < created <= began and
            0 < start <= began < end and end - start <= 14 * 24 * 60 * 60, "MATCH_WINDOW")
    declaration = _declaration(value, first)
    first, pairs = stages.ordinary_roster(declaration)
    require(source == first["merge"], "MERGE_SOURCE")
    github = stages.fields(value["github"], "profile event ref workflow workflowSha job runId runAttempt "
                           "runnerOS runnerArch", "GITHUB_FIELDS")
    stages.joint.run(github)
    require(type(github["profile"]) is str and github["profile"] in I.PROFILES, "PROFILE")
    profile = github["profile"]
    roles = [role for role, host in stages.joint.ROLES.items() if host == (github["runnerOS"], github["runnerArch"])]
    require(len(roles) == 1, "HOST")
    role = roles[0]
    require({"profile": profile, "role": role, "runId": github["runId"], "runAttempt": github["runAttempt"]}
            in first["runs"], "WORKER_SLOT")
    workflow, job, _ = I.PROFILES[profile]
    require((github["event"], github["ref"], github["workflow"], github["workflowSha"], github["job"]) ==
            ("pull_request", f"refs/pull/{first['number']}/merge", workflow, source["commit"], job), "WORKER_ONLY")
    policy = stages.fields(value["policy"], "origin commit blob path sha256", "POLICY_FIELDS")
    require(policy == {"origin": "reviewed-head", "commit": reviewed["commit"], "blob": I.sha(policy["blob"]),
            "path": I.POLICY_PATH, "sha256": stages.POLICY_SHA256}, "POLICY_ORIGIN")
    prior = stages.fields(value["stage1"], "commentId bodySha256 reviewed", "STAGE1_REFERENCE_FIELDS")
    stages.positive(prior["commentId"])
    stages.digest(prior["bodySha256"])
    require(stages.joint.source(prior["reviewed"])["commit"] not in (reviewed["commit"], source["commit"]),
            "SEPARATE_REVIEWED_HEADS")
    entries, records = value["qualifications"], value["historicalRecords"]
    require(type(entries) is list and len(entries) == 4 and type(records) is list and len(records) == 4,
            "QUALIFICATION_REFERENCES")
    covered, run_ids, artifacts = set(), {item["runId"] for item in first["runs"]}, set()
    for entry, record in zip(entries, records):
        stages.fields(entry, "selection runId runAttempt completedAt packet inventory compatibility review", "QUALIFICATION_FIELDS")
        cohort = stages.bootstrap.selection(entry["selection"])[:2]
        run_id, _ = stages.joint.run(entry)
        require(cohort in pairs and cohort not in covered and run_id not in run_ids, "QUALIFICATION_COHORT_OR_RUN")
        covered.add(cohort)
        run_ids.add(run_id)
        packet = stages.fields(entry["packet"], "artifactId bytes sha256", "PACKET_FIELDS")
        stages.positive(packet["artifactId"])
        require(packet["artifactId"] not in artifacts, "DUPLICATE_PACKET")
        artifacts.add(packet["artifactId"])
        stages._reference({name: packet[name] for name in ("bytes", "sha256")}, maximum=512 * 1024 * 1024)
        for name in ("inventory", "compatibility", "review"):
            stages.comment_reference(entry[name])
        require(type(entry["completedAt"]) is int and 0 < entry["completedAt"] < created, "HISTORICAL_COMPLETION")
        stages.fields(record, "selection recordSha256", "HISTORICAL_RECORD_FIELDS")
        require(record["selection"] == entry["selection"], "HISTORICAL_SELECTION")
        stages.digest(record["recordSha256"])
    require(covered == pairs, "MISSING_COHORT")
    body = stages.COMMANDS[stages.STAGE2].encode("ascii") + I.encoded(declaration).removesuffix(b"\n")
    require(hashlib.sha256(body).hexdigest() == authority["bodySha256"], "OWNER_STATEMENT_BINDING")
    return profile, role


def _record(match, first, event_sha256, policy):
    profile = match["github"]["profile"]
    github = {name: value for name, value in match["github"].items() if name != "profile"}
    value = {"schema": 1, "scope": SCOPE, "profile": profile, "suites": list(I.PROFILES[profile][2]),
        "source": match["source"], "github": {**github, "repository": I.REPOSITORY, "eventSha256": event_sha256,
            "eventBinding": {"number": first["number"], "base": stages.BASE["commit"],
                "head": match["reviewed"]["commit"], "headRepository": I.REPOSITORY,
                "originalMain": stages.BASE["commit"], "policyHead": match["reviewed"]["commit"]}},
        "policy": policy, "initialRecipient": match, "firstPullRequest": first}
    if profile == "desktop":
        value["samplePackagingRequired"] = False  # First PR is never main publication.
    return value


def bind_worker_match(match, *, comment_raw, event_raw, policy_raw, now):
    """Bind supplied originals without claiming they were acquired/qualified.

    The retained exact C2 roster is necessary: OrdinaryMatch alone does not
    contain the complete first-PR run roster. Native callers cannot skip the
    original comment, current approval/environment or full historical checks.
    """
    require(type(match) is stages.OrdinaryMatch and type(match.record) is bytes and
            type(comment_raw) is bytes and type(event_raw) is bytes and type(policy_raw) is bytes, "ORIGINAL_TYPES")
    value = I.parse(match.record, stages.LIMIT)
    require(set(value) == MATCH_FIELDS and match.record == I.encoded(value), "MATCH_ENCODING")
    authority = stages.fields(value["authority"], "id url bodySha256 owner ownerId createdAt", "AUTHORITY_FIELDS")
    declaration, original_authority, _ = stages.statement(stages.STAGE2, comment_raw, authority["id"], authority["bodySha256"])
    first = declaration["firstPullRequest"]
    _match(value, first)
    require(declaration == _declaration(value, first) and original_authority == authority, "ORIGINAL_STATEMENT")
    policy, key = I._policy(policy_raw, now)
    require(type(now) is int and policy["notBefore"] <= value["notBefore"] <= value["firstUseAt"] <= now <
            value["expiresAt"] <= policy["expiresAt"] and policy["retrievalOwner"] == stages.joint.OWNER_LOGIN,
            "CURRENT_WINDOW")
    blob = hashlib.sha1(b"blob " + str(len(policy_raw)).encode("ascii") + b"\0" + policy_raw).hexdigest()
    require(hashlib.sha256(policy_raw).hexdigest() == stages.POLICY_SHA256 and value["policy"]["blob"] == blob, "POLICY_BYTES")
    event = I.parse(event_raw, I.EVENT_LIMIT)
    repository = I.mapping(event.get("repository"))
    require(repository.get("full_name") == I.REPOSITORY and repository.get("default_branch") == "main" and
            type(event.get("number")) is int and event["number"] == first["number"] and
            event.get("action") in ("opened", "reopened", "synchronize"), "EVENT")
    stages.joint._current_pr(event.get("pull_request"), declaration, first)
    recipient = policy["recipient"]
    declared = {**value["policy"], "fingerprint": recipient["fingerprint"], "keySha256": recipient["sha256"],
                "expiresAt": policy["expiresAt"], "retentionDays": 14}
    raw = I.encoded(_record(value, first, hashlib.sha256(event_raw).hexdigest(), declared))
    return InitialOrdinaryIdentity(raw, event_raw, policy_raw, key, recipient["fingerprint"],
                                   recipient["sha256"], policy["expiresAt"])


def cache_cohort(raw):
    """Closed declaration route, NOT bootstrap selection or native admission.

    None means this is not an initial-ordinary record; other existing readers
    must still validate it. A returned (profile, role) is ORDINARY layout. A
    future seed dispatcher must return None as its bootstrap selection after
    checking this tuple, not feed it to the productive/initializer layout.
    Partial/relabelled Stage2 markers refuse rather than fall through.
    """
    require(type(raw) is bytes, "RECORD_BYTES")
    value = I.parse(raw, I.EVENT_LIMIT)
    github, policy, initial = (value.get(name) for name in ("github", "policy", "initialRecipient"))
    binding = github.get("eventBinding") if type(github) is dict else None
    shared_markers = (type(policy) is dict and "origin" in policy or
                      type(binding) is dict and bool({"originalMain", "policyHead"}.intersection(binding)))
    selected = (value.get("scope") == SCOPE or "firstPullRequest" in value or
                type(initial) is dict and initial.get("scope") == MATCH_SCOPE or
                value.get("profile") in ("desktop", "full") and shared_markers)
    if not selected:
        return None
    profile = value.get("profile")
    require(type(profile) is str and profile in I.PROFILES and
            set(value) == FIELDS | ({"samplePackagingRequired"} if profile == "desktop" else set()) and
            type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == SCOPE, "RECORD_FIELDS")
    cohort = _match(initial, value["firstPullRequest"])
    require(type(policy) is dict and set(policy) == {"origin", "commit", "blob", "path", "sha256", "fingerprint",
            "keySha256", "expiresAt", "retentionDays"} and type(policy["retentionDays"]) is int and
            policy["retentionDays"] == 14 and type(policy["expiresAt"]) is int and
            initial["expiresAt"] <= policy["expiresAt"], "RECORD_POLICY")
    require({name: policy[name] for name in initial["policy"]} == initial["policy"], "RECORD_POLICY_ORIGIN")
    require(type(policy["fingerprint"]) is str and re.fullmatch(r"[0-9A-F]{40}", policy["fingerprint"]), "RECORD_FINGERPRINT")
    stages.digest(policy["keySha256"])
    require(type(github) is dict, "RECORD_GITHUB")
    stages.digest(github.get("eventSha256"))
    # Compare encoded reconstruction as well as the parsed contract: Python's
    # bool/int equality must not let 0 impersonate samplePackagingRequired=False
    # or let a boolean replace a numeric binding in a nested record.
    require(raw == I.encoded(_record(initial, value["firstPullRequest"], github["eventSha256"], policy)),
            "RECORD_BINDINGS")
    return cohort
