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

    override fun events(connection: RawConnection): Flow<ProtocolEvent> = flow {
        val reader = FrameReader(logger)
        val reassembler = Reassembler(clock = clock)
        connection.read().collect { bytes ->
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
                val payload = HelloPayload.decode(frame.payload)
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
        }
    }

    private fun controlFrame(type: PacketType, payload: ByteArray = EMPTY): Frame = Frame(
        type = type,
        flags = FrameFlags.LAST_CHUNK.toByte(),
        messageId = MessageId.random(random),
        chunkIndex = 0,
        totalChunks = 1,
        payload = payload
    )

    private companion object {
        val EMPTY = ByteArray(0)
    }
}
