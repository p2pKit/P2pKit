#!/usr/bin/env python3
"""Promote existing, reviewed main sample artifacts to a development prerelease.

No compiler, Gradle, signing, cache, app execution or library publication here.
admit/verify/prepare-review are read-only. publish requires a fresh protected
environment approval of the exact review request, repeats admission before any
mutation, and never replaces tags/releases/assets. No private evidence is opened.
"""

import argparse
import base64
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile


ROOT = Path(__file__).resolve().parents[1]
REPO = "p2pKit/P2pKit"
API = "https://api.github.com"
PREFIX = "/repos/" + REPO
WORKFLOW = ".github/workflows/sample-development-releases.yml"
PRODUCER = ".github/workflows/desktop-cross-host.yml"
MAVEN_WORKFLOW = ".github/workflows/publish-maven-central.yml"
MAVEN_NAME = "Publish Maven Central"
TRIGGERS = {"Desktop cross-host": PRODUCER, "CI": ".github/workflows/ci.yml",
            "OSV Advisory Scan": ".github/workflows/osv-scanner.yml"}
MAIN_EVENTS = {PRODUCER: ("push",),
               ".github/workflows/ci.yml": ("push", "schedule", "workflow_dispatch"),
               ".github/workflows/osv-scanner.yml": ("push", "schedule", "workflow_dispatch")}
REQUIRED = {"complete-gate", "review", "scan / osv-scan", "osv-scanner"}
# All protected contexts remain mandatory on the reviewed PR head. Dependency
# review and Code Scanning's PR result are not duplicate postmerge checks;
# main must pass the real CI and fail-closed OSV workflow jobs for its exact SHA.
MAIN_REQUIRED = {"complete-gate", "scan / osv-scan"}
OWNER_LOGIN, OWNER_ID = "Apdelrahman1911", 104788132
ENVIRONMENT = "sample-development-release"
RELEASE_MARKER = "[release ci]"
APPROVE_PR = "/p2pkit approve-pr "
RETENTION_SECONDS = 14 * 24 * 60 * 60
CHECK_WORKFLOWS = {"complete-gate": ".github/workflows/ci.yml",
                   "review": ".github/workflows/dependency-review.yml",
                   "scan / osv-scan": ".github/workflows/osv-scanner.yml"}
MIB = 1024**2
JSON_LIMIT = 4 * MIB
ARCHIVE_LIMIT = 1024 * MIB
TRANSFER_LIMIT = 4 * ARCHIVE_LIMIT + 64 * MIB
SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
SPEC = importlib.util.spec_from_file_location("sample_packager", ROOT / "scripts/package-sample-apps.py")
PACK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PACK)
VERSION = PACK.IDENTITY.VERSION


class Hold(ValueError):
    pass


def need(value, reason):
    if not value:
        raise Hold(reason)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()


def parsed(raw):
    need(0 < len(raw) <= JSON_LIMIT, "JSON size outside bound")
    return json.loads(raw, object_pairs_hook=PACK.unique_pairs,
                      parse_constant=lambda _: need(False, "Nonfinite JSON"))


def number(value):
    need(re.fullmatch(r"[1-9][0-9]{0,19}", str(value)) is not None, "Invalid GitHub numeric identity")
    return int(value)


def timestamp(value):
    need(type(value) is str and re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z", value),
         "Missing exact GitHub UTC timestamp")
    try:
        return int(datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc).timestamp())
    except ValueError:
        raise Hold("Invalid GitHub UTC timestamp") from None


def is_owner(user):
    return (type(user) is dict and type(user.get("id")) is int and user["id"] == OWNER_ID and
            user.get("login") == OWNER_LOGIN and user.get("type") == "User")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None


class Api:
    def __init__(self, token):
        need(token and "\n" not in token and "\r" not in token, "Missing API credential")
        self.token, self.transferred = token, 0
        self.opener = urllib.request.build_opener(NoRedirect)

    def open(self, url, *, method="GET", data=None, binary=False, authenticated=True, size=None):
        headers = {"User-Agent": "P2pKit-development-samples", "X-GitHub-Api-Version": "2022-11-28",
                   # Artifact redirects and upload responses are GitHub JSON APIs.
                   # Only the anonymous storage response is requested as binary.
                   "Accept": "application/octet-stream" if binary and not authenticated else "application/vnd.github+json"}
        if authenticated:
            need(url.startswith(API + PREFIX + "/") or url.startswith("https://uploads.github.com" + PREFIX + "/"),
                 "Credential destination outside this repository")
            headers["Authorization"] = "Bearer " + self.token
        if data is not None:
            headers["Content-Type"] = "application/octet-stream" if binary else "application/json"
        if size is not None:
            headers["Content-Length"] = str(size)
        return self.opener.open(urllib.request.Request(url, headers=headers, method=method, data=data), timeout=30)

    def json(self, path, *, method="GET", value=None, missing=False, upload=None):
        need(path.startswith("/") and ".." not in path and "#" not in path, "Invalid API path")
        try:
            if upload is None:
                response = self.open(API + PREFIX + path, method=method,
                                     data=None if value is None else encoded(value))
            else:
                with upload.open("rb") as stream:
                    response = self.open("https://uploads.github.com" + PREFIX + path, method="POST", data=stream,
                                         binary=True, size=upload.stat().st_size)
                    with response:
                        return parsed(response.read(JSON_LIMIT + 1))
            with response:
                return parsed(response.read(JSON_LIMIT + 1))
        except urllib.error.HTTPError as error:
            if missing and error.code == 404:
                return None
            # Do not emit bodies, tokens or signed redirect URLs.
            raise Hold("GitHub API HTTP " + str(error.code)) from None

    def pages(self, path, key=None):
        rows = []
        for page in range(1, 11):
            value = self.json(path + ("&" if "?" in path else "?") + f"per_page=100&page={page}")
            items = value if key is None else value.get(key)
            need(isinstance(items, list) and len(items) <= 100, "Unexpected API page shape")
            rows.extend(items)
            if len(items) < 100:
                if key and "total_count" in value:
                    need(value["total_count"] == len(rows), "Incomplete API collection")
                return rows
        raise Hold("API pagination bound exceeded")

    def download(self, artifact, destination):
        size, expected = artifact["size_in_bytes"], artifact["digest"].removeprefix("sha256:")
        need(type(size) is int and 0 < size <= ARCHIVE_LIMIT and self.transferred + size <= TRANSFER_LIMIT,
             "Artifact transfer exceeds finite budget")
        url = API + PREFIX + f"/actions/artifacts/{number(artifact['id'])}/zip"
        try:
            response = self.open(url, binary=True)
        except urllib.error.HTTPError as error:
            need(error.code in (301, 302, 303, 307), "Artifact download did not yield a supported redirect")
            location = error.headers.get("Location", "")
            target = urllib.parse.urlsplit(location)
            need(target.scheme == "https" and target.username is None and target.password is None and
                 target.port in (None, 443) and target.hostname and
                 (target.hostname.endswith(".blob.core.windows.net") or
                  target.hostname.endswith(".actions.githubusercontent.com")), "Unexpected artifact storage host")
            response = self.open(location, binary=True, authenticated=False)
        deadline, count, digest = time.monotonic() + 600, 0, hashlib.sha256()
        with response, destination.open("xb") as output:
            while True:
                need(time.monotonic() < deadline, "Artifact transfer deadline exceeded")
                block = response.read(min(MIB, size - count + 1))
                if not block:
                    break
                count += len(block)
                self.transferred += len(block)
                need(count <= size and self.transferred <= TRANSFER_LIMIT, "Artifact grew beyond its byte budget")
                output.write(block)
                digest.update(block)
        need(count == size and digest.hexdigest() == expected, "Downloaded artifact differs from GitHub digest/size")

    def public_probe(self, tag, asset):
        """Verify the entire anonymously downloadable asset, not a range probe.

        No token, cookies, Range, or compressed transfer. Redirect destinations
        are allowlisted independently; signed storage URLs are never logged.
        """
        need(type(asset.get("bytes")) is int and 0 < asset["bytes"] <= PACK.MAX_FILE and
             re.fullmatch(r"[0-9a-f]{64}", asset.get("sha256", "")), "Invalid public asset size/hash")
        url = "https://github.com/" + REPO + "/releases/download/" + urllib.parse.quote(tag, safe="") + "/" + \
              urllib.parse.quote(asset["file"], safe="")
        deadline = time.monotonic() + 600
        for _ in range(3):
            target = urllib.parse.urlsplit(url)
            need(target.scheme == "https" and target.hostname in ("github.com", "release-assets.githubusercontent.com") and
                 target.username is None and target.password is None and target.port in (None, 443) and not target.fragment,
                 "Unexpected public asset destination")
            need(time.monotonic() < deadline, "Anonymous download deadline exceeded")
            request = urllib.request.Request(url, headers={"User-Agent": "P2pKit-development-samples", "Accept-Encoding": "identity"})
            try:
                response = self.opener.open(request, timeout=30)
            except urllib.error.HTTPError as error:
                need(error.code in (301, 302, 303, 307, 308), "Anonymous Release download failed")
                url = error.headers.get("Location", "")
                error.close()
                continue
            with response:
                need(response.status == 200 and response.headers.get("Content-Range") is None and
                     response.headers.get("Content-Encoding", "identity") == "identity" and
                     response.headers.get("Content-Length", str(asset["bytes"])) == str(asset["bytes"]),
                     "Anonymous Release response is partial, encoded or differently sized")
                count, digest = 0, hashlib.sha256()
                while True:
                    need(time.monotonic() < deadline, "Anonymous download deadline exceeded")
                    block = response.read(min(MIB, asset["bytes"] - count + 1))
                    if not block:
                        break
                    count += len(block)
                    need(count <= asset["bytes"], "Anonymous download exceeds its recorded size")
                    digest.update(block)
                need(count == asset["bytes"] and digest.hexdigest() == asset["sha256"],
                     "Anonymous full-download size/hash differs")
            return
        raise Hold("Anonymous Release redirect bound exceeded")


