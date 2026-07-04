package dev.p2pkit.core.transfer

import dev.p2pkit.core.P2pError

/**
 * Lifecycle of one file transfer.
 *
 * **Sender:** `Offered` → `Accepted` → `Sending(progress)` → `Completed`,
 * or short-circuited to `Rejected`, `Cancelled`, or `Failed` at any point.
 *
 * **Receiver:** `Offered` → `Accepted` → `Sending(progress)` → `Completed`.
 * `Rejected` is reached if the receiver calls [P2pFileOffer.reject] or the
 * offer goes unanswered past `offerTimeoutMillis` (reason `"timeout"`);
 * `Cancelled` if either side aborts the transfer in flight.
 *
 * **Unanswered-offer asymmetry (decision #11a, 2026-07-04):** when an offer
 * times out unanswered, the receiver's transfer terminalizes as
 * `Rejected("timeout")` while the sender's terminalizes as `Cancelled` with
 * the offer-timeout message (`"offer not accepted within <ms>ms"`, from the
 * sender's own local timer) — the two sides of the same event reach
 * different terminal states.
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

    /**
     * Receiver declined the offer — explicitly via [P2pFileOffer.reject], or
     * by the receive-side auto-reject when the offer goes unanswered past
     * `offerTimeoutMillis` (reason `"timeout"`). On an unanswered offer this
     * is the **receiver's** terminal state; the sender sees [Cancelled]
     * (decision #11a).
     */
    public data class Rejected(val reason: String?) : FileTransferState()

    /**
     * Either side cancelled mid-transfer. Also the **sender's** terminal
     * state for an unanswered offer: the sender's local timer fires with
     * reason `"offer not accepted within <ms>ms"` while the receiver's side
     * of the same event terminalizes as [Rejected] with reason `"timeout"`
     * (decision #11a, 2026-07-04).
     */
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
