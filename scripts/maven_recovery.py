#!/usr/bin/env python3
"""Read-only recovery of a published Maven attempt's failed verification tail.

The original attempt remains FAILED. Only a separately approved successful
recovery workflow can provide verification authority. No upload, signing,
absence probe, tag/release mutation, library build or evidence renewal exists.
"""

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("deployment_evidence", ROOT / "scripts/central_deployment_evidence.py")
D = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(D)
P, F = D.P, D.F
WORKFLOW = ".github/workflows/recover-maven-central.yml"
NAME = "Recover Maven Central verification"
ENVIRONMENT = "maven-central-recovery"
REQUEST = "recovery-request.json"
RESULT = "recovery-result.json"
SIGNED_UPLOAD = "Retain reviewed signed bundle before Central upload"
DEPLOYMENT_UPLOAD = "Retain original PUBLISHED deployment receipt"
PORTAL_UPLOAD = "Upload once and wait for publication"
REMOTE = "Verify immutable remote bytes and consumers"
VERIFY_ORIGINALS = "Verify original public signatures and immutable remote bytes"
VERIFY_CONSUMERS = "Verify complete remote consumers without republishing"
PREPARE = "Prepare the exact original recovery request"
REQUEST_UPLOAD = "Retain the immutable recovery request"
AUTHORIZE = "Require the exact protected recovery approval"
RECORD_RESULT = "Record fresh recovery verification and original custody"
RESULT_UPLOAD = "Retain the successful public recovery result"
REQUEST_SCOPE = "P2PKIT_MAVEN_RECOVERY_REQUEST"
RESULT_SCOPE = "P2PKIT_MAVEN_RECOVERY_VERIFIED_PUBLIC_RESULT"
REMOTE_SCRIPT = "scripts/check-maven-central-version.sh"
CONSUMER_SCRIPT = "scripts/check-published-consumers.sh"
COMMANDS = {"remote": [REMOTE_SCRIPT, "published", "ORIGINAL_SIGNED_BUNDLE"], "consumers": [CONSUMER_SCRIPT]}
LOG_LIMIT = 64 * P.MIB
JOB_SECONDS = 90 * 60
REQUIRED_STEPS = (
    "Revalidate frozen applications and exact owner approval",
    "Revalidate approved release and credentials",
    "Build and inspect signed Central bundle",
    "Generate and verify publication-build SBOM",
    "Validate signed originals before retention",
    SIGNED_UPLOAD,
    "Revalidate original readiness immediately before irreversible upload",
    PORTAL_UPLOAD,
    "Bind original completed Portal publication",
    DEPLOYMENT_UPLOAD,
)


class ReadOnlyApi(P.Api):
    def open(self, url, *, method="GET", **options):
        P.need(method == "GET", "Recovery has no mutation authority")
        return super().open(url, method=method, **options)


def job(api, invocation, name, conclusion):
    rows = api.pages(f"/actions/runs/{invocation['id']}/attempts/{invocation['attempt']}/jobs", "jobs")
    found = [x for x in rows if x.get("name") == name]
    P.need(len(found) == 1, "Missing or ambiguous original workflow job")
    value = found[0]
    P.need(value.get("run_id") == invocation["id"] and value.get("run_attempt") == invocation["attempt"] and
           value.get("head_sha") == invocation["source"] and value.get("status") == "completed" and
           value.get("conclusion") == conclusion and
           P.timestamp(value["started_at"]) <= P.timestamp(value["completed_at"]) <= time.time(),
           "Original job/source/attempt/conclusion differs")
    return value


def step(job_value, name, conclusion="success"):
    found = [x for x in job_value["steps"] if x.get("name") == name]
    P.need(len(found) == 1 and found[0].get("status") == "completed" and
           found[0].get("conclusion") == conclusion, "Missing required original step result")
    value = found[0]
    upper = P.timestamp(job_value["completed_at"]) if job_value.get("completed_at") else time.time()
    P.need(type(value.get("number")) is int and value["number"] > 0 and
           P.timestamp(job_value["started_at"]) <= P.timestamp(value["started_at"]) <=
           P.timestamp(value["completed_at"]) <= upper,
           "Original step timing is outside its job")
    return {key: value[key] for key in ("number", "name", "started_at", "completed_at", "conclusion")}


def original_invocation(api, source, identifier, attempt):
    identifier, attempt = P.number(identifier), P.number(attempt)
    run = api.json(f"/actions/runs/{identifier}/attempts/{attempt}")
    current = api.json(f"/actions/runs/{identifier}")
    workflow = api.json("/actions/workflows/publish-maven-central.yml")
    invocation = P.maven_source_identity(api, source, identifier, attempt, run, workflow)
    P.need(current.get("id") == identifier and current.get("run_attempt") == attempt and
           run.get("status") == current.get("status") == "completed" and
           run.get("conclusion") == current.get("conclusion") == "failure",
           "Recovery requires the unchanged original failed attempt, never a cancellation or later rerun")
    jobs = {}
    for name in ("freeze-applications", "verify-release", "publish-release"):
        value = job(api, invocation, name, "failure" if name == "publish-release" else "success")
        jobs[name] = {key: value[key] for key in ("id", "name", "started_at", "completed_at", "conclusion")}
        if name == "publish-release":
            bound = [step(value, name) for name in REQUIRED_STEPS]
            numbers = [x["number"] for x in bound]
            P.need(numbers == sorted(set(numbers)), "Original publication stage order differs")
            failures = [x for x in value["steps"] if x.get("conclusion") != "success"]
            allowed = {REMOTE, "Upload publication evidence"}
            P.need(any(x.get("conclusion") == "failure" for x in failures) and
                   all(x.get("name") in allowed and x.get("conclusion") in ("failure", "skipped") and
                                   x.get("number", 0) > numbers[-1] for x in failures),
                   "Original failure was not solely in the post-publication verification/evidence tail")
            remote = [x for x in value["steps"] if x.get("name") == REMOTE]
            P.need(len(remote) == 1 and remote[0].get("conclusion") in ("success", "failure") and
                   remote[0].get("number", 0) > numbers[-1], "Remote verification tail was missing or never executed")
            jobs[name]["verificationTail"] = step(value, REMOTE, remote[0]["conclusion"])
            P.need(all(P.timestamp(left["completed_at"]) <= P.timestamp(right["started_at"])
                       for left, right in zip(bound, bound[1:] + [jobs[name]["verificationTail"]])),
                   "Original publication steps overlap or were reordered")
            jobs[name]["requiredSteps"] = bound
    return invocation, jobs


