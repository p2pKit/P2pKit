package dev.p2pkit.sample.rpc.profile

import dev.p2pkit.sample.rpc.desktop.DesktopRpcProfile
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

/** Managed failure/ownership controls only. No DLL, Windows storage, loader or production admission. */
class WindowsProfileNativeUncertaintyTest {
    @Test
    fun unpublishedRootReportingErrorsRetainTheExactFailureAndUnpublishedNativeOwner() {
        for (physicallyReleased in listOf(false, true)) {
            for (original in reportingErrors()) {
                val model = WindowsProfileModel()
                var closeAttempts = 0
                val native = object : WindowsProfileNativeApi by model {
                    override fun openRoot(): Long {
                        val unpublished = model.openRoot()
                        if (physicallyReleased) model.close(unpublished)
                        // JNI fail(result=CleanupUnknown) may preserve an existing reporting Error instead.
                        throw original
                    }
                    override fun close(handle: Long) { closeAttempts++; model.close(handle) }
                }
                val failure = assertFailsWith<WindowsProfileFiles.AcquisitionFailure> {
                    WindowsProfileFiles.openForValidation(native)
                }
                assertSame(original, failure.cause)
                assertSame(original, failure.cleanupFailure)
                assertTrue(failure.suppressed.isEmpty())
                assertTrue(original.suppressed.isEmpty())
                assertEquals(0, failure.retainedSession.retainedHandleCount)
                assertTrue(failure.retainedSession.retirementStarted)
                repeat(2) { assertSame(original, assertFails { failure.retainedSession.close() }) }
                assertFails { failure.retainedSession.root }
                assertEquals(1, model.opens)
                assertEquals(0, closeAttempts)
                assertEquals(if (physicallyReleased) 0 else 1, model.remaining)
            }
        }
    }

    @Test
    fun rootMetadataReportingErrorRemainsUncertainAfterPublishedRootRetirement() {
        for (original in reportingErrors()) {
            val model = WindowsProfileModel()
            val native = object : WindowsProfileNativeApi by model {
                override fun directoryIdentity(handle: Long): LongArray = throw original
            }
            val failure = assertFailsWith<WindowsProfileFiles.AcquisitionFailure> {
                WindowsProfileFiles.openForValidation(native)
            }
            assertSame(original, failure.cause)
            assertSame(original, failure.cleanupFailure)
            assertEquals(listOf(1L), model.closeCalls)
            assertEquals(0, failure.retainedSession.retainedHandleCount)
            repeat(2) { assertSame(original, assertFails { failure.retainedSession.close() }) }
            assertEquals(listOf(1L), model.closeCalls)
        }
    }

    @Test
    fun unpublishedChildReportingErrorsSealAdmissionAndSurvivePublishedHandleDrain() {
        for (original in reportingErrors()) {
            val model = WindowsProfileModel()
            val native = object : WindowsProfileNativeApi by model {
                override fun child(directory: Long, name: String, create: Boolean): Long {
                    model.child(directory, name, create)
                    throw original
                }
            }
            val files = WindowsProfileFiles.openForValidation(native)
            val root = files.root
            assertSame(original, assertFails { root.child("identity", true) })
            assertFails { root.exists("profile.header") }
            repeat(2) { assertSame(original, assertFails { files.close() }) }
            assertEquals(listOf(1L), model.closeCalls)
            assertEquals(0, files.retainedHandleCount)
            assertEquals(1, model.remaining)
            assertFails { files.root }
            assertTrue(original.suppressed.isEmpty())
        }
    }

    @Test
    fun introspectionErrorsBeforeStorageEntryNeverInventNativeOwnership() {
        for (failAbi in listOf(false, true)) {
            for (original in reportingErrors()) {
                val model = WindowsProfileModel()
                val native = object : WindowsProfileNativeApi by model {
                    override fun abi(): Int = if (failAbi) throw original else 1
                    override fun capabilities(): Long = throw original
                }
                assertSame(original, assertFails { WindowsProfileFiles.openForValidation(native) })
                assertEquals(0, model.opens)
                assertEquals(0, model.remaining)
                assertTrue(model.closeCalls.isEmpty())
                assertTrue(original.suppressed.isEmpty())
            }
        }
    }

