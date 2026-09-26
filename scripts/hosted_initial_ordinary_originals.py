"""Dormant Stage2 current-original composition, NOT native admission.

The caller must own the actual Git and HTTP-child domains, original fence,
first-use UTC, private retainer and known enclosing return. No Stage1 native
owner/SourceReturn is repurposed here; this increment has NO native CLI caller.
Returned matches are reference data, not live current authority, qualification
or permission to execute. Supplied historical bytes cannot reconstruct those
capabilities. Productive packet qualification and repeated real current-source
acquisitions remain required before any later ordinary use.
"""
from __future__ import annotations

import base64
import hashlib
import math
import os
from pathlib import Path
import re
import time

import hosted_cache_bootstrap_origin as origin
import hosted_initial_recipient_gate as gate


stages, I = gate.stages, gate.identity
API = "/repos/" + I.REPOSITORY
# The existing whole-JVM interlock uses this selector. This dormant composition
# does not wire, execute or qualify a replacement job or admit a gate budget.
GATE_SELECTOR = "ubuntu-latest"


def require(value, code):
    I.require(value, "INITIAL_ORDINARY_ORIGINALS_" + code)


def _context(env, event_raw, kind, first_use_at):
    """Pure seam; actual event/env are read only by acquire_ordinary below."""
    require(type(kind) is str and kind in ("gate", "worker") and
            type(first_use_at) is int and first_use_at > 0, "CONTEXT_KIND_OR_CLOCK")
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == I.REPOSITORY and
            env.get("GITHUB_SERVER_URL") == "https://github.com" and
            env.get("GITHUB_API_URL") == "https://api.github.com" and
            env.get("RUNNER_ENVIRONMENT") == "github-hosted", "HOSTED_CONTEXT")
    require(env.get("GITHUB_EVENT_NAME") == "pull_request" and type(event_raw) is bytes, "PR_EVENT")
    event = I.parse(event_raw, I.EVENT_LIMIT)
    repository, pr = I.mapping(event.get("repository")), I.mapping(event.get("pull_request"))
    number = stages.joint.number(event.get("number"))
    ref = f"refs/pull/{number}/merge"
    require(repository.get("full_name") == I.REPOSITORY and repository.get("default_branch") == "main" and
            env.get("GITHUB_REF") == ref and event.get("action") in ("opened", "reopened", "synchronize"),
            "PR_REPOSITORY_OR_REF")
    merge = I.sha(env.get("GITHUB_SHA"))
    head = I.sha(I.mapping(pr.get("head")).get("sha"))
    require(merge not in (head, stages.BASE["commit"]) and head != stages.BASE["commit"], "SEPARATE_PR_SOURCE")
    # Reuse the closed first-PR predicates against the ORIGINAL event PR, not an
    # invented REST response. Trees are obtained from native Git, never events.
    stages.joint._current_pr(pr, {"reviewed": {"commit": head}},
                             {"number": number, "merge": {"commit": merge}})
    profiles = [name for name, (workflow, _, _) in I.PROFILES.items() if env.get("GITHUB_WORKFLOW_REF") ==
                I.REPOSITORY + "/" + workflow + "@" + ref]
    require(len(profiles) == 1 and env.get("GITHUB_WORKFLOW_SHA") == merge, "WORKFLOW")
    profile = profiles[0]
    workflow, worker, _ = I.PROFILES[profile]
    stages.joint.run({"runId": env.get("GITHUB_RUN_ID"), "runAttempt": env.get("GITHUB_RUN_ATTEMPT")})
    host = env.get("RUNNER_OS"), env.get("RUNNER_ARCH")
    roles = [role for role, labels in stages.joint.ROLES.items() if labels == host]
    require(len(roles) == 1 and env.get("GITHUB_JOB") == (gate.JOB if kind == "gate" else worker) and
            (host == ("Linux", "X64") if kind == "gate" else profile != "full" or host[0] == "macOS"),
            "ACTUAL_JOB_HOST")
    runner = env.get("RUNNER_NAME")
    require(type(runner) is str and 0 < len(runner) <= 256 and
            not any(ord(char) < 32 or ord(char) == 127 for char in runner), "RUNNER_NAME")
    return {"kind": kind, "profile": profile, "sourceCommit": merge, "reviewedCommit": head,
        "pullRequestNumber": number, "firstUseAt": first_use_at, "role": roles[0], "runnerName": runner,
        "github": {"event": "pull_request", "ref": ref, "workflow": workflow, "workflowSha": merge,
            "job": env["GITHUB_JOB"], "runId": env["GITHUB_RUN_ID"], "runAttempt": env["GITHUB_RUN_ATTEMPT"],
            "runnerOS": host[0], "runnerArch": host[1]}}


