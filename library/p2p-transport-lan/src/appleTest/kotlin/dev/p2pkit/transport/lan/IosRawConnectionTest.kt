@file:OptIn(ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportHint
import dev.p2pkit.transport.lan.interop.p2pkit_nw_create_plain_tcp_parameters
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertTrue
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import platform.Network.nw_connection_create
import platform.Network.nw_endpoint_create_host
import platform.darwin.dispatch_queue_create

/**
 * Direct unit tests for [IosRawConnection]'s local close/cancel latch —
 * the pure-logic paths that need no live peer:
 *
 * - [IosRawConnection.close] / [IosRawConnection.cancelNow] flip the state
 *   to [ConnectionState.Closed] synchronously and are idempotent
 *   (cancelOnce is CAS-guarded).
 * - `write()` on a closed connection is refused promptly — it must throw
 *   from the entry `closed` check without ever suspending into the
 *   nw_connection_send await.
 * - A write whose connection never leaves `Connecting` reaches one terminal
 *   timeout, cancels its native handle, and cannot repeat the full wait.
 *   (The separate V0.6-WRITE-TIMEOUT send-completion deadline still needs a
 *   wedged live peer and is covered by external fault injection.)
 *
 * The connection dials 127.0.0.1:9 (discard port; nothing listens there in
 * the simulator). The dial's outcome is irrelevant — every assertion
 * targets the local latch, never a successful round-trip, so there is no
 * network-timing flake surface.
 */
class IosRawConnectionTest {

    private fun newStartedConnection(): IosRawConnection {
        val params = p2pkit_nw_create_plain_tcp_parameters()
            ?: error("p2pkit_nw_create_plain_tcp_parameters returned null")
        val endpoint = nw_endpoint_create_host("127.0.0.1", "9")
            ?: error("nw_endpoint_create_host returned null")
        val conn = nw_connection_create(endpoint, params)
            ?: error("nw_connection_create returned null")
        val queue = dispatch_queue_create("dev.p2pkit.test.rawconn", null)
        return IosRawConnection.wrap(conn, queue)
    }

    private fun newWriteControlledConnection(
        send: suspend (ByteArray) -> Unit
    ): IosRawConnection {
        val params = p2pkit_nw_create_plain_tcp_parameters()
            ?: error("p2pkit_nw_create_plain_tcp_parameters returned null")
        val endpoint = nw_endpoint_create_host("127.0.0.1", "9")
            ?: error("nw_endpoint_create_host returned null")
        val conn = nw_connection_create(endpoint, params)
            ?: error("nw_connection_create returned null")
        val queue = dispatch_queue_create("dev.p2pkit.test.rawconn.write", null)
        return IosRawConnection.wrapForWriteTest(conn, queue, send)
    }

    private fun newWedgedConnectingConnection(
        writeReadyTimeoutMillis: Long = 25
    ): IosRawConnection {
        val params = p2pkit_nw_create_plain_tcp_parameters()
            ?: error("p2pkit_nw_create_plain_tcp_parameters returned null")
        val endpoint = nw_endpoint_create_host("127.0.0.1", "9")
            ?: error("nw_endpoint_create_host returned null")
        val conn = nw_connection_create(endpoint, params)
            ?: error("nw_connection_create returned null")
        val queue = dispatch_queue_create("dev.p2pkit.test.rawconn.connecting", null)
        return IosRawConnection.wrapConnectingForTest(
            connection = conn,
            queue = queue,
            writeReadyTimeoutMillis = writeReadyTimeoutMillis
        )
    }

    @Test
    fun writeAfterCloseIsRefusedPromptly() = runBlocking {
        val raw = newStartedConnection()
        raw.close()
        assertEquals(ConnectionState.Closed, raw.state.value)
        // withTimeout bounds "promptly": the refuse path must throw from the
        // entry check, never suspend into the send await.
        val e = withTimeout(2_000) {
            assertFailsWith<IllegalStateException> { raw.write(byteArrayOf(1, 2, 3)) }
        }
        assertEquals("connection closed", e.message)
    }

    @Test
    fun cancelNowLatchesClosedSynchronouslyAndIsIdempotent() = runBlocking {
        val raw = newStartedConnection()
        raw.cancelNow("test: inbound dropped")
        assertEquals(ConnectionState.Closed, raw.state.value)
        // Repeat cancels and a later close() are safe no-ops (CAS-guarded).
        raw.cancelNow("test: again")
        raw.close()
        assertEquals(ConnectionState.Closed, raw.state.value)
        val e = withTimeout(2_000) {
            assertFailsWith<IllegalStateException> { raw.write(byteArrayOf(1)) }
        }
        assertEquals("connection closed", e.message)
    }

    @Test
    fun writeReadyTimeoutIsTerminalAndCannotRepeatTheWedge() = runBlocking {
        val raw = newWedgedConnectingConnection()

        val timeout = assertFailsWith<IllegalStateException> {
            raw.write(byteArrayOf(1, 2, 3))
        }
        assertTrue(timeout.message.orEmpty().contains("25ms"))
        assertEquals(ConnectionState.Closed, raw.state.value)

        val repeated = withTimeout(2_000) {
            assertFailsWith<IllegalStateException> { raw.write(byteArrayOf(4)) }
        }
        assertEquals("connection closed", repeated.message)
    }

    @Test
    fun callerTimeoutIsNotReclassifiedAsWriteReadyTimeout() = runBlocking {
        val raw = newWedgedConnectingConnection(writeReadyTimeoutMillis = 5_000)

        assertFailsWith<TimeoutCancellationException> {
            withTimeout(CALLER_TIMEOUT_MILLIS) {
                raw.write(byteArrayOf(1, 2, 3))
            }
        }
        assertEquals(
            ConnectionState.Connecting,
            raw.state.value,
            "caller-owned timeout must not be reported as P2pKit's terminal write deadline"
        )
        raw.close()
    }

    @Test
    fun callerTimeoutIsNotReclassifiedAsSendDeadline() = runBlocking {
        val raw = newWriteControlledConnection { awaitCancellation() }

        assertFailsWith<TimeoutCancellationException> {
            withTimeout(CALLER_TIMEOUT_MILLIS) {
                raw.write(byteArrayOf(1, 2, 3))
            }
        }
        assertEquals(
            ConnectionState.Connected,
            raw.state.value,
            "caller-owned timeout must not become P2pKit's terminal send deadline"
        )
        raw.close()
    }

    @Test
    fun cancellingReadCollectorCancelsOutstandingNetworkReceive() = runBlocking {
        val context = TransportContext(
            appId = AppId("ios-read-cancel"),
            localPeerId = PeerId("ios-read-cancel-local"),
            deviceName = "local",
            platform = Platform.IOS
        )
        val transport = IosLanDataTransport(context, IosEndpointRegistry())
        assertTrue(transport.start().isSuccess)
        val port = requireNotNull(transport.tcpPort.value)
        val incoming = async(start = CoroutineStart.UNDISPATCHED) {
            transport.incomingConnections().first()
        }
        val peer = InternalPeer(
            publicPeer = Peer(
                id = PeerId("ios-read-cancel-remote"),
                name = "loopback",
                platform = Platform.IOS,
                supportedTransports = setOf(TransportKind.LAN)
            ),
            transportHints = listOf(
                TransportHint(TransportKind.LAN, host = "127.0.0.1", port = port)
            )
        )
        val outbound = withTimeout(CONNECTION_TIMEOUT_MILLIS) { transport.connect(peer) }
        val inbound = withTimeout(CONNECTION_TIMEOUT_MILLIS) { incoming.await() }
        try {
            // UNDISPATCHED runs the flow until nw_connection_receive is
            // installed, providing deterministic synchronization with the
            // cancellation handler and no timing delay.
            val reader = launch(start = CoroutineStart.UNDISPATCHED) {
                inbound.read().collect { }
            }
            reader.cancel()
            withTimeout(CONNECTION_TIMEOUT_MILLIS) { reader.cancelAndJoin() }
            assertEquals(ConnectionState.Closed, inbound.state.value)
        } finally {
            outbound.close()
            transport.close()
        }
        assertNull(transport.tcpPort.value)
        assertNull(transport.listener)
        assertTrue(transport.start().isFailure, "terminally closed transport must not restart")
    }

    @Test
    fun writerQueuedBeforeCloseIsRefusedAfterItAcquiresTheMutex() = runBlocking {
        val firstSendEntered = kotlinx.coroutines.CompletableDeferred<Unit>()
        val releaseFirstSend = kotlinx.coroutines.CompletableDeferred<Unit>()
        val raw = newWriteControlledConnection { bytes ->
            if (bytes.first() == 1.toByte()) {
                firstSendEntered.complete(Unit)
                releaseFirstSend.await()
            }
        }

        val first = async(start = CoroutineStart.UNDISPATCHED) {
            raw.write(byteArrayOf(1))
        }
        firstSendEntered.await()
        val queued = async(start = CoroutineStart.UNDISPATCHED) {
            runCatching { raw.write(byteArrayOf(2)) }
        }

        raw.close()
        releaseFirstSend.complete(Unit)
        first.await()
        val error = queued.await().exceptionOrNull()

        assertIs<IllegalStateException>(error)
        assertEquals("connection closed", error.message)
        assertEquals(ConnectionState.Closed, raw.state.value)
    }

    private companion object {
        const val CONNECTION_TIMEOUT_MILLIS: Long = 10_000
        const val CALLER_TIMEOUT_MILLIS: Long = 100
    }
}
