#!/usr/bin/env python3
"""Admit explicitly selected immutable component results, not bootstrap proofs.

No execution, decryption, signing or publication. A failed enclosing matrix run
does not invalidate a successful selected job; its original attempt, artifact,
host and complete evidence are still mandatory. Freeze never reselects results.
"""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import time
import zipfile

REPOSITORY = "p2pKit/P2pKit"
WORKFLOW = ".github/workflows/ci.yml"
QUALIFY_JOB = "Qualify release components"
COMPONENTS = {
    "source": ("Linux", "x86_64"), "dependencies": ("Linux", "x86_64"),
    "jvm-linux": ("Linux", "x86_64"), "jvm-windows": ("Windows", "AMD64"),
    "android": ("Linux", "x86_64"), "apple-arm64": ("Darwin", "arm64"),
    "apple-x64": ("Darwin", "x86_64"), "desktop-linux": ("Linux", "x86_64"),
    "desktop-windows": ("Windows", "AMD64"), "desktop-macos": ("Darwin", "arm64"),
    "security": ("Linux", "x86_64"), "compatibility": ("Darwin", "arm64"),
    "consumers": ("Darwin", "arm64"),
}
RUNNERS = {component: ("windows-2025" if host[0] == "Windows" else
                      "macos-15-intel" if host == ("Darwin", "x86_64") else
                      "macos-26" if host[0] == "Darwin" else "ubuntu-24.04")
           for component, host in COMPONENTS.items()}
RUNNERS["consumers"] = "macos-14"
APPLICATIONS = {
    "android": ("android", "apk-abis-not-inspected", "sample-app-android"),
    "linux": ("desktop-linux", "x64", "sample-app-desktop-linux"),
    "windows": ("desktop-windows", "x64", "sample-app-desktop-windows"),
    "macos": ("desktop-macos", "arm64", "sample-app-desktop-macos"),
}
SHA = re.compile(r"[0-9a-f]{40}")
HASH = re.compile(r"[0-9a-f]{64}")
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
JSON_LIMIT = 4 * 1024**2
ARTIFACT_LIMIT = 1024**3
RETENTION = 14 * 86400


class AdmissionError(ValueError):
    pass


class MetadataSnapshot:
    """Read shared run/job originals once per admission, never across revalidation."""
    def __init__(self, api):
        self.api, self.records = api, {}
    def json(self, path):
        key = ("json", path)
        if key not in self.records:
            self.records[key] = self.api.json(path)
        return self.records[key]
    def pages(self, path, key=None):
        identity = ("pages", path, key)
        if identity not in self.records:
            self.records[identity] = self.api.pages(path, key)
        return self.records[identity]
    def download(self, artifact, destination):
        return self.api.download(artifact, destination)


def need(value, reason):
    if not value:
        raise AdmissionError(reason)


def integer(value):
    need(type(value) is int and value > 0, "Invalid positive identity")
    return value


def timestamp(value):
    need(type(value) is str and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value), "Invalid UTC timestamp")
    try:
        return int(datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc).timestamp())
    except ValueError:
        raise AdmissionError("Invalid UTC calendar timestamp") from None


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False) + "\n").encode()


def parsed(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, "Duplicate JSON field")
            result[key] = value
        return result
    need(0 < len(raw) <= JSON_LIMIT, "Public record size limit")
    return json.loads(raw, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, "Nonfinite JSON"))


def artifact_identity(item, run_id, source, branch, now=None):
    now = time.time() if now is None else now
    need(type(item) is dict and item.get("expired") is False and
         DIGEST.fullmatch(item.get("digest", "")) and type(item.get("size_in_bytes")) is int and
         0 < item["size_in_bytes"] <= ARTIFACT_LIMIT, "Expired/undigested/oversize artifact")
    run = item.get("workflow_run", {})
    need(run.get("id") == run_id and run.get("head_sha") == source and run.get("head_branch") == branch,
         "Artifact source/run/branch differs")
    created, expires = timestamp(item.get("created_at")), timestamp(item.get("expires_at"))
    need(created <= now < expires <= created + RETENTION, "Original artifact retention expired/changed")
    integer(item.get("id"))
    return {key: item[key] for key in ("id", "name", "size_in_bytes", "digest", "created_at", "expires_at")}


