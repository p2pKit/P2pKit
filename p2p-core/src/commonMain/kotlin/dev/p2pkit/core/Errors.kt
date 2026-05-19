package dev.p2pkit.core

import dev.p2pkit.core.permission.P2pPermission

/**
 * Typed errors thrown by the P2pKit public API.
 *
 * All P2pKit failures are subtypes of [P2pError] so callers can match
 * specific cases with `when`. Library code does not throw raw `RuntimeException`s.
 */
public sealed class P2pError(message: String? = null, cause: Throwable? = null) : Exception(message, cause) {

    /** No registered transport reported it could reach this peer. */
    public data class NoTransportAvailable(val peer: Peer) :
        P2pError("No transport available for peer: ${peer.id.value}")

    /** Generic connection failure (DNS, TCP, etc.). */
    public data class ConnectionFailed(val reason: String) : P2pError(reason)

    /** The peer spoke the protocol incorrectly. Session is closed. */
    public data class ProtocolError(val reason: String) : P2pError(reason)

    /**
     * The app has not been granted one or more required runtime permissions.
     * Apps must request them; the library never does.
     */
    public data class PermissionMissing(val permissions: List<P2pPermission>) :
        P2pError("Missing permissions: $permissions")

    /** [P2pSession.send] rejected an oversized payload. */
    public data class PayloadTooLarge(val maxBytes: Long, val actualBytes: Long) :
        P2pError("Payload too large: $actualBytes > $maxBytes")

    /** Peer rejected the HELLO handshake (typically appId mismatch). */
    public data class HandshakeRejected(val reason: String) : P2pError(reason)

    /** Peer advertised an incompatible protocol major version. */
    public data class VersionMismatch(val localVersion: Int, val remoteVersion: Int) :
        P2pError("Protocol version mismatch: local=$localVersion remote=$remoteVersion")

    /**
     * A registered transport could not be brought up by [P2pKit.start] or by
     * the first [P2pKit.startAdvertising] / [P2pKit.connect] call that
     * triggered lazy startup. Carries the failed transport's kind and the
     * underlying cause so the host app can surface an actionable message.
     *
     * Replaces the v0.2 behaviour where a transport's `init` block could
     * throw (e.g., `IllegalStateException` from `IosLanDataTransport` when
     * Apple's listener didn't reach `.ready` in 5 s) and tear down the
     * kit-construction call site.
     */
    public data class TransportStartFailed(
        val transportKind: TransportKind,
        val reason: String,
        val underlying: Throwable? = null
    ) : P2pError("Transport $transportKind failed to start: $reason", underlying)
}
