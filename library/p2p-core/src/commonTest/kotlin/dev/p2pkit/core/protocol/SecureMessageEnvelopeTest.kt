package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.internal.security.Sha256Hasher
import dev.p2pkit.core.internal.security.sha256
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import kotlinx.coroutines.async
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.test.runTest
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs

@OptIn(ExperimentalCoroutinesApi::class)
class SecureMessageEnvelopeTest {
    @Test
    fun sha256MatchesStandardVectors() {
        assertEquals(
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            sha256(ByteArray(0)).toString()
        )
        assertEquals(
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            sha256("abc".encodeToByteArray()).toString()
        )
        val multiBlock =
            "abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq".encodeToByteArray()
        assertEquals(
            "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
            sha256(multiBlock).toString()
        )
        val incremental = Sha256Hasher()
        incremental.update(multiBlock, 0, 7)
        incremental.update(multiBlock, 7, 19)
        incremental.update(multiBlock, 26, multiBlock.size - 26)
        assertEquals(
            "248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1",
            incremental.finish().toString()
        )
    }

    @Test
    fun metadataCanonicalizesByRawUtf8KeyBytes() {
        val id = MessageId(ByteArray(MessageId.SIZE) { it.toByte() })
        val first = AppMessageEnvelope.encode(
            P2pMessage.Text("hello", linkedMapOf("z" to "last", "a" to "first")),
            id,
            0,
            "sender",
            "recipient"
        )
        val second = AppMessageEnvelope.encode(
            P2pMessage.Text("hello", linkedMapOf("a" to "first", "z" to "last")),
            id,
            0,
            "sender",
            "recipient"
        )
        assertContentEquals(first, second)
    }

    @Test
    fun negotiatedEnvelopeRoundTripsTextMetadataOverSecureProtocol() = runTest {
        val pair = FakeConnectionPair()
        val protocol = DefaultP2pProtocol(
            clock = { testScheduler.currentTime },
            version = ProtocolConstants.SECURE_VERSION
        )
        val sender = secureState("alice", "bob")
        val receiver = secureState("bob", "alice")
        val received = async {
            protocol.events(pair.b, receiver).first { it is ProtocolEvent.Message }
        }
        protocol.sendMessage(
            pair.a,
            P2pMessage.Text("hello", mapOf("content-type" to "text/plain", "trace" to "42")),
            sender
        )
        val message = assertIs<P2pMessage.Text>(assertIs<ProtocolEvent.Message>(received.await()).message)
        assertEquals("hello", message.value)
        assertEquals(mapOf("content-type" to "text/plain", "trace" to "42"), message.metadata)
    }

    @Test
    fun readerCommitsHelloBeforeDecodingFollowingEnvelope() = runTest {
        val pair = FakeConnectionPair()
        val protocol = DefaultP2pProtocol(
            clock = { 0L },
            version = ProtocolConstants.SECURE_VERSION
        )
        val sender = secureState("alice", "bob")
        val receiver = ProtocolSessionState("bob", secure = true)
        val received = async { protocol.events(pair.b, receiver).take(2).toList() }
        protocol.sendHello(
            pair.a,
            HelloPayload(
                appId = "com.example",
                peerId = "alice",
                deviceName = "Alice",
                platform = "JVM",
                supportedTransports = listOf("LAN"),
                protocolVersion = ProtocolConstants.SECURE_VERSION.toInt(),
                features = ProtocolFeatures.SECURE_V2.sorted()
            )
        )
        protocol.sendMessage(pair.a, P2pMessage.Text("hello", mapOf("k" to "v")), sender)

        val events = received.await()
        assertIs<ProtocolEvent.Hello>(events[0])
        assertEquals("v", assertIs<P2pMessage.Text>(
            assertIs<ProtocolEvent.Message>(events[1]).message
        ).metadata["k"])
        assertEquals("alice", receiver.remotePeerId)
    }