def hosted_context(env, operation=None):
    need(env.get("GITHUB_ACTIONS") == "true" and env.get("RUNNER_ENVIRONMENT") == "github-hosted" and
         env.get("GITHUB_REPOSITORY") == REPO and env.get("GITHUB_REF") == "refs/heads/main" and
         env.get("GITHUB_SERVER_URL") == "https://github.com" and env.get("GITHUB_API_URL") == API and
         env.get("GITHUB_WORKFLOW_REF") == REPO + "/" + WORKFLOW + "@refs/heads/main",
         "Sample publication requires the genuine main workflow")
    sha = env.get("GITHUB_WORKFLOW_SHA", "")
    need(SHA.fullmatch(sha) and env.get("GITHUB_SHA") == sha, "Invalid publisher source identity")
    need(env.get("GITHUB_EVENT_NAME") in ("workflow_run", "workflow_dispatch"), "Unsupported publisher event")
    for key in ("GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT"):
        number(env.get(key, ""))
    if operation is not None:
        jobs = {"admit": "admit", "verify": "verify-only", "prepare-review": "prepare-review", "publish": "publish"}
        need(operation == "cleanup" and env.get("GITHUB_JOB") in ("verify-only", "prepare-review", "publish") or
             operation in jobs and env.get("GITHUB_JOB") == jobs[operation], "Wrong publisher operation/job")
    return {"source": sha, "run": int(env["GITHUB_RUN_ID"]), "attempt": int(env["GITHUB_RUN_ATTEMPT"])}


def trusted_run(run, path, sha, events):
    if isinstance(events, str):
        events = (events,)
    need(run.get("path") == path and run.get("head_sha") == sha and run.get("event") in events and
         run.get("repository", {}).get("full_name") == REPO and
         run.get("head_repository", {}).get("full_name") == REPO, "Wrong workflow/source/repository/event")
    need(run.get("status") == "completed" and run.get("conclusion") == "success", "Workflow is not successful")
    if run["event"] != "pull_request":
        need(run.get("head_branch") == "main", "Workflow is not on main")
    number(run["id"])
    number(run["run_attempt"])


def trigger_source(api, event):
    if event.get("name") == MAVEN_NAME:
        publication = maven_publication(api, event["head_sha"], event["id"], event["run_attempt"])
        need(event.get("head_branch") == publication["tag"], "Maven completion tag differs from the original run")
        return event["head_sha"]
    raise Hold("Only verified Maven completion can trigger application publication")


def source_version(api, sha):
    properties = api.json(f"/contents/gradle.properties?ref={sha}")
    need(properties.get("type") == "file" and properties.get("path") == "gradle.properties" and
         properties.get("encoding") == "base64" and type(properties.get("size")) is int and
         0 < properties["size"] <= 65536 and type(properties.get("content")) is str and
         len(properties["content"]) <= 131072, "Missing or oversized canonical version metadata")
    raw = base64.b64decode(properties["content"].replace("\n", ""), validate=True)
    need(len(raw) == properties["size"], "Canonical version metadata size differs")
    try:
        value = VERSION.from_properties(raw.decode("utf-8"))
    except ValueError:
        raise Hold("Canonical source version metadata is invalid or ambiguous") from None
    name = value["canonicalVersion"]
    need(not name.endswith("-SNAPSHOT") and tuple(map(int, name.split("-")[0].split("."))) >= (0, 8, 0),
         "Publication requires a non-snapshot 0.8.0+ version under the existing compatibility policy")
    return value