def _line(raw, commit, code):
    require(type(raw) is bytes and raw in (commit.encode("ascii") + b"\n", commit.encode("ascii") + b"\r\n"), code)


def _source(git, context, check):
    def call(method, *args, **kwargs):
        check()
        result = getattr(git, method)(*args, **kwargs)
        check()
        return result

    merge, head = context["sourceCommit"], context["reviewedCommit"]
    require(call("root_matches") and call("clean") and call("commit", "HEAD") == merge, "SOURCE")
    require(call("query", "rev-parse", "--is-shallow-repository") in (b"false\n", b"false\r\n"), "FULL_HISTORY")
    source = {"commit": merge, "tree": I.sha(call("tree", merge))}
    reviewed = {"commit": head, "tree": I.sha(call("tree", head))}
    parents = call("parents", merge)
    require(source["tree"] == reviewed["tree"] and parents == [stages.BASE["commit"], head], "PR_MERGE")
    require(call("commit", "refs/remotes/origin/main") == stages.BASE["commit"] and
            call("tree", stages.BASE["commit"]) == stages.BASE["tree"], "ORIGINAL_BASE")
    base_entry = call("query", "ls-tree", "-z", stages.BASE["commit"], "--", I.POLICY_PATH)
    require(type(base_entry) is bytes and base_entry == b"", "BASE_POLICY_NOT_ABSENT")
    ancestry = call("query", "merge-base", stages.BASE["commit"], head)
    _line(ancestry, stages.BASE["commit"], "BASE_ANCESTRY")
    entry = call("query", "ls-tree", "-z", head, "--", I.POLICY_PATH)
    require(type(entry) is bytes, "POLICY_ENTRY")
    match = re.fullmatch(rb"100644 blob ([0-9a-f]{40})\t" + re.escape(I.POLICY_PATH.encode("ascii")) + rb"\x00", entry)
    require(match is not None, "POLICY_ENTRY")
    blob = match.group(1).decode("ascii")
    size = call("query", "cat-file", "-s", blob)
    require(type(size) is bytes and re.fullmatch(rb"[1-9][0-9]{0,5}\r?\n", size) and
            int(size) <= I.POLICY_LIMIT, "POLICY_SIZE")
    policy = call("query", "cat-file", "blob", blob, limit=I.POLICY_LIMIT)
    require(type(policy) is bytes and len(policy) == int(size) and hashlib.sha1(b"blob " +
            str(len(policy)).encode("ascii") + b"\0" + policy).hexdigest() == blob and
            hashlib.sha256(policy).hexdigest() == stages.POLICY_SHA256, "POLICY_BLOB")
    return {"source": source, "reviewed": reviewed, "mergeParents": parents}, {
        "base_policy_entry": base_entry, "ancestry_raw": ancestry,
        "candidate_policy_entry": entry, "candidate_policy_raw": policy}


def _prior(git, context, declaration, check):
    prior = stages.fields(declaration["stage1"], "commentId bodySha256 reviewed", "STAGE1_REFERENCE_FIELDS")
    stages.positive(prior["commentId"])
    stages.digest(prior["bodySha256"])
    reviewed = stages.joint.source(prior["reviewed"])
    require(reviewed["commit"] != context["reviewedCommit"], "SEPARATE_REVIEWED_HEADS")
    check()
    require(git.tree(reviewed["commit"]) == reviewed["tree"], "HISTORICAL_TREE")
    check()
    raw = git.query("merge-base", reviewed["commit"], context["reviewedCommit"])
    check()
    _line(raw, reviewed["commit"], "HISTORICAL_ANCESTRY")
    return raw


