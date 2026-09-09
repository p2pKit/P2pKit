package dev.p2pkit.core.transfer

import dev.p2pkit.core.Peer
import kotlinx.coroutines.flow.StateFlow

/**
 * Handle to a single file transfer — either outgoing (returned by
 * [dev.p2pkit.core.P2pSession.sendFile]) or incoming (returned by
 * [P2pFileOffer.accept]).
 *
 * Observe [state] and [bytesTransferred] to render progress. Call [cancel] to
 * request local cancellation; remote notification is best-effort.
 *
 * The handle's identity is stable for the lifetime of the transfer. After
 * the transfer reaches a terminal state ([FileTransferState.Completed],
 * [FileTransferState.Rejected], [FileTransferState.Cancelled],
 * [FileTransferState.Failed]) resource ownership is detached from the handle,
 * bounded cleanup is attempted, and further [cancel] calls are no-ops. A
 * non-cooperative application source/destination callback can finish cleanup
 * after the state becomes terminal; it cannot keep the handle or session
 * lifecycle non-terminal indefinitely.
 */
public interface P2pFileTransfer {

    /**
     * 32-character hex transfer id, stable for the lifetime of the transfer.
     * Scoped to its owning [dev.p2pkit.core.P2pSession]; use `(session.id, id)`
     * as the key when retaining transfers from more than one session.
     */
    public val id: String

    /** The remote peer this transfer is to (sender) or from (receiver). */
    public val peer: Peer

    /** File name as advertised in the offer. */
    public val name: String

    /** Total bytes the sender promised to deliver. */
    public val sizeBytes: Long

    /** Optional MIME type from the offer. `null` if the sender did not provide one. */
    public val mimeType: String?

    /** Current lifecycle state. */
    public val state: StateFlow<FileTransferState>

    /**
     * Monotonically non-decreasing local payload-byte progress for this attempt.
     *
     * Outgoing counts are recorded after successful local transport writes:
     * submission is not proof that the peer received or acknowledged those bytes.
     * Incoming counts describe bytes accepted by the receive sink/buffer, not
     * necessarily flushed, digest-verified, or durably committed content. A failed
     * or cancelled attempt retains its last reported local progress.
     *
     * Reaching [sizeBytes] (100%) is not [FileTransferState.Completed]; consult
     * that state for the negotiated completion semantics. Only an authenticated
     * sender waits for the matching durable-commit acknowledgement; legacy
     * transfers do not provide that confirmation. This flow and [state] are
     * independent snapshots, so their notifications are not atomic.
     */
    public val bytesTransferred: StateFlow<Long>

    /**
     * Request local cancellation. If it wins the terminal transition, [state]
     * becomes [FileTransferState.Cancelled] and the SDK attempts to notify the
     * peer. Returning does not confirm remote receipt or processing: the peer
     * may continue or already have a different terminal outcome.
     *
     * Cancellation does not roll back a published receiver destination. For
     * example, the receiver may be [FileTransferState.Completed] while the
     * sender cancels before receiving its commit acknowledgement. A destination
     * commit already in progress can also publish after local cancellation;
     * see [FileTransferDestination] for late-publication and cleanup ownership.
     *
     * No-op if the transfer is already in a terminal state.
     */
    @Throws(Exception::class)
    public suspend fun cancel(reason: String? = null)
}
