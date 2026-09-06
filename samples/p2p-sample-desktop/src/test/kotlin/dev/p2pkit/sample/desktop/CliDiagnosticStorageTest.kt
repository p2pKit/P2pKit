package dev.p2pkit.sample.desktop

import dev.p2pkit.sample.diagnostics.DiagnosticRecord
import java.io.File
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

class CliDiagnosticStorageTest {
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
