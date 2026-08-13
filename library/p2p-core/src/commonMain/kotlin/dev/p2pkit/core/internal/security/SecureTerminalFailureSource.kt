package dev.p2pkit.core.internal.security

import dev.p2pkit.core.P2pError
import kotlinx.coroutines.flow.StateFlow

/**
 * Internal fail-closed signal for a post-handshake authenticated transport.
 *
 * Secure-record cleanup is deliberately bounded and may outlive the instant
 * at which authentication or structural validation failure is known. The
 * session lifecycle observes this signal directly so raw-close/reconnect
 * classification cannot win while the secure reader is still clearing native
 * and cryptographic resources.
 *
 * Implementations publish only terminal, non-retryable peer/session failures:
 * [P2pError.AuthenticationFailed] or [P2pError.ProtocolError]. Ordinary EOF,
 * I/O failure, and locally recoverable transport loss are not published here.
 */
internal interface SecureTerminalFailureSource {
    val terminalFailure: StateFlow<P2pError?>
}
