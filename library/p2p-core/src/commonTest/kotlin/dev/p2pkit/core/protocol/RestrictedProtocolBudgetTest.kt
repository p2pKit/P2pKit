package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSessionProfile
import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.core.PeerAdmission
import kotlin.random.Random
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNotNull

class RestrictedProtocolBudgetTest {
    private val budget = PayloadBudget(4L * 1_048_576)
    private val profile = P2pSessionProfile({ PeerAdmission.Trusted }, budget, 128)

    private fun frame(bytes: Int, flags: Int = FrameFlags.LAST_CHUNK): Frame = Frame(
        PacketType.DATA, flags.toByte(), MessageId.random(Random(3)), 0, 1, ByteArray(bytes)
    )

    @Test
    fun restrictedHeaderRefusesLargeChunksAndTextBeforePayloadAllocation() {
        for (f in listOf(frame(65_537), frame(1, FrameFlags.LAST_CHUNK or FrameFlags.IS_TEXT))) {
            val reader = FrameReader(profile = profile)
            val header = FrameCodec.encode(f).copyOf(ProtocolConstants.HEADER_SIZE)
            assertFailsWith<P2pError.ProtocolError> { reader.feed(header) }
            assertEquals(256L, budget.retainedBytes.value)
            reader.close()
            assertEquals(0L, budget.retainedBytes.value)
        }
    }

    @Test
    fun prohibitedFileFramesAreRejectedBeforeReadingThePayload() {
        val reader = FrameReader(profile = profile)
        val header = FrameCodec.encode(frame(1)).copyOf(ProtocolConstants.HEADER_SIZE)
        header[5] = PacketType.FILE_OFFER.code
        assertFailsWith<P2pError.ProtocolError> { reader.feed(header) }
        reader.close()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun parsedFramesAndCompletedMessagesHaveDistinctReleaseOwners() {
        val reader = FrameReader(profile = profile)
        val parsed = reader.feed(FrameCodec.encode(frame(4096))).single()
        val reassembler = Reassembler(
            clock = { 0 }, payloadBudget = budget,
            sessionState = ProtocolSessionState("local", secure = true, restrictedApplicationBytes = 8192)
        )
        assertIs<P2pMessage.Binary>(reassembler.accept(parsed))
        val completed = assertNotNull(reassembler.takeCompletedLease())
        parsed.releasePayload()
        reassembler.close()
        reader.close()
        assertEquals(4096L + 512, budget.retainedBytes.value)
        completed.release()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun exhaustedBudgetAndPartialReassemblyTeardownReleaseAllOwnedBytes() {
        val small = PayloadBudget(256)
        val reader = FrameReader(profile = P2pSessionProfile({ PeerAdmission.Trusted }, small, 1))
        assertFailsWith<P2pError.ProtocolError> { reader.feed(FrameCodec.encode(frame(1024))) }
        reader.close()
        assertEquals(0L, small.retainedBytes.value)

        val reassembler = Reassembler(clock = { 0 }, payloadBudget = budget)
        reassembler.accept(Frame(PacketType.DATA, 0, MessageId.random(Random(1)), 0, 2, ByteArray(17)))
        reassembler.close()
        assertEquals(0L, budget.retainedBytes.value)
    }
}
