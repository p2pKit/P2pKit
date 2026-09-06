package dev.p2pkit.sample.diagnostics

import java.io.File
import java.io.IOException
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class RollingJsonlFileAliasTest {
    @Test
    fun clearUsesPhysicalFamilyIdentityWithoutDeletingDistinctCaseSensitiveNames() = withDirectory { directory ->
        val lower = File(directory, "operator.jsonl")
        val upper = File(directory, "OPERATOR.JSONL")
        RollingJsonlFileSink.forFile(lower)("lower")
        val alias = aliases(lower, upper)
        val sink = RollingJsonlFileSink.forFile(upper)
        if (!alias) sink("upper")

        sink.clear()

        assertFalse(upper.exists(), "clear must not falsely succeed for a physical case alias")
        if (alias) assertFalse(lower.exists()) else assertEquals("lower\n", lower.readText())
    }

    @Test
    fun exportFindsPhysicalAliasesButNeverIncludesDistinctCaseSensitiveFamily() = withDirectory { directory ->
        val lower = File(directory, "operator.jsonl")
        val upper = File(directory, "OPERATOR.JSONL")
        val lowerLine = event("lower-session")
        RollingJsonlFileSink.forFile(lower)(lowerLine)
        val alias = aliases(lower, upper)
        val sink = RollingJsonlFileSink.forFile(upper)
        if (!alias) sink(event("upper-session"))
        val selectedSession = if (alias) "lower-session" else "upper-session"

        val exported = sink.evidenceFiles(selectedSession)

        assertEquals(1, exported.size)
        assertTrue(exported.values.single().decodeToString().contains("\"testSessionId\":\"$selectedSession\""))
        if (!alias) assertTrue(sink.evidenceFiles("lower-session").isEmpty())
        assertEquals(lowerLine + "\n", lower.readText(), "export never rewrites local originals")
    }

    @Test
    fun reducedRetentionPrunesAllAliasesButPreservesDistinctCaseSensitiveFamily() = withDirectory { directory ->
        val lower = File(directory, "operator.jsonl")
        val upper = File(directory, "OPERATOR.JSONL")
        val lowerSink = RollingJsonlFileSink.forFile(lower, 4_096, 4)
        repeat(4) { lowerSink("$it".repeat(4_095)) }
        val alias = aliases(lower, upper)
        val lowerBefore = (0..3).associateWith { generation(lower, it).readText() }

        RollingJsonlFileSink.forFile(upper, 4_096, 2)("next")

        assertEquals("next\n", upper.readText())
        if (alias) {
            assertFalse(generation(lower, 2).exists())
            assertFalse(generation(lower, 3).exists())
            assertEquals(lowerBefore.getValue(0), generation(upper, 1).readText())
            assertEquals(2, directory.listFiles().orEmpty().count { !it.name.startsWith(".") })
        } else {
            assertEquals(lowerBefore, (0..3).associateWith { generation(lower, it).readText() })
        }
    }

    @Test
    fun aliasSelectionWorksWhenOnlyOlderGenerationsRemain() = withDirectory { directory ->
        val lower = File(directory, "operator.jsonl")
        val upper = File(directory, "OPERATOR.JSONL")
        val lowerSink = RollingJsonlFileSink.forFile(lower, 4_096, 4)
        repeat(4) { lowerSink(event("lower-session").padEnd(4_095)) }
        val alias = aliases(lower, upper)
        assertTrue(lower.delete())
        val sink = RollingJsonlFileSink.forFile(upper, 4_096, 2)
        if (alias) {
            assertEquals(3, sink.evidenceFiles("lower-session").size)
            sink(event("lower-session"))
            assertFalse(generation(lower, 2).exists())
            assertFalse(generation(lower, 3).exists())
            sink.clear()
            assertFalse(generation(lower, 1).exists())
        } else {
            sink(event("upper-session"))
            assertTrue(sink.evidenceFiles("lower-session").isEmpty())
            sink.clear()
            assertTrue((1..3).all { generation(lower, it).isFile })
        }
    }

    @Test
    fun coldLockFileExistsBeforeItsCanonicalKeyIsRead() = withDirectory { directory ->
        var resolved = false
        val coordination = object : File(directory, ".synthetic.lock") {
            override fun getCanonicalPath(): String {
                assertTrue(isFile, "canonical spelling must be resolved after exclusive creation")
                resolved = true
                return super.getCanonicalPath()
            }
        }
        RollingJsonlFileLock.withLock(coordination) { assertTrue(resolved) }
        assertTrue(coordination.isFile)
    }

    @Test
    fun unicodeNormalizationAliasesUsePhysicalIdentityWithoutMergingDistinctFiles() = withDirectory { directory ->
        val composed = File(directory, "caf\u00e9.jsonl")
        val decomposed = File(directory, "cafe\u0301.jsonl")
        RollingJsonlFileSink.forFile(composed)(event("composed-session"))
        val alias = aliases(composed, decomposed)
        val sink = RollingJsonlFileSink.forFile(decomposed)
        if (!alias) sink(event("decomposed-session"))
        assertEquals(1, sink.evidenceFiles(if (alias) "composed-session" else "decomposed-session").size)
        sink.clear()
        assertFalse(decomposed.exists())
        assertEquals(!alias, composed.exists())
    }

    @Test
    fun identityAliasDoesNotAuthorizeDeletingAnotherDirectoryEntry() = withDirectory { directory ->
        val active = File(directory, "diagnostic-events.jsonl").apply { writeText("owned\n") }
        val unrelated = File(directory, "unrelated.txt").apply { writeText("preserve") }
        // Model a symlink/provider alias without requiring Windows symlink-creation privileges.
        val alias = object : File(unrelated.path) {
            override fun getCanonicalPath(): String = active.canonicalPath
        }
        val operations = object : RollingJsonlFileOperations() {
            override fun list(directory: File): Array<File> = arrayOf(active, alias)
        }
        val sink = RollingJsonlFileSink(directory, 4_096, 2, operations)
        assertFailsWith<IOException> { sink.clear() }
        assertFailsWith<IOException> { sink("next") }
        assertEquals("owned\n", active.readText())
        assertEquals("preserve", unrelated.readText())
    }

    private fun aliases(first: File, second: File): Boolean =
        (second.exists() && Files.isSameFile(first.toPath(), second.toPath())).also {
            println("caseAliases=$it; both filesystem policies assert their required behavior")
        }

    private fun generation(active: File, index: Int): File =
        if (index == 0) active else File(active.parentFile, "${active.name}.$index")

    private fun event(session: String): String = diagnosticJson(
        DiagnosticEvent(
            index = 1,
            timestamp = "2026-09-06T12:00:00Z",
            platform = "synthetic",
            operatingSystem = "test",
            applicationVersion = "test",
            buildNumber = "test",
            gitCommitSha = "synthetic",
            safeDeviceId = "synthetic",
            testSessionId = session,
            testId = "PS-T05",
            role = "both",
            category = "test",
            eventName = "test.case_alias",
            severity = DiagnosticSeverity.INFO
        )
    )

    private fun withDirectory(action: (File) -> Unit) {
        val directory = Files.createTempDirectory("p2pkit-log-case-alias").toFile()
        try {
            action(directory)
        } finally {
            assertTrue(directory.deleteRecursively())
        }
    }
}
