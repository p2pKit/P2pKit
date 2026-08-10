package dev.p2pkit.core.transfer

import dev.p2pkit.core.Peer
import kotlinx.coroutines.flow.StateFlow

/**
 * Handle to a single file transfer — either outgoing (returned by
 * [dev.p2pkit.core.P2pSession.sendFile]) or incoming (returned by
 * [P2pFileOffer.accept]).
 *
 * Observe [state] and [bytesTransferred] to render progress. Call [cancel] to
 * abort; both sides observe the resulting `Cancelled` state.
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

    /** 32-character hex transfer id, stable for the lifetime of the transfer. */
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

    /** Bytes transferred so far. Monotonically non-decreasing until terminal state. */
    public val bytesTransferred: StateFlow<Long>

    /**
     * Abort the transfer. Sends a `FILE_CANCEL` to the peer; both sides
     * transition to [FileTransferState.Cancelled].
     *
     * No-op if the transfer is already in a terminal state.
     */
    @Throws(Exception::class)
    public suspend fun cancel(reason: String? = null)
}
