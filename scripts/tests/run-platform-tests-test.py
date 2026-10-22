#!/usr/bin/env python3
"""Policy mutations and fake-Gradle lifecycle tests; these do not execute Kotlin tests."""

import ast
import contextlib
import copy
from datetime import datetime, timedelta, timezone
import errno
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("platform_gate", ROOT / "scripts/run-platform-tests.py")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)
POLICY = GATE.read_json(ROOT / "gradle/platform-test-policy.json")
TOKEN = "a" * 32


def model_process_launch(supplier):
    """Supply a child to the retained owner, without executing native admission."""
    def start(owner, argv, *, cwd, stdout=None, stderr=None):
        owner.attempted = True
        outputs = {} if stdout is None and stderr is None else {"stdout": stdout, "stderr": stderr}
        owner.child = supplier(argv, cwd=cwd, **outputs)
    return mock.patch.object(GATE.ProcessOwner, "start", new=start)


def example_report(profile="full", arch="arm64"):
    required = GATE.required_tasks(POLICY, profile, arch)
    tasks = {name for entry in POLICY["model"].values() for name in entry["tests"]}
    unavailable = "iosX64Test" if arch == "arm64" else "iosSimulatorArm64Test"
    report = {
        "schema": 1, "token": TOKEN, "buildFailed": False, "dryRun": False,
        "host": {"os": "Mac OS X", "arch": "aarch64" if arch == "arm64" else "x86_64"},
        "model": copy.deepcopy(POLICY["model"]),
        "tests": {name: {
            "outcome": "EXECUTED" if name in required else "SKIPPED" if profile == "full" else "NOT_REQUESTED",
            "enabled": not name.endswith(":" + unavailable), "inGraph": profile == "full" or name in required,
            "passed": 1 if name in required else 0, "failed": 0, "skipped": 0,
        } for name in tasks},
    }
    for name in GATE.SEPARATE_QUALIFICATION_TASKS:
        report["tests"][name].update(outcome="NOT_REQUESTED", inGraph=False)
    return report


def intel_encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def intel_hash(raw):
    return hashlib.sha256(raw).hexdigest()


class IntelEvidenceFixture:
    """Independent supplied originals, not native observations or owner authority."""
    tasks = (":p2p-core:iosX64Test", ":p2p-transport-lan:iosX64Test",
             ":p2p-rpc:iosX64Test", ":p2p-sample-rpc:iosX64Test")
    uuid = "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
    runtime = "com.apple.CoreSimulator.SimRuntime.iOS-26-2"
    prepare = ("simulator-macos-version", "simulator-xcode-version", "simulator-first-launch", "simulator-runtimes",
               "intel-bootstatus-help", "simulator-devices", "intel-boot", "intel-bootstatus", "intel-prelaunch")
    retire = ("intel-retire-before", "intel-shutdown", "intel-retire-after")

    def inventory(self, state):
        return intel_encoded({"devices": {self.runtime: [{"name": "iPhone 17", "udid": self.uuid, "state": state,
            "isAvailable": True, "deviceTypeIdentifier": "com.apple.CoreSimulator.SimDeviceType.iPhone-17"}]}})

    def __init__(self, root="/synthetic/intel-source", token=TOKEN):
        self.root, self.token = root, token
        source = {"commit": "a" * 40, "tree": "b" * 40, "status": "", "diffSha256": intel_hash(b"")}
        tasks = list(self.tasks)
        device = {"name": "iPhone 17", "udid": self.uuid, "state": "Shutdown", "isAvailable": True,
                  "deviceTypeIdentifier": "com.apple.CoreSimulator.SimDeviceType.iPhone-17"}
        self.binding = {"schema": 1, "scope": "CALLER_MANAGED_INTEL_SIMULATOR_V1", "profile": "ios-x64",
            "role": "macos-x64", "root": root, "token": token, "source": copy.deepcopy(source), "developerDir": None,
            "github": {key: None for key in ("actions", "repository", "runId", "runAttempt", "sha", "ref", "job")},
            "tasks": tasks, "standalone": False,
            "selected": {"runtime": {"identifier": self.runtime, "version": "26.2", "isAvailable": True}, "device": device},
            "bootedDevice": {**device, "state": "Booted"}, "originals": {}}
        self.retirement = {"schema": 1, "scope": "CALLER_MANAGED_INTEL_SIMULATOR_RETIREMENT_V1", "root": root,
            "token": token, "source": copy.deepcopy(source), "selected": copy.deepcopy(self.binding["selected"]),
            "bindingSha256": None, "shutdownIssued": True, "originals": {}, "deviceAfter": copy.deepcopy(device), "errors": []}
        self.invocation = {**source, "profile": "ios-x64", "token": token, "startedUtc": "2026-10-07T00:00:00Z"}
        self.argv = {
            "simulator-macos-version": ["/usr/bin/sw_vers", "-productVersion"],
            "simulator-xcode-version": ["/usr/bin/xcodebuild", "-version"],
            "simulator-first-launch": ["/usr/bin/xcodebuild", "-checkFirstLaunchStatus"],
            "simulator-runtimes": ["/usr/bin/xcrun", "simctl", "list", "--json", "runtimes"],
            "intel-bootstatus-help": ["/usr/bin/xcrun", "simctl", "help", "bootstatus"],
            "intel-boot": ["/usr/bin/xcrun", "simctl", "boot", self.uuid],
            "intel-bootstatus": ["/usr/bin/xcrun", "simctl", "bootstatus", self.uuid],
            "intel-shutdown": ["/usr/bin/xcrun", "simctl", "shutdown", self.uuid]}
        for label in ("simulator-devices", "intel-prelaunch", "intel-retire-before", "intel-retire-after"):
            self.argv[label] = ["/usr/bin/xcrun", "simctl", "list", "--json", "devices", "available"]
        self.stdout = {label: b"" for label in self.prepare + self.retire}
        self.stdout.update({"simulator-macos-version": b"15.0\n",
            "simulator-xcode-version": b"Xcode 26.3\nBuild version 17C529\n",
            "simulator-runtimes": intel_encoded({"runtimes": [{"identifier": self.runtime, "version": "26.2", "isAvailable": True}]}),
            "intel-bootstatus-help": b"Usage: simctl bootstatus <device> [-b] [-d]\n",
            "simulator-devices": self.inventory("Shutdown"), "intel-prelaunch": self.inventory("Booted"),
            "intel-retire-before": self.inventory("Booted"), "intel-retire-after": self.inventory("Shutdown")})
        self.stderr = {label: b"" for label in self.prepare + self.retire}
        self.rows = {}
        for ordinal, label in enumerate(self.prepare + self.retire, 1):
            at = datetime(2026, 10, 7, tzinfo=timezone.utc) + timedelta(seconds=ordinal * 2)
            self.rows[label] = {"schema": 1, "label": label, "argv": self.argv[label], "cwd": root,
                "startedUtc": at.isoformat(), "finishedUtc": (at + timedelta(seconds=1)).isoformat(),
                "exitCode": 0, "timedOut": False, "outputLimitExceeded": False, "ownedGroupDrained": True}

    def packet(self):
        originals = {}
        for label, record in self.rows.items():
            row = copy.deepcopy(record)
            for stream, values in (("stdout", self.stdout), ("stderr", self.stderr)):
                raw = values[label]
                originals[label + "/" + stream + ".bin"] = raw
                row[stream + "Bytes"], row[stream + "Sha256"] = len(raw), intel_hash(raw)
            originals[label + "/result.json"] = intel_encoded(row)
        def references(labels):
            return {name: {"bytes": len(raw), "sha256": intel_hash(raw)} for name, raw in originals.items()
                    if name.split("/")[0] in labels}
        binding = copy.deepcopy(self.binding)
        binding["originals"] = references(self.prepare)
        binding_raw = intel_encoded(binding)
        identity = {"scope": "CALLER_MANAGED_INTEL_SIMULATOR_V1", "bindingSha256": intel_hash(binding_raw),
                    "prelaunchSha256": intel_hash(originals["intel-prelaunch/result.json"]), "token": binding["token"],
                    "device": binding["selected"]["device"]["udid"], "runtime": binding["selected"]["runtime"]["identifier"],
                    "standalone": False}
        invocation = copy.deepcopy(self.invocation)
        invocation["intelSimulator"] = identity
        invocation["command"] = [self.root + "/gradlew", *self.tasks,
            "--no-daemon", "--no-build-cache", "--no-configuration-cache", "--rerun-tasks", "--dependency-verification",
            "strict", "--max-workers=2", "--no-parallel", "--console=plain", "--init-script",
            self.root + "/gradle/platform-test-coverage.init.gradle", "-Pp2pkit.testCoverageRoot=" + self.root,
            "-Pp2pkit.testCoverageToken=" + self.token, "-Pp2pkit.intelSimulatorBinding=" + self.root +
            "/build/reports/platform-tests/" + self.token + "/intel-simulator/binding.json",
            "-Pp2pkit.intelSimulatorSha256=" + intel_hash(binding_raw)]
        retirement = copy.deepcopy(self.retirement)
        retirement["bindingSha256"] = intel_hash(binding_raw)
        retirement["originals"] = references(self.retire)
        properties = {task: {"device": self.uuid, "type": "org.jetbrains.kotlin.gradle.targets.native.tasks.KotlinNativeSimulatorTest",
                             "standalone": False} for task in self.tasks}
        model = {**identity, "configured": properties, "inGraph": copy.deepcopy(properties), "unchanged": True}
        return {"intel_binding": binding_raw, "intel_originals": originals, "intel_retirement": intel_encoded(retirement),
                "intel_invocation": invocation}, model


class CoveragePolicyTest(unittest.TestCase):
    def assess(self, report, profile="full", arch="arm64"):
        arguments = {}
        if profile == "ios-x64":
            arguments, model = IntelEvidenceFixture().packet()
            report = copy.deepcopy(report)
            report["intelSimulator"] = model
        try:
            return GATE.assess(report, POLICY, profile, arch, TOKEN, **arguments)
        except ValueError as error:
            # Existing mutations must reach their actual old gate, not trivially
            # fail because the new mandatory Intel originals were omitted.
            if profile == "ios-x64":
                self.assertNotIn("INTEL_", str(error))
            raise

    def test_current_executed_set_is_not_empty_or_sample_only(self):
        arm = self.assess(example_report())
        intel = self.assess(example_report(arch="x64"), arch="x64")
        x64_only = self.assess(example_report("ios-x64", "x64"), "ios-x64", "x64")
        self.assertEqual(20, len(arm))
        self.assertEqual(20, len(intel))
        self.assertEqual({":p2p-core:iosX64Test", ":p2p-transport-lan:iosX64Test",
                          ":p2p-rpc:iosX64Test", ":p2p-sample-rpc:iosX64Test"}, x64_only)
        native_arm = [":p2p-core:iosSimulatorArm64Test", ":p2p-transport-lan:iosSimulatorArm64Test",
                      ":p2p-rpc:iosSimulatorArm64Test", ":p2p-sample-rpc:iosSimulatorArm64Test"]
        self.assertEqual(native_arm, GATE.PROFILES["ios-arm64"])
        arm_only = example_report("ios-arm64", "arm64")
        self.assertEqual(set(native_arm), self.assess(arm_only, "ios-arm64", "arm64"))
        with self.assertRaises(ValueError):
            self.assess(arm_only, "full", "arm64")
        for arch, target in (("arm64", "iosSimulatorArm64"), ("x64", "iosX64")):
            profile = "ios-lan-" + arch
            lan_task = ":p2p-transport-lan:" + target + "Test"
            self.assertEqual([lan_task], GATE.PROFILES[profile])
            lan_only = example_report(profile, arch)
            self.assertEqual({lan_task}, self.assess(lan_only, profile, arch))
            for broader in ("full", "ios-" + arch):
                with self.subTest(profile=profile, broader=broader), self.assertRaises(ValueError):
                    self.assess(lan_only, broader, arch)
            rows = {row["target"]: row for row in GATE.target_rows(lan_only)}
            self.assertEqual("NOT_REQUESTED", rows[":p2p-core/" + target]["status"])
            self.assertIn("did not request", rows[":p2p-core/" + target]["reason"])
        self.assertIn(":sample-kmp-shared:testAndroidHostTest", arm)
        self.assertIn(":p2p-core:testAndroidHostTest", arm)
        self.assertIn(":p2p-core:iosSimulatorArm64Test", arm)
        self.assertNotIn(":p2p-core:iosX64Test", arm)
        self.assertNotIn(":p2p-core:iosSimulatorArm64Test", intel)

    def test_macos_shared_and_native_union_preserves_complete_check_inventory(self):
        shared = self.assess(example_report("macos-shared"), "macos-shared")
        arm = self.assess(example_report("ios-arm64"), "ios-arm64")
        intel = self.assess(example_report("ios-x64", "x64"), "ios-x64", "x64")
        configured = {task for entry in POLICY["model"].values() for task in entry["tests"]}
        self.assertEqual((16, 4, 4), (len(shared), len(arm), len(intel)))
        self.assertEqual(26, len(configured))
        self.assertEqual(configured - set(GATE.SEPARATE_QUALIFICATION_TASKS), shared | arm | intel)
        self.assertFalse(shared & (arm | intel))
        self.assertFalse(arm & intel)
        self.assertEqual(["check"], GATE.PROFILES["full"])
        command = GATE.PROFILES["macos-shared"]
        self.assertEqual("check", command[0])
        self.assertEqual(["-x"] * 8, command[1::2])
        self.assertEqual(arm | intel, set(command[2::2]))
        self.assertEqual(17, len(command))
        self.assertTrue({":p2p-sample-diagnostics:test", ":sample-kmp-shared:jvmTest",
                         ":sample-kmp-shared:testAndroidHostTest"} <= shared)
        self.assertEqual(9, sum(task.endswith((":test", ":jvmTest")) for task in shared))
        self.assertEqual(7, len(shared) - 9)
        intel_shared = self.assess(example_report("macos-shared", "x64"), "macos-shared", "x64")
        self.assertEqual(shared, intel_shared)
        with self.assertRaisesRegex(ValueError, "native ARM64 or Intel"):
            GATE.required_tasks(POLICY, "macos-shared", "unknown")
        mutated = copy.deepcopy(POLICY)
        mutated["model"][":p2p-core"]["tests"].remove(":p2p-core:iosSimulatorArm64Test")
        with self.assertRaisesRegex(ValueError, "Delegated native tasks"):
            GATE.required_tasks(mutated, "macos-shared", "arm64")

    def test_every_expected_task_must_execute_fresh_successful_cases(self):
        for profile, arch in (("full", "arm64"), ("full", "x64"), ("ios-x64", "x64"),
                              ("ios-arm64", "arm64"), ("ios-lan-arm64", "arm64"), ("ios-lan-x64", "x64"),
                              ("macos-shared", "arm64"), ("macos-shared", "x64")):
            baseline = example_report(profile, arch)
            for name in GATE.required_tasks(POLICY, profile, arch):
                changes = [("outcome", outcome) for outcome in (
                    "SKIPPED", "UP-TO-DATE", "FROM-CACHE", "NO_SOURCE", "NOT_COMPLETED", "NOT_REQUESTED", "FAILED")]
                changes += [("enabled", False), ("inGraph", False), ("passed", 0), ("failed", 1)]
                for key, value in changes:
                    with self.subTest(profile=profile, arch=arch, task=name, field=key, value=value):
                        report = copy.deepcopy(baseline)
                        report["tests"][name][key] = value
                        with self.assertRaises(ValueError):
                            self.assess(report, profile, arch)
                report = copy.deepcopy(baseline)
                del report["tests"][name]
                with self.assertRaises(ValueError):
                    self.assess(report, profile, arch)

    def test_every_target_and_task_is_guarded_against_model_drift(self):
        for project, entry in POLICY["model"].items():
            for target in entry["targets"]:
                report = example_report()
                del report["model"][project]["targets"][target]
                with self.subTest(project=project, missing_target=target), self.assertRaises(ValueError):
                    self.assess(report)
            for task in entry["tests"]:
                report = example_report()
                report["model"][project]["tests"].remove(task)
                del report["tests"][task]
                with self.subTest(missing_task=task), self.assertRaises(ValueError):
                    self.assess(report)
        report = example_report()
        report["model"][":p2p-core"]["targets"]["newNative"] = "native"
        with self.assertRaises(ValueError):
            self.assess(report)

    def test_separate_qualification_list_is_exact_and_cannot_exclude_mandatory_tasks(self):
        expected = [":p2p-transport-lan:macInstalledBundleTest", ":p2p-transport-lan:macTcpNativeTest"]
        self.assertEqual(expected, POLICY["separateQualificationTasks"])
        self.assertEqual(expected, sorted(GATE.SEPARATE_QUALIFICATION_TASKS))
        for arch in ("arm64", "x64"):
            for task in GATE.required_tasks(POLICY, "full", arch):
                policy = copy.deepcopy(POLICY)
                policy["separateQualificationTasks"].append(task)
                with self.subTest(arch=arch, excluded=task), self.assertRaises(ValueError):
                    GATE.required_tasks(policy, "full", arch)
        for replacement in ([], None, expected[:1], expected + [expected[0]], expected[::-1],
                            expected + [":p2p-transport-lan:newNativeTest"]):
            policy = copy.deepcopy(POLICY)
            policy["separateQualificationTasks"] = replacement
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                GATE.required_tasks(policy, "full", "arm64")
        for change in ("missing", "unknown", "inventory-omission"):
            policy = copy.deepcopy(POLICY)
            if change == "missing":
                del policy["separateQualificationTasks"]
            elif change == "unknown":
                policy["excludedTasks"] = [":p2p-core:jvmTest"]
            else:
                policy["model"][":p2p-transport-lan"]["tests"].remove(expected[0])
            with self.subTest(change=change), self.assertRaises(ValueError):
                GATE.required_tasks(policy, "full", "arm64")

    def test_unknown_and_missing_auxiliary_records_are_not_ignored(self):
        for task in GATE.SEPARATE_QUALIFICATION_TASKS:
            report = example_report()
            del report["tests"][task]
            with self.subTest(missing=task), self.assertRaises(ValueError):
                self.assess(report)
        for add_model in (False, True):
            report = example_report()
            task = ":p2p-transport-lan:newNativeTest"
            report["tests"][task] = copy.deepcopy(report["tests"][":p2p-transport-lan:macTcpNativeTest"])
            if add_model:
                report["model"][":p2p-transport-lan"]["tests"].append(task)
            with self.subTest(unknown_in_model=add_model), self.assertRaises(ValueError):
                self.assess(report)

    def test_auxiliary_execution_failure_disabled_state_and_counts_cannot_pass(self):
        for profile, arch in (("full", "arm64"), ("full", "x64"), ("ios-x64", "x64"),
                              ("ios-arm64", "arm64"), ("ios-lan-arm64", "arm64"), ("ios-lan-x64", "x64"),
                              ("macos-shared", "arm64"), ("macos-shared", "x64")):
            for task in GATE.SEPARATE_QUALIFICATION_TASKS:
                changes = [("outcome", value) for value in
                           ("EXECUTED", "FAILED", "SKIPPED", "UP-TO-DATE", "FROM-CACHE", "NO_SOURCE",
                            "NOT_COMPLETED", "INVENTED")]
                changes += [("enabled", False), ("inGraph", True)]
                changes += [(count, value) for count in ("passed", "failed", "skipped")
                            for value in (1, -1, True, "0", 0.5)]
                for key, value in changes:
                    report = example_report(profile, arch)
                    report["tests"][task][key] = value
                    with self.subTest(profile=profile, task=task, field=key, value=value), \
                            self.assertRaises(ValueError):
                        self.assess(report, profile, arch)
                report = example_report(profile, arch)
                report["tests"][task].update(outcome="EXECUTED", inGraph=True, passed=1)
                with self.subTest(profile=profile, native_success_is_not_qualification=task), \
                        self.assertRaises(ValueError):
                    self.assess(report, profile, arch)

    def test_auxiliary_summary_preserves_separate_scope_and_actual_outcome_without_credit(self):
        report = example_report()
        self.assess(report)
        rows = {row["target"]: row for row in GATE.target_rows(report)}
        for task in GATE.SEPARATE_QUALIFICATION_TASKS:
            row = rows[task]
            self.assertEqual("SEPARATE_QUALIFICATION", row["status"])
            self.assertEqual("NOT_REQUESTED", row["outcome"])
            self.assertIs(False, row["qualificationCredit"])
            self.assertEqual([0, 0, 0], [row[key] for key in ("passed", "failed", "skipped")])
            self.assertIn("no native/JNI or installed-application qualification credit", row["reason"])
            altered = copy.deepcopy(report)
            altered["tests"][task].update(outcome="FAILED", inGraph=True, failed=1)
            with self.assertRaises(ValueError):
                self.assess(altered)
            failed = next(row for row in GATE.target_rows(altered) if row["target"] == task)
            self.assertEqual("FAILED", failed["outcome"])
            self.assertEqual(1, failed["failed"])
            self.assertIs(False, failed["qualificationCredit"])

    def test_stale_failed_dry_run_wrong_host_and_malformed_reports_fail(self):
        for key, value in (
            ("schema", 2), ("schema", True), ("token", "b" * 32), ("dryRun", True), ("buildFailed", True),
            ("host", []), ("host", {"os": "Linux", "arch": "aarch64"}),
            ("host", {"os": "Mac OS X", "arch": "amd64"}), ("host", {"os": "Mac OS X", "arch": 1}),
            ("tests", []), ("tests", {}), ("model", None),
        ):
            report = example_report()
            report[key] = value
            with self.subTest(field=key, value=value), self.assertRaises(ValueError):
                self.assess(report)
        for report in (None, [], 1, "invalid"):
            with self.assertRaises(ValueError):
                self.assess(report)

    def test_malformed_task_states_and_counts_fail(self):
        name = ":p2p-core:jvmTest"
        for key, value in (
            ("enabled", 1), ("inGraph", "true"), ("outcome", "INVENTED"),
            ("passed", -1), ("passed", True), ("passed", "1"), ("passed", 1.5),
            ("failed", None), ("skipped", -1),
        ):
            report = example_report()
            report["tests"][name][key] = value
            with self.subTest(field=key, value=value), self.assertRaises(ValueError):
                self.assess(report)
        report = example_report()
        report["tests"][name] = None
        with self.assertRaises(ValueError):
            self.assess(report)

    def test_skip_counts_and_all_nonexecution_limits_are_visible(self):
        report = example_report()
        report["tests"][":p2p-transport-lan:iosSimulatorArm64Test"]["skipped"] = 1
        self.assess(report)
        rows = {row["target"]: row for row in GATE.target_rows(report)}
        self.assertEqual(1, rows[":p2p-transport-lan/iosSimulatorArm64"]["skipped"])
        self.assertEqual("SKIPPED", rows[":p2p-core/iosX64"]["status"])
        self.assertIn("architecture disabled", rows[":p2p-core/iosX64"]["reason"])
        self.assertEqual("NOT_CONFIGURED", rows[":p2p-core/iosArm64"]["status"])
        self.assertEqual("COMPILATION_ONLY", rows[":p2p-core/metadata"]["status"])
        self.assertIn("no ART/instrumented", rows[":p2p-core/android"]["reason"])
        self.assertIn("commonTest is excluded", rows[":p2p-core/android"]["reason"])
        self.assertEqual("OUTSIDE_THIS_INVOCATION", rows[":iosApp/Swift"]["status"])
        # An unclassified future target must not disappear from failure evidence.
        report["model"][":p2p-core"]["targets"]["newTarget"] = "native"
        self.assertIn("NO_TEST_TASK", [row["status"] for row in GATE.target_rows(report)])

    def test_bounded_json_reader_rejects_duplicates_and_invalid_inputs(self):
        with tempfile.TemporaryDirectory(prefix="p2pkit-coverage-json-") as temp:
            path = Path(temp) / "input.json"
            for content in (b"", b"{}" * (512 * 1024 + 1), b'{"schema":1,"schema":1}', b'{"v":NaN}', b"\xff"):
                path.write_bytes(content)
                with self.subTest(size=len(content)), self.assertRaises(ValueError):
                    GATE.read_json(path)
            path.write_text('{"schema":1}')
            self.assertEqual({"schema": 1}, GATE.read_json(path))

    def test_malformed_policy_and_wrong_profile_fail_before_build(self):
        for policy in (None, [], {"schema": True}, {"schema": 1, "model": {}},
                       {"schema": 1, "model": {":bad": {"targets": {}, "tests": [False]}}}):
            with self.assertRaises(ValueError):
                GATE.required_tasks(policy, "full", "arm64")
        for profile, arch in (("ios-x64", "arm64"), ("ios-arm64", "x64"), ("ios-arm64", "unknown"),
                              ("ios-lan-arm64", "x64"), ("ios-lan-arm64", "unknown"),
                              ("ios-lan-x64", "arm64"), ("ios-lan-x64", "unknown"),
                              ("full", "unknown"), ("other", "x64")):
            with self.assertRaises(ValueError):
                GATE.required_tasks(POLICY, profile, arch)