def original_artifact(api, invocation, name, original_step):
    candidates = [x for x in api.pages(f"/actions/runs/{invocation['id']}/artifacts", "artifacts")
                  if x.get("name") == name]
    P.need(len(candidates) == 1, "Missing/ambiguous original publication artifact; never substitute")
    artifact = P.artifact_identity(candidates[0], invocation["id"], invocation["source"], invocation["tag"])
    P.need(P.timestamp(original_step["started_at"]) <= P.timestamp(artifact["created_at"]) <=
           P.timestamp(original_step["completed_at"]), "Artifact was not retained by its original upload step")
    return artifact


def original_metadata(api, source, identifier, attempt, frozen_artifact, frozen_sha256, directory,
                      *, remaining_seconds=F.MAVEN_HEADROOM):
    invocation, jobs = original_invocation(api, source, identifier, attempt)
    commit = api.json("/git/commits/" + source)
    P.need(commit.get("sha") == source and P.SHA.fullmatch(commit.get("tree", {}).get("sha", "")),
           "Missing exact original release tree")
    document, frozen = F.load(api, invocation, directory, artifact_id=frozen_artifact,
                              expected_hash=frozen_sha256, remaining_seconds=remaining_seconds)
    P.need(document["qualification"]["source"] == {"commit": source, "tree": commit["tree"]["sha"]},
           "Frozen source tree differs from the original tag commit")
    approval = F.require_approval(api, document, frozen)
    steps = {x["name"]: x for x in jobs["publish-release"]["requiredSteps"]}
    suffix = f"{invocation['tag']}-{invocation['id']}-{invocation['attempt']}"
    signed = original_artifact(api, invocation, "maven-central-signed-bundle-" + suffix, steps[SIGNED_UPLOAD])
    deployment = original_artifact(api, invocation, "maven-central-deployment-" + suffix, steps[DEPLOYMENT_UPLOAD])
    P.need(signed["id"] != deployment["id"] and deployment["size_in_bytes"] <= 8 * P.JSON_LIMIT,
           "Original artifact roster/size differs")
    end = min((document["expiresAt"], frozen["artifact"]["expires_at"], signed["expires_at"], deployment["expires_at"]),
              key=P.timestamp)
    P.need(time.time() + remaining_seconds < P.timestamp(end), "Original retention cannot cover recovery and delivery")
    return {"maven": invocation, "originalConclusion": "failure", "tree": commit["tree"]["sha"], "jobs": jobs,
            "qualification": document["qualification"],
            "frozenApplicationSet": {**frozen, "ownerApproval": approval},
            "artifacts": {"signedBundle": signed, "deployment": deployment}, "expiresAt": end}


def unpack(api, artifact, names, directory, *, total_limit):
    """Copy only predeclared regular public members into an owned empty folder."""
    directory.mkdir(mode=0o700)
    path = directory / "original.zip"
    api.download(artifact, path)
    try:
        P.need(P.PACK.file_hash(path, P.ARCHIVE_LIMIT) == {"bytes": artifact["size_in_bytes"],
               "sha256": artifact["digest"].removeprefix("sha256:")}, "Original artifact digest/size differs")
        with P.PACK.zip_input(path) as archive:
            rows = archive.infolist()
            P.need(len(rows) == len(names) and {x.filename for x in rows} == set(names) and
                   sum(x.file_size for x in rows) <= total_limit and
                   all(x.orig_filename == x.filename and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", x.filename) and
                       not x.is_dir() and not x.flag_bits & 1 and
                       stat.S_IFMT(x.external_attr >> 16) in (0, stat.S_IFREG) and
                       0 < x.file_size <= names[x.filename] for x in rows), "Original artifact member roster differs")
            for item in rows:
                with archive.open(item) as source, (directory / item.filename).open("xb") as target:
                    count = 0
                    while data := source.read(P.MIB):
                        count += len(data)
                        P.need(count <= item.file_size, "Original archive member exceeds its declared bound")
                        target.write(data)
                    P.need(count == item.file_size, "Original archive member is truncated")
    finally:
        path.unlink()  # Exclusively created, public original download only.


