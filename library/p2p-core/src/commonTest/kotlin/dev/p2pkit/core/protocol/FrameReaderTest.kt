package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.testfixtures.RecordingLogger
import kotlinx.coroutines.CancellationException
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class FrameReaderTest {

    private val rng = Random(7)

    private fun frame(payloadSize: Int): Frame = Frame(
        type = PacketType.DATA,
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
        val b = frame(32)
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
    fun unexpectedVersionIsRejectedFromHeaderAlone() {
        val reader = FrameReader(expectedVersion = ProtocolConstants.SECURE_VERSION)
        val header = FrameCodec.encode(
            frame(0).withVersion(ProtocolConstants.LEGACY_VERSION)
        ).copyOfRange(0, ProtocolConstants.HEADER_SIZE)
        FrameCodec.writeIntBE(header, 32, ProtocolConstants.MAX_FRAME_PAYLOAD_BYTES)

        val error = assertFailsWith<P2pError.VersionMismatch> { reader.feed(header) }

        assertEquals(ProtocolConstants.SECURE_VERSION.toInt(), error.localVersion)
        assertEquals(ProtocolConstants.LEGACY_VERSION.toInt(), error.remoteVersion)
    }

    @Test
    fun emptyFeedReturnsEmpty() {
        val reader = FrameReader()
        assertTrue(reader.feed(ByteArray(0)).isEmpty())
    }

    // ---- Declared-length bound enforcement (2026-07 review P1-17, A07 §3 r1) ----

    /**
     * The bounded-memory guard advertised by [ProtocolConstants.MAX_FRAME_PAYLOAD_BYTES]:
     * a header declaring an over-limit payload length must raise
     * [P2pError.ProtocolError] from the header alone — before a single payload
     * byte has arrived — so the reader never waits for or buffers the declared
     * (potentially multi-GiB) payload.
     */
    @Test
    fun oversizeDeclaredPayloadLengthIsRejectedOnHeaderAloneWithoutBuffering() {
        val reader = FrameReader()
        // A complete valid header (encoded zero-payload frame), with the
        // payload_len field patched to one past the cap. Only these 36 header
        // bytes are fed — no payload bytes exist to buffer.
        val headerOnly = FrameCodec.encode(frame(0)).copyOfRange(0, ProtocolConstants.HEADER_SIZE)
        FrameCodec.writeIntBE(headerOnly, 32, ProtocolConstants.MAX_FRAME_PAYLOAD_BYTES + 1)

        val err = assertFailsWith<P2pError.ProtocolError> { reader.feed(headerOnly) }
        assertTrue(
            err.message!!.contains("exceeds maximum"),
            "Rejection must cite the payload-length cap, got: ${err.message}"
        )
    }

    /**
     * Boundary companion: a declared length of exactly
     * [ProtocolConstants.MAX_DATA_FRAME_PAYLOAD_BYTES] is within the DATA bound — the
     * reader accepts the header and waits (buffering only the header bytes it
     * was given) for the payload to arrive.
     */
    @Test
    fun maxDeclaredDataPayloadLengthIsAcceptedAtTheBoundary() {
        val reader = FrameReader()
        val headerOnly = FrameCodec.encode(frame(0)).copyOfRange(0, ProtocolConstants.HEADER_SIZE)
        FrameCodec.writeIntBE(headerOnly, 32, ProtocolConstants.MAX_DATA_FRAME_PAYLOAD_BYTES)

        val out = reader.feed(headerOnly)

        assertTrue(out.isEmpty(), "No frame can be emitted until the payload arrives")
        assertEquals(ProtocolConstants.HEADER_SIZE, reader.bufferedBytes())
    }

    @Test
    fun unknownPacketTypeIsSkippedAndSurroundingFramesStillDecode() {
        val reader = FrameReader()
        val valid = frame(8)
        val validBytes = FrameCodec.encode(valid)

        // Build a frame with a deliberately bogus packet type code.
        val unknown = FrameCodec.encode(frame(8)).copyOf()
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

    @Test
    fun diagnosticCancellationFromUnknownPacketLoggerCannotAbortParsing() {
        val logger = object : P2pLogger {
            override fun debug(message: String) = Unit
            override fun info(message: String) = Unit
            override fun warn(message: String, throwable: Throwable?) {
                throw CancellationException("logger callback")
            }
            override fun error(message: String, throwable: Throwable?) = Unit
        }
        val reader = FrameReader(logger)
        val valid = FrameCodec.encode(frame(8))
        val unknown = FrameCodec.encode(frame(4)).also { it[5] = 0x7F }

        val decoded = reader.feed(unknown + valid)

        assertEquals(1, reader.skippedUnknownFrames)
        assertEquals(1, decoded.size)
    }

    @Test
    fun fragmentedLargeFrameUsesLinearRelocationWork() {
        val reader = FrameReader()
        val original = frame(256 * 1024)
        val encoded = FrameCodec.encode(original)
        val decoded = mutableListOf<Frame>()

        var offset = 0
        while (offset < encoded.size) {
            val end = minOf(encoded.size, offset + 7)
            decoded += reader.feed(encoded.copyOfRange(offset, end))
            offset = end
        }

        assertEquals(listOf(original), decoded)
        assertTrue(
            reader.relocatedBytes <= encoded.size.toLong() * 2,
            "buffer growth relocated ${reader.relocatedBytes} bytes for ${encoded.size} input bytes"
        )
    }

    @Test
    fun packetSpecificLimitIsRejectedFromHeaderAlone() {
        val hello = Frame(
            PacketType.HELLO,
            FrameFlags.LAST_CHUNK.toByte(),
            MessageId.random(rng),
            0,
            1,
            byteArrayOf(1)
        )
        val header = FrameCodec.encode(hello).copyOfRange(0, ProtocolConstants.HEADER_SIZE)
        FrameCodec.writeIntBE(header, 32, ProtocolConstants.MAX_HELLO_PAYLOAD_BYTES + 1)

        val failure = assertFailsWith<P2pError.ProtocolError> { FrameReader().feed(header) }

        assertTrue(failure.message!!.contains("HELLO"))
    }

    @Test
    fun allPacketFamiliesEnforceTheirDeclaredLimitFromTheHeader() {
        val cases = PacketType.entries.map { type ->
            type to FrameValidation.maxPayloadBytes(type)
        }
        for ((type, maximum) in cases) {
            val payload = when (type) {
                PacketType.HELLO, PacketType.FILE_OFFER, PacketType.ERROR,
                PacketType.FILE_FINISH, PacketType.FILE_COMMIT, PacketType.FILE_RESULT,
                PacketType.DATA, PacketType.FILE_DATA -> byteArrayOf(1)
                else -> ByteArray(0)
            }
            val valid = Frame(
                type,
                FrameFlags.LAST_CHUNK.toByte(),
                MessageId.random(rng),
                0,
                1,
                payload
            )
            val header = FrameCodec.encode(valid).copyOfRange(0, ProtocolConstants.HEADER_SIZE)
            FrameCodec.writeIntBE(header, 32, maximum + 1)

            val failure = assertFailsWith<P2pError.ProtocolError>(type.name) {
                FrameReader().feed(header)
            }
            assertTrue(failure.message!!.contains(type.name))
        }
    }

    @Test
    fun unknownPacketPayloadIsCappedFromHeaderForForwardCompatibility() {
        val header = FrameCodec.encode(frame(0)).copyOfRange(0, ProtocolConstants.HEADER_SIZE)
        header[5] = 0x7F
        FrameCodec.writeIntBE(header, 32, ProtocolConstants.MAX_UNKNOWN_PACKET_PAYLOAD_BYTES + 1)

        val failure = assertFailsWith<P2pError.ProtocolError> { FrameReader().feed(header) }

        assertTrue(failure.message!!.contains("unknown packet"))
    }

    @Test
    fun invalidControlShapeIsRejectedFromHeaderAlone() {
        val ping = Frame(
            PacketType.PING,
            FrameFlags.LAST_CHUNK.toByte(),
            MessageId.random(rng),
            0,
            1,
            ByteArray(0)
        )
        val header = FrameCodec.encode(ping).copyOfRange(0, ProtocolConstants.HEADER_SIZE)
        header[6] = 0

        val failure = assertFailsWith<P2pError.ProtocolError> { FrameReader().feed(header) }

        assertTrue(failure.message!!.contains("flags"))
    }

    @Test
    fun unknownPacketWarningsAreBoundedPerConnection() {
        val logger = RecordingLogger()
        val reader = FrameReader(logger)
        val unknown = FrameCodec.encode(frame(1)).also { it[5] = 0x7F }
        val input = ByteArray(unknown.size * 100)
        repeat(100) { index -> unknown.copyInto(input, index * unknown.size) }

        assertTrue(reader.feed(input).isEmpty())

        assertEquals(100, reader.skippedUnknownFrames)
        assertEquals(5, logger.warnings.size)
        assertTrue(logger.warnings.last().contains("suppressed"))
    }
}
