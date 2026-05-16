package dev.p2pkit.core

import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow

/**
 * A single active connection to another peer.
 *
 * Created by [P2pKit.connect] for outgoing connections and emitted by
 * [P2pKit.incomingSessions] for inbound ones. Sessions are 1:1 — a device with
 * multiple peers has multiple sessions, tracked in [P2pKit.sessions].
 *
 * ### Send semantics
 *
 * [send] is safe to call from multiple coroutines concurrently. Writes are
 * serialized internally with a `Mutex`; frames will never interleave on the
 * underlying connection.
 *
 * ### Receive semantics
 *
 * [incoming] is a hot [SharedFlow] with `replay = 0`,
 * `extraBufferCapacity = 64`, `onBufferOverflow = SUSPEND`. **Subscribe
 * immediately after `connect()` or when accepting an incoming session** —
 * messages emitted before any subscriber attaches are not buffered.
 *
 * ### Lifecycle
 *
 * `close()` walks `Connected → Closing → Closed`. After [close], the underlying
 * connection is released and [incoming] completes.
 */
public interface P2pSession {
    /** Stable identifier of this session for the lifetime of the process. */
    public val id: String

    public val peer: Peer

    public val state: StateFlow<ConnectionState>

    public val incoming: SharedFlow<P2pMessage>

    /**
     * Send a single message to the peer.
     *
     * Throws [P2pError.PayloadTooLarge] for [P2pMessage.Binary] exceeding the
     * configured maximum (default 4 MiB in v0.1). Throws
     * [P2pError.ConnectionFailed] if the connection has dropped.
     */
    public suspend fun send(message: P2pMessage)

    public suspend fun close()
}
