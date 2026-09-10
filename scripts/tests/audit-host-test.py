#!/usr/bin/env python3
"""Audit-host admission/evidence controls, not native product or device acceptance.

Git admission uses an isolated synthetic repository. Platform identity and external
process boundaries are controlled fixtures; actual maintained report assessors are
invoked without replacing their policy, test model, or case-count validation.
"""

import contextlib
import copy
import ctypes
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("audit_host_under_test", ROOT / "scripts/run-audit-host.py")
HOST = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HOST)
POLICY = json.loads((ROOT / "gradle/platform-test-policy.json").read_text(encoding="utf-8"))
TOKEN = "abcdef0123456789abcdef0123456789"
WINDOWS_TASKS = {":p2p-core:jvmTest", ":p2p-transport-lan:jvmTest",
                 ":p2p-network-provisioning-desktop:test"}
WINDOWS_FOLLOWUP_TASKS = {":p2p-core:jvmTest", ":p2p-core:testAndroidHostTest", ":p2p-transport-lan:jvmTest"}
WINDOWS_DIAGNOSTICS_TASKS = {":p2p-transport-lan:jvmTest"}
SWIFT_TARGETS = ("p2pkit-sample-tests", "p2pkit-sample-uitests")


def temporary(test):
    parent = Path(tempfile.gettempdir()).resolve()
    if parent == ROOT or ROOT in parent.parents:
        test.fail("synthetic audit state must be outside the source checkout")
    directory = tempfile.TemporaryDirectory(prefix="p2pkit-audit-host-", dir=parent)
    test.addCleanup(directory.cleanup)
    return Path(directory.name)


def windows_report(required_tasks=WINDOWS_TASKS):
    tasks = {task for entry in POLICY["model"].values() for task in entry["tests"]}
    return {
        "schema": 1, "token": TOKEN, "buildFailed": False, "dryRun": False,
        "host": {"os": "Windows Server 2025", "arch": "amd64"},
        "model": copy.deepcopy(POLICY["model"]),
        "tests": {task: {"outcome": "EXECUTED" if task in required_tasks else "NOT_REQUESTED",
                         "enabled": task in required_tasks, "inGraph": task in required_tasks,
                         "passed": 3 if task in required_tasks else 0, "failed": 0, "skipped": 0}
                  for task in tasks},
    }


def swift_case(identifier="SyntheticTests/testCase()", status="Success"):
    return {"_type": {"_name": "ActionTestMetadata"}, "identifier": {"_value": identifier},
            "testStatus": {"_value": status}}


def swift_target(name, cases=None):
    return {"_type": {"_name": "ActionTestableSummary"}, "targetName": {"_value": name},
            "tests": {"_values": [{"_type": {"_name": "ActionTestSummaryGroup"},
                                   "subtests": {"_values": [swift_case()] if cases is None else cases}}]}}


def swift_objects():
    return [{"_type": {"_name": "ActionTestPlanRunSummaries"},
             "summaries": {"_values": [{"testableSummaries": {"_values": [
                 swift_target(name) for name in SWIFT_TARGETS]}}]}}]


@contextlib.contextmanager
def windows_tool_boundary(test, host, *, layout="cmd", missing=None, bash_result=None,
                          git_version="git version 2.55.0.windows.5\n"):
    """Real file lookup; modeled Windows version/RAM processes, never native acceptance."""
    work = temporary(test)
    installation = work / "Program Files Ω" / "Git"
    for directory in ("cmd", "bin", "usr/bin"):
        (installation / directory).mkdir(parents=True, exist_ok=True)
    git_exe = installation / layout / "git.exe"
    git_exe.parent.mkdir(parents=True, exist_ok=True)
    bash_exe = installation / "bin/bash.exe"
    wsl = work / "Windows" / "System32"
    wsl.mkdir(parents=True)
    for path in (git_exe, bash_exe, wsl / "bash.exe", wsl / "bash"):
        path.write_text("synthetic executable; subprocess boundary must intercept\n", encoding="utf-8")
        path.chmod(0o700)
    if missing == "git":
        git_exe.unlink()
    elif missing == "bash":
        bash_exe.unlink()
    elif missing == "utilities":
        (installation / "usr/bin").rmdir()
    path_value = os.pathsep.join((str(wsl), str(git_exe.parent)))
    host.environment.update(PATH=path_value, JAVA_HOME=str(work / "jdk17"),
                            P2PKIT_AUDIT_JDK21=str(work / "jdk21"))
    original_environment = dict(host.environment)
    calls = []

    def version(command, **kwargs):
        calls.append({"command": list(command), "options": kwargs})
        test.assertEqual(HOST.ROOT, kwargs["cwd"])
        test.assertTrue(kwargs["capture_output"])
        test.assertTrue(kwargs["text"])
        test.assertEqual(60, kwargs["timeout"])
        if command == ["bash", "--version"]:
            return subprocess.CompletedProcess(command, 1,
                stdout="Windows Subsystem for Linux has no installed distributions.\n", stderr="")
        if command == [str(bash_exe), "--version"]:
            result = bash_result or (0, "GNU bash, version 5.2.37(1)-release (x86_64-pc-msys)\n", "")
            if isinstance(result, Exception):
                raise result
            return subprocess.CompletedProcess(command, result[0], stdout=result[1], stderr=result[2])
        if command in (["git", "--version"], [str(git_exe), "--version"]):
            return subprocess.CompletedProcess(command, 0, stdout=git_version, stderr="")
        if command == [sys.executable, "--version"]:
            return subprocess.CompletedProcess(command, 0, stdout="Python 3.12.10\n", stderr="")
        for major in (17, 21):
            if command == [str(work / ("jdk" + str(major)) / "bin/java.exe"), "-version"]:
                return subprocess.CompletedProcess(command, 0, stdout="", stderr=f'openjdk version "{major}.0.1"\n')
        test.fail("unexpected prerequisite subprocess: " + repr(command))

    def memory(pointer):
        pointer._obj.totalPhysical = 16 * 1024 ** 3
        return 1

    native_os = types.SimpleNamespace(**vars(os))
    native_os.name = "nt"  # Do not change pathlib's real host OS or launch native Windows processes.
    memory_api = mock.Mock(side_effect=memory)
    disk = types.SimpleNamespace(free=10 * 1024 ** 3,
                                 _asdict=lambda: {"total": 20 * 1024 ** 3, "used": 10 * 1024 ** 3,
                                                  "free": 10 * 1024 ** 3})
    with mock.patch.object(HOST, "os", native_os), \
            mock.patch.dict(os.environ, host.environment, clear=True), \
            mock.patch.object(HOST.platform, "platform", return_value="Windows-2025-fixture"), \
            mock.patch.object(HOST.platform, "machine", return_value="AMD64"), \
            mock.patch.object(ctypes, "WinDLL", create=True,
                              return_value=types.SimpleNamespace(GlobalMemoryStatusEx=memory_api)), \
            mock.patch.object(HOST.shutil, "disk_usage", return_value=disk), \
            mock.patch.object(HOST.subprocess, "run", side_effect=version):
        yield {"git": git_exe, "bash": bash_exe, "installation": installation, "wsl": wsl,
               "calls": calls, "environment": original_environment, "memory": memory_api}


class AdmissionTest(unittest.TestCase):
    def setUp(self):
        self.work = temporary(self)
        self.repo = self.work / "checkout with spaces Ω"
        self.repo.mkdir()
        scripts = self.repo / "scripts"
        scripts.mkdir()
        shutil.copy2(ROOT / "scripts/run-platform-tests.py", scripts / "run-platform-tests.py")
        self.workflow = self.repo / HOST.WORKFLOW
        self.workflow.parent.mkdir(parents=True)
        self.workflow.write_text("# synthetic previous workflow revision\n", encoding="utf-8")
        (self.repo / "tracked.txt").write_text("unchanged source\n", encoding="utf-8")
        self.environment = dict(os.environ)
        for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY",
                     "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT"):
            self.environment.pop(name, None)
        self.environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                                GIT_AUTHOR_NAME="Synthetic Host Fixture", GIT_COMMITTER_NAME="Synthetic Host Fixture",
                                GIT_AUTHOR_EMAIL="host-fixture@example.invalid",
                                GIT_COMMITTER_EMAIL="host-fixture@example.invalid")
        hooks = self.work / "empty hooks"
        hooks.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Synthetic Host Fixture")
        self.git("config", "user.email", "host-fixture@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", str(hooks))
        self.git("checkout", "-b", "audit/complete-2026-09-04")
        self.commit("Synthetic existing branch base")
        self.before = self.git("rev-parse", "HEAD")
        self.workflow.write_text("# synthetic explicit audit trigger revision\n", encoding="utf-8")
        self.commit("Synthetic explicit audit trigger")
        self.after = self.git("rev-parse", "HEAD")
        self.tree = self.git("rev-parse", "HEAD^{tree}")
        self.event = {"ref": HOST.REF, "repository": {"full_name": "p2pKit/P2pKit"},
                      "deleted": False, "forced": False, "created": False,
                      "before": self.before, "after": self.after}
        self.environment.update(GITHUB_EVENT_NAME="push", GITHUB_REPOSITORY="p2pKit/P2pKit",
                                GITHUB_REF=HOST.REF, GITHUB_SHA=self.after,
                                GITHUB_RUN_ID="101", GITHUB_RUN_ATTEMPT="2")
        self.native_calls = []

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.repo, env=self.environment,
                                       text=True, stderr=subprocess.PIPE).strip()

    def commit(self, message):
        self.git("add", ".")
        self.git("commit", "-qm", message)

    def admit(self, role="windows-x64", event=None, environment=None, native=None, translated=(0, "0\n")):
        system, machine = native or {"windows-x64": ("Windows", "AMD64"),
                                     "macos-arm64": ("Darwin", "arm64"),
                                     "macos-x64": ("Darwin", "x86_64")}.get(role, ("Windows", "AMD64"))
        original_run = subprocess.run

        def boundary(command, *args, **kwargs):
            if command[0] == "sysctl":
                self.assertEqual(["sysctl", "-in", "sysctl.proc_translated"], command)
                self.native_calls.append(list(command))
                return subprocess.CompletedProcess(command, translated[0], stdout=translated[1], stderr="")
            self.assertEqual("git", command[0], "admission must not start a product or runner process")
            return original_run(command, *args, **kwargs)

        with mock.patch.dict(os.environ, self.environment, clear=True), \
                mock.patch.object(HOST.platform, "system", return_value=system), \
                mock.patch.object(HOST.platform, "machine", return_value=machine), \
                mock.patch.object(HOST.subprocess, "run", side_effect=boundary):
            return HOST.admit(self.event if event is None else event,
                              self.environment if environment is None else environment, role, root=self.repo)

    def test_explicit_existing_branch_trigger_binds_exact_commit_tree_and_native_role(self):
        for role in ("windows-x64", "macos-arm64", "macos-x64"):
            with self.subTest(role=role):
                self.native_calls.clear()
                admission = self.admit(role)
                self.assertEqual(self.after, admission["commit"])
                self.assertEqual(self.tree, admission["tree"])
                self.assertEqual(self.before, admission["before"])
                self.assertEqual(HOST.REF, admission["ref"])
                self.assertEqual(role, admission["role"])
                self.assertEqual("full", admission["requestedScope"])
                self.assertEqual([HOST.WORKFLOW], admission["changedPaths"])
                self.assertEqual("101", admission["runId"])
                self.assertEqual("2", admission["runAttempt"])
                self.assertEqual(0 if role == "windows-x64" else 1, len(self.native_calls))

    def test_event_environment_and_exact_repository_ref_must_all_agree(self):
        for key, value in (("GITHUB_EVENT_NAME", "workflow_dispatch"), ("GITHUB_EVENT_NAME", "pull_request"),
                           ("GITHUB_REPOSITORY", "another/P2pKit"), ("GITHUB_REF", "refs/heads/main"),
                           ("GITHUB_REF", "refs/tags/v0.7.0-rc3"), ("GITHUB_SHA", "f" * 40)):
            with self.subTest(environment=key, value=value):
                environment = dict(self.environment, **{key: value})
                with self.assertRaises(ValueError):
                    self.admit(environment=environment)
        for key, value in (("ref", "refs/heads/main"), ("repository", {"full_name": "another/P2pKit"}),
                           ("after", "f" * 40), ("after", "A" * 40), ("after", None)):
            with self.subTest(event=key, value=value):
                event = copy.deepcopy(self.event)
                event[key] = value
                with self.assertRaises(ValueError):
                    self.admit(event=event)

    def test_missing_base_force_creation_and_deletion_never_use_a_fallback_base(self):
        for field in ("forced", "created", "deleted"):
            for value in (True, None, "false", 0):
                with self.subTest(field=field, value=value):
                    event = copy.deepcopy(self.event)
                    if value is None:
                        del event[field]
                    else:
                        event[field] = value
                    with self.assertRaises(ValueError):
                        self.admit(event=event)
        for value in (None, "0" * 40, "A" * 40, "1" * 39, "HEAD~1"):
            with self.subTest(before=value):
                event = dict(self.event, before=value)
                with self.assertRaises(ValueError):
                    self.admit(event=event)
        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
            self.admit(event=dict(self.event, before="f" * 40))

    def test_nonancestor_existing_commit_is_rejected_without_resetting_checkout(self):
        self.git("checkout", "--detach", self.before)
        (self.repo / "tracked.txt").write_text("synthetic divergent source\n", encoding="utf-8")
        self.commit("Synthetic unrelated descendant")
        divergent = self.git("rev-parse", "HEAD")
        self.git("checkout", "--detach", self.after)
        with self.assertRaises((ValueError, subprocess.CalledProcessError)):
            self.admit(event=dict(self.event, before=divergent))
        self.assertEqual(self.after, self.git("rev-parse", "HEAD"))
        self.assertEqual("", self.git("status", "--porcelain=v1", "--untracked-files=all"))

    def test_source_only_push_and_noop_push_do_not_satisfy_explicit_workflow_path(self):
        for modify in (False, True):
            with self.subTest(modify=modify):
                before = self.git("rev-parse", "HEAD")
                if modify:
                    (self.repo / "tracked.txt").write_text("synthetic source-only revision\n", encoding="utf-8")
                    self.commit("Synthetic source-only update")
                after = self.git("rev-parse", "HEAD")
                with self.assertRaisesRegex(ValueError, "workflow trigger path"):
                    self.admit(event=dict(self.event, before=before, after=after),
                               environment=dict(self.environment, GITHUB_SHA=after))

    def test_dirty_staged_and_untracked_source_reject_without_deleting_input(self):
        tracked = self.repo / "tracked.txt"
        tracked.write_text("preserve contributor source\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not clean"):
            self.admit()
        self.git("add", "tracked.txt")
        with self.assertRaisesRegex(ValueError, "not clean"):
            self.admit()
        self.assertEqual("preserve contributor source\n", tracked.read_text(encoding="utf-8"))
        self.git("restore", "--staged", "--worktree", "tracked.txt")  # Only this disposable fixture's tracked file.
        untracked = self.repo / "untracked Ω.txt"
        untracked.write_text("preserve untracked source", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "not clean"):
            self.admit()
        self.assertEqual("preserve untracked source", untracked.read_text(encoding="utf-8"))

    def test_native_role_cannot_be_substituted_with_another_os_or_architecture(self):
        for role, native in (("windows-x64", ("Linux", "x86_64")),
                             ("windows-x64", ("Windows", "arm64")),
                             ("macos-arm64", ("Darwin", "x86_64")),
                             ("macos-x64", ("Darwin", "aarch64")),
                             ("macos-x64", ("Darwin", "unknown")),
                             ("macos-arm64", ("Linux", "arm64")),
                             ("invented", ("Windows", "AMD64"))):
            with self.subTest(role=role, native=native), self.assertRaises(ValueError):
                self.admit(role, native=native)

    def test_rosetta_or_unknown_translation_status_cannot_be_native_mac_evidence(self):
        for role in ("macos-arm64", "macos-x64"):
            for translated in ((0, "1\n"), (2, ""), (1, "unexpected"), (0, "unknown")):
                with self.subTest(role=role, translated=translated), self.assertRaisesRegex(ValueError, "native"):
                    self.admit(role, translated=translated)
            with self.subTest(role=role, translated="absent native sysctl"):
                self.assertEqual(role, self.admit(role, translated=(1, ""))["role"])


