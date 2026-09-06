package dev.p2pkit.sample.diagnostics

import kotlinx.serialization.decodeFromString
import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

class DiagnosticRecorderClearTest {
    @Test
    fun storageCallbackRunsOutsideStateLockAndLaterRecordsAndSessionChangesSurvive() {
        val persisted = mutableListOf<DiagnosticEvent>()
        val recorder = recorder(sink = { persisted += JSON.decodeFromString<DiagnosticEvent>(it) })
        recorder.startSession("PS-T01", "both", "other")
        recorder.startSession("PS-T01", "both", "selected")
        recorder.record(event("test.before"))
        val callbackFailure = AtomicReference<Throwable?>()

        val removed = recorder.clearCurrentSession { session ->
            assertEquals("selected", session)
            val worker = thread(name = "diagnostic-clear-new-records") {
                try {
                    recorder.record(event("test.after"))
                    recorder.startSession("PS-T01", "both", "new-session")
                    recorder.record(event("test.new_session"))
                } catch (failure: Throwable) {
                    callbackFailure.set(failure)
                }
            }
            worker.join(5_000)
            assertFalse(worker.isAlive, "storage callback must not hold the recorder state lock")
            callbackFailure.get()?.let { throw it }
            assertEquals(listOf(1L, 2L, 3L), persisted.map { it.index }, "sink must remain excluded")
            persisted.removeAll { it.testSessionId == session }
        }

        assertEquals(2, removed)
        assertEquals("new-session", recorder.activeSessionId)
        assertEquals(listOf(1L, 4L, 5L, 6L), recorder.snapshot().map { it.index })
        assertEquals(recorder.snapshot(), persisted)
        assertEquals(0L, recorder.droppedEventCount())
    }

    @Test
    fun failedPersistenceRetainsMemoryAndDrainsDeferredRecordsBeforeRetry() {
        val persisted = mutableListOf<DiagnosticEvent>()
        val recorder = recorder(sink = { persisted += JSON.decodeFromString<DiagnosticEvent>(it) })
        recorder.startSession("PS-T01", "both", "selected")
        val before = recorder.snapshot()
        val failure = IOException("synthetic persistence failure")

        assertSame(failure, assertFailsWith<IOException> {
            recorder.clearCurrentSession {
                recorder.record(event("test.after"))
                assertEquals(before, persisted)
                throw failure
            }
        })

        assertEquals(before, recorder.snapshot().take(before.size))
        assertEquals(recorder.snapshot(), persisted)
        assertEquals(2, recorder.clearCurrentSession { persisted.removeAll { it.testSessionId == "selected" } })
        assertTrue(recorder.snapshot().isEmpty())
        assertTrue(persisted.isEmpty())
        assertEquals(0L, recorder.droppedEventCount())
    }

    @Test
    fun concurrentClearsFailFastAndNewQueuedRecordsAreNotCleared() {
        val recorder = recorder()
        recorder.startSession("PS-T01", "both", "selected")
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val result = AtomicReference<Result<Int>>()
        val worker = thread(name = "diagnostic-clear-owner") {
            result.set(runCatching {
                recorder.clearCurrentSession {
                    entered.countDown()
                    check(release.await(5, TimeUnit.SECONDS))
                }
            })
        }
        try {
            assertTrue(entered.await(5, TimeUnit.SECONDS))
            var secondCallback = false
            assertFailsWith<IOException> { recorder.clearCurrentSession { secondCallback = true } }
            assertFalse(secondCallback)
            recorder.record(event("test.concurrent"))
        } finally {
            release.countDown()
            worker.join(5_000)
            assertFalse(worker.isAlive)
        }
        assertEquals(1, result.get().getOrThrow())
        assertEquals(listOf("test.concurrent"), recorder.snapshot().map { it.eventName })
        assertEquals(1, recorder.clearCurrentSession())
        assertEquals(0L, recorder.droppedEventCount())
    }