def inspect_originals(api, original, directory, *, signatures):
    spec = importlib.util.spec_from_file_location("central_bundle", ROOT / "scripts/central_bundle_evidence.py")
    bundle_policy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bundle_policy)
    invocation = original["maven"]
    stem = f"p2pkit-{invocation['version']}-central-bundle"
    signed, deployment = directory / "signed", directory / "deployment"
    names = {stem + ".zip": P.ARCHIVE_LIMIT, stem + ".manifest.sha256": P.JSON_LIMIT,
             stem + ".summary.json": P.JSON_LIMIT, stem + ".public.asc": P.JSON_LIMIT}
    unpack(api, original["artifacts"]["signedBundle"], names, signed, total_limit=P.ARCHIVE_LIMIT + 3 * P.JSON_LIMIT)
    unpack(api, original["artifacts"]["deployment"], {name: P.JSON_LIMIT for name in (*D.FILES, "deployment-receipt.json")},
           deployment, total_limit=6 * P.JSON_LIMIT)
    inspection = bundle_policy.inspect(signed / (stem + ".zip"), signed / (stem + ".manifest.sha256"),
                                       signed / (stem + ".summary.json"), signed / (stem + ".public.asc"),
                                       invocation["source"], original["tree"], invocation["version"],
                                       verify_signatures=signatures)
    summary_raw = D.read(signed / (stem + ".summary.json"))
    originals = {name: D.read(deployment / name) for name in D.FILES}
    receipt = D.receipt({"source": invocation["source"], "tag": invocation["tag"], "id": invocation["id"],
                         "attempt": invocation["attempt"]}, original["tree"], summary_raw, originals)
    P.need(D.read(deployment / "deployment-receipt.json") == P.encoded(receipt), "Original deployment receipt differs")
    upload = next(x for x in original["jobs"]["publish-release"]["requiredSteps"] if x["name"] == PORTAL_UPLOAD)
    P.need(P.timestamp(upload["started_at"]) <= D.event_time(receipt["deployment"]["startedAt"]) <=
           D.event_time(receipt["deployment"]["completedAt"]) <= P.timestamp(upload["completed_at"]),
           "Original Portal events are outside the successful original upload step")
    return receipt, inspection, signed / (stem + ".zip")


def environment(api):
    value = api.json("/environments/" + ENVIRONMENT)
    P.need(value.get("name") == ENVIRONMENT and value.get("can_admins_bypass") is False and
           value.get("deployment_branch_policy") == {"protected_branches": False, "custom_branch_policies": True},
           "Recovery requires its separate protected main-only environment")
    rules = value.get("protection_rules", [])
    P.need(len(rules) == 2 and sorted(x.get("type", "") for x in rules) == ["branch_policy", "required_reviewers"],
           "Missing or unreviewed recovery protection rules")
    owners = next(x for x in rules if x["type"] == "required_reviewers")
    reviewers = owners.get("reviewers", [])
    P.need(owners.get("prevent_self_review") is False and len(reviewers) == 1 and
           reviewers[0].get("type") == "User" and P.is_owner(reviewers[0].get("reviewer")),
           "Recovery requires the owner's personal protected approval")
    branches = api.pages("/environments/" + ENVIRONMENT + "/deployment-branch-policies", "branch_policies")
    P.need(len(branches) == 1 and branches[0].get("type") == "branch" and branches[0].get("name") == "main",
           "Recovery environment may admit main only, not Maven tags")
    return {"id": P.number(value["id"]), "name": ENVIRONMENT, "owner": {"login": P.OWNER_LOGIN, "id": P.OWNER_ID},
            "branch": "main", "preventSelfReview": False, "canAdminsBypass": False}


def challenge(request):
    context = request["recovery"]
    return f"APPROVE_MAVEN_RECOVERY {context['id']}/{context['attempt']} {hashlib.sha256(P.encoded(request)).hexdigest()}"


def approval(api, request):
    P.need(environment(api) == request["environment"], "Recovery environment changed after request preparation")
    rows = api.json(f"/actions/runs/{request['recovery']['id']}/approvals")
    P.need(type(rows) is list and len(rows) <= 1000, "Unexpected recovery approval history")
    line = challenge(request)
    found = [x for x in rows if type(x.get("comment")) is str and x["comment"].strip() == line]
    P.need(len(found) == 1 and found[0].get("state") == "approved" and P.is_owner(found[0].get("user")),
           "Missing unique personal approval of this exact recovery attempt/request")
    environments = found[0].get("environments", [])
    P.need(len(environments) == 1 and environments[0].get("id") == request["environment"]["id"] and
           environments[0].get("name") == ENVIRONMENT, "Approval belongs to another protected environment")
    return {"owner": request["environment"]["owner"], "environment": request["environment"]["id"],
            "comment": line, "state": "approved"}


def recovery_invocation(api, identifier, attempt, *, completed):
    """The main controller commit is NOT the original release/library source."""
    identifier, attempt = P.number(identifier), P.number(attempt)
    run = api.json(f"/actions/runs/{identifier}/attempts/{attempt}")
    current = api.json(f"/actions/runs/{identifier}")
    workflow = api.json("/actions/workflows/recover-maven-central.yml")
    source = run.get("head_sha", "")
    P.need(P.SHA.fullmatch(source) and run.get("id") == current.get("id") == identifier and
           run.get("run_attempt") == current.get("run_attempt") == attempt and
           run.get("path") == workflow.get("path") == WORKFLOW and run.get("name") == NAME and
           run.get("workflow_id") == workflow.get("id") and type(workflow.get("id")) is int and
           run.get("event") == "workflow_dispatch" and run.get("head_branch") == "main" and
           run.get("repository", {}).get("full_name") == run.get("head_repository", {}).get("full_name") == P.REPO and
           current.get("head_sha") == source and P.is_owner(run.get("actor")) and P.is_owner(run.get("triggering_actor")),
           "Recovery requires the exact owner-dispatched main workflow attempt")
    P.need(run.get("status") == current.get("status") == ("completed" if completed else "in_progress") and
           run.get("conclusion") == current.get("conclusion") == ("success" if completed else None),
           "Recovery is not the unchanged required running/successful attempt")
    commit = api.json("/git/commits/" + source)
    P.need(commit.get("sha") == source and P.SHA.fullmatch(commit.get("tree", {}).get("sha", "")),
           "Missing exact trusted-controller tree")
    main = api.json("/git/ref/heads/main")["object"]["sha"]
    P.need(P.SHA.fullmatch(main), "Missing current main identity")
    comparison = api.json(f"/compare/{source}...{main}")
    P.need(comparison.get("status") in ("identical", "ahead") and
           comparison.get("merge_base_commit", {}).get("sha") == source, "Recovery controller is not preserved in main")
    return {"id": identifier, "attempt": attempt, "source": source, "tree": commit["tree"]["sha"],
            "workflowId": workflow["id"], "workflowPath": WORKFLOW}


