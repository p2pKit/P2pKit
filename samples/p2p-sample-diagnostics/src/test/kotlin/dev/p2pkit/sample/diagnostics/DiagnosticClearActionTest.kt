package dev.p2pkit.sample.diagnostics

import java.io.IOException
import java.io.InterruptedIOException
import java.nio.channels.ClosedByInterruptException
import java.util.concurrent.CancellationException
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

class DiagnosticClearActionTest {
    @Test
    fun storageFailureDoesNotInvokeSuccessOrExposeRawErrorDetailsAndCanBeRetried() {
        var selected = setOf(1L, 2L)
        var paused = listOf("synthetic-event")
        var status: String? = null
        var fail = true
        val clear = { if (fail) throw IOException("private/path\nprivate-log-detail") else 2 }
        val confirmed: (Int) -> Unit = { count ->
            assertEquals(2, count)
            selected = emptySet()
            paused = emptyList()
            status = "cleared"
        }

        DiagnosticClearAction.confirm(clear, confirmed) { status = it }
        assertEquals(setOf(1L, 2L), selected)
        assertEquals(listOf("synthetic-event"), paused)
        assertEquals(DiagnosticClearAction.FAILURE_MESSAGE, status)
        assertFalse(status!!.contains("private"))
        fail = false
        DiagnosticClearAction.confirm(clear, confirmed) { status = it }
        assertTrue(selected.isEmpty())
        assertTrue(paused.isEmpty())
        assertEquals("cleared", status)
    }

    @Test
    fun cancellationAndInterruptionPropagateWithoutPresentationCallbacks() {
        val failures = listOf(
            CancellationException("synthetic"), InterruptedException("synthetic"),
            InterruptedIOException("synthetic"), ClosedByInterruptException()
        )
        for (failure in failures) {
            var callback = false
            try {
                assertSame(failure, assertFails {
                    DiagnosticClearAction.confirm(
                        clear = { throw failure }, onCleared = { callback = true }, onFailure = { callback = true }
                    )
                })
                assertFalse(callback)
                assertEquals(failure !is CancellationException, Thread.currentThread().isInterrupted)
            } finally {
                Thread.interrupted()
            }
        }
    }

    @Test
    fun anAlreadyInterruptedOperationDoesNotBecomeAnOrdinaryStorageError() {
        var started = false
        var callback = false
        try {
            Thread.currentThread().interrupt()
            assertFailsWith<InterruptedException> {
                DiagnosticClearAction.confirm(
                    clear = { started = true; 0 }, onCleared = { callback = true }, onFailure = { callback = true }
                )
            }
            assertTrue(Thread.currentThread().isInterrupted)
            assertFalse(started)
            assertFalse(callback)
        } finally {
            Thread.interrupted()
        }
    }

    @Test
    fun postCommitPresentationFailureIsNotMisreportedAsAStorageFailure() {
        val failure = IllegalStateException("synthetic callback failure")
        var failedStorage = false
        assertSame(failure, assertFails {
            DiagnosticClearAction.confirm(
                clear = { 1 }, onCleared = { throw failure }, onFailure = { failedStorage = true }
            )
        })
        assertFalse(failedStorage)
    }
}
