"""Dormant pre-execution approval selector/eligibility, NOT native admission.

This parses supplied original API/Git/context bytes only. It acquires no token,
response or source and creates no environment/run. The future nonproductive job
must obtain fresh complete bounded originals; workers must reacquire authority
and genuine native/qualification inputs before any productive side effects.
"""
from __future__ import annotations

import dataclasses
import re

import hosted_initial_recipient_stages as stages


identity = stages.identity
JOB = "initial-recipient-gate"
NAMES = {"stage1": stages.STAGE1, "stage2": stages.STAGE2}
APPROVAL = re.compile(r"AUTHORIZE_INITIAL_RECIPIENT (stage1|stage2) ([1-9][0-9]{0,19})/"
                      r"([1-9][0-9]{0,19}) ([1-9][0-9]{0,19}) ([0-9a-f]{64})\Z")
HISTORY_LIMIT = 2 * 1024 * 1024


@dataclasses.dataclass(frozen=True)
class ApprovalSelector:
    record: bytes


@dataclasses.dataclass(frozen=True)
class GateEligibility:
    """Never a native worker identity, evidence qualification or Admission."""

    record: bytes


def require(value, code):
    identity.require(value, "INITIAL_GATE_" + code)


def _stage(stage):
    require(type(stage) is str and stage in NAMES, "STAGE")
    return NAMES[stage]


def _run(run_id, attempt):
    stages.joint.run({"runId": run_id, "runAttempt": attempt})


def _recheck(result, expected, kind):
    if expected is not None:
        require(type(expected) is kind and type(expected.record) is bytes and result.record == expected.record,
                "CHANGED_BEFORE_RECHECK")
    return result


def select(*, stage, run_id, attempt, approvals_raw, expected=None):
    """Read one exact run/attempt challenge, then fetch ONLY its chosen comment.

    GitHub approval history does not itself identify attempts. No .strip(),
    latest-comment search, reused challenge, inferred approval or synthetic
    attempt is accepted. This selection is not the selected statement's match.
    """
    _stage(stage)
    _run(run_id, attempt)
    require(type(approvals_raw) is bytes and 0 < len(approvals_raw) <= HISTORY_LIMIT, "HISTORY_BYTES")
    # Parse the actual list response with the maintained duplicate-key/size
    # parser. The wrapper is parsing only, never a claimed original response.
    wrapped = identity.parse(b'{"history":' + approvals_raw + b'}', HISTORY_LIMIT + 12)
    # A malformed original such as `[],"other":true` must not become valid
    # merely because this parser supplies an outer object around the list.
    require(set(wrapped) == {"history"}, "HISTORY_SHAPE")
    history = wrapped["history"]
    require(type(history) is list and len(history) <= 1000 and all(type(x) is dict for x in history), "HISTORY_SHAPE")
    matches = []
    for item in history:
        line = item.get("comment")
        parsed = APPROVAL.fullmatch(line) if type(line) is str else None
        if parsed and parsed.group(1, 2, 3) == (stage, run_id, attempt):
            matches.append((item, parsed))
    require(len(matches) == 1, "MISSING_OR_AMBIGUOUS_CHALLENGE")
    approval, parsed = matches[0]
    require(approval.get("state") == "approved" and stages.joint.owner(approval.get("user")), "OWNER_APPROVAL")
    environments = approval.get("environments")
    require(type(environments) is list and len(environments) == 1 and type(environments[0]) is dict and
            environments[0].get("name") == stages.ENVIRONMENT, "APPROVAL_ENVIRONMENT")
    environment_id = stages.positive(environments[0].get("id"))
    return _recheck(ApprovalSelector(identity.encoded({"schema": 1,
        "scope": "INITIAL_RECIPIENT_SELECTED_APPROVAL_ONLY", "stage": stage,
        "runId": run_id, "runAttempt": attempt, "commentId": int(parsed.group(4)),
        "bodySha256": parsed.group(5), "environmentId": environment_id,
        "environmentName": stages.ENVIRONMENT, "approvalLine": approval["comment"],
        "owner": {"login": stages.joint.OWNER_LOGIN, "id": stages.joint.OWNER_ID}})), expected, ApprovalSelector)


def check_environment(expected, environment_raw, branches_raw):
    """Exact owner-pinned environment/rules, not name-only lookup or creation."""
    stages.environment(expected)
    require(type(environment_raw) is bytes and type(branches_raw) is bytes, "ENVIRONMENT_BYTES")
    value = identity.parse(environment_raw, stages.LIMIT)
    require(type(value.get("id")) is int and value["id"] == expected["id"] and
            value.get("name") == stages.ENVIRONMENT and value.get("can_admins_bypass") is False and
            type(value.get("deployment_branch_policy")) is dict and
            identity.encoded(value["deployment_branch_policy"]) == identity.encoded(
                {"protected_branches": False, "custom_branch_policies": True}), "ENVIRONMENT_CONFIGURATION")
    rules = value.get("protection_rules")
    require(type(rules) is list and len(rules) == 2 and all(type(x) is dict for x in rules) and
            sorted(x.get("type", "") for x in rules if type(x.get("type")) is str) ==
            ["branch_policy", "required_reviewers"], "PROTECTION_RULES")
    reviewer = next(x for x in rules if x.get("type") == "required_reviewers")
    reviewers = reviewer.get("reviewers")
    require(reviewer.get("prevent_self_review") is False and type(reviewers) is list and len(reviewers) == 1 and
            type(reviewers[0]) is dict and reviewers[0].get("type") == "User" and
            stages.joint.owner(reviewers[0].get("reviewer")), "SOLE_OWNER_REVIEWER")
    branches = identity.parse(branches_raw, stages.LIMIT)
    require(type(branches.get("total_count")) is int and branches["total_count"] == 2 and
            type(branches.get("branch_policies")) is list and len(branches["branch_policies"]) == 2,
            "COMPLETE_BRANCH_POLICIES")
    actual = []
    for item in branches["branch_policies"]:
        require(type(item) is dict, "BRANCH_POLICY")
        stages.positive(item.get("id"))
        require(type(item.get("name")) is str and type(item.get("type")) is str, "BRANCH_POLICY")
        actual.append({name: item[name] for name in ("id", "name", "type")})
    require(sorted(actual, key=lambda x: x["id"]) == sorted(expected["branchPolicies"], key=lambda x: x["id"]),
            "BRANCH_POLICY_CHANGED")
    return expected


