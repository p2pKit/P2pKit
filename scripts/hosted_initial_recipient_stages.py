"""Dormant two-stage initial-recipient contracts, NOT acquisition or admission.

Stage 1 has no PR dependency. Stage 2 binds historical Stage 1 records at their
original clocks and new H2/PR identities, never live H1 authority after advance.
All originals are SUPPLIED. Neither a match nor selected qualification hashes
authenticate GitHub, establish qualification, consume a slot or lift a HOLD.
No caller, network, process, key access or workflow activation exists here.
The older joint matcher is unchanged; its scope is not a staged fallback.
"""
from __future__ import annotations

import dataclasses
import hashlib
import re

import hosted_initial_recipient_exception as joint


identity, bootstrap = joint.identity, joint.bootstrap
BASE, SOURCE_REF, POLICY_SHA256 = joint.BASE, joint.SOURCE_REF, joint.POLICY_SHA256
LIMIT = joint.LIMIT
STAGE1 = "P2PKIT_INITIAL_RECIPIENT_BOOTSTRAP_STAGE1_V1"
STAGE2 = "P2PKIT_INITIAL_RECIPIENT_ORDINARY_STAGE2_V1"
COMMANDS = {STAGE1: "/p2pkit authorize-initial-bootstrap ",
            STAGE2: "/p2pkit authorize-initial-ordinary "}
ENVIRONMENT = "initial-recipient-execution"
BRANCHES = (SOURCE_REF.removeprefix("refs/heads/"), "refs/pull/*/merge")
COMMON = "schema scope repository base reviewed sourceRef policySha256 notBefore expiresAt environment"


@dataclasses.dataclass(frozen=True)
class BootstrapMatch:
    record: bytes


@dataclasses.dataclass(frozen=True)
class OrdinaryMatch:
    """Authority/reference binding only; NOT acceptance of referenced evidence."""

    record: bytes


@dataclasses.dataclass(frozen=True)
class BootstrapHistory:
    """Retained supplied originals, not a capability or fresh Stage 1 permission.

    The future reader must prove original acquisition, immutable custody, actual
    completion and current availability. Re-validating these bytes historically
    is necessary but cannot prove those premises or provider qualification.
    """

    comment_raw: bytes
    observation_raw: bytes
    base_policy_entry: bytes
    ancestry_raw: bytes
    candidate_policy_entry: bytes
    candidate_policy_raw: bytes
    completed_at: int
    expected: BootstrapMatch


def require(value, code):
    identity.require(value, "INITIAL_STAGES_" + code)


def fields(value, names, code):
    require(type(value) is dict and set(value) == set(names.split()), code)
    return value


def digest(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "DIGEST")
    return value


def positive(value):
    require(type(value) is int and 0 < value < 10 ** 20, "POSITIVE_ID")
    return value


def environment(value):
    """Owner statement pins real IDs; no environment or placeholder is created."""
    fields(value, "name id branchPolicies", "ENVIRONMENT_FIELDS")
    require(value["name"] == ENVIRONMENT, "ENVIRONMENT_NAME")
    positive(value["id"])
    policies = value["branchPolicies"]
    require(type(policies) is list and len(policies) == 2, "ENVIRONMENT_BRANCHES")
    ids = set()
    for policy, name in zip(policies, BRANCHES):
        fields(policy, "id name type", "ENVIRONMENT_BRANCH_FIELDS")
        positive(policy["id"])
        require(policy["type"] == "branch" and policy["name"] == name and policy["id"] not in ids,
                "ENVIRONMENT_BRANCHES")
        ids.add(policy["id"])
    return value


