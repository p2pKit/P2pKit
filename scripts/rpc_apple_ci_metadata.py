"""Read-only metadata supplier for the separate ordinary-CI Apple context.

No Terminal launch, native admission, or permission changes occur here. In
particular a valid metadata result is not authorization to execute a product.
The caller must independently observe Git, run the maintained scope resolver,
verify tools/credentials/private state, and retain the original clock anchor.
"""
from __future__ import annotations

from datetime import datetime
import http.client
import json
import math
import re
import urllib.error
import urllib.request

from rpc_apple_ci_admission import (
    REPOSITORY, SCHEMA, SCOPE, admit_context, command_for, oid, require,
)

API = "https://api.github.com"
MAX_RESPONSE = 2 * 1024 * 1024
PROFILES = {"platform-checks": "platform-full", "artifact-checks": "consumers-complete"}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate metadata key")
        result[key] = value
    return result


def finite_decimal(value):
    result = float(value)
    require(math.isfinite(result), "Nonfinite metadata")
    return result


def decode_metadata(raw: bytes) -> dict:
    require(type(raw) is bytes and 0 < len(raw) <= MAX_RESPONSE, "Unbounded or empty metadata")
    try:
        value = json.loads(raw, object_pairs_hook=unique_object, parse_float=finite_decimal,
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite metadata")))
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("Invalid metadata encoding") from None
    require(type(value) is dict, "Metadata object required")
    return value


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file, code, message, headers, new_url):
        # Never forward even a read-only token to a redirect destination.
        return None


def github_json(path: str, token: str | None = None) -> dict:
    """GET only exact repository run/attempt endpoints; no polling or mutations.

    The 30-second timeout bounds individual blocking socket operations, NOT the
    whole acquisition: DNS and a slowly arriving body may exceed that interval.
    The caller must supervise the entire acquisition within its existing job
    deadline and retain ownership until it retires. This function does not
    provide that supervisor, renew a lease, or fall back to another attempt.
    Authentication is neither retained nor returned.
    """
    require(type(path) is str and re.fullmatch(
        r"/repos/p2pKit/P2pKit/actions/runs/[1-9][0-9]*/attempts/[1-9][0-9]*(?:/jobs\?per_page=100)?",
        path) is not None, "Unadmitted metadata endpoint")
    require(token is None or (type(token) is str and 0 < len(token) <= 4096 and
                            all(32 < ord(character) < 127 for character in token)), "Invalid API credential")
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "P2pKit-ordinary-CI-context-metadata"}
    if token is not None:
        headers["Authorization"] = "Bearer " + token
    request = urllib.request.Request(API + path, headers=headers, method="GET")
    try:
        # Do not inherit proxy destinations or accept redirects for this request.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirects())
        with opener.open(request, timeout=30) as response:
            require(response.status == 200 and response.url == API + path, "Unexpected metadata response")
            return decode_metadata(response.read(MAX_RESPONSE + 1))
    except urllib.error.HTTPError as error:
        # HTTPError retains the denied response stream before our context
        # manager is entered. Retire it rather than relying on garbage collection.
        try:
            error.close()
        finally:
            raise ValueError("GitHub metadata acquisition failed") from None
    except (OSError, urllib.error.URLError, http.client.HTTPException):
        # Neither exception URLs, token-bearing requests, nor response bodies
        # belong in a diagnostic or forwarded evidence record.
        raise ValueError("GitHub metadata acquisition failed") from None


def positive_text(value, label):
    require(type(value) is str and re.fullmatch(r"[1-9][0-9]{0,18}", value) is not None,
            "Invalid " + label)
    number = int(value)
    require(number < 2**63, "Oversized " + label)
    return number


def timestamp(value):
    require(type(value) is str and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value) is not None,
            "Missing exact job start")
    try:
        return datetime.fromisoformat(value.removesuffix("Z") + "+00:00").timestamp()
    except (ValueError, OverflowError, OSError):
        raise ValueError("Invalid job start") from None


