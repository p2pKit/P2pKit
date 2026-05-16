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

        fun encode(payload: HelloPayload): ByteArray =
            json.encodeToString(serializer(), payload).encodeToByteArray()

        fun decode(bytes: ByteArray): HelloPayload =
            json.decodeFromString(serializer(), bytes.decodeToString())
    }
}
