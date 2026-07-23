package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pMessage
import kotlin.random.Random

/**
 * Splits a [P2pMessage] into one or more [Frame]s.
 *
 * Payloads up to [chunkSize] produce exactly one frame with
 * [FrameFlags.LAST_CHUNK] set. Larger payloads are split; every frame in such
 * a sequence carries the same [MessageId] and a 0-based [Frame.chunkIndex];
 * only the final frame has [FrameFlags.LAST_CHUNK].
 *
 * Throws [P2pError.PayloadTooLarge] if the payload exceeds
 * [ProtocolConstants.MAX_PAYLOAD_BYTES] (4 MiB in v0.1).
 */
internal class Chunker(
    private val chunkSize: Int = ProtocolConstants.DEFAULT_CHUNK_SIZE,
    private val maxPayloadBytes: Long = ProtocolConstants.MAX_PAYLOAD_BYTES,
    private val random: Random = Random.Default
) {
    init {
        require(chunkSize > 0) { "chunkSize must be positive, got $chunkSize" }
        require(maxPayloadBytes > 0) { "maxPayloadBytes must be positive" }
    }

    fun chunk(message: P2pMessage, needsAck: Boolean = false): List<Frame> {
        val (bytes, isText) = when (message) {
            is P2pMessage.Text -> {
                val encoded = try {
                    message.value.encodeToByteArray(throwOnInvalidSequence = true)
                } catch (failure: Exception) {
                    throw IllegalArgumentException("Text message contains an invalid Unicode sequence", failure)
                }
                encoded to true
            }
            is P2pMessage.Binary -> message.bytes to false
        }
        if (bytes.size.toLong() > maxPayloadBytes) {
            throw P2pError.PayloadTooLarge(maxBytes = maxPayloadBytes, actualBytes = bytes.size.toLong())
        }
        return chunkPayload(
            bytes = bytes,
            messageId = MessageId.random(random),
            extraFlags = if (isText) FrameFlags.IS_TEXT else 0,
            needsAck = needsAck,
            maximumBytes = maxPayloadBytes
        )
    }

    fun chunkEnvelope(payload: ByteArray, messageId: MessageId): List<Frame> =
        chunkPayload(
            bytes = payload,
            messageId = messageId,
            extraFlags = FrameFlags.IS_ENVELOPE,
            needsAck = false,
            maximumBytes = ProtocolConstants.MAX_APP_MESSAGE_ENVELOPE_BYTES.toLong()
        )

    private fun chunkPayload(
        bytes: ByteArray,
        messageId: MessageId,
        extraFlags: Int,
        needsAck: Boolean,
        maximumBytes: Long
    ): List<Frame> {
        if (bytes.size.toLong() > maximumBytes) {
            throw P2pError.PayloadTooLarge(maxBytes = maximumBytes, actualBytes = bytes.size.toLong())
        }

        if (bytes.isEmpty() || bytes.size <= chunkSize) {
            // Single frame: total = 1, index = 0, LAST_CHUNK set.
            return listOf(
                Frame(
                    type = PacketType.DATA,
                    flags = combineFlags(extraFlags, lastChunk = true, needsAck = needsAck),
                    messageId = messageId,
                    chunkIndex = 0,
                    totalChunks = 1,
                    payload = bytes
                )
            )
        }

        val total = (bytes.size + chunkSize - 1) / chunkSize
        return (0 until total).map { i ->
            val start = i * chunkSize
            val end = minOf(start + chunkSize, bytes.size)
            val isLast = i == total - 1
            Frame(
                type = PacketType.DATA,
                flags = combineFlags(extraFlags, lastChunk = isLast, needsAck = needsAck),
                messageId = messageId,
                chunkIndex = i,
                totalChunks = total,
                payload = bytes.copyOfRange(start, end)
            )
        }
    }

    private fun combineFlags(extra: Int, lastChunk: Boolean, needsAck: Boolean): Byte {
        var flags = extra
        if (lastChunk) flags = flags or FrameFlags.LAST_CHUNK
        if (needsAck) flags = flags or FrameFlags.NEEDS_ACK
        return flags.toByte()
    }
}
