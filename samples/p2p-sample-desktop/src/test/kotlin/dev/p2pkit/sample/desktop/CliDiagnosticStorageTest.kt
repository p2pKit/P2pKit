package dev.p2pkit.sample.desktop

import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.sample.diagnostics.DiagnosticRecord
import dev.p2pkit.sample.diagnostics.DiagnosticClearAction
import java.io.File
import java.io.IOException
import java.nio.file.Files
import java.util.zip.ZipFile
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class CliDiagnosticStorageTest {
    @Test
    fun exportReportsTheSdkKeepAliveDefault() = withHome { home ->
        configure(home, File(home, "cli.jsonl"))
        ZipFile(CliDiagnostics.export()).use { zip ->
            val entry = assertNotNull(zip.getEntry("summary.json"))
            val summary = zip.getInputStream(entry).bufferedReader().use { it.readText() }
            val timeout = KeepAliveConfig().timeoutMillis
            assertTrue(
                Regex(""""timeoutsMillis"\s*:\s*\{[^}]*"keepAlive"\s*:\s*$timeout(?=\s*[,}])""")
                    .containsMatchIn(summary),
                "Exported keep-alive must match the SDK default used by the CLI"
            )
        }
    }

    @Test
    fun actualClearCommandReportsPartialStorageFailureAndRemainsUsableForRetry() = withHome { home ->
        val direct = File(home, "cli.jsonl")
        configure(home, direct)
        CliDiagnostics.startSession("PS-T05", "both", "other-session")
        CliDiagnostics.startSession("PS-T05", "both", "synthetic-storage")
        val before = CliDiagnostics.recorder.snapshot()
        val directBefore = direct.readText()
        val dropsBefore = CliDiagnostics.recorder.droppedEventCount()
        val obstruction = File(home, "cli.jsonl.1").apply { assertTrue(mkdir()) }
        val messages = mutableListOf<String>()

        CliDiagnostics.clearCommand(messages::add)

        assertEquals(listOf(DiagnosticClearAction.FAILURE_MESSAGE), messages)
        assertEquals(before, CliDiagnostics.recorder.snapshot())
        assertEquals(directBefore, direct.readText())
        val rolling = File(home, ".p2pkit/test-diagnostics/diagnostic-events.jsonl")
        assertTrue("other-session" in rolling.readText())
        assertTrue("synthetic-storage" !in rolling.readText(), "first sink already committed; report partial failure")
        assertEquals(dropsBefore, CliDiagnostics.recorder.droppedEventCount())

        assertTrue(obstruction.delete())
        CliDiagnostics.clearCommand(messages::add)
        assertEquals(2, messages.size)
        assertTrue(messages.last().startsWith("cleared session history"))
        assertEquals(before.filter { it.testSessionId == "other-session" }, CliDiagnostics.recorder.snapshot())
        assertTrue("synthetic-storage" !in direct.readText())
        assertTrue("other-session" in direct.readText())
    }

    @Test
    fun clearStorageFailurePreservesRecorderUntilRetrySucceeds() = withHome { home ->
        configure(home, File(home, "cli.jsonl"))
        val before = CliDiagnostics.recorder.snapshot()
        val obstruction = File(home, ".p2pkit/test-diagnostics/diagnostic-events.jsonl.1")
        assertTrue(obstruction.mkdir())

        assertFailsWith<IOException> { CliDiagnostics.clearCurrent() }
        assertEquals(before, CliDiagnostics.recorder.snapshot())
        assertTrue(obstruction.delete())
        CliDiagnostics.clearCurrent()
        assertTrue(CliDiagnostics.recorder.snapshot().isEmpty())
    }

    @Test
    fun invalidAncestorDoesNotReportSuccessfulClearAndTheActualCommandCanRetry() = withHome { home ->
        val direct = File(home, "cli.jsonl")
        configure(home, direct)
        val before = CliDiagnostics.recorder.snapshot()
        val directBefore = direct.readBytes()
        val logRoot = File(home, ".p2pkit")
        val retained = File(home, "retained-history")
        assertTrue(logRoot.renameTo(retained))
        logRoot.writeText("synthetic ancestor obstruction")
        val messages = mutableListOf<String>()

        CliDiagnostics.clearCommand(messages::add)

        assertEquals(listOf(DiagnosticClearAction.FAILURE_MESSAGE), messages)
        assertEquals(before, CliDiagnostics.recorder.snapshot())
        assertTrue(directBefore.contentEquals(direct.readBytes()))
        assertTrue("synthetic-storage" in File(retained, "test-diagnostics/diagnostic-events.jsonl").readText())
        assertTrue(logRoot.delete())
        assertTrue(retained.renameTo(logRoot))
        CliDiagnostics.clearCommand(messages::add)
        assertEquals(2, messages.size)
        assertTrue(messages.last().startsWith("cleared session history"))
        assertTrue(CliDiagnostics.recorder.snapshot().isEmpty())
        assertTrue("synthetic-storage" !in direct.readText())
        assertTrue("synthetic-storage" !in File(logRoot, "test-diagnostics/diagnostic-events.jsonl").readText())
    }

    @Test
    fun failedDirectLogRotationDoesNotGrowAndIsReportedToRecorder() = withHome { home ->
        val direct = File(home, "cli.jsonl")
        val original = "a".repeat(2 * 1024 * 1024 - 1) + "\n"
        direct.writeText(original)
        val obstruction = File(home, "cli.jsonl.1").apply { mkdir() }
        val sentinel = File(obstruction, "unrelated.txt").apply { writeText("preserve") }
        configure(home, direct)

        assertEquals(original, direct.readText())
        assertEquals("preserve", sentinel.readText())
        assertTrue(CliDiagnostics.recorder.snapshot().isNotEmpty())
        assertTrue(CliDiagnostics.recorder.droppedEventCount() > 0)
        assertTrue(sentinel.delete())
        assertTrue(obstruction.delete())
        CliDiagnostics.recorder.record(DiagnosticRecord(category = "test", eventName = "test.retry"))
        assertEquals(original, File(home, "cli.jsonl.1").readText())
        assertTrue("test.retry" in direct.readText())
        assertTrue(direct.length() <= 2 * 1024 * 1024)
    }

    @Test
    fun failedDefaultLogStillAttemptsDirectOutputAndReportsPersistenceFailure() = withHome { home ->
        val direct = File(home, "cli.jsonl")
        configure(home, direct)
        val obstruction = File(home, ".p2pkit/test-diagnostics/diagnostic-events.jsonl.1").apply { mkdir() }
        File(obstruction, "unrelated.txt").writeText("preserve")
        val original = File(home, ".p2pkit/test-diagnostics/diagnostic-events.jsonl").readText()
        val before = CliDiagnostics.recorder.droppedEventCount()

        CliDiagnostics.recorder.record(DiagnosticRecord(category = "test", eventName = "test.partial_persistence"))

        assertEquals(before + 1, CliDiagnostics.recorder.droppedEventCount())
        assertTrue("test.partial_persistence" in direct.readText())
        assertEquals(original, File(home, ".p2pkit/test-diagnostics/diagnostic-events.jsonl").readText())
    }

    @Test
    fun invalidDirectLogDestinationDoesNotBreakApplicationStartupOrRecording() = withHome { home ->
        configure(home, home.toPath().root.toFile())
        val before = CliDiagnostics.recorder.droppedEventCount()
        assertTrue(before > 0)
        CliDiagnostics.recorder.record(DiagnosticRecord(category = "test", eventName = "test.invalid_destination"))
        assertEquals(before + 1, CliDiagnostics.recorder.droppedEventCount())
        assertEquals("test.invalid_destination", CliDiagnostics.recorder.snapshot().last().eventName)
        assertTrue(File(home, ".p2pkit/test-diagnostics/diagnostic-events.jsonl").isFile)
    }

    private fun configure(home: File, direct: File) {
        val options = assertIs<CliParseResult.Success>(
            parseCliOptions(arrayOf("session=synthetic-storage", "log=${direct.path}"))
        ).options
        CliDiagnostics.configure(options, home)
    }

    private fun withHome(action: (File) -> Unit) {
        val home = Files.createTempDirectory("p2pkit-cli-storage").toFile()
        try {
            action(home)
        } finally {
            CliDiagnostics.close()
            assertTrue(home.deleteRecursively())
        }
    }
}
