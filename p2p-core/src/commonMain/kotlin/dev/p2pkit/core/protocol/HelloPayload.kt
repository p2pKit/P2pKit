package dev.p2pkit.core.protocol

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json

/**
 * JSON body of a [PacketType.HELLO] frame.
 *
 * Both peers exchange this once at session start. If [appId] does not match
 * the local config, the receiver rejects the session with
 * [dev.p2pkit.core.P2pError.HandshakeRejected]. If [protocolVersion] differs
 * in its major component, the receiver rejects with
 * [dev.p2pkit.core.P2pError.VersionMismatch].
 */
@Serializable
internal data class HelloPayload(
    val appId: String,
    val peerId: String,
    val deviceName: String,
    val platform: String,
    val supportedTransports: List<String>,
    val protocolVersion: Int = ProtocolConstants.LEGACY_VERSION.toInt()
) {
    companion object {
        private val json = Json {
            ignoreUnknownKeys = true
            encodeDefaults = true
        }

        /** Max accepted length (chars) for an untrusted HELLO string field. */
        const val MAX_FIELD_LEN: Int = 512

        /** UTF-8 bound for one HELLO string field. */
        const val MAX_FIELD_UTF8_BYTES: Int = MAX_FIELD_LEN * 4

        /** Max number of advertised transport tags accepted from a peer. */
        const val MAX_TRANSPORTS: Int = 32

        fun encode(payload: HelloPayload): ByteArray {
            validate(payload)
            val encoded = json.encodeToString(serializer(), payload).encodeToByteArray()
            require(encoded.size <= ProtocolConstants.MAX_HELLO_PAYLOAD_BYTES) {
                "HELLO payload ${encoded.size} exceeds ${ProtocolConstants.MAX_HELLO_PAYLOAD_BYTES} bytes"
            }
            return encoded
        }

        fun decode(bytes: ByteArray): HelloPayload {
            require(bytes.size <= ProtocolConstants.MAX_HELLO_PAYLOAD_BYTES) {
                "HELLO payload ${bytes.size} exceeds ${ProtocolConstants.MAX_HELLO_PAYLOAD_BYTES} bytes"
            }
            val payload = json.decodeFromString(serializer(), bytes.decodeStrictUtf8("HELLO payload"))
            validate(payload)
            return payload
        }

        private fun validate(payload: HelloPayload) {
            validateWireText(payload.appId, "HELLO appId", MAX_FIELD_LEN, MAX_FIELD_UTF8_BYTES, true)
            validateWireText(payload.peerId, "HELLO peerId", MAX_FIELD_LEN, MAX_FIELD_UTF8_BYTES, true)
            validateWireText(
                payload.deviceName,
                "HELLO deviceName",
                MAX_FIELD_LEN,
                MAX_FIELD_UTF8_BYTES,
                true
            )
            validateWireText(payload.platform, "HELLO platform", MAX_FIELD_LEN, MAX_FIELD_UTF8_BYTES, true)
            require(payload.supportedTransports.size <= MAX_TRANSPORTS) {
                "HELLO advertised too many transports: ${payload.supportedTransports.size}"
            }
            payload.supportedTransports.forEachIndexed { index, transport ->
                validateWireText(
                    transport,
                    "HELLO supportedTransports[$index]",
                    MAX_FIELD_LEN,
                    MAX_FIELD_UTF8_BYTES,
                    true
                )
            }
            require(payload.protocolVersion in 1..255) {
                "HELLO protocolVersion must be in 1..255, got ${payload.protocolVersion}"
            }
        }
    }
}
