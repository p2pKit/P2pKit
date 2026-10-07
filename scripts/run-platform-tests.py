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
import re
import selectors
import signal
import stat
import subprocess
import sys
import time
import uuid

# Do not dirty the evidence-bound source tree while importing local suppliers.
sys.dont_write_bytecode = True
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
INTEL_BOOTSTATUS_SECONDS = 600
INTEL_SCOPE = "CALLER_MANAGED_INTEL_SIMULATOR_V1"
INTEL_RETIREMENT_SCOPE = "CALLER_MANAGED_INTEL_SIMULATOR_RETIREMENT_V1"
INTEL_PREPARE = ("simulator-macos-version", "simulator-xcode-version", "simulator-first-launch",
                 "simulator-runtimes", "intel-bootstatus-help", "simulator-devices",
                 "intel-boot", "intel-bootstatus", "intel-prelaunch")
INTEL_RETIRE = ("intel-retire-before", "intel-shutdown", "intel-retire-after")
INTEL_LEAVES = ("result.json", "stdout.bin", "stderr.bin")
INTEL_JSON_LIMIT, INTEL_STDOUT_LIMIT, INTEL_STDERR_LIMIT = 64 * 1024, 1024 * 1024, 64 * 1024
INTEL_GITHUB = dict(zip(("actions", "repository", "runId", "runAttempt", "sha", "ref", "job"),
                       ("GITHUB_ACTIONS", "GITHUB_REPOSITORY", "GITHUB_RUN_ID", "GITHUB_RUN_ATTEMPT",
                        "GITHUB_SHA", "GITHUB_REF", "GITHUB_JOB")))


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


def assess(report, policy, profile, arch, token, simulator_binding=None, simulator_start=None, simulator_prelaunch=None,
           *, intel_binding=None, intel_originals=None, intel_retirement=None, intel_invocation=None):
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
    if profile == "ios-x64":
        require(all(value is not None for value in (intel_binding, intel_originals, intel_retirement, intel_invocation)),
                "INTEL_REQUIRED_ORIGINALS")
        intel_simulator_retirement(intel_binding, intel_retirement, intel_originals, intel_invocation)
        binding = _intel_json(intel_binding)
        identity = _intel_identity(intel_binding, binding)
        require(binding["token"] == token, "INTEL_REPORT_TOKEN")
        properties = {name: {"device": identity["device"], "type": simulator.TYPE, "standalone": False}
                      for name in PROFILES["ios-x64"]}
        actual = report.get("intelSimulator")
        require(type(actual) is dict and set(actual) == set(identity) | {"configured", "inGraph", "unchanged"} and
                all(actual.get(key) == value for key, value in identity.items()) and
                actual.get("standalone") is False and actual.get("unchanged") is True and
                actual.get("configured") == properties and actual.get("inGraph") == properties and
                all(row.get("standalone") is False for kind in ("configured", "inGraph")
                    for row in actual[kind].values()), "INTEL_ACTUAL_TASK_PROPERTIES")
    else:
        require(all(value is None for value in (intel_binding, intel_originals, intel_retirement, intel_invocation)) and
                report.get("intelSimulator") is None, "INTEL_UNEXPECTED_MODE")
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


def _intel_json(raw):
    require(type(raw) is bytes and 0 < len(raw) <= INTEL_JSON_LIMIT, "INTEL_JSON_LIMIT")
    value = simulator.parse(raw)
    require(type(value) is dict and simulator.encoded(value) == raw, "INTEL_CANONICAL_JSON")
    return value


def _intel_time(value):
    require(type(value) is str and re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?(?:Z|\+00:00)", value),
        "INTEL_PHASE_TIME")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _intel_source(value):
    require(type(value) is dict and set(value) == {"commit", "tree", "status", "diffSha256"} and
            all(type(value[key]) is str and re.fullmatch(r"[0-9a-f]{40}", value[key]) for key in ("commit", "tree")) and
            value["status"] == "" and value["diffSha256"] == simulator.digest(b""), "INTEL_CLEAN_SOURCE")


