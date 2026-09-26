"""Dormant initial-recipient statement matcher; NOT an admission or trust reader.

All inputs are supplied records. This module acquires nothing, authenticates no
GitHub response, starts no process and returns no ordinary Admission. A future
reviewed caller must obtain/retain fresh originals and enforce the real hosted
identity, native ownership, first-use clock, HOLDs and independent source review.
An exact finite run/attempt roster permits idempotent rechecks, not a claim of
exactly-once execution. No production caller or exception activation exists.
"""
from __future__ import annotations

import dataclasses
import datetime
import hashlib
import re

import hosted_cache_bootstrap_identity as bootstrap
import hosted_test_identity as identity


SCOPE = "P2PKIT_INITIAL_RECIPIENT_EXCEPTION_V1"
COMMAND = "/p2pkit authorize-initial-recipient "
OWNER_LOGIN, OWNER_ID, ISSUE = "Apdelrahman1911", 104788132, 437
BASE = {"commit": "3bc76f956f8f47447b51a62474fc878b9c43173c",
        "tree": "2a1105fde1d1ac299448489501e29d7a0d4a407a"}
# One-time Foundation lane only. Historical campaign statements are not
# authority for this source; the actual final commit/tree still need fresh
# personal authorization and independently acquired original evidence.
SOURCE_REF = "refs/heads/work/release-foundation-20260926-1WzHcOIr"
POLICY_SHA256 = "2e90a1ed038d5bb6759d8d22e1bb5468331b49274a6956df470c1e785691f521"
LIMIT = 64 * 1024
ROLES = {"linux-x64": ("Linux", "X64"), "windows-x64": ("Windows", "X64"),
         "macos-arm64": ("macOS", "ARM64"), "macos-x64": ("macOS", "X64")}


@dataclasses.dataclass(frozen=True)
class Match:
    """Stable byte binding only. Original API/query captures need separate custody."""

    record: bytes


def require(value, code):
    identity.require(value, "INITIAL_RECIPIENT_" + code)


def fields(value, names, code):
    require(type(value) is dict and set(value) == set(names.split()), code)
    return value


def source(value):
    fields(value, "commit tree", "SOURCE_FIELDS")
    identity.sha(value["commit"])
    identity.sha(value["tree"])
    return value


def number(value):
    require(type(value) is int and 0 < value <= 10 ** 10, "NUMBER")
    return value


def run(value):
    for name in ("runId", "runAttempt"):
        require(type(value.get(name)) is str and identity.ID.fullmatch(value[name]), "RUN")
    return value["runId"], value["runAttempt"]


def owner(value):
    return (type(value) is dict and value.get("login") == OWNER_LOGIN and
            type(value.get("id")) is int and value["id"] == OWNER_ID and value.get("type") == "User")


def timestamp(value):
    require(type(value) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value),
            "COMMENT_TIME")
    try:
        return int(datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc).timestamp())
    except ValueError:
        raise identity.AdmissionError("INITIAL_RECIPIENT_COMMENT_TIME") from None


def statement(comment_raw, comment_id, body_sha256):
    """Check one explicitly selected, recorded-unedited owner comment, not latest."""
    require(type(comment_id) is int and 0 < comment_id < 10 ** 20, "COMMENT_ID")
    require(type(body_sha256) is str and re.fullmatch(r"[0-9a-f]{64}", body_sha256), "COMMENT_DIGEST")
    value = identity.parse(comment_raw, LIMIT)
    api = "https://api.github.com/repos/" + identity.REPOSITORY
    web = "https://github.com/" + identity.REPOSITORY
    require(type(value.get("id")) is int and value["id"] == comment_id and
            value.get("url") == f"{api}/issues/comments/{comment_id}" and
            value.get("issue_url") == f"{api}/issues/{ISSUE}" and
            value.get("html_url") == f"{web}/issues/{ISSUE}#issuecomment-{comment_id}", "COMMENT_LOCATION")
    require(owner(value.get("user")) and "performed_via_github_app" in value and
            value["performed_via_github_app"] is None, "COMMENT_OWNER")
    created = timestamp(value.get("created_at"))
    require(created > 0 and value.get("created_at") == value.get("updated_at"), "COMMENT_EDITED")
    body = value.get("body")
    require(type(body) is str and body.startswith(COMMAND) and len(body) <= LIMIT, "COMMENT_BODY")
    try:
        raw = body.encode("utf-8")
    except UnicodeError:
        raise identity.AdmissionError("INITIAL_RECIPIENT_COMMENT_BODY") from None
    require(hashlib.sha256(raw).hexdigest() == body_sha256, "COMMENT_DIGEST")
    declaration = identity.parse(raw[len(COMMAND):], LIMIT)
    # One exact ASCII command, no Markdown fence/prose/whitespace aliases. Extra
    # REST metadata (e.g. reactions) is not mistaken for edited authorization.
    require(body == COMMAND + identity.encoded(declaration).decode("ascii").removesuffix("\n"), "COMMENT_ENCODING")
    fields(declaration, "schema scope repository base reviewed sourceRef policySha256 notBefore expiresAt "
                       "bootstrap firstPullRequest", "STATEMENT_FIELDS")
    require(type(declaration["schema"]) is int and declaration["schema"] == 1 and
            declaration["scope"] == SCOPE and declaration["repository"] == identity.REPOSITORY and
            source(declaration["base"]) == BASE and declaration["sourceRef"] == SOURCE_REF and
            declaration["policySha256"] == POLICY_SHA256, "STATEMENT_SCOPE")
    reviewed = source(declaration["reviewed"])
    require(reviewed["commit"] != BASE["commit"] and reviewed["tree"] != BASE["tree"], "REVIEWED_SOURCE")
    return declaration, {"id": comment_id, "url": value["html_url"], "bodySha256": body_sha256,
                         "owner": OWNER_LOGIN, "ownerId": OWNER_ID, "createdAt": value["created_at"]}, created


