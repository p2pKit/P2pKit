package dev.p2pkit.transport.lan

import dev.p2pkit.core.ConnectionState
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import java.io.Closeable
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * AUDIT-2026-07 (CON-1) regression tests: connection cleanup must release the
 * socket fd even when the coroutine driving it is cancelled.
 *
 * Drives [JvmRawConnection] directly over a real loopback TCP pair (same
 * approach as `JvmLanLoopbackTest.remoteDisconnectClosesLocalSocketFd`): the
 * socket is the exact resource the fix protects and `Socket.isClosed` is the
 * direct observable — assertions are on resource state, never on the mere
 * absence of exceptions. `AndroidRawConnection` is the intentionally
 * duplicated behavior-parity twin, changed in lockstep; this JVM test covers
 * the shared shape (there are no instrumented Android tests).
 */
class JvmRawConnectionCancellationTest {

    private class LoopbackPair(
        val server: ServerSocket,
        val local: Socket,
        val remote: Socket
    ) : Closeable {
        override fun close() {
            runCatching { local.close() }
            runCatching { remote.close() }
            runCatching { server.close() }
        }
    }

    private fun openLoopbackPair(): LoopbackPair {
        val server = ServerSocket(0, 1, InetAddress.getLoopbackAddress())
        val local = Socket()
        local.connect(
            InetSocketAddress(InetAddress.getLoopbackAddress(), server.localPort),
            CONNECT_TIMEOUT_MS
        )
        val remote = server.accept()
        return LoopbackPair(server, local, remote)
    }

    /**
     * P1-16 clause 1: `close()` issued from an already-cancelled coroutine
     * still releases the fd. Pre-fix, the `withContext(Dispatchers.IO)` hop
     * inside `close()` threw CancellationException on entry without running
     * `closeSocketOnce()` — the exact shape of session teardown
     * (`SessionManager` / `P2pSessionImpl`) closing a connection from a
     * cancelling scope, which leaked the fd and the watchdog scope.
     */
    @Test
    fun closeFromAlreadyCancelledCoroutineStillReleasesSocketFd() {
        runBlocking {
            openLoopbackPair().use { pair ->
                val connection = JvmRawConnection(pair.local)
                val started = CompletableDeferred<Unit>()
                val cleanupRan = CompletableDeferred<Unit>()
                val job = launch {
                    try {
                        started.complete(Unit)
                        awaitCancellation()
                    } finally {
                        // This block runs inside an already-cancelled
                        // coroutine, mirroring production teardown. The
                        // runCatching only keeps the test flow deterministic;
                        // the invariant asserted below is the observable
                        // socket state, not the exception disposition.
                        runCatching { connection.close() }
                        cleanupRan.complete(Unit)
                    }
                }
                withTimeout(TIMEOUT_MS) { started.await() }
                job.cancelAndJoin()
                withTimeout(TIMEOUT_MS) { cleanupRan.await() }

                assertTrue(
                    pair.local.isClosed,
                    "close() from an already-cancelled coroutine must release the socket fd"
                )
                assertEquals(ConnectionState.Closed, connection.state.value)
            }
        }
    }

    /**
     * P1-16 clause 2: a cancelled read collector followed by a remote close
     * still ends with the local fd released. Pre-fix, the collector's
     * CancellationException propagated out of the read flow past the terminal
     * `closeSocketOnce()`, leaving the fd open until GC.
     */
    @Test
    fun cancellingReadCollectorImmediatelyReleasesSocketFd() {
        runBlocking {
            openLoopbackPair().use { pair ->
                val connection = JvmRawConnection(pair.local)
                val firstChunk = CompletableDeferred<Unit>()
                val reader = launch {
                    connection.read().collect { firstChunk.complete(Unit) }
                }
                // Rendezvous: prove the collector is live (it has delivered a
                // chunk and is back in the blocking read) before cancelling.
                pair.remote.getOutputStream().apply {
                    write(byteArrayOf(1))
                    flush()
                }
                withTimeout(TIMEOUT_MS) { firstChunk.await() }

                reader.cancel()
                // Cancellation itself must close the local socket and unblock
                // SocketInputStream.read(); no remote action is required.
                withTimeout(TIMEOUT_MS) { reader.join() }

                assertTrue(
                    pair.local.isClosed,
                    "cancelled read collector must release the local socket fd"
                )
                assertEquals(ConnectionState.Closed, connection.state.value)
            }
        }
    }

    private companion object {
        const val CONNECT_TIMEOUT_MS = 5_000
        const val TIMEOUT_MS = 10_000L
    }
}