def _run(context, attempt, jobs, service_date):
    """GitHub service head is H2; actual checkout/workflow source remains M."""
    github = context["github"]
    run_id, number = int(github["runId"]), int(github["runAttempt"])
    head, branch = context["reviewedCommit"], stages.SOURCE_REF.removeprefix("refs/heads/")
    require(type(attempt.get("id")) is int and attempt["id"] == run_id and
            type(attempt.get("run_attempt")) is int and attempt["run_attempt"] == number and
            I.mapping(attempt.get("repository")).get("full_name") == I.REPOSITORY and
            I.mapping(attempt.get("head_repository")).get("full_name") == I.REPOSITORY and
            attempt.get("path") == github["workflow"] and attempt.get("event") == "pull_request" and
            attempt.get("head_sha") == head and attempt.get("head_branch") == branch and
            attempt.get("status") == "in_progress" and "conclusion" in attempt and attempt["conclusion"] is None,
            "CURRENT_ATTEMPT")
    prs = attempt.get("pull_requests")
    require(type(prs) is list and len(prs) == 1 and type(prs[0]) is dict and
            type(prs[0].get("number")) is int and prs[0]["number"] == context["pullRequestNumber"], "ATTEMPT_PR")
    for side, commit, ref in (("base", stages.BASE["commit"], "main"), ("head", head, branch)):
        item = I.mapping(prs[0].get(side))
        require(item.get("sha") == commit and item.get("ref") == ref and
                I.mapping(item.get("repo")).get("url") == origin.wire.ORIGIN + API, "ATTEMPT_PR")
    rows = jobs.get("jobs")
    require(type(rows) is list and 0 < len(rows) <= 100 and type(jobs.get("total_count")) is int and
            jobs["total_count"] == len(rows) and all(type(row) is dict for row in rows), "COMPLETE_JOBS")
    ids = [stages.positive(row.get("id")) for row in rows]
    require(len(set(ids)) == len(ids), "DUPLICATE_JOB")
    selector = (GATE_SELECTOR if context["kind"] == "gate" else "macos-latest" if context["profile"] == "full"
                else origin.wire.DESKTOP_HOSTS[(github["runnerOS"], github["runnerArch"])][1])
    name = gate.JOB if context["kind"] == "gate" else "complete-gate" if context["profile"] == "full" else selector
    selected = [row for row in rows if row.get("name") == name]
    require(len(selected) == 1, "EXACT_JOB")
    job = selected[0]

    def bound(row):
        return (type(row.get("run_id")) is int and row["run_id"] == run_id and
            type(row.get("run_attempt")) is int and row["run_attempt"] == number and
            row.get("head_sha") == head and row.get("head_branch") == branch and
            row.get("url") == origin.wire.ORIGIN + API + "/actions/jobs/" + str(row["id"]) and
            row.get("run_url") == origin.wire.ORIGIN + API + "/actions/runs/" + github["runId"])

    require(bound(job) and job.get("status") == "in_progress" and "conclusion" in job and
            job["conclusion"] is None and "completed_at" in job and job["completed_at"] is None, "CURRENT_JOB")
    require(job.get("runner_name") == context["runnerName"] and type(job.get("runner_id")) is int and
            job["runner_id"] > 0 and job.get("labels") == [selector] and
            type(job.get("runner_group_id")) is int and job["runner_group_id"] == 0 and
            job.get("runner_group_name") == "GitHub Actions", "SERVICE_RUNNER")
    require(origin.wire.utc_epoch(attempt.get("created_at")) <= origin.wire.utc_epoch(attempt.get("run_started_at")) <=
            origin.wire.utc_epoch(job.get("started_at")) <= service_date, "SERVICE_START")
    if context["kind"] == "worker":
        predecessors = [row for row in rows if row.get("name") == gate.JOB]
        require(len(predecessors) == 1, "GATE_PREDECESSOR")
        predecessor = predecessors[0]
        require(bound(predecessor) and predecessor.get("status") == "completed" and
                predecessor.get("conclusion") == "success" and predecessor.get("labels") == [GATE_SELECTOR] and
                origin.wire.utc_epoch(predecessor.get("started_at")) <=
                origin.wire.utc_epoch(predecessor.get("completed_at")) <=
                origin.wire.utc_epoch(job["started_at"]), "GATE_PREDECESSOR")
    return job  # Exact original row; successful predecessor is NOT qualification.


