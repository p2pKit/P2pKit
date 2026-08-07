package dev.p2pkit.core.internal.security.noise

import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class SecureProtocolV2WireTest {
    @Test
    fun prefaceHasExactFrozenEncodingAndRoundTripsRoles() {
        val initiator = SecureV2Preface(NoiseRole.Initiator).encode()
        val responder = SecureV2Preface(NoiseRole.Responder).encode()

        assertContentEquals(
            byteArrayOf(0x50, 0x32, 0x4b, 0x53, 1, 2, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0),
            initiator,
        )
        assertEquals(NoiseRole.Initiator, SecureV2Preface.decode(initiator).role)
        assertEquals(NoiseRole.Responder, SecureV2Preface.decode(responder).role)
        assertFailsWith<NoiseProtocolException> {
            SecureV2Preface.decode(initiator, NoiseRole.Responder)
        }
    }

    @Test
    fun everyUnsupportedPrefaceFieldAndReservedByteFailsClosed() {
        for (index in 0 until SECURE_V2_PREFACE_SIZE_BYTES) {
            val invalid = SecureV2Preface(NoiseRole.Initiator).encode()
            invalid[index] = (invalid[index].toInt() xor 0x40).toByte()
            assertFailsWith<NoiseProtocolException>("byte $index") {
                SecureV2Preface.decode(invalid)
            }
        }
    }

    @Test
    fun prologueBindsDomainAppIdAndBothDirectionalPrefaces() {
        val initiator = SecureV2Preface(NoiseRole.Initiator).encode()
        val responder = SecureV2Preface(NoiseRole.Responder).encode()
        val prologue = SecureV2Prologue.encode("app.π", initiator, responder)
        val domain = "dev.p2pkit.secure-channel.v2\u0000".encodeToByteArray()
        val appId = "app.π".encodeToByteArray()

        assertContentEquals(domain, prologue.copyOfRange(0, domain.size))
        assertEquals(appId.size, readU16BigEndian(prologue[domain.size], prologue[domain.size + 1]))
        assertContentEquals(
            appId,
            prologue.copyOfRange(domain.size + 2, domain.size + 2 + appId.size),
        )
        assertContentEquals(
            initiator,
            prologue.copyOfRange(domain.size + 2 + appId.size, domain.size + 2 + appId.size + 16),
        )
        assertContentEquals(responder, prologue.copyOfRange(prologue.size - 16, prologue.size))
    }

    @Test
    fun appIdAndHandshakeFramesAreBoundedBeforeAllocation() {
        val initiator = SecureV2Preface(NoiseRole.Initiator).encode()
        val responder = SecureV2Preface(NoiseRole.Responder).encode()
        SecureV2Prologue.encode("a".repeat(SECURE_V2_MAX_APP_ID_UTF8_BYTES), initiator, responder)
        assertFailsWith<IllegalArgumentException> {
            SecureV2Prologue.encode(
                "a".repeat(SECURE_V2_MAX_APP_ID_UTF8_BYTES + 1),
                initiator,
                responder,
            )
        }

        val maximum = ByteArray(SECURE_V2_MAX_HANDSHAKE_MESSAGE_BYTES)
        assertContentEquals(maximum, SecureV2HandshakeFrame.decode(SecureV2HandshakeFrame.encode(maximum)))
        assertFailsWith<NoiseProtocolException> {
            SecureV2HandshakeFrame.encode(ByteArray(SECURE_V2_MAX_HANDSHAKE_MESSAGE_BYTES + 1))
        }
    }

    @Test
    fun productionEmptyHandshakeFramesRequireExactFlightLengths() {
        SecureV2HandshakeFlight.entries.forEach { flight ->
            val body = ByteArray(flight.bodySizeBytes)
            assertContentEquals(
                body,
                SecureV2EmptyHandshakeFrame.decode(
                    flight,
                    SecureV2EmptyHandshakeFrame.encode(flight, body),
                ),
            )
            assertFailsWith<NoiseProtocolException> {
                SecureV2EmptyHandshakeFrame.encode(flight, ByteArray(flight.bodySizeBytes + 1))
            }
        }
    }
}
