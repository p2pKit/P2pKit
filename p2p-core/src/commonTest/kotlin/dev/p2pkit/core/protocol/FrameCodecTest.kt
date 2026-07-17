package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class FrameCodecTest {

    private val rng = Random(42)
    private fun id() = MessageId.random(rng)

    @Test
    fun roundTripDataFrame() {
        val payload = "hello, p2pkit".encodeToByteArray()
        val frame = Frame(
            type = PacketType.DATA,
            flags = (FrameFlags.LAST_CHUNK or FrameFlags.IS_TEXT).toByte(),
            messageId = id(),
            chunkIndex = 0,
            totalChunks = 1,
            payload = payload
        )
        val encoded = FrameCodec.encode(frame)
        val decoded = FrameCodec.decode(encoded)
        assertEquals(frame, decoded)
        assertTrue(decoded.isLastChunk)
        assertTrue(decoded.isText)
    }

    @Test
    fun roundTripEveryPacketType() {
        for (type in PacketType.entries) {
            val frame = Frame(
                type = type,
                flags = FrameFlags.LAST_CHUNK.toByte(),
                messageId = id(),
                chunkIndex = 0,
                totalChunks = 1,
                payload = byteArrayOf(1, 2, 3)
            )
            val decoded = FrameCodec.decode(FrameCodec.encode(frame))
            assertEquals(type, decoded.type, "Round-trip failed for $type")
            assertEquals(frame, decoded)
        }
    }

    @Test
    fun emptyPayloadIsValid() {
        val frame = Frame(
            type = PacketType.ACK,
            flags = 0,
            messageId = id(),
            chunkIndex = 0,
            totalChunks = 1,
            payload = ByteArray(0)
        )
        val decoded = FrameCodec.decode(FrameCodec.encode(frame))
        assertEquals(0, decoded.payload.size)
        assertEquals(PacketType.ACK, decoded.type)
    }

    @Test
    fun magicBytesAreCorrect() {
        val encoded = FrameCodec.encode(
            Frame(PacketType.HELLO, 0, id(), 0, 1, ByteArray(0))
        )
        // Magic = 'P' 'P' '2' 'K'
        assertEquals(0x50.toByte(), encoded[0])
        assertEquals(0x50.toByte(), encoded[1])
        assertEquals(0x32.toByte(), encoded[2])
        assertEquals(0x4B.toByte(), encoded[3])
        // Version
        assertEquals(ProtocolConstants.VERSION, encoded[4])
    }

    @Test
    fun decodeRejectsBadMagic() {
        val good = FrameCodec.encode(Frame(PacketType.PING, 0, id(), 0, 1, ByteArray(0)))
        good[0] = 0x00
        val err = assertFailsWith<P2pError.ProtocolError> { FrameCodec.decode(good) }
        assertTrue(err.message!!.contains("magic", ignoreCase = true))
    }

    @Test
    fun decodeRejectsUnexpectedHeaderVersion() {
        val encoded = FrameCodec.encode(
            Frame(PacketType.PING, 0, id(), 0, 1, ByteArray(0), version = 99)
        )

        val error = assertFailsWith<P2pError.VersionMismatch> {
            FrameCodec.decode(encoded, expectedVersion = ProtocolConstants.SECURE_VERSION)
        }

        assertEquals(ProtocolConstants.SECURE_VERSION.toInt(), error.localVersion)
        assertEquals(99, error.remoteVersion)
    }

    @Test
    fun secureVersionRoundTripsOnlyWhenExplicitlyExpected() {
        val frame = Frame(
            PacketType.PING,
            0,
            id(),
            0,
            1,
            ByteArray(0),
            version = ProtocolConstants.SECURE_VERSION
        )

        assertEquals(
            frame,
            FrameCodec.decode(
                FrameCodec.encode(frame),
                expectedVersion = ProtocolConstants.SECURE_VERSION
            )
        )
    }

    @Test
    fun decodeRejectsTooShort() {
        val tiny = ByteArray(ProtocolConstants.HEADER_SIZE - 1)
        assertFailsWith<P2pError.ProtocolError> { FrameCodec.decode(tiny) }
    }

    @Test
    fun decodeRejectsTruncatedPayload() {
        val frame = Frame(
            type = PacketType.DATA,
            flags = FrameFlags.LAST_CHUNK.toByte(),
            messageId = id(),
            chunkIndex = 0,
            totalChunks = 1,
            payload = ByteArray(100) { it.toByte() }
        )
        val full = FrameCodec.encode(frame)
        // Drop the last 10 bytes of the payload.
        val truncated = full.copyOfRange(0, full.size - 10)
        val err = assertFailsWith<P2pError.ProtocolError> { FrameCodec.decode(truncated) }
        assertTrue(err.message!!.contains("Truncated", ignoreCase = true))
    }

    @Test
    fun decodeThrowsUnknownPacketTypeForUnrecognizedTypeCode() {
        val encoded = FrameCodec.encode(Frame(PacketType.PING, 0, id(), 0, 1, ByteArray(0)))
        encoded[5] = 0x7F // bogus type code
        val err = assertFailsWith<UnknownPacketTypeException> { FrameCodec.decode(encoded) }
        assertEquals(0x7F.toByte(), err.typeCode)
    }

    @Test
    fun decodeRejectsInvalidChunkIndex() {
        val encoded = FrameCodec.encode(
            Frame(PacketType.DATA, FrameFlags.LAST_CHUNK.toByte(), id(), 0, 2, ByteArray(4))
        )
        // Overwrite chunk_index to be >= totalChunks.
        FrameCodec.writeIntBE(encoded, 24, 5)
        val err = assertFailsWith<P2pError.ProtocolError> { FrameCodec.decode(encoded) }
        assertTrue(err.message!!.contains("chunkIndex", ignoreCase = true))
    }

    @Test
    fun decodeRejectsZeroTotalChunks() {
        val encoded = FrameCodec.encode(
            Frame(PacketType.DATA, FrameFlags.LAST_CHUNK.toByte(), id(), 0, 1, ByteArray(0))
        )
        FrameCodec.writeIntBE(encoded, 28, 0)
        assertFailsWith<P2pError.ProtocolError> { FrameCodec.decode(encoded) }
    }

    @Test
    fun decodeRejectsNegativePayloadLength() {
        val encoded = FrameCodec.encode(
            Frame(PacketType.DATA, FrameFlags.LAST_CHUNK.toByte(), id(), 0, 1, ByteArray(0))
        )
        FrameCodec.writeIntBE(encoded, 32, -1)
        assertFailsWith<P2pError.ProtocolError> { FrameCodec.decode(encoded) }
    }

    /**
     * Decode-side twin of the reader's declared-length bound (2026-07 review
     * P1-17, A07 §3 r1): a payload_len over
     * [ProtocolConstants.MAX_FRAME_PAYLOAD_BYTES] is rejected as a
     * [P2pError.ProtocolError] citing the cap — checked before the truncation
     * check, so the rejection is about the bound, not the missing bytes.
     */
    @Test
    fun decodeRejectsOversizeDeclaredPayloadLength() {
        val encoded = FrameCodec.encode(
            Frame(PacketType.DATA, FrameFlags.LAST_CHUNK.toByte(), id(), 0, 1, ByteArray(4))
        )
        FrameCodec.writeIntBE(encoded, 32, ProtocolConstants.MAX_FRAME_PAYLOAD_BYTES + 1)
        val err = assertFailsWith<P2pError.ProtocolError> { FrameCodec.decode(encoded) }
        assertTrue(
            err.message!!.contains("exceeds maximum"),
            "Rejection must cite the payload-length cap, got: ${err.message}"
        )
    }

    @Test
    fun flagsBitsRoundTripIndependently() {
        val withAll = Frame(
            type = PacketType.DATA,
            flags = (FrameFlags.NEEDS_ACK or FrameFlags.LAST_CHUNK or FrameFlags.IS_TEXT).toByte(),
            messageId = id(),
            chunkIndex = 0,
            totalChunks = 1,
            payload = byteArrayOf()
        )
        val decoded = FrameCodec.decode(FrameCodec.encode(withAll))
        assertTrue(decoded.needsAck)
        assertTrue(decoded.isLastChunk)
        assertTrue(decoded.isText)
    }
}
