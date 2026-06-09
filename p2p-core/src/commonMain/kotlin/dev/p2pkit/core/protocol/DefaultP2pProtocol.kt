package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlin.random.Random

/**
 * Default [P2pProtocol] implementation that wires together the building
 * blocks from Step 3: [Chunker] for outbound, [FrameReader] +
 * [Reassembler] for inbound, [FrameCodec] for the wire byte format.
 */
internal class DefaultP2pProtocol(
    private val chunker: Chunker = Chunker(),
    private val clock: () -> Long,
    private val random: Random = Random.Default,
    private val logger: P2pLogger = P2pLogger.NoOp
) : P2pProtocol {

    override suspend fun sendMessage(connection: RawConnection, message: P2pMessage) {
        val frames = chunker.chunk(message)
        for (frame in frames) {
            connection.write(FrameCodec.encode(frame))
        }
    }

    override suspend fun sendHello(connection: RawConnection, hello: HelloPayload) {
        val frame = controlFrame(PacketType.HELLO, HelloPayload.encode(hello))
        connection.write(FrameCodec.encode(frame))
    }

    override suspend fun sendPing(connection: RawConnection) {
        connection.write(FrameCodec.encode(controlFrame(PacketType.PING)))
    }

    override suspend fun sendPong(connection: RawConnection) {
        connection.write(FrameCodec.encode(controlFrame(PacketType.PONG)))
    }

    override suspend fun sendClose(connection: RawConnection) {
        connection.write(FrameCodec.encode(controlFrame(PacketType.CLOSE)))
    }

    override suspend fun sendError(connection: RawConnection, reason: String) {
        val payload = reason.encodeToByteArray()
        connection.write(FrameCodec.encode(controlFrame(PacketType.ERROR, payload)))
    }

    override suspend fun sendFileOffer(
        connection: RawConnection,
        transferId: MessageId,
        offer: FileOfferPayload
    ) {
        val frame = controlFrame(
            type = PacketType.FILE_OFFER,
            messageId = transferId,
            payload = FileOfferPayload.encode(offer)
        )
        connection.write(FrameCodec.encode(frame))
    }

    override suspend fun sendFileAccept(connection: RawConnection, transferId: MessageId) {
        connection.write(FrameCodec.encode(controlFrame(PacketType.FILE_ACCEPT, messageId = transferId)))
    }

    override suspend fun sendFileReject(
        connection: RawConnection,
        transferId: MessageId,
        reason: String?
    ) {
        val payload = reason?.encodeToByteArray() ?: EMPTY
        connection.write(
            FrameCodec.encode(controlFrame(PacketType.FILE_REJECT, messageId = transferId, payload = payload))
        )
    }

    override suspend fun sendFileDataFrame(connection: RawConnection, frame: Frame) {
        require(frame.type == PacketType.FILE_DATA) {
            "sendFileDataFrame expects FILE_DATA, got ${frame.type}"
        }
        connection.write(FrameCodec.encode(frame))
    }

    override suspend fun sendFileDone(connection: RawConnection, transferId: MessageId) {
        connection.write(FrameCodec.encode(controlFrame(PacketType.FILE_DONE, messageId = transferId)))
    }

    override suspend fun sendFileCancel(
        connection: RawConnection,
        transferId: MessageId,
        reason: String?
    ) {
        val payload = reason?.encodeToByteArray() ?: EMPTY
        connection.write(
            FrameCodec.encode(controlFrame(PacketType.FILE_CANCEL, messageId = transferId, payload = payload))
        )
    }

    override fun events(connection: RawConnection): Flow<ProtocolEvent> = flow {
        val reader = FrameReader(logger)
        val reassembler = Reassembler(clock = clock)
        connection.read().collect { bytes ->
            // Reclaim partial multi-chunk messages whose final chunk never
            // arrived. evictStale() is otherwise never driven (it has no timer),
            // so without this call a stalled transfer would pin its chunks for
            // the life of the connection. Cheap: no-op while `pending` is empty.
            reassembler.evictStale()
            val frames = reader.feed(bytes)
            for (frame in frames) {
                val event = decodeEvent(frame, reassembler)
                if (event != null) emit(event)
            }
        }
    }

    private fun decodeEvent(frame: Frame, reassembler: Reassembler): ProtocolEvent? {
        return when (frame.type) {
            PacketType.DATA -> {
                val message = reassembler.accept(frame) ?: return null
                ProtocolEvent.Message(message)
            }
            PacketType.HELLO -> {
                // A malformed HELLO body must not throw a SerializationException
                // out of the events flow (which would tear the session down as
                // an unhandled error). Skip + warn, mirroring the unknown-packet
                // policy; during the handshake a missing HELLO simply times out
                // and surfaces as a clean HandshakeRejected.
                val payload = runCatching { HelloPayload.decode(frame.payload) }.getOrElse { e ->
                    logger.warn("Skipping malformed HELLO frame: ${e.message ?: e::class.simpleName}")
                    return null
                }
                ProtocolEvent.Hello(payload)
            }
            PacketType.PING -> ProtocolEvent.Ping
            PacketType.PONG -> ProtocolEvent.Pong
            PacketType.CLOSE -> ProtocolEvent.Close
            PacketType.ERROR -> {
                val reason = frame.payload.decodeToString()
                ProtocolEvent.PeerError(reason)
            }
            PacketType.ACK -> ProtocolEvent.Ack(frame.messageId, frame.chunkIndex)
            PacketType.FILE_OFFER -> {
                // Skip + warn on a malformed offer body instead of letting the
                // SerializationException escape into routeEvents. A hostile peer
                // could otherwise resend a bad FILE_OFFER after every reconnect
                // to drive a reconnect loop.
                val payload = runCatching { FileOfferPayload.decode(frame.payload) }.getOrElse { e ->
                    logger.warn("Skipping malformed FILE_OFFER frame: ${e.message ?: e::class.simpleName}")
                    return null
                }
                ProtocolEvent.FileOffer(frame.messageId, payload)
            }
            PacketType.FILE_ACCEPT -> ProtocolEvent.FileAccept(frame.messageId)
            PacketType.FILE_REJECT -> {
                val reason = if (frame.payload.isEmpty()) null else frame.payload.decodeToString()
                ProtocolEvent.FileReject(frame.messageId, reason)
            }
            PacketType.FILE_DATA -> ProtocolEvent.FileData(frame)
            PacketType.FILE_DONE -> ProtocolEvent.FileDone(frame.messageId)
            PacketType.FILE_CANCEL -> {
                val reason = if (frame.payload.isEmpty()) null else frame.payload.decodeToString()
                ProtocolEvent.FileCancel(frame.messageId, reason)
            }
        }
    }

    private fun controlFrame(
        type: PacketType,
        payload: ByteArray = EMPTY,
        messageId: MessageId = MessageId.random(random)
    ): Frame = Frame(
        type = type,
        flags = FrameFlags.LAST_CHUNK.toByte(),
        messageId = messageId,
        chunkIndex = 0,
        totalChunks = 1,
        payload = payload
    )

    private companion object {
        val EMPTY = ByteArray(0)
    }
}
