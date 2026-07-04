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

        /** Max accepted length (chars) for the peer-supplied file name. */
        const val MAX_NAME_LEN: Int = 4096

        /** Max accepted length (chars) for the peer-supplied MIME type. */
        const val MAX_MIME_LEN: Int = 255

        fun encode(payload: FileOfferPayload): ByteArray =
            json.encodeToString(serializer(), payload).encodeToByteArray()

        fun decode(bytes: ByteArray): FileOfferPayload {
            val payload = json.decodeFromString(serializer(), bytes.decodeToString())
            // Validate untrusted peer-supplied fields. The caller
            // (DefaultP2pProtocol.decodeEvent) treats a thrown error as a
            // malformed frame and skips it.
            require(payload.sizeBytes >= 0) {
                "FILE_OFFER sizeBytes must be non-negative, got ${payload.sizeBytes}"
            }
            require(payload.name.length <= MAX_NAME_LEN) {
                "FILE_OFFER name too long: ${payload.name.length} > $MAX_NAME_LEN"
            }
            require((payload.mimeType?.length ?: 0) <= MAX_MIME_LEN) {
                "FILE_OFFER mimeType too long: ${payload.mimeType?.length} > $MAX_MIME_LEN"
            }
            return payload
        }
    }
}
