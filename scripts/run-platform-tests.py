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
import stat
import subprocess
import sys
import time
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_processes
import hosted_full_simulator as simulator


ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "gradle/platform-test-policy.json"
PROFILES = {
    "full": ["check"],
    "ios-x64": [":p2p-core:iosX64Test", ":p2p-transport-lan:iosX64Test"],
    "ios-arm64": [":p2p-core:iosSimulatorArm64Test", ":p2p-transport-lan:iosSimulatorArm64Test"],
    "ios-lan-arm64": [":p2p-transport-lan:iosSimulatorArm64Test"],
    "ios-lan-x64": [":p2p-transport-lan:iosX64Test"],
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
    if profile in ("ios-x64", "ios-lan-x64"):
        require(arch == "x64", profile + " requires an Intel macOS host, not Apple Silicon")
        required = set(PROFILES[profile])
        require(required <= tasks, "Intel test targets are missing from the committed model")
        return required
    if profile in ("ios-arm64", "ios-lan-arm64"):
        require(arch == "arm64", profile + " requires an Apple Silicon macOS host, not Intel")
        required = set(PROFILES[profile])
        require(required <= tasks, "ARM simulator test targets are missing from the committed model")
        return required
    require(profile == "full" and arch in ("arm64", "x64"), "Unsupported platform-test profile/host")
    unavailable = "iosX64Test" if arch == "arm64" else "iosSimulatorArm64Test"
    return {task for task in tasks if not task.endswith(":" + unavailable)}


def assess(report, policy, profile, arch, token, simulator_binding=None, simulator_start=None, simulator_prelaunch=None):
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
    if simulator_binding is not None:
        require(profile == "full", "Ordinary simulator binding is primary FULL only")
        require(type(simulator_start) is bytes and type(simulator_prelaunch) is bytes,
                "Ordinary simulator actual start and prelaunch originals required")
        simulator.assess_coverage(report, simulator_binding, simulator_start, simulator_prelaunch)
    else:
        require(report.get("ordinarySimulator") is None, "Unexpected ordinary simulator evidence in an unbound invocation")
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


def simulator_original(path, *, allow_empty=False):
    """Bounded no-follow reads of the controller's existing private receipts."""
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts, "Ordinary simulator receipt path is not absolute")
    for parent in (path, *path.parents):
        require(not stat.S_ISLNK(parent.lstat().st_mode), "Ordinary simulator receipt path is linked")
    before = path.lstat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_uid == os.getuid() and
            not before.st_mode & 0o077 and (before.st_size >= 0 if allow_empty else before.st_size > 0) and
            before.st_size <= simulator.LIMIT, "Ordinary simulator receipt is not private")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        stream = os.fdopen(descriptor, "rb")
    except BaseException:
        os.close(descriptor)
        raise
    with stream:
        opened = os.fstat(stream.fileno())
        require(os.path.samestat(before, opened), "Ordinary simulator receipt changed before read")
        raw = stream.read(simulator.LIMIT + 1)
        after = os.fstat(stream.fileno())
    current = path.lstat()
    require(os.path.samestat(before, after) and os.path.samestat(before, current) and
            before.st_mtime_ns == after.st_mtime_ns == current.st_mtime_ns and
            before.st_ctime_ns == after.st_ctime_ns == current.st_ctime_ns and
            before.st_size == after.st_size == current.st_size == len(raw), "Ordinary simulator receipt changed during read")
    return raw


