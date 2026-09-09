package dev.p2pkit.sample.diagnostics

import java.io.IOException
import java.nio.file.Files
import java.util.zip.ZipFile
import kotlinx.serialization.decodeFromString
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertSame
import kotlin.test.assertTrue

class DiagnosticDropAttributionTest {
    @Test
    fun retainedSessionEvictionsNeverContaminateTheCleanSessionOrItsActualExport() {
        val recorder = recorder(maxEvents = 4)
        recorder.startSession("PS-T01", "both", "session-a")
        repeat(8) { recorder.record(event) }
        recorder.completeSession(DiagnosticOutcome.SUCCESS, "done", "complete")
        assertEquals(6L, recorder.summary("session-a").droppedEventCount)
        recorder.startSession("PS-T02", "both", "session-b")
        recorder.completeSession(DiagnosticOutcome.SUCCESS, "done", "complete")
        assertEquals(8L, recorder.summary("session-a").droppedEventCount)
        assertEquals(0L, recorder.summary("session-b").droppedEventCount)

        val directory = Files.createTempDirectory("diagnostic-session-drop-export").toFile()
        try {
            val archive = DiagnosticEvidenceExporter.export(recorder, directory)
            val summary = ZipFile(archive).use { zip ->
                JSON.decodeFromString<DiagnosticSessionSummary>(
                    zip.getInputStream(zip.getEntry("summary.json")).bufferedReader().use { it.readText() }
                )
            }
            assertEquals("session-b", summary.testSessionId)
            assertEquals(0L, summary.droppedEventCount)
            assertTrue(DiagnosticEvidenceExporter.verifyChecksums(archive))
            // The export marker evicts another A event, not a B event.
            assertEquals(9L, recorder.summary("session-a").droppedEventCount)
            assertEquals(0L, recorder.summary("session-b").droppedEventCount)
            assertEquals(9L, recorder.droppedEventCount())
        } finally {
            assertTrue(directory.deleteRecursively())
        }
    }

    @Test
    fun aLateSinkFailureStaysWithTheQueuedOwnerAfterTheSessionChanges() {
        lateinit var recorder: DiagnosticRecorder
        var first = true
        recorder = recorder(sink = {
            if (first) {
                first = false
                recorder.startSession("PS-T02", "both", "session-b")
                recorder.completeSession(DiagnosticOutcome.SUCCESS, "done", "complete")
                throw IOException("synthetic late A failure")
            }
        })
        recorder.startSession("PS-T01", "both", "session-a")
        assertEquals("session-b", recorder.activeSessionId)
        assertEquals(1L, recorder.summary("session-a").droppedEventCount)
        assertEquals(0L, recorder.summary("session-b").droppedEventCount)
        assertEquals(1L, recorder.droppedEventCount())
    }

    @Test
    fun invalidInputAndLaterUnrelatedFailuresDoNotInflateACompletedSession() {
        var invalidTimestamp = false
        val recorder = recorder(timestamp = {
            check(!invalidTimestamp) { "synthetic unencodable input" }
            "2026-09-09T00:00:00Z"
        })
        recorder.startSession("PS-T01", "both", "session-a")
        recorder.completeSession(DiagnosticOutcome.SUCCESS, "done", "complete")
        recorder.startSession("PS-T02", "both", "session-b")
        invalidTimestamp = true
        recorder.record(event)
        invalidTimestamp = false
        recorder.completeSession(DiagnosticOutcome.SUCCESS, "done", "complete")
        assertEquals(0L, recorder.summary("session-a").droppedEventCount)
        assertEquals(1L, recorder.summary("session-b").droppedEventCount)
        // Same identifier means the same retained evidence, not a chance to erase its losses.
        recorder.startSession("PS-T02", "both", "session-b")
        assertEquals(1L, recorder.summary("session-b").droppedEventCount)
    }

    @Test
    fun queueRejectionsAndRetentionEvictionsChargeTheirEventOwners() {
        lateinit var recorder: DiagnosticRecorder
        var first = true
        recorder = recorder(maxEvents = 3, sink = {
            if (first) {
                first = false
                recorder.startSession("PS-T02", "both", "session-b")
                repeat(3) { recorder.record(event) }
                throw IOException("synthetic late A failure")
            }
        })
        recorder.startSession("PS-T01", "both", "session-a")
        assertEquals(2L, recorder.summary("session-a").droppedEventCount, "A eviction and A sink failure")
        assertEquals(2L, recorder.summary("session-b").droppedEventCount, "B eviction and B queue rejection")
        assertEquals(4L, recorder.droppedEventCount())
    }

