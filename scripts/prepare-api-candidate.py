#!/usr/bin/env python3
"""Generate a review-only core API patch in a fresh detached exact-source worktree.

Run only through the reviewed hosted workflow and ci_evidence.py. No dependency
writer, arbitrary Gradle task, baseline application, commit or publication is
offered. Generation is not API compatibility or release qualification.
"""
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ".github/workflows/prepare-api-candidate.yml"
API_FILES = (
    "library/p2p-core/api/p2p-core.klib.api",
    "library/p2p-core/api/jvm/p2p-core.api",
    "library/p2p-core/api/android/p2p-core.api",
    "library/p2p-core/api/android-bcv/p2p-core.api",
)
TASKS = (":p2p-core:updateKotlinAbi", ":p2p-core:updateAndroidAbi")
GRADLE_OPTIONS = ("--no-daemon", "--console=plain", "--no-build-cache",
                  "--no-configuration-cache", "--dependency-verification", "strict",
                  "--max-workers=2", "--no-parallel")
MAX_API_BYTES = 2 * 1024 * 1024
MAX_PATCH_BYTES = 4 * 1024 * 1024


class CandidateError(ValueError):
    pass


def require(condition, reason):
    if not condition:
        raise CandidateError(reason)


def git(root, *arguments):
    result = subprocess.run(["git", "--no-replace-objects", "-c", "core.hooksPath=/dev/null",
                             "-c", "core.fsmonitor=false", "-C", str(root), *arguments],
                            stdin=subprocess.DEVNULL, capture_output=True, timeout=60, check=False)
    require(result.returncode == 0 and len(result.stdout) <= 4 * 1024 * 1024, "GIT_FAILED")
    return result.stdout


def source(root, sha, *, clean=True):
    require(re.fullmatch(r"[0-9a-f]{40}", sha) is not None, "SOURCE_SHA")
    require(git(root, "rev-parse", "HEAD").decode().strip() == sha, "SOURCE_SHA")
    tree = git(root, "rev-parse", "HEAD^{tree}").decode().strip()
    require(re.fullmatch(r"[0-9a-f]{40}", tree) is not None, "SOURCE_TREE")
    require(not git(root, "diff", "--cached", "--name-only", "-z", "HEAD"), "STAGED_CHANGE")
    require(not git(root, "ls-files", "--others", "--exclude-standard", "-z"), "UNTRACKED_SOURCE")
    if clean:
        require(not git(root, "status", "--porcelain=v1", "--untracked-files=all"), "SOURCE_DIRTY")
    return {"commit": sha, "tree": tree}


def regular_file(root, name, limit):
    path = root / name
    require(not any(root.joinpath(*Path(name).parts[:i]).is_symlink()
                    for i in range(1, len(Path(name).parts) + 1)), "LINKED_SOURCE")
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_size <= limit, "SOURCE_FILE")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    require(len(raw) == info.st_size, "SOURCE_FILE_CHANGED")
    return raw, stat.S_IMODE(info.st_mode)


def snapshot(root):
    """Check real tracked bytes too; Git's assume-unchanged flags cannot hide writes."""
    result, total = {}, 0
    for row in git(root, "ls-files", "--stage", "-z").split(b"\0"):
        if not row:
            continue
        identity, name = row.split(b"\t", 1)
        mode, blob, stage = identity.decode("ascii").split()
        name = name.decode("utf-8")
        require(mode in ("100644", "100755") and stage == "0" and name not in result and
                not Path(name).is_absolute() and ".." not in Path(name).parts, "SOURCE_ROSTER")
        raw, permissions = regular_file(root, name, 64 * 1024 * 1024)
        require(bool(permissions & stat.S_IXUSR) == (mode == "100755"), "SOURCE_MODE_OR_INDEX_CHANGED")
        total += len(raw)
        require(len(result) < 20000 and total <= 256 * 1024 * 1024, "SOURCE_LIMIT")
        result[name] = (mode, blob, permissions, hashlib.sha256(raw).hexdigest())
    require(result and set(API_FILES) <= result.keys(), "MISSING_BASELINE")
    return result


def api_bytes(root):
    """Bounded dump-shape checks, not a replacement for the ABI compatibility tasks."""
    result = {}
    for name in API_FILES:
        raw, _ = regular_file(root, name, MAX_API_BYTES)
        text = raw.decode("utf-8")
        require(raw and raw.endswith(b"\n") and not re.search(r"[\x00-\x08\x0b-\x1f\x7f]", text), "INVALID_API")
        code = "\n".join(line.partition("//")[0].rstrip() for line in text.splitlines())
        depth = 0
        for line in code.splitlines():
            depth += line.count("{") - line.count("}")
            require(depth >= 0, "INVALID_API_BLOCKS")
        require(depth == 0, "INVALID_API_BLOCKS")
        if name.endswith(".klib.api"):
            require(text.startswith("// Klib ABI Dump\n") and
                    "// Targets: [iosArm64, iosSimulatorArm64, iosX64]\n" in text and
                    re.search(r"^[^\n]*\b(class|interface|object) dev\.p2pkit\.core/[^\n]+ \{$", code, re.M),
                    "INVALID_NATIVE_API")
        else:
            require(re.search(r"^public [^\n]*\b(class|interface) dev/p2pkit/core/[^\n]+ \{$", code, re.M),
                    "INVALID_JVM_API")
        result[name] = raw
    return result


def review_patch(before, after):
    parts = []
    for name in API_FILES:
        parts.extend(difflib.unified_diff(before[name].decode().splitlines(keepends=True),
                                         after[name].decode().splitlines(keepends=True),
                                         fromfile="a/" + name, tofile="b/" + name, n=3))
    patch = "".join(parts).encode("utf-8")
    require(len(patch) <= MAX_PATCH_BYTES, "PATCH_LIMIT")
    return patch


