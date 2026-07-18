package dev.p2pkit.core.protocol

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertTrue

class HelloPayloadTest {

    @Test
    fun roundTripPreservesAllFields() {
        val original = HelloPayload(
            appId = "com.example.transfer",
            peerId = "abc-123",
            deviceName = "Abdo's Phone",
            platform = "ANDROID",
            supportedTransports = listOf("LAN"),
            protocolVersion = 1
        )
        val encoded = HelloPayload.encode(original)
        val decoded = HelloPayload.decode(encoded)
        assertEquals(original, decoded)
    }

    @Test
    fun unknownFieldsAreIgnoredOnDecode() {
        val json = """{
            "appId":"com.example",
            "peerId":"p1",
            "deviceName":"Dev",
            "platform":"JVM_DESKTOP",
            "supportedTransports":["LAN"],
            "protocolVersion":1,
            "futureFieldFromV2":"whatever"
        }""".trimIndent().encodeToByteArray()

        val decoded = HelloPayload.decode(json)
        assertEquals("com.example", decoded.appId)
        assertEquals("p1", decoded.peerId)
    }

    @Test
    fun encodedJsonIsUtf8() {
        val payload = HelloPayload(
            appId = "com.example",
            peerId = "p",
            deviceName = "هاتف",
            platform = "ANDROID",
            supportedTransports = listOf("LAN")
        )
        val encoded = HelloPayload.encode(payload)
        val decoded = HelloPayload.decode(encoded)
        assertEquals("هاتف", decoded.deviceName)
    }

    @Test
    fun emptySupportedTransportsListIsPreserved() {
        val payload = HelloPayload(
            appId = "x",
            peerId = "p",
            deviceName = "d",
            platform = "UNKNOWN",
            supportedTransports = emptyList()
        )
        val decoded = HelloPayload.decode(HelloPayload.encode(payload))
        assertEquals(emptyList(), decoded.supportedTransports)
    }

    // ---- decode input-validation guards for peer-supplied bytes ----
    // (2026-07 review P1-18, PRO-4, SEC-I2, A07 §3 r2)

    /** Builds a payload whose fields default to valid values; tests override one at a time. */
    private fun payload(
        appId: String = "com.example",
        peerId: String = "p1",
        deviceName: String = "Dev",
        platform: String = "JVM_DESKTOP",
        supportedTransports: List<String> = listOf("LAN")
    ) = HelloPayload(appId, peerId, deviceName, platform, supportedTransports)

    /**
     * A body that is not JSON at all must be rejected with the exception
     * family the caller ([DefaultP2pProtocol.decodeEvent]) treats as a
     * malformed HELLO (skip + warn) — never returned as a payload.
     */
    @Test
    fun malformedJsonBodyIsRejected() {
        assertFailsWith<IllegalArgumentException> {
            HelloPayload.decode("{definitely not json".encodeToByteArray())
        }
    }

    /** Structurally valid JSON missing a required field (peerId) is rejected. */
    @Test
    fun missingRequiredFieldIsRejected() {
        val json = """{
            "appId":"com.example",
            "deviceName":"Dev",
            "platform":"JVM_DESKTOP",
            "supportedTransports":["LAN"]
        }""".trimIndent().encodeToByteArray()
        assertFailsWith<IllegalArgumentException> { HelloPayload.decode(json) }
    }

    /** protocolVersion is the one optional field: omitting it defaults to the current version. */
    @Test
    fun missingProtocolVersionDefaultsToCurrentVersion() {
        val json = """{
            "appId":"com.example",
            "peerId":"p1",
            "deviceName":"Dev",
            "platform":"JVM_DESKTOP",
            "supportedTransports":["LAN"]
        }""".trimIndent().encodeToByteArray()
        val decoded = HelloPayload.decode(json)
        assertEquals(ProtocolConstants.VERSION.toInt(), decoded.protocolVersion)
    }

    @Test
    fun blankAppIdIsRejected() {
        val err = assertFailsWith<IllegalArgumentException> {
            HelloPayload.encode(payload(appId = "   "))
        }
        assertTrue(err.message!!.contains("appId"), "got: ${err.message}")
    }

    @Test
    fun blankPeerIdIsRejected() {
        val err = assertFailsWith<IllegalArgumentException> {
            HelloPayload.encode(payload(peerId = " "))
        }
        assertTrue(err.message!!.contains("peerId"), "got: ${err.message}")
    }

    /** Fields at exactly MAX_FIELD_LEN (512) chars pass; the guard is a bound, not a shorter heuristic. */
    @Test
    fun fieldsAtMaxLenAreAccepted() {
        val atLimit = "a".repeat(HelloPayload.MAX_FIELD_LEN)
        val decoded = HelloPayload.decode(
            HelloPayload.encode(
                payload(
                    appId = atLimit,
                    peerId = atLimit,
                    deviceName = atLimit,
                    platform = atLimit,
                    supportedTransports = listOf(atLimit)
                )
            )
        )
        assertEquals(atLimit, decoded.appId)
        assertEquals(atLimit, decoded.peerId)
        assertEquals(atLimit, decoded.deviceName)
        assertEquals(atLimit, decoded.platform)
        assertEquals(listOf(atLimit), decoded.supportedTransports)
    }

