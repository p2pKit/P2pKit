package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.FakeDataTransport
import dev.p2pkit.core.testfixtures.FakeDiscoveryTransport
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportHint
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals

/**
 * Verifies V0.4-RECONNECT: [SessionReconnectHandler] re-resolves the target
 * [InternalPeer] from `PeerRegistry` on every attempt, so address rotation
 * (DHCP lease change, hotspot move, Android NSD rebind on network change)
 * propagates into the next dial without waiting for the host app to
 * re-issue `connect()`.
 *
 * Strategy: drive a controlled rotation via [FakeDiscoveryTransport] —
 * emit `PeerEvent.Found` to seed `PeerRegistry`, run the initial connect,
 * break the wire, emit `PeerEvent.Updated` with different transport hints,
 * then assert the next reconnect attempt's `connect(internalPeer)` call
 * carries the *new* hints. Recording happens via
 * [FakeDataTransport.connectCalls].
 */
class SessionReconnectRotationTest {

    private val bobPeer: Peer = Peer(
        id = PeerId("bob-id"),
        name = "Bob",
        platform = Platform.JVM_DESKTOP,
        supportedTransports = setOf(TransportKind.LAN)
    )

    @Test
    fun reconnectUsesRefreshedHintsAfterPeerRegistryUpdate() = runBlocking<Unit> {
        // Two pre-staged pairs: first breaks, second is what the retry reaches.
        val pair1 = FakeConnectionPair()
        val pair2 = FakeConnectionPair()
        val outQueue = ArrayDeque<RawConnection>().apply {
            add(pair1.a); add(pair2.a)
        }
        val aliceData = FakeDataTransport(outgoingConnection = { outQueue.removeFirst() })
        val aliceDiscovery = FakeDiscoveryTransport()

        val hintsV1 = listOf(TransportHint(TransportKind.LAN, host = "10.0.0.5", port = 4000))
        val hintsV2 = listOf(TransportHint(TransportKind.LAN, host = "10.0.0.99", port = 5555))
        val bobV1 = InternalPeer(publicPeer = bobPeer, transportHints = hintsV1)
        val bobV2 = InternalPeer(publicPeer = bobPeer, transportHints = hintsV2)

        val alice = P2pKit.create {
            appId = AppId("com.example.test")
            deviceName = "Alice"
            keepAlive {
                // Very long PING so the only thing driving state transitions
                // in this test is the wire-break + reconnect, not keep-alive
                // timeout.
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            lifecycle {
                // Small retryDelayMillis keeps the test fast while still
                // giving PeerRegistry time to process the Updated event
                // between attempts.
                reconnectPolicy = ReconnectPolicy.Enabled(
                    maxAttempts = 3,
                    retryDelayMillis = 200
                )
            }
            transports {
                register(RotationTestFactory(aliceData, aliceDiscovery))
            }
        }
        val bob = P2pKit.create {
            appId = AppId("com.example.test")
            deviceName = "Bob"
            // Match the dialed id ("bob-id") so the outgoing handshake's peerId
            // verification passes (mirrors production discovery).
            peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("bob-id"))
            keepAlive {
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            transports {
                register(
                    RotationTestFactory(
                        data = FakeDataTransport(
                            preStagedIncoming = listOf(pair1.b, pair2.b)
                        ),
                        discovery = null
                    )
                )
            }
        }
        try {
            // Seed alice's PeerRegistry with bobV1.
            aliceDiscovery.emit(PeerEvent.Found(bobV1))
            withTimeout(2_000) {
                alice.peers.first { list -> list.any { it.id == bobPeer.id } }
            }

            // Initial connect — handler captures bobV1 as originalInternalPeer
            // and dials it.
            val session = withTimeout(5_000) { alice.connect(bobPeer) }
            assertEquals(ConnectionState.Connected, session.state.value)
            assertEquals(1, aliceData.connectCalls.size, "exactly one dial for initial connect")
            assertEquals(
                hintsV1, aliceData.connectCalls[0].transportHints,
                "initial dial must use the InternalPeer seeded into PeerRegistry"
            )

            // Break the wire — session goes Reconnecting and the handler
            // parks on retryDelayMillis OR pathSatisfiedSignal.
            pair1.a.breakWith(RuntimeException("simulated wire break"))
            withTimeout(5_000) {
                session.state.first { it == ConnectionState.Reconnecting }
            }

            // Rotation: emit a fresh InternalPeer for the SAME peerId but
            // with different transport hints. PeerRegistry processes this
            // event asynchronously via its onEach pipeline; the
            // retryDelayMillis (200ms) is more than enough for the update
            // to land before the next dial fires.
            aliceDiscovery.emit(PeerEvent.Updated(bobV2))

            // Wait for the reconnect attempt to succeed against pair2.
            withTimeout(5_000) {
                session.state.first { it == ConnectionState.Connected }
            }

            // The second dial must have used hintsV2 — the rotated address
            // from PeerRegistry, NOT the originally captured hintsV1.
            assertEquals(2, aliceData.connectCalls.size, "exactly two dials: initial + one retry")
            assertEquals(
                hintsV2, aliceData.connectCalls[1].transportHints,
                "reconnect attempt must dial the rotated address resolved from PeerRegistry, " +
                    "not the originalInternalPeer captured at session creation"
            )
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    @Test
    fun reconnectFallsBackToOriginalWhenRegistryHasNoEntry() = runBlocking<Unit> {
        val pair1 = FakeConnectionPair()
        val pair2 = FakeConnectionPair()
        val outQueue = ArrayDeque<RawConnection>().apply {
            add(pair1.a); add(pair2.a)
        }
        val aliceData = FakeDataTransport(outgoingConnection = { outQueue.removeFirst() })
        val aliceDiscovery = FakeDiscoveryTransport()

        val hintsV1 = listOf(TransportHint(TransportKind.LAN, host = "10.0.0.5", port = 4000))
        val bobV1 = InternalPeer(publicPeer = bobPeer, transportHints = hintsV1)

        val alice = P2pKit.create {
            appId = AppId("com.example.test")
            deviceName = "Alice"
            keepAlive {
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            lifecycle {
                reconnectPolicy = ReconnectPolicy.Enabled(
                    maxAttempts = 3,
                    retryDelayMillis = 200
                )
            }
            transports {
                register(RotationTestFactory(aliceData, aliceDiscovery))
            }
        }
        val bob = P2pKit.create {
            appId = AppId("com.example.test")
            deviceName = "Bob"
            // Match the dialed id ("bob-id") so the outgoing handshake's peerId
            // verification passes (mirrors production discovery).
            peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("bob-id"))
            keepAlive {
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            transports {
                register(
                    RotationTestFactory(
                        data = FakeDataTransport(
                            preStagedIncoming = listOf(pair1.b, pair2.b)
                        ),
                        discovery = null
                    )
                )
            }
        }
        try {
            // Seed initially, then evict by emitting Lost — simulates the
            // peer disappearing from discovery (e.g., long outage exceeding
            // staleTimeoutMillis). The reconnect handler should fall back
            // to its originalInternalPeer capture.
            aliceDiscovery.emit(PeerEvent.Found(bobV1))
            withTimeout(2_000) {
                alice.peers.first { list -> list.any { it.id == bobPeer.id } }
            }
            val session = withTimeout(5_000) { alice.connect(bobPeer) }
            assertEquals(ConnectionState.Connected, session.state.value)
            assertEquals(hintsV1, aliceData.connectCalls[0].transportHints)

            // Break the wire and immediately evict the peer from the registry.
            pair1.a.breakWith(RuntimeException("simulated wire break"))
            aliceDiscovery.emit(PeerEvent.Lost(bobPeer.id))
            withTimeout(2_000) {
                alice.peers.first { list -> list.none { it.id == bobPeer.id } }
            }

            // Reconnect attempt should now find peerLookup returning null
            // and fall back to the originally captured InternalPeer (hintsV1).
            withTimeout(5_000) {
                session.state.first { it == ConnectionState.Connected }
            }
            assertEquals(2, aliceData.connectCalls.size)
            assertEquals(
                hintsV1, aliceData.connectCalls[1].transportHints,
                "with registry empty, reconnect must fall back to originalInternalPeer (hintsV1)"
            )
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    /**
     * V0.4-DISCOVERY-REFRESH: when an outgoing session enters Reconnecting,
     * SessionManager must invoke `refresh()` on every registered
     * DiscoveryTransport exactly once before the retry loop starts. This
     * closes the gap where the remote peer rebound to a new port but the
     * local NSD cache hasn't observed the re-announcement — the active
     * refresh forces a fresh query so the remote can respond with its
     * current port before the next dial.
     */
    @Test
    fun discoveryRefreshFiresOnReconnectingTransition() = runBlocking<Unit> {
        val pair1 = FakeConnectionPair()
        val pair2 = FakeConnectionPair()
        val outQueue = ArrayDeque<RawConnection>().apply {
            add(pair1.a); add(pair2.a)
        }
        val aliceData = FakeDataTransport(outgoingConnection = { outQueue.removeFirst() })
        val aliceDiscovery = FakeDiscoveryTransport()

        val hintsV1 = listOf(TransportHint(TransportKind.LAN, host = "10.0.0.5", port = 4000))
        val bobV1 = InternalPeer(publicPeer = bobPeer, transportHints = hintsV1)

        val alice = P2pKit.create {
            appId = AppId("com.example.test")
            deviceName = "Alice"
            keepAlive {
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            lifecycle {
                reconnectPolicy = ReconnectPolicy.Enabled(
                    maxAttempts = 3,
                    retryDelayMillis = 200
                )
            }
            transports {
                register(RotationTestFactory(aliceData, aliceDiscovery))
            }
        }
        val bob = P2pKit.create {
            appId = AppId("com.example.test")
            deviceName = "Bob"
            // Match the dialed id ("bob-id") so the outgoing handshake's peerId
            // verification passes (mirrors production discovery).
            peerIdStorage = InMemoryPeerIdStorage(seed = PeerId("bob-id"))
            keepAlive {
                pingIntervalMillis = 60_000
                timeoutMillis = 120_000
            }
            transports {
                register(
                    RotationTestFactory(
                        data = FakeDataTransport(
                            preStagedIncoming = listOf(pair1.b, pair2.b)
                        ),
                        discovery = null
                    )
                )
            }
        }
        try {
            aliceDiscovery.emit(PeerEvent.Found(bobV1))
            withTimeout(2_000) {
                alice.peers.first { list -> list.any { it.id == bobPeer.id } }
            }

            val session = withTimeout(5_000) { alice.connect(bobPeer) }
            assertEquals(ConnectionState.Connected, session.state.value)
            // refresh() must NOT fire on initial connect — only on reconnect.
            assertEquals(0, aliceDiscovery.refreshCalls, "no refresh during initial connect")

            // Break the wire — session goes Reconnecting → handler should
            // invoke refresh() exactly once before the first retry dials.
            pair1.a.breakWith(RuntimeException("simulated wire break"))
            withTimeout(5_000) {
                session.state.first { it == ConnectionState.Reconnecting }
            }

            // Wait for reconnect to land. The exact ordering of refresh()
            // vs. the first retry attempt is "refresh first, then attempts" —
            // we assert refreshCalls becomes 1 by the time we observe
            // Connected, and stays at 1 (single refresh per Reconnecting
            // episode).
            withTimeout(5_000) {
                session.state.first { it == ConnectionState.Connected }
            }
            assertEquals(
                1, aliceDiscovery.refreshCalls,
                "refresh() must be invoked exactly once per Reconnecting episode"
            )
        } finally {
            alice.stop()
            bob.stop()
        }
    }

    private class RotationTestFactory(
        private val data: FakeDataTransport,
        private val discovery: DiscoveryTransport?
    ) : TransportFactory {
        override fun build(context: TransportContext): TransportPair =
            TransportPair(data = data, discovery = discovery)
    }
}
