package dev.p2pkit.core.internal

import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.DiscoveryLifetime
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.PeerAuthenticationHint
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportHint
import dev.p2pkit.core.transport.TransportSecurityProfile
import dev.p2pkit.core.transport.withDiscoveryLifetime
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull

@OptIn(ExperimentalP2pApi::class)
class PeerDiscoveryClaimTest {
    private val pin = PeerFingerprint("p2f1-" + "a".repeat(52))
    private val id = PeerId("discovery-only-test")
    private fun peer() = InternalPeer(
        Peer(id, "Untrusted discovery name", Platform.IOS, setOf(TransportKind.LAN)),
        listOf(TransportHint(TransportKind.LAN, "10.1.2.3", 5432)),
        authenticationHint = PeerAuthenticationHint.UntrustedDiscoveryClaim(pin),
    )

    @Test
    fun claimExpiresBeforeEvictionPollAndCannotSurviveLostOrClose() = runTest {
        var now = 0L
        val registry = PeerRegistry(emptyList(), backgroundScope, { now }, staleTimeoutMillis = 100)
        registry.processEvent(PeerEvent.Found(peer()))
        val first = assertNotNull(registry.discoveryClaim(id))
        assertEquals(pin, first.fingerprint)
        now = 101
        assertNull(registry.discoveryClaim(id))
        registry.processEvent(PeerEvent.Found(peer()))
        assertNotNull(registry.discoveryClaim(id))
        registry.processEvent(PeerEvent.Lost(id))
        assertNull(registry.discoveryClaim(id))
        registry.processEvent(PeerEvent.Found(peer()))
        registry.close()
        assertNull(registry.discoveryClaim(id))
        assertEquals(0L, first.lastSeenMillis) // Published values remain immutable snapshots.
    }

    @Test
    fun transportManagedClaimFollowsBrowserOwnershipNotHeartbeatExpiry() = runTest {
        var now = 0L
        val registry = PeerRegistry(emptyList(), backgroundScope, { now }, staleTimeoutMillis = 100)
        registry.processEvent(PeerEvent.Found(peer().copy(transportHints = peer().transportHints.map {
            it.withDiscoveryLifetime(DiscoveryLifetime.TransportManaged)
        })))
        now = 100_000
        assertNotNull(registry.discoveryClaim(id))
        registry.processEvent(PeerEvent.Lost(id))
        assertNull(registry.discoveryClaim(id))
        registry.close()
    }

    @Test
    fun manualPinAndDisplayNameNeverMasqueradeAsDiscoveredIdentity() = runTest {
        val registry = PeerRegistry(emptyList(), backgroundScope, { 0L },
            securityProfile = TransportSecurityProfile.AuthenticatedV2, peerIdFromFingerprint = { id })
        val manualPin = PeerFingerprint("p2f1-" + "b".repeat(51) + "a")
        registry.registerManualPeer("10.1.2.4", 5432, deviceName = "Manual trusted name",
            expectedFingerprint = manualPin)
        assertNull(registry.discoveryClaim(id))
        registry.processEvent(PeerEvent.Found(peer()))
        val claim = assertNotNull(registry.discoveryClaim(id))
        assertEquals(pin, claim.fingerprint)
        assertEquals("Untrusted discovery name", claim.peer.name)
        registry.processEvent(PeerEvent.Lost(id))
        assertNull(registry.discoveryClaim(id))
        assertNotNull(registry.internalPeer(id)) // Retained manual record isn't discovery.
        registry.close()
    }

    @Test
    fun unsignedOrReplacedClaimsDoNotReuseAnEarlierPin() = runTest {
        val registry = PeerRegistry(emptyList(), backgroundScope, { 0L })
        registry.processEvent(PeerEvent.Found(peer()))
        assertNotNull(registry.discoveryClaim(id))
        registry.processEvent(PeerEvent.Updated(peer().copy(authenticationHint = null)))
        assertNull(registry.discoveryClaim(id))
        registry.close()
    }
}
