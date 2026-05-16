package dev.p2pkit.core.protocol

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * JSON body of a [PacketType.FILE_OFFER] frame.
 *
 * The frame's `messageId` carries the transferId; this payload only carries
 * the human-meaningful metadata (name, size, mime).
 *
 * If `sizeBytes` exceeds the receiver's
 * [dev.p2pkit.core.transfer.FileTransferConfig.maxFileSizeBytes], the receiver
 * auto-rejects the offer with reason `"sizeBytes exceeds maxFileSizeBytes"`.
 */
@Serializable
internal data class FileOfferPayload(
    val name: String,
    val sizeBytes: Long,
    val mimeType: String? = null
) {
    companion object {
        private val json = Json {
            ignoreUnknownKeys = true
            encodeDefaults = true
        }

        fun encode(payload: FileOfferPayload): ByteArray =
            json.encodeToString(serializer(), payload).encodeToByteArray()

        fun decode(bytes: ByteArray): FileOfferPayload =
            json.decodeFromString(serializer(), bytes.decodeToString())
    }
}
