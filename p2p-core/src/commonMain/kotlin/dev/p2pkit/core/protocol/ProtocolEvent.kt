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
 *   - [FileOffer], [FileAccept], [FileReject], [FileData], [FileDone],
 *     [FileCancel] → dispatched by file-transfer-id to the session's transfer
 *     manager (v0.2.2). [FileData] hands over the raw [Frame] so the
 *     receiver can route by `messageId` and stream the payload to a sink
 *     without an intermediate copy.
 */
internal sealed class ProtocolEvent {
    data class Message(val message: P2pMessage) : ProtocolEvent()
    data class Hello(val payload: HelloPayload) : ProtocolEvent()
    data object Ping : ProtocolEvent()
    data object Pong : ProtocolEvent()
    data class Ack(val messageId: MessageId, val chunkIndex: Int) : ProtocolEvent()
    data class PeerError(val reason: String) : ProtocolEvent()
    data object Close : ProtocolEvent()

    data class FileOffer(
        val transferId: MessageId,
        val payload: FileOfferPayload,
        val secureOffer: SecureFileOffer? = null
    ) : ProtocolEvent()
    data class FileAccept(val transferId: MessageId) : ProtocolEvent()
    data class FileReject(val transferId: MessageId, val reason: String?) : ProtocolEvent()
    data class FileData(val frame: Frame) : ProtocolEvent()
    data class FileDone(val transferId: MessageId) : ProtocolEvent()
    data class FileFinish(val payload: SecureFileFinish) : ProtocolEvent()
    data class FileCommit(val payload: SecureFileCommit) : ProtocolEvent()
    data class FileResult(val payload: SecureFileResult) : ProtocolEvent()
    data class FileCancel(val transferId: MessageId, val reason: String?) : ProtocolEvent()
}