class IntelSimulatorEvidenceModels(unittest.TestCase):
    """Supplied originals exercise the real predicates, not a native simulator."""
    def assess(self, fixture=None, change=None):
        arguments, model = (fixture or IntelEvidenceFixture()).packet()
        report = example_report("ios-x64", "x64")
        report["intelSimulator"] = model
        if change is not None:
            change(arguments, report)
        return GATE.assess(report, POLICY, "ios-x64", "x64", TOKEN, **arguments)

    def test_bootstatus_phase_ceiling_preserves_other_limits_and_failures(self):
        self.assertEqual(600, GATE.INTEL_BOOTSTATUS_SECONDS)
        self.assertEqual(120, GATE.simulator.SECONDS)
        self.assertEqual((15, 5), (GATE.TERMINATION_GRACE_SECONDS, GATE.TERMINATION_KILL_SECONDS))
        for label in IntelEvidenceFixture.prepare + IntelEvidenceFixture.retire:
            ceiling = 690 if label == "intel-bootstatus" else 210
            durations = (300, ceiling, ceiling + 1) if label == "intel-bootstatus" else (ceiling, ceiling + 1)
            for duration in durations:
                fixture = IntelEvidenceFixture()
                row = fixture.rows[label]
                row["finishedUtc"] = (datetime.fromisoformat(row["startedUtc"]) +
                                      timedelta(seconds=duration)).isoformat()
                arguments, _model = fixture.packet()
                with self.subTest(label=label, duration=duration):
                    if duration <= ceiling:
                        actual = GATE._intel_phase(arguments["intel_originals"], label,
                                                   fixture.root, fixture.binding["selected"])
                        self.assertEqual(row["finishedUtc"], actual["finishedUtc"])
                    else:
                        with self.assertRaisesRegex(ValueError, "INTEL_PHASE_DEADLINE"):
                            GATE._intel_phase(arguments["intel_originals"], label,
                                              fixture.root, fixture.binding["selected"])
        for key, value in (("exitCode", 1), ("exitCode", True), ("exitCode", None), ("timedOut", True),
                           ("outputLimitExceeded", True), ("ownedGroupDrained", False)):
            fixture = IntelEvidenceFixture()
            row = fixture.rows["intel-bootstatus"]
            row.update({key: value, "finishedUtc": (datetime.fromisoformat(row["startedUtc"]) +
                                                    timedelta(seconds=600)).isoformat()})
            arguments, _model = fixture.packet()
            with self.subTest(field=key, value=value), self.assertRaisesRegex(ValueError, "INTEL_PHASE_FAILED"):
                GATE._intel_phase(arguments["intel_originals"], "intel-bootstatus",
                                  fixture.root, fixture.binding["selected"])

    def test_complete_rpc_rosters_match_policy_driver_and_gradle_init(self):
        modules = (":p2p-core", ":p2p-transport-lan", ":p2p-rpc", ":p2p-sample-rpc")
        intel = [module + ":iosX64Test" for module in modules]
        ordinary = [module + suffix for module in modules
                    for suffix in (":iosSimulatorArm64Test", ":iosX64Test")]
        self.assertEqual(intel, list(IntelEvidenceFixture.tasks))
        self.assertEqual(intel, GATE.PROFILES["ios-x64"])
        self.assertEqual([module + ":iosSimulatorArm64Test" for module in modules], GATE.PROFILES["ios-arm64"])
        self.assertEqual(ordinary, list(GATE.simulator.TASKS))
        policy_tasks = {task for entry in POLICY["model"].values() for task in entry["tests"]
                        if task.endswith((":iosSimulatorArm64Test", ":iosX64Test"))}
        self.assertEqual(set(ordinary), policy_tasks)
        init = (ROOT / "gradle/platform-test-coverage.init.gradle").read_text()
        for name, expected in (("intelTasks", intel), ("expectedSimulators", ordinary)):
            literals = re.findall(r"def " + name + r" = (\[[^\]]+\])", init)
            self.assertEqual(len(literals), 1)
            self.assertEqual(ast.literal_eval(literals[0]), expected)

    def test_rpc_tasks_cannot_be_omitted_reordered_or_fabricated(self):
        tasks = list(IntelEvidenceFixture.tasks)
        for changed in (tasks[:2], tasks[:-1], tasks[::-1], tasks + [":other:iosX64Test"]):
            fixture = IntelEvidenceFixture()
            fixture.binding["tasks"] = changed
            with self.subTest(binding=changed), self.assertRaisesRegex(ValueError, "INTEL_BINDING_SCHEMA"):
                self.assess(fixture)
        for task in tasks[2:]:
            for field in ("configured", "inGraph"):
                with self.subTest(task=task, field=field), self.assertRaisesRegex(ValueError, "INTEL_ACTUAL_TASK_PROPERTIES"):
                    self.assess(change=lambda _arguments, report: report["intelSimulator"][field].pop(task))
            def omit_command(arguments, _report):
                arguments["intel_invocation"]["command"].remove(task)
            with self.subTest(command=task), self.assertRaisesRegex(ValueError, "INTEL_INVOCATION_JOIN"):
                self.assess(change=omit_command)

    def test_complete_originals_bind_foreign_root_real_properties_and_other_logical_job(self):
        fixture = IntelEvidenceFixture()
        fixture.binding["github"] = {"actions": "true", "repository": "example/project", "runId": "123",
            "runAttempt": "1", "sha": "a" * 40, "ref": "refs/heads/reviewed", "job": "audit_full_macos-x64"}
        self.assertEqual(set(IntelEvidenceFixture.tasks), self.assess(fixture))
        arguments, model = fixture.packet()
        self.assertEqual(36, len(arguments["intel_originals"]))
        self.assertEqual(27, len(json.loads(arguments["intel_binding"])["originals"]))
        self.assertEqual(9, len(json.loads(arguments["intel_retirement"])["originals"]))
        with mock.patch.object(GATE, "ROOT", Path("/not/the/observed/host")):
            result = GATE.intel_simulator_retirement(arguments["intel_binding"], arguments["intel_retirement"],
                arguments["intel_originals"], arguments["intel_invocation"])
        self.assertIs(result["shutdownVerified"], True)
        self.assertEqual(model["device"], result["device"])
        self.assertEqual(model["bindingSha256"], result["bindingSha256"])
        self.assertEqual(intel_hash(arguments["intel_retirement"]), result["retirementSha256"])

    def test_missing_originals_wrong_mode_and_changed_invocation_are_not_fallbacks(self):
        for missing in ("intel_binding", "intel_originals", "intel_retirement", "intel_invocation"):
            with self.subTest(missing=missing), self.assertRaisesRegex(ValueError, "INTEL_REQUIRED_ORIGINALS"):
                self.assess(change=lambda arguments, _report: arguments.pop(missing))
        arguments, _model = IntelEvidenceFixture().packet()
        with self.assertRaisesRegex(ValueError, "INTEL_UNEXPECTED_MODE"):
            GATE.assess(example_report(), POLICY, "full", "arm64", TOKEN, **arguments)
        for key, value in (("commit", "c" * 40), ("tree", "c" * 40), ("token", "c" * 32), ("command", [])):
            with self.subTest(field=key), self.assertRaisesRegex(ValueError, "INTEL_INVOCATION_JOIN"):
                self.assess(change=lambda arguments, _report: arguments["intel_invocation"].update({key: value}))

    def test_fixed_host_unique_shutdown_and_actual_booted_originals_are_required(self):
        cases = (("simulator-macos-version", b"14.0\n", "SIMULATOR_UNADMITTED_MACOS"),
            ("simulator-xcode-version", b"Xcode 26.3\nBuild version OTHER\n", "SIMULATOR_UNADMITTED_XCODE"),
            ("simulator-runtimes", b'{"runtimes":[]}', "SIMULATOR_RUNTIME_UNAVAILABLE_OR_CHANGED"),
            ("intel-bootstatus-help", b"unrelated help", "INTEL_BOOTSTATUS_CAPABILITY"))
        for label, raw, reason in cases:
            fixture = IntelEvidenceFixture()
            fixture.stdout[label] = raw
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, reason):
                self.assess(fixture)
        for label, state, reason in (("simulator-devices", "Booted", "SIMULATOR_ONE_ORIGINALLY_SHUTDOWN"),
                                    ("intel-prelaunch", "Shutdown", "INTEL_BOOTED_PRELAUNCH")):
            fixture = IntelEvidenceFixture()
            fixture.stdout[label] = fixture.inventory(state)
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, reason):
                self.assess(fixture)
        fixture = IntelEvidenceFixture()
        inventory = json.loads(fixture.stdout["simulator-devices"])
        duplicate = {**inventory["devices"][fixture.runtime][0], "udid": "BBBBBBBB-BBBB-CCCC-DDDD-EEEEEEEEEEEE"}
        inventory["devices"][fixture.runtime].append(duplicate)
        fixture.stdout["simulator-devices"] = intel_encoded(inventory)
        with self.assertRaisesRegex(ValueError, "SIMULATOR_ONE_ORIGINALLY_SHUTDOWN"):
            self.assess(fixture)

    def test_once_commands_actual_status_order_and_exact_deadline_are_required(self):
        for label, argv in (("intel-bootstatus", ["/usr/bin/xcrun", "simctl", "bootstatus", IntelEvidenceFixture.uuid, "-b"]),
                            ("intel-boot", ["/usr/bin/xcrun", "simctl", "boot", "all"])):
            fixture = IntelEvidenceFixture()
            fixture.rows[label]["argv"] = argv
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, "INTEL_PHASE_COMMAND"):
                self.assess(fixture)
        for key, value in (("exitCode", 1), ("exitCode", True), ("timedOut", True),
                           ("outputLimitExceeded", True), ("ownedGroupDrained", False)):
            fixture = IntelEvidenceFixture()
            fixture.rows["intel-boot"][key] = value
            with self.subTest(field=key), self.assertRaisesRegex(ValueError, "INTEL_PHASE_FAILED"):
                self.assess(fixture)
        fixture = IntelEvidenceFixture()
        fixture.rows["intel-boot"].update(startedUtc="2026-10-07T00:00:00Z", finishedUtc="2026-10-07T00:00:01Z")
        with self.assertRaisesRegex(ValueError, "INTEL_PHASE_ORDER"):
            self.assess(fixture)
        fixture = IntelEvidenceFixture()
        row = fixture.rows["intel-boot"]
        row["finishedUtc"] = (datetime.fromisoformat(row["startedUtc"]) + timedelta(seconds=211)).isoformat()
        with self.assertRaisesRegex(ValueError, "INTEL_PHASE_DEADLINE"):
            self.assess(fixture)

    def test_both_actual_typed_task_maps_must_be_locked_and_false_not_zero(self):
        task = ":p2p-core:iosX64Test"
        for field in ("configured", "inGraph"):
            for key, value in (("device", "BBBBBBBB-BBBB-CCCC-DDDD-EEEEEEEEEEEE"), ("type", "untyped"),
                               ("standalone", True), ("standalone", 0)):
                with self.subTest(field=field, key=key, value=value), \
                        self.assertRaisesRegex(ValueError, "INTEL_ACTUAL_TASK_PROPERTIES"):
                    self.assess(change=lambda _arguments, report: report["intelSimulator"][field][task].update({key: value}))
            with self.assertRaisesRegex(ValueError, "INTEL_ACTUAL_TASK_PROPERTIES"):
                self.assess(change=lambda _arguments, report: report["intelSimulator"][field].pop(task))
        with self.assertRaisesRegex(ValueError, "INTEL_ACTUAL_TASK_PROPERTIES"):
            self.assess(change=lambda _arguments, report: report["intelSimulator"].update(unchanged=False))

    def test_retirement_original_integrity_source_and_complete_roster_are_required(self):
        for key, value in (("shutdownIssued", False), ("errors", ["INTEL_SHUTDOWN_FAILED"]),
                           ("source", {"commit": "c" * 40}), ("deviceAfter", {})):
            fixture = IntelEvidenceFixture()
            fixture.retirement[key] = value
            reason = "INTEL_SHUTDOWN_ORIGINAL" if key == "deviceAfter" else "INTEL_RETIREMENT_CONTEXT"
            with self.subTest(field=key), self.assertRaisesRegex(ValueError, reason):
                self.assess(fixture)
        for kind in ("device", "runtime"):
            fixture = IntelEvidenceFixture()
            fixture.retirement["selected"][kind]["isAvailable"] = 1
            with self.subTest(coerced_availability=kind), self.assertRaisesRegex(ValueError, "INTEL_RETIREMENT_CONTEXT"):
                self.assess(fixture)
        for label, state in (("intel-retire-before", "Shutdown"), ("intel-retire-after", "Booted")):
            fixture = IntelEvidenceFixture()
            fixture.stdout[label] = fixture.inventory(state)
            with self.subTest(label=label), self.assertRaisesRegex(ValueError, "INTEL_SHUTDOWN_ORIGINAL"):
                self.assess(fixture)
        with self.assertRaisesRegex(ValueError, "INTEL_COMPLETE_ORIGINAL_ROSTER"):
            self.assess(change=lambda arguments, _report: arguments["intel_originals"].pop("intel-shutdown/stderr.bin"))
        with self.assertRaisesRegex(ValueError, "INTEL_COMPLETE_ORIGINAL_ROSTER"):
            self.assess(change=lambda arguments, _report: arguments["intel_originals"].update({"extra/stdout.bin": b""}))
        with self.assertRaisesRegex(ValueError, "INTEL_ORIGINAL_HASH_OR_LIMIT"):
            self.assess(change=lambda arguments, _report: arguments["intel_originals"].update({"intel-boot/stdout.bin": b"changed"}))
        with self.assertRaisesRegex(ValueError, "SIMULATOR_JSON"):
            self.assess(change=lambda arguments, _report: arguments.update(intel_binding=b'{"schema":1,"schema":1}'))

    def test_hosted_identity_remains_complete_and_logical_job_is_canonical(self):
        baseline = {"actions": "true", "repository": "example/project", "runId": "123", "runAttempt": "1",
                    "sha": "a" * 40, "ref": "refs/heads/reviewed", "job": "audit_full_macos-x64"}
        for key, value in (("job", "123invalid"), ("job", "two jobs"), ("job", "job/path"), ("job", None),
                           ("runId", "0123"), ("runAttempt", "0"), ("sha", "c" * 40), ("ref", "unbound")):
            fixture = IntelEvidenceFixture()
            fixture.binding["github"] = {**baseline, key: value}
            with self.subTest(field=key, value=value), self.assertRaisesRegex(ValueError, "INTEL_HOSTED_CONTEXT"):
                self.assess(fixture)

    def test_disjoint_init_seam_reads_both_real_properties_and_rechecks_inherited_identity(self):
        text = (ROOT / "gradle/platform-test-coverage.init.gradle").read_text()
        for needle in ("gradle.startParameter.taskNames == intelTasks", "if (intelRequired && ordinaryRequired)",
            "actualType.getMethod('getStandalone')", "if (!intelTasks.contains(task.path)) return",
            "task.getDevice().set(intelBinding.selected.device.udid)", "task.getStandalone().set(false)",
            "entry.task.getStandalone().disallowChanges()", "intelConfigured[path] = intelDeviceRecord(entry)",
            "intelGraph[task.path] = intelDeviceRecord(intelSelected[task.path])",
            "[device: device, type: entry.type, standalone: standalone]",
            "intelGraph.keySet() != (intelTasks as Set)", "report.intelSimulator = intelIdentity +",
            "intelBinding.github != github", "github.job ==~ /[A-Za-z_][A-Za-z0-9_-]*/"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text)