def _intel_phase_command(label, selected=None):
    if label in simulator.COMMANDS:
        return simulator.command(label)
    if label == "intel-bootstatus-help":
        return ["/usr/bin/xcrun", "simctl", "help", "bootstatus"]
    if label in ("intel-prelaunch", "intel-retire-before", "intel-retire-after"):
        return simulator.command("simulator-devices")
    require(label in ("intel-boot", "intel-bootstatus", "intel-shutdown") and type(selected) is dict,
            "INTEL_CLOSED_COMMAND")
    action = {"intel-boot": "boot", "intel-bootstatus": "bootstatus", "intel-shutdown": "shutdown"}[label]
    return ["/usr/bin/xcrun", "simctl", action, simulator.uuid(selected["device"]["udid"])]


def _intel_command(root, token, binding_hash):
    return [root + "/gradlew", *PROFILES["ios-x64"], *FLAGS, "--init-script",
            root + "/gradle/platform-test-coverage.init.gradle", "-Pp2pkit.testCoverageRoot=" + root,
            "-Pp2pkit.testCoverageToken=" + token, "-Pp2pkit.intelSimulatorBinding=" + root +
            "/build/reports/platform-tests/" + token + "/intel-simulator/binding.json",
            "-Pp2pkit.intelSimulatorSha256=" + binding_hash]


def _intel_paths(labels):
    return {label + "/" + leaf for label in labels for leaf in INTEL_LEAVES}


def _intel_references(originals):
    return {name: {"bytes": len(raw), "sha256": simulator.digest(raw)} for name, raw in originals.items()}


def _intel_originals(references, originals, labels):
    expected = _intel_paths(labels)
    require(type(references) is dict and type(originals) is dict and set(references) == set(originals) == expected,
            "INTEL_ORIGINAL_ROSTER")
    for name, raw in originals.items():
        limit = INTEL_JSON_LIMIT if name.endswith("result.json") else (
            INTEL_STDOUT_LIMIT if name.endswith("stdout.bin") else INTEL_STDERR_LIMIT)
        row = references[name]
        require(type(raw) is bytes and len(raw) <= limit and type(row) is dict and
                set(row) == {"bytes", "sha256"} and type(row["bytes"]) is int and row["bytes"] == len(raw) and
                row["sha256"] == simulator.digest(raw), "INTEL_ORIGINAL_HASH_OR_LIMIT")


def _intel_work_seconds(label):
    return INTEL_BOOTSTATUS_SECONDS if label == "intel-bootstatus" else simulator.SECONDS


def _intel_phase(originals, label, root, selected):
    row = _intel_json(originals[label + "/result.json"])
    require(set(row) == {"schema", "label", "argv", "cwd", "startedUtc", "finishedUtc", "exitCode",
                        "timedOut", "outputLimitExceeded", "ownedGroupDrained", "stdoutBytes", "stdoutSha256",
                        "stderrBytes", "stderrSha256"} and type(row["schema"]) is int and row["schema"] == 1 and
            row["label"] == label and row["argv"] == _intel_phase_command(label, selected) and row["cwd"] == root,
            "INTEL_PHASE_COMMAND")
    require(type(row["exitCode"]) is int and row["exitCode"] == 0 and row["timedOut"] is False and
            row["outputLimitExceeded"] is False and row["ownedGroupDrained"] is True, "INTEL_PHASE_FAILED")
    start, end = _intel_time(row["startedUtc"]), _intel_time(row["finishedUtc"])
    require(0 <= (end - start).total_seconds() <= _intel_work_seconds(label) + TERMINATION_GRACE_SECONDS +
            TERMINATION_KILL_SECONDS, "INTEL_PHASE_DEADLINE")
    for stream in ("stdout", "stderr"):
        raw = originals[label + "/" + stream + ".bin"]
        require(type(row[stream + "Bytes"]) is int and row[stream + "Bytes"] == len(raw) and
                row[stream + "Sha256"] == simulator.digest(raw), "INTEL_PHASE_STREAM_HASH")
    return row


