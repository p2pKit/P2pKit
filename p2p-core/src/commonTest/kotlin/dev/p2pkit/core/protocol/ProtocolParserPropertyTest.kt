package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pMessage
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertIs

class ProtocolParserPropertyTest {

    @Test
    fun deterministicRandomFramesRoundTripAcrossArbitraryFragmentation() {
        val random = Random(0x5032504B)
        val expected = List(500) {
            val size = random.nextInt(0, 4097)
            Frame(
                type = PacketType.DATA,
                flags = (
                    FrameFlags.LAST_CHUNK or
                        if (random.nextBoolean()) FrameFlags.NEEDS_ACK else 0
                    ).toByte(),
                messageId = MessageId.random(random),
                chunkIndex = 0,
                totalChunks = 1,
                payload = random.nextBytes(size)
            )
        }
        val wireSize = expected.sumOf { ProtocolConstants.HEADER_SIZE + it.payload.size }
        val wire = ByteArray(wireSize)
        var writeOffset = 0
        for (frame in expected) {
            val encoded = FrameCodec.encode(frame)
            encoded.copyInto(wire, writeOffset)
            writeOffset += encoded.size
        }

        val reader = FrameReader()
        val actual = mutableListOf<Frame>()
        var readOffset = 0
        while (readOffset < wire.size) {
            val fragmentSize = random.nextInt(1, 98)
            val end = minOf(wire.size, readOffset + fragmentSize)
            actual += reader.feed(wire.copyOfRange(readOffset, end))
            readOffset = end
        }

        assertEquals(expected, actual)
        assertEquals(0, reader.bufferedBytes())
        assertEquals(0, reader.skippedUnknownFrames)
        assertEquals(ProtocolConstants.LEGACY_VERSION, actual.first().version)
    }

    @Test
    fun deterministicRandomReassemblyPreservesPayloadAcrossChunkArrivalOrders() {
        val random = Random(0x52454153)
        repeat(100) {
            val payload = random.nextBytes(random.nextInt(1, 32 * 1024))
            val chunkSize = random.nextInt(1, 2049)
            val frames = Chunker(chunkSize = chunkSize, random = random)
                .chunk(P2pMessage.Binary(payload))
                .shuffled(random)
            val reassembler = Reassembler(clock = { 0L })
            var result: P2pMessage? = null

            for (frame in frames) result = reassembler.accept(frame) ?: result

            val binary = assertIs<P2pMessage.Binary>(result)
            assertContentEquals(payload, binary.bytes)
            assertEquals(0, reassembler.pendingCount())
        }
    }
}
