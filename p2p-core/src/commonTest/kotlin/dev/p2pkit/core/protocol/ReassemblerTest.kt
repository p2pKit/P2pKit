package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pMessage
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertTrue

class ReassemblerTest {

    private val chunker = Chunker(chunkSize = 8, random = Random(123))

    @Test
    fun singleFrameYieldsMessageImmediately() {
        val reassembler = Reassembler(clock = { 0L })
        val frames = chunker.chunk(P2pMessage.Text("hello"))
        assertEquals(1, frames.size)

        val message = reassembler.accept(frames[0])
        assertIs<P2pMessage.Text>(message)
        assertEquals("hello", message.value)
        assertEquals(0, reassembler.pendingCount())
    }

    @Test
    fun multipleFramesReassembleInOrder() {
        val reassembler = Reassembler(clock = { 0L })
        val payload = ByteArray(20) { it.toByte() }
        val frames = chunker.chunk(P2pMessage.Binary(payload))
        assertTrue(frames.size > 1)

        for (i in 0 until frames.size - 1) {
            assertNull(reassembler.accept(frames[i]))
        }
        val message = reassembler.accept(frames.last())
        assertIs<P2pMessage.Binary>(message)
        assertContentEquals(payload, message.bytes)
        assertEquals(0, reassembler.pendingCount())
    }

    @Test
    fun multipleFramesReassembleOutOfOrder() {
        val reassembler = Reassembler(clock = { 0L })
        val payload = ByteArray(20) { it.toByte() }
        val frames = chunker.chunk(P2pMessage.Binary(payload))
        assertEquals(3, frames.size)

        // Deliver index 2, then 0, then 1. Last delivered frame completes.
        assertNull(reassembler.accept(frames[2]))
        assertNull(reassembler.accept(frames[0]))
        val message = reassembler.accept(frames[1])
        assertIs<P2pMessage.Binary>(message)
        assertContentEquals(payload, message.bytes)
    }

    @Test
    fun textFlagIsPreservedAcrossChunks() {
        val reassembler = Reassembler(clock = { 0L })
        val text = (1..100).joinToString("") { "x" }  // forces >1 chunk at chunkSize=8
        val frames = chunker.chunk(P2pMessage.Text(text))
        assertTrue(frames.size > 1)

        var result: P2pMessage? = null
        for (frame in frames) {
            result = reassembler.accept(frame) ?: result
        }
        assertIs<P2pMessage.Text>(result)
        assertEquals(text, result.value)
    }

    @Test
    fun nonDataFrameReturnsNull() {
        val reassembler = Reassembler(clock = { 0L })
        val ping = Frame(
            type = PacketType.PING,
            flags = 0,
            messageId = MessageId.random(Random(1)),
            chunkIndex = 0,
            totalChunks = 1,
            payload = ByteArray(0)
        )
        assertNull(reassembler.accept(ping))
        assertEquals(0, reassembler.pendingCount())
    }

    @Test
    fun stalePartialMessageIsEvicted() {
        var now = 1_000L
        val reassembler = Reassembler(clock = { now }, reassemblyTimeoutMillis = 5_000)
        val payload = ByteArray(20)  // 3 chunks at chunkSize=8
        val frames = chunker.chunk(P2pMessage.Binary(payload))
        assertTrue(frames.size > 1)

        // Deliver only the first chunk; pending state is created.
        reassembler.accept(frames[0])
        assertEquals(1, reassembler.pendingCount())

        // Advance the clock past the timeout and evict.
        now += 6_000
        reassembler.evictStale()
        assertEquals(0, reassembler.pendingCount())

        // Now even if more chunks arrive, the reassembler has forgotten them
        // — delivering the final frame should re-create state, not complete.
        for (i in 1 until frames.size - 1) {
            assertNull(reassembler.accept(frames[i]))
        }
        // The last frame would normally complete; but state was lost, so we
        // get null until all the previously dropped chunks re-arrive (which
        // they won't in the real world — the message is gone).
        val last = reassembler.accept(frames.last())
        // With one chunk missing (chunk 0), the message is incomplete.
        assertNull(last)
    }

    @Test
    fun freshPartialMessageIsNotEvicted() {
        var now = 1_000L
        val reassembler = Reassembler(clock = { now }, reassemblyTimeoutMillis = 5_000)
        val frames = chunker.chunk(P2pMessage.Binary(ByteArray(20)))

        reassembler.accept(frames[0])
        now += 1_000  // well within timeout
        reassembler.evictStale()
        assertEquals(1, reassembler.pendingCount())
    }

    @Test
    fun mismatchedTotalChunksThrowsProtocolError() {
        val reassembler = Reassembler(clock = { 0L })
        val id = MessageId.random(Random(99))
        val a = Frame(PacketType.DATA, 0, id, 0, totalChunks = 3, payload = byteArrayOf(1))
        val b = Frame(PacketType.DATA, 0, id, 1, totalChunks = 5, payload = byteArrayOf(2))

        assertNull(reassembler.accept(a))
        assertFailsWith<P2pError.ProtocolError> { reassembler.accept(b) }
        // After the protocol error, the pending entry was discarded.
        assertEquals(0, reassembler.pendingCount())
    }
}