def _ref(value, name, commit):
    require(value.get("ref") == "refs/heads/" + name and
            value.get("url") == origin.wire.ORIGIN + API + "/git/refs/heads/" + name, "REF_LOCATION")
    obj = I.mapping(value.get("object"))
    require(obj.get("type") == "commit" and obj.get("sha") == commit and
            obj.get("url") == origin.wire.ORIGIN + API + "/git/commits/" + commit, "REF_COMMIT")


def _acquire_ordinary(context, event_raw, git, invocation, token, retain, fence, original_work_end,
                      now, histories, expected):
    """Nine closed current requests, retaining failures once; no native fallback.

    Histories are supplied historical DATA, not a reconstructed live return or
    evidence acceptance. Transport uses the existing fixed-origin 45/15/5 caps
    inside the caller's original work fence; this admits no new gate budget.
    """
    require(type(invocation) is str and re.fullmatch(r"[0-9a-f]{32}", invocation), "INVOCATION")
    require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token), "READ_TOKEN")
    require(callable(retain) and callable(now) and type(histories) is tuple and len(histories) == 4,
            "OWNER_CALLBACKS_OR_HISTORY")
    require(fence.clock.role == context["role"], "NATIVE_CLOCK_ROLE")
    start = fence.now(limit=original_work_end)
    end = min(original_work_end, start + origin.wire.ACQUIRE_SECONDS * origin.NS)
    originals, previous_date, first_date = {}, None, None

    def keep(label, raw, *, failed=False):
        require(label not in originals and type(raw) is bytes, "ORIGINAL_REUSE")
        if not failed:
            try:
                fence.now(limit=end)
            except BaseException as original:
                # Only a not-yet-entered retainer gets the parent's final fence.
                # The exact acquired bytes are retained once, not rewritten.
                try:
                    retain(label, raw, failed=True)
                except BaseException as secondary:
                    raise original from secondary
                originals[label] = raw
                raise
        retain(label, raw, failed=failed)
        if not failed:
            fence.now(limit=end)
        originals[label] = raw

    def get(label, path):
        nonlocal previous_date, first_date
        fence.now(limit=end)
        raw, error = origin._request(path, token, invocation, fence, end)
        try:
            keep(label, raw, failed=error is not None)
        except BaseException as secondary:
            if error is None:
                raise
            raise error from secondary
        if error is not None:
            raise error
        response, body, date = origin.response_bytes(raw, path, invocation, fence.clock)
        _, headers = origin.wire.headers(base64.b64decode(response["headersBase64"], validate=True))
        require("link" not in headers, "INCOMPLETE_RESPONSE")
        require(start <= response["startedNs"] <= response["finishedNs"] < end, "ORIGINAL_INTERVAL")
        if first_date is None:
            first_date = date
        require((previous_date is None or date >= previous_date) and
                0 <= date - first_date <= math.ceil((response["finishedNs"] - start) / origin.NS) +
                origin.wire.CACHE_SECONDS + 1, "SERVICE_DATE_DRIFT")
        previous_date = date
        fence.now(minimum=response["finishedNs"], limit=end)
        return body, date

    check = lambda: fence.now(limit=end)
    keep("event", event_raw)
    source, policy_inputs = _source(git, context, check)
    keep("source_binding", I.encoded(source))
    for label, raw in policy_inputs.items():
        keep(label, raw)
    github = context["github"]
    base = API + "/actions/runs/" + github["runId"]
    attempt_path = base + "/attempts/" + github["runAttempt"]
    attempt_raw, _ = get("attempt", attempt_path)
    jobs_raw, date = get("jobs", attempt_path + "/jobs?per_page=100&page=1")
    _run(context, I.parse(attempt_raw, origin.wire.BODY_LIMIT), I.parse(jobs_raw, origin.wire.BODY_LIMIT), date)
    approvals_raw, _ = get("approvals", base + "/approvals")
    selected = gate.select(stage="stage2", run_id=github["runId"], attempt=github["runAttempt"], approvals_raw=approvals_raw)
    selector = I.parse(selected.record, stages.LIMIT)
    comment_raw, _ = get("comment", API + "/issues/comments/" + str(selector["commentId"]))
    declaration, _, _ = stages.statement(stages.STAGE2, comment_raw, selector["commentId"], selector["bodySha256"])
    first, _ = stages.ordinary_roster(declaration)
    require(first["number"] == context["pullRequestNumber"] and first["merge"] == source["source"] and
            declaration["reviewed"] == source["reviewed"], "CURRENT_DECLARED_SOURCE")
    require(selector["environmentId"] == declaration["environment"]["id"], "APPROVED_ENVIRONMENT_CHANGED")
    prior = _prior(git, context, declaration, check)
    keep("prior_ancestry_raw", prior)
    environment_path = API + "/environments/" + stages.ENVIRONMENT
    environment_raw, _ = get("environment", environment_path)
    branches_raw, _ = get("branches", environment_path + "/deployment-branch-policies?per_page=100&page=1")
    gate.check_environment(declaration["environment"], environment_raw, branches_raw)
    for label, branch, commit in (("main", "main", stages.BASE["commit"]),
            ("reviewed_ref", stages.SOURCE_REF.removeprefix("refs/heads/"), context["reviewedCommit"])):
        body, _ = get(label, API + "/git/ref/heads/" + branch)
        _ref(I.parse(body, stages.LIMIT), branch, commit)
    pr_raw, _ = get("pull_request", API + "/pulls/" + str(context["pullRequestNumber"]))
    pr = I.parse(pr_raw, origin.wire.BODY_LIMIT)
    stages.joint._current_pr(pr, declaration, first)
    require(_source(git, context, check) == (source, policy_inputs) and
            _prior(git, context, declaration, check) == prior, "SOURCE_CHANGED_DURING_ACQUISITION")
    observed = {"repository": I.REPOSITORY, "base": dict(stages.BASE), **source,
        "firstUseAt": context["firstUseAt"], "github": dict(github), "pullRequest": pr}
    check()
    if context["kind"] == "gate":
        result = gate.eligible(stage="stage2", approvals_raw=approvals_raw, comment_raw=comment_raw,
            environment_raw=environment_raw, branches_raw=branches_raw, observation_raw=I.encoded(observed),
            now=now(), histories=histories, prior_ancestry_raw=prior, expected=expected, **policy_inputs)
    else:
        observed["github"]["profile"] = context["profile"]
        result = stages.match_ordinary(comment_raw=comment_raw, comment_id=selector["commentId"],
            body_sha256=selector["bodySha256"], observation_raw=I.encoded(observed), now=now(),
            histories=histories, prior_ancestry_raw=prior, expected=expected, **policy_inputs)
    keep("observation", I.encoded(observed))
    keep("match", result.record)
    check()
    return result, tuple(originals.items())


def acquire_ordinary(root, *, kind, query_runner, invocation, token, retain, fence, original_work_end,
                     first_use_at, histories, expected=None):
    """Actual environment/event entry; NO production caller is wired yet.

    The enclosing native owner must keep token in its private HTTP child and
    independently prove Git/HTTP/retainer and enclosing-return retirement. It
    must not serialize this tuple and hydrate SourceReturn, Recipient, a current
    authority or a qualified packet from it. Stage1's native owner does not
    acquire Stage2 merely by passing a new kind/argument to its existing CLI.
    """
    env = dict(os.environ)
    root = Path(root)
    require(root.is_absolute() and root == root.resolve(strict=True) and
            env.get("GITHUB_WORKSPACE") == str(root), "WORKSPACE")
    event = I.read_regular(Path(env.get("GITHUB_EVENT_PATH", "")), I.EVENT_LIMIT)
    context = _context(env, event, kind, first_use_at)
    git = I.GitView(root, env, query_runner)
    return _acquire_ordinary(context, event, git, invocation, token, retain, fence, original_work_end,
                             lambda: int(time.time()), histories, expected)
