package dev.p2pkit.core.protocol

/**
 * Wire-shape rules shared by outbound encoding and inbound header parsing.
 * Keeping these rules header-only lets [FrameReader] reject hostile declared
 * lengths, flags, and indices before it buffers their payload.
 */
internal object FrameValidation {

    private const val DATA_FLAGS: Int =
        FrameFlags.NEEDS_ACK or FrameFlags.LAST_CHUNK or FrameFlags.IS_TEXT

    fun maxPayloadBytes(type: PacketType?): Int = when (type) {
        null -> ProtocolConstants.MAX_UNKNOWN_PACKET_PAYLOAD_BYTES
        PacketType.HELLO -> ProtocolConstants.MAX_HELLO_PAYLOAD_BYTES
        PacketType.DATA, PacketType.FILE_DATA -> ProtocolConstants.MAX_DATA_FRAME_PAYLOAD_BYTES
        PacketType.ERROR, PacketType.FILE_REJECT, PacketType.FILE_CANCEL ->
            ProtocolConstants.MAX_REASON_PAYLOAD_BYTES
        PacketType.FILE_OFFER -> ProtocolConstants.MAX_FILE_OFFER_PAYLOAD_BYTES
        PacketType.ACK, PacketType.PING, PacketType.PONG, PacketType.CLOSE,
        PacketType.FILE_ACCEPT, PacketType.FILE_DONE -> 0
    }

    /** Returns a stable diagnostic when a known packet's header is invalid. */
    fun violation(
        type: PacketType,
        flags: Byte,
        reserved: Byte,
        chunkIndex: Int,
        totalChunks: Int,
        payloadLength: Int
    ): String? {
        if (reserved != 0.toByte()) return "$type reserved header byte must be zero"
        if (payloadLength < 0) return "$type has negative payload length $payloadLength"

        val maxPayload = maxPayloadBytes(type)
        if (payloadLength > maxPayload) {
            return "$type payload length $payloadLength exceeds maximum $maxPayload"
        }

        if (totalChunks <= 0) return "$type has invalid totalChunks $totalChunks"
        if (chunkIndex < 0 || chunkIndex >= totalChunks) {
            return "$type chunkIndex $chunkIndex is outside 0 until $totalChunks"
        }

        val bits = flags.toInt() and 0xFF
        return when (type) {
            PacketType.DATA -> {
                when {
                    bits and DATA_FLAGS != bits -> "$type has unsupported flags 0x${bits.toString(16)}"
                    totalChunks > ProtocolConstants.MAX_TOTAL_CHUNKS ->
                        "$type totalChunks $totalChunks exceeds maximum ${ProtocolConstants.MAX_TOTAL_CHUNKS}"
                    (bits and FrameFlags.LAST_CHUNK != 0) != (chunkIndex == totalChunks - 1) ->
                        "$type LAST_CHUNK must be set exactly on the final chunk"
                    else -> null
                }
            }

            PacketType.FILE_DATA -> {
                when {
                    bits and (FrameFlags.LAST_CHUNK.inv() and 0xFF) != 0 ->
                        "$type has unsupported flags 0x${bits.toString(16)}"
                    payloadLength == 0 -> "$type payload must not be empty"
                    (bits and FrameFlags.LAST_CHUNK != 0) != (chunkIndex == totalChunks - 1) ->
                        "$type LAST_CHUNK must be set exactly on the final chunk"
                    else -> null
                }
            }

            PacketType.ACK -> when {
                bits != FrameFlags.LAST_CHUNK -> "$type flags must be LAST_CHUNK"
                payloadLength != 0 -> "$type payload must be empty"
                totalChunks > ProtocolConstants.MAX_TOTAL_CHUNKS ->
                    "$type totalChunks $totalChunks exceeds maximum ${ProtocolConstants.MAX_TOTAL_CHUNKS}"
                else -> null
            }

            PacketType.HELLO, PacketType.FILE_OFFER -> singletonViolation(
                type = type,
                bits = bits,
                chunkIndex = chunkIndex,
                totalChunks = totalChunks,
                requirePayload = true,
                payloadLength = payloadLength
            )

            PacketType.PING, PacketType.PONG, PacketType.CLOSE,
            PacketType.FILE_ACCEPT, PacketType.FILE_DONE -> singletonViolation(
                type = type,
                bits = bits,
                chunkIndex = chunkIndex,
                totalChunks = totalChunks,
                requireEmptyPayload = true,
                payloadLength = payloadLength
            )

            PacketType.ERROR, PacketType.FILE_REJECT, PacketType.FILE_CANCEL -> singletonViolation(
                type = type,
                bits = bits,
                chunkIndex = chunkIndex,
                totalChunks = totalChunks,
                payloadLength = payloadLength
            )
        }
    }

    private fun singletonViolation(
        type: PacketType,
        bits: Int,
        chunkIndex: Int,
        totalChunks: Int,
        payloadLength: Int,
        requirePayload: Boolean = false,
        requireEmptyPayload: Boolean = false
    ): String? = when {
        bits != FrameFlags.LAST_CHUNK -> "$type flags must be LAST_CHUNK"
        chunkIndex != 0 || totalChunks != 1 -> "$type must use chunkIndex=0 and totalChunks=1"
        requirePayload && payloadLength == 0 -> "$type payload must not be empty"
        requireEmptyPayload && payloadLength != 0 -> "$type payload must be empty"
        else -> null
    }
}
