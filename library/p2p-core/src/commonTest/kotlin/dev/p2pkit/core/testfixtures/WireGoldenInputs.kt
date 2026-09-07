package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.protocol.HelloPayload
import dev.p2pkit.core.protocol.ProtocolFeatures
import kotlin.random.Random

/** Public synthetic inputs for the immutable baseline bytes; never installed identities. */
internal object WireGoldenInputs {
    const val APP_ID: String = "wire.golden.π"
    const val TEXT: String = "Golden π 🚀"

    val peerIds: List<String> = listOf(
        "p2id2-m2eljpfm6uuasrpqbylg565w6bjjkt3lvmigcg4yx34nuoa3alva",
        "p2id2-badaecm6um4qlfzjgy6ijy4li7ppuzp7eg4b2euhhx235cvkqxra",
    )
    val fingerprints: List<String> = listOf(
        "p2f1-osmwjm6wq6t555pm6nq3fmjw33r7sd23w4rpfke22fuq3vwticsa",
        "p2f1-gw2ld36gxrwbi4evpis7ppo3bvvlf7tu5a7wh43wbkq3tkgt6l2a",
    )

    fun metadata(): Map<String, String> = linkedMapOf("é" to "café", "z" to "", "a" to "first")

    fun binary(): ByteArray = byteArrayOf(0, 1, 0x7f, 0x80.toByte(), 0xff.toByte())

    fun textMessage(withMetadata: Boolean): P2pMessage.Text =
        P2pMessage.Text(TEXT, if (withMetadata) metadata() else emptyMap())

    fun binaryMessage(withMetadata: Boolean): P2pMessage.Binary =
        P2pMessage.Binary(binary(), if (withMetadata) metadata() else emptyMap())

    fun hello(endpoint: Int): HelloPayload = HelloPayload(
        appId = APP_ID,
        peerId = peerIds[endpoint],
        deviceName = "Golden ${if (endpoint == 0) "initiator" else "responder"}",
        platform = "UNKNOWN",
        supportedTransports = listOf("LAN"),
        protocolVersion = 2,
        features = ProtocolFeatures.SECURE_V2.sorted(),
    )

    /** Only MessageId's 16-byte requests are allowed; no implementation-dependent seeded RNG. */
    fun messageIds(endpoint: Int): Random = object : Random() {
        private var next = 1 + endpoint * 64

        override fun nextBits(bitCount: Int): Int = error("Unexpected random primitive in wire golden")

        override fun nextBytes(size: Int): ByteArray {
            require(size == 16)
            return ByteArray(size) { next++.toByte() }
        }
    }
}
