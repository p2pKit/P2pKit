package dev.p2pkit.core

import dev.p2pkit.core.internal.immutableMapSnapshot

/**
 * A message exchanged over a [P2pSession].
 *
 * Carries text and binary payloads. Files are streamed separately via
 * [P2pSession.sendFile] and are intentionally not a [P2pMessage] subtype.
 * The maximum encoded payload size per [P2pSession.send] call is 4 MiB by
 * default; larger payloads throw [P2pError.PayloadTooLarge]. Internally
 * messages may be split into chunks for transport, but chunking is invisible
 * to the application.
 *
 * ### Metadata compatibility
 *
 * Authenticated secure sessions negotiate `app-message-envelope-v1` inside
 * their encrypted HELLO exchange. When negotiated, message type, id,
 * per-session sequence, sender, recipient, metadata, content length, and the
 * content SHA-256 are carried in the authenticated canonical envelope.
 * Metadata keys are serialized in raw UTF-8 byte order.
 *
 * Explicit legacy protocol v1 remains byte-compatible and metadata-free. A
 * secure peer that does not negotiate the envelope may exchange messages with
 * empty metadata, but [P2pSession.send] fails with
 * [P2pError.UnsupportedFeature] rather than dropping non-empty metadata.
 */
public sealed class P2pMessage {

    /**
     * UTF-8 text payload with optional string metadata.
     *
     * @property value the UTF-8 text payload.
     * @property metadata immutable metadata transmitted by negotiated secure
     *   sessions; explicit legacy protocol v1 does not transmit it.
     */
    public class Text(
        public val value: String,
        metadata: Map<String, String> = emptyMap()
    ) : P2pMessage() {
        /** Stable, unmodifiable snapshot of message metadata. */
        public val metadata: Map<String, String> = immutableMapSnapshot(metadata)

        public operator fun component1(): String = value
        public operator fun component2(): Map<String, String> = metadata

        public fun copy(
            value: String = this.value,
            metadata: Map<String, String> = this.metadata
        ): Text = Text(value, metadata)

        override fun equals(other: Any?): Boolean =
            this === other || other is Text && value == other.value && metadata == other.metadata

        override fun hashCode(): Int = 31 * value.hashCode() + metadata.hashCode()

        override fun toString(): String = "Text(value=$value, metadata=$metadata)"
    }

    /**
     * Arbitrary binary payload with optional string metadata.
     *
     * @property bytes the binary payload.
     * @property metadata immutable metadata transmitted by negotiated secure
     *   sessions; explicit legacy protocol v1 does not transmit it.
     */
    public class Binary(
        bytes: ByteArray,
        metadata: Map<String, String> = emptyMap()
    ) : P2pMessage() {

        private val content: ByteArray = bytes.copyOf()

        /** Defensive copy; mutating the returned array cannot alter this message. */
        public val bytes: ByteArray get() = content.copyOf()

        internal val payloadSizeBytes: Int get() = content.size

        private val metadataSnapshot: Map<String, String> = immutableMapSnapshot(metadata)

        /** Stable, unmodifiable metadata snapshot. */
        public val metadata: Map<String, String> get() = metadataSnapshot

        override fun equals(other: Any?): Boolean {
            if (this === other) return true
            if (other !is Binary) return false
            if (!content.contentEquals(other.content)) return false
            if (metadataSnapshot != other.metadataSnapshot) return false
            return true
        }

        override fun hashCode(): Int {
            var result = content.contentHashCode()
            result = 31 * result + metadataSnapshot.hashCode()
            return result
        }

        override fun toString(): String =
            "Binary(bytes=ByteArray(size=${content.size}), metadata=$metadataSnapshot)"
    }
}
