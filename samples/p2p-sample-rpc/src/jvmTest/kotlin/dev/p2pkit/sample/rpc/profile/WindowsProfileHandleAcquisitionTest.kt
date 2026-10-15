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

/** Inert allocation/reporting faults, not actual JVM exhaustion, JNI, NTFS or installed-runtime evidence. */
class WindowsProfileHandleAcquisitionTest {
    private class Observation : WindowsProfileFiles.HandleAcquisitionObservation {
        var reservations = 0
        var acquisitions = 0
        var before: () -> Unit = {}
        var retained: () -> Unit = {}
        var after: () -> Unit = {}
        override fun beforeCarrierAllocation() { reservations++; before() }
        override fun afterPrimitiveRetention() { retained() }
        override fun afterAcquisition() { acquisitions++; after() }
    }

    private fun assertProvisional(files: WindowsProfileFiles, raw: Long, failure: Throwable) {
        // Inspect only an inert test owner's ledger; the provisional value must not become close authority.
        val ledger = WindowsProfileFiles::class.java.getDeclaredField("handles").also { it.isAccessible = true }
        val handle = (ledger.get(files) as Array<*>).filterNotNull().single()
        fun field(name: String): Any? = handle.javaClass.getDeclaredField(name)
            .also { it.isAccessible = true }.get(handle)
        assertEquals(raw, field("value"))
        assertEquals(false, field("registered"))
        assertSame(failure, field("failure"))
    }

    @Test
    fun rootPostStoreFailureRetainsUnvalidatedTokenAndNeverRetriesItsClose() {
        val model = WindowsProfileModel()
        val original = OutOfMemoryError("synthetic root post-store controller failure")
        val observation = Observation().also { it.retained = { throw original } }
        val failure = assertFailsWith<WindowsProfileFiles.AcquisitionFailure> {
            WindowsProfileFiles.openForValidation(model, observation)
        }
        assertSame(original, failure.cause)
        assertSame(original, failure.cleanupFailure)
        assertProvisional(failure.retainedSession, 1L, original)
        assertEquals(0, failure.retainedSession.retainedHandleCount)
        assertEquals(1, model.remaining)
        repeat(2) { assertSame(original, assertFails { failure.retainedSession.close() }) }
        assertTrue(model.closeCalls.isEmpty())
        assertEquals(0, observation.acquisitions)
        assertTrue(original.suppressed.isEmpty())
    }

    @Test
    fun childAndLockPostStoreFailuresRetainPrimitiveBeforeReportingWithoutInventingCloseAuthority() {
        for (lock in listOf(false, true)) {
            val model = WindowsProfileModel()
            val original = OutOfMemoryError("synthetic post-store controller failure")
            val observation = Observation()
            val files = WindowsProfileFiles.openForValidation(model, observation)
            observation.retained = { throw original }
            assertSame(original, assertFails {
                if (lock) files.root.lock("profile.lock", nonBlocking = true)
                else files.root.child("identity", create = true)
            })
            repeat(2) { assertSame(original, assertFails { files.close() }) }
            assertProvisional(files, 2L, original)
            assertEquals(listOf(1L), model.closeCalls)
            assertEquals(1, model.remaining)
            assertEquals(0, files.retainedHandleCount)
            assertEquals(1, observation.acquisitions)
            assertTrue(original.suppressed.isEmpty())
        }
    }

    @Test
    fun duplicatePostStoreFailureCannotCloseTheOriginalTokenTwice() {
        val model = WindowsProfileModel()
        val original = OutOfMemoryError("synthetic duplicate post-store controller failure")
        val observation = Observation()
        val native = object : WindowsProfileNativeApi by model {
            override fun child(directory: Long, name: String, create: Boolean): Long = 1L
        }
        val files = WindowsProfileFiles.openForValidation(native, observation)
        observation.retained = { throw original }
        assertSame(original, assertFails { files.root.child("identity", create = true) })
        repeat(2) { assertSame(original, assertFails { files.close() }) }
        assertProvisional(files, 1L, original)
        assertEquals(listOf(1L), model.closeCalls)
        assertEquals(0, model.remaining)
        assertEquals(0, files.retainedHandleCount)
        assertTrue(original.suppressed.isEmpty())
    }

    @Test
    fun rootCarrierAllocationFailurePrecedesAllNativeStorageAndInventsNoOwner() {
        val model = WindowsProfileModel()
        val original = OutOfMemoryError("synthetic carrier allocation failure")
        val observation = Observation().also { it.before = { throw original } }
        assertSame(original, assertFailsWith<OutOfMemoryError> {
            WindowsProfileFiles.openForValidation(model, observation)
        })
        assertEquals(1, observation.reservations)
        assertEquals(0, observation.acquisitions)
        assertEquals(0, model.opens)
        assertEquals(0, model.remaining)
        assertTrue(model.closeCalls.isEmpty())
        assertTrue(original.suppressed.isEmpty())
    }

