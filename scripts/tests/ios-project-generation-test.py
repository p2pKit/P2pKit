#!/usr/bin/env python3
"""macOS generation checks using real XcodeGen/Xcode, not fake build success."""

import hashlib
import json
import pathlib
import plistlib
import re
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = pathlib.Path(__file__).resolve().parents[2]


def run_tool(arguments, cwd):
    result = subprocess.run(arguments, cwd=cwd, capture_output=True, text=True, timeout=90)
    if result.returncode:
        raise RuntimeError(f"{arguments[0]} exited {result.returncode}:\n{result.stdout}\n{result.stderr}")
    return result.stdout


class IosProjectGenerationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for tool in ("git", "xcodegen", "xcodebuild"):
            if shutil.which(tool) is None:
                raise RuntimeError(f"{tool} is required: run this generation gate on macOS with Xcode/XcodeGen")
        temporary = tempfile.TemporaryDirectory(prefix="p2pkit-ios-project-")
        cls.addClassCleanup(temporary.cleanup)
        cls.workspace = pathlib.Path(temporary.name)
        # Copy only first-party tracked inputs, never a user's generated project,
        # build directory, local signing files, or other ignored/untracked files.
        names = run_tool(["git", "ls-files", "-z", "--", "samples/iosApp"], ROOT).split("\0")
        for name in filter(None, names):
            target = cls.workspace / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / name, target)
        cls.project = cls.workspace / "samples/iosApp"
        cls.originals = {
            path: hashlib.sha256(path.read_bytes()).digest()
            for path in (ROOT / "samples/iosApp/project.yml", ROOT / "samples/iosApp/Info.plist")
        }
        cls.addClassCleanup(cls.assert_sources_unchanged)
        run_tool(["xcodegen", "generate", "--spec", str(cls.project / "project.yml")], cls.project)
        cls.generated = cls.project / "p2pkit-sample.xcodeproj"
        listing = run_tool(["xcodebuild", "-list", "-json", "-project", str(cls.generated)], cls.project)
        cls.schemes = json.loads(listing)["project"]["schemes"]

    @classmethod
    def assert_sources_unchanged(cls):
        for path, original in cls.originals.items():
            if hashlib.sha256(path.read_bytes()).digest() != original:
                raise AssertionError(f"Generation changed original source {path}")

    def scheme(self, name):
        self.assertIn(name, self.schemes, f"Maintained caller selects missing generated scheme {name}")
        return ET.parse(self.generated / "xcshareddata/xcschemes" / f"{name}.xcscheme").getroot()

    def test_application_launcher_selects_runnable_application_product(self):
        launcher = (ROOT / "scripts/run-ios-app.sh").read_text()
        name = re.search(r'local scheme="([^"]+)"', launcher)[1]
        scheme = self.scheme(name)
        target = scheme.find("LaunchAction/BuildableProductRunnable/BuildableReference")
        self.assertIsNotNone(target)
        self.assertEqual("p2pkit-sample", target.attrib["BlueprintName"])
        # The launcher deliberately derives the installed bundle path from its
        # scheme variable; substituting the UI scheme must not appear to pass.
        self.assertEqual(f"{name}.app", target.attrib["BuildableName"])
        entries = scheme.findall("BuildAction/BuildActionEntries/BuildActionEntry")
        self.assertTrue(any(
            entry.attrib["buildForRunning"] == "YES"
            and entry.find("BuildableReference").attrib["BlueprintName"] == "p2pkit-sample"
            for entry in entries
        ))

    def test_ui_and_release_callers_preserve_both_test_targets(self):
        for caller in ("scripts/run-ios-ui-tests.sh", "scripts/run-release-gate.sh"):
            with self.subTest(caller=caller):
                name = re.search(r"-scheme\s+([\w-]+)", (ROOT / caller).read_text())[1]
                scheme = self.scheme(name)
                testables = scheme.findall("TestAction/Testables/TestableReference")
                enabled = {
                    test.find("BuildableReference").attrib["BlueprintName"]
                    for test in testables if test.attrib["skipped"] == "NO"
                }
                self.assertTrue({"p2pkit-sample-tests", "p2pkit-sample-uitests"} <= enabled)

    def test_generation_preserves_provenance_and_local_network_declarations(self):
        project_text = (self.generated / "project.pbxproj").read_text()
        phases = [
            json.loads(match[1])
            for match in re.finditer(r'shellScript = ("(?:\\.|[^"\\])*?");', project_text)
        ]
        self.assertIn('sh "$SRCROOT/scripts/check-xcframework.sh"', phases)
        with (self.project / "Info.plist").open("rb") as stream:
            info = plistlib.load(stream)
        self.assertTrue(info["NSLocalNetworkUsageDescription"])
        self.assertIn("_p2pkit2._tcp", info["NSBonjourServices"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
