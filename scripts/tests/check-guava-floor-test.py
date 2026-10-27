#!/usr/bin/env python3
"""Offline Guava source/lock tripwires, not artifact provenance or JVM execution.

GHSA-xxph-c9ww-hj94 is fixed in33.7.2. The maintained hosted generator and
independent provenance review must produce the locks before the full suite runs.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
MINIMUM = "33.7.2"
ROW = '"com.google.guava:guava" to "33.7.2-jre",'
SCOPES = (("buildscript {\n", "\nplugins {\n"),
          ("val advisoryMinimumVersions = mapOf(\n", "\nfun isVersionBelow("))
VARIANT = '''val selectedMinimumVersion = if (
requestedModule == "com.google.guava:guava" &&
requested.version?.endsWith("-android") == true
) minimumVersion.removeSuffix("-jre") + "-android" else minimumVersion
useVersion(selectedMinimumVersion)'''


def section(source, start, end):
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("ambiguous Guava floor scope")
    return source.split(start, 1)[1].split(end, 1)[0]


def check_source(source):
    for start, end in SCOPES:
        scope = section(source, start, end)
        if "/*" in scope or "*/" in scope:
            raise ValueError("source tripwire supports line comments only")
        rows = re.findall(r'^[ \t]*"com\.google\.guava:guava"[ \t]+to[ \t]+"([^"]+)"[ \t]*,[ \t]*$',
                          scope, re.MULTILINE)
        if rows != [MINIMUM + "-jre"]:
            raise ValueError("root and project Guava floors must each occur exactly once")
    normalized = "\n".join(line.strip() for line in source.splitlines())
    if normalized.count(VARIANT) != 2:
        raise ValueError("both requested-dependency scopes must preserve the Android edition")
    for guard in ('if (requestedIsBelow) {',
                  'if (minimumVersion != null && isVersionBelow(requested.version, minimumVersion)) {'):
        if source.count(guard) != 1:
            raise ValueError("a floor must not force a downgrade or affect unrequested modules")
    required = section(source, '        val required = setOf(\n', '        val resolvedComponents =')
    if required.count('"com.google.guava:guava",') != 1:
        raise ValueError("the actual root classpath Guava floor must be verified")


def check_lock(text):
    versions = re.findall(r'^com\.google\.guava:guava:([^=\n]+)=', text, re.MULTILINE)
    for version in versions:
        match = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)-(jre|android)', version)
        if match is None or tuple(map(int, match.groups()[:3])) < (33, 7, 2):
            raise ValueError("locked Guava is below the patched floor or has an unknown edition")
    return versions


class GuavaSourceControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "build.gradle.kts").read_text(encoding="utf-8")

    def test_actual_requested_root_project_floors_and_variant_guards(self):
        check_source(self.source)

    def test_each_scope_rejects_missing_commented_duplicate_or_vulnerable_floor(self):
        before, middle, after = self.source.split(ROW)
        for index in (0, 1):
            for replacement in ("", "// " + ROW, "/*\n" + ROW + "\n*/", ROW + "\n" + ROW,
                                ROW.replace("33.7.2", "32.0.1"), ROW.replace("33.7.2", "33.6.0"),
                                ROW.replace("33.7.2", "33.7.1"), ROW.replace(":guava", ":other")):
                rows = [ROW, ROW]
                rows[index] = replacement
                with self.subTest(scope=index, replacement=replacement), self.assertRaises(ValueError):
                    check_source(before + rows[0] + middle + rows[1] + after)

    def test_floor_requires_actual_request_version_and_edition(self):
        for old, new in (('if (requestedIsBelow) {', 'if (true) {'),
                         ('if (minimumVersion != null && isVersionBelow(requested.version, minimumVersion)) {',
                          'if (minimumVersion != null) {'),
                         ('requested.version?.endsWith("-android") == true', 'true'),
                         ('minimumVersion.removeSuffix("-jre") + "-android"', 'minimumVersion'),
                         ('useVersion(selectedMinimumVersion)', 'useVersion(minimumVersion)')):
            with self.subTest(mutation=old), self.assertRaises(ValueError):
                check_source(self.source.replace(old, new, 1))

    def test_guava_cannot_disappear_from_root_floor_verification(self):
        required = '        val required = setOf(\n            "com.google.guava:guava",'
        self.assertEqual(self.source.count(required), 1)
        with self.assertRaises(ValueError):
            check_source(self.source.replace(required, '        val required = setOf('))


class GuavaLockControls(unittest.TestCase):
    def test_all_actual_lock_occurrences_are_at_the_patched_floor(self):
        paths = [ROOT / "buildscript-gradle.lockfile", ROOT / "gradle.lockfile",
                 *ROOT.glob("library/*/gradle.lockfile"), *ROOT.glob("samples/*/gradle.lockfile")]
        versions = [version for path in paths for version in check_lock(path.read_text(encoding="utf-8"))]
        self.assertTrue(versions, "Guava must be inspected, not silently absent from every lock")
        root_versions = check_lock((ROOT / "buildscript-gradle.lockfile").read_text())
        self.assertEqual(len(root_versions), 1)
        self.assertTrue(root_versions[0].endswith("-jre"), "Preserve the existing root JRE edition")

    def test_both_editions_reject_vulnerable_versions_and_allow_safe_versions(self):
        for edition in ("jre", "android"):
            for version in ("4.0", "32.0.1", "33.4.0", "33.4.8", "33.6.0", "33.7.0", "33.7.1"):
                with self.subTest(version=version, edition=edition), self.assertRaises(ValueError):
                    check_lock("com.google.guava:guava:" + version + "-" + edition + "=classpath\n")
            for version in ("33.7.2", "33.7.3", "34.0.0"):
                expected = version + "-" + edition
                self.assertEqual(check_lock("com.google.guava:guava:" + expected + "=classpath\n"), [expected])
        self.assertEqual(check_lock("com.google.guava:failureaccess:1.0.3=classpath\n"), [])


if __name__ == "__main__":
    unittest.main()
