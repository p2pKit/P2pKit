package dev.p2pkit.core.protocol

/** Wire constants shared by the encoder, decoder, chunker, and reassembler. */
internal object ProtocolConstants {

    // Magic = ASCII 'P' 'P' '2' 'K'
    const val MAGIC_0: Byte = 0x50
    const val MAGIC_1: Byte = 0x50
    const val MAGIC_2: Byte = 0x32
    const val MAGIC_3: Byte = 0x4B

    /** Current protocol major version. */
    const val VERSION: Byte = 1

    /** Bytes in the fixed-size frame header (everything before the payload). */
    const val HEADER_SIZE: Int = 36

    /** Default chunk size; payloads larger than this are split across frames. */
    const val DEFAULT_CHUNK_SIZE: Int = 64 * 1024

    /** Maximum size of a single P2pMessage payload in v0.1. */
    const val MAX_PAYLOAD_BYTES: Long = 4L * 1024 * 1024

    /** Default reassembly timeout. Stale partial messages are discarded. */
    const val DEFAULT_REASSEMBLY_TIMEOUT_MS: Long = 60_000
}
