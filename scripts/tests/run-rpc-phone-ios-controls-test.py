#!/usr/bin/env python3
"""Offline negative controls, not XCTest execution or phone qualification."""
import copy
import importlib.util
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("phone_controls", ROOT / "scripts/run-rpc-phone-ios-controls.py")
phone = importlib.util.module_from_spec(spec)
spec.loader.exec_module(phone)


class PhoneResultControls(unittest.TestCase):
    def objects(self):
        return [{"summaries": [{"_type": {"_name": "ActionTestableSummary"}, "targetName": {"_value": target},
            "tests": [{"_type": {"_name": "ActionTestMetadata"}, "identifier": {"_value": name},
                       "testStatus": {"_value": "Success"}} for name in sorted(methods)]}
            for target, methods in phone.inventory(ROOT).items()]}]

    def test_exact_source_inventory_is_required_and_accepted(self):
        expected = phone.inventory(ROOT)
        actual = phone.assess_xctest(self.objects(), expected)
        self.assertEqual([6, 2], [len(methods) for methods in actual.values()])

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
        self.assertIn('path: samples/p2p-sample-rpc/build/phone-ios/Info.plist', project)
        self.assertIn('SWIFT_TREAT_WARNINGS_AS_ERRORS: YES', project)
        android = (ROOT / "samples/p2p-sample-android/build.gradle.kts").read_text()
        self.assertIn('debugImplementation(project(":p2p-sample-rpc"))', android)
        self.assertNotIn('implementation(project(":p2p-sample-rpc"))', android)
        self.assertIn('LanPermissionRuntimeInstrumentation', android)


if __name__ == "__main__":
    unittest.main(verbosity=2)
