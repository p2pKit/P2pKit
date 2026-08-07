package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError
import kotlinx.io.Buffer
import kotlinx.io.readByteArray
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class StreamingFileReceiverTest {

    private val rng = Random(11)
    private fun id() = MessageId.random(rng)

    private fun dataFrame(
        transferId: MessageId,
        index: Int,
        total: Int,
        payload: ByteArray,
        isLast: Boolean = index == total - 1
    ) = Frame(
        type = PacketType.FILE_DATA,
        flags = if (isLast) FrameFlags.LAST_CHUNK.toByte() else 0,
        messageId = transferId,
        chunkIndex = index,
        totalChunks = total,
        payload = payload
    )

    @Test
    fun acceptsInOrderChunksAndFlushesOnFinish() {
        val sink = Buffer()
        val transferId = id()
        val payload = ByteArray(256) { it.toByte() }
        val recv = StreamingFileReceiver(transferId, payload.size.toLong(), sink)

        // Two chunks of 128.
        recv.acceptDataChunk(dataFrame(transferId, 0, 2, payload.copyOfRange(0, 128)))
        recv.acceptDataChunk(dataFrame(transferId, 1, 2, payload.copyOfRange(128, 256)))
        recv.finish()

        assertTrue(recv.isComplete())
        assertEquals(payload.size.toLong(), recv.bytesReceived)
        assertContentEquals(payload, sink.readByteArray())
    }

    @Test
    fun outOfOrderChunkIsRejected() {
        val transferId = id()
        val recv = StreamingFileReceiver(transferId, 200L, Buffer())
        // Skip chunk 0 and feed chunk 1 directly.
        assertFailsWith<P2pError.ProtocolError> {
            recv.acceptDataChunk(dataFrame(transferId, 1, 2, ByteArray(100)))
        }
    }

    @Test
    fun overSizeChunkIsRejected() {
        val transferId = id()
        val recv = StreamingFileReceiver(transferId, 100L, Buffer())
        assertFailsWith<P2pError.ProtocolError> {
            recv.acceptDataChunk(dataFrame(transferId, 0, 1, ByteArray(101)))
        }
    }

    @Test
    fun finishBeforeCompleteFails() {
        val transferId = id()
        val recv = StreamingFileReceiver(transferId, 100L, Buffer())
        recv.acceptDataChunk(dataFrame(transferId, 0, 2, ByteArray(50)))
        assertFailsWith<P2pError.ProtocolError> {
            recv.finish()
        }
    }

    @Test
    fun wrongTransferIdFails() {
        val recv = StreamingFileReceiver(id(), 50L, Buffer())
        val foreignId = id()
        assertFailsWith<IllegalArgumentException> {
            recv.acceptDataChunk(dataFrame(foreignId, 0, 1, ByteArray(50)))
        }
    }

    @Test
    fun zeroByteFileCompletesWithJustFinish() {
        val transferId = id()
        val recv = StreamingFileReceiver(transferId, 0L, Buffer())
        recv.finish()
        assertTrue(recv.isComplete())
        assertEquals(0L, recv.bytesReceived)
    }

    @Test
    fun nonFileDataFrameRejected() {
        val recv = StreamingFileReceiver(id(), 10L, Buffer())
        val bogus = Frame(
            type = PacketType.DATA,
            flags = FrameFlags.LAST_CHUNK.toByte(),
            messageId = id(),
            chunkIndex = 0,
            totalChunks = 1,
            payload = ByteArray(10)
        )
        assertFailsWith<IllegalArgumentException> {
            recv.acceptDataChunk(bogus)
        }
    }

    @Test
    fun emptyChunkAndInvalidLastPlacementAreRejectedBeforeSinkWrite() {
        val transferId = id()
        val sink = Buffer()
        val recv = StreamingFileReceiver(transferId, 10L, sink)

        assertFailsWith<P2pError.ProtocolError> {
            recv.acceptDataChunk(dataFrame(transferId, 0, 1, ByteArray(0)))
        }
        assertFailsWith<P2pError.ProtocolError> {
            recv.acceptDataChunk(dataFrame(transferId, 0, 2, ByteArray(5), isLast = true))
        }

        assertEquals(0L, recv.bytesReceived)
        assertEquals(0L, sink.size)
    }

    @Test
    fun totalChunksCannotChangeMidTransfer() {
        val transferId = id()
        val recv = StreamingFileReceiver(transferId, 10L, Buffer())
        recv.acceptDataChunk(dataFrame(transferId, 0, 2, ByteArray(5)))

        assertFailsWith<P2pError.ProtocolError> {
            recv.acceptDataChunk(dataFrame(transferId, 1, 3, ByteArray(5), isLast = false))
        }
    }

    @Test
    fun reachingAdvertisedSizeRequiresLastAndRejectsFurtherData() {
        val transferId = id()
        val recv = StreamingFileReceiver(transferId, 5L, Buffer())
        recv.acceptDataChunk(dataFrame(transferId, 0, 1, ByteArray(5)))

        assertFailsWith<P2pError.ProtocolError> {
            recv.acceptDataChunk(dataFrame(transferId, 1, 2, byteArrayOf(1)))
        }
    }
}
