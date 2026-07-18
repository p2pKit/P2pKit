package dev.p2pkit.core.transfer

import dev.p2pkit.core.Peer
import kotlinx.io.RawSink

/**
 * Inbound file offer from a peer. Emitted on
 * [dev.p2pkit.core.P2pSession.incomingFiles] after the sender calls
 * [dev.p2pkit.core.P2pSession.sendFile].
 *
 * The receiver must respond by calling either [accept] (which provides a
 * [RawSink] for the bytes) or [reject]. If neither is called within the
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
     * Accept the offer and stream incoming bytes into [sink]. The returned
     * [P2pFileTransfer] tracks progress; on [FileTransferState.Completed] the
     * sink has been flushed but not closed — the caller is responsible for
     * closing it.
     *
     * Throws [IllegalStateException] if the offer was already accepted, rejected,
     * or timed out.
     */
    @Throws(Exception::class)
    public suspend fun accept(sink: RawSink): P2pFileTransfer

    /**
     * Decline the offer. The sender observes [FileTransferState.Rejected].
     *
     * No-op if the offer was already accepted or rejected.
     */
    @Throws(Exception::class)
    public suspend fun reject(reason: String? = null)
}