class IntelOwnerLifecycleModels(unittest.TestCase):
    """Owned-driver control flow with supplied native receipts; no native process."""
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="intel-simulator-model-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = {"commit": "a" * 40, "tree": "b" * 40, "status": "", "diffSha256": intel_hash(b"")}
        self.fixture = IntelEvidenceFixture(str(self.root))
        self.calls, self.faults, self.state = [], {}, "Shutdown"
        self.after_product, self.directory = None, None
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        for target, name, value in ((GATE, "ROOT", self.root), (GATE, "POLICY", ROOT / "gradle/platform-test-policy.json")):
            self.stack.enter_context(mock.patch.object(target, name, value))
        self.stack.enter_context(mock.patch.object(GATE, "source_state", side_effect=lambda: dict(self.source)))
        self.stack.enter_context(mock.patch.object(GATE.platform, "system", return_value="Darwin"))
        self.stack.enter_context(mock.patch.object(GATE.platform, "machine", return_value="x86_64"))
        self.stack.enter_context(mock.patch.object(GATE, "_intel_capture_phase", side_effect=self.phase))
        self.stack.enter_context(model_process_launch(self.product))
        self.stack.enter_context(mock.patch.object(GATE.subprocess, "Popen", side_effect=AssertionError("NO_PROCESS")))
        self.stack.enter_context(mock.patch.object(GATE.subprocess, "check_output", side_effect=AssertionError("NO_PROCESS")))
        self.stack.enter_context(mock.patch.object(GATE.os, "killpg", side_effect=AssertionError("NO_NATIVE_SIGNAL")))
        self.stack.enter_context(mock.patch.object(GATE, "terminate_process", return_value=True))
        self.stack.enter_context(mock.patch.object(GATE, "stop_gradle", side_effect=lambda: self.calls.append("stop") or 0))
        self.stack.enter_context(mock.patch.object(GATE.signal, "signal", return_value=signal.SIG_DFL))

    def phase(self, directory, label, argv):
        self.directory = directory
        self.calls.append(label)
        self.assertEqual(self.fixture.argv[label], argv)
        path = directory / label
        path.mkdir(mode=0o700)
        fault = self.faults.get(label)
        if label == "intel-boot" and fault not in ("spawn", "ownership"):
            self.state = "Booted"
        if label == "intel-shutdown" and fault not in ("spawn", "exit", "ownership"):
            self.state = "Shutdown"
        stdout = self.fixture.stdout[label]
        if label in ("simulator-devices", "intel-prelaunch", "intel-retire-before", "intel-retire-after"):
            stdout = self.fixture.inventory(self.state)
        if fault == "host":
            stdout = b"Xcode 26.3\nBuild version WRONG\n"
        row = copy.deepcopy(self.fixture.rows[label])
        row.update(startedUtc=datetime.now(timezone.utc).isoformat(), finishedUtc=datetime.now(timezone.utc).isoformat(),
                   exitCode=None if fault in ("spawn", "ownership") else 1 if fault == "exit" else 0,
                   timedOut=fault == "timeout")
        for stream, raw in (("stdout", stdout), ("stderr", b"")):
            row[stream + "Bytes"], row[stream + "Sha256"] = len(raw), intel_hash(raw)
            GATE._intel_write(path / (stream + ".bin"), raw)
        GATE._intel_write(path / "result.json", intel_encoded(row))
        if fault == "spawn":
            raise OSError("supplied failed spawn")
        if fault == "ownership":
            raise GATE.audit_processes.OwnershipError("supplied native ownership refusal")
        if fault == "interrupt":
            raise KeyboardInterrupt()
        return row

    def product(self, command, *, cwd):
        self.calls.append("gradle")
        self.assertEqual(self.root, cwd)
        raw = (self.directory / "binding.json").read_bytes()
        binding = json.loads(raw)
        fixture = IntelEvidenceFixture(str(self.root), binding["token"])
        expected, model = fixture.packet()
        expected_command = expected["intel_invocation"]["command"]
        expected_command[-1] = "-Pp2pkit.intelSimulatorSha256=" + intel_hash(raw)
        self.assertEqual(expected_command, command)
        model.update(bindingSha256=intel_hash(raw),
                     prelaunchSha256=intel_hash((self.directory / "intel-prelaunch/result.json").read_bytes()))
        report = example_report("ios-x64", "x64")
        report.update(token=binding["token"], intelSimulator=model)
        (self.directory.parent / "execution.json").write_text(json.dumps(report))
        if self.after_product is not None:
            self.after_product()
        return mock.Mock(wait=mock.Mock(return_value=0))

    def invoke(self, environment=None):
        self.calls, self.directory, self.state = [], None, "Shutdown"
        with mock.patch.dict(os.environ, environment or {}, clear=True), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code = GATE.run("ios-x64")
        summary = json.loads((self.directory.parent / "summary.json").read_bytes())
        return code, summary

    def test_native_ownership_refusal_still_attempts_remaining_intel_retirement(self):
        for failed in GATE.INTEL_RETIRE:
            self.faults = {failed: "ownership"}
            with self.subTest(phase=failed):
                code, summary = self.invoke()
                self.assertNotEqual(0, code)
                self.assertEqual("FAIL", summary["result"])
                self.assertTrue(summary["errors"])
                self.assertEqual(list(GATE.INTEL_RETIRE), [name for name in self.calls if name in GATE.INTEL_RETIRE])
                self.assertEqual(1, self.calls.count("stop"))

    def test_once_preparation_real_property_join_and_owned_retirement_order(self):
        environment = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "example/project", "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "1", "GITHUB_SHA": "a" * 40, "GITHUB_REF": "refs/heads/reviewed",
            "GITHUB_JOB": "audit_full_macos-x64"}
        code, summary = self.invoke(environment)
        self.assertEqual(0, code)
        self.assertEqual("PASS", summary["result"])
        self.assertIs(summary["intelSimulatorRetirement"]["shutdownVerified"], True)
        self.assertEqual([*self.fixture.prepare, "gradle", "stop", *self.fixture.retire], self.calls)
        files = [path for path in self.directory.rglob("*") if path.is_file()]
        self.assertEqual(38, len(files))
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o400 for path in files))
        self.assertTrue(all(path.stat().st_mode & 0o777 == 0o700 for path in self.directory.rglob("*") if path.is_dir()))
        self.assertEqual("audit_full_macos-x64", json.loads((self.directory / "binding.json").read_bytes())["github"]["job"])

    def test_boot_failure_and_readiness_interrupt_retire_before_any_gradle_launch(self):
        for label, fault in (("intel-boot", "exit"), ("intel-bootstatus", "timeout"), ("intel-bootstatus", "interrupt")):
            self.faults = {label: fault}
            with self.subTest(label=label, fault=fault):
                code, summary = self.invoke()
                self.assertNotEqual(0, code)
                self.assertEqual("FAIL", summary["result"])
                self.assertEqual(list(self.fixture.retire), self.calls[-3:])
                self.assertEqual(1, self.calls.count("intel-boot"))
                self.assertEqual(1, self.calls.count("intel-shutdown"))
                self.assertNotIn("gradle", self.calls)
                self.assertNotIn("stop", self.calls)
                self.assertIsNone(summary["gradleExitCode"])
                self.assertIsNone(summary["stopExitCode"])

    def test_failed_boot_spawn_reserves_cleanup_without_pointless_shutdown_or_retry(self):
        self.faults = {"intel-boot": "spawn"}
        code, summary = self.invoke()
        self.assertNotEqual(0, code)
        self.assertEqual("FAIL", summary["result"])
        self.assertEqual(["intel-retire-before", "intel-retire-after"], self.calls[-2:])
        self.assertEqual(1, self.calls.count("intel-boot"))
        for absent in ("intel-shutdown", "intel-bootstatus", "gradle", "stop"):
            self.assertNotIn(absent, self.calls)
        self.assertIsNone(json.loads((self.directory / "intel-boot/result.json").read_bytes())["exitCode"])
        retirement = json.loads((self.directory / "retirement.json").read_bytes())
        self.assertIs(retirement["shutdownIssued"], False)
        self.assertIsNone(retirement["bindingSha256"])
        self.assertIn("INTEL_RETIRE_BEFORE_STATE", retirement["errors"])

    def test_host_mismatch_and_partial_ordinary_context_cannot_start_an_intel_product(self):
        self.faults = {"simulator-xcode-version": "host"}
        code, summary = self.invoke()
        self.assertNotEqual(0, code)
        self.assertEqual("FAIL", summary["result"])
        self.assertEqual(["simulator-macos-version", "simulator-xcode-version"], self.calls)
        for environment in ({"P2PKIT_ORDINARY_FULL_SIMULATOR": "/missing"},
                            {"P2PKIT_ORDINARY_FULL_SIMULATOR_SHA256": "a" * 64},
                            {"GITHUB_ACTIONS": "true", "GITHUB_JOB": "complete-gate"}):
            self.calls = []
            with self.subTest(environment=environment), mock.patch.dict(os.environ, environment, clear=True), \
                    self.assertRaisesRegex(ValueError, "Ordinary FULL requires"):
                GATE.run("ios-x64")
            self.assertEqual([], self.calls)

    def test_cleanup_failure_changed_original_and_changed_inherited_job_still_fail(self):
        self.faults = {"intel-shutdown": "exit"}
        code, summary = self.invoke()
        self.assertNotEqual(0, code)
        self.assertIn("INTEL_SHUTDOWN_NOT_OBSERVED", summary["errors"])
        self.assertEqual(1, self.calls.count("intel-shutdown"))
        self.faults = {}
        def change_original():
            path = self.directory / "intel-boot/stdout.bin"
            path.chmod(0o600)
            path.write_bytes(b"changed")
            path.chmod(0o400)
        self.after_product = change_original
        code, summary = self.invoke()
        self.assertNotEqual(0, code)
        self.assertIn("INTEL_ORIGINAL_CHANGED", summary["errors"])
        self.assertEqual(list(self.fixture.retire), self.calls[-3:])
        self.after_product = lambda: os.environ.update(GITHUB_JOB="changed_job")
        code, summary = self.invoke({"GITHUB_JOB": "audit_full_macos-x64"})
        self.assertNotEqual(0, code)
        self.assertIn("INTEL_CONTEXT_CHANGED", summary["errors"])


