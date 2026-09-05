package dev.p2pkit.provisioning.android

import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference
import java.util.concurrent.locks.LockSupport
import kotlin.concurrent.thread
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertSame
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
    fun initialBindingRetainsTheOuterLeaseUntilTheNativeBindCompletes() {
        val lease = CurrentNetworkLease("network")
        val owner = JoinCallbackOwner<Any>()
        val handle = Any()
        assertTrue(owner.claimInitial())
        assertTrue(owner.install(handle))
        val nativeBindEntered = CountDownLatch(1)
        val releaseNativeBind = CountDownLatch(1)
        val closeBodyEntered = AtomicBoolean()
        val bound = AtomicBoolean()
        val failure = AtomicReference<Throwable?>()
        var clearCalls = 0
        var unregisterCalls = 0
        var tokenReleases = 0
        val cleanup = RetryableJoinCleanup(
            clearProcessBinding = { clearCalls += 1; true },
            unregisterCallback = { unregisterCalls += 1 },
            releaseBindingToken = { tokenReleases += 1 },
            report = {}
        )
        val binder = checkedThread("initial-bind", failure) {
            bound.set(lease.bindInitial(cleanup) { network ->
                assertEquals("network", network)
                nativeBindEntered.countDown()
                assertTrue(releaseNativeBind.await(5, TimeUnit.SECONDS), "native bind was not released")
                true
            })
        }
        var closer: Thread? = null
        try {
            assertTrue(nativeBindEntered.await(5, TimeUnit.SECONDS), "native bind was not reached")
            closer = checkedThread("join-close", failure) {
                // Same order as continuation cancellation after handle install:
                // take the callback owner, then close outside its monitor.
                assertSame(handle, owner.closeAndTake())
                lease.close {
                    closeBodyEntered.set(true)
                    owner.markClosed(handle)
                    cleanup.close()
                }
            }
            awaitMonitorWait(closer)
            assertFalse(
                closeBodyEntered.get(),
                "close must wait on the outer lease, not hold it while waiting on the cleanup monitor"
            )
        } finally {
            releaseNativeBind.countDown()
            binder.join(5_000)
            closer?.join(5_000)
            assertFalse(binder.isAlive, "initial bind thread leaked")
            assertFalse(closer?.isAlive == true, "close thread leaked")
        }
        failure.get()?.let { throw AssertionError("binding/close worker failed", it) }
        assertTrue(bound.get())
        assertTrue(closeBodyEntered.get())
        assertFalse(owner.tryDeliver(handle) { error("cancelled join was delivered") })
        assertEquals(1, clearCalls)
        assertEquals(1, unregisterCalls)
        assertEquals(1, tokenReleases)
        lease.close { cleanup.close() }
        assertFalse(lease.bindInitial(cleanup) { error("terminal lease rebound") })
        assertFalse(lease.rebind("late", canRebind = { true }, bind = { error("terminal lease rebound") }))
        assertEquals(1, clearCalls)
        assertEquals(1, unregisterCalls)
        assertEquals(1, tokenReleases)
    }

    @Test
    fun terminalLeaseRejectsInitialBindingBeforeNativeCleanupRuns() {
        for (lost in listOf(false, true)) {
            val lease = CurrentNetworkLease("network")
            var nativeBinds = 0
            var tokenReleases = 0
            val cleanup = RetryableJoinCleanup(
                clearProcessBinding = { error("no binding was installed") },
                unregisterCallback = {},
                releaseBindingToken = { tokenReleases += 1 },
                report = {}
            )
            if (lost) {
                assertTrue(lease.claimLoss("network", canClaim = { true }, onClaim = {}))
            }
            lease.close {
                // The lease is terminal even while the independently retryable
                // native cleanup has not begun. Reentrant callbacks must not bind.
                assertFalse(lease.bindInitial(cleanup) { nativeBinds += 1; true })
                cleanup.close()
            }
            assertEquals(0, nativeBinds)
            assertEquals(1, tokenReleases)
        }
    }

    @Test
    fun failedInitialBindingSealsTheLeaseBeforeItsCallerCanStartCleanup() {
        for (throws in listOf(false, true)) {
            val lease = CurrentNetworkLease("network")
            var bindCalls = 0
            var unregisterCalls = 0
            var tokenReleases = 0
            val cleanup = RetryableJoinCleanup(
                clearProcessBinding = { error("rejected binding must not clear an unrelated route") },
                unregisterCallback = { unregisterCalls += 1 },
                releaseBindingToken = { tokenReleases += 1 },
                report = {}
            )
            val bind = {
                lease.bindInitial(cleanup) {
                    bindCalls += 1
                    if (throws) throw SecurityException("synthetic permission failure")
                    false
                }
            }
            if (throws) assertFailsWith<SecurityException> { bind() } else assertFalse(bind())
            assertFalse(lease.bindInitial(cleanup) { bindCalls += 1; true })
            assertFalse(lease.rebind("late", canRebind = { true }, bind = { bindCalls += 1; true }))
            assertEquals(1, bindCalls)
            lease.close { cleanup.close() }
            assertEquals(1, unregisterCalls)
            assertEquals(1, tokenReleases)
        }
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
    fun rejectedRebindCannotResurrectTheJoinWhileManagerCleanupIsPending() {
        for (throws in listOf(false, true)) {
            val lease = CurrentNetworkLease("network-a")
            val owner = JoinCallbackOwner<Any>()
            val handle = Any()
            var bindAttempts = 0
            var clearAttempts = 0
            var unregisterAttempts = 0
            var tokenReleases = 0
            val cleanup = RetryableJoinCleanup(
                clearProcessBinding = { clearAttempts += 1; true },
                unregisterCallback = { unregisterAttempts += 1 },
                releaseBindingToken = { tokenReleases += 1 },
                report = {}
            )
            assertTrue(owner.claimInitial())
            assertTrue(owner.install(handle))
            assertTrue(cleanup.bindInitial { true })

            assertFalse(
                lease.rebind("network-b", canRebind = { owner.current() === handle }, bind = {
                    cleanup.rebind {
                        bindAttempts += 1
                        if (throws) throw SecurityException("synthetic binding rejection")
                        false
                    }
                })
            )
            // The wrapper emits `released` now. The manager may be waiting
            // behind another OS acquisition, but a new onAvailable must not bind.
            assertFalse(
                lease.rebind("network-c", canRebind = { owner.current() === handle }, bind = {
                    cleanup.rebind { bindAttempts += 1; true }
                })
            )
            assertEquals(1, bindAttempts)
            assertEquals("network-a", lease.snapshot())
            assertEquals(0, clearAttempts, "notification is not a native cleanup acknowledgement")
            assertSame(handle, owner.current(), "pre-delivery cancellation must still own the handle")

            lease.close {
                assertSame(handle, owner.closeAndTake())
                cleanup.close()
            }
            assertEquals(1, clearAttempts)
            assertEquals(1, unregisterAttempts)
            assertEquals(1, tokenReleases)
        }
    }

    @Test
    fun rejectedRebindOwnershipIsTerminalWithoutCallingThePlatform() {
        val lease = CurrentNetworkLease("network-a")
        var bindAttempts = 0
        assertFalse(lease.rebind("network-b", canRebind = { false }, bind = { bindAttempts += 1; true }))
        assertFalse(lease.rebind("network-c", canRebind = { true }, bind = { bindAttempts += 1; true }))
        assertEquals(0, bindAttempts)
        assertEquals("network-a", lease.snapshot())
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

    private fun checkedThread(
        name: String,
        failure: AtomicReference<Throwable?>,
        block: () -> Unit
    ): Thread = thread(name = "p2pkit-$name-test", isDaemon = true) {
        try {
            block()
        } catch (caught: Throwable) {
            failure.compareAndSet(null, caught)
        }
    }

    private fun awaitMonitorWait(worker: Thread) {
        val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
        while (worker.state != Thread.State.BLOCKED && worker.isAlive && System.nanoTime() < deadline) {
            LockSupport.parkNanos(TimeUnit.MILLISECONDS.toNanos(1))
        }
        assertEquals(Thread.State.BLOCKED, worker.state, "worker did not reach the contested monitor")
    }
}
