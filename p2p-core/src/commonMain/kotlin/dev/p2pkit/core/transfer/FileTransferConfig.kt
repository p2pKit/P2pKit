package dev.p2pkit.core.transfer

/**
 * Configuration for the file-transfer subsystem.
 *
 * Configured via `fileTransfer { … }` on [dev.p2pkit.core.dsl.P2pKitBuilder].
 * All defaults are sensible for typical LAN file transfer; raise
 * [maxFileSizeBytes] to allow very large files, lower [offerTimeoutMillis] for
 * unattended setups, lower [chunkSizeBytes] to give other traffic (PING,
 * messages) more frequent slots on the write mutex.
 */
public data class FileTransferConfig(
    /** Hard cap on a single file's byte size. Defaults to 2 GiB. */
    val maxFileSizeBytes: Long = 2L * 1024 * 1024 * 1024,

    /**
     * Bytes per `FILE_DATA` frame. Matches the default message chunk size; each
     * chunk is one write through the session's send mutex.
     */
    val chunkSizeBytes: Int = 64 * 1024,

    /**
     * Time the receiver has to call [P2pFileOffer.accept] or [P2pFileOffer.reject]
     * before the offer auto-rejects with reason `"timeout"`. Default 30 s.
     */
    val offerTimeoutMillis: Long = 30_000
) {
    init {
        require(maxFileSizeBytes > 0) { "maxFileSizeBytes must be positive" }
        require(chunkSizeBytes in 1..(4 * 1024 * 1024)) {
            "chunkSizeBytes must be in 1..4MiB (got $chunkSizeBytes)"
        }
        require(offerTimeoutMillis > 0) { "offerTimeoutMillis must be positive" }
    }
}