class IntelCommandCaptureModels(unittest.TestCase):
    def test_phase_diagnostic_only_emits_finite_original_fields(self):
        for label in GATE.INTEL_PREPARE + GATE.INTEL_RETIRE:
            for code in (None, -255, -15, 0, 1, 255):
                row = {"label": label, "exitCode": code, "timedOut": True,
                       "outputLimitExceeded": False, "ownedGroupDrained": False,
                       "argv": ["private-command"], "cwd": "private-path", "stderr": "private-payload"}
                output = io.StringIO()
                with self.subTest(label=label, code=code), contextlib.redirect_stdout(output):
                    GATE._intel_report_phase(row)
                self.assertEqual(output.getvalue(), f"INTEL_PHASE_RESULT {label} EXIT " +
                    ("null" if code is None else str(code)) + " TIMEOUT 1 OVERFLOW 0 DRAINED 0\n")
        for key, value in (("label", "private-label"), ("label", ["intel-boot"]),
                           ("exitCode", True), ("exitCode", "private"), ("exitCode", -256),
                           ("exitCode", 256), ("timedOut", 0), ("outputLimitExceeded", "private"),
                           ("ownedGroupDrained", None)):
            row = {"label": "intel-boot", "exitCode": 1, "timedOut": False,
                   "outputLimitExceeded": False, "ownedGroupDrained": True, key: value}
            output = io.StringIO()
            with self.subTest(key=key, value=value), contextlib.redirect_stdout(output):
                GATE._intel_report_phase(row)
            self.assertEqual(output.getvalue(), "")

    def test_failed_phase_capture_emits_original_null_exit_without_exposing_exception(self):
        with tempfile.TemporaryDirectory(prefix="intel-finite-phase-") as temporary:
            root, output = Path(temporary).resolve(), io.StringIO()
            with mock.patch.object(GATE, "ROOT", root), contextlib.redirect_stdout(output), \
                    mock.patch.object(GATE.ProcessOwner, "start", side_effect=OSError("private-launch-error")), \
                    mock.patch.object(GATE, "terminate_process", return_value=True) as drain, \
                    self.assertRaisesRegex(OSError, "private-launch-error"):
                GATE._intel_capture_phase(root, "simulator-first-launch", ["private-not-executed"])
            drain.assert_called_once()
            self.assertIs(type(drain.call_args.args[0]), GATE.ProcessOwner)
            self.assertIsNone(drain.call_args.args[0].child)
            row = json.loads((root / "simulator-first-launch/result.json").read_bytes())
            self.assertIsNone(row["exitCode"])
            self.assertIs(row["ownedGroupDrained"], True)
            self.assertEqual(output.getvalue(), "INTEL_PHASE_RESULT simulator-first-launch EXIT null "
                             "TIMEOUT 0 OVERFLOW 0 DRAINED 1\n")

    def test_partial_gate_failure_keeps_null_exit_and_both_finite_causes_without_native_retry(self):
        with tempfile.TemporaryDirectory(prefix="intel-partial-gate-") as temporary:
            root, stdout, stderr = Path(temporary).resolve(), io.StringIO(), io.StringIO()
            child = mock.Mock(stdout=None, stderr=None, returncode=None)
            child.poll.return_value = None
            scope = mock.Mock(leaders=[child], discovery_errors=set(), pending_discoveries={},
                              launches=[{"created": True, "gateReleased": False, "pid": 999,
                                         "requestedArgv": ["PRIVATE_ARG"]}])
            failure = GATE.audit_processes.OwnershipError("Darwin exec gate did not establish readiness")
            scope.spawn.side_effect = failure
            scope.drain.return_value = [{"pid": 999, "private": "PRIVATE_IDENTITY"}]
            with mock.patch.object(GATE, "ROOT", root), \
                    mock.patch.object(GATE.ci_evidence, "local_command_scope", return_value=scope), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr), \
                    self.assertRaises(GATE.audit_processes.OwnershipError) as caught:
                GATE._intel_capture_phase(root, "intel-bootstatus", ["PRIVATE_ARG"])
            self.assertIs(failure, caught.exception)
            row = json.loads((root / "intel-bootstatus/result.json").read_bytes())
            self.assertIsNone(row["exitCode"])
            self.assertFalse(row["ownedGroupDrained"])
            self.assertEqual((0, 0), (row["stdoutBytes"], row["stderrBytes"]))
            launch = json.loads(next(line.split(" ", 1)[1] for line in stderr.getvalue().splitlines()
                                     if line.startswith("PLATFORM_LAUNCH_FAILURE ")))
            drain = json.loads(next(line.split(" ", 1)[1] for line in stderr.getvalue().splitlines()
                                    if line.startswith("PLATFORM_RETIREMENT_FAILURE ")))
            self.assertEqual("GATE_NOT_READY", launch["reason"])
            self.assertIs(launch["created"], True)
            self.assertIs(launch["gateReleased"], False)
            self.assertIs(launch["childReturned"], False)
            self.assertEqual({"returned": True, "live": 1, "leaders": 1, "discoveryErrors": 0,
                              "pendingDiscoveries": 0}, drain["drainState"])
            self.assertEqual("PLATFORM_DRIVER", drain["nativeError"]["sourceFrames"][-1]["source"])
            self.assertNotIn("PRIVATE_ARG", stderr.getvalue())
            self.assertNotIn("PRIVATE_IDENTITY", stderr.getvalue())
            self.assertNotIn(str(root), stderr.getvalue())
            scope.spawn.assert_called_once(); scope.drain.assert_called_once(); scope.close.assert_called_once()
            scope.discover.assert_not_called(); scope.description.assert_not_called()

    def test_bootstatus_capture_uses_only_its_named_work_budget(self):
        # Only test-local constants are scaled; the real capture and drain run.
        with tempfile.TemporaryDirectory(prefix="intel-bootstatus-budget-") as temporary:
            root = Path(temporary).resolve()
            with mock.patch.object(GATE, "ROOT", root), \
                    mock.patch.object(GATE.simulator, "SECONDS", 0.1), \
                    mock.patch.object(GATE, "INTEL_BOOTSTATUS_SECONDS", 2):
                cases = (("intel-bootstatus", 0.3, False), ("intel-bootstatus-help", 30, True),
                         ("intel-boot", 30, True), ("intel-bootstatus-extra", 30, True),
                         ("INTEL-BOOTSTATUS", 30, True), ("intel-bootstatus", 30, True))
                for ordinal, (label, delay, timeout) in enumerate(cases):
                    directory = root / str(ordinal)
                    directory.mkdir(mode=0o700)
                    script = "import time; time.sleep(%r); print('ready')" % delay
                    with self.subTest(label=label, delay=delay):
                        row = GATE._intel_capture_phase(directory, label,
                            [sys.executable, "-I", "-B", "-S", "-c", script])
                        self.assertIs(row["timedOut"], timeout)
                        self.assertIs(row["outputLimitExceeded"], False)
                        self.assertIs(row["ownedGroupDrained"], True)
                        if timeout:
                            self.assertIsNotNone(row["exitCode"])
                            self.assertNotEqual(0, row["exitCode"])
                        else:
                            self.assertEqual(0, row["exitCode"])
                            self.assertEqual(b"ready\n", (directory / label / "stdout.bin").read_bytes())
                        self.assertEqual(row, json.loads((directory / label / "result.json").read_bytes()))
                        for stream in ("stdout", "stderr"):
                            path = directory / label / (stream + ".bin")
                            raw = path.read_bytes()
                            self.assertEqual(len(raw), row[stream + "Bytes"])
                            self.assertEqual(intel_hash(raw), row[stream + "Sha256"])
                            self.assertEqual(0o400, path.stat().st_mode & 0o777)

    def test_bounded_fake_child_capture_overflow_timeout_and_failed_spawn_keep_originals(self):
        with tempfile.TemporaryDirectory(prefix="intel-command-capture-") as temporary:
            root = Path(temporary).resolve()
            with mock.patch.object(GATE, "ROOT", root):
                cases = (("normal", "print('bounded')", False, False),
                         ("overflow", "import os; os.write(1,b'x'*1024)", True, False),
                         ("timeout", "import time; time.sleep(30)", False, True))
                for label, script, overflow, timeout in cases:
                    with self.subTest(label=label), mock.patch.object(GATE, "INTEL_STDOUT_LIMIT", 512), \
                            mock.patch.object(GATE.simulator, "SECONDS", 0.1 if timeout else 5):
                        row = GATE._intel_capture_phase(root, label, [sys.executable, "-I", "-B", "-S", "-c", script])
                    self.assertIs(row["outputLimitExceeded"], overflow)
                    self.assertIs(row["timedOut"], timeout)
                    self.assertIs(row["ownedGroupDrained"], True)
                    self.assertLessEqual((root / label / "stdout.bin").stat().st_size, 512)
                    self.assertEqual(0o400, (root / label / "result.json").stat().st_mode & 0o777)
                    self.assertEqual(row, json.loads((root / label / "result.json").read_bytes()))
                with mock.patch.object(GATE.ProcessOwner, "start", side_effect=OSError("supplied failed spawn")), \
                        self.assertRaises(OSError):
                    GATE._intel_capture_phase(root, "spawn", ["not-executed"])
                failed = json.loads((root / "spawn/result.json").read_bytes())
                self.assertIsNone(failed["exitCode"])
                self.assertIs(failed["ownedGroupDrained"], True)
                self.assertEqual(b"", (root / "spawn/stdout.bin").read_bytes())
                owned = mock.Mock(stdout=io.BytesIO(), stderr=io.BytesIO(), returncode=-15)
                def interrupt(_signum, _frame):
                    raise KeyboardInterrupt()
                def interrupted_launch(*_args, **_kwargs):
                    # Deliver before the model supplier returns its child.
                    signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
                    return owned
                previous = signal.signal(signal.SIGTERM, interrupt)
                try:
                    with model_process_launch(interrupted_launch), \
                            mock.patch.object(GATE, "terminate_process", return_value=True) as drain, \
                            self.assertRaises(KeyboardInterrupt):
                        GATE._intel_capture_phase(root, "interrupted", ["not-executed"])
                    drain.assert_called_once()
                    self.assertIs(drain.call_args.args[0].child, owned)
                    interrupted = json.loads((root / "interrupted/result.json").read_bytes())
                    self.assertEqual(-15, interrupted["exitCode"])
                    self.assertIs(interrupted["ownedGroupDrained"], True)
                finally:
                    signal.signal(signal.SIGTERM, previous)


