package dev.p2pkit.transport.lan

import dev.p2pkit.core.ConnectionState
import java.io.IOException
import java.io.InputStream
import java.net.Socket
import java.net.SocketAddress
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout

class JvmRawConnectionPostCancellationTest {
    @Test
    fun ordinaryLateFailuresAreAttributedWithoutEscalating() = runBlocking<Unit> {
        for (failure in listOf(IOException(PRIVATE_DETAIL), IllegalStateException(PRIVATE_DETAIL))) {
            val observed = observeCancelledRead { throw failure }

            assertTrue(observed.uncaught.isEmpty(), "ordinary teardown failure must not escape its worker")
            assertIs<CancellationException>(observed.completion)
            val line = observed.diagnostics.single { "post-cancellation read failure:" in it }
            assertTrue(failure::class.simpleName.orEmpty() in line)
            assertFalse(PRIVATE_DETAIL in line, "diagnostics must not include exception messages")
        }
    }

    @Test
    fun bytesReturnedAfterCancellationAreDiscardedAndCounted() = runBlocking<Unit> {
        val observed = observeCancelledRead { 17 }

        assertTrue(observed.uncaught.isEmpty())
        assertIs<CancellationException>(observed.completion)
        assertTrue(observed.diagnostics.any { "discarded 17B read after cancellation" in it })
    }

    @Test
    fun cancellationRemainsSilentAndFatalErrorsStillEscapeTheWorker() = runBlocking<Unit> {
        val cancelled = observeCancelledRead { throw CancellationException("controlled read cancellation") }
        assertTrue(cancelled.uncaught.isEmpty())
        assertIs<CancellationException>(cancelled.completion)
        assertTrue(cancelled.diagnostics.none { "post-cancellation read failure:" in it })

        val fatal = AssertionError("controlled fatal read failure")
        val failed = observeCancelledRead { throw fatal }
        assertSame(fatal, failed.uncaught.single())
        assertSame(fatal, failed.completion)
        assertTrue(failed.diagnostics.none { "post-cancellation read failure:" in it })
    }

    private suspend fun observeCancelledRead(outcome: () -> Int): ReadObservation = coroutineScope {
        val owner = SupervisorJob()
        val uncaught = CopyOnWriteArrayList<Throwable>()
        val scope = CoroutineScope(
            owner + Dispatchers.Default + CoroutineExceptionHandler { _, failure -> uncaught.add(failure) }
        )
        val marker = "cancelled-read-${System.nanoTime()}"
        val socket = ControlledReadSocket(marker, outcome)
        val previousEnabled = JvmLanDiag.enabled
        JvmLanDiag.enabled = true
        val connection = JvmRawConnection(socket, connectionScopeForTest = scope)
        val deliveredChunks = AtomicInteger()
        val collector = launch(start = CoroutineStart.UNDISPATCHED) {
            connection.read().collect { deliveredChunks.incrementAndGet() }
        }
        try {
            withTimeout(TIMEOUT_MS) { socket.readEntered.await() }
            val worker = owner.children.single()
            val completion = CompletableDeferred<Throwable?>()
            worker.invokeOnCompletion { completion.complete(it) }

            collector.cancel()
            withTimeout(TIMEOUT_MS) { collector.join() }
            assertTrue(socket.isClosed, "cancelling the collector must close the socket before the late result")
            assertEquals(ConnectionState.Closed, connection.state.value)
            // The worker cannot produce its outcome until cancellation has made the
            // continuation inactive and the synchronous socket-close callback has returned.
            socket.releaseRead()
            withTimeout(TIMEOUT_MS) { worker.join() }
            connection.close()
            connection.close()

            assertEquals(1, socket.closeCalls.get(), "all terminal paths must share the close-once gate")
            assertEquals(0, deliveredChunks.get(), "cancelled reads must never deliver stale bytes")
            ReadObservation(
                uncaught.toList(),
                withTimeout(TIMEOUT_MS) { completion.await() },
                JvmLanDiag.events.replayCache.filter { marker in it }
            )
        } finally {
            socket.releaseRead()
            connection.close()
            try {
                withContext(NonCancellable) {
                    withTimeout(TIMEOUT_MS) {
                        collector.cancelAndJoin()
                        owner.cancelAndJoin()
                    }
                }
            } finally {
                JvmLanDiag.enabled = previousEnabled
                socket.close()
            }
        }
    }

    private data class ReadObservation(
        val uncaught: List<Throwable>,
        val completion: Throwable?,
        val diagnostics: List<String>
    )

    /** Uses the existing Socket constructor seam; no native descriptor or production stream factory is added. */
    private class ControlledReadSocket(marker: String, private val outcome: () -> Int) : Socket() {
        val readEntered = CompletableDeferred<Unit>()
        val closeCalls = AtomicInteger()
        private val release = CountDownLatch(1)
        private val address = object : SocketAddress() {
            override fun toString(): String = marker
        }

        override fun getRemoteSocketAddress(): SocketAddress = address

        override fun getInputStream(): InputStream = object : InputStream() {
            override fun read(): Int = error("The transport must use its byte-array read")

            override fun read(bytes: ByteArray, offset: Int, length: Int): Int {
                readEntered.complete(Unit)
                if (!release.await(TIMEOUT_MS, TimeUnit.MILLISECONDS)) {
                    throw AssertionError("Controlled read was not released within the fixture deadline")
                }
                return outcome()
            }
        }

        fun releaseRead() {
            release.countDown()
        }

        override fun close() {
            closeCalls.incrementAndGet()
            super.close()
        }
    }

    private companion object {
        const val TIMEOUT_MS = 10_000L
        const val PRIVATE_DETAIL = "private exception detail must not appear in diagnostics"
    }
}
