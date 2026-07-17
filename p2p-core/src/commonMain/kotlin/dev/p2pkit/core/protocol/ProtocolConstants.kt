package dev.p2pkit.core.protocol

/** Wire constants shared by the encoder, decoder, chunker, and reassembler. */
internal object ProtocolConstants {

    // Magic = ASCII 'P' 'P' '2' 'K'
    const val MAGIC_0: Byte = 0x50
    const val MAGIC_1: Byte = 0x50
    const val MAGIC_2: Byte = 0x32
    const val MAGIC_3: Byte = 0x4B

    /** Explicit plaintext migration-profile major. */
    const val LEGACY_VERSION: Byte = 1

    /** Authenticated/encrypted profile major. */
    const val SECURE_VERSION: Byte = 2

    /**
     * Backward-compatible alias for code constructing legacy frames directly.
     * Production protocols select their version explicitly.
     */
    const val VERSION: Byte = LEGACY_VERSION

    /** Bytes in the fixed-size frame header (everything before the payload). */
    const val HEADER_SIZE: Int = 36

    /** Default chunk size; payloads larger than this are split across frames. */
    const val DEFAULT_CHUNK_SIZE: Int = 64 * 1024

    /** Maximum size of a single P2pMessage payload in v0.1. */
    const val MAX_PAYLOAD_BYTES: Long = 4L * 1024 * 1024

    /**
     * Hard upper bound on a single inbound frame's payload length, enforced on
     * the RECEIVE path ([FrameReader.feed], [FrameCodec.decode]) before any
     * buffering or allocation. A frame's payload is at most one DATA/FILE_DATA
     * chunk (capped at 4 MiB by [dev.p2pkit.core.transfer.FileTransferConfig])
     * plus protocol slack; 8 MiB gives comfortable headroom while denying a
     * peer the ability to declare a ~2 GiB payload and drive the process to OOM.
     * A frame exceeding this is a protocol violation and closes the session.
     */
    const val MAX_FRAME_PAYLOAD_BYTES: Int = 8 * 1024 * 1024

    /**
     * Largest [Frame.totalChunks] a peer may advertise for a multi-chunk DATA
     * message. Well-behaved senders chunk at [DEFAULT_CHUNK_SIZE] (64 KiB), so a
     * 4 MiB message needs 64 chunks; 1024 is generous headroom while bounding
     * the per-message chunk map. Exceeding it closes the session.
     */
    const val MAX_TOTAL_CHUNKS: Int = 1024

    /**
     * Cap on the number of concurrently-pending (incomplete) multi-chunk
     * messages a single [Reassembler] will track. Prevents a peer from opening
     * unbounded partial messages to exhaust memory. Exceeding it closes the
     * session.
     */
    const val MAX_PENDING_REASSEMBLIES: Int = 256

    /**
     * Aggregate cap on buffered chunk bytes across ALL concurrently-pending
     * partial messages in one [Reassembler]. The per-message cap alone is not
     * enough: [MAX_PAYLOAD_BYTES] x [MAX_PENDING_REASSEMBLIES] would let a
     * peer pin ~1 GiB (4 MiB x 256) of partials per session. 16 MiB is ample
     * for legitimate interleaved sends (a well-behaved sender writes one
     * message's chunks back-to-back). Exceeding it closes the session
     * (AUDIT-2026-06 fix).
     */
    const val MAX_TOTAL_PENDING_BYTES: Long = 16L * 1024 * 1024

    /** Default reassembly timeout. Stale partial messages are discarded. */
    const val DEFAULT_REASSEMBLY_TIMEOUT_MS: Long = 60_000
}
