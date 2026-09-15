#!/usr/bin/env python3
"""Promote existing, reviewed main sample artifacts to a development prerelease.

No compiler, Gradle, signing, cache, app execution or library publication here.
admit is read-only. publish repeats admission before any mutation, downloads
only four named producer ZIPs, and never replaces tags/releases/assets.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
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
                   "Accept": "application/octet-stream" if binary else "application/vnd.github+json"}
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


def hosted_context(env):
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
    need(event.get("name") in TRIGGERS, "Unexpected triggering workflow")
    path = TRIGGERS[event["name"]]
    trigger = api.json("/actions/runs/" + str(number(event["id"])))
    trusted_run(trigger, path, event["head_sha"], MAIN_EVENTS[path])
    return event["head_sha"]


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
    reviews = api.pages(f"/pulls/{pull['number']}/reviews")
    decisive = {}
    for review in sorted(reviews, key=lambda x: number(x["id"])):
        if review.get("state") in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED"):
            decisive[review["user"]["login"]] = review
    need(not any(x["state"] == "CHANGES_REQUESTED" for x in decisive.values()), "Unresolved formal change request")
    approved = [x for user, x in decisive.items() if user != pull["user"]["login"] and
                x["user"].get("type") == "User" and x.get("author_association") in ("OWNER", "MEMBER", "COLLABORATOR") and
                x["state"] == "APPROVED" and x.get("commit_id") == head and
                x.get("submitted_at", "~") <= pull["merged_at"]]
    need(approved, "Missing independent formal approval of the final head before merge")
    required = checks(api, head, REQUIRED, "pull_request", pull["number"])
    need(all(x["completedAt"] and x["completedAt"] <= pull["merged_at"] for x in required),
         "PR check evidence is not pre-merge")
    return {"number": pull["number"], "head": head, "merge": sha, "mergedAt": pull["merged_at"],
            "reviews": [{"id": x["id"], "reviewer": x["user"]["login"], "commit": head} for x in approved],
            "checks": required}


def admit(api, sha, producer_id=None, attempt=None):
    need(isinstance(sha, str) and SHA.fullmatch(sha), "Expected a full source SHA")
    rules = api.json("/rules/branches/main")
    names = {check["context"] for rule in rules if rule.get("type") == "required_status_checks"
             for check in rule.get("parameters", {}).get("required_status_checks", [])}
    need(names == REQUIRED and any(x.get("type") == "pull_request" for x in rules),
         "Required-check/protected-PR policy changed; review it, do not bypass it")
    commit = api.json("/commits/" + sha)
    need(commit.get("sha") == sha, "Commit lookup mismatch")
    tree = commit.get("commit", {}).get("tree", {}).get("sha", "")
    need(SHA.fullmatch(tree), "Missing exact source tree")
    main = api.json("/git/ref/heads/main")["object"]["sha"]
    comparison = api.json(f"/compare/{sha}...{main}")
    need(comparison.get("status") in ("identical", "ahead") and
         comparison.get("merge_base_commit", {}).get("sha") == sha, "Candidate is not preserved in main")
    pull = approved_pull(api, sha, commit)
    main_checks = checks(api, sha, MAIN_REQUIRED, "main")
    if producer_id is None:
        run = latest(api.pages("/actions/workflows/desktop-cross-host.yml/runs?event=push&branch=main&head_sha=" + sha,
                               "workflow_runs"), "No main sample producer")
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
        need(item.get("expired") is False and DIGEST.fullmatch(item.get("digest", "")) and
             type(item.get("size_in_bytes")) is int and 0 < item["size_in_bytes"] <= ARCHIVE_LIMIT and
             item.get("workflow_run", {}).get("id") == producer_id and
             item["workflow_run"].get("head_sha") == sha and item["workflow_run"].get("head_branch") == "main",
             "Expired/unbound artifact or unavailable digest")
        arch = "apk-abis-not-inspected" if platform == "android" else (
            "arm64" if item["name"].startswith(prefix + "ARM64-") else "x64")
        selected.append({key: item[key] for key in ("id", "name", "size_in_bytes", "digest")} |
                        {"platform": platform, "architecture": arch})
    need(len({x["id"] for x in selected}) == 4 and sum(x["size_in_bytes"] for x in selected) <= TRANSFER_LIMIT,
         "Artifact set duplicates/exceeds transfer budget")
    return {"schema": 1, "source": {"commit": sha, "tree": tree}, "tag": "samples-" + sha,
            "producer": {"id": producer_id, "attempt": selected_attempt, "workflowId": run["workflow_id"],
                         "workflowPath": PRODUCER, "jobs": [{"id": x["id"], "name": x["name"]} for x in jobs if x["name"] in hosts]},
            "pullRequest": pull, "mainChecks": main_checks, "artifacts": selected, "scope": PACK.SCOPE}


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
                    "platform": "linux" if platform == "android" else platform}
        if platform != "android":
            expected["architecture"] = arch
        need(all(context.get(k) == v for k, v in expected.items()) and context.get("architecture") in ("x64", "arm64") and
             manifest.get("schema") == 2 and manifest.get("scope") == PACK.SCOPE, "Bundle manifest source/run/scope differs")
        if platform == "android":
            payload = [manifest["artifact"]]
            need(manifest.get("agpMetadata") == {"applicationId": "dev.p2pkit.sample.android", "variant": "debug",
                 "versionCode": 1, "versionName": "0.1.0"} and payload[0]["file"].endswith(".apk"), "Not the development APK")
        else:
            payload = manifest["artifacts"]
            suffix = ".zip" if platform == "windows" else ".tar.gz"
            need([x["file"] for x in payload] == [f"{kind}-{platform}-{arch}-{sha[:12]}{suffix}"
                 for kind in ("desktop-ui", "desktop-cli")] + [
                     f"desktop-installer-{platform}-{arch}-{sha[:12]}.{PACK.INSTALLER_FORMATS[platform]}"],
                 "Missing complete native UI/CLI archives or installer")
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
        return payload[-1]


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
        notices = {}
        for name in PACK.LICENSES:
            member = archive.getinfo("licenses/" + name)
            need(member.file_size <= MIB, "Oversized public notice")
            notices[name] = archive.read(member)
    need(PACK.file_hash(path) == {k: selected[k] for k in ("bytes", "sha256")}, "Promoted installer bytes differ")
    return {"file": path.name, "bytes": selected["bytes"], "sha256": selected["sha256"],
            "artifactId": artifact["id"], "member": selected["file"]}, notices


def release_body(plan, manifest_hash):
    return ("Development sample apps — not a library or production release.\n\n"
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


def publish(api, plan, directory, mutate):
    need(directory.is_dir() and {p.name for p in directory.iterdir()} <= {".owner.json"},
         "Publisher workspace must be exclusively allocated and empty")
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
    need(admit(api, plan["source"]["commit"], plan["producer"]["id"], plan["producer"]["attempt"]) == plan,
         "Admission changed while downloading; retain a HOLD")
    body = release_body(plan, assets[-2]["sha256"])
    if not mutate:
        return {"result": "VERIFIED_NOT_PUBLISHED", "source": plan["source"], "assets": assets}
    tag = plan["tag"]
    need(tag == "samples-" + plan["source"]["commit"] and not tag.startswith("v"), "Unapproved release namespace")
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
    title = "Development samples — " + plan["source"]["commit"][:12]
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
        api.json(f"/releases/{release['id']}/assets?name=" + urllib.parse.quote(name, safe=""), upload=directory / name)
    need(roster() == set(expected), "Remote asset roster/digests incomplete")
    if release.get("draft") is True:
        need(admit(api, plan["source"]["commit"], plan["producer"]["id"], plan["producer"]["attempt"]) == plan,
             "Admission changed before draft publication")
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
    return {"result": "PUBLISHED_DEVELOPMENT_PRERELEASE", "source": plan["source"], "releaseId": release["id"],
            "url": final["html_url"], "assets": assets}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("admit", "verify", "publish", "cleanup"))
    parser.add_argument("--source", default="")
    parser.add_argument("--producer", default="")
    parser.add_argument("--attempt", default="")
    args = parser.parse_args()
    directory, result, code = None, {"result": "HOLD"}, 1
    try:
        context = hosted_context(os.environ)
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
            allowed = {".owner.json", "receipt.json", "sample-release.json", "SHA256SUMS"}
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
        sha, producer, attempt = args.source, args.producer or None, args.attempt or None
        if os.environ["GITHUB_EVENT_NAME"] == "workflow_run" and args.operation == "admit":
            event = parsed(Path(os.environ["GITHUB_EVENT_PATH"]).read_bytes())["workflow_run"]
            sha = trigger_source(api, event)
        need(sha, "Exact candidate source required")
        plan = admit(api, sha, producer, attempt)
        if args.operation == "admit":
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
                output.write(f"ready=true\nsource={sha}\nproducer={plan['producer']['id']}\nattempt={plan['producer']['attempt']}\n")
            result, code = {"result": "ADMITTED_METADATA_ONLY", "plan": plan}, 0
        else:
            candidate.mkdir(mode=0o700)
            directory = candidate  # Set only after this invocation's exclusive creation.
            info = directory.stat()
            (directory / ".owner.json").write_bytes(encoded({"context": context, "device": info.st_dev, "inode": info.st_ino}))
            result = publish(api, plan, directory, args.operation == "publish")
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
