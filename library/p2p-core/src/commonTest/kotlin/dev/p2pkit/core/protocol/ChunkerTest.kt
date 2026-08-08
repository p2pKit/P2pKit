package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pMessage
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotEquals
import kotlin.test.assertTrue

class ChunkerTest {

    @Test
    fun textMessageProducesOneFrameWithIsTextFlag() {
        val chunker = Chunker(chunkSize = 1024, random = Random(0))
        val frames = chunker.chunk(P2pMessage.Text("hello"))

        assertEquals(1, frames.size)
        val frame = frames[0]
        assertEquals(PacketType.DATA, frame.type)
        assertEquals(0, frame.chunkIndex)
        assertEquals(1, frame.totalChunks)
        assertTrue(frame.isText)
        assertTrue(frame.isLastChunk)
        assertContentEquals("hello".encodeToByteArray(), frame.payload)
    }

    @Test
    fun binaryMessageProducesOneFrameWithoutTextFlag() {
        val chunker = Chunker(chunkSize = 1024, random = Random(0))
        val payload = byteArrayOf(1, 2, 3, 4, 5)
        val frames = chunker.chunk(P2pMessage.Binary(payload))

        assertEquals(1, frames.size)
        val frame = frames[0]
        assertEquals(false, frame.isText)
        assertTrue(frame.isLastChunk)
        assertContentEquals(payload, frame.payload)
    }

    @Test
    fun emptyPayloadStillProducesOneFrame() {
        val chunker = Chunker(chunkSize = 1024, random = Random(0))
        val frames = chunker.chunk(P2pMessage.Binary(ByteArray(0)))
        assertEquals(1, frames.size)
        assertEquals(0, frames[0].payload.size)
        assertTrue(frames[0].isLastChunk)
    }

    @Test
    fun payloadEqualToChunkSizeProducesExactlyOneFrame() {
        val chunker = Chunker(chunkSize = 64, random = Random(0))
        val payload = ByteArray(64) { it.toByte() }
        val frames = chunker.chunk(P2pMessage.Binary(payload))
        assertEquals(1, frames.size)
        assertEquals(1, frames[0].totalChunks)
        assertTrue(frames[0].isLastChunk)
    }

    @Test
    fun payloadOneByteOverChunkSizeSplitsIntoTwoFrames() {
        val chunker = Chunker(chunkSize = 64, random = Random(0))
        val payload = ByteArray(65) { it.toByte() }
        val frames = chunker.chunk(P2pMessage.Binary(payload))

        assertEquals(2, frames.size)
        assertEquals(64, frames[0].payload.size)
        assertEquals(1, frames[1].payload.size)
        assertEquals(0, frames[0].chunkIndex)
        assertEquals(1, frames[1].chunkIndex)
        assertEquals(2, frames[0].totalChunks)
        assertEquals(2, frames[1].totalChunks)
        assertEquals(false, frames[0].isLastChunk)
        assertTrue(frames[1].isLastChunk)
        assertEquals(frames[0].messageId, frames[1].messageId)
    }

    @Test
    fun largePayloadSplitsAcrossManyFrames() {
        val chunkSize = 1024
        val chunker = Chunker(chunkSize = chunkSize, random = Random(0))
        val payload = ByteArray(10_000) { (it and 0xFF).toByte() }
        val frames = chunker.chunk(P2pMessage.Binary(payload))

        val expectedCount = (payload.size + chunkSize - 1) / chunkSize  // 10
        assertEquals(expectedCount, frames.size)
        assertEquals(expectedCount, frames.first().totalChunks)
        // Reassemble manually and verify integrity.
        val reassembled = ByteArray(payload.size)
        var offset = 0
        frames.forEachIndexed { i, frame ->
            assertEquals(i, frame.chunkIndex)
            assertEquals(expectedCount, frame.totalChunks)
            frame.payload.copyInto(reassembled, offset)
            offset += frame.payload.size
        }
        assertContentEquals(payload, reassembled)
        assertTrue(frames.last().isLastChunk)
        // Only the final frame has LAST_CHUNK set.
        for (i in 0 until frames.size - 1) {
            assertEquals(false, frames[i].isLastChunk, "Frame $i should not have LAST_CHUNK")
        }
    }

    @Test
    fun allChunksShareSameMessageId() {
        val chunker = Chunker(chunkSize = 8, random = Random(0))
        val payload = ByteArray(64) { it.toByte() }
        val frames = chunker.chunk(P2pMessage.Binary(payload))
        val firstId = frames.first().messageId
        for (frame in frames) {
            assertEquals(firstId, frame.messageId)
        }
    }

    @Test
    fun separateMessagesGetDifferentMessageIds() {
        val chunker = Chunker(chunkSize = 1024, random = Random(7))
        val one = chunker.chunk(P2pMessage.Text("a")).first().messageId
        val two = chunker.chunk(P2pMessage.Text("b")).first().messageId
        assertNotEquals(one, two)
    }

    @Test
    fun needsAckFlagPropagatesToEveryFrame() {
        val chunker = Chunker(chunkSize = 4, random = Random(0))
        val frames = chunker.chunk(P2pMessage.Binary(ByteArray(12)), needsAck = true)
        for (frame in frames) {
            assertTrue(frame.needsAck, "Frame at index ${frame.chunkIndex} should have NEEDS_ACK")
        }
    }

    @Test
    fun payloadOverMaxThrowsPayloadTooLarge() {
        val chunker = Chunker(
            chunkSize = 1024,
            maxPayloadBytes = 100,
            random = Random(0)
        )
        val tooBig = ByteArray(101)
        val err = assertFailsWith<P2pError.PayloadTooLarge> {
            chunker.chunk(P2pMessage.Binary(tooBig))
        }
        assertEquals(100L, err.maxBytes)
        assertEquals(101L, err.actualBytes)
    }

    @Test
    fun invalidLocalUnicodeIsRejectedInsteadOfReplaced() {
        val chunker = Chunker(random = Random(0))

        assertFailsWith<IllegalArgumentException> {
            chunker.chunk(P2pMessage.Text("bad\uD800value"))
        }
    }
}