class WindowsAssessmentTest(unittest.TestCase):
    def assess(self, report, policy=POLICY):
        return HOST.assess_windows(report, policy, TOKEN)

    def test_only_all_three_fresh_library_event_records_establish_windows_execution(self):
        report = windows_report()
        actual = self.assess(report)
        self.assertEqual(WINDOWS_TASKS, set(actual))
        self.assertEqual(sorted(WINDOWS_TASKS), list(actual))
        self.assertTrue(all(result["passed"] == 3 for result in actual.values()))
        self.assertTrue(all(report["tests"][task]["outcome"] == "NOT_REQUESTED"
                            for task in report["tests"] if task not in WINDOWS_TASKS))

    def test_each_required_task_rejects_nonexecution_disabled_zero_or_failed_counts(self):
        for task in WINDOWS_TASKS:
            mutations = [("outcome", outcome) for outcome in
                         ("SKIPPED", "UP-TO-DATE", "FROM-CACHE", "NO_SOURCE", "NOT_COMPLETED", "NOT_REQUESTED", "FAILED")]
            mutations += [("enabled", False), ("inGraph", False), ("passed", 0), ("failed", 1)]
            for field, value in mutations:
                with self.subTest(task=task, field=field, value=value):
                    report = windows_report()
                    report["tests"][task][field] = value
                    with self.assertRaises(ValueError):
                        self.assess(report)

    def test_focused_tasks_keep_complete_model_and_cannot_pass_as_full_windows(self):
        for required in (WINDOWS_FOLLOWUP_TASKS, WINDOWS_DIAGNOSTICS_TASKS):
            report = windows_report(required)
            self.assertEqual(required, set(HOST.assess_windows(report, POLICY, TOKEN, required)))
            with self.assertRaises(ValueError):
                self.assess(report)
            if required == WINDOWS_DIAGNOSTICS_TASKS:
                with self.assertRaises(ValueError):
                    HOST.assess_windows(report, POLICY, TOKEN, WINDOWS_FOLLOWUP_TASKS)
            for task in required:
                for field, value in (("outcome", "FROM-CACHE"), ("passed", 0), ("failed", 1), ("inGraph", False)):
                    mutated = copy.deepcopy(report)
                    mutated["tests"][task][field] = value
                    with self.subTest(required=required, task=task, field=field), self.assertRaises(ValueError):
                        HOST.assess_windows(mutated, POLICY, TOKEN, required)
            for change in ("failed-unrequested", "missing-inventory", "stale-token"):
                mutated = copy.deepcopy(report)
                if change == "failed-unrequested":
                    mutated["tests"][":p2p-network-provisioning-desktop:test"]["failed"] = 1
                elif change == "missing-inventory":
                    del mutated["tests"][":p2p-transport-lan:jvmTest"]
                else:
                    mutated["token"] = "stale"
                with self.subTest(required=required, change=change), self.assertRaises(ValueError):
                    HOST.assess_windows(mutated, POLICY, TOKEN, required)
        for required in (set(), {":p2p-core:jvmTest"}, {":unclassified:test"}):
            with self.subTest(required=required), self.assertRaises(ValueError):
                HOST.assess_windows(report, POLICY, TOKEN, required)

    def test_stale_dry_failed_wrong_host_and_malformed_reports_cannot_pass(self):
        for field, value in (("schema", True), ("schema", 2), ("token", "previous-token"),
                             ("dryRun", True), ("dryRun", 0), ("buildFailed", True), ("buildFailed", 0),
                             ("host", None), ("host", []), ("host", {"os": "Linux", "arch": "amd64"}),
                             ("host", {"os": "Windows", "arch": "arm64"}),
                             ("host", {"os": "Windows", "arch": 1}),
                             ("tests", []), ("tests", {}), ("model", None)):
            with self.subTest(field=field, value=value):
                report = windows_report()
                report[field] = value
                with self.assertRaises(ValueError):
                    self.assess(report)
        for report in (None, [], "invalid", 1):
            with self.subTest(report=report), self.assertRaises(ValueError):
                self.assess(report)

    def test_every_configured_task_and_target_must_match_committed_model(self):
        for project, entry in POLICY["model"].items():
            for target in entry["targets"]:
                with self.subTest(project=project, missing_target=target):
                    report = windows_report()
                    del report["model"][project]["targets"][target]
                    with self.assertRaises(ValueError):
                        self.assess(report)
            for task in entry["tests"]:
                with self.subTest(missing_record=task):
                    report = windows_report()
                    del report["tests"][task]
                    with self.assertRaises(ValueError):
                        self.assess(report)
                with self.subTest(missing_model_task=task):
                    report = windows_report()
                    report["model"][project]["tests"].remove(task)
                    del report["tests"][task]
                    with self.assertRaises(ValueError):
                        self.assess(report)
        report = windows_report()
        report["tests"][":unclassified:test"] = copy.deepcopy(report["tests"][":p2p-core:jvmTest"])
        with self.assertRaises(ValueError):
            self.assess(report)

    def test_boolean_pseudocounts_and_unrequested_failures_are_rejected(self):
        for task in (":p2p-core:jvmTest", ":p2p-core:iosX64Test"):
            for field, value in (("enabled", 1), ("inGraph", "true"), ("outcome", "INVENTED"),
                                 ("passed", True), ("passed", -1), ("passed", "1"), ("passed", 1.5),
                                 ("failed", False), ("failed", 1), ("skipped", None), ("skipped", -1)):
                with self.subTest(task=task, field=field, value=value):
                    report = windows_report()
                    report["tests"][task][field] = value
                    with self.assertRaises(ValueError):
                        self.assess(report)
        report = windows_report()
        report["tests"][":p2p-core:jvmTest"] = None
        with self.assertRaises(ValueError):
            self.assess(report)

    def test_skipped_case_counts_remain_visible_without_becoming_device_acceptance(self):
        report = windows_report()
        report["tests"][":p2p-core:jvmTest"]["skipped"] = 2
        self.assertEqual(2, self.assess(report)[":p2p-core:jvmTest"]["skipped"])
        for invalid in (None, {}, {"schema": True}, {"schema": 1, "model": {}},
                        {"schema": 1, "model": {":p2p-core": {"targets": {}, "tests": [False]}}}):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.assess(report, invalid)


class SwiftAssessmentTest(unittest.TestCase):
    def test_nested_actual_metadata_requires_both_maintained_swift_targets(self):
        result = HOST.assess_swift(swift_objects())
        self.assertEqual(set(SWIFT_TARGETS), set(result))
        for target in SWIFT_TARGETS:
            self.assertEqual([{"identifier": "SyntheticTests/testCase()", "status": "Success"}], result[target])

    def test_distinct_cases_can_span_summary_objects_without_dropping_either_target(self):
        objects = [swift_target(name, [swift_case("First/testOne()")]) for name in SWIFT_TARGETS]
        objects += [swift_target(name, [swift_case("Second/testTwo()")]) for name in SWIFT_TARGETS]
        result = HOST.assess_swift(objects)
        for target in SWIFT_TARGETS:
            self.assertEqual(["First/testOne()", "Second/testTwo()"],
                             [case["identifier"] for case in result[target]])

    def test_build_success_missing_target_or_empty_metadata_is_not_xctest_acceptance(self):
        for objects in ([], [{"_value": "BUILD SUCCEEDED"}], [swift_case()],
                        [swift_target(SWIFT_TARGETS[0])], [swift_target(SWIFT_TARGETS[1])],
                        [swift_target(name, []) for name in SWIFT_TARGETS],
                        [swift_target("unmaintained-tests"), swift_target(SWIFT_TARGETS[1])]):
            with self.subTest(objects=objects), self.assertRaises(ValueError):
                HOST.assess_swift(objects)

    def test_failed_skipped_unknown_and_missing_case_status_cannot_pass(self):
        for target in SWIFT_TARGETS:
            for status in ("Failure", "Skipped", "Expected Failure", "Unknown", "", None, True, 1):
                with self.subTest(target=target, status=status):
                    objects = [swift_target(name, [swift_case(status=status if name == target else "Success")])
                               for name in SWIFT_TARGETS]
                    with self.assertRaises(ValueError):
                        HOST.assess_swift(objects)

    def test_duplicate_cases_within_target_or_across_bundles_are_not_double_counted(self):
        for target in SWIFT_TARGETS:
            with self.subTest(target=target, duplication="same summary"):
                objects = [swift_target(name, [swift_case(), swift_case()] if name == target else [swift_case()])
                           for name in SWIFT_TARGETS]
                with self.assertRaisesRegex(ValueError, "Duplicated"):
                    HOST.assess_swift(objects)
            with self.subTest(target=target, duplication="another bundle"):
                objects = swift_objects() + [swift_target(target)]
                with self.assertRaisesRegex(ValueError, "Duplicated"):
                    HOST.assess_swift(objects)

    def test_malformed_swift_shapes_are_controlled_rejections_not_unhandled_attribute_errors(self):
        for objects in (None, True, 1, "not xcresult objects", {}, [None], [[False]]):
            with self.subTest(objects=objects), self.assertRaises(ValueError):
                HOST.assess_swift(objects)
        for field, value in (("_type", None), ("_type", []), ("targetName", None),
                             ("targetName", SWIFT_TARGETS[0]), ("tests", None)):
            with self.subTest(field=field, value=value):
                target = swift_target(SWIFT_TARGETS[0])
                target[field] = value
                with self.assertRaises(ValueError):
                    HOST.assess_swift([target, swift_target(SWIFT_TARGETS[1])])
        for field, value in (("_type", None), ("_type", []), ("identifier", None),
                             ("identifier", "unboxed identifier"), ("identifier", {"_value": ""}),
                             ("identifier", {"_value": 1}), ("testStatus", None), ("testStatus", [])):
            with self.subTest(field=field, value=value):
                case = swift_case()
                case[field] = value
                with self.assertRaises(ValueError):
                    HOST.assess_swift([swift_target(SWIFT_TARGETS[0], [case]), swift_target(SWIFT_TARGETS[1])])


