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
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

/**
 * Pins the keep-alive contract from Spec §14, both directions:
 *  - **negative:** if no `PONG` is observed within `timeoutMillis`, the session
 *    transitions to [ConnectionState.Failed];
 *  - **positive:** while `PONG`s keep arriving the session stays
 *    [ConnectionState.Connected] across many timeout windows; and an inbound
 *    `PING` is answered with a `PONG` on the wire (the responder path).
 *
 * Each test constructs a [P2pSessionImpl] directly with a [FakeConnectionPair]
 * and a hand-fed events channel, so the keep-alive loop and event router can be
 * driven deterministically without a real socket or a SessionManager.
 *
 * Virtual time (fixture upgrade F9 / TST-12): the suite runs under `runTest`
 * with the session scope on a [StandardTestDispatcher] sharing the test
 * scheduler and the session/protocol clocks reading
 * `testScheduler.currentTime`, so keep-alive cadence and deadlines are exact
 * virtual-time arithmetic — no wall-clock waits, no scheduling jitter.
 */
class KeepAliveTest {

    @Test
    fun sessionTransitionsToFailedWhenNoPongArrivesWithinTimeout() {
        runTest {
            val pair = FakeConnectionPair()
            val protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime })
            val supervisor = SupervisorJob()
            val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)

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
                clock = { testScheduler.currentTime },
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

    @Test
    fun respondsToInboundPingWithPong() {
        runTest {
            val pair = FakeConnectionPair()
            val protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime })
            val supervisor = SupervisorJob()
            val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)

            val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
            val peer = Peer(
                id = PeerId("test-pong-responder"),
                name = "Test",
                platform = Platform.JVM_DESKTOP,
                supportedTransports = setOf(TransportKind.LAN)
            )

            val session = P2pSessionImpl(
                id = "pong-responder-test",
                peer = peer,
                initialConnection = pair.a,
                initialEvents = events,
                protocol = protocol,
                parentScope = scope,
                // Long ping interval: the session never emits a spontaneous PING
                // in the test window, so the ONLY frame it writes is the PONG
                // reply we assert on.
                keepAlive = KeepAliveConfig(pingIntervalMillis = 60_000, timeoutMillis = 120_000),
                clock = { testScheduler.currentTime },
                logger = P2pLogger.NoOp
            )
            session.start()

            try {
                // Decode whatever the session writes back onto the wire by
                // running the protocol's event reader on the PEER side (pair.b).
                val outbound = Channel<ProtocolEvent>(Channel.UNLIMITED)
                scope.launch { protocol.events(pair.b).collect { outbound.send(it) } }

                // Simulate an inbound PING arriving from the peer.
                events.send(ProtocolEvent.Ping)

                val reply = withTimeout(3_000) { outbound.receive() }
                assertEquals(
                    ProtocolEvent.Pong, reply,
                    "session must answer an inbound PING with a PONG frame"
                )
            } finally {
                supervisor.cancel()
            }
        }
    }

    @Test
    fun staysConnectedWhilePongsArriveWithinTimeout() {
        runTest {
            val pair = FakeConnectionPair()
            val protocol = DefaultP2pProtocol(clock = { testScheduler.currentTime })
            val supervisor = SupervisorJob()
            val scope = CoroutineScope(StandardTestDispatcher(testScheduler) + supervisor)

            val events = Channel<ProtocolEvent>(Channel.UNLIMITED)
            val peer = Peer(
                id = PeerId("test-keepalive-positive"),
                name = "Test",
                platform = Platform.JVM_DESKTOP,
                supportedTransports = setOf(TransportKind.LAN)
            )

            val session = P2pSessionImpl(
                id = "keepalive-positive-test",
                peer = peer,
                initialConnection = pair.a,
                initialEvents = events,
                protocol = protocol,
                parentScope = scope,
                // timeout (600ms virtual) is 24x the 25ms virtual PONG cadence
                // below; the 900ms virtual run still exceeds the timeout, so
                // the no-PONG baseline (the failure test above) WOULD have
                // failed — proving it is the PONGs keeping the session
                // Connected. All arithmetic is on the test scheduler's virtual
                // clock, so the margins are exact, not jitter-dependent.
                keepAlive = KeepAliveConfig(pingIntervalMillis = 50, timeoutMillis = 600),
                clock = { testScheduler.currentTime },
                logger = P2pLogger.NoOp
            )

            // Feed PONGs faster than the timeout for the whole run.
            val feeder = scope.launch {
                while (isActive) {
                    events.send(ProtocolEvent.Pong)
                    delay(25)
                }
            }
            session.start()

            try {
                delay(900)
                assertEquals(
                    ConnectionState.Connected, session.state.value,
                    "session must stay Connected while PONGs keep arriving within timeout"
                )
                assertTrue(
                    pair.a.writtenChunks.isNotEmpty(),
                    "keep-alive loop should have written PING frames during the run"
                )
            } finally {
                feeder.cancel()
                supervisor.cancel()
            }
        }
    }
}
