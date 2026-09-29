#!/usr/bin/env python3
"""Offline source floors only; actual resolution and generated locks are separate.

This scoped source tripwire supports line comments only in the inspected policy
sections. It rejects block-comment delimiters instead of attempting to parse Kotlin.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
MINIMUM = "2.22.2"
COORDINATES = ("com.fasterxml.jackson.core:jackson-core", "com.fasterxml.jackson.core:jackson-databind")
SCOPES = (("buildscript {\n", "\nplugins {\n"),
          ("val advisoryMinimumVersions = mapOf(\n", "\nfun isVersionBelow("))


def section(source, start, end):
    if source.count(start) != 1 or source.count(end) != 1:
        raise ValueError("ambiguous build-tool policy scope")
    return source.split(start, 1)[1].split(end, 1)[0]


def check(source):
    # Independently pin both modules in each real scope, not global occurrences.
    for start, end in SCOPES:
        scope = section(source, start, end)
        if "/*" in scope or "*/" in scope:
            raise ValueError("policy source tripwire supports line comments only")
        for coordinate in COORDINATES:
            rows = re.findall(r'^[ \t]*"' + re.escape(coordinate) +
                              r'"[ \t]+to[ \t]+"([^"]+)"[ \t]*,[ \t]*$', scope, re.MULTILINE)
            if rows != [MINIMUM]:
                raise ValueError("both scopes require exactly one Jackson 2.22.2 floor per module")


def replace_scope(source, index, old, new):
    """Memory-only mutation in one selected source section."""
    start, end = SCOPES[index]
    before, tail = source.split(start, 1)
    scope, after = tail.split(end, 1)
    if scope.count(old) != 1:
        raise ValueError("mutation requires exactly one scoped row")
    return before + start + scope.replace(old, new, 1) + end + after


class JacksonFloorControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = (ROOT / "build.gradle.kts").read_text(encoding="utf-8")

    def test_actual_four_scoped_floors(self):
        check(self.source)

    def test_each_scope_and_module_rejects_missing_misplaced_or_stale_floor(self):
        for index in range(len(SCOPES)):
            for coordinate in COORDINATES:
                row = '"' + coordinate + '" to "' + MINIMUM + '",'
                replacements = {
                    "missing": "",
                    "commented": "// " + row,
                    "block-commented": "/*\n" + row + "\n*/",
                    "duplicate": row + "\n" + row,
                    "wrong-coordinate": row.replace(coordinate, coordinate + "-other"),
                    "stale-2.21.5": row.replace(MINIMUM, "2.21.5"),
                    "insufficient-2.21.6": row.replace(MINIMUM, "2.21.6"),
                    "stale-2.22.1": row.replace(MINIMUM, "2.22.1"),
                }
                mutations = {name: replace_scope(self.source, index, row, replacement)
                             for name, replacement in replacements.items()}
                missing = mutations["missing"]
                mutations["outside-both-scopes"] = missing + "\n" + row + "\n"
                mutations["moved-to-other-scope"] = replace_scope(missing, 1 - index, row, row + "\n" + row)
                for name, changed in mutations.items():
                    with self.subTest(scope=index, coordinate=coordinate, mutation=name):
                        self.assertNotEqual(changed, self.source)
                        with self.assertRaises(ValueError):
                            check(changed)


if __name__ == "__main__":
    unittest.main()
