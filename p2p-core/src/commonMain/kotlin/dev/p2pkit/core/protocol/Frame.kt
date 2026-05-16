package dev.p2pkit.core.protocol

import kotlin.random.Random

/**
 * One packet on the wire. A message larger than the configured chunk size is
 * split into multiple frames that share the same [messageId]; the last frame
 * in such a sequence has [FrameFlags.LAST_CHUNK] set.
 */
internal class Frame(
    val type: PacketType,
    val flags: Byte,
    val messageId: MessageId,
    val chunkIndex: Int,
    val totalChunks: Int,
    val payload: ByteArray,
    val version: Byte = ProtocolConstants.VERSION
) {

    val needsAck: Boolean get() = (flags.toInt() and FrameFlags.NEEDS_ACK) != 0
    val isLastChunk: Boolean get() = (flags.toInt() and FrameFlags.LAST_CHUNK) != 0
    val isText: Boolean get() = (flags.toInt() and FrameFlags.IS_TEXT) != 0

    override fun equals(other: Any?): Boolean {
        if (this === other) return true
        if (other !is Frame) return false
        return version == other.version &&
            type == other.type &&
            flags == other.flags &&
            messageId == other.messageId &&
            chunkIndex == other.chunkIndex &&
            totalChunks == other.totalChunks &&
            payload.contentEquals(other.payload)
    }

    override fun hashCode(): Int {
        var result = version.toInt()
        result = 31 * result + type.hashCode()
        result = 31 * result + flags
        result = 31 * result + messageId.hashCode()
        result = 31 * result + chunkIndex
        result = 31 * result + totalChunks
        result = 31 * result + payload.contentHashCode()
        return result
    }

    override fun toString(): String =
        "Frame(type=$type, flags=0x${flags.toUByte().toString(16)}, messageId=$messageId, " +
            "chunkIndex=$chunkIndex/$totalChunks, payload=${payload.size}B)"
}

/** Packet types defined by the P2pKit protocol. */
internal enum class PacketType(val code: Byte) {
    HELLO(0x01),
    DATA(0x02),
    ACK(0x03),
    PING(0x04),
    PONG(0x05),
    ERROR(0x06),
    CLOSE(0x07),

    // File transfer (v0.2.2). All share the same Frame format; messageId carries the
    // transferId for the lifetime of a single file offer.
    FILE_OFFER(0x10),
    FILE_ACCEPT(0x11),
    FILE_REJECT(0x12),
    FILE_DATA(0x13),
    FILE_DONE(0x14),
    FILE_CANCEL(0x15);

    companion object {
        fun fromCode(code: Byte): PacketType? = entries.firstOrNull { it.code == code }
    }
}

/** Bit positions in [Frame.flags]. */
internal object FrameFlags {
    const val NEEDS_ACK: Int = 0x01
    const val LAST_CHUNK: Int = 0x02
    const val IS_TEXT: Int = 0x04
}

/**
 * Stable identifier for a logical message. All frames belonging to one
 * message share the same id. 16 bytes; equality compares by content.
 */
internal class MessageId(val bytes: ByteArray) {

    init {
        require(bytes.size == SIZE) { "MessageId must be $SIZE bytes, got ${bytes.size}" }
    }

    override fun equals(other: Any?): Boolean = other is MessageId && bytes.contentEquals(other.bytes)
    override fun hashCode(): Int = bytes.contentHashCode()
    override fun toString(): String = bytes.toHexString()

    companion object {
        const val SIZE: Int = 16

        fun random(random: Random = Random.Default): MessageId = MessageId(random.nextBytes(SIZE))
    }
}

private fun ByteArray.toHexString(): String = buildString(size * 2) {
    for (b in this@toHexString) {
        val v = b.toInt() and 0xFF
        append(HEX[v ushr 4])
        append(HEX[v and 0x0F])
    }
}

private val HEX = "0123456789abcdef".toCharArray()
