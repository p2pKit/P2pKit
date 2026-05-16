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
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Pins the keep-alive contract from Spec §14:
 * if no `PONG` is observed within `timeoutMillis`, the session transitions to
 * [ConnectionState.Failed].
 *
 * We construct a [P2pSessionImpl] directly with a [FakeConnectionPair] and an
 * **empty** events channel — so the session's PINGs go onto the wire (where no
 * one consumes them) but no `Pong` event is ever delivered upstream. The
 * keep-alive loop should observe the elapsed wall-clock and fail the session.
 */
class KeepAliveTest {

    @Test
    fun sessionTransitionsToFailedWhenNoPongArrivesWithinTimeout() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = DefaultP2pProtocol(clock = { systemTimeMillis() })
            val supervisor = SupervisorJob()
            val scope = CoroutineScope(Dispatchers.Default + supervisor)

            // No events ever land in this channel → the session never sees a
            // ProtocolEvent.Pong → keepalive deadline elapses.
            val events = Channel<ProtocolEvent>(Channel.UNLIMITED)

            val peer = Peer(
                id = PeerId("test-keepalive"),
                name = "Test",
                platform = Platform.JVM_DESKTOP,
                supportedTransports = setOf(TransportKind.LAN)
            )

            val session = P2pSessionImpl(
                id = "keepalive-test",
                peer = peer,
                initialConnection = pair.a,
                initialEvents = events,
                protocol = protocol,
                parentScope = scope,
                keepAlive = KeepAliveConfig(pingIntervalMillis = 50, timeoutMillis = 150),
                clock = { systemTimeMillis() },
                logger = P2pLogger.NoOp
            )
            session.start()

            try {
                val terminal = withTimeout(3_000) {
                    session.state.first { it == ConnectionState.Failed || it == ConnectionState.Closed }
                }
                assertEquals(ConnectionState.Failed, terminal, "Session should fail due to missing PONG")

                // Sanity: the session did write *some* PINGs onto the wire
                // before failing (i.e., the loop ran at least once).
                assertTrue(
                    pair.a.writtenChunks.isNotEmpty(),
                    "Keep-alive loop should have written at least one PING frame"
                )
            } finally {
                supervisor.cancel()
            }
        }
    }
}