class OrdinarySimulatorModels(unittest.TestCase):
    """Offline receipt/driver/coverage models only; ALL process/native calls blocked.

    No fake executable, Git subprocess, Gradle, KGP, Xcode or simulator runs in
    this class. Groovy seam checks below are source checks, not compilation.
    """
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="ordinary-simulator-model-")
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root, self.session = self.base / "source", self.base / "ordinary"
        self.root.mkdir(mode=0o700)
        self.source = {"commit": "a" * 40, "tree": "b" * 40, "status": "", "diffSha256": GATE.simulator.digest(b"")}
        self.job, self.reserved, self.uuid = "c" * 32, "d" * 32, "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE"
        self.calls, self.report_change, self.after_product = [], None, None
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(mock.patch.object(GATE, "ROOT", self.root))
        self.stack.enter_context(mock.patch.object(GATE, "POLICY", ROOT / "gradle/platform-test-policy.json"))
        self.stack.enter_context(mock.patch.object(GATE, "source_state", side_effect=lambda: dict(self.source)))
        self.stack.enter_context(mock.patch.object(GATE.platform, "system", return_value="Darwin"))
        self.stack.enter_context(mock.patch.object(GATE.platform, "machine", return_value="arm64"))
        self.stack.enter_context(mock.patch.object(GATE.os, "getppid", return_value=65001))
        self.stack.enter_context(model_process_launch(self.product))
        self.stack.enter_context(mock.patch.object(GATE.subprocess, "Popen", side_effect=AssertionError("NO_REAL_PROCESS")))
        self.stack.enter_context(mock.patch.object(GATE.subprocess, "check_output", side_effect=AssertionError("NO_REAL_PROCESS")))
        self.stack.enter_context(mock.patch.object(GATE.audit_processes.ctypes, "CDLL", side_effect=AssertionError("NO_NATIVE_API")))
        self.stack.enter_context(mock.patch.object(GATE.os, "killpg", side_effect=AssertionError("NO_NATIVE_SIGNAL")))
        self.stack.enter_context(mock.patch.object(GATE, "terminate_process", return_value=True))
        self.stack.enter_context(mock.patch.object(GATE, "stop_gradle", side_effect=lambda: self.calls.append(["--stop"]) or 0))
        self.stack.enter_context(mock.patch.object(GATE.signal, "signal", return_value=signal.SIG_DFL))
        self.install_binding()

    def save(self, path, raw):
        if not isinstance(raw, bytes):
            raw = GATE.simulator.encoded(raw)
        parents = []
        parent = path.parent
        while not parent.exists():
            parents.append(parent)
            parent = parent.parent
        for parent in reversed(parents):
            parent.mkdir(mode=0o700)
        path.write_bytes(raw)
        path.chmod(0o600)
        return raw

    def install_binding(self, role="macos-arm64"):
        sim = GATE.simulator
        native = sim.HOSTS[role]
        self.run = {"schema": 1, "scope": "CLOSED_ORDINARY_TEST_CONTROLLER", "profile": "full", "role": role,
            "kind": "command", "command": ["python3", "scripts/run-platform-tests.py", "full"], "job": "f" * 32,
            "root": str(self.root), "session": str(self.session), "source": {key: self.source[key] for key in ("commit", "tree")},
            "jobBudgetSha256": "1" * 64, "primarySimulatorRequired": True, "developerDir": None, "ancestorInvocationIds": []}
        state = self.session / "state"
        canonical = {"schema": 1, "id": self.job, "root": str(self.root), "host": role, "gradleHome": str(state / "gradle-home"),
                     "source": dict(self.source), "preexistingOutputPaths": []}
        request = {"ownerKind": "audit", "ownerState": str(state), "home": str(state / "gradle-home"), "root": str(self.root),
                   "source": dict(self.source), "command": self.run["command"],
                   "owner": {"job": self.job, "productInvocation": self.reserved, "stopInvocation": None}}
        self.inventory = {"devices": {native["runtime"]: [{"name": "iPhone 17", "udid": self.uuid, "state": "Shutdown",
            "isAvailable": True, "deviceTypeIdentifier": "com.apple.CoreSimulator.SimDeviceType.iPhone-17"}]}}
        stdout = {"simulator-macos-version": (native["osMajor"] + ".0\n").encode(),
                  "simulator-xcode-version": native["xcode"].encode(), "simulator-first-launch": b"",
                  "simulator-runtimes": sim.encoded({"runtimes": [{"identifier": native["runtime"], "version": native["version"],
                                                                  "isAvailable": True}]}),
                  "simulator-devices": sim.encoded(self.inventory)}
        observations = {label: ({"phase": label, "argv": sim.command(label), "exitCode": 0, "launchAttempted": True,
            "scopeAttempted": True, "retirement": "KNOWN", "errors": [], "survivors": [], "ownership": {"discoveryErrors": []},
            "job": self.run["job"], "state": str(self.session), "home": str(self.session / "control-home"),
            "jobBudgetSha256": self.run["jobBudgetSha256"], "developerDir": None}, stdout[label], b"") for label in sim.PREPARE}
        run_raw = self.save(self.session / "run-context.json", self.run)
        canonical_raw = self.save(state / "context.json", canonical)
        request_raw = self.save(self.session / "evidence/custody/request.json", request)
        admission = sim.admission_record(run_raw, canonical_raw, observations, None)
        self.save(self.session / "evidence/simulator/admission.json", admission)
        self.binding = sim.binding_record(run_raw, canonical_raw, request_raw, admission)
        self.save(self.session / sim.RELATIVE, self.binding)
        environment = GATE.audit_processes.ownership_environment({}, self.job, "e" * 32, str(state), str(state / "gradle-home"))
        environment = GATE.audit_processes.ownership_environment(environment, self.job, self.reserved,
                                                                str(state), str(state / "gradle-home"))
        self.environment = {**environment, sim.PATH_ENV: str(self.session / sim.RELATIVE), sim.HASH_ENV: sim.digest(self.binding)}
        start = {"schema": 1, "id": self.reserved, "purpose": "ordinary-full", "kind": "command",
            "requestedArgv": self.run["command"], "cwd": str(self.root), "wrapper": str(self.root / "gradlew"),
            "host": role, "jobId": self.job, "gradleHome": str(state / "gradle-home"),
            "startedUtc": "2026-09-16T00:00:00Z", "controllerPid": 65001, "ancestorInvocationIds": ["e" * 32],
            "sourceBefore": None, "sourceAfter": None, "productExitCode": None, "stopExitCode": None,
            "finalExitCode": 125, "sourceUnchanged": False, "ownedSurvivors": [], "errors": [],
            "evidenceDirectory": str(state / "evidence" / self.reserved)}
        self.start = self.save(state / "evidence" / self.reserved / "start.json", start)
        row = {**observations["simulator-devices"][0], "phase": sim.PRELAUNCH, "argv": sim.command(sim.PRELAUNCH),
               "simulatorBindingSha256": sim.digest(self.binding)}
        stdout = sim.encoded(self.inventory)
        for name, value in (("result.json", sim.encoded(row)), ("stdout.log", stdout), ("stderr.log", b"")):
            self.save(self.session / "evidence/commands" / sim.PRELAUNCH / name, value)
        self.prelaunch = sim.prelaunch_record(run_raw, self.binding, row, stdout, b"")
        self.save(self.session / "evidence/simulator/prelaunch.json", self.prelaunch)

    def product(self, command, *, cwd):
        self.assertEqual(cwd, self.root)
        self.calls.append(command)
        token = next(arg.split("=", 1)[1] for arg in command if arg.startswith("-Pp2pkit.testCoverageToken="))
        report = example_report()
        report["token"] = token
        if GATE.simulator.PATH_ENV in os.environ:
            identity = GATE.simulator.coverage_identity(self.binding, self.start, self.prelaunch)
            properties = {path: {"device": self.uuid, "type": GATE.simulator.TYPE} for path in GATE.simulator.TASKS}
            report["ordinarySimulator"] = {**identity, "configured": properties, "inGraph": copy.deepcopy(properties), "unchanged": True}
        if self.report_change:
            self.report_change(report)
        self.save(self.root / "build/reports/platform-tests" / token / "execution.json", report)
        if self.after_product:
            self.after_product()
        return mock.Mock(wait=mock.Mock(return_value=0))

    def invoke(self, profile="full"):
        with mock.patch.dict(os.environ, self.environment, clear=True), contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            return GATE.run(profile)

    def summary(self):
        paths = list(self.root.glob("build/reports/platform-tests/*/summary.json"))
        self.assertEqual(len(paths), 1)
        return json.loads(paths[0].read_bytes())

    def test_bound_driver_keeps_full_check_and_records_actual_property_model(self):
        self.assertEqual(self.invoke(), 0)
        self.assertEqual(self.calls[-1], ["--stop"])
        self.assertEqual(self.calls[0][1:11], ["check", *GATE.FLAGS])
        self.assertIn("-Pp2pkit.ordinarySimulatorBinding=" + str(self.session / GATE.simulator.RELATIVE), self.calls[0])
        self.assertIn("-Pp2pkit.ordinarySimulatorStartSha256=" + GATE.simulator.digest(self.start), self.calls[0])
        self.assertIn("-Pp2pkit.ordinarySimulatorPrelaunchSha256=" + GATE.simulator.digest(self.prelaunch), self.calls[0])
        self.assertEqual(self.summary()["ordinarySimulator"], GATE.simulator.coverage_identity(self.binding, self.start, self.prelaunch))
        self.assertEqual(self.summary()["result"], "PASS")

    def test_standalone_full_stays_unbound_without_changing_its_selector(self):
        self.environment = {}
        self.assertEqual(self.invoke(), 0)
        self.assertEqual(self.calls[0][1:11], ["check", *GATE.FLAGS])
        self.assertFalse(any("ordinarySimulator" in argument for argument in self.calls[0]))
        self.assertNotIn("ordinarySimulator", self.summary())

    def test_tag_release_full_stays_standalone_without_changing_its_selector(self):
        self.environment = {"GITHUB_ACTIONS": "true", "GITHUB_JOB": "verify-release", "GITHUB_EVENT_NAME": "push",
                            "GITHUB_REF": "refs/tags/v0.8.0-fixture", "GITHUB_REF_TYPE": "tag"}
        self.assertEqual(self.invoke(), 0)
        self.assertEqual(self.calls[0][1:11], ["check", *GATE.FLAGS])
        self.assertFalse(any("ordinarySimulator" in argument for argument in self.calls[0]))
        self.assertNotIn("ordinarySimulator", self.summary())

    def test_tag_label_cannot_hide_an_ordinary_parent_context(self):
        self.environment.update(GITHUB_ACTIONS="true", GITHUB_JOB="verify-release",
                                GITHUB_EVENT_NAME="push", GITHUB_REF="refs/tags/v0.8.0-fixture")
        self.environment.pop(GATE.simulator.PATH_ENV)
        self.environment.pop(GATE.simulator.HASH_ENV)
        with self.assertRaisesRegex(ValueError, "binding path"):
            self.invoke()
        self.assertEqual(self.calls, [])

    def test_tag_label_cannot_ignore_either_partial_ordinary_marker(self):
        for marker in (GATE.simulator.PATH_ENV, GATE.simulator.HASH_ENV):
            self.environment = {"GITHUB_ACTIONS": "true", "GITHUB_JOB": "verify-release",
                                "GITHUB_REF": "refs/tags/v0.8.0-fixture", marker: "synthetic-partial-binding"}
            with self.subTest(marker=marker), self.assertRaisesRegex(ValueError, "canonical simulator context"):
                self.invoke()
            self.assertEqual(self.calls, [])

    def test_missing_markers_cannot_fall_back_from_the_canonical_parent_context(self):
        for name in (GATE.simulator.PATH_ENV, GATE.simulator.HASH_ENV):
            self.environment.pop(name)
        with self.assertRaisesRegex(ValueError, "binding path"):
            self.invoke()
        self.assertEqual(self.calls, [])

    def test_missing_hash_marker_refuses_before_gradle(self):
        self.environment.pop(GATE.simulator.HASH_ENV)
        with self.assertRaisesRegex(ValueError, "source/context/reservation"):
            self.invoke()
        self.assertEqual(self.calls, [])

    def test_recognized_ordinary_job_without_a_canonical_context_is_not_standalone(self):
        self.environment = {"GITHUB_ACTIONS": "true", "GITHUB_JOB": "complete-gate"}
        with self.assertRaisesRegex(ValueError, "canonical simulator context"):
            self.invoke()
        self.assertEqual(self.calls, [])

    def test_simulator_task_option_or_different_profile_cannot_replace_aggregate_check(self):
        with self.assertRaises(ValueError):
            self.invoke("ios-arm64")
        self.assertEqual(self.calls, [])
        self.assertEqual(GATE.PROFILES["full"], ["check"])

    def test_stale_source_and_different_native_role_refuse_before_gradle(self):
        self.source["tree"] = "f" * 40
        with self.assertRaisesRegex(ValueError, "primary canonical invocation"):
            self.invoke()
        self.source["tree"] = "b" * 40
        self.install_binding("macos-x64")
        with self.assertRaisesRegex(ValueError, "primary canonical invocation"):
            self.invoke()
        self.assertEqual(self.calls, [])

    def test_other_reserved_invocation_cannot_reuse_this_device_binding(self):
        chain = self.environment[GATE.audit_processes.CHAIN_ENV]
        domains = json.loads(self.environment[GATE.audit_processes.DOMAINS_ENV])
        domains[-1]["id"] = "0" * 32
        self.environment[GATE.audit_processes.CHAIN_ENV] = chain.rsplit(":", 1)[0] + ":" + "0" * 32
        self.environment[GATE.audit_processes.DOMAINS_ENV] = json.dumps(domains)
        with self.assertRaisesRegex(ValueError, "primary canonical invocation"):
            self.invoke()
        self.assertEqual(self.calls, [])

    def test_public_or_linked_receipt_is_not_accepted_as_controller_custody(self):
        path = self.session / GATE.simulator.RELATIVE
        path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, "not private"):
            self.invoke()
        path.chmod(0o600)
        real = path.with_name("binding-original.json")
        path.rename(real)
        path.symlink_to(real)
        with self.assertRaisesRegex(ValueError, "linked"):
            self.invoke()
        self.assertEqual(self.calls, [])

    def test_mutated_binding_after_product_cannot_reuse_original_pass(self):
        def mutate():
            path = self.session / "evidence/simulator/admission.json"
            self.save(path, path.read_bytes() + b" ")
        self.after_product = mutate
        self.assertNotEqual(self.invoke(), 0)
        self.assertEqual(self.calls[-1], ["--stop"])
        self.assertEqual(self.summary()["result"], "FAIL")
        self.assertIn("source/context/reservation", " ".join(self.summary()["errors"]))

    def test_all_tests_passing_without_property_report_is_still_failed(self):
        self.report_change = lambda report: report.pop("ordinarySimulator")
        self.assertNotEqual(self.invoke(), 0)
        self.assertEqual(self.calls[-1], ["--stop"])
        self.assertIn("SIMULATOR_COVERAGE_BINDING", " ".join(self.summary()["errors"]))

    def test_wrong_device_property_fails_despite_other_successful_outcomes(self):
        self.report_change = lambda report: report["ordinarySimulator"]["inGraph"][GATE.simulator.TASKS[0]].update(device="other")
        self.assertNotEqual(self.invoke(), 0)
        self.assertEqual(self.summary()["result"], "FAIL")
        self.assertIn("SIMULATOR_KGP_PROPERTY_CHANGED", " ".join(self.summary()["errors"]))

    def test_changed_typed_property_model_graph_and_receipt_are_rejected(self):
        identity = GATE.simulator.coverage_identity(self.binding, self.start, self.prelaunch)
        selected = {path: {"device": self.uuid, "type": GATE.simulator.TYPE} for path in GATE.simulator.TASKS}
        baseline = example_report()
        baseline["ordinarySimulator"] = {**identity, "configured": selected, "inGraph": copy.deepcopy(selected), "unchanged": True}
        for kind in ("missing-task", "extra-task", "wrong-type", "missing-graph", "stale-binding", "mutable"):
            report = copy.deepcopy(baseline)
            ordinary = report["ordinarySimulator"]
            if kind == "missing-task": ordinary["configured"].pop(GATE.simulator.TASKS[0])
            elif kind == "extra-task": ordinary["configured"][":other:test"] = selected[GATE.simulator.TASKS[0]]
            elif kind == "wrong-type": ordinary["configured"][GATE.simulator.TASKS[0]]["type"] = "Object"
            elif kind == "missing-graph": ordinary["inGraph"].pop(GATE.simulator.TASKS[0])
            elif kind == "stale-binding": ordinary["bindingSha256"] = "f" * 64
            else: ordinary["unchanged"] = False
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                GATE.assess(report, POLICY, "full", "arm64", TOKEN, self.binding, self.start, self.prelaunch)

    def test_rpc_ordinary_properties_and_applicable_graph_are_mandatory(self):
        identity = GATE.simulator.coverage_identity(self.binding, self.start, self.prelaunch)
        selected = {path: {"device": self.uuid, "type": GATE.simulator.TYPE} for path in GATE.simulator.TASKS}
        baseline = example_report()
        baseline["ordinarySimulator"] = {**identity, "configured": selected,
                                        "inGraph": copy.deepcopy(selected), "unchanged": True}
        GATE.assess(baseline, POLICY, "full", "arm64", TOKEN, self.binding, self.start, self.prelaunch)
        for module in (":p2p-rpc", ":p2p-sample-rpc"):
            for suffix in (":iosSimulatorArm64Test", ":iosX64Test"):
                task = module + suffix
                for field, reason in (("configured", "SIMULATOR_KGP_TASK_MODEL_CHANGED"),
                                      ("inGraph", "SIMULATOR_KGP_GRAPH_CHANGED")):
                    report = copy.deepcopy(baseline)
                    report["ordinarySimulator"][field].pop(task)
                    with self.subTest(task=task, field=field), self.assertRaisesRegex(ValueError, reason):
                        GATE.assess(report, POLICY, "full", "arm64", TOKEN,
                                    self.binding, self.start, self.prelaunch)
            report = copy.deepcopy(baseline)
            task = module + ":iosSimulatorArm64Test"
            report["ordinarySimulator"]["inGraph"].pop(task)
            report["tests"][task]["inGraph"] = False
            with self.subTest(applicable=task), self.assertRaisesRegex(ValueError, "SIMULATOR_APPLICABLE_GRAPH_MISSING"):
                GATE.simulator.assess_coverage(report, self.binding, self.start, self.prelaunch)

    def test_absent_actual_start_is_rejected_before_gradle(self):
        (self.session / "state/evidence" / self.reserved / "start.json").unlink()
        with self.assertRaises(FileNotFoundError):
            self.invoke()
        self.assertEqual(self.calls, [])

    def test_new_outer_ancestor_cannot_be_invented_with_matching_start_and_domains(self):
        processes = GATE.audit_processes
        domains = processes.ownership_domains(self.environment[processes.CHAIN_ENV], self.environment[processes.DOMAINS_ENV])
        domains.insert(0, {**domains[0], "id": "0" * 32})
        self.environment[processes.CHAIN_ENV] = ":".join(row["id"] for row in domains)
        self.environment[processes.DOMAINS_ENV] = json.dumps(domains)
        start = json.loads(self.start)
        start["ancestorInvocationIds"].insert(0, "0" * 32)
        self.save(self.session / "state/evidence" / self.reserved / "start.json", start)
        with self.assertRaisesRegex(ValueError, "primary canonical invocation"):
            self.invoke()
        self.assertEqual(self.calls, [])

    def test_foreign_malformed_parent_or_final_receipt_cannot_replace_actual_start(self):
        path = self.session / "state/evidence" / self.reserved / "start.json"
        baseline = json.loads(self.start)
        changes = {"schema": True, "id": "0" * 32, "purpose": "foreign", "kind": "gradle", "requestedArgv": ["help"],
            "cwd": "/foreign", "wrapper": "/foreign/gradlew", "host": "macos-x64", "jobId": "0" * 32,
            "gradleHome": "/foreign/home", "controllerPid": 65002, "ancestorInvocationIds": ["0" * 32],
            "sourceBefore": self.source, "sourceAfter": self.source, "productExitCode": 0, "stopExitCode": 0,
            "finalExitCode": 0, "sourceUnchanged": True, "ownedSurvivors": [1], "errors": ["failed"],
            "evidenceDirectory": "/foreign/evidence", "startedUtc": "not-time"}
        for key, value in changes.items():
            self.save(path, {**baseline, key: value})
            with self.subTest(field=key), self.assertRaises(ValueError):
                self.invoke()
        for raw in (b"[]", b"{", b'{"schema":1,"schema":1}'):
            self.save(path, raw)
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                self.invoke()
        self.assertEqual(self.calls, [])

    def test_actual_start_byte_mutation_after_product_fails_with_same_home_stop(self):
        def mutate():
            path = self.session / "state/evidence" / self.reserved / "start.json"
            self.save(path, path.read_bytes() + b" ")
        self.after_product = mutate
        self.assertNotEqual(self.invoke(), 0)
        self.assertEqual(self.calls[-1], ["--stop"])
        self.assertEqual(self.summary()["result"], "FAIL")

    def test_prelaunch_original_change_refuses_before_gradle(self):
        path = self.session / "evidence/commands" / GATE.simulator.PRELAUNCH / "stdout.log"
        value = json.loads(path.read_bytes())
        value["devices"][GATE.simulator.HOSTS["macos-arm64"]["runtime"]][0]["state"] = "Booted"
        self.save(path, value)
        with self.assertRaisesRegex(ValueError, "SIMULATOR_PRELAUNCH_EXTERNAL_STATE_CHANGE"):
            self.invoke()
        self.assertEqual(self.calls, [])

    def test_selector_rejects_ambiguous_unavailable_relabelled_or_wrong_runtime_devices(self):
        runtime = GATE.simulator.HOSTS["macos-arm64"]["runtime"]
        for kind in ("ambiguous", "booted", "unavailable", "numeric-availability", "wrong-type", "bad-uuid", "wrong-runtime",
                     "duplicate-uuid"):
            inventory = copy.deepcopy(self.inventory)
            row = inventory["devices"][runtime][0]
            if kind == "ambiguous": inventory["devices"][runtime].append({**row, "udid": "BBBBBBBB-BBBB-CCCC-DDDD-EEEEEEEEEEEE"})
            elif kind == "booted": row["state"] = "Booted"
            elif kind == "unavailable": row["isAvailable"] = False
            elif kind == "numeric-availability": row["isAvailable"] = 1
            elif kind == "wrong-type": row["deviceTypeIdentifier"] = "com.apple.CoreSimulator.SimDeviceType.iPhone-16"
            elif kind == "bad-uuid": row["udid"] = "all"
            elif kind == "wrong-runtime": inventory["devices"] = {"com.apple.CoreSimulator.SimRuntime.iOS-18-2": [row]}
            else: inventory["devices"]["different-runtime"] = [dict(row)]
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                GATE.simulator.original("simulator-devices", "macos-arm64", GATE.simulator.encoded(inventory))

    def test_two_native_combinations_and_closed_commands_never_admit_old_writer_profile(self):
        for role, major, xcode in (("macos-arm64", "26", "Xcode 26.5\nBuild version 17F42\n"),
                                  ("macos-x64", "15", "Xcode 26.3\nBuild version 17C529\n")):
            self.assertEqual(GATE.simulator.original("simulator-macos-version", role, (major + ".0\n").encode()), major + ".0")
            self.assertEqual(GATE.simulator.original("simulator-xcode-version", role, xcode.encode()), xcode)
            for label, raw in (("simulator-macos-version", b"14.7\n"),
                               ("simulator-xcode-version", b"Xcode 16.2\nBuild version 16C5032a\n")):
                with self.subTest(role=role, label=label), self.assertRaises(ValueError):
                    GATE.simulator.original(label, role, raw)
        for name in ("shutdown-all", "arbitrary-command", "simulator-boot"):
            with self.assertRaises(ValueError):
                GATE.simulator.command(name)
        selected = GATE.simulator.parse(self.binding)["selected"]
        self.assertEqual(GATE.simulator.command(GATE.simulator.SHUTDOWN, selected),
                         ["/usr/bin/xcrun", "simctl", "shutdown", self.uuid])

    def test_typed_kgp_source_seam_is_preserved_without_claiming_runtime_execution(self):
        source = (ROOT / "gradle/platform-test-coverage.init.gradle").read_text()
        for needle in ("plugin.class.classLoader.loadClass(simulatorType)", "Property.isAssignableFrom",
                       "actualType.getMethod('getDevice')", "task.getDevice().set(binding.selected.device.udid)",
                       "entry.task.getDevice().disallowChanges()", "simulatorConfigured[path] = deviceRecord(entry)",
                       "simulatorGraph[task.path] = deviceRecord(selected[task.path])"):
            self.assertIn(needle, source)
        self.assertTrue(all(path in source for path in GATE.simulator.TASKS))
        self.assertNotIn("P2PKIT_WRITER_", source)
        for name in ("enabled", "standalone", "timeout", "executable", "filter"):
            self.assertNotRegex(source, r"task\." + name + r"\s*=")


FAKE_GRADLE = r'''
import json, os, pathlib, signal, subprocess, sys, time
root = pathlib.Path.cwd()
with (root / "trace.jsonl").open("a") as stream:
    stream.write(json.dumps(sys.argv[1:]) + "\n")
mode = os.environ.get("P2PKIT_FAKE_PLATFORM_MODE", "pass")
if sys.argv[1:] == ["--stop"]:
    sys.exit(7 if mode == "stop-failure" else 0)
if mode == "wait":
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(90)"])
    def terminated(signum, frame):
        child.wait(timeout=10)
        sys.exit(143)
    signal.signal(signal.SIGTERM, terminated)
    (root / "worker.pid").write_text(str(child.pid))
    time.sleep(90)
    sys.exit(8)
token = next(arg.split("=", 1)[1] for arg in sys.argv if arg.startswith("-Pp2pkit.testCoverageToken="))
if mode == "no-report":
    sys.exit(0)
report = json.loads((root / "fixture.json").read_text())
report["token"] = "0" * 32 if mode == "stale-token" else token
if mode == "build-failure":
    report["buildFailed"] = True
if mode == "source-change":
    (root / "tracked.txt").write_text("changed during execution\n")
path = root / "build/reports/platform-tests" / token / "execution.json"
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text("[]" if mode == "malformed" else json.dumps(report))
sys.exit(9 if mode in ("exit-failure", "build-failure") else 0)
'''


def standalone_fixture_environment(mode):
    """Environment for this synthetic fake-wrapper fixture, never production.

    The fixture is deliberately standalone even when the test runner itself is
    real ordinary CI. Do not copy its identity, canonical ownership, simulator
    markers, credentials or Gradle home into an unrelated fake invocation.
    Explicit OrdinarySimulatorModels above keep the anti-fallback coverage.
    """
    names = ("PATH", "HOME", "TMPDIR", "TMP", "TEMP", "SystemRoot", "WINDIR", "COMSPEC")
    return {**{name: os.environ[name] for name in names if name in os.environ}, "P2PKIT_FAKE_PLATFORM_MODE": mode}


