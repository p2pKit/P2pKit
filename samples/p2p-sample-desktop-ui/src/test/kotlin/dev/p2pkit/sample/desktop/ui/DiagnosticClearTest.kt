package dev.p2pkit.sample.desktop.ui

import dev.p2pkit.sample.diagnostics.DiagnosticClearAction
import java.io.File
import java.io.IOException
import java.nio.file.Files
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class DiagnosticClearTest {
    @Test
    fun actualConfirmationKeepsSelectionAndPausedSnapshotOnFailureThenAllowsRetry() {
        val home = Files.createTempDirectory("p2pkit-desktop-clear-action").toFile()
        try {
            val harness = DesktopDiagnosticHarness(home) {}
            val before = harness.recorder.snapshot()
            var selected = before.map { it.index }.toSet()
            var pausedEvents = before
            var status: String? = null
            val obstruction = File(home, ".p2pkit/desktop-ui-test-diagnostics/diagnostic-events.jsonl.1")
            assertTrue(obstruction.mkdir())
            val confirmed: (Int) -> Unit = { count ->
                assertEquals(before.size, count)
                selected = emptySet()
                pausedEvents = emptyList()
                status = "cleared"
            }

            harness.confirmClearCurrent(confirmed) { status = it }

            assertEquals(DiagnosticClearAction.FAILURE_MESSAGE, status)
            assertEquals(before.map { it.index }.toSet(), selected)
            assertEquals(before, pausedEvents)
            assertEquals(before, harness.recorder.snapshot())
            assertTrue(obstruction.delete())
            harness.confirmClearCurrent(confirmed) { status = it }
            assertEquals("cleared", status)
            assertTrue(selected.isEmpty())
            assertTrue(pausedEvents.isEmpty())
            assertTrue(harness.recorder.snapshot().isEmpty())
        } finally {
            assertTrue(home.deleteRecursively())
        }
    }

    @Test
    fun storageFailurePreservesRecorderUntilRetrySucceeds() {
        val home = Files.createTempDirectory("p2pkit-desktop-clear").toFile()
        try {
            val harness = DesktopDiagnosticHarness(home) {}
            val before = harness.recorder.snapshot()
            val obstruction = File(home, ".p2pkit/desktop-ui-test-diagnostics/diagnostic-events.jsonl.1")
            assertTrue(obstruction.mkdir())

            assertFailsWith<IOException> { harness.clearCurrent() }
            assertEquals(before, harness.recorder.snapshot())
            assertTrue(obstruction.delete())
            assertEquals(before.size, harness.clearCurrent())
            assertTrue(harness.recorder.snapshot().isEmpty())
        } finally {
            assertTrue(home.deleteRecursively())
        }
    }
}
