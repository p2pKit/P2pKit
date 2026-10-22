package dev.p2pkit.core.transfer

import java.io.IOException
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.io.Buffer
import kotlinx.io.RawSource
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Real coroutine dispatch/ownership, with an inert source instead of Android framework descriptors. */
class OwnedUriSourceAndroidHostTest {
    @Test
    fun cancelledEntryClosesBeforeAnyHashOrTransferHandoff() = runBlocking {
        val source = TrackedSource()
        var hashes = 0
        var handedOff = false
        val task = launch(start = CoroutineStart.UNDISPATCHED) {
            coroutineContext[Job]!!.cancel()
            try {
                prepareOwnedUriSource(source) { hashes++; 1 }
                handedOff = true
            } catch (_: CancellationException) {
                assertEquals(listOf("stream", "descriptor"), source.closes)
            }
        }
        task.join()
        assertTrue(task.isCancelled)
        assertEquals(0, hashes)
        assertFalse(handedOff)
        assertEquals(listOf("stream", "descriptor"), source.closes)
    }

    @Test
    fun successfulPreparationClosesExactlyOnceBeforeHandoff() = runBlocking {
        val source = TrackedSource()
        assertEquals(7, prepareOwnedUriSource(source) { assertSame(source, it); 7 })
        assertEquals(listOf("stream", "descriptor"), source.closes)
    }

    @Test
    fun hashFailureRemainsPrimaryWhenCloseAlsoFails() = runBlocking {
        val failure = IOException("hash failed")
        val closeFailure = IOException("close failed")
        val source = TrackedSource(closeFailure)
        val thrown = try {
            prepareOwnedUriSource(source) { throw failure }
        } catch (error: Throwable) { error }
        // Coroutine debug recovery may copy an exception across withContext, retaining its cause.
        assertSame(failure, thrown.cause ?: thrown)
        assertEquals(listOf(closeFailure), thrown.suppressedExceptions)
        assertEquals(listOf("stream", "descriptor"), source.closes)
    }

    @Test
    fun cancellationDuringHashClosesAndDoesNotBecomeAnOrdinaryFailure() = runBlocking {
        val cancellation = CancellationException("hash cancelled")
        val closeFailure = IOException("close failed")
        val source = TrackedSource(closeFailure)
        val thrown = try {
            prepareOwnedUriSource(source) { throw cancellation }
        } catch (error: Throwable) { error }
        assertSame(cancellation, thrown.cause ?: thrown)
        assertEquals(listOf(closeFailure), thrown.suppressedExceptions)
        assertEquals(listOf("stream", "descriptor"), source.closes)
    }

    @Test
    fun cancelledReturnClosesEvenWhenHashReturnsNormally() = runBlocking {
        val source = TrackedSource()
        var hashes = 0
        var handedOff = false
        val task = launch {
            val owner = coroutineContext[Job]!!
            prepareOwnedUriSource(source) { hashes++; owner.cancel(); 1 }
            handedOff = true
        }
        task.join()
        assertTrue(task.isCancelled)
        assertEquals(1, hashes)
        assertFalse(handedOff)
        assertEquals(listOf("stream", "descriptor"), source.closes)
    }

    @Test
    fun closeFailurePreventsSuccessfulHandoff() = runBlocking {
        val failure = IOException("close failed")
        val source = TrackedSource(failure)
        var handedOff = false
        val thrown = try {
            prepareOwnedUriSource(source) { 1 }
            handedOff = true
            null
        } catch (error: Throwable) { error }
        assertSame(failure, thrown)
        assertFalse(handedOff)
        assertEquals(listOf("stream", "descriptor"), source.closes)
    }

    private class TrackedSource(private val closeFailure: Throwable? = null) : RawSource {
        val closes = mutableListOf<String>()
        override fun readAtMostTo(sink: Buffer, byteCount: Long): Long = -1L
        override fun close() {
            try {
                closes += "stream"
                closeFailure?.let { throw it }
            } finally {
                closes += "descriptor"
            }
        }
    }
}
