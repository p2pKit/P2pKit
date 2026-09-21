"""Explicit Stage1 worker identity; never trusted-main or productive admission.

The pure binding/reader below cannot authenticate supplied Match/event/policy
bytes. The native original-acquisition owner is the only current caller; it
binds this identity to its actual worker return. Neither this type nor a copied
record is accepted by the existing trusted-main bootstrap/ordinary admission
or exporters. Repeated original authority acquisition and job-budget admission
remain necessary before productive use; no workflow invokes this path.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib

import hosted_initial_recipient_stages as stages


I, B = stages.identity, stages.bootstrap
SCOPE = "CACHE_BOOTSTRAP_INITIAL_RECIPIENT_IDENTITY_V1"
MATCH_SCOPE = stages.STAGE1 + "_MATCH_ONLY_NOT_ADMISSION"
FIELDS = {"schema", "scope", "profile", "selection", "cacheCohort", "producerCommand", "producerScope",
          "testAcceptance", "source", "github", "policy", "initialRecipient"}
MATCH_FIELDS = {"schema", "scope", "authority", "originalBase", "reviewed", "source", "github", "policy",
                "firstUseAt", "notBefore", "expiresAt", "environment"}


@dataclass(frozen=True)
class InitialBootstrapIdentity:
    """Immutable source binding, deliberately NOT ordinary.Admission.

    Original native return is separate from this serializable value. A future
    reader may not construct original custody from this type or its bytes.
    """
    record: bytes = field(repr=False)
    original_event: bytes = field(repr=False)
    original_policy: bytes = field(repr=False)
    public_key: bytes = field(repr=False)
    fingerprint: str
    key_sha256: str
    expires_at: int


def require(value, code):
    I.require(value, "INITIAL_BOOTSTRAP_IDENTITY_" + code)


def _match(value):
    """Closed declaration checks, not another authority acquisition."""
    require(type(value) is dict and set(value) == MATCH_FIELDS and type(value["schema"]) is int and
            value["schema"] == 1 and value["scope"] == MATCH_SCOPE, "MATCH_FIELDS")
    require(value["originalBase"] == stages.BASE and stages.joint.source(value["reviewed"]) ==
            stages.joint.source(value["source"]) and value["source"]["commit"] != stages.BASE["commit"] and
            value["source"]["tree"] != stages.BASE["tree"], "MATCH_SOURCE")
    stages.environment(value["environment"])
    authority = stages.fields(value["authority"], "id url bodySha256 owner ownerId createdAt", "AUTHORITY_FIELDS")
    stages.positive(authority["id"])
    stages.digest(authority["bodySha256"])
    require(authority["owner"] == stages.joint.OWNER_LOGIN and type(authority["ownerId"]) is int and
            authority["ownerId"] == stages.joint.OWNER_ID and authority["url"] ==
            "https://github.com/" + I.REPOSITORY + "/issues/437#issuecomment-" + str(authority["id"]), "AUTHORITY")
    created = stages.joint.timestamp(authority["createdAt"])
    start, first, end = (value[name] for name in ("notBefore", "firstUseAt", "expiresAt"))
    require(all(type(x) is int for x in (start, first, end)) and 0 < created <= first and
            0 < start <= first < end and end - start <= 14 * 24 * 60 * 60, "MATCH_WINDOW")
    github = stages.fields(value["github"], "profile event ref workflow workflowSha job runId runAttempt "
                           "runnerOS runnerArch selection", "GITHUB_FIELDS")
    stages.joint.run(github)
    profile, role, system, arch = B.selection(github["selection"])
    require((github["profile"], github["event"], github["ref"], github["workflow"], github["workflowSha"],
             github["job"], github["runnerOS"], github["runnerArch"]) ==
            (B.PROFILE, "workflow_dispatch", stages.SOURCE_REF, B.WORKFLOW, value["source"]["commit"],
             B.JOB, system, arch), "WORKER_ONLY")
    policy = stages.fields(value["policy"], "origin commit blob path sha256", "POLICY_FIELDS")
    require(policy == {"origin": "reviewed-head", "commit": value["reviewed"]["commit"],
            "blob": I.sha(policy["blob"]), "path": I.POLICY_PATH, "sha256": stages.POLICY_SHA256}, "POLICY_ORIGIN")
    return profile, role


def _record(match, event_sha256, policy):
    profile, role = _match(match)
    github = match["github"]
    return {"schema": 1, "scope": SCOPE, "profile": B.PROFILE, "selection": github["selection"],
        "cacheCohort": {"profile": profile, "role": role}, "producerCommand": list(B.COMMAND),
        "producerScope": B.PRODUCER_SCOPE, "testAcceptance": "NOT_PERFORMED", "source": match["source"],
        "github": {**{name: github[name] for name in ("event", "ref", "workflow", "workflowSha", "job", "runId",
                       "runAttempt", "runnerOS", "runnerArch")}, "repository": I.REPOSITORY,
                   "eventSha256": event_sha256, "eventBinding": {
                       "originalMain": stages.BASE["commit"], "policyHead": match["reviewed"]["commit"],
                       "selection": github["selection"], "expectedCommit": match["source"]["commit"],
                       "expectedTree": match["source"]["tree"]}},
        "policy": policy, "initialRecipient": match}


def bind_worker_match(match, *, event_raw, policy_raw, now):
    """Pure input binding; the native caller separately proves original custody.

    Do not call this instead of acquiring/validating original authority, native
    source, the original empty-base query, or the actual enclosing return.
    """
    require(type(match) is stages.BootstrapMatch and type(match.record) is bytes and
            type(event_raw) is bytes and type(policy_raw) is bytes, "ORIGINAL_TYPES")
    value = I.parse(match.record, stages.LIMIT)
    require(match.record == I.encoded(value), "MATCH_ENCODING")
    _match(value)
    policy, key = I._policy(policy_raw, now)
    require(type(now) is int and policy["notBefore"] <= value["notBefore"] <= value["firstUseAt"] <= now <
            value["expiresAt"] <= policy["expiresAt"] and policy["retrievalOwner"] == stages.joint.OWNER_LOGIN,
            "CURRENT_WINDOW")
    blob = hashlib.sha1(b"blob " + str(len(policy_raw)).encode("ascii") + b"\0" + policy_raw).hexdigest()
    require(hashlib.sha256(policy_raw).hexdigest() == stages.POLICY_SHA256 and value["policy"]["blob"] == blob,
            "POLICY_BYTES")
    event = I.parse(event_raw, I.EVENT_LIMIT)
    repository = I.mapping(event.get("repository"))
    require(repository.get("full_name") == I.REPOSITORY and repository.get("default_branch") == "main" and
            event.get("ref") in (stages.SOURCE_REF, stages.SOURCE_REF.removeprefix("refs/heads/")) and
            event.get("inputs") == {"selection": value["github"]["selection"],
                "expected_sha": value["source"]["commit"], "expected_tree": value["source"]["tree"]}, "EVENT")
    recipient = policy["recipient"]
    declared = {**value["policy"], "fingerprint": recipient["fingerprint"], "keySha256": recipient["sha256"],
                "expiresAt": policy["expiresAt"], "retentionDays": 14}
    raw = I.encoded(_record(value, hashlib.sha256(event_raw).hexdigest(), declared))
    return InitialBootstrapIdentity(raw, event_raw, policy_raw, key, recipient["fingerprint"],
                                    recipient["sha256"], policy["expiresAt"])


def cache_cohort(raw):
    """Explicit pre-budget route; None means the unchanged legacy reader must run.

    This checks declarations only. It admits neither a native worker nor a
    producer/exporter. Initial-recipient markers cannot fall through to ordinary
    or trusted-main bootstrap handling if the top-level scope was relabelled.
    """
    require(type(raw) is bytes, "RECORD_BYTES")
    value = I.parse(raw, I.EVENT_LIMIT)
    github, policy = value.get("github"), value.get("policy")
    binding = github.get("eventBinding") if type(github) is dict else None
    initial = (value.get("scope") == SCOPE or "initialRecipient" in value or
               type(policy) is dict and "origin" in policy or
               type(binding) is dict and bool({"originalMain", "policyHead"}.intersection(binding)))
    if not initial:
        return None
    require(set(value) == FIELDS and type(value["schema"]) is int and value["schema"] == 1 and
            value["scope"] == SCOPE and value["profile"] == B.PROFILE, "RECORD_FIELDS")
    cohort = _match(value["initialRecipient"])
    require(type(policy) is dict and set(policy) == {"origin", "commit", "blob", "path", "sha256", "fingerprint",
            "keySha256", "expiresAt", "retentionDays"} and type(policy["retentionDays"]) is int and
            policy["retentionDays"] == 14 and type(policy["expiresAt"]) is int and
            value["initialRecipient"]["expiresAt"] <= policy["expiresAt"], "RECORD_POLICY")
    require({name: policy[name] for name in value["initialRecipient"]["policy"]} ==
            value["initialRecipient"]["policy"], "RECORD_POLICY_ORIGIN")
    require(type(policy["fingerprint"]) is str and len(policy["fingerprint"]) == 40 and
            all(char in "0123456789ABCDEF" for char in policy["fingerprint"]), "RECORD_FINGERPRINT")
    stages.digest(policy["keySha256"])
    require(type(github) is dict, "RECORD_GITHUB")
    event_sha256 = github.get("eventSha256")
    stages.digest(event_sha256)
    require(value == _record(value["initialRecipient"], event_sha256, policy) and raw == I.encoded(value),
            "RECORD_BINDINGS")
    return cohort
