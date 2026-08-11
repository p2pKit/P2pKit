package dev.p2pkit.core.protocol

import kotlinx.serialization.ExperimentalSerializationApi
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
        @OptIn(ExperimentalSerializationApi::class)
        private val json = Json {
            ignoreUnknownKeys = true
            encodeDefaults = true
            // Decode failures can reach bounded warnings; never echo peer JSON.
            exceptionsWithDebugInfo = false
        }

        /** Max accepted length (chars) for the peer-supplied file name. */
        const val MAX_NAME_LEN: Int = 4096

        /** Maximum UTF-8 bytes for the peer-supplied file name. */
        const val MAX_NAME_UTF8_BYTES: Int = MAX_NAME_LEN * 4

        /** Max accepted length (chars) for the peer-supplied MIME type. */
        const val MAX_MIME_LEN: Int = 255

        /** Maximum UTF-8 bytes for the peer-supplied MIME type. */
        const val MAX_MIME_UTF8_BYTES: Int = MAX_MIME_LEN

        fun encode(payload: FileOfferPayload): ByteArray {
            validate(payload)
            val encoded = json.encodeToString(serializer(), payload).encodeToByteArray()
            require(encoded.size <= ProtocolConstants.MAX_FILE_OFFER_PAYLOAD_BYTES) {
                "FILE_OFFER payload ${encoded.size} exceeds " +
                    "${ProtocolConstants.MAX_FILE_OFFER_PAYLOAD_BYTES} bytes"
            }
            return encoded
        }

        fun decode(bytes: ByteArray): FileOfferPayload {
            require(bytes.size <= ProtocolConstants.MAX_FILE_OFFER_PAYLOAD_BYTES) {
                "FILE_OFFER payload ${bytes.size} exceeds " +
                    "${ProtocolConstants.MAX_FILE_OFFER_PAYLOAD_BYTES} bytes"
            }
            val jsonText = bytes.decodeStrictUtf8("FILE_OFFER payload")
            rejectDuplicateTopLevelJsonFields(jsonText, "FILE_OFFER payload")
            val payload = json.decodeFromString(serializer(), jsonText)
            validate(payload)
            return payload
        }

        internal fun validate(payload: FileOfferPayload) {
            require(payload.sizeBytes >= 0) {
                "FILE_OFFER sizeBytes must be non-negative, got ${payload.sizeBytes}"
            }
            validateWireText(
                payload.name,
                "FILE_OFFER name",
                MAX_NAME_LEN,
                MAX_NAME_UTF8_BYTES,
                requireNonBlank = true
            )
            require(payload.name != "." && payload.name != "..") {
                "FILE_OFFER name must not be a dot segment"
            }
            require('/' !in payload.name && '\\' !in payload.name) {
                "FILE_OFFER name must be a single path component"
            }
            payload.mimeType?.let {
                validateWireText(
                    it,
                    "FILE_OFFER mimeType",
                    MAX_MIME_LEN,
                    MAX_MIME_LEN,
                    requireNonBlank = true
                )
            }
        }
    }
}