class DriverFixtureEnvironmentModels(unittest.TestCase):
    def test_fixture_environment_is_closed_and_preserves_process_essentials(self):
        essentials = {"PATH": "/synthetic/bin", "HOME": "/synthetic/home", "TMPDIR": "/synthetic/tmp",
                      "SystemRoot": "C:\\SyntheticWindows"}
        other = {"GITHUB_ACTIONS": "true", "GITHUB_JOB": "complete-gate", "GITHUB_TOKEN": "synthetic-not-a-token",
                 GATE.audit_processes.STATE_ENV: "/synthetic/ordinary-state",
                 GATE.audit_processes.JOB_ENV: "a" * 32, GATE.audit_processes.CHAIN_ENV: "b" * 32,
                 GATE.audit_processes.DOMAINS_ENV: "synthetic-domain",
                 GATE.audit_processes.LOCAL_CHAIN_ENV: "d" * 32,
                 GATE.simulator.PATH_ENV: "/synthetic/simulator-binding", GATE.simulator.HASH_ENV: "c" * 64,
                 "GRADLE_USER_HOME": "/synthetic/ordinary-home", "P2PKIT_FAKE_PLATFORM_MODE": "foreign"}
        with mock.patch.dict(os.environ, {**essentials, **other}, clear=True):
            self.assertEqual(standalone_fixture_environment("pass"), {**essentials, "P2PKIT_FAKE_PLATFORM_MODE": "pass"})
            self.assertEqual(standalone_fixture_environment("wait"), {**essentials, "P2PKIT_FAKE_PLATFORM_MODE": "wait"})
            self.assertEqual(os.environ["GITHUB_JOB"], "complete-gate")
            self.assertEqual(os.environ[GATE.audit_processes.STATE_ENV], "/synthetic/ordinary-state")

    def test_direct_entrypoint_without_bytecode_flags_keeps_source_clean(self):
        with tempfile.TemporaryDirectory(prefix="p2pkit-platform-entrypoint-") as temporary:
            root = Path(temporary)
            scripts = root / "scripts"
            scripts.mkdir()
            originals = {}
            for name in ("run-platform-tests.py", "audit_processes.py", "hosted_full_simulator.py",
                         "ci_evidence.py", "hosted_evidence.py", "hosted_evidence_primitives.py"):
                raw = (ROOT / "scripts" / name).read_bytes()
                (scripts / name).write_bytes(raw)
                originals["scripts/" + name] = raw
            expected_paths = {"scripts", *originals}
            self.assertEqual(expected_paths, {path.relative_to(root).as_posix() for path in root.rglob("*")})
            environment = standalone_fixture_environment("pass")
            environment.update({name: str(root) for name in ("HOME", "TMPDIR", "TMP", "TEMP")})
            self.assertFalse({"PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX", "PYTHONPATH"} & environment.keys())
            # A fresh interpreter does not inherit this test module's runtime flag.
            result = subprocess.run([sys.executable, str(scripts / "run-platform-tests.py"), "--help"],
                                    cwd=root, env=environment, capture_output=True, timeout=10, check=False)
            self.assertEqual(0, result.returncode, "Direct entrypoint help failed")
            self.assertLessEqual(len(result.stdout), 64 * 1024)
            self.assertIn(b"usage: run-platform-tests.py", result.stdout)
            self.assertFalse(result.stderr, "Direct entrypoint help wrote stderr")
            self.assertEqual(expected_paths, {path.relative_to(root).as_posix() for path in root.rglob("*")},
                             "Direct entrypoint created source-tree files or directories")
            for name, raw in originals.items():
                self.assertTrue((root / name).read_bytes() == raw, "Direct entrypoint changed " + name)


class DriverLifecycleTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="p2pkit-platform-driver-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        (self.root / "gradle").mkdir()
        shutil.copy2(ROOT / "gradle/platform-test-policy.json", self.root / "gradle/platform-test-policy.json")
        (self.root / "gradlew").write_text("#!" + sys.executable + "\n" + FAKE_GRADLE)
        (self.root / "gradlew").chmod(0o755)
        (self.root / "fixture.json").write_text(json.dumps(example_report()))
        (self.root / "tracked.txt").write_text("unchanged\n")
        (self.root / ".gitignore").write_text("build/\ntrace.jsonl\nworker.pid\n")
        for args in (("init", "-q"), ("add", "."),
                     ("-c", "user.name=Test Fixture", "-c", "user.email=fixture@example.invalid",
                      "-c", "commit.gpgsign=false", "commit", "-qm", "Synthetic input")):
            subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(GATE, "ROOT", self.root).start()
        mock.patch.object(GATE, "POLICY", self.root / "gradle/platform-test-policy.json").start()
        mock.patch.object(GATE.platform, "system", return_value="Darwin").start()
        mock.patch.object(GATE.platform, "machine", return_value="arm64").start()

    def invoke(self, mode):
        with mock.patch.dict(os.environ, standalone_fixture_environment(mode), clear=True), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return GATE.run("full")

    def summaries(self):
        return [json.loads(path.read_text()) for path in self.root.glob("build/reports/platform-tests/*/summary.json")]

    def calls(self):
        return [json.loads(line) for line in (self.root / "trace.jsonl").read_text().splitlines()]

    def test_success_uses_strict_fresh_bounded_command_and_stops(self):
        self.assertEqual(0, self.invoke("pass"))
        calls = self.calls()
        self.assertEqual(2, len(calls))
        self.assertEqual(["--stop"], calls[-1])
        self.assertEqual(["check", "--no-daemon", "--no-build-cache", "--no-configuration-cache", "--rerun-tasks",
                          "--dependency-verification", "strict", "--max-workers=2", "--no-parallel", "--console=plain"],
                         calls[0][:10])
        self.assertIn("--init-script", calls[0])
        summary = self.summaries()[0]
        self.assertEqual("PASS", summary["result"])
        self.assertEqual([], summary["errors"])
        self.assertEqual(summary["commit"], summary["sourceAfter"]["commit"])
        self.assertEqual(summary["diffSha256"], summary["sourceAfter"]["diffSha256"])

    def test_shared_driver_keeps_check_only_delegates_native_and_stops(self):
        (self.root / "fixture.json").write_text(json.dumps(example_report("macos-shared")))
        subprocess.run(["git", "add", "fixture.json"], cwd=self.root, check=True, capture_output=True)
        subprocess.run(["git", "-c", "user.name=Test Fixture", "-c", "user.email=fixture@example.invalid",
                        "-c", "commit.gpgsign=false", "commit", "-qm", "Shared fixture"],
                       cwd=self.root, check=True, capture_output=True)
        with mock.patch.dict(os.environ, standalone_fixture_environment("pass"), clear=True), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(0, GATE.run("macos-shared"))
        calls = self.calls()
        self.assertEqual(2, len(calls))
        self.assertEqual(["--stop"], calls[-1])
        self.assertEqual(GATE.PROFILES["macos-shared"] + GATE.FLAGS,
                         calls[0][:len(GATE.PROFILES["macos-shared"]) + len(GATE.FLAGS)])
        self.assertEqual("PASS", self.summaries()[0]["result"])
        self.assertEqual("macos-shared", self.summaries()[0]["profile"])

    def test_failure_modes_cannot_pass_and_always_stop(self):
        for mode in ("no-report", "stale-token", "malformed", "exit-failure", "build-failure", "stop-failure"):
            with self.subTest(mode=mode):
                self.assertNotEqual(0, self.invoke(mode))
                self.assertEqual(["--stop"], self.calls()[-1])
        self.assertEqual(6, len(self.summaries()))
        self.assertTrue(all(report["result"] == "FAIL" and report["errors"] for report in self.summaries()))

    def test_previous_success_report_cannot_mask_missing_current_execution(self):
        self.assertEqual(0, self.invoke("pass"))
        self.assertNotEqual(0, self.invoke("no-report"))
        summaries = self.summaries()
        self.assertEqual({"PASS", "FAIL"}, {report["result"] for report in summaries})
        self.assertEqual(2, len({report["token"] for report in summaries}))

    def test_source_mutation_fails_despite_successful_tests(self):
        self.assertNotEqual(0, self.invoke("source-change"))
        self.assertIn("Source state changed", " ".join(self.summaries()[0]["errors"]))
        self.assertEqual(["--stop"], self.calls()[-1])

    def test_untracked_input_is_rejected_before_starting_gradle(self):
        (self.root / "untracked.kt").write_text("// not evidence-bound\n")
        with self.assertRaisesRegex(ValueError, "untracked"):
            self.invoke("pass")
        self.assertFalse((self.root / "trace.jsonl").exists())

    def test_missing_wrapper_still_records_failure_and_cleanup_attempt(self):
        (self.root / "gradlew").unlink()
        self.assertNotEqual(0, self.invoke("pass"))
        summary = self.summaries()[0]
        self.assertEqual("FAIL", summary["result"])
        self.assertNotEqual(0, summary["stopExitCode"])

    def test_undrained_owned_group_fails_gate_but_still_attempts_gradle_stop(self):
        retire = GATE.terminate_process
        def uncertain(owner):
            retire(owner)  # Do not leak the fixture's real retained native handles.
            return False
        with mock.patch.object(GATE, "terminate_process", side_effect=uncertain):
            self.assertNotEqual(0, self.invoke("pass"))
        self.assertEqual("FAIL", self.summaries()[0]["result"])
        self.assertEqual(["--stop"], self.calls()[-1])

    def test_failed_inner_retirement_is_retained_in_summary_without_changing_task_or_stop_results(self):
        retire, owners = GATE.terminate_process, []
        def uncertain(owner):
            result = retire(owner)  # Retire real fixture resources before supplying an observation failure.
            owners.append(owner)
            if len(owners) == 1:
                owner.retirement_error = GATE.audit_processes.OwnershipError(
                    "Unclassified Darwin lifetimes remain; cleanup is not proven")
                owner.retirement_phase, owner.drained = "DRAIN", False
                return False
            return result
        with mock.patch.object(GATE, "terminate_process", side_effect=uncertain):
            self.assertNotEqual(0, self.invoke("pass"))
        summary = self.summaries()[0]
        self.assertEqual((0, 0, "FAIL"), (summary["gradleExitCode"], summary["stopExitCode"], summary["result"]))
        self.assertEqual(owners[0].retirement_diagnostic(), summary["gradleRetirementFailure"])
        self.assertEqual("DRAIN_UNCLASSIFIED", summary["gradleRetirementFailure"]["reason"])
        self.assertEqual(["--stop"], self.calls()[-1])

    def test_stop_timeout_is_failure_and_terminates_its_owned_process(self):
        process = mock.Mock()
        process.wait.side_effect = subprocess.TimeoutExpired("gradlew --stop", 90)
        with model_process_launch(mock.Mock(return_value=process)), \
                mock.patch.object(GATE, "terminate_process", return_value=True) as retire, \
                mock.patch.object(GATE.os, "killpg", side_effect=AssertionError("NO_NUMERIC_SIGNAL")), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(124, GATE.stop_gradle())
        process.wait.assert_called_once_with(timeout=90)
        retire.assert_called_once()
        self.assertIs(retire.call_args.args[0].child, process)

    def test_cancellation_signals_owned_gradle_group_stops_and_reports_failure(self):
        # A separate Python driver plus a real fake-wrapper/worker process tests
        # signal propagation. No Gradle, Kotlin, simulator or device is launched.
        bootstrap = (
            "import importlib.util, pathlib, sys; sys.dont_write_bytecode=True; "
            f"s=importlib.util.spec_from_file_location('gate', {str(ROOT / 'scripts/run-platform-tests.py')!r}); "
            "g=importlib.util.module_from_spec(s); s.loader.exec_module(g); "
            f"g.ROOT=pathlib.Path({str(self.root)!r}); g.POLICY=g.ROOT/'gradle/platform-test-policy.json'; "
            "g.platform.system=lambda:'Darwin'; g.platform.machine=lambda:'arm64'; sys.exit(g.run('full'))"
        )
        with owned_process_fixture(standalone_fixture_environment("wait")) as fixture, tempfile.TemporaryFile() as log:
            launch, rescue = fixture
            process = launch([sys.executable, "-I", "-B", "-c", bootstrap], cwd=self.root,
                             stdout=log, stderr=subprocess.STDOUT)
            deadline = time.monotonic() + 10
            while not (self.root / "worker.pid").exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue((self.root / "worker.pid").exists(), "Fake build never reached worker start")
            worker_pid = int((self.root / "worker.pid").read_text())
            worker = next((identity for identity in rescue.discover() if identity["pid"] == worker_pid), None)
            self.assertIsNotNone(worker, "Rescue must bind the actual worker before cancellation")
            leader = next((identity for identity in process.scope.discover() if identity["pid"] == process.pid), None)
            self.assertIsNotNone(leader)
            key = process.scope._key(leader)
            # Deliver cancellation only through the originally retained native
            # capability. Cleanup never uses the ready file's numeric PID.
            process.scope._send(leader, process.scope.handles[key], signal.SIGTERM,
                                deadline=time.monotonic() + 10)
            process.wait(timeout=20)
            log.seek(0)
            output = log.read(64 * 1024 + 1)
            self.assertLessEqual(len(output), 64 * 1024)
            self.assertEqual(130, process.returncode, output.decode(errors="replace"))
            self.assertEqual(["--stop"], self.calls()[-1])
            self.assertEqual("FAIL", self.summaries()[0]["result"])
            current = rescue._identity(worker_pid)
            self.assertTrue(current is None or rescue._key(current) != rescue._key(worker),
                            "Fake Gradle did not reap its original worker")


def retire_fixture_owners(owners, rescue):
    """Attempt every original owner, then an independent retained rescue scope."""
    first = None
    for owner in owners:
        try:
            if not GATE.terminate_process(owner):
                raise AssertionError("Fixture owner did not prove retirement")
        except BaseException as error:
            if first is None:
                first = error
    try:
        # Shorter test-local grace, never a longer production deadline. The
        # rescue owns the fixture's inherited prefix, not a numeric PID/PGID.
        end = time.monotonic() + 5.2
        live = rescue.drain(0.2, 5, deadline=end)
        if live or rescue.discovery_errors or getattr(rescue, "pending_discoveries", None):
            raise AssertionError("Fixture rescue did not prove retirement")
    except BaseException as error:
        if first is None:
            first = error
    finally:
        try:
            rescue.close()
        except BaseException as error:
            if first is None:
                first = error
    if first is not None:
        raise first


@contextlib.contextmanager
def owned_process_fixture(environment=None):
    """Finite self-created POSIX children; no foreign-group signal authority.

    An independent native rescue scope is retained before any child starts, so
    even a failed tested retirement cannot force the fixture to signal a PID.
    """
    native = GATE.audit_processes
    token = GATE.uuid.uuid4().hex
    environment = native.local_ownership_environment(dict(os.environ) if environment is None else environment, token)
    rescue = native.make_local_scope(environment.get(native.JOB_ENV, token), token,
                                    environment.get(native.STATE_ENV, str(ROOT)),
                                    environment.get("GRADLE_USER_HOME", str(Path.home() / ".gradle")))
    owners = []
    def launch(argv, *, cwd=ROOT, stdout=None, stderr=None):
        owner = GATE.ProcessOwner()
        owners.append(owner)  # Retain the owner before a partial/failed spawn.
        owner.start(argv, cwd=cwd, stdout=stdout, stderr=stderr)
        return owner
    with mock.patch.dict(os.environ, environment, clear=True):
        try:
            yield launch, rescue
        finally:
            with mock.patch.object(GATE, "TERMINATION_GRACE_SECONDS", 0.2):
                retire_fixture_owners(owners, rescue)


