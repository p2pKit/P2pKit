package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class FrameReaderTest {

    private val rng = Random(7)

    private fun frame(payloadSize: Int, type: PacketType = PacketType.DATA): Frame = Frame(
        type = type,
        flags = FrameFlags.LAST_CHUNK.toByte(),
        messageId = MessageId.random(rng),
        chunkIndex = 0,
        totalChunks = 1,
        payload = ByteArray(payloadSize) { it.toByte() }
    )

    @Test
    fun feedingCompleteFrameYieldsIt() {
        val reader = FrameReader()
        val f = frame(16)
        val out = reader.feed(FrameCodec.encode(f))
        assertEquals(1, out.size)
        assertEquals(f, out[0])
        assertEquals(0, reader.bufferedBytes())
    }

    @Test
    fun feedingTwoBackToBackFramesYieldsBoth() {
        val reader = FrameReader()
        val a = frame(8)
        val b = frame(32, PacketType.ACK)
        val combined = FrameCodec.encode(a) + FrameCodec.encode(b)
        val out = reader.feed(combined)
        assertEquals(2, out.size)
        assertEquals(a, out[0])
        assertEquals(b, out[1])
        assertEquals(0, reader.bufferedBytes())
    }

    @Test
    fun partialHeaderIsBufferedNotEmitted() {
        val reader = FrameReader()
        val f = frame(8)
        val encoded = FrameCodec.encode(f)
        // Feed only the first 10 bytes — less than the 36-byte header.
        val out = reader.feed(encoded.copyOfRange(0, 10))
        assertTrue(out.isEmpty())
        assertEquals(10, reader.bufferedBytes())

        // Feed the rest; the frame should now appear.
        val out2 = reader.feed(encoded.copyOfRange(10, encoded.size))
        assertEquals(1, out2.size)
        assertEquals(f, out2[0])
        assertEquals(0, reader.bufferedBytes())
    }

    @Test
    fun headerCompletePayloadPartialBuffers() {
        val reader = FrameReader()
        val f = frame(100)
        val encoded = FrameCodec.encode(f)
        // Feed header + half the payload.
        val splitAt = ProtocolConstants.HEADER_SIZE + 50
        val first = reader.feed(encoded.copyOfRange(0, splitAt))
        assertTrue(first.isEmpty())
        assertEquals(splitAt, reader.bufferedBytes())

        // Deliver the rest.
        val rest = reader.feed(encoded.copyOfRange(splitAt, encoded.size))
        assertEquals(1, rest.size)
        assertEquals(f, rest[0])
    }

    @Test
    fun byteAtATimeStillReconstructs() {
        val reader = FrameReader()
        val f = frame(40)
        val encoded = FrameCodec.encode(f)
        val emitted = mutableListOf<Frame>()
        for (b in encoded) {
            emitted.addAll(reader.feed(byteArrayOf(b)))
        }
        assertEquals(1, emitted.size)
        assertEquals(f, emitted[0])
    }

    @Test
    fun corruptedFrameRaisesProtocolError() {
        val reader = FrameReader()
        val f = frame(8)
        val encoded = FrameCodec.encode(f)
        encoded[0] = 0x00 // bad magic
        assertFailsWith<P2pError.ProtocolError> { reader.feed(encoded) }
    }

    @Test
    fun emptyFeedReturnsEmpty() {
        val reader = FrameReader()
        assertTrue(reader.feed(ByteArray(0)).isEmpty())
    }

    @Test
    fun unknownPacketTypeIsSkippedAndSurroundingFramesStillDecode() {
        val reader = FrameReader()
        val valid = frame(8)
        val validBytes = FrameCodec.encode(valid)

        // Build a frame with a deliberately bogus packet type code.
        val unknown = FrameCodec.encode(frame(8, PacketType.PING)).copyOf()
        unknown[5] = 0x7F

        // Feed [valid][unknown][valid] in one shot.
        val combined = validBytes + unknown + validBytes
        val out = reader.feed(combined)

        // Reader emits the two valid frames, skips the middle one, and reports it.
        assertEquals(2, out.size)
        assertEquals(valid, out[0])
        assertEquals(valid, out[1])
        assertEquals(1, reader.skippedUnknownFrames)
        // Buffer fully consumed.
        assertEquals(0, reader.bufferedBytes())
    }
}
