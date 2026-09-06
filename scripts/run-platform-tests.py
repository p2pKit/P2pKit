#!/usr/bin/python3
"""Run fresh platform tests and reject missing execution, not just missing XML."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time
import uuid


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "gradle/platform-test-policy.json"
PROFILES = {
    "full": ["check"],
    "ios-x64": [":p2p-core:iosX64Test", ":p2p-transport-lan:iosX64Test"],
}
FLAGS = ["--no-daemon", "--no-build-cache", "--no-configuration-cache", "--rerun-tasks",
         "--dependency-verification", "strict", "--max-workers=2", "--no-parallel", "--console=plain"]
TERMINATION_GRACE_SECONDS = 15
TERMINATION_KILL_SECONDS = 5


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate coverage JSON key")
        result[key] = value
    return result


def read_json(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(1024 * 1024 + 1)
    require(0 < len(raw) <= 1024 * 1024, "Coverage JSON must contain 1..1MiB bytes")
    def nonfinite(value):
        raise ValueError("Non-finite coverage JSON number")

    return json.loads(raw, object_pairs_hook=unique_object, parse_constant=nonfinite)


def architecture(value):
    return {"arm64": "arm64", "aarch64": "arm64", "x86_64": "x64", "amd64": "x64"}.get(
        value.lower() if isinstance(value, str) else "")


def validate_policy(policy):
    require(isinstance(policy, dict) and type(policy.get("schema")) is int and policy["schema"] == 1,
            "Wrong committed platform-test policy schema")
    model = policy.get("model")
    require(isinstance(model, dict) and model, "Missing committed platform-test model")
    for project, entry in model.items():
        require(isinstance(project, str) and project.startswith(":"), "Invalid model project")
        require(isinstance(entry, dict) and set(entry) == {"targets", "tests"}, "Invalid model entry")
        require(isinstance(entry["targets"], dict) and
                all(isinstance(name, str) and isinstance(kind, str) for name, kind in entry["targets"].items()),
                "Invalid target model")
        tests = entry["tests"]
        require(isinstance(tests, list) and all(isinstance(task, str) and task.startswith(project + ":")
                                             for task in tests) and len(tests) == len(set(tests)),
                "Invalid or duplicate task model")


def required_tasks(policy, profile, arch):
    validate_policy(policy)
    tasks = {task for project in policy["model"].values() for task in project["tests"]}
    if profile == "ios-x64":
        require(arch == "x64", "ios-x64 requires an Intel macOS host, not Apple Silicon")
        required = set(PROFILES[profile])
        require(required <= tasks, "Intel test targets are missing from the committed model")
        return required
    require(profile == "full" and arch in ("arm64", "x64"), "Unsupported platform-test profile/host")
    unavailable = "iosX64Test" if arch == "arm64" else "iosSimulatorArm64Test"
    return {task for task in tasks if not task.endswith(":" + unavailable)}


def assess(report, policy, profile, arch, token):
    required = required_tasks(policy, profile, arch)
    require(isinstance(report, dict) and type(report.get("schema")) is int and report["schema"] == 1,
            "Wrong coverage report schema")
    require(report.get("token") == token, "Stale or unrelated test-execution report")
    require(report.get("dryRun") is False, "A dry-run is not test execution")
    require(report.get("buildFailed") is False, "Gradle build failed; coverage cannot pass")
    host = report.get("host", {})
    require(isinstance(host, dict) and host.get("os") in ("Mac OS X", "Darwin") and
            architecture(host.get("arch")) == arch,
            "Gradle and requested macOS host architecture differ")
    require(report.get("model") == policy["model"],
            "Configured project/target/test-task model differs from gradle/platform-test-policy.json")
    tasks = {task for project in policy["model"].values() for task in project["tests"]}
    actual = report.get("tests")
    require(isinstance(actual, dict) and set(actual) == tasks, "Missing, extra or unclassified test-task record")
    for name, result in actual.items():
        require(isinstance(result, dict), f"Invalid task record: {name}")
        require(type(result.get("enabled")) is bool and type(result.get("inGraph")) is bool,
                f"Invalid task state: {name}")
        require(result.get("outcome") in ("EXECUTED", "FAILED", "NO_SOURCE", "SKIPPED", "UP-TO-DATE",
                                          "FROM-CACHE", "NOT_COMPLETED", "NOT_REQUESTED"),
                f"Unrecognized task outcome: {name}")
        for count in ("passed", "failed", "skipped"):
            value = result.get(count)
            require(type(value) is int and value >= 0, f"Invalid {count} count: {name}")
        require(result["failed"] == 0 and result["outcome"] != "FAILED", f"Failed test task: {name}")
        if name in required:
            require(result.get("outcome") == "EXECUTED" and result.get("enabled") is True and
                    result.get("inGraph") is True and result["passed"] > 0 and result["failed"] == 0,
                    f"Expected fresh nonzero successful test execution missing: {name} ({result})")
    return required


def target_rows(report):
    """Describe each target without equating Android host tests with ART."""
    rows = []
    for project, model in sorted(report.get("model", {}).items()):
        for target, kind in sorted(model["targets"].items()):
            if kind == "common":
                rows.append({"target": f"{project}/{target}", "status": "COMPILATION_ONLY",
                             "reason": "Metadata is not a runtime test target"})
                continue
            if target == "iosArm64":
                rows.append({"target": f"{project}/{target}", "status": "NOT_CONFIGURED",
                             "reason": "No iOS physical-device test runner; hosted simulators are not devices"})
                continue
            suffixes = {"android": ("testAndroidHostTest", "testDebugUnitTest"),
                        "jvm": ("jvmTest", "test")}.get(target, (target + "Test",))
            matching = [name for name in model["tests"] if name.rsplit(":", 1)[1] in suffixes]
            if not matching:
                rows.append({"target": f"{project}/{target}", "status": "NO_TEST_TASK",
                             "reason": "No matching runtime test task in the configured model"})
            for name in matching:
                result = report["tests"][name]
                status = result["outcome"]
                reason = "See task result; no execution is inferred from an existing XML file"
                if target in ("iosX64", "iosSimulatorArm64") and not result["enabled"]:
                    reason = "Simulator architecture disabled on this host; a matching host is required"
                elif kind == "androidJvm":
                    reason = "Host JVM only (stubs/shadows); no ART/instrumented test suite is authored"
                    if project == ":p2p-core":
                        reason += "; core commonTest is excluded by the intentional host filter"
                elif status == "NOT_REQUESTED":
                    reason = "This invocation's profile did not request the task"
                rows.append({"target": f"{project}/{target}", "task": name, "status": status,
                             "passed": result["passed"], "failed": result["failed"],
                             "skipped": result["skipped"], "reason": reason})
    rows.append({"target": ":iosApp/Swift", "status": "OUTSIDE_THIS_INVOCATION",
                 "reason": "Swift unit/UI tests use a separate xcodebuild test command in CI"})
    return rows


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT, text=True).strip()


def source_state():
    require(not git("ls-files", "--others", "--exclude-standard"),
            "Review/stage untracked source inputs before the evidence-bound platform gate")
    patch = subprocess.check_output(["git", "diff", "--binary", "HEAD"], cwd=ROOT)
    return {"commit": git("rev-parse", "HEAD"), "tree": git("rev-parse", "HEAD^{tree}"),
            "status": git("status", "--porcelain"), "diffSha256": hashlib.sha256(patch).hexdigest()}


def terminate_process(process):
    """Drain an owned process group even after its leader exits; never kill other groups."""
    if process is None:
        return True
    # Every caller uses start_new_session=True, so this PID is the owned PGID.
    # Leader completion alone says nothing about workers still in that group.
    try:
        for sig, timeout in ((signal.SIGTERM, TERMINATION_GRACE_SECONDS), (signal.SIGKILL, TERMINATION_KILL_SECONDS)):
            os.killpg(process.pid, sig)
            deadline = time.monotonic() + timeout
            while True:
                process.poll()  # Reap the leader too; a zombie can keep the group present.
                os.killpg(process.pid, 0)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                time.sleep(min(0.05, remaining))
    except ProcessLookupError:
        process.poll()
        return True
    except OSError as error:
        print(f"FATAL: Could not drain owned process group {process.pid}: {error}", file=sys.stderr)
        return False
    print(f"FATAL: Owned process group {process.pid} survived TERM/KILL deadlines", file=sys.stderr)
    return False


def stop_gradle():
    process = None
    code = 1
    try:
        process = subprocess.Popen([str(ROOT / "gradlew"), "--stop"], cwd=ROOT, start_new_session=True)
        code = process.wait(timeout=90)
    except subprocess.TimeoutExpired:
        print("FATAL: Gradle stop timed out", file=sys.stderr)
        code = 124
    except OSError as error:
        print(f"FATAL: Could not stop Gradle: {error}", file=sys.stderr)
    finally:
        if not terminate_process(process):
            code = code or 1
    return code


def run(profile):
    require(platform.system() == "Darwin", "Platform gate requires macOS; use the documented JVM-only tasks elsewhere")
    arch = architecture(platform.machine())
    policy = read_json(POLICY)
    required_tasks(policy, profile, arch)  # Reject a mismatched host before starting any build.
    token = uuid.uuid4().hex
    directory = ROOT / "build/reports/platform-tests" / token
    directory.mkdir(parents=True, exist_ok=False)
    execution = directory / "execution.json"
    source = {**source_state(), "profile": profile, "token": token,
              "startedUtc": datetime.now(timezone.utc).isoformat()}
    command = [str(ROOT / "gradlew"), *PROFILES[profile], *FLAGS, "--init-script",
               str(ROOT / "gradle/platform-test-coverage.init.gradle"),
               f"-Pp2pkit.testCoverageRoot={ROOT}", f"-Pp2pkit.testCoverageToken={token}"]
    source["command"] = command
    (directory / "invocation.json").write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
    process = None
    code = 130
    stop_code = 1
    errors = []

    def interrupted(signum, frame):
        raise KeyboardInterrupt()

    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        process = subprocess.Popen(command, cwd=ROOT, start_new_session=True)
        code = process.wait()
    except KeyboardInterrupt:
        errors.append("Platform test invocation interrupted")
    except OSError as error:
        code = 1
        errors.append(f"Could not start/wait for Gradle: {error}")
    finally:
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        try:
            if not terminate_process(process):
                errors.append("Owned Gradle process group did not exit")
            stop_code = stop_gradle()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)

    report = {}
    try:
        report = read_json(execution)
        assess(report, policy, profile, arch, token)
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        errors.append(str(error))
    if code:
        errors.append(f"Gradle exited {code}")
    if stop_code:
        errors.append(f"Gradle stop exited {stop_code}")
    source_after = None
    try:
        source_after = source_state()
        if any(source[key] != value for key, value in source_after.items()):
            errors.append("Source state changed during the test invocation")
    except (OSError, ValueError) as error:
        errors.append(str(error))
    # Do not try to turn malformed/unvalidated input into a successful table.
    try:
        targets = target_rows(report)
    except (TypeError, KeyError, AttributeError):
        targets = []
    summary = {**source, "gradleExitCode": code, "stopExitCode": stop_code,
               "finishedUtc": datetime.now(timezone.utc).isoformat(), "sourceAfter": source_after,
               "result": "FAIL" if errors else "PASS", "errors": errors, "targets": targets}
    (directory / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    for row in targets:
        print(f"{row['target']}: {row['status']} "
              f"(passed={row.get('passed', 0)}, failed={row.get('failed', 0)}, skipped={row.get('skipped', 0)}) "
              f"— {row['reason']}")
    print(f"Platform coverage evidence: {directory.relative_to(ROOT)}")
    for error in errors:
        print(f"FATAL: {error}", file=sys.stderr)
    if not errors:
        print("RESULT: PASS — expected platform test tasks executed; listed runtime/device gaps remain")
    return (code or 1) if errors else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=PROFILES)
    arguments = parser.parse_args()
    try:
        return run(arguments.profile)
    except (OSError, ValueError, RecursionError) as error:
        print(f"FATAL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