    @Test
    fun successfulClearDropsOldAccountingButKeepsEveryPostBoundaryLoss() {
        val recorder = recorder(maxEvents = 3)
        recorder.startSession("PS-T01", "both", "selected")
        repeat(3) { recorder.record(event) }
        assertEquals(1L, recorder.summary().droppedEventCount)
        assertEquals(0, recorder.clearCurrentSession { repeat(4) { recorder.record(event) } })
        assertEquals(2L, recorder.summary().droppedEventCount, "one new eviction and one new queue rejection")
        assertEquals(6L, recorder.droppedEventCount(), "lifetime total still includes cleared old losses")
        assertEquals(listOf(6L, 7L, 8L), recorder.snapshot().map { it.index })
        assertEquals(3, recorder.clearCurrentSession())
        assertEquals(0L, recorder.summary().droppedEventCount)
        assertEquals(6L, recorder.droppedEventCount())
    }

    @Test
    fun failedClearKeepsOldAndConcurrentLossesAndSupportsATruthfulRetry() {
        val recorder = recorder(maxEvents = 3)
        recorder.startSession("PS-T01", "both", "selected")
        repeat(3) { recorder.record(event) }
        val failure = IOException("synthetic storage obstruction")
        assertSame(failure, assertFailsWith<IOException> {
            recorder.clearCurrentSession {
                repeat(4) { recorder.record(event) }
                throw failure
            }
        })
        assertEquals(6L, recorder.summary().droppedEventCount)
        assertEquals(6L, recorder.droppedEventCount())
        recorder.clearCurrentSession()
        assertEquals(0L, recorder.summary().droppedEventCount)
        assertEquals(6L, recorder.droppedEventCount())
    }

    @Test
    fun clearOfTheCapturedOwnerDoesNotResetANewerSession() {
        var invalidTimestamp = false
        val recorder = recorder(timestamp = {
            check(!invalidTimestamp)
            "2026-09-09T00:00:00Z"
        })
        recorder.startSession("PS-T01", "both", "session-a")
        invalidTimestamp = true
        recorder.record(event)
        invalidTimestamp = false
        recorder.clearCurrentSession {
            recorder.startSession("PS-T02", "both", "session-b")
            invalidTimestamp = true
            recorder.record(event)
            invalidTimestamp = false
        }
        assertEquals(0L, recorder.summary("session-a").droppedEventCount)
        assertEquals(1L, recorder.summary("session-b").droppedEventCount)
        assertEquals(2L, recorder.droppedEventCount())
    }

    @Test
    fun sessionLimitEvictionIsChargedAndAccountingDoesNotGrowWithoutBound() {
        val recorder = recorder(maxSessions = 1)
        recorder.startSession("PS-T01", "both", "session-a")
        recorder.completeSession(DiagnosticOutcome.SUCCESS, "done", "complete")
        recorder.startSession("PS-T02", "both", "session-b")
        assertEquals(2L, recorder.summary("session-a").droppedEventCount)
        assertEquals(0L, recorder.summary("session-b").droppedEventCount)
        repeat(100) { recorder.startSession("PS-T02", "both", "new-$it") }
        assertEquals(setOf("new-99"), recorder.snapshot().map { it.testSessionId }.toSet())
        // Structural bound assertion avoids introducing another unused diagnostics API.
        val accounting = DiagnosticRecorder::class.java.getDeclaredField("droppedEventsBySession")
        accounting.isAccessible = true
        assertTrue((accounting.get(recorder) as Map<*, *>).size <= 3)
    }

    private fun recorder(
        maxEvents: Int = 100,
        maxSessions: Int = 8,
        timestamp: () -> String = { "2026-09-09T00:00:00Z" },
        sink: (String) -> Unit = {}
    ) = DiagnosticRecorder(
        environment = DiagnosticEnvironment("test", "synthetic", "test", "test", "test", "synthetic"),
        maxEvents = maxEvents,
        maxSessions = maxSessions,
        timestamp = timestamp,
        eventSink = sink
    )

    private companion object {
        val event = DiagnosticRecord(category = "test", eventName = "test.synthetic")
    }
}