def maven_invocation(api, sha, identifier, attempt, *, completed):
    """Bind a tag-run separately from ordinary main builds, before or after upload."""
    need(type(sha) is str and SHA.fullmatch(sha), "Invalid Maven source SHA")
    identifier, attempt = number(identifier), number(attempt)
    run = api.json(f"/actions/runs/{identifier}/attempts/{attempt}")
    workflow = api.json("/actions/workflows/publish-maven-central.yml")
    need(run.get("id") == identifier and run.get("run_attempt") == attempt and
         run.get("path") == workflow.get("path") == MAVEN_WORKFLOW and
         run.get("workflow_id") == workflow.get("id") and type(workflow.get("id")) is int and
         run.get("head_sha") == sha and run.get("event") == "push" and
         run.get("repository", {}).get("full_name") == REPO and
         run.get("head_repository", {}).get("full_name") == REPO,
         "Maven run/source/attempt/workflow is not the exact tag push")
    if completed:
        need(run.get("status") == "completed" and run.get("conclusion") == "success",
             "Maven publication attempt is not successful")
    else:
        current = api.json(f"/actions/runs/{identifier}")
        need(current.get("id") == identifier and current.get("run_attempt") == attempt and
             run.get("status") == current.get("status") == "in_progress" and
             run.get("conclusion") is current.get("conclusion") is None,
             "Preflight requires the current in-progress Maven attempt, never a completed publication")
    tag = run.get("head_branch", "")
    need(type(tag) is str and re.fullmatch(r"v[0-9][0-9A-Za-z._+-]{0,99}", tag) and
         "SNAPSHOT" not in tag.upper(), "Maven publication lacks a safe non-snapshot version tag")
    ref = api.json("/git/ref/tags/" + urllib.parse.quote(tag, safe=""))
    need(ref.get("ref") == "refs/tags/" + tag, "Maven tag reference differs")
    target = ref.get("object", {})
    for _ in range(4):
        need(SHA.fullmatch(target.get("sha", "")), "Maven tag lacks an immutable object")
        if target.get("type") != "tag":
            break
        annotated = api.json("/git/tags/" + target["sha"])
        need(annotated.get("sha") == target["sha"], "Annotated Maven tag lookup differs")
        target = annotated.get("object", {})
    need(target.get("type") == "commit" and target.get("sha") == sha,
         "Immutable Maven tag does not resolve to this exact source")
    need(source_version(api, sha)["canonicalVersion"] == tag[1:],
         "Maven tag does not match the canonical source version")
    return {"id": identifier, "attempt": attempt, "workflowId": workflow["id"], "workflowPath": MAVEN_WORKFLOW,
            "source": sha, "tag": tag, "version": tag[1:], "tagObject": ref["object"]["sha"]}


def maven_publication(api, sha, identifier, attempt):
    """Only successful original verification/freeze/publication jobs are delivery authority."""
    invocation = maven_invocation(api, sha, identifier, attempt, completed=True)
    identifier, attempt = invocation["id"], invocation["attempt"]
    jobs = api.pages(f"/actions/runs/{identifier}/attempts/{attempt}/jobs", "jobs")
    verified = []
    for name in ("freeze-applications", "verify-release", "publish-release"):
        found = [x for x in jobs if x.get("name") == name]
        need(len(found) == 1 and found[0].get("run_id") == identifier and found[0].get("run_attempt") == attempt and
             found[0].get("head_sha") == sha and found[0].get("status") == "completed" and
             found[0].get("conclusion") == "success", "Missing successful original Maven verification/publication job")
        job = found[0]
        need(timestamp(job.get("completed_at")) <= time.time(), "Maven job completion is not in the past")
        verified.append({"id": number(job["id"]), "name": name, "completedAt": job["completed_at"]})
    return {**invocation, "jobs": verified}


def frozen_publication_plan(api, publication, binding=None):
    """Load only this Maven attempt's immutable set, never reselect applications."""
    spec = importlib.util.spec_from_file_location("release_application_set", ROOT / "scripts/release_application_set.py")
    frozen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(frozen)
    parent = Path(os.environ["RUNNER_TEMP"])
    PACK.physical_directory(parent)
    options = {} if binding is None else {"artifact_id": binding["artifact"]["id"], "expected_hash": binding["sha256"]}
    with tempfile.TemporaryDirectory(prefix="p2pkit-frozen-apps-", dir=parent) as temporary:
        try:
            return frozen.publication_plan(api, publication, Path(temporary), **options)
        except frozen.P.Hold as error:
            # Independently loaded policy has its own Hold type; preserve only
            # its deliberate public reason, never arbitrary backend details.
            raise Hold(str(error)) from None


def revalidate_plan(api, plan):
    publication = plan["mavenPublication"]
    current = maven_publication(api, plan["source"]["commit"], publication["id"], publication["attempt"])
    need(current == publication and frozen_publication_plan(api, current, plan["frozenApplicationSet"]) == plan,
         "Original Maven publication/frozen set/gates/evidence changed")


def latest(rows, reason):
    need(rows, reason)
    return max(rows, key=lambda row: number(row["id"]))


def checks(api, sha, contexts, event, pull_number=None):
    rows = api.pages(f"/commits/{sha}/check-runs?filter=all", "check_runs")
    result = []
    for name in sorted(contexts):
        row = latest([x for x in rows if x.get("name") == name], "Missing required check: " + name)
        need(row.get("head_sha") == sha and row.get("status") == "completed" and row.get("conclusion") == "success",
             "Required check not successful: " + name)
        app = row.get("app", {}).get("slug")
        if name == "osv-scanner":
            need(app == "github-code-scanning", "Unexpected OSV required-check publisher")
        else:
            need(app == "github-actions", "Unexpected required-check publisher")
            match = re.fullmatch(r"https://github\.com/" + re.escape(REPO) + r"/actions/runs/([1-9][0-9]*)/job/([1-9][0-9]*)",
                                 row.get("details_url", ""))
            need(match and int(match[2]) == row["id"], "Required check lacks exact workflow/job identity")
            run = api.json("/actions/runs/" + match[1])
            path = CHECK_WORKFLOWS[name]
            trusted_run(run, path, sha, MAIN_EVENTS[path] if event == "main" else event)
            if pull_number is not None:
                need(any(x.get("number") == pull_number and x.get("head", {}).get("sha") == sha
                         for x in run.get("pull_requests", [])), "Check does not bind the reviewed PR head")
        result.append({"id": row["id"], "name": name, "sha": sha, "app": app,
                       "completedAt": row["completed_at"], "url": row["details_url"]})
        if app == "github-actions":
            result[-1]["run"] = {"id": number(run["id"]), "attempt": number(run["run_attempt"]), "workflow": path}
    return result


def approved_pull(api, sha, commit):
    linked = api.pages(f"/commits/{sha}/pulls")
    candidates = [x for x in linked if x.get("merged_at") and x.get("merge_commit_sha") == sha and
                  x.get("base", {}).get("ref") == "main"]
    need(len(candidates) == 1, "Candidate lacks one exact merged main PR")
    pull = api.json("/pulls/" + str(number(candidates[0]["number"])))
    head = pull["head"]["sha"]
    need(SHA.fullmatch(head) and pull.get("merged") is True and pull.get("merge_commit_sha") == sha and
         pull.get("base", {}).get("repo", {}).get("full_name") == REPO and
         pull.get("head", {}).get("repo", {}).get("full_name") == REPO and
         [x["sha"] for x in commit.get("parents", [])][1:] == [head],
         "Require the normal history-preserving merge of the reviewed final head")
    need(is_owner(pull.get("user")) and is_owner(pull.get("merged_by")) and pull.get("auto_merge") is None,
         "Require the owner's PR and manual owner merge, never automatic approval/merge")
    reviews = api.pages(f"/pulls/{pull['number']}/reviews")
    decisive = {}
    for review in sorted(reviews, key=lambda x: number(x["id"])):
        if review.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            decisive[review["user"]["login"]] = review
    need(not any(x["state"] == "CHANGES_REQUESTED" for x in decisive.values()), "Unresolved formal change request")
    required = checks(api, head, REQUIRED, "pull_request", pull["number"])
    merged = timestamp(pull["merged_at"])
    need(all(timestamp(x["completedAt"]) <= merged for x in required),
         "PR check evidence is not pre-merge")
    # GitHub cannot accept a native APPROVED review from the PR's own author.
    # This is the explicitly owner-authorized replacement, not a fabricated review.
    comments = api.pages(f"/issues/{pull['number']}/comments")
    approval = latest([x for x in comments if is_owner(x.get("user")) and type(x.get("body")) is str and
                       x["body"].strip().startswith(APPROVE_PR.rstrip())], "Missing manual owner PR authorization")
    need(approval["body"].strip() == APPROVE_PR + head, "Owner authorization is not for the exact final PR head")
    created, updated = timestamp(approval.get("created_at")), timestamp(approval.get("updated_at"))
    # REST identifies the original author, not the editor of a changed body.
    # Require a newly posted, recorded-unedited command; corrections need a new
    # owner comment rather than attributing an unknown editor's text to them.
    need(max(timestamp(x["completedAt"]) for x in required) <= created == updated <= merged,
         "Owner authorization must be unedited, follow required PR checks and precede merge")
    comment_id = number(approval["id"])
    link = f"https://github.com/{REPO}/pull/{pull['number']}#issuecomment-{comment_id}"
    need(approval.get("html_url") == link, "Owner authorization comment does not belong to this PR")
    return {"number": pull["number"], "head": head, "merge": sha, "mergedAt": pull["merged_at"],
            "ownerAuthorization": {"id": comment_id, "owner": OWNER_LOGIN, "ownerId": OWNER_ID, "commit": head,
                "createdAt": approval["created_at"], "updatedAt": approval["updated_at"], "url": link,
                "bodySha256": hashlib.sha256(approval["body"].encode("utf-8")).hexdigest()},
            "checks": required}


