package dev.p2pkit.core.transfer

/**
 * Configuration for the file-transfer subsystem.
 *
 * Configured via `fileTransfer { … }` on [dev.p2pkit.core.dsl.P2pKitBuilder].
 * All defaults are sensible for typical LAN file transfer; raise
 * [maxFileSizeBytes] and [maxConcurrentIncomingBytes] together for large
 * batches, lower [offerTimeoutMillis] for unattended setups, lower
 * [chunkSizeBytes] to give other traffic (PING, messages) more frequent slots
 * on the write mutex.
 */
public data class FileTransferConfig(
    /** Hard positive cap on a single file's byte size. Defaults to 2 GiB. */
    val maxFileSizeBytes: Long = 2L * 1024 * 1024 * 1024,

    /**
     * Bytes per `FILE_DATA` frame. Must be in `1..4 MiB`. Matches the default
     * message chunk size; each chunk is one write through the session's send
     * mutex.
     */
    val chunkSizeBytes: Int = 64 * 1024,

    /**
     * Time the receiver has to call [P2pFileOffer.accept] or [P2pFileOffer.reject]
     * before the offer auto-rejects with reason `"timeout"`. It is also the
     * maximum idle interval for both sending and receiving after acceptance;
     * the overall accepted-transfer deadline in either direction is twenty
     * times this value. Secure-v2 receiver commit and sender FILE_COMMIT
     * acknowledgement each use the same bound. Must be positive. Default 30 s.
     */
    val offerTimeoutMillis: Long = 30_000,

    /**
     * Hard positive cap on the sum of peer-declared bytes in all active
     * incoming transfers. The receiver reserves this budget when it admits an
     * offer and releases it when that offer reaches a terminal state, before
     * an application can open a staging sink. Defaults to 8 GiB.
     *
     * Increase this together with [maxFileSizeBytes] only when the receiving
     * application has an appropriate storage policy for larger batches.
     */
    val maxConcurrentIncomingBytes: Long = DEFAULT_MAX_CONCURRENT_INCOMING_BYTES
) {
    /** Retains the published three-argument constructor for existing callers. */
    public constructor(
        maxFileSizeBytes: Long,
        chunkSizeBytes: Int,
        offerTimeoutMillis: Long
    ) : this(
        maxFileSizeBytes = maxFileSizeBytes,
        chunkSizeBytes = chunkSizeBytes,
        offerTimeoutMillis = offerTimeoutMillis,
        maxConcurrentIncomingBytes = DEFAULT_MAX_CONCURRENT_INCOMING_BYTES
    )

    /** Retains the published three-property copy overload for existing callers. */
    public fun copy(
        maxFileSizeBytes: Long = this.maxFileSizeBytes,
        chunkSizeBytes: Int = this.chunkSizeBytes,
        offerTimeoutMillis: Long = this.offerTimeoutMillis
    ): FileTransferConfig = FileTransferConfig(
        maxFileSizeBytes = maxFileSizeBytes,
        chunkSizeBytes = chunkSizeBytes,
        offerTimeoutMillis = offerTimeoutMillis,
        maxConcurrentIncomingBytes = maxConcurrentIncomingBytes
    )

    init {
        require(maxFileSizeBytes > 0) { "maxFileSizeBytes must be positive" }
        require(maxConcurrentIncomingBytes > 0) {
            "maxConcurrentIncomingBytes must be positive"
        }
        require(chunkSizeBytes in 1..(4 * 1024 * 1024)) {
            "chunkSizeBytes must be in 1..4MiB (got $chunkSizeBytes)"
        }
        require(offerTimeoutMillis > 0) { "offerTimeoutMillis must be positive" }
        val maximumChunkCount = 1L + (maxFileSizeBytes - 1L) / chunkSizeBytes.toLong()
        require(maximumChunkCount <= Int.MAX_VALUE.toLong()) {
            "maxFileSizeBytes/chunkSizeBytes requires $maximumChunkCount chunks; " +
                "the wire format supports at most ${Int.MAX_VALUE}"
        }
    }
}

private const val DEFAULT_MAX_CONCURRENT_INCOMING_BYTES: Long = 8L * 1024 * 1024 * 1024

/**
 * Accepted transfers must not retain a sink forever when a peer stays
 * connected but stops making progress. These deadlines derive from the
 * existing timeout setting to preserve the public data-class constructor ABI.
 */
internal val FileTransferConfig.acceptedIdleTimeoutMillis: Long
    get() = offerTimeoutMillis

internal val FileTransferConfig.acceptedOverallTimeoutMillis: Long
    get() = saturatingMultiply(offerTimeoutMillis, ACCEPTED_OVERALL_TIMEOUT_MULTIPLIER)

/** Deadline for receiver commit and sender acknowledgement; default remains 30 s. */
internal val FileTransferConfig.commitTimeoutMillis: Long
    get() = offerTimeoutMillis

/**
 * A conforming receiver owns the unanswered-offer deadline and replies with
 * FILE_REJECT. The sender watchdog starts after the offer is actually written
 * and includes a response grace, retaining a finite bound for an unresponsive
 * or non-conforming peer without racing the receiver's normal decision timer.
 */
internal val FileTransferConfig.outgoingOfferWatchdogMillis: Long
    get() = saturatingAdd(
        offerTimeoutMillis,
        maxOf(MIN_OFFER_RESPONSE_GRACE_MILLIS, offerTimeoutMillis / 4L)
    )

private fun saturatingMultiply(value: Long, multiplier: Long): Long =
    if (value > Long.MAX_VALUE / multiplier) Long.MAX_VALUE else value * multiplier

private fun saturatingAdd(left: Long, right: Long): Long =
    if (left > Long.MAX_VALUE - right) Long.MAX_VALUE else left + right

private const val ACCEPTED_OVERALL_TIMEOUT_MULTIPLIER: Long = 20L
private const val MIN_OFFER_RESPONSE_GRACE_MILLIS: Long = 1_000L
