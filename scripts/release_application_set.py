#!/usr/bin/env python3
"""Freeze/revalidate the qualified applications before irreversible Maven upload.

No build, signing, upload, publication, or private-evidence decryption occurs here.
The tag-run record is distinct from its original main-only application/evidence
artifacts. Retaining this public JSON never renews their fourteen-day lifetime.
"""

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sample_release_policy", ROOT / "scripts/publish-sample-release.py")
P = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(P)
ENVIRONMENT = "maven-central"
FILE = "release-application-set.json"
SCOPE = "QUALIFIED_APPLICATION_SET_BEFORE_MAVEN"
# Preserve the existing publisher (90 min) and sample delivery (20 min) bounds.
MAVEN_HEADROOM = (90 + 20) * 60
DELIVERY_HEADROOM = 20 * 60


def set_name(invocation):
    return f"release-application-set-{invocation['id']}-{invocation['attempt']}"


def invocation_fields(value):
    keys = ("id", "attempt", "workflowId", "workflowPath", "source", "tag", "version", "tagObject")
    return {key: value[key] for key in keys}


def protected_environment(api):
    value = api.json("/environments/" + ENVIRONMENT)
    P.need(value.get("name") == ENVIRONMENT and value.get("can_admins_bypass") is False and
           value.get("deployment_branch_policy") == {"protected_branches": False, "custom_branch_policies": True},
           "Maven environment protections changed")
    rules = value.get("protection_rules", [])
    P.need(len(rules) == 2 and sorted(x.get("type", "") for x in rules) == ["branch_policy", "required_reviewers"],
           "Missing/unreviewed Maven environment rules")
    review = next(x for x in rules if x["type"] == "required_reviewers")
    owners = review.get("reviewers", [])
    P.need(review.get("prevent_self_review") is False and len(owners) == 1 and
           owners[0].get("type") == "User" and P.is_owner(owners[0].get("reviewer")),
           "Maven publication requires the sole owner's manual review")
    branches = api.pages("/environments/" + ENVIRONMENT + "/deployment-branch-policies", "branch_policies")
    P.need(len(branches) == 1 and branches[0].get("name") == "v*" and branches[0].get("type") == "tag",
           "Only canonical version tags may enter the Maven environment")
    return {"id": P.number(value["id"]), "name": ENVIRONMENT, "tagPattern": "v*",
            "owner": {"login": P.OWNER_LOGIN, "id": P.OWNER_ID}, "canAdminsBypass": False, "preventSelfReview": False}


def expiry(qualification):
    originals = qualification["artifacts"] + qualification["evidence"]
    P.need(len(originals) == 8 and len({x["id"] for x in originals}) == 8,
           "Require four application and four original encrypted-evidence artifacts")
    return min((x["expires_at"] for x in originals), key=P.timestamp)


def eligibility(document, remaining_seconds):
    P.need(type(remaining_seconds) is int and remaining_seconds >= 0, "Invalid remaining execution bound")
    end = expiry(document["qualification"])
    P.need(document["expiresAt"] == end and time.time() + remaining_seconds < P.timestamp(end),
           "Original application/evidence retention cannot cover the remaining publication window")


def inspect_originals(api, qualification, directory):
    packages, notices = [], None
    for artifact in qualification["artifacts"]:
        path = directory / f"original-{artifact['id']}.zip"
        try:
            api.download(artifact, path)
            selected = P.inspect_bundle(path, artifact, qualification)
            with P.PACK.zip_input(path) as archive:
                manifest_hash = hashlib.sha256(archive.read("manifest.json")).hexdigest()
                current_notices = P.read_notices(archive)
            P.need(notices is None or notices == current_notices, "Producer notices differ across platform bundles")
            notices = current_notices
            packages.append({"artifactId": artifact["id"], "artifactDigest": artifact["digest"],
                             "platform": artifact["platform"], "architecture": artifact["architecture"],
                             "manifestSha256": manifest_hash, "installable": selected})
        finally:
            if path.is_file() and not path.is_symlink():
                path.unlink()  # Only this invocation's exclusively created public download.
    return packages


