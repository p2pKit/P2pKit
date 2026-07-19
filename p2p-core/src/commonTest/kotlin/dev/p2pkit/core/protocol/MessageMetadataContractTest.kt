package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertTrue

/**
 * AUDIT-2026-07 (API-1, P1-06; decision #3c): pins the protocol v1 metadata
 * contract — [P2pMessage.Text.metadata] / [P2pMessage.Binary.metadata] are
 * NOT transmitted. A message sent with non-empty metadata arrives with an
 * empty metadata map, and the DATA payload bytes contain only the value/bytes
 * (no serialized metadata).
 *
 * This pin is deliberate: the post-RC `metadata-wire` milestone
 * (`docs/STABILIZATION_AND_RELEASE.md` §C4) must consciously flip these
 * assertions to round-trip equality when metadata is wired onto the wire.
 */
class MessageMetadataContractTest {

    private val metadata = mapOf("k1" to "v1", "content-type" to "text/plain")

    @Test
    fun binarySnapshotsCallerBytesAndMetadata() {
        val source = byteArrayOf(1, 2, 3)
        val sourceMetadata = mutableMapOf("one" to "1", "two" to "2")
        val message = P2pMessage.Binary(source, sourceMetadata)
        val originalHash = message.hashCode()

        source[0] = 9
        sourceMetadata.clear()
        val exposedBytes = message.bytes
        exposedBytes[1] = 9
        @Suppress("UNCHECKED_CAST")
        (message.metadata as MutableMap<String, String>).clear()

        assertContentEquals(byteArrayOf(1, 2, 3), message.bytes)
        assertEquals(mapOf("one" to "1", "two" to "2"), message.metadata)
        assertEquals(originalHash, message.hashCode())
    }

    // --- Chunker/Reassembler round-trip (protocol codec layer) ---

    @Test
    fun textMetadataIsDroppedOnSingleChunkRoundTrip() {
        val chunker = Chunker(random = Random(1))
        val reassembler = Reassembler(clock = { 0L })

        val frames = chunker.chunk(P2pMessage.Text("hello", metadata))
        assertEquals(1, frames.size)
        // The DATA payload is exactly the UTF-8 value bytes — no envelope.
        assertContentEquals("hello".encodeToByteArray(), frames[0].payload)

        val received = reassembler.accept(frames[0])
        val text = assertIs<P2pMessage.Text>(received)
        assertEquals("hello", text.value)
        assertEquals(emptyMap(), text.metadata)
    }

    @Test
    fun binaryMetadataIsDroppedOnSingleChunkRoundTrip() {
        val chunker = Chunker(random = Random(2))
        val reassembler = Reassembler(clock = { 0L })
        val payload = ByteArray(32) { it.toByte() }

        val frames = chunker.chunk(P2pMessage.Binary(payload, metadata))
        assertEquals(1, frames.size)
        // The DATA payload is exactly the binary bytes — no envelope.
        assertContentEquals(payload, frames[0].payload)

        val received = reassembler.accept(frames[0])
        val binary = assertIs<P2pMessage.Binary>(received)
        assertContentEquals(payload, binary.bytes)
        assertEquals(emptyMap(), binary.metadata)
    }

    @Test
    fun textMetadataIsDroppedOnMultiChunkRoundTrip() {
        val chunker = Chunker(chunkSize = 8, random = Random(3))
        val reassembler = Reassembler(clock = { 0L })
        val value = "x".repeat(100)

        val frames = chunker.chunk(P2pMessage.Text(value, metadata))
        assertTrue(frames.size > 1)

        var received: P2pMessage? = null
        for (frame in frames) {
            received = reassembler.accept(frame) ?: received
        }
        val text = assertIs<P2pMessage.Text>(received)
        assertEquals(value, text.value)
        assertEquals(emptyMap(), text.metadata)
    }

    @Test
    fun binaryMetadataIsDroppedOnMultiChunkRoundTrip() {
        val chunker = Chunker(chunkSize = 8, random = Random(4))
        val reassembler = Reassembler(clock = { 0L })
        val payload = ByteArray(100) { it.toByte() }

        val frames = chunker.chunk(P2pMessage.Binary(payload, metadata))
        assertTrue(frames.size > 1)

        var received: P2pMessage? = null
        for (frame in frames) {
            received = reassembler.accept(frame) ?: received
        }
        val binary = assertIs<P2pMessage.Binary>(received)
        assertContentEquals(payload, binary.bytes)
        assertEquals(emptyMap(), binary.metadata)
    }

    // --- Loopback variant (full protocol send/receive over the fixture pair) ---

    @Test
    fun textMetadataIsDroppedOverProtocolLoopback() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = DefaultP2pProtocol(clock = { 0L })
            val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())
            try {
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.Message }
                }
                protocol.sendMessage(pair.a, P2pMessage.Text("hello", metadata))
                val event = assertIs<ProtocolEvent.Message>(deferred.await())
                val text = assertIs<P2pMessage.Text>(event.message)
                assertEquals("hello", text.value)
                assertEquals(emptyMap(), text.metadata)
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun binaryMetadataIsDroppedOverProtocolLoopback() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = DefaultP2pProtocol(clock = { 0L })
            val scope = CoroutineScope(Dispatchers.Default + SupervisorJob())
            try {
                val payload = ByteArray(2000) { (it and 0xFF).toByte() }
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.Message }
                }
                protocol.sendMessage(pair.a, P2pMessage.Binary(payload, metadata))
                val event = assertIs<ProtocolEvent.Message>(deferred.await())
                val binary = assertIs<P2pMessage.Binary>(event.message)
                assertContentEquals(payload, binary.bytes)
                assertEquals(emptyMap(), binary.metadata)
            } finally {
                scope.cancel()
            }
        }
    }
}
