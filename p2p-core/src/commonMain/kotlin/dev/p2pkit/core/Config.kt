package dev.p2pkit.core

/**
 * Keep-alive (PING/PONG) timings for each [P2pSession].
 *
 * Each side sends a `PING` every [pingIntervalMillis]. If no `PONG` is observed
 * within [timeoutMillis], the session transitions to [ConnectionState.Failed],
 * or to [ConnectionState.Reconnecting] for outgoing sessions configured with
 * [ReconnectPolicy.Enabled].
 */
public data class KeepAliveConfig(
    val pingIntervalMillis: Long = 10_000,
    val timeoutMillis: Long = 30_000
) {
    init {
        require(pingIntervalMillis > 0) { "pingIntervalMillis must be positive" }
        require(timeoutMillis > pingIntervalMillis) { "timeoutMillis must exceed pingIntervalMillis" }
    }
}

/**
 * Whether and how the SDK retries a session after the underlying connection
 * fails.
 */
public sealed class ReconnectPolicy {
    /** Failed sessions become [ConnectionState.Failed] immediately. Default for v0.1. */
    public data object Disabled : ReconnectPolicy()

    /**
     * Failed sessions enter [ConnectionState.Reconnecting] and retry up to
     * [maxAttempts] times with [retryDelayMillis] between attempts. On
     * success the session returns to [ConnectionState.Connected] with its
     * public identity preserved (same [P2pSession] instance, same `incoming`
     * flow). On exhaustion it transitions to [ConnectionState.Failed].
     *
     * Scope (v0.2): retries fire only on **outgoing** sessions — the ones
     * opened by [dev.p2pkit.core.P2pKit.connect]. Incoming sessions that
     * lose their connection still transition directly to
     * [ConnectionState.Failed]; the remote peer is expected to redial.
     *
     * Retries reuse the [dev.p2pkit.core.transport.InternalPeer] captured at
     * session creation. If the peer's transport address has rotated since
     * (e.g., Wi-Fi reconnect changed its IP), attempts may exhaust until the
     * app re-discovers the peer and calls
     * [dev.p2pkit.core.P2pKit.connect] again.
     *
     * Clean closes — both [P2pSession.close] and a `CLOSE` frame from the
     * peer — never trigger retry.
     */
    public data class Enabled(val maxAttempts: Int, val retryDelayMillis: Long) : ReconnectPolicy() {
        init {
            require(maxAttempts > 0) { "maxAttempts must be positive" }
            require(retryDelayMillis >= 0) { "retryDelayMillis must be non-negative" }
        }
    }
}

/** Behavior applied when the app calls [P2pKit.notifyAppBackgrounded]. */
public sealed class BackgroundPolicy {
    /** Default. Close all active sessions and stop advertising/discovery. */
    public data object CloseActiveSessions : BackgroundPolicy()

    /**
     * Keep sessions alive when the app is backgrounded. The app is responsible
     * for running a foreground service or equivalent so the OS does not kill it.
     */
    public data object KeepRunning : BackgroundPolicy()
}

/** Persistence behavior when the app process is killed. v0.1 has only one policy. */
public sealed class AppKilledPolicy {
    /** No session state is persisted across process death. */
    public data object NoPersistenceForMvp : AppKilledPolicy()
}

/** Security mode for the SDK. v0.1 ships only [NoneForMvp]; see Spec §18 for future. */
public sealed class SecurityMode {
    /** No encryption, no pairing. Connections are plain TCP. */
    public data object NoneForMvp : SecurityMode()
}
