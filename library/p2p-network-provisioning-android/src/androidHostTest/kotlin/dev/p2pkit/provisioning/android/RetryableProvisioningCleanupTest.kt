package dev.p2pkit.provisioning.android

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class RetryableProvisioningCleanupTest {

    @Test
    fun registryRetainsOneIdentityEntryAndRemovesItAfterSuccessfulRetry() {
        val registry = RetryableCleanupRegistry()
        val owner = Any()
        var attempts = 0
        val cleanup = {
            attempts += 1
            if (attempts < 3) error("simulated cleanup failure")
        }

        assertNotNull(registry.runOrRetain(owner, cleanup))
        assertNotNull(registry.runOrRetain(owner, cleanup))
        assertEquals(1, registry.pendingCount(), "same owner must not create duplicate retained work")

        assertTrue(registry.retryAll().isEmpty())
        assertEquals(3, attempts)
        assertEquals(0, registry.pendingCount())
        assertTrue(registry.retryAll().isEmpty())
    }

    @Test
    fun nativeRequestGateRemainsOwnedUntilARealTerminalCallback() {
        val request = PendingNativeRequest()

        val first = assertNotNull(request.tryBegin())
        assertTrue(request.isPending())
        assertEquals(null, request.tryBegin(), "caller cancellation must not permit a second native request")

        request.complete(first)
        assertFalse(request.isPending())
        val second = assertNotNull(request.tryBegin())
        request.complete(first)
        assertTrue(request.isPending(), "a stale callback must not release the newer request generation")
        request.complete(second)
        assertFalse(request.isPending())
    }

    @Test
    fun failedUnbindKeepsBindingTokenUntilARealRetrySucceeds() {
        var clearAttempts = 0
        var unregisterAttempts = 0
        var tokenReleases = 0
        var rebindCalls = 0
        val reports = mutableListOf<String>()
        val cleanup = RetryableJoinCleanup(
            clearProcessBinding = {
                clearAttempts += 1
                clearAttempts > 1
            },
            unregisterCallback = { unregisterAttempts += 1 },
            releaseBindingToken = { tokenReleases += 1 },
            report = reports::add
        )
        assertTrue(cleanup.bindInitial { true })

        assertFailsWith<IllegalStateException> { cleanup.close() }
        assertEquals(1, clearAttempts)
        assertEquals(1, unregisterAttempts)
        assertEquals(0, tokenReleases, "token must remain held while the old binding may still be active")
        assertFalse(cleanup.rebind { rebindCalls += 1; true })
        assertEquals(0, rebindCalls, "terminal cleanup must reject queued rebind callbacks")
        assertTrue(reports.any { it.contains("binding clear") })

        cleanup.close()
        assertEquals(2, clearAttempts)
        assertEquals(1, unregisterAttempts, "successful callback cleanup must not repeat")
        assertEquals(1, tokenReleases)

        cleanup.close()
        assertEquals(2, clearAttempts)
        assertEquals(1, unregisterAttempts)
        assertEquals(1, tokenReleases)
    }

    @Test
    fun callbackFailureRetriesIndependentlyAfterBindingWasCleared() {
        var clearAttempts = 0
        var unregisterAttempts = 0
        var tokenReleases = 0
        val cleanup = RetryableJoinCleanup(
            clearProcessBinding = { clearAttempts += 1; true },
            unregisterCallback = {
                unregisterAttempts += 1
                if (unregisterAttempts == 1) error("simulated unregister failure")
            },
            releaseBindingToken = { tokenReleases += 1 },
            report = {}
        )
        assertTrue(cleanup.bindInitial { true })

        assertFailsWith<IllegalStateException> { cleanup.close() }
        assertEquals(1, clearAttempts)
        assertEquals(1, tokenReleases)
        assertEquals(1, unregisterAttempts)

        cleanup.close()
        assertEquals(1, clearAttempts, "a cleared binding must not be cleared again")
        assertEquals(1, tokenReleases, "a released token must not be released again")
        assertEquals(2, unregisterAttempts)
    }

    @Test
    fun neverInstalledBindingDoesNotClearAnUnrelatedProcessRoute() {
        var clearAttempts = 0
        var unregisterAttempts = 0
        var tokenReleases = 0
        val cleanup = RetryableJoinCleanup(
            clearProcessBinding = { clearAttempts += 1; true },
            unregisterCallback = { unregisterAttempts += 1 },
            releaseBindingToken = { tokenReleases += 1 },
            report = {}
        )

        cleanup.close()

        assertEquals(0, clearAttempts)
        assertEquals(1, unregisterAttempts)
        assertEquals(1, tokenReleases)
    }

    @Test
    fun terminalCleanupPreventsALateInitialProcessBinding() {
        var bindAttempts = 0
        val cleanup = RetryableJoinCleanup(
            clearProcessBinding = { true },
            unregisterCallback = {},
            releaseBindingToken = {},
            report = {}
        )

        cleanup.close()

        assertFalse(cleanup.bindInitial { bindAttempts += 1; true })
        assertEquals(0, bindAttempts)
    }

    @Test
    fun successfulRebindBecomesTheBindingThatTerminalCleanupClears() {
        var clearAttempts = 0
        var tokenReleases = 0
        val cleanup = RetryableJoinCleanup(
            clearProcessBinding = { clearAttempts += 1; true },
            unregisterCallback = {},
            releaseBindingToken = { tokenReleases += 1 },
            report = {}
        )

        assertTrue(cleanup.rebind { true })
        cleanup.close()

        assertEquals(1, clearAttempts)
        assertEquals(1, tokenReleases)
        cleanup.close()
    }

    @Test
    fun delayedLossCannotClaimAReboundNetworkGeneration() {
        val lease = CurrentNetworkLease("network-a")
        var claims = 0

        assertTrue(lease.rebind("network-b", canRebind = { true }, bind = { true }))
        assertEquals("network-b", lease.snapshot())
        assertFalse(
            lease.claimLoss("network-a", canClaim = { true }, onClaim = { claims += 1 }),
            "a delayed loss for the superseded network must be ignored"
        )
        assertEquals(0, claims)

        assertTrue(lease.claimLoss("network-b", canClaim = { true }, onClaim = { claims += 1 }))
        assertEquals(1, claims)
        assertFalse(lease.rebind("network-c", canRebind = { true }, bind = { true }))
        assertEquals("network-b", lease.snapshot())
    }

    @Test
    fun failedOwnershipCheckDoesNotTerminallyConsumeCurrentNetwork() {
        val lease = CurrentNetworkLease("network-a")

        assertFalse(lease.claimLoss("network-a", canClaim = { false }, onClaim = {}))
        assertTrue(lease.rebind("network-b", canRebind = { true }, bind = { true }))
        assertEquals("network-b", lease.snapshot())
    }

    @Test
    fun joinDeliveryAndTerminalCallbackHaveOneLinearizedWinner() {
        val deliveredOwner = JoinCallbackOwner<String>()
        assertTrue(deliveredOwner.claimInitial())
        assertTrue(deliveredOwner.install("network"))
        var deliveries = 0
        assertTrue(deliveredOwner.tryDeliver("network") { deliveries += 1; true })
        val afterDelivery = deliveredOwner.closeAndTakeWithDelivery()
        assertTrue(afterDelivery.newlyClosed)
        assertTrue(afterDelivery.wasDelivered)
        assertEquals("network", afterDelivery.handle)
        assertEquals(1, deliveries)

        val lostBeforeDelivery = JoinCallbackOwner<String>()
        assertTrue(lostBeforeDelivery.claimInitial())
        assertTrue(lostBeforeDelivery.install("network"))
        val beforeDelivery = lostBeforeDelivery.closeAndTakeWithDelivery()
        assertTrue(beforeDelivery.newlyClosed)
        assertFalse(beforeDelivery.wasDelivered)
        assertEquals("network", beforeDelivery.handle)
        assertFalse(lostBeforeDelivery.tryDeliver("network") { deliveries += 1; true })
        assertEquals(1, deliveries, "terminal loss must suppress a late success delivery")
    }
}
