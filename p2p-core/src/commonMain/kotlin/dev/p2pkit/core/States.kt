package dev.p2pkit.core

/**
 * Lifecycle state of the whole P2pKit instance.
 *
 * Transitions follow `Idle → Starting → Running → Stopping → Stopped`.
 * [Failed] is terminal until [P2pKit.stop] is called, which returns to [Idle].
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
