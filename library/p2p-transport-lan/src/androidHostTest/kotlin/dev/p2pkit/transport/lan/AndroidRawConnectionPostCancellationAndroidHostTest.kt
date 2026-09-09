package dev.p2pkit.transport.lan

import dev.p2pkit.core.ConnectionState
import java.io.InputStream
import java.net.Socket
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlin.test.Test
import kotlin.test.assertEquals
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

/** Host execution of Android's shipped raw code; Android logcat/ART behavior is not simulated here. */
class AndroidRawConnectionPostCancellationAndroidHostTest {
    @Test
    fun ordinaryLateFailureDoesNotEscalate() = runBlocking<Unit> {
        val observed = observeCancelledRead { throw IllegalStateException("controlled late read failure") }
        assertTrue(observed.uncaught.isEmpty(), "ordinary teardown failure must not escape its worker")
        assertIs<CancellationException>(observed.completion)
    }

    @Test
    fun lateBytesAndCancellationRemainTerminal() = runBlocking<Unit> {
        val bytes = observeCancelledRead { 17 }
        assertTrue(bytes.uncaught.isEmpty())
        assertIs<CancellationException>(bytes.completion)

        val cancelled = observeCancelledRead { throw CancellationException("controlled read cancellation") }
        assertTrue(cancelled.uncaught.isEmpty())
        assertIs<CancellationException>(cancelled.completion)
    }

    @Test
    fun fatalLateFailureStillEscapesTheWorker() = runBlocking<Unit> {
        val fatal = AssertionError("controlled fatal read failure")
        val observed = observeCancelledRead { throw fatal }
        assertSame(fatal, observed.uncaught.single())
        assertSame(fatal, observed.completion)
    }

    private suspend fun observeCancelledRead(outcome: () -> Int): ReadObservation = coroutineScope {
        val owner = SupervisorJob()
        val uncaught = CopyOnWriteArrayList<Throwable>()
        val scope = CoroutineScope(
            owner + Dispatchers.Default + CoroutineExceptionHandler { _, failure -> uncaught.add(failure) }
        )
        val socket = ControlledReadSocket(outcome)
        val previousEnabled = AndroidLanDiag.enabled
        // Android's ordinary host tests use framework stubs. JVM tests observe the
        // paired opt-in sink; this fixture must not pretend to execute logcat.
        AndroidLanDiag.enabled = false
        val connection = AndroidRawConnection(socket, connectionScopeForTest = scope)
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
                withTimeout(TIMEOUT_MS) { completion.await() }
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
                AndroidLanDiag.enabled = previousEnabled
                socket.close()
            }
        }
    }

    private data class ReadObservation(
        val uncaught: List<Throwable>,
        val completion: Throwable?
    )

    /** Uses the existing Socket constructor seam; no native descriptor or production stream factory is added. */
    private class ControlledReadSocket(private val outcome: () -> Int) : Socket() {
        val readEntered = CompletableDeferred<Unit>()
        val closeCalls = AtomicInteger()
        private val release = CountDownLatch(1)

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
    }
}