def hosted_context(api, env, operation):
    expected_job = "prepare-recovery" if operation == "prepare" else "verify-recovery"
    P.need(env.get("GITHUB_ACTIONS") == "true" and env.get("RUNNER_ENVIRONMENT") == "github-hosted" and
           env.get("GITHUB_REPOSITORY") == P.REPO and env.get("GITHUB_SERVER_URL") == "https://github.com" and
           env.get("GITHUB_API_URL") == P.API and env.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and
           env.get("GITHUB_REF") == "refs/heads/main" and
           env.get("GITHUB_WORKFLOW_REF") == P.REPO + "/" + WORKFLOW + "@refs/heads/main" and
           env.get("GITHUB_JOB") == expected_job and
           env.get("RUNNER_OS") == ("Linux" if operation == "prepare" else "macOS"),
           "Recovery operation requires its genuine protected hosted main job")
    context = recovery_invocation(api, env.get("GITHUB_RUN_ID"), env.get("GITHUB_RUN_ATTEMPT"), completed=False)
    P.need(context["source"] == env.get("GITHUB_WORKFLOW_SHA") == env.get("GITHUB_SHA"),
           "Recovery controller/environment identity differs")
    verify_checkout(ROOT, context["source"], context["tree"])
    return context


def verify_checkout(directory, source, tree, version=None):
    P.PACK.physical_directory(directory)
    P.need(P.PACK.git(directory, "--no-replace-objects", "rev-parse", "HEAD").decode() == source and
           P.PACK.git(directory, "--no-replace-objects", "rev-parse", "HEAD^{tree}").decode() == tree and
           not P.PACK.git(directory, "status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none"),
           "Checkout is dirty or differs from the exact controller/original source tree")
    if version is not None:
        P.need(directory != ROOT and not (directory in ROOT.parents or ROOT in directory.parents),
               "Original source must be a separate physical checkout, never the trusted controller")
        P.need(P.VERSION.from_properties(D.read(directory / "gradle.properties", 65536).decode())["canonicalVersion"] == version,
               "Original consumer version differs; current-main/version overrides are forbidden")


def active_job(api, context):
    rows = api.pages(f"/actions/runs/{context['id']}/attempts/{context['attempt']}/jobs", "jobs")
    values = [x for x in rows if x.get("name") == "verify-recovery"]
    P.need(len(values) == 1, "Missing/ambiguous active recovery job")
    value = values[0]
    P.need(value.get("run_id") == context["id"] and value.get("run_attempt") == context["attempt"] and
           value.get("head_sha") == context["source"] and value.get("status") == "in_progress" and
           value.get("conclusion") is None and value.get("completed_at") is None and
           P.timestamp(value["started_at"]) <= time.time() < P.timestamp(value["started_at"]) + JOB_SECONDS,
           "Recovery job is not the current bounded running provider")
    return value


def bundle_identity(value):
    return {key: item for key, item in value.items()
            if key not in ("scope", "signaturesVerified", "signerFingerprints", "members")}


def signature_receipt(value, expected):
    compact = {key: item for key, item in value.items() if key != "members"}
    signers = compact.get("signerFingerprints")
    P.need(bundle_identity(compact) == expected and compact.get("scope") == "VERIFIED_PUBLIC_SIGNATURES" and
           compact.get("signaturesVerified") is True and type(signers) is list and
           1 <= len(signers) <= 84 and signers == sorted(set(signers)) and
           all(type(x) is str and re.fullmatch(r"(?:[0-9A-F]{40}|[0-9A-F]{64})", x) for x in signers),
           "Full original public-signature verification is missing or differently bound")
    return compact


def request_name(context):
    return f"maven-central-recovery-request-{context['id']}-{context['attempt']}"


def result_name(context):
    return f"maven-central-recovery-{context['id']}-{context['attempt']}"


def prepare(api, context, source, identifier, attempt, frozen_artifact, frozen_sha256, directory):
    existing = api.pages(f"/actions/runs/{context['id']}/artifacts", "artifacts")
    P.need(not any(x.get("name") in (request_name(context), result_name(context)) for x in existing),
           "This recovery attempt already retained evidence; never overwrite/reselect it")
    original = original_metadata(api, source, identifier, attempt, frozen_artifact, frozen_sha256, directory)
    # Structural public metadata only, not signature or recovery authority.
    # After the exact owner approval, verify-originals must use signatures=True.
    deployment, inspection, _ = inspect_originals(api, original, directory, signatures=False)
    request = {"schema": 1, "scope": REQUEST_SCOPE, "recovery": context, "preparedAt": int(time.time()),
               "environment": environment(api), "original": original, "deployment": deployment,
               "bundle": bundle_identity(inspection)}
    P.need(original_metadata(api, source, identifier, attempt, frozen_artifact, frozen_sha256, directory) == original and
           recovery_invocation(api, context["id"], context["attempt"], completed=False) == context and
           environment(api) == request["environment"], "Original inputs/controller/protection changed during preparation")
    return request