    @Test
    fun appIdOverMaxLenIsRejected() {
        assertFailsWith<IllegalArgumentException> {
            HelloPayload.encode(payload(appId = "a".repeat(HelloPayload.MAX_FIELD_LEN + 1)))
        }
    }

    @Test
    fun peerIdOverMaxLenIsRejected() {
        assertFailsWith<IllegalArgumentException> {
            HelloPayload.encode(payload(peerId = "a".repeat(HelloPayload.MAX_FIELD_LEN + 1)))
        }
    }

    @Test
    fun deviceNameOverMaxLenIsRejected() {
        val err = assertFailsWith<IllegalArgumentException> {
            HelloPayload.encode(payload(deviceName = "a".repeat(HelloPayload.MAX_FIELD_LEN + 1)))
        }
        assertTrue(err.message!!.contains("deviceName"), "got: ${err.message}")
    }

    /** Exactly MAX_TRANSPORTS (32) advertised transports pass; 33 are rejected. */
    @Test
    fun transportsAtMaxCountAreAcceptedAndOneOverIsRejected() {
        val atLimit = List(HelloPayload.MAX_TRANSPORTS) { "T$it" }
        assertEquals(
            atLimit,
            HelloPayload.decode(HelloPayload.encode(payload(supportedTransports = atLimit))).supportedTransports
        )

        val overLimit = List(HelloPayload.MAX_TRANSPORTS + 1) { "T$it" }
        val err = assertFailsWith<IllegalArgumentException> {
            HelloPayload.decode(HelloPayload.encode(payload(supportedTransports = overLimit)))
        }
        assertTrue(err.message!!.contains("transports"), "got: ${err.message}")
    }

    /**
     * AUDIT-2026-07 (SEC-1 rider, P1-18): `platform` is bounded at
     * MAX_FIELD_LEN like every other untrusted HELLO string field — one char
     * over is rejected, as is a very large value. (Until the M4 group this
     * field was unbounded below the frame-payload cap; the former divergence
     * pin is replaced by this guard test.)
     */
    @Test
    fun overLimitPlatformStringIsRejected() {
        val oneOver = "p".repeat(HelloPayload.MAX_FIELD_LEN + 1)
        val err = assertFailsWith<IllegalArgumentException> {
            HelloPayload.decode(HelloPayload.encode(payload(platform = oneOver)))
        }
        assertTrue(err.message!!.contains("platform"), "got: ${err.message}")

        assertFailsWith<IllegalArgumentException> {
            HelloPayload.decode(HelloPayload.encode(payload(platform = "p".repeat(100_000))))
        }
    }

    /**
     * AUDIT-2026-07 (SEC-1 rider, P1-18): each per-transport tag is bounded
     * at MAX_FIELD_LEN (previously only the transport COUNT was bounded) —
     * one char over is rejected, as is a very large value. Replaces the
     * former divergence pin.
     */
    @Test
    fun overLimitPerTransportStringIsRejected() {
        val oneOver = "t".repeat(HelloPayload.MAX_FIELD_LEN + 1)
        val err = assertFailsWith<IllegalArgumentException> {
            HelloPayload.decode(
                HelloPayload.encode(payload(supportedTransports = listOf("LAN", oneOver)))
            )
        }
        assertTrue(err.message!!.contains("transport", ignoreCase = true), "got: ${err.message}")

        assertFailsWith<IllegalArgumentException> {
            HelloPayload.decode(
                HelloPayload.encode(payload(supportedTransports = listOf("t".repeat(100_000))))
            )
        }
    }

    @Test
    fun malformedUtf8IsRejectedWithoutReplacement() {
        val invalid = byteArrayOf(0x7B, 0x22, 0xC3.toByte(), 0x28, 0x22, 0x7D)

        val failure = assertFailsWith<IllegalArgumentException> { HelloPayload.decode(invalid) }

        assertTrue(failure.message!!.contains("UTF-8"))
    }

    @Test
    fun controlCharactersAreRejectedOnEncodeAndDecode() {
        assertFailsWith<IllegalArgumentException> {
            HelloPayload.encode(payload(deviceName = "safe\u202Etxt"))
        }
        val inbound = """{
            "appId":"com.example",
            "peerId":"p1",
            "deviceName":"bad\u0000name",
            "platform":"JVM_DESKTOP",
            "supportedTransports":["LAN"],
            "protocolVersion":1
        }""".trimIndent().encodeToByteArray()

        assertFailsWith<IllegalArgumentException> { HelloPayload.decode(inbound) }
    }

    @Test
    fun invalidLocalUnicodeIsRejectedBeforeJsonEncoding() {
        assertFailsWith<IllegalArgumentException> {
            HelloPayload.encode(payload(deviceName = "bad\uD800value"))
        }
    }
}