def _intel_identity(raw, binding):
    return {"scope": INTEL_SCOPE, "bindingSha256": simulator.digest(raw),
            "prelaunchSha256": binding["originals"]["intel-prelaunch/result.json"]["sha256"],
            "token": binding["token"], "device": binding["selected"]["device"]["udid"],
            "runtime": binding["selected"]["runtime"]["identifier"], "standalone": False}


def intel_simulator_admission(binding_raw, originals, invocation):
    """Pure original-backed Intel proof; a remote root is DATA, not local ROOT."""
    binding = _intel_json(binding_raw)
    require(set(binding) == {"schema", "scope", "profile", "role", "root", "token", "source", "developerDir",
                             "github", "tasks", "standalone", "selected", "bootedDevice", "originals"} and
            type(binding["schema"]) is int and binding["schema"] == 1 and binding["scope"] == INTEL_SCOPE and
            binding["profile"] == "ios-x64" and binding["role"] == "macos-x64" and
            binding["tasks"] == PROFILES["ios-x64"] and binding["standalone"] is False, "INTEL_BINDING_SCHEMA")
    root, token = binding["root"], binding["token"]
    require(type(root) is str and root.startswith("/") and not root.startswith("//") and
            len(root) <= 4096 and str(Path(root)) == root and ".." not in Path(root).parts and root != "/" and
            type(token) is str and re.fullmatch(r"[0-9a-f]{32}", token), "INTEL_ROOT_OR_TOKEN")
    _intel_source(binding["source"])
    require(binding["developerDir"] is None or type(binding["developerDir"]) is str and
            0 < len(binding["developerDir"]) <= 4096 and binding["developerDir"].startswith("/"), "INTEL_DEVELOPER_DIR")
    github = binding["github"]
    require(type(github) is dict and set(github) == set(INTEL_GITHUB) and
            all(value is None or type(value) is str and 0 < len(value) <= 1024 for value in github.values()),
            "INTEL_GITHUB_CONTEXT")
    if github["actions"] == "true":
        require(all(type(value) is str for value in github.values()) and
                all(re.fullmatch(r"[1-9][0-9]*", github[key]) for key in ("runId", "runAttempt")) and
                re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", github["job"]) and
                github["sha"] == binding["source"]["commit"] and
                re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", github["repository"]) and
                github["ref"].startswith("refs/"), "INTEL_HOSTED_CONTEXT")
    require(type(binding["selected"]) is dict and set(binding["selected"]) == {"runtime", "device"}, "INTEL_SELECTED")
    _intel_originals(binding["originals"], originals, INTEL_PREPARE)
    phases = [_intel_phase(originals, label, root, binding["selected"]) for label in INTEL_PREPARE]
    require(all(_intel_time(a["finishedUtc"]) <= _intel_time(b["startedUtc"]) for a, b in zip(phases, phases[1:])),
            "INTEL_PHASE_ORDER")
    values = {label: simulator.original(label, "macos-x64", originals[label + "/stdout.bin"])
              for label in simulator.PREPARE}
    require(simulator.encoded(binding["selected"]) == simulator.encoded(
            {"runtime": values["simulator-runtimes"], "device": values["simulator-devices"]}),
            "INTEL_SELECTED_ORIGINAL")
    help_text = (originals["intel-bootstatus-help/stdout.bin"] + originals["intel-bootstatus-help/stderr.bin"]).decode("utf-8")
    require("Usage: simctl bootstatus <device>" in help_text, "INTEL_BOOTSTATUS_CAPABILITY")
    ready = simulator.terminal_device(originals["intel-prelaunch/stdout.bin"], binding["selected"])
    require(ready["state"] == "Booted" and simulator.encoded(binding["bootedDevice"]) == simulator.encoded(ready),
            "INTEL_BOOTED_PRELAUNCH")
    identity = _intel_identity(binding_raw, binding)
    require(type(invocation) is dict and invocation.get("profile") == "ios-x64" and invocation.get("token") == token and
            all(invocation.get(key) == value for key, value in binding["source"].items()) and
            invocation.get("command") == _intel_command(root, token, identity["bindingSha256"]) and
            invocation.get("intelSimulator") == identity and invocation["intelSimulator"]["standalone"] is False and
            invocation.get("ordinarySimulator") is None,
            "INTEL_INVOCATION_JOIN")
    require(_intel_time(invocation.get("startedUtc")) <= _intel_time(phases[0]["startedUtc"]), "INTEL_INVOCATION_TIME")
    return identity


