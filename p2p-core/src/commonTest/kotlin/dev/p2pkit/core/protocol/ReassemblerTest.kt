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

    private fun dataFrame(
        id: MessageId,
        index: Int,
        total: Int,
        payload: ByteArray,
        isText: Boolean = false,
        needsAck: Boolean = false
    ): Frame {
        var flags = 0
        if (index == total - 1) flags = flags or FrameFlags.LAST_CHUNK
        if (isText) flags = flags or FrameFlags.IS_TEXT
        if (needsAck) flags = flags or FrameFlags.NEEDS_ACK
        return Frame(PacketType.DATA, flags.toByte(), id, index, total, payload)
    }

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
    fun semanticFlagsMustRemainStableAcrossChunks() {
        val reassembler = Reassembler(clock = { 0L })
        val id = MessageId.random(Random(321))
        assertNull(reassembler.accept(dataFrame(id, 0, 2, byteArrayOf(1), isText = true)))

        assertFailsWith<P2pError.ProtocolError> {
            reassembler.accept(dataFrame(id, 1, 2, byteArrayOf(2), isText = false))
        }

        assertEquals(0, reassembler.pendingCount())
    }

    @Test
    fun lastFlagMustMatchFinalChunk() {
        val reassembler = Reassembler(clock = { 0L })
        val id = MessageId.random(Random(322))
        val invalid = Frame(
            PacketType.DATA,
            FrameFlags.LAST_CHUNK.toByte(),
            id,
            0,
            2,
            byteArrayOf(1)
        )

        assertFailsWith<P2pError.ProtocolError> { reassembler.accept(invalid) }
        assertEquals(0, reassembler.pendingCount())
    }

    @Test
    fun malformedUtf8TextIsRejectedWithoutReplacement() {
        val reassembler = Reassembler(clock = { 0L })
        val invalidUtf8 = byteArrayOf(0xC3.toByte(), 0x28)

        assertFailsWith<P2pError.ProtocolError> {
            reassembler.accept(
                dataFrame(
                    id = MessageId.random(Random(323)),
                    index = 0,
                    total = 1,
                    payload = invalidUtf8,
                    isText = true
                )
            )
        }
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
        val a = dataFrame(id, 0, 3, byteArrayOf(1))
        val b = dataFrame(id, 1, 5, byteArrayOf(2))

        assertNull(reassembler.accept(a))
        assertFailsWith<P2pError.ProtocolError> { reassembler.accept(b) }
        // After the protocol error, the pending entry was discarded.
        assertEquals(0, reassembler.pendingCount())
    }

    @Test
    fun duplicateChunkIndexThrowsAndDoesNotReplaceStoredBytes() {
        val reassembler = Reassembler(clock = { 0L })
        val id = MessageId.random(Random(7))
        val threeMiB = 3 * 1024 * 1024
        val oneMiB = 1024 * 1024

        assertNull(
            reassembler.accept(
                dataFrame(id, 0, 2, ByteArray(threeMiB))
            )
        )

        // A re-sent index is rejected outright; previously it silently replaced
        // the stored bytes without being counted against MAX_PAYLOAD_BYTES.
        assertFailsWith<P2pError.ProtocolError> {
            reassembler.accept(
                dataFrame(id, 0, 2, ByteArray(4 * 1024 * 1024))
            )
        }

        // The original 3 MiB chunk is still the stored one and the duplicate
        // was not counted: a 1 MiB chunk 1 completes at exactly
        // MAX_PAYLOAD_BYTES (a counted or stored duplicate would either throw
        // here or change the delivered size).
        val message = reassembler.accept(
            dataFrame(id, 1, 2, ByteArray(oneMiB))
        )
        assertIs<P2pMessage.Binary>(message)
        assertEquals(threeMiB + oneMiB, message.bytes.size)
        assertEquals(0, reassembler.pendingCount())
    }

    @Test
    fun outOfRangeChunkIndexThrowsProtocolError() {
        val reassembler = Reassembler(clock = { 0L })
        val id = MessageId.random(Random(11))
        assertNull(
            reassembler.accept(dataFrame(id, 0, 3, byteArrayOf(1)))
        )

        assertFailsWith<P2pError.ProtocolError> {
            reassembler.accept(Frame(PacketType.DATA, 0, id, 3, totalChunks = 3, payload = byteArrayOf(2)))
        }
        assertFailsWith<P2pError.ProtocolError> {
            reassembler.accept(Frame(PacketType.DATA, 0, id, -1, totalChunks = 3, payload = byteArrayOf(3)))
        }
    }

    @Test
    fun singleFrameOverMaxPayloadBytesThrowsProtocolError() {
        val reassembler = Reassembler(clock = { 0L })
        val cap = ProtocolConstants.MAX_PAYLOAD_BYTES.toInt()

        // Exactly at the cap: delivered.
        val atCap = reassembler.accept(
            dataFrame(MessageId.random(Random(1)), 0, 1, ByteArray(cap))
        )
        assertIs<P2pMessage.Binary>(atCap)
        assertEquals(cap, atCap.bytes.size)

        // One byte over: the single-frame fast path must not bypass the
        // message cap (the codec accepts frames up to MAX_FRAME_PAYLOAD_BYTES).
        assertFailsWith<P2pError.ProtocolError> {
            reassembler.accept(
                dataFrame(MessageId.random(Random(2)), 0, 1, ByteArray(cap + 1))
            )
        }
        assertEquals(0, reassembler.pendingCount())
    }

    @Test
    fun aggregatePendingBytesAcrossMessagesIsCapped() {
        val reassembler = Reassembler(clock = { 0L })
        val rng = Random(2026)
        val perMessageCap = ProtocolConstants.MAX_PAYLOAD_BYTES.toInt()
        val chunk0 = ByteArray(perMessageCap - 16)  // just under the per-message cap

        // Four partials buffer 4 x (4 MiB - 16) = MAX_TOTAL_PENDING_BYTES - 64.
        val ids = List(4) { MessageId.random(rng) }
        for (id in ids) {
            assertNull(
                reassembler.accept(dataFrame(id, 0, 2, chunk0))
            )
        }
        assertEquals(4, reassembler.pendingCount())

        // A fifth partial's 65-byte chunk pushes the aggregate one byte over the cap.
        assertFailsWith<P2pError.ProtocolError> {
            reassembler.accept(
                dataFrame(MessageId.random(rng), 0, 2, ByteArray(65))
            )
        }
        // The offending message was discarded; the earlier partials are untouched.
        assertEquals(4, reassembler.pendingCount())

        // Completing a partial releases its budget: chunk 1 finishes ids[0] at
        // exactly MAX_PAYLOAD_BYTES...
        val done = reassembler.accept(
            dataFrame(ids[0], 1, 2, ByteArray(16))
        )
        assertIs<P2pMessage.Binary>(done)
        assertEquals(perMessageCap, done.bytes.size)
        assertEquals(3, reassembler.pendingCount())

        // ...so an equally large new partial fits under the aggregate cap again.
        assertNull(
            reassembler.accept(
                dataFrame(MessageId.random(rng), 0, 2, chunk0)
            )
        )
        assertEquals(4, reassembler.pendingCount())
    }

    @Test
    fun slowButSteadyPartialIsNotEvictedAndCompletes() {
        var now = 0L
        val reassembler = Reassembler(clock = { now }, reassemblyTimeoutMillis = 5_000)
        val payload = ByteArray(20) { it.toByte() }
        val frames = chunker.chunk(P2pMessage.Binary(payload))
        assertEquals(3, frames.size)

        // Each inter-chunk gap (4 s) is under the timeout, but the total
        // elapsed time (8 s) exceeds it. Inactivity-based eviction keeps the
        // message alive; first-seen-age eviction would have dropped it.
        assertNull(reassembler.accept(frames[0]))
        now += 4_000
        reassembler.evictStale()
        assertEquals(1, reassembler.pendingCount())

        assertNull(reassembler.accept(frames[1]))
        now += 4_000
        reassembler.evictStale()
        assertEquals(1, reassembler.pendingCount())

        val message = reassembler.accept(frames[2])
        assertIs<P2pMessage.Binary>(message)
        assertContentEquals(payload, message.bytes)
        assertEquals(0, reassembler.pendingCount())
    }

    @Test
    fun idlePartialIsEvictedByInactivityNotByAge() {
        var now = 0L
        val reassembler = Reassembler(clock = { now }, reassemblyTimeoutMillis = 5_000)
        val frames = chunker.chunk(P2pMessage.Binary(ByteArray(20)))
        assertEquals(3, frames.size)

        assertNull(reassembler.accept(frames[0]))
        now = 3_000
        assertNull(reassembler.accept(frames[1]))  // last activity at t=3 s

        // Age since the first chunk (7 s) exceeds the timeout, but the message
        // has only been idle for 4 s: it must survive.
        now = 7_000
        reassembler.evictStale()
        assertEquals(1, reassembler.pendingCount())

        // Idle past the timeout (5 s + 1 ms since t=3 s): evicted.
        now = 8_001
        reassembler.evictStale()
        assertEquals(0, reassembler.pendingCount())

        // The final chunk arrives too late; state was lost, so no message.
        assertNull(reassembler.accept(frames.last()))
    }
}
