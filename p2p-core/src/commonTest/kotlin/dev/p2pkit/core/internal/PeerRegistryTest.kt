package dev.p2pkit.core.internal

import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class PeerRegistryTest {

    private fun peer(id: String, name: String = id): InternalPeer = InternalPeer(
        publicPeer = Peer(
            id = PeerId(id),
            name = name,
            platform = Platform.JVM_DESKTOP,
            supportedTransports = setOf(TransportKind.LAN)
        ),
        transportHints = emptyList()
    )

    @Test
    fun directProcessEventBypassesFlow() {
        val supervisor = SupervisorJob()
        try {
            val transport = FakeDiscovery()
            val registry = PeerRegistry(
                discoveryTransports = listOf(transport),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { 1_000L },
                staleTimeoutMillis = 60_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            registry.processEvent(PeerEvent.Found(peer("direct")))
            assertEquals(1, registry.peers.value.size)
            assertEquals(PeerId("direct"), registry.peers.value[0].id)
        } finally {
            supervisor.cancel()
        }
    }

    @Test
    fun foundEventAddsPeer() = runBlocking {
        val supervisor = SupervisorJob()
        try {
            val transport = FakeDiscovery()
            val registry = PeerRegistry(
                discoveryTransports = listOf(transport),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { 1_000L },
                staleTimeoutMillis = 60_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            registry.start()
            transport.emit(PeerEvent.Found(peer("p1")))

            assertEquals(1, registry.peers.value.size)
            assertEquals(PeerId("p1"), registry.peers.value[0].id)
        } finally {
            supervisor.cancel()
        }
    }

    @Test
    fun updatedEventReplacesPeerWithSameId() = runBlocking {
        val supervisor = SupervisorJob()
        try {
            val transport = FakeDiscovery()
            val registry = PeerRegistry(
                discoveryTransports = listOf(transport),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { 1_000L },
                staleTimeoutMillis = 60_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            registry.start()
            transport.emit(PeerEvent.Found(peer("p1", "First")))
            transport.emit(PeerEvent.Updated(peer("p1", "Renamed")))

            val peers = registry.peers.value
            assertEquals(1, peers.size)
            assertEquals("Renamed", peers[0].name)
        } finally {
            supervisor.cancel()
        }
    }

    @Test
    fun lostEventRemovesPeer() = runBlocking {
        val supervisor = SupervisorJob()
        try {
            val transport = FakeDiscovery()
            val registry = PeerRegistry(
                discoveryTransports = listOf(transport),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { 1_000L },
                staleTimeoutMillis = 60_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            registry.start()
            transport.emit(PeerEvent.Found(peer("p1")))
            transport.emit(PeerEvent.Found(peer("p2")))
            assertEquals(2, registry.peers.value.size)

            transport.emit(PeerEvent.Lost(PeerId("p1")))

            assertEquals(1, registry.peers.value.size)
            assertEquals(PeerId("p2"), registry.peers.value[0].id)
        } finally {
            supervisor.cancel()
        }
    }

    @Test
    fun evictStalePeersRemovesPeerOlderThanTimeout() {
        val supervisor = SupervisorJob()
        try {
            val transport = FakeDiscovery()
            var now = 1_000L
            val registry = PeerRegistry(
                discoveryTransports = listOf(transport),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { now },
                staleTimeoutMillis = 5_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            // Add a peer directly, then advance the clock and force eviction.
            registry.processEvent(PeerEvent.Found(peer("p1")))
            assertEquals(1, registry.peers.value.size)

            now += 6_000
            registry.evictStalePeers()

            assertTrue(registry.peers.value.isEmpty(), "Expected peer to be evicted")
            assertNull(registry.lastSeen(PeerId("p1")))
        } finally {
            supervisor.cancel()
        }
    }

    @Test
    fun evictStalePeersKeepsRecentPeer() {
        val supervisor = SupervisorJob()
        try {
            val transport = FakeDiscovery()
            var now = 1_000L
            val registry = PeerRegistry(
                discoveryTransports = listOf(transport),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { now },
                staleTimeoutMillis = 5_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            registry.processEvent(PeerEvent.Found(peer("p1")))

            now += 3_000  // less than staleTimeoutMillis
            registry.evictStalePeers()

            assertEquals(1, registry.peers.value.size)
        } finally {
            supervisor.cancel()
        }
    }

    @Test
    fun lastSeenReflectsLatestEvent() = runBlocking {
        val supervisor = SupervisorJob()
        try {
            val transport = FakeDiscovery()
            var now = 1_000L
            val registry = PeerRegistry(
                discoveryTransports = listOf(transport),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { now },
                staleTimeoutMillis = 60_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            registry.start()
            transport.emit(PeerEvent.Found(peer("p1")))
            val first = registry.lastSeen(PeerId("p1"))
            assertNotNull(first)

            now += 1_000
            transport.emit(PeerEvent.Updated(peer("p1")))

            val second = registry.lastSeen(PeerId("p1"))
            assertNotNull(second)
            assertTrue(second > first, "Updated event should refresh lastSeen")
        } finally {
            supervisor.cancel()
        }
    }

    private class FakeDiscovery : DiscoveryTransport {
        override val type = TransportKind.LAN
        private val flow = MutableSharedFlow<PeerEvent>(extraBufferCapacity = 16)
        override val events: Flow<PeerEvent> = flow

        suspend fun emit(event: PeerEvent) {
            flow.emit(event)
        }

        override suspend fun startAdvertising(localPeer: LocalPeerInfo) = Unit
        override suspend fun stopAdvertising() = Unit
        override suspend fun startDiscovery() = Unit
        override suspend fun stopDiscovery() = Unit
    }
}