def load_request(api, context, artifact_id, expected_hash, directory, *, remaining_seconds):
    P.need(type(expected_hash) is str and re.fullmatch(r"[0-9a-f]{64}", expected_hash), "Missing exact recovery request hash")
    item = api.json(f"/actions/artifacts/{P.number(artifact_id)}")
    artifact = P.artifact_identity(item, context["id"], context["source"])
    P.need(artifact["name"] == request_name(context) and artifact["size_in_bytes"] <= 2 * P.JSON_LIMIT,
           "Recovery request is not this attempt's bounded original artifact")
    stage = job(api, context, "prepare-recovery", "success")
    prepared, uploaded = step(stage, PREPARE), step(stage, REQUEST_UPLOAD)
    P.need(prepared["number"] < uploaded["number"] and
           P.timestamp(prepared["completed_at"]) <= P.timestamp(uploaded["started_at"]) <=
           P.timestamp(artifact["created_at"]) <= P.timestamp(uploaded["completed_at"]),
           "Request artifact was not retained by the exact successful preparation step")
    folder = directory / "request"
    unpack(api, artifact, {REQUEST: P.JSON_LIMIT}, folder, total_limit=P.JSON_LIMIT)
    raw = D.read(folder / REQUEST)
    request = P.parsed(raw)
    P.need(raw == P.encoded(request) and hashlib.sha256(raw).hexdigest() == expected_hash and
           set(request) == {"schema", "scope", "recovery", "preparedAt", "environment", "original", "deployment", "bundle"} and
           type(request["schema"]) is int and request["schema"] == 1 and request["scope"] == REQUEST_SCOPE and
           request["recovery"] == context and type(request["preparedAt"]) is int and
           P.timestamp(prepared["started_at"]) <= request["preparedAt"] <= P.timestamp(prepared["completed_at"]),
           "Recovery request is not canonical or differs from its exact source/attempt/preparation")
    original = request["original"]
    invocation, frozen = original["maven"], original["frozenApplicationSet"]
    P.need(original_metadata(api, invocation["source"], invocation["id"], invocation["attempt"],
                             frozen["artifact"]["id"], frozen["sha256"], directory,
                             remaining_seconds=remaining_seconds) == original,
           "Original failed attempt, frozen apps, gates, ownership or custody changed")
    P.need(environment(api) == request["environment"] and
           time.time() + remaining_seconds < P.timestamp(artifact["expires_at"]),
           "Recovery protection/request retention cannot cover the remaining execution")
    return request, {"artifact": artifact, "sha256": expected_hash, "prepareJob": {
        "id": P.number(stage["id"]), "completedAt": stage["completed_at"], "steps": [prepared, uploaded]}}


def owned_directory(parent, context, *, create):
    P.PACK.physical_directory(parent)
    directory = parent / "p2pkit-maven-recovery"
    if create:
        directory.mkdir(mode=0o700)
    P.PACK.physical_directory(directory)
    info = directory.stat()
    owner = {"recovery": context, "device": info.st_dev, "inode": info.st_ino}
    marker = directory / ".owner.json"
    if create:
        with marker.open("xb") as stream:
            stream.write(P.encoded(owner))
    P.need(D.read(marker) == P.encoded(owner), "Recovery temporary-directory ownership differs")
    return directory


def write_record(directory, name, value):
    raw = P.encoded(value)
    P.need(len(raw) <= P.JSON_LIMIT, "Public recovery record exceeds its bound")
    with (directory / name).open("xb") as stream:
        stream.write(raw)


def read_record(directory, name):
    raw = D.read(directory / name)
    value = P.parsed(raw)
    P.need(raw == P.encoded(value), "Local recovery record is not canonical")
    return value


def execution_environment(environment, directory, purpose):
    """No GH/Central/signing credentials, inherited Gradle options or user home."""
    keys = ("PATH", "JAVA_HOME", "ANDROID_HOME", "ANDROID_SDK_ROOT", "DEVELOPER_DIR", "SDKROOT")
    result = {key: environment[key] for key in keys if environment.get(key)}
    P.need(result.get("PATH") and result.get("JAVA_HOME") and result.get("ANDROID_HOME"), "Missing hosted SDK tool paths")
    for name in ("home", "tmp"):
        (directory / name).mkdir(mode=0o700)
    result.update(HOME=str(directory / "home"), TMPDIR=str(directory / "tmp"), LANG="en_US.UTF-8", LC_ALL="en_US.UTF-8",
                  CI="true")
    if purpose == "consumers":
        result.update(P2PKIT_CONSUMER_REPOSITORY_URL="https://repo.maven.apache.org/maven2",
                      P2PKIT_CONSUMER_PROFILE="complete", P2PKIT_CONSUMER_WORK_DIR=str(directory / "consumer"))
    return result


def group_exists(identifier):
    try:
        os.killpg(identifier, 0)
        return True
    except ProcessLookupError:
        return False


def retire_group(process):
    """Bound only the process group we created; never target borrowed processes."""
    if group_exists(process.pid):
        os.killpg(process.pid, signal.SIGTERM)
        end = time.monotonic() + 2
        while group_exists(process.pid) and time.monotonic() < end:
            process.poll()
            time.sleep(0.05)
        if group_exists(process.pid):
            os.killpg(process.pid, signal.SIGKILL)
    process.wait(timeout=5)


