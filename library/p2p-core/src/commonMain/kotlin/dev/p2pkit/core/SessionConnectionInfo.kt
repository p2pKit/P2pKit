package dev.p2pkit.core

/** Sanitized failure categories; no remote reason strings or application payloads. */
public enum class SessionFailureKind {
    Transport,
    Authentication,
    Authorization,
    Protocol,
    Capacity,
    ReconnectExhausted,
}

public data class SessionFailure(public val kind: SessionFailureKind, public val retryable: Boolean)

/**
 * Retained connection observation. SDK sessions start at generation 1 and increment ONLY after a new
 * authenticated/protocol connection is installed. Reconnect does not imply application replay.
 * Generation 0 denotes a third-party session without this optional observation capability.
 */
public data class SessionConnectionInfo(
    public val generation: Long,
    public val lastFailure: SessionFailure? = null,
)
