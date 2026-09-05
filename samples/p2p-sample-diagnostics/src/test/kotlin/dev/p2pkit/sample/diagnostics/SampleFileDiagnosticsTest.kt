package dev.p2pkit.sample.diagnostics

import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

class SampleFileDiagnosticsTest {
    @Test
    fun ordinaryReadFailureRemainsAvailableOnlyAsAResult() = runBlocking {
        val failure = IOException("synthetic private filename")
        val result = readSampleFileDiagnostic { throw failure }
        assertSame(failure, result.exceptionOrNull())
    }

    @Test
    fun successfulReadReturnsItsValue() = runBlocking {
        assertEquals("digest", readSampleFileDiagnostic { "digest" }.getOrThrow())
    }

    @Test
    fun callbackCancellationIsNotAnOrdinaryReadFailure() = runBlocking {
        val failure = assertFailsWith<CancellationException> {
            readSampleFileDiagnostic { throw CancellationException("synthetic cancellation") }
        }
        assertEquals("synthetic cancellation", failure.message)
    }

    @Test
    fun alreadyCancelledCallerDoesNotRead() = runBlocking {
        val cancelled = Job().also { it.cancel() }
        var read = false
        assertFailsWith<CancellationException> {
            withContext(cancelled) {
                readSampleFileDiagnostic { read = true }
            }
        }
        assertFalse(read)
    }

    @Test
    fun cancellationDuringAReadCannotPublishAnOrdinaryFailureResult() = runBlocking {
        val entered = CompletableDeferred<Unit>()
        val release = CountDownLatch(1)
        val returnedResult = AtomicBoolean(false)
        val reader = launch {
            readSampleFileDiagnostic {
                entered.complete(Unit)
                check(release.await(5, TimeUnit.SECONDS)) { "test did not release the synthetic read" }
                throw IOException("synthetic failure after cancellation")
            }
            returnedResult.set(true)
        }
        try {
            withTimeout(5_000) { entered.await() }
            reader.cancel()
            release.countDown()
            withTimeout(5_000) { reader.join() }
            assertTrue(reader.isCancelled)
            assertFalse(returnedResult.get())
        } finally {
            release.countDown()
            reader.cancel()
            reader.join()
        }
    }

    @Test
    fun fatalErrorIsNotConvertedIntoAnAbsentDigest() = runBlocking {
        val error = LinkageError("synthetic fatal failure")
        val thrown = assertFailsWith<LinkageError> { readSampleFileDiagnostic { throw error } }
        // Coroutine debug stack recovery may copy a thrown error and retain the original as its cause.
        assertSame(error, thrown.cause ?: thrown)
    }
}
