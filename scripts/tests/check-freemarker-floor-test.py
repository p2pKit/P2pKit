#!/usr/bin/env python3
"""Offline source tripwires only; generated locks and native resolution are separate."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
FLOOR = '"org.freemarker:freemarker" to "2.3.35",'


def section(source, start, end):
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("ambiguous build-tool policy scope")
    return source.split(start, 1)[1].split(end, 1)[0]


def check(source):
    # The fixed expected version is independent of the implementation and locks.
    # Check each real scope, not merely two occurrences anywhere in the file.
    root = section(source, "buildscript {\n", "\nplugins {\n")
    project = section(source, "val advisoryMinimumVersions = mapOf(\n", "\nfun isVersionBelow(")
    for scope in (root, project):
        rows = re.findall(r'^\s*"org\.freemarker:freemarker"\s+to\s+"([^"]+)"\s*,\s*$', scope, re.MULTILINE)
        if rows != ["2.3.35"]:
            raise ValueError("both requested-dependency scopes require FreeMarker 2.3.35")
    if ')[requestedModule]' not in root or "if (requestedIsBelow) {" not in root:
        raise ValueError("root floor must only upgrade a requested dependency")
    if 'else -> advisoryMinimumVersions[requestedModule]' not in source or \
            'if (minimumVersion != null && isVersionBelow(requested.version, minimumVersion)) {' not in source:
        raise ValueError("project floor must only upgrade a requested dependency")
    required = section(source, "        val required = setOf(\n", "        val resolvedComponents =")
    if "org.freemarker" in required:
        raise ValueError("FreeMarker is not required to occur in the root classpath")


class FreeMarkerFloorControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "build.gradle.kts").read_text(encoding="utf-8")

    def test_actual_two_floor_source(self):
        check(self.source)

    def test_each_scope_rejects_missing_stale_duplicate_or_commented_floor(self):
        before, middle, after = self.source.split(FLOOR)
        for scope in (0, 1):
            for replacement in ("", FLOOR.replace("2.3.35", "2.3.34"), FLOOR + "\n" + FLOOR,
                                "// " + FLOOR, FLOOR.replace("freemarker:freemarker", "freemarker:other")):
                rows = [FLOOR, FLOOR]
                rows[scope] = replacement
                changed = before + rows[0] + middle + rows[1] + after
                with self.subTest(scope=scope, replacement=replacement), self.assertRaises(ValueError):
                    check(changed)

    def test_no_forced_downgrade_or_unrequested_dependency(self):
        for old, new in ((")[requestedModule]", ')["org.freemarker:freemarker"]'),
                         ("if (requestedIsBelow) {", "if (true) {"),
                         ("else -> advisoryMinimumVersions[requestedModule]", 'else -> "2.3.35"'),
                         ("if (minimumVersion != null && isVersionBelow(requested.version, minimumVersion)) {",
                          "if (minimumVersion != null) {")):
            changed = self.source.replace(old, new)
            self.assertNotEqual(changed, self.source)
            with self.subTest(old=old), self.assertRaises(ValueError):
                check(changed)

    def test_root_classpath_presence_is_not_newly_required(self):
        changed = self.source.replace("        val required = setOf(\n",
                                      '        val required = setOf(\n            "org.freemarker:freemarker",\n')
        with self.assertRaises(ValueError):
            check(changed)


if __name__ == "__main__":
    unittest.main()
