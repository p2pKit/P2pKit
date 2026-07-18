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
        require(payloadLen <= ProtocolConstants.MAX_FRAME_PAYLOAD_BYTES) {
            "${frame.type} payload length $payloadLen exceeds universal maximum " +
                "${ProtocolConstants.MAX_FRAME_PAYLOAD_BYTES}"
        }
        val violation = FrameValidation.violation(
            type = frame.type,
            flags = frame.flags,
            reserved = 0,
            chunkIndex = frame.chunkIndex,
            totalChunks = frame.totalChunks,
            payloadLength = payloadLen
        )
        require(violation == null) { violation ?: "invalid frame" }
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
     * Throws [P2pError.ProtocolError] for structural problems (bad magic,
     * truncation, invalid flags/indices, or invalid declared size) and
     * [UnknownPacketTypeException] for an otherwise complete bounded frame
     * whose type is not defined by this protocol major.
     */
    fun decode(
        bytes: ByteArray,
        expectedVersion: Byte = ProtocolConstants.LEGACY_VERSION
    ): Frame = decode(
        bytes = bytes,
        offset = 0,
        length = bytes.size,
        expectedVersion = expectedVersion
    )

    /** Decode one exact frame from a window without copying the enclosing stream buffer. */
    internal fun decode(
        bytes: ByteArray,
        offset: Int,
        length: Int,
        expectedVersion: Byte
    ): Frame {
        if (offset < 0 || length < 0 || offset > bytes.size - length) {
            throw P2pError.ProtocolError(
                "Invalid frame window: offset=$offset length=$length bytes=${bytes.size}"
            )
        }
        if (length < ProtocolConstants.HEADER_SIZE) {
            throw P2pError.ProtocolError(
                "Frame too short: $length bytes (need at least ${ProtocolConstants.HEADER_SIZE})"
            )
        }
        if (bytes[offset] != ProtocolConstants.MAGIC_0 ||
            bytes[offset + 1] != ProtocolConstants.MAGIC_1 ||
            bytes[offset + 2] != ProtocolConstants.MAGIC_2 ||
            bytes[offset + 3] != ProtocolConstants.MAGIC_3
        ) {
            throw P2pError.ProtocolError("Bad magic bytes")
        }

        val version = bytes[offset + 4]
        if (version != expectedVersion) {
            throw P2pError.VersionMismatch(
                localVersion = expectedVersion.toUByte().toInt(),
                remoteVersion = version.toUByte().toInt()
            )
        }
        val typeCode = bytes[offset + 5]
        val type = PacketType.fromCode(typeCode)
        val flags = bytes[offset + 6]
        val reserved = bytes[offset + 7]
        val chunkIndex = readIntBE(bytes, offset + 24)
        val totalChunks = readIntBE(bytes, offset + 28)
        val payloadLen = readIntBE(bytes, offset + 32)

        if (payloadLen < 0) {
            throw P2pError.ProtocolError("Negative payload length: $payloadLen")
        }
        if (payloadLen > ProtocolConstants.MAX_FRAME_PAYLOAD_BYTES) {
            throw P2pError.ProtocolError(
                "Payload length $payloadLen exceeds maximum ${ProtocolConstants.MAX_FRAME_PAYLOAD_BYTES}"
            )
        }
        val typeMaximum = FrameValidation.maxPayloadBytes(type)
        if (payloadLen > typeMaximum) {
            val packet = type?.name ?: "unknown packet 0x${typeCode.toUByte().toString(16)}"
            throw P2pError.ProtocolError(
                "$packet payload length $payloadLen exceeds maximum $typeMaximum"
            )
        }
        if (type != null) {
            val violation = FrameValidation.violation(
                type = type,
                flags = flags,
                reserved = reserved,
                chunkIndex = chunkIndex,
                totalChunks = totalChunks,
                payloadLength = payloadLen
            )
            if (violation != null) throw P2pError.ProtocolError(violation)
        }

        val frameLength = ProtocolConstants.HEADER_SIZE + payloadLen
        if (length < frameLength) {
            throw P2pError.ProtocolError(
                "Truncated frame: header says payload=$payloadLen but only " +
                    "${length - ProtocolConstants.HEADER_SIZE} bytes follow"
            )
        }
        if (length != frameLength) {
            throw P2pError.ProtocolError(
                "Frame window has ${length - frameLength} trailing bytes"
            )
        }
        if (type == null) throw UnknownPacketTypeException(typeCode)

        val messageId = MessageId(bytes.copyOfRange(offset + 8, offset + 8 + MessageId.SIZE))
        val payloadStart = offset + ProtocolConstants.HEADER_SIZE
        val payload = bytes.copyOfRange(payloadStart, payloadStart + payloadLen)
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