def freeze(api, invocation, directory):
    P.need(P.maven_invocation(api, invocation["source"], invocation["id"], invocation["attempt"], completed=False) == invocation,
           "Maven preflight invocation changed")
    existing = api.pages(f"/actions/runs/{invocation['id']}/artifacts", "artifacts")
    P.need(not any(x.get("name") == set_name(invocation) for x in existing),
           "This attempt already has a frozen set; never overwrite or replace it")
    qualification = P.admit(api, invocation["source"])
    P.need(qualification["versionBinding"]["canonicalVersion"] == invocation["version"] and
           qualification["tag"] == "samples-" + invocation["tag"], "Tag and application version differ")
    document = {"schema": 1, "scope": SCOPE, "maven": invocation, "qualification": qualification,
                "environment": protected_environment(api), "preparedAt": int(time.time()),
                "expiresAt": expiry(qualification)}
    eligibility(document, MAVEN_HEADROOM)
    document["packages"] = inspect_originals(api, qualification, directory)
    P.need(P.admit(api, invocation["source"], qualification["producer"]["id"], qualification["producer"]["attempt"]) == qualification and
           P.maven_invocation(api, invocation["source"], invocation["id"], invocation["attempt"], completed=False) == invocation and
           protected_environment(api) == document["environment"], "Source/gates/originals changed while freezing applications")
    eligibility(document, MAVEN_HEADROOM)
    return document


def frozen_stage(api, invocation, artifact):
    jobs = api.pages(f"/actions/runs/{invocation['id']}/attempts/{invocation['attempt']}/jobs", "jobs")
    found = [x for x in jobs if x.get("name") == "freeze-applications"]
    P.need(len(found) == 1, "Missing/ambiguous original application-freeze job")
    job = found[0]
    P.need(job.get("run_id") == invocation["id"] and job.get("run_attempt") == invocation["attempt"] and
           job.get("head_sha") == invocation["source"] and job.get("status") == "completed" and
           job.get("conclusion") == "success" and
           P.timestamp(job.get("started_at")) <= P.timestamp(artifact["created_at"]) <=
           P.timestamp(job.get("completed_at")) <= time.time(),
           "Frozen set is not from the completed original freeze job")
    return {"id": P.number(job["id"]), "completedAt": job["completed_at"]}


def validate_document(document, invocation):
    P.need(set(document) == {"schema", "scope", "maven", "qualification", "environment", "preparedAt", "expiresAt", "packages"} and
           type(document["schema"]) is int and document["schema"] == 1 and document["scope"] == SCOPE and
           document["maven"] == invocation_fields(invocation) and type(document["preparedAt"]) is int and
           0 < document["preparedAt"] <= time.time(), "Frozen application-set identity/schema differs")
    qualification = document["qualification"]
    P.need(qualification["source"]["commit"] == invocation["source"] and
           qualification["versionBinding"]["canonicalVersion"] == invocation["version"] and
           qualification["tag"] == "samples-" + invocation["tag"], "Frozen source/version/tag differs")
    packages = document["packages"]
    P.need(type(packages) is list and len(packages) == 4 and
           [x["artifactId"] for x in packages] == [x["id"] for x in qualification["artifacts"]],
           "Frozen package roster differs")
    for package, artifact in zip(packages, qualification["artifacts"]):
        P.need(set(package) == {"artifactId", "artifactDigest", "platform", "architecture", "manifestSha256", "installable"} and
               all(package[key] == artifact[key] for key in ("platform", "architecture")) and
               package["artifactDigest"] == artifact["digest"] and
               re.fullmatch(r"[0-9a-f]{64}", package["manifestSha256"]) and
               type(package["installable"].get("bytes")) is int and 0 < package["installable"]["bytes"] <= P.PACK.MAX_FILE and
               re.fullmatch(r"[0-9a-f]{64}", package["installable"].get("sha256", "")),
               "Invalid frozen installer/manifest identity")


