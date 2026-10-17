package dev.p2pkit.sample.rpc.profile

import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Managed/inert ownership interleavings, not native Windows, JNI loading or profile qualification. */
class WindowsProfileErrorCloseInterleavingTest {
    @Test
    fun lateUnpublishedErrorSurvivesInterruptedOwnerAndWaiterWithoutPrematureRetirement() {
        for (physicallyReleased in listOf(false, true)) {
            val model = WindowsProfileModel()
            val original = OutOfMemoryError("synthetic pending JNI reporting error")
            val entered = CountDownLatch(1)
            val release = CountDownLatch(1)
            val native = object : WindowsProfileNativeApi by model {
                override fun child(directory: Long, name: String, create: Boolean): Long {
                    val unpublished = model.child(directory, name, create)
                    entered.countDown()
                    await(release)
                    if (physicallyReleased) model.close(unpublished)
                    throw original
                }
            }
            val files = WindowsProfileFiles.openForValidation(native)
            val root = files.root
            val child = Outcome { root.child("identity", true) }
            var owner: Outcome? = null
            var waiter: Outcome? = null
            try {
                await(entered)
                owner = Outcome(interrupted = true) { files.close() }
                awaitRetiring(files)
                waiter = Outcome(interrupted = true) { files.close() }
                awaitWaiting(waiter.worker)
                assertTrue(owner.worker.isAlive)
                assertTrue(model.closeCalls.isEmpty())
                assertEquals(1, files.retainedHandleCount)
                assertFails { root.exists("profile.header") }
                assertFails { files.root }
            } finally {
                release.countDown()
                try { child.join() } finally {
                    try { owner?.join() } finally { waiter?.join() }
                }
            }
            assertSame(original, child.failure.get())
            assertSame(original, checkNotNull(owner).failure.get())
            assertSame(original, checkNotNull(waiter).failure.get())
            assertTrue(owner.interruptRestored.get())
            assertTrue(waiter.interruptRestored.get())
            assertFalse(child.interruptRestored.get())
            assertEquals(if (physicallyReleased) listOf(2L, 1L) else listOf(1L), model.closeCalls)
            assertEquals(0, files.retainedHandleCount)
            assertEquals(if (physicallyReleased) 0 else 1, model.remaining)
            val completedCalls = model.closeCalls.toList()
            repeat(2) { assertSame(original, assertFails { files.close() }) }
            assertEquals(completedCalls, model.closeCalls)
            assertTrue(original.suppressed.isEmpty())
            assertFails { files.root }
        }
    }

    @Test
    fun activeLeaseCloseErrorStaysOwnedWhileInterruptedSessionCloseDrainsIndependentHandles() {
        for (physicallyReleased in listOf(false, true)) {
            val model = WindowsProfileModel()
            val original = NoClassDefFoundError("synthetic pending JNI close-reporting error")
            val entered = CountDownLatch(1)
            val release = CountDownLatch(1)
            val closeAttempts = mutableListOf<Long>()
            var leaseHandle = 0L
            val native = object : WindowsProfileNativeApi by model {
                override fun lock(directory: Long, name: String, nonBlocking: Boolean): Long =
                    model.lock(directory, name, nonBlocking).also { leaseHandle = it }
                override fun close(handle: Long) {
                    closeAttempts += handle
                    if (handle == leaseHandle) {
                        entered.countDown()
                        await(release)
                        if (physicallyReleased) model.close(handle)
                        throw original
                    }
                    model.close(handle)
                }
            }
            val files = WindowsProfileFiles.openForValidation(native)
            val root = files.root
            val lease = root.lock("profile.lock", nonBlocking = true)
            val leaseOwner = Outcome { lease.close() }
            var owner: Outcome? = null
            var waiter: Outcome? = null
            try {
                await(entered)
                owner = Outcome(interrupted = true) { files.close() }
                awaitRetiring(files)
                waiter = Outcome(interrupted = true) { files.close() }
                awaitWaiting(waiter.worker)
                assertTrue(owner.worker.isAlive)
                assertEquals(listOf(leaseHandle), closeAttempts)
                assertTrue(model.closeCalls.isEmpty())
                assertEquals(2, files.retainedHandleCount)
                assertFails { root.verifyIdentity() }
            } finally {
                release.countDown()
                try { leaseOwner.join() } finally {
                    try { owner?.join() } finally { waiter?.join() }
                }
            }
            assertSame(original, leaseOwner.failure.get())
            val closeFailure = checkNotNull(owner).failure.get()
            assertTrue(closeFailure is InterruptedException)
            assertSame(closeFailure, checkNotNull(waiter).failure.get())
            assertTrue(owner.interruptRestored.get())
            assertTrue(waiter.interruptRestored.get())
            assertFalse(leaseOwner.interruptRestored.get())
            assertEquals(listOf(leaseHandle, 1L), closeAttempts)
            assertEquals(if (physicallyReleased) listOf(leaseHandle, 1L) else listOf(1L), model.closeCalls)
            assertEquals(1, files.retainedHandleCount)
            assertEquals(if (physicallyReleased) 0 else 1, model.remaining)
            repeat(2) {
                assertSame(closeFailure, assertFails { files.close() })
                // The session's earlier cancellation is not proof that this exact failed lease was retired.
                assertSame(original, assertFails { lease.close() })
            }
            assertEquals(listOf(leaseHandle, 1L), closeAttempts)
            assertTrue(original.suppressed.isEmpty())
            assertTrue(closeFailure.suppressed.isEmpty())
            assertFails { files.root }
        }
    }

    private class Outcome(interrupted: Boolean = false, operation: () -> Unit) {
        val failure = AtomicReference<Throwable?>()
        val interruptRestored = AtomicBoolean()
        val worker = thread {
            if (interrupted) Thread.currentThread().interrupt()
            try { operation() } catch (caught: Throwable) { failure.set(caught) }
            finally { interruptRestored.set(Thread.currentThread().isInterrupted) }
        }
        fun join() { worker.join(5_000); assertFalse(worker.isAlive) }
    }

    private fun await(latch: CountDownLatch) = assertTrue(latch.await(5, TimeUnit.SECONDS))

    private fun awaitRetiring(files: WindowsProfileFiles) {
        val end = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
        while (!files.retirementStarted && System.nanoTime() < end) Thread.yield()
        assertTrue(files.retirementStarted)
    }

    private fun awaitWaiting(worker: Thread) {
        val end = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
        // Thread.getState is a snapshot: an observed waiter may transiently run
        // again before a second read. Assert the same observation we awaited.
        var observed = worker.state
        while (observed != Thread.State.WAITING && worker.isAlive && System.nanoTime() < end) {
            Thread.yield()
            observed = worker.state
        }
        assertEquals(Thread.State.WAITING, observed)
    }
}
