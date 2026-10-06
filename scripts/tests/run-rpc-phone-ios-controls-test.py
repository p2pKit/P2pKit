#!/usr/bin/env python3
"""Offline negative controls, not XCTest execution or phone qualification."""
import ast
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("phone_controls", ROOT / "scripts/run-rpc-phone-ios-controls.py")
phone = importlib.util.module_from_spec(spec)
spec.loader.exec_module(phone)


class PhoneResultControls(unittest.TestCase):
    def tool_attempt(self, poll, ticks, *, required=True, launch=None, observer=None):
        row = dict(label='boot-readiness', argv=['NOT-A-REAL-TOOL'], timeoutSeconds=120)
        process = Mock()
        process.poll.side_effect = poll
        popen = Mock(return_value=process, side_effect=launch)
        utc = Mock(side_effect=['2026-10-01T12:00:00+00:00', '2026-10-01T12:02:01+00:00'])
        with tempfile.TemporaryDirectory(prefix='rpc-phone-deadline-') as temporary:
            work = Path(temporary)
            try:
                # This helper's setup takes no time; polling retains its original scripted times.
                result = phone.execute_tool(row, work, ROOT, {}, utc, required=required, popen=popen,
                                            now=Mock(side_effect=[ticks[0], *ticks]), sleep=Mock(), observer=observer)
                return row, process, result, None
            except RuntimeError as error:
                return row, process, None, str(error)

    def test_timely_tool_completion_preserves_exit_and_records_observation_end(self):
        row, process, result, error = self.tool_attempt([None, 0], [0, 1, 119.5])
        self.assertIsNone(error)
        self.assertIs(result, row)
        self.assertEqual(row['exitCode'], 0)
        self.assertIn('endedUtc', row)
        process.terminate.assert_not_called()
        process.kill.assert_not_called()

    def test_late_zero_exit_cannot_satisfy_original_readiness_bound(self):
        for ticks in ([0, 120], [0, 121], [0, 1, 121]):
            poll = [None, 0] if len(ticks) == 3 else [0]
            with self.subTest(ticks=ticks):
                row, process, result, error = self.tool_attempt(poll, ticks)
                self.assertIsNone(result)
                self.assertEqual(error, 'Command deadline; native owner must drain: boot-readiness')
                self.assertEqual(row['exitCode'], 0)  # Observed exit, not an admitted deadline.
                self.assertIn('endedUtc', row)
                process.terminate.assert_not_called()
                process.kill.assert_not_called()

    def test_deadline_keeps_unknown_exit_and_does_not_claim_process_retirement(self):
        row, process, result, error = self.tool_attempt([None], [0, 120])
        self.assertIsNone(result)
        self.assertIsNone(row['exitCode'])
        self.assertEqual(error, 'Command deadline; native owner must drain: boot-readiness')
        self.assertIn('endedUtc', row)
        process.wait.assert_not_called()
        process.terminate.assert_not_called()
        process.kill.assert_not_called()

    def test_process_observation_cannot_extend_deadline_or_promote_late_zero(self):
        observer = Mock()
        observer.finish.return_value = {'diagnostic': 'fixture'}
        row, process, result, error = self.tool_attempt([0], [0, 119, 121], observer=observer)
        self.assertIsNone(result)
        self.assertEqual(error, 'Command deadline; native owner must drain: boot-readiness')
        self.assertEqual(row['exitCode'], 0)
        self.assertEqual(row['processObservation'], observer.finish.return_value)
        observer.start.assert_called_once()
        observer.sample.assert_called_once()
        observer.finish.assert_called_once()
        process.kill.assert_not_called()
        process.terminate.assert_not_called()

    def test_expired_observer_setup_cannot_launch_a_tool(self):
        for elapsed in (120, 121):
            for required in (True, False):
                with self.subTest(elapsed=elapsed, required=required):
                    clock = [1000]
                    observer = Mock()
                    observer.start.side_effect = lambda: clock.__setitem__(0, 1000 + elapsed)
                    observer.finish.return_value = {'diagnostic': 'offline expired setup'}
                    process = Mock()
                    process.poll.return_value = 0
                    popen = Mock(return_value=process)
                    row = dict(label='boot-readiness', argv=['NOT-A-REAL-TOOL'], timeoutSeconds=120)
                    with tempfile.TemporaryDirectory(prefix='rpc-phone-expired-setup-') as temporary:
                        with self.assertRaisesRegex(RuntimeError, 'Command deadline; native owner must drain:'):
                            phone.execute_tool(row, Path(temporary), ROOT, {}, Mock(return_value='OFFLINE UTC'),
                                               required=required, popen=popen, now=lambda: clock[0],
                                               sleep=Mock(), observer=observer)
                    popen.assert_not_called()
                    process.poll.assert_not_called()
                    process.wait.assert_not_called()
                    process.kill.assert_not_called()
                    process.terminate.assert_not_called()
                    observer.start.assert_called_once()
                    observer.sample.assert_not_called()
                    observer.finish.assert_called_once()
                    self.assertNotIn('exitCode', row)
                    self.assertIn('endedUtc', row)
                    self.assertEqual(row['processObservation'], observer.finish.return_value)

    def test_timely_observer_setup_does_not_restart_the_tool_deadline(self):
        for completed in (1119.5, 1120, 1121):
            with self.subTest(completed=completed):
                clock = [1000]
                observer = Mock()
                observer.start.side_effect = lambda: clock.__setitem__(0, 1119)
                observer.finish.return_value = {'diagnostic': 'offline setup within original budget'}
                process = Mock()

                def poll():
                    clock[0] = completed
                    return 0

                process.poll.side_effect = poll
                popen = Mock(return_value=process)
                row = dict(label='boot-readiness', argv=['NOT-A-REAL-TOOL'], timeoutSeconds=120)
                with tempfile.TemporaryDirectory(prefix='rpc-phone-timely-setup-') as temporary:
                    def attempt():
                        return phone.execute_tool(row, Path(temporary), ROOT, {}, Mock(return_value='OFFLINE UTC'),
                                                  popen=popen, now=lambda: clock[0], sleep=Mock(), observer=observer)

                    if completed < 1120:
                        self.assertIs(attempt(), row)
                        observer.sample.assert_called_once()
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'Command deadline; native owner must drain:'):
                            attempt()
                        observer.sample.assert_not_called()
                popen.assert_called_once()
                process.poll.assert_called_once()
                process.wait.assert_not_called()
                process.kill.assert_not_called()
                process.terminate.assert_not_called()
                observer.start.assert_called_once()
                observer.finish.assert_called_once()
                self.assertEqual(row['exitCode'], 0)
                self.assertIn('endedUtc', row)

    def test_log_preparation_cannot_launch_a_tool_after_the_original_deadline(self):
        clock = [1000]
        opened = []
        original_open = Path.open

        def prepare_log(path, *args, **kwargs):
            stream = original_open(path, *args, **kwargs)
            opened.append(stream)
            if path.name == 'boot-readiness.stderr':
                clock[0] = 1120
            return stream

        process = Mock()
        process.poll.return_value = 0
        popen = Mock(return_value=process)
        row = dict(label='boot-readiness', argv=['NOT-A-REAL-TOOL'], timeoutSeconds=120)
        with tempfile.TemporaryDirectory(prefix='rpc-phone-expired-logs-') as temporary:
            with patch.object(Path, 'open', prepare_log):
                with self.assertRaisesRegex(RuntimeError, 'Command deadline; native owner must drain:'):
                    phone.execute_tool(row, Path(temporary), ROOT, {}, Mock(return_value='OFFLINE UTC'),
                                       popen=popen, now=lambda: clock[0], sleep=Mock())
        popen.assert_not_called()
        process.poll.assert_not_called()
        process.wait.assert_not_called()
        process.kill.assert_not_called()
        process.terminate.assert_not_called()
        self.assertEqual(len(opened), 2)
        self.assertTrue(all(stream.closed for stream in opened))
        self.assertNotIn('exitCode', row)
        self.assertIn('endedUtc', row)

    def test_nonzero_tool_exit_and_optional_test_result_keep_distinct_semantics(self):
        for required in (True, False):
            row, _, result, error = self.tool_attempt([65], [0, 1], required=required)
            self.assertEqual(row['exitCode'], 65)
            self.assertEqual(error, 'Command failed: boot-readiness' if required else None)
            self.assertEqual(result, None if required else row)
        _, _, result, error = self.tool_attempt([0], [0, 121], required=False)
        self.assertIsNone(result)  # Optional exit assessment never waives a deadline.
        self.assertIn('Command deadline;', error)

    def test_failed_tool_start_records_end_without_inventing_an_exit(self):
        row, _, result, error = self.tool_attempt([], [0], launch=RuntimeError('OFFLINE launch refused'))
        self.assertIsNone(result)
        self.assertEqual(error, 'OFFLINE launch refused')
        self.assertNotIn('exitCode', row)
        self.assertIn('endedUtc', row)

    def test_source_orders_one_cold_boot_before_producer_without_warmup_or_new_bound(self):
        # Offline source/orchestration check, not execution of a simulator.
        tree = ast.parse((ROOT / 'scripts/run-rpc-phone-ios-controls.py').read_text())
        main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == 'main')
        run = next(node for node in main.body if isinstance(node, ast.FunctionDef) and node.name == 'run')
        self.assertEqual([ast.literal_eval(node) for node in run.args.defaults], [120, True])
        calls = sorted((node.lineno, node) for node in ast.walk(main) if isinstance(node, ast.Call) and
                       isinstance(node.func, ast.Name) and node.func.id == 'run' and node.args and
                       isinstance(node.args[0], ast.Constant))
        labels = [call.args[0].value for _, call in calls]
        for name in ('create-simulator', 'boot-simulator', 'boot-readiness', 'framework-producer', 'phone-unit-ui'):
            self.assertEqual(labels.count(name), 1)
        self.assertLess(labels.index('boot-readiness'), labels.index('framework-producer'))
        self.assertLess(labels.index('framework-producer'), labels.index('phone-unit-ui'))
        boot = next(call for _, call in calls if call.args[0].value == 'boot-readiness')
        self.assertEqual(boot.keywords, [])  # Still the original 120-second default.
        self.assertEqual(ast.literal_eval(boot.args[1].elts[-1]), '-b')

    def test_shutdown_does_not_substitute_for_exact_owned_simulator_deletion(self):
        owned = 'AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE'
        other = '11111111-2222-3333-4444-555555555555'
        phone.verify_simulator_deleted({'devices': {'runtime': [{'udid': other, 'state': 'Booted'}]}}, owned)
        for value in ({}, {'devices': []}, {'devices': {'runtime': 'bad'}}, {'devices': {'runtime': [{}]}},
                      {'devices': {'runtime': [{'udid': owned, 'state': 'Shutdown'}]}},
                      {'devices': {'runtime': [{'udid': owned.lower(), 'state': 'Shutdown'}]}},
                      {'devices': {'runtime': [{'udid': 'malformed'}]}},
                      {'devices': {'one': [{'udid': other}], 'two': [{'udid': other}]}}):
            with self.assertRaises(RuntimeError):
                phone.verify_simulator_deleted(value, owned)
        for identifier in ('all', '', 'unavailable', '../foreign'):
            with self.assertRaises(RuntimeError):
                phone.verify_simulator_deleted({'devices': {}}, identifier)
        source = (ROOT / 'scripts/run-rpc-phone-ios-controls.py').read_text()
        self.assertIn('["/usr/bin/xcrun", "simctl", "delete", simulator]', source)
        self.assertNotIn('["/usr/bin/xcrun", "simctl", "delete", "all"]', source)
        self.assertIn('or not result["simulatorDeleted"]', source)

    def objects(self):
        return [{"summaries": [{"_type": {"_name": "ActionTestableSummary"}, "targetName": {"_value": target},
            "tests": [{"_type": {"_name": "ActionTestMetadata"}, "identifier": {"_value": name},
                       "testStatus": {"_value": "Success"}} for name in sorted(methods)]}
            for target, methods in phone.inventory(ROOT).items()]}]

    def test_exact_source_inventory_is_required_and_accepted(self):
        expected = phone.inventory(ROOT)
        actual = phone.assess_xctest(self.objects(), expected)
        self.assertEqual([64, 5], [len(methods) for methods in actual.values()])
        self.assertIn("RpcPhoneRunOwnerTests/testActualKeychainRoundTripNamespacesRevocationAndFixtureRetirement()",
                      actual["p2pkit-rpc-phone-tests"])
        self.assertIn("RpcPhoneRunOwnerTests/testCapacityRunLabelsRejectTrailingLineEndingsBeforeCreatingASlot()",
                      actual["p2pkit-rpc-phone-tests"])
        for name in ("testEventLogIsBoundedWithoutLosingLastFailure",
                     "testEventLogRejectsArbitrarySecretsAndUnrecognizedFailureComponents",
                     "testEventLogRetainsFailureAcrossRefreshSuccessfulOperationsAndStop",
                     "testEventLogShowsRoleAndObservedPendingWithoutInventingApproval",
                     "testModelDiagnosticsCopyOmitsInputAndCannotStartOrApproveAnything",
                     "testModelRefreshAndStopRetainRejectedStartDiagnostics",
                     "testInvitationCopyAvailabilityUsesTheOriginalDeadlineWithoutRevealOrTimerDelivery",
                     "testModelMaskedCopyStillRejectsIdleStartingStoppedAndBackgroundStates",
                     "testShareWindowRefusedNativeAllowanceCannotKeepARolePending",
                     "testShareWindowNativeExpiryEndsExactlyOnceAndCancelsItsTimer",
                     "testShareWindowTimerExpiryEndsExactlyOnceAndIgnoresLateNativeExpiry",
                     "testShareWindowSynchronousNativeExpiryCannotPublishAnAllowance",
                     "testShareWindowSynchronousTimerExpiryCannotPublishOrLeakCancellation",
                     "testShareWindowRepeatedLeaveCannotRenewItsOriginalDeadlineOrCallback",
                     "testShareWindowResumeChecksMonotonicDeadlineEvenWhenTimerNeverRan",
                     "testShareWindowTimelyResumeAndLateCallbacksCannotRetireTheNextAllowance",
                     "testShareWindowNativeBeginElapsedTimeCannotExtendTheOriginalDeadline",
                     "testShareWindowEligibilityRejectsBusyRetiringAndCapacityRoles",
                     "testModelIdleBackgroundDoesNotRequestShareTimeAndRetiresSensitiveInput",
                     "testModelBackgroundDuringScheduledStartupCannotAcquireShareTimeOrEnterFactory",
                     "testInvitationCopyIsExactLocalOnlyAndDoesNotExtendMintLifetime",
                     "testInvitationRetirementPreservesUnrelatedClipboardContents",
                     "testInvitationReplacementRejectsLateExpiryAndClearsOnlyItsOwnCopy",
                     "testSlowInvitationMintCannotPublishAnExpiredCopy",
                     "testModelStopAndBackgroundRetireCopyAndIdleCannotCopy",
                     "testEmptyRoleSetupExplainsEveryMissingFieldWithoutAcquiringAnOwner",
                     "testWhitespaceOnlyRoleFieldsStayInvalidAndDiagnosticsDoNotEchoInput",
                     "testInvalidPortAndUnapprovedCapacityImportExplainWhyNeitherRoleStarts",
                     "testRejectedNonemptyPolicyAlsoPresentsTheAsynchronousStartupFailure",
                     "testWifiSubnetDerivationUsesActualMaskAndInterface",
                     "testWifiSelectionRejectsPublicUnsafeAmbiguousOrNonWifiPaths",
                     "testWifiSelectionRejectsMalformedMasksAndNonHostAddresses",
                     "testWifiPathDiagnosticsDistinguishUnavailableIpv4NonWifiAndMixedPaths",
                     "testWifiAddressDiagnosticsIdentifyEachExistingRejectionWithoutAdmittingIt",
                     "testWifiSelectionUsesTheSingleAddressedInterfaceNotTheOfferedInterfaceCount",
                     "testWifiSelectionNeverIgnoresAddressedAlternativesOrIncompleteWifiAddressReads",
                     "testWifiInterfaceIdentityCollapsesOnlyVerifiedDuplicateReports",
                     "testWifiInterfaceIdentityRejectsConflictingOrUnavailableMappings",
                     "testWifiInterfaceIdentityDoesNotHideAliasesOtherAddressesOrRejectedPaths",
                     "testWifiDiagnosticRequiresExplicitLaunchAndOmitsNetworkAddresses",
                     "testWifiRefreshRetiresCallbacksRevokesApprovalAndPreservesUnrelatedInput",
                     "testWifiDiagnosticAndCandidateStayTogetherAtConfirmationAndAcrossForegrounds",
                     "testWifiRefreshCannotInterruptInactiveManualOrStartingAndStoppingStates",
                     "testWifiSuggestionNeedsConfirmationAndNeverStartsARoleOrImportsTrust",
                     "testWifiConfirmationRechecksCurrentSnapshotBeforeCopyingSettings",
                     "testWifiChangeAndBackgroundRevokeApprovalAndIgnoreRetiredCallbacks",
                     "testManualSetupRemainsExplicitAndIsNotOverwrittenByWifiSuggestions",
                     "testWifiStartupRejectsUnobservedChangeAndEditedApprovedSettings",
                     "testStopBeforeScheduledStartupDoesNotEnterTheFactory",
                     "testActualWifiObserverRetiresItsMonitorAndCannotReuseAStoppedPath"):
            self.assertIn("RpcPhoneRunOwnerTests/" + name + "()", actual["p2pkit-rpc-phone-tests"])
        self.assertIn("RpcPhonePresentationTests/testSafeDiagnosticsExplainRejectedStartAndCanBeCopiedWithoutSelectingARole()",
                      actual["p2pkit-rpc-phone-uitests"])
        self.assertIn("RpcPhonePresentationTests/testUnconfirmedWifiExplainsNextTapWithoutStartingANetworkRuntime()",
                      actual["p2pkit-rpc-phone-uitests"])
        self.assertIn("RpcPhonePresentationTests/testWifiRefreshShowsItsReasonWithoutConfirmingOrStartingARole()",
                      actual["p2pkit-rpc-phone-uitests"])

    def test_framework_preparation_is_a_bounded_current_source_native_producer(self):
        receipt = Path("/synthetic/owned/framework.json")
        argv = phone.framework_producer_argv(ROOT, receipt)
        self.assertEqual(argv[argv.index("--") + 1:], [phone.FRAMEWORK_TASK, "--console=plain"])
        self.assertEqual(argv[argv.index("--cwd") + 1], str(ROOT))
        self.assertEqual(argv[argv.index("--wrapper") + 1], str(ROOT / "gradlew"))
        self.assertEqual(argv[argv.index("--receipt") + 1], str(receipt))
        self.assertEqual(argv[argv.index("--timeout") + 1], "3600")
        self.assertEqual(argv[1], str(ROOT / "scripts/run-audit-command.py"))
        self.assertEqual(argv[argv.index("--kind") + 1], "gradle")

    def test_actual_project_framework_reference_rejects_wrong_paths_or_group_roots(self):
        good = {"rootObject": "project", "objects": {
            "project": {"isa": "PBXProject", "mainGroup": "main"},
            "main": {"isa": "PBXGroup", "sourceTree": "<group>", "children": ["frameworks"]},
            "frameworks": {"isa": "PBXGroup", "sourceTree": "<group>", "children": ["framework"]},
            "framework": {"isa": "PBXFileReference", "lastKnownFileType": "wrapper.xcframework",
                          "sourceTree": "<group>", "path": phone.FRAMEWORK_REFERENCE}}}
        phone.verify_framework_reference(good)
        for owner, field, value in (("framework", "path", "samples/p2p-sample-rpc/build/XCFrameworks/debug/" +
                                    "P2pKitRpcExample.xcframework"), ("framework", "path", "/other/framework"),
                                   ("framework", "sourceTree", "SOURCE_ROOT"), ("main", "path", "elsewhere"),
                                   ("frameworks", "path", "elsewhere"), ("main", "children", []),
                                   ("frameworks", "children", [])):
            bad = copy.deepcopy(good)
            bad["objects"][owner][field] = value
            with self.subTest(owner=owner, field=field), self.assertRaises(RuntimeError):
                phone.verify_framework_reference(bad)
        for duplicate in ("framework", "frameworks"):
            bad = copy.deepcopy(good)
            bad["objects"]["duplicate"] = copy.deepcopy(bad["objects"][duplicate])
            with self.subTest(duplicate=duplicate), self.assertRaises(RuntimeError):
                phone.verify_framework_reference(bad)

    def test_plist_is_bound_to_both_actual_application_configurations(self):
        good = {"objects": {
            "app": {"isa": "PBXNativeTarget", "name": "p2pkit-rpc-phone",
                    "productType": "com.apple.product-type.application", "buildConfigurationList": "configs"},
            "configs": {"isa": "XCConfigurationList", "buildConfigurations": ["debug", "release"]},
            **{name.lower(): {"isa": "XCBuildConfiguration", "name": name,
                             "buildSettings": {"INFOPLIST_FILE": "Info.plist"}} for name in ("Debug", "Release")}}}
        phone.verify_info_reference(good)
        for name in ("debug", "release"):
            for settings in ({}, {"INFOPLIST_FILE": "samples/p2p-sample-rpc/build/phone-ios/Info.plist"},
                             {"INFOPLIST_FILE": "/other/Info.plist"}, {"INFOPLIST_FILE": "../Info.plist"},
                             {"INFOPLIST_FILE": "Info.plist", "INFOPLIST_FILE[sdk=iphoneos*]": "elsewhere"}):
                bad = copy.deepcopy(good)
                bad["objects"][name]["buildSettings"] = settings
                with self.subTest(name=name, settings=settings), self.assertRaises(RuntimeError):
                    phone.verify_info_reference(bad)
        for owner, field, value in (("app", "name", "other"), ("app", "buildConfigurationList", "missing"),
                                   ("configs", "buildConfigurations", ["debug"]),
                                   ("configs", "buildConfigurations", ["debug", "debug"]),
                                   ("release", "name", "Profile")):
            bad = copy.deepcopy(good)
            bad["objects"][owner][field] = value
            with self.subTest(owner=owner, field=field), self.assertRaises(RuntimeError):
                phone.verify_info_reference(bad)

    def test_generation_has_one_explicit_generated_project_root(self):
        parent = ROOT / "samples/p2p-sample-rpc/build/phone-ios"
        argv = phone.project_generation_argv(ROOT, Path("/synthetic/xcodegen"), parent)
        self.assertEqual(argv[argv.index("--project") + 1], str(parent))
        self.assertEqual(argv[argv.index("--project-root") + 1], str(parent))
        self.assertEqual(argv[argv.index("--spec") + 1], str(ROOT / "samples/p2p-sample-rpc/phone-ios/project.yml"))
        self.assertIn("--no-env", argv)

    def run_stubbed_hook(self, python):
        # The stub exits before any Gradle/artifact operation. Its deliberately
        # unusable shebang proves the explicit interpreter, not PATH, runs it.
        with tempfile.TemporaryDirectory(prefix="rpc-phone-hook-") as temporary:
            root = Path(temporary).resolve()
            hook = root / "samples/p2p-sample-rpc/phone-ios/check-xcframework.sh"
            hook.parent.mkdir(parents=True)
            hook.write_bytes((ROOT / "samples/p2p-sample-rpc/phone-ios/check-xcframework.sh").read_bytes())
            executor = root / "executor.py"
            executor.write_text('#!/intentionally/unavailable/python\nimport json, sys\n'
                                'print(json.dumps(sys.argv[1:]))\nsys.exit(23)\n')
            executor.chmod(0o700)
            env = {"PATH": "/usr/bin:/bin", "P2PKIT_GRADLE_EXECUTOR": str(executor)}
            if python is not None:
                env["P2PKIT_PYTHON3"] = python
            result = subprocess.run(["/bin/sh", str(hook)], env=env, capture_output=True, text=True, timeout=10)
            return root, result

    def test_native_hook_uses_the_bound_interpreter_and_preserves_executor_failure(self):
        root, result = self.run_stubbed_hook(sys.executable)
        self.assertEqual(result.returncode, 23, result.stderr)
        self.assertEqual(json.loads(result.stdout), ["--cwd", str(root), "--wrapper", str(root / "gradlew"),
                         "--purpose", "rpc-phone-xcode-provenance", "--", phone.FRAMEWORK_TASK, "-q", "--console=plain"])

    def test_native_hook_refuses_missing_relative_or_unavailable_interpreter(self):
        for value in (None, "python3", "/intentionally/unavailable/python"):
            with self.subTest(value=value):
                _, result = self.run_stubbed_hook(value)
                self.assertNotEqual(result.returncode, 0)
                self.assertNotEqual(result.returncode, 23)
                self.assertEqual(result.stdout, "")

    def test_each_missing_or_duplicate_method_is_rejected(self):
        original = self.objects()
        for index, summary in enumerate(original[0]["summaries"]):
            for number in range(len(summary["tests"])):
                for duplicate in (False, True):
                    value = copy.deepcopy(original)
                    tests = value[0]["summaries"][index]["tests"]
                    tests.append(tests[number]) if duplicate else tests.pop(number)
                    with self.subTest(index=index, method=number, duplicate=duplicate), self.assertRaises(RuntimeError):
                        phone.assess_xctest(value, phone.inventory(ROOT))

    def test_failed_skipped_and_unknown_status_is_not_passing(self):
        for status in ("Failure", "Skipped", "Unknown", "Expected Failure", ""):
            value = self.objects()
            value[0]["summaries"][0]["tests"][0]["testStatus"]["_value"] = status
            with self.subTest(status=status), self.assertRaises(RuntimeError):
                phone.assess_xctest(value, phone.inventory(ROOT))

    def test_wrong_missing_and_extra_targets_are_rejected(self):
        for change in ("remove", "rename", "extra"):
            value = self.objects()
            if change == "remove": value[0]["summaries"].pop()
            elif change == "rename": value[0]["summaries"][0]["targetName"]["_value"] = "ordinary-p2p-tests"
            else: value[0]["summaries"].append({"_type": {"_name": "ActionTestableSummary"},
                                               "targetName": {"_value": "unclassified"}, "tests": []})
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                phone.assess_xctest(value, phone.inventory(ROOT))

    def test_malformed_empty_and_wrong_case_names_are_rejected(self):
        for value in ([], {}, [None], [{}]):
            with self.assertRaises(RuntimeError): phone.assess_xctest(value, phone.inventory(ROOT))
        for replacement in ({"_value": 7}, "not-a-field", {"_value": "Other/testInvented()"}):
            value = self.objects()
            value[0]["summaries"][0]["tests"][0]["identifier"] = replacement
            with self.assertRaises(RuntimeError): phone.assess_xctest(value, phone.inventory(ROOT))

    def test_apps_keep_explicit_provenance_permissions_and_debug_only_android_dependency(self):
        project = (ROOT / "samples/p2p-sample-rpc/phone-ios/project.yml").read_text()
        self.assertIn('NSLocalNetworkUsageDescription:', project)
        self.assertIn('"_p2pkit2._tcp"', project)
        self.assertIn('sh "$SRCROOT/../../phone-ios/check-xcframework.sh"', project)
        self.assertIn('path: Info.plist', project)
        for directory in ("Sources", "Tests", "UITests"):
            self.assertIn('- ../../phone-ios/' + directory, project)
        self.assertIn('framework: ' + phone.FRAMEWORK_REFERENCE, project)
        self.assertIn('SWIFT_TREAT_WARNINGS_AS_ERRORS: YES', project)
        android = (ROOT / "samples/p2p-sample-android/build.gradle.kts").read_text()
        self.assertIn('debugImplementation(project(":p2p-sample-rpc"))', android)
        self.assertNotIn('implementation(project(":p2p-sample-rpc"))', android)
        self.assertIn('LanPermissionRuntimeInstrumentation', android)

    def test_masked_invitation_copy_keeps_role_admission_and_never_changes_reveal(self):
        root = ROOT / "samples/p2p-sample-rpc/phone-ios/Sources"
        model = (root / "RpcPhoneModel.swift").read_text()
        view = (root / "RpcPhoneApp.swift").read_text()
        action = model.split('    func copyInvitation() {', 1)[1].split('\n    func approve(', 1)[0]
        self.assertIn('guard canCopyInvitation else { return }', action)
        self.assertIn('invitationClipboard.copy()', action)
        self.assertNotIn('revealInvitation', action)
        self.assertIn('var canCopyInvitation: Bool { canAct && hostRole && !invitation.isEmpty && '
                      'invitationClipboard.hasLiveInvitation }', model)
        self.assertIn('var canAct: Bool { foreground && owner.phase == .running && !actionBusy && !operationBusy }', model)
        button = view.split('Button("Copy invitation")', 1)[1].split('            Text(', 1)[0]
        self.assertIn('.disabled(!model.canCopyInvitation)', button)
        self.assertNotIn('revealInvitation', button)
        self.assertIn('Toggle("Reveal on this trusted local display", isOn: $model.revealInvitation)', view)
        self.assertIn('if model.revealInvitation, !model.invitation.isEmpty {', view)


if __name__ == "__main__":
    unittest.main(verbosity=2)