def intel_simulator_retirement(binding_raw, retirement_raw, originals, invocation):
    """Pure complete startup/actual-property consumer's owned-shutdown evidence."""
    require(type(originals) is dict and set(originals) == _intel_paths(INTEL_PREPARE + INTEL_RETIRE),
            "INTEL_COMPLETE_ORIGINAL_ROSTER")
    prepared = {name: raw for name, raw in originals.items() if name in _intel_paths(INTEL_PREPARE)}
    identity = intel_simulator_admission(binding_raw, prepared, invocation)
    binding, retirement = _intel_json(binding_raw), _intel_json(retirement_raw)
    require(set(retirement) == {"schema", "scope", "root", "token", "source", "selected", "bindingSha256",
                                "shutdownIssued", "originals", "deviceAfter", "errors"} and
            type(retirement["schema"]) is int and retirement["schema"] == 1 and
            retirement["scope"] == INTEL_RETIREMENT_SCOPE and retirement["shutdownIssued"] is True and
            retirement["errors"] == [] and retirement["bindingSha256"] == identity["bindingSha256"] and
            all(simulator.encoded(retirement[key]) == simulator.encoded(binding[key])
                for key in ("root", "token", "source", "selected")),
            "INTEL_RETIREMENT_CONTEXT")
    retired = {name: raw for name, raw in originals.items() if name in _intel_paths(INTEL_RETIRE)}
    _intel_originals(retirement["originals"], retired, INTEL_RETIRE)
    phases = [_intel_phase(originals, label, binding["root"], binding["selected"]) for label in INTEL_RETIRE]
    previous = _intel_json(originals["intel-prelaunch/result.json"])
    require(all(_intel_time(a["finishedUtc"]) <= _intel_time(b["startedUtc"])
                for a, b in zip([previous, *phases], phases)), "INTEL_RETIREMENT_ORDER")
    before = simulator.terminal_device(originals["intel-retire-before/stdout.bin"], binding["selected"])
    after = simulator.terminal_device(originals["intel-retire-after/stdout.bin"], binding["selected"])
    require(before["state"] == "Booted" and after["state"] == "Shutdown" and
            simulator.encoded(retirement["deviceAfter"]) == simulator.encoded(after),
            "INTEL_SHUTDOWN_ORIGINAL")
    return {"bindingSha256": identity["bindingSha256"], "retirementSha256": simulator.digest(retirement_raw),
            "device": identity["device"], "runtime": identity["runtime"], "shutdownVerified": True}


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


def _intel_write(path, raw):
    require(type(raw) is bytes and path.is_absolute(), "INTEL_PRIVATE_WRITE")
    for parent in (path.parent, *path.parent.parents):
        require(not stat.S_ISLNK(parent.lstat().st_mode), "INTEL_LINKED_PARENT")
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fchmod(stream.fileno(), 0o400)
        os.fsync(stream.fileno())