def artifact_identity(item, run_id, sha, branch="main"):
    need(item.get("expired") is False and DIGEST.fullmatch(item.get("digest", "")) and
         type(item.get("size_in_bytes")) is int and 0 < item["size_in_bytes"] <= ARCHIVE_LIMIT and
         item.get("workflow_run", {}).get("id") == run_id and
         item["workflow_run"].get("head_sha") == sha and item["workflow_run"].get("head_branch") == branch,
         "Expired/unbound artifact or unavailable digest")
    created, expires = timestamp(item.get("created_at")), timestamp(item.get("expires_at"))
    need(created <= time.time() < expires <= created + RETENTION_SECONDS,
         "Artifact is expired or exceeds the fourteen-day retention policy")
    number(item["id"])
    return {key: item[key] for key in ("id", "name", "size_in_bytes", "digest", "created_at", "expires_at")}


def evidence_set(api, source, producer, artifacts, applications, main_checks):
    """Bind original encrypted uploads, not their plaintext or a test verdict.

    The owner must retrieve/decrypt these exact artifacts and check the internal
    source/policy/receipts before approving. Merely naming an upload is not that
    inspection. No ciphertext is duplicated into the Release or review artifact.
    """
    result = []
    for application in applications:
        if application["platform"] == "android":
            continue  # Android packaging shares the Linux Desktop invocation.
        runner = {"linux": "Linux", "windows": "Windows", "macos": "macOS"}[application["platform"]]
        name = f"ordinary-desktop-evidence-{runner}-{application['architecture'].upper()}-{source}-{producer['id']}-{producer['attempt']}"
        found = [x for x in artifacts if x.get("name") == name]
        need(len(found) == 1, "Missing/ambiguous original Desktop encrypted evidence")
        result.append({**artifact_identity(found[0], producer["id"], source), "profile": "desktop",
                       "run": {"id": producer["id"], "attempt": producer["attempt"], "workflow": PRODUCER}})
    full = next(x["run"] for x in main_checks if x["name"] == "complete-gate")
    names = [f"ordinary-full-evidence-macOS-{arch}-{source}-{full['id']}-{full['attempt']}" for arch in ("ARM64", "X64")]
    found = [x for x in api.pages(f"/actions/runs/{full['id']}/artifacts", "artifacts") if x.get("name") in names]
    need(len(found) == 1, "Missing/ambiguous original FULL encrypted evidence")
    result.append({**artifact_identity(found[0], full["id"], source), "profile": "full", "run": full})
    need(len({x["id"] for x in result + applications}) == len(result + applications), "Evidence/application artifact IDs overlap")
    return result


def admit(api, sha, producer_id=None, attempt=None, publication=None):
    need(isinstance(sha, str) and SHA.fullmatch(sha), "Expected a full source SHA")
    maven = None if publication is None else maven_publication(api, sha, publication["id"], publication["attempt"])
    rules = api.json("/rules/branches/main")
    names = {check["context"] for rule in rules if rule.get("type") == "required_status_checks"
             for check in rule.get("parameters", {}).get("required_status_checks", [])}
    need(names == REQUIRED and any(x.get("type") == "pull_request" for x in rules) and
         any(x.get("type") == "required_status_checks" and x.get("parameters", {}).get("strict_required_status_checks_policy") is True
             for x in rules),
         "Required-check/protected-PR policy changed; review it, do not bypass it")
    commit = api.json("/commits/" + sha)
    need(commit.get("sha") == sha, "Commit lookup mismatch")
    message = commit.get("commit", {}).get("message")
    need(type(message) is str and len(message.encode("utf-8")) <= 65536 and RELEASE_MARKER in message,
         "Actual main merge commit lacks the exact case-sensitive [release ci] marker")
    tree = commit.get("commit", {}).get("tree", {}).get("sha", "")
    need(SHA.fullmatch(tree), "Missing exact source tree")
    version = source_version(api, sha)
    main = api.json("/git/ref/heads/main")["object"]["sha"]
    comparison = api.json(f"/compare/{sha}...{main}")
    need(comparison.get("status") in ("identical", "ahead") and
         comparison.get("merge_base_commit", {}).get("sha") == sha, "Candidate is not preserved in main")
    pull = approved_pull(api, sha, commit)
    main_checks = checks(api, sha, MAIN_REQUIRED, "main")
    if producer_id is None:
        runs = api.pages("/actions/workflows/desktop-cross-host.yml/runs?event=push&branch=main&head_sha=" + sha,
                         "workflow_runs")
        need(len(runs) == 1, "Require one exact main push producer; never select latest or substitute a run")
        run = runs[0]
        producer_id = number(run["id"])
    producer_id = number(producer_id)
    run = api.json("/actions/runs/" + str(producer_id))
    trusted_run(run, PRODUCER, sha, "push")
    workflow = api.json("/actions/workflows/desktop-cross-host.yml")
    need(workflow.get("path") == PRODUCER and run.get("workflow_id") == workflow.get("id"), "Wrong producer workflow ID")
    selected_attempt = number(run["run_attempt"])
    need(attempt is None or number(attempt) == selected_attempt, "Producer attempt differs; never mix reruns")
    jobs = api.pages(f"/actions/runs/{producer_id}/attempts/{selected_attempt}/jobs", "jobs")
    hosts = ["ubuntu-latest", "windows-latest", "macos-15"]
    for host in hosts:
        found = [x for x in jobs if x.get("name") == host]
        need(len(found) == 1 and found[0].get("conclusion") == "success" and found[0].get("status") == "completed" and
             found[0].get("run_id") == producer_id and found[0].get("run_attempt") == selected_attempt,
             "All three native host jobs must succeed in the same attempt")
    artifacts = api.pages(f"/actions/runs/{producer_id}/artifacts", "artifacts")
    suffix = f"-{sha}-{producer_id}-{selected_attempt}"
    selected = []
    for platform, prefix in (("android", "sample-android"), ("linux", "sample-desktop-Linux-"),
                             ("windows", "sample-desktop-Windows-"), ("macos", "sample-desktop-macOS-")):
        matches = [x for x in artifacts if x["name"] == prefix + suffix] if platform == "android" else [
            x for x in artifacts if x["name"] in [prefix + arch + suffix for arch in ("X64", "ARM64")]]
        need(len(matches) == 1, "Missing/ambiguous same-attempt sample artifact: " + platform)
        item = matches[0]
        arch = "apk-abis-not-inspected" if platform == "android" else (
            "arm64" if item["name"].startswith(prefix + "ARM64-") else "x64")
        selected.append({**artifact_identity(item, producer_id, sha), "platform": platform, "architecture": arch})
    need(len({x["id"] for x in selected}) == 4 and sum(x["size_in_bytes"] for x in selected) <= TRANSFER_LIMIT,
         "Artifact set duplicates/exceeds transfer budget")
    producer = {"id": producer_id, "attempt": selected_attempt, "workflowId": run["workflow_id"],
                "workflowPath": PRODUCER, "jobs": [{"id": x["id"], "name": x["name"]} for x in jobs if x["name"] in hosts]}
    need([(x["platform"], x["architecture"]) for x in selected] ==
         [("android", "apk-abis-not-inspected"), ("linux", "x64"), ("windows", "x64"), ("macos", "arm64")],
         "Require Android, Linux x64, Windows x64 and native macOS ARM64")
    plan = {"schema": 3, "source": {"commit": sha, "tree": tree}, "versionBinding": version,
            "tag": "samples-v" + version["canonicalVersion"], "producer": producer,
            "pullRequest": pull, "mainChecks": main_checks, "artifacts": selected, "scope": PACK.SCOPE,
            "evidence": evidence_set(api, sha, producer, artifacts, selected, main_checks)}
    if maven is not None:
        need([(x["platform"], x["architecture"]) for x in selected] ==
             [("android", "apk-abis-not-inspected"), ("linux", "x64"), ("windows", "x64"), ("macos", "arm64")],
             "Maven sample delivery requires Android, Linux x64, Windows x64 and native macOS ARM64")
        plan.update(tag="samples-" + maven["tag"], mavenPublication=maven)
    return plan


