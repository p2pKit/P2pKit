package dev.p2pkit.core.protocol

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
import kotlin.test.assertNull

class FileTransferProtocolTest {

    private val rng = Random(99)
    private fun id() = MessageId.random(rng)
    private fun protocol() = DefaultP2pProtocol(clock = { 0L })
    private fun newScope(): CoroutineScope = CoroutineScope(Dispatchers.Default + SupervisorJob())

    @Test
    fun offerRoundTrip() {
        runBlocking<Unit> {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val transferId = id()
                val offer = FileOfferPayload(name = "song.mp3", sizeBytes = 5_242_880L, mimeType = "audio/mpeg")
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.FileOffer }
                }
                protocol.sendFileOffer(pair.a, transferId, offer)
                val event = assertIs<ProtocolEvent.FileOffer>(deferred.await())
                assertEquals(transferId, event.transferId)
                assertEquals(offer, event.payload)
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun acceptCarriesTransferId() {
        runBlocking<Unit> {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val transferId = id()
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.FileAccept }
                }
                protocol.sendFileAccept(pair.a, transferId)
                val event = assertIs<ProtocolEvent.FileAccept>(deferred.await())
                assertEquals(transferId, event.transferId)
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun rejectWithReason() {
        runBlocking<Unit> {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val transferId = id()
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.FileReject }
                }
                protocol.sendFileReject(pair.a, transferId, "no thanks")
                val event = assertIs<ProtocolEvent.FileReject>(deferred.await())
                assertEquals(transferId, event.transferId)
                assertEquals("no thanks", event.reason)
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun rejectWithoutReason() {
        runBlocking<Unit> {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.FileReject }
                }
                protocol.sendFileReject(pair.a, id(), reason = null)
                val event = assertIs<ProtocolEvent.FileReject>(deferred.await())
                assertNull(event.reason)
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun fileDataFrameRoundTrips() {
        runBlocking<Unit> {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val transferId = id()
                val payload = ByteArray(4096) { (it and 0xFF).toByte() }
                val outgoing = Frame(
                    type = PacketType.FILE_DATA,
                    flags = FrameFlags.LAST_CHUNK.toByte(),
                    messageId = transferId,
                    chunkIndex = 0,
                    totalChunks = 1,
                    payload = payload
                )
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.FileData }
                }
                protocol.sendFileDataFrame(pair.a, outgoing)
                val event = assertIs<ProtocolEvent.FileData>(deferred.await())
                assertEquals(transferId, event.frame.messageId)
                assertContentEquals(payload, event.frame.payload)
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun doneCarriesTransferId() {
        runBlocking<Unit> {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val transferId = id()
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.FileDone }
                }
                protocol.sendFileDone(pair.a, transferId)
                val event = assertIs<ProtocolEvent.FileDone>(deferred.await())
                assertEquals(transferId, event.transferId)
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun cancelCarriesReason() {
        runBlocking<Unit> {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val transferId = id()
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.FileCancel }
                }
                protocol.sendFileCancel(pair.a, transferId, "user aborted")
                val event = assertIs<ProtocolEvent.FileCancel>(deferred.await())
                assertEquals(transferId, event.transferId)
                assertEquals("user aborted", event.reason)
            } finally {
                scope.cancel()
            }
        }
    }
}