    @Test
    fun transferredProfileAttemptRetainsOwnerWhenTheNativeLeaseErrorCouldNotBeReported() {
        val model = WindowsProfileModel()
        val original = OutOfMemoryError("synthetic JNI reporting failure")
        val native = object : WindowsProfileNativeApi by model {
            override fun lock(directory: Long, name: String, nonBlocking: Boolean): Long {
                model.lock(directory, name, nonBlocking)
                throw original
            }
        }
        val files = WindowsProfileFiles.openForValidation(native)
        val password = "synthetic-reporting-failure".toCharArray()
        val attempt = DesktopRpcProfile.openAttempt(files, password)
        assertSame(original, attempt.result.exceptionOrNull())
        assertSame(original, attempt.cleanupFailure)
        assertSame(files, attempt.retainedSession)
        assertTrue(password.all { it == '\u0000' })
        assertEquals(listOf(1L), model.closeCalls)
        assertEquals(0, files.retainedHandleCount)
        assertEquals(1, model.remaining)
        repeat(2) { assertSame(original, assertFails { files.close() }) }
        assertEquals(listOf(1L), model.closeCalls)
    }

    @Test
    fun acquisitionRetainsDistinctAdmissionAndCleanupErrorWithoutSuppressionAllocation() {
        val model = WindowsProfileModel()
        val admission = IOException("synthetic metadata rejection")
        val cleanup = OutOfMemoryError("synthetic close reporting failure")
        var closeAttempts = 0
        val native = object : WindowsProfileNativeApi by model {
            override fun directoryIdentity(handle: Long): LongArray = throw admission
            override fun close(handle: Long) { closeAttempts++; throw cleanup }
        }
        val failure = assertFailsWith<WindowsProfileFiles.AcquisitionFailure> {
            WindowsProfileFiles.openForValidation(native)
        }
        assertSame(admission, failure.cause)
        assertSame(cleanup, failure.cleanupFailure)
        assertTrue(failure.suppressed.isEmpty())
        assertTrue(admission.suppressed.isEmpty())
        assertTrue(cleanup.suppressed.isEmpty())
        assertEquals(1, failure.retainedSession.retainedHandleCount)
        repeat(2) { assertSame(cleanup, assertFails { failure.retainedSession.close() }) }
        assertEquals(1, closeAttempts)
        assertEquals(1, model.remaining)
    }

    @Test
    fun rootReportingErrorRetainsKnownCloseFailureWithoutMutatingTheErrorOrRetrying() {
        val model = WindowsProfileModel()
        val admission = OutOfMemoryError("synthetic metadata reporting failure")
        val cleanup = IOException("synthetic original root close uncertainty")
        var closeAttempts = 0
        val native = object : WindowsProfileNativeApi by model {
            override fun directoryIdentity(handle: Long): LongArray = throw admission
            override fun close(handle: Long) { closeAttempts++; throw cleanup }
        }
        val failure = assertFailsWith<WindowsProfileFiles.AcquisitionFailure> {
            WindowsProfileFiles.openForValidation(native)
        }
        assertSame(admission, failure.cause)
        assertSame(admission, failure.cleanupFailure)
        assertTrue(failure.suppressed.isEmpty())
        assertTrue(admission.suppressed.isEmpty())
        assertTrue(cleanup.suppressed.isEmpty())
        // A distinct failed handle remains retained even when suppression allocation is unsafe.
        assertEquals(1, failure.retainedSession.retainedHandleCount)
        repeat(2) { assertSame(admission, assertFails { failure.retainedSession.close() }) }
        assertEquals(1, closeAttempts)
        assertEquals(1, model.remaining)
        assertFails { failure.retainedSession.root }
    }

    private fun reportingErrors(): List<Error> = listOf(
        OutOfMemoryError("synthetic JNI allocation failure"),
        NoClassDefFoundError("synthetic JNI error-class failure"),
        NoSuchMethodError("synthetic JNI error-constructor failure"),
        ExceptionInInitializerError("synthetic JNI error-class initialization failure"),
        LinkageError("synthetic JNI error reporting failure"),
    )