def statement(stage, comment_raw, comment_id, body_sha256):
    """One exact selected unedited owner comment; never latest/substring search."""
    require(type(stage) is str and stage in COMMANDS, "STAGE")
    positive(comment_id)
    digest(body_sha256)
    require(type(comment_raw) is bytes, "COMMENT_BYTES")
    value = identity.parse(comment_raw, LIMIT)
    api = "https://api.github.com/repos/" + identity.REPOSITORY
    web = "https://github.com/" + identity.REPOSITORY
    require(type(value.get("id")) is int and value["id"] == comment_id and
            value.get("url") == f"{api}/issues/comments/{comment_id}" and
            value.get("issue_url") == f"{api}/issues/{joint.ISSUE}" and
            value.get("html_url") == f"{web}/issues/{joint.ISSUE}#issuecomment-{comment_id}", "COMMENT_LOCATION")
    require(joint.owner(value.get("user")) and "performed_via_github_app" in value and
            value["performed_via_github_app"] is None, "COMMENT_OWNER")
    created = joint.timestamp(value.get("created_at"))
    require(created > 0 and value["created_at"] == value.get("updated_at"), "COMMENT_EDITED")
    body, command = value.get("body"), COMMANDS[stage]
    require(type(body) is str and body.startswith(command) and len(body) <= LIMIT, "COMMENT_BODY")
    try:
        raw = body.encode("ascii")
    except UnicodeError:
        raise identity.AdmissionError("INITIAL_STAGES_COMMENT_BODY") from None
    require(hashlib.sha256(raw).hexdigest() == body_sha256, "COMMENT_DIGEST")
    declaration = identity.parse(raw[len(command):], LIMIT)
    require(body == command + identity.encoded(declaration).decode("ascii").removesuffix("\n"), "COMMENT_ENCODING")
    fields(declaration, COMMON + (" bootstrap" if stage == STAGE1 else
                                 " firstPullRequest stage1 qualifications"), "STATEMENT_FIELDS")
    require(type(declaration["schema"]) is int and declaration["schema"] == 1 and
            declaration["scope"] == stage and declaration["repository"] == identity.REPOSITORY and
            joint.source(declaration["base"]) == BASE and declaration["sourceRef"] == SOURCE_REF and
            declaration["policySha256"] == POLICY_SHA256, "STATEMENT_SCOPE")
    reviewed = joint.source(declaration["reviewed"])
    require(reviewed["commit"] != BASE["commit"] and reviewed["tree"] != BASE["tree"], "REVIEWED_SOURCE")
    environment(declaration["environment"])
    authority = {"id": comment_id, "url": value["html_url"], "bodySha256": body_sha256,
                 "owner": joint.OWNER_LOGIN, "ownerId": joint.OWNER_ID, "createdAt": value["created_at"]}
    return declaration, authority, created


def bootstrap_roster(entries):
    require(type(entries) is list and 1 <= len(entries) <= len(bootstrap.SELECTIONS), "BOOTSTRAP_ROSTER")
    selections, ids = set(), set()
    for entry in entries:
        fields(entry, "selection runId runAttempt", "BOOTSTRAP_RUN_FIELDS")
        bootstrap.selection(entry["selection"])
        run_id, _ = joint.run(entry)
        require(entry["selection"] not in selections and run_id not in ids, "DUPLICATE_BOOTSTRAP")
        selections.add(entry["selection"])
        ids.add(run_id)
    return entries


def ordinary_roster(declaration):
    first = fields(declaration["firstPullRequest"], "number merge runs", "PR_FIELDS")
    joint.number(first["number"])
    merge = joint.source(first["merge"])
    require(merge["commit"] not in (BASE["commit"], declaration["reviewed"]["commit"]) and
            merge["tree"] == declaration["reviewed"]["tree"], "PR_MERGE_SOURCE")
    entries = first["runs"]
    require(type(entries) is list and len(entries) == 4, "ORDINARY_ROSTER")
    pairs, desktops, fulls = set(), set(), set()
    for entry in entries:
        fields(entry, "profile role runId runAttempt", "ORDINARY_RUN_FIELDS")
        profile, role = entry["profile"], entry["role"]
        require(type(profile) is str and type(role) is str and profile in ("desktop", "full") and
                role in joint.ROLES and (profile != "full" or role.startswith("macos-")), "ORDINARY_ROLE")
        require((profile, role) not in pairs, "DUPLICATE_ORDINARY")
        pairs.add((profile, role))
        (desktops if profile == "desktop" else fulls).add(joint.run(entry))
    roles = {role for profile, role in pairs if profile == "desktop"}
    require(len(desktops) == len(fulls) == 1 and len(roles) == 3 and
            {"linux-x64", "windows-x64"} <= roles and len(pairs) == 4, "ORDINARY_ROSTER")
    require(next(iter(desktops))[0] != next(iter(fulls))[0], "DUPLICATE_ORDINARY_RUN")
    return first, pairs


