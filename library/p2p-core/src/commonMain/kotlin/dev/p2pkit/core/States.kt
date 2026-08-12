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
 * failure surfaced as [P2pError.TransportStartFailed]). A later lifecycle call
 * retries only when rollback completed. An incomplete/timed-out rollback is
 * fail-closed: call [P2pKit.stop] and create a replacement instance.
 *
 * [Stopped] is **terminal**: [P2pKit.stop] cancels the kit's internal scope and
 * the instance cannot be restarted. Later start/connect or per-feature
 * start/stop calls throw `IllegalStateException`; repeated [P2pKit.stop]
 * calls join or return the same terminal teardown result. Create a new
 * instance to start again.
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
 * SDK-created sessions become application-visible only after the transport
 * setup and handshake have succeeded, so their first observable state is
 * [Connected]. A local `close()` commits [Closing] before bounded
 * wire/resource cleanup and then reaches [Closed]; concurrent close callers
 * join that transaction. Connection loss enters [Failed], or [Reconnecting]
 * if [ReconnectPolicy.Enabled] is configured. [Idle], [Connecting], and
 * [Handshaking] remain available to transport-level state machines and future
 * API evolution but are not currently emitted by an SDK-created
 * [P2pSession].
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
