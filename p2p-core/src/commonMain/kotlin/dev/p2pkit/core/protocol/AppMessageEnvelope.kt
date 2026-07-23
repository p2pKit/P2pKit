package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.internal.security.sha256

internal object AppMessageEnvelope {
    private val MAGIC: ByteArray = byteArrayOf(0x50, 0x32, 0x4d, 0x45) // P2ME
    private const val VERSION: Int = 1
    private const val TYPE_TEXT: Int = 1
    private const val TYPE_BINARY: Int = 2
    private const val FIXED_BYTES: Int = 4 + 1 + 1 + 2 + MessageId.SIZE + 8 + 2 + 2 + 2 + 8 + 32

    const val MAX_METADATA_ENTRIES: Int = 64
    const val MAX_METADATA_KEY_BYTES: Int = 256
    const val MAX_METADATA_VALUE_BYTES: Int = 4 * 1024
    const val MAX_METADATA_BYTES: Int = 32 * 1024
    const val MAX_ENVELOPE_OVERHEAD_BYTES: Int =
        FIXED_BYTES + (2 * HelloPayload.MAX_FIELD_UTF8_BYTES) + MAX_METADATA_BYTES +
            MAX_METADATA_ENTRIES * 6

    fun encode(
        message: P2pMessage,
        messageId: MessageId,
        sequence: Long,
        senderPeerId: String,
        recipientPeerId: String
    ): ByteArray {
        require(sequence >= 0) { "Application message sequence must be non-negative" }
        val content: ByteArray
        val type: Int
        val metadata: Map<String, String>
        when (message) {
            is P2pMessage.Text -> {
                content = try {
                    message.value.encodeToByteArray(throwOnInvalidSequence = true)
                } catch (failure: Exception) {
                    throw IllegalArgumentException("Text message contains an invalid Unicode sequence", failure)
                }
                type = TYPE_TEXT
                metadata = message.metadata
            }
            is P2pMessage.Binary -> {
                content = message.bytes
                type = TYPE_BINARY
                metadata = message.metadata
            }
        }
        if (content.size.toLong() > ProtocolConstants.MAX_PAYLOAD_BYTES) {
            throw P2pError.PayloadTooLarge(ProtocolConstants.MAX_PAYLOAD_BYTES, content.size.toLong())
        }
        val sender = encodeIdentity(senderPeerId, "senderPeerId")
        val recipient = encodeIdentity(recipientPeerId, "recipientPeerId")
        val entries = canonicalMetadata(metadata)
        val metadataWireBytes = entries.sumOf { 2 + it.first.size + 4 + it.second.size }
        val total = FIXED_BYTES + sender.size + recipient.size + metadataWireBytes + content.size
        val output = ByteArray(total)
        val writer = Writer(output)
        writer.bytes(MAGIC)
        writer.u8(VERSION)
        writer.u8(type)
        writer.u16(0)
        writer.bytes(messageId.bytes)
        writer.u64(sequence)
        writer.sizedU16(sender)
        writer.sizedU16(recipient)
        writer.u16(entries.size)
        for ((key, value) in entries) {
            writer.sizedU16(key)
            writer.sizedU32(value)
        }
        writer.u64(content.size.toLong())
        writer.bytes(sha256(content).copyBytes())
        writer.bytes(content)
        check(writer.position == output.size)
        return output
    }

