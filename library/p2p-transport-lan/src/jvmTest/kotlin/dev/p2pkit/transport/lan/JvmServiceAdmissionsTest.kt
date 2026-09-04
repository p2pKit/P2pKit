package dev.p2pkit.transport.lan

import dev.p2pkit.core.PeerId
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.concurrent.thread
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Deterministic contract for TXT-less JmDNS removal ownership. */
class JvmServiceAdmissionsTest {

    @Test
    fun unauthenticatedServiceOwnershipIsBounded() {
        val admissions = JvmServiceAdmissions()
        val lease = JvmListenerLease()
        repeat(MAX_TRACKED_LAN_PEERS) { index ->
            assertTrue(admissions.admit("service-$index", PeerId("peer-$index"), lease))
        }

        assertFalse(admissions.admit("overflow", PeerId("overflow"), lease))
        assertEquals(MAX_TRACKED_LAN_PEERS, admissions.sizeForTest())
        assertTrue(admissions.admit("service-0", PeerId("peer-updated"), lease))
        assertEquals(MAX_TRACKED_LAN_PEERS, admissions.sizeForTest())
    }

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
    fun newerInvalidResolutionWithdrawsAndFencesAnActivePredecessor() {
        val admissions = JvmServiceAdmissions()
        val predecessor = JvmListenerLease()
        val current = JvmListenerLease()
        val priorPeer = PeerId("peer-prior")
        admissions.admit("service-instance", priorPeer, predecessor)

        assertEquals(priorPeer, admissions.remove("service-instance", current))
        assertEquals(0, admissions.sizeForTest())
        assertFalse(
            admissions.admit("service-instance", PeerId("stale-peer"), predecessor),
            "the overlapping old listener must not restore invalidated state"
        )

        val currentPeer = PeerId("peer-current")
        assertTrue(admissions.admit("service-instance", currentPeer, current))
        assertFalse(admissions.admit("service-instance", PeerId("stale-peer"), predecessor))
        assertEquals(currentPeer, admissions.remove("service-instance", current))
        assertFalse(
            admissions.admit("service-instance", PeerId("stale-after-invalid"), predecessor),
            "a valid→invalid transition on the new listener must retain the predecessor fence"
        )

        predecessor.deactivate()
        admissions.listenerDeactivated(predecessor)
        assertTrue(admissions.admit("service-instance", currentPeer, current))
    }

    @Test
    fun failedFreshListenerCanReturnOwnershipToTheStillActivePredecessor() {
        val admissions = JvmServiceAdmissions()
        val predecessor = JvmListenerLease()
        val failedFresh = JvmListenerLease()
        val peer = PeerId("peer")
        admissions.admit("service-instance", peer, predecessor)
        assertEquals(peer, admissions.remove("service-instance", failedFresh))

        failedFresh.deactivate()
        admissions.listenerDeactivated(failedFresh)

        assertTrue(admissions.admit("service-instance", peer, predecessor))
    }

    @Test
    fun relayPublicationAndNewerInvalidationAreSerialized() {
        val admissions = JvmServiceAdmissions()
        val predecessor = JvmListenerLease()
        val current = JvmListenerLease()
        val publicationEntered = CountDownLatch(1)
        val releasePublication = CountDownLatch(1)
        val invalidationStarted = CountDownLatch(1)
        val invalidationFinished = CountDownLatch(1)
        val relayPresent = AtomicBoolean(false)

        val publisher = thread(name = "old-listener-publish") {
            admissions.admitAndPublish("service-instance", PeerId("peer"), predecessor) {
                publicationEntered.countDown()
                check(releasePublication.await(5, TimeUnit.SECONDS))
                relayPresent.set(true)
                true
            }
        }
        assertTrue(publicationEntered.await(5, TimeUnit.SECONDS))
        val invalidator = thread(name = "new-listener-invalidate") {
            invalidationStarted.countDown()
            admissions.removeAndPublish("service-instance", current) {
                relayPresent.set(false)
            }
            invalidationFinished.countDown()
        }
        assertTrue(invalidationStarted.await(5, TimeUnit.SECONDS))
        assertFalse(
            invalidationFinished.await(100, TimeUnit.MILLISECONDS),
            "invalidation must wait until publication completes"
        )

        releasePublication.countDown()
        publisher.join(5_000)
        invalidator.join(5_000)

        assertFalse(publisher.isAlive)
        assertFalse(invalidator.isAlive)
        assertFalse(relayPresent.get())
        assertEquals(0, admissions.sizeForTest())
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
        lease.publishIfActive("peer") { publications += 1 }
        assertEquals(0, publications, "an uncommitted listener must stage callbacks")
        lease.activate()
        assertEquals(1, publications)
        lease.deactivate()
        lease.publishIfActive("peer") { publications += 1 }

        assertEquals(1, publications)
    }

    @Test
    fun stagedFreshInvalidationWinsOverOldCallbacksDuringListenerRotation() {
        val admissions = JvmServiceAdmissions()
        val predecessor = JvmListenerLease().also { it.activate() }
        val fresh = JvmListenerLease()
        val stalePeer = PeerId("stale-peer")
        var withdrawn: PeerId? = null

        // JmDNS can invoke the fresh listener synchronously from add. Its
        // invalid result must not take effect until the predecessor retires.
        fresh.publishIfActive("service-instance") {
            withdrawn = admissions.remove("service-instance", fresh)
        }
        assertNull(withdrawn)

        // A predecessor callback that was already runnable is ordered before
        // the staged fresh callback and is subsequently withdrawn.
        predecessor.publishIfActive("service-instance") {
            admissions.admit("service-instance", stalePeer, predecessor)
        }
        predecessor.deactivate()
        admissions.listenerDeactivated(predecessor)
        fresh.activate()

        assertEquals(stalePeer, withdrawn)
        assertEquals(0, admissions.sizeForTest())
        predecessor.publishIfActive("service-instance") {
            admissions.admit("service-instance", PeerId("late-stale-peer"), predecessor)
        }
        assertEquals(0, admissions.sizeForTest())
    }

    @Test
    fun stagedCallbacksAreLatestPerInstanceAndBounded() {
        val publications = mutableListOf<String>()
        val lease = JvmListenerLease(maxStagedInstances = 2) { publications += "reset" }

        lease.publishIfActive("first") { publications += "first-old" }
        lease.publishIfActive("second") { publications += "second" }
        lease.publishIfActive("first") { publications += "first-latest" }
        lease.publishIfActive("third") { publications += "third" }

        assertEquals(2, lease.stagedCountForTest())
        assertTrue(publications.isEmpty())
        lease.activate()

        assertEquals(listOf("reset", "first-latest", "third"), publications)
        assertEquals(0, lease.stagedCountForTest())
    }
}
