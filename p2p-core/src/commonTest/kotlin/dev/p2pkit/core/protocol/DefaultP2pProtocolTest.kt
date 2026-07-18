package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import dev.p2pkit.core.testfixtures.RecordingLogger
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertTrue

class DefaultP2pProtocolTest {

    private fun protocol() = DefaultP2pProtocol(clock = { 0L })

    private fun newScope(): CoroutineScope = CoroutineScope(Dispatchers.Default + SupervisorJob())

    @Test
    fun textRoundsTripViaLoopback() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.Message }
                }
                protocol.sendMessage(pair.a, P2pMessage.Text("hello"))
                val event = deferred.await()
                val msg = assertIs<ProtocolEvent.Message>(event)
                val text = assertIs<P2pMessage.Text>(msg.message)
                assertEquals("hello", text.value)
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun binaryRoundsTripViaLoopback() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val payload = ByteArray(2000) { (it and 0xFF).toByte() }
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.Message }
                }
                protocol.sendMessage(pair.a, P2pMessage.Binary(payload))
                val event = deferred.await()
                val msg = assertIs<ProtocolEvent.Message>(event)
                val bin = assertIs<P2pMessage.Binary>(msg.message)
                assertContentEquals(payload, bin.bytes)
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun largePayloadChunksAndReassembles() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = DefaultP2pProtocol(
                chunker = Chunker(chunkSize = 1024),
                clock = { 0L }
            )
            val scope = newScope()
            try {
                val payload = ByteArray(8 * 1024) { it.toByte() }
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.Message }
                }
                protocol.sendMessage(pair.a, P2pMessage.Binary(payload))
                val msg = (deferred.await() as ProtocolEvent.Message).message
                val bin = assertIs<P2pMessage.Binary>(msg)
                assertContentEquals(payload, bin.bytes)
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun pingAndPongAreDistinctEvents() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val deferred = scope.async {
                    protocol.events(pair.b).take(2).toList()
                }
                protocol.sendPing(pair.a)
                protocol.sendPong(pair.a)
                val events = deferred.await()
                assertEquals(ProtocolEvent.Ping, events[0])
                assertEquals(ProtocolEvent.Pong, events[1])
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun helloRoundTripsAsEvent() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val hello = HelloPayload(
                    appId = "com.example",
                    peerId = "p1",
                    deviceName = "D",
                    platform = "ANDROID",
                    supportedTransports = listOf("LAN")
                )
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.Hello }
                }
                protocol.sendHello(pair.a, hello)
                val event = deferred.await() as ProtocolEvent.Hello
                assertEquals(hello, event.payload)
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun closeEventIsEmitted() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.Close }
                }
                protocol.sendClose(pair.a)
                deferred.await()
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun peerErrorCarriesReason() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val deferred = scope.async {
                    protocol.events(pair.b).first { it is ProtocolEvent.PeerError }
                }
                protocol.sendError(pair.a, "appId mismatch")
                val event = deferred.await() as ProtocolEvent.PeerError
                assertEquals("appId mismatch", event.reason)
            } finally {
                scope.cancel()
            }
        }
    }

    // ---- Malformed-body skip-not-throw policy (2026-07 review P1-19, A07 §3 r3) ----
    // A HELLO/FILE_OFFER frame whose body fails to decode must be skipped with
    // a warn diagnostic — never thrown out of the events flow (which would
    // tear the session down on non-conforming peer input) — and the flow must
    // keep delivering every subsequent frame.

    private val rng = Random(11)

    /** A structurally valid frame carrying an arbitrary (possibly undecodable) body. */
    private fun rawControlFrame(type: PacketType, payload: ByteArray): Frame = Frame(
        type = type,
        flags = FrameFlags.LAST_CHUNK.toByte(),
        messageId = MessageId.random(rng),
        chunkIndex = 0,
        totalChunks = 1,
        payload = payload
    )

    @Test
    fun malformedHelloBodyIsSkippedWithWarnAndSubsequentFramesStillDelivered() {
        runBlocking {
            val pair = FakeConnectionPair()
            val logger = RecordingLogger()
            val protocol = DefaultP2pProtocol(clock = { 0L }, logger = logger)
            val scope = newScope()
            try {
                val deferred = scope.async { protocol.events(pair.b).take(2).toList() }
                // Non-JSON HELLO body, then a valid HELLO, then a PING.
                pair.a.write(FrameCodec.encode(rawControlFrame(PacketType.HELLO, "{not json".encodeToByteArray())))
                val valid = HelloPayload(
                    appId = "com.example",
                    peerId = "p1",
                    deviceName = "D",
                    platform = "ANDROID",
                    supportedTransports = listOf("LAN")
                )
                protocol.sendHello(pair.a, valid)
                protocol.sendPing(pair.a)

                val events = deferred.await()
                // The malformed frame produced no event; delivery continued in order.
                val hello = assertIs<ProtocolEvent.Hello>(events[0])
                assertEquals(valid, hello.payload)
                assertEquals(ProtocolEvent.Ping, events[1])
                assertTrue(
                    logger.warnings.any { it.contains("malformed HELLO") },
                    "Expected a malformed-HELLO warn diagnostic, got: ${logger.warnings}"
                )
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun helloBodyFailingValidationIsSkippedWithWarnNotThrown() {
        runBlocking {
            val pair = FakeConnectionPair()
            val logger = RecordingLogger()
            val protocol = DefaultP2pProtocol(clock = { 0L }, logger = logger)
            val scope = newScope()
            try {
                val deferred = scope.async { protocol.events(pair.b).take(1).toList() }
                // Valid JSON that fails the decode-side input-validation guards (blank peerId).
                val invalidBody = """{
                    "appId":"com.example",
                    "peerId":" ",
                    "deviceName":"D",
                    "platform":"ANDROID",
                    "supportedTransports":["LAN"],
                    "protocolVersion":1
                }""".trimIndent().encodeToByteArray()
                pair.a.write(FrameCodec.encode(rawControlFrame(PacketType.HELLO, invalidBody)))
                protocol.sendPing(pair.a)

                val events = deferred.await()
                assertEquals(ProtocolEvent.Ping, events[0], "The invalid HELLO must yield no event")
                assertTrue(
                    logger.warnings.any { it.contains("malformed HELLO") },
                    "Expected a malformed-HELLO warn diagnostic, got: ${logger.warnings}"
                )
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun malformedFileOfferBodyIsSkippedWithWarnAndSubsequentFramesStillDelivered() {
        runBlocking {
            val pair = FakeConnectionPair()
            val logger = RecordingLogger()
            val protocol = DefaultP2pProtocol(clock = { 0L }, logger = logger)
            val scope = newScope()
            try {
                val deferred = scope.async { protocol.events(pair.b).take(1).toList() }
                // Non-JSON FILE_OFFER body, then a valid offer.
                pair.a.write(FrameCodec.encode(rawControlFrame(PacketType.FILE_OFFER, "###".encodeToByteArray())))
                val transferId = MessageId.random(rng)
                val validOffer = FileOfferPayload(name = "report.pdf", sizeBytes = 1_234, mimeType = "application/pdf")
                protocol.sendFileOffer(pair.a, transferId, validOffer)

                val events = deferred.await()
                // First (and only) event is the VALID offer — the malformed one yielded nothing.
                val offer = assertIs<ProtocolEvent.FileOffer>(events[0])
                assertEquals(transferId, offer.transferId)
                assertEquals(validOffer, offer.payload)
                assertTrue(
                    logger.warnings.any { it.contains("malformed FILE_OFFER") },
                    "Expected a malformed-FILE_OFFER warn diagnostic, got: ${logger.warnings}"
                )
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun fileOfferBodyFailingValidationIsSkippedWithWarnAndSubsequentOfferDelivered() {
        runBlocking {
            val pair = FakeConnectionPair()
            val logger = RecordingLogger()
            val protocol = DefaultP2pProtocol(clock = { 0L }, logger = logger)
            val scope = newScope()
            try {
                val deferred = scope.async { protocol.events(pair.b).take(1).toList() }
                // Valid JSON that fails the decode guards (negative sizeBytes).
                val invalidBody = """{"name":"x","sizeBytes":-1,"mimeType":null}""".encodeToByteArray()
                pair.a.write(FrameCodec.encode(rawControlFrame(PacketType.FILE_OFFER, invalidBody)))
                val transferId = MessageId.random(rng)
                val validOffer = FileOfferPayload(name = "ok.bin", sizeBytes = 42)
                protocol.sendFileOffer(pair.a, transferId, validOffer)

                val events = deferred.await()
                val offer = assertIs<ProtocolEvent.FileOffer>(events[0])
                assertEquals(transferId, offer.transferId)
                assertEquals(validOffer, offer.payload)
                assertTrue(
                    logger.warnings.any { it.contains("malformed FILE_OFFER") },
                    "Expected a malformed-FILE_OFFER warn diagnostic, got: ${logger.warnings}"
                )
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun outboundReasonLimitsAreEnforcedExactly() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val atLimit = "a".repeat(ProtocolConstants.MAX_REASON_PAYLOAD_BYTES)

            protocol.sendError(pair.a, atLimit)
            assertFailsWith<IllegalArgumentException> {
                protocol.sendError(pair.a, "$atLimit!")
            }
            assertFailsWith<IllegalArgumentException> {
                protocol.sendError(pair.a, "")
            }
            assertFailsWith<IllegalArgumentException> {
                protocol.sendFileReject(pair.a, MessageId.random(rng), "   ")
            }
            assertFailsWith<IllegalArgumentException> {
                protocol.sendFileCancel(pair.a, MessageId.random(rng), "bad\nreason")
            }
        }
    }

    @Test
    fun malformedReasonUtf8IsAProtocolError() {
        runBlocking {
            val pair = FakeConnectionPair()
            val protocol = protocol()
            val scope = newScope()
            try {
                val result = scope.async { protocol.events(pair.b).first() }
                pair.a.write(
                    FrameCodec.encode(
                        rawControlFrame(
                            PacketType.ERROR,
                            byteArrayOf(0xC3.toByte(), 0x28)
                        )
                    )
                )

                assertFailsWith<P2pError.ProtocolError> { result.await() }
            } finally {
                scope.cancel()
            }
        }
    }

    @Test
    fun throwingFrameTraceCannotFailProtocolIo() {
        runBlocking {
            val previousEnabled = FrameTrace.enabled
            val previousSink = FrameTrace.sink
            try {
                FrameTrace.sink = { error("trace failed") }
                FrameTrace.enabled = true
                val pair = FakeConnectionPair()
                val protocol = protocol()
                val scope = newScope()
                try {
                    val event = scope.async { protocol.events(pair.b).first() }
                    protocol.sendPing(pair.a)

                    assertEquals(ProtocolEvent.Ping, event.await())
                    assertTrue(!FrameTrace.enabled)
                } finally {
                    scope.cancel()
                }
            } finally {
                FrameTrace.sink = previousSink
                FrameTrace.enabled = previousEnabled
            }
        }
    }

    @Test
    fun malformedBodyWarningsAreBoundedPerConnection() {
        runBlocking {
            val pair = FakeConnectionPair()
            val logger = RecordingLogger()
            val protocol = DefaultP2pProtocol(clock = { 0L }, logger = logger)
            val scope = newScope()
            try {
                val event = scope.async { protocol.events(pair.b).first() }
                repeat(100) {
                    pair.a.write(
                        FrameCodec.encode(
                            rawControlFrame(PacketType.HELLO, "not-json".encodeToByteArray())
                        )
                    )
                }
                protocol.sendPing(pair.a)

                assertEquals(ProtocolEvent.Ping, event.await())
                assertEquals(5, logger.warnings.size)
                assertTrue(logger.warnings.last().contains("suppressed"))
            } finally {
                scope.cancel()
            }
        }
    }
}