def execute(root, sha, output, temporary, *, run=subprocess.run):
    root, temporary = root.resolve(strict=True), temporary.resolve(strict=True)
    output = output.absolute()
    require(output.parent.resolve(strict=True) == temporary and root != temporary and
            root not in temporary.parents and not output.exists() and not output.is_symlink(), "OUTPUT_PATH")
    identity = source(root, sha)
    controller = snapshot(root)
    state = Path(tempfile.mkdtemp(prefix="core-api-worktree-", dir=temporary))
    candidate = state / "source"
    git(root, "worktree", "add", "--detach", str(candidate), sha)
    try:
        require(source(candidate, sha) == identity, "WORKTREE_SOURCE")
        before = snapshot(candidate)
        # Checkout permissions may reflect a different umask. Git modes and real
        # bytes must match; each worktree's full permissions stay fixed thereafter.
        require(before.keys() == controller.keys() and all(
            value[:2] == controller[name][:2] and value[3] == controller[name][3]
            for name, value in before.items()), "WORKTREE_SOURCE")
        old_api = api_bytes(candidate)
        for check in ("check-gradle-wrapper.sh", "check-dependency-verification.sh"):
            require(run(["bash", str(candidate / "scripts" / check)], cwd=candidate,
                        stdin=subprocess.DEVNULL, check=False).returncode == 0, "PREREQUISITE_FAILED")
        try:
            generated = run([str(candidate / "gradlew"), *GRADLE_OPTIONS, *TASKS],
                            cwd=candidate, stdin=subprocess.DEVNULL, check=False).returncode
        finally:
            stopped = run([str(candidate / "gradlew"), "--stop"], cwd=candidate,
                          stdin=subprocess.DEVNULL, timeout=90, check=False).returncode
        require(generated == 0 and stopped == 0, "GENERATION_OR_STOP_FAILED")
        require(source(candidate, sha, clean=False) == identity, "WORKTREE_SOURCE")
        after = snapshot(candidate)
        require(before.keys() == after.keys(), "SOURCE_ROSTER_CHANGED")
        for name, original in before.items():
            require(original[:3] == after[name][:3], "SOURCE_MODE_OR_INDEX_CHANGED")
            require(original[3] == after[name][3] or name in API_FILES, "NON_API_SOURCE_CHANGED")
        new_api = api_bytes(candidate)
        patch = review_patch(old_api, new_api)
    finally:
        # This exact directory was created by this invocation, never a caller's worktree.
        git(root, "worktree", "remove", "--force", str(candidate))
        state.rmdir()
    require(source(root, sha) == identity and snapshot(root) == controller, "CONTROLLER_CHANGED")
    changes = [name for name in API_FILES if old_api[name] != new_api[name]]
    manifest = {
        "schema": 1, "scope": "CORE_API_CANDIDATE_REVIEW_ONLY", "source": identity,
        "workflow": {"path": WORKFLOW, "commit": sha}, "tasks": list(TASKS),
        "dependencyVerification": "strict", "dependencyWritesAllowed": False,
        "requiresReviewBeforeApply": True, "releaseQualified": False,
        "outcome": "CHANGED" if changes else "UNCHANGED", "changedFiles": changes,
        "files": [{"path": name, "beforeSha256": hashlib.sha256(old_api[name]).hexdigest(),
                   "afterSha256": hashlib.sha256(new_api[name]).hexdigest(),
                   "beforeBytes": len(old_api[name]), "afterBytes": len(new_api[name])}
                  for name in API_FILES],
        "patch": {"path": "core-api-candidate.patch", "bytes": len(patch),
                  "sha256": hashlib.sha256(patch).hexdigest()},
    }
    raw_manifest = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    output.mkdir(mode=0o700)
    for name, raw in (("core-api-candidate.patch", patch), ("core-api-candidate.json", raw_manifest)):
        with (output / name).open("xb") as stream:
            stream.write(raw)
    # Captured by ci_evidence: bind the separate review artifact to the encrypted original log.
    print("API_CANDIDATE REVIEW_ONLY manifest-sha256=" + hashlib.sha256(raw_manifest).hexdigest())
    return manifest


def validate_request(sha, environment):
    require(re.fullmatch(r"[0-9a-f]{40}", sha) is not None and
            sha == environment.get("GITHUB_SHA") == environment.get("GITHUB_WORKFLOW_SHA"), "REQUEST_SHA")
    require(environment.get("GITHUB_REPOSITORY") == "p2pKit/P2pKit" and
            environment.get("GITHUB_ACTIONS") == "true" and environment.get("GITHUB_JOB") == "generate" and
            environment.get("GITHUB_EVENT_NAME") == "workflow_dispatch" and
            re.fullmatch(re.escape("p2pKit/P2pKit/" + WORKFLOW) + r"@refs/[^\r\n]{1,255}",
                         environment.get("GITHUB_WORKFLOW_REF", "")) is not None and
            environment.get("RUNNER_ENVIRONMENT") == "github-hosted" and
            environment.get("RUNNER_OS") == "macOS" and environment.get("RUNNER_ARCH") == "X64", "HOSTED_REQUEST")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        validate_request(args.source_sha, os.environ)
        execute(ROOT, args.source_sha, args.output, Path(os.environ["RUNNER_TEMP"]))
    except (CandidateError, OSError, UnicodeError, subprocess.SubprocessError, KeyError) as error:
        code = str(error) if type(error) is CandidateError else type(error).__name__
        print("API_CANDIDATE FAIL " + code, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