    @Test
    fun unpublishedRootUncertaintyRetainsTheProviderWithoutInventingAHandleOrRetryingCleanup() {
        for (code in listOf(8, 0, -1, Int.MAX_VALUE)) {
            for (physicallyReleased in listOf(false, true)) {
                val model = WindowsProfileModel()
                val original = WindowsProfileCustodyException(code)
                var managedCloseAttempts = 0
                val native = object : WindowsProfileNativeApi by model {
                    override fun openRoot(): Long {
                        val unpublished = model.openRoot()
                        if (physicallyReleased) model.close(unpublished)
                        throw original
                    }
                    override fun close(handle: Long) { managedCloseAttempts++; model.close(handle) }
                }
                val failure = assertFailsWith<WindowsProfileFiles.AcquisitionFailure> {
                    WindowsProfileFiles.openForValidation(native)
                }
                assertSame(original, failure.cause)
                assertSame(original, failure.cleanupFailure)
                assertTrue(failure.suppressed.isEmpty())
                assertTrue(original.suppressed.isEmpty())
                val retained = failure.retainedSession
                assertTrue(retained.retirementStarted)
                assertEquals(0, retained.retainedHandleCount) // No handle was published through the ABI.
                assertFails { retained.root }
                repeat(2) { assertSame(original, assertFailsWith<WindowsProfileCustodyException> { retained.close() }) }
                assertEquals(0, managedCloseAttempts)
                assertEquals(1, model.opens)
                assertEquals(if (physicallyReleased) 0 else 1, model.remaining)
            }
        }
    }

    @Test
    fun rootMetadataUncertaintyIsNotSettledBySuccessfulRetirementOfThePublishedRoot() {
        val model = WindowsProfileModel()
        val original = WindowsProfileCustodyException(8)
        val native = object : WindowsProfileNativeApi by model {
            override fun directoryIdentity(handle: Long): LongArray = throw original
        }
        val failure = assertFailsWith<WindowsProfileFiles.AcquisitionFailure> {
            WindowsProfileFiles.openForValidation(native)
        }
        assertSame(original, failure.cause)
        assertSame(original, failure.cleanupFailure)
        assertEquals(listOf(1L), model.closeCalls)
        assertEquals(0, model.remaining)
        assertEquals(0, failure.retainedSession.retainedHandleCount)
        repeat(2) {
            assertSame(original, assertFailsWith<WindowsProfileCustodyException> { failure.retainedSession.close() })
        }
        assertEquals(listOf(1L), model.closeCalls)
        assertTrue(original.suppressed.isEmpty())
    }

    @Test
    fun knownRootFailuresDoNotInventUnpublishedCleanupUncertainty() {
        for (code in listOf(1, 2, 3, 4, 5, 6, 7, 9)) {
            val model = WindowsProfileModel()
            val original = WindowsProfileCustodyException(code)
            val native = object : WindowsProfileNativeApi by model {
                override fun openRoot(): Long = throw original
            }
            assertSame(original, assertFailsWith<WindowsProfileCustodyException> {
                WindowsProfileFiles.openForValidation(native)
            })
            assertEquals(0, model.opens)
            assertTrue(model.closeCalls.isEmpty())
            assertTrue(original.suppressed.isEmpty())
        }
    }

    @Test
    fun unpublishedChildUncertaintySurvivesKnownHandleCleanupAndNeverReopensAdmission() {
        for (code in listOf(8, -1)) {
            val model = WindowsProfileModel()
            val original = WindowsProfileCustodyException(code)
            var childAttempts = 0
            val native = object : WindowsProfileNativeApi by model {
                override fun child(directory: Long, name: String, create: Boolean): Long {
                    childAttempts++
                    model.child(directory, name, create) // Native-only ledger entry, never returned to managed code.
                    throw original
                }
            }
            val files = WindowsProfileFiles.openForValidation(native)
            val root = files.root
            assertSame(original, assertFailsWith<WindowsProfileCustodyException> { root.child("identity", true) })
            assertEquals(1, files.retainedHandleCount)
            assertFails { root.exists("profile.header") }
            repeat(2) { assertSame(original, assertFailsWith<WindowsProfileCustodyException> { files.close() }) }
            assertEquals(0, files.retainedHandleCount)
            assertEquals(1, model.remaining) // The managed layer has no authority to close this unpublished entry.
            assertEquals(listOf(1L), model.closeCalls)
            assertEquals(1, childAttempts)
            assertFails { files.root }
            assertTrue(original.suppressed.isEmpty())
        }
    }

