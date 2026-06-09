package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError

/**
 * Thrown by [FrameCodec.decode] when a frame's header is structurally valid
 * but its [PacketType] code is unknown.
 *
 * Distinguished from [P2pError.ProtocolError] (which is reserved for
 * unrecoverable structural errors and closes the session) because Spec §17
 * says unknown packet types should be **logged at warn level and skipped**
 * for forward compatibility, not crash the session. [FrameReader] catches
 * this and advances past the frame.
 */
internal class UnknownPacketTypeException(val typeCode: Byte) : RuntimeException(
    "Unknown packet type code: 0x${typeCode.toUByte().toString(16)}"
)

/**
 * Encodes [Frame]s to bytes and decodes single complete frames back.
 *
 * The codec is intentionally stateless and pure. For parsing a continuous
 * byte stream that may carry partial or multiple frames, use [FrameReader].
 */
internal object FrameCodec {

    /**
     * Serialize [frame] to a byte array containing exactly one frame
     * (header + payload).
     */
    fun encode(frame: Frame): ByteArray {
        val payloadLen = frame.payload.size
        val out = ByteArray(ProtocolConstants.HEADER_SIZE + payloadLen)
        out[0] = ProtocolConstants.MAGIC_0
        out[1] = ProtocolConstants.MAGIC_1
        out[2] = ProtocolConstants.MAGIC_2
        out[3] = ProtocolConstants.MAGIC_3
        out[4] = frame.version
        out[5] = frame.type.code
        out[6] = frame.flags
        out[7] = 0 // reserved
        frame.messageId.bytes.copyInto(out, destinationOffset = 8)
        writeIntBE(out, 24, frame.chunkIndex)
        writeIntBE(out, 28, frame.totalChunks)
        writeIntBE(out, 32, payloadLen)
        frame.payload.copyInto(out, destinationOffset = ProtocolConstants.HEADER_SIZE)
        return out
    }

    /**
     * Decode a single complete frame from [bytes]. The input must hold the
     * full header *and* the full payload — see [FrameReader] for streaming.
     *
     * Throws [P2pError.ProtocolError] for any structural problem (bad magic,
     * truncated frame, unknown packet type, invalid chunk indices, negative
     * payload length).
     */
    fun decode(bytes: ByteArray): Frame {
        if (bytes.size < ProtocolConstants.HEADER_SIZE) {
            throw P2pError.ProtocolError(
                "Frame too short: ${bytes.size} bytes (need at least ${ProtocolConstants.HEADER_SIZE})"
            )
        }
        if (bytes[0] != ProtocolConstants.MAGIC_0 ||
            bytes[1] != ProtocolConstants.MAGIC_1 ||
            bytes[2] != ProtocolConstants.MAGIC_2 ||
            bytes[3] != ProtocolConstants.MAGIC_3
        ) {
            throw P2pError.ProtocolError("Bad magic bytes")
        }

        val version = bytes[4]
        val typeCode = bytes[5]
        val flags = bytes[6]
        // bytes[7] reserved

        val messageId = MessageId(bytes.copyOfRange(8, 8 + MessageId.SIZE))
        val chunkIndex = readIntBE(bytes, 24)
        val totalChunks = readIntBE(bytes, 28)
        val payloadLen = readIntBE(bytes, 32)

        if (payloadLen < 0) {
            throw P2pError.ProtocolError("Negative payload length: $payloadLen")
        }
        if (payloadLen > ProtocolConstants.MAX_FRAME_PAYLOAD_BYTES) {
            throw P2pError.ProtocolError(
                "Payload length $payloadLen exceeds maximum ${ProtocolConstants.MAX_FRAME_PAYLOAD_BYTES}"
            )
        }
        if (totalChunks <= 0) {
            throw P2pError.ProtocolError("Invalid totalChunks: $totalChunks")
        }
        if (chunkIndex < 0 || chunkIndex >= totalChunks) {
            throw P2pError.ProtocolError("chunkIndex out of range: $chunkIndex (totalChunks=$totalChunks)")
        }
        val frameEnd = ProtocolConstants.HEADER_SIZE + payloadLen
        if (bytes.size < frameEnd) {
            throw P2pError.ProtocolError(
                "Truncated frame: header says payload=$payloadLen but only " +
                    "${bytes.size - ProtocolConstants.HEADER_SIZE} bytes follow"
            )
        }
        val type = PacketType.fromCode(typeCode)
            ?: throw UnknownPacketTypeException(typeCode)

        val payload = bytes.copyOfRange(ProtocolConstants.HEADER_SIZE, frameEnd)
        return Frame(type, flags, messageId, chunkIndex, totalChunks, payload, version)
    }

    internal fun writeIntBE(out: ByteArray, offset: Int, value: Int) {
        out[offset] = (value ushr 24).toByte()
        out[offset + 1] = (value ushr 16).toByte()
        out[offset + 2] = (value ushr 8).toByte()
        out[offset + 3] = value.toByte()
    }

    internal fun readIntBE(bytes: ByteArray, offset: Int): Int {
        return ((bytes[offset].toInt() and 0xFF) shl 24) or
            ((bytes[offset + 1].toInt() and 0xFF) shl 16) or
            ((bytes[offset + 2].toInt() and 0xFF) shl 8) or
            (bytes[offset + 3].toInt() and 0xFF)
    }
}
