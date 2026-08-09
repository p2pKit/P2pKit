package dev.p2pkit.core.internal

import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportHint
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotEquals
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
    fun publishedPeerListsAreStableUnmodifiableSnapshots() {
        val supervisor = SupervisorJob()
        try {
            val registry = PeerRegistry(
                discoveryTransports = emptyList(),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { 1_000L },
                staleTimeoutMillis = 60_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            val initial = registry.peers.value
            assertTrue(
                runCatching { (initial as MutableList<Peer>).add(peer("injected").publicPeer) }
                    .isFailure
            )

            registry.processEvent(PeerEvent.Found(peer("published")))
            val published = registry.peers.value
            assertTrue(
                runCatching { (published as MutableList<Peer>).clear() }.isFailure
            )
            assertEquals(listOf(PeerId("published")), registry.peers.value.map { it.id })
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
    fun peerContributionsAreMergedAndLostPerTransportInstance() = runBlocking {
        val supervisor = SupervisorJob()
        try {
            val lan = FakeDiscovery(TransportKind.LAN)
            val ble = FakeDiscovery(TransportKind.BLE)
            val registry = PeerRegistry(
                discoveryTransports = listOf(lan, ble),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { 1_000L },
                staleTimeoutMillis = 60_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            registry.start()

            lan.emit(
                PeerEvent.Found(
                    peer("shared").copy(
                        transportHints = listOf(
                            TransportHint(TransportKind.LAN, host = "192.0.2.10", port = 9_001)
                        )
                    )
                )
            )
            ble.emit(
                PeerEvent.Found(
                    peer("shared").copy(
                        publicPeer = peer("shared").publicPeer.copy(
                            supportedTransports = setOf(TransportKind.BLE)
                        ),
                        transportHints = listOf(TransportHint(TransportKind.BLE))
                    )
                )
            )

            assertEquals(
                setOf(TransportKind.LAN, TransportKind.BLE),
                registry.peers.value.single().supportedTransports
            )
            assertEquals(
                setOf(TransportKind.LAN, TransportKind.BLE),
                registry.internalPeer(PeerId("shared"))!!.transportHints.map { it.type }.toSet()
            )

            lan.emit(PeerEvent.Lost(PeerId("shared")))
            assertEquals(setOf(TransportKind.BLE), registry.peers.value.single().supportedTransports)
            assertEquals(
                listOf(TransportKind.BLE),
                registry.internalPeer(PeerId("shared"))!!.transportHints.map { it.type }
            )

            ble.emit(PeerEvent.Lost(PeerId("shared")))
            assertTrue(registry.peers.value.isEmpty())
        } finally {
            supervisor.cancel()
        }
    }

    @Test
    fun registrySnapshotsMutableDiscoveryCollections() = runBlocking {
        val supervisor = SupervisorJob()
        try {
            val transport = FakeDiscovery()
            val kinds = mutableSetOf(TransportKind.LAN)
            val metadata = mutableMapOf("route" to "primary", "scope" to "local")
            val hints = mutableListOf(
                TransportHint(TransportKind.LAN, "192.0.2.20", 9_000, metadata)
            )
            val registry = PeerRegistry(
                discoveryTransports = listOf(transport),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { 1_000L },
                staleTimeoutMillis = 60_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            registry.start()
            transport.emit(
                PeerEvent.Found(
                    InternalPeer(
                        Peer(PeerId("snapshot"), "Snapshot", Platform.JVM_DESKTOP, kinds),
                        hints
                    )
                )
            )

            kinds += TransportKind.BLE
            metadata.clear()
            hints.clear()

            assertEquals(setOf(TransportKind.LAN), registry.peers.value.single().supportedTransports)
            val retainedHint = registry.internalPeer(PeerId("snapshot"))!!.transportHints.single()
            assertEquals(mapOf("route" to "primary", "scope" to "local"), retainedHint.metadata)
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

    // ---- Manual-peer staleness exemption (2026-07 review P1-10, A04 §3 r1) ----

    /**
     * Manual peers carry no discovery heartbeats, so they must be exempt from
     * staleness eviction: a discovered peer registered at the same time is
     * evicted after the stale timeout while the manual entry survives.
     */
    @OptIn(ExperimentalP2pApi::class)
    @Test
    fun manualPeerSurvivesStalenessEvictionWhileDiscoveredPeerIsEvicted() {
        val supervisor = SupervisorJob()
        try {
            var now = 1_000L
            val registry = PeerRegistry(
                discoveryTransports = listOf(FakeDiscovery()),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { now },
                staleTimeoutMillis = 5_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            val manual = registry.registerManualPeer(
                host = "192.168.1.50",
                port = 9_000,
                kind = TransportKind.LAN,
                deviceName = "Desk"
            )
            registry.processEvent(PeerEvent.Found(peer("discovered")))
            assertEquals(2, registry.peers.value.size)

            now += 6_000 // beyond staleTimeoutMillis for both entries
            registry.evictStalePeers()

            assertEquals(
                listOf(manual.id),
                registry.peers.value.map { it.id },
                "Only the manual peer must survive eviction after the clock advance"
            )
            assertNotNull(registry.lastSeen(manual.id), "Manual peer must stay tracked")
            assertNull(registry.lastSeen(PeerId("discovered")), "Discovered peer must be evicted")
        } finally {
            supervisor.cancel()
        }
    }

    /**
     * The exemption must hold across repeated eviction passes and arbitrarily
     * large clock advances, not just the first pass after registration.
     */
    @OptIn(ExperimentalP2pApi::class)
    @Test
    fun manualPeerSurvivesRepeatedEvictionPassesAfterLargeClockAdvance() {
        val supervisor = SupervisorJob()
        try {
            var now = 1_000L
            val registry = PeerRegistry(
                discoveryTransports = listOf(FakeDiscovery()),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { now },
                staleTimeoutMillis = 5_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            val manual = registry.registerManualPeer(host = "10.1.2.3", port = 4_242)

            repeat(3) {
                now += 60_000 // 12x the stale timeout, each pass
                registry.evictStalePeers()
            }

            assertEquals(1, registry.peers.value.size)
            assertEquals(manual.id, registry.peers.value.single().id)
        } finally {
            supervisor.cancel()
        }
    }

    // ---- registerManualPeer endpoint dedupe (2026-07 review P1-11, IDN-5, A04 §3 r2)
    // ---- + dedupe-hit name refresh (AUDIT-2026-07 (IDN-7), decision #6b) ----

    /**
     * Repeat registration of the same (host, port, kind) endpoint reuses the
     * existing synthetic peer (same id, exactly one tracked entry), and a
     * repeat that supplies a different non-blank deviceName refreshes the
     * stored display name instead of silently dropping it
     * (AUDIT-2026-07 (IDN-7), decision #6b).
     */
    @OptIn(ExperimentalP2pApi::class)
    @Test
    fun registerManualPeerSameEndpointReturnsSamePeerAndKeepsOneEntry() {
        val supervisor = SupervisorJob()
        try {
            val registry = PeerRegistry(
                discoveryTransports = listOf(FakeDiscovery()),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { 1_000L },
                staleTimeoutMillis = 60_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            val first = registry.registerManualPeer("10.0.0.7", 7_000, TransportKind.LAN, "First name")
            val second = registry.registerManualPeer("10.0.0.7", 7_000, TransportKind.LAN, "Different name")

            assertEquals(first.id, second.id, "Same endpoint must reuse the existing synthetic id")
            assertEquals("Different name", second.name, "Dedupe-hit must refresh the display name")
            assertEquals(1, registry.peers.value.size, "Repeat registration must not grow the registry")
            assertEquals(
                "Different name",
                registry.peers.value.single().name,
                "The published peer list must show the refreshed name"
            )
            assertEquals(
                first.id,
                registry.peers.value.single().id,
                "The refreshed entry must keep the original synthetic id"
            )
        } finally {
            supervisor.cancel()
        }
    }

    /**
     * A dedupe-hit with a null or blank deviceName keeps the existing display
     * name (only a non-blank new name refreshes it), and a repeat of the same
     * name causes no registry churn (AUDIT-2026-07 (IDN-7), decision #6b).
     */
    @OptIn(ExperimentalP2pApi::class)
    @Test
    fun registerManualPeerDedupeWithNullOrBlankNameKeepsExistingName() {
        val supervisor = SupervisorJob()
        try {
            val registry = PeerRegistry(
                discoveryTransports = listOf(FakeDiscovery()),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { 1_000L },
                staleTimeoutMillis = 60_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            val first = registry.registerManualPeer("10.0.0.7", 7_000, TransportKind.LAN, "First name")

            val nullRepeat = registry.registerManualPeer("10.0.0.7", 7_000, TransportKind.LAN, null)
            assertEquals(first.id, nullRepeat.id)
            assertEquals("First name", nullRepeat.name, "Null deviceName must keep the existing name")

            val blankRepeat = registry.registerManualPeer("10.0.0.7", 7_000, TransportKind.LAN, "   ")
            assertEquals(first.id, blankRepeat.id)
            assertEquals("First name", blankRepeat.name, "Blank deviceName must keep the existing name")

            val sameName = registry.registerManualPeer("10.0.0.7", 7_000, TransportKind.LAN, "First name")
            assertEquals(first, sameName, "Same-name repeat returns the same public Peer value")

            assertEquals(1, registry.peers.value.size, "No repeat variant may grow the registry")
        } finally {
            supervisor.cancel()
        }
    }

    /** A new endpoint (different host or different port) mints a new synthetic id. */
    @OptIn(ExperimentalP2pApi::class)
    @Test
    fun registerManualPeerNewEndpointMintsNewId() {
        val supervisor = SupervisorJob()
        try {
            val registry = PeerRegistry(
                discoveryTransports = listOf(FakeDiscovery()),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { 1_000L },
                staleTimeoutMillis = 60_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            val base = registry.registerManualPeer("10.0.0.7", 7_000, TransportKind.LAN)
            val otherPort = registry.registerManualPeer("10.0.0.7", 7_001, TransportKind.LAN)
            val otherHost = registry.registerManualPeer("10.0.0.8", 7_000, TransportKind.LAN)

            assertNotEquals(base.id, otherPort.id, "Different port is a new endpoint")
            assertNotEquals(base.id, otherHost.id, "Different host is a new endpoint")
            assertNotEquals(otherPort.id, otherHost.id)
            assertEquals(3, registry.peers.value.size)
        } finally {
            supervisor.cancel()
        }
    }

    /** The transport kind is part of the dedupe key: same host:port over a different kind is a new entry. */
    @OptIn(ExperimentalP2pApi::class)
    @Test
    fun registerManualPeerSameHostPortDifferentKindMintsNewId() {
        val supervisor = SupervisorJob()
        try {
            val registry = PeerRegistry(
                discoveryTransports = listOf(FakeDiscovery()),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { 1_000L },
                staleTimeoutMillis = 60_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            val lan = registry.registerManualPeer("10.0.0.7", 7_000, TransportKind.LAN)
            val ble = registry.registerManualPeer("10.0.0.7", 7_000, TransportKind.BLE)

            assertNotEquals(lan.id, ble.id, "Same host:port under a different kind is a distinct endpoint")
            assertEquals(2, registry.peers.value.size)
            // And the repeat within each kind still dedupes.
            assertEquals(lan.id, registry.registerManualPeer("10.0.0.7", 7_000, TransportKind.LAN).id)
            assertEquals(2, registry.peers.value.size)
        } finally {
            supervisor.cancel()
        }
    }

    @OptIn(ExperimentalP2pApi::class)
    @Test
    fun manualHostsAreCanonicalizedAndUnsafeUriFormsRejected() {
        val supervisor = SupervisorJob()
        try {
            val registry = PeerRegistry(
                discoveryTransports = listOf(FakeDiscovery()),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { 1_000L },
                staleTimeoutMillis = 60_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            val first = registry.registerManualPeer("  EXAMPLE.COM  ", 9_000)
            val duplicate = registry.registerManualPeer("example.com", 9_000)
            assertEquals(first.id, duplicate.id)
            assertEquals(
                "example.com",
                registry.internalPeer(first.id)!!.transportHints.single().host
            )

            val ipv6 = registry.registerManualPeer("[FE80::1%EN0]", 9_001)
            assertEquals(
                "fe80::1%en0",
                registry.internalPeer(ipv6.id)!!.transportHints.single().host
            )

            listOf("https://host", "user@host", "host/path", "host name", "host\u0000name")
                .forEach { unsafe ->
                    assertFailsWith<IllegalArgumentException> {
                        registry.registerManualPeer(unsafe, 9_002)
                    }
                }
        } finally {
            supervisor.cancel()
        }
    }

    @Test
    fun staleEvictionUsesMonotonicTimeWhileLastSeenRemainsEpochTime() {
        val supervisor = SupervisorJob()
        try {
            var epochNow = 1_000L
            var monotonicNow = 50L
            val registry = PeerRegistry(
                discoveryTransports = emptyList(),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { epochNow },
                monotonicClock = { monotonicNow },
                staleTimeoutMillis = 5_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            registry.processEvent(PeerEvent.Found(peer("clock-safe")))
            assertEquals(1_000L, registry.lastSeen(PeerId("clock-safe")))

            // A wall-clock correction is not evidence that the peer stopped
            // emitting discovery observations.
            epochNow += 24L * 60L * 60L * 1_000L
            registry.evictStalePeers()
            assertEquals(1, registry.peers.value.size)

            monotonicNow += 5_001L
            registry.evictStalePeers()
            assertTrue(registry.peers.value.isEmpty())
        } finally {
            supervisor.cancel()
        }
    }

    @OptIn(ExperimentalP2pApi::class)
    @Test
    fun manualRegistrationRetriesAtomicallyWhenSameEndpointWinsItsSnapshot() {
        val supervisor = SupervisorJob()
        try {
            lateinit var registry: PeerRegistry
            var reentered = false
            var nested: Peer? = null
            registry = PeerRegistry(
                discoveryTransports = emptyList(),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { 1_000L },
                staleTimeoutMillis = 60_000,
                evictionPollMillis = Long.MAX_VALUE / 2,
                beforeManualPeerCompareAndSetForTest = {
                    if (!reentered) {
                        reentered = true
                        nested = registry.registerManualPeer("192.0.2.44", 9_044)
                    }
                }
            )

            val outer = registry.registerManualPeer("192.0.2.44", 9_044)

            assertEquals(nested?.id, outer.id)
            assertEquals(1, registry.peers.value.size)
            assertEquals(outer.id, registry.peers.value.single().id)
        } finally {
            supervisor.cancel()
        }
    }

    @OptIn(ExperimentalP2pApi::class)
    @Test
    fun closeClearsAllPeersAndRejectsLateEventsAndManualRegistrations() {
        val supervisor = SupervisorJob()
        try {
            val registry = PeerRegistry(
                discoveryTransports = emptyList(),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { 1_000L },
                staleTimeoutMillis = 60_000,
                evictionPollMillis = Long.MAX_VALUE / 2
            )
            registry.processEvent(PeerEvent.Found(peer("discovered")))
            registry.registerManualPeer("192.0.2.45", 9_045)
            assertEquals(2, registry.peers.value.size)

            registry.close()

            assertTrue(registry.peers.value.isEmpty())
            assertNull(registry.lastSeen(PeerId("discovered")))
            registry.processEvent(PeerEvent.Found(peer("late")))
            assertTrue(registry.peers.value.isEmpty())
            assertFailsWith<IllegalStateException> {
                registry.registerManualPeer("192.0.2.46", 9_046)
            }
        } finally {
            supervisor.cancel()
        }
    }

    @OptIn(ExperimentalP2pApi::class)
    @Test
    fun closeWinsAgainstManualRegistrationAlreadyAtItsCompareAndSetBoundary() {
        val supervisor = SupervisorJob()
        try {
            lateinit var registry: PeerRegistry
            var closeInjected = false
            registry = PeerRegistry(
                discoveryTransports = emptyList(),
                scope = CoroutineScope(Dispatchers.Unconfined + supervisor),
                clock = { 1_000L },
                staleTimeoutMillis = 60_000,
                evictionPollMillis = Long.MAX_VALUE / 2,
                beforeManualPeerCompareAndSetForTest = {
                    if (!closeInjected) {
                        closeInjected = true
                        registry.close()
                    }
                }
            )

            assertFailsWith<IllegalStateException> {
                registry.registerManualPeer("192.0.2.47", 9_047)
            }
            assertTrue(registry.peers.value.isEmpty())
        } finally {
            supervisor.cancel()
        }
    }

    private class FakeDiscovery(
        override val type: TransportKind = TransportKind.LAN
    ) : DiscoveryTransport {
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