    @Test
    fun independentKnownHandleCloseFailuresRemainAttachedToTheOriginalNativeUncertainty() {
        val model = WindowsProfileModel()
        val original = WindowsProfileCustodyException(8)
        val cleanup = IOException("synthetic known-root close uncertainty")
        var closeAttempts = 0
        val native = object : WindowsProfileNativeApi by model {
            override fun child(directory: Long, name: String, create: Boolean): Long = throw original
            override fun close(handle: Long) { closeAttempts++; throw cleanup }
        }
        val files = WindowsProfileFiles.openForValidation(native)
        assertSame(original, assertFailsWith<WindowsProfileCustodyException> { files.root.child("identity", true) })
        repeat(2) { assertSame(original, assertFailsWith<WindowsProfileCustodyException> { files.close() }) }
        assertSame(cleanup, original.suppressed.single())
        assertEquals(1, closeAttempts)
        assertEquals(1, files.retainedHandleCount)
        assertEquals(1, model.remaining)
    }

    @Test
    fun closeWaitingForNativeReturnPreservesUncertaintyReportedByThatLateReturn() {
        val model = WindowsProfileModel()
        val original = WindowsProfileCustodyException(8)
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val childFailure = AtomicReference<Throwable?>()
        val closeFailure = AtomicReference<Throwable?>()
        val native = object : WindowsProfileNativeApi by model {
            override fun child(directory: Long, name: String, create: Boolean): Long {
                entered.countDown()
                assertTrue(release.await(5, TimeUnit.SECONDS))
                throw original
            }
        }
        val files = WindowsProfileFiles.openForValidation(native)
        val root = files.root
        val child = thread {
            try { root.child("identity", true) } catch (failure: Throwable) { childFailure.set(failure) }
        }
        var closer: Thread? = null
        try {
            assertTrue(entered.await(5, TimeUnit.SECONDS))
            closer = thread {
                try { files.close() } catch (failure: Throwable) { closeFailure.set(failure) }
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
        assertFalse(closer.isAlive)
        assertSame(original, childFailure.get())
        assertSame(original, closeFailure.get())
        assertEquals(listOf(1L), model.closeCalls)
        assertEquals(0, files.retainedHandleCount)
        assertSame(original, assertFailsWith<WindowsProfileCustodyException> { files.close() })
        assertEquals(listOf(1L), model.closeCalls)
    }

    @Test
    fun profileOpenAttemptRetainsTheSealedSessionAfterAnUnpublishedLeaseFailure() {
        val model = WindowsProfileModel()
        val original = WindowsProfileCustodyException(8)
        val native = object : WindowsProfileNativeApi by model {
            override fun lock(directory: Long, name: String, nonBlocking: Boolean): Long {
                model.lock(directory, name, nonBlocking)
                throw original
            }
        }
        val files = WindowsProfileFiles.openForValidation(native)
        val password = "synthetic-unpublished-lease".toCharArray()
        val attempt = DesktopRpcProfile.openAttempt(files, password)
        assertSame(original, attempt.result.exceptionOrNull())
        assertSame(original, attempt.cleanupFailure)
        assertSame(files, attempt.retainedSession)
        assertTrue(password.all { it == '\u0000' })
        assertEquals(0, files.retainedHandleCount)
        assertEquals(1, model.remaining)
        assertEquals(listOf(1L), model.closeCalls)
        assertSame(original, assertFailsWith<WindowsProfileCustodyException> { files.close() })
        assertEquals(listOf(1L), model.closeCalls)
        assertFalse(WindowsProfileAvailability.IMPLEMENTED)
        assertFalse(WindowsProfileAvailability.QUALIFIED)
    }
}
