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

/** Deterministic contract for Android JmDNS removals with no ServiceInfo/TXT. */
class AndroidServiceAdmissionsTest {
    @Test
    fun unauthenticatedServiceOwnershipIsBounded() {
        val admissions = AndroidServiceAdmissions()
        val lease = AndroidListenerLease()
        repeat(MAX_TRACKED_LAN_PEERS) { index ->
            assertTrue(admissions.admit("service-$index", PeerId("peer-$index"), lease))
        }

        assertFalse(admissions.admit("overflow", PeerId("overflow"), lease))
        assertEquals(MAX_TRACKED_LAN_PEERS, admissions.sizeForTest())
        assertTrue(admissions.admit("service-0", PeerId("peer-updated"), lease))
        assertEquals(MAX_TRACKED_LAN_PEERS, admissions.sizeForTest())
    }

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
    fun invalidResolutionWithdrawalIsFencedFromANewerListener() {
        val admissions = AndroidServiceAdmissions()
        val retired = AndroidListenerLease()
        val current = AndroidListenerLease()
        val currentPeer = PeerId("peer-current")
        admissions.admit("service-instance", currentPeer, current)
        retired.activate()

        var retiredWithdrawal: PeerId? = null
        retired.publishIfActive("service-instance") {
            retiredWithdrawal = admissions.remove("service-instance", retired)
        }

        assertNull(retiredWithdrawal)
        assertEquals(currentPeer, admissions.remove("service-instance", current))
    }

    @Test
    fun stagedFreshInvalidationWinsOverOldCallbacksDuringListenerRotation() {
        val admissions = AndroidServiceAdmissions()
        val predecessor = AndroidListenerLease().also { it.activate() }
        val fresh = AndroidListenerLease()
        val stalePeer = PeerId("stale-peer")
        var withdrawn: PeerId? = null

        fresh.publishIfActive("service-instance") {
            withdrawn = admissions.remove("service-instance", fresh)
        }
        assertNull(withdrawn)

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
        val lease = AndroidListenerLease(maxStagedInstances = 2) { publications += "reset" }

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

    @Test
    fun newerInvalidResolutionWithdrawsAndFencesAnActivePredecessor() {
        val admissions = AndroidServiceAdmissions()
        val predecessor = AndroidListenerLease()
        val current = AndroidListenerLease()
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
        val admissions = AndroidServiceAdmissions()
        val predecessor = AndroidListenerLease()
        val failedFresh = AndroidListenerLease()
        val peer = PeerId("peer")
        admissions.admit("service-instance", peer, predecessor)
        assertEquals(peer, admissions.remove("service-instance", failedFresh))

        failedFresh.deactivate()
        admissions.listenerDeactivated(failedFresh)

        assertTrue(admissions.admit("service-instance", peer, predecessor))
    }

    @Test
    fun relayPublicationAndNewerInvalidationAreSerialized() {
        val admissions = AndroidServiceAdmissions()
        val predecessor = AndroidListenerLease()
        val current = AndroidListenerLease()
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
    fun repeatedInvalidResolutionWithdrawsCurrentOwnershipExactlyOnce() {
        val admissions = AndroidServiceAdmissions()
        val current = AndroidListenerLease()
        val peer = PeerId("peer-current")
        admissions.admit("service-instance", peer, current)

        assertEquals(peer, admissions.remove("service-instance", current))
        assertNull(admissions.remove("service-instance", current))
        assertEquals(0, admissions.sizeForTest())
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

    @Test
    fun retiredNetworkWatcherLeaseCannotPublishIntoANewLifetime() {
        val retired = AndroidNetworkWatcherLease()
        val current = AndroidNetworkWatcherLease()
        var retiredPublications = 0
        var currentPublications = 0

        retired.publishIfActive { retiredPublications++ }
        retired.deactivate()
        retired.publishIfActive { retiredPublications++ }
        current.publishIfActive { currentPublications++ }

        assertEquals(1, retiredPublications)
        assertEquals(1, currentPublications)
        assertTrue(current.isActive())
    }

    @Test
    fun losingTheObservedOrSelectedPrimaryNetworkRequiresSelectorReconciliation() {
        val fallbackAlreadyAvailable = "wifi-a"
        val boundThenLost = "ethernet-b"

        val currentLoss = androidPrimaryNetworkLoss(
            observed = boundThenLost,
            selected = boundThenLost,
            lost = boundThenLost
        )
        val selectedLossWithObservedFallback = androidPrimaryNetworkLoss(
            observed = fallbackAlreadyAvailable,
            selected = boundThenLost,
            lost = boundThenLost
        )
        val unrelatedLoss = androidPrimaryNetworkLoss(
            observed = fallbackAlreadyAvailable,
            selected = fallbackAlreadyAvailable,
            lost = boundThenLost
        )

        assertNull(currentLoss.observedAfterLoss)
        assertTrue(currentLoss.requiresSelectorReconciliation)
        assertEquals(
            fallbackAlreadyAvailable,
            selectedLossWithObservedFallback.observedAfterLoss
        )
        assertTrue(selectedLossWithObservedFallback.requiresSelectorReconciliation)
        assertEquals(fallbackAlreadyAvailable, unrelatedLoss.observedAfterLoss)
        assertEquals(false, unrelatedLoss.requiresSelectorReconciliation)
    }
}
