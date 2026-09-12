package dev.p2pkit.sample.diagnostics

/**
 * Records Connected in a sample configured for authenticated v2, not optional HELLO features.
 * The public session does not expose the negotiated feature intersection. In particular,
 * Connected alone cannot establish file-commit-sha256-v1 support, including after reconnect.
 */
public fun secureV2ConnectionRecord(
    peerId: String,
    connectionId: String?,
    sdkSessionId: String? = null
): DiagnosticRecord = DiagnosticRecord(
    peerId = peerId,
    connectionId = connectionId,
    sdkSessionId = sdkSessionId,
    category = "protocol",
    eventName = DiagnosticEventNames.PROTOCOL_NEGOTIATED,
    currentState = "secure-v2"
)