def project_context(env: dict, event: dict, checkout: dict, resolved_scope: dict,
                    run: dict, jobs: dict, *, root: str, python: str) -> dict:
    """Cross-check actual event/Git and exact-attempt API documents.

    For PRs API head_sha is the branch head, NOT the synthetic GITHUB_SHA being
    tested. The independently observed Git parents prove the latter. API job
    started_at (not a new Terminal-launch time) anchors the original 60 minutes.
    Returned runner/job identifiers must stay in the private binding, not public
    payload evidence. API dictionaries may add fields; only this closed
    projection crosses the future execution boundary.
    """
    require(all(type(value) is dict for value in (env, event, checkout, resolved_scope, run, jobs)),
            "Missing source/event/API observation")
    require(env.get("GITHUB_ACTIONS") == "true" and env.get("GITHUB_REPOSITORY") == REPOSITORY and
            env.get("GITHUB_SERVER_URL") == "https://github.com" and env.get("GITHUB_API_URL") == API and
            env.get("RUNNER_ENVIRONMENT") == "github-hosted" and env.get("RUNNER_OS") == "macOS" and
            env.get("RUNNER_ARCH") in ("ARM64", "X64"), "Wrong hosted CI context")
    job_name = env.get("GITHUB_JOB")
    require(type(job_name) is str and job_name in PROFILES, "Unknown complete CI job")
    run_id = positive_text(env.get("GITHUB_RUN_ID"), "run ID")
    attempt = positive_text(env.get("GITHUB_RUN_ATTEMPT"), "attempt")
    require(attempt < 2**31, "Oversized attempt")
    sha = env.get("GITHUB_SHA")
    require(oid(sha), "Exact event SHA required")
    require(env.get("GITHUB_WORKSPACE") == root and
            env.get("GITHUB_WORKFLOW_REF") == f'{REPOSITORY}/.github/workflows/ci.yml@{env.get("GITHUB_REF")}',
            "Wrong workflow source or workspace")
    require(type(event.get("repository")) is dict and event["repository"].get("full_name") == REPOSITORY,
            "Event repository differs")
    pr = None
    event_name = env.get("GITHUB_EVENT_NAME")
    expected_head = sha
    if event_name == "pull_request":
        pull = event.get("pull_request")
        require(type(pull) is dict and type(pull.get("base")) is dict and type(pull.get("head")) is dict,
                "Missing PR event parents")
        base_repo = pull["base"].get("repo")
        require(type(base_repo) is dict and base_repo.get("full_name") == REPOSITORY,
                "PR base repository differs")
        pr = {"number": event.get("number"), "base": pull["base"].get("sha"), "head": pull["head"].get("sha")}
        expected_head = pr["head"]
    elif event_name == "push":
        require(event.get("after") == sha and event.get("ref") == env.get("GITHUB_REF") and
                event.get("deleted") is False, "Push event source differs")
    require(type(run.get("id")) is int and run["id"] == run_id and
            type(run.get("run_attempt")) is int and run["run_attempt"] == attempt and
            run.get("event") == event_name and run.get("head_sha") == expected_head and
            run.get("path") == ".github/workflows/ci.yml" and run.get("status") == "in_progress" and
            "conclusion" in run and run["conclusion"] is None and type(run.get("repository")) is dict and
            run["repository"].get("full_name") == REPOSITORY,
            "Run/attempt/workflow/source metadata mismatch")
    rows = jobs.get("jobs")
    require(type(rows) is list and type(jobs.get("total_count")) is int and
            0 < jobs["total_count"] == len(rows) <= 100 and all(type(row) is dict for row in rows),
            "Incomplete or ambiguous job inventory")
    matches = [row for row in rows if row.get("name") == job_name]
    require(len(matches) == 1, "Exact non-matrix CI job is missing or ambiguous")
    job = matches[0]
    require(type(job.get("id")) is int and job["id"] > 0 and
            type(job.get("run_id")) is int and job["run_id"] == run_id and
            type(job.get("run_attempt")) is int and job["run_attempt"] == attempt and
            job.get("head_sha") == expected_head and job.get("status") == "in_progress" and
            "conclusion" in job and job["conclusion"] is None and
            "completed_at" in job and job["completed_at"] is None and
            job.get("runner_name") == env.get("RUNNER_NAME") and
            type(job.get("runner_name")) is str and bool(job["runner_name"]) and
            type(job.get("runner_id")) is int and job["runner_id"] > 0,
            "Current job/worker/attempt metadata mismatch")
    profile = PROFILES[job_name]
    binding = {"schema": SCHEMA, "scope": SCOPE, "repository": REPOSITORY, "event": event_name,
               "ref": env.get("GITHUB_REF"), "runId": run_id, "runAttempt": attempt, "profile": profile,
               "source": {"commit": sha, "tree": checkout.get("tree")}, "ciScope": resolved_scope,
               "pr": pr, "root": root, "python": python, "argv": command_for(profile, root, python)}
    observed_run = {key: binding[key] for key in
                    ("repository", "event", "ref", "runId", "runAttempt", "profile")}
    observed_run["sha"] = sha
    admitted = admit_context(binding, checkout, observed_run)
    return {"binding": admitted, "observedRun": observed_run,
            "job": {"id": job["id"], "name": job_name, "runnerId": job["runner_id"],
                    "runnerName": job["runner_name"], "startedWall": timestamp(job.get("started_at"))},
            "nativeExecutionAuthorized": False, "cleanupVerified": False}
