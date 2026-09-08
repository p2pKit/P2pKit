package dev.p2pkit.core

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotSame
import kotlin.test.assertNull
import kotlin.test.assertSame

/** Diagnostic causes must not change the published data-class value shape. */
class ErrorCauseContractTest {
    @Test
    fun localIdentityCauseIsDiagnosticOnly() {
        val error = P2pError.LocalIdentityUnavailable(
            LocalIdentityFailureKind.TEMPORARILY_UNAVAILABLE,
            LocalIdentityRecovery.RETRY,
            "synthetic identity failure"
        )
        assertNull(error.cause)
        val cause = IllegalStateException("synthetic cause")
        error.underlying = cause

        assertDiagnosticCause(error, cause, error.copy())
    }

    @Test
    fun connectionCauseIsDiagnosticOnly() {
        val error = P2pError.ConnectionFailed("synthetic connection failure")
        assertNull(error.cause)
        val cause = IllegalStateException("synthetic cause")
        error.underlying = cause

        assertDiagnosticCause(error, cause, error.copy())
    }

    @Test
    fun fileTransferCauseIsDiagnosticOnly() {
        val error = P2pError.FileTransferFailed(
            FileTransferFailureKind.STORAGE,
            FileTransferPhase.FLUSH,
            Retryability.RETRY_AFTER_USER_ACTION,
            "synthetic-transfer",
            "synthetic transfer failure"
        )
        assertNull(error.cause)
        val cause = IllegalStateException("synthetic cause")
        error.underlying = cause

        assertDiagnosticCause(error, cause, error.copy())
    }

    @Test
    fun authenticationCauseIsDiagnosticOnly() {
        val error = P2pError.AuthenticationFailed("synthetic authentication failure")
        assertNull(error.cause)
        val cause = IllegalStateException("synthetic cause")
        error.underlying = cause

        assertDiagnosticCause(error, cause, error.copy())
    }

    private fun assertDiagnosticCause(error: P2pError, cause: Throwable, copy: P2pError) {
        assertSame(cause, error.cause)
        assertNotSame(error, copy)
        assertEquals(error, copy)
        assertEquals(error.hashCode(), copy.hashCode())
        assertNull(copy.cause, "copy deliberately excludes the diagnostic cause")
    }
}