def selected_job(api, source, run_id, attempt, name, *, require_main=False):
    integer(run_id); integer(attempt)
    current = api.json(f"/actions/runs/{run_id}")
    run = api.json(f"/actions/runs/{run_id}/attempts/{attempt}")
    workflow = api.json("/actions/workflows/ci.yml")
    for original in (current, run):
        need(original.get("id") == run_id and
             original.get("path") == WORKFLOW and original.get("workflow_id") == workflow.get("id") and
             original.get("repository", {}).get("full_name") == REPOSITORY and
             original.get("head_repository", {}).get("full_name") == REPOSITORY and
             original.get("event") in ("push", "workflow_dispatch", "pull_request", "schedule") and
             (not require_main or original.get("head_branch") == "main" and original.get("event") != "pull_request"),
             "Untrusted component source/workflow/environment")
    need(workflow.get("path") == WORKFLOW and run.get("run_attempt") == attempt and
         type(current.get("run_attempt")) is int and current["run_attempt"] >= attempt and
         run.get("head_branch") == current.get("head_branch") and run.get("head_sha") == current.get("head_sha") and
         run.get("event") == current.get("event"), "Attempt identity differs")
    if run["event"] == "pull_request":
        # GitHub's service records bind the PR head, while the actual checkout
        # and public evidence bind its synthetic merge. Do not conflate them.
        pulls = run.get("pull_requests")
        need(type(pulls) is list and len(pulls) == 1, "PR run lacks one original pull identity")
        pull = pulls[0]
        head, base = pull.get("head", {}), pull.get("base", {})
        need(head.get("sha") == run["head_sha"] and base.get("ref") == "main" and
             SHA.fullmatch(base.get("sha", "")) and
             integer(head.get("repo", {}).get("id")) == integer(run["head_repository"].get("id")) and
             integer(base.get("repo", {}).get("id")) == integer(run["repository"].get("id")),
             "PR original head/base/repository differs")
        merge = api.json("/git/commits/" + source)
        need(merge.get("sha") == source and [row.get("sha") for row in merge.get("parents", [])] ==
             [base["sha"], head["sha"]], "Selected source is not the original PR synthetic merge")
    else:
        need(run.get("head_sha") == source, "Component source SHA differs")
    jobs = api.pages(f"/actions/runs/{run_id}/attempts/{attempt}/jobs", "jobs")
    found = [job for job in jobs if job.get("name") == name]
    need(len(found) == 1, "Missing/ambiguous selected component job")
    job = found[0]
    need(job.get("run_id") == run_id and job.get("run_attempt") == attempt and
         job.get("head_sha") == run["head_sha"] and job.get("status") == "completed" and
         job.get("conclusion") == "success" and integer(job.get("runner_id")) and
         timestamp(job.get("started_at")) <= timestamp(job.get("completed_at")) <= time.time(),
         "Selected job is not genuinely successful/assigned/completed")
    component = name.removesuffix(" / Execute component")
    if component in COMPONENTS:
        need(type(job.get("labels")) is list and RUNNERS[component] in job["labels"] and
             "self-hosted" not in job["labels"], "Unexpected component runner labels")
    return run, {key: job[key] for key in ("id", "name", "started_at", "completed_at")}


def selected_artifact(api, selection, source, run, job, expected_name):
    integer(selection.get("artifactId"))
    need(DIGEST.fullmatch(selection.get("digest", "")), "Missing selected artifact digest")
    item = api.json(f"/actions/artifacts/{selection['artifactId']}")
    artifact = artifact_identity(item, run["id"], run.get("head_sha", source), run["head_branch"])
    need(artifact["digest"] == selection["digest"] and artifact["name"] == expected_name and
         timestamp(job["started_at"]) <= timestamp(artifact["created_at"]) <= timestamp(job["completed_at"]),
         "Artifact name/digest/original attempt job interval differs")
    return artifact