def _policy(declaration, observed, created, base_policy_entry, ancestry_raw,
            candidate_policy_entry, candidate_policy_raw, now):
    require(type(now) is int, "CLOCK")
    require(observed["repository"] == identity.REPOSITORY and joint.source(observed["base"]) == BASE and
            joint.source(observed["reviewed"]) == declaration["reviewed"], "CURRENT_SOURCE")
    joint.source(observed["source"])
    # Empty stdout is admissible ONLY after the future native owner proves the
    # exact original query succeeded completely inside its original fence.
    require(type(base_policy_entry) is bytes and base_policy_entry == b"", "BASE_POLICY_NOT_ABSENT")
    require(type(ancestry_raw) is bytes and ancestry_raw in
            (BASE["commit"].encode("ascii") + b"\n", BASE["commit"].encode("ascii") + b"\r\n"), "BASE_ANCESTRY")
    require(type(candidate_policy_entry) is bytes and len(candidate_policy_entry) <= 256, "POLICY_ENTRY")
    entry = re.fullmatch(rb"100644 blob ([0-9a-f]{40})\t" + re.escape(identity.POLICY_PATH.encode("ascii")) + rb"\x00",
                         candidate_policy_entry)
    require(entry is not None, "POLICY_ENTRY")
    require(type(candidate_policy_raw) is bytes and 0 < len(candidate_policy_raw) <= identity.POLICY_LIMIT and
            hashlib.sha256(candidate_policy_raw).hexdigest() == POLICY_SHA256, "POLICY_DIGEST")
    blob = hashlib.sha1(b"blob " + str(len(candidate_policy_raw)).encode("ascii") + b"\x00" + candidate_policy_raw).hexdigest()
    require(entry.group(1).decode("ascii") == blob, "POLICY_BLOB")
    policy, _ = identity._policy(candidate_policy_raw, now)
    start, end, began = declaration["notBefore"], declaration["expiresAt"], observed["firstUseAt"]
    require(type(start) is int and type(end) is int and type(began) is int and
            policy["notBefore"] <= start <= began <= now < end <= policy["expiresAt"] and
            end - start <= 14 * 24 * 60 * 60 and 0 < created <= began and
            policy["retrievalOwner"] == joint.OWNER_LOGIN, "VALIDITY_OR_PRIOR_AUTHORITY")
    return {"origin": "reviewed-head", "commit": declaration["reviewed"]["commit"], "blob": blob,
            "path": identity.POLICY_PATH, "sha256": POLICY_SHA256}


def _result(kind, stage, declaration, authority, observed, policy, expected, **extra):
    result = kind(identity.encoded({"schema": 1, "scope": stage + "_MATCH_ONLY_NOT_ADMISSION",
        "authority": authority, "originalBase": BASE, "reviewed": declaration["reviewed"],
        "source": observed["source"], "github": observed["github"], "policy": policy,
        "firstUseAt": observed["firstUseAt"], "notBefore": declaration["notBefore"],
        "expiresAt": declaration["expiresAt"], "environment": declaration["environment"], **extra}))
    if expected is not None:
        require(type(expected) is kind and type(expected.record) is bytes and result.record == expected.record,
                "CHANGED_BEFORE_RECHECK")
    return result