    @Test
    fun reentrantSinkAndStorageClearsFailWithoutDeadlockOrPermitLeak() {
        lateinit var recorder: DiagnosticRecorder
        val persisted = mutableListOf<DiagnosticEvent>()
        var reentrantFailure: Throwable? = null
        var forbiddenCallback = false
        recorder = recorder(sink = { json ->
            persisted += JSON.decodeFromString<DiagnosticEvent>(json)
            if (persisted.size == 1) {
                recorder.record(event("test.reentrant"))
                reentrantFailure = runCatching {
                    recorder.clearCurrentSession { forbiddenCallback = true }
                }.exceptionOrNull()
            }
        })
        recorder.startSession("PS-T01", "both", "selected")
        assertTrue(reentrantFailure is IOException)
        assertFalse(forbiddenCallback)
        assertEquals(listOf(1L, 2L), persisted.map { it.index })
        assertEquals(recorder.snapshot(), persisted)

        assertEquals(2, recorder.clearCurrentSession {
            assertFailsWith<IOException> { recorder.clearCurrentSession { forbiddenCallback = true } }
        })
        assertFalse(forbiddenCallback)
        assertEquals(0, recorder.clearCurrentSession())
        assertEquals(0L, recorder.droppedEventCount())
    }

    @Test
    fun reentrantTimestampClearCannotInvokeStorageUnderStateLock() {
        lateinit var recorder: DiagnosticRecorder
        var nestedFailure: Throwable? = null
        var callback = false
        recorder = DiagnosticRecorder(
            environment = environment,
            timestamp = {
                nestedFailure = runCatching { recorder.clearCurrentSession { callback = true } }.exceptionOrNull()
                "2026-09-06T00:00:00Z"
            }
        )
        recorder.startSession("PS-T01", "both", "selected")

        assertTrue(nestedFailure is IOException)
        assertFalse(callback)
        assertEquals(1, recorder.clearCurrentSession())
        assertEquals(0L, recorder.droppedEventCount())
    }

    @Test
    fun clearKeepsPendingQueueCountBoundAndDoesNotChargeIntentionalRemovalAsADrop() {
        val persisted = mutableListOf<DiagnosticEvent>()
        val recorder = recorder(maxEvents = 3, sink = { persisted += JSON.decodeFromString<DiagnosticEvent>(it) })
        recorder.startSession("PS-T01", "both", "selected")

        assertEquals(0, recorder.clearCurrentSession {
            repeat(10) { recorder.record(event("test.queued")) }
            assertEquals(1, persisted.size)
        })

        assertEquals(listOf(1L, 2L, 3L, 4L), persisted.map { it.index })
        assertEquals(listOf(9L, 10L, 11L), recorder.snapshot().map { it.index })
        assertEquals(15L, recorder.droppedEventCount(), "8 ring evictions + 7 queue rejections only")
        recorder.clearCurrentSession()
        assertEquals(15L, recorder.droppedEventCount())
    }

    @Test
    fun clearKeepsPendingQueueByteBoundWhileStorageIsBusy() {
        val persisted = mutableListOf<String>()
        val recorder = recorder(maxEvents = 100, maxBytes = 2_000, sink = { persisted += it })
        recorder.startSession("PS-T01", "both", "selected")
        recorder.clearCurrentSession {
            repeat(20) { recorder.record(event("test.queued")) }
            assertEquals(1, persisted.size)
        }

        val deferred = persisted.drop(1)
        assertTrue(deferred.isNotEmpty())
        assertTrue(deferred.size < 20)
        assertTrue(deferred.sumOf { it.toByteArray().size + 1 } <= 2_000)
        assertTrue(recorder.droppedEventCount() > 0)
        val indexes = persisted.map { JSON.decodeFromString<DiagnosticEvent>(it).index }
        assertEquals(indexes.sorted().distinct(), indexes)
    }

    private fun recorder(
        maxEvents: Int = 5_000,
        maxBytes: Int = 5 * 1024 * 1024,
        sink: (String) -> Unit = {}
    ): DiagnosticRecorder = DiagnosticRecorder(
        environment = environment,
        maxEvents = maxEvents,
        maxEncodedBytes = maxBytes,
        timestamp = { "2026-09-06T00:00:00Z" },
        eventSink = sink
    )

    private fun event(name: String): DiagnosticRecord = DiagnosticRecord(category = "test", eventName = name)

    private companion object {
        val environment = DiagnosticEnvironment("test", "synthetic", "test", "test", "test", "synthetic")
    }
}
