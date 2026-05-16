package dev.p2pkit.core.protocol

import kotlin.test.Test
import kotlin.test.assertEquals

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
}