    fun decode(payload: ByteArray, frameMessageId: MessageId, state: ProtocolSessionState): P2pMessage {
        if (!state.secure || !state.supports(ProtocolFeatures.APP_MESSAGE_ENVELOPE_V1)) {
            throw P2pError.ProtocolError("Application message envelope was not negotiated")
        }
        if (payload.size > ProtocolConstants.MAX_APP_MESSAGE_ENVELOPE_BYTES) {
            throw P2pError.ProtocolError("Application message envelope exceeds the configured bound")
        }
        val reader = Reader(payload)
        if (!reader.bytes(MAGIC.size).contentEquals(MAGIC)) {
            throw P2pError.ProtocolError("Invalid application message envelope magic")
        }
        if (reader.u8() != VERSION) throw P2pError.ProtocolError("Unsupported application envelope version")
        val type = reader.u8()
        if (type != TYPE_TEXT && type != TYPE_BINARY) {
            throw P2pError.ProtocolError("Unsupported application message type $type")
        }
        if (reader.u16() != 0) throw P2pError.ProtocolError("Application envelope flags must be zero")
        val embeddedId = MessageId(reader.bytes(MessageId.SIZE))
        if (embeddedId != frameMessageId) {
            throw P2pError.ProtocolError("Application envelope messageId does not match frame header")
        }
        val sequence = reader.u64()
        val sender = reader.sizedU16("senderPeerId", HelloPayload.MAX_FIELD_UTF8_BYTES)
            .decodeStrictUtf8("application senderPeerId")
        val recipient = reader.sizedU16("recipientPeerId", HelloPayload.MAX_FIELD_UTF8_BYTES)
            .decodeStrictUtf8("application recipientPeerId")
        validateWireText(sender, "application senderPeerId", HelloPayload.MAX_FIELD_LEN,
            HelloPayload.MAX_FIELD_UTF8_BYTES, true)
        validateWireText(recipient, "application recipientPeerId", HelloPayload.MAX_FIELD_LEN,
            HelloPayload.MAX_FIELD_UTF8_BYTES, true)
        if (sender != state.remotePeerId || recipient != state.localPeerId) {
            throw P2pError.AuthenticatedIdentityMismatch(
                "Application envelope identity does not match the authenticated session"
            )
        }
        val count = reader.u16()
        if (count > MAX_METADATA_ENTRIES) {
            throw P2pError.ProtocolError("Application metadata has $count entries; max $MAX_METADATA_ENTRIES")
        }
        val metadata = linkedMapOf<String, String>()
        var metadataBytes = 0
        var previousKey: ByteArray? = null
        repeat(count) {
            val keyBytes = reader.sizedU16("metadata key", MAX_METADATA_KEY_BYTES)
            val valueBytes = reader.sizedU32("metadata value", MAX_METADATA_VALUE_BYTES)
            metadataBytes += keyBytes.size + valueBytes.size
            if (metadataBytes > MAX_METADATA_BYTES) {
                throw P2pError.ProtocolError("Application metadata exceeds $MAX_METADATA_BYTES bytes")
            }
            val prior = previousKey
            if (prior != null && compareUnsigned(prior, keyBytes) >= 0) {
                throw P2pError.ProtocolError("Application metadata keys are duplicated or not canonical")
            }
            previousKey = keyBytes
            val key = keyBytes.decodeStrictUtf8("metadata key")
            val value = valueBytes.decodeStrictUtf8("metadata value")
            validateWireText(key, "metadata key", MAX_METADATA_KEY_BYTES, MAX_METADATA_KEY_BYTES, true)
            validateWireText(value, "metadata value", MAX_METADATA_VALUE_BYTES,
                MAX_METADATA_VALUE_BYTES, false)
            metadata[key] = value
        }
        val contentLength = reader.u64()
        if (contentLength > ProtocolConstants.MAX_PAYLOAD_BYTES) {
            throw P2pError.ProtocolError("Application content length $contentLength exceeds maximum")
        }
        val expectedDigest = reader.bytes(32)
        if (contentLength > Int.MAX_VALUE || reader.remaining != contentLength.toInt()) {
            throw P2pError.ProtocolError("Application content length does not match envelope bytes")
        }
        val content = reader.bytes(contentLength.toInt())
        if (!sha256(content).copyBytes().contentEquals(expectedDigest)) {
            throw P2pError.ProtocolError("Application content SHA-256 mismatch")
        }
        state.commitInboundEnvelope(sequence, frameMessageId)
        return if (type == TYPE_TEXT) {
            P2pMessage.Text(content.decodeStrictUtf8("application text content"), metadata)
        } else {
            P2pMessage.Binary(content, metadata)
        }
    }

    private fun encodeIdentity(value: String, field: String): ByteArray {
        validateWireText(value, field, HelloPayload.MAX_FIELD_LEN, HelloPayload.MAX_FIELD_UTF8_BYTES, true)
        return value.encodeToByteArray()
    }

