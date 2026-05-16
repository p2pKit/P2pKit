package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pMessage

/**
 * Events emitted by the protocol layer as frames arrive from a peer.
 *
 * A higher layer (the session manager) consumes these and routes:
 *   - [Message] → application's [dev.p2pkit.core.P2pSession.incoming] flow
 *   - [Ping] → respond with a [Pong]
 *   - [Pong] → update the keep-alive deadline
 *   - [Close], [PeerError] → terminate the session
 *   - [Hello] → only meaningful during the initial handshake; ignored after
 *   - [Ack] → reserved for v0.2 reliability work
 */
internal sealed class ProtocolEvent {
    data class Message(val message: P2pMessage) : ProtocolEvent()
    data class Hello(val payload: HelloPayload) : ProtocolEvent()
    data object Ping : ProtocolEvent()
    data object Pong : ProtocolEvent()
    data class Ack(val messageId: MessageId, val chunkIndex: Int) : ProtocolEvent()
    data class PeerError(val reason: String) : ProtocolEvent()
    data object Close : ProtocolEvent()
}