class ProcessOwnerModels(unittest.TestCase):
    """No real child/census/signal; native currency and lifetime transitions modeled."""
    def setUp(self):
        self.native = GATE.audit_processes
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        # Synthetic owners use supplied backends unless a case explicitly tests
        # hosted admission; do not inherit the CI runner's real Darwin context.
        self.stack.enter_context(mock.patch.dict(os.environ, standalone_fixture_environment("model"), clear=True))
        for name in ("kill", "killpg", "getpgid", "pidfd_open"):
            self.stack.enter_context(mock.patch.object(os, name, create=True,
                side_effect=AssertionError("NO_NUMERIC_PROCESS_OPERATION")))
        self.pidfd_send = self.stack.enter_context(mock.patch.object(signal, "pidfd_send_signal", create=True,
            side_effect=AssertionError("NO_NATIVE_SIGNAL")))
        self.stack.enter_context(mock.patch.object(subprocess, "Popen", side_effect=AssertionError("NO_REAL_PROCESS")))
        self.stack.enter_context(contextlib.redirect_stderr(io.StringIO()))

    def owner(self, child=None):
        if child is None:
            child = mock.Mock(stdout=None, stderr=None, returncode=0)
            child.poll.return_value = 0
        scope = mock.Mock(leaders=[child], discovery_errors=set(), pending_discoveries={})
        scope.drain.return_value = []
        owner = GATE.ProcessOwner()
        owner.scope, owner.child, owner.attempted = scope, child, True
        return owner, scope, child

    def linux_scope(self):
        # Native constructors are deliberately NOT called. All census/handle
        # observations are supplied, including the conditional kernel ID reuse.
        scope = self.native.LocalLinuxScope.__new__(self.native.LocalLinuxScope)
        scope.job, scope.invocation, scope.state, scope.home = "b" * 32, TOKEN, "/state", "/home"
        scope.leaders, scope.launches, scope.discovery_reconciliations = [], [], []
        scope.known, scope.handles, scope.pending_discoveries = {}, {}, {}
        scope.baseline, scope.discovery_errors = set(), set()
        scope._closed, scope._retirement_error = False, None
        scope._pids = mock.Mock(return_value=[])
        scope._environment = mock.Mock(return_value={})
        scope._acquire = mock.Mock(side_effect=AssertionError("NO_FOREIGN_HANDLE_ACQUISITION"))
        scope._release = mock.Mock()
        return scope

    def test_original_reaped_popen_model_cannot_adopt_a_recycled_group(self):
        for cached_status in (None, 0):
            stale = mock.Mock(pid=74001, returncode=cached_status)
            stale.poll.return_value = cached_status
            with self.subTest(cached_status=cached_status):
                self.assertFalse(GATE.terminate_process(stale))
                stale.poll.assert_not_called()
        self.assertTrue(GATE.terminate_process(None))

    def test_reaped_owner_excludes_same_pid_and_group_with_different_lifetime(self):
        scope = self.linux_scope()
        original = {"pid": 74001, "startTicks": 11, "uid": os.getuid(), "group": 74001, "live": False}
        replacement = {**original, "startTicks": 12, "live": True}
        handle = object()
        scope.known[(74001, 11)], scope.handles[(74001, 11)] = original, handle
        scope._pids.return_value = [74001]
        scope._identity = mock.Mock(return_value=replacement)
        owner, _, child = self.owner()
        child.pid = 74001
        owner.scope, scope.leaders = scope, [child]
        with mock.patch.object(time, "monotonic", return_value=100), mock.patch.object(time, "sleep") as sleep:
            self.assertTrue(GATE.terminate_process(owner))
        self.assertEqual(2, sleep.call_count, "Three quiet native observations remain mandatory")
        scope._acquire.assert_not_called()
        scope._release.assert_called_once_with(handle)
        self.pidfd_send.assert_not_called()
        child.close.assert_called_once_with()
        self.assertTrue(GATE.terminate_process(owner))
        scope._release.assert_called_once_with(handle)

    def test_replacement_between_census_and_signal_uses_only_retained_pidfd(self):
        scope = self.linux_scope()
        original = {"pid": 74001, "startTicks": 11, "live": True}
        handle = object()
        scope.known[(74001, 11)], scope.handles[(74001, 11)] = original, handle
        scope.discover = mock.Mock(return_value=[original])
        # Original lifetime ended after the census; the old descriptor's ESRCH
        # cannot authorize an open/signal of the unrelated replacement PID.
        self.pidfd_send.side_effect = ProcessLookupError(errno.ESRCH, "original lifetime ended")
        scope.signal_all(signal.SIGTERM)
        self.pidfd_send.assert_called_once_with(handle, signal.SIGTERM)
        scope._acquire.assert_not_called()

    def test_unknown_live_or_unobserved_exit_remains_failed_without_retry(self):
        for outcome in ("live", "denied", "pending", "leader"):
            owner, scope, child = self.owner()
            if outcome == "live":
                scope.drain.return_value = [{"pid": 74001}]
            elif outcome == "denied":
                scope.discovery_errors.add("denied lifetime")
            elif outcome == "pending":
                scope.pending_discoveries[74001] = {"outcome": "unresolved"}
            else:
                child.poll.return_value = None
            with self.subTest(outcome=outcome):
                self.assertFalse(GATE.terminate_process(owner))
                scope.drain.return_value = []
                scope.discovery_errors.clear()
                scope.pending_discoveries.clear()
                child.poll.return_value = 0
                self.assertFalse(GATE.terminate_process(owner), "UNKNOWN must not become a later green retry")
                scope.drain.assert_called_once()
                scope.close.assert_called_once_with()

    def test_denied_signal_census_and_timeout_failures_still_close_all_resources(self):
        class FalseyError(self.native.OwnershipError):
            def __bool__(self):
                return False
        failures = (PermissionError(errno.EPERM, "signal denied"), OSError(errno.EIO, "census failed"),
                    self.native.DrainDeadlineExceeded("original deadline"), FalseyError("original unknown"),
                    KeyboardInterrupt())
        for failure in failures:
            child = mock.Mock(stdout=mock.Mock(closed=False), stderr=mock.Mock(closed=False), returncode=0)
            child.poll.return_value = 0
            owner, scope, _ = self.owner(child)
            scope.drain.side_effect = failure
            scope.close.side_effect = OSError("later native close")
            child.stdout.close.side_effect = OSError("later reader close")
            with self.subTest(error=type(failure).__name__):
                if isinstance(failure, Exception):
                    self.assertFalse(GATE.terminate_process(owner))
                else:
                    with self.assertRaises(KeyboardInterrupt) as caught:
                        GATE.terminate_process(owner)
                    self.assertIs(caught.exception, failure)
                self.assertIs(owner.retirement_error, failure)
                scope.close.assert_called_once_with()
                child.stdout.close.assert_called_once_with()
                child.stderr.close.assert_called_once_with()
                self.assertFalse(GATE.terminate_process(owner))
                child.stderr.close.assert_called_once_with()

    def test_success_requires_original_15_plus_5_end_including_finalization(self):
        self.assertEqual((15, 5), (GATE.TERMINATION_GRACE_SECONDS, GATE.TERMINATION_KILL_SECONDS))
        for observed in (120 - 0.001, 120, 121):
            owner, scope, child = self.owner()
            with self.subTest(observed=observed), mock.patch.object(time, "monotonic", side_effect=[100, observed]):
                self.assertIs(GATE.terminate_process(owner), observed < 120)
            scope.drain.assert_called_once_with(15, 5, deadline=120)
            scope.close.assert_called_once_with()
            child.poll.assert_called_once_with()

    def darwin_owner(self, census_seconds):
        owner, _, child = self.owner()
        scope = self.native.DarwinScope.__new__(self.native.DarwinScope)
        scope.leaders, scope.discovery_errors, scope.pending_discoveries = [child], set(), {}
        scope.active_drain, scope.drain_reconciliations = None, []
        scope.known, scope.handles = {}, {}
        clock = [100.]
        def discover():
            clock[0] += census_seconds
            return []
        scope.discover = mock.Mock(side_effect=discover)
        scope.close = mock.Mock()
        scope.signal_all = mock.Mock(side_effect=AssertionError("NO_SIGNAL_FOR_QUIET_CENSUS"))
        owner.scope = scope
        timer = mock.Mock(monotonic=lambda: clock[0], sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds))
        return owner, scope, timer

    def test_measured_slow_censuses_require_three_fresh_in_one_original_phase(self):
        # 7s is a supplied model near the observed two-census mean, not a claim
        # about unretained individual native timings or a future-host bound.
        for old_policy in (True, False):
            owner, scope, timer = self.darwin_owner(7.)
            with self.subTest(old_policy=old_policy), contextlib.ExitStack() as stack:
                stack.enter_context(mock.patch.object(self.native, "time", timer))
                stack.enter_context(mock.patch.object(GATE, "time", timer))
                if old_policy:
                    stack.enter_context(mock.patch.object(GATE, "DARWIN_TERMINATION_GRACE_SECONDS", 15, create=True))
                    stack.enter_context(mock.patch.object(GATE, "DARWIN_TERMINATION_KILL_SECONDS", 5, create=True))
                self.assertIs(GATE.terminate_process(owner), not old_policy)
            record = scope.drain_reconciliations[0]
            self.assertEqual((15, 5) if old_policy else (45, 45),
                             (record["graceSeconds"], record["killWaitSeconds"]))
            self.assertEqual(120 if old_policy else 190, record["absoluteDeadlineMonotonic"])
            rows = owner.drain_state["darwinDrain"]["phases"]
            self.assertEqual([2, 0] if old_policy else [3], [row["quietEnd"] for row in rows])
            self.assertEqual(3, scope.discover.call_count)
            scope.signal_all.assert_not_called(); scope.close.assert_called_once_with()
            if old_policy:
                self.assertEqual("DRAIN_NOT_QUIET", owner.retirement_diagnostic()["reason"])
            else:
                self.assertEqual("retired", record["outcome"])

    def test_darwin_two_plus_two_and_late_third_do_not_establish_retirement(self):
        owner, scope, timer = self.darwin_owner(15.)
        with mock.patch.object(self.native, "time", timer), mock.patch.object(GATE, "time", timer):
            self.assertFalse(GATE.terminate_process(owner))
        rows = owner.drain_state["darwinDrain"]["phases"]
        self.assertEqual([2, 2], [row["quietEnd"] for row in rows])
        self.assertEqual([2, 2], [row["inTime"] for row in rows])
        self.assertEqual([1, 1], [row["late"] for row in rows])
        self.assertEqual(6, scope.discover.call_count)
        self.assertEqual("DRAIN_NOT_QUIET", owner.retirement_diagnostic()["reason"])
        scope.signal_all.assert_not_called(); scope.close.assert_called_once_with()

    def test_actual_backend_selects_original_reserve_including_every_final_close(self):
        classes = (self.native.DarwinScope, self.native.LocalDarwinScope,
                   GATE.ci_evidence._HostedLocalDarwinScope, self.native.LocalLinuxScope, self.native.WindowsScope)
        for cls in classes:
            darwin = issubclass(cls, self.native.DarwinScope)
            grace, kill = (45, 45) if darwin else (15, 5)
            end = 100 + grace + kill
            for observed in (end - .001, end, end + 1):
                owner, _, child = self.owner()
                scope = cls.__new__(cls)  # No native constructor or fabricated host admission.
                scope.leaders, scope.discovery_errors, scope.pending_discoveries = [child], set(), {}
                scope.drain, scope.close = mock.Mock(return_value=[]), mock.Mock()
                owner.scope = scope
                with self.subTest(backend=cls.__name__, observed=observed), \
                        mock.patch.object(time, "monotonic", side_effect=[100, observed]):
                    self.assertIs(GATE.terminate_process(owner), observed < end)
                scope.drain.assert_called_once_with(grace, kill, deadline=end)
                scope.close.assert_called_once_with(); child.poll.assert_called_once_with()

    def test_darwin_reserve_cannot_convert_unknown_cancellation_or_close_failure_to_success(self):
        for failed in ("live", "denied", "pending", "leader", "cancel", "scope", "stdout", "stderr"):
            child = mock.Mock(stdout=mock.Mock(closed=False), stderr=mock.Mock(closed=False), returncode=0)
            child.poll.return_value = 0
            owner, _, _ = self.owner(child)
            scope = self.native.DarwinScope.__new__(self.native.DarwinScope)
            scope.leaders, scope.discovery_errors, scope.pending_discoveries = [child], set(), {}
            scope.drain, scope.close = mock.Mock(return_value=[]), mock.Mock()
            owner.scope = scope
            if failed == "live":
                scope.drain.return_value = [{"pid": 74001}]
            elif failed == "denied":
                scope.discovery_errors.add("unresolved")
            elif failed == "pending":
                scope.pending_discoveries[74001] = {}
            elif failed == "leader":
                child.poll.return_value = None
            elif failed == "cancel":
                scope.drain.side_effect = KeyboardInterrupt()
            else:
                (scope if failed == "scope" else getattr(child, failed)).close.side_effect = OSError("close failed")
            with self.subTest(failed=failed), mock.patch.object(time, "monotonic", return_value=100):
                if failed == "cancel":
                    with self.assertRaises(KeyboardInterrupt):
                        GATE.terminate_process(owner)
                else:
                    self.assertFalse(GATE.terminate_process(owner))
                self.assertFalse(GATE.terminate_process(owner), "Never renew an unsuccessful retirement")
            scope.drain.assert_called_once_with(45, 45, deadline=190)
            for resource in (scope, child.stdout, child.stderr):
                resource.close.assert_called_once_with()

    def test_close_failure_alone_cannot_pass_or_skip_the_other_reader(self):
        for failed in ("scope", "stdout", "stderr"):
            child = mock.Mock(stdout=mock.Mock(closed=False), stderr=mock.Mock(closed=False), returncode=0)
            child.poll.return_value = 0
            owner, scope, _ = self.owner(child)
            resource = scope if failed == "scope" else getattr(child, failed)
            failure = OSError("uncertain close")
            resource.close.side_effect = failure
            with self.subTest(resource=failed):
                self.assertFalse(GATE.terminate_process(owner))
                self.assertIs(owner.retirement_error, failure)
                for resource in (scope, child.stdout, child.stderr):
                    resource.close.assert_called_once_with()

    def test_clock_failure_keeps_first_error_and_still_attempts_all_closes(self):
        for early in (True, False):
            child = mock.Mock(stdout=mock.Mock(closed=False), stderr=mock.Mock(closed=False), returncode=0)
            child.poll.return_value = 0
            owner, scope, _ = self.owner(child)
            failure = OSError("original retirement failure")
            clock_error = OSError("retirement clock unavailable")
            scope.drain.side_effect = failure
            with self.subTest(early=early), mock.patch.object(time, "monotonic",
                    side_effect=clock_error if early else [100, clock_error]):
                self.assertFalse(GATE.terminate_process(owner))
            self.assertIs(owner.retirement_error, clock_error if early else failure)
            if early:
                scope.drain.assert_not_called()  # Never fall back to an unbounded drain.
            else:
                scope.drain.assert_called_once_with(15, 5, deadline=120)
            for resource in (scope, child.stdout, child.stderr):
                resource.close.assert_called_once_with()

    def test_later_cancellation_propagates_without_losing_first_error_or_other_closes(self):
        child = mock.Mock(stdout=mock.Mock(closed=False), stderr=mock.Mock(closed=False), returncode=0)
        child.poll.return_value = 0
        owner, scope, _ = self.owner(child)
        failure, cancelled = OSError("first native failure"), KeyboardInterrupt()
        scope.drain.side_effect = failure
        child.stdout.close.side_effect = cancelled
        with self.assertRaises(KeyboardInterrupt) as caught:
            GATE.terminate_process(owner)
        self.assertIs(caught.exception, cancelled)
        self.assertIs(owner.retirement_error, failure)
        self.assertIs(cancelled.__cause__, failure)
        for resource in (scope, child.stdout, child.stderr):
            resource.close.assert_called_once_with()
        self.assertFalse(GATE.terminate_process(owner))

    def test_partial_spawn_retains_scope_leader_and_readers_before_return(self):
        child = mock.Mock(stdout=mock.Mock(closed=False), stderr=mock.Mock(closed=False), returncode=0)
        child.poll.return_value = 0
        _, scope, _ = self.owner(child)
        scope.leaders = []
        failure = self.native.OwnershipError("discovery after successful spawn failed")
        def partial(*_args, **_kwargs):
            scope.leaders.append(child)
            raise failure
        scope.spawn.side_effect = partial
        owner = GATE.ProcessOwner()
        with mock.patch.object(self.native, "make_local_scope", return_value=scope), self.assertRaises(type(failure)):
            owner.start(["not-executed"], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertIs(owner.scope, scope)
        self.assertIsNone(owner.child)
        self.assertIs(owner.launch_error, failure)
        self.assertTrue(GATE.terminate_process(owner))
        scope.close.assert_called_once_with()
        child.stdout.close.assert_called_once_with()
        child.stderr.close.assert_called_once_with()
        with self.assertRaises(self.native.OwnershipError):
            owner.start(["not-executed"], cwd=ROOT)

    def test_closed_preexec_readers_are_not_closed_again_and_unknown_carrier_persists(self):
        for attached in (False, True):
            child = mock.Mock(stdout=mock.Mock(closed=True), stderr=mock.Mock(closed=True), returncode=0)
            child.poll.return_value = 0
            owner, scope, _ = self.owner(child)
            failure = self.native.OwnershipError("failed pre-exec admission")
            failure._p2pkit_retirement = {"status": "UNKNOWN", "resources": [
                {"phase": "posix-darwin-spawn", "resource": "stream:0", "status": "UNKNOWN", "error": "close"}],
                "omitted": 0}
            owner.launch_error = failure
            if not attached:
                owner.scope = owner.child = None
            with self.subTest(scope_returned=attached):
                self.assertFalse(GATE.terminate_process(owner))
                child.stdout.close.assert_not_called()
                child.stderr.close.assert_not_called()
                if attached:
                    self.assertIs(owner.retirement_error, failure)
                    scope.close.assert_called_once_with()

    def test_start_defers_handled_cancellation_until_native_child_is_retained(self):
        _, scope, child = self.owner()
        observed = []
        owner = GATE.ProcessOwner()
        def cancelled(_sig, _frame):
            observed.append((owner.scope, owner.child))
            raise KeyboardInterrupt()
        def launch(*_args, **_kwargs):
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
            self.assertEqual([], observed)
            return child
        scope.spawn.side_effect = launch
        previous = signal.signal(signal.SIGTERM, cancelled)
        try:
            with mock.patch.object(self.native, "make_local_scope", return_value=scope), self.assertRaises(KeyboardInterrupt):
                owner.start(["not-executed"], cwd=ROOT)
            self.assertEqual([(scope, child)], observed)
            self.assertIs(signal.getsignal(signal.SIGTERM), cancelled)
            self.assertTrue(GATE.terminate_process(owner))
        finally:
            signal.signal(signal.SIGTERM, previous)

    def test_launch_preserves_exact_canonical_context_and_borrows_output_sinks(self):
        base = self.native.ownership_environment({"PATH": "/synthetic/bin", "UNRELATED": "unchanged"},
                                                "b" * 32, "c" * 32, "/canonical/state", "/canonical/home")
        for capture in ("inherited", "pipes", "merged-file"):
            owner, scope, child = self.owner()
            owner.attempted, owner.scope, owner.child = False, None, None
            scope.spawn.return_value = child
            sink = io.BytesIO()
            outputs = {} if capture == "inherited" else {"stdout": subprocess.PIPE, "stderr": subprocess.PIPE} \
                if capture == "pipes" else {"stdout": sink, "stderr": subprocess.STDOUT}
            with self.subTest(capture=capture), mock.patch.dict(os.environ, base, clear=True), \
                    mock.patch.object(GATE.uuid, "uuid4", return_value=mock.Mock(hex=TOKEN)), \
                    mock.patch.object(self.native, "make_local_scope", return_value=scope) as factory:
                owner.start(["not-executed"], cwd=ROOT, **outputs)
                factory.assert_called_once_with("b" * 32, TOKEN, "/canonical/state", "/canonical/home")
                command, cwd, environment = scope.spawn.call_args.args
                self.assertEqual((["not-executed"], str(ROOT)), (command, cwd))
                self.assertEqual({**base, self.native.LOCAL_CHAIN_ENV: TOKEN}, environment)
                self.assertEqual(base, dict(os.environ), "Do not alter the parent's canonical context")
                self.assertEqual({"stdout": 1, "stderr": 2} if capture == "inherited" else {} if capture == "pipes"
                                 else {"stdout": sink, "stderr": sink}, scope.spawn.call_args.kwargs)
                self.assertTrue(GATE.terminate_process(owner))
                self.assertFalse(sink.closed, "Borrowed output sinks do not become owned readers")
            sink.close()

    def test_local_marker_is_independent_bounded_and_nested_without_environment_rewrites(self):
        base = {self.native.JOB_ENV: "b" * 32, self.native.CHAIN_ENV: "c" * 32,
                self.native.DOMAINS_ENV: "byte-identical", self.native.STATE_ENV: "/state", "GRADLE_USER_HOME": "/home"}
        first = self.native.local_ownership_environment(base, TOKEN)
        nested = self.native.local_ownership_environment(first, "d" * 32)
        self.assertEqual({**base, self.native.LOCAL_CHAIN_ENV: TOKEN + ":" + "d" * 32}, nested)
        scope = self.linux_scope()
        self.assertTrue(scope._ours({self.native.LOCAL_CHAIN_ENV.encode(): nested[self.native.LOCAL_CHAIN_ENV].encode()}))
        self.assertFalse(scope._ours({self.native.CHAIN_ENV.encode(): TOKEN.encode()}))
        full = ":".join("%032x" % number for number in range(32))
        self.assertEqual(32, len(self.native.local_ownership_chain(full)))
        invalid = (None, 1, TOKEN + ":", ":" + TOKEN, TOKEN + ":" + TOKEN, "A" * 32,
                   TOKEN + ":" + full, TOKEN + ":not-hex")
        for chain in invalid:
            with self.subTest(chain=chain), self.assertRaises(self.native.OwnershipError):
                self.native.local_ownership_environment({self.native.LOCAL_CHAIN_ENV: chain}, "d" * 32)
        for token in (TOKEN, "c" * 32, "z" * 32, "a" * 31, True):
            with self.subTest(token=token), self.assertRaises(self.native.OwnershipError):
                self.native.local_ownership_environment(first, token)
        with self.assertRaises(self.native.OwnershipError):
            self.native.local_ownership_environment({self.native.LOCAL_CHAIN_ENV: full}, TOKEN)
        for chain in (TOKEN.encode() + b":bad", TOKEN.encode() + b":\xff"):
            with self.assertRaises(self.native.OwnershipError):
                scope._ours({self.native.LOCAL_CHAIN_ENV.encode(): chain})
        parsed = self.native.parse_environment(self.native.LOCAL_CHAIN_ENV.encode() + b"=" + TOKEN.encode() + b"\0")
        self.assertTrue(scope._ours(parsed))
        with self.assertRaises(self.native.OwnershipError):
            self.native.parse_environment((self.native.LOCAL_CHAIN_ENV.encode() + b"=" + TOKEN.encode() + b"\0") * 2)

    def test_darwin_local_nesting_retains_only_verified_inherited_pipe_capabilities(self):
        scope = self.native.LocalDarwinScope.__new__(self.native.LocalDarwinScope)
        scope.invocation = TOKEN
        marker = (17, 18, 19)
        rows = [{"id": token, "fd": fd, "digest": scope._pipe_digest(marker)}
                for token, fd in (("c" * 32, 10), ("d" * 32, 11))]
        env = {self.native.CHAIN_ENV: "c" * 32, self.native.LOCAL_CHAIN_ENV: "d" * 32 + ":" + TOKEN,
               self.native.PIPE_ENV: json.dumps(rows)}
        scope._pipe_identity = mock.Mock(return_value=marker)
        self.assertEqual(rows, scope._inherited_pipes(env))
        scope._pipe_identity.return_value = (20, 21, 22)  # Recycled descriptor, not the held original pipe.
        self.assertEqual([], scope._inherited_pipes(env))
        with self.assertRaises(self.native.OwnershipError):
            scope._inherited_pipes({**env, self.native.LOCAL_CHAIN_ENV: TOKEN})
        with self.assertRaises(self.native.OwnershipError):
            scope._inherited_pipes({**env, self.native.PIPE_ENV: json.dumps(rows * 17)})
        self.assertIs(self.native.LocalDarwinScope._send, self.native.DarwinScope._send)
        self.assertIs(self.native.LocalDarwinScope._acquire, self.native.DarwinScope._acquire)

    def test_factory_keeps_native_backends_and_existing_windows_job_contract(self):
        for platform_name, kind in (("linux", "LocalLinuxScope"), ("darwin", "LocalDarwinScope"), ("win32", "WindowsScope")):
            with self.subTest(platform=platform_name), mock.patch.object(sys, "platform", platform_name), \
                    mock.patch.object(self.native, kind) as factory:
                self.assertIs(factory.return_value, self.native.make_local_scope("job", TOKEN, "/state", "/home"))
                factory.assert_called_once_with("job", TOKEN, "/state", "/home")
        with mock.patch.object(sys, "platform", "unsupported"), self.assertRaises(self.native.OwnershipError):
            self.native.make_local_scope("job", TOKEN, "/state", "/home")

    def test_actual_owner_selects_hosted_local_scope_without_rebinding_canonical_context(self):
        base = self.native.ownership_environment({"GITHUB_ACTIONS": "true", "RUNNER_ENVIRONMENT": "github-hosted",
            "GITHUB_REPOSITORY": "p2pKit/P2pKit", "GITHUB_SHA": "a" * 40, "GITHUB_WORKFLOW_SHA": "a" * 40,
            "GITHUB_WORKFLOW_REF": "p2pKit/P2pKit/.github/workflows/ci.yml@refs/pull/504/merge"},
            "b" * 32, "c" * 32, "/canonical/state", "/canonical/home")
        owner, scope, child = self.owner()
        owner.attempted, owner.scope, owner.child = False, None, None
        scope.spawn.return_value = child
        with mock.patch.dict(os.environ, base, clear=True), \
                mock.patch.object(GATE.uuid, "uuid4", return_value=mock.Mock(hex=TOKEN)), \
                mock.patch.object(GATE.ci_evidence.platform, "system", return_value="Darwin"), \
                mock.patch.object(GATE.ci_evidence, "_HostedLocalDarwinScope", return_value=scope) as factory, \
                mock.patch.object(self.native, "make_local_scope", side_effect=AssertionError("STRICT_SCOPE_SELECTED")):
            owner.start(["not-executed"], cwd=ROOT)
            factory.assert_called_once_with("b" * 32, TOKEN, "/canonical/state", "/canonical/home")
            self.assertEqual({**base, self.native.LOCAL_CHAIN_ENV: TOKEN}, scope.spawn.call_args.args[2])
            self.assertEqual(base, dict(os.environ))
            self.assertTrue(GATE.terminate_process(owner))
            self.assertIsNone(owner.retirement_diagnostic())

    def test_retirement_diagnostic_preserves_first_phase_and_never_serializes_private_error(self):
        owner, scope, child = self.owner()
        failure = self.native.OwnershipError("Unclassified Darwin lifetimes remain; cleanup is not proven")
        scope.drain.side_effect = failure
        scope.close.side_effect = OSError("PRIVATE_LATER_CLOSE")
        with contextlib.redirect_stderr(io.StringIO()) as output:
            self.assertFalse(GATE.terminate_process(owner))
        diagnostic = owner.retirement_diagnostic()
        self.assertEqual("DRAIN", diagnostic["phase"])
        self.assertEqual("DRAIN_UNCLASSIFIED", diagnostic["reason"])
        self.assertEqual("OWNERSHIP_ERROR", diagnostic["nativeError"]["exceptionType"])
        self.assertIn("PLATFORM_RETIREMENT_FAILURE", output.getvalue())
        self.assertNotIn("PRIVATE_LATER_CLOSE", output.getvalue())
        self.assertNotIn(str(failure), output.getvalue())
        scope.close.side_effect = None
        self.assertFalse(GATE.terminate_process(owner))
        self.assertEqual(diagnostic, owner.retirement_diagnostic())
        scope.drain.assert_called_once()
        scope.close.assert_called_once()

    def test_retirement_diagnostic_labels_clock_close_and_pending_launch_without_native_queries(self):
        for failed, phase in (("clock", "CLOCK"), ("scope", "SCOPE_CLOSE"), ("pipe", "PIPE_CLOSE"),
                              ("launch", "LAUNCH")):
            child = mock.Mock(stdout=mock.Mock(closed=False), stderr=None, returncode=0)
            child.poll.return_value = 0
            owner, scope, _ = self.owner(child)
            failure = OSError(errno.EPERM, "PRIVATE_TOKEN=https://private.invalid/signed?secret=yes")
            if failed == "scope":
                scope.close.side_effect = failure
            elif failed == "pipe":
                child.stdout.close.side_effect = failure
            elif failed == "launch":
                failure._p2pkit_retirement = {"resources": [], "omitted": 1}
                owner.scope = owner.child = None
                owner.launch_error = failure
            with self.subTest(failed=failed), mock.patch.object(time, "monotonic",
                    side_effect=failure if failed == "clock" else [100, 100]), \
                    contextlib.redirect_stderr(io.StringIO()) as output:
                self.assertFalse(GATE.terminate_process(owner))
                diagnostic = owner.retirement_diagnostic()
                self.assertEqual(phase, diagnostic["phase"])
                self.assertEqual("OS", diagnostic["nativeError"]["kind"])
                self.assertEqual(errno.EPERM, diagnostic["nativeError"]["errno"])
                self.assertNotIn("PRIVATE_TOKEN", output.getvalue())
                self.assertNotIn("private.invalid", output.getvalue())
                self.assertIs(owner.retirement_error, failure)

    def test_first_launch_failure_is_finite_even_if_diagnostic_sink_fails(self):
        owner, scope, child = self.owner()
        owner.attempted, owner.scope, owner.child = False, None, None
        failure = OSError(errno.EIO, "PRIVATE_LAUNCH_BODY", "/PRIVATE/PATH")
        scope.spawn.side_effect = failure
        scope.launches = [{"created": True, "gateReleased": False, "pid": 123, "private": "PRIVATE_RECORD"}]
        with mock.patch.object(GATE.ci_evidence, "local_command_scope", return_value=scope), \
                mock.patch("builtins.print", side_effect=OSError("sink failed")), \
                self.assertRaises(OSError) as caught:
            owner.start(["PRIVATE_ARG"], cwd=ROOT)
        self.assertIs(failure, caught.exception)
        diagnostic = owner.launch_diagnostic()
        self.assertEqual("LAUNCH_ERROR", diagnostic["reason"])
        self.assertEqual(errno.EIO, diagnostic["nativeError"]["errno"])
        self.assertEqual((True, False, 1, True, False), tuple(diagnostic[k] for k in
            ("scopeReturned", "childReturned", "recordedLaunches", "created", "gateReleased")))
        self.assertNotIn("PRIVATE", json.dumps(diagnostic))
        self.assertTrue(GATE.terminate_process(owner))
        scope.spawn.assert_called_once(); scope.drain.assert_called_once()

    def test_postdrain_snapshot_precedes_close_and_contains_only_counts(self):
        for returns in (True, False):
            owner, scope, child = self.owner()
            live = [{"pid": 999, "name": "PRIVATE_PROCESS"}]
            scope.drain.return_value = live
            scope.discovery_errors.add("PRIVATE_DISCOVERY")
            scope.pending_discoveries[999] = {"identity": "PRIVATE_IDENTITY"}
            if not returns:
                scope.drain.side_effect = self.native.OwnershipError("PRIVATE_DRAIN_ERROR")
            def close():
                live.clear(); scope.discovery_errors.clear(); scope.pending_discoveries.clear(); scope.leaders.clear()
            scope.close.side_effect = close
            with self.subTest(returned=returns):
                self.assertFalse(GATE.terminate_process(owner))
                diagnostic = owner.retirement_diagnostic()
                self.assertEqual({"returned": returns, "live": 1 if returns else None, "leaders": 1,
                                  "discoveryErrors": 1, "pendingDiscoveries": 1}, diagnostic["drainState"])
                self.assertNotIn("PRIVATE", json.dumps(diagnostic))
                scope.discover.assert_not_called(); scope.description.assert_not_called()
                self.assertFalse(GATE.terminate_process(owner))
                scope.drain.assert_called_once(); scope.close.assert_called_once()

    def test_actual_darwin_drain_metrics_are_projected_before_close_without_new_observations(self):
        # Over the entire new 90s reserve: still zero timely observations.
        for census_seconds in (0., 91.):
            owner, _, child = self.owner()
            scope = self.native.DarwinScope.__new__(self.native.DarwinScope)
            scope.leaders, scope.discovery_errors, scope.pending_discoveries = [child], set(), {}
            scope.active_drain, scope.drain_reconciliations = None, []
            scope.known, scope.handles = {}, {}
            clock = [100.]
            def discover():
                clock[0] += census_seconds
                return []
            scope.discover = mock.Mock(side_effect=discover)
            scope.close = mock.Mock(side_effect=lambda: scope.drain_diagnostics.clear())
            scope.description = mock.Mock(side_effect=AssertionError("NO_RAW_OWNER_DESCRIPTION"))
            scope.signal_all = mock.Mock(side_effect=AssertionError("NO_NEW_SIGNALS"))
            owner.scope = scope
            timer = mock.Mock(monotonic=lambda: clock[0], sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds))
            with mock.patch.object(self.native, "time", timer), mock.patch.object(GATE, "time", timer):
                self.assertEqual(census_seconds == 0., GATE.terminate_process(owner))
            projected = owner.drain_state["darwinDrain"]
            row = projected["phases"][0]
            self.assertEqual("OBSERVATION_ONLY_NOT_RETIREMENT", projected["scope"])
            self.assertEqual(3 if census_seconds == 0. else 0, row["inTime"])
            self.assertEqual(3 if census_seconds == 0. else 1, scope.discover.call_count)
            self.assertEqual([], scope.drain_diagnostics)  # Snapshot survives independent close.
            scope.close.assert_called_once(); scope.description.assert_not_called(); scope.signal_all.assert_not_called()
            if census_seconds:
                diagnostic = owner.retirement_diagnostic()
                self.assertEqual("DRAIN_NOT_QUIET", diagnostic["reason"])
                self.assertFalse(diagnostic["drainState"]["returned"])
                self.assertEqual(projected, diagnostic["drainState"]["darwinDrain"])

    def test_owner_diagnostics_bound_counts_and_real_source_frame_projection(self):
        class UntrustedLength:
            def __len__(self):
                raise AssertionError("DO_NOT_CALL_FOREIGN_COUNTER")
        for value in (None, UntrustedLength(), [None] * (self.native.MAX_PROCESSES + 1)):
            self.assertIsNone(GATE._recorded_owner_count(value))
        self.assertEqual(2, GATE._recorded_owner_count({"PRIVATE": 1, "SECOND_PRIVATE": 2}))
        try:
            self.native.resolve_executable([], str(ROOT), {})  # Real pure source guard, no native child.
        except self.native.OwnershipError as error:
            diagnostic = GATE._owner_error_diagnostic(error)
        else:
            self.fail("Empty command unexpectedly admitted")
        self.assertEqual("OWNERSHIP", diagnostic["sourceFrames"][-1]["source"])
        self.assertTrue(0 < diagnostic["sourceFrames"][-1]["line"] <= 1_000_000)
        self.assertLessEqual(len(diagnostic["sourceFrames"]), 3)
        self.assertNotIn(str(ROOT), json.dumps(diagnostic))

    def test_fixture_attempts_remaining_retirements_after_cleanup_failure(self):
        for failed in ("owner", "rescue", "close"):
            first = PermissionError(errno.EPERM, "first fixture retirement failure")
            owners, scope = [object(), object()], mock.Mock(discovery_errors=set(), pending_discoveries={})
            scope.drain.return_value = []
            if failed == "rescue":
                scope.drain.side_effect = first
            if failed == "close":
                scope.close.side_effect = first
            with self.subTest(failed=failed), mock.patch.object(GATE, "terminate_process",
                    side_effect=[first, True] if failed == "owner" else [True, True]) as retire:
                with self.assertRaises(PermissionError) as caught:
                    retire_fixture_owners(owners, scope)
                self.assertIs(caught.exception, first)
                self.assertEqual([mock.call(owner) for owner in owners], retire.call_args_list)
                scope.drain.assert_called_once()
                scope.close.assert_called_once_with()