def roster(declaration):
    """One bootstrap run per named selection, one first-PR Desktop/FULL run pair."""
    first = fields(declaration["firstPullRequest"], "number merge runs", "PR_FIELDS")
    number(first["number"])
    merged = source(first["merge"])
    require(merged["commit"] not in (BASE["commit"], declaration["reviewed"]["commit"]) and
            merged["tree"] == declaration["reviewed"]["tree"], "PR_MERGE_SOURCE")
    entries = first["runs"]
    require(type(entries) is list and len(entries) == 4, "PR_RUN_ROSTER")
    pairs, desktops, fulls = set(), set(), set()
    for entry in entries:
        fields(entry, "profile role runId runAttempt", "PR_RUN_FIELDS")
        require(type(entry["profile"]) is str and type(entry["role"]) is str and
                entry["profile"] in ("desktop", "full") and entry["role"] in ROLES and
                (entry["profile"] != "full" or entry["role"].startswith("macos-")), "PR_RUN_ROLE")
        pair = entry["profile"], entry["role"]
        require(pair not in pairs, "DUPLICATE_USE")
        pairs.add(pair)
        (desktops if pair[0] == "desktop" else fulls).add(run(entry))
    desktop_roles = {role for profile, role in pairs if profile == "desktop"}
    require(len(desktops) == len(fulls) == 1 and len(desktop_roles) == 3 and
            {"linux-x64", "windows-x64"} <= desktop_roles and
            len([pair for pair in pairs if pair[0] == "full"]) == 1, "PR_RUN_ROSTER")
    desktop, full = next(iter(desktops)), next(iter(fulls))
    require(desktop[0] != full[0], "DUPLICATE_RUN")
    seeds = declaration["bootstrap"]
    require(type(seeds) is list and 1 <= len(seeds) <= len(bootstrap.SELECTIONS), "BOOTSTRAP_ROSTER")
    selections, cohorts, ids = set(), set(), {desktop[0], full[0]}
    for entry in seeds:
        fields(entry, "selection runId runAttempt", "BOOTSTRAP_RUN_FIELDS")
        profile, role, _, _ = bootstrap.selection(entry["selection"])
        require(entry["selection"] not in selections, "DUPLICATE_USE")
        selections.add(entry["selection"])
        cohorts.add((profile, role))
        run_id, _ = run(entry)
        require(run_id not in ids, "DUPLICATE_RUN")
        ids.add(run_id)
    require(pairs <= cohorts, "MISSING_BOOTSTRAP_COHORT")
    return first


def _current_pr(pr, declaration, first):
    # The entire joint exception ends on this PR's closure/merge/head change,
    # including a remaining bootstrap slot. Bootstrap must not ignore that state.
    require(type(pr) is dict and type(pr.get("number")) is int and pr["number"] == first["number"] and
            pr.get("state") == "open" and pr.get("merged") is False and
            pr.get("merge_commit_sha") == first["merge"]["commit"] and owner(pr.get("user")) and
            "auto_merge" in pr and pr["auto_merge"] is None and
            pr.get("url") == f"https://api.github.com/repos/{identity.REPOSITORY}/pulls/{first['number']}" and
            pr.get("html_url") == f"https://github.com/{identity.REPOSITORY}/pull/{first['number']}", "PR_CURRENT")
    for name, commit, branch in (("base", BASE["commit"], "main"),
                                 ("head", declaration["reviewed"]["commit"], SOURCE_REF.removeprefix("refs/heads/"))):
        item = pr.get(name)
        require(type(item) is dict and item.get("sha") == commit and item.get("ref") == branch and
                type(item.get("repo")) is dict and item["repo"].get("full_name") == identity.REPOSITORY,
                "PR_BASE_OR_HEAD")


