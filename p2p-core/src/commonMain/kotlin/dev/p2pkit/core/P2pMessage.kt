package dev.p2pkit.core

/**
 * A message exchanged over a [P2pSession].
 *
 * Carries text and binary payloads. Files are streamed separately via
 * [P2pSession.sendFile] and are intentionally not a [P2pMessage] subtype.
 * The maximum encoded payload size per [P2pSession.send] call is 4 MiB by
 * default; larger payloads throw [P2pError.PayloadTooLarge]. Internally
 * messages may be split into chunks for transport, but chunking is invisible
 * to the application.
 */
public sealed class P2pMessage {

    /** UTF-8 text payload with optional string metadata. */
    public data class Text(
        val value: String,
        val metadata: Map<String, String> = emptyMap()
    ) : P2pMessage()

    /** Arbitrary binary payload with optional string metadata. */
    public class Binary(
        public val bytes: ByteArray,
        public val metadata: Map<String, String> = emptyMap()
    ) : P2pMessage() {

        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (other !is Binary) return false
            if (!bytes.contentEquals(other.bytes)) return false
            if (metadata != other.metadata) return false
            return true
        }

        override fun hashCode(): Int {
            var result = bytes.contentHashCode()
            result = 31 * result + metadata.hashCode()
            return result
        }

        override fun toString(): String =
            "Binary(bytes=ByteArray(size=${bytes.size}), metadata=$metadata)"
    }
}
