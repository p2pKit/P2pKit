package dev.p2pkit.sample.rpc.profile

import java.io.IOException
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFails
import kotlin.test.assertFailsWith
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Inert ownership controls; no DLL, NTFS protection, production admission or Windows execution. */
class WindowsProfileAcquisitionFailureTest {
    @Test fun rejectedRootRetainsSealedOwnerForBothPhysicalCloseOutcomes() {
        for (releasedBeforeFailure in listOf(false, true)) {
            val model = WindowsProfileModel()
            val admission = IOException("synthetic rejected root")
            val cleanup = IOException("synthetic uncertain retirement")
            var closeAttempts = 0
            val native = object : WindowsProfileNativeApi by model {
                override fun directoryIdentity(handle: Long): LongArray = throw admission
                override fun close(handle: Long) {
                    closeAttempts++
                    if (releasedBeforeFailure) model.close(handle)
                    throw cleanup
                }
            }
            val failure = assertFailsWith<WindowsProfileFiles.AcquisitionFailure> {
                WindowsProfileFiles.openForValidation(native)
            }
            assertSame(admission, failure.cause)
            assertSame(cleanup, failure.cleanupFailure)
            assertSame(cleanup, failure.suppressed.single())
            val retained = failure.retainedSession
            assertTrue(retained.retirementStarted)
            // Managed ownership cannot be inferred from the model's actual close outcome.
            assertEquals(1, retained.retainedHandleCount)
            assertEquals(if (releasedBeforeFailure) 0 else 1, model.remaining)
            assertFails { retained.root }
            repeat(2) { assertSame(cleanup, assertFailsWith<IOException> { retained.close() }) }
            assertEquals(1, closeAttempts)
            assertTrue(admission.suppressed.isEmpty())
        }
    }

    @Test fun identicalAdmissionAndCleanupFailureStillRetainsOwnerWithoutSelfSuppression() {
        val model = WindowsProfileModel()
        val shared = IOException("synthetic shared failure")
        var closeAttempts = 0
        val native = object : WindowsProfileNativeApi by model {
            override fun directoryIdentity(handle: Long): LongArray = throw shared
            override fun close(handle: Long) { closeAttempts++; throw shared }
        }
        val failure = assertFailsWith<WindowsProfileFiles.AcquisitionFailure> {
            WindowsProfileFiles.openForValidation(native)
        }
        assertSame(shared, failure.cause)
        assertSame(shared, failure.cleanupFailure)
        assertTrue(failure.suppressed.isEmpty())
        assertTrue(shared.suppressed.isEmpty())
        assertEquals(1, failure.retainedSession.retainedHandleCount)
        assertSame(shared, assertFailsWith<IOException> { failure.retainedSession.close() })
        assertEquals(1, closeAttempts)
    }

    @Test fun successfulRetirementPreservesOriginalAdmissionFailureWithoutFalseRetainedOwnership() {
        val model = WindowsProfileModel()
        val admission = IOException("synthetic rejected root")
        val native = object : WindowsProfileNativeApi by model {
            override fun directoryIdentity(handle: Long): LongArray = throw admission
        }
        assertSame(admission, assertFailsWith<IOException> { WindowsProfileFiles.openForValidation(native) })
        assertEquals(listOf(1L), model.closeCalls)
        assertEquals(0, model.remaining)
        assertTrue(admission.suppressed.isEmpty())
    }

    @Test fun failedRootAllocationDoesNotInventHandleOwnershipOrCallNativeClose() {
        val model = WindowsProfileModel()
        val admission = IOException("synthetic no root allocated")
        val native = object : WindowsProfileNativeApi by model {
            override fun openRoot(): Long = throw admission
        }
        assertSame(admission, assertFailsWith<IOException> { WindowsProfileFiles.openForValidation(native) })
        assertTrue(model.closeCalls.isEmpty())
        assertEquals(0, model.remaining)
    }
}