def eligible(*, stage, approvals_raw, comment_raw, environment_raw, branches_raw, observation_raw,
             base_policy_entry, ancestry_raw, candidate_policy_entry, candidate_policy_raw, now,
             histories=(), prior_ancestry_raw=None, expected=None):
    """Nonproductive gate context; NEVER rewrite it into a native job identity.

    This is not an original acquirer, whole-job workflow dependency or authority
    for any product/provider operation. Gate and productive jobs have distinct
    original first-use clocks and ownership. Actual workers need fresh admission,
    complete originals and qualification; gate success cannot replace them.
    """
    scope = _stage(stage)
    require(type(observation_raw) is bytes, "OBSERVATION_BYTES")
    observed = identity.parse(observation_raw, stages.LIMIT)
    stages.fields(observed, "repository base reviewed source github firstUseAt" +
                  (" inputs" if stage == "stage1" else " pullRequest mergeParents"), "GATE_OBSERVATION_FIELDS")
    github = stages.fields(observed["github"], "event ref workflow workflowSha job runId runAttempt runnerOS runnerArch",
                           "GATE_GITHUB_FIELDS")
    _run(github["runId"], github["runAttempt"])
    require(github["job"] == JOB and (github["runnerOS"], github["runnerArch"]) == ("Linux", "X64"),
            "NONPRODUCTIVE_JOB")
    selector = select(stage=stage, run_id=github["runId"], attempt=github["runAttempt"], approvals_raw=approvals_raw)
    selection = identity.parse(selector.record, stages.LIMIT)
    declaration, authority, created = stages.statement(scope, comment_raw, selection["commentId"], selection["bodySha256"])
    require(selection["environmentId"] == declaration["environment"]["id"], "APPROVED_ENVIRONMENT_CHANGED")
    check_environment(declaration["environment"], environment_raw, branches_raw)
    policy = stages._policy(declaration, observed, created, base_policy_entry, ancestry_raw,
                            candidate_policy_entry, candidate_policy_raw, now)
    if stage == "stage1":
        require(type(histories) is tuple and len(histories) == 0 and prior_ancestry_raw is None,
                "BOOTSTRAP_HAS_NO_PR_HISTORY")
        stages.bootstrap_roster(declaration["bootstrap"])
        inputs = stages.fields(observed["inputs"], "selection expected_sha expected_tree", "DISPATCH_INPUTS")
        stages.bootstrap.selection(inputs["selection"])
        selected = {"selection": inputs["selection"], "runId": github["runId"], "runAttempt": github["runAttempt"]}
        require(selected in declaration["bootstrap"] and observed["source"] == declaration["reviewed"] and
                inputs["expected_sha"] == declaration["reviewed"]["commit"] and
                inputs["expected_tree"] == declaration["reviewed"]["tree"], "BOOTSTRAP_SELECTION")
        require((github["event"], github["ref"], github["workflow"], github["workflowSha"]) ==
                ("workflow_dispatch", stages.SOURCE_REF, stages.bootstrap.WORKFLOW, declaration["reviewed"]["commit"]),
                "BOOTSTRAP_CONTEXT")
    else:
        first, pairs = stages.ordinary_roster(declaration)
        stages.joint._current_pr(observed["pullRequest"], declaration, first)
        require(observed["source"] == first["merge"] and observed["mergeParents"] ==
                [stages.BASE["commit"], declaration["reviewed"]["commit"]], "ORDINARY_MERGE")
        profiles = [profile for profile, value in identity.PROFILES.items() if value[0] == github["workflow"]]
        require(len(profiles) == 1 and any(x["profile"] == profiles[0] and x["runId"] == github["runId"] and
                x["runAttempt"] == github["runAttempt"] for x in first["runs"]), "ORDINARY_RUN")
        require((github["event"], github["ref"], github["workflowSha"]) ==
                ("pull_request", f"refs/pull/{first['number']}/merge", first["merge"]["commit"]), "ORDINARY_CONTEXT")
        stages._histories(declaration, pairs, histories, created, prior_ancestry_raw)
    return _recheck(GateEligibility(identity.encoded({"schema": 1, "scope": "NONPRODUCTIVE_ELIGIBILITY",
        "stage": stage, "selector": selection, "authority": authority, "github": github,
        "originalBase": stages.BASE, "reviewed": declaration["reviewed"], "source": observed["source"],
        "policy": policy, "environment": declaration["environment"], "firstUseAt": observed["firstUseAt"],
        "notBefore": declaration["notBefore"], "expiresAt": declaration["expiresAt"],
        "workerAdmission": "NOT_PERFORMED", "qualificationAcceptance": "NOT_ESTABLISHED_BY_GATE"})),
        expected, GateEligibility)
