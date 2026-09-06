package dev.p2pkit.core.transfer

import dev.p2pkit.core.P2pError

/**
 * Local lifecycle of one file transfer. The two peers can reach different
 * terminal states when a notification is lost or races another outcome.
 *
 * **Sender:** `Offered` → `Accepted` → `Sending(progress)` → `Completed`,
 * or short-circuited to `Rejected`, `Cancelled`, or `Failed` at any point.
 *
 * **Receiver:** `Offered` → `Accepted` → `Sending(progress)` → `Completed`.
 * `Rejected` is reached if the receiver calls [P2pFileOffer.reject] or the
 * offer goes unanswered past `offerTimeoutMillis` (reason `"timeout"`);
 * `Cancelled` if a local or received cancellation wins the terminal transition.
 *
 * A conforming receiver is the unanswered-offer timeout authority and becomes
 * `Rejected("timeout")`. The sender observes the same rejection only if its
 * notification arrives before another terminal outcome. The sender's later
 * safety watchdog also covers lost notifications from conforming peers; that
 * local-only path is [Failed] with a typed `TIMEOUT` failure in the `OFFER` phase.
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

    /**
     * All bytes completed under the negotiated protocol. For legacy receive,
     * the sink was flushed. For secure-v2 receive, the destination was
     * digest-verified and durably committed before the SDK attempted
     * `FILE_COMMIT`; an acknowledgement write failure does not undo that
     * durable local result. A secure-v2 sender reaches this state only after
     * receiving the matching authenticated commit acknowledgement.
     */
    public data object Completed : FileTransferState()

    /**
     * Receiver declined the offer — explicitly via [P2pFileOffer.reject], or
     * by the receive-side auto-reject when the offer goes unanswered past
     * `offerTimeoutMillis` (reason `"timeout"`). The sender observes the same
     * rejection only after receiving the notification while still nonterminal.
     */
    public data class Rejected(val reason: String?) : FileTransferState()

    /**
     * Local cancellation won, or a peer cancellation was received and applied.
     * This does not confirm that the other peer is also cancelled or that no
     * receiver output exists; see [P2pFileTransfer.cancel].
     */
    public data class Cancelled(val reason: String?) : FileTransferState()

    /**
     * Transfer ended in an error. File-transfer-owned failures use
     * [P2pError.FileTransferFailed]; session authentication failures retain
     * their existing session-level [P2pError] type.
     */
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