def run_command(request, source_root, purpose, directory, deadline, bundle=None):
    """No test-mode/version/profile overrides; capture no output in Actions logs."""
    original, context = request["original"], request["recovery"]
    invocation = original["maven"]
    P.need(purpose in COMMANDS, "Unapproved recovery command")
    verify_checkout(source_root, invocation["source"], original["tree"], invocation["version"])
    script = source_root / COMMANDS[purpose][0]
    script_hash = P.PACK.file_hash(script, P.JSON_LIMIT)
    command = ["bash", str(script)]
    if purpose == "remote":
        P.need(bundle is not None and P.PACK.file_hash(bundle, P.ARCHIVE_LIMIT) == {
            "bytes": request["bundle"]["bundleSizeBytes"], "sha256": request["bundle"]["bundleSha256"]},
            "Remote verifier lacks the original inspected signed bundle")
        command += ["published", str(bundle)]
    env = execution_environment(os.environ, directory, purpose)
    output = directory / "command.log"
    wall_start, monotonic_start = time.time(), time.monotonic()
    started = int(wall_start)
    P.need(wall_start < deadline, "Recovery job has no execution time remaining")
    # Clip once from the original provider deadline. A subsequent wall-clock
    # rollback cannot grant more command time; the hosted 90-minute job remains.
    monotonic_deadline = monotonic_start + min(JOB_SECONDS, deadline - wall_start)
    process, failure, closure_error, receipt = None, None, None, None
    phase, failed_phase = "start", None
    try:
        with output.open("xb") as stream:
            os.chmod(output, 0o600)
            process = subprocess.Popen(command, cwd=source_root, env=env, stdin=subprocess.DEVNULL,
                                       stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            phase = "execution"
            while process.poll() is None:
                P.need(time.monotonic() < monotonic_deadline and output.stat().st_size <= LOG_LIMIT,
                       "Recovery command exceeded its remaining job/output safety budget")
                time.sleep(0.25)
        phase = "exit"
        P.need(process.returncode == 0, "Original " + purpose + " verification failed; no retry or publication authority")
        phase = "process-group-close"
        P.need(not group_exists(process.pid), "Recovery command left live same-group processes")
        completed = int(time.time())
        phase = "timing-and-source"
        P.need(time.monotonic() <= monotonic_deadline, "Recovery command exceeded its remaining job window")
        log = P.PACK.file_hash(output, LOG_LIMIT)
        verify_checkout(source_root, invocation["source"], original["tree"], invocation["version"])
        receipt = {"recovery": context, "requestSha256": hashlib.sha256(P.encoded(request)).hexdigest(),
                   "source": {"commit": invocation["source"], "tree": original["tree"]}, "purpose": purpose,
                   "command": COMMANDS[purpose], "script": script_hash, "startedAt": started, "completedAt": completed,
                   "wallSeconds": round(time.monotonic() - monotonic_start, 3), "exitCode": 0, "log": log,
                   "ownedProcessGroupRetired": True}
    except BaseException as error:
        failure, failed_phase = error, phase
    finally:
        try:
            if process is not None and (process.poll() is None or group_exists(process.pid)):
                retire_group(process)
                P.need(not group_exists(process.pid), "Owned command process group did not retire")
        except BaseException as error:
            closure_error = error
        # Preserve originals and consumer work in this owned per-job directory,
        # including failure/unknown-close paths. Never upload the raw log. The
        # ephemeral runner's disposal is not a retained failure-evidence claim.
        status = {"purpose": purpose, "result": "PASS" if failure is closure_error is None else "HOLD",
                  "phase": failed_phase or ("retirement" if closure_error else "complete"),
                  "exitCode": None if process is None else process.returncode,
                  "errorType": None if failure is None else type(failure).__name__,
                  "retirementErrorType": None if closure_error is None else type(closure_error).__name__}
        try:
            write_record(directory, "command-status.json", status)
        except BaseException as error:
            if failure is closure_error is None:
                closure_error = error
        if failure is not None:
            raise failure
        if closure_error is not None:
            raise P.Hold("Recovery command closure/status recording failed; originals retained") from None
    return receipt


def validate_command(value, request, purpose, provider_step):
    P.need(set(value) == {"recovery", "requestSha256", "source", "purpose", "command", "script", "startedAt", "completedAt",
                          "wallSeconds", "exitCode", "log", "ownedProcessGroupRetired"} and
           value["recovery"] == request["recovery"] and value["requestSha256"] == hashlib.sha256(P.encoded(request)).hexdigest() and
           value["source"] == request["original"]["qualification"]["source"] and value["purpose"] == purpose and
           value["command"] == COMMANDS[purpose] and type(value["exitCode"]) is int and value["exitCode"] == 0 and
           value["ownedProcessGroupRetired"] is True and type(value["startedAt"]) is type(value["completedAt"]) is int and
           P.timestamp(provider_step["started_at"]) <= value["startedAt"] <= value["completedAt"] <=
           P.timestamp(provider_step["completed_at"]) and
           type(value["wallSeconds"]) in (int, float) and 0 <= value["wallSeconds"] <= JOB_SECONDS and
           abs((value["completedAt"] - value["startedAt"]) - value["wallSeconds"]) <= 2,
           "Recovery command receipt lacks an exact successful provider-step/source join")
    for key, limit in (("script", P.JSON_LIMIT), ("log", LOG_LIMIT)):
        item = value[key]
        P.need(set(item) == {"bytes", "sha256"} and type(item["bytes"]) is int and 0 < item["bytes"] <= limit and
               re.fullmatch(r"[0-9a-f]{64}", item["sha256"]), "Recovery command output/script identity differs")


def verification_steps(value):
    names = (AUTHORIZE, VERIFY_ORIGINALS, VERIFY_CONSUMERS)
    steps = [step(value, name) for name in names]
    P.need([x["number"] for x in steps] == sorted({x["number"] for x in steps}) and
           all(P.timestamp(left["completed_at"]) <= P.timestamp(right["started_at"])
               for left, right in zip(steps, steps[1:])), "Recovery verification steps overlap or are out of order")
    return steps


def finish(api, request, descriptor, authorization, directory, source_root):
    context, original = request["recovery"], request["original"]
    P.need(recovery_invocation(api, context["id"], context["attempt"], completed=False) == context and
           approval(api, request) == authorization, "Controller or exact owner approval changed before result retention")
    verify_checkout(source_root, original["maven"]["source"], original["tree"], original["maven"]["version"])
    provider = active_job(api, context)
    steps = verification_steps(provider)
    originals = read_record(directory, "verified-originals.json")
    consumers = read_record(directory, "verified-consumers.json")
    P.need(set(originals) == {"deployment", "bundle", "remote"} and originals["deployment"] == request["deployment"],
           "Verified original deployment differs from the approved request")
    signature_receipt(originals["bundle"], request["bundle"])
    validate_command(originals["remote"], request, "remote", steps[1])
    validate_command(consumers, request, "consumers", steps[2])
    for purpose, receipt in (("remote", originals["remote"]), ("consumers", consumers)):
        P.need(P.PACK.file_hash(source_root / COMMANDS[purpose][0], P.JSON_LIMIT) == receipt["script"],
               "Original verifier/consumer source changed before recording the result")
    end = min((original["expiresAt"], descriptor["artifact"]["expires_at"]), key=P.timestamp)
    P.need(time.time() + F.DELIVERY_HEADROOM < P.timestamp(end), "Original custody cannot cover subsequent sample delivery")
    return {"schema": 1, "scope": RESULT_SCOPE, "recovery": context, "request": descriptor, "ownerApproval": authorization,
            "original": original, "originalConclusion": "failure", "verification": {**originals, "consumers": consumers},
            "provider": {"id": P.number(provider["id"]), "name": "verify-recovery", "startedAt": provider["started_at"], "steps": steps},
            "recordedAt": int(time.time()), "expiresAt": end}


def publication_plan(api, identifier, attempt, directory, *, artifact_id=None, expected_hash=None):
    """Successful recovery is distinct authority; the original Maven stays failed."""
    context = recovery_invocation(api, identifier, attempt, completed=True)
    provider = job(api, context, "verify-recovery", "success")
    steps = verification_steps(provider)
    recorded, uploaded = step(provider, RECORD_RESULT), step(provider, RESULT_UPLOAD)
    P.need(steps[-1]["number"] < recorded["number"] < uploaded["number"] and
           P.timestamp(steps[-1]["completed_at"]) <= P.timestamp(recorded["started_at"]) <=
           P.timestamp(recorded["completed_at"]) <= P.timestamp(uploaded["started_at"]) and
           P.timestamp(provider["completed_at"]) - P.timestamp(provider["started_at"]) <= JOB_SECONDS,
           "Recovery result was not recorded after successful bounded verification")
    if artifact_id is None:
        P.need(expected_hash is None, "Recovery result hash requires its exact artifact ID")
        found = [x for x in api.pages(f"/actions/runs/{context['id']}/artifacts", "artifacts") if x.get("name") == result_name(context)]
        P.need(len(found) == 1, "Missing/ambiguous original recovery result; never choose latest")
        item = found[0]
    else:
        P.need(type(expected_hash) is str and re.fullmatch(r"[0-9a-f]{64}", expected_hash), "Missing exact recovery result hash")
        item = api.json(f"/actions/artifacts/{P.number(artifact_id)}")
    artifact = P.artifact_identity(item, context["id"], context["source"])
    P.need(artifact["name"] == result_name(context) and artifact["size_in_bytes"] <= 2 * P.JSON_LIMIT and
           P.timestamp(uploaded["started_at"]) <= P.timestamp(artifact["created_at"]) <= P.timestamp(uploaded["completed_at"]),
           "Recovery result artifact does not belong to its exact successful upload step")
    folder = directory / "result"
    unpack(api, artifact, {RESULT: P.JSON_LIMIT}, folder, total_limit=P.JSON_LIMIT)
    raw = D.read(folder / RESULT)
    value, digest = P.parsed(raw), hashlib.sha256(raw).hexdigest()
    P.need(raw == P.encoded(value) and (expected_hash is None or digest == expected_hash) and
           set(value) == {"schema", "scope", "recovery", "request", "ownerApproval", "original", "originalConclusion",
                          "verification", "provider", "recordedAt", "expiresAt"} and
           type(value["schema"]) is int and value["schema"] == 1 and value["scope"] == RESULT_SCOPE and
           value["recovery"] == context and value["originalConclusion"] == "failure" and
           type(value["recordedAt"]) is int and
           P.timestamp(recorded["started_at"]) <= value["recordedAt"] <= P.timestamp(recorded["completed_at"]),
           "Recovery result identity/schema/hash/recording time differs")
    request, descriptor = load_request(api, context, value["request"]["artifact"]["id"], value["request"]["sha256"],
                                       directory, remaining_seconds=F.DELIVERY_HEADROOM)
    P.need(descriptor == value["request"] and request["original"] == value["original"] and
           approval(api, request) == value["ownerApproval"] and value["provider"] == {
               "id": P.number(provider["id"]), "name": "verify-recovery", "startedAt": provider["started_at"], "steps": steps},
           "Recovery no longer binds its original request, owner approval, failed attempt or provider evidence")
    verification = value["verification"]
    P.need(set(verification) == {"deployment", "bundle", "remote", "consumers"} and
           verification["deployment"] == request["deployment"], "Recovery deployment receipt differs")
    signature_receipt(verification["bundle"], request["bundle"])
    validate_command(verification["remote"], request, "remote", steps[1])
    validate_command(verification["consumers"], request, "consumers", steps[2])
    end = min((request["original"]["expiresAt"], descriptor["artifact"]["expires_at"]), key=P.timestamp)
    P.need(value["expiresAt"] == end and time.time() + F.DELIVERY_HEADROOM <
           min(P.timestamp(end), P.timestamp(artifact["expires_at"])), "Original/recovery evidence expired; no renewal by recovery")
    original = request["original"]
    return {**original["qualification"], "frozenApplicationSet": original["frozenApplicationSet"],
            "mavenRecovery": {"invocation": context, "artifact": artifact, "sha256": digest, "request": descriptor,
                "ownerApproval": value["ownerApproval"], "original": original["maven"], "originalConclusion": "failure",
                "originalArtifacts": original["artifacts"], "verification": verification, "provider": value["provider"],
                "completedAt": provider["completed_at"], "expiresAt": end}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "authorize", "verify-originals", "verify-consumers", "finish"))
    for name in ("source", "maven-run", "maven-attempt", "frozen-artifact", "frozen-sha256", "request-artifact", "request-sha256"):
        parser.add_argument("--" + name, default="")
    parser.add_argument("--original-root", type=Path)
    args = parser.parse_args()
    try:
        api = ReadOnlyApi(os.environ.get("GH_TOKEN", ""))
        context = hosted_context(api, os.environ, args.operation)
        parent = Path(os.environ["RUNNER_TEMP"])
        P.PACK.physical_directory(parent)
        source_args = (args.source, args.maven_run, args.maven_attempt, args.frozen_artifact, args.frozen_sha256)
        if args.operation == "prepare":
            P.need(all(source_args) and not args.request_artifact and not args.request_sha256 and args.original_root is None,
                   "Prepare requires only exact original source/Maven/frozen-set bindings")
            with tempfile.TemporaryDirectory(prefix="p2pkit-recovery-prepare-", dir=parent) as temporary:
                request = prepare(api, context, *source_args, Path(temporary))
            output = owned_directory(parent, context, create=True)
            write_record(output, REQUEST, request)
            digest = hashlib.sha256(P.encoded(request)).hexdigest()
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
                stream.write(f"sha256={digest}\noriginal_source={args.source}\n")
            result = {"result": "PREPARED_NOT_VERIFIED_NOT_PUBLISHED", "requestSha256": digest,
                      "ownerApprovalComment": challenge(request), "original": request["original"]["maven"],
                      "expiresAt": request["original"]["expiresAt"]}
        else:
            P.need(not any(source_args) and args.request_artifact and args.request_sha256 and
                   (args.original_root is None) == (args.operation == "authorize"),
                   "Execution requires the retained exact request, never new source/version inputs")
            provider = active_job(api, context)
            deadline = P.timestamp(provider["started_at"]) + JOB_SECONDS - 60
            remaining = F.DELIVERY_HEADROOM if args.operation == "finish" else (
                F.MAVEN_HEADROOM if args.operation == "authorize" else max(0, int(deadline - time.time())) + F.DELIVERY_HEADROOM)
            with tempfile.TemporaryDirectory(prefix="p2pkit-recovery-check-", dir=parent) as temporary:
                work = Path(temporary)
                request, descriptor = load_request(api, context, args.request_artifact, args.request_sha256, work,
                                                   remaining_seconds=remaining)
                authorization = approval(api, request)
                output = owned_directory(parent, context, create=args.operation == "authorize")
                if args.operation == "authorize":
                    write_record(output, "authorization.json", {"request": descriptor, "approval": authorization})
                    result = {"result": "OWNER_RECOVERY_AUTHORIZED_NOT_VERIFIED", "originalSource": request["original"]["maven"]["source"]}
                else:
                    P.need(read_record(output, "authorization.json") == {"request": descriptor, "approval": authorization},
                           "Recovery approval/request changed since entering the protected job")
                    if args.operation == "verify-originals":
                        # The remote verifier receives this bundle pathname.
                        # Keep its inputs outside disposable metadata even when
                        # command retirement is unknown or a later step fails.
                        originals_dir = output / "originals"
                        originals_dir.mkdir(mode=0o700)
                        deployment, inspected, bundle = inspect_originals(api, request["original"], originals_dir, signatures=True)
                        P.need(deployment == request["deployment"], "Original retained deployment differs from approved request")
                        signatures = signature_receipt(inspected, request["bundle"])
                        command_dir = output / "remote-command"
                        command_dir.mkdir(mode=0o700)
                        receipt = run_command(request, args.original_root, "remote", command_dir, deadline, bundle)
                        write_record(output, "verified-originals.json", {"deployment": deployment, "bundle": signatures, "remote": receipt})
                        result = {"result": "ORIGINAL_SIGNATURES_AND_REMOTE_BYTES_VERIFIED_NOT_PUBLISHED"}
                    elif args.operation == "verify-consumers":
                        step(provider, VERIFY_ORIGINALS)
                        originals = read_record(output, "verified-originals.json")
                        signature_receipt(originals["bundle"], request["bundle"])
                        command_dir = output / "consumer-command"
                        command_dir.mkdir(mode=0o700)
                        receipt = run_command(request, args.original_root, "consumers", command_dir, deadline)
                        write_record(output, "verified-consumers.json", receipt)
                        result = {"result": "ORIGINAL_SOURCE_COMPLETE_REMOTE_CONSUMERS_VERIFIED_NOT_PUBLISHED"}
                    else:
                        value = finish(api, request, descriptor, authorization, output, args.original_root)
                        write_record(output, RESULT, value)
                        digest = hashlib.sha256(P.encoded(value)).hexdigest()
                        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
                            stream.write("sha256=" + digest + "\n")
                        result = {"result": "RECORDED_AWAITING_SUCCESSFUL_WORKFLOW_AND_FRESH_SAMPLE_OWNER_APPROVAL",
                                  "resultSha256": digest, "originalMavenConclusion": "failure", "expiresAt": value["expiresAt"]}
        print(result["result"])
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as stream:
                stream.write("### Read-only Maven recovery\n\n```json\n" + P.encoded(result).decode() + "```\n")
        return 0
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        print("HOLD: " + (str(error) if isinstance(error, P.Hold) else type(error).__name__))
        return 1  # Never print backend URLs, command output, environment or credentials.


if __name__ == "__main__":
    sys.exit(main())
