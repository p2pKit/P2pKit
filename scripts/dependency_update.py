#!/usr/bin/env python3
"""Generate a review-only dependency patch in a separate exact-source checkout.

Run under ci_evidence.py with the immutable controller as --source-root. The
maintained generator/checksum/provenance commands are unchanged. This adapter
never applies, commits, pushes, submits a graph, or qualifies a release.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SHA = re.compile(r"[0-9a-f]{40}")
LIMIT = 32 * 1024**2
PATCH_LIMIT = 64 * 1024**2
HELPERS = (
    "gradlew", "gradle/wrapper/gradle-wrapper.jar", "gradle/wrapper/gradle-wrapper.properties",
    "scripts/prepare-dependency-update.sh", "scripts/check-gradle-wrapper.sh",
    "scripts/check-dependency-verification.sh", "scripts/review-dependency-verification.sh",
    "scripts/validate-gradle-plugin-marker.sh", "scripts/validate-gradle-plugin-metadata.py",
    "scripts/resolve-gradle-variant-artifact.py", "gradle/plugin-provenance-policy.txt",
)
XML = "gradle/verification-metadata.xml"


class UpdateError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise UpdateError(message)


def git(root, *arguments, limit=PATCH_LIMIT):
    result = subprocess.run(["git", "--no-replace-objects", "-C", str(root), *arguments],
                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=60, check=False)
    need(result.returncode == 0 and len(result.stdout) <= limit, "GIT_METADATA_REFUSED")
    return result.stdout


def read(path):
    info = path.lstat()
    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= LIMIT,
         "SOURCE_FILE_TYPE_OR_SIZE")
    with path.open("rb") as stream:
        raw = stream.read(LIMIT + 1)
    need(len(raw) == info.st_size, "SOURCE_FILE_CHANGED")
    return raw


def snapshot(root):
    rows, total = {}, 0
    for record in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not record:
            continue
        identity, raw_name = record.split(b"\t", 1)
        mode, blob, stage = identity.decode("ascii").split()
        name = raw_name.decode("utf-8")
        need(mode in ("100644", "100755") and stage == "0" and name not in rows and
             not Path(name).is_absolute() and ".." not in Path(name).parts and
             all(c not in name for c in "\r\n\0"), "SOURCE_ROSTER")
        path = root / name
        need(not any(p.is_symlink() for p in (path, *path.parents)), "LINKED_SOURCE")
        raw = read(path)
        total += len(raw)
        need(len(rows) < 20000 and total <= 128 * 1024**2, "SOURCE_ROSTER_LIMIT")
        rows[name] = {"mode": mode, "blob": blob, "bytes": len(raw),
                      "sha256": hashlib.sha256(raw).hexdigest(), "permissions": stat.S_IMODE(path.stat().st_mode)}
    need(rows, "EMPTY_SOURCE")
    return rows


def source(root, commit, tree, *, clean=True):
    need(SHA.fullmatch(commit) and SHA.fullmatch(tree), "SOURCE_IDENTITY")
    need(git(root, "rev-parse", "HEAD").decode().strip() == commit and
         git(root, "rev-parse", "HEAD^{tree}").decode().strip() == tree, "SOURCE_IDENTITY")
    if clean:
        need(not git(root, "status", "--porcelain=v1", "--untracked-files=all"), "SOURCE_DIRTY")


def changes(before, after, staged, untracked):
    need(set(before) == set(after) and not staged and not untracked, "CANDIDATE_ROSTER_CHANGED")
    allowed = {name for name in before if name.endswith("lockfile")} | {XML}
    result = []
    for name, original in before.items():
        current = after[name]
        need(all(original[key] == current[key] for key in ("mode", "blob", "permissions")), "SOURCE_MODE_CHANGED")
        if original["sha256"] != current["sha256"]:
            need(name in allowed, "NON_DEPENDENCY_SOURCE_CHANGED")
            result.append({"path": name, "before": original["sha256"],
                           "after": current["sha256"], "bytes": current["bytes"]})
    return sorted(result, key=lambda row: row["path"])


def verification(raw):
    """Preserve all old hashes and trust flags; the existing checker reviews additions."""
    need(0 < len(raw) <= LIMIT and not re.search(br"<!\s*(DOCTYPE|ENTITY)\b", raw, re.I), "VERIFICATION_XML")
    ns = "{https://schema.gradle.org/dependency-verification}"
    root = ET.fromstring(raw)
    need(root.tag == ns + "verification-metadata" and
         [child.tag for child in root] == [ns + "configuration", ns + "components"], "VERIFICATION_STRUCTURE")
    configuration, components = root
    need(not components.attrib and all(not (element.tail or "").strip() for element in root.iter()) and
         all(not (element.text or "").strip() for element in (root, configuration, components)),
         "VERIFICATION_STRUCTURE")
    need(not configuration.attrib and [child.tag for child in configuration] ==
         [ns + "verify-metadata", ns + "verify-signatures"] and
         all(not child.attrib and len(child) == 0 and child.text == value
             for child, value in zip(configuration, ("true", "false"))), "VERIFICATION_TRUST_CHANGED")
    entries, coordinates_seen = set(), set()
    for component in components:
        need(component.tag == ns + "component" and set(component.attrib) == {"group", "name", "version"},
             "VERIFICATION_COMPONENT")
        need(not (component.text or "").strip(), "VERIFICATION_COMPONENT")
        coordinates = tuple(component.attrib[key] for key in ("group", "name", "version"))
        need(coordinates not in coordinates_seen and len(component) > 0, "DUPLICATE_OR_EMPTY_COMPONENT")
        coordinates_seen.add(coordinates)
        names = set()
        for artifact in component:
            need(artifact.tag == ns + "artifact" and set(artifact.attrib) == {"name"} and len(artifact) == 1,
                 "VERIFICATION_ARTIFACT")
            need(artifact.attrib["name"] not in names, "DUPLICATE_VERIFICATION_ARTIFACT")
            names.add(artifact.attrib["name"])
            need(not (artifact.text or "").strip(), "VERIFICATION_ARTIFACT")
            checksum = artifact[0]
            value = checksum.get("value", "")
            need(checksum.tag == ns + "sha256" and re.fullmatch(r"[0-9a-f]{64}", value) and
                 {"value"} <= set(checksum.attrib) <= {"value", "origin", "reason"} and
                 len(checksum) == 0 and not (checksum.text or "").strip(), "VERIFICATION_CHECKSUM")
            entry = (*coordinates, artifact.attrib["name"], value)
            need(entry not in entries, "DUPLICATE_VERIFICATION_ENTRY")
            entries.add(entry)
    need(entries, "EMPTY_VERIFICATION")
    return root.attrib, entries


def retain_reports(candidate, controller):
    # Reuse the ordinary evidence collector: selected files only, no links,
    # finite count/bytes. They stay private inside the controller's encryption.
    sys.path.insert(0, str(controller / "scripts"))
    import ci_evidence
    parent = controller / "build/reports"
    parent.mkdir(parents=True, exist_ok=True)
    ci_evidence.collect_reports(candidate, ["**/build/test-results/**/*.xml", "build/reports/**/*"],
                                parent / "dependency-update")


def step_exit_diagnostic(step, code):
    # Only a returned original subprocess code, never an initialized fallback.
    # These labels are diagnostic observations, not completion/cleanup authority.
    if step in ("GENERATOR", "GRADLE_STOP") and type(code) is int and -(2**31) <= code < 2**32:
        print("DEPENDENCY_UPDATE_STEP " + step + " EXIT " + str(code))


def execute(controller, candidate, request, output, *, run=subprocess.run, reports=retain_reports):
    controller, candidate, output = (Path(p).absolute() for p in (controller, candidate, output))
    need(all(".." not in p.parts and not any(parent.is_symlink() for parent in (p, *p.parents))
             for p in (controller, candidate, output)), "LINKED_OR_TRAVERSAL_PATH")
    need(controller != candidate and controller not in candidate.parents and candidate not in controller.parents,
         "SEPARATE_CANDIDATE_REQUIRED")
    need(not output.exists() and not output.is_symlink() and
         all(root != output and root not in output.parents for root in (controller, candidate)), "OUTPUT_MUST_BE_FRESH_EXTERNAL")
    need(type(request) is dict and all(type(value) is str and SHA.fullmatch(value) for value in request.values()) and set(request) ==
         {"controller_sha", "controller_tree", "candidate_sha", "candidate_tree", "dependency_base_sha"}, "REQUEST_IDENTITY")
    source(controller, request["controller_sha"], request["controller_tree"])
    source(candidate, request["candidate_sha"], request["candidate_tree"])
    git(candidate, "merge-base", "--is-ancestor", request["dependency_base_sha"], request["candidate_sha"])
    original_controller, before = snapshot(controller), snapshot(candidate)
    for path in HELPERS:
        need(path in before and before[path] == original_controller.get(path), "MAINTAINED_GENERATOR_CHANGED")
    for path, row in before.items():
        if path.endswith("lockfile") or path == XML:
            need(hashlib.sha256(git(candidate, "show", request["dependency_base_sha"] + ":" + path)).hexdigest() ==
                 row["sha256"], "DEPENDENCY_BASE_ALREADY_CHANGED")
    old_xml = read(candidate / XML)
    generator_code, stop_code = 125, 125
    try:
        # Only this real generator invocation opts into the curator's exact-XML
        # no-additions case. The generator still performs its normal writer,
        # verification-policy, strict resolution and plugin-floor checks first.
        generator_code = run([str(candidate / "scripts/prepare-dependency-update.sh"), request["dependency_base_sha"]],
                             cwd=candidate, check=False,
                             env={**os.environ, "P2PKIT_DEPENDENCY_REVIEW_ALLOW_UNCHANGED": "1"}).returncode
        step_exit_diagnostic("GENERATOR", generator_code)
    finally:
        try:
            stop_code = run([str(candidate / "gradlew"), "--stop"], cwd=candidate, check=False, timeout=90).returncode
            step_exit_diagnostic("GRADLE_STOP", stop_code)
        finally:
            reports(candidate, controller)
    need(generator_code == 0 and stop_code == 0, "GENERATION_OR_GRADLE_STOP_FAILED")
    source(controller, request["controller_sha"], request["controller_tree"])
    need(snapshot(controller) == original_controller, "CONTROLLER_CHANGED")
    source(candidate, request["candidate_sha"], request["candidate_tree"], clean=False)
    delta = changes(before, snapshot(candidate), git(candidate, "diff", "--cached", "--binary"),
                    git(candidate, "ls-files", "--others", "--exclude-standard", "-z"))
    old_policy, old_entries = verification(old_xml)
    new_xml = read(candidate / XML)
    new_policy, new_entries = verification(new_xml)
    need(old_policy == new_policy and old_entries <= new_entries, "VERIFICATION_HISTORY_REMOVED")
    need(old_entries != new_entries or old_xml == new_xml, "UNCHANGED_VERIFICATION_BYTES_DIFFER")
    git(candidate, "diff", "--check")
    patch = git(candidate, "diff", "--binary", "--no-ext-diff", "--no-textconv", "--no-renames", "HEAD")
    need(len(patch) <= PATCH_LIMIT and bool(patch) == bool(delta), "PATCH_LIMIT_OR_DELTA_MISMATCH")
    outcome = "UPDATED_VERIFICATION" if new_entries != old_entries else "LOCK_ONLY" if delta else "UNCHANGED"
    document = {"schema": 1, "scope": "DEPENDENCY_UPDATE_CANDIDATE_NOT_QUALIFICATION", "request": request,
                "outcome": outcome,
                "generatorExitCode": generator_code, "gradleStopExitCode": stop_code,
                "changes": delta, "addedVerifiedArtifacts": len(new_entries - old_entries),
                "patch": {"sha256": hashlib.sha256(patch).hexdigest(), "bytes": len(patch)},
                "requiresReviewBeforeApply": True, "releaseQualified": False}
    output.mkdir(mode=0o700)
    (output / "generated-dependencies.patch").write_bytes(patch)
    (output / "generated-dependencies.json").write_text(json.dumps(document, sort_keys=True, indent=2) + "\n")
    return document


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        request = json.loads(os.environ["DEPENDENCY_UPDATE_REQUEST"])
        need(type(request) is dict, "REQUEST_IDENTITY")
        need(os.environ.get("GITHUB_ACTIONS") == "true" and os.environ.get("RUNNER_ENVIRONMENT") == "github-hosted" and
             os.environ.get("GITHUB_REPOSITORY") == "p2pKit/P2pKit" and
             os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and os.environ.get("GITHUB_JOB") == "generate" and
             os.environ.get("GITHUB_SHA") == os.environ.get("GITHUB_WORKFLOW_SHA") == request["controller_sha"],
             "HOSTED_CONTROLLER_IDENTITY")
        execute(ROOT, args.candidate, request, args.output)
        print("DEPENDENCY_CANDIDATE_REQUIRES_REVIEW_NOT_RELEASE_QUALIFICATION")
        return 0
    except (UpdateError, ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
        print("DEPENDENCY_UPDATE_FAILED: " + (str(error) if type(error) is UpdateError else type(error).__name__))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
