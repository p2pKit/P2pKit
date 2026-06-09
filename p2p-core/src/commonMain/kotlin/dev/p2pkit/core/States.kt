package dev.p2pkit.core

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
 * Lifecycle state of a single [P2pSession].
 *
 * `Connecting → Handshaking → Connected` is the happy path. `close()` walks
 * `Connected → Closing → Closed`. Connection loss enters `Failed`, or
 * `Reconnecting` if [ReconnectPolicy.Enabled] is configured.
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
