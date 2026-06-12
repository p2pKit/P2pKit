package dev.p2pkit.core.transfer

import dev.p2pkit.core.P2pError

/**
 * Lifecycle of one file transfer.
 *
 * **Sender:** `Offered` → `Accepted` → `Sending(progress)` → `Completed`,
 * or short-circuited to `Rejected`, `Cancelled`, or `Failed` at any point.
 *
 * **Receiver:** `Offered` → `Accepted` → `Sending(progress)` → `Completed`.
 * `Rejected` is reached if the receiver calls [P2pFileOffer.reject]; `Cancelled`
 * if either side aborts the transfer in flight.
 *
 * Progress in [Sending] is `bytesTransferred / sizeBytes` clamped to `0.0..1.0`.
 */
public sealed class FileTransferState {

    /** Offer has been sent / received but not yet acted on. */
    public data object Offered : FileTransferState()

    /** Receiver has accepted; sender is about to stream bytes. */
    public data object Accepted : FileTransferState()

    /** Bytes are flowing. [progress] is `0.0..1.0`. */
    public data class Sending(val progress: Float) : FileTransferState()

    /** All bytes delivered and the sink has been flushed. */
    public data object Completed : FileTransferState()

    /** Receiver rejected the offer. */
    public data class Rejected(val reason: String?) : FileTransferState()

    /** Either side cancelled mid-transfer, or the offer auto-rejected on timeout. */
    public data class Cancelled(val reason: String?) : FileTransferState()

    /** Transfer ended in an error (I/O, protocol, connection drop). */
    public data class Failed(val error: P2pError) : FileTransferState()
}

/**
 * True for states that end a transfer's lifecycle. Terminal states are
 * final — internal state holders refuse to overwrite them.
 */
internal fun FileTransferState.isTerminal(): Boolean = when (this) {
    is FileTransferState.Completed,
    is FileTransferState.Rejected,
    is FileTransferState.Cancelled,
    is FileTransferState.Failed -> true
    else -> false
}