def load(api, invocation, directory, *, artifact_id=None, expected_hash=None, remaining_seconds=DELIVERY_HEADROOM):
    if artifact_id is None:
        P.need(expected_hash is None, "Frozen hash requires an explicit original artifact ID")
        candidates = [x for x in api.pages(f"/actions/runs/{invocation['id']}/artifacts", "artifacts")
                      if x.get("name") == set_name(invocation)]
        P.need(len(candidates) == 1, "Missing/ambiguous original frozen set; never choose a newer set")
        item = candidates[0]
    else:
        P.need(type(expected_hash) is str and re.fullmatch(r"[0-9a-f]{64}", expected_hash), "Missing frozen JSON hash")
        item = api.json(f"/actions/artifacts/{P.number(artifact_id)}")
    artifact = P.artifact_identity(item, invocation["id"], invocation["source"], invocation["tag"])
    P.need(artifact["name"] == set_name(invocation) and artifact["size_in_bytes"] <= 2 * P.JSON_LIMIT,
           "Frozen metadata is not the original bounded tag-run artifact")
    stage = frozen_stage(api, invocation, artifact)
    path = directory / "frozen-application-set.zip"
    try:
        api.download(artifact, path)
        P.need(P.PACK.file_hash(path, 2 * P.JSON_LIMIT) == {"bytes": artifact["size_in_bytes"],
               "sha256": artifact["digest"].removeprefix("sha256:")}, "Frozen artifact digest/size differs")
        with P.PACK.zip_input(path) as archive:
            items = archive.infolist()
            P.need(len(items) == 1 and items[0].filename == FILE and not items[0].is_dir() and
                   not items[0].flag_bits & 1 and stat.S_IFMT(items[0].external_attr >> 16) in (0, stat.S_IFREG) and
                   0 < items[0].file_size <= P.JSON_LIMIT, "Unexpected frozen metadata archive contents")
            raw = archive.read(FILE)
        digest, document = hashlib.sha256(raw).hexdigest(), P.parsed(raw)
        P.need(raw == P.encoded(document) and (expected_hash is None or digest == expected_hash),
               "Frozen JSON canonical encoding/hash differs")
        validate_document(document, invocation)
        P.need(document["preparedAt"] <= P.timestamp(artifact["created_at"]), "Frozen record was not prepared before upload")
        qualification = document["qualification"]
        P.need(P.admit(api, invocation["source"], qualification["producer"]["id"], qualification["producer"]["attempt"]) == qualification,
               "Frozen source/gates/producer/original evidence changed")
        P.need(protected_environment(api) == document["environment"], "Maven protection changed after freeze")
        eligibility(document, remaining_seconds)
        return document, {"artifact": artifact, "sha256": digest, "maven": invocation_fields(invocation),
                          "expiresAt": document["expiresAt"], "freezeJob": stage, "packages": document["packages"]}
    finally:
        if path.is_file() and not path.is_symlink():
            path.unlink()


def approval_line(document):
    invocation = document["maven"]
    return f"APPROVE_APPLICATION_SET {invocation['id']}/{invocation['attempt']} {hashlib.sha256(P.encoded(document)).hexdigest()}"


def require_approval(api, document, descriptor):
    P.need(protected_environment(api) == document["environment"], "Maven environment changed after preparation")
    invocation, artifact = document["maven"], descriptor["artifact"]
    P.need(P.artifact_identity(api.json(f"/actions/artifacts/{artifact['id']}"), invocation["id"], invocation["source"],
                              invocation["tag"]) == artifact and
           hashlib.sha256(P.encoded(document)).hexdigest() == descriptor["sha256"],
           "Original frozen set was changed, replaced or expired")
    reviews = api.json(f"/actions/runs/{invocation['id']}/approvals")
    P.need(type(reviews) is list and len(reviews) <= 1000, "Unexpected Maven approval history")
    line = approval_line(document)
    matches = [x for x in reviews if type(x.get("comment")) is str and x["comment"].strip() == line]
    P.need(len(matches) == 1, "Missing unique owner approval of this exact Maven attempt/application-set hash")
    review = matches[0]
    environments = review.get("environments", [])
    P.need(review.get("state") == "approved" and P.is_owner(review.get("user")) and len(environments) == 1 and
           environments[0].get("name") == ENVIRONMENT and environments[0].get("id") == document["environment"]["id"],
           "Frozen application set lacks the owner's real protected Maven approval")
    return {"scope": "OWNER_APPLICATION_SET_APPROVAL", "run": invocation["id"], "attempt": invocation["attempt"],
            "artifactId": artifact["id"], "artifactDigest": artifact["digest"], "setSha256": descriptor["sha256"],
            "owner": document["environment"]["owner"], "environmentId": document["environment"]["id"], "comment": line}


def publication_plan(api, publication, directory, *, artifact_id=None, expected_hash=None):
    document, descriptor = load(api, publication, directory, artifact_id=artifact_id, expected_hash=expected_hash)
    approval = require_approval(api, document, descriptor)
    return {**document["qualification"], "mavenPublication": publication,
            "frozenApplicationSet": {**descriptor, "ownerApproval": approval}}