def publication_environment(api):
    environment = api.json("/environments/" + ENVIRONMENT)
    need(environment.get("name") == ENVIRONMENT and environment.get("can_admins_bypass") is False and
         environment.get("deployment_branch_policy") == {"protected_branches": False, "custom_branch_policies": True},
         "Sample publication environment protections differ")
    rules = environment.get("protection_rules", [])
    need(len(rules) == 2 and sorted(x.get("type", "") for x in rules) == ["branch_policy", "required_reviewers"],
         "Missing/unreviewed sample deployment protection rules")
    rule = next(x for x in rules if x["type"] == "required_reviewers")
    reviewers = rule.get("reviewers", [])
    need(rule.get("prevent_self_review") is False and len(reviewers) == 1 and reviewers[0].get("type") == "User" and
         is_owner(reviewers[0].get("reviewer")), "Require the owner as sole manual deployment reviewer")
    branches = api.pages("/environments/" + ENVIRONMENT + "/deployment-branch-policies", "branch_policies")
    need(len(branches) == 1 and branches[0].get("name") == "main" and branches[0].get("type") == "branch",
         "Only main may use the sample publication environment")
    return {"id": number(environment["id"]), "name": ENVIRONMENT, "reviewer": {"login": OWNER_LOGIN, "id": OWNER_ID},
            "preventSelfReview": False, "canAdminsBypass": False, "branch": "main"}


def publisher_run(api, context):
    run = api.json(f"/actions/runs/{context['run']}")
    workflow = api.json("/actions/workflows/sample-development-releases.yml")
    need(run.get("id") == context["run"] and run.get("run_attempt") == context["attempt"] and
         run.get("path") == workflow.get("path") == WORKFLOW and run.get("workflow_id") == workflow.get("id") and
         run.get("head_sha") == context["source"] and run.get("head_branch") == "main" and
         run.get("repository", {}).get("full_name") == REPO and run.get("head_repository", {}).get("full_name") == REPO and
         run.get("event") in ("workflow_run", "workflow_dispatch") and run.get("status") == "in_progress",
         "Review must bind the original running main publisher attempt")


def make_review_request(api, plan, context, manifest_hash):
    publisher_run(api, context)
    need(re.fullmatch(r"[0-9a-f]{64}", manifest_hash) is not None, "Missing inspected application manifest hash")
    return {"schema": 1, "scope": "P2PKIT_SAMPLE_POST_BUILD_OWNER_REVIEW", "publisher": context,
            "preparedAt": int(time.time()), "environment": publication_environment(api),
            "qualification": plan, "releaseManifestSha256": manifest_hash}


def approval_line(request):
    context = request["publisher"]
    return f"APPROVE_EVIDENCE {context['run']}/{context['attempt']} {hashlib.sha256(encoded(request)).hexdigest()}"


def load_review_request(api, descriptor, directory, context):
    need(type(descriptor) is tuple and len(descriptor) == 2 and type(descriptor[1]) is str and
         re.fullmatch(r"[0-9a-f]{64}", descriptor[1]), "Missing exact review artifact/request binding")
    item = api.json(f"/actions/artifacts/{number(descriptor[0])}")
    artifact = artifact_identity(item, context["run"], context["source"])
    need(artifact["name"] == f"sample-release-review-{context['run']}-{context['attempt']}" and
         artifact["size_in_bytes"] <= 4 * JSON_LIMIT, "Not this publisher attempt's bounded public review artifact")
    path = directory / "review-request.zip"
    api.download(artifact, path)
    try:
        need(PACK.file_hash(path, 4 * JSON_LIMIT) == {"bytes": artifact["size_in_bytes"],
             "sha256": artifact["digest"].removeprefix("sha256:")}, "Review artifact bytes differ")
        with PACK.zip_input(path) as archive:
            items = archive.infolist()
            need(len(items) == 4 and {x.filename for x in items} ==
                 {"review-request.json", "receipt.json", "sample-release.json", "SHA256SUMS"} and
                 all(not x.is_dir() and not x.flag_bits & 1 and stat.S_IFMT(x.external_attr >> 16) in (0, stat.S_IFREG) and
                     0 < x.file_size <= JSON_LIMIT for x in items), "Unapproved review artifact member")
            raw = archive.read("review-request.json")
            need(hashlib.sha256(raw).hexdigest() == descriptor[1], "Review request hash differs from preparation")
            request = parsed(raw)
            need(raw == encoded(request) and hashlib.sha256(archive.read("sample-release.json")).hexdigest() ==
                 request.get("releaseManifestSha256"), "Review manifest is not the inspected application manifest")
        (directory / "review-request.json").write_bytes(raw)
        return {"request": request, "artifact": artifact}
    finally:
        path.unlink()  # Only this exclusively created, public metadata download.