def _use(observed, declaration, first):
    github = observed["github"]
    require(type(github) is dict, "GITHUB_FIELDS")
    profile = github.get("profile")
    require(type(profile) is str and profile in (bootstrap.PROFILE, "desktop", "full"), "PROFILE")
    fields(github, "profile event ref workflow workflowSha job runId runAttempt runnerOS runnerArch" +
           (" selection" if profile == bootstrap.PROFILE else ""), "GITHUB_FIELDS")
    run(github)
    _current_pr(observed["pullRequest"], declaration, first)
    if profile == bootstrap.PROFILE:
        require(observed["source"] == declaration["reviewed"] and observed["mergeParents"] is None, "BOOTSTRAP_SOURCE")
        selected = {key: github[key] for key in ("selection", "runId", "runAttempt")}
        require(selected in declaration["bootstrap"], "UNLISTED_USE")
        _, _, system, arch = bootstrap.selection(github["selection"])
        event, ref, workflow, job = "workflow_dispatch", SOURCE_REF, bootstrap.WORKFLOW, bootstrap.JOB
    else:
        require(observed["source"] == first["merge"] and
                observed["mergeParents"] == [BASE["commit"], declaration["reviewed"]["commit"]], "PR_SOURCE")
        roles = [role for role, host in ROLES.items() if host == (github["runnerOS"], github["runnerArch"])]
        require(len(roles) == 1, "HOST")
        selected = {"profile": profile, "role": roles[0], "runId": github["runId"], "runAttempt": github["runAttempt"]}
        require(selected in first["runs"], "UNLISTED_USE")
        system, arch = ROLES[roles[0]]
        event, ref = "pull_request", f"refs/pull/{first['number']}/merge"
        workflow, job, _ = identity.PROFILES[profile]
    require((github["event"], github["ref"], github["workflow"], github["job"],
             github["runnerOS"], github["runnerArch"]) == (event, ref, workflow, job, system, arch) and
            github["workflowSha"] == observed["source"]["commit"], "EXECUTION_BINDING")


def match(*, comment_raw, comment_id, body_sha256, observation_raw, base_policy_entry,
          ancestry_raw, candidate_policy_entry, candidate_policy_raw, now, expected=None):
    """Match bounded SUPPLIED originals; never fetch or authorize missing inputs.

    ``base_policy_entry`` must be stdout from a SUCCESSFUL, complete original
    ``git ls-tree -z B -- .github/test-evidence-recipient.json`` query. An error
    code/string, None or an empty capture from a failed query is not that premise.
    A real caller must establish it; catching GitView.policy's broad MISSING
    error is forbidden. Likewise all source/main/PR/account/clock observations
    need real acquisition, custody and repeated rechecks outside this module.

    ``firstUseAt`` is the original caller-owned pre-use UTC instant, not a reset
    on reread. ``expected`` compares stable authorization/source/use bindings;
    unrelated REST metadata changes may be retained without changing authority.
    No input or result is a proof of independent review or exactly-once use.
    """
    declaration, authority, created = statement(comment_raw, comment_id, body_sha256)
    first = roster(declaration)
    observed = identity.parse(observation_raw, LIMIT)
    fields(observed, "repository base reviewed source github pullRequest mergeParents firstUseAt", "OBSERVATION_FIELDS")
    require(observed["repository"] == identity.REPOSITORY and source(observed["base"]) == BASE and
            source(observed["reviewed"]) == declaration["reviewed"], "OBSERVED_SOURCE")
    source(observed["source"])
    # Do not treat a malformed/wrong-mode/present policy as initial absence.
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
            policy["retrievalOwner"] == OWNER_LOGIN, "VALIDITY_OR_PRIOR_AUTHORITY")
    _use(observed, declaration, first)
    result = Match(identity.encoded({"schema": 1, "scope": SCOPE + "_MATCH_ONLY_NOT_ADMISSION",
        "authority": authority, "originalBase": BASE, "reviewed": declaration["reviewed"],
        "source": observed["source"], "github": observed["github"], "firstUseAt": began,
        "notBefore": start, "expiresAt": end,
        # This blob really comes from H, not B. Never relabel it to satisfy the
        # existing ordinary/bootstrap admission or exporter schema.
        "policy": {"commit": declaration["reviewed"]["commit"], "blob": blob,
                   "path": identity.POLICY_PATH, "sha256": POLICY_SHA256}}))
    if expected is not None:
        require(type(expected) is Match and type(expected.record) is bytes and
                result.record == expected.record, "CHANGED_BEFORE_RECHECK")
    return result