class OwnedProcessGroupTest(unittest.TestCase):
    """Live own-process controls; no actual foreign PID churn or native-platform equivalence claim."""
    def resistant_worker_control(self, leader_exits_first):
        with tempfile.TemporaryDirectory(prefix="p2pkit-owned-lifetime-") as temporary, owned_process_fixture() as fixture:
            launch, rescue = fixture
            ready = Path(temporary) / "worker.pid"
            worker_code = (
                "import os,pathlib,signal,sys,time; signal.signal(signal.SIGTERM,signal.SIG_IGN); "
                "pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(90)"
            )
            leader_code = (
                "import pathlib,subprocess,sys,time; "
                f"subprocess.Popen([sys.executable,'-c',{worker_code!r},sys.argv[1]]); "
                "ready=pathlib.Path(sys.argv[1]); "
                "\nwhile not ready.exists(): time.sleep(0.01)\n"
                + ("sys.exit(0)" if leader_exits_first else "time.sleep(90)")
            )
            leader = launch([sys.executable, "-I", "-B", "-c", leader_code, str(ready)])
            unrelated = launch([sys.executable, "-I", "-B", "-c", "import time; time.sleep(90)"])
            deadline = time.monotonic() + 10
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(ready.exists(), "TERM-resistant worker never reached ready state")
            worker_pid = int(ready.read_text())
            if leader_exits_first:
                self.assertEqual(0, leader.wait(timeout=10))
            live = rescue.discover()
            worker = next((identity for identity in live if identity["pid"] == worker_pid), None)
            self.assertIsNotNone(worker, "Independent rescue did not bind the actual owned worker lifetime")
            worker_key = rescue._key(worker)
            self.assertIn(worker_key, rescue.handles)
            self.assertIn(worker_key, {leader.scope._key(identity) for identity in leader.scope.discover()})
            # Keep the exact main-owner native signal path but record its input
            # currency. No extra native signal is issued by this observer.
            with mock.patch.object(leader.scope, "_send", wraps=leader.scope._send) as send, \
                    mock.patch.object(GATE, "TERMINATION_GRACE_SECONDS", 0.2):
                drained = GATE.terminate_process(leader)
            self.assertTrue(drained)
            worker_signals = [call.args[2] for call in send.call_args_list
                              if leader.scope._key(call.args[0]) == worker_key]
            self.assertIn(signal.SIGTERM, worker_signals)
            self.assertIn(signal.SIGKILL, worker_signals, "TERM-resistant descendants still require KILL")
            current = rescue._identity(worker_pid)
            self.assertTrue(current is None or rescue._key(current) != worker_key or not current["live"],
                            "Original owned worker lifetime remains live")
            # A replaced numeric identity is not absence. The original retained
            # capability and scoped census, not kill(pid, 0), establish this check.
            self.assertNotIn(worker_key, {rescue._key(identity) for identity in rescue.discover()})
            self.assertIsNotNone(leader.poll())
            self.assertIsNone(unrelated.poll(), "Cleanup touched the separately owned unrelated control")

    def test_term_resistant_worker_is_killed_after_leader_exits_on_term(self):
        self.resistant_worker_control(leader_exits_first=False)

    def test_surviving_group_is_drained_even_when_leader_already_exited(self):
        self.resistant_worker_control(leader_exits_first=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