def ordinary_simulator_binding(profile, arch, source):
    """Keep standalone profiles unchanged; never silently fall back from ordinary FULL.

    Presence of the real ordinary job, its canonical parent context, OR either
    marker requires the complete immutable binding. A missing env path/hash is
    not permission to use the old unbound path. No host command runs here.
    """
    environment = os.environ
    required = (simulator.PATH_ENV in environment or simulator.HASH_ENV in environment or
                environment.get("GITHUB_ACTIONS") == "true" and environment.get("GITHUB_JOB") == "complete-gate")
    state_name = environment.get(audit_processes.STATE_ENV)
    context_path, run_raw = None, None
    if state_name:
        state = Path(state_name)
        require(state.is_absolute() and ".." not in state.parts, "Invalid canonical simulator state path")
        context_path = state.parent / "run-context.json"
        if os.path.lexists(context_path):
            run_raw = simulator_original(context_path)
            run_context = simulator.parse(run_raw)
            require(type(run_context) is dict, "Invalid canonical simulator parent context")
            required |= run_context.get("scope") == "CLOSED_ORDINARY_TEST_CONTROLLER" and run_context.get("profile") == "full"
    if not required:
        return None
    require(profile == "full" and arch in ("arm64", "x64") and state_name and run_raw is not None,
            "Ordinary FULL requires its canonical simulator context")
    session = context_path.parent
    path = session / simulator.RELATIVE
    require(environment.get(simulator.PATH_ENV) == str(path), "Missing or foreign ordinary simulator binding path")
    originals = {str(context_path): run_raw}
    for original in (Path(state_name) / "context.json", session / "evidence/custody/request.json",
                     session / "evidence/simulator/admission.json", path):
        originals[str(original)] = simulator_original(original)
    binding_raw = originals[str(path)]
    expected = simulator.binding_record(run_raw, originals[str(Path(state_name) / "context.json")],
        originals[str(session / "evidence/custody/request.json")], originals[str(session / "evidence/simulator/admission.json")])
    require(binding_raw == expected and environment.get(simulator.HASH_ENV) == simulator.digest(binding_raw),
            "Ordinary simulator binding differs from its source/context/reservation")
    binding = simulator.parse(binding_raw)
    domains = audit_processes.ownership_domains(environment.get(audit_processes.CHAIN_ENV, ""),
                                                environment.get(audit_processes.DOMAINS_ENV, ""))
    domain = {"id": binding["productInvocation"], "job": binding["job"], "state": binding["state"], "home": binding["home"]}
    require(len(domains) >= 2 and domains[-1] == domain and all(domains[-2][key] == domain[key]
            for key in ("job", "state", "home")) and environment.get(audit_processes.JOB_ENV) == binding["job"] and
            [item["id"] for item in domains[:-2]] == run_context.get("ancestorInvocationIds") and
            environment.get(audit_processes.STATE_ENV) == binding["state"] and environment.get("GRADLE_USER_HOME") == binding["home"] and
            binding["source"] == source and binding["root"] == str(ROOT) and binding["session"] == str(session) and
            binding["role"] == "macos-" + arch and binding["developerDir"] == environment.get("DEVELOPER_DIR"),
            "Ordinary simulator binding is not this primary canonical invocation")
    start_path = Path(binding["state"]) / "evidence" / binding["productInvocation"] / "start.json"
    start_raw = simulator_original(start_path)
    simulator.canonical_start(binding_raw, start_raw, [item["id"] for item in domains[:-1]], os.getppid())
    originals[str(start_path)] = start_raw
    prelaunch_path = session / "evidence/simulator/prelaunch.json"
    prelaunch_raw = simulator_original(prelaunch_path)
    originals[str(prelaunch_path)] = prelaunch_raw
    phase = session / "evidence/commands" / simulator.PRELAUNCH
    for name in ("result.json", "stdout.log", "stderr.log"):
        original = phase / name
        originals[str(original)] = simulator_original(original, allow_empty=name == "stderr.log")
    row_raw = originals[str(phase / "result.json")]
    row = simulator.parse(row_raw)
    require(row_raw == simulator.encoded(row) and prelaunch_raw == simulator.prelaunch_record(run_raw, binding_raw, row,
        originals[str(phase / "stdout.log")], originals[str(phase / "stderr.log")]), "Ordinary simulator prelaunch changed")
    return {"raw": binding_raw, "path": str(path), "originals": originals, "start": start_raw, "prelaunch": prelaunch_raw}


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
                try:
                    os.killpg(process.pid, 0)
                except PermissionError:
                    # Darwin may report EPERM while a killed group's members are
                    # exiting but not yet reaped. This is uncertainty, not drain:
                    # keep the same deadline and require a later actual ESRCH.
                    pass
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
    print(f"FATAL: Owned process group {process.pid} was not proven absent within TERM/KILL deadlines", file=sys.stderr)
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
    ordinary = ordinary_simulator_binding(profile, arch, {key: source[key] for key in ("commit", "tree", "status", "diffSha256")})
    command = [str(ROOT / "gradlew"), *PROFILES[profile], *FLAGS, "--init-script",
               str(ROOT / "gradle/platform-test-coverage.init.gradle"),
               f"-Pp2pkit.testCoverageRoot={ROOT}", f"-Pp2pkit.testCoverageToken={token}"]
    if ordinary is not None:
        source["ordinarySimulator"] = simulator.coverage_identity(ordinary["raw"], ordinary["start"], ordinary["prelaunch"])
        command.extend(["-Pp2pkit.ordinarySimulatorBinding=" + ordinary["path"],
                        "-Pp2pkit.ordinarySimulatorSha256=" + simulator.digest(ordinary["raw"]),
                        "-Pp2pkit.ordinarySimulatorStartSha256=" + simulator.digest(ordinary["start"]),
                        "-Pp2pkit.ordinarySimulatorPrelaunchSha256=" + simulator.digest(ordinary["prelaunch"])])
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
        assess(report, policy, profile, arch, token, None if ordinary is None else ordinary["raw"],
               None if ordinary is None else ordinary["start"], None if ordinary is None else ordinary["prelaunch"])
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
    if ordinary is not None:
        try:
            require(ordinary_simulator_binding(profile, arch, source_after) == ordinary,
                    "Ordinary simulator binding changed during the platform invocation")
        except (OSError, ValueError, TypeError, KeyError, audit_processes.OwnershipError) as error:
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
    except (OSError, ValueError, TypeError, KeyError, RecursionError, audit_processes.OwnershipError) as error:
        print(f"FATAL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