def require_publication_approval(api, plan, authorization, context):
    request, artifact = authorization["request"], authorization["artifact"]
    need(set(request) == {"schema", "scope", "publisher", "preparedAt", "environment", "qualification", "releaseManifestSha256"} and
         type(request["schema"]) is int and request["schema"] == 1 and
         request["scope"] == "P2PKIT_SAMPLE_POST_BUILD_OWNER_REVIEW" and request["publisher"] == context and
         request["qualification"] == plan and type(request["preparedAt"]) is int and 0 < request["preparedAt"] <= time.time(),
         "Approval request does not bind this exact publisher/source/evidence attempt")
    publisher_run(api, context)
    need(publication_environment(api) == request["environment"], "Deployment protection changed after preparation")
    need(artifact_identity(api.json(f"/actions/artifacts/{artifact['id']}"), context["run"], context["source"]) == artifact,
         "Public review artifact changed or expired")
    history = api.json(f"/actions/runs/{context['run']}/approvals")
    need(type(history) is list and len(history) <= 1000, "Unexpected deployment review history")
    # GitHub does not supply an attempt binding in these approval records. The
    # exact, owner-entered challenge supplies it; a reused environment approval
    # without the current challenge never authorizes a rerun.
    line = approval_line(request)
    matches = [x for x in history if type(x.get("comment")) is str and x["comment"].strip() == line]
    need(len(matches) == 1, "Missing/ambiguous fresh post-build owner evidence approval")
    approval = matches[0]
    environments = approval.get("environments", [])
    need(approval.get("state") == "approved" and is_owner(approval.get("user")) and len(environments) == 1 and
         environments[0].get("id") == request["environment"]["id"] and environments[0].get("name") == ENVIRONMENT,
         "Evidence approval is not the owner's approval of this protected environment")
    return {"schema": 1, "scope": "OWNER_EVIDENCE_REVIEW_ATTESTATION_NOT_AUTOMATED_DECRYPTION", "publisher": context,
            "owner": {"login": OWNER_LOGIN, "id": OWNER_ID}, "environment": request["environment"],
            "reviewArtifactId": artifact["id"], "reviewRequestSha256": hashlib.sha256(encoded(request)).hexdigest(),
            "comment": line, "state": "approved"}


def inspect_bundle(path, artifact, plan):
    """Read allowlisted metadata; no execution or general archive extraction."""
    need(PACK.file_hash(path, ARCHIVE_LIMIT) == {"bytes": artifact["size_in_bytes"],
         "sha256": artifact["digest"].removeprefix("sha256:")}, "Bundle bytes differ")
    platform, arch, sha = artifact["platform"], artifact["architecture"], plan["source"]["commit"]
    with PACK.zip_input(path) as archive:
        entries, total = {}, 0
        for item in archive.infolist():
            name = item.filename.rstrip("/")
            PACK.safe_name(name)
            need(name not in entries and not item.flag_bits & 1 and
                 stat.S_IFMT(item.external_attr >> 16) in (0, stat.S_IFREG, stat.S_IFDIR) and
                 item.file_size <= ARCHIVE_LIMIT, "Unsafe outer ZIP member")
            need(not item.is_dir() or name == "licenses", "Unexpected outer directory")
            entries[name] = item
            total += item.file_size
        need(total <= ARCHIVE_LIMIT and len(entries) <= 10, "Outer ZIP contents exceed bound")
        need("manifest.json" in entries and entries["manifest.json"].file_size <= JSON_LIMIT and
             "checksums.sha256" in entries and entries["checksums.sha256"].file_size <= 8192, "Missing bounded bundle metadata")
        manifest = parsed(archive.read("manifest.json"))
        context = manifest.get("sourceAndRun", {})
        expected = {"repository": REPO, "commit": sha, "tree": plan["source"]["tree"], "event_name": "push",
                    "ref": "refs/heads/main", "run_id": str(plan["producer"]["id"]),
                    "run_attempt": str(plan["producer"]["attempt"]), "job": "verify",
                    "workflow_ref": REPO + "/" + PRODUCER + "@refs/heads/main", "workflow_sha": sha,
                    "platform": "linux" if platform == "android" else platform,
                    "canonicalVersion": plan["versionBinding"]["canonicalVersion"]}
        if platform != "android":
            expected["architecture"] = arch
        need(all(context.get(k) == v for k, v in expected.items()) and context.get("architecture") in ("x64", "arm64") and
             manifest.get("schema") == 3 and manifest.get("scope") == PACK.SCOPE and
             manifest.get("versionBinding") == plan["versionBinding"], "Bundle manifest source/run/version/scope differs")
        version = plan["versionBinding"]
        embedded = VERSION.embedded_identity(version["canonicalVersion"], sha)
        if platform == "android":
            payload = [manifest["artifact"]]
            need(manifest.get("agpMetadata") == {"applicationId": "dev.p2pkit.sample.android", "variant": "debug",
                 "versionCode": version["androidVersionCode"], "versionName": version["canonicalVersion"]} and
                 payload[0]["file"].endswith(".apk"), "Not the source-version-bound development APK")
            need(manifest.get("apkInspection") == {"binaryManifest": {"applicationId": "dev.p2pkit.sample.android",
                 "versionCode": version["androidVersionCode"], "versionName": version["canonicalVersion"]},
                 "embeddedIdentity": embedded, "signerIdentity": "NOT_VERIFIED"}, "Missing actual APK identity readback")
        else:
            payload = manifest["artifacts"]
            suffix = ".zip" if platform == "windows" else ".tar.gz"
            need([x["file"] for x in payload] == [f"{kind}-{platform}-{arch}-{sha[:12]}{suffix}"
                 for kind in ("desktop-ui", "desktop-cli")] + [
                     f"desktop-installer-{platform}-{arch}-{sha[:12]}.{PACK.INSTALLER_FORMATS[platform]}"],
                 "Missing complete native UI/CLI archives or installer")
            native = payload[-1].get("nativeMetadata", {})
            need(native.get("embeddedIdentity") == embedded and
                 manifest.get("layoutInspection", {}).get("embeddedIdentity") == embedded,
                 "Installer/image embedded source identity differs")
            PACK.IDENTITY.native_fields(platform, native.get("fields", {}), version["canonicalVersion"])
        expected_files = {"manifest.json", "checksums.sha256", *("licenses/" + x for x in PACK.LICENSES),
                          *(x["file"] for x in payload)}
        need(set(entries) - {"licenses"} == expected_files, "Unapproved bundle file; no logs/private evidence allowed")
        sums = {}
        for line in archive.read("checksums.sha256").decode("ascii").splitlines():
            match = re.fullmatch(r"([0-9a-f]{64})  (.+)", line)
            need(match and match[2] not in sums, "Malformed/duplicate bundle checksum")
            sums[match[2]] = match[1]
        need(set(sums) == expected_files - {"checksums.sha256"}, "Incomplete bundle checksums")
        for name, digest in sums.items():
            with archive.open(entries[name]) as stream:
                need(PACK.hash_stream(stream, entries[name].file_size) == digest, "Bundle member checksum differs")
        need(all(x.get("bytes") == entries[x["file"]].file_size and x.get("sha256") == sums[x["file"]] for x in payload),
             "Payload manifest size/hash differs")
        if "frozenApplicationSet" in plan:
            records = [x for x in plan["frozenApplicationSet"]["packages"] if x["artifactId"] == artifact["id"]]
            need(len(records) == 1 and records[0]["artifactDigest"] == artifact["digest"] and
                 records[0]["manifestSha256"] == hashlib.sha256(archive.read("manifest.json")).hexdigest() and
                 records[0]["installable"] == payload[-1], "Application bytes/metadata differ from the pre-Maven frozen set")
        return payload[-1]


