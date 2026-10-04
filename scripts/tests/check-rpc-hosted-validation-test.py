#!/usr/bin/env python3
"""Offline controls for feature-only hosted generation; no Java/network/Gradle."""

import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("rpc_hosted", ROOT / "scripts/run-rpc-hosted-validation.py")
hosted = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hosted)


class HostedValidationTest(unittest.TestCase):
    def test_complete_writer_is_not_replaced_by_a_partial_graph(self):
        commands = hosted.generator_commands()
        self.assertEqual([row[0] for row in commands], ["apple-abi", "complete-lock-writer"])
        self.assertEqual(commands[1][1], ["resolveAndLockAll", "--write-locks",
                                        "--write-verification-metadata", "sha256"])
        self.assertIn("--no-configure-on-demand", hosted.FLAGS)
        self.assertIn("--rerun-tasks", hosted.FLAGS)
        self.assertEqual(hosted.FLAGS[hosted.FLAGS.index("--dependency-verification") + 1], "strict")
        self.assertNotIn("-x", hosted.FLAGS)
        self.assertTrue(all("publish" not in str(row).lower() for row in commands))

    def test_generated_allowlist_excludes_keys_source_and_binaries(self):
        for path in ("keys.json", "gradle.properties", "library/p2p-rpc/src/Test.kt",
                     "library/p2p-rpc/build/rpc.jar", "AGENTS.md", "CLAUDE.md", "RPC_MODULE_PLAN.md"):
            self.assertNotIn(path, hosted.GENERATED)
        self.assertIn("library/p2p-rpc/gradle.lockfile", hosted.GENERATED)
        self.assertIn("samples/p2p-sample-rpc/gradle.lockfile", hosted.GENERATED)
        self.assertEqual(len(hosted.LOCKS), 14)

    def test_no_offline_execution_can_be_mistaken_for_hosted_authorization(self):
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "false"}):
            with self.assertRaisesRegex(hosted.HostedValidationError, "authorized disposable"):
                hosted.paths()

    def test_unrelated_ref_is_rejected_before_any_build(self):
        with patch.object(hosted.platform, "system", return_value="Darwin"), patch.dict(os.environ, {
            "GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": "p2pKit/P2pKit", "GITHUB_REF": "refs/heads/main",
        }):
            with self.assertRaisesRegex(hosted.HostedValidationError, "feature ref"):
                hosted.paths()

    def test_diagnostics_exclude_fixture_payloads_and_assertion_bodies(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.log"
            path.write_text("e: file:///public/Example.kt:12:7 Unresolved reference 'example'.\n"
                            "> Task :p2p-rpc:compileKotlinIosArm64 FAILED\n"
                            "> Could not resolve org.example:public-library:1.0.\n"
                            "invitation=synthetic-private-value\n"
                            "Expected payload <synthetic-private-value>\n"
                            "> Could not resolve secret: synthetic-private-value\n"
                            "BUILD FAILED in 4s\n")
            output = hosted.safe_diagnostics(path)
            self.assertEqual(len(output), 4)
            self.assertNotIn("synthetic-private-value", "\n".join(output))

    def test_overlong_line_is_not_admitted_by_a_matching_suffix(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.log"
            path.write_text("x" * 8193 + "e: file:///public/Example.kt:12 synthetic-private-value\n"
                            "BUILD FAILED in 4s\n")
            self.assertEqual(hosted.safe_diagnostics(path), ["BUILD FAILED in 4s"])

    def test_test_report_redacts_output_messages_and_stacktraces(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "library/example/build/test-results/iosTest/TEST-example.xml"
            path.parent.mkdir(parents=True)
            path.write_text('<testsuite tests="2" failures="1" errors="0" skipped="0">'
                            '<testcase classname="example.Test" name="failure">'
                            '<failure message="secret">private trace</failure>'
                            '<system-out>private payload</system-out></testcase>'
                            '<testcase name="pass"/><system-err>private stderr</system-err></testsuite>')
            result = hosted.test_summary(root)
            self.assertEqual(result[0]["tests"], 2)
            self.assertEqual(result[0]["failedCases"], [{"classname": "example.Test", "name": "failure",
                                                       "type": "OTHER", "locations": []}])
            self.assertNotIn("private", json.dumps(result))
            self.assertNotIn("secret", json.dumps(result))

    def test_failure_details_allow_only_known_types_and_public_in_range_locations(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "library/example/src/commonTest/kotlin/PublicTest.kt"
            source.parent.mkdir(parents=True)
            source.write_text("package example\nclass PublicTest\n// fixture\n")
            failure = hosted.ET.fromstring(
                '<failure type="java.lang.AssertionError" message="synthetic-secret">'
                'private-path/synthetic-secret/PublicTest.kt:2:4\n'
                'private-path/SecretFile.kt:1\nPublicTest.kt:9999999\n'
                'PublicTest.kt:0\nPublicTest.kt:4\nprivate message</failure>')
            details = hosted.failure_details(failure, hosted.source_locations(root))
            self.assertEqual(details, {"type": "java.lang.AssertionError", "locations": [
                {"source": source.relative_to(root).as_posix(), "line": 2}]})
            failure.attrib["type"] = "synthetic.secret.Exception"
            self.assertEqual(hosted.failure_details(failure, {})["type"], "OTHER")
            self.assertNotIn("secret", json.dumps(details))
            self.assertNotIn("private", json.dumps(details))

    def test_fixture_markers_reject_addresses_paths_dynamic_errors_and_extra_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "library/p2p-transport-lan/build/reports/jmdns-close/run-fixture/control-123.log"
            path.parent.mkdir(parents=True)
            accepted = ["FAIL mode=control", "phase=fixture_rescue_begin mode=control",
                        "startup firstSendFailureClass=java.net.NoRouteToHostException "
                        "firstSendDestinationIpv4Mdns=true",
                        "startup routeFlag=BLACKHOLE present=false",
                        "startup interfaceSnapshot=BEFORE_WAIT selectedKnown=true hostKnown=true socketKnown=true "
                        "selectedHostMatch=true selectedSocketMatch=true hostSocketMatch=true"]
            secret = "synthetic-private-value"
            rejected = ["FAIL mode=" + secret, "phase=" + secret + " mode=control",
                        "startup firstSendFailureClass=" + secret + " firstSendDestinationIpv4Mdns=true",
                        "startup frameRole=send_failure frame=" + secret,
                        "startup routeFlag=" + secret + " present=false", "path=/private/" + secret,
                        "startup address=192.168.1.1", "startup selectedInterface=en0",
                        "Exception in thread \"main\" java.lang.AssertionError: " + secret]
            path.write_text("\n".join([*accepted, *(line + " " + secret for line in accepted), *rejected,
                                       'Exception in thread "main" java.lang.AssertionError: host_not_announced']))
            summary = hosted.fixture_summary(root)
            self.assertEqual(summary, [{"mode": "control", "markers": [*accepted,
                                                                         "assertionCode=host_not_announced"]}])
            for excluded in (secret, "192.168.1.1", "en0", "/private/"):
                self.assertNotIn(excluded, json.dumps(summary))

    def test_diagnostic_mode_never_substitutes_for_full_writer(self):
        commands = hosted.diagnostic_commands()
        self.assertEqual([command[0] for command in commands], ["diagnostic-jmdns", "diagnostic-ios-lan"])
        self.assertEqual(commands[0][1], [":p2p-transport-lan:jvmTest", "--tests",
                                         "dev.p2pkit.transport.lan.JmdnsCloseLifecycleTest"])
        self.assertEqual(commands[1][1], [":p2p-transport-lan:iosSimulatorArm64Test"])
        self.assertNotIn("--write-locks", str(commands))
        self.assertNotIn("resolveAndLockAll", str(commands))
        self.assertNotIn("publish", str(commands).lower())

    def test_native_correction_does_not_retry_unchanged_jmdns_or_write_inputs(self):
        commands = hosted.diagnostic_commands("diagnose-native")
        self.assertEqual(commands, [hosted.diagnostic_commands()[1]])
        self.assertNotIn("jvmTest", str(commands))
        self.assertNotIn("--write-", str(commands))
        with self.assertRaises(hosted.HostedValidationError):
            hosted.diagnostic_commands("unknown")

    def test_workflow_allocates_only_explicit_feature_work_without_shared_secrets(self):
        source = (ROOT / ".github/workflows/rpc-feature-validation.yml").read_text()
        for required in (hosted.REF, "github.event_name == 'workflow_dispatch'", "[rpc-native]",
                         "[rpc-diagnose]", "[rpc-generate]", "cancel-in-progress: false",
                         "persist-credentials: false", "contents: read", "fetch-depth: 1",
                         "git fetch --no-tags --unshallow origin"):
            self.assertIn(required, source)
        for forbidden in ("pull_request_target:", "secrets.", "environment:", "continue-on-error:",
                          "cancel-in-progress: true", "secrets: inherit", "fetch-depth: 0",
                          "+refs/tags/*:refs/tags/*"):
            self.assertNotIn(forbidden, source)

    def test_compiler_checks_are_strict_separate_from_tests_locks_and_publication(self):
        commands = hosted.compilation_commands()
        self.assertEqual(commands[0][1], [f":{name}:dokkaGeneratePublicationHtml" for name in hosted.LIBRARIES])
        self.assertEqual(commands[1][1], [":p2p-sample-rpc:linkDebugFrameworkIosSimulatorArm64",
                                         ":p2p-sample-rpc:linkDebugFrameworkIosArm64",
                                         ":p2p-sample-rpc:linkDebugFrameworkIosX64"])
        for forbidden in ("jvmTest", "iosSimulatorArm64Test", "resolveAndLockAll", "--write-", "publish"):
            self.assertNotIn(forbidden, str(commands))
        with tempfile.TemporaryDirectory() as directory:
            for target, (sdk, triple) in hosted.APPLE_TARGETS.items():
                with patch.object(hosted.subprocess, "check_output", return_value=directory):
                    command = hosted.swift_command(Path(directory), target)
                    self.assertIn("-typecheck", command)
                    self.assertIn("-warnings-as-errors", command)
                    self.assertEqual(command[command.index("-target") + 1], triple)
                    self.assertIn("ios14.0", triple)
                    self.assertEqual(command[2], sdk)

    def test_compilation_requires_nonempty_genuine_outputs_and_preserves_ios_minimum(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in hosted.LIBRARIES:
                path = root / f"library/{name}/build/dokka/html/index.html"
                path.parent.mkdir(parents=True)
                path.write_text("<html>synthetic control</html>")
            self.assertEqual(len(hosted.compilation_receipt(root, "strict-dokka")["htmlIndexes"]), 3)
            for target in hosted.APPLE_TARGETS:
                path = hosted.framework_path(root, target)
                for name in ("P2pKitRpcExample", "Headers/P2pKitRpcExample.h", "Modules/module.modulemap"):
                    output = path / name
                    output.parent.mkdir(parents=True, exist_ok=True)
                    output.write_bytes(b"synthetic offline control, not a framework")
                (path / "Info.plist").write_bytes(hosted.plistlib.dumps({"MinimumOSVersion": "14.0"}))
            result = hosted.compilation_receipt(root, "rpc-frameworks")
            self.assertEqual(len(result["frameworks"]), 3)
            (path / "Info.plist").write_bytes(hosted.plistlib.dumps({"MinimumOSVersion": "15.0"}))
            with self.assertRaisesRegex(hosted.HostedValidationError, "minimum iOS"):
                hosted.compilation_receipt(root, "rpc-frameworks")
            (path / "Info.plist").write_bytes(hosted.plistlib.dumps({"MinimumOSVersion": "14.0"}))
            (path / "P2pKitRpcExample").write_bytes(b"")
            with self.assertRaisesRegex(hosted.HostedValidationError, "compiler output"):
                hosted.compilation_receipt(root, "rpc-frameworks")

    def diagnostic_fixture(self, root, label):
        helper = hosted.platform_runner()
        policy = helper.read_json(ROOT / "gradle/platform-test-policy.json")
        task = hosted.diagnostic_commands()[0 if label == "diagnostic-jmdns" else 1][1][0]
        report = {"schema": 1, "token": "fixture", "dryRun": False, "buildFailed": False,
                  "host": {"os": "Mac OS X", "arch": "aarch64"}, "model": policy["model"], "tests": {}}
        for entry in policy["model"].values():
            for name in entry["tests"]:
                report["tests"][name] = {"outcome": "NOT_REQUESTED", "enabled": True, "inGraph": False,
                                         "passed": 0, "failed": 0, "skipped": 0}
        count = 2 if label == "diagnostic-jmdns" else 1
        report["tests"][task].update(outcome="EXECUTED", inGraph=True, passed=count)
        path = root / ("library/p2p-transport-lan/build/test-results/" + task.rsplit(":", 1)[1]
                       + "/TEST-dev.p2pkit.transport.lan.JmdnsCloseLifecycleTest.xml")
        path.parent.mkdir(parents=True)
        methods = ["realResourceCloseRegressionsExitNaturally"]
        if label == "diagnostic-jmdns":
            methods.append("failedSendsCannotMultiplyTheSdkCleanupBudget")
        path.write_text(f'<testsuite tests="{count}" failures="0" errors="0" skipped="0">' + ''.join(
            '<testcase classname="dev.p2pkit.transport.lan.JmdnsCloseLifecycleTest" '
            f'name="{method}"/>' for method in methods) + '</testsuite>')
        for mode in hosted.FIXTURE_MODES:
            log = root / f"library/p2p-transport-lan/build/reports/jmdns-close/run-fixture/{mode}-123.log"
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text("PASS mode=" + mode + "\n")
        return report, path, task

    def test_diagnostics_require_fresh_matching_task_counts_and_xml(self):
        for label in ("diagnostic-jmdns", "diagnostic-ios-lan"):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                report, path, task = self.diagnostic_fixture(root, label)
                self.assertEqual(hosted.assess_diagnostic(root, label, report, "fixture")["passed"],
                                 2 if label == "diagnostic-jmdns" else 1)
                for key, value in (("token", "stale"), ("dryRun", True), ("buildFailed", True)):
                    with patch.dict(report, {key: value}), self.assertRaises((hosted.HostedValidationError, ValueError)):
                        hosted.assess_diagnostic(root, label, report, "fixture")
                for key, value in (("outcome", "UP-TO-DATE"), ("passed", 0), ("failed", 1), ("enabled", False)):
                    with patch.dict(report["tests"][task], {key: value}):
                        with self.assertRaises((hosted.HostedValidationError, ValueError)):
                            hosted.assess_diagnostic(root, label, report, "fixture")
                path.unlink()
                with self.assertRaisesRegex(hosted.HostedValidationError, "XML is missing"):
                    hosted.assess_diagnostic(root, label, report, "fixture")

    def test_zero_gradle_exit_cannot_hide_deferred_native_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, path, task = self.diagnostic_fixture(root, "diagnostic-ios-lan")
            for xml in ('<testsuite tests="1" failures="1"><testcase><failure/></testcase></testsuite>',
                        '<testsuite tests="1" failures="0"><testcase><failure/></testcase></testsuite>',
                        '<testsuite tests="1" failures="0"/>'):
                path.write_text(xml)
                with self.assertRaises(hosted.HostedValidationError):
                    hosted.assess_diagnostic(root, "diagnostic-ios-lan", report, "fixture")

    def test_jmdns_pass_marker_cannot_hide_failed_or_missing_child(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, path, task = self.diagnostic_fixture(root, "diagnostic-jmdns")
            log = root / "library/p2p-transport-lan/build/reports/jmdns-close/run-fixture/control-123.log"
            log.write_text("PASS mode=control\nphase=fixture_rescue_begin mode=control\n")
            with self.assertRaisesRegex(hosted.HostedValidationError, "natural child"):
                hosted.assess_diagnostic(root, "diagnostic-jmdns", report, "fixture")
            log.unlink()
            with self.assertRaisesRegex(hosted.HostedValidationError, "natural child"):
                hosted.assess_diagnostic(root, "diagnostic-jmdns", report, "fixture")

    def test_jmdns_requires_both_new_budget_children_across_invocation_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            report, _, task = self.diagnostic_fixture(root, "diagnostic-jmdns")
            parent = root / "library/p2p-transport-lan/build/reports/jmdns-close"
            budget = parent / "run-budget-fixture"
            budget.mkdir()
            for mode in ("stop_during_recovery", "failed_goodbyes"):
                (parent / "run-fixture" / (mode + "-123.log")).rename(budget / (mode + "-123.log"))
            self.assertEqual(hosted.assess_diagnostic(root, "diagnostic-jmdns", report, "fixture")["passed"], 2)
            with patch.dict(report["tests"][task], passed=1):
                with self.assertRaisesRegex(hosted.HostedValidationError, "fresh JmDNS fixture"):
                    hosted.assess_diagnostic(root, "diagnostic-jmdns", report, "fixture")
            for mode in ("stop_during_recovery", "failed_goodbyes"):
                path = budget / (mode + "-123.log")
                raw = path.read_text()
                path.write_text(raw + "phase=fixture_rescue_begin mode=" + mode + "\n")
                with self.assertRaisesRegex(hosted.HostedValidationError, "natural child"):
                    hosted.assess_diagnostic(root, "diagnostic-jmdns", report, "fixture")
                path.unlink()
                with self.assertRaisesRegex(hosted.HostedValidationError, "natural child"):
                    hosted.assess_diagnostic(root, "diagnostic-jmdns", report, "fixture")
                path.write_text(raw)

    def test_invalid_counts_and_xml_entities_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "samples/example/build/test-results/test/TEST-example.xml"
            path.parent.mkdir(parents=True)
            for xml in ('<testsuite tests="-1"/>', '<!DOCTYPE x><testsuite tests="1"/>'):
                path.write_text(xml)
                with self.assertRaises(hosted.HostedValidationError):
                    hosted.test_summary(root)

    def test_bounded_reader_rejects_oversized_files_and_symlinks(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "input"
            path.write_bytes(b"12345")
            self.assertEqual(hosted.read_bounded(path, 5), b"12345")
            with self.assertRaises(hosted.HostedValidationError):
                hosted.read_bounded(path, 4)
            link = path.with_name("link")
            link.symlink_to(path)
            with self.assertRaises(hosted.HostedValidationError):
                hosted.read_bounded(link)

    def test_unexpected_source_changes_block_candidate_export(self):
        with patch.object(hosted, "git", return_value=b"library/p2p-rpc/src/Unexpected.kt\n"):
            with self.assertRaisesRegex(hosted.HostedValidationError, "Unexpected source"):
                hosted.collect_candidates(ROOT, False)

    def test_failed_writer_never_exports_acceptable_locks(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(hosted, "git", return_value=b""):
            root = Path(directory)
            for name in (*hosted.LOCKS, *(f"library/{n}/api/{n}.klib.api" for n in hosted.LIBRARIES)):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("synthetic fixture\n")
            self.assertEqual(hosted.collect_candidates(root, False)[0]["status"], "INCOMPLETE_DO_NOT_IMPORT")
            self.assertEqual(hosted.collect_candidates(root, True)[0]["status"], "REVIEW_REQUIRED")
            (root / "library/p2p-rpc/gradle.lockfile").unlink()
            self.assertEqual(hosted.collect_candidates(root, True)[0]["status"], "INCOMPLETE_DO_NOT_IMPORT")

    def terminal_fixture(self, observed, *, returncode=0, size=0, drained=True, running=False,
                         stat_error=None):
        # All process, clock, log and cleanup objects are fake. No child, signal,
        # socket or filesystem operation is performed by this source regression.
        state, log = MagicMock(), MagicMock()
        state.__truediv__.return_value = log
        log.stat.return_value = SimpleNamespace(st_size=size)
        if stat_error is not None:
            log.stat.side_effect = stat_error
        process = Mock(returncode=returncode)
        process.poll.return_value = None if running else returncode
        child = SimpleNamespace(Popen=Mock(return_value=process), STDOUT=hosted.subprocess.STDOUT)
        clock = SimpleNamespace(monotonic=Mock(side_effect=[0.0, observed, observed + 0.001]),
                                sleep=Mock(side_effect=AssertionError("Unexpected fake polling retry")))
        helper = SimpleNamespace(terminate_process=Mock(return_value=drained))
        def execute():
            with patch.object(hosted, "platform_runner", return_value=helper), \
                    patch.object(hosted, "subprocess", child), patch.object(hosted, "time", clock):
                return hosted.execute(state, "terminal-fixture", ["not-executed"], 5)
        return execute, child, helper, process, log, clock

    def assert_terminal_cleanup(self, child, helper, process, log, clock):
        child.Popen.assert_called_once_with(["not-executed"], cwd=hosted.ROOT,
                                           stdout=log.open.return_value.__enter__.return_value,
                                           stderr=hosted.subprocess.STDOUT, start_new_session=True)
        log.open.assert_called_once_with("xb")
        log.open.return_value.__exit__.assert_called_once()
        helper.terminate_process.assert_called_once_with(process)
        clock.sleep.assert_not_called()

    def test_terminal_observation_within_original_bounds_preserves_success_and_failure(self):
        for returncode, size in ((0, 0), (7, 0), (0, hosted.MAX_LOG)):
            with self.subTest(returncode=returncode, size=size):
                execute, *fakes = self.terminal_fixture(4.999, returncode=returncode, size=size)
                row = execute()
                self.assertEqual(row["exitCode"], returncode)
                self.assertTrue(row["processGroupDrained"])
                self.assert_terminal_cleanup(*fakes)

    def test_terminal_success_at_or_after_original_deadline_is_rejected(self):
        for observed in (5.0, 5.001, 25.0):
            with self.subTest(observed=observed):
                execute, *fakes = self.terminal_fixture(observed)
                row = execute()
                self.assertEqual(row["exitCode"], 124)
                self.assertTrue(row["processGroupDrained"])
                self.assert_terminal_cleanup(*fakes)

    def test_terminal_exit_cannot_hide_an_overlong_final_log(self):
        for returncode in (0, 7):
            with self.subTest(returncode=returncode):
                execute, *fakes = self.terminal_fixture(1.0, returncode=returncode, size=hosted.MAX_LOG + 1)
                row = execute()
                self.assertEqual(row["exitCode"], 124)
                self.assertTrue(row["processGroupDrained"])
                self.assert_terminal_cleanup(*fakes)

    def test_terminal_cleanup_uncertainty_cannot_be_reported_as_success(self):
        for observed, size in ((1.0, 0), (5.0, 0), (1.0, hosted.MAX_LOG + 1)):
            with self.subTest(observed=observed, size=size):
                execute, *fakes = self.terminal_fixture(observed, size=size, drained=False)
                row = execute()
                self.assertEqual(row["exitCode"], 125)
                self.assertFalse(row["processGroupDrained"])
                self.assert_terminal_cleanup(*fakes)

    def test_original_running_deadline_and_log_guards_still_drain_the_same_process(self):
        for observed, size in ((5.001, 0), (1.0, hosted.MAX_LOG + 1)):
            with self.subTest(observed=observed, size=size):
                execute, *fakes = self.terminal_fixture(observed, size=size, running=True)
                row = execute()
                self.assertEqual(row["exitCode"], 124)
                self.assertTrue(row["processGroupDrained"])
                self.assert_terminal_cleanup(*fakes)

    def test_terminal_log_observation_error_still_drains_the_owned_process(self):
        execute, *fakes = self.terminal_fixture(1.0, stat_error=OSError("synthetic stat failure"))
        with self.assertRaisesRegex(OSError, "synthetic stat failure"):
            execute()
        self.assert_terminal_cleanup(*fakes)

    def test_python_fixture_exit_and_deadline_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory)
            failed = hosted.execute(state, "failure", [sys.executable, "-c", "raise SystemExit(7)"], 5)
            self.assertEqual(failed["exitCode"], 7)
            self.assertTrue(failed["processGroupDrained"])
            timed = hosted.execute(state, "deadline", [sys.executable, "-c", "import time; time.sleep(10)"], 0.1)
            self.assertEqual(timed["exitCode"], 124)
            self.assertTrue(timed["processGroupDrained"])


if __name__ == "__main__":
    unittest.main()
