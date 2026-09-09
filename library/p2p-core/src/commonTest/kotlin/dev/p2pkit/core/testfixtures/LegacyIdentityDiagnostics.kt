package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.PeerId
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * The identity-rejection callers each submit one controlled inbound connection. Once the initiator
 * has asserted its typed failure, terminal stop may cancel the responder before it diagnoses that
 * rejection. Permit zero or one exact responder diagnostic, never arbitrary setup/session warnings.
 */
internal fun assertLegacyPeerMismatchDiagnostics(recorder: RecordingLogger, initiator: PeerId) {
    val diagnostics = recorder.entries.filter {
        it.level == RecordingLogger.Level.WARN || it.level == RecordingLogger.Level.ERROR
    }
    assertTrue(diagnostics.size <= 1, "only one controlled HELLO mismatch was sent")
    // This responder's first incoming session uses the initiator's actual id and sequence 1.
    // Only the production clock component varies; no expected id/count is obtained from the logs.
    val message = Regex(
        "Session in-${Regex.escape(initiator.value)}-[0-9]+-1: peer error: peerId mismatch"
    )
    diagnostics.forEach { entry ->
        assertEquals(RecordingLogger.Level.WARN, entry.level)
        assertTrue(message.matches(entry.message), "unexpected identity-rejection diagnostic: ${entry.message}")
        assertEquals(null, entry.throwable)
    }
}

internal fun assertLegacySelfCollisionDiagnostics(recorder: RecordingLogger) {
    val diagnostics = recorder.entries.filter {
        it.level == RecordingLogger.Level.WARN || it.level == RecordingLogger.Level.ERROR
    }
    assertTrue(diagnostics.size <= 1, "only one controlled self-collision setup was attempted")
    diagnostics.forEach { entry ->
        assertEquals(RecordingLogger.Level.WARN, entry.level)
        assertEquals("Incoming session setup failed", entry.message)
        val failure = assertIs<P2pError.HandshakeRejected>(entry.throwable)
        assertEquals("Remote HELLO claims our own peerId", failure.reason)
        assertEquals(null, failure.cause)
        assertTrue(failure.suppressedExceptions.isEmpty(), "rejection must not conceal failed cleanup")
    }
}
