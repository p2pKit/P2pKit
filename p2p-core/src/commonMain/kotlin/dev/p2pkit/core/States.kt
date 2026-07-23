package dev.p2pkit.core

import dev.p2pkit.core.internal.immutableListSnapshot
import dev.p2pkit.core.permission.P2pPermission

/**
 * Lifecycle state of the whole P2pKit instance.
 *
 * Transitions follow `Idle → Starting → Running → Stopping → Stopped`. The kit
 * reaches [Running] on the first successful `start()` (or the implicit start
 * performed by [P2pKit.startAdvertising] / [P2pKit.startDiscovery] /
 * [P2pKit.connect]).
 *
 * [Failed] carries the [P2pError] that aborted startup (e.g. a transport bind
 * failure surfaced as [P2pError.TransportStartFailed]); the next lifecycle call
 * retries and moves back through [Starting].
 *
 * [Stopped] is **terminal**: [P2pKit.stop] cancels the kit's internal scope and
 * the instance cannot be restarted — any later lifecycle call throws
 * `IllegalStateException`. Create a new instance to start again.
 */
public sealed class P2pState {
    public data object Idle : P2pState()
    public data object Starting : P2pState()
    public data object Running : P2pState()
    public data object Stopping : P2pState()
    public data object Stopped : P2pState()
    public data class Failed(val error: P2pError) : P2pState()
}

/**
 * Independent lifecycle of advertising or discovery.
 *
 * [P2pKit.state] remains the lifecycle of the kit and its data transports;
 * feature failures never overwrite that global state. Permission state is the
 * result of the last authoritative start attempt and changes only after a
 * retry because [dev.p2pkit.core.permission.P2pPermissionManager] exposes
 * suspend queries rather than an observation flow.
 */
public sealed class FeatureState {
    public data object Idle : FeatureState()
    public data object Starting : FeatureState()
    public data object Active : FeatureState()
    public data object Stopping : FeatureState()

    /** A start attempt was gated before any feature transport was touched. */
    public class PermissionRequired(missing: List<P2pPermission>) : FeatureState() {
        /** Stable, unmodifiable snapshot of missing runtime permissions. */
        public val missing: List<P2pPermission> = immutableListSnapshot(missing)

        public operator fun component1(): List<P2pPermission> = missing

        public fun copy(
            missing: List<P2pPermission> = this.missing
        ): PermissionRequired = PermissionRequired(missing)

        override fun equals(other: Any?): Boolean =
            this === other || other is PermissionRequired && missing == other.missing

        override fun hashCode(): Int = missing.hashCode()

        override fun toString(): String = "PermissionRequired(missing=$missing)"
    }

    /** No registered transport declares the requested feature capability. */
    public data class Unsupported(val reason: String) : FeatureState()

    /** Feature startup or cleanup failed; the other feature remains independent. */
    public data class Failed(val error: P2pError) : FeatureState()
}

/**
 * Lifecycle state of a single [P2pSession].
 *
 * `Connecting → Handshaking → Connected` is the happy path. `close()` moves
 * the session directly from `Connected` to `Closed` — the `Closing` constant
 * is declared for completeness but is never emitted by the current
 * implementation, so apps should not wait on it. Connection loss enters
 * `Failed`, or `Reconnecting` if [ReconnectPolicy.Enabled] is configured.
 */
public enum class ConnectionState {
    Idle,
    Connecting,
    Handshaking,
    Connected,
    Reconnecting,
    Closing,
    Closed,
    Failed
}