def manifest_identity(manifest, source, component, run, job, artifact):
    need(type(manifest) is dict and type(manifest.get("schema")) is int and manifest["schema"] == 1 and
         manifest.get("component") == component, "Evidence schema/component differs")
    origin, github, host, outcome = (manifest.get(key, {}) for key in ("source", "github", "host", "outcome"))
    need(origin.get("commit") == source and SHA.fullmatch(origin.get("tree", "")) and
         type(origin.get("version")) is str and origin["version"], "Evidence source/version missing")
    need(type(github.get("runId")) is str and type(github.get("runAttempt")) is str and
         github == {"repository": REPOSITORY, "runId": str(run["id"]), "runAttempt": str(run["run_attempt"]),
                    "workflowPath": WORKFLOW, "workflowSha": source, "jobId": "run"},
         "Evidence run/attempt/workflow differs")
    need(host == {"platform": COMPONENTS[component][0], "arch": COMPONENTS[component][1],
                  "runnerEnvironment": "github-hosted"}, "Evidence host/environment differs")
    need(type(outcome.get("exitCode")) is int and outcome["exitCode"] == 0 and
         outcome.get("timedOut") is False and outcome.get("cleanupKnown") is True and
         outcome.get("code") == "PASS", "Failed/incomplete component evidence")
    if host["platform"] == "Darwin":
        need(outcome.get("ownershipBoundary") == "GITHUB_HOSTED_DARWIN_MARKER_DOMAIN_V1" and
             type(outcome.get("outsideDomainObservations")) is int and
             0 <= outcome["outsideDomainObservations"] <= 1_000_000,
             "Missing or different routine hosted Darwin ownership boundary")
    timing = manifest.get("timing", {})
    need(timestamp(job["started_at"]) <= timestamp(timing.get("startedAt")) <=
         timestamp(timing.get("completedAt")) <= timestamp(artifact["created_at"]), "Evidence timing differs")
    need(type(manifest.get("tools")) is dict and manifest["tools"] and
         HASH.fullmatch(manifest.get("command", {}).get("sha256", "")), "Missing actual tools/command identity")
    if component == "consumers":
        xcode = manifest["tools"].get("xcode")
        need(type(xcode) is dict and xcode.get("version") == "16.2" and
             type(xcode.get("executableSha256")) is str and HASH.fullmatch(xcode["executableSha256"]),
             "Consumer baseline requires recorded Xcode 16.2 identity")
    for key in ("privateArchive", "ciphertext"):
        row = manifest.get(key, {})
        need(HASH.fullmatch(row.get("sha256", "")) and type(row.get("bytes")) is int and
             0 < row["bytes"] <= ARTIFACT_LIMIT, "Missing archive/ciphertext digest")
    need(re.fullmatch(r"[0-9A-F]{40,64}", manifest["ciphertext"].get("recipientFingerprint", "")),
         "Missing approved recipient fingerprint")
    return manifest


def read_archive(api, artifact, *, evidence=False):
    """Read public metadata and hash ciphertext; never decrypt/extract private data."""
    with tempfile.TemporaryDirectory(prefix="p2pkit-qualification-") as temporary:
        path = Path(temporary) / "original.zip"
        api.download(artifact, path)
        digest, count = hashlib.sha256(), 0
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024**2), b""):
                digest.update(block); count += len(block)
        need(count == artifact["size_in_bytes"] and "sha256:" + digest.hexdigest() == artifact["digest"],
             "Original downloaded ZIP digest differs")
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            names = {"manifest.json", "evidence.tar.gz.gpg"} if evidence else {"qualification.json"}
            need(len(members) == len(names) and {item.filename for item in members} == names and
                 all(not item.is_dir() and not item.flag_bits & 1 and
                     stat.S_IFMT(item.external_attr >> 16) in (0, stat.S_IFREG) and
                     0 < item.file_size <= ARTIFACT_LIMIT for item in members), "Unexpected record ZIP members")
            name = "manifest.json" if evidence else "qualification.json"
            need(archive.getinfo(name).file_size <= JSON_LIMIT, "Oversize public manifest")
            raw = archive.read(name)
            document = parsed(raw)
            if evidence:
                cipher = document.get("ciphertext", {})
                info = archive.getinfo("evidence.tar.gz.gpg")
                need(info.file_size == cipher.get("bytes"), "Ciphertext size differs")
                digest = hashlib.sha256()
                with archive.open(info) as stream:
                    for block in iter(lambda: stream.read(1024**2), b""):
                        digest.update(block)
                need(digest.hexdigest() == cipher.get("sha256"), "Ciphertext digest differs")
            else:
                need(raw == encoded(document), "Qualification record is not canonical")
            return document


