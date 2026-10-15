"""Private setup-gradle witnesses and an inactive owned-home transition.

Captures bind observations, not authenticated Git/Actions source or execution
authority. Workflow wiring must place before/after immediately around the exact
pinned setup action and supply its actual outcome/conclusion. Clean source,
authenticated metadata, tool provenance and the complete watchdog remain caller
obligations. No Java/Git command, cache change or global environment mutation.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

if __name__ == "__main__":
    # The workflow deliberately uses -I -B -S, without ambient import paths/site.
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from rpc_apple_ci_admission import BINDING_KEYS, SCOPE as ADMISSION_SCOPE, absolute_path, require
from rpc_apple_ci_environment import admit_environment, scalar


SCOPE = "ORDINARY_CI_SETUP_WITNESS_NOT_EXECUTION_OR_RELEASE_AUTHORITY"
ACTION = "gradle/actions/setup-gradle@9c971963bec38e04b3d30dcc455b5382be2fdbfb"
STEP = "ci-gradle-setup"
PROFILES = {"platform-checks": "platform-full", "artifact-checks": "consumers-complete"}
STATE_SELECTOR = "P2PKIT_AUDIT_STATE_DIR"
MARKER = "GRADLE_BUILD_ACTION_SETUP_COMPLETED"
OUTCOME = "P2PKIT_CI_SETUP_OUTCOME"
CONCLUSION = "P2PKIT_CI_SETUP_CONCLUSION"
IDENTITY_KEYS = (
    "GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT",
    "GITHUB_JOB", "GITHUB_REF", "GITHUB_EVENT_NAME", "GITHUB_WORKFLOW_REF", "GITHUB_WORKFLOW_SHA",
    "GITHUB_WORKSPACE", "RUNNER_TEMP", "RUNNER_ENVIRONMENT", "RUNNER_OS", "RUNNER_ARCH",
    "HOME", "USER", "LOGNAME", "JAVA_HOME", "P2PKIT_AUDIT_JDK21", "RUNNER_TRACKING_ID",
)
PRE_KEYS = {"schema", "scope", "phase", "action", "step", "binding", "workflowSha256"}
POST_KEYS = PRE_KEYS | {"beforeSha256", "outcome", "conclusion", "setupCompleted", "oldGradleHome"}
MAX_RECORD = 65536


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _absolute(value: object) -> Path:
    require(scalar(value), "Missing absolute path")
    return Path(absolute_path(value[:-1] if value.endswith("/") else value, "setup path"))


def _directory(value: object) -> Path:
    path = _absolute(value).resolve(strict=True)
    require(path.is_dir(), "Physical directory required")
    return path


def _owned_directory(value: object) -> Path:
    path = _absolute(value)
    require(path.resolve(strict=True) == path and path.is_dir(), "Owned audit directory must not contain aliases")
    return path


def _overlaps(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _binding(ambient: dict) -> dict:
    require(type(ambient) is dict and len(ambient) <= 2048 and all(
        type(key) is str and key and "=" not in key and "\0" not in key and
        type(value) is str and "\0" not in value for key, value in ambient.items()), "Invalid environment mapping")
    require("DYLD_INSERT_LIBRARIES" not in ambient, "Wrapper-affecting environment presence refused")
    require(not any(key.startswith("P2PKIT_AUDIT_") and key != "P2PKIT_AUDIT_JDK21" for key in ambient),
            "Inherited audit state refused, including empty selectors")
    require(all(scalar(ambient.get(key)) for key in IDENTITY_KEYS), "Incomplete setup binding")
    value = {key: ambient[key] for key in IDENTITY_KEYS}
    require(value["GITHUB_ACTIONS"] == "true" and value["GITHUB_REPOSITORY"] == "p2pKit/P2pKit" and
            value["RUNNER_ENVIRONMENT"] == "github-hosted" and value["RUNNER_OS"] == "macOS" and
            value["RUNNER_ARCH"] in ("ARM64", "X64") and value["GITHUB_JOB"] in PROFILES,
            "Wrong complete Apple CI job")
    for key in ("GITHUB_SHA", "GITHUB_WORKFLOW_SHA"):
        require(re.fullmatch(r"[0-9a-f]{40}", value[key]) is not None and set(value[key]) != {"0"}, "Invalid source label")
    for key, maximum in (("GITHUB_RUN_ID", 2**63), ("GITHUB_RUN_ATTEMPT", 2**31)):
        require(re.fullmatch(r"[1-9][0-9]{0,18}", value[key]) is not None and int(value[key]) < maximum,
                "Invalid run or attempt label")
    require(value["GITHUB_WORKFLOW_REF"] == "p2pKit/P2pKit/.github/workflows/ci.yml@" + value["GITHUB_REF"],
            "Wrong workflow label")
    require(re.fullmatch(r"[A-Za-z0-9_.-]{1,512}", value["RUNNER_TRACKING_ID"]) is not None,
            "Invalid tracking observation")
    for key in ("GITHUB_WORKSPACE", "RUNNER_TEMP", "HOME", "JAVA_HOME", "P2PKIT_AUDIT_JDK21"):
        _absolute(value[key])
    return value


def witness_directory(binding: dict) -> Path:
    """Deterministic private location; existence never grants overwrite/retry."""
    temporary = _directory(binding["RUNNER_TEMP"])
    root = _directory(binding["GITHUB_WORKSPACE"])
    require(not _overlaps(temporary, root), "Witness parent must be outside source")
    name = "p2pkit-ci-setup-" + "-".join(binding[key] for key in (
        "GITHUB_SHA", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT", "GITHUB_JOB"))
    return temporary / name


def _private_directory(directory: Path) -> None:
    info = directory.lstat()
    require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.getuid() and stat.S_IMODE(info.st_mode) == 0o700,
            "Wrong private witness directory")


def _read(path: Path, maximum: int, *, private: bool = False) -> bytes:
    require(path.resolve(strict=True) == path, "Symlinked input refused")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and 0 < before.st_size <= maximum, "Unbounded input file")
        if private:
            require(before.st_uid == os.getuid() and before.st_nlink == 1 and stat.S_IMODE(before.st_mode) == 0o600,
                    "Wrong private witness file")
        raw = stream.read(maximum + 1)
        after = os.fstat(stream.fileno())
        require(len(raw) == before.st_size and len(raw) <= maximum and
                (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), "Input changed while read")
        return raw


def _workflow_digest(binding: dict) -> str:
    return _hash(_read(_directory(binding["GITHUB_WORKSPACE"]) / ".github/workflows/ci.yml", 1024 * 1024))


def _write(directory: Path, name: str, record: dict) -> None:
    _private_directory(directory)
    raw = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    require(len(raw) <= MAX_RECORD, "Oversized witness")
    fd = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, "wb") as stream:
        require(stat.S_IMODE(os.fstat(stream.fileno()).st_mode) == 0o600, "Wrong new witness mode")
        require(stream.write(raw) == len(raw), "Incomplete witness write")
        stream.flush()
        os.fsync(stream.fileno())


def _pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "Duplicate witness key")
        result[key] = value
    return result


def _load(directory: Path, name: str, phase: str) -> tuple[dict, str]:
    _private_directory(directory)
    raw = _read(directory / name, MAX_RECORD, private=True)
    try:
        record = json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("Invalid witness encoding") from None
    require(type(record) is dict and set(record) == (PRE_KEYS if phase == "BEFORE" else POST_KEYS) and
            type(record["schema"]) is int and record["schema"] == 1 and record["scope"] == SCOPE and
            record["phase"] == phase and record["action"] == ACTION and record["step"] == STEP and
            type(record["binding"]) is dict and set(record["binding"]) == set(IDENTITY_KEYS), "Wrong closed witness")
    return record, _hash(raw)


def before(ambient: dict) -> dict:
    """Capture only; source cleanliness and metadata authenticity are not claimed."""
    binding = _binding(ambient)
    require(all(key not in ambient for key in ("GRADLE_USER_HOME", MARKER, OUTCOME, CONCLUSION)),
            "Setup must begin without inherited home, completion or outcome")
    record = {"schema": 1, "scope": SCOPE, "phase": "BEFORE", "action": ACTION, "step": STEP,
              "binding": binding, "workflowSha256": _workflow_digest(binding)}
    directory = witness_directory(binding)
    directory.mkdir(mode=0o700)  # mkdir is exclusive: never reuse an earlier witness directory.
    _write(directory, "before.json", record)
    return record


def after(ambient: dict) -> dict:
    binding = _binding(ambient)
    require(ambient.get(OUTCOME) == "success" and ambient.get(CONCLUSION) == "success" and
            ambient.get(MARKER) == "true", "Actual setup outcome, conclusion and marker must succeed")
    _absolute(ambient.get("GRADLE_USER_HOME"))  # Actual action export; never derive HOME/.gradle.
    directory = witness_directory(binding)
    pre, pre_hash = _load(directory, "before.json", "BEFORE")
    require(pre["binding"] == binding and pre["workflowSha256"] == _workflow_digest(binding),
            "Setup identity or workflow changed")
    record = {**pre, "phase": "AFTER", "beforeSha256": pre_hash, "outcome": "success", "conclusion": "success",
              "setupCompleted": "true", "oldGradleHome": ambient["GRADLE_USER_HOME"]}
    _write(directory, "after.json", record)
    return record


def transition_environment(ambient: dict, *, admitted_context: dict, state: str,
                           context_at, expected_tracking_id: str) -> dict:
    """Future runtime only: project an explicit old-home -> real context transition.

    The caller must pass the actual canonical context_at callable and the actual
    authenticated admit_context result. Dependency injection and labels cannot
    establish their provenance here. No bare context dictionary substitutes for
    calling the validator. Its policy digest is checked again; JDK paths are
    cross-bound without executing Java or claiming runtime-version qualification.
    Current PATH may include later approved XcodeGen/SDK tools: the existing
    environment guard admits it independently, not by equality with pre-setup.
    One private exclusive transition record consumes the witness before returning
    an environment. Failed/uncertain writes remain refusals, never deleted/retried.
    """
    binding = _binding(ambient)
    directory = witness_directory(binding)
    pre, pre_hash = _load(directory, "before.json", "BEFORE")
    post, post_hash = _load(directory, "after.json", "AFTER")
    require(pre["binding"] == post["binding"] == binding and post["beforeSha256"] == pre_hash and
            pre["workflowSha256"] == post["workflowSha256"] == _workflow_digest(binding) and
            post["outcome"] == post["conclusion"] == "success" and post["setupCompleted"] == "true" and
            ambient.get(MARKER) == "true" and ambient.get("GRADLE_USER_HOME") == post["oldGradleHome"],
            "Exact successful old-home witness required")
    require(type(admitted_context) is dict and set(admitted_context) == BINDING_KEYS and
            admitted_context["scope"] == ADMISSION_SCOPE and type(admitted_context["schema"]) is int and
            admitted_context["schema"] == 1, "Actual admitted CI context required")
    source = admitted_context["source"]
    require(type(source) is dict and set(source) == {"commit", "tree"} and
            all(type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value) is not None for value in source.values()),
            "Exact admitted source required")
    root = _directory(binding["GITHUB_WORKSPACE"])
    profile = PROFILES[binding["GITHUB_JOB"]]
    require(source["commit"] == binding["GITHUB_SHA"] and admitted_context["root"] == str(root) and
            admitted_context["profile"] == profile and admitted_context["repository"] == binding["GITHUB_REPOSITORY"] and
            admitted_context["event"] == binding["GITHUB_EVENT_NAME"] and admitted_context["ref"] == binding["GITHUB_REF"] and
            type(admitted_context["runId"]) is int and admitted_context["runId"] == int(binding["GITHUB_RUN_ID"]) and
            type(admitted_context["runAttempt"]) is int and admitted_context["runAttempt"] == int(binding["GITHUB_RUN_ATTEMPT"]),
            "Admitted CI and setup witness differ")
    require(type(admitted_context["ciScope"]) is dict and set(admitted_context["ciScope"]) == {"full", "head"} and
            admitted_context["ciScope"]["full"] is True and admitted_context["ciScope"]["head"] == source["commit"],
            "Same-source full scope required")
    require(callable(context_at), "Canonical context validator required")
    selected = _owned_directory(state)  # Do not hide a raw selector alias from the canonical validator.
    validated_state, context = context_at(str(selected))
    require(type(context) is dict and Path(validated_state) == selected and context.get("root") == str(root),
            "Canonical context selector differs")
    fresh = _owned_directory(context.get("gradleHome"))
    old = _absolute(post["oldGradleHome"]).resolve(strict=False)
    require(fresh == selected / "gradle-home" and not any(_overlaps(left, right) for left, right in (
        (selected, root), (selected, old), (fresh, root), (fresh, old))), "Fresh home/state overlaps old home or source")
    require(context.get("source") == {**source, "status": "", "diffSha256": _hash(b"")} and
            context.get("expectedCommit") == source["commit"] and context.get("tree") == source["tree"],
            "Canonical context source differs")
    homes = [str(_directory(binding[key])) for key in ("JAVA_HOME", "P2PKIT_AUDIT_JDK21")]
    require(homes[0] != homes[1] and context.get("javaHomes") == homes, "Canonical JDK17/JDK21 path binding differs")
    require(context.get("gradlePropertiesSha256") == _hash(_read(fresh / "gradle.properties", MAX_RECORD)),
            "Canonical Gradle policy binding differs")
    require(type(context.get("id")) is str and re.fullmatch(r"[0-9a-f]{32}", context["id"]) is not None and
            set(context["id"]) != {"0"}, "Canonical context identity required")
    copied = dict(ambient)
    del copied["GRADLE_USER_HOME"]  # Only after validating the exact old witness and canonical fresh context.
    projected = admit_environment(profile, copied, expected_tracking_id=expected_tracking_id)
    environment = projected["environment"]
    environment.update({"GRADLE_USER_HOME": str(fresh), STATE_SELECTOR: str(selected)})
    _write(directory, "transition.json", {"schema": 1, "scope": SCOPE, "phase": "TRANSITION",
        "beforeSha256": pre_hash, "afterSha256": post_hash, "contextId": context["id"], "state": str(selected),
        "gradleHome": str(fresh), "source": source, "gradlePropertiesSha256": context["gradlePropertiesSha256"]})
    return {"scope": SCOPE, "profile": profile, "environment": environment, "oldHomeWitnessSha256": post_hash,
            "nativeExecutionAuthorized": False, "cleanupVerified": False}


def main(argv=None, ambient=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    ambient = dict(os.environ) if ambient is None else ambient
    try:
        require(argv in (["before"], ["after"]), "Fixed witness phase required")
        (before if argv == ["before"] else after)(ambient)
    except Exception:
        print("FAIL: setup witness refused; no execution authority", file=sys.stderr)
        return 125
    print("PASS: setup witness recorded; NOT_EXECUTION_OR_RELEASE_AUTHORITY")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