def match_bootstrap(*, comment_raw, comment_id, body_sha256, observation_raw, base_policy_entry,
                    ancestry_raw, candidate_policy_entry, candidate_policy_raw, now, expected=None):
    declaration, authority, created = statement(STAGE1, comment_raw, comment_id, body_sha256)
    bootstrap_roster(declaration["bootstrap"])
    require(type(observation_raw) is bytes, "OBSERVATION_BYTES")
    observed = identity.parse(observation_raw, LIMIT)
    # No PR/merge/ordinary field, even a null one: Stage 1 needs no PR/run pair.
    fields(observed, "repository base reviewed source github firstUseAt", "BOOTSTRAP_OBSERVATION_FIELDS")
    policy = _policy(declaration, observed, created, base_policy_entry, ancestry_raw,
                     candidate_policy_entry, candidate_policy_raw, now)
    github = fields(observed["github"], "profile event ref workflow workflowSha job runId runAttempt "
                    "runnerOS runnerArch selection", "BOOTSTRAP_GITHUB_FIELDS")
    joint.run(github)
    slot = {name: github[name] for name in ("selection", "runId", "runAttempt")}
    require(slot in declaration["bootstrap"], "UNLISTED_BOOTSTRAP")
    _, _, system, arch = bootstrap.selection(github["selection"])
    require(observed["source"] == declaration["reviewed"] and
            (github["profile"], github["event"], github["ref"], github["workflow"], github["job"],
             github["runnerOS"], github["runnerArch"], github["workflowSha"]) ==
            (bootstrap.PROFILE, "workflow_dispatch", SOURCE_REF, bootstrap.WORKFLOW, bootstrap.JOB,
             system, arch, declaration["reviewed"]["commit"]), "BOOTSTRAP_EXECUTION")
    return _result(BootstrapMatch, STAGE1, declaration, authority, observed, policy, expected)


def _reference(value, *, maximum):
    fields(value, "bytes sha256", "REFERENCE_FIELDS")
    require(type(value["bytes"]) is int and 0 < value["bytes"] <= maximum, "REFERENCE_SIZE")
    digest(value["sha256"])


def _histories(declaration, pairs, histories, created, prior_ancestry_raw):
    prior = fields(declaration["stage1"], "commentId bodySha256 reviewed", "STAGE1_REFERENCE_FIELDS")
    positive(prior["commentId"])
    digest(prior["bodySha256"])
    source = joint.source(prior["reviewed"])
    require(source["commit"] != declaration["reviewed"]["commit"], "SEPARATE_REVIEWED_HEADS")
    require(type(prior_ancestry_raw) is bytes and prior_ancestry_raw in
            (source["commit"].encode("ascii") + b"\n", source["commit"].encode("ascii") + b"\r\n"), "STAGE1_ANCESTRY")
    entries = declaration["qualifications"]
    require(type(entries) is list and len(entries) == 4 and type(histories) is tuple and len(histories) == 4,
            "QUALIFICATION_ROSTER")
    covered, ids, artifacts, retained = set(), set(), set(), []
    ordinary_ids = {x["runId"] for x in declaration["firstPullRequest"]["runs"]}
    for entry, history in zip(entries, histories):
        fields(entry, "selection runId runAttempt completedAt packet inventory compatibility review", "QUALIFICATION_FIELDS")
        profile, role, _, _ = bootstrap.selection(entry["selection"])
        run_id, _ = joint.run(entry)
        require((profile, role) in pairs and (profile, role) not in covered and
                run_id not in ids | ordinary_ids, "QUALIFICATION_COHORT_OR_RUN")
        covered.add((profile, role))
        ids.add(run_id)
        # These bind references, not the contents/truth of an encrypted packet
        # or its independent review. The later reader must inspect all originals
        # and compatibility, not accept a digest/cache-key/save/probe as proof.
        packet = fields(entry["packet"], "artifactId bytes sha256", "PACKET_FIELDS")
        positive(packet["artifactId"])
        require(packet["artifactId"] not in artifacts, "DUPLICATE_PACKET")
        artifacts.add(packet["artifactId"])
        _reference({name: packet[name] for name in ("bytes", "sha256")}, maximum=512 * 1024 * 1024)
        for name in ("inventory", "compatibility", "review"):
            _reference(entry[name], maximum=4 * 1024 * 1024)
        require(type(history) is BootstrapHistory and type(history.expected) is BootstrapMatch and
                type(history.expected.record) is bytes, "HISTORICAL_RECORD_TYPE")
        require(type(entry["completedAt"]) is int and type(history.completed_at) is int and
                0 < history.completed_at == entry["completedAt"] < created, "QUALIFICATION_BEFORE_AUTHORITY")
        # Historical check: deliberately use the original completed_at and H1
        # originals, never current H2/now as a pretend renewed Stage 1 admission.
        checked = match_bootstrap(comment_raw=history.comment_raw, comment_id=prior["commentId"],
            body_sha256=prior["bodySha256"], observation_raw=history.observation_raw,
            base_policy_entry=history.base_policy_entry, ancestry_raw=history.ancestry_raw,
            candidate_policy_entry=history.candidate_policy_entry, candidate_policy_raw=history.candidate_policy_raw,
            now=history.completed_at, expected=history.expected)
        value = identity.parse(checked.record, LIMIT)
        require(value["reviewed"] == source and value["environment"] == declaration["environment"] and
                all(value["github"][name] == entry[name] for name in ("selection", "runId", "runAttempt")),
                "HISTORICAL_SOURCE_OR_USE")
        retained.append({"selection": entry["selection"], "recordSha256": hashlib.sha256(checked.record).hexdigest()})
    require(covered == pairs, "MISSING_QUALIFICATION_COHORT")
    return retained


