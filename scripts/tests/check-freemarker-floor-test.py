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


def check_writer(source):
    """Pin the reviewed small graph wiring, not Kotlin execution or lock contents."""
    def lines(value):
        return "\n".join(line.strip() for line in value.splitlines()
                         if line.strip() and not line.lstrip().startswith("//"))

    graph = section(source, "gradle.taskGraph.whenReady {\n", "\n// Keep coverage in sync")
    expected = '''
    val lockRefreshInGraph = hasTask(resolveAndLockAll.get())
    check(lockRefreshInGraph == gradle.startParameter.isWriteDependencyLocks) {
        if (lockRefreshInGraph) {
            "resolveAndLockAll must be invoked with --write-locks"
        } else {
            "--write-locks may only be used with resolveAndLockAll"
        }
    }
    if (lockRefreshInGraph) {
        val dokkaPluginLockConfigurations = subprojects
            .filter { it.plugins.hasPlugin("org.jetbrains.dokka") }
            .map { subproject ->
                subproject.tasks.named("dokkaJavadoc").get()
                subproject.configurations.getByName("dokkaJavadocPlugin").also { configuration ->
                    check(configuration.isCanBeResolved && !configuration.isCanBeConsumed) {
                        "Dokka migration plugin lock refresh requires a resolvable, non-consumable configuration"
                    }
                }
            }
        resolveAndLockAll.get().doLast {
            dokkaPluginLockConfigurations.forEach { configuration ->
                configuration.resolve()
            }
        }
    }
}
'''
    if lines(graph) != lines(expected):
        raise ValueError("only the admitted writer may realize and resolve the exact migration plugin configuration")
    for selector in ('tasks.named("dokkaJavadoc")', 'configurations.getByName("dokkaJavadocPlugin")',
                     "configuration.resolve()"):
        if source.count(selector) != 1:
            raise ValueError("migration configuration access must remain exclusive to the writer graph")
    consumers = section(source, "gradle.projectsEvaluated {\n", "\nval aggregateSbomGroup =")
    if lines(consumers) != lines('''
    val dependencyConsumerTasks = subprojects.flatMap { subproject ->
        listOfNotNull(
            subproject.tasks.findByName("check"),
            subproject.tasks.findByName("dokkaGeneratePublicationHtml"),
        )
    }
    resolveAndLockAll.configure {
        dependsOn(dependencyConsumerTasks)
    }
}
'''):
        raise ValueError("writer check and HTML dependencies must remain unchanged")
    writer = section(source, 'val resolveAndLockAll = tasks.register("resolveAndLockAll") {\n',
                     "\n// Authorize lock writes")
    if 'dependsOn(\n        "cyclonedxBom",\n    )' not in writer or \
            "check(gradle.startParameter.isWriteDependencyLocks)" not in writer or \
            "check(!gradle.startParameter.isWriteDependencyLocks || !gradle.startParameter.isConfigureOnDemand)" not in source:
        raise ValueError("writer SBOM and original lock-write admission must remain unchanged")


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

    def test_actual_writer_is_exact_graph_gated_and_resolves_only_the_plugin(self):
        check_writer(self.source)

    def test_writer_rejects_flag_only_missing_or_bypassed_graph_admission(self):
        for old, new in (
                ("check(lockRefreshInGraph == gradle.startParameter.isWriteDependencyLocks)", "check(true)"),
                ("val lockRefreshInGraph = hasTask(resolveAndLockAll.get())", "val lockRefreshInGraph = true"),
                ("if (lockRefreshInGraph) {\n        val dokkaPluginLockConfigurations",
                 "if (gradle.startParameter.isWriteDependencyLocks) {\n        val dokkaPluginLockConfigurations"),
                ("gradle.taskGraph.whenReady {\n",
                 'subprojects.forEach { it.tasks.named("dokkaJavadoc").get() }\ngradle.taskGraph.whenReady {\n')):
            changed = self.source.replace(old, new)
            self.assertNotEqual(changed, self.source)
            with self.subTest(old=old), self.assertRaises(ValueError):
                check_writer(changed)

    def test_writer_rejects_wrong_or_synthetic_configuration_and_role_coercion(self):
        for old, new in (
                ('.filter { it.plugins.hasPlugin("org.jetbrains.dokka") }', '.filter { true }'),
                ('tasks.named("dokkaJavadoc").get()', 'tasks.findByName("dokkaJavadoc")'),
                ('configurations.getByName("dokkaJavadocPlugin")', 'configurations.create("dokkaJavadocPlugin")'),
                ('configurations.getByName("dokkaJavadocPlugin")', 'configurations.getByName("dokkaJavadocRuntime")'),
                ("configuration.isCanBeResolved && !configuration.isCanBeConsumed", "true"),
                ("check(configuration.isCanBeResolved", "configuration.isCanBeResolved = true\n                    check(configuration.isCanBeResolved")):
            changed = self.source.replace(old, new)
            self.assertNotEqual(changed, self.source)
            with self.subTest(old=old), self.assertRaises(ValueError):
                check_writer(changed)

    def test_writer_rejects_early_or_missing_resolution_helper_execution_and_omitted_gates(self):
        for old, new in (
                ("resolveAndLockAll.get().doLast {", "resolveAndLockAll.get().doFirst {"),
                ("configuration.resolve()", "// configuration.resolve()"),
                ('subproject.tasks.named("dokkaJavadoc").get()',
                 'resolveAndLockAll.get().dependsOn(subproject.tasks.named("dokkaJavadoc"))'),
                ('subproject.tasks.named("dokkaJavadoc").get()',
                 'subproject.tasks.named("dokkaJavadoc").get().actions.forEach { action -> '
                 'action.execute(subproject.tasks.getByName("dokkaJavadoc")) }'),
                ('subproject.tasks.findByName("check"),', ''),
                ('subproject.tasks.findByName("dokkaGeneratePublicationHtml"),', ''),
                ('"cyclonedxBom",', ''),
                ("check(!gradle.startParameter.isWriteDependencyLocks || !gradle.startParameter.isConfigureOnDemand)",
                 "check(true)")):
            changed = self.source.replace(old, new)
            self.assertNotEqual(changed, self.source)
            with self.subTest(old=old), self.assertRaises(ValueError):
                check_writer(changed)


if __name__ == "__main__":
    unittest.main()
