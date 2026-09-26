#!/usr/bin/env python3
"""Offline version/negative controls only; no JVM, build, packages, or downloads."""

import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("application_release_version", ROOT / "scripts/application_release_version.py")
subject = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(subject)


class VersionTests(unittest.TestCase):
    def test_shared_vectors(self):
        for row in (ROOT / "scripts/tests/fixtures/application-release-versions.tsv").read_text().splitlines():
            if row.startswith("#"):
                continue
            name, code, native, deb = row.split("\t")
            with self.subTest(version=name):
                self.assertEqual(subject.version_fields(name), {"canonicalVersion": name, "androidVersionCode": int(code),
                                 "nativeVersion": native, "debianVersion": deb})

    def test_invalid_versions_and_aliases(self):
        for name in (None, "", "v0.8.0", "0.08.0", "00.8.0", "0.8.00", "0.8", "100.0.0", "0.100.0", "0.8.100",
                     "0.8.0-alpha0", "0.8.0-rc01", "0.8.0-rc100", "0.8.0-RC1", "0.8.0-snapshot", "0.8.0-alpha.1",
                     "0.8.0-rc1+build", "0.8.0\n", " 0.8.0", "0.8.0 ", "0.8.0-rc١", "0.8.0-rc1-SNAPSHOT"):
            with self.subTest(version=name), self.assertRaises(ValueError):
                subject.version_fields(name)

    def test_numeric_prerelease_order_and_bounds(self):
        suffixes = ["-SNAPSHOT"] + [f"-{kind}{n}" for kind in ("alpha", "beta", "rc") for n in range(1, 100)] + [""]
        previous_code, previous_tuple = 0, (0, 0, 0)
        seen = set()
        for base in ("0.0.0", "0.0.1", "0.1.0", "0.99.99", "1.0.0", "99.99.99"):
            for suffix in suffixes:
                value = subject.version_fields(base + suffix)
                code, native = value["androidVersionCode"], tuple(map(int, value["nativeVersion"].split(".")))
                self.assertTrue(previous_code < code <= 400000000)
                self.assertTrue(previous_tuple < native)
                self.assertTrue(1 <= native[0] <= 255 and 0 <= native[1] <= 255 and 0 <= native[2] <= 65535)
                self.assertNotIn((code, native), seen)
                seen.add((code, native))
                previous_code, previous_tuple = code, native

    def test_single_exact_property_not_alias(self):
        content = "# comment\nOTHER=a\\:b\nVERSION_NAME=0.8.0-rc1\n"
        self.assertEqual(subject.from_properties(content), subject.version_fields("0.8.0-rc1"))
        for invalid in ("", "VERSION_NAME=0.8.0-rc1 \n", " VERSION_NAME=0.8.0-rc1\n", "VERSION_NAME:0.8.0-rc1\n",
                        content + "VERSION_NAME=0.8.0-rc1\n", content + "VERSION_NAME : 0.8.0-rc1\n",
                        content + "VERSION\\u005fNAME=0.8.0-rc1\n", content + "VERSION\\_NAME=0.8.0-rc1\n",
                        content + "VERSION_\\\n NAME=0.8.0-rc1\n"):
            with self.subTest(content=invalid), self.assertRaises(ValueError):
                subject.from_properties(invalid)

    def test_embedded_identity_requires_exact_source(self):
        value = subject.embedded_identity("0.8.0-rc1", "a" * 40)
        self.assertEqual(value["sourceCommit"], "a" * 40)
        self.assertEqual(value["canonicalVersion"], "0.8.0-rc1")
        for source in ("unknown", "main", "a" * 39, "A" * 40, "a" * 40 + "\n"):
            with self.subTest(source=source), self.assertRaises(ValueError):
                subject.embedded_identity("0.8.0-rc1", source)

    def test_java_properties_line_boundaries(self):
        for separator in ("\n", "\r", "\r\n"):
            self.assertEqual(subject.from_properties("VERSION_NAME=0.8.0" + separator), subject.version_fields("0.8.0"))
        for separator in ("\f", "\v", "\x85", "\u2028", "\u2029"):
            with self.subTest(separator=separator), self.assertRaises(ValueError):
                subject.from_properties("VERSION_NAME=0.8.0" + separator + "OTHER=1\n")

    def test_gradle_wiring_is_single_source(self):
        root = (ROOT / "build.gradle.kts").read_text()
        android = (ROOT / "samples/p2p-sample-android/build.gradle.kts").read_text()
        desktop = (ROOT / "samples/p2p-sample-desktop-ui/build.gradle.kts").read_text()
        self.assertIn("ApplicationReleaseVersion.fromProperties(", root)
        self.assertIn("version = canonicalReleaseVersion", root)
        self.assertIn("versionCode = applicationReleaseVersion.androidCode", android)
        self.assertIn("versionName = applicationReleaseVersion.name", android)
        self.assertIn("assets.srcDir(sampleReleaseIdentity)", android)
        self.assertIn('tasks.named("preBuild") { dependsOn(sampleReleaseIdentity) }', android)
        self.assertIn("packageVersion = applicationReleaseVersion.nativeVersion", desktop)
        self.assertIn('appRelease = "1"', desktop)
        self.assertIn("packageBuildVersion = applicationReleaseVersion.nativeVersion", desktop)
        self.assertIn('tasks.named<ProcessResources>("processResources") { from(sampleReleaseIdentity) }', desktop)


if __name__ == "__main__":
    unittest.main(failfast=True)