def read_notices(archive):
    """The same bounded public-notice reader is required before and after Maven."""
    notices = {}
    for name in PACK.LICENSES:
        member = archive.getinfo("licenses/" + name)
        need(member.file_size <= MIB, "Oversized public notice")
        notices[name] = archive.read(member)
    return notices


def copy_installable(bundle, artifact, plan, directory):
    selected = inspect_bundle(bundle, artifact, plan)
    platform, arch = artifact["platform"], artifact["architecture"]
    label = platform + ("-" + arch if platform != "android" else "")
    extension = "apk" if platform == "android" else PACK.INSTALLER_FORMATS[platform]
    path = directory / f"P2pKit-samples-{label}-{plan['source']['commit'][:12]}.{extension}"
    with PACK.zip_input(bundle) as archive:
        # Fixed destination, one validated member; never extractall or execute it.
        with archive.open(selected["file"]) as reader, path.open("xb") as writer:
            PACK.copy_stream(reader, writer, selected["bytes"])
        notices = read_notices(archive)
    need(PACK.file_hash(path) == {k: selected[k] for k in ("bytes", "sha256")}, "Promoted installer bytes differ")
    return {"file": path.name, "bytes": selected["bytes"], "sha256": selected["sha256"],
            "artifactId": artifact["id"], "member": selected["file"]}, notices


def release_body(plan, manifest_hash):
    publication = plan.get("mavenPublication")
    maven = (f"Built from the same source as Maven Central version `{publication['version']}`. "
             f"Verified Maven publisher: https://github.com/{REPO}/actions/runs/{publication['id']} "
             f"(attempt {publication['attempt']}, tag `{publication['tag']}`).\n\n") if publication else ""
    return ("Development sample apps — not a library or production release.\n\n" + maven +
            "Download the Android .apk, Windows .msi, macOS .dmg or Linux .deb for your platform. "
            "Verify SHA256SUMS before opening the package. License/notice material is in sample-notices.zip.\n\n"
            "These are development packages: no production signing/notarization, installation test, app-launch, "
            "LAN or physical-device qualification is claimed. Do not disable OS security controls. "
            "The Desktop UI includes its Java runtime; separate CLI archives remain in the producer's Actions artifacts. "
            "The ongoing audit is NOT_READY; advisory exceptions are not vulnerability fixes.\n\n"
            f"Source: `{plan['source']['commit']}` / tree `{plan['source']['tree']}`.\n"
            f"Producer: https://github.com/{REPO}/actions/runs/{plan['producer']['id']} "
            f"(attempt {plan['producer']['attempt']}).\n"
            f"Reviewed PR: https://github.com/{REPO}/pull/{plan['pullRequest']['number']}.\n"
            f"Manifest SHA-256: `{manifest_hash}`.\n")


