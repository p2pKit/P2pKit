#!/usr/bin/env python3
"""Offline negative controls, not XCTest execution or phone qualification."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("phone_controls", ROOT / "scripts/run-rpc-phone-ios-controls.py")
phone = importlib.util.module_from_spec(spec)
spec.loader.exec_module(phone)


class PhoneResultControls(unittest.TestCase):
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
        self.assertEqual([7, 2], [len(methods) for methods in actual.values()])
        self.assertIn("RpcPhoneRunOwnerTests/testActualKeychainRoundTripNamespacesRevocationAndFixtureRetirement()",
                      actual["p2pkit-rpc-phone-tests"])

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
