"""Dormant Stage1 original acquisition, not Admission or a native supervisor.

The actual entry reads the process's original event/context and delegates only
closed Git queries and fixed-origin HTTP GETs. Its caller MUST already own the
native query and HTTP-child domains, original fence and private retainer. No
workflow/CLI calls this module yet; calling it without that enclosing owner is
not a supported execution path. No policy exception is installed by a return.
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


stages, identity = gate.stages, gate.identity
API = "/repos/" + identity.REPOSITORY
GATE_SELECTOR = "ubuntu-24.04"


def require(value, code):
    identity.require(value, "INITIAL_ORIGINALS_" + code)


def _context(env, event_raw, kind, first_use_at):
    """Pure context seam; supplied test contexts are not hosted observations."""
    require(kind in ("gate", "worker") and type(first_use_at) is int and first_use_at > 0, "CONTEXT_KIND_OR_CLOCK")
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == identity.REPOSITORY and
            env.get("GITHUB_SERVER_URL") == "https://github.com" and
            env.get("GITHUB_API_URL") == "https://api.github.com" and
            env.get("RUNNER_ENVIRONMENT") == "github-hosted", "HOSTED_CONTEXT")
    require(env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and
            env.get("GITHUB_REF") == stages.SOURCE_REF, "BOOTSTRAP_EVENT_REF")
    source = identity.sha(env.get("GITHUB_SHA"))
    require(env.get("GITHUB_WORKFLOW_SHA") == source and env.get("GITHUB_WORKFLOW_REF") ==
            identity.REPOSITORY + "/" + stages.bootstrap.WORKFLOW + "@" + stages.SOURCE_REF, "WORKFLOW")
    stages.joint.run({"runId": env.get("GITHUB_RUN_ID"), "runAttempt": env.get("GITHUB_RUN_ATTEMPT")})
    require(type(event_raw) is bytes, "EVENT_BYTES")
    event = identity.parse(event_raw, identity.EVENT_LIMIT)
    repo = identity.mapping(event.get("repository"))
    require(repo.get("full_name") == identity.REPOSITORY and repo.get("default_branch") == "main" and
            event.get("ref") in (stages.SOURCE_REF, stages.SOURCE_REF.removeprefix("refs/heads/")), "EVENT_REPOSITORY")
    inputs = stages.fields(event.get("inputs"), "selection expected_sha expected_tree", "DISPATCH_INPUTS")
    _, role, system, arch = stages.bootstrap.selection(inputs["selection"])
    require(inputs["expected_sha"] == source, "EXPECTED_SOURCE")
    tree = identity.sha(inputs["expected_tree"])
    job = gate.JOB if kind == "gate" else stages.bootstrap.JOB
    host = ("Linux", "X64") if kind == "gate" else (system, arch)
    require(env.get("GITHUB_JOB") == job and (env.get("RUNNER_OS"), env.get("RUNNER_ARCH")) == host,
            "ACTUAL_JOB_HOST")
    runner = env.get("RUNNER_NAME")
    require(type(runner) is str and 0 < len(runner) <= 256 and
            not any(ord(char) < 32 or ord(char) == 127 for char in runner), "RUNNER_NAME")
    return {"kind": kind, "source": {"commit": source, "tree": tree}, "inputs": dict(inputs),
            "firstUseAt": first_use_at, "role": "linux-x64" if kind == "gate" else role,
            "runnerName": runner, "github": {"event": "workflow_dispatch", "ref": stages.SOURCE_REF,
            "workflow": stages.bootstrap.WORKFLOW, "workflowSha": source, "job": job,
            "runId": env["GITHUB_RUN_ID"], "runAttempt": env["GITHUB_RUN_ATTEMPT"],
            "runnerOS": host[0], "runnerArch": host[1]}}


def _source(git, context, check):
    """Only exact empty stdout from the successful owned ls-tree means absent."""
    def call(method, *args, **kwargs):
        check()
        result = getattr(git, method)(*args, **kwargs)
        check()
        return result

    source = context["source"]
    require(call("root_matches") and call("clean") and call("commit", "HEAD") == source["commit"] and
            call("tree", source["commit"]) == source["tree"], "SOURCE")
    require(call("query", "rev-parse", "--is-shallow-repository") in (b"false\n", b"false\r\n"), "FULL_HISTORY")
    require(call("commit", "refs/remotes/origin/main") == stages.BASE["commit"] and
            call("tree", stages.BASE["commit"]) == stages.BASE["tree"], "ORIGINAL_BASE")
    base_entry = call("query", "ls-tree", "-z", stages.BASE["commit"], "--", identity.POLICY_PATH)
    require(type(base_entry) is bytes and base_entry == b"", "BASE_POLICY_NOT_ABSENT")
    ancestry = call("query", "merge-base", stages.BASE["commit"], source["commit"])
    entry = call("query", "ls-tree", "-z", source["commit"], "--", identity.POLICY_PATH)
    require(type(entry) is bytes, "POLICY_ENTRY_CHANGED")
    match = re.fullmatch(rb"100644 blob ([0-9a-f]{40})\t" + re.escape(identity.POLICY_PATH.encode("ascii")) + rb"\x00", entry)
    require(match is not None, "POLICY_ENTRY_CHANGED")
    blob = match.group(1).decode("ascii")
    size = call("query", "cat-file", "-s", blob)
    require(type(size) is bytes and re.fullmatch(rb"[1-9][0-9]{0,5}\r?\n", size) and
            int(size) <= identity.POLICY_LIMIT, "POLICY_SIZE")
    policy = call("query", "cat-file", "blob", blob, limit=identity.POLICY_LIMIT)
    require(type(policy) is bytes and len(policy) == int(size) and hashlib.sha1(b"blob " +
            str(len(policy)).encode("ascii") + b"\0" + policy).hexdigest() == blob, "POLICY_BLOB")
    return {"base_policy_entry": base_entry, "ancestry_raw": ancestry,
            "candidate_policy_entry": entry, "candidate_policy_raw": policy}


def _run(context, attempt, jobs, service_date):
    """Bind the actual gate OR populate service job; never relabel one as another."""
    github, source = context["github"], context["source"]
    run_id, number = int(github["runId"]), int(github["runAttempt"])
    branch = stages.SOURCE_REF.removeprefix("refs/heads/")
    require(type(attempt.get("id")) is int and attempt["id"] == run_id and
            type(attempt.get("run_attempt")) is int and attempt["run_attempt"] == number and
            identity.mapping(attempt.get("repository")).get("full_name") == identity.REPOSITORY and
            identity.mapping(attempt.get("head_repository")).get("full_name") == identity.REPOSITORY and
            attempt.get("path") == stages.bootstrap.WORKFLOW and attempt.get("event") == "workflow_dispatch" and
            attempt.get("head_sha") == source["commit"] and attempt.get("head_branch") == branch and
            attempt.get("status") == "in_progress" and "conclusion" in attempt and attempt["conclusion"] is None and
            attempt.get("pull_requests") == [], "CURRENT_ATTEMPT")
    rows = jobs.get("jobs")
    require(type(rows) is list and 0 < len(rows) <= 100 and type(jobs.get("total_count")) is int and
            jobs["total_count"] == len(rows) and all(type(row) is dict for row in rows), "COMPLETE_JOBS")
    ids = [stages.positive(row.get("id")) for row in rows]
    require(len(set(ids)) == len(ids), "DUPLICATE_JOB")
    selected = [row for row in rows if row.get("name") == github["job"]]
    require(len(selected) == 1, "EXACT_JOB")
    job = selected[0]
    require(type(job.get("run_id")) is int and job["run_id"] == run_id and
            type(job.get("run_attempt")) is int and job["run_attempt"] == number and
            job.get("head_sha") == source["commit"] and job.get("head_branch") == branch and
            job.get("url") == origin.wire.ORIGIN + API + "/actions/jobs/" + str(job["id"]) and
            job.get("run_url") == origin.wire.ORIGIN + API + "/actions/runs/" + github["runId"] and
            job.get("status") == "in_progress" and "conclusion" in job and job["conclusion"] is None and
            "completed_at" in job and job["completed_at"] is None, "CURRENT_JOB")
    selector = GATE_SELECTOR if context["kind"] == "gate" else origin.SERVICE_SELECTORS[context["role"]]
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
        require(type(predecessor.get("run_id")) is int and predecessor["run_id"] == run_id and
                type(predecessor.get("run_attempt")) is int and predecessor["run_attempt"] == number and
                predecessor.get("head_sha") == source["commit"] and predecessor.get("head_branch") == branch and
                predecessor.get("run_url") == job["run_url"] and predecessor.get("url") ==
                origin.wire.ORIGIN + API + "/actions/jobs/" + str(predecessor["id"]) and
                predecessor.get("status") == "completed" and predecessor.get("conclusion") == "success" and
                predecessor.get("labels") == [GATE_SELECTOR] and
                origin.wire.utc_epoch(predecessor.get("started_at")) <=
                origin.wire.utc_epoch(predecessor.get("completed_at")) <=
                origin.wire.utc_epoch(job["started_at"]), "GATE_PREDECESSOR")
    return job  # The exact selected original row; no new service observation.


def _ref(value, name, commit):
    require(value.get("ref") == "refs/heads/" + name and
            value.get("url") == origin.wire.ORIGIN + API + "/git/refs/heads/" + name, "REF_LOCATION")
    obj = identity.mapping(value.get("object"))
    require(obj.get("type") == "commit" and obj.get("sha") == commit and
            obj.get("url") == origin.wire.ORIGIN + API + "/git/commits/" + commit, "REF_COMMIT")


def _acquire_bootstrap(context, event_raw, git, invocation, token, retain, fence, original_work_end, now, expected):
    """Actual fixed-origin supplier composition; native enclosure is mandatory.

    Tests replace the transport, Git and clocks explicitly. There is no URL,
    response, selector/comment ID, environment ID or policy-absence override in
    the production interface. An error is retained before propagation; no retry.
    """
    require(type(invocation) is str and re.fullmatch(r"[0-9a-f]{32}", invocation), "INVOCATION")
    require(type(token) is str and re.fullmatch(r"[A-Za-z0-9_.-]{16,4096}", token), "READ_TOKEN")
    require(callable(retain) and callable(now), "OWNER_CALLBACKS")
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
                # Acquisition has returned these exact bytes, but the work
                # boundary failed BEFORE retention started. Offer them once
                # under the parent's original final fence, then keep failure.
                # Never retry an entered retainer or rewrite the HTTP record.
                try:
                    retain(label, raw, failed=True)
                except BaseException as secondary:
                    raise original from secondary
                originals[label] = raw
                raise
        # Failed originals use only the enclosing owner's existing final fence;
        # an exhausted work fence must not erase the primary HTTP failure.
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
        # These fixed endpoints must return complete single responses. Jobs and
        # branch-policy counts are also checked; no unbounded pagination follows.
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

    keep("event", event_raw)
    policy_inputs = _source(git, context, lambda: fence.now(limit=end))
    fence.now(limit=end)
    for label, raw in policy_inputs.items():
        keep(label, raw)
    github = context["github"]
    base = API + "/actions/runs/" + github["runId"]
    attempt_path = base + "/attempts/" + github["runAttempt"]
    attempt_raw, _ = get("attempt", attempt_path)
    jobs_raw, date = get("jobs", attempt_path + "/jobs?per_page=100&page=1")
    _run(context, identity.parse(attempt_raw, origin.wire.BODY_LIMIT),
         identity.parse(jobs_raw, origin.wire.BODY_LIMIT), date)
    approvals_raw, _ = get("approvals", base + "/approvals")
    selected = gate.select(stage="stage1", run_id=github["runId"], attempt=github["runAttempt"],
                           approvals_raw=approvals_raw)
    selector = identity.parse(selected.record, stages.LIMIT)
    comment_raw, _ = get("comment", API + "/issues/comments/" + str(selector["commentId"]))
    declaration, _, _ = stages.statement(stages.STAGE1, comment_raw, selector["commentId"], selector["bodySha256"])
    require(selector["environmentId"] == declaration["environment"]["id"], "APPROVED_ENVIRONMENT_CHANGED")
    environment_path = API + "/environments/" + stages.ENVIRONMENT
    environment_raw, _ = get("environment", environment_path)
    branches_raw, _ = get("branches", environment_path + "/deployment-branch-policies?per_page=100&page=1")
    gate.check_environment(declaration["environment"], environment_raw, branches_raw)
    # Fresh service ref observations, not only a stale local remote-tracking ref.
    for label, branch, commit in (("main", "main", stages.BASE["commit"]),
            ("reviewed_ref", stages.SOURCE_REF.removeprefix("refs/heads/"), context["source"]["commit"])):
        body, _ = get(label, API + "/git/ref/heads/" + branch)
        _ref(identity.parse(body, stages.LIMIT), branch, commit)
    require(_source(git, context, lambda: fence.now(limit=end)) == policy_inputs, "SOURCE_CHANGED_DURING_ACQUISITION")
    fence.now(limit=end)
    observed = {"repository": identity.REPOSITORY, "base": dict(stages.BASE), "reviewed": context["source"],
        "source": context["source"], "firstUseAt": context["firstUseAt"], "github": dict(github)}
    if context["kind"] == "gate":
        observed["inputs"] = context["inputs"]
        result = gate.eligible(stage="stage1", approvals_raw=approvals_raw, comment_raw=comment_raw,
            environment_raw=environment_raw, branches_raw=branches_raw, observation_raw=identity.encoded(observed),
            now=now(), expected=expected, **policy_inputs)
    else:
        observed["github"].update(profile=stages.bootstrap.PROFILE, selection=context["inputs"]["selection"])
        result = stages.match_bootstrap(comment_raw=comment_raw, comment_id=selector["commentId"],
            body_sha256=selector["bodySha256"], observation_raw=identity.encoded(observed), now=now(),
            expected=expected, **policy_inputs)
    keep("observation", identity.encoded(observed))
    keep("match", result.record)
    fence.now(limit=end)
    return result, tuple(originals.items())


def acquire_bootstrap(root, *, kind, query_runner, invocation, token, retain, fence, original_work_end,
                      first_use_at, expected=None):
    """Read the real event/environment, never override hosted identity in a CLI.

    Only the enclosing native owner can call this entry. It must keep the token
    in the private HTTP child boundary (never NativeGitQueries' serialized env),
    retain each original, and verify its own child retirement and enclosing
    return before use. This function does not supply those missing obligations.
    """
    env = dict(os.environ)
    root = Path(root)
    require(root.is_absolute() and root == root.resolve(strict=True) and
            env.get("GITHUB_WORKSPACE") == str(root), "WORKSPACE")
    event = identity.read_regular(Path(env.get("GITHUB_EVENT_PATH", "")), identity.EVENT_LIMIT)
    context = _context(env, event, kind, first_use_at)
    git = identity.GitView(root, env, query_runner)  # Its closed environment never contains token.
    return _acquire_bootstrap(context, event, git, invocation, token, retain, fence, original_work_end,
                             lambda: int(time.time()), expected)
