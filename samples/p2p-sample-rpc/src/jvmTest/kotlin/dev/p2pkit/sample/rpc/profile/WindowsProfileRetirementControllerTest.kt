package dev.p2pkit.sample.rpc.profile

import java.io.IOException
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Injected controller faults only: no actual memory exhaustion, DLL, NTFS or installed runtime. */
class WindowsProfileRetirementControllerTest {
    @Test
    fun controllerErrorBeforeTheFirstCloseRetainsEveryOwnerAndSealsRetries() {
        val model = WindowsProfileModel()
        val original = OutOfMemoryError("synthetic cleanup-controller allocation failure")
        var observations = 0
        val files = WindowsProfileFiles.openForValidation(model) { observations++; throw original }
        val root = files.root
        root.child("identity", create = true).lock("vault.lock", nonBlocking = true)
        val failure = assertFailsWith<WindowsProfileFiles.RetirementFailure> { files.close() }
        assertSame(files, failure.retainedSession)
        assertSame(original, failure.cause)
        assertEquals(null, failure.priorFailure)
        assertTrue(failure.suppressed.isEmpty())
        assertTrue(original.suppressed.isEmpty())
        assertEquals(3, files.retainedHandleCount)
        assertEquals(3, model.remaining)
        assertTrue(model.closeCalls.isEmpty())
        assertTrue(files.retirementStarted)
        assertFails { files.root }
        assertFails { root.exists("profile.header") }
        repeat(2) { assertSame(failure, assertFailsWith<WindowsProfileFiles.RetirementFailure> { files.close() }) }
        assertEquals(1, observations)
        assertTrue(model.closeCalls.isEmpty())
    }

    @Test
    fun controllerErrorAfterPartialDrainRetainsOnlyTheUnretiredOriginalHandles() {
        val model = WindowsProfileModel()
        val original = OutOfMemoryError("synthetic partial-drain controller failure")
        var observations = 0
        val files = WindowsProfileFiles.openForValidation(model) {
            if (++observations == 2) throw original
        }
        files.root.child("identity", create = true).lock("vault.lock", nonBlocking = true)
        val failure = assertFailsWith<WindowsProfileFiles.RetirementFailure> { files.close() }
        assertSame(original, failure.cause)
        assertSame(files, failure.retainedSession)
        assertEquals(listOf(3L), model.closeCalls)
        assertEquals(2, files.retainedHandleCount)
        assertEquals(2, model.remaining)
        repeat(2) { assertSame(failure, assertFailsWith<WindowsProfileFiles.RetirementFailure> { files.close() }) }
        assertEquals(listOf(3L), model.closeCalls)
        assertEquals(2, observations)
    }

    @Test
    fun controllerErrorPreservesThePriorNativeFailureWithoutSuppressionOrRetry() {
        val model = WindowsProfileModel()
        val nativeFailure = IOException("synthetic original lease retirement failure")
        val controllerFailure = OutOfMemoryError("synthetic later cleanup-controller failure")
        var observations = 0
        val native = object : WindowsProfileNativeApi by model {
            override fun close(handle: Long) {
                model.closeCalls += handle
                throw nativeFailure
            }
        }
        val files = WindowsProfileFiles.openForValidation(native) {
            if (++observations == 2) throw controllerFailure
        }
        files.root.child("identity", create = true).lock("vault.lock", nonBlocking = true)
        val failure = assertFailsWith<WindowsProfileFiles.RetirementFailure> { files.close() }
        assertSame(controllerFailure, failure.cause)
        assertSame(nativeFailure, failure.priorFailure)
        assertTrue(failure.suppressed.isEmpty())
        assertTrue(controllerFailure.suppressed.isEmpty())
        assertTrue(nativeFailure.suppressed.isEmpty())
        assertEquals(listOf(3L), model.closeCalls)
        assertEquals(3, files.retainedHandleCount)
        repeat(2) { assertSame(failure, assertFailsWith<WindowsProfileFiles.RetirementFailure> { files.close() }) }
        assertEquals(listOf(3L), model.closeCalls)
    }

    @Test
    fun controllerFailureSignalsAnExistingCloseWaiterWithTheSameRetainedOutcome() {
        val model = WindowsProfileModel()
        val original = OutOfMemoryError("synthetic concurrent cleanup-controller failure")
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val waiterStarted = CountDownLatch(1)
        val firstFailure = AtomicReference<Throwable?>()
        val waitingFailure = AtomicReference<Throwable?>()
        var observations = 0
        val files = WindowsProfileFiles.openForValidation(model) {
            observations++
            entered.countDown()
            assertTrue(release.await(5, TimeUnit.SECONDS))
            throw original
        }
        val first = thread(name = "synthetic-profile-close-owner", isDaemon = true) {
            try { files.close() } catch (caught: Throwable) { firstFailure.set(caught) }
        }
        var waiter: Thread? = null
        try {
            assertTrue(entered.await(5, TimeUnit.SECONDS))
            waiter = thread(name = "synthetic-profile-close-waiter", isDaemon = true) {
                waiterStarted.countDown()
                try { files.close() } catch (caught: Throwable) { waitingFailure.set(caught) }
            }
            assertTrue(waiterStarted.await(5, TimeUnit.SECONDS))
            val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
            while (waiter.state != Thread.State.WAITING && System.nanoTime() < deadline) Thread.yield()
            assertEquals(Thread.State.WAITING, waiter.state)
            assertTrue(model.closeCalls.isEmpty())
        } finally {
            release.countDown()
            first.join(5_000)
            waiter?.join(5_000)
        }
        assertFalse(first.isAlive)
        assertFalse(checkNotNull(waiter).isAlive)
        val failure = firstFailure.get() as WindowsProfileFiles.RetirementFailure
        assertSame(failure, waitingFailure.get())
        assertSame(original, failure.cause)
        assertSame(files, failure.retainedSession)
        assertEquals(1, observations)
        assertEquals(1, files.retainedHandleCount)
        assertTrue(model.closeCalls.isEmpty())
        assertSame(failure, assertFailsWith<WindowsProfileFiles.RetirementFailure> { files.close() })
    }

    @Test
    fun failedAcquisitionTransfersTheSessionWhenItsCleanupControllerFails() {
        val model = WindowsProfileModel()
        val admission = IOException("synthetic root metadata refusal")
        val controller = OutOfMemoryError("synthetic acquisition cleanup-controller failure")
        val native = object : WindowsProfileNativeApi by model {
            override fun directoryIdentity(handle: Long): LongArray = throw admission
        }
        val failure = assertFailsWith<WindowsProfileFiles.AcquisitionFailure> {
            WindowsProfileFiles.openForValidation(native) { throw controller }
        }
        assertSame(admission, failure.cause)
        val cleanup = failure.cleanupFailure as WindowsProfileFiles.RetirementFailure
        assertSame(controller, cleanup.cause)
        assertSame(failure.retainedSession, cleanup.retainedSession)
        assertEquals(1, failure.retainedSession.retainedHandleCount)
        assertTrue(model.closeCalls.isEmpty())
        repeat(2) {
            assertSame(cleanup, assertFailsWith<WindowsProfileFiles.RetirementFailure> {
                failure.retainedSession.close()
            })
        }
        assertTrue(model.closeCalls.isEmpty())
    }
}
