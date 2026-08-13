package dev.p2pkit.core.protocol

import dev.p2pkit.core.FileTransferPhase
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.internal.security.sha256
import dev.p2pkit.core.testfixtures.FakeConnectionPair
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.runTest
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs

class SecureFileTransferProtocolTest {
    @Test
    fun offerEncodingIsCanonicalAndBindsMetadataDigestAndTransferId() {
        val id = MessageId.random(Random(1))
        val digest = sha256(byteArrayOf(1, 2, 3))
        val offer = SecureFileOffer.create(id, "name.bin", 3L, "application/octet-stream", digest)
        val decoded = SecureFileOffer.decode(id, offer.encode())
        assertEquals(offer, decoded)
        assertEquals(offer.offerHash, decoded.offerHash)
        assertContentEquals(offer.encode(), decoded.encode())

        val renamed = SecureFileOffer.create(id, "other.bin", 3L, "application/octet-stream", digest)
        val redigested = SecureFileOffer.create(id, "name.bin", 3L, "application/octet-stream",
            sha256(byteArrayOf(1, 2, 4)))
        assertEquals(false, offer.offerHash == renamed.offerHash)
        assertEquals(false, offer.offerHash == redigested.offerHash)
        assertFailsWith<P2pError.ProtocolError> {
            SecureFileOffer.decode(MessageId.random(Random(2)), offer.encode())
        }
    }

    @Test
    fun acceptRequiresZeroOffsetAndMatchingHeaderId() {
        val id = MessageId.random(Random(3))
        val encoded = SecureFileAccept.encode(id)
        SecureFileAccept.decode(id, encoded)
        val nonZeroOffset = encoded.copyOf().also { it[it.lastIndex] = 1 }
        assertFailsWith<P2pError.ProtocolError> { SecureFileAccept.decode(id, nonZeroOffset) }
        assertFailsWith<P2pError.ProtocolError> {
            SecureFileAccept.decode(MessageId.random(Random(4)), encoded)
        }
    }

    @Test
    fun finishCommitAndFailureRoundTripWithoutTrailingBytes() {
        val id = MessageId.random(Random(5))
        val digest = sha256(ByteArray(100) { it.toByte() })
        val offerHash = sha256("offer".encodeToByteArray())
        val finish = SecureFileFinish(id, 100L, 2, digest, offerHash)
        assertEquals(finish, SecureFileFinish.decode(id, finish.encode()))
        val commit = SecureFileCommit(id, 100L, digest, offerHash)
        assertEquals(commit, SecureFileCommit.decode(id, commit.encode()))
        val result = SecureFileResult(
            id,
            FileResultCode.STORAGE_FAILURE,
            FileTransferPhase.DURABLE_COMMIT,
            "fsync failed"
        )
        assertEquals(result, SecureFileResult.decode(id, result.encode()))

        assertFailsWith<P2pError.ProtocolError> {
            SecureFileFinish.decode(id, finish.encode() + byteArrayOf(0))
        }
        assertFailsWith<P2pError.ProtocolError> {
            SecureFileCommit.decode(id, commit.encode().copyOf(commit.encode().size - 1))
        }
    }

    @Test
    fun malformedAuthenticatedFileResultReasonIsAlwaysAProtocolError() {
        val id = MessageId.random(Random(6))
        val encoded = SecureFileResult(
            id,
            FileResultCode.PROTOCOL_FAILURE,
            FileTransferPhase.RECEIVE,
            "x"
        ).encode()
        val invalidUtf8 = encoded.copyOf().also { it[it.lastIndex] = 0x80.toByte() }
        val forbiddenControl = encoded.copyOf().also { it[it.lastIndex] = 0x01 }

        assertFailsWith<P2pError.ProtocolError> {
            SecureFileResult.decode(id, invalidUtf8)
        }
        assertFailsWith<P2pError.ProtocolError> {
            SecureFileResult.decode(id, forbiddenControl)
        }
    }

    @Test
    fun protocolEventsPropagatesMalformedAuthenticatedFileResultAsProtocolError() = runTest {
        val pair = FakeConnectionPair()
        val protocol = DefaultP2pProtocol(
            clock = { 0L },
            version = ProtocolConstants.SECURE_VERSION
        )
        val state = ProtocolSessionState("receiver", secure = true).also {
            it.completeHello("sender", ProtocolFeatures.SECURE_V2)
        }
        val id = MessageId.random(Random(7))
        val malformed = SecureFileResult(
            id,
            FileResultCode.PROTOCOL_FAILURE,
            FileTransferPhase.RECEIVE,
            "x"
        ).encode().also { it[it.lastIndex] = 0x80.toByte() }
        val received = async { runCatching { protocol.events(pair.b, state).first() } }

        pair.a.write(
            FrameCodec.encode(
                Frame(
                    type = PacketType.FILE_RESULT,
                    flags = FrameFlags.LAST_CHUNK.toByte(),
                    messageId = id,
                    chunkIndex = 0,
                    totalChunks = 1,
                    payload = malformed,
                    version = ProtocolConstants.SECURE_VERSION
                )
            )
        )

        assertIs<P2pError.ProtocolError>(received.await().exceptionOrNull())
    }

    @Test
    fun securePeerWithoutFileFeatureRejectsLegacyTransferFrames() = runTest {
        val pair = FakeConnectionPair()
        val protocol = DefaultP2pProtocol(
            clock = { 0L },
            version = ProtocolConstants.SECURE_VERSION
        )
        val state = ProtocolSessionState("receiver", secure = true).also {
            it.completeHello("sender", listOf(ProtocolFeatures.APP_MESSAGE_ENVELOPE_V1))
        }
        val received = async { runCatching { protocol.events(pair.b, state).first() } }
        val id = MessageId.random(Random(8))
        val legacyOffer = Frame(
            type = PacketType.FILE_OFFER,
            flags = FrameFlags.LAST_CHUNK.toByte(),
            messageId = id,
            chunkIndex = 0,
            totalChunks = 1,
            payload = FileOfferPayload.encode(FileOfferPayload("legacy.bin", 1L)),
            version = ProtocolConstants.SECURE_VERSION
        )
        pair.a.write(FrameCodec.encode(legacyOffer))

        assertIs<P2pError.ProtocolError>(received.await().exceptionOrNull())
    }
}
