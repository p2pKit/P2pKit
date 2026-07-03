package dev.p2pkit.core.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.transport.RawConnection
import kotlin.concurrent.Volatile
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Pins the AUDIT-2026-06 close-promptness contract: `session.close()` must
 * return within a bounded time even when the peer has stopped draining and
 * the best-effort CLOSE frame write is wedged in the transport. The old
 * implementation wrapped the CLOSE send in `withTimeoutOrNull`, which cannot
 * interrupt a blocking (cancellation-ignoring) write — close() parked
 * forever. The fixed implementation bounds only the WAIT for the send job and
 * lets `transitionToTerminal`'s `connection.close()` unblock the wedged
 * writer.
 */
class CloseSemanticsTest {

    @Test
    fun closeReturnsPromptlyAndClosesConnectionWhenCloseFrameWriteWedges() {
        runBlocking {
            val connection = WedgedWriteConnection()
            val protocol = DefaultP2pProtocol(clock = { systemTimeMillis() })
            val supervisor = SupervisorJob()
            val scope = CoroutineScope(Dispatchers.Default + supervisor)

            // Hand-fed events channel; nothing arrives, so the only writer in
            // the test window is close()'s CLOSE frame.
            val events = Channel<ProtocolEvent>(Channel.UNLIMITED)

            val session = P2pSessionImpl(
                id = "close-wedged-write",
                peer = Peer(
                    id = PeerId("test-close-wedged"),
                    name = "Test",
                    platform = Platform.JVM_DESKTOP,
                    supportedTransports = setOf(TransportKind.LAN)
                ),
                initialConnection = connection,
                initialEvents = events,
                protocol = protocol,
                parentScope = scope,
                // Long intervals: no spontaneous keep-alive PING competes for
                // the send mutex during the test window.
                keepAlive = KeepAliveConfig(pingIntervalMillis = 60_000, timeoutMillis = 120_000),
                clock = { systemTimeMillis() },
                logger = P2pLogger.NoOp
            )
            session.start()

            try {
                // close() must complete even though the CLOSE frame write
                // parks forever: the bounded wait (CLOSE_FRAME_TIMEOUT_MS,
                // 2 s) gives up and teardown closes the raw connection, which
                // is the one lever that unblocks the wedged writer. 10 s is
                // the generous outer bound — pre-fix, close() never returned
                // and this test hung here.
                withTimeout(10_000) { session.close() }

                // The invariant, not just "it returned": close() completed
                // AND the session/connection are terminal.
                assertEquals(
                    ConnectionState.Closed, session.state.value,
                    "session must end terminal Closed after close()"
                )
                assertEquals(
                    ConnectionState.Closed, connection.state.value,
                    "teardown must close the raw connection (that is what unblocks the wedged write)"
                )
                assertTrue(
                    connection.writeAttempts >= 1,
                    "the best-effort CLOSE frame send must have been attempted (and wedged)"
                )

                // close() stays idempotent after the wedged first call.
                withTimeout(2_000) { session.close() }
                assertEquals(ConnectionState.Closed, session.state.value)
            } finally {
                supervisor.cancel()
            }
        }
    }
}

/**
 * [RawConnection] whose [write] parks forever — NON-cancellably — until
 * [close] releases it. Models blocking socket I/O against a wedged peer: a
 * `java.net.Socket` write parked in a full TCP send window ignores both
 * thread interruption and coroutine cancellation, and the only lever that
 * unblocks it is closing the socket, which makes the write throw.
 */
private class WedgedWriteConnection : RawConnection {

    private val _state = MutableStateFlow(ConnectionState.Connected)
    override val state: StateFlow<ConnectionState> = _state.asStateFlow()

    private val closedGate = CompletableDeferred<Unit>()

    /** How many writes reached the wedge. Single writer (sendMutex) in this test. */
    @Volatile
    var writeAttempts: Int = 0
        private set

    override suspend fun write(bytes: ByteArray) {
        writeAttempts++
        // NonCancellable so a caller-side withTimeout / cancel cannot unblock
        // it — exactly like the real blocking write. Only close() releases it.
        withContext(NonCancellable) { closedGate.await() }
        throw IllegalStateException("connection closed while write was wedged")
    }

    override fun read(): Flow<ByteArray> = emptyFlow()

    override suspend fun close() {
        _state.value = ConnectionState.Closed
        closedGate.complete(Unit)
    }
}