    private fun canonicalMetadata(metadata: Map<String, String>): List<Pair<ByteArray, ByteArray>> {
        require(metadata.size <= MAX_METADATA_ENTRIES) {
            "Application metadata has ${metadata.size} entries; max $MAX_METADATA_ENTRIES"
        }
        var total = 0
        return metadata.map { (key, value) ->
            validateWireText(key, "metadata key", MAX_METADATA_KEY_BYTES, MAX_METADATA_KEY_BYTES, true)
            validateWireText(value, "metadata value", MAX_METADATA_VALUE_BYTES,
                MAX_METADATA_VALUE_BYTES, false)
            val keyBytes = key.encodeToByteArray()
            val valueBytes = value.encodeToByteArray()
            total += keyBytes.size + valueBytes.size
            require(total <= MAX_METADATA_BYTES) {
                "Application metadata exceeds $MAX_METADATA_BYTES bytes"
            }
            keyBytes to valueBytes
        }.sortedWith { left, right -> compareUnsigned(left.first, right.first) }
    }

    private fun compareUnsigned(left: ByteArray, right: ByteArray): Int {
        val common = minOf(left.size, right.size)
        for (index in 0 until common) {
            val difference = (left[index].toInt() and 0xff) - (right[index].toInt() and 0xff)
            if (difference != 0) return difference
        }
        return left.size - right.size
    }

    private class Writer(private val output: ByteArray) {
        var position: Int = 0
            private set
        fun u8(value: Int) { output[position++] = value.toByte() }
        fun u16(value: Int) {
            require(value in 0..0xffff)
            output[position++] = (value ushr 8).toByte()
            output[position++] = value.toByte()
        }
        fun u32(value: Int) {
            require(value >= 0)
            output[position++] = (value ushr 24).toByte()
            output[position++] = (value ushr 16).toByte()
            output[position++] = (value ushr 8).toByte()
            output[position++] = value.toByte()
        }
        fun u64(value: Long) {
            require(value >= 0)
            for (shift in 56 downTo 0 step 8) output[position++] = (value ushr shift).toByte()
        }
        fun bytes(value: ByteArray) { value.copyInto(output, position); position += value.size }
        fun sizedU16(value: ByteArray) { u16(value.size); bytes(value) }
        fun sizedU32(value: ByteArray) { u32(value.size); bytes(value) }
    }

    private class Reader(private val input: ByteArray) {
        var position: Int = 0
            private set
        val remaining: Int get() = input.size - position
        fun u8(): Int = bytes(1)[0].toInt() and 0xff
        fun u16(): Int {
            val value = bytes(2)
            return ((value[0].toInt() and 0xff) shl 8) or (value[1].toInt() and 0xff)
        }
        fun u32(): Int {
            val value = bytes(4)
            val decoded = ((value[0].toInt() and 0xff) shl 24) or
                ((value[1].toInt() and 0xff) shl 16) or
                ((value[2].toInt() and 0xff) shl 8) or (value[3].toInt() and 0xff)
            if (decoded < 0) throw P2pError.ProtocolError("Unsigned length exceeds supported range")
            return decoded
        }
        fun u64(): Long {
            val value = bytes(8)
            if (value[0].toInt() and 0x80 != 0) {
                throw P2pError.ProtocolError("Unsigned 64-bit value exceeds supported range")
            }
            var result = 0L
            for (byte in value) result = (result shl 8) or (byte.toLong() and 0xff)
            return result
        }
        fun bytes(count: Int): ByteArray {
            if (count < 0 || count > remaining) throw P2pError.ProtocolError("Truncated application envelope")
            return input.copyOfRange(position, position + count).also { position += count }
        }
        fun sizedU16(field: String, max: Int): ByteArray {
            val size = u16()
            if (size > max) throw P2pError.ProtocolError("$field exceeds $max bytes")
            return bytes(size)
        }
        fun sizedU32(field: String, max: Int): ByteArray {
            val size = u32()
            if (size > max) throw P2pError.ProtocolError("$field exceeds $max bytes")
            return bytes(size)
        }
    }
}
