package dev.p2pkit.rpc.internal

import dev.p2pkit.core.PayloadBudget
import dev.p2pkit.rpc.RpcFailure
import dev.p2pkit.rpc.RpcFailureKind
import kotlinx.serialization.KSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.encoding.Encoder
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

class RpcCodecTest {
    @Test
    fun streamingEncoderBoundsBodiesAndReleasesReservationsOnRefusal() {
        val budget = PayloadBudget(2L * 1_048_576)
        assertFailsWith<RpcFailure> { RpcBodyCodec.encode(String.serializer(), "x".repeat(131_072), 32, budget) }
        assertEquals(0L, budget.retainedBytes.value)
        val body = RpcBodyCodec.encode(String.serializer(), "stock", 32, budget)
        assertEquals("stock", RpcBodyCodec.decode(String.serializer(), body, 32, budget))
        body.release()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun serializerErrorReleasesEveryOwnedEncodingReservationAndPreservesTheError() {
        val marker = AssertionError("Serializer fixture failure")
        val serializer = object : KSerializer<String> by String.serializer() {
            override fun serialize(encoder: Encoder, value: String) {
                encoder.encodeString(value)
                throw marker
            }
        }
        for (preReserved in listOf(false, true)) {
            val budget = PayloadBudget(1_048_576)
            val reservation = if (preReserved) budget.tryReserve(RpcBodyCodec.encodingAllowance(64)) else null
            if (preReserved) assertNotNull(reservation)
            assertSame(marker, assertFailsWith<AssertionError> {
                RpcBodyCodec.encode(serializer, "fixture", 64, budget, reservation)
            })
            assertEquals(0L, budget.retainedBytes.value)
            val body = RpcBodyCodec.encode(String.serializer(), "next", 64, budget)
            assertEquals("next", RpcBodyCodec.decode(String.serializer(), body, 64, budget))
            body.release()
            assertEquals(0L, budget.retainedBytes.value)
        }
    }

    @Test
    fun strictJsonRejectsDuplicateEscapedKeysDepthMalformedAndTrailingInput() {
        val rejected = listOf(
            "{\"a\":1,\"a\":2}", "{\"a\":1,\"\\u0061\":2}", "[".repeat(34) + "0" + "]".repeat(34),
            "[1,]", "{\"a\":01}", "true false", "\"bad\nstring\"", "{\"x\":NaN}",
        )
        for (input in rejected) assertFailsWith<RpcFailure>(input) { JsonPreflight(input).validate() }
        JsonPreflight("{\"a\":[true,false,null,-1.5e+2],\"b\":\"ok\"}").validate()
    }

    @Test
    fun binaryWireLengthAndCompatibilityValidationPrecedeBodyAllocation() {
        val budget = PayloadBudget(1024)
        val body = testBody("\"q\"", budget)
        val original = WireMessage(WireKind.Invoke, TEST_REQUEST, TEST_INCARNATION, "echo", 1, 1000, 1, body = body)
        val wire = RpcWire.encode(original)
        original.release()
        val decoded = RpcWire.decode(wire, budget)
        assertEquals("echo", decoded.name)
        assertContentEquals("\"q\"".encodeToByteArray(), assertNotNull(decoded.body).bytes)
        decoded.release()
        assertEquals(0L, budget.retainedBytes.value)
        for (invalid in listOf(wire.copyOf(55), wire.copyOf().also { it[52] = 0x7f },
            wire.copyOf().also { it[6] = 1 }, wire + byteArrayOf(0))) {
            assertFailsWith<RpcFailure> { RpcWire.decode(invalid, budget) }
            assertEquals(0L, budget.retainedBytes.value)
        }
        val unsupported = wire.copyOf().also { it[4] = 99 }
        assertEquals(RpcFailureKind.IncompatibleVersion,
            assertFailsWith<RpcFailure> { RpcWire.decode(unsupported, budget) }.kind)
    }

    @Test
    fun maximumBodyRoundTripIsSeparateFromCapacityQualification() {
        val budget = PayloadBudget(16L * 1_048_576)
        val value = "a".repeat(1_048_574) // Quotes make exactly 1 MiB encoded JSON, not peak-rate qualification.
        val encoded = RpcBodyCodec.encode(String.serializer(), value, 1_048_576, budget)
        assertEquals(1_048_576, encoded.size)
        val message = WireMessage(WireKind.Success, TEST_REQUEST, TEST_INCARNATION, "large", 1, body = encoded)
        val decoded = RpcWire.decode(RpcWire.encode(message), budget)
        assertEquals(value, RpcBodyCodec.decode(String.serializer(), assertNotNull(decoded.body), 1_048_576, budget))
        decoded.release()
        message.release()
        assertEquals(0L, budget.retainedBytes.value)
    }

    @Test
    fun cancelledQueueTicketsNeverTransmitAndSharedHandlesReleaseOnlyTheirOwnReference() {
        val budget = PayloadBudget(1024)
        val body = testBody("q", budget)
        val other = body.retain()
        val ticket = SendTicket(WireMessage(WireKind.Notify, TEST_REQUEST, TEST_INCARNATION,
            "notice", 1, body = body), 1000, 1, true)
        assertTrue(ticket.cancelQueued())
        assertFalse(ticket.begin())
        assertEquals(257L, budget.retainedBytes.value)
        other.release()
        other.release()
        assertEquals(0L, budget.retainedBytes.value)
    }
}
