package dev.p2pkit.core.internal

import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.FakeDiscoveryTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.PeerEvent
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * 2026-07 (DSC-1, P1-13 contract leg): pins the liveness contract between
 * [PeerRegistry] and every [dev.p2pkit.core.transport.DiscoveryTransport] —
 * a transport MUST re-emit `Found`/`Updated` for a healthy peer within the
 * registry's stale timeout ([PeerRegistry.DEFAULT_STALE_TIMEOUT_MS], 15 s),
 * or the peer is evicted from `kit.peers` and, on JVM/Android, never returns
 * in steady state (the goodbye path emits no usable `Lost`, so eviction is
 * the only disappearance mechanism there). All three shipped LAN transports
 * satisfy the contract with a ~5 s cache re-emit heartbeat; this test states
 * the contract itself against [FakeDiscoveryTransport] with a fake clock:
 *
 *  - a peer whose transport re-emits within the timeout survives past the
 *    20 s / 35 s idle marks of the coverage row;
 *  - a peer whose transport goes quiet (departed — no cache entry to
 *    re-emit) is evicted once the stale timeout elapses.
 */
class DiscoveryReemitContractTest {

    /** The documented transport heartbeat cadence (LanConstants.PEER_REANNOUNCE_INTERVAL_MS). */
    private val heartbeatIntervalMillis = 5_000L

    private fun peer(id: String): InternalPeer = InternalPeer(
        publicPeer = Peer(
            id = PeerId(id),
            name = id,
            platform = Platform.JVM_DESKTOP,
            supportedTransports = setOf(TransportKind.LAN)
        ),
        transportHints = emptyList()
    )

    @Test
    fun heartbeatCadenceStaysBelowTheDefaultStaleTimeout() {
        assertTrue(
            heartbeatIntervalMillis * 2 < PeerRegistry.DEFAULT_STALE_TIMEOUT_MS,
            "the transport re-emit cadence must stay comfortably below the eviction horizon"
        )
    }

    @Test
    fun peerReemittedWithinStaleTimeoutSurvivesPastTheEvictionHorizon() = runBlocking {
        val supervisor = SupervisorJob()
        try {
            val transport = FakeDiscoveryTransport(strictDelivery = true)
            var now = 0L
            val registry = PeerRegistry(
                discoveryTransports = listOf(transport),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { now },
                // Default 15 s stale timeout — the horizon under contract.
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            registry.start()
            transport.emit(PeerEvent.Found(peer("idle-peer")))

            // Conforming transport: one Updated re-emit per heartbeat tick.
            // Run eviction at every tick and verify the 20 s and 35 s idle
            // marks of the P1-13 row (and beyond, to 40 s).
            repeat(8) {
                now += heartbeatIntervalMillis
                transport.emit(PeerEvent.Updated(peer("idle-peer")))
                registry.evictStalePeers()
                assertTrue(
                    registry.peers.value.any { it.id == PeerId("idle-peer") },
                    "peer re-emitted within the stale timeout must survive at t=${now / 1000} s"
                )
            }
        } finally {
            supervisor.cancel()
        }
    }

    @Test
    fun peerWhoseTransportGoesQuietIsEvictedAfterTheStaleTimeout() = runBlocking {
        val supervisor = SupervisorJob()
        try {
            val transport = FakeDiscoveryTransport(strictDelivery = true)
            var now = 0L
            val registry = PeerRegistry(
                discoveryTransports = listOf(transport),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { now },
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            registry.start()
            transport.emit(PeerEvent.Found(peer("departed-peer")))

            // One healthy tick, then silence: the transport re-emits only
            // cache-present peers, so a departed peer stops being announced.
            now += heartbeatIntervalMillis
            transport.emit(PeerEvent.Updated(peer("departed-peer")))
            registry.evictStalePeers()
            assertTrue(registry.peers.value.any { it.id == PeerId("departed-peer") })

            // Still inside the horizon measured from the LAST re-emit: kept.
            now += PeerRegistry.DEFAULT_STALE_TIMEOUT_MS
            registry.evictStalePeers()
            assertTrue(
                registry.peers.value.any { it.id == PeerId("departed-peer") },
                "peer must survive up to exactly the stale timeout since the last re-emit"
            )

            // Past the horizon: evicted — departure still works even though
            // no Lost event ever fired.
            now += 1
            registry.evictStalePeers()
            assertTrue(
                registry.peers.value.none { it.id == PeerId("departed-peer") },
                "a peer no longer re-emitted must age out via staleness eviction"
            )
            assertNull(registry.lastSeen(PeerId("departed-peer")))
        } finally {
            supervisor.cancel()
        }
    }
}
