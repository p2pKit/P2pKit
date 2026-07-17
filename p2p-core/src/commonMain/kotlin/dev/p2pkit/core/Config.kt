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
     * Scope: retries fire only on **outgoing** sessions — the ones
     * opened by [dev.p2pkit.core.P2pKit.connect]. Incoming sessions that
     * lose their connection still transition directly to
     * [ConnectionState.Failed]; the remote peer is expected to redial.
     *
     * Each attempt re-resolves the peer's endpoint from the freshest
     * discovery data immediately before dialing, falling back to the
     * [dev.p2pkit.core.transport.InternalPeer] captured at session creation
     * only when the registry has no current entry. For the whole
     * `Reconnecting` window the SDK also nudges discovery transports with
     * periodic `refresh()` calls, so an address rotation (e.g., Wi-Fi
     * reconnect changed the peer's IP) is picked up automatically once the
     * peer is re-observed — no manual re-discovery is needed.
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

/**
 * Whole-kit security profile.
 *
 * A kit never negotiates this value with a peer. In particular, a failed
 * authenticated handshake is terminal and is never retried as plaintext.
 */
public sealed class SecurityMode {
    /**
     * Authenticated protocol v2. Traffic is protected by the fixed
     * `Noise_XX_25519_ChaChaPoly_SHA256` profile and peer identity is bound to
     * possession of a persistent X25519 key.
     */
    public data class AuthenticatedV2(
        val authorization: PeerAuthorizationPolicy = PeerAuthorizationPolicy.RejectUnknown
    ) : SecurityMode()

    /**
     * Deprecated migration profile: protocol v1 with no encryption or peer
     * authentication. Both endpoints must select it explicitly.
     */
    @Deprecated(
        message = "Plaintext protocol v1 is unauthenticated. Use AuthenticatedV2 and configure peer authorization.",
        replaceWith = ReplaceWith("SecurityMode.AuthenticatedV2()")
    )
    public data object NoneForMvp : SecurityMode()
}

/** Authorization applied after the remote proves possession of its X25519 key. */
public sealed interface PeerAuthorizationPolicy {
    /** Reject every identity that is not supplied as a per-connect/manual pin. */
    public data object RejectUnknown : PeerAuthorizationPolicy

    /** Admit only the complete, high-entropy fingerprints in [fingerprints]. */
    public data class PinnedOnly(
        val fingerprints: Set<PeerFingerprint>
    ) : PeerAuthorizationPolicy

    /**
     * Admit any authenticated key whose handshake is bound to the same exact
     * AppId. AppId scopes a product; it is not an authorization secret.
     */
    @ExplicitSecurityRisk
    public data object AcceptAnyAuthenticatedSameApp : PeerAuthorizationPolicy
}

/** Marks APIs that deliberately weaken peer admission and require explicit opt-in. */
@RequiresOptIn(
    message = "This policy authenticates transport keys but does not restrict which same-AppId peer may connect.",
    level = RequiresOptIn.Level.WARNING
)
@Retention(AnnotationRetention.BINARY)
@Target(AnnotationTarget.CLASS, AnnotationTarget.PROPERTY, AnnotationTarget.FUNCTION)
public annotation class ExplicitSecurityRisk
