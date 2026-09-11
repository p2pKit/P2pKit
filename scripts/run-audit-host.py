#!/usr/bin/env python3
"""Audit-branch host components; never a replacement release/physical acceptance gate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ".github/workflows/audit-host-validation.yml"
REF = "refs/heads/audit/complete-2026-09-04"
ROLES = {"windows-x64": ("Windows", "x64"), "macos-arm64": ("Darwin", "arm64"),
         "macos-x64": ("Darwin", "x64")}
SCOPES = {"full": set(ROLES), "windows-followup": {"windows-x64"}, "windows-diagnostics": {"windows-x64"},
          "apple-followup": {"macos-arm64"}, "apple-provenance": {"macos-arm64"},
          "apple-native-compilation": {"macos-arm64"}, "apple-owned-cancellation": {"macos-arm64"}}
CANCELLATION_PROBE_ROUTES = {("macos-arm64", "apple-followup"), ("macos-arm64", "apple-provenance"),
                             ("macos-x64", "full")}
# Closed source inventories: native execution must contain every listed method,
# never merely a nonzero class-prefix match. Update only with reviewed test changes.
OWNED_NATIVE_TASK = ":p2p-transport-lan:iosSimulatorArm64Test"
OWNED_NATIVE_CLASS = "dev.p2pkit.transport.lan.IosOwnedFlowCollectionTest"
OWNED_NATIVE_METHODS = frozenset({
    "cancellationBeforeStartNeverAdmitsSourceOrCallback",
    "idleSharedFlowCancellationClosesSubscriptionAndPrivateParent",
    "stateFlowReplayAndCancellationPreserveTheOtherSubscriber",
    "normalCompletionAndFailuresRetainTheirOriginalTerminalCause",
})
OWNED_SWIFT_METHODS = {
    "OwnedFlowCollectionTests": frozenset({
        "testCancelBeforeStartClosesAdmissionAndCancelledWaitersStillWaitForNativeRetirement",
        "testCancellationDuringImmediateCompletionRegistrationIsStickyAndDisposesTheReturnedHandle",
        "testQueuedCallbackIsSkippedAndAcknowledgedBeforeCancelledDrainReturns",
        "testSerialBackpressureAcknowledgesOnlyAfterDeliveryWithoutGrowingCallbackTaskOwnership",
        "testNormalAndFailedNativeCompletionBothDrainAnAlreadyAcceptedCallback",
        "testTypeMismatchCancelsNativeWithoutThrowingSwiftErrorAcrossKotlinAndPreservesFailure",
        "testOverlappingEmitFailsClosedAndAcknowledgesBothWithoutAddingCallbackTasks",
        "testBackgroundCallbacksAndCancellationUseTheSameThreadSafeAdmissionAndRetirement",
        "testRetirementReleasesNativeJobRegistrationAndHandlerCapture",
    }),
    "SampleRunLifecycleTests": frozenset({
        "testStopDuringManualInfoRejectsLateSuccessAndFailureBeforeObserverInstallation",
        "testOldStartupFailureAndTracingReleaseCannotClearOrReleaseReplacement",
        "testFailedRollbackRetainsOwnerRejectsAdmissionAndRetriesStopOperation",
        "testCallerCancellationReachesRollbackInsteadOfAbandoningTheAcquiredKit",
        "testActualCollectorQueuedCallbackCompletesWithoutPublishingIntoReplacement",
        "testPermissionDelayRejectsCancellationAndStopEvenWhenTheDelayReturnsLate",
        "testUnbuiltCreateFailureWaitsForOwnedDiagnosticsBeforeAllowingAnotherRun",
        "testRemovedSessionRetireesAndLateCompletionCannotEraseReplacementLeases",
        "testStopDrainsAllFourOwnedRolesAfterSdkCleanupAndPreservesObserverFailure",
        "testFailedSdkStopDrainsObserversThenRetriesRealCleanupWithoutRecreatingThem",
        "testCallerCancellationCannotPublishIdleBeforeOwnedNativeRetirement",
        "testStopSkipsQueuedOwnedCallbackAndPublishesSuccessOnlyAfterItsAcknowledgement",
    }),
    "IosLanDiagnosticsLeaseTests": frozenset({
        "testConsoleOptInMatchesBuildConfigurationAndDefaultSettingsAreRestored",
        "testOverlappingOwnersAndStaleReleaseDoNotDisableTheActiveRun",
        "testOutOfOrderReleasePreservesAllOtherOwners",
        "testEachRunRestoresItsOwnHostConfiguration",
        "testPreRetainingHostHistoryIsNotErasedOnRelease",
        "testDeinitializationReleasesOnlyItsOwnLease",
        "testReleaseBuildNeverTakesOwnershipOfExternalConsoleChanges",
    }),
}
OWNED_SWIFT_CASE = "SwiftOwnedFlowCancellationTests/testOwnedAdapterCancellationFinishesActualDiagnosticCollection()"
SWIFT_SELECTIONS = {
    "owned-flow-lifecycle": {"p2pkit-sample-tests": {
        name + "/" + method + "()" for name, methods in OWNED_SWIFT_METHODS.items() for method in methods}},
    "owned-cancellation": {"p2pkit-sample-cancellation-probe-tests": {OWNED_SWIFT_CASE}},
}
WINDOWS_TASKS = {":p2p-core:jvmTest", ":p2p-transport-lan:jvmTest", ":p2p-network-provisioning-desktop:test"}
WINDOWS_FOLLOWUP_TASKS = {":p2p-core:jvmTest"}
WINDOWS_DIAGNOSTICS_TASKS = {":p2p-transport-lan:jvmTest"}
DESKTOP_TASKS = [":p2p-sample-desktop:check", ":p2p-sample-desktop:installDist", ":p2p-sample-desktop-ui:test",
                 ":p2p-sample-desktop-ui:checkRuntime", ":p2p-sample-desktop-ui:hotRunArgfile",
                 ":p2p-sample-desktop-ui:createDistributable"]
MODULES = ["p2p-core", "p2p-transport-lan", "p2p-network-provisioning-android", "p2p-network-provisioning-desktop"]
OUTPUTS = ["build", "buildSrc/build", *["library/" + module + "/build" for module in MODULES],
           *["samples/" + module + "/build" for module in (
               "p2p-sample-android", "p2p-sample-desktop", "p2p-sample-desktop-ui", "p2p-sample-diagnostics",
               "sample-kmp-shared", "iosApp")]]
GENERATED_PROJECT = "samples/iosApp/p2pkit-sample.xcodeproj"
FINALIZATION_GRACE = 360
MAX_SCAN_ENTRIES = 100000
ADAPTER_OPT_INS = ("P2PKIT_GRADLE_EXECUTOR", "P2PKIT_XCODE_JOBS", "P2PKIT_CONSUMER_WORK_DIR",
                   "P2PKIT_CONSUMER_AUDIT_METADATA", "P2PKIT_KEEP_CONSUMER_ARTIFACTS",
                   "P2PKIT_CONSUMER_REPOSITORY_URL", "IOS_RUN_DIR", "KEEP_IOS_RUN_ARTIFACTS")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def strict_walk(path):
    """Never certify a partial tree after an unreadable directory or unbounded scan."""
    def fail(error):
        raise error

    scanned = 0
    for row in os.walk(path, followlinks=False, onerror=fail):
        scanned += len(row[1]) + len(row[2])
        require(scanned <= MAX_SCAN_ENTRIES, "Evidence traversal exceeds its entry bound")
        yield row


def now():
    return datetime.now(timezone.utc).isoformat()


def resolve_windows_shell(environment):
    """Bind Git for Windows, never the ambient Bash/WSL executable search."""
    executable = shutil.which("git.exe", path=environment.get("PATH", ""))
    require(executable is not None and Path(executable).is_absolute(), "Git for Windows git.exe is unavailable")
    git_exe = Path(executable).resolve(strict=True)
    require(git_exe.name.lower() == "git.exe" and git_exe.parent.name.lower() in ("cmd", "bin"),
            "Unsupported Git for Windows installation layout: " + str(git_exe))
    installation = git_exe.parent.parent
    bash = installation / "bin/bash.exe"
    utilities = installation / "usr/bin"
    require(bash.is_file() and utilities.is_dir(), "Git for Windows Bash/tools are unavailable: " + str(installation))
    # Nested /usr/bin/env bash and checksum/checkout utilities need this same
    # installation. Do not shadow Windows tools for native Gradle product tasks.
    path = os.pathsep.join((str(bash.parent), str(utilities), environment.get("PATH", "")))
    return {"git": str(git_exe), "bash": str(bash), "PATH": path}


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for data in iter(lambda: stream.read(262144), b""):
            value.update(data)
    return value.hexdigest()


def git(*args, root=ROOT):
    return git_bytes(*args, root=root).decode("utf-8", errors="surrogateescape").strip()


def git_bytes(*args, root=ROOT):
    environment = dict(os.environ)
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_EXTERNAL_DIFF"):
        environment.pop(key, None)
    return subprocess.check_output(["git", "--no-replace-objects", "--no-pager", *args], cwd=root,
                                   env=environment, timeout=30)


def source_snapshot(root=ROOT):
    return {"commit": git("rev-parse", "HEAD", root=root),
            "tree": git("rev-parse", "HEAD^{tree}", root=root),
            "status": git_bytes("status", "--porcelain=v1", "--untracked-files=all", root=root).decode(
                "utf-8", errors="surrogateescape"),
            "diffSha256": hashlib.sha256(git_bytes("diff", "--binary", "--no-ext-diff", "--no-textconv",
                                                  "HEAD", "--", root=root)).hexdigest()}


def physical(path):
    """Reject symlink/reparse ancestors before touching caller-specified evidence/work."""
    path = Path(path)
    require(path.is_absolute() and ".." not in path.parts, "Expected a physical absolute path")
    for candidate in (path, *path.parents):
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode) and not (getattr(info, "st_file_attributes", 0) & 0x400),
                "Symlink/reparse path is not audit-owned: " + str(candidate))
    return path


def strict_files(root):
    for parent, directories, files in strict_walk(root):
        for name in directories:
            require(physical(Path(parent) / name).is_dir(), "Evidence directory is not regular")
        for name in files:
            path = physical(Path(parent) / name)
            require(path.is_file(), "Evidence is not a regular file")
            yield path


def read_json(path):
    physical(path)
    require(Path(path).is_file(), "Missing regular JSON evidence")
    return load_gate().read_json(path)


def load_receipt_checker():
    spec = importlib.util.spec_from_file_location("audit_receipt_check", ROOT / "scripts/check-audit-receipt.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    return checker


def load_gate(root=ROOT):
    spec = importlib.util.spec_from_file_location("audit_platform_gate", root / "scripts/run-platform-tests.py")
    gate = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gate)
    return gate


def admit(event, environment, role, root=ROOT, scope="full"):
    """Reject fallback push triggers, foreign refs, dirty inputs and cross-architecture substitution."""
    require(scope in SCOPES and role in SCOPES[scope], "Unsupported audit role/scope pair")
    gate = load_gate(root)
    require(type(event) is dict and type(event.get("repository")) is dict, "Malformed push event")
    require(role in ROLES, "Unsupported audit host role")
    require(environment.get("GITHUB_EVENT_NAME") == "push", "Audit entry requires a push event")
    require(environment.get("GITHUB_REPOSITORY") == "p2pKit/P2pKit", "Unexpected repository")
    require(environment.get("GITHUB_REF") == REF and event.get("ref") == REF, "Unexpected audit branch")
    require(event.get("repository", {}).get("full_name") == "p2pKit/P2pKit", "Event repository differs")
    require(event.get("deleted") is False and event.get("forced") is False and event.get("created") is False,
            "Deleted, forced, new or incomplete push events are not admitted")
    before, after = event.get("before"), event.get("after")
    require(type(before) is str and re.fullmatch(r"[0-9a-f]{40}", before) and before != "0" * 40,
            "Missing existing-branch base commit")
    require(type(after) is str and re.fullmatch(r"[0-9a-f]{40}", after), "Invalid push head")
    require(after == environment.get("GITHUB_SHA") == git("rev-parse", "HEAD", root=root), "Checkout SHA differs")
    git("merge-base", "--is-ancestor", before, after, root=root)
    changed = git("diff", "--name-only", "--no-renames", before, after, "--", root=root).splitlines()
    require(WORKFLOW in changed, "Push did not change the explicit audit workflow trigger path")
    require(not git("status", "--porcelain=v1", "--untracked-files=all", root=root), "Audit source is not clean")
    expected_os, expected_arch = ROLES[role]
    require(platform.system() == expected_os and gate.architecture(platform.machine()) == expected_arch,
            "Native runner OS/architecture differs from the admitted role")
    if expected_os == "Darwin":
        translated = subprocess.run(["sysctl", "-in", "sysctl.proc_translated"], capture_output=True, text=True)
        require(translated.returncode in (0, 1) and translated.stdout.strip() in ("", "0"),
                "Rosetta/unknown translated execution is not native host evidence")
    return {"commit": after, "tree": git("rev-parse", "HEAD^{tree}", root=root), "before": before,
            "ref": REF, "role": role, "requestedScope": scope, "changedPaths": changed, "admittedUtc": now(),
            "runId": environment.get("GITHUB_RUN_ID"), "runAttempt": environment.get("GITHUB_RUN_ATTEMPT")}


def assess_windows(report, policy, token, required_tasks=WINDOWS_TASKS):
    """Use real Gradle execution events, not stale XML or compilation as a test pass."""
    require(required_tasks in (WINDOWS_TASKS, WINDOWS_FOLLOWUP_TASKS, WINDOWS_DIAGNOSTICS_TASKS),
            "Unsupported Windows required-task set")
    gate = load_gate()
    gate.validate_policy(policy)
    require(type(report) is dict and type(report.get("schema")) is int and report["schema"] == 1,
            "Invalid Windows execution report schema")
    require(report.get("token") == token and report.get("dryRun") is False and report.get("buildFailed") is False,
            "Stale, dry-run or failed Windows execution report")
    host = report.get("host", {})
    require(type(host) is dict and type(host.get("os")) is str and host["os"].startswith("Windows") and
            gate.architecture(host.get("arch")) == "x64", "Not native Windows x64 execution")
    require(report.get("model") == policy["model"], "Windows configured target/task model differs")
    expected = {task for entry in policy["model"].values() for task in entry["tests"]}
    require(required_tasks <= expected and type(report.get("tests")) is dict and
            set(report["tests"]) == expected, "Missing or unclassified Windows test tasks")
    outcomes = {"EXECUTED", "FAILED", "NO_SOURCE", "SKIPPED", "UP-TO-DATE", "FROM-CACHE", "NOT_COMPLETED", "NOT_REQUESTED"}
    for task, result in report["tests"].items():
        require(type(result) is dict and type(result.get("enabled")) is bool and
                type(result.get("inGraph")) is bool and result.get("outcome") in outcomes,
                "Malformed Windows task state: " + task)
        require(all(type(result.get(key)) is int and result[key] >= 0 for key in ("passed", "failed", "skipped")),
                "Malformed Windows counts: " + task)
        require(result["failed"] == 0 and result["outcome"] != "FAILED", "Failed Windows task: " + task)
        if task in required_tasks:
            require(result["outcome"] == "EXECUTED" and result["enabled"] and result["inGraph"] and result["passed"] > 0,
                    "Fresh nonzero Windows test execution is missing: " + task)
    return {name: report["tests"][name] for name in sorted(required_tasks)}


def assess_swift(objects, selection=None):
    """Require BOTH ordinary targets by default, or one explicit closed focused inventory."""
    require(selection is None or type(selection) is str and selection in SWIFT_SELECTIONS,
            "Unsupported focused Swift selection")
    expected = SWIFT_SELECTIONS.get(selection)
    targets = {name: [] for name in expected} if expected is not None else {
        "p2pkit-sample-tests": [], "p2pkit-sample-uitests": []}
    def walk(value):
        if isinstance(value, dict):
            yield value
            for nested in value.values():
                yield from walk(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from walk(nested)
    require(type(objects) is list and objects and all(type(obj) is dict for obj in objects),
            "Missing or malformed xcresult test summaries")
    def field(entry, name):
        value = entry.get(name)
        require(type(value) is dict and type(value.get("_value")) is str, "Malformed Swift " + name)
        return value["_value"]
    for obj in objects:
        for entry in walk(obj):
            kind = entry.get("_type", {})
            require(type(kind) is dict, "Malformed xcresult type")
            if kind.get("_name") != "ActionTestableSummary":
                continue
            name = field(entry, "targetName")
            if name not in targets and expected is None:
                continue
            for test in walk(entry.get("tests", {})):
                test_kind = test.get("_type", {})
                require(type(test_kind) is dict, "Malformed Swift test type")
                if test_kind.get("_name") == "ActionTestMetadata":
                    require(name in targets, "Unexpected executed Swift target: " + name)
                    targets[name].append({"identifier": field(test, "identifier"), "status": field(test, "testStatus")})
    for name, cases in targets.items():
        require(cases and all(type(case["identifier"]) is str and case["identifier"] for case in cases),
                "Missing actual Swift cases for " + name)
        require(len({case["identifier"] for case in cases}) == len(cases), "Duplicated Swift cases for " + name)
        require(all(case["status"] == "Success" for case in cases), "Failed/skipped/unknown Swift case in " + name)
        if expected is not None:
            require({case["identifier"] for case in cases} == expected[name],
                    "Missing or unexpected selected Swift methods in " + name)
    return targets


def assess_owned_native(report, policy, token, junit):
    """Bind four real helper cases to fresh ARM events; no other test task may supply counts."""
    required = load_gate().assess(report, policy, "ios-lan-arm64", "arm64", token)
    require(required == {OWNED_NATIVE_TASK}, "Owned helper task differs from the maintained platform model")
    for name, row in report["tests"].items():
        if name == OWNED_NATIVE_TASK:
            require(row["passed"] == len(OWNED_NATIVE_METHODS) and row["skipped"] == 0,
                    "Owned native helper counts differ from the frozen method inventory")
        else:
            require(not row["inGraph"] and row["outcome"] == "NOT_REQUESTED" and
                    row["passed"] == row["failed"] == row["skipped"] == 0,
                    "Unexpected native test task in the focused graph: " + name)
    require(type(junit) is bytes and 0 < len(junit) <= 1024 ** 2 and
            b"<!DOCTYPE" not in junit and b"<!ENTITY" not in junit, "Invalid bounded native JUnit XML")
    suite = ET.fromstring(junit)
    native_class = "iosSimulatorArm64Test." + OWNED_NATIVE_CLASS
    require(suite.tag == "testsuite" and suite.get("name") == native_class and
            all(child.tag in ("properties", "testcase", "system-out", "system-err") for child in suite),
            "Unexpected native helper JUnit suite")
    cases = suite.findall("testcase")
    expected = {method + "[iosSimulatorArm64]" for method in OWNED_NATIVE_METHODS}
    require(suite.get("tests") == str(len(expected)) and all(suite.get(key) == "0"
            for key in ("errors", "failures", "skipped")), "Failed/skipped or incomplete native JUnit suite")
    require(len(cases) == len(expected) and {case.get("name") for case in cases} == expected and
            all(case.get("classname") == native_class and
                all(child.tag in ("system-out", "system-err") for child in case) for case in cases),
            "Missing, duplicate, unexpected or unsuccessful native helper methods")
    return {"task": OWNED_NATIVE_TASK, "class": native_class, "methods": sorted(expected),
            "counts": report["tests"][OWNED_NATIVE_TASK]}


class InfrastructureFailure(RuntimeError):
    pass


class Host:
    def __init__(self, role, state, timeout_seconds=None, scope="full"):
        require(scope in SCOPES and role in SCOPES[scope], "Unsupported audit role/scope pair")
        self.scope = scope
        self.role, self.state = role, state
        self.evidence = state / "evidence"
        self.runner = ROOT / "scripts/run-audit-command.py"
        self.wrapper = ROOT / ("gradlew.bat" if role == "windows-x64" else "gradlew")
        self.rows = []
        self.environment = dict(os.environ, P2PKIT_AUDIT_STATE_DIR=str(state),
                                P2PKIT_GRADLE_EXECUTOR=str(self.runner), P2PKIT_XCODE_JOBS="2")
        for key in ADAPTER_OPT_INS:
            if key not in ("P2PKIT_GRADLE_EXECUTOR", "P2PKIT_XCODE_JOBS"):
                self.environment.pop(key, None)
        self.environment.pop("ANDROID_SDK_ROOT", None)
        self.admission = None
        self.context = None
        self.context_hash = None
        self.owns_state = False
        self.state_identity = None
        self.work_identity = None
        self.safe = False
        self.windows_shell = None
        self.simulator = None
        self.started = now()
        budget = timeout_seconds if timeout_seconds is not None else (19200 if role == "macos-arm64" else 8400)
        require(type(budget) is int and FINALIZATION_GRACE + 60 <= budget <= 19800, "Invalid host deadline")
        self.deadline = time.monotonic() + budget
        self.finalizing = False
        self.receipts = {}
        self.leaf_hashes = {}

    def write(self, name, value):
        self.assert_owned_state()
        path = physical(self.evidence / name)
        require(path.parent == self.evidence, "Host metadata must have an exact evidence basename")
        with path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(value, indent=2, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    @staticmethod
    def identity(path):
        info = physical(path).stat()
        return info.st_dev, info.st_ino

    def assert_owned_state(self):
        require(self.owns_state and self.state_identity == self.identity(self.state),
                "Audit state was not initialized by this host or its identity changed")
        require(self.evidence.is_dir(), "Initialized evidence directory is missing")
        physical(self.evidence)

    def remaining(self):
        reserve = 0 if self.finalizing else FINALIZATION_GRACE
        remaining = self.deadline - time.monotonic() - reserve
        require(remaining > 0, "Host deadline reached; remaining components are NOT_EXECUTED")
        return remaining

    def validate_receipt(self, record, status, invocation, label, kind, arguments, receipt):
        load_receipt_checker().validate(record, status, label, ROOT, self.wrapper, arguments)
        require(record.get("id") == invocation and record.get("jobId") == self.context["id"] and
                record.get("kind") == kind and record.get("host") == self.role and
                record.get("gradleHome") == self.context["gradleHome"], "Receipt invocation/context binding differs")
        require(record.get("ownedSurvivors") == [] and type(record["ownedSurvivors"]) is list,
                "Worker drain proof is not an empty list")
        require(record["sourceBefore"] == self.context["source"] and
                record["sourceBefore"]["commit"] == self.admission["commit"] and
                record["sourceBefore"]["tree"] == self.admission["tree"] and
                record["sourceBefore"]["status"] == "" and
                record["sourceBefore"]["diffSha256"] == hashlib.sha256(b"").hexdigest(),
                "Receipt is not bound to the admitted clean source")
        evidence = physical(self.evidence / invocation)
        require(record.get("evidenceDirectory") == str(evidence), "Receipt evidence directory differs")
        for name in ("receipt.json", "start.json", "product.stdout.log", "product.stderr.log",
                     "stop.stdout.log", "stop.stderr.log", "report-manifest.json"):
            require(physical(evidence / name).is_file(), "Required leaf evidence is absent: " + name)
        require(digest(evidence / "receipt.json") == digest(receipt), "Final receipt copies differ")
        start = read_json(evidence / "start.json")
        for name in ("schema", "id", "purpose", "kind", "jobId", "host", "gradleHome", "cwd", "wrapper", "requestedArgv"):
            require(start.get(name) == record[name] and type(start.get(name)) is type(record[name]),
                    "Invocation start binding differs: " + name)
        reports = read_json(evidence / "report-manifest.json")
        require(type(reports.get("schema")) is int and reports["schema"] == 1 and
                type(reports.get("records")) is list and reports["records"] == record.get("reports"),
                "Report manifest is not bound to this finalized receipt")
        retained = set()
        for item in reports["records"]:
            require(type(item) is dict and type(item.get("bytes")) is int and item["bytes"] >= 0 and
                    type(item.get("sha256")) is str and re.fullmatch(r"[0-9a-f]{64}", item["sha256"]),
                    "Malformed retained report binding")
            require(item.get("classification") in ("changed-since-admission", "preexisting-unchanged"),
                    "Unknown report freshness classification")
            if item["classification"] == "changed-since-admission":
                relative = item.get("retained")
                require(type(relative) is str and relative.startswith("reports/") and "\\" not in relative,
                        "Missing retained report path")
                target = physical(evidence / relative)
                require(relative not in retained and target.is_relative_to(evidence) and target.is_file(),
                        "Invalid or duplicate retained report")
                require(target.stat().st_size == item["bytes"] and digest(target) == item["sha256"],
                        "Retained report hash/size differs")
                retained.add(relative)
        require(digest(self.state / "context.json") == self.context_hash, "Host context changed")
        return evidence

    def invoke(self, label, args, kind="gradle", timeout=3600, extra_env=None):
        self.assert_owned_state()
        require(re.fullmatch(r"[a-z0-9-]+", label), "Unsafe component label")
        receipt = self.state / ("host-" + label + ".json")
        require(not receipt.exists(), "Component already executed: " + label)
        require(shutil.disk_usage(self.state).free >= 2 * 1024 ** 3, "Less than 2GiB free before " + label)
        environment = dict(self.environment)
        for key, value in (extra_env or {}).items():
            if value is None:
                environment.pop(key, None)
            else:
                environment[key] = value
        arguments = list(map(str, args))
        invocation = uuid.uuid4().hex
        timeout = min(timeout, self.remaining())
        command = [sys.executable, str(self.runner), "--cwd", str(ROOT), "--wrapper", str(self.wrapper),
                   "--purpose", label, "--kind", kind, "--id", invocation, "--receipt", str(receipt),
                   "--timeout", str(timeout), "--", *arguments]
        print("==> " + label, flush=True)
        process, status, record, clean, cancellation, diagnostic = None, 125, {}, False, False, None
        try:
            process = subprocess.Popen(command, cwd=ROOT, env=environment)
            try:
                status = process.wait(timeout=timeout + FINALIZATION_GRACE)
            except (KeyboardInterrupt, subprocess.TimeoutExpired):
                cancellation = True
                # Windows terminate()/SIGTERM is hard process death, not Python finally.
                # Ask the still-live controller to drain/stop/retain cooperatively.
                signals = {number: signal.signal(number, signal.SIG_IGN) for number in (signal.SIGINT, signal.SIGTERM)}
                try:
                    cancelled = subprocess.run([sys.executable, str(self.runner), "request-cancel", "--state",
                                                str(self.state), "--id", invocation], cwd=ROOT, env=environment,
                                               timeout=30, capture_output=True)
                    self.write("cancel-" + invocation + ".json", {"requestExitCode": cancelled.returncode,
                               "stdout": cancelled.stdout.decode(errors="replace"),
                               "stderr": cancelled.stderr.decode(errors="replace")})
                    status = process.wait(timeout=FINALIZATION_GRACE)
                finally:
                    for number, handler in signals.items():
                        signal.signal(number, handler)
            record = read_json(receipt)
            evidence = self.validate_receipt(record, status, invocation, label, kind, arguments, receipt)
            hashes = {}
            for path in strict_files(evidence):
                hashes[path.relative_to(evidence).as_posix()] = digest(path)
            self.leaf_hashes[invocation] = hashes
            clean = not cancellation
        except Exception as error:
            diagnostic = type(error).__name__ + ": " + str(error)
        self.rows.append({"component": label, "command": command, "exitCode": status,
                          "result": "PASS" if status == 0 and clean else "FAIL",
                          "cleanupComplete": clean, "receipt": str(receipt.relative_to(self.state)),
                          "controllerPid": process.pid if process else None,
                          "cancelled": cancellation, "error": diagnostic})
        if not clean:
            self.safe = False
            raise InfrastructureFailure("Missing/failed source, ownership, stop or evidence finalization: " + label)
        self.receipts[label] = record
        return status == 0

    def check(self, label, callback):
        """Retained inspection only; it must not start a build/test subprocess."""
        try:
            result = callback()
            self.write(label + ".json", {"result": "PASS", "details": result})
            self.rows.append({"component": label, "result": "PASS", "inspectionOnly": True})
            return True
        except Exception as error:
            self.write(label + ".json", {"result": "FAIL", "error": str(error)})
            self.rows.append({"component": label, "result": "FAIL", "inspectionOnly": True})
            return False

    def clean_outputs(self):
        self.assert_owned_state()
        paths = [str(ROOT / path) for path in OUTPUTS if (ROOT / path).exists()]
        if not paths:
            return
        command = [sys.executable, str(self.runner), "cleanup", "--state", str(self.state)]
        for path in paths:
            command.extend(["--path", path])
        try:
            result = subprocess.run(command, cwd=ROOT, env=self.environment, timeout=120)
            require(result.returncode == 0, "Owned output cleaner returned nonzero")
        except Exception as error:
            self.safe = False
            raise InfrastructureFailure("Disposable-output cleanup failed; do not advance to another host") from error

    def retain_tree(self, source, destination, *, selected=None, byte_limit=2 * 1024 ** 3):
        """Copy explicit job-owned evidence with source/destination hashes; never follow links."""
        self.assert_owned_state()
        physical(source)
        physical(destination)
        require(source.is_dir() and destination.is_relative_to(self.evidence) and not destination.exists(),
                "Evidence source/destination is not a fresh explicit directory")
        rows, omitted, total = [], [], 0
        for parent, dirs, files in strict_walk(source):
            # A metadata selection must not walk excluded cache/runtime links.
            # Raw bundle/publication retention remains strict: selected links are
            # never dereferenced or silently substituted for required evidence.
            for name in [*dirs, *files]:
                path = Path(parent) / name
                info = path.lstat()
                linked = stat.S_ISLNK(info.st_mode) or (getattr(info, "st_file_attributes", 0) & 0x400)
                if linked and selected is not None and not selected(path.relative_to(source)):
                    omitted.append({"path": path.relative_to(source).as_posix(),
                                    "reason": "unselected-link-not-followed"})
                    require(len(omitted) <= 20000, "Excluded link count exceeds its bound")
                    if name in dirs:
                        dirs.remove(name)
                    else:
                        files.remove(name)
                else:
                    physical(path)
            for name in sorted(files):
                path = Path(parent) / name
                require(path.is_file(), "Evidence is not a regular file")
                relative = path.relative_to(source)
                if selected is not None and not selected(relative):
                    continue
                size = path.stat().st_size
                total += size
                require(total <= byte_limit and len(rows) < 20000, "Selected evidence exceeds its bound")
                rows.append({"path": relative.as_posix(), "bytes": size, "sha256": digest(path)})
        require(shutil.disk_usage(self.state).free > total + 256 * 1024 ** 2, "Insufficient space to retain evidence")
        destination.mkdir(parents=True, exist_ok=False)
        for row in rows:
            path = source / row["path"]
            target = destination / row["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            with path.open("rb") as incoming, target.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
            require(digest(target) == row["sha256"] == digest(path), "Evidence changed during copy")
        if omitted:
            self.write("retention-omissions-" + uuid.uuid4().hex + ".json",
                       {"source": str(source), "destination": str(destination), "omitted": omitted})
        return rows

    def prerequisites(self):
        tools = {"python": [sys.executable, "--version"], "git": ["git", "--version"],
                 "java17": [str(Path(os.environ["JAVA_HOME"]) / "bin" / ("java.exe" if os.name == "nt" else "java")), "-version"],
                 "java21": [str(Path(os.environ["P2PKIT_AUDIT_JDK21"]) / "bin" /
                                ("java.exe" if os.name == "nt" else "java")), "-version"],
                 "bash": ["bash", "--version"]}
        if self.role != "windows-x64":
            tools.update({"ruby": ["ruby", "--version"], "xcode": ["xcodebuild", "-version"],
                          "sdk": ["xcrun", "--show-sdk-version", "--sdk", "iphonesimulator"],
                          "jq": ["jq", "--version"], "xmllint": ["xmllint", "--version"]})
        results = {}
        shell = None
        if self.role == "windows-x64":
            self.windows_shell = None
            del tools["bash"]
            try:
                shell = resolve_windows_shell(self.environment)
                tools["git"] = [shell["git"], "--version"]
                tools["bash"] = [shell["bash"], "--version"]
            except (OSError, ValueError) as error:
                # Keep other version diagnostics and write the failed selection;
                # absence must not fall back to WSL or bypass prerequisites.json.
                results["bash"] = {"command": [], "exitCode": None, "error": str(error)}
        for label, args in tools.items():
            try:
                environment = dict(self.environment)
                if label == "bash" and shell is not None:
                    environment["PATH"] = shell["PATH"]
                proc = subprocess.run(args, cwd=ROOT, env=environment, capture_output=True, text=True, timeout=60)
                results[label] = {"command": args, "exitCode": proc.returncode,
                                  "stdout": proc.stdout, "stderr": proc.stderr}
            except (OSError, subprocess.SubprocessError) as error:
                results[label] = {"command": args, "exitCode": None, "error": str(error)}
        if os.name == "nt":
            import ctypes
            from ctypes import wintypes
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD),
                            *[(name, ctypes.c_ulonglong) for name in ("totalPhysical", "availablePhysical",
                              "totalPageFile", "availablePageFile", "totalVirtual", "availableVirtual", "reserved")]]
            memory = MemoryStatus()
            memory.length = ctypes.sizeof(memory)
            api = ctypes.WinDLL("kernel32", use_last_error=True).GlobalMemoryStatusEx
            api.argtypes, api.restype = [ctypes.POINTER(MemoryStatus)], wintypes.BOOL
            require(api(ctypes.byref(memory)) != 0, "Native RAM query failed")
            ram = memory.totalPhysical
        else:
            ram = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True, timeout=30))
        self.write("prerequisites.json", {"observedUtc": now(), "os": platform.platform(),
                   "architecture": platform.machine(), "cpuCount": os.cpu_count(),
                   "physicalMemoryBytes": ram,
                   "disk": shutil.disk_usage(self.state)._asdict(),
                   "imageOS": os.environ.get("ImageOS"), "imageVersion": os.environ.get("ImageVersion"),
                   "tools": results, "windowsShell": shell,
                   "limits": "Hosted/simulator only; no physical or independent acceptance."})
        require(ram >= 6 * 1024 ** 3, "Less than 6GiB native RAM; bounded hosted gate cannot start")
        require(all(value["exitCode"] == 0 for value in results.values()), "Required tool version query failed")
        require(re.search(r'version "17\.', results["java17"]["stderr"] + results["java17"]["stdout"]),
                "Launcher is not the provided JDK17")
        require(re.search(r'version "21\.', results["java21"]["stderr"] + results["java21"]["stdout"]),
                "Daemon prerequisite is not the provided JDK21")
        if self.role != "windows-x64":
            expected = "Xcode 26.5" if self.role == "macos-arm64" else "Xcode 26.3"
            require(results["xcode"]["stdout"].splitlines()[0] == expected, "Unexpected selected Xcode version")
        else:
            require(re.search(r"^git version [^\r\n]+\.windows\.[0-9]+", results["git"]["stdout"], re.M),
                    "Not a Git for Windows version")
            # The bundled MSYS2 Bash can report either supported x64 runtime triplet.
            require(re.search(r"^GNU bash, version [^\r\n]+\(x86_64-pc-(?:msys|cygwin)\)",
                              results["bash"]["stdout"], re.M),
                    "Not native x64 Git for Windows Bash")
            self.windows_shell = shell

    def setup_sdk(self):
        sdk = Path(self.environment.get("ANDROID_HOME", ""))
        require(sdk.is_absolute() and sdk.is_dir(), "ANDROID_HOME is not an existing SDK")
        manager = sdk / "cmdline-tools/latest/bin" / ("sdkmanager.bat" if os.name == "nt" else "sdkmanager")
        require(manager.is_file(), "Android command-line tools are unavailable")
        if not self.invoke("android-platforms", [str(manager), "--sdk_root=" + str(sdk),
                                                "platforms;android-36", "platforms;android-37.0"], kind="command"):
            raise ValueError("Android platform installation failed; no required platform is skipped")
        properties = {}
        for name, api in (("android-36", "36"), ("android-37.0", "37.0")):
            path = sdk / "platforms" / name / "source.properties"
            content = path.read_text(encoding="utf-8")
            require(re.search(r"^AndroidVersion\.ApiLevel\s*=\s*" + re.escape(api) + r"\s*$", content, re.M),
                    "Wrong Android platform metadata: " + name)
            properties[name] = {"sha256": digest(path), "content": content}
        self.write("android-platforms.json", properties)

    def windows(self):
        require(self.windows_shell is not None, "Windows shell prerequisite has not passed")
        self.invoke("wrapper-checkouts", [self.windows_shell["bash"], "scripts/tests/check-gradle-wrapper-test.sh"],
                    kind="command", extra_env={"PATH": self.windows_shell["PATH"]})
        token = uuid.uuid4().hex
        success = self.invoke("windows-libraries", [*sorted(WINDOWS_TASKS), "--continue", "--init-script",
                               str(ROOT / "gradle/platform-test-coverage.init.gradle"),
                               "-Pp2pkit.testCoverageRoot=" + str(ROOT), "-Pp2pkit.testCoverageToken=" + token])
        if success:
            gate = load_gate()
            self.check("windows-execution", lambda: assess_windows(
                gate.read_json(ROOT / "build/reports/platform-tests" / token / "execution.json"),
                gate.read_json(ROOT / "gradle/platform-test-policy.json"), token))
        self.clean_outputs()
        self.invoke("windows-desktop-samples", [
            *DESKTOP_TASKS,
            ":p2p-core:downloadKotlinNativeDistribution",
            ":p2p-sample-android:assembleDebug",
            "--continue",
        ])
        self.clean_outputs()

    def windows_followup(self):
        """Seven core diagnostic caller classes, not full Windows qualification."""
        token = uuid.uuid4().hex
        success = self.invoke("windows-followup", [
            ":p2p-core:jvmTest", "--tests", "dev.p2pkit.core.internal.KitLifecycleTest",
            "--tests", "dev.p2pkit.core.internal.NetworkProvisioningCloseTest",
            "--tests", "dev.p2pkit.core.internal.TransportCapabilityTest",
            "--tests", "dev.p2pkit.core.internal.KitStrictInvariantsTest",
            "--tests", "dev.p2pkit.core.internal.PermissionGateTest",
            "--tests", "dev.p2pkit.core.PublicConfigurationValidationTest",
            "--tests", "dev.p2pkit.core.PublicModelImmutabilityTest",
            "--continue", "--init-script", str(ROOT / "gradle/platform-test-coverage.init.gradle"),
            "-Pp2pkit.testCoverageRoot=" + str(ROOT), "-Pp2pkit.testCoverageToken=" + token,
        ])
        if success:
            gate = load_gate()
            self.check("windows-followup-execution", lambda: assess_windows(
                gate.read_json(ROOT / "build/reports/platform-tests" / token / "execution.json"),
                gate.read_json(ROOT / "gradle/platform-test-policy.json"), token, WINDOWS_FOLLOWUP_TASKS))
        self.clean_outputs()

    def windows_diagnostics(self):
        """Only the affected strict LAN diagnostic callers, not full Windows qualification."""
        token = uuid.uuid4().hex
        success = self.invoke("windows-diagnostics", [
            ":p2p-transport-lan:jvmTest", "--tests", "dev.p2pkit.transport.lan.JvmLanAcceptLoopResilienceTest",
            "--tests", "dev.p2pkit.transport.lan.JvmLanAdmissionControlTest",
            "--continue", "--init-script", str(ROOT / "gradle/platform-test-coverage.init.gradle"),
            "-Pp2pkit.testCoverageRoot=" + str(ROOT), "-Pp2pkit.testCoverageToken=" + token,
        ])
        if success:
            gate = load_gate()
            self.check("windows-diagnostics-execution", lambda: assess_windows(
                gate.read_json(ROOT / "build/reports/platform-tests" / token / "execution.json"),
                gate.read_json(ROOT / "gradle/platform-test-policy.json"), token, WINDOWS_DIAGNOSTICS_TASKS))
        self.clean_outputs()

    def mac_policies(self):
        if self.scope in ("apple-followup", "apple-owned-cancellation"):
            # Reuse unaffected source-bound policy results; native executor admission still runs above.
            return
        # Preserve release-gate ordering; no no-op replacement of real graph/native probes.
        scripts = ["scripts/check-gradle-wrapper.sh", "scripts/check-dependency-verification.sh",
                   "scripts/tests/check-dependency-update-policy-test.sh", "scripts/tests/check-lock-write-policy-test.sh",
                   "scripts/tests/check-repository-layout.sh", "scripts/tests/check-osv-lockfile-coverage.sh",
                   "scripts/tests/check-markdown-links.sh", "scripts/tests/classify-ci-scope-test.sh",
                   "scripts/tests/resolve-ci-scope-test.sh", "scripts/tests/check-ci-scope-policy-test.rb",
                   "scripts/tests/check-git-whitespace-test.sh", "scripts/tests/check-release-identity-test.sh",
                   "scripts/tests/check-kotlin-toolchain-policy-test.sh", "scripts/check-android-abi-guard.sh",
                   "scripts/tests/check-platform-test-policy-test.rb", "scripts/tests/run-platform-tests-test.py",
                   "scripts/check-release-metadata.sh", "scripts/check-git-whitespace.sh",
                   "scripts/tests/ios-project-generation-test.py",
                   "scripts/tests/check-gradle-wrapper-test.sh", "scripts/tests/check-release-tag-test.sh",
                   "scripts/tests/check-maven-release-environment-test.sh", "scripts/tests/check-maven-namespace-access-test.sh",
                   "scripts/tests/check-maven-central-version-test.sh", "scripts/tests/publish-central-portal-bundle-test.sh",
                   "scripts/tests/build-central-portal-bundle-test.sh", "scripts/tests/install-xcodegen-test.sh",
                   "scripts/tests/release-workflow-test.sh", "scripts/tests/check-sample-run-profiles.sh",
                   "scripts/tests/run-ios-app-test.sh", "scripts/tests/audit-leaf-hooks-test.py",
                   "scripts/tests/audit-consumer-test.py", "scripts/tests/audit-host-test.py",
                   "scripts/tests/audit-host-workflow-test.py", "scripts/tests/swift-jvm-transfer-test.py"]
        native_policies = ("scripts/tests/check-lock-write-policy-test.sh", "scripts/check-android-abi-guard.sh")
        for number, path in enumerate(scripts):
            if self.scope == "apple-provenance" and path not in native_policies:
                continue  # Keep original labels/order for the two pending real graph probes.
            tool = sys.executable if path.endswith(".py") else "ruby" if path.endswith(".rb") else "bash"
            # Default fake-boundary suites must not inherit real opt-in leaves
            # against their fake source trees. Retain the outer ownership chain.
            env = None if path in native_policies else {key: None for key in ADAPTER_OPT_INS}
            self.invoke("policy-" + str(number) + "-" + Path(path).stem, [tool, path], kind="command", extra_env=env)
            self.clean_outputs()

    def install_xcodegen(self):
        destination = self.state / "work/xcodegen"
        destination.parent.mkdir(parents=True, exist_ok=True)
        require(not destination.exists(), "XcodeGen installation directory is not fresh")
        if not self.invoke("xcodegen-install", ["bash", "scripts/install-xcodegen.sh", str(destination)], kind="command"):
            raise ValueError("Pinned XcodeGen installation failed")
        # Installer's contract returns a directory; select exactly one actual tool, not arbitrary stdout text.
        bins = [path for path in strict_files(destination) if path.name == "xcodegen" and os.access(path, os.X_OK)]
        require(len(bins) == 1, "Pinned installer did not produce exactly one executable XcodeGen")
        self.environment["PATH"] = str(bins[0].parent) + os.pathsep + self.environment["PATH"]

    def inspect_tcp_options_headers(self):
        """Retain the selected iOS SDK declarations, not inferred Apple socket behavior."""
        self.assert_owned_state()
        require(self.role == "macos-arm64" and self.scope == "full", "SDK inspection requires the full Apple role")
        developer = Path(self.environment["DEVELOPER_DIR"])
        require(developer.is_absolute(), "Selected Xcode developer directory is not absolute")
        developer = physical(developer.resolve(strict=True))
        require(developer.is_dir(), "Selected Xcode developer directory is unavailable")
        prerequisite = physical(self.evidence / "prerequisites.json")
        require(prerequisite.is_file(), "Missing retained selected-Xcode prerequisites")
        bindings = []
        for sdk in ("iphoneos", "iphonesimulator"):
            prefix = "apple-sdk-" + sdk
            metadata = {}
            for field, flag in (("path", "--show-sdk-path"), ("version", "--show-sdk-version"),
                                ("build", "--show-sdk-build-version")):
                output = self.inspect_tool(prefix + "-" + field, ["xcrun", "--sdk", sdk, flag])
                with output.open("rb") as stream:
                    raw = stream.read(4097)
                require(0 < len(raw) <= 4096, "SDK metadata exceeds its bound or is empty")
                lines = raw.decode("utf-8").splitlines()
                require(len(lines) == 1 and lines[0].strip() and "\0" not in lines[0], "Malformed SDK metadata")
                metadata[field] = {"value": lines[0].strip(), "path": output.relative_to(self.evidence).as_posix(),
                                   "sha256": digest(output)}
            requested = Path(metadata["path"]["value"])
            require(requested.is_absolute(), "Selected SDK path is not absolute")
            sdk_root = physical(requested.resolve(strict=True))
            require(sdk_root.is_dir() and sdk_root != developer and sdk_root.is_relative_to(developer),
                    "SDK is outside the selected Xcode developer directory")
            # Installed SDK/framework aliases are read-only inputs, not owned outputs.
            # Resolve them only within the selected SDK; never traverse an arbitrary header tree.
            location = sdk_root / "System/Library/Frameworks/Network.framework/Headers/tcp_options.h"
            header = physical(location.resolve(strict=True))
            require(header.is_relative_to(sdk_root) and header.is_file(), "TCP header is outside the selected SDK")
            size = header.stat().st_size
            require(0 < size <= 1024 ** 2, "TCP header exceeds its bound or is empty")
            with header.open("rb") as stream:
                raw = stream.read(1024 ** 2 + 1)
            require(len(raw) == size, "TCP header changed size during inspection")
            checksum = hashlib.sha256(raw).hexdigest()
            retained = physical(self.evidence / (prefix + "-tcp_options.h.log"))
            with retained.open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            require(physical(location.resolve(strict=True)) == header and digest(retained) == checksum,
                    "TCP header path or retained bytes changed during inspection")
            with header.open("rb") as stream:
                require(stream.read(1024 ** 2 + 1) == raw, "TCP header changed during retention")
            name = prefix + "-tcp-options-binding.json"
            self.write(name, {"result": "INSPECTED", "inspectionOnly": True, "source": self.admission,
                       "observedUtc": now(), "developerDirectory": str(developer), "sdk": sdk, "metadata": metadata,
                       "prerequisites": {"path": prerequisite.name, "sha256": digest(prerequisite)},
                       "sdkRoot": str(sdk_root), "headerPath": str(location), "resolvedHeaderPath": str(header),
                       "retainedPath": retained.name, "sha256": checksum, "bytes": size,
                       "limits": "Verbatim selected-SDK declarations; not compilation, socket behavior, latency or issue acceptance."})
            bindings.append({"path": name, "sha256": digest(self.evidence / name)})
        return {"bindings": bindings, "limits": "Inspection only; review both original SDK headers before API claims."}

    def inspect_intel_simulators(self):
        """Check the actual read-only inventory before Intel product builds, never boot a device."""
        require(self.role == "macos-x64", "Intel simulator inventory requires the native Intel role")
        runtime_path = self.inspect_tool("intel-simulator-runtimes",
                                         ["xcrun", "simctl", "list", "--json", "runtimes"])
        device_path = self.inspect_tool("intel-simulator-devices",
                                        ["xcrun", "simctl", "list", "--json", "devices", "available"])
        runtimes, devices = read_json(runtime_path).get("runtimes"), read_json(device_path).get("devices")
        require(type(runtimes) is list and type(devices) is dict, "Missing actual Intel simulator inventory")
        require(all(type(runtime) is dict and type(runtime.get("identifier")) is str for runtime in runtimes),
                "Malformed Intel simulator runtime inventory")
        available = {runtime["identifier"] for runtime in runtimes
                     if re.search(r"\.SimRuntime\.iOS-[0-9-]+$", runtime["identifier"]) and
                     runtime.get("isAvailable") is True}
        candidates = []
        for runtime, entries in devices.items():
            if runtime not in available:
                continue
            require(type(entries) is list and all(type(device) is dict for device in entries),
                    "Malformed available Intel simulator devices")
            for device in entries:
                if device.get("name") == "iPhone 17" and device.get("isAvailable") is not False:
                    udid, state = device.get("udid"), device.get("state")
                    require(type(udid) is str and
                            re.fullmatch(r"[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}", udid) and
                            state in ("Booted", "Shutdown"), "Invalid Intel simulator device metadata")
                    candidates.append({"runtime": runtime, "udid": udid, "state": state})
        require(candidates, "No available iOS runtime with an exact iPhone17 simulator; product builds are NOT_EXECUTED")
        return {"availableCandidates": candidates,
                "limits": "Inventory only, not boot, x86_64 execution or qualification; Apple execution revalidates its exact device."}

    def mac(self):
        if self.scope == "apple-native-compilation":
            self.invoke("413-native-compilation-admission",
                        [":p2p-transport-lan:compileTestKotlinIosSimulatorArm64"])
            return
        if self.scope == "full":
            self.check("apple-tcp-options-sdk", self.inspect_tcp_options_headers)
        self.install_xcodegen()
        self.mac_policies()
        if self.scope == "apple-owned-cancellation":
            # One real generation setup checks the additive app source and retained test containers.
            self.invoke("owned-flow-project-generation", [sys.executable,
                        "scripts/tests/ios-project-generation-test.py",
                        "IosProjectGenerationTest.test_owned_flow_sources_use_existing_test_containers",
                        "IosProjectGenerationTest.test_ui_and_release_callers_preserve_both_test_targets",
                        "IosProjectGenerationTest.test_cancellation_probe_is_excluded_from_both_acceptance_schemes",
                        "IosProjectGenerationTest.test_generation_preserves_provenance_and_local_network_declarations"],
                        kind="command", extra_env={key: None for key in ADAPTER_OPT_INS})
            self.clean_outputs()
            self.owned_flow_native()
            self.clean_outputs()
            # A finalized helper/ABI failure stays failed, but must not suppress
            # independent fresh-producer/Swift evidence. Ownership, stop, source
            # or cleanup exceptions still escape before reaching this chain.
            self.apple()
            return
        if self.scope == "apple-provenance":
            # All policy graphs/cleanup finish before the one retained fresh framework producer.
            self.apple()
            return
        profile = "ios-lan-arm64" if self.scope == "apple-followup" else "full"
        self.invoke("mac-platform-" + profile, [sys.executable, "scripts/run-platform-tests.py", profile],
                    kind="command", timeout=7200)
        self.clean_outputs()
        if self.scope == "full":
            # The full check already runs all four Kotlin and three Android ABI
            # compares. Inspect their actual task outcomes in that leaf's raw log;
            # platform execution.json inventories test tasks, not ABI execution.
            # Prepare installDist once immediately before its live Swift counterpart.
            artifacts = [":p2p-sample-android:assembleDebug",
                         *[task for task in DESKTOP_TASKS if task != ":p2p-sample-desktop:installDist"],
                         *[":" + module + ":dokkaGeneratePublicationHtml" for module in MODULES],
                         "cyclonedxBom", "--continue"]
            if self.invoke("mac-artifact-build", artifacts):
                self.invoke("sbom-inspect", ["bash", "scripts/check-sbom.sh", "build/reports/cyclonedx/bom.json",
                                             "build/reports/cyclonedx/bom.xml"], kind="command")
            self.clean_outputs()
        self.isolated_consumers()
        self.clean_outputs()
        # Retain the real CLI distribution until its live Swift counterpart has finished.
        self.invoke("swift-jvm-cli-prepare", [":p2p-sample-desktop:installDist"])
        # Receipt/helper manifests are copied by finalize(); preserve failed fixtures until that copy, too.
        self.apple()

    def owned_flow_native(self):
        """One fresh helper/ABI leaf; retain and assess its exact reports before cleanup."""
        token = uuid.uuid4().hex
        label, prefix = "owned-flow-helper-abi", "owned-flow-native"
        try:
            require(self.role == "macos-arm64" and self.scope == "apple-owned-cancellation",
                    "Owned native helper requires its explicit ARM scope")
            udid = self.select_simulator(prefix + "-before")
            self.write(prefix + "-admission.json", {
                "source": self.admission, "task": OWNED_NATIVE_TASK, "udid": udid,
                "stateBefore": self.simulator["stateBefore"], "nativeInvocationReceipt": "host-" + label + ".json",
                "initialStateObservation": prefix + "-before.stdout.log",
                "requiredRetirementObservations": [prefix + "-retire-before.stdout.log", prefix + "-retire-after.stdout.log"],
                "limits": "Exact device state only; not shared CoreSimulator service termination or native case success.",
            })
        except BaseException:
            self.safe = False
            raise
        try:
            tested = self.invoke(label, [OWNED_NATIVE_TASK, "--device", udid, "--tests", OWNED_NATIVE_CLASS,
                                ":p2p-transport-lan:checkKotlinAbi", "--continue", "--init-script",
                                str(ROOT / "gradle/platform-test-coverage.init.gradle"),
                                "-Pp2pkit.testCoverageRoot=" + str(ROOT), "-Pp2pkit.testCoverageToken=" + token])
        finally:
            # KGP receives this exact owned device; even a failed/interrupted
            # standalone spawn must be retired before any producer can begin.
            finalizing = self.finalizing
            self.finalizing = True
            try:
                self.shutdown_simulator(label=prefix + "-retire")
                require(self.simulator.get("udid") == udid and self.simulator.get("stateAfter") == "Shutdown",
                        "Owned native helper simulator retirement is not proven")
            except BaseException:
                self.safe = False
                raise
            finally:
                self.finalizing = finalizing
        def inspect():
            require(tested is True, "Native helper/ABI invocation failed; no helper or ABI completion is awarded")
            receipt = self.receipts[label]
            directory = Path(receipt["evidenceDirectory"])
            def retained(source):
                rows = [row for row in receipt["reports"] if row["source"] == source]
                require(len(rows) == 1 and rows[0]["classification"] == "changed-since-admission",
                        "Missing fresh retained native helper report: " + source)
                row = rows[0]
                path = physical(directory / row["retained"])
                require(path.is_relative_to(directory) and path.is_file() and
                        path.stat().st_size == row["bytes"] and digest(path) == row["sha256"],
                        "Native helper report differs from its finalized receipt")
                return path
            prefix = "library/p2p-transport-lan/build/test-results/iosSimulatorArm64Test/TEST-"
            xml_source = prefix + "iosSimulatorArm64Test." + OWNED_NATIVE_CLASS + ".xml"
            require([row["source"] for row in receipt["reports"]
                    if row["source"].startswith(prefix) and row["source"].endswith(".xml")] == [xml_source],
                    "Unexpected native test-class XML in the focused invocation")
            execution = retained("build/reports/platform-tests/" + token + "/execution.json")
            xml = retained(xml_source)
            with xml.open("rb") as stream:
                junit = stream.read(1024 ** 2 + 1)
            result = assess_owned_native(read_json(execution),
                                         read_json(ROOT / "gradle/platform-test-policy.json"), token, junit)
            # These actual aggregate task names are observed in native Gradle logs,
            # not invented per-target compares. Keep all compiler/compare log context.
            abi = ["> Task :p2p-transport-lan:" + name for name in (
                "iosArm64MainKlibrary", "iosSimulatorArm64MainKlibrary", "iosX64MainKlibrary",
                "internalDumpKotlinAbi", "checkKotlinAbi")]
            with physical(directory / "product.stdout.log").open(encoding="utf-8") as stream:
                lines = [line.rstrip("\r\n") for line in stream if line.startswith("> Task :p2p-transport-lan:")]
            require(all(lines.count(task) == 1 for task in abi), "Fresh native ABI dump/compare execution is missing")
            return {**result, "token": token, "invocationId": receipt["id"], "source": self.admission,
                    "executionSha256": digest(execution), "junitSha256": digest(xml), "abiTasks": abi,
                    "productLogSha256": digest(directory / "product.stdout.log"),
                    "limits": "Focused ARM helper and LAN ABI only; no whole-host or physical qualification."}
        return self.check("owned-flow-helper-execution", inspect)

    def isolated_consumers(self):
        # One source-local publisher also supplies the independent archive gate.
        # A later consumer compile failure does not invalidate its successful receipt.
        consumer = self.state / "work/consumer"
        self.invoke("isolated-consumers", ["bash", "scripts/check-published-consumers.sh"],
                    kind="command", timeout=7200,
                    extra_env={"P2PKIT_CONSUMER_WORK_DIR": str(consumer), "P2PKIT_CONSUMER_AUDIT_METADATA": "1"})
        try:
            if self.consumer_publication_ready(consumer):
                self.invoke("consumer-publication-inspect", ["bash", "scripts/check-publish-artifacts.sh",
                                                              str(consumer / "repository")], kind="command")
        finally:
            if (consumer / "repository").is_dir():
                self.retain_publication(consumer / "repository", "consumer-publication")
            self.retain_consumer_framework(consumer)

    def consumer_publication_ready(self, consumer):
        outer = self.receipts["isolated-consumers"]
        candidates = sorted(self.state.glob("consumer-receipts.*/consumer-publish.json"))
        if not candidates:
            require(outer["finalExitCode"] != 0, "Successful consumer lacks its publisher receipt")
            self.write("consumer-publication-prerequisite.json", {"result": "NOT_EXECUTED",
                       "reason": "No finalized publisher receipt; no partial repository is trusted"})
            return False
        require(len(candidates) == 1, "Ambiguous consumer publisher receipts")
        receipt = candidates[0]
        record = read_json(receipt)
        arguments = ["--no-daemon", "--console=plain", "publishToMavenLocal",
                     "-Dmaven.repo.local=" + str(consumer / "repository")]
        # Reuse the complete nested-leaf checker, including source, stop, drain,
        # original argv, canonical copies and retained reports. Invalid finalization
        # stops this host rather than allowing another product build.
        self.validate_receipt(record, record.get("finalExitCode"), record.get("id"), "consumer-publish",
                              "gradle", arguments, receipt)
        require(record.get("ancestorInvocationIds") == [*outer["ancestorInvocationIds"], outer["id"]],
                "Publisher is not the exact isolated-consumer descendant")
        admission = read_json(receipt.parent / "consumer-admission.json")
        require(admission.get("source") == self.context["source"] and
                admission.get("workDir") == str(consumer) and
                admission.get("repository") == str(consumer / "repository") and
                admission.get("publicationReceipt") == str(receipt) and
                admission.get("repositoryInitiallyAbsent") is True,
                "Publisher repository was not admitted empty for this source and work root")
        ready = record["finalExitCode"] == 0
        require(ready or outer["finalExitCode"] != 0, "Successful consumer has a failed publisher")
        require(not ready or physical(consumer / "repository").is_dir(), "Successful publisher repository is absent")
        self.write("consumer-publication-prerequisite.json", {"result": "PASS" if ready else "NOT_EXECUTED",
                   "publisherInvocationId": record["id"], "publisherExitCode": record["finalExitCode"],
                   "publisherReceiptSha256": digest(receipt), "consumerExitCode": outer["finalExitCode"],
                   "limits": "Publisher prerequisite only, not consumer or archive acceptance"})
        return ready

    def retain_consumer_framework(self, consumer):
        # The unchanged consumer gate captures vtool in a shell variable. Keep an
        # additional hash-bound native inspection before disposing its binary.
        # This is read-only evidence, not a replacement for its original checks.
        binary = consumer / "consumer/kmpConsumer/build/bin/iosSimulatorArm64/debugFramework/P2pKitConsumer.framework/P2pKitConsumer"
        self.retain_native_binary("consumer-framework", binary, self.receipts["isolated-consumers"]["id"])

    def retain_native_binary(self, label, binary, invocation):
        physical(binary)
        binding = {"path": str(binary), "source": self.admission, "observedUtc": now(),
                   "sourceInvocationId": invocation,
                   "limitation": "Supplemental post-command inspection, not its original captured stream, physical or independent acceptance."}
        if not binary.exists():
            self.write(label + "-binding.json", {**binding, "result": "NOT_EXECUTED", "reason": "binary absent"})
            return
        require(binary.is_file(), "Framework binary is not a regular file")
        before = digest(binary)
        outputs = {}
        for tool, flags in (("vtool", "-show-build"), ("lipo", "-archs")):
            output = self.inspect_tool(label + "-" + tool, ["xcrun", tool, flags, str(binary)])
            outputs[tool] = {"path": output.relative_to(self.evidence).as_posix(), "sha256": digest(output)}
        require(digest(binary) == before, "Binary changed during native evidence inspection")
        self.write(label + "-binding.json", {**binding, "result": "INSPECTED", "sha256": before,
                   "bytes": binary.stat().st_size, "nativeInspections": outputs})

    def retain_xcframework_header(self, label, header, invocation):
        """Preserve one generated Objective-C header before dependent builds/cleanup."""
        self.assert_owned_state()
        require(re.fullmatch(r"[a-z0-9-]+", label), "Unsafe generated-header evidence label")
        header = physical(header)
        require(header.is_file(), "Generated Objective-C header is not a regular file")
        size = header.stat().st_size
        require(0 < size <= 1024 ** 2, "Generated Objective-C header exceeds its bound or is empty")
        with header.open("rb") as stream:
            raw = stream.read(1024 ** 2 + 1)
        require(len(raw) == size, "Generated Objective-C header changed size during inspection")
        checksum = hashlib.sha256(raw).hexdigest()
        retained = physical(self.evidence / (label + ".h.log"))
        require(retained.parent == self.evidence, "Generated-header evidence is not an exact basename")
        with retained.open("xb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        require(digest(retained) == checksum, "Retained generated Objective-C header changed")
        require(physical(header).is_file(), "Generated Objective-C header is no longer regular")
        with header.open("rb") as stream:
            require(stream.read(1024 ** 2 + 1) == raw, "Generated Objective-C header changed during retention")
        return {"source": self.admission, "sourceInvocationId": invocation, "observedUtc": now(),
                "headerPath": str(header), "retainedPath": retained.name, "sha256": checksum, "bytes": size,
                "limits": "Verbatim generated declaration observation, not Swift bridge execution or issue acceptance."}

    def retain_publication(self, publication, label):
        rows = []
        for parent, directories, files in strict_walk(physical(publication)):
            for name in [*directories, *files]:
                physical(Path(parent) / name)
            for name in sorted(files):
                path = Path(parent) / name
                require(path.is_file(), "Publication contains a nonregular artifact")
                rows.append({"path": path.relative_to(publication).as_posix(), "sha256": digest(path),
                             "bytes": path.stat().st_size})
        copied = self.retain_tree(publication, self.evidence / (label + "-metadata"),
                                  selected=lambda path: path.suffix in (".pom", ".module", ".xml"))
        self.write(label + "-manifest.json", {"artifacts": rows, "retainedMetadata": copied,
                   "limits": "Hashes/metadata are not independent artifact or runtime acceptance."})

    def remove_work(self, path):
        self.assert_owned_state()
        work = physical(self.state / "work")
        require(self.work_identity == self.identity(work) and path.is_relative_to(work),
                "Work output is not under this driver's newly created work root")
        physical(path)
        # rmtree removes links themselves without following them. Before removal,
        # required non-link evidence has already been copied and hash-checked.
        require(path.is_dir() and path != work, "Expected an explicit child work directory")
        shutil.rmtree(path)

    def apple(self):
        built = self.invoke("xcframework-build", [":p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance"], timeout=7200)
        inspected = built and self.invoke("xcframework-inspect",
                                          ["bash", "scripts/check-xcframework-minimum-os.sh"], kind="command")
        release = physical(ROOT / "library/p2p-transport-lan/build/XCFrameworks/release")
        sidecars = []
        for name in ("BUILD_COMMIT.txt", "BUILD_SOURCE_STATE.txt", "BUILD_INPUTS_SHA256.txt", "BUILD_ARTIFACTS_SHA256.txt"):
            path = physical(release / name)
            if not path.exists():
                sidecars.append({"path": name, "result": "MISSING"})
                continue
            require(path.is_file(), "XCFramework sidecar is not regular")
            before = digest(path)
            with path.open("rb") as incoming, physical(self.evidence / name).open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
            require(digest(self.evidence / name) == before == digest(path), "XCFramework sidecar changed during retention")
            sidecars.append({"path": name, "sha256": before, "result": "RETAINED"})
        self.write("xcframework-sidecars.json", {"files": sidecars, "sourceInvocationId": self.receipts["xcframework-build"]["id"]})
        headers_ok = True
        for name, identifier in (("device", "ios-arm64"), ("simulator", "ios-arm64_x86_64-simulator")):
            binary = release / "P2pKitShared.xcframework" / identifier / "P2pKitShared.framework/P2pKitShared"
            label = "xcframework-" + name + "-header"
            headers_ok = self.check(label, lambda: self.retain_xcframework_header(
                label, binary.parent / "Headers/P2pKitShared.h", self.receipts["xcframework-build"]["id"])) and headers_ok
            self.retain_native_binary("xcframework-" + name, binary, self.receipts["xcframework-build"]["id"])
        strict_reuse = self.scope in ("apple-provenance", "apple-owned-cancellation")
        if not built or (strict_reuse and not (inspected and headers_ok)):
            return
        if not self.invoke("xcode-project", [":iosApp:regenerateXcodeProject"]):
            return
        if strict_reuse:
            task = ":p2p-transport-lan:verifyP2pKitSharedReleaseXCFrameworkProvenance"
            if not self.invoke("xcode-provenance", [task, "--console=plain"], timeout=900):
                return
            def inspect_reuse():
                record = self.receipts["xcode-provenance"]
                reuse, executed = record.get("xcframeworkReuse"), record.get("executedArgv")
                require(type(reuse) is dict and record.get("xcframeworkReuseUnchanged") is True and
                        reuse.get("producerInvocationId") == self.receipts["xcframework-build"]["id"],
                        "Visible verifier lacks unchanged same-producer reuse proof")
                require(type(executed) is list and executed[:3] == [str(self.wrapper), task, "--console=plain"] and
                        "--rerun-tasks" not in executed, "Visible verifier did not use the exact incremental lane")
                return {"verifierInvocationId": record["id"], "reuse": reuse,
                        "limits": "Receipt binding only; inspect retained Gradle task outcomes for actual incremental reuse."}
            if not self.check("xcframework-reuse-receipt", inspect_reuse):
                return
        else:
            build_dir = self.state / "work/swift-build"
            build_ok = self.invoke("swift-warnings-build", ["xcodebuild", "-jobs", "2", "-project",
                                   "samples/iosApp/p2pkit-sample.xcodeproj", "-scheme", "p2pkit-sample-ui", "-configuration",
                                   "Debug", "-sdk", "iphonesimulator", "-destination", "generic/platform=iOS Simulator",
                                   "-derivedDataPath", str(build_dir), "CODE_SIGNING_ALLOWED=NO",
                                   "SWIFT_TREAT_WARNINGS_AS_ERRORS=YES", "build"], kind="command", timeout=7200)
            if not build_ok:
                return
            def require_marker():
                directory = Path(self.receipts["swift-warnings-build"]["evidenceDirectory"])
                found = False
                for name in ("product.stdout.log", "product.stderr.log"):
                    with physical(directory / name).open("rb") as stream:
                        found = found or any(b"** BUILD SUCCEEDED **" in line for line in stream)
                require(found, "xcodebuild returned zero without the original required BUILD SUCCEEDED marker")
                return {"leaf": self.receipts["swift-warnings-build"]["id"], "marker": "** BUILD SUCCEEDED **"}
            if not self.check("swift-build-marker", require_marker):
                return
        udid = self.select_simulator()
        ui_dir = self.state / "work/swift-ui"
        if self.scope == "apple-owned-cancellation":
            self.swift_owned_flow_lifecycle(ui_dir, udid)
            # An ordinary lifecycle assertion failure stays failed; after proved
            # retirement the independent actual-flow cancellation case may run last.
            self.swift_cancellation_probe(ui_dir, udid, owned=True)
            return
        if self.scope == "apple-provenance":
            self.swift_cancellation_probe(ui_dir, udid)
            return
        tested = self.invoke("swift-unit-ui", ["bash", "scripts/run-ios-ui-tests.sh"], kind="command", timeout=7200,
                             extra_env={"IOS_RUN_DIR": str(ui_dir), "KEEP_IOS_RUN_ARTIFACTS": "1", "SIM_UDID": udid})
        bundles = sorted(ui_dir.glob("DerivedData/Logs/Test/*.xcresult"))
        objects = []
        for index, bundle in enumerate(bundles):
            # Copy first, including failed xcresults. Inspection/parser failure
            # cannot erase the native result bundle or its raw diagnostic output.
            manifest = self.retain_tree(bundle, self.evidence / "swift-xcresult" / bundle.name)
            self.write("swift-bundle-" + str(index) + ".json", {"path": str(bundle), "files": manifest})
            first = self.inspect_tool("swift-actions-" + str(index),
                                      ["xcrun", "xcresulttool", "get", "object", "--legacy", "--format", "json", "--path", str(bundle)])
            action = load_gate().read_json(first)
            identifiers = {item["actionResult"]["testsRef"]["id"]["_value"]
                           for item in action.get("actions", {}).get("_values", [])
                           if "testsRef" in item.get("actionResult", {})}
            for ordinal, identifier in enumerate(sorted(identifiers)):
                details = self.inspect_tool(f"swift-tests-{index}-{ordinal}",
                                             ["xcrun", "xcresulttool", "get", "object", "--legacy", "--format", "json",
                                              "--path", str(bundle), "--id", identifier])
                objects.append(load_gate().read_json(details))
        if tested and self.check("swift-case-execution", lambda: assess_swift(objects)):
            self.swift_jvm_transfer(ui_dir, udid)
        # Investigation stays last and separate from both acceptance processes.
        # A cleaned integration/product failure must not erase independent evidence.
        if (self.role, self.scope) in CANCELLATION_PROBE_ROUTES:
            self.swift_cancellation_probe(ui_dir, udid)

    def swift_jvm_transfer(self, ui_dir, udid):
        # Only one JVM peer and one XCTest coexist, after all builds have ended
        # and the existing executor has stopped their task-isolated Gradle home.
        prepared = self.receipts.get("swift-jvm-cli-prepare")
        require(prepared is not None, "Real CLI preparation receipt is missing")
        if prepared.get("finalExitCode") != 0:
            return
        environment = {"IOS_RUN_DIR": str(ui_dir), "KEEP_IOS_RUN_ARTIFACTS": "1", "SIM_UDID": udid}
        if not self.invoke("swift-jvm-ui-prepare", ["bash", "scripts/run-ios-ui-tests.sh", "prepare-jvm-transfer"],
                           kind="command", timeout=3600, extra_env=environment):
            return
        tested = self.invoke("swift-jvm-transfer", ["bash", "scripts/run-ios-ui-tests.sh", "run-jvm-transfer"],
                             kind="command", timeout=900, extra_env=environment)
        bundles = sorted(ui_dir.glob("DerivedData/Logs/Test/swift-jvm-transfer-*.xcresult"))
        for index, bundle in enumerate(bundles):
            manifest = self.retain_tree(bundle, self.evidence / "swift-xcresult" / bundle.name)
            self.write("swift-jvm-bundle-" + str(index) + ".json", {"path": str(bundle), "files": manifest})
        if tested:
            def inspect_result():
                result = read_json(ui_dir / "jvm-transfer/result.json")
                case = ("p2pkit-sample-jvm-transfer-tests/SwiftJvmTransferUITests/"
                        "testBidirectionalSecure204800ByteTransferWithJvmPeer()")
                require(len(bundles) == 1 and result.get("schema") == 1 and result.get("result") == "PASS" and
                        result.get("source") == self.context["source"] and result.get("case") == case and
                        result.get("nativeCase") == {"identifier": case, "status": "Success"} and
                        result.get("resultBundle") == str(bundles[0].relative_to(ui_dir / "DerivedData")),
                        "Missing source-bound exact native Swift/JVM case")
                transfers = result.get("transfers", [])
                require(len(transfers) == 2 and {row.get("direction") for row in transfers} ==
                        {"swift-to-jvm", "jvm-to-swift"} and len({row.get("transferId") for row in transfers}) == 2 and
                        all(row.get("bytes") == 204800 and re.fullmatch(r"[0-9a-f]{64}", row.get("sha256", "")) and
                            row.get("sender", {}).get("events") and row.get("receiver", {}).get("events")
                            for row in transfers) and not result.get("cleanupErrors") and not result.get("unresolvedChildren"),
                        "Missing genuine bidirectional integrity or graceful cleanup results")
                return result
            self.check("swift-jvm-case-integrity", inspect_result)

    def swift_owned_flow_lifecycle(self, ui_dir, udid):
        """Only the three owned-flow/lifecycle classes, with failed raw evidence retained."""
        require(self.role == "macos-arm64" and self.scope == "apple-owned-cancellation" and
                self.simulator and self.simulator.get("udid") == udid and
                self.simulator.get("stateBefore") == "Shutdown", "Owned lifecycle simulator is not admitted")
        prefix = "swift-owned-flow-lifecycle"
        bundle = ui_dir / ("DerivedData/Logs/Test/" + prefix + ".xcresult")
        require(not bundle.exists(), "Owned lifecycle result path is not fresh")
        tested = None
        try:
            tested = self.invoke(prefix + "-invocation", ["bash", "scripts/run-ios-ui-tests.sh", "run-owned-flow-lifecycle"],
                                 kind="command", timeout=7200,
                                 extra_env={"IOS_RUN_DIR": str(ui_dir), "KEEP_IOS_RUN_ARTIFACTS": "1", "SIM_UDID": udid})
        finally:
            # Also retire on interruption, when the outer safe flag cannot authorize
            # generic finalizer cleanup. This exact device was originally Shutdown.
            finalizing = self.finalizing
            self.finalizing = True
            try:
                self.shutdown_simulator(label=prefix + "-retire")
                require(self.simulator.get("stateAfter") == "Shutdown", "Owned lifecycle host retirement is not proven")
            except BaseException:
                self.safe = False
                raise
            finally:
                self.finalizing = finalizing
                if bundle.is_dir():
                    files = self.retain_tree(bundle, self.evidence / "swift-xcresult" / bundle.name)
                    self.write(prefix + "-bundle.json", {"path": str(bundle), "files": files})
        def inspect():
            require(bundle.is_dir(), "Owned lifecycle invocation has no raw xcresult")
            arguments = ["xcrun", "xcresulttool", "get", "object", "--legacy", "--format", "json", "--path", str(bundle)]
            actions = read_json(self.inspect_tool(prefix + "-actions", arguments))
            identifiers = {item["actionResult"]["testsRef"]["id"]["_value"]
                           for item in actions.get("actions", {}).get("_values", [])
                           if "testsRef" in item.get("actionResult", {})}
            objects = [read_json(self.inspect_tool(prefix + "-tests-" + str(index), arguments + ["--id", identifier]))
                       for index, identifier in enumerate(sorted(identifiers))]
            require(tested is True, "Owned lifecycle invocation failed")
            return assess_swift(objects, selection="owned-flow-lifecycle")
        return self.check(prefix + "-case-execution", inspect)

    def swift_cancellation_probe(self, ui_dir, udid, *, owned=False):
        """One explicit raw/owned host; shutdown is cleanup, never cancellation success."""
        require(type(owned) is bool and ((self.role == "macos-arm64" and self.scope == "apple-owned-cancellation")
                if owned else (self.role, self.scope) in CANCELLATION_PROBE_ROUTES),
                "Cancellation investigation requires an explicit native Apple follow-through route")
        prefix = "swift-owned-cancellation" if owned else "swift-cancellation-probe"
        isolation = "swift-owned-cancellation" if owned else "swift-cancellation"
        action = "run-owned-cancellation" if owned else "run-cancellation-probe"
        case = "p2pkit-sample-cancellation-probe-tests/" + (OWNED_SWIFT_CASE.removesuffix("()") if owned else
                "SwiftFlowCancellationProbeTests/testSwiftTaskCancellationFinishesActualDiagnosticCollection")
        admitted = bool(self.simulator and self.simulator.get("udid") == udid and
                        self.simulator.get("stateBefore") == "Shutdown")
        self.write(prefix + "-admission.json", {
            "source": self.admission, "case": case, "udid": udid,
            "initialStateObservation": "simulators-before.stdout.log",
            "result": "ADMITTED" if admitted else "NOT_EXECUTED",
            "reason": None if admitted else "No exact originally Shutdown simulator is owned; preserve originally Booted/unowned devices",
        })
        if not admitted:
            self.rows.append({"component": prefix + "-admission", "result": "FAIL",
                              "inspectionOnly": True, "investigationOnly": not owned,
                              "reason": "Owned initially Shutdown simulator unavailable"})
            return
        bundle = ui_dir / ("DerivedData/Logs/Test/" + prefix + ".xcresult")
        require(not bundle.exists(), "Cancellation probe result path is not fresh")
        tested, retired = None, False
        try:
            # Positively retire prior acceptance hosts before cold-booting this
            # otherwise reused simulator. No new runtime/device/cache is needed.
            self.shutdown_simulator(label=isolation + "-isolate")
            self.simulator.pop("stateAfter", None)
            tested = self.invoke(prefix + "-invocation",
                                 ["bash", "scripts/run-ios-ui-tests.sh", action],
                                 kind="command", timeout=900,
                                 extra_env={"IOS_RUN_DIR": str(ui_dir), "KEEP_IOS_RUN_ARTIFACTS": "1", "SIM_UDID": udid})
        finally:
            # The existing executor drains its own workers/Gradle home, not an
            # arbitrary launchd-owned simulator app. Use the reserved cleanup
            # interval to prove this exact originally Shutdown device is retired.
            finalizing = self.finalizing
            self.finalizing = True
            try:
                self.shutdown_simulator(label=isolation + "-retire")
                retired = self.simulator.get("stateAfter") == "Shutdown"
                require(retired, "Isolated cancellation test-host retirement is not proven")
            except BaseException:
                self.safe = False
                raise
            finally:
                self.finalizing = finalizing
                files = None
                if bundle.is_dir():
                    files = self.retain_tree(bundle, self.evidence / "swift-xcresult" / bundle.name)
                self.write(prefix + "-result.json", {
                    "source": self.admission, "case": case, "udid": udid,
                    "invocationSucceeded": tested, "ownedSimulatorShutdownObserved": retired,
                    "cancellationVerdict": "SEE_NATIVE_CASE_ASSESSMENT" if owned else "PENDING_NATIVE_EVIDENCE_REVIEW",
                    "resultBundle": str(bundle), "retainedFiles": files,
                    "limits": "Retirement is fallback cleanup, not Flow cancellation or acceptance-suite success.",
                })
        objects = []
        if bundle.is_dir():
            # Retain the actual case tree for root's observation review. Do not
            # create a second acceptance assessor or invert a failing assertion.
            arguments = ["xcrun", "xcresulttool", "get", "object", "--legacy", "--format", "json", "--path", str(bundle)]
            actions = read_json(self.inspect_tool(prefix + "-actions", arguments))
            identifiers = {item["actionResult"]["testsRef"]["id"]["_value"]
                           for item in actions.get("actions", {}).get("_values", [])
                           if "testsRef" in item.get("actionResult", {})}
            for index, identifier in enumerate(sorted(identifiers)):
                details = self.inspect_tool(prefix + "-tests-" + str(index), arguments + ["--id", identifier])
                if owned:
                    objects.append(read_json(details))
        require(tested is not True or bundle.is_dir(), "Successful probe invocation has no raw xcresult")
        if owned:
            def inspect_owned():
                require(tested is True and retired, "Owned cancellation invocation/retirement failed")
                return assess_swift(objects, selection="owned-cancellation")
            self.check(prefix + "-case-execution", inspect_owned)

    def inspect_tool(self, label, arguments):
        """Retain read-only native tool output; this never builds or runs tests."""
        self.assert_owned_state()
        stdout, stderr = self.evidence / (label + ".stdout.log"), self.evidence / (label + ".stderr.log")
        with physical(stdout).open("xb") as output, physical(stderr).open("xb") as errors:
            result = subprocess.run(arguments, env=self.environment, stdout=output, stderr=errors, timeout=120)
        self.write(label + "-inspection.json", {"command": arguments, "exitCode": result.returncode,
                   "stdoutSha256": digest(stdout), "stderrSha256": digest(stderr), "inspectionOnly": True})
        require(result.returncode == 0, "Native evidence inspection failed: " + label)
        return stdout

    def select_simulator(self, label="simulators-before"):
        """Retain exact available-device selection; callers keep their own mutation/retirement boundary."""
        devices = self.inspect_tool(label, ["xcrun", "simctl", "list", "--json", "devices", "available"])
        devices = load_gate().read_json(devices).get("devices", {})
        require(type(devices) is dict, "Missing actual simulator list")
        choices = []
        for runtime, candidates in devices.items():
            match = re.search(r"\.SimRuntime\.iOS-([0-9-]+)$", runtime)
            if match:
                for device in candidates:
                    if device.get("name") == "iPhone 17" and device.get("isAvailable") is not False:
                        choices.append((tuple(map(int, match[1].split("-"))), device["udid"], device["state"]))
        require(choices, "No available exact iPhone17 simulator; required Swift tests are not skipped")
        if self.scope == "apple-owned-cancellation":
            choices = [choice for choice in choices if choice[2] == "Shutdown"]
            require(choices, "Owned cancellation requires an exact originally Shutdown simulator")
        elif (self.role, self.scope) in CANCELLATION_PROBE_ROUTES:
            # Prefer an already Shutdown available device for the terminal
            # isolated probe; a Booted newest choice is not a hardware blocker.
            choices = [choice for choice in choices if choice[2] == "Shutdown"] or choices
        _, udid, state_before = sorted(choices)[-1]
        require(re.fullmatch(r"[0-9A-Fa-f]{8}(?:-[0-9A-Fa-f]{4}){3}-[0-9A-Fa-f]{12}", udid) and
                state_before in ("Booted", "Shutdown"), "Invalid simulator metadata")
        self.simulator = {"udid": udid, "stateBefore": state_before, "scope": "Hosted simulator, not physical hardware"}
        return udid

    def shutdown_simulator(self, label="simulator-cleanup"):
        if not self.simulator or self.simulator["stateBefore"] != "Shutdown":
            return
        udid = self.simulator["udid"]
        def current(label):
            path = self.inspect_tool(label, ["xcrun", "simctl", "list", "--json", "devices", "available"])
            data = load_gate().read_json(path)
            devices = [item for group in data["devices"].values() for item in group if item["udid"] == udid]
            require(len(devices) == 1, "Cannot prove state of exact initially shutdown simulator")
            return devices[0]["state"]
        observed = current(label + "-before")
        if observed != "Shutdown":
            operation = "owned-simulator-shutdown" if label == "simulator-cleanup" else label + "-shutdown"
            require(self.invoke(operation, ["xcrun", "simctl", "shutdown", udid], kind="command", timeout=120),
                    "Exact job-booted simulator shutdown failed")
        observed = current(label + "-after")
        require(observed == "Shutdown", "Job-booted simulator did not return to its original shutdown state")
        self.simulator["stateAfter"] = observed

    def validate_completed_leaves(self):
        """Do not seal later-tampered or unfinished receipts as safe continuation."""
        self.assert_owned_state()
        for label, original in self.receipts.items():
            receipt = self.state / ("host-" + label + ".json")
            require(read_json(receipt) == original, "Completed host receipt was replaced")
            directory = self.validate_receipt(original, original["finalExitCode"], original["id"], label,
                                                original["kind"], original["requestedArgv"], receipt)
            current = {}
            for path in strict_files(directory):
                current[path.relative_to(directory).as_posix()] = digest(path)
            require(current == self.leaf_hashes[original["id"]], "Completed leaf evidence changed or disappeared")
        # Nested consumer/provenance/lock-policy leaves have their own canonical
        # receipts. Failed or incomplete nested finalization must never be masked
        # by an outer command's exit status, including an expected-red probe.
        for directory in self.evidence.iterdir():
            if re.fullmatch(r"[0-9a-f]{32}", directory.name):
                physical(directory)
                require(directory.is_dir(), "Invalid native invocation directory")
                receipt = directory / "receipt.json"
                record = read_json(receipt)
                self.validate_receipt(record, record.get("finalExitCode"), directory.name, record.get("purpose"),
                                      record.get("kind"), record.get("requestedArgv"), receipt)

    def finalize(self, error):
        # A rejected/preexisting or partially initialized state is never ours to
        # inspect, overwrite or delete. The workflow's separately owned bootstrap
        # logs retain admission/init errors, including absence of this summary.
        self.finalizing = True
        if not self.owns_state:
            self.safe = False
            self.emit_safe(False)
            return 1
        failures, after = [error] if error else [], None
        try:
            self.validate_completed_leaves()
        except Exception as failure:
            self.safe = False
            failures.append("Final leaf evidence: " + type(failure).__name__ + ": " + str(failure))
        try:
            self.assert_owned_state()
            # Never infer cleanup after an invocation lost its ownership proof.
            if self.safe:
                self.shutdown_simulator()
                self.clean_outputs()
            for directory in sorted(self.state.glob("consumer-receipts.*")):
                rows = self.retain_tree(directory, self.evidence / directory.name)
                self.write(directory.name + "-copy.json", {"files": rows})
            for path in [self.state / "context.json", *sorted(self.state.glob("host-*.json"))]:
                physical(path)
                require(path.is_file(), "Audit receipt/context is not a regular file")
                target = physical(self.evidence / path.name)
                with path.open("rb") as incoming, target.open("xb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
                require(digest(target) == digest(path), "Receipt/context changed during preservation")
            work = physical(self.state / "work")
            if work.exists():
                require(self.work_identity == self.identity(work), "Owned workspace identity changed")
                # These are explicit generated fixture/build diagnostics, never a
                # whole cache/home. Native Gradle reports were copied by each leaf.
                def selected(path):
                    excluded = {".gradle", ".konan", ".kotlin", ".git", "ModuleCache.noindex", "Index.noindex"}
                    return (not excluded.intersection(path.parts) and not any(
                        part.endswith(".xcresult") for part in path.parts) and
                        path.suffix in (".log", ".xml", ".json", ".txt", ".properties", ".kts", ".kt", ".java",
                                        ".swift", ".plist", ".yaml", ".yml", ".pom", ".module", ".xcactivitylog"))
                retained = self.retain_tree(work, self.evidence / "work-metadata", selected=selected)
                self.write("work-metadata-copy.json", {"files": retained})
                # A parser/cancellation failure may have prevented apple() copying
                # an already created result. Preserve those raw xcresults too.
                for bundle in sorted((work / "swift-ui/DerivedData/Logs/Test").glob("*.xcresult")):
                    target = self.evidence / "swift-xcresult" / bundle.name
                    if not target.exists():
                        self.retain_tree(bundle, target)
            after = source_snapshot(root=ROOT)
            require(self.context is not None and after == self.context["source"] and
                    digest(self.state / "context.json") == self.context_hash, "Final admitted source/context changed")
            if self.safe and work.exists():
                # No deletion until every dependent check and evidence copy above
                # has finished. rmtree never follows a worktree symlink.
                require(self.work_identity == self.identity(work), "Work ownership changed before removal")
                shutil.rmtree(work)
                require(not work.exists(), "Disposable workspace removal was incomplete")
            project = physical(ROOT / GENERATED_PROJECT)
            if self.safe and project.exists() and str(project) not in self.context["preexistingOutputPaths"]:
                result = subprocess.run([sys.executable, str(self.runner), "cleanup", "--state", str(self.state),
                                         "--path", str(project)], cwd=ROOT, env=self.environment, timeout=120)
                require(result.returncode == 0 and not project.exists(), "Owned generated Xcode project cleanup failed")
            after = source_snapshot(root=ROOT)
            require(after == self.context["source"], "Source changed during final cleanup")
            if self.safe:
                self.validate_completed_leaves()
        except Exception as failure:
            self.safe = False
            failures.append(type(failure).__name__ + ": " + str(failure))
        passed = bool(not failures and self.safe and self.rows and all(row["result"] == "PASS" for row in self.rows))
        try:
            self.write("host-summary.json", {"schema": 1, "role": self.role, "source": self.admission,
                       "requestedScope": self.scope,
                       "hostQualification": "FULL_COMPONENT_SCOPE" if self.scope == "full" else
                           "NOT_ESTABLISHED_BY_FOCUSED_SCOPE",
                       "sourceAfter": after, "startedUtc": self.started, "finishedUtc": now(),
                       "result": "PASS" if passed else "FAIL", "safeToContinue": self.safe,
                       "error": "; ".join(failures) or None, "components": self.rows, "simulator": self.simulator,
                       "releaseGateMonolith": "NOT_EXECUTED_COMPONENT_REPLAY",
                       "externalAcceptance": "NOT_VALIDATED: physical/ART/OEM, hostile networks, independent interoperability and professional cryptography"})
            manifest = physical(self.evidence / "manifest.sha256")
            files = []
            for parent, directories, names in strict_walk(self.evidence):
                for name in [*directories, *names]:
                    physical(Path(parent) / name)
                for name in names:
                    path = Path(parent) / name
                    require(path.is_file() and path != manifest, "Nonregular or preexisting sealed evidence")
                    files.append(path)
            with manifest.open("x", encoding="utf-8") as stream:
                for path in sorted(files):
                    stream.write(digest(path) + "  " + path.relative_to(self.evidence).as_posix() + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            self.emit_safe(self.safe)
        except Exception as failure:
            # Even a written optimistic summary cannot release a later host if
            # final sealing/output publication failed. Do not rewrite old evidence.
            self.safe = False
            print("FATAL: hosted final evidence/cleanup is UNKNOWN: " + str(failure), file=sys.stderr, flush=True)
            self.emit_safe(False)
            return 1
        return 0 if passed else 1

    @staticmethod
    def emit_safe(safe):
        output = os.environ.get("GITHUB_OUTPUT")
        if output:
            with open(output, "a", encoding="utf-8") as stream:
                stream.write("safe_to_continue=" + ("true" if safe else "false") + "\n")

    def initialize(self):
        physical(self.state)
        require(not self.state.exists(), "Audit state is not new; preserve prior attempts")
        require(self.state.parent.is_dir() and not self.state.is_relative_to(ROOT) and not ROOT.is_relative_to(self.state),
                "Audit state requires an existing physical parent outside source")
        result = subprocess.run([sys.executable, str(self.runner), "init", "--root", str(ROOT), "--state", str(self.state),
                                 "--expected-commit", self.admission["commit"], "--host", self.role], cwd=ROOT,
                                env=self.environment, timeout=120)
        require(result.returncode == 0, "Audit context initialization failed; partial state is preserved")
        context = read_json(self.state / "context.json")
        require(type(context.get("schema")) is int and context["schema"] == 1 and context.get("root") == str(ROOT) and
                context.get("host") == self.role and context.get("expectedCommit") == self.admission["commit"] and
                context.get("tree") == self.admission["tree"] and context.get("source") == source_snapshot(root=ROOT),
                "Initialized context does not bind the admitted source/host")
        require(context["source"]["status"] == "" and context["source"]["diffSha256"] == hashlib.sha256(b"").hexdigest() and
                type(context.get("id")) is str and re.fullmatch(r"[0-9a-f]{32}", context["id"]) and
                context.get("gradleHome") == str(self.state / "gradle-home"), "Malformed owned context")
        self.context, self.context_hash = context, digest(self.state / "context.json")
        self.state_identity = self.identity(self.state)
        self.owns_state = True
        self.assert_owned_state()
        work = self.state / "work"
        work.mkdir(mode=0o700, exist_ok=False)
        self.work_identity = self.identity(work)
        self.write("admission.json", self.admission)

    def run(self):
        error = None
        def interrupt(signum, frame):
            raise KeyboardInterrupt("Hosted audit interrupted")
        previous = {sig: signal.signal(sig, interrupt) for sig in (signal.SIGINT, signal.SIGTERM)}
        try:
            self.emit_safe(False)
            physical(self.state)
            require(not self.state.exists(), "Audit state is not new; preserve prior attempts")
            event = load_gate().read_json(Path(os.environ["GITHUB_EVENT_PATH"]))
            self.admission = admit(event, os.environ, self.role, scope=self.scope)
            self.initialize()
            self.prerequisites()
            # Native ownership/admission tests must pass before any product project task.
            if not self.invoke("executor-native-controls", [sys.executable, "scripts/tests/run-audit-command-test.py",
                               "--expected-host", self.role, "--evidence-dir", str(self.evidence / "native-controls")], kind="command"):
                raise InfrastructureFailure("Native executor controls failed; product execution is blocked")
            self.safe = True
            self.setup_sdk()
            if self.scope == "windows-diagnostics":
                self.windows_diagnostics()
            elif self.scope == "windows-followup":
                self.windows_followup()
            elif self.role == "windows-x64":
                self.windows()
            elif self.role == "macos-arm64":
                self.mac()
            else:
                require(self.check("intel-simulator-prerequisites", self.inspect_intel_simulators),
                        "Intel simulator prerequisite failed; product builds are NOT_EXECUTED")
                self.invoke("intel-platform", [sys.executable, "scripts/run-platform-tests.py", "ios-x64"], kind="command", timeout=7200)
                self.clean_outputs()
                self.install_xcodegen()
                self.isolated_consumers()
                self.clean_outputs()
                preparation = [*[":" + module + ":checkKotlinAbi" for module in MODULES],
                               *[":" + module + ":checkAndroidAbi" for module in (
                                   "p2p-core", "p2p-transport-lan", "p2p-network-provisioning-android")],
                               ":p2p-sample-desktop:installDist", "--continue"]
                self.invoke("swift-jvm-cli-prepare", preparation)
                # Independent Apple work may continue after a finalized graph failure.
                # The live peer still requires this actual preparation receipt to succeed.
                self.apple()
        except (Exception, KeyboardInterrupt) as failure:
            error = type(failure).__name__ + ": " + str(failure)
            print("FATAL: " + error, file=sys.stderr, flush=True)
            self.safe = False
        finally:
            for sig in previous:
                signal.signal(sig, signal.SIG_IGN)
            try:
                return self.finalize(error)
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=ROLES)
    parser.add_argument("--timeout-seconds", type=int)
    parser.add_argument("--scope", choices=SCOPES, default="full")
    args = parser.parse_args()
    require(args.role in SCOPES[args.scope], "Unsupported audit role/scope pair")
    state = Path(os.environ["P2PKIT_AUDIT_STATE_DIR"])
    require(state.is_absolute() and not state.is_symlink() and not state.resolve().is_relative_to(ROOT),
            "Audit state must be a new physical absolute directory outside source")
    return Host(args.role, state, args.timeout_seconds, scope=args.scope).run()


if __name__ == "__main__":
    raise SystemExit(main())
