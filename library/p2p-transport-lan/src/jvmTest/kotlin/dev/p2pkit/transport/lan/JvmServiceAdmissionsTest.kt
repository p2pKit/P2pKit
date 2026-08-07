package dev.p2pkit.transport.lan

import dev.p2pkit.core.PeerId
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Deterministic contract for TXT-less JmDNS removal ownership. */
class JvmServiceAdmissionsTest {

    @Test
    fun admittedInstanceOwnsExactPeerIdForOneRemoval() {
        val admissions = JvmServiceAdmissions()
        val lease = JvmListenerLease()
        val peerId = PeerId("peer-admitted")

        admissions.admit("service-instance", peerId, lease)

        assertEquals(peerId, admissions.remove("service-instance", lease))
        assertNull(admissions.remove("service-instance", lease))
        assertNull(admissions.remove("never-admitted", lease))
    }

    @Test
    fun staleListenerCannotWithdrawNewerActiveOwnership() {
        val admissions = JvmServiceAdmissions()
        val stale = JvmListenerLease()
        val current = JvmListenerLease()
        val peerId = PeerId("peer-current")
        admissions.admit("service-instance", peerId, current)

        assertNull(admissions.remove("service-instance", stale))
        assertEquals(peerId, admissions.remove("service-instance", current))
    }

    @Test
    fun currentListenerCanConsumeRemovalOwnedByInactivePredecessor() {
        val admissions = JvmServiceAdmissions()
        val predecessor = JvmListenerLease()
        val current = JvmListenerLease()
        val peerId = PeerId("peer-predecessor")
        admissions.admit("service-instance", peerId, predecessor)
        predecessor.deactivate()

        assertEquals(peerId, admissions.remove("service-instance", current))
    }

    @Test
    fun terminalDrainDeduplicatesPeerIdsAndClearsOwnership() {
        val admissions = JvmServiceAdmissions()
        val lease = JvmListenerLease()
        val first = PeerId("peer-first")
        val second = PeerId("peer-second")
        admissions.admit("first-a", first, lease)
        admissions.admit("first-b", first, lease)
        admissions.admit("second", second, lease)

        assertEquals(setOf(first, second), admissions.drain())
        assertTrue(admissions.drain().isEmpty())
    }

    @Test
    fun deactivatedLeaseRejectsQueuedPublication() {
        val lease = JvmListenerLease()
        var publications = 0
        lease.publishIfActive { publications += 1 }
        lease.deactivate()
        lease.publishIfActive { publications += 1 }

        assertEquals(1, publications)
    }
}