def aggregate(api, selection, *, manifests=None, require_main=False):
    """A supplied manifest cache is only for revalidating a trusted frozen record."""
    api = MetadataSnapshot(api)
    need(type(selection) is dict and set(selection) == {"schema", "source", "components", "applications"} and
         type(selection["schema"]) is int and selection["schema"] == 1 and
         SHA.fullmatch(selection["source"]), "Selection schema/source differs")
    source = selection["source"]
    rows = selection["components"]
    need(type(rows) is list and len(rows) == len(COMPONENTS) and
         {row.get("component") for row in rows} == set(COMPONENTS), "Missing/duplicate required components")
    admitted, origins = [], []
    for component in COMPONENTS:
        row = next(row for row in rows if row["component"] == component)
        need(set(row) == {"component", "runId", "runAttempt", "artifactId", "digest"}, "Component selector fields differ")
        run, job = selected_job(api, source, row["runId"], row["runAttempt"], component + " / Execute component",
                                require_main=require_main)
        artifact = selected_artifact(api, row, source, run, job,
                                     f"ci-evidence-{component}-{row['runId']}-{row['runAttempt']}")
        manifest = read_archive(api, artifact, evidence=True) if manifests is None else manifests[component]
        manifest_identity(manifest, source, component, run, job, artifact)
        admitted.append({"component": component, "run": {"id": row["runId"], "attempt": row["runAttempt"],
                         "workflowPath": WORKFLOW, "event": run["event"], "branch": run["head_branch"],
                         "serviceHead": run["head_sha"]},
                         "job": job, "artifact": artifact, "manifest": manifest})
        origins.append(manifest["source"])
    need(all(origin == origins[0] for origin in origins), "Components disagree on source tree/version")
    commit = api.json("/git/commits/" + source)
    need(commit.get("sha") == source and commit.get("tree", {}).get("sha") == origins[0]["tree"],
         "Evidence tree is not the original Git commit tree")
    apps = selection["applications"]
    need(type(apps) is list and len(apps) == 4 and {app.get("platform") for app in apps} == set(APPLICATIONS),
         "Missing/duplicate four-application selection")
    applications = []
    for platform, (component, arch, prefix) in APPLICATIONS.items():
        row = next(row for row in apps if row["platform"] == platform)
        need(set(row) == {"platform", "runId", "runAttempt", "artifactId", "digest"}, "Application selector fields differ")
        owner = next(item for item in admitted if item["component"] == component)
        need((row["runId"], row["runAttempt"]) == (owner["run"]["id"], owner["run"]["attempt"]),
             "Application is not from its selected qualified component attempt")
        run = {"id": row["runId"], "head_branch": owner["run"]["branch"], "head_sha": owner["run"]["serviceHead"]}
        artifact = selected_artifact(api, row, source, run, owner["job"],
                                     f"{prefix}-{row['runId']}-{row['runAttempt']}")
        applications.append({**artifact, "platform": platform, "architecture": arch, "component": component,
                             "producer": owner["run"]})
    identifiers = [row["artifact"]["id"] for row in admitted] + [row["id"] for row in applications]
    need(len(set(identifiers)) == len(identifiers), "Artifact identities overlap")
    return {"schema": 1, "scope": "P2PKIT_MODULAR_QUALIFICATION", "source": origins[0],
            "selection": selection, "components": admitted, "applications": applications}


def load_qualification(api, source, binding=None):
    """Discover once, then freeze the exact selection. Never choose 'latest'."""
    if binding is None and os.environ.get("RELEASE_QUALIFICATION_BINDING"):
        binding = parsed(os.environ["RELEASE_QUALIFICATION_BINDING"].encode())
    if binding is None:
        runs = api.pages("/actions/workflows/ci.yml/runs?branch=main&head_sha=" + source, "workflow_runs")
        candidates = []
        for run in runs:
            if run.get("head_sha") != source or run.get("event") not in ("push", "workflow_dispatch", "schedule"):
                continue
            for item in api.pages(f"/actions/runs/{integer(run['id'])}/artifacts", "artifacts"):
                match = re.fullmatch(r"ci-qualification-" + source + r"-([1-9][0-9]*)-([1-9][0-9]*)", item.get("name", ""))
                if match and int(match[1]) == run["id"] and item.get("expired") is False:
                    candidates.append({"runId": run["id"], "runAttempt": int(match[2]),
                                       "artifactId": item["id"], "digest": item.get("digest")})
        need(len(candidates) == 1, "Missing/ambiguous exact-source qualification; provide an explicit selection")
        binding = candidates[0]
    need(set(binding) == {"runId", "runAttempt", "artifactId", "digest"}, "Qualification binding differs")
    run, job = selected_job(api, source, binding["runId"], binding["runAttempt"], QUALIFY_JOB, require_main=True)
    artifact = selected_artifact(api, binding, source, run, job,
                                 f"ci-qualification-{source}-{binding['runId']}-{binding['runAttempt']}")
    document = read_archive(api, artifact)
    need(document.get("source", {}).get("commit") == source, "Qualification source differs")
    manifests = {item["component"]: item["manifest"] for item in document.get("components", [])}
    verified = aggregate(api, document["selection"], manifests=manifests, require_main=True)
    need(verified == document, "Qualification component/original metadata changed")
    return document, binding


