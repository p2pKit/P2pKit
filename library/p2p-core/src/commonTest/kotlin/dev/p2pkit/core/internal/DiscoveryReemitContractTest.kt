package dev.p2pkit.core.internal

import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.testfixtures.FakeDiscoveryTransport
import dev.p2pkit.core.transport.DiscoveryLifetime
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportHint
import dev.p2pkit.core.transport.withDiscoveryLifetime
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertTrue

/**
 * Pins both discovery-lifetime contracts. Event-based transports must refresh
 * within the core stale horizon. Native DNS-SD browsers own TTL expiry and
 * remove their contribution with an exact [PeerEvent.Lost]; core must neither
 * evict them early nor require cache-derived heartbeat events.
 */
class DiscoveryReemitContractTest {

    private fun peer(
        id: String,
        lifetime: DiscoveryLifetime = DiscoveryLifetime.CoreStaleTimeout
    ): InternalPeer = InternalPeer(
        publicPeer = Peer(
            id = PeerId(id),
            name = id,
            platform = Platform.JVM_DESKTOP,
            supportedTransports = setOf(TransportKind.LAN)
        ),
        transportHints = listOf(
            TransportHint(TransportKind.LAN).withDiscoveryLifetime(lifetime)
        )
    )

    @Test
    fun eventBasedPeerReemittedWithinStaleTimeoutSurvives() = runBlocking {
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

            // An event-based transport refreshes before each eviction pass.
            repeat(8) {
                now += 5_000L
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
    fun eventBasedPeerWhoseTransportGoesQuietIsEvicted() = runBlocking {
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
            now += 5_000L
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
        } finally {
            supervisor.cancel()
        }
    }

    @Test
    fun transportManagedPeerSurvivesCoreEvictionAndExactLostRemovesIt() = runBlocking {
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
            val id = PeerId("native-ttl-peer")
            transport.emit(
                PeerEvent.Found(peer(id.value, DiscoveryLifetime.TransportManaged))
            )

            now += PeerRegistry.DEFAULT_STALE_TIMEOUT_MS * 100
            registry.evictStalePeers()
            assertTrue(registry.peers.value.any { it.id == id })

            transport.emit(PeerEvent.Lost(id))
            assertTrue(registry.peers.value.none { it.id == id })
        } finally {
            supervisor.cancel()
        }
    }
}
