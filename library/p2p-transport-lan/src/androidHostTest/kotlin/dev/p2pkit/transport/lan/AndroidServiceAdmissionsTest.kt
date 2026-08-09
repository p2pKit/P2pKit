package dev.p2pkit.transport.lan

import dev.p2pkit.core.PeerId
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Deterministic contract for Android JmDNS removals with no ServiceInfo/TXT. */
class AndroidServiceAdmissionsTest {
    @Test
    fun instanceNameRecoversExactPeerIdWithoutRemovalMetadata() {
        val admissions = AndroidServiceAdmissions()
        val lease = AndroidListenerLease()
        val peerId = PeerId("peer-admitted")
        admissions.admit("service-instance", peerId, lease)

        assertEquals(peerId, admissions.remove("service-instance", lease))
        assertNull(admissions.remove("service-instance", lease))
        assertNull(admissions.remove("unknown", lease))
    }

    @Test
    fun staleGenerationCannotRemoveNewActiveOwnership() {
        val admissions = AndroidServiceAdmissions()
        val stale = AndroidListenerLease()
        val current = AndroidListenerLease()
        val peerId = PeerId("peer-current")
        admissions.admit("service-instance", peerId, current)

        assertNull(admissions.remove("service-instance", stale))
        assertEquals(peerId, admissions.remove("service-instance", current))
    }

    @Test
    fun currentGenerationCanConsumeInactivePredecessorOwnership() {
        val admissions = AndroidServiceAdmissions()
        val predecessor = AndroidListenerLease()
        val current = AndroidListenerLease()
        val peerId = PeerId("peer-predecessor")
        admissions.admit("service-instance", peerId, predecessor)
        predecessor.deactivate()

        assertEquals(peerId, admissions.remove("service-instance", current))
    }

    @Test
    fun terminalDrainDeduplicatesAndClearsAllOwnership() {
        val admissions = AndroidServiceAdmissions()
        val lease = AndroidListenerLease()
        val peer = PeerId("peer")
        admissions.admit("first", peer, lease)
        admissions.admit("second", peer, lease)

        assertEquals(setOf(peer), admissions.drain())
        assertTrue(admissions.drain().isEmpty())
    }
}