    @Test
    fun rootPublicationFailureRetainsTheAcquiredPrimitiveTokenBeforeReporting() {
        val model = WindowsProfileModel()
        val original = OutOfMemoryError("synthetic root publication failure")
        val observation = Observation().also { it.after = { throw original } }
        val failure = assertFailsWith<WindowsProfileFiles.AcquisitionFailure> {
            WindowsProfileFiles.openForValidation(model, observation)
        }
        assertSame(original, failure.cause)
        assertSame(original, failure.cleanupFailure)
        assertEquals(listOf(1L), model.closeCalls)
        assertEquals(0, model.remaining)
        assertEquals(0, failure.retainedSession.retainedHandleCount)
        repeat(2) { assertSame(original, assertFails { failure.retainedSession.close() }) }
        assertEquals(listOf(1L), model.closeCalls)
        assertEquals(1, observation.reservations)
        assertEquals(1, observation.acquisitions)
        assertTrue(original.suppressed.isEmpty())
    }

    @Test
    fun failedRootRetirementAfterPublicationErrorStaysOwnedWithoutRetry() {
        val model = WindowsProfileModel()
        val original = OutOfMemoryError("synthetic root publication error")
        val cleanup = IOException("synthetic actual root close uncertainty")
        val observation = Observation().also { it.after = { throw original } }
        val native = object : WindowsProfileNativeApi by model {
            override fun close(handle: Long) { model.closeCalls += handle; throw cleanup }
        }
        val failure = assertFailsWith<WindowsProfileFiles.AcquisitionFailure> {
            WindowsProfileFiles.openForValidation(native, observation)
        }
        assertSame(original, failure.cause)
        assertSame(original, failure.cleanupFailure)
        assertEquals(1, failure.retainedSession.retainedHandleCount)
        assertEquals(1, model.remaining)
        repeat(2) { assertSame(original, assertFails { failure.retainedSession.close() }) }
        assertEquals(listOf(1L), model.closeCalls)
        assertTrue(original.suppressed.isEmpty())
        assertTrue(cleanup.suppressed.isEmpty())
    }

    @Test
    fun childCarrierAllocationFailureNeverEntersNativeChildAcquisition() {
        val model = WindowsProfileModel()
        val original = OutOfMemoryError("synthetic child carrier allocation failure")
        val observation = Observation()
        val files = WindowsProfileFiles.openForValidation(model, observation)
        observation.before = { throw original }
        var childEntries = 0
        model.beforeChild = { childEntries++ }
        assertSame(original, assertFails { files.root.child("identity", create = true) })
        assertEquals(0, childEntries)
        assertEquals(1, files.retainedHandleCount)
        // Metadata verification already entered this admitted storage session, so Error remains uncertain.
        repeat(2) { assertSame(original, assertFails { files.close() }) }
        assertEquals(listOf(1L), model.closeCalls)
        assertEquals(0, model.remaining)
        assertEquals(2, observation.reservations)
        assertEquals(1, observation.acquisitions)
    }

    @Test
    fun invalidPrimitiveReturnsNeverCreateASecondNativeCloseAuthority() {
        for (returned in listOf(0L, -1L, 1L)) {
            val model = WindowsProfileModel()
            val observation = Observation()
            val native = object : WindowsProfileNativeApi by model {
                override fun child(directory: Long, name: String, create: Boolean): Long = returned
            }
            val files = WindowsProfileFiles.openForValidation(native, observation)
            assertFailsWith<IllegalStateException> { files.root.child("identity", create = true) }
            assertEquals(1, files.retainedHandleCount)
            assertEquals(1, observation.acquisitions)
            files.close()
            files.close()
            assertEquals(listOf(1L), model.closeCalls)
            assertEquals(0, model.remaining)
        }
    }

    @Test
    fun acquiredChildStaysOwnedWhileCloseWaitsForItsFailingPublicationReturn() {
        val model = WindowsProfileModel()
        val observation = Observation()
        val original = OutOfMemoryError("synthetic late child publication failure")
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val files = WindowsProfileFiles.openForValidation(model, observation)
        val root = files.root
        observation.after = {
            assertEquals(2, files.retainedHandleCount)
            entered.countDown()
            assertTrue(release.await(5, TimeUnit.SECONDS))
            throw original
        }
        val childFailure = AtomicReference<Throwable?>()
        val closeFailure = AtomicReference<Throwable?>()
        val child = thread(name = "synthetic-handle-publication", isDaemon = true) {
            try { root.child("identity", create = true) } catch (caught: Throwable) { childFailure.set(caught) }
        }
        var closer: Thread? = null
        try {
            assertTrue(entered.await(5, TimeUnit.SECONDS))
            closer = thread(name = "synthetic-handle-retirement", isDaemon = true) {
                try { files.close() } catch (caught: Throwable) { closeFailure.set(caught) }
            }
            val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
            while (!files.retirementStarted && System.nanoTime() < deadline) Thread.yield()
            assertTrue(files.retirementStarted)
            assertTrue(model.closeCalls.isEmpty())
        } finally {
            release.countDown()
            child.join(5_000)
            closer?.join(5_000)
        }
        assertFalse(child.isAlive)
        assertFalse(checkNotNull(closer).isAlive)
        assertSame(original, childFailure.get())
        assertSame(original, closeFailure.get())
        assertEquals(listOf(2L, 1L), model.closeCalls)
        assertEquals(0, model.remaining)
        assertEquals(0, files.retainedHandleCount)
        repeat(2) { assertSame(original, assertFails { files.close() }) }
        assertEquals(listOf(2L, 1L), model.closeCalls)
    }
}
