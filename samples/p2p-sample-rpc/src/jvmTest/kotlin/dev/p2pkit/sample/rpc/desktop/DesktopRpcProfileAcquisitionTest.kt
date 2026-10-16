package dev.p2pkit.sample.rpc.desktop

import dev.p2pkit.sample.rpc.profile.WindowsProfileFiles
import dev.p2pkit.sample.rpc.profile.WindowsProfileModel
import dev.p2pkit.sample.rpc.profile.WindowsProfileNativeApi
import java.io.IOException
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Managed acquisition/ownership controls only; no DLL, native storage or installed-runtime qualification. */
class DesktopRpcProfileAcquisitionTest {
    private fun password() = "synthetic-acquisition-passphrase".toCharArray()

    @Test fun invalidPasswordIsClearedWithoutCallingTheProviderFactory() {
        for (size in listOf(0, 11, 129)) {
            val password = CharArray(size) { 'x' }
            var calls = 0
            val attempt = DesktopRpcProfile.openAttempt(password) {
                calls++
                error("Provider must not be acquired")
            }
            assertIs<IllegalArgumentException>(attempt.result.exceptionOrNull())
            assertNull(attempt.cleanupFailure)
            assertNull(attempt.retainedSession)
            assertEquals(0, calls)
            assertTrue(password.all { it == '\u0000' })
        }
    }

    @Test fun ordinaryAcquisitionFailureClearsPasswordWithoutInventingAnOwnerOrRetry() {
        val password = password()
        val failure = IOException("synthetic provider acquisition failure")
        var calls = 0
        val attempt = DesktopRpcProfile.openAttempt(password) {
            calls++
            throw failure
        }
        assertSame(failure, attempt.result.exceptionOrNull())
        assertSame(failure, attempt.cleanupFailure)
        assertNull(attempt.retainedSession)
        assertEquals(1, calls)
        assertTrue(password.all { it == '\u0000' })
    }

    @Test fun genericUnsupportedFailureIsNotMistakenForTheExactLoaderNoEffectsResult() {
        val password = password()
        val failure = UnsupportedOperationException("WINDOWS_LOADER_DISABLED_TRUSTED_BOOTSTRAP_NOT_IMPLEMENTED")
        var calls = 0
        val attempt = DesktopRpcProfile.openAttempt(password) {
            calls++
            throw failure
        }
        assertSame(failure, attempt.result.exceptionOrNull())
        assertSame(failure, attempt.cleanupFailure)
        assertNull(attempt.retainedSession)
        assertEquals(1, calls)
        assertTrue(password.all { it == '\u0000' })
    }

    @Test fun unpublishedNativeOwnerSurvivesAcquisitionReportingErrorWithoutCloseReplay() {
        val model = WindowsProfileModel()
        val failure = OutOfMemoryError("synthetic native reporting failure")
        val native = object : WindowsProfileNativeApi by model {
            override fun openRoot(): Long {
                model.openRoot()
                throw failure
            }
        }
        val password = password()
        val attempt = DesktopRpcProfile.openAttempt(password) { WindowsProfileFiles.openForValidation(native) }
        val carrier = assertIs<WindowsProfileFiles.AcquisitionFailure>(attempt.result.exceptionOrNull())
        assertSame(failure, carrier.cause)
        assertSame(failure, attempt.cleanupFailure)
        assertSame(carrier.retainedSession, attempt.retainedSession)
        assertEquals(0, carrier.retainedSession.retainedHandleCount)
        assertTrue(carrier.retainedSession.retirementStarted)
        assertEquals(1, model.opens)
        assertEquals(1, model.remaining) // An intentionally uncertain inert owner, not successful native retirement.
        assertTrue(model.closeCalls.isEmpty())
        assertTrue(password.all { it == '\u0000' })
    }

    @Test fun distinctAdmissionAndCleanupFailuresTransferOriginalSealedSessionWithoutRetry() {
        val model = WindowsProfileModel()
        val admission = IOException("synthetic root metadata refusal")
        val cleanup = IOException("synthetic root retirement uncertainty")
        var closeCalls = 0
        val native = object : WindowsProfileNativeApi by model {
            override fun directoryIdentity(handle: Long): LongArray = throw admission
            override fun close(handle: Long) { closeCalls++; throw cleanup }
        }
        val password = password()
        val attempt = DesktopRpcProfile.openAttempt(password) { WindowsProfileFiles.openForValidation(native) }
        val carrier = assertIs<WindowsProfileFiles.AcquisitionFailure>(attempt.result.exceptionOrNull())
        assertSame(admission, carrier.cause)
        assertSame(cleanup, attempt.cleanupFailure)
        assertSame(carrier.retainedSession, attempt.retainedSession)
        assertTrue(carrier.retainedSession.retirementStarted)
        assertEquals(1, carrier.retainedSession.retainedHandleCount)
        assertEquals(1, model.remaining)
        assertEquals(1, closeCalls)
        assertTrue(password.all { it == '\u0000' })
    }

    @Test fun successfulAcquisitionTransfersEncryptedProfileAndRetiresOnlyWhenProfileCloses() {
        val model = WindowsProfileModel()
        val password = password()
        var calls = 0
        val attempt = DesktopRpcProfile.openAttempt(password) {
            calls++
            WindowsProfileFiles.openForValidation(model)
        }
        val profile = attempt.result.getOrThrow()
        assertNull(attempt.cleanupFailure)
        assertNull(attempt.retainedSession)
        assertEquals(1, calls)
        assertTrue(model.remaining > 0)
        assertTrue(password.all { it == '\u0000' })
        val value = byteArrayOf(1, 2, 3)
        val stored = profile.vault.putIfAbsent("synthetic-acquisition-record", value)
        try { assertTrue(stored.contentEquals(value)) } finally { stored.fill(0); value.fill(0) }
        profile.close()
        assertEquals(0, model.remaining)
        assertTrue(model.store.locks.isEmpty())
    }

    @Test fun wrongPasswordAfterAcquisitionClearsPasswordAndRetiresTheTransferredSession() {
        val original = WindowsProfileModel()
        DesktopRpcProfile.openAttempt(password()) { WindowsProfileFiles.openForValidation(original) }
            .result.getOrThrow().close()
        val model = WindowsProfileModel(original.store)
        val password = "wrong-synthetic-acquisition-passphrase".toCharArray()
        val attempt = DesktopRpcProfile.openAttempt(password) { WindowsProfileFiles.openForValidation(model) }
        assertTrue(attempt.result.isFailure)
        assertNull(attempt.cleanupFailure)
        assertNull(attempt.retainedSession)
        assertEquals(0, model.remaining)
        assertTrue(model.store.locks.isEmpty())
        assertTrue(password.all { it == '\u0000' })
    }
}
