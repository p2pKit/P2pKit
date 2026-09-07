package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.testfixtures.WireGoldenBytes
import dev.p2pkit.core.testfixtures.WireGoldenInputs
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertIs

/** Fixed-byte decoding is deliberately separate from production encoding, not a round-trip oracle. */
class AppMessageEnvelopeGoldenTest {
    @Test
    fun textEncodingMatchesFrozenEnvelopesWithAndWithoutMetadata() {
        for (metadata in listOf(false, true)) {
            assertContentEquals(
                WireGoldenBytes.read(name("text", metadata)),
                encode(WireGoldenInputs.textMessage(metadata)),
            )
        }
    }

    @Test
    fun binaryEncodingMatchesFrozenEnvelopesWithAndWithoutMetadata() {
        for (metadata in listOf(false, true)) {
            assertContentEquals(
                WireGoldenBytes.read(name("binary", metadata)),
                encode(WireGoldenInputs.binaryMessage(metadata)),
            )
        }
    }

    @Test
    fun frozenTextEnvelopesDecodeWithoutCallingEncoder() {
        for (metadata in listOf(false, true)) {
            val decoded = assertIs<P2pMessage.Text>(decode(name("text", metadata)))
            assertEquals(WireGoldenInputs.TEXT, decoded.value)
            assertMetadata(metadata, decoded.metadata)
        }
    }

    @Test
    fun frozenBinaryEnvelopesDecodeWithoutCallingEncoder() {
        for (metadata in listOf(false, true)) {
            val decoded = assertIs<P2pMessage.Binary>(decode(name("binary", metadata)))
            assertContentEquals(WireGoldenInputs.binary(), decoded.bytes)
            assertMetadata(metadata, decoded.metadata)
        }
    }

    private fun encode(message: P2pMessage): ByteArray = AppMessageEnvelope.encode(
        message = message,
        messageId = messageId(),
        sequence = 0,
        senderPeerId = "sender-π",
        recipientPeerId = "recipient",
    )

    private fun decode(name: String): P2pMessage = AppMessageEnvelope.decode(
        payload = WireGoldenBytes.read(name),
        frameMessageId = messageId(),
        state = ProtocolSessionState("recipient", secure = true).apply {
            completeHello("sender-π", listOf("app-message-envelope-v1"))
        },
    )

    private fun messageId(): MessageId = MessageId(ByteArray(16) { it.toByte() })

    private fun name(type: String, metadata: Boolean): String =
        "envelope-$type${if (metadata) "-metadata" else ""}"

    private fun assertMetadata(present: Boolean, actual: Map<String, String>) {
        assertEquals(if (present) WireGoldenInputs.metadata() else emptyMap(), actual)
        assertEquals(if (present) listOf("a", "z", "é") else emptyList(), actual.keys.toList())
    }
}