def collect(api, source, run_id, attempt):
    """Collect only this explicit attempt's artifact names; aggregate validates it."""
    integer(run_id); integer(attempt)
    need(SHA.fullmatch(source), "Invalid selection source")
    artifacts = api.pages(f"/actions/runs/{run_id}/artifacts", "artifacts")
    def item(name):
        found = [row for row in artifacts if row.get("name") == name]
        need(len(found) == 1, "Missing/ambiguous exact-attempt artifact")
        return {"runId": run_id, "runAttempt": attempt, "artifactId": integer(found[0].get("id")),
                "digest": found[0].get("digest")}
    return {"schema": 1, "source": source,
            "components": [{"component": component, **item(f"ci-evidence-{component}-{run_id}-{attempt}")}
                           for component in COMPONENTS],
            "applications": [{"platform": platform, **item(f"{prefix}-{run_id}-{attempt}")}
                             for platform, (_, _, prefix) in APPLICATIONS.items()]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("aggregate", "collect", "verify"))
    parser.add_argument("--source", required=True)
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--run", type=int)
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        spec = importlib.util.spec_from_file_location("sample_policy", Path(__file__).with_name("publish-sample-release.py"))
        policy = importlib.util.module_from_spec(spec); spec.loader.exec_module(policy)
        need(SHA.fullmatch(args.source) and os.environ.get("GITHUB_REPOSITORY") == REPOSITORY,
             "Aggregator source/repository differs")
        if args.operation == "verify":
            checked_out = subprocess.run(["git", "--no-replace-objects", "rev-parse", "HEAD"],
                cwd=Path(__file__).resolve().parents[1], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=15, check=True).stdout.decode().strip()
            need(checked_out == args.source, "Verification checkout differs from selected source")
        else:
            need(args.source == os.environ.get("GITHUB_SHA"), "Aggregator hosted source differs")
        api = policy.Api(os.environ.get("GH_TOKEN", ""))
        # Thirteen independently encrypted results plus four public application bundles.
        policy.TRANSFER_LIMIT = (len(COMPONENTS) + 4) * ARTIFACT_LIMIT
        if args.operation == "verify":
            binding = None if args.selection is None else parsed(args.selection.read_bytes())
            document, _ = load_qualification(api, args.source, binding)
        elif args.operation == "collect":
            supplied = os.environ.get("CI_SELECTION", "")
            document = parsed(supplied.encode()) if supplied else collect(api, args.source, args.run, args.attempt)
            need(document.get("source") == args.source, "Explicit selection has another source")
        else:
            need(args.selection is not None and args.run is None and args.attempt is None, "Wrong aggregate arguments")
            selection = parsed(args.selection.read_bytes())
            need(selection["source"] == args.source, "Selection has another source")
            document = aggregate(api, selection)
        raw = encoded(document)
        need(len(raw) <= JSON_LIMIT, "Qualification record too large")
        with args.output.open("xb") as stream:
            stream.write(raw)
        print("QUALIFIED_COMPONENT_SELECTION_NOT_PUBLICATION")
        return 0
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, subprocess.SubprocessError, zipfile.BadZipFile) as error:
        # AdmissionError is constructed here only from fixed source-owned
        # reasons. Never render API exceptions, bodies, signed URLs or paths.
        reason = str(error) if type(error) is AdmissionError else "component qualification refused"
        print("HOLD: " + reason)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
