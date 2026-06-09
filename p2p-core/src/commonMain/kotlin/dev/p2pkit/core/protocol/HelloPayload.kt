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
    val protocolVersion: Int = ProtocolConstants.VERSION.toInt()
) {
    companion object {
        private val json = Json {
            ignoreUnknownKeys = true
            encodeDefaults = true
        }

        /** Max accepted length (chars) for an untrusted HELLO string field. */
        const val MAX_FIELD_LEN: Int = 512

        /** Max number of advertised transport tags accepted from a peer. */
        const val MAX_TRANSPORTS: Int = 32

        fun encode(payload: HelloPayload): ByteArray =
            json.encodeToString(serializer(), payload).encodeToByteArray()

        fun decode(bytes: ByteArray): HelloPayload {
            val payload = json.decodeFromString(serializer(), bytes.decodeToString())
            // Validate untrusted peer-supplied fields before they flow into
            // PeerId / session id / the published Peer. A thrown error is
            // treated as a malformed HELLO frame and skipped by the caller.
            require(payload.appId.isNotBlank() && payload.appId.length <= MAX_FIELD_LEN) {
                "HELLO appId blank or too long"
            }
            require(payload.peerId.isNotBlank() && payload.peerId.length <= MAX_FIELD_LEN) {
                "HELLO peerId blank or too long"
            }
            require(payload.deviceName.length <= MAX_FIELD_LEN) {
                "HELLO deviceName too long: ${payload.deviceName.length} > $MAX_FIELD_LEN"
            }
            require(payload.supportedTransports.size <= MAX_TRANSPORTS) {
                "HELLO advertised too many transports: ${payload.supportedTransports.size}"
            }
            return payload
        }
    }
}