def hosted_context(env, operation):
    tag = env.get("GITHUB_REF_NAME", "")
    P.need(env.get("GITHUB_ACTIONS") == "true" and env.get("RUNNER_ENVIRONMENT") == "github-hosted" and
           env.get("GITHUB_REPOSITORY") == P.REPO and env.get("GITHUB_SERVER_URL") == "https://github.com" and
           env.get("GITHUB_API_URL") == P.API and env.get("GITHUB_EVENT_NAME") == "push" and
           re.fullmatch(r"v[0-9][0-9A-Za-z.-]{0,99}", tag) and env.get("GITHUB_REF") == "refs/tags/" + tag and
           env.get("GITHUB_WORKFLOW_REF") == P.REPO + "/" + P.MAVEN_WORKFLOW + "@refs/tags/" + tag and
           P.SHA.fullmatch(env.get("GITHUB_SHA", "")) and env.get("GITHUB_WORKFLOW_SHA") == env["GITHUB_SHA"] and
           env.get("GITHUB_JOB") == ("freeze-applications" if operation == "freeze" else "publish-release"),
           "Frozen-set operation requires the exact genuine Maven tag-run job")
    return {"source": env["GITHUB_SHA"], "id": P.number(env.get("GITHUB_RUN_ID")),
            "attempt": P.number(env.get("GITHUB_RUN_ATTEMPT")), "tag": tag}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("freeze", "revalidate"))
    parser.add_argument("--artifact")
    parser.add_argument("--sha256")
    args = parser.parse_args()
    try:
        context = hosted_context(os.environ, args.operation)
        P.need((args.operation == "freeze" and args.artifact is None and args.sha256 is None) or
               (args.operation == "revalidate" and args.artifact and args.sha256), "Wrong frozen-set argument binding")
        P.need(P.PACK.git(ROOT, "rev-parse", "HEAD").decode("ascii") == context["source"] and
               not P.PACK.git(ROOT, "status", "--porcelain=v1", "--untracked-files=all", "--ignore-submodules=none"),
               "Maven checkout is dirty or not the exact tagged source")
        api = P.Api(os.environ.get("GH_TOKEN", ""))
        invocation = P.maven_invocation(api, context["source"], context["id"], context["attempt"], completed=False)
        P.need(invocation["tag"] == context["tag"], "Hosted tag differs from original Maven invocation")
        parent = Path(os.environ["RUNNER_TEMP"])
        P.PACK.physical_directory(parent)
        if args.operation == "freeze":
            output = parent / "p2pkit-release-application-set"
            output.mkdir(mode=0o700)
            with tempfile.TemporaryDirectory(prefix="p2pkit-app-preflight-", dir=parent) as temporary:
                document = freeze(api, invocation, Path(temporary))
            raw = P.encoded(document)
            P.need(len(raw) <= P.JSON_LIMIT, "Frozen document exceeds its finite bound")
            with (output / FILE).open("xb") as stream:
                stream.write(raw)
            digest = hashlib.sha256(raw).hexdigest()
            with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
                stream.write("sha256=" + digest + "\n")
            result = {"result": "FROZEN_NOT_PUBLISHED", "source": context["source"], "version": invocation["version"],
                      "sha256": digest, "expiresAt": document["expiresAt"], "ownerApprovalComment": approval_line(document)}
        else:
            with tempfile.TemporaryDirectory(prefix="p2pkit-app-revalidate-", dir=parent) as temporary:
                document, descriptor = load(api, invocation, Path(temporary), artifact_id=args.artifact,
                                            expected_hash=args.sha256, remaining_seconds=MAVEN_HEADROOM)
                approval = require_approval(api, document, descriptor)
            result = {"result": "EXACT_APPLICATION_SET_REVALIDATED_NOT_PUBLICATION", "frozenApplicationSet": descriptor,
                      "ownerApproval": approval}
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with open(summary, "a", encoding="utf-8") as stream:
                stream.write("### Pre-Maven application readiness\n\n```json\n" + P.encoded(result).decode() + "```\n")
        print(result["result"])
        return 0
    except (ValueError, KeyError, TypeError, OSError, RuntimeError, subprocess.SubprocessError) as error:
        # Never expose an API body, token, filesystem packet or signed URL.
        print("HOLD: " + (str(error) if isinstance(error, P.Hold) else type(error).__name__))
        return 1


if __name__ == "__main__":
    sys.exit(main())
