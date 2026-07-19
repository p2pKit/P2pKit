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
 *
 * ### `metadata` is NOT transmitted in protocol v1 (AUDIT-2026-07 API-1, decision #3c)
 *
 * Protocol v1 DATA frames carry only the text/binary payload. The
 * [Text.metadata] / [Binary.metadata] maps are **local-only on send** — they
 * are never serialized onto the wire — and messages received from a peer
 * **always** carry an empty metadata map, regardless of what the sender
 * attached. This contract is pinned by `MessageMetadataContractTest`.
 * Transmitting metadata is scheduled as the post-RC `metadata-wire`
 * milestone (see `docs/STABILIZATION_AND_RELEASE.md` §C4).
 */
public sealed class P2pMessage {

    /**
     * UTF-8 text payload with optional string metadata.
     *
     * @property value the UTF-8 text payload — the only part transmitted.
     * @property metadata NOT transmitted in protocol v1: visible only within
     *   the sender's process; received [Text] messages always have an empty
     *   map. See [P2pMessage] docs and the post-RC `metadata-wire` milestone.
     */
    public data class Text(
        val value: String,
        val metadata: Map<String, String> = emptyMap()
    ) : P2pMessage()

    /**
     * Arbitrary binary payload with optional string metadata.
     *
     * @property bytes the binary payload — the only part transmitted.
     * @property metadata NOT transmitted in protocol v1: visible only within
     *   the sender's process; received [Binary] messages always have an empty
     *   map. See [P2pMessage] docs and the post-RC `metadata-wire` milestone.
     */
    public class Binary(
        bytes: ByteArray,
        metadata: Map<String, String> = emptyMap()
    ) : P2pMessage() {

        private val content: ByteArray = bytes.copyOf()

        /** Defensive copy; mutating the returned array cannot alter this message. */
        public val bytes: ByteArray get() = content.copyOf()

        internal val payloadSizeBytes: Int get() = content.size

        private val metadataSnapshot: Map<String, String> = metadata.toMap()
        public val metadata: Map<String, String> get() = metadataSnapshot.toMap()

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
