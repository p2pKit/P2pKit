package dev.p2pkit.core.protocol

import dev.p2pkit.core.transfer.FileTransferConfig
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.test.runTest
import kotlinx.io.Buffer
import kotlinx.io.write
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class StreamingFileSenderTest {

    private val rng = Random(7)
    private fun id() = MessageId.random(rng)

    private fun bufferOf(bytes: ByteArray): Buffer = Buffer().apply { write(bytes) }

    @Test
    fun emptyFileEmitsNoFrames() {
        runTest {
            val frames = streamFileData(
                transferId = id(),
                rawSource = bufferOf(ByteArray(0)),
                sizeBytes = 0L,
                chunkSizeBytes = 64
            ).toList()
            assertTrue(frames.isEmpty(), "Expected zero frames for empty file, got ${frames.size}")
        }
    }

    @Test
    fun chunkCountOverflowIsRejectedBeforeReadingSource() = runTest {
        assertFailsWith<IllegalArgumentException> {
            streamFileData(
                transferId = id(),
                rawSource = bufferOf(byteArrayOf(1)),
                sizeBytes = Int.MAX_VALUE.toLong() + 1L,
                chunkSizeBytes = 1
            ).toList()
        }
    }

    @Test
    fun configurationRejectsAChunkCountTheWireCannotRepresent() {
        assertFailsWith<IllegalArgumentException> {
            FileTransferConfig(
                maxFileSizeBytes = Int.MAX_VALUE.toLong() + 1L,
                chunkSizeBytes = 1
            )
        }
    }

    @Test
    fun singleChunkFileFitsInOneFrame() {
        runTest {
            val payload = ByteArray(123) { it.toByte() }
            val transferId = id()
            val frames = streamFileData(
                transferId = transferId,
                rawSource = bufferOf(payload),
                sizeBytes = payload.size.toLong(),
                chunkSizeBytes = 256
            ).toList()
            assertEquals(1, frames.size)
            val f = frames[0]
            assertEquals(PacketType.FILE_DATA, f.type)
            assertEquals(transferId, f.messageId)
            assertEquals(0, f.chunkIndex)
            assertEquals(1, f.totalChunks)
            assertTrue(f.isLastChunk)
            assertContentEquals(payload, f.payload)
        }
    }

    @Test
    fun exactMultipleOfChunkSizeSplitsCleanly() {
        runTest {
            val chunk = 64
            val payload = ByteArray(chunk * 4) { (it and 0xFF).toByte() }
            val frames = streamFileData(
                transferId = id(),
                rawSource = bufferOf(payload),
                sizeBytes = payload.size.toLong(),
                chunkSizeBytes = chunk
            ).toList()
            assertEquals(4, frames.size)
            frames.forEachIndexed { i, f ->
                assertEquals(i, f.chunkIndex)
                assertEquals(4, f.totalChunks)
                assertEquals(chunk, f.payload.size)
                assertEquals(i == 3, f.isLastChunk)
            }
            val recombined = ByteArray(payload.size).also {
                var off = 0
                for (f in frames) {
                    f.payload.copyInto(it, off)
                    off += f.payload.size
                }
            }
            assertContentEquals(payload, recombined)
        }
    }

    @Test
    fun nonMultipleOfChunkSizeSplitsLastShort() {
        runTest {
            val chunk = 64
            val payload = ByteArray(chunk * 2 + 5) { (it and 0xFF).toByte() }
            val frames = streamFileData(
                transferId = id(),
                rawSource = bufferOf(payload),
                sizeBytes = payload.size.toLong(),
                chunkSizeBytes = chunk
            ).toList()
            assertEquals(3, frames.size)
            assertEquals(chunk, frames[0].payload.size)
            assertEquals(chunk, frames[1].payload.size)
            assertEquals(5, frames[2].payload.size)
            assertTrue(frames[2].isLastChunk)
        }
    }

    @Test
    fun largeFileStreamsWithoutBufferingAll() {
        runTest {
            // 5 MiB at 64 KiB chunks → 80 frames.
            val size = 5L * 1024 * 1024
            val chunk = 64 * 1024
            val rand = Random(13)
            val payload = ByteArray(size.toInt()).also { rand.nextBytes(it) }
            val frames = streamFileData(
                transferId = id(),
                rawSource = bufferOf(payload),
                sizeBytes = size,
                chunkSizeBytes = chunk
            ).toList()
            assertEquals(80, frames.size)
            assertEquals(0, frames.first().chunkIndex)
            assertEquals(79, frames.last().chunkIndex)
            assertTrue(frames.last().isLastChunk)
            // Last chunk is the same size as the others (5 MiB is a multiple of 64 KiB).
            assertEquals(chunk, frames.last().payload.size)
        }
    }
}
