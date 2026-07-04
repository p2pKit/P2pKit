package dev.p2pkit.transport.lan

import dev.p2pkit.core.ConnectionState
import java.io.Closeable
import java.io.IOException
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.ServerSocket
import java.net.Socket
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

/**
 * 2026-07 P1-15 (CON-14): transport-level coverage for the V0.6-WRITE-TIMEOUT
 * watchdog on the REAL [JvmRawConnection] over a real loopback TCP pair — the
 * f4dd3a9 mechanism previously had only a FakeRawConnection-driven test.
 * Exercised via the AUDIT-2026-07 (CON-14) injectable-timeout seam
 * (production call sites keep the 30 s default; `AndroidRawConnection` is the
 * behavior-parity twin changed in lockstep).
 *
 * Pins the row's three observables for a wedged write: IOException surfaced
 * to the caller, `socket.isClosed`, and `ConnectionState.Closed` — plus the
 * false-positive guard (a draining peer under the same short deadline
 * completes normally and the socket stays open).
 */
class JvmRawConnectionWriteWatchdogTest {

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

    /**
     * Small socket buffers on both ends so a multi-megabyte write cannot be
     * absorbed by the kernel: once the peer's receive buffer and our send
     * buffer are full, `OutputStream.write` parks exactly like the field
     * failure mode (peer's TCP receive window wedged).
     */
    private fun openThrottledLoopbackPair(): LoopbackPair {
        val server = ServerSocket()
        server.receiveBufferSize = SMALL_BUFFER_BYTES
        server.bind(InetSocketAddress(InetAddress.getLoopbackAddress(), 0), 1)
        val local = Socket()
        local.sendBufferSize = SMALL_BUFFER_BYTES
        local.connect(
            InetSocketAddress(InetAddress.getLoopbackAddress(), server.localPort),
            CONNECT_TIMEOUT_MS
        )
        val remote = server.accept()
        return LoopbackPair(server, local, remote)
    }

    @Test
    fun wedgedWriteTimesOutClosesSocketAndReportsClosed() {
        runBlocking {
            openThrottledLoopbackPair().use { pair ->
                // The remote NEVER reads: the write must park, the watchdog
                // must fire at the injected deadline and close the socket.
                val connection = JvmRawConnection(pair.local, writeTimeoutMillis = SHORT_TIMEOUT_MS)
                val payload = ByteArray(WEDGE_PAYLOAD_BYTES)

                val error = assertFailsWith<IOException>("wedged write must surface an IOException") {
                    withTimeout(TEST_BOUND_MS) { connection.write(payload) }
                }
                assertTrue(
                    error.message.orEmpty().contains("timed out"),
                    "watchdog outcome must be reported as the timeout, not a raw close error " +
                        "(was: ${error.message})"
                )
                assertTrue(pair.local.isClosed, "the watchdog must release the wedged socket fd")
                assertEquals(ConnectionState.Closed, connection.state.value)
            }
        }
    }

    @Test
    fun drainingPeerWriteCompletesWithinInjectedTimeoutAndSocketStaysOpen() {
        runBlocking {
            openThrottledLoopbackPair().use { pair ->
                val connection = JvmRawConnection(pair.local, writeTimeoutMillis = SHORT_TIMEOUT_MS)
                val payload = ByteArray(WEDGE_PAYLOAD_BYTES)

                // A peer that drains keeps the write moving; the watchdog must
                // NOT fire (false-positive guard on the CAS race).
                val drainer = launch(Dispatchers.IO) {
                    val sink = ByteArray(64 * 1024)
                    val input = pair.remote.getInputStream()
                    var total = 0L
                    while (total < payload.size) {
                        val n = input.read(sink)
                        if (n < 0) break
                        total += n
                    }
                }

                withTimeout(TEST_BOUND_MS) { connection.write(payload) }
                drainer.join()

                assertFalse(pair.local.isClosed, "a completed write must leave the socket open")
                assertEquals(ConnectionState.Connected, connection.state.value)
                connection.close()
            }
        }
    }

    private companion object {
        const val CONNECT_TIMEOUT_MS = 5_000
        const val TEST_BOUND_MS = 30_000L

        /** Injected watchdog deadline — long enough for a draining peer, short enough to test. */
        const val SHORT_TIMEOUT_MS = 1_500L

        /** Kernel-buffer hint keeping the unread backlog far below the payload size. */
        const val SMALL_BUFFER_BYTES = 16 * 1024

        /** Comfortably exceeds both kernel buffers even if the OS inflates the hints. */
        const val WEDGE_PAYLOAD_BYTES = 8 * 1024 * 1024
    }
}