class HostInvocationTest(unittest.TestCase):
    def setUp(self):
        self.work = temporary(self)
        self.repo = self.work / "source with spaces Ω"
        scripts = self.repo / "scripts"
        scripts.mkdir(parents=True)
        for name in ("check-audit-receipt.py", "run-platform-tests.py"):
            shutil.copy2(ROOT / "scripts" / name, scripts / name)
        # No actual Gradle/native program is installed in this fixture checkout.
        for path in (self.repo / "gradlew", self.repo / "gradlew.bat", scripts / "run-audit-command.py"):
            path.write_text("synthetic boundary; never execute this file\n", encoding="utf-8")
        patcher = mock.patch.object(HOST, "ROOT", self.repo)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.state = self.work / "new job state Ω"
        self.host = HOST.Host("windows-x64", self.state)
        self.assertFalse(self.state.exists(), "Host construction must not create or overwrite state")
        self.state.mkdir()
        self.host.evidence.mkdir()
        home = self.state / "gradle-home"
        home.mkdir()
        policy = b"synthetic bounded-home policy\n"
        (home / "gradle.properties").write_bytes(policy)
        self.source = {"commit": "1" * 40, "tree": "2" * 40, "status": "",
                       "diffSha256": hashlib.sha256(b"").hexdigest()}
        self.context = {"schema": 1, "id": "3" * 32, "root": str(self.repo),
                        "expectedCommit": self.source["commit"], "tree": self.source["tree"],
                        "source": copy.deepcopy(self.source), "host": "windows-x64",
                        "gradleHome": str(home), "gradlePropertiesSha256": hashlib.sha256(policy).hexdigest(),
                        "javaHomes": [], "preexistingOutputPaths": [], "createdUtc": "synthetic fixture"}
        self.context_bytes = (json.dumps(self.context, indent=2) + "\n").encode("utf-8")
        (self.state / "context.json").write_bytes(self.context_bytes)
        self.host.admission = {"commit": self.source["commit"], "tree": self.source["tree"],
                               "ref": HOST.REF, "role": self.host.role, "requestedScope": "full"}
        self.host.context = copy.deepcopy(self.context)
        self.host.context_hash = hashlib.sha256(self.context_bytes).hexdigest()
        self.host.owns_state = True
        self.host.state_identity = self.host.identity(self.state)
        owned_work = self.state / "work"
        owned_work.mkdir()
        self.host.work_identity = self.host.identity(owned_work)
        self.host.safe = True
        self.calls = []
        self.cancel_calls = []
        self.children = []
        self.next_mutation = None
        self.next_status = 0
        self.next_wait = None
        self.cancel_status = 0
        self.arguments = ["check", "--tests", "test case with spaces Ω", ""]
        self.output = self.work / "github-output.txt"
        env_patch = mock.patch.dict(os.environ, {"GITHUB_OUTPUT": str(self.output)})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        popen_patch = mock.patch.object(HOST.subprocess, "Popen", side_effect=self.controller)
        popen_patch.start()
        self.addCleanup(popen_patch.stop)
        run_patch = mock.patch.object(HOST.subprocess, "run", side_effect=self.external_command)
        run_patch.start()
        self.addCleanup(run_patch.stop)
        for name in ("kill", "killpg"):
            if hasattr(HOST.os, name):
                signal_patch = mock.patch.object(HOST.os, name,
                    side_effect=AssertionError("host fixture must not signal its synthetic/unowned PID"))
                signal_patch.start()
                self.addCleanup(signal_patch.stop)
        disk_patch = mock.patch.object(HOST.shutil, "disk_usage",
                                      return_value=types.SimpleNamespace(free=10 * 1024 ** 3))
        disk_patch.start()
        self.addCleanup(disk_patch.stop)

    def write_receipt(self, command):
        boundary = command.index("--")
        options = dict(zip(command[2:boundary:2], command[3:boundary:2]))
        invocation = options["--id"]
        self.assertRegex(invocation, r"^[0-9a-f]{32}$")
        receipt = Path(options["--receipt"])
        evidence = self.host.evidence / invocation
        evidence.mkdir()
        record = {"schema": 1, "id": invocation, "purpose": options["--purpose"],
                  "kind": options["--kind"], "host": self.host.role, "jobId": self.context["id"],
                  "requestedArgv": command[boundary + 1:], "cwd": str(self.repo),
                  "wrapper": str(self.host.wrapper), "gradleHome": self.context["gradleHome"],
                  "sourceBefore": copy.deepcopy(self.source), "sourceAfter": copy.deepcopy(self.source),
                  "productExitCode": self.next_status, "stopExitCode": 0, "finalExitCode": self.next_status,
                  "sourceUnchanged": True, "ownedSurvivors": [], "errors": [],
                  "evidenceDirectory": str(evidence), "reports": []}
        initial = dict(record, productExitCode=None, stopExitCode=None, finalExitCode=125,
                       sourceBefore=None, sourceAfter=None, sourceUnchanged=False)
        (evidence / "start.json").write_text(json.dumps(initial), encoding="utf-8")
        for name in ("product.stdout.log", "product.stderr.log", "stop.stdout.log", "stop.stderr.log"):
            (evidence / name).write_text("synthetic " + name + "\n", encoding="utf-8")
        (evidence / "report-manifest.json").write_text(json.dumps({"schema": 1, "records": []}), encoding="utf-8")
        if self.next_mutation:
            self.next_mutation(record, receipt, evidence, "before-write")
        raw = (json.dumps(record, indent=2) + "\n").encode("utf-8")
        receipt.write_bytes(raw)
        (evidence / "receipt.json").write_bytes(raw)
        if self.next_mutation:
            self.next_mutation(record, receipt, evidence, "after-write")
        return options, record

    def controller(self, command, **kwargs):
        self.assertEqual([sys.executable, str(self.host.runner)], command[:2])
        self.assertEqual(self.repo, kwargs["cwd"])
        self.calls.append({"command": list(command), "options": kwargs})
        options, record = self.write_receipt(command)
        owner = self

        class Controller:
            pid = 424242  # Recorded fixture identity only; never passed to an OS signal API.

            def __init__(self):
                self.waits = []

            def wait(self, timeout=None):
                self.waits.append(timeout)
                if len(self.waits) == 1 and owner.next_wait == "interrupt":
                    raise KeyboardInterrupt("synthetic cooperative interruption")
                if owner.next_wait == "always-timeout" or (len(self.waits) == 1 and owner.next_wait == "timeout"):
                    raise subprocess.TimeoutExpired(command, timeout)
                return owner.next_status

            def terminate(self):
                owner.fail("host driver must not hard-terminate its Windows controller")

            def kill(self):
                owner.fail("host driver must request cooperative cancellation, not kill its controller")

        child = Controller()
        self.children.append(child)
        return child

    def external_command(self, command, **kwargs):
        expected = [sys.executable, str(self.host.runner), "request-cancel", "--state", str(self.state), "--id"]
        self.assertEqual(expected, command[:-1], "unexpected real external command in a host fixture")
        self.assertRegex(command[-1], r"^[0-9a-f]{32}$")
        self.cancel_calls.append({"command": list(command), "options": kwargs})
        return subprocess.CompletedProcess(command, self.cancel_status, stdout=b"synthetic cancel receipt\n", stderr=b"")

    def invoke(self, label="fixture-leaf", **kwargs):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return self.host.invoke(label, self.arguments, timeout=60, **kwargs)

    def test_unknown_or_mismatched_scope_is_rejected_before_state_or_process_creation(self):
        for role, scope in (("windows-x64", "invented"), ("macos-arm64", "windows-followup"),
                             ("macos-x64", "windows-followup"), ("macos-arm64", "windows-diagnostics"),
                             ("macos-x64", "windows-diagnostics"), ("windows-x64", "apple-followup"),
                             ("macos-x64", "apple-followup"), ("unknown", "full")):
            state = self.work / (role + "-" + scope)
            with self.subTest(role=role, scope=scope), self.assertRaisesRegex(ValueError, "role/scope"):
                HOST.Host(role, state, scope=scope)
            self.assertFalse(state.exists())
        self.assertEqual([], self.calls)

    def test_windows_followup_has_one_filtered_graph_assessment_and_cleanup(self):
        gate = HOST.load_gate()
        expected = [
            ":p2p-core:jvmTest", "--tests", "dev.p2pkit.core.transfer.FileTransferJvmTest",
            "--tests", "dev.p2pkit.core.internal.PeerRegistryTest",
            "--tests", "dev.p2pkit.core.internal.PeerSubscriptionHookTest",
            "--tests", "dev.p2pkit.core.internal.PeerPublicationConcurrencyTest",
            "--tests", "dev.p2pkit.core.internal.DiscoveryReemitContractTest",
            ":p2p-core:testAndroidHostTest", "--tests",
            "dev.p2pkit.core.transfer.AndroidDurableFileDestinationAndroidHostTest",
            ":p2p-transport-lan:jvmTest", "--tests", "dev.p2pkit.transport.lan.JvmRawConnection*",
            "--tests", "dev.p2pkit.transport.lan.KitTestDiagnosticsTest",
            "--tests", "dev.p2pkit.transport.lan.JvmLanLoopbackTest",
            "--tests", "dev.p2pkit.transport.lan.JvmLanAcceptLoopResilienceTest",
            "--tests", "dev.p2pkit.transport.lan.JvmLanAdmissionControlTest",
            "--tests", "dev.p2pkit.transport.lan.JvmLanDiscoveryHeartbeatTest",
            ":p2p-sample-desktop-ui:checkRuntime", ":p2p-sample-desktop-ui:createDistributable",
            "--continue", "--init-script", str(self.repo / "gradle/platform-test-coverage.init.gradle"),
            "-Pp2pkit.testCoverageRoot=" + str(self.repo), "-Pp2pkit.testCoverageToken=" + TOKEN,
        ]
        for success in (True, False):
            with self.subTest(success=success), \
                    mock.patch.object(HOST.uuid, "uuid4", return_value=types.SimpleNamespace(hex=TOKEN)), \
                    mock.patch.object(self.host, "invoke", return_value=success) as invoke, \
                    mock.patch.object(self.host, "clean_outputs") as clean, \
                    mock.patch.object(HOST, "load_gate", return_value=gate), \
                    mock.patch.object(gate, "read_json", side_effect=[windows_report(WINDOWS_FOLLOWUP_TASKS), POLICY]) as read:
                self.host.windows_followup()
            invoke.assert_called_once_with("windows-followup", expected)
            clean.assert_called_once_with()
            self.assertEqual(2 if success else 0, read.call_count)
        self.assertEqual([{"component": "windows-followup-execution", "result": "PASS", "inspectionOnly": True}],
                         self.host.rows)

    def test_windows_diagnostics_has_only_the_filtered_lan_graph_assessment_and_cleanup(self):
        gate = HOST.load_gate()
        expected = [
            ":p2p-transport-lan:jvmTest", "--tests", "dev.p2pkit.transport.lan.JvmLanAcceptLoopResilienceTest",
            "--tests", "dev.p2pkit.transport.lan.JvmLanAdmissionControlTest",
            "--continue", "--init-script", str(self.repo / "gradle/platform-test-coverage.init.gradle"),
            "-Pp2pkit.testCoverageRoot=" + str(self.repo), "-Pp2pkit.testCoverageToken=" + TOKEN,
        ]
        for success in (True, False):
            with self.subTest(success=success), \
                    mock.patch.object(HOST.uuid, "uuid4", return_value=types.SimpleNamespace(hex=TOKEN)), \
                    mock.patch.object(self.host, "invoke", return_value=success) as invoke, \
                    mock.patch.object(self.host, "clean_outputs") as clean, \
                    mock.patch.object(HOST, "load_gate", return_value=gate), \
                    mock.patch.object(gate, "read_json", side_effect=[windows_report(WINDOWS_DIAGNOSTICS_TASKS), POLICY]) as read:
                self.host.windows_diagnostics()
            invoke.assert_called_once_with("windows-diagnostics", expected)
            clean.assert_called_once_with()
            self.assertEqual(2 if success else 0, read.call_count)
        self.assertEqual([{"component": "windows-diagnostics-execution", "result": "PASS", "inspectionOnly": True}],
                         self.host.rows)

    def test_constructor_does_not_borrow_foreign_state_or_caller_opt_ins(self):
        foreign = self.work / "foreign prior attempt"
        foreign.mkdir()
        sentinel = foreign / "context.json"
        sentinel.write_text("preserve prior attempt\n", encoding="utf-8")
        injected = {name: "caller-owned override" for name in HOST.ADAPTER_OPT_INS}
        injected.update(ANDROID_SDK_ROOT="legacy conflicting SDK")
        with mock.patch.dict(os.environ, injected):
            host = HOST.Host("macos-arm64", foreign)
        self.assertFalse(host.owns_state)
        self.assertEqual("preserve prior attempt\n", sentinel.read_text(encoding="utf-8"))
        self.assertEqual(["context.json"], [path.name for path in foreign.iterdir()])
        for key in HOST.ADAPTER_OPT_INS:
            if key not in ("P2PKIT_GRADLE_EXECUTOR", "P2PKIT_XCODE_JOBS"):
                self.assertNotIn(key, host.environment)
        self.assertEqual(str(host.runner), host.environment["P2PKIT_GRADLE_EXECUTOR"])
        self.assertEqual("2", host.environment["P2PKIT_XCODE_JOBS"])
        self.assertNotIn("ANDROID_SDK_ROOT", host.environment)
        for budget in (True, 0, HOST.FINALIZATION_GRACE, 19801):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                HOST.Host("windows-x64", foreign, timeout_seconds=budget)

    def test_invocation_binds_exact_original_vector_and_complete_evidence_before_pass(self):
        self.assertTrue(self.invoke())
        self.assertEqual(1, len(self.calls))
        command = self.calls[0]["command"]
        self.assertEqual(self.arguments, command[command.index("--") + 1:])
        self.assertEqual(str(self.repo / "gradlew.bat"), command[command.index("--wrapper") + 1])
        self.assertEqual([60 + HOST.FINALIZATION_GRACE], self.children[0].waits)
        row = self.host.rows[-1]
        self.assertEqual("PASS", row["result"])
        self.assertTrue(row["cleanupComplete"])
        self.assertFalse(row["cancelled"])
        self.assertEqual(424242, row["controllerPid"])
        receipt = self.host.receipts["fixture-leaf"]
        self.assertEqual(self.context["id"], receipt["jobId"])
        self.assertEqual(self.source, receipt["sourceBefore"])
        self.assertEqual(self.source, receipt["sourceAfter"])
        self.assertTrue(self.host.safe)
        self.assertEqual([], self.cancel_calls)

    def test_windows_git_bash_precedes_wsl_in_both_real_callers_without_changing_native_gradle(self):
        with windows_tool_boundary(self, self.host) as tools:
            try:
                self.host.prerequisites()
            except ValueError:
                print((self.host.evidence / "prerequisites.json").read_text(encoding="utf-8"))
                raise
            observed = json.loads((self.host.evidence / "prerequisites.json").read_text(encoding="utf-8"))
            self.assertEqual([str(tools["bash"]), "--version"], observed["tools"]["bash"]["command"])
            self.assertEqual([str(tools["git"]), "--version"], observed["tools"]["git"]["command"])
            self.assertEqual(0, observed["tools"]["bash"]["exitCode"])
            self.assertEqual(1, tools["memory"].call_count)
            with mock.patch.object(self.host, "check", return_value=True), \
                    mock.patch.object(self.host, "clean_outputs") as clean:
                self.host.windows()
            self.assertEqual(2, clean.call_count)
            self.assertEqual(3, len(self.calls))
            wrapper, libraries, desktop = self.calls
            command = wrapper["command"]
            self.assertEqual([str(tools["bash"]), "scripts/tests/check-gradle-wrapper-test.sh"],
                             command[command.index("--") + 1:])
            self.assertEqual("command", command[command.index("--kind") + 1])
            scoped_path = wrapper["options"]["env"]["PATH"]
            self.assertEqual([str(tools["installation"] / "bin"), str(tools["installation"] / "usr/bin"),
                              str(tools["wsl"]), str(tools["git"].parent)], scoped_path.split(os.pathsep))
            version_call = next(row for row in tools["calls"] if row["command"][0] == str(tools["bash"]))
            self.assertEqual(scoped_path, version_call["options"]["env"]["PATH"])
            for call in (libraries, desktop):
                command = call["command"]
                self.assertEqual("gradle", command[command.index("--kind") + 1])
                self.assertEqual(tools["environment"]["PATH"], call["options"]["env"]["PATH"])
            self.assertTrue(WINDOWS_TASKS <= set(libraries["command"]))
            self.assertEqual(HOST.DESKTOP_TASKS, desktop["command"][desktop["command"].index("--") + 1:])
            for call in self.calls:
                command = call["command"]
                self.assertEqual([sys.executable, str(self.host.runner)], command[:2])
                self.assertEqual(str(self.repo / "gradlew.bat"), command[command.index("--wrapper") + 1])
            self.assertEqual(tools["environment"], self.host.environment)
            self.assertEqual(tools["environment"]["PATH"], os.environ["PATH"])
            self.assertTrue(all(row["result"] == "PASS" and row["cleanupComplete"] for row in self.host.rows))

    def test_windows_git_bin_layout_with_spaces_uses_the_same_explicit_shell(self):
        with windows_tool_boundary(self, self.host, layout="bin") as tools:
            self.host.prerequisites()
            observed = json.loads((self.host.evidence / "prerequisites.json").read_text(encoding="utf-8"))
            self.assertEqual([str(tools["bash"]), "--version"], observed["tools"]["bash"]["command"])
            self.assertEqual([str(tools["git"]), "--version"], observed["tools"]["git"]["command"])
            self.assertEqual(tools["environment"], self.host.environment)

    def assert_observed_cygwin_git_bash_reaches_both_callers(self, layout):
        # Actual Git-for-Windows 2.55.0.windows.5 banner from hosted trial2.
        banner = "GNU bash, version 5.3.15(2)-release (x86_64-pc-cygwin)\n"
        with windows_tool_boundary(self, self.host, layout=layout, bash_result=(0, banner, "")) as tools:
            try:
                self.host.prerequisites()
            except ValueError:
                print((self.host.evidence / "prerequisites.json").read_text(encoding="utf-8"))
                raise
            observed = json.loads((self.host.evidence / "prerequisites.json").read_text(encoding="utf-8"))
            self.assertEqual(banner, observed["tools"]["bash"]["stdout"])
            self.assertEqual("git version 2.55.0.windows.5\n", observed["tools"]["git"]["stdout"])
            self.assertEqual([str(tools["bash"]), "--version"], observed["tools"]["bash"]["command"])
            with mock.patch.object(self.host, "check", return_value=True), \
                    mock.patch.object(self.host, "clean_outputs") as clean:
                self.host.windows()
            self.assertEqual(2, clean.call_count)
            self.assertEqual(3, len(self.calls))
            wrapper, libraries, desktop = self.calls
            command = wrapper["command"]
            self.assertEqual([str(tools["bash"]), "scripts/tests/check-gradle-wrapper-test.sh"],
                             command[command.index("--") + 1:])
            self.assertEqual("command", command[command.index("--kind") + 1])
            bash_probe = next(row for row in tools["calls"] if row["command"][0] == str(tools["bash"]))
            self.assertEqual(bash_probe["options"]["env"]["PATH"], wrapper["options"]["env"]["PATH"])
            self.assertEqual(observed["windowsShell"]["PATH"], wrapper["options"]["env"]["PATH"])
            for call in (libraries, desktop):
                self.assertEqual(tools["environment"]["PATH"], call["options"]["env"]["PATH"])
                self.assertEqual("gradle", call["command"][call["command"].index("--kind") + 1])
            for call in self.calls:
                self.assertEqual([sys.executable, str(self.host.runner)], call["command"][:2])
                self.assertEqual(str(self.repo / "gradlew.bat"),
                                 call["command"][call["command"].index("--wrapper") + 1])
            self.assertTrue(WINDOWS_TASKS <= set(libraries["command"]))
            self.assertEqual(HOST.DESKTOP_TASKS, desktop["command"][desktop["command"].index("--") + 1:])
            self.assertEqual(tools["environment"], self.host.environment)
            self.assertEqual(tools["environment"]["PATH"], os.environ["PATH"])
            self.assertFalse(any(row["command"][0] == "bash" for row in tools["calls"]))
            self.assertTrue(all(row["result"] == "PASS" and row["cleanupComplete"] for row in self.host.rows))

    def test_observed_cygwin_git_bash_cmd_layout_reaches_both_callers(self):
        self.assert_observed_cygwin_git_bash_reaches_both_callers("cmd")

    def test_observed_cygwin_git_bash_bin_layout_reaches_both_callers(self):
        self.assert_observed_cygwin_git_bash_reaches_both_callers("bin")

    def test_windows_bash_rejects_other_or_malformed_build_targets(self):
        banners = (
            "GNU bash, version 5.3 (i686-pc-cygwin)\n",
            "GNU bash, version 5.3 (aarch64-pc-cygwin)\n",
            "GNU bash, version 5.3 (i686-pc-msys)\n",
            "GNU bash, version 5.3 (x86_64-pc-linux-gnu)\n",
            "GNU bash, version 5.3 (x86_64-pc-cygwin-extra)\n",
            "GNU bash, version 5.3 (x86_64-pc-msys2)\n",
            "GNU bash, version 5.3 (x86_64-pc-cygwin\n",
            "Not GNU bash, version 5.3 (x86_64-pc-cygwin)\n",
            "Windows Subsystem for Linux has no installed distributions.\n",
            "",
        )
        for index, banner in enumerate(banners):
            # Each prerequisite report is write-once, including rejected probes.
            host = HOST.Host("windows-x64", self.work / ("rejected-banner-" + str(index)))
            host.evidence.mkdir(parents=True)
            host.owns_state = True
            host.state_identity = host.identity(host.state)
            with self.subTest(banner=banner), \
                    windows_tool_boundary(self, host, bash_result=(0, banner, "")):
                with self.assertRaisesRegex(ValueError, "Git for Windows Bash"):
                    host.prerequisites()
                observed = json.loads((host.evidence / "prerequisites.json").read_text(encoding="utf-8"))
                self.assertEqual(banner, observed["tools"]["bash"]["stdout"])
                self.assertEqual(0, observed["tools"]["bash"]["exitCode"])
                self.assertIsNone(host.windows_shell)
                self.assertEqual([], self.calls)

    def test_cygwin_git_bash_banner_does_not_override_failed_version_query(self):
        banner = "GNU bash, version 5.3.15(2)-release (x86_64-pc-cygwin)\n"
        with windows_tool_boundary(self, self.host, bash_result=(7, banner, "synthetic failure\n")):
            with self.assertRaisesRegex(ValueError, "Required tool version query failed"):
                self.host.prerequisites()
        observed = json.loads((self.host.evidence / "prerequisites.json").read_text(encoding="utf-8"))
        self.assertEqual(7, observed["tools"]["bash"]["exitCode"])
        self.assertEqual(banner, observed["tools"]["bash"]["stdout"])
        self.assertEqual("synthetic failure\n", observed["tools"]["bash"]["stderr"])
        self.assertIsNone(self.host.windows_shell)
        self.assertEqual([], self.calls)

    def test_cygwin_git_bash_banner_does_not_admit_non_windows_git(self):
        banner = "GNU bash, version 5.3.15(2)-release (x86_64-pc-cygwin)\n"
        with windows_tool_boundary(self, self.host, bash_result=(0, banner, ""),
                                   git_version="git version 2.55.0\n"):
            with self.assertRaisesRegex(ValueError, "Git for Windows version"):
                self.host.prerequisites()
        observed = json.loads((self.host.evidence / "prerequisites.json").read_text(encoding="utf-8"))
        self.assertEqual(banner, observed["tools"]["bash"]["stdout"])
        self.assertEqual("git version 2.55.0\n", observed["tools"]["git"]["stdout"])
        self.assertIsNone(self.host.windows_shell)
        self.assertEqual([], self.calls)

    def test_missing_windows_git_retains_failed_resolution_and_other_version_diagnostics(self):
        with windows_tool_boundary(self, self.host, missing="git"):
            with self.assertRaisesRegex(ValueError, "Required tool version query failed"):
                self.host.prerequisites()
        observed = json.loads((self.host.evidence / "prerequisites.json").read_text(encoding="utf-8"))
        self.assertEqual([], observed["tools"]["bash"]["command"])
        self.assertIsNone(observed["tools"]["bash"]["exitCode"])
        self.assertIn("Git for Windows", observed["tools"]["bash"]["error"])
        self.assertEqual({"python", "git", "java17", "java21", "bash"}, set(observed["tools"]))
        self.assertEqual([], self.calls)
        self.assertIsNone(self.host.windows_shell)

    def test_missing_windows_bash_retains_failed_resolution_and_never_uses_wsl(self):
        with windows_tool_boundary(self, self.host, missing="bash") as tools:
            with self.assertRaisesRegex(ValueError, "Required tool version query failed"):
                self.host.prerequisites()
            self.assertFalse(any(row["command"][0] == "bash" for row in tools["calls"]))
        observed = json.loads((self.host.evidence / "prerequisites.json").read_text(encoding="utf-8"))
        self.assertEqual([], observed["tools"]["bash"]["command"])
        self.assertIn("Git for Windows Bash", observed["tools"]["bash"]["error"])
        self.assertTrue(all(observed["tools"][name]["exitCode"] == 0 for name in ("python", "git", "java17", "java21")))
        self.assertIsNone(self.host.windows_shell)

    def test_unusable_windows_bash_is_fail_closed_with_its_original_diagnostic(self):
        with windows_tool_boundary(self, self.host, bash_result=(7, "", "synthetic Bash failed\n")) as tools:
            with self.assertRaisesRegex(ValueError, "Required tool version query failed"):
                self.host.prerequisites()
            observed = json.loads((self.host.evidence / "prerequisites.json").read_text(encoding="utf-8"))
            self.assertEqual({"command": [str(tools["bash"]), "--version"], "exitCode": 7,
                              "stdout": "", "stderr": "synthetic Bash failed\n"}, observed["tools"]["bash"])
        self.assertIsNone(self.host.windows_shell)
        self.assertEqual([], self.calls)

    def test_windows_bash_start_failure_is_retained_without_binding_an_unvalidated_shell(self):
        with windows_tool_boundary(self, self.host, bash_result=OSError("synthetic executable unavailable")):
            with self.assertRaisesRegex(ValueError, "Required tool version query failed"):
                self.host.prerequisites()
        observed = json.loads((self.host.evidence / "prerequisites.json").read_text(encoding="utf-8"))
        self.assertIsNone(observed["tools"]["bash"]["exitCode"])
        self.assertEqual("synthetic executable unavailable", observed["tools"]["bash"]["error"])
        self.assertIsNone(self.host.windows_shell)

    def test_windows_bash_timeout_is_retained_and_does_not_fall_back_to_wsl(self):
        timeout = subprocess.TimeoutExpired("synthetic Git Bash", 60)
        with windows_tool_boundary(self, self.host, bash_result=timeout) as tools:
            with self.assertRaisesRegex(ValueError, "Required tool version query failed"):
                self.host.prerequisites()
            self.assertFalse(any(row["command"][0] == "bash" for row in tools["calls"]))
        observed = json.loads((self.host.evidence / "prerequisites.json").read_text(encoding="utf-8"))
        self.assertIsNone(observed["tools"]["bash"]["exitCode"])
        self.assertIn("timed out", observed["tools"]["bash"]["error"])
        self.assertIsNone(self.host.windows_shell)

    def test_unsupported_windows_git_layout_is_reported_without_ancestor_search(self):
        with windows_tool_boundary(self, self.host, layout="mingw64/bin"):
            with self.assertRaisesRegex(ValueError, "Required tool version query failed"):
                self.host.prerequisites()
        observed = json.loads((self.host.evidence / "prerequisites.json").read_text(encoding="utf-8"))
        self.assertEqual([], observed["tools"]["bash"]["command"])
        self.assertIn("Git for Windows Bash/tools are unavailable", observed["tools"]["bash"]["error"])
        self.assertIsNone(self.host.windows_shell)

    def test_missing_windows_unix_utilities_cannot_be_substituted_with_ambient_tools(self):
        with windows_tool_boundary(self, self.host, missing="utilities"):
            with self.assertRaisesRegex(ValueError, "Required tool version query failed"):
                self.host.prerequisites()
        observed = json.loads((self.host.evidence / "prerequisites.json").read_text(encoding="utf-8"))
        self.assertEqual([], observed["tools"]["bash"]["command"])
        self.assertIn("Git for Windows Bash/tools are unavailable", observed["tools"]["bash"]["error"])
        self.assertIsNone(self.host.windows_shell)

    def test_windows_shell_requires_msys_bash_not_just_a_successful_version_exit(self):
        with windows_tool_boundary(self, self.host, bash_result=(0, "GNU bash, version 5.2 (x86_64-pc-linux-gnu)\n", "")):
            with self.assertRaisesRegex(ValueError, "Git for Windows Bash"):
                self.host.prerequisites()
        self.assertTrue((self.host.evidence / "prerequisites.json").is_file())
        self.assertIsNone(self.host.windows_shell)

    def test_windows_shell_requires_native_git_for_windows_version(self):
        with windows_tool_boundary(self, self.host, git_version="git version 2.55.0\n"):
            with self.assertRaisesRegex(ValueError, "Git for Windows version"):
                self.host.prerequisites()
        self.assertTrue((self.host.evidence / "prerequisites.json").is_file())
        self.assertIsNone(self.host.windows_shell)

    def test_windows_components_cannot_bypass_shell_prerequisites(self):
        with self.assertRaisesRegex(ValueError, "Windows shell prerequisite"):
            self.host.windows()
        self.assertEqual([], self.calls)

    def test_mac_prerequisites_keep_posix_bash_and_required_xcode_without_windows_resolution(self):
        self.host.role = "macos-arm64"
        native_os = types.SimpleNamespace(**vars(os))
        native_os.name = "posix"
        environment = dict(self.host.environment, JAVA_HOME=str(self.work / "jdk17"),
                           P2PKIT_AUDIT_JDK21=str(self.work / "jdk21"))
        self.host.environment = dict(environment)
        versions = {sys.executable: "Python 3.12.10\n", "git": "git version 2.55.0\n",
                    "bash": "GNU bash, version 3.2.57(1)-release (arm64-apple-darwin)\n",
                    "ruby": "ruby 3.4.0\n", "xcodebuild": "Xcode 26.5\nBuild version fixture\n",
                    "xcrun": "26.5\n", "jq": "jq-1.8.1\n", "xmllint": "libxml version fixture\n"}
        for major in (17, 21):
            versions[str(self.work / ("jdk" + str(major)) / "bin/java")] = f'openjdk version "{major}.0.1"\n'
        calls = []

        def version(command, **kwargs):
            self.assertEqual(environment["PATH"], kwargs["env"]["PATH"])
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, stdout=versions[command[0]], stderr="")

        disk = types.SimpleNamespace(_asdict=lambda: {"free": 10 * 1024 ** 3})
        with mock.patch.object(HOST, "os", native_os), \
                mock.patch.dict(os.environ, environment, clear=True), \
                mock.patch.object(HOST.platform, "platform", return_value="macOS-fixture"), \
                mock.patch.object(HOST.platform, "machine", return_value="arm64"), \
                mock.patch.object(HOST.shutil, "disk_usage", return_value=disk), \
                mock.patch.object(HOST.shutil, "which", side_effect=AssertionError("not a Windows role")), \
                mock.patch.object(HOST.subprocess, "run", side_effect=version), \
                mock.patch.object(HOST.subprocess, "check_output", return_value=str(16 * 1024 ** 3)) as ram:
            self.host.prerequisites()
        ram.assert_called_once_with(["sysctl", "-n", "hw.memsize"], text=True, timeout=30)
        self.assertIn(["bash", "--version"], calls)
        self.assertIn(["xcodebuild", "-version"], calls)
        self.assertIn(["xcrun", "--show-sdk-version", "--sdk", "iphonesimulator"], calls)
        self.assertEqual(10, len(calls))
        self.assertEqual(environment, self.host.environment)
        self.assertIsNone(self.host.windows_shell)

    def test_clean_product_failure_remains_failed_but_cleanup_proof_is_retained(self):
        self.next_status = 7
        self.assertFalse(self.invoke())
        row = self.host.rows[-1]
        self.assertEqual("FAIL", row["result"])
        self.assertEqual(7, row["exitCode"])
        self.assertTrue(row["cleanupComplete"])
        self.assertTrue(self.host.safe, "a finalized product failure must not be relabelled an ownership failure")
        self.assertEqual(7, self.host.receipts["fixture-leaf"]["productExitCode"])

    def test_missing_malformed_or_unbound_receipt_cannot_become_a_successful_leaf(self):
        changes = (("schema", True), ("id", "f" * 32), ("jobId", "4" * 32), ("kind", "command"),
                   ("host", "macos-x64"), ("gradleHome", str(self.work)),
                   ("purpose", "another-purpose"), ("cwd", str(self.work)),
                   ("wrapper", str(self.repo / "gradlew")), ("requestedArgv", ["help"]),
                   ("stopExitCode", 9), ("stopExitCode", False), ("productExitCode", 1),
                   ("finalExitCode", False), ("sourceUnchanged", 1), ("ownedSurvivors", {}),
                   ("ownedSurvivors", [{"pid": 99}]), ("errors", ["synthetic failed cleanup"]),
                   ("evidenceDirectory", str(self.work)))
        for index, (field, value) in enumerate(changes):
            with self.subTest(field=field, value=value):
                self.host.safe = True

                def mutate(record, receipt, evidence, phase):
                    if phase == "before-write":
                        record[field] = value

                self.next_mutation = mutate
                with self.assertRaises(HOST.InfrastructureFailure):
                    self.invoke("invalid-receipt-" + str(index))
                self.assertFalse(self.host.safe)
                self.assertEqual("FAIL", self.host.rows[-1]["result"])
                self.assertFalse(self.host.rows[-1]["cleanupComplete"])
        self.assertEqual({}, self.host.receipts)

    def test_fresh_source_equality_cannot_be_forged_with_self_consistent_foreign_receipts(self):
        for index, (field, value) in enumerate((("commit", "7" * 40), ("tree", "8" * 40),
                                               ("status", " M tracked.txt\n"), ("diffSha256", "9" * 64))):
            with self.subTest(field=field):

                def mutate(record, receipt, evidence, phase):
                    if phase == "before-write":
                        record["sourceBefore"][field] = value
                        record["sourceAfter"][field] = value

                self.next_mutation = mutate
                with self.assertRaises(HOST.InfrastructureFailure):
                    self.invoke("foreign-source-" + str(index))
                self.assertFalse(self.host.rows[-1]["cleanupComplete"])

    def test_actual_log_start_manifest_and_final_receipt_files_are_mandatory(self):
        for index, name in enumerate(("receipt.json", "start.json", "product.stdout.log", "product.stderr.log",
                                      "stop.stdout.log", "stop.stderr.log", "report-manifest.json")):
            with self.subTest(missing=name):

                def mutate(record, receipt, evidence, phase):
                    if phase == "after-write":
                        (evidence / name).unlink()

                self.next_mutation = mutate
                with self.assertRaises(HOST.InfrastructureFailure):
                    self.invoke("missing-evidence-" + str(index))
                self.assertFalse(self.host.safe)
        for index, mode in enumerate(("missing", "malformed", "duplicate", "copies-differ", "context-changed")):
            with self.subTest(mode=mode):
                (self.state / "context.json").write_bytes(self.context_bytes)

                def mutate(record, receipt, evidence, phase):
                    if phase != "after-write":
                        return
                    if mode == "missing":
                        receipt.unlink()
                    elif mode == "malformed":
                        receipt.write_text("{invalid", encoding="utf-8")
                    elif mode == "duplicate":
                        receipt.write_text('{"schema":1,"schema":1}', encoding="utf-8")
                    elif mode == "copies-differ":
                        (evidence / "receipt.json").write_text("{}", encoding="utf-8")
                    elif mode == "context-changed":
                        (self.state / "context.json").write_bytes(self.context_bytes + b" ")

                self.next_mutation = mutate
                with self.assertRaises(HOST.InfrastructureFailure):
                    self.invoke("unretained-evidence-" + str(index))
                self.assertFalse(self.host.rows[-1]["cleanupComplete"])

    def test_symlinked_evidence_is_not_followed_or_uploaded_as_owned(self):
        sentinel = self.work / "caller-owned-file"
        sentinel.write_text("preserve caller data\n", encoding="utf-8")

        def mutate(record, receipt, evidence, phase):
            if phase == "after-write":
                log = evidence / "product.stdout.log"
                log.unlink()
                log.symlink_to(sentinel)

        self.next_mutation = mutate
        with self.assertRaises(HOST.InfrastructureFailure):
            self.invoke()
        self.assertEqual("preserve caller data\n", sentinel.read_text(encoding="utf-8"))
        self.assertFalse(self.host.safe)

    def test_cancellation_uses_id_bound_cooperative_request_and_cannot_pass_on_zero_exit(self):
        for index, interruption in enumerate(("interrupt", "timeout")):
            with self.subTest(interruption=interruption):
                self.next_wait = interruption
                label = "cancelled-" + str(index)
                with self.assertRaises(HOST.InfrastructureFailure):
                    self.invoke(label)
                self.assertEqual([60 + HOST.FINALIZATION_GRACE, HOST.FINALIZATION_GRACE], self.children[-1].waits)
                row = self.host.rows[-1]
                self.assertTrue(row["cancelled"])
                self.assertEqual("FAIL", row["result"])
                self.assertFalse(row["cleanupComplete"])
                self.assertFalse(self.host.safe)
                command = self.calls[-1]["command"]
                invocation = command[command.index("--id") + 1]
                self.assertEqual(invocation, self.cancel_calls[-1]["command"][-1])
                cancel = json.loads((self.host.evidence / ("cancel-" + invocation + ".json")).read_text())
                self.assertEqual(0, cancel["requestExitCode"])
                self.assertNotIn(label, self.host.receipts)

    def test_failed_cancel_or_unfinished_controller_never_reports_clean_continuation(self):
        for index, wait in enumerate(("timeout", "always-timeout")):
            with self.subTest(wait=wait):
                self.next_wait = wait
                self.cancel_status = 125
                with self.assertRaises(HOST.InfrastructureFailure):
                    self.invoke("failed-cancel-" + str(index))
                self.assertFalse(self.host.safe)
                self.assertTrue(self.host.rows[-1]["cancelled"])
                self.assertEqual("FAIL", self.host.rows[-1]["result"])
                self.assertEqual(2, len(self.children[-1].waits))

    def test_invocation_rejects_reused_receipt_changed_state_and_resource_admission_before_spawn(self):
        (self.state / "host-previous.json").write_text("preserve prior invocation", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.invoke("previous")
        self.assertEqual([], self.calls)
        self.assertEqual("preserve prior invocation", (self.state / "host-previous.json").read_text())
        with mock.patch.object(HOST.shutil, "disk_usage", return_value=types.SimpleNamespace(free=1024)):
            with self.assertRaises(ValueError):
                self.invoke("insufficient-disk")
        with mock.patch.object(self.host, "state_identity", (0, 0)), self.assertRaises(ValueError):
            self.invoke("changed-state")
        with mock.patch.object(self.host, "owns_state", False), self.assertRaises(ValueError):
            self.invoke("unowned-state")
        with mock.patch.object(self.host, "deadline", 0), self.assertRaises(ValueError):
            self.invoke("expired-host")
        self.assertEqual([], self.calls)

    def test_explicit_environment_removal_does_not_leak_outer_opt_ins_to_fixture_controls(self):
        self.assertTrue(self.invoke(kind="command", extra_env={"P2PKIT_GRADLE_EXECUTOR": None,
                             "P2PKIT_XCODE_JOBS": None, "OWNED_SYNTHETIC_VALUE": "space Ω"}))
        environment = self.calls[0]["options"]["env"]
        self.assertNotIn("P2PKIT_GRADLE_EXECUTOR", environment)
        self.assertNotIn("P2PKIT_XCODE_JOBS", environment)
        self.assertEqual("space Ω", environment["OWNED_SYNTHETIC_VALUE"])
        self.assertEqual(str(self.state), environment["P2PKIT_AUDIT_STATE_DIR"])
        self.assertIn("P2PKIT_GRADLE_EXECUTOR", self.host.environment)

    def test_start_receipt_and_report_manifest_are_parsed_and_bound_not_just_present(self):
        for index, mutation in enumerate(("malformed-start", "stale-start", "bool-start-schema",
                                          "malformed-manifest", "mismatched-manifest", "bool-manifest-schema")):
            with self.subTest(mutation=mutation):

                def mutate(record, receipt, evidence, phase):
                    if phase != "after-write":
                        return
                    start = evidence / "start.json"
                    manifest = evidence / "report-manifest.json"
                    if mutation == "malformed-start":
                        start.write_text("{invalid", encoding="utf-8")
                    elif mutation in ("stale-start", "bool-start-schema"):
                        value = json.loads(start.read_text())
                        value["id" if mutation == "stale-start" else "schema"] = (
                            "f" * 32 if mutation == "stale-start" else True)
                        start.write_text(json.dumps(value), encoding="utf-8")
                    elif mutation == "malformed-manifest":
                        manifest.write_text("{invalid", encoding="utf-8")
                    else:
                        value = {"schema": True if mutation == "bool-manifest-schema" else 1,
                                 "records": [] if mutation == "bool-manifest-schema" else [{"source": "another-report"}]}
                        manifest.write_text(json.dumps(value), encoding="utf-8")

                self.next_mutation = mutate
                with self.assertRaises(HOST.InfrastructureFailure):
                    self.invoke("unbound-manifest-" + str(index))
                self.assertFalse(self.host.safe)

    def retained_report(self, record, receipt, evidence, phase):
        if phase == "before-write":
            path = evidence / "reports/build/test-results/fixture.xml"
            path.parent.mkdir(parents=True)
            raw = b'<testsuite name="synthetic" tests="1" failures="0"/>\n'
            path.write_bytes(raw)
            record["reports"] = [{"source": "build/test-results/fixture.xml", "bytes": len(raw),
                                  "sha256": hashlib.sha256(raw).hexdigest(),
                                  "classification": "changed-since-admission",
                                  "retained": path.relative_to(evidence).as_posix()}]
            (evidence / "report-manifest.json").write_text(
                json.dumps({"schema": 1, "records": record["reports"]}), encoding="utf-8")

    def test_retained_report_bytes_and_hashes_are_verified_without_inferred_test_acceptance(self):
        self.next_mutation = self.retained_report
        self.assertTrue(self.invoke())
        record = self.host.receipts["fixture-leaf"]
        self.assertEqual(1, len(record["reports"]))
        self.assertEqual(["fixture-leaf"], [row["component"] for row in self.host.rows])
        # The host leaf is finalized, not assessed as Windows/Kotlin/Swift test execution.
        self.assertNotIn("windows-execution", self.host.receipts)

    def test_corrupt_unretained_or_escape_report_records_reject_even_consistent_receipt_copies(self):
        modes = ("wrong-hash", "wrong-size", "bool-size", "missing-file", "escape", "symlink",
                 "unclassified", "duplicate-retained")
        for index, mode in enumerate(modes):
            with self.subTest(mode=mode):

                def mutate(record, receipt, evidence, phase):
                    self.retained_report(record, receipt, evidence, phase)
                    if phase != "before-write":
                        return
                    row = record["reports"][0]
                    path = evidence / row["retained"]
                    if mode == "wrong-hash":
                        row["sha256"] = "f" * 64
                    elif mode == "wrong-size":
                        row["bytes"] += 1
                    elif mode == "bool-size":
                        row["bytes"] = True
                    elif mode == "missing-file":
                        path.unlink()
                    elif mode == "escape":
                        row["retained"] = "../context.json"
                    elif mode == "symlink":
                        path.unlink()
                        path.symlink_to(self.state / "context.json")
                    elif mode == "unclassified":
                        row["classification"] = "assumed-execution"
                    elif mode == "duplicate-retained":
                        record["reports"].append(dict(row, source="another/source.xml"))
                    (evidence / "report-manifest.json").write_text(
                        json.dumps({"schema": 1, "records": record["reports"]}), encoding="utf-8")

                self.next_mutation = mutate
                with self.assertRaises(HOST.InfrastructureFailure):
                    self.invoke("corrupt-report-" + str(index))
                self.assertFalse(self.host.safe)

    def test_retention_copies_and_hashes_selected_owned_files_before_source_removal(self):
        source = self.state / "work/owned reports"
        source.mkdir()
        (source / "test.xml").write_bytes(b"synthetic XML evidence\n")
        (source / "product.log").write_bytes(b"synthetic failure log\n")
        nested = source / "nested Ω"
        nested.mkdir()
        (nested / "other.txt").write_bytes(b"retained nested bytes\n")
        before = {path.relative_to(source).as_posix(): path.read_bytes()
                  for path in source.rglob("*") if path.is_file()}
        destination = self.host.evidence / "retained-reports"
        rows = self.host.retain_tree(source, destination)
        self.assertEqual(set(before), {row["path"] for row in rows})
        for row in rows:
            self.assertEqual(before[row["path"]], (destination / row["path"]).read_bytes())
            self.assertEqual(hashlib.sha256(before[row["path"]]).hexdigest(), row["sha256"])
            self.assertEqual(len(before[row["path"]]), row["bytes"])
            self.assertEqual(before[row["path"]], (source / row["path"]).read_bytes())
        self.host.remove_work(source)
        self.assertFalse(source.exists())
        self.assertTrue((destination / "product.log").is_file())

    def test_retention_rejects_foreign_destination_symlinks_limits_overwrite_and_corrupt_copy(self):
        source = self.state / "work/reports"
        source.mkdir()
        original = source / "original.txt"
        original.write_bytes(b"preserve original report bytes\n")
        outside = self.work / "unrelated caller data"
        outside.mkdir()
        sentinel = outside / "sentinel.txt"
        sentinel.write_bytes(b"preserve caller data\n")
        with self.assertRaises(ValueError):
            self.host.retain_tree(source, outside / "not-evidence")
        with self.assertRaises(ValueError):
            self.host.retain_tree(source, self.host.evidence / "too-large", byte_limit=1)
        self.assertFalse((self.host.evidence / "too-large").exists())
        existing = self.host.evidence / "existing"
        existing.mkdir()
        (existing / "keep.txt").write_text("prior evidence", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.host.retain_tree(source, existing)
        self.assertEqual("prior evidence", (existing / "keep.txt").read_text())
        link = source / "borrowed.txt"
        link.symlink_to(sentinel)
        with self.assertRaises(ValueError):
            self.host.retain_tree(source, self.host.evidence / "symlink-copy")
        self.assertFalse((self.host.evidence / "symlink-copy").exists())
        link.unlink()
        with mock.patch.object(HOST.shutil, "copyfileobj", side_effect=lambda incoming, outgoing: outgoing.write(b"wrong")):
            with self.assertRaisesRegex(ValueError, "changed during copy"):
                self.host.retain_tree(source, self.host.evidence / "corrupt-copy")
        self.assertEqual(b"preserve original report bytes\n", original.read_bytes())
        self.assertEqual(b"preserve caller data\n", sentinel.read_bytes())

    def test_selected_retention_prunes_only_unselected_links_and_records_omissions(self):
        source = self.state / "work/metadata"
        source.mkdir()
        caller = self.work / "caller-evidence"
        caller.mkdir()
        sentinel = caller / "never-read.txt"
        sentinel.write_text("outside the selected evidence", encoding="utf-8")
        (source / "cache-link").symlink_to(caller, target_is_directory=True)
        (source / "binary-link").symlink_to(sentinel)
        nested = source / "ordinary-directory"
        nested.mkdir()
        (nested / "required.txt").write_text("selected nested file", encoding="utf-8")
        destination = self.host.evidence / "selected-metadata"
        rows = self.host.retain_tree(source, destination, selected=lambda path: path.suffix == ".txt")
        self.assertEqual(["ordinary-directory/required.txt"], [row["path"] for row in rows])
        omissions = json.loads(next(self.host.evidence.glob("retention-omissions-*.json")).read_text())
        self.assertEqual({"cache-link", "binary-link"}, {row["path"] for row in omissions["omitted"]})
        self.assertTrue(all(row["reason"] == "unselected-link-not-followed" for row in omissions["omitted"]))
        (source / "selected-link.txt").symlink_to(sentinel)
        with self.assertRaises(ValueError):
            self.host.retain_tree(source, self.host.evidence / "selected-link-rejection",
                                  selected=lambda path: path.suffix == ".txt")
        self.assertEqual("outside the selected evidence", sentinel.read_text())
        self.assertFalse((destination / "cache-link").exists())

    def test_mac_batches_artifacts_and_reuses_the_consumer_publication_without_erasing_failed_dependencies(self):
        # Orchestration only: existing invocation/retention controls exercise
        # actual receipt validation, file copies and owned cleanup boundaries.
        host = HOST.Host("macos-arm64", self.state / "mac-order")
        consumer = host.state / "work/consumer"
        repository = consumer / "repository"
        repository.mkdir(parents=True)
        artifacts = [":p2p-sample-android:assembleDebug",
                     *[task for task in HOST.DESKTOP_TASKS if task != ":p2p-sample-desktop:installDist"],
                     *[":" + module + ":dokkaGeneratePublicationHtml" for module in HOST.MODULES],
                     "cyclonedxBom", "--continue"]
        for batch_ok, consumer_ok in ((True, True), (False, True), (True, False), (False, False)):
            with self.subTest(batch_ok=batch_ok, consumer_ok=consumer_ok):
                events = []
                def invoke(label, arguments, **kwargs):
                    events.append(label)
                    return {"mac-artifact-build": batch_ok, "isolated-consumers": consumer_ok}.get(label, True)
                def observe(name):
                    return lambda *args, **kwargs: events.append(name)
                with contextlib.ExitStack() as stack:
                    operations = {name: stack.enter_context(mock.patch.object(host, name, side_effect=observe(name)))
                                  for name in ("check", "install_xcodegen", "mac_policies", "clean_outputs",
                                               "retain_publication", "retain_consumer_framework", "apple")}
                    invoked = stack.enter_context(mock.patch.object(host, "invoke", side_effect=invoke))
                    host.mac()
                expected_calls = [
                    mock.call("mac-platform-full", [sys.executable, "scripts/run-platform-tests.py", "full"],
                              kind="command", timeout=7200),
                    mock.call("mac-artifact-build", artifacts),
                ]
                if batch_ok:
                    expected_calls.append(mock.call("sbom-inspect", ["bash", "scripts/check-sbom.sh",
                        "build/reports/cyclonedx/bom.json", "build/reports/cyclonedx/bom.xml"], kind="command"))
                expected_calls.append(mock.call("isolated-consumers", ["bash", "scripts/check-published-consumers.sh"],
                    kind="command", timeout=7200, extra_env={"P2PKIT_CONSUMER_WORK_DIR": str(consumer),
                                                            "P2PKIT_CONSUMER_AUDIT_METADATA": "1"}))
                if consumer_ok:
                    expected_calls.append(mock.call("consumer-publication-inspect",
                        ["bash", "scripts/check-publish-artifacts.sh", str(repository)], kind="command"))
                expected_calls.append(mock.call("swift-jvm-cli-prepare", [":p2p-sample-desktop:installDist"]))
                self.assertEqual(expected_calls, invoked.call_args_list)
                self.assertEqual(["check", "install_xcodegen", "mac_policies", "mac-platform-full", "clean_outputs",
                                  "mac-artifact-build", *(["sbom-inspect"] if batch_ok else []), "clean_outputs",
                                  "isolated-consumers", *(["consumer-publication-inspect"] if consumer_ok else []),
                                  "retain_publication", "retain_consumer_framework", "clean_outputs",
                                  "swift-jvm-cli-prepare", "apple"], events)
                operations["check"].assert_called_once_with("apple-tcp-options-sdk", host.inspect_tcp_options_headers)
                operations["retain_publication"].assert_called_once_with(repository, "consumer-publication")
                operations["retain_consumer_framework"].assert_called_once_with(consumer)
                self.assertFalse((host.state / "work/publication").exists(), "Do not create a redundant publication")
        self.assertEqual([], self.calls, "Orchestration fixture must not invoke a product subprocess")

    def test_apple_followup_selects_failed_leaves_and_remaining_native_dependents_without_full_rebuild(self):
        host = HOST.Host("macos-arm64", self.state / "apple-followup-order", scope="apple-followup")
        consumer = host.state / "work/consumer"
        repository = consumer / "repository"
        repository.mkdir(parents=True)
        policies = [
            (15, "scripts/tests/run-platform-tests-test.py"),
        ]
        for product_ok in (True, False):
            with self.subTest(product_ok=product_ok):
                events = []
                def invoke(label, arguments, **kwargs):
                    events.append(label)
                    return product_ok
                def observe(name):
                    return lambda *args, **kwargs: events.append(name)
                with contextlib.ExitStack() as stack:
                    operations = {name: stack.enter_context(mock.patch.object(host, name, side_effect=observe(name)))
                                  for name in ("check", "install_xcodegen", "clean_outputs", "retain_publication",
                                               "retain_consumer_framework", "apple")}
                    invoked = stack.enter_context(mock.patch.object(host, "invoke", side_effect=invoke))
                    host.mac()
                expected_calls, policy_events = [], []
                for number, path in policies:
                    label = "policy-" + str(number) + "-" + Path(path).stem
                    tool = sys.executable if path.endswith(".py") else "bash"
                    env = None if number in (3, 13) else {key: None for key in HOST.ADAPTER_OPT_INS}
                    expected_calls.append(mock.call(label, [tool, path,
                        "OwnedProcessGroupTest.test_term_resistant_worker_is_killed_after_leader_exits_on_term",
                        "OwnedProcessGroupTest.test_surviving_group_is_drained_even_when_leader_already_exited",
                    ], kind="command", extra_env=env))
                    policy_events.extend((label, "clean_outputs"))
                expected_calls.extend([
                    mock.call("mac-platform-ios-arm64", [sys.executable, "scripts/run-platform-tests.py", "ios-arm64"],
                              kind="command", timeout=7200),
                    mock.call("isolated-consumers", ["bash", "scripts/check-published-consumers.sh"],
                              kind="command", timeout=7200,
                              extra_env={"P2PKIT_CONSUMER_WORK_DIR": str(consumer),
                                         "P2PKIT_CONSUMER_AUDIT_METADATA": "1"}),
                ])
                if product_ok:
                    expected_calls.append(mock.call("consumer-publication-inspect",
                        ["bash", "scripts/check-publish-artifacts.sh", str(repository)], kind="command"))
                expected_calls.append(mock.call("swift-jvm-cli-prepare", [":p2p-sample-desktop:installDist"]))
                self.assertEqual(expected_calls, invoked.call_args_list)
                self.assertEqual(["install_xcodegen", *policy_events, "mac-platform-ios-arm64", "clean_outputs",
                                  "isolated-consumers", *(["consumer-publication-inspect"] if product_ok else []),
                                  "retain_publication", "retain_consumer_framework", "clean_outputs",
                                  "swift-jvm-cli-prepare", "apple"], events)
                operations["check"].assert_not_called()
                operations["retain_publication"].assert_called_once_with(repository, "consumer-publication")
                operations["retain_consumer_framework"].assert_called_once_with(consumer)
                operations["apple"].assert_called_once_with()
                self.assertFalse((host.state / "work/publication").exists())
        self.assertEqual([], self.calls, "Routing fixture must not invoke a product subprocess")

    def test_swift_jvm_peer_requires_successful_cli_receipt_and_serial_ui_preparation(self):
        ui_dir = self.state / "work/swift-ui"
        udid = "11111111-1111-1111-1111-111111111111"
        labels = ["swift-jvm-ui-prepare", "swift-jvm-transfer"]
        with self.assertRaisesRegex(ValueError, "CLI preparation receipt is missing"):
            self.host.swift_jvm_transfer(ui_dir, udid)
        for failure in ("cli", *labels):
            with self.subTest(failure=failure):
                self.host.receipts["swift-jvm-cli-prepare"] = {"finalExitCode": 1 if failure == "cli" else 0}
                def invoke(label, arguments, **kwargs):
                    return label != failure
                with mock.patch.object(self.host, "invoke", side_effect=invoke) as invoked:
                    self.host.swift_jvm_transfer(ui_dir, udid)
                calls = invoked.call_args_list
                expected = [] if failure == "cli" else labels[:labels.index(failure) + 1]
                self.assertEqual(expected, [call.args[0] for call in calls])
                for call, action in zip(calls, ("prepare-jvm-transfer", "run-jvm-transfer")):
                    self.assertEqual(["bash", "scripts/run-ios-ui-tests.sh", action], call.args[1])
                    self.assertEqual("command", call.kwargs["kind"])
                    self.assertEqual({"IOS_RUN_DIR": str(ui_dir), "KEEP_IOS_RUN_ARTIFACTS": "1", "SIM_UDID": udid},
                                     call.kwargs["extra_env"])
        self.assertEqual([], self.calls, "No actual product subprocess belongs in this orchestration fixture")

    def test_consumer_framework_inspection_is_bound_and_missing_binary_is_not_a_pass(self):
        self.host.receipts["isolated-consumers"] = {"id": "b" * 32}
        consumer = self.state / "work/consumer"
        self.host.retain_consumer_framework(consumer)
        binding_file = self.host.evidence / "consumer-framework-binding.json"
        absent = json.loads(binding_file.read_text())
        self.assertEqual("NOT_EXECUTED", absent["result"])
        self.assertEqual("b" * 32, absent["sourceInvocationId"])
        binding_file.unlink()  # Explicitly replace only this test's synthetic absent case.
        binary = consumer / "consumer/kmpConsumer/build/bin/iosSimulatorArm64/debugFramework/P2pKitConsumer.framework/P2pKitConsumer"
        binary.parent.mkdir(parents=True)
        binary.write_bytes(b"synthetic Mach-O fixture, not a built product")
        calls = []
        def inspect(label, arguments):
            calls.append((label, arguments))
            output = self.host.evidence / (label + ".stdout.log")
            output.write_bytes(b"synthetic read-only native tool output")
            return output
        with mock.patch.object(self.host, "inspect_tool", side_effect=inspect):
            self.host.retain_consumer_framework(consumer)
        binding = json.loads(binding_file.read_text())
        self.assertEqual("INSPECTED", binding["result"])
        self.assertEqual(hashlib.sha256(binary.read_bytes()).hexdigest(), binding["sha256"])
        self.assertEqual(self.host.admission, binding["source"])
        self.assertEqual(["vtool", "lipo"], [row[1][1] for row in calls])
        self.assertEqual({"vtool", "lipo"}, set(binding["nativeInspections"]))
        self.assertTrue(all(row[1][-1] == str(binary) for row in calls))

    def test_publication_manifest_preserves_partial_failure_metadata_and_all_artifact_hashes(self):
        publication = self.state / "work/partial-publication"
        publication.mkdir()
        files = {"module.pom": b"synthetic partial POM\n", "module.module": b"synthetic module metadata\n",
                 "maven-metadata-local.xml": b"synthetic Maven metadata\n", "module.jar": b"synthetic binary\n"}
        for name, raw in files.items():
            (publication / name).write_bytes(raw)
        self.host.retain_publication(publication, "partial-publication")
        manifest = json.loads((self.host.evidence / "partial-publication-manifest.json").read_text())
        self.assertEqual(set(files), {row["path"] for row in manifest["artifacts"]})
        self.assertEqual({"module.pom", "module.module", "maven-metadata-local.xml"},
                         {row["path"] for row in manifest["retainedMetadata"]})
        for row in manifest["artifacts"]:
            self.assertEqual(hashlib.sha256(files[row["path"]]).hexdigest(), row["sha256"])
        self.assertTrue((publication / "module.jar").exists(), "retention must precede any explicit cleanup")
        self.assertFalse((self.host.evidence / "partial-publication-metadata/module.jar").exists())

    def test_work_cleanup_never_removes_foreign_state_work_root_or_link_targets(self):
        work = self.state / "work"
        caller = self.work / "caller-owned"
        caller.mkdir()
        sentinel = caller / "keep.txt"
        sentinel.write_text("keep caller data", encoding="utf-8")
        for path in (work, self.state, caller):
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.host.remove_work(path)
        child = work / "disposable"
        child.mkdir()
        (child / "borrowed").symlink_to(caller, target_is_directory=True)
        with mock.patch.object(self.host, "work_identity", (0, 0)), self.assertRaises(ValueError):
            self.host.remove_work(child)
        self.host.remove_work(child)
        self.assertFalse(child.exists())
        self.assertEqual("keep caller data", sentinel.read_text())

    def test_output_cleanup_requests_exact_disposable_roots_and_never_source_named_build(self):
        disposable = [self.repo / "build", self.repo / "buildSrc/build"]
        for path in disposable:
            path.mkdir(parents=True)
        source = self.repo / "buildSrc/src/main/java/dev/p2pkit/build"
        source.mkdir(parents=True)
        sentinel = source / "Preserve.java"
        sentinel.write_text("synthetic source sentinel", encoding="utf-8")
        with mock.patch.object(HOST.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as cleanup:
            self.host.clean_outputs()
        command = cleanup.call_args.args[0]
        self.assertEqual([sys.executable, str(self.host.runner), "cleanup", "--state", str(self.state)], command[:5])
        self.assertEqual(["--path", str(disposable[0]), "--path", str(disposable[1])], command[5:])
        with mock.patch.object(HOST.subprocess, "run", return_value=subprocess.CompletedProcess([], 125)):
            with self.assertRaises(HOST.InfrastructureFailure):
                self.host.clean_outputs()
        self.assertFalse(self.host.safe)
        self.assertEqual("synthetic source sentinel", sentinel.read_text())
        self.assertTrue(all(path.is_dir() for path in disposable))

    def test_failed_actual_assessment_is_a_failed_inspection_not_a_fake_pass(self):
        report = windows_report()
        report["tests"][":p2p-core:jvmTest"]["passed"] = 0
        result = self.host.check("windows-execution", lambda: HOST.assess_windows(report, POLICY, TOKEN))
        self.assertFalse(result)
        row = self.host.rows[-1]
        self.assertEqual({"component": "windows-execution", "result": "FAIL", "inspectionOnly": True}, row)
        evidence = json.loads((self.host.evidence / "windows-execution.json").read_text())
        self.assertEqual("FAIL", evidence["result"])
        self.assertIn("Fresh nonzero Windows test execution", evidence["error"])
        self.assertEqual([], self.calls)

    def seed_apple_sidecars(self):
        release = self.repo / "library/p2p-transport-lan/build/XCFrameworks/release"
        release.mkdir(parents=True)
        for name, value in (("BUILD_COMMIT.txt", self.source["commit"]), ("BUILD_SOURCE_STATE.txt", "clean"),
                            ("BUILD_INPUTS_SHA256.txt", "a" * 64), ("BUILD_ARTIFACTS_SHA256.txt", "b" * 64)):
            (release / name).write_text(value + "\n", encoding="utf-8")

    def test_xcframework_native_inspections_headers_and_four_sidecars_precede_later_builds(self):
        self.seed_apple_sidecars()
        release = self.repo / "library/p2p-transport-lan/build/XCFrameworks/release"
        headers = {}
        for identifier in ("ios-arm64", "ios-arm64_x86_64-simulator"):
            binary = release / "P2pKitShared.xcframework" / identifier / "P2pKitShared.framework/P2pKitShared"
            binary.parent.mkdir(parents=True)
            binary.write_bytes(("synthetic " + identifier).encode())
            header = binary.parent / "Headers/P2pKitShared.h"
            header.parent.mkdir()
            headers[identifier] = b"/* Synthetic header, not generated ABI. */\r\n" + identifier.encode() + b"\r\n"
            header.write_bytes(headers[identifier])
        events = []
        original_invoke = self.host.invoke
        original_check = self.host.check
        def invoke(label, *args, **kwargs):
            events.append(label)
            if label == "xcode-project":
                return False  # No later native product boundary is needed for this fixture.
            return original_invoke(label, *args, **kwargs)
        def check(label, callback):
            events.append(label)
            return original_check(label, callback)
        def inspect(label, arguments):
            events.append(label)
            path = self.host.evidence / (label + ".stdout.log")
            path.write_text("synthetic inspection output", encoding="utf-8")
            self.assertEqual("xcrun", arguments[0])
            self.assertTrue(Path(arguments[-1]).is_file())
            return path
        with mock.patch.object(self.host, "invoke", side_effect=invoke), \
                mock.patch.object(self.host, "check", side_effect=check), \
                mock.patch.object(self.host, "inspect_tool", side_effect=inspect):
            self.host.apple()
        self.assertEqual(["xcframework-build", "xcframework-inspect", "xcframework-device-header",
                          "xcframework-device-vtool", "xcframework-device-lipo", "xcframework-simulator-header",
                          "xcframework-simulator-vtool", "xcframework-simulator-lipo", "xcode-project"], events)
        sidecars = json.loads((self.host.evidence / "xcframework-sidecars.json").read_text())
        self.assertEqual(4, len(sidecars["files"]))
        for row in sidecars["files"]:
            self.assertEqual("RETAINED", row["result"])
            self.assertEqual((release / row["path"]).read_bytes(), (self.host.evidence / row["path"]).read_bytes())
        for name, identifier in (("device", "ios-arm64"), ("simulator", "ios-arm64_x86_64-simulator")):
            record = json.loads((self.host.evidence / ("xcframework-" + name + "-binding.json")).read_text())
            self.assertEqual(self.host.receipts["xcframework-build"]["id"], record["sourceInvocationId"])
            self.assertEqual(hashlib.sha256(Path(record["path"]).read_bytes()).hexdigest(), record["sha256"])
            self.assertEqual({"vtool", "lipo"}, set(record["nativeInspections"]))
            inspection = json.loads((self.host.evidence / ("xcframework-" + name + "-header.json")).read_text())
            self.assertEqual("PASS", inspection["result"])
            binding = inspection["details"]
            self.assertEqual(self.host.admission, binding["source"])
            self.assertEqual(self.host.receipts["xcframework-build"]["id"], binding["sourceInvocationId"])
            self.assertEqual(headers[identifier], Path(binding["headerPath"]).read_bytes())
            self.assertEqual(headers[identifier], (self.host.evidence / binding["retainedPath"]).read_bytes())
            self.assertEqual(hashlib.sha256(headers[identifier]).hexdigest(), binding["sha256"])
            self.assertEqual(len(headers[identifier]), binding["bytes"])
            self.assertIn("not Swift bridge execution", binding["limits"])

    def test_generated_headers_reject_missing_nonregular_linked_empty_and_oversized_inputs(self):
        for invalid in ("missing", "directory", "linked-leaf", "linked-parent", "empty", "oversized"):
            with self.subTest(invalid=invalid):
                label = "fixture-header-" + invalid
                parent = self.repo / label
                parent.mkdir()
                header = parent / "Headers/P2pKitShared.h"
                foreign = self.work / (label + "-foreign")
                foreign.mkdir()
                sentinel = foreign / "P2pKitShared.h"
                sentinel.write_bytes(b"outside synthetic header must stay untouched\n")
                if invalid == "linked-parent":
                    header.parent.symlink_to(foreign, target_is_directory=True)
                else:
                    header.parent.mkdir()
                    if invalid == "directory":
                        header.mkdir()
                    elif invalid == "linked-leaf":
                        header.symlink_to(sentinel)
                    elif invalid in ("empty", "oversized"):
                        header.write_bytes(b"x" * (1024 ** 2 + 1) if invalid == "oversized" else b"")
                self.assertFalse(self.host.check(label, lambda: self.host.retain_xcframework_header(label, header, TOKEN)))
                result = json.loads((self.host.evidence / (label + ".json")).read_text())
                self.assertEqual("FAIL", result["result"])
                self.assertNotIn("details", result)
                self.assertFalse((self.host.evidence / (label + ".h.log")).exists())
                self.assertEqual(b"outside synthetic header must stay untouched\n", sentinel.read_bytes())
        self.assertEqual([], self.calls, "Generated-header inspection must not run a product or native tool")

    def test_generated_header_exact_size_limit_is_retained_without_running_a_tool(self):
        header = self.repo / "SyntheticP2pKitShared.h"
        raw = b"x" * (1024 ** 2)
        header.write_bytes(raw)
        binding = self.host.retain_xcframework_header("fixture-header-limit", header, TOKEN)
        self.assertEqual(raw, (self.host.evidence / binding["retainedPath"]).read_bytes())
        self.assertEqual(raw, header.read_bytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(), binding["sha256"])
        self.assertEqual(len(raw), binding["bytes"])
        self.assertEqual(TOKEN, binding["sourceInvocationId"])
        self.assertEqual([], self.calls)

    def test_generated_header_is_write_once_and_source_mutation_preserves_raw_failure_evidence(self):
        for failure in ("existing-copy", "source-mutation"):
            with self.subTest(failure=failure):
                label = "fixture-header-" + failure
                header = self.repo / (label + ".h")
                raw = b"/* Synthetic original header, not generated ABI. */\r\n"
                header.write_bytes(raw)
                retained = self.host.evidence / (label + ".h.log")
                prior = b"preserve previous raw evidence\n"
                if failure == "existing-copy":
                    retained.write_bytes(prior)
                digest = HOST.digest
                def mutate(path):
                    value = digest(path)
                    if path == retained and failure == "source-mutation":
                        header.write_bytes(b"changed synthetic source\n")
                    return value
                with mock.patch.object(HOST, "digest", side_effect=mutate):
                    self.assertFalse(self.host.check(label, lambda: self.host.retain_xcframework_header(
                        label, header, TOKEN)))
                result = json.loads((self.host.evidence / (label + ".json")).read_text())
                self.assertEqual("FAIL", result["result"])
                self.assertNotIn("details", result)
                self.assertEqual(prior if failure == "existing-copy" else raw, retained.read_bytes())
                if failure == "existing-copy":
                    self.assertEqual(raw, header.read_bytes())
                else:
                    self.assertIn("changed during retention", result["error"])
        self.assertEqual([], self.calls)

    def test_zero_xcode_exit_without_real_build_marker_does_not_start_swift_tests(self):
        self.seed_apple_sidecars()
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.host.apple()
        labels = [row["component"] for row in self.host.rows]
        self.assertIn("swift-warnings-build", labels)
        self.assertNotIn("swift-unit-ui", labels)
        self.assertEqual("FAIL", self.host.rows[-1]["result"])
        self.assertEqual("swift-build-marker", self.host.rows[-1]["component"])
        self.assertEqual([], self.cancel_calls)

    def test_retained_exact_build_marker_allows_only_the_next_real_simulator_inspection(self):
        self.seed_apple_sidecars()

        def marker(record, receipt, evidence, phase):
            if phase == "after-write" and record["purpose"] == "swift-warnings-build":
                (evidence / "product.stdout.log").write_text("** BUILD SUCCEEDED **\n", encoding="utf-8")

        self.next_mutation = marker

        class ReachedInspection(Exception):
            pass

        with mock.patch.object(self.host, "inspect_tool", side_effect=ReachedInspection) as inspection, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(ReachedInspection):
                self.host.apple()
        inspection.assert_called_once_with("simulators-before",
                                           ["xcrun", "simctl", "list", "--json", "devices", "available"])
        self.assertEqual("swift-build-marker", self.host.rows[-1]["component"])
        self.assertEqual("PASS", self.host.rows[-1]["result"])
        self.assertNotIn("swift-unit-ui", [row["component"] for row in self.host.rows])

    def finalize(self, error=None):
        with mock.patch.object(HOST, "source_snapshot", return_value=copy.deepcopy(self.source)), \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return self.host.finalize(error)

    def summary(self):
        return json.loads((self.host.evidence / "host-summary.json").read_text(encoding="utf-8"))

    def test_finalizer_seals_every_retained_file_before_emitting_safe_continuation(self):
        self.assertTrue(self.invoke())
        owned_log = self.state / "work/synthetic-failure.log"
        owned_log.write_text("preserve this historical fixture diagnostic\n", encoding="utf-8")
        self.assertEqual(0, self.finalize())
        self.assertFalse((self.state / "work").exists())
        self.assertEqual("preserve this historical fixture diagnostic\n",
                         (self.host.evidence / "work-metadata/synthetic-failure.log").read_text())
        summary = self.summary()
        self.assertEqual("PASS", summary["result"])
        self.assertTrue(summary["safeToContinue"])
        self.assertEqual(self.source, summary["sourceAfter"])
        self.assertEqual("NOT_EXECUTED_COMPONENT_REPLAY", summary["releaseGateMonolith"])
        self.assertIn("NOT_VALIDATED", summary["externalAcceptance"])
        self.assertEqual("safe_to_continue=true\n", self.output.read_text())
        manifest = self.host.evidence / "manifest.sha256"
        hashes = dict(line.split("  ", 1)[::-1] for line in manifest.read_text().splitlines())
        files = {path.relative_to(self.host.evidence).as_posix(): path for path in self.host.evidence.rglob("*")
                 if path.is_file() and path != manifest}
        self.assertEqual(set(files), set(hashes))
        for name, path in files.items():
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), hashes[name])

    def test_finalized_product_failure_stays_failed_while_later_host_admission_can_be_safe(self):
        self.next_status = 7
        self.assertFalse(self.invoke())
        self.assertEqual(1, self.finalize())
        summary = self.summary()
        self.assertEqual("FAIL", summary["result"])
        self.assertTrue(summary["safeToContinue"])
        self.assertEqual("FAIL", summary["components"][0]["result"])
        self.assertEqual(7, summary["components"][0]["exitCode"])
        self.assertEqual("safe_to_continue=true\n", self.output.read_text())

    def test_finalizer_without_owned_state_does_not_read_write_copy_or_delete_prior_attempt(self):
        foreign = self.work / "previous owned-by-someone-else attempt"
        foreign.mkdir()
        sentinel = foreign / "context.json"
        sentinel.write_text("not this driver's context", encoding="utf-8")
        host = HOST.Host("windows-x64", foreign)
        host.safe = True  # Even an optimistic caller cannot manufacture state ownership.
        with mock.patch.object(host, "assert_owned_state", side_effect=AssertionError("must not inspect foreign state")), \
                mock.patch.object(host, "write", side_effect=AssertionError("must not write foreign state")), \
                mock.patch.object(host, "clean_outputs", side_effect=AssertionError("must not clean foreign state")):
            self.assertEqual(1, host.finalize("source admission was rejected"))
        self.assertFalse(host.safe)
        self.assertEqual("not this driver's context", sentinel.read_text())
        self.assertEqual(["context.json"], [path.name for path in foreign.iterdir()])
        self.assertEqual("safe_to_continue=false\n", self.output.read_text())

    def test_finalizer_retains_uncopied_raw_xcresults_even_after_product_or_parser_failure(self):
        self.assertTrue(self.invoke())
        bundle = self.state / "work/swift-ui/DerivedData/Logs/Test/FailedFixture.xcresult"
        bundle.mkdir(parents=True)
        raw = bundle / "opaque-result-data"
        raw.write_bytes(b"synthetic failed xcresult bytes\n")
        self.assertEqual(1, self.finalize("synthetic XCTest/parser failure"))
        retained = self.host.evidence / "swift-xcresult/FailedFixture.xcresult/opaque-result-data"
        self.assertEqual(b"synthetic failed xcresult bytes\n", retained.read_bytes())
        self.assertFalse((self.state / "work").exists())
        self.assertEqual("FAIL", self.summary()["result"])
        self.assertTrue(self.summary()["safeToContinue"], "product failure and ownership failure are distinct")

    def test_source_change_after_leaf_forbids_deletion_and_continuation(self):
        self.assertTrue(self.invoke())
        sentinel = self.state / "work/preserve-failure.txt"
        sentinel.write_text("preserve until source/ownership is reconciled", encoding="utf-8")
        changed = dict(self.source, status=" M tracked.txt\n")
        with mock.patch.object(HOST, "source_snapshot", return_value=changed), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(1, self.host.finalize(None))
        self.assertFalse(self.host.safe)
        self.assertFalse(self.summary()["safeToContinue"])
        self.assertEqual("preserve until source/ownership is reconciled", sentinel.read_text())
        self.assertEqual("safe_to_continue=false\n", self.output.read_text())

    def test_cleanup_failure_preserves_work_and_blocks_following_host(self):
        self.assertTrue(self.invoke())
        sentinel = self.state / "work/preserve.txt"
        sentinel.write_text("retain incomplete cleanup", encoding="utf-8")
        with mock.patch.object(self.host, "clean_outputs", side_effect=HOST.InfrastructureFailure("synthetic cleanup failure")):
            self.assertEqual(1, self.finalize())
        self.assertFalse(self.host.safe)
        self.assertEqual("retain incomplete cleanup", sentinel.read_text())
        self.assertIn("synthetic cleanup failure", self.summary()["error"])
        self.assertEqual("safe_to_continue=false\n", self.output.read_text())

    def test_postinvoke_lost_or_modified_evidence_and_unfinished_nested_leaf_cannot_be_sealed_safe(self):
        self.assertTrue(self.invoke())
        original = self.host.receipts["fixture-leaf"]
        directory = Path(original["evidenceDirectory"])
        stdout = directory / "product.stdout.log"
        baseline = stdout.read_bytes()
        for mode in ("missing-log", "modified-log", "deleted-leaf", "unfinished-nested"):
            with self.subTest(mode=mode):
                nested = None
                renamed = None
                if mode == "missing-log":
                    stdout.unlink()
                elif mode == "modified-log":
                    stdout.write_bytes(b"later changed output, not original evidence\n")
                elif mode == "deleted-leaf":
                    renamed = self.state / "temporarily preserved original evidence"
                    directory.rename(renamed)
                else:
                    nested = self.host.evidence / ("e" * 32)
                    nested.mkdir()
                    (nested / "start.json").write_text('{"schema":1}', encoding="utf-8")
                with self.assertRaises((ValueError, OSError, KeyError)):
                    self.host.validate_completed_leaves()
                if renamed:
                    renamed.rename(directory)
                if nested:
                    shutil.rmtree(nested)
                stdout.write_bytes(baseline)
        # A full finalizer failure must publish false, not merely expose a helper exception.
        stdout.unlink()
        self.assertEqual(1, self.finalize())
        self.assertFalse(self.host.safe)
        self.assertFalse(self.summary()["safeToContinue"])
        self.assertTrue((self.state / "work").exists())
        self.assertEqual("safe_to_continue=false\n", self.output.read_text())

    def test_manifest_seal_failure_never_publishes_true_or_rewrites_earlier_summary(self):
        self.assertTrue(self.invoke())
        original_digest = HOST.digest

        def fail_final_summary_hash(path):
            if Path(path).name == "host-summary.json":
                raise OSError("synthetic manifest write/hash failure")
            return original_digest(path)

        with mock.patch.object(HOST, "digest", side_effect=fail_final_summary_hash):
            self.assertEqual(1, self.finalize())
        self.assertFalse(self.host.safe)
        # Historical optimistic content is not silently rewritten. The failed seal
        # and false workflow output are mandatory before any later host may run.
        self.assertEqual("PASS", self.summary()["result"])
        self.assertEqual("safe_to_continue=false\n", self.output.read_text())

    def test_replaced_state_identity_cannot_be_finalized_or_overwritten(self):
        before = {path.relative_to(self.state).as_posix(): path.read_bytes()
                  for path in self.state.rglob("*") if path.is_file()}
        self.host.state_identity = (0, 0)
        self.assertEqual(1, self.finalize())
        after = {path.relative_to(self.state).as_posix(): path.read_bytes()
                 for path in self.state.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertFalse(self.host.safe)
        self.assertEqual("safe_to_continue=false\n", self.output.read_text())

    def initialize_boundary(self, host, status=0, mutation=None):
        def initialize(command, **kwargs):
            self.assertEqual([sys.executable, str(host.runner), "init"], command[:3])
            options = dict(zip(command[3::2], command[4::2]))
            self.assertEqual({"--root": str(self.repo), "--state": str(host.state),
                              "--expected-commit": host.admission["commit"], "--host": host.role}, options)
            host.state.mkdir()
            (host.state / "evidence").mkdir()
            home = host.state / "gradle-home"
            home.mkdir()
            (home / "gradle.properties").write_bytes(b"synthetic bounded-home policy\n")
            context = copy.deepcopy(self.context)
            context["gradleHome"] = str(home)
            if mutation:
                mutation(context)
            (host.state / "context.json").write_text(json.dumps(context), encoding="utf-8")
            return subprocess.CompletedProcess(command, status)
        return initialize

    def test_initialization_claims_only_fresh_context_bound_to_source_host_and_private_home(self):
        state = self.work / "fresh initialized state Ω"
        host = HOST.Host("windows-x64", state)
        host.admission = dict(self.host.admission)
        with mock.patch.object(HOST.subprocess, "run", side_effect=self.initialize_boundary(host)), \
                mock.patch.object(HOST, "source_snapshot", return_value=copy.deepcopy(self.source)):
            host.initialize()
        self.assertTrue(host.owns_state)
        self.assertEqual(host.identity(state), host.state_identity)
        self.assertEqual(host.identity(state / "work"), host.work_identity)
        self.assertEqual(self.source, host.context["source"])
        self.assertEqual(hashlib.sha256((state / "context.json").read_bytes()).hexdigest(), host.context_hash)
        self.assertTrue((state / "evidence/admission.json").is_file())
        self.assertFalse(host.safe, "initialization is not successful native ownership-control execution")

    def test_initialization_rejects_malformed_context_and_preserves_failed_partial_state(self):
        changes = (("schema", True), ("root", str(self.work)), ("host", "macos-x64"),
                   ("expectedCommit", "7" * 40), ("tree", "8" * 40), ("id", "invalid"),
                   ("gradleHome", str(self.work / "unrelated-home")))
        for index, (field, value) in enumerate(changes):
            with self.subTest(field=field):
                host = HOST.Host("windows-x64", self.work / ("bad-context-" + str(index)))
                host.admission = dict(self.host.admission)
                with mock.patch.object(HOST.subprocess, "run", side_effect=self.initialize_boundary(
                        host, mutation=lambda context: context.update({field: value}))), \
                        mock.patch.object(HOST, "source_snapshot", return_value=copy.deepcopy(self.source)):
                    with self.assertRaises(ValueError):
                        host.initialize()
                self.assertFalse(host.owns_state)
                self.assertTrue((host.state / "context.json").is_file())
                self.assertFalse((host.state / "work").exists())
        host = HOST.Host("windows-x64", self.work / "failed partial context")
        host.admission = dict(self.host.admission)
        with mock.patch.object(HOST.subprocess, "run", side_effect=self.initialize_boundary(host, status=125)):
            with self.assertRaises(ValueError):
                host.initialize()
        before = (host.state / "context.json").read_bytes()
        self.assertFalse(host.owns_state)
        self.assertEqual(1, host.finalize("native init failed"))
        self.assertEqual(before, (host.state / "context.json").read_bytes())
        self.assertEqual([], list((host.state / "evidence").iterdir()))

    def test_initialization_never_reuses_an_existing_state(self):
        before = (self.state / "context.json").read_bytes()
        host = HOST.Host("windows-x64", self.state)
        host.admission = dict(self.host.admission)
        with mock.patch.object(HOST.subprocess, "run") as controller:
            with self.assertRaises(ValueError):
                host.initialize()
        controller.assert_not_called()
        self.assertFalse(host.owns_state)
        self.assertEqual(before, (self.state / "context.json").read_bytes())

    def test_run_blocks_product_tasks_when_native_controller_controls_fail_and_keeps_failure_evidence(self):
        # Recreate only this test's disposable setup state through the real
        # initialize path. No real source checkout or user's state is removed.
        shutil.rmtree(self.state)
        self.host = HOST.Host("windows-x64", self.state)
        admission = {"commit": self.source["commit"], "tree": self.source["tree"],
                     "ref": HOST.REF, "role": "windows-x64"}
        self.host.admission = admission
        event = self.work / "event.json"
        event.write_text("{}", encoding="utf-8")
        self.next_status = 7
        with mock.patch.dict(os.environ, {"GITHUB_EVENT_PATH": str(event)}), \
                mock.patch.object(HOST, "admit", return_value=admission), \
                mock.patch.object(HOST.subprocess, "run", side_effect=self.initialize_boundary(self.host)), \
                mock.patch.object(HOST, "source_snapshot", return_value=copy.deepcopy(self.source)), \
                mock.patch.object(self.host, "prerequisites"), \
                mock.patch.object(self.host, "setup_sdk") as sdk, \
                mock.patch.object(self.host, "windows") as products, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(1, self.host.run())
        sdk.assert_not_called()
        products.assert_not_called()
        self.assertEqual(1, len(self.calls))
        command = self.calls[0]["command"]
        self.assertEqual("executor-native-controls", command[command.index("--purpose") + 1])
        arguments = command[command.index("--") + 1:]
        self.assertEqual([sys.executable, "scripts/tests/run-audit-command-test.py", "--expected-host", "windows-x64",
                          "--evidence-dir", str(self.host.evidence / "native-controls")], arguments)
        self.assertFalse(self.host.safe)
        self.assertEqual("FAIL", self.summary()["result"])
        self.assertFalse(self.summary()["safeToContinue"])
        self.assertNotIn("safe_to_continue=true", self.output.read_text())

    def simulator_inspection(self, states):
        values = iter(states)

        def inspect(label, command):
            self.assertEqual(["xcrun", "simctl", "list", "--json", "devices", "available"], command)
            path = self.host.evidence / (label + ".json")
            path.write_text(json.dumps({"devices": {"synthetic-runtime": [
                {"udid": self.host.simulator["udid"], "state": next(values)},
                {"udid": "22222222-2222-2222-2222-222222222222", "state": "Booted"}]}}), encoding="utf-8")
            return path
        return inspect

    def test_only_exact_job_booted_simulator_is_shutdown_and_original_state_is_rechecked(self):
        udid = "11111111-1111-1111-1111-111111111111"
        self.host.simulator = {"udid": udid, "stateBefore": "Shutdown"}
        with mock.patch.object(self.host, "inspect_tool", side_effect=self.simulator_inspection(["Booted", "Shutdown"])) as inspect:
            self.host.shutdown_simulator()
        self.assertEqual(2, inspect.call_count)
        command = self.calls[0]["command"]
        self.assertEqual(["xcrun", "simctl", "shutdown", udid], command[command.index("--") + 1:])
        self.assertEqual("Shutdown", self.host.simulator["stateAfter"])

    def test_preexisting_booted_or_already_restored_simulator_is_never_blindly_stopped(self):
        self.host.simulator = {"udid": "11111111-1111-1111-1111-111111111111", "stateBefore": "Booted"}
        with mock.patch.object(self.host, "inspect_tool") as inspect:
            self.host.shutdown_simulator()
        inspect.assert_not_called()
        self.assertEqual([], self.calls)
        self.host.simulator["stateBefore"] = "Shutdown"
        with mock.patch.object(self.host, "inspect_tool", side_effect=self.simulator_inspection(["Shutdown", "Shutdown"])):
            self.host.shutdown_simulator()
        self.assertEqual([], self.calls)
        self.assertEqual("Shutdown", self.host.simulator["stateAfter"])

    def test_cancellation_probe_is_isolated_and_retired_after_success_failure_or_interruption(self):
        udid = "11111111-1111-1111-1111-111111111111"
        for outcome in (True, False, "interrupted", "retirement-failed", "unowned"):
            with self.subTest(outcome=outcome):
                fixture = HostInvocationTest()
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                host = fixture.host
                host.role, host.scope = "macos-arm64", "apple-followup"
                host.simulator = {"udid": udid, "stateBefore": "Booted" if outcome == "unowned" else "Shutdown"}
                ui_dir = fixture.state / "work/swift-ui"
                bundle = ui_dir / "DerivedData/Logs/Test/swift-cancellation-probe.xcresult"
                events = []
                def invoke(label, arguments, **kwargs):
                    events.append(label)
                    if label.endswith("-shutdown"):
                        self.assertEqual(["xcrun", "simctl", "shutdown", udid], arguments)
                        if label == "swift-cancellation-retire-shutdown":
                            self.assertTrue(host.finalizing, "retirement can use the reserved cleanup interval")
                            return outcome != "retirement-failed"
                        return True
                    self.assertEqual("swift-cancellation-probe-invocation", label)
                    self.assertEqual(["bash", "scripts/run-ios-ui-tests.sh", "run-cancellation-probe"], arguments)
                    self.assertEqual(udid, kwargs["extra_env"]["SIM_UDID"])
                    self.assertEqual(900, kwargs["timeout"])
                    self.assertNotIn("stateAfter", host.simulator, "pre-probe shutdown cannot masquerade as final retirement")
                    bundle.mkdir(parents=True)
                    (bundle / "retained-observation.txt").write_text("synthetic bounded observation, not native evidence")
                    if outcome == "interrupted":
                        host.safe = False  # Mirror an executor ownership/cancellation failure.
                        raise HOST.InfrastructureFailure("synthetic interrupted probe")
                    return outcome is not False
                simulator = fixture.simulator_inspection(["Booted", "Shutdown", "Booted", "Shutdown"])
                def inspect(label, arguments):
                    if label.startswith("swift-cancellation-probe-"):
                        expected = ["xcrun", "xcresulttool", "get", "object", "--legacy", "--format", "json",
                                    "--path", str(bundle)]
                        if label.endswith("tests-0"):
                            expected += ["--id", "synthetic-tests"]
                        self.assertEqual(expected, arguments)
                        path = host.evidence / (label + ".json")
                        path.write_text(json.dumps({"actions": {"_values": [{"actionResult": {
                            "testsRef": {"id": {"_value": "synthetic-tests"}}}}]}}))
                        return path
                    return simulator(label, arguments)
                with mock.patch.object(host, "invoke", side_effect=invoke), \
                        mock.patch.object(host, "inspect_tool", side_effect=inspect):
                    if outcome in ("interrupted", "retirement-failed"):
                        with self.assertRaises((HOST.InfrastructureFailure, ValueError)):
                            host.swift_cancellation_probe(ui_dir, udid)
                    else:
                        host.swift_cancellation_probe(ui_dir, udid)
                if outcome == "unowned":
                    self.assertEqual([], events)
                    self.assertEqual({"component": "swift-cancellation-probe-admission", "result": "FAIL",
                                      "inspectionOnly": True, "investigationOnly": True,
                                      "reason": "Owned initially Shutdown simulator unavailable"}, host.rows[-1])
                    admission = json.loads((host.evidence / "swift-cancellation-probe-admission.json").read_text())
                    self.assertEqual("NOT_EXECUTED", admission["result"])
                    self.assertFalse((host.evidence / "swift-cancellation-probe-result.json").exists())
                    continue
                self.assertEqual(["swift-cancellation-isolate-shutdown", "swift-cancellation-probe-invocation",
                                  "swift-cancellation-retire-shutdown"], events)
                report = json.loads((host.evidence / "swift-cancellation-probe-result.json").read_text())
                self.assertEqual(outcome != "retirement-failed", report["ownedSimulatorShutdownObserved"])
                self.assertEqual("PENDING_NATIVE_EVIDENCE_REVIEW", report["cancellationVerdict"])
                self.assertEqual(False if outcome is False else None if outcome == "interrupted" else True,
                                 report["invocationSucceeded"])
                self.assertTrue((host.evidence / "swift-xcresult" / bundle.name / "retained-observation.txt").is_file())
                self.assertFalse(host.finalizing)
                if outcome in ("interrupted", "retirement-failed"):
                    self.assertFalse(host.safe)

    def test_failed_simulator_shutdown_blocks_final_continuation(self):
        self.host.simulator = {"udid": "11111111-1111-1111-1111-111111111111", "stateBefore": "Shutdown"}
        self.next_status = 7
        with mock.patch.object(self.host, "inspect_tool", side_effect=self.simulator_inspection(["Booted"])):
            self.assertEqual(1, self.finalize())
        self.assertFalse(self.host.safe)
        self.assertEqual("FAIL", self.summary()["result"])
        self.assertFalse(self.summary()["safeToContinue"])
        self.assertIn("simulator shutdown failed", self.summary()["error"])
        self.assertEqual("safe_to_continue=false\n", self.output.read_text())


    def test_strict_tree_scan_counts_directories_as_well_as_files(self):
        source = self.state / "work/entry-bound"
        (source / "first/second/third").mkdir(parents=True)
        with mock.patch.object(HOST, "MAX_SCAN_ENTRIES", 2):
            with self.assertRaisesRegex(ValueError, "traversal exceeds its entry bound"):
                list(HOST.strict_walk(source))
        with mock.patch.object(HOST, "MAX_SCAN_ENTRIES", 3):
            self.assertEqual(4, len(list(HOST.strict_walk(source))))
        self.assertTrue((source / "first/second/third").is_dir())

    def test_required_work_scan_failure_preserves_originals_and_blocks_continuation(self):
        self.assertTrue(self.invoke())
        hidden = self.state / "work/unreadable"
        hidden.mkdir()
        sentinel = hidden / "required.log"
        sentinel.write_bytes(b"required diagnostic must not disappear\n")
        original = os.scandir

        def scan(path):
            if not isinstance(path, int) and Path(path) == hidden:
                raise PermissionError("fixture required work scan failed")
            return original(path)

        with mock.patch.object(os, "scandir", side_effect=scan):
            self.assertEqual(1, self.finalize())
        self.assertFalse(self.host.safe)
        self.assertFalse(self.summary()["safeToContinue"])
        self.assertEqual(b"required diagnostic must not disappear\n", sentinel.read_bytes())
        self.assertIn("fixture required work scan failed", self.summary()["error"])
        self.assertEqual("safe_to_continue=false\n", self.output.read_text())

    def test_final_seal_scan_error_cannot_emit_safe_continuation(self):
        self.assertTrue(self.invoke())
        hidden = self.host.evidence / "unreadable-final-evidence"
        hidden.mkdir()
        sentinel = hidden / "required.log"
        sentinel.write_bytes(b"original retained evidence\n")
        original = os.scandir

        def scan(path):
            if not isinstance(path, int) and Path(path) == hidden:
                raise PermissionError("fixture final seal scan failed")
            return original(path)

        with mock.patch.object(os, "scandir", side_effect=scan):
            self.assertEqual(1, self.finalize())
        self.assertFalse(self.host.safe)
        self.assertEqual(b"original retained evidence\n", sentinel.read_bytes())
        self.assertFalse((self.host.evidence / "manifest.sha256").exists())
        self.assertEqual("safe_to_continue=false\n", self.output.read_text())

    def test_retention_and_publication_scans_reject_unreadable_root_or_descendant(self):
        for operation in ("retention", "publication"):
            for position in ("root", "descendant"):
                with self.subTest(operation=operation, position=position):
                    source = self.state / "work" / (operation + "-" + position)
                    hidden = source / "unreadable"
                    hidden.mkdir(parents=True)
                    sentinel = hidden / "required.xml"
                    sentinel.write_bytes(b"preserve original required evidence\n")
                    denied = source if position == "root" else hidden
                    original = os.scandir

                    def scan(path):
                        if not isinstance(path, int) and Path(path) == denied:
                            raise PermissionError("fixture required evidence scan failed")
                        return original(path)

                    with mock.patch.object(os, "scandir", side_effect=scan):
                        with self.assertRaisesRegex(PermissionError, "fixture required evidence scan failed"):
                            if operation == "retention":
                                self.host.retain_tree(source, self.host.evidence / (operation + "-" + position))
                            else:
                                self.host.retain_publication(source, operation + "-" + position)
                    self.assertEqual(b"preserve original required evidence\n", sentinel.read_bytes())
                    self.assertFalse((self.host.evidence / (operation + "-" + position)).exists())
                    self.assertFalse((self.host.evidence / (operation + "-" + position + "-manifest.json")).exists())


class AppleSdkHeadersTest(unittest.TestCase):
    @contextlib.contextmanager
    def fixture(self):
        work = temporary(self)
        state = work / "state"
        host = HOST.Host("macos-arm64", state)
        host.evidence.mkdir(parents=True)
        host.owns_state = True
        host.state_identity = host.identity(state)
        host.admission = {"commit": "1" * 40, "tree": "2" * 40, "role": host.role, "requestedScope": "full"}
        host.write("prerequisites.json", {"tools": {"xcode": {"stdout": "Xcode 26.5\nBuild version fixture\n"}}})
        developer = work / "Xcode SDK fixture Ω.app/Contents/Developer"
        host.environment["DEVELOPER_DIR"] = str(developer)
        responses, headers, roots, codes, calls = {}, {}, {}, {}, []
        for sdk in ("iphoneos", "iphonesimulator"):
            root = developer / "Platforms" / sdk / "Developer/SDKs" / (sdk + "26.5.sdk")
            framework = root / "System/Library/Frameworks/Network.framework"
            actual_headers = framework / "Versions/A/Headers"
            actual_headers.mkdir(parents=True)
            header = actual_headers / "tcp_options.h"
            header.write_bytes(b"/* Synthetic SDK fixture, not an Apple declaration. */\r\n" + sdk.encode() + b"\r\n")
            (framework / "Headers").symlink_to("Versions/A/Headers", target_is_directory=True)
            alias = root.with_name(sdk + ".sdk")
            alias.symlink_to(root.name, target_is_directory=True)
            roots[sdk], headers[sdk] = root, header
            responses[(sdk, "--show-sdk-path")] = (str(alias) + "\n").encode("utf-8")
            responses[(sdk, "--show-sdk-version")] = b"26.5\n"
            responses[(sdk, "--show-sdk-build-version")] = b"synthetic-build\n"

        def inspect(command, **kwargs):
            self.assertEqual(["xcrun", "--sdk"], command[:2])
            self.assertEqual(4, len(command))
            self.assertEqual(host.environment, kwargs["env"])
            self.assertEqual(120, kwargs["timeout"])
            calls.append(list(command))
            key = tuple(command[2:])
            kwargs["stdout"].write(responses[key])
            kwargs["stderr"].write(b"synthetic inspection stderr\n")
            return subprocess.CompletedProcess(command, codes.get(key, 0))

        with mock.patch.object(HOST.subprocess, "run", side_effect=inspect), \
                mock.patch.object(HOST.subprocess, "Popen", side_effect=AssertionError("No build/test process")):
            yield types.SimpleNamespace(host=host, developer=developer, responses=responses, headers=headers,
                                        roots=roots, codes=codes, calls=calls, work=work)

    def test_exact_selected_ios_headers_and_native_metadata_are_retained_verbatim_and_hash_bound(self):
        with self.fixture() as case:
            original = {sdk: path.read_bytes() for sdk, path in case.headers.items()}
            result = case.host.inspect_tcp_options_headers()
            self.assertEqual(2, len(result["bindings"]))
            self.assertEqual([["xcrun", "--sdk", sdk, flag] for sdk in ("iphoneos", "iphonesimulator")
                              for flag in ("--show-sdk-path", "--show-sdk-version", "--show-sdk-build-version")], case.calls)
            for sdk, record in zip(("iphoneos", "iphonesimulator"), result["bindings"]):
                path = case.host.evidence / record["path"]
                self.assertEqual(HOST.digest(path), record["sha256"])
                binding = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual("INSPECTED", binding["result"])
                self.assertIs(binding["inspectionOnly"], True)
                self.assertEqual(case.host.admission, binding["source"])
                self.assertEqual(str(case.developer), binding["developerDirectory"])
                self.assertEqual(str(case.roots[sdk]), binding["sdkRoot"])
                self.assertEqual(str(case.headers[sdk]), binding["resolvedHeaderPath"])
                self.assertEqual(original[sdk], (case.host.evidence / binding["retainedPath"]).read_bytes())
                self.assertEqual(original[sdk], case.headers[sdk].read_bytes(), "SDK inputs must not change")
                self.assertEqual(hashlib.sha256(original[sdk]).hexdigest(), binding["sha256"])
                self.assertEqual(len(original[sdk]), binding["bytes"])
                for item in [binding["prerequisites"], *binding["metadata"].values()]:
                    self.assertEqual(HOST.digest(case.host.evidence / item["path"]), item["sha256"])

    def test_missing_escaped_oversized_or_malformed_sdk_inputs_never_become_header_evidence(self):
        for invalid in ("sdk-outside", "header-outside", "missing", "oversized", "relative", "multiline", "empty"):
            with self.subTest(invalid=invalid), self.fixture() as case:
                sdk = "iphoneos"
                if invalid == "sdk-outside":
                    outside = case.work / "unselected-sdk"
                    outside.mkdir()
                    case.responses[(sdk, "--show-sdk-path")] = (str(outside) + "\n").encode()
                elif invalid == "header-outside":
                    outside = case.work / "foreign-header.h"
                    outside.write_bytes(b"never copy this unselected header\n")
                    case.headers[sdk].unlink()
                    case.headers[sdk].symlink_to(outside)
                elif invalid == "missing":
                    case.headers[sdk].unlink()
                elif invalid == "oversized":
                    case.headers[sdk].write_bytes(b"x" * (1024 ** 2 + 1))
                else:
                    case.responses[(sdk, "--show-sdk-path")] = {
                        "relative": b"relative-sdk\n", "multiline": b"one\ntwo\n", "empty": b"\n"
                    }[invalid]
                with self.assertRaises((ValueError, FileNotFoundError)):
                    case.host.inspect_tcp_options_headers()
                self.assertFalse(list(case.host.evidence.glob("*-tcp_options.h.log")))
                self.assertFalse(list(case.host.evidence.glob("*-tcp-options-binding.json")))
                self.assertTrue((case.host.evidence / "apple-sdk-iphoneos-path.stdout.log").is_file())

    def test_nonzero_sdk_query_preserves_raw_logs_and_cannot_become_a_header_pass(self):
        with self.fixture() as case:
            case.codes[("iphoneos", "--show-sdk-path")] = 9
            with self.assertRaisesRegex(ValueError, "Native evidence inspection failed"):
                case.host.inspect_tcp_options_headers()
            record = json.loads((case.host.evidence / "apple-sdk-iphoneos-path-inspection.json").read_text())
            self.assertEqual(9, record["exitCode"])
            self.assertEqual(case.responses[("iphoneos", "--show-sdk-path")],
                             (case.host.evidence / "apple-sdk-iphoneos-path.stdout.log").read_bytes())
            self.assertFalse(list(case.host.evidence.glob("*-tcp-options-binding.json")))

    def test_existing_header_copy_is_never_overwritten(self):
        with self.fixture() as case:
            prior = case.host.evidence / "apple-sdk-iphoneos-tcp_options.h.log"
            prior.write_bytes(b"preserve prior evidence\n")
            with self.assertRaises(FileExistsError):
                case.host.inspect_tcp_options_headers()
            self.assertEqual(b"preserve prior evidence\n", prior.read_bytes())
            self.assertFalse(list(case.host.evidence.glob("*-tcp-options-binding.json")))

    def test_header_mutation_after_copy_preserves_observation_but_refuses_a_binding(self):
        with self.fixture() as case:
            retained = case.host.evidence / "apple-sdk-iphoneos-tcp_options.h.log"
            original = case.headers["iphoneos"].read_bytes()
            digest = HOST.digest
            def mutate(path):
                if path == retained:
                    case.headers["iphoneos"].write_bytes(b"changed synthetic SDK input\n")
                return digest(path)
            with mock.patch.object(HOST, "digest", side_effect=mutate):
                with self.assertRaisesRegex(ValueError, "TCP header changed during retention"):
                    case.host.inspect_tcp_options_headers()
            self.assertEqual(original, retained.read_bytes())
            self.assertFalse(list(case.host.evidence.glob("*-tcp-options-binding.json")))

    def test_mac_records_header_inspection_before_existing_component_builds_without_claiming_issue_acceptance(self):
        for query_status in (0, 9):
            with self.subTest(query_status=query_status), self.fixture() as case:
                case.codes[("iphoneos", "--show-sdk-path")] = query_status
                def stop():
                    self.assertTrue((case.host.evidence / "apple-tcp-options-sdk.json").is_file())
                    raise ValueError("fixture stops before existing XcodeGen install")
                with mock.patch.object(case.host, "install_xcodegen", side_effect=stop):
                    with self.assertRaisesRegex(ValueError, "fixture stops before"):
                        case.host.mac()
                self.assertEqual([{"component": "apple-tcp-options-sdk", "result": "FAIL" if query_status else "PASS",
                                   "inspectionOnly": True}], case.host.rows)


class SdkSetupTest(unittest.TestCase):
    """Real SDK admission/invocation with synthetic manager/native process boundaries."""

    @contextlib.contextmanager
    def fixture(self, role="windows-x64", newline="\n"):
        # Each table row needs a fresh write-once evidence/context namespace.
        fixture = HostInvocationTest()
        try:
            fixture.setUp()
            host = fixture.host
            host.role = role
            host.wrapper = fixture.repo / ("gradlew.bat" if role == "windows-x64" else "gradlew")
            host.admission["role"] = role
            fixture.context["host"] = role
            fixture.context_bytes = (json.dumps(fixture.context, indent=2) + "\n").encode("utf-8")
            (fixture.state / "context.json").write_bytes(fixture.context_bytes)
            host.context = copy.deepcopy(fixture.context)
            host.context_hash = hashlib.sha256(fixture.context_bytes).hexdigest()
            sdk = fixture.work / "Android SDK with spaces Ω"
            manager = sdk / "cmdline-tools/latest/bin" / (
                "sdkmanager.bat" if role == "windows-x64" else "sdkmanager")
            manager.parent.mkdir(parents=True)
            manager.write_text("synthetic manager; never execute\n", encoding="utf-8")
            properties = {}
            for name, api in (("android-36", "36"), ("android-37.0", "37.0")):
                # Canonical API spellings from Google's installed platforms;
                # these fixtures do not certify a native install or archive.
                raw = newline.join(("Pkg.Revision=2", "AndroidVersion.ApiLevel=" + api,
                                    "AndroidVersion.IsBaseSdk=true", "")).encode("utf-8")
                path = sdk / "platforms" / name / "source.properties"
                path.parent.mkdir(parents=True)
                path.write_bytes(raw)
                properties[name] = path
            host.environment["ANDROID_HOME"] = str(sdk)
            facade = types.SimpleNamespace(**vars(os))
            facade.name = "nt" if role == "windows-x64" else "posix"
            with mock.patch.object(HOST, "os", facade):
                yield fixture, sdk, manager, properties
        finally:
            fixture.doCleanups()

    def assert_manager_receipt(self, fixture, sdk, manager, status=0):
        command = fixture.calls[-1]["command"]
        self.assertEqual([str(manager), "--sdk_root=" + str(sdk),
                          "platforms;android-36", "platforms;android-37.0"],
                         command[command.index("--") + 1:])
        self.assertEqual("command", command[command.index("--kind") + 1])
        self.assertEqual(str(fixture.host.wrapper), command[command.index("--wrapper") + 1])
        self.assertEqual(fixture.host.environment, fixture.calls[-1]["options"]["env"])
        receipt = fixture.host.receipts["android-platforms"]
        self.assertEqual(status, receipt["productExitCode"])
        self.assertEqual(0, receipt["stopExitCode"])
        self.assertEqual([], receipt["ownedSurvivors"])
        self.assertTrue(receipt["sourceUnchanged"])
        self.assertTrue(fixture.host.rows[-1]["cleanupComplete"])

    def test_required_platform_metadata_is_accepted_and_retained_for_each_role(self):
        for role in HOST.ROLES:
            for newline in ("\n", "\r\n"):
                with self.subTest(role=role, newline=repr(newline)), self.fixture(role, newline) as data:
                    fixture, sdk, manager, properties = data
                    fixture.host.setup_sdk()
                    self.assertEqual(1, len(fixture.calls))
                    self.assert_manager_receipt(fixture, sdk, manager)
                    observed = json.loads((fixture.host.evidence / "android-platforms.json").read_text(encoding="utf-8"))
                    self.assertEqual({name: {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                                             "content": path.read_text(encoding="utf-8")}
                                      for name, path in properties.items()}, observed)

    def test_missing_or_nonabsolute_sdk_and_inapplicable_manager_fail_before_invocation(self):
        for role in HOST.ROLES:
            for problem in ("unset", "relative", "missing", "file", "manager"):
                with self.subTest(role=role, problem=problem), self.fixture(role) as data:
                    fixture, sdk, manager, _ = data
                    if problem == "unset":
                        fixture.host.environment.pop("ANDROID_HOME")
                    elif problem == "relative":
                        fixture.host.environment["ANDROID_HOME"] = "relative-sdk"
                    elif problem == "missing":
                        fixture.host.environment["ANDROID_HOME"] = str(sdk / "absent")
                    elif problem == "file":
                        fixture.host.environment["ANDROID_HOME"] = str(manager)
                    else:
                        other = "sdkmanager" if manager.name == "sdkmanager.bat" else "sdkmanager.bat"
                        manager.rename(manager.with_name(other))
                    with self.assertRaisesRegex(ValueError, "command-line tools" if problem == "manager" else "ANDROID_HOME"):
                        fixture.host.setup_sdk()
                    self.assertEqual([], fixture.calls)
                    self.assertFalse((fixture.host.evidence / "android-platforms.json").exists())

    def test_failed_sdk_manager_blocks_success_even_with_valid_properties(self):
        for role in HOST.ROLES:
            with self.subTest(role=role), self.fixture(role) as data:
                fixture, sdk, manager, _ = data
                fixture.next_status = 7
                with self.assertRaisesRegex(ValueError, "Android platform installation failed"):
                    fixture.host.setup_sdk()
                self.assertEqual(1, len(fixture.calls))
                self.assert_manager_receipt(fixture, sdk, manager, status=7)
                self.assertFalse((fixture.host.evidence / "android-platforms.json").exists())

    def test_missing_platform_properties_fail_after_manager_finishes(self):
        for role in HOST.ROLES:
            for platform in ("android-36", "android-37.0"):
                with self.subTest(role=role, platform=platform), self.fixture(role) as data:
                    fixture, sdk, manager, properties = data
                    properties[platform].unlink()
                    with self.assertRaises(FileNotFoundError):
                        fixture.host.setup_sdk()
                    self.assert_manager_receipt(fixture, sdk, manager)
                    self.assertFalse((fixture.host.evidence / "android-platforms.json").exists())

    def test_api_values_and_keys_are_matched_literally_for_the_required_platform(self):
        invalid = [("android-36", "AndroidVersion.ApiLevel=" + value)
                   for value in ("", "37.0", "36.0", "360", "36suffix")]
        invalid += [("android-37.0", "AndroidVersion.ApiLevel=" + value)
                    for value in ("", "36", "37", "37x0", "370", "37.1", "37.00", "037.0", "37.0suffix")]
        invalid += [(platform, key + "=" + value)
                    for platform, value in (("android-36", "36"), ("android-37.0", "37.0"))
                    for key in ("OtherKey", "AndroidVersionXApiLevel")]
        for role in HOST.ROLES:
            for platform, content in invalid:
                with self.subTest(role=role, platform=platform, content=content), self.fixture(role) as data:
                    fixture, sdk, manager, properties = data
                    properties[platform].write_text(content + "\n", encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "Wrong Android platform metadata: " + re.escape(platform)):
                        fixture.host.setup_sdk()
                    self.assert_manager_receipt(fixture, sdk, manager)
                    self.assertFalse((fixture.host.evidence / "android-platforms.json").exists())

    def run_fixture(self, fixture, sdk, *, manager_status=0, scope="full"):
        # Recreate only this owned temporary context through real initialize/run.
        role = fixture.host.role
        shutil.rmtree(fixture.state)
        fixture.host = HOST.Host(role, fixture.state, scope=scope)
        host = fixture.host
        host.environment["ANDROID_HOME"] = str(sdk)
        admission = {"commit": fixture.source["commit"], "tree": fixture.source["tree"],
                     "ref": HOST.REF, "role": role, "requestedScope": scope}
        host.admission = admission
        event = fixture.work / "event.json"
        event.write_text("{}", encoding="utf-8")

        def controller(command, **kwargs):
            purpose = command[command.index("--purpose") + 1]
            fixture.next_status = manager_status if purpose == "android-platforms" else 0
            if purpose == "intel-platform":
                self.assertTrue((host.evidence / "android-platforms.json").is_file())
            return fixture.controller(command, **kwargs)

        def products():
            self.assertTrue((host.evidence / "android-platforms.json").is_file())
            self.assertEqual(["executor-native-controls", "android-platforms"],
                             [row["component"] for row in host.rows])

        with mock.patch.dict(os.environ, {"GITHUB_EVENT_PATH": str(event)}), \
                mock.patch.object(HOST, "admit", return_value=admission), \
                mock.patch.object(HOST.subprocess, "run", side_effect=fixture.initialize_boundary(host)), \
                mock.patch.object(HOST.subprocess, "Popen", side_effect=controller), \
                mock.patch.object(HOST, "source_snapshot", return_value=copy.deepcopy(fixture.source)), \
                mock.patch.object(host, "prerequisites"), \
                mock.patch.object(host, "windows", side_effect=products) as windows, \
                mock.patch.object(host, "windows_followup", side_effect=products) as followup, \
                mock.patch.object(host, "windows_diagnostics", side_effect=products) as diagnostics, \
                mock.patch.object(host, "mac", side_effect=products) as mac, \
                contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = host.run()
        return result, windows.call_count, mac.call_count, followup.call_count, diagnostics.call_count

    def test_run_routes_all_roles_only_after_sdk_validation(self):
        for role, scope in [*((role, "full") for role in HOST.ROLES),
                             ("windows-x64", "windows-followup"), ("windows-x64", "windows-diagnostics"),
                             ("macos-arm64", "apple-followup")]:
            with self.subTest(role=role, scope=scope), self.fixture(role) as data:
                fixture, sdk, _, _ = data
                result, windows, mac, followup, diagnostics = self.run_fixture(fixture, sdk, scope=scope)
                self.assertEqual(0, result)
                self.assertEqual(int(role == "windows-x64" and scope == "full"), windows)
                self.assertEqual(int(scope == "windows-followup"), followup)
                self.assertEqual(int(scope == "windows-diagnostics"), diagnostics)
                self.assertEqual(int(role == "macos-arm64"), mac)
                expected = ["executor-native-controls", "android-platforms"]
                if role == "macos-x64":
                    expected.append("intel-platform")
                self.assertEqual(expected, [row["component"] for row in fixture.host.rows])
                self.assertEqual("PASS", fixture.summary()["result"])
                self.assertEqual(scope, fixture.summary()["requestedScope"])
                self.assertEqual(scope, fixture.summary()["source"]["requestedScope"])
                self.assertEqual("FULL_COMPONENT_SCOPE" if scope == "full" else
                                 "NOT_ESTABLISHED_BY_FOCUSED_SCOPE", fixture.summary()["hostQualification"])
                self.assertTrue(fixture.summary()["safeToContinue"])

    def test_run_blocks_all_products_and_finalizes_invalid_metadata(self):
        for role, scope in [*((role, "full") for role in HOST.ROLES),
                             ("windows-x64", "windows-followup"), ("windows-x64", "windows-diagnostics"),
                             ("macos-arm64", "apple-followup")]:
            with self.subTest(role=role, scope=scope), self.fixture(role) as data:
                fixture, sdk, _, properties = data
                properties["android-37.0"].write_text("AndroidVersion.ApiLevel=37.1\n", encoding="utf-8")
                result, windows, mac, followup, diagnostics = self.run_fixture(fixture, sdk, scope=scope)
                self.assertEqual((1, 0, 0, 0, 0), (result, windows, mac, followup, diagnostics))
                self.assertEqual(["executor-native-controls", "android-platforms"],
                                 [row["component"] for row in fixture.host.rows])
                self.assertIn("Wrong Android platform metadata: android-37.0", fixture.summary()["error"])
                self.assertEqual("FAIL", fixture.summary()["result"])
                self.assertFalse(fixture.summary()["safeToContinue"])
                self.assertFalse((fixture.host.evidence / "android-platforms.json").exists())
                self.assertNotIn("safe_to_continue=true", fixture.output.read_text(encoding="utf-8"))

    def test_run_blocks_all_products_and_finalizes_failed_sdk_installation(self):
        for role, scope in [*((role, "full") for role in HOST.ROLES),
                             ("windows-x64", "windows-followup"), ("windows-x64", "windows-diagnostics"),
                             ("macos-arm64", "apple-followup")]:
            with self.subTest(role=role, scope=scope), self.fixture(role) as data:
                fixture, sdk, _, _ = data
                result, windows, mac, followup, diagnostics = self.run_fixture(fixture, sdk, manager_status=7, scope=scope)
                self.assertEqual((1, 0, 0, 0, 0), (result, windows, mac, followup, diagnostics))
                self.assertEqual(["executor-native-controls", "android-platforms"],
                                 [row["component"] for row in fixture.host.rows])
                self.assertEqual("FAIL", fixture.host.rows[-1]["result"])
                self.assertTrue(fixture.host.rows[-1]["cleanupComplete"])
                self.assertIn("Android platform installation failed", fixture.summary()["error"])
                self.assertFalse(fixture.summary()["safeToContinue"])
                self.assertFalse((fixture.host.evidence / "android-platforms.json").exists())
                self.assertNotIn("safe_to_continue=true", fixture.output.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