def _intel_capture_phase(directory, label, argv):
    """One bounded owned command, retaining originals even on interruption."""
    phase = directory / label
    phase.mkdir(mode=0o700)
    began = datetime.now(timezone.utc).isoformat()
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    limits = {"stdout": INTEL_STDOUT_LIMIT, "stderr": INTEL_STDERR_LIMIT}
    process, timed_out, overflow, drained = None, False, False, False
    try:
        deadline = time.monotonic() + _intel_work_seconds(label)
        # A handled signal must not escape between successful spawn and assigning
        # the owned process. Defer only callable handlers; retirement's IGN stays
        # ignored, and exec resets caught handlers in the child without mask changes.
        pending = []
        launch_handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
        def defer(signum, _frame):
            pending.append(signum)
        try:
            for sig, handler in launch_handlers.items():
                if callable(handler):
                    signal.signal(sig, defer)
            process = subprocess.Popen(argv, cwd=ROOT, start_new_session=True,
                                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        finally:
            for sig, handler in launch_handlers.items():
                if callable(handler):
                    signal.signal(sig, handler)
        for sig in pending:
            launch_handlers[sig](sig, None)
        with selectors.DefaultSelector() as selector:
            for name in buffers:
                stream = getattr(process, name)
                os.set_blocking(stream.fileno(), False)
                selector.register(stream, selectors.EVENT_READ, name)
            while selector.get_map() and not overflow:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                for key, _events in selector.select(min(0.1, remaining)):
                    name = key.data
                    try:
                        data = os.read(key.fileobj.fileno(), min(65536, limits[name] - len(buffers[name]) + 1))
                    except BlockingIOError:
                        continue
                    if not data:
                        selector.unregister(key.fileobj)
                        continue
                    room = limits[name] - len(buffers[name])
                    buffers[name].extend(data[:room])
                    if len(data) > room:
                        overflow = True
                        break
            if not timed_out and not overflow:
                try:
                    process.wait(timeout=max(0.001, deadline - time.monotonic()))
                except subprocess.TimeoutExpired:
                    timed_out = True
    finally:
        previous = {sig: signal.signal(sig, signal.SIG_IGN) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            drained = terminate_process(process)
        finally:
            if process is not None:
                for name in buffers:
                    stream = getattr(process, name)
                    if stream is not None:
                        stream.close()
            row = {"schema": 1, "label": label, "argv": argv, "cwd": str(ROOT), "startedUtc": began,
                   "finishedUtc": datetime.now(timezone.utc).isoformat(),
                   "exitCode": None if process is None else process.returncode, "timedOut": timed_out,
                   "outputLimitExceeded": overflow, "ownedGroupDrained": drained}
            try:
                for name, value in buffers.items():
                    raw = bytes(value)
                    row[name + "Bytes"], row[name + "Sha256"] = len(raw), simulator.digest(raw)
                    _intel_write(phase / (name + ".bin"), raw)
                raw = simulator.encoded(row)
                require(len(raw) <= INTEL_JSON_LIMIT, "INTEL_JSON_LIMIT")
                _intel_write(phase / "result.json", raw)
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
    return row


class IntelSimulatorOwner:
    """Only ios-x64 owns this device lifecycle; never an ordinary-FULL binding."""
    def __init__(self, directory, source):
        self.directory = directory / "intel-simulator"
        self.directory.mkdir(mode=0o700)
        self.source = {key: source[key] for key in ("commit", "tree", "status", "diffSha256")}
        _intel_source(self.source)
        self.token = source["token"]
        self.developer_dir = os.environ.get("DEVELOPER_DIR")
        self.github = {key: os.environ.get(name) for key, name in INTEL_GITHUB.items()}
        self.selected, self.binding_raw, self.retirement_raw = None, None, None
        self.originals = {}
        self.boot_attempted, self.shutdown_issued = False, False

    def phase(self, label):
        argv = _intel_phase_command(label, self.selected)
        # Reserve this exact selected-device attempt before any interruptible
        # spawn. A failed spawn is partial evidence, never a successful command.
        if label == "intel-boot":
            require(not self.boot_attempted, "INTEL_BOOT_ALREADY_ATTEMPTED")
            self.boot_attempted = True
        if label == "intel-shutdown":
            require(not self.shutdown_issued, "INTEL_SHUTDOWN_ALREADY_ATTEMPTED")
            self.shutdown_issued = True
        try:
            _intel_capture_phase(self.directory, label, argv)
        finally:
            for leaf in INTEL_LEAVES:
                path = self.directory / label / leaf
                if path.exists():
                    self.originals[label + "/" + leaf] = simulator_original(path, allow_empty=leaf != "result.json")
        _intel_phase(self.originals, label, str(ROOT), self.selected)
        return self.originals[label + "/stdout.bin"]

    def prepare(self):
        values = {}
        for label in INTEL_PREPARE[:4]:
            values[label] = simulator.original(label, "macos-x64", self.phase(label))
        self.phase("intel-bootstatus-help")
        help_text = (self.originals["intel-bootstatus-help/stdout.bin"] +
                     self.originals["intel-bootstatus-help/stderr.bin"]).decode("utf-8")
        require("Usage: simctl bootstatus <device>" in help_text, "INTEL_BOOTSTATUS_CAPABILITY")
        device = simulator.original("simulator-devices", "macos-x64", self.phase("simulator-devices"))
        self.selected = {"runtime": values["simulator-runtimes"], "device": device}
        self.phase("intel-boot")
        self.phase("intel-bootstatus")
        ready = simulator.terminal_device(self.phase("intel-prelaunch"), self.selected)
        require(ready["state"] == "Booted", "INTEL_BOOTED_PRELAUNCH")
        binding = {"schema": 1, "scope": INTEL_SCOPE, "profile": "ios-x64", "role": "macos-x64",
                   "root": str(ROOT), "token": self.token, "source": self.source, "developerDir": self.developer_dir,
                   "github": self.github, "tasks": PROFILES["ios-x64"], "standalone": False,
                   "selected": self.selected, "bootedDevice": ready, "originals": _intel_references(self.originals)}
        self.binding_raw = simulator.encoded(binding)
        require(len(self.binding_raw) <= INTEL_JSON_LIMIT, "INTEL_JSON_LIMIT")
        _intel_write(self.directory / "binding.json", self.binding_raw)
        return _intel_identity(self.binding_raw, binding)

    def retire(self):
        errors, after = [], None
        if self.boot_attempted:
            already_shutdown = False
            try:
                before = simulator.terminal_device(self.phase("intel-retire-before"), self.selected)
                already_shutdown = before["state"] == "Shutdown"
                if before["state"] != "Booted":
                    errors.append("INTEL_RETIRE_BEFORE_STATE")
            except (OSError, ValueError, TypeError, KeyError, RecursionError):
                errors.append("INTEL_RETIRE_BEFORE_FAILED")
            if not already_shutdown:
                try:
                    self.phase("intel-shutdown")
                except (OSError, ValueError, TypeError, KeyError, RecursionError):
                    errors.append("INTEL_SHUTDOWN_FAILED")
            try:
                after = simulator.terminal_device(self.phase("intel-retire-after"), self.selected)
                if after["state"] != "Shutdown":
                    errors.append("INTEL_SHUTDOWN_NOT_OBSERVED")
            except (OSError, ValueError, TypeError, KeyError, RecursionError):
                errors.append("INTEL_RETIRE_AFTER_FAILED")
        else:
            errors.append("INTEL_BOOT_NOT_ATTEMPTED")
        retired = {name: raw for name, raw in self.originals.items() if name in _intel_paths(INTEL_RETIRE)}
        self.retirement_raw = simulator.encoded({"schema": 1, "scope": INTEL_RETIREMENT_SCOPE, "root": str(ROOT),
            "token": self.token, "source": self.source, "selected": self.selected,
            "bindingSha256": None if self.binding_raw is None else simulator.digest(self.binding_raw),
            "shutdownIssued": self.shutdown_issued, "originals": _intel_references(retired),
            "deviceAfter": after, "errors": errors})
        require(len(self.retirement_raw) <= INTEL_JSON_LIMIT, "INTEL_JSON_LIMIT")
        _intel_write(self.directory / "retirement.json", self.retirement_raw)
        return errors

    def evidence(self, invocation, invocation_raw):
        require(self.binding_raw is not None and self.retirement_raw is not None, "INTEL_REQUIRED_ORIGINALS")
        for name, expected in (("binding.json", self.binding_raw), ("retirement.json", self.retirement_raw)):
            require(simulator_original(self.directory / name) == expected, "INTEL_RECORD_CHANGED")
        for name, expected in self.originals.items():
            require(simulator_original(self.directory / name, allow_empty=not name.endswith("result.json")) == expected,
                    "INTEL_ORIGINAL_CHANGED")
        require(simulator_original(self.directory.parent / "invocation.json") == invocation_raw,
                "INTEL_INVOCATION_CHANGED")
        require(os.environ.get("DEVELOPER_DIR") == self.developer_dir and
                {key: os.environ.get(name) for key, name in INTEL_GITHUB.items()} == self.github, "INTEL_CONTEXT_CHANGED")
        return {"intel_binding": self.binding_raw, "intel_originals": self.originals,
                "intel_retirement": self.retirement_raw, "intel_invocation": invocation}


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
    if profile != "ios-x64":
        (directory / "invocation.json").write_text(json.dumps(source, indent=2) + "\n", encoding="utf-8")
    process = None
    code = 130
    stop_code = 1
    errors = []
    intel, invocation_raw, gradle_attempted = None, None, False

    def interrupted(signum, frame):
        raise KeyboardInterrupt()

    previous = {sig: signal.signal(sig, interrupted) for sig in (signal.SIGINT, signal.SIGTERM)}
    try:
        if profile == "ios-x64":
            intel = IntelSimulatorOwner(directory, source)
            source["intelSimulator"] = intel.prepare()
            command = _intel_command(str(ROOT), token, source["intelSimulator"]["bindingSha256"])
            source["command"] = command
            intel_simulator_admission(intel.binding_raw, intel.originals, source)
            invocation_raw = (json.dumps(source, indent=2) + "\n").encode("utf-8")
            _intel_write(directory / "invocation.json", invocation_raw)
        gradle_attempted = True
        process = subprocess.Popen(command, cwd=ROOT, start_new_session=True)
        code = process.wait()
    except KeyboardInterrupt:
        errors.append("Platform test invocation interrupted")
    except OSError as error:
        code = 1
        errors.append("INTEL_PREPARATION_OR_LAUNCH_IO" if profile == "ios-x64" else
                      f"Could not start/wait for Gradle: {error}")
    except (ValueError, TypeError, KeyError, RecursionError) as error:
        if profile != "ios-x64":
            raise
        code = 1
        reason = str(error) if re.fullmatch(r"[A-Z_]{1,80}", str(error)) else type(error).__name__
        errors.append("INTEL_PREPARATION_OR_LAUNCH_FAILED:" + reason)
    finally:
        for sig in previous:
            signal.signal(sig, signal.SIG_IGN)
        try:
            if not terminate_process(process):
                errors.append("Owned Gradle process group did not exit")
            if profile != "ios-x64" or gradle_attempted:
                stop_code = stop_gradle()
            else:
                stop_code = None  # No Gradle process was attempted; do not launch one merely for cleanup.
        finally:
            try:
                if intel is not None:
                    try:
                        errors.extend(intel.retire())
                    except (OSError, ValueError, TypeError, KeyError, RecursionError):
                        errors.append("INTEL_RETIREMENT_FAILED")
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)

    report = {}
    intel_arguments, intel_retired = {}, None
    try:
        if intel is not None:
            intel_arguments = intel.evidence(source, invocation_raw)
            intel_retired = intel_simulator_retirement(intel.binding_raw, intel.retirement_raw, intel.originals, source)
        report = read_json(execution)
        assess(report, policy, profile, arch, token, None if ordinary is None else ordinary["raw"],
               None if ordinary is None else ordinary["start"], None if ordinary is None else ordinary["prelaunch"],
               **intel_arguments)
    except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
        errors.append(str(error))
    if code and (profile != "ios-x64" or gradle_attempted):
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
    summary = {**source, "gradleExitCode": code if profile != "ios-x64" or gradle_attempted else None, "stopExitCode": stop_code,
               "finishedUtc": datetime.now(timezone.utc).isoformat(), "sourceAfter": source_after,
               "result": "FAIL" if errors else "PASS", "errors": errors, "targets": targets}
    if profile == "ios-x64":
        summary["intelSimulatorRetirement"] = intel_retired
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
