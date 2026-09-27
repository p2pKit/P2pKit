"""Distinct Stage2 worker binding; reference-only, NOT ordinary Admission.

This does not turn a supplied OrdinaryMatch or successful gate into productive
qualification. The actual native caller must separately prove current original
acquisition, known return, recipient validation and all four genuine compatible
bootstrap packets. Retained records alone confer no native/controller authority.
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
JVM_SCOPE = "JVM_LIBRARY_INITIAL_RECIPIENT_IDENTITY_V1"
JVM_MATCH_SCOPE = stages.JVM_MATCH_SCOPE
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


@dataclass(frozen=True)
class InitialJvmLibraryIdentity:
    """Distinct JVM worker DATA, never OrdinaryMatch, Admission or live current."""
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
    return _worker_match(value, first, jvm=False)


def _worker_match(value, first, *, jvm):
    require(type(jvm) is bool, "MATCH_WORKER_KIND")
    require(type(value) is dict and set(value) == MATCH_FIELDS and type(value["schema"]) is int and
            value["schema"] == 1 and value["scope"] == (JVM_MATCH_SCOPE if jvm else MATCH_SCOPE) and
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
    require(type(github["profile"]) is str and
            (github["profile"] == I.JVM_PROFILE if jvm else github["profile"] in I.PROFILES), "PROFILE")
    profile = github["profile"]
    roles = [role for role, host in stages.joint.ROLES.items() if host == (github["runnerOS"], github["runnerArch"])]
    require(len(roles) == 1, "HOST")
    role = roles[0]
    slot = {"role": role, "runId": github["runId"], "runAttempt": github["runAttempt"]}
    if not jvm:
        slot["profile"] = profile
    require(slot in first["jvmRuns" if jvm else "runs"], "WORKER_SLOT")
    I.worker_host(profile, (github["runnerOS"], github["runnerArch"]))
    workflow, job, _ = I.worker_contract(profile)
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
    return _worker_record(match, first, event_sha256, policy, jvm=False)


def _worker_record(match, first, event_sha256, policy, *, jvm):
    require(type(jvm) is bool and (match["github"]["profile"] == I.JVM_PROFILE if jvm else
            match["github"]["profile"] in I.PROFILES), "RECORD_WORKER_KIND")
    profile = match["github"]["profile"]
    github = {name: value for name, value in match["github"].items() if name != "profile"}
    value = {"schema": 1, "scope": JVM_SCOPE if jvm else SCOPE, "profile": profile,
        "suites": list(I.worker_contract(profile)[2]),
        "source": match["source"], "github": {**github, "repository": I.REPOSITORY, "eventSha256": event_sha256,
            "eventBinding": {"number": first["number"], "base": stages.BASE["commit"],
                "head": match["reviewed"]["commit"], "headRepository": I.REPOSITORY,
                "originalMain": stages.BASE["commit"], "policyHead": match["reviewed"]["commit"]}},
        "policy": policy, "initialRecipient": match, "firstPullRequest": first}
    if profile == "desktop":
        value["samplePackagingRequired"] = False  # First PR is never main publication.
    if jvm:
        value["cacheCohort"] = {"profile": "desktop", "role":
            I.worker_host(profile, (github["runnerOS"], github["runnerArch"]))}
    return value


def bind_worker_match(match, *, comment_raw, event_raw, policy_raw, now):
    """Bind supplied originals without claiming they were acquired/qualified.

    The retained exact C2 roster is necessary: OrdinaryMatch alone does not
    contain the complete first-PR run roster. Native callers cannot skip the
    original comment, current approval/environment or full historical checks.
    """
    return _bind_worker_match(match, comment_raw=comment_raw, event_raw=event_raw, policy_raw=policy_raw, now=now,
                              jvm=False)


def bind_jvm_worker_match(match, *, comment_raw, event_raw, policy_raw, now):
    return _bind_worker_match(match, comment_raw=comment_raw, event_raw=event_raw, policy_raw=policy_raw, now=now,
                              jvm=True)


def _bind_worker_match(match, *, comment_raw, event_raw, policy_raw, now, jvm):
    require(type(jvm) is bool and type(match) is (stages.JvmLibraryMatch if jvm else stages.OrdinaryMatch) and
            type(match.record) is bytes and
            type(comment_raw) is bytes and type(event_raw) is bytes and type(policy_raw) is bytes, "ORIGINAL_TYPES")
    value = I.parse(match.record, stages.LIMIT)
    require(set(value) == MATCH_FIELDS and match.record == I.encoded(value), "MATCH_ENCODING")
    authority = stages.fields(value["authority"], "id url bodySha256 owner ownerId createdAt", "AUTHORITY_FIELDS")
    declaration, original_authority, _ = stages.statement(stages.STAGE2, comment_raw, authority["id"], authority["bodySha256"])
    first = declaration["firstPullRequest"]
    _worker_match(value, first, jvm=jvm)
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
    raw = I.encoded(_worker_record(value, first, hashlib.sha256(event_raw).hexdigest(), declared, jvm=jvm))
    kind = InitialJvmLibraryIdentity if jvm else InitialOrdinaryIdentity
    return kind(raw, event_raw, policy_raw, key, recipient["fingerprint"], recipient["sha256"], policy["expiresAt"])


def cache_cohort(raw):
    """Closed declaration route, NOT bootstrap selection or native admission.

    None means this is not an initial-ordinary record; other existing readers
    must still validate it. A returned (profile, role) is ORDINARY layout. A
    future seed dispatcher must return None as its bootstrap selection after
    checking this tuple, not feed it to the productive/initializer layout.
    Partial/relabelled Stage2 markers refuse rather than fall through.
    """
    return _cache_cohort(raw, jvm=False)


def jvm_cache_cohort(raw):
    """Initial JVM bytes only; no ordinary-admission or bootstrap fallback."""
    return _cache_cohort(raw, jvm=True)


def _cache_cohort(raw, *, jvm):
    require(type(jvm) is bool and type(raw) is bytes, "RECORD_BYTES")
    value = I.parse(raw, I.EVENT_LIMIT)
    github, policy, initial = (value.get(name) for name in ("github", "policy", "initialRecipient"))
    binding = github.get("eventBinding") if type(github) is dict else None
    shared_markers = (type(policy) is dict and "origin" in policy or
                      type(binding) is dict and bool({"originalMain", "policyHead"}.intersection(binding)))
    if jvm:
        selected = (value.get("scope") == JVM_SCOPE or
                    type(initial) is dict and initial.get("scope") == JVM_MATCH_SCOPE or
                    value.get("profile") == I.JVM_PROFILE and
                    (shared_markers or "firstPullRequest" in value or "initialRecipient" in value))
    else:
        selected = (value.get("scope") == SCOPE or "firstPullRequest" in value or
                    type(initial) is dict and initial.get("scope") == MATCH_SCOPE or
                    value.get("profile") in ("desktop", "full") and shared_markers)
    if not selected:
        return None
    profile = value.get("profile")
    extra = {"cacheCohort"} if jvm else ({"samplePackagingRequired"} if profile == "desktop" else set())
    require(type(profile) is str and (profile == I.JVM_PROFILE if jvm else profile in I.PROFILES) and
            set(value) == FIELDS | extra and type(value["schema"]) is int and value["schema"] == 1 and
            value["scope"] == (JVM_SCOPE if jvm else SCOPE), "RECORD_FIELDS")
    execution, role = _worker_match(initial, value["firstPullRequest"], jvm=jvm)
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
    require(raw == I.encoded(_worker_record(initial, value["firstPullRequest"], github["eventSha256"], policy, jvm=jvm)),
            "RECORD_BINDINGS")
    return "desktop" if jvm else execution, role


def worker_cohort(raw):
    """Closed dispatch between distinct retained initial worker identities."""
    selected = jvm_cache_cohort(raw)
    return selected if selected is not None else cache_cohort(raw)


def retained_identity(record_raw, event_raw, policy_raw, public_key, *, now):
    """Validate retained Stage2 DATA; never hydrate a current or Admission.

    This leaf is also used by isolated provider/crypto readers. It has no HTTP,
    native owner, token, registry or permission to execute. Its caller must
    separately establish real local source and, at acceptance, genuine current.
    """
    return _retained_identity(record_raw, event_raw, policy_raw, public_key, now=now, jvm=False)


def retained_jvm_identity(record_raw, event_raw, policy_raw, public_key, *, now):
    return _retained_identity(record_raw, event_raw, policy_raw, public_key, now=now, jvm=True)


def retained_worker_identity(record_raw, event_raw, policy_raw, public_key, *, now):
    selected = jvm_cache_cohort(record_raw)
    return _retained_identity(record_raw, event_raw, policy_raw, public_key, now=now, jvm=selected is not None)


def _retained_identity(record_raw, event_raw, policy_raw, public_key, *, now, jvm):
    require(type(jvm) is bool and all(type(raw) is bytes for raw in (record_raw, event_raw, policy_raw, public_key)),
            "RETAINED_ORIGINAL_TYPES")
    require(_cache_cohort(record_raw, jvm=jvm) is not None, "RETAINED_STAGE2_REQUIRED")
    value = I.parse(record_raw, I.EVENT_LIMIT)
    match, first = value["initialRecipient"], value["firstPullRequest"]
    policy, key = I._policy(policy_raw, now)
    require(type(now) is int and policy["notBefore"] <= match["notBefore"] <= match["firstUseAt"] <= now <
            match["expiresAt"] <= policy["expiresAt"] and policy["retrievalOwner"] == stages.joint.OWNER_LOGIN,
            "RETAINED_CURRENT_WINDOW")
    recipient = policy["recipient"]
    blob = hashlib.sha1(b"blob " + str(len(policy_raw)).encode("ascii") + b"\0" + policy_raw).hexdigest()
    require(hashlib.sha256(policy_raw).hexdigest() == stages.POLICY_SHA256 and
            match["policy"]["blob"] == blob and key == public_key and
            hashlib.sha256(key).hexdigest() == recipient["sha256"], "RETAINED_POLICY_OR_KEY")
    declared = {**match["policy"], "fingerprint": recipient["fingerprint"], "keySha256": recipient["sha256"],
                "expiresAt": policy["expiresAt"], "retentionDays": 14}
    require(I.encoded(declared) == I.encoded(value["policy"]), "RETAINED_POLICY_BINDING")
    require(len(event_raw) <= I.EVENT_LIMIT and hashlib.sha256(event_raw).hexdigest() ==
            value["github"]["eventSha256"], "RETAINED_EVENT_BYTES")
    event = I.parse(event_raw, I.EVENT_LIMIT)
    repository = I.mapping(event.get("repository"))
    require(repository.get("full_name") == I.REPOSITORY and repository.get("default_branch") == "main" and
            type(event.get("number")) is int and event["number"] == first["number"] and
            event.get("action") in ("opened", "reopened", "synchronize"), "RETAINED_EVENT")
    stages.joint._current_pr(event.get("pull_request"), _declaration(match, first), first)
    require(record_raw == I.encoded(_worker_record(match, first, hashlib.sha256(event_raw).hexdigest(), declared, jvm=jvm)),
            "RETAINED_IDENTITY_BINDING")
    kind = InitialJvmLibraryIdentity if jvm else InitialOrdinaryIdentity
    return kind(record_raw, event_raw, policy_raw, public_key, recipient["fingerprint"], recipient["sha256"],
                policy["expiresAt"])


def retained_current(raw, bound, role):
    """Closed worker-current DATA, never a reconstructed live registry handle.

    History, provider and crypto readers all require the same exact roster.
    Native/current ownership and currency must still be proved by their actual
    callers; hashes here neither perform those checks nor grant execution.
    """
    return _retained_current(raw, bound, role, jvm=False)


def retained_jvm_current(raw, bound, role):
    return _retained_current(raw, bound, role, jvm=True)


def retained_worker_current(raw, bound, role):
    require(type(bound) in (InitialOrdinaryIdentity, InitialJvmLibraryIdentity), "CURRENT_WORKER_TYPE")
    return _retained_current(raw, bound, role, jvm=type(bound) is InitialJvmLibraryIdentity)


def _retained_current(raw, bound, role, *, jvm):
    require(type(jvm) is bool and type(raw) is bytes and
            type(bound) is (InitialJvmLibraryIdentity if jvm else InitialOrdinaryIdentity),
            "CURRENT_DATA_TYPES")
    record = I.parse(bound.record, 4 * 1024 * 1024)
    require(_cache_cohort(bound.record, jvm=jvm) == ("desktop" if jvm else record["profile"], role),
            "CURRENT_DATA_COHORT")
    value = I.parse(raw, 4 * 1024 * 1024)
    keys = {"schema", "scope", "contextSha256", "source", "reviewed", "kind", "profile", "role",
        "matchSha256", "identitySha256", "qualifications", "ownerCloseSha256", "nativeReturnSha256", "pendingSha256",
        "ordinaryAcceptance", "h2ProviderAcceptance", "cryptoAcceptance", "budgetAcceptance", "publicationAuthority"}
    require(type(value) is dict and set(value) == keys and raw == I.encoded(value) and
            type(value["schema"]) is int and value["schema"] == 1 and
            value["scope"] == "INITIAL_ORDINARY_ORIGINAL_CURRENT_SOURCE_V1" and value["kind"] == "worker" and
            value["source"] == record["source"] and value["reviewed"] == record["initialRecipient"]["reviewed"] and
            value["profile"] == record["profile"] and value["role"] == role and
            value["matchSha256"] == hashlib.sha256(I.encoded(record["initialRecipient"])).hexdigest() and
            value["identitySha256"] == hashlib.sha256(bound.record).hexdigest() and
            all(value[name] == "NOT_PERFORMED" for name in
                ("ordinaryAcceptance", "h2ProviderAcceptance", "cryptoAcceptance")) and
            value["budgetAcceptance"] == "NOT_ADMITTED" and value["publicationAuthority"] is False,
            "CURRENT_DATA_BINDING")
    for name in ("contextSha256", "matchSha256", "identitySha256", "ownerCloseSha256", "nativeReturnSha256", "pendingSha256"):
        stages.digest(value[name])
    require(type(value["qualifications"]) is list and len(value["qualifications"]) == 4 and
            all(type(sha) is str and re.fullmatch(r"[0-9a-f]{64}", sha) for sha in value["qualifications"]),
            "CURRENT_DATA_QUALIFICATIONS")
    return value
