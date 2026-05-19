package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.flow.Flow

/**
 * Encodes and decodes the wire protocol over a [RawConnection].
 *
 * The protocol carries both *data* (text/binary messages produced by the app)
 * and *control* frames (HELLO, ACK, PING/PONG, CLOSE, ERROR). The session
 * manager owns the connection and routes [ProtocolEvent]s emitted by
 * [events] to the right place.
 *
 * Send methods are not synchronized — the caller is expected to serialize
 * writes per connection (the session uses an internal Mutex for this).
 */
internal interface P2pProtocol {

    suspend fun sendMessage(connection: RawConnection, message: P2pMessage)

    suspend fun sendHello(connection: RawConnection, hello: HelloPayload)

    suspend fun sendPing(connection: RawConnection)

    suspend fun sendPong(connection: RawConnection)

    suspend fun sendClose(connection: RawConnection)

    suspend fun sendError(connection: RawConnection, reason: String)

    // File transfer (v0.2.2). transferId is reused as the frame's messageId
    // so the receiver can demultiplex incoming FILE_DATA frames by transfer.
    suspend fun sendFileOffer(connection: RawConnection, transferId: MessageId, offer: FileOfferPayload)
    suspend fun sendFileAccept(connection: RawConnection, transferId: MessageId)
    suspend fun sendFileReject(connection: RawConnection, transferId: MessageId, reason: String?)
    suspend fun sendFileDataFrame(connection: RawConnection, frame: Frame)
    suspend fun sendFileDone(connection: RawConnection, transferId: MessageId)
    suspend fun sendFileCancel(connection: RawConnection, transferId: MessageId, reason: String?)

    /**
     * Stream of decoded events read from [connection]. Completes when the
     * underlying read flow completes; throws on protocol or transport errors.
     */
    fun events(connection: RawConnection): Flow<ProtocolEvent>
}
