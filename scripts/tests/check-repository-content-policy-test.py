#!/usr/bin/env python3
"""Offline tripwires for the maintained repository DSL, not Gradle resolution proof."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[2]
EXCLUSION = 'excludeVersion("org.jetbrains.kotlin", "kotlin-metadata-jvm", "2.3.21")'
EXPECTED = '''dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google {
            content {
                excludeVersion("org.jetbrains.kotlin", "kotlin-metadata-jvm", "2.3.21")
            }
        }
        mavenCentral()
    }
}'''


def tokens(source):
    # Keep strings intact: whitespace inside a coordinate is not formatting.
    return re.findall(r'"(?:\\.|[^"\\])*"|//[^\n]*|[^\s]', source)


def check_project_repositories(source):
    starts = list(re.finditer(r"(?m)^dependencyResolutionManagement\s*\{", source))
    ends = list(re.finditer(r"(?m)^rootProject\.name\b", source))
    if len(starts) != 1 or len(ends) != 1 or starts[0].start() >= ends[0].start():
        raise ValueError("Missing or ambiguous maintained project repository block")
    actual = source[starts[0].start():ends[0].start()]
    actual_tokens = [token for token in tokens(actual) if not token.startswith("//")]
    if actual_tokens != tokens(EXPECTED):
        raise ValueError("Project repositories must retain Google, Central, and only the exact Kotlin metadata exception")


class RepositoryContentPolicyTest(unittest.TestCase):
    def candidate(self, block):
        return block + '\nrootProject.name = "test"\n'

    def test_current_repository_scope(self):
        check_project_repositories((ROOT / "settings.gradle.kts").read_text(encoding="utf-8"))

    def test_comments_and_formatting_do_not_change_the_exception(self):
        check_project_repositories(self.candidate(EXPECTED.replace(EXCLUSION, "// Exact Central coordinate.\n" + EXCLUSION)))

    def test_no_unfiltered_google_lookup_for_the_coordinate(self):
        with self.assertRaises(ValueError):
            check_project_repositories(self.candidate(EXPECTED.replace(EXCLUSION, "")))

    def test_other_versions_and_modules_are_not_excluded(self):
        for altered in (EXCLUSION.replace("2.3.21", "2.3.20"), EXCLUSION.replace("kotlin-metadata-jvm", "kotlin-stdlib"),
                        EXCLUSION.replace("2.3.21", "2.3.21 ")):
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                check_project_repositories(self.candidate(EXPECTED.replace(EXCLUSION, altered)))

    def test_broad_module_or_group_exclusions_are_rejected(self):
        for altered in ('excludeModule("org.jetbrains.kotlin", "kotlin-metadata-jvm")',
                        'excludeGroup("org.jetbrains.kotlin")'):
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                check_project_repositories(self.candidate(EXPECTED.replace(EXCLUSION, altered)))

    def test_comments_strings_and_conditionals_are_not_an_active_filter(self):
        for altered in ("// " + EXCLUSION, "/* " + EXCLUSION + " */", '"filter only"', "if (false) { " + EXCLUSION + " }"):
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                check_project_repositories(self.candidate(EXPECTED.replace(EXCLUSION, altered)))

    def test_required_google_and_repository_order_are_retained(self):
        for altered in (EXPECTED.replace("google {", "mavenCentral {"),
                        EXPECTED.replace("        mavenCentral()", ""),
                        EXPECTED.replace("    repositories {", "    repositories {\n        mavenCentral()")):
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                check_project_repositories(self.candidate(altered))

    def test_duplicate_exclusion_and_project_repository_override_are_rejected(self):
        for altered in (EXPECTED.replace(EXCLUSION, EXCLUSION + "\n" + EXCLUSION),
                        EXPECTED.replace("FAIL_ON_PROJECT_REPOS", "PREFER_PROJECT")):
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                check_project_repositories(self.candidate(altered))


if __name__ == "__main__":
    unittest.main()