    @Test
    fun securePeerWithoutFeatureRejectsNonEmptyMetadataWithoutWriting() = runTest {
        val pair = FakeConnectionPair()
        val protocol = DefaultP2pProtocol(clock = { 0L }, version = ProtocolConstants.SECURE_VERSION)
        val state = ProtocolSessionState("alice", secure = true).also {
            it.completeHello("bob", emptyList())
        }
        val error = assertFailsWith<P2pError.UnsupportedFeature> {
            protocol.sendMessage(pair.a, P2pMessage.Binary(byteArrayOf(1), mapOf("k" to "v")), state)
        }
        assertEquals(ProtocolFeatures.APP_MESSAGE_ENVELOPE_V1, error.feature)
    }

    @Test
    fun negotiatedReceiverRejectsRawDataDowngrade() = runTest {
        val pair = FakeConnectionPair()
        val protocol = DefaultP2pProtocol(
            clock = { 0L },
            version = ProtocolConstants.SECURE_VERSION
        )
        val received = async {
            runCatching { protocol.events(pair.b, secureState("bob", "alice")).first() }
        }
        val raw = Frame(
            type = PacketType.DATA,
            flags = (FrameFlags.IS_TEXT or FrameFlags.LAST_CHUNK).toByte(),
            messageId = MessageId.random(Random(12)),
            chunkIndex = 0,
            totalChunks = 1,
            payload = "downgrade".encodeToByteArray(),
            version = ProtocolConstants.SECURE_VERSION
        )
        pair.a.write(FrameCodec.encode(raw))

        assertIs<P2pError.ProtocolError>(received.await().exceptionOrNull())
    }

    @Test
    fun digestTamperIdentityMismatchAndSequenceReplayFailClosed() {
        val id = MessageId.random(Random(10))
        val payload = AppMessageEnvelope.encode(
            P2pMessage.Binary(byteArrayOf(1, 2, 3), mapOf("k" to "v")),
            id,
            0,
            "alice",
            "bob"
        )
        val tampered = payload.copyOf().also { it[it.lastIndex] = (it.last() + 1).toByte() }
        assertFailsWith<P2pError.ProtocolError> {
            AppMessageEnvelope.decode(tampered, id, secureState("bob", "alice"))
        }
        assertFailsWith<P2pError.AuthenticatedIdentityMismatch> {
            AppMessageEnvelope.decode(payload, id, secureState("mallory", "alice"))
        }
        val replayState = secureState("bob", "alice")
        assertIs<P2pMessage.Binary>(AppMessageEnvelope.decode(payload, id, replayState))
        assertFailsWith<P2pError.ProtocolError> {
            AppMessageEnvelope.decode(payload, id, replayState)
        }
        val duplicateIdWithNextSequence = AppMessageEnvelope.encode(
            P2pMessage.Binary(byteArrayOf(4, 5, 6)),
            id,
            1,
            "alice",
            "bob"
        )
        assertFailsWith<P2pError.ProtocolError> {
            AppMessageEnvelope.decode(duplicateIdWithNextSequence, id, replayState)
        }
        assertFailsWith<P2pError.ProtocolError> {
            AppMessageEnvelope.decode(payload, MessageId.random(Random(11)), secureState("bob", "alice"))
        }
    }

    @Test
    fun protocolStateSnapshotsLocalCapabilities() {
        val features = mutableSetOf(ProtocolFeatures.APP_MESSAGE_ENVELOPE_V1)
        val state = ProtocolSessionState("alice", secure = true, localFeatures = features)
        features.clear()
        state.completeHello("bob", listOf(ProtocolFeatures.APP_MESSAGE_ENVELOPE_V1))

        assertEquals(setOf(ProtocolFeatures.APP_MESSAGE_ENVELOPE_V1), state.localFeatures)
        assertEquals(setOf(ProtocolFeatures.APP_MESSAGE_ENVELOPE_V1), state.negotiatedFeatures)
    }

    private fun secureState(local: String, remote: String): ProtocolSessionState =
        ProtocolSessionState(local, secure = true).also {
            it.completeHello(remote, ProtocolFeatures.SECURE_V2)
        }
}