def publish(api, plan, directory, mutate, review=None):
    need(directory.is_dir() and {p.name for p in directory.iterdir()} <= {".owner.json"},
         "Publisher workspace must be exclusively allocated and empty")
    authorization, approval, context = None, None, None
    need(plan.get("mavenPublication") is not None and plan.get("frozenApplicationSet") is not None,
         "Application delivery requires successful Maven and its exact frozen application set")
    if mutate:
        context = hosted_context(os.environ, "publish")
        authorization = load_review_request(api, review, directory, context)
        approval = require_publication_approval(api, plan, authorization, context)
        (directory / "approval-receipt.json").write_bytes(encoded(approval))
    assets, notices = [], None
    for artifact in plan["artifacts"]:
        label = artifact["platform"] + ("-" + artifact["architecture"] if artifact["platform"] != "android" else "")
        path = directory / f"P2pKit-samples-producer-{label}-{plan['source']['commit'][:12]}.zip"
        api.download(artifact, path)
        asset, current_notices = copy_installable(path, artifact, plan, directory)
        need(notices is None or notices == current_notices, "Producer notices differ across platform bundles")
        notices = current_notices
        assets.append(asset)
    notices_path = directory / "sample-notices.zip"
    with zipfile.ZipFile(notices_path, "x", compression=zipfile.ZIP_STORED) as archive:
        for name, raw in sorted(notices.items()):
            archive.writestr(zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0)), raw)
    assets.append({"file": notices_path.name, **PACK.file_hash(notices_path, JSON_LIMIT)})
    manifest = {**plan, "releaseAssets": assets}
    raw = encoded(manifest)
    (directory / "sample-release.json").write_bytes(raw)
    assets.append({"file": "sample-release.json", "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
    sums = "".join(x["sha256"] + "  " + x["file"] + "\n" for x in assets).encode()
    (directory / "SHA256SUMS").write_bytes(sums)
    assets.append({"file": "SHA256SUMS", "bytes": len(sums), "sha256": hashlib.sha256(sums).hexdigest()})
    # No mutation until *all* bytes are inspected and live gates still bind the
    # same candidate. No permission to rebuild when a producer has expired.
    revalidate_plan(api, plan)
    body = release_body(plan, assets[-2]["sha256"])
    if not mutate:
        return {"result": "VERIFIED_NOT_PUBLISHED", "source": plan["source"], "assets": assets}
    need(assets[-2]["sha256"] == authorization["request"]["releaseManifestSha256"],
         "Inspected application manifest differs from the owner's evidence review request")
    need(require_publication_approval(api, plan, authorization, context) == approval,
         "Owner evidence approval changed before Release mutation")
    tag = plan["tag"]
    publication = plan.get("mavenPublication")
    expected_tag = "samples-v" + plan["versionBinding"]["canonicalVersion"]
    need(tag == expected_tag and not tag.startswith("v"), "Unapproved release namespace")
    # The tag endpoint promises published releases, not draft visibility. Search
    # the authenticated, complete list so a retry cannot create a second draft.
    matches = [x for x in api.pages("/releases") if x.get("tag_name") == tag]
    need(len(matches) <= 1, "Ambiguous existing release/draft tag; never create another")
    release = matches[0] if matches else None
    ref = api.json("/git/ref/tags/" + tag, missing=True)
    if ref is not None:
        need(ref.get("object") == {"type": "commit", "sha": plan["source"]["commit"],
             "url": API + PREFIX + "/git/commits/" + plan["source"]["commit"]}, "Existing tag target/type differs")
        need(release is not None, "Existing orphan tag requires manual reconciliation")
    title = "Development samples — " + (publication["version"] if publication else plan["source"]["commit"][:12])
    if release is None:
        release = api.json("/releases", method="POST", value={"tag_name": tag,
                           "target_commitish": plan["source"]["commit"], "name": title, "body": body,
                           "draft": True, "prerelease": True, "make_latest": "false"})
    need(release.get("tag_name") == tag and release.get("name") == title and release.get("body") == body and
         release.get("prerelease") is True and release.get("target_commitish") == plan["source"]["commit"],
         "Existing release belongs to different frozen inputs; never replace it")
    expected = {x["file"]: x for x in assets}
    def roster():
        found = api.pages(f"/releases/{number(release['id'])}/assets")
        need(len({x["name"] for x in found}) == len(found), "Duplicate remote asset name")
        for item in found:
            need(item["name"] in expected, "Unapproved existing release asset")
            value = expected[item["name"]]
            need(item.get("state") == "uploaded" and item.get("size") == value["bytes"] and
                 item.get("digest") == "sha256:" + value["sha256"], "Remote asset is incomplete/different; no clobber")
        return {x["name"] for x in found}
    found = roster()
    need(release.get("draft") is True or found == set(expected), "Published release is incomplete; do not modify it")
    for name in sorted(set(expected) - found):
        need(require_publication_approval(api, plan, authorization, context) == approval,
             "Owner evidence approval changed before asset upload")
        api.json(f"/releases/{release['id']}/assets?name=" + urllib.parse.quote(name, safe=""), upload=directory / name)
    need(roster() == set(expected), "Remote asset roster/digests incomplete")
    if release.get("draft") is True:
        revalidate_plan(api, plan)
        need(require_publication_approval(api, plan, authorization, context) == approval,
             "Owner evidence approval changed before draft publication")
        current_tag = api.json("/git/ref/tags/" + tag, missing=True)
        need(current_tag is None or (current_tag.get("object", {}).get("type") == "commit" and
             current_tag["object"].get("sha") == plan["source"]["commit"]), "Tag changed before publication")
        api.json(f"/releases/{release['id']}", method="PATCH",
                 value={"draft": False, "prerelease": True, "make_latest": "false"})
    final = api.json(f"/releases/{release['id']}")
    ref = api.json("/git/ref/tags/" + tag)
    need(final.get("draft") is False and final.get("prerelease") is True and final.get("body") == body and
         final.get("tag_name") == tag and ref.get("object", {}).get("type") == "commit" and
         ref["object"].get("sha") == plan["source"]["commit"] and roster() == set(expected), "Publication read-back differs")
    for asset in assets:
        api.public_probe(tag, asset)
    return {"result": "PUBLISHED_DEVELOPMENT_PRERELEASE", "source": plan["source"], "releaseId": release["id"],
            "url": final["html_url"], "assets": assets, "publicFullDownloadHashesVerified": True, "ownerEvidenceApproval": approval}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("admit", "verify", "prepare-review", "publish", "cleanup"))
    parser.add_argument("--source", default="")
    parser.add_argument("--maven-run", default="")
    parser.add_argument("--maven-attempt", default="")
    parser.add_argument("--frozen-artifact", default="")
    parser.add_argument("--frozen-sha256", default="")
    parser.add_argument("--review-artifact", default="")
    parser.add_argument("--review-request", default="")
    args = parser.parse_args()
    directory, result, code = None, {"result": "HOLD"}, 1
    try:
        context = hosted_context(os.environ, args.operation)
        need(args.operation == "publish" or not args.review_artifact and not args.review_request,
             "Review authorization arguments are publication-only")
        parent = Path(os.environ["RUNNER_TEMP"])
        PACK.physical_directory(parent)
        candidate = parent / "p2pkit-sample-release"
        if args.operation == "cleanup":
            if not candidate.exists():
                result = {"result": "NO_OWNED_METADATA"}
                return 0
            PACK.physical_directory(candidate)
            info = candidate.stat()
            need(parsed((candidate / ".owner.json").read_bytes()) ==
                 {"context": context, "device": info.st_dev, "inode": info.st_ino}, "Cleanup ownership differs")
            allowed = {".owner.json", "receipt.json", "sample-release.json", "SHA256SUMS", "review-request.json", "approval-receipt.json"}
            paths = list(candidate.iterdir())
            need({p.name for p in paths} <= allowed and all(p.is_file() and not p.is_symlink() and
                 p.stat().st_nlink == 1 for p in paths), "Unknown publisher cleanup content")
            for path in paths:
                path.unlink()
            candidate.rmdir()
            result = {"result": "OWNED_METADATA_REMOVED"}
            return 0
        actual = subprocess.run(["git", "--no-replace-objects", "rev-parse", "HEAD"], cwd=ROOT,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15, check=True)
        need(actual.stdout.decode().strip() == context["source"], "Checkout is not the trusted publisher source")
        api = Api(os.environ.get("GH_TOKEN", ""))
        sha, publication = args.source, None
        if os.environ["GITHUB_EVENT_NAME"] == "workflow_run":
            event = parsed(Path(os.environ["GITHUB_EVENT_PATH"]).read_bytes())["workflow_run"]
            triggered_sha = trigger_source(api, event)
            need(not sha or sha == triggered_sha, "Requested source differs from the completed workflow")
            sha = triggered_sha
            need((not args.maven_run or number(args.maven_run) == event["id"]) and
                 (not args.maven_attempt or number(args.maven_attempt) == event["run_attempt"]),
                 "Requested Maven attempt differs from the triggering completion")
            publication = maven_publication(api, sha, event["id"], event["run_attempt"])
        need(sha, "Exact candidate source required")
        if publication is None:
            need(args.maven_run and args.maven_attempt and args.frozen_artifact and args.frozen_sha256,
                 "Manual delivery needs exact original Maven run/attempt and frozen artifact/hash")
            publication = maven_publication(api, sha, args.maven_run, args.maven_attempt)
        need(bool(args.frozen_artifact) == bool(args.frozen_sha256), "Incomplete frozen artifact/hash binding")
        binding = {"artifact": {"id": args.frozen_artifact}, "sha256": args.frozen_sha256} if args.frozen_artifact else None
        plan = frozen_publication_plan(api, publication, binding)
        if args.operation == "admit":
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
                frozen = plan["frozenApplicationSet"]
                output.write(f"ready=true\nsource={sha}\nmaven_run={publication['id']}\nmaven_attempt={publication['attempt']}\n"
                             f"frozen_artifact={frozen['artifact']['id']}\nfrozen_sha256={frozen['sha256']}\n")
            result, code = {"result": "ADMITTED_METADATA_ONLY", "plan": plan}, 0
        else:
            candidate.mkdir(mode=0o700)
            directory = candidate  # Set only after this invocation's exclusive creation.
            info = directory.stat()
            (directory / ".owner.json").write_bytes(encoded({"context": context, "device": info.st_dev, "inode": info.st_ino}))
            result = publish(api, plan, directory, args.operation == "publish",
                             (args.review_artifact, args.review_request) if args.operation == "publish" else None)
            if args.operation == "prepare-review":
                request = make_review_request(api, plan, context, hashlib.sha256((directory / "sample-release.json").read_bytes()).hexdigest())
                raw = encoded(request)
                (directory / "review-request.json").write_bytes(raw)
                request_hash = hashlib.sha256(raw).hexdigest()
                with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
                    output.write("request_sha256=" + request_hash + "\n")
                result = {"result": "READY_FOR_OWNER_EVIDENCE_REVIEW_NOT_PUBLICATION", "request": request,
                          "requestSha256": request_hash, "ownerApprovalComment": approval_line(request)}
            code = 0
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        # Exception details can contain private signed URLs; print only safe type.
        result = {"result": "HOLD", "reason": str(error) if isinstance(error, Hold) else type(error).__name__}
    finally:
        print(result["result"] + (": " + result["reason"] if "reason" in result else ""))
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as output:
                output.write("### Development samples\n\n```json\n" + encoded(result).decode() + "```\n")
        if directory is not None and directory.is_dir():
            # Keep small public provenance/receipt for the always-run uploader;
            # producer ZIP originals remain under their recorded Actions IDs.
            (directory / "receipt.json").write_bytes(encoded(result))
            for path in [*directory.glob("P2pKit-samples-*"), directory / "sample-notices.zip"]:
                if path.is_file() and not path.is_symlink():
                    path.unlink()
    return code


if __name__ == "__main__":
    sys.exit(main())
