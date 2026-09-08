#!/usr/bin/env python3
"""No network/Gradle: exercise the actual host-classifier policy on fixtures."""

import copy
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
CHECKER = ROOT / "scripts/check-host-toolchain-verification.py"
NS = "{https://schema.gradle.org/dependency-verification}"
# Intentionally independent of the checker. Historical records are permitted;
# the current seven names must not be inferred from the metadata under test.
COMPONENTS = (
    ("org.jetbrains.kotlin", "kotlin-native-prebuilt", "2.4.10", (
        "kotlin-native-prebuilt-2.4.10-linux-x86_64.tar.gz",
        "kotlin-native-prebuilt-2.4.10-macos-aarch64.tar.gz",
        "kotlin-native-prebuilt-2.4.10-macos-x86_64.tar.gz",
        "kotlin-native-prebuilt-2.4.10-windows-x86_64.zip",
    )),
    ("com.android.tools.build", "aapt2", "9.3.1-15703166", (
        "aapt2-9.3.1-15703166-linux.jar",
        "aapt2-9.3.1-15703166-osx.jar",
        "aapt2-9.3.1-15703166-windows.jar",
    )),
)


class HostToolchainPolicyTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="p2pkit-host-toolchain-")
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "gradle").mkdir()
        self.catalog = self.root / "gradle/libs.versions.toml"
        self.catalog.write_text('[versions]\nkotlin = "2.4.10"\nagp = "9.3.1"\n', encoding="utf-8")
        self.metadata = self.root / "gradle/verification-metadata.xml"
        self.tree = ET.Element(NS + "verification-metadata")
        self.components = ET.SubElement(self.tree, NS + "components")
        for group, name, version, artifacts in COMPONENTS:
            component = ET.SubElement(self.components, NS + "component", group=group, name=name, version=version)
            for artifact in artifacts:
                element = ET.SubElement(component, NS + "artifact", name=artifact)
                ET.SubElement(element, NS + "sha256", value="a" * 64)

    def invoke(self, expected, diagnostic):
        ET.ElementTree(self.tree).write(self.metadata, encoding="utf-8", xml_declaration=True)
        result = subprocess.run([sys.executable, str(CHECKER), "--root", str(self.root)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(expected, result.returncode, result.stdout + result.stderr)
        self.assertIn(diagnostic, result.stdout + result.stderr)

    def test_seven_current_hosts_and_historical_metadata_pass(self):
        historical = copy.deepcopy(self.components[0])
        historical.set("version", "2.3.21")
        self.components.append(historical)
        self.invoke(0, "7 current Native/AAPT2 host artifacts")

    def test_every_missing_host_is_rejected(self):
        for component in self.components:
            for artifact in list(component):
                with self.subTest(artifact=artifact.get("name")):
                    component.remove(artifact)
                    self.invoke(1, "missing host-toolchain artifact " + artifact.get("name"))
                    component.append(artifact)

    def test_original_mac_only_metadata_is_rejected(self):
        for component in self.components:
            for artifact in list(component):
                if not any(host in artifact.get("name") for host in ("macos-aarch64", "-osx.jar")):
                    component.remove(artifact)
        self.invoke(1, "missing host-toolchain artifact kotlin-native-prebuilt-2.4.10-linux-x86_64.tar.gz")

    def test_every_renamed_classifier_is_rejected(self):
        for component in self.components:
            for artifact in component:
                original = artifact.get("name")
                with self.subTest(artifact=original):
                    artifact.set("name", original + ".wrong-host")
                    self.invoke(1, "missing host-toolchain artifact " + original)
                    artifact.set("name", original)

    def test_wrong_component_coordinates_or_version_are_rejected(self):
        for component in self.components:
            for field in ("group", "name", "version"):
                original = component.get(field)
                with self.subTest(component=component.get("name"), field=field):
                    component.set(field, original + ".unreviewed")
                    self.invoke(1, "expected exactly one component")
                    component.set(field, original)

    def test_duplicate_current_components_are_rejected(self):
        for component in list(self.components):
            with self.subTest(component=component.get("name")):
                duplicate = copy.deepcopy(component)
                self.components.append(duplicate)
                self.invoke(1, "expected exactly one component")
                self.components.remove(duplicate)

    def test_duplicate_artifacts_are_rejected(self):
        for component in self.components:
            with self.subTest(component=component.get("name")):
                duplicate = copy.deepcopy(component[0])
                component.append(duplicate)
                self.invoke(1, "duplicate artifact")
                component.remove(duplicate)

    def test_missing_malformed_and_multiple_hashes_are_rejected(self):
        for component in self.components:
            for artifact in component:
                with self.subTest(artifact=artifact.get("name")):
                    original = artifact[0]
                    artifact.remove(original)
                    self.invoke(1, "expected one exact SHA-256")
                    artifact.append(original)
                    for value in ("", "a" * 63, "g" * 64, "A" * 64, "a" * 65):
                        original.set("value", value)
                        self.invoke(1, "expected one exact SHA-256")
                    original.set("value", "a" * 64)
                    duplicate = copy.deepcopy(original)
                    artifact.append(duplicate)
                    self.invoke(1, "expected one exact SHA-256")
                    artifact.remove(duplicate)
                    alternative = ET.SubElement(original, NS + "also-trust", value="b" * 64)
                    self.invoke(1, "expected one exact SHA-256")
                    original.remove(alternative)

    def test_catalog_change_or_ambiguous_input_requires_review(self):
        original = self.catalog.read_text(encoding="utf-8")
        for content in (
            original.replace('"2.4.10"', '"2.4.20"'),
            original.replace('"9.3.1"', '"9.4.0"'),
            original + 'kotlin = "2.4.10"\n',
            original + '[versions]\nkotlin = "2.4.10"\nagp = "9.3.1"\n',
            original.replace("[versions]", "[libraries]"),
        ):
            with self.subTest(catalog=content):
                self.catalog.write_text(content, encoding="utf-8")
                self.invoke(1, "FATAL:")

    def test_outer_toolchain_policy_invokes_checker_and_regressions(self):
        lines = (ROOT / "scripts/tests/check-kotlin-toolchain-policy-test.sh").read_text(encoding="utf-8").splitlines()
        self.assertEqual(1, lines.count('python3 "$ROOT/scripts/check-host-toolchain-verification.py"'))
        self.assertEqual(1, lines.count('python3 "$ROOT/scripts/tests/check-host-toolchain-verification-test.py"'))


if __name__ == "__main__":
    unittest.main(verbosity=2)