def match_ordinary(*, comment_raw, comment_id, body_sha256, observation_raw, base_policy_entry,
                   ancestry_raw, candidate_policy_entry, candidate_policy_raw, now,
                   histories, prior_ancestry_raw, expected=None):
    """Stage 2 match/reference binding, NOT qualification of selected packets.

    Productive integration must separately obtain/validate current originals,
    full artifact inventory, decryption-independent ciphertext bindings and the
    retained independent qualification review. Compare relevant H1/H2 dependency
    inputs, executable validation suppliers, provider path/version/compression/
    ref compatibility; a matching reusable key or this result is insufficient.
    This function cannot issue ordinary Admission, restore or execute anything.
    """
    declaration, authority, created = statement(STAGE2, comment_raw, comment_id, body_sha256)
    first, pairs = ordinary_roster(declaration)
    require(type(observation_raw) is bytes, "OBSERVATION_BYTES")
    observed = identity.parse(observation_raw, LIMIT)
    fields(observed, "repository base reviewed source github firstUseAt pullRequest mergeParents", "ORDINARY_OBSERVATION_FIELDS")
    policy = _policy(declaration, observed, created, base_policy_entry, ancestry_raw,
                     candidate_policy_entry, candidate_policy_raw, now)
    github = fields(observed["github"], "profile event ref workflow workflowSha job runId runAttempt runnerOS runnerArch",
                    "ORDINARY_GITHUB_FIELDS")
    joint.run(github)
    joint._current_pr(observed["pullRequest"], declaration, first)
    require(observed["source"] == first["merge"] and observed["mergeParents"] ==
            [BASE["commit"], declaration["reviewed"]["commit"]], "ORDINARY_MERGE")
    roles = [role for role, host in joint.ROLES.items() if host == (github["runnerOS"], github["runnerArch"])]
    require(len(roles) == 1 and type(github["profile"]) is str and github["profile"] in identity.PROFILES, "ORDINARY_HOST")
    slot = {"profile": github["profile"], "role": roles[0], "runId": github["runId"], "runAttempt": github["runAttempt"]}
    require(slot in first["runs"], "UNLISTED_ORDINARY")
    workflow, job, _ = identity.PROFILES[github["profile"]]
    require((github["event"], github["ref"], github["workflow"], github["job"], github["workflowSha"]) ==
            ("pull_request", f"refs/pull/{first['number']}/merge", workflow, job, first["merge"]["commit"]), "ORDINARY_EXECUTION")
    retained = _histories(declaration, pairs, histories, created, prior_ancestry_raw)
    return _result(OrdinaryMatch, STAGE2, declaration, authority, observed, policy, expected,
                   stage1=declaration["stage1"], qualifications=declaration["qualifications"],
                   historicalRecords=retained, qualificationAcceptance="NOT_ESTABLISHED_BY_REFERENCE_MATCH")
