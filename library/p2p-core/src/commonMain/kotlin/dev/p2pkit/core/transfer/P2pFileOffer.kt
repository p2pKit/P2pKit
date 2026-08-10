package dev.p2pkit.core.transfer

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.Peer
import kotlinx.io.RawSink

/**
 * Inbound file offer from a peer. Retained in
 * [dev.p2pkit.core.P2pSession.pendingFileOffers] after the sender calls
 * [dev.p2pkit.core.P2pSession.sendFile]. The deprecated `incomingFiles` flow
 * also emits newly admitted offers, but can miss offers before subscription
 * or while its bounded migration buffer is backpressured.
 *
 * The receiver must respond by calling either [accept] with a transactional
 * [FileTransferDestination], the deprecated legacy [RawSink] overload, or
 * [reject]. If neither is called within the
 * configured `offerTimeoutMillis` (default 30 s), the offer is auto-rejected
 * with reason `"timeout"`; both sides terminalize as
 * [FileTransferState.Rejected]. A later sender watchdog exists only for an
 * unresponsive/non-conforming receiver that sends no decision.
 */
public interface P2pFileOffer {

    /** 32-character hex transfer id, matches the eventual [P2pFileTransfer.id]. */
    public val id: String

    /** The peer who sent the offer. */
    public val peer: Peer

    /** Suggested file name. */
    public val name: String

    /** Total bytes the sender will deliver if accepted. */
    public val sizeBytes: Long

    /** Optional MIME type. */
    public val mimeType: String?

    /**
     * Accept a legacy protocol-v1 offer and stream incoming bytes into [sink]. The returned
     * [P2pFileTransfer] tracks progress; on [FileTransferState.Completed] the
     * sink has been flushed but not closed. The sink remains caller-owned on
     * every terminal outcome, including failure and cancellation; the caller
     * is responsible for closing it after observing the terminal state.
     *
     * Throws [IllegalStateException] if the offer was already accepted,
     * rejected, cancelled, or timed out. Once the FILE_ACCEPT write commits,
     * this offer is removed from the session's retained pending snapshot.
     */
    @Deprecated("Legacy flush-only transfer; use accept(FileTransferDestination)")
    @Throws(Exception::class)
    public suspend fun accept(sink: RawSink): P2pFileTransfer

    /**
     * Accept into a transactional destination. Available only when both peers
     * negotiated authenticated `file-commit-sha256-v1`; there is no
     * flush-only fallback. The sender completes only after [destination]
     * commits and the acknowledgement is written. The SDK owns the
     * destination after it successfully transitions this retained offer into
     * acceptance and invokes its terminal cleanup on every later failure.
     * If the call is refused before that transition (for example, another
     * response already won), ownership never transfers; callers should
     * defensively invoke the idempotent [FileTransferDestination.abort] when
     * handling any thrown acceptance error.
     */
    @Throws(Exception::class)
    public suspend fun accept(destination: FileTransferDestination): P2pFileTransfer =
        throw P2pError.FileTransferFailed(
            kind = dev.p2pkit.core.FileTransferFailureKind.UNSUPPORTED_FEATURE,
            phase = dev.p2pkit.core.FileTransferPhase.ACCEPT,
            retryability = dev.p2pkit.core.Retryability.NOT_RETRYABLE,
            transferId = id,
            reason = "Transactional authenticated file transfer is not implemented by this offer"
        )

    /**
     * Decline the offer. The sender observes [FileTransferState.Rejected].
     *
     * Throws [IllegalStateException] if another accept/reject/cancel/timeout
     * transition already won.
     */
    @Throws(Exception::class)
    public suspend fun reject(reason: String? = null)
}
