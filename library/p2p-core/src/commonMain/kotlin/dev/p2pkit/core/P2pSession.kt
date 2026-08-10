package dev.p2pkit.core

import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.core.transfer.PreparedFileSource
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.io.RawSource

/**
 * A single active connection to another peer.
 *
 * Created by [P2pKit.connect] for outgoing connections and emitted by
 * [P2pKit.incomingSessions] for inbound ones. Sessions are 1:1 — a device with
 * multiple peers has multiple sessions, tracked in [P2pKit.sessions].
 *
 * ### Send semantics
 *
 * [send] is safe to call from multiple coroutines concurrently. Writes are
 * serialized internally with a `Mutex`; frames will never interleave on the
 * underlying connection.
 *
 * ### Receive semantics
 *
 * [incoming] is a hot [SharedFlow] with `replay = 0`. Decoded application
 * messages wait in a separately bounded internal queue (at most 64 messages
 * and 8 MiB) while a subscriber is slow; exceeding that bound fails the
 * session instead of growing memory without limit. **Subscribe immediately
 * after `connect()` or when accepting an incoming session** — messages
 * delivered before any subscriber attaches are not retained.
 *
 * ### Lifecycle
 *
 * `close()` commits [ConnectionState.Closing] before its bounded wire/resource
 * cleanup, then transitions to `Closed`. After [close], the underlying
 * connection is released and terminal cleanup cancels queued application
 * delivery. [SharedFlow] has no completion signal, so collectors should
 * observe [state] or be cancelled with their owning scope. Concurrent close
 * callers join the same cleanup transaction.
 */
public interface P2pSession {
    /** Stable identifier of this session for the lifetime of the process. */
    public val id: String

    public val peer: Peer

    /**
     * Cryptographically verified identity, or a null fingerprint in explicit
     * legacy mode. The default preserves source compatibility for third-party
     * test/session implementations; SDK-created secure sessions always
     * override it with the authenticated identity.
     */
    public val peerIdentity: PeerIdentity get() = PeerIdentity(peer.id)

    public val state: StateFlow<ConnectionState>

    public val incoming: SharedFlow<P2pMessage>

    /**
     * Send a single message to the peer.
     *
     * ### Error contract (AUDIT-2026-07 API-2, decision #12a)
     *
     * All failures surface as typed [P2pError], identically on every platform:
     *
     * - [P2pError.PayloadTooLarge] — the encoded payload exceeds the
     *   configured maximum (default 4 MiB); [P2pMessage.Text] is measured in
     *   UTF-8 bytes.
     * - [P2pError.ConnectionFailed] — the session is not
     *   [ConnectionState.Connected], or the underlying write failed. When the
     *   failure wraps an unexpected transport/platform exception (a raw
     *   socket write error, the write-watchdog timeout, …), the original
     *   exception is preserved as the error's [cause][Throwable.cause].
     * - [kotlinx.coroutines.CancellationException] propagates unchanged; it
     *   is never wrapped.
     *
     * Raw platform exceptions (`IOException`, `IllegalStateException`, …) are
     * never thrown from this method.
     */
    @Throws(Exception::class)
    public suspend fun send(message: P2pMessage)

    /**
     * Authoritative retained snapshot of inbound offers awaiting a response.
     *
     * Offers are ordered by admission and are present before their response
     * timer starts. An offer is removed when acceptance commits, it is
     * rejected, expires, is remotely cancelled, or this session closes. At
     * most 64 incoming transfers (pending and accepted combined) are active;
     * an excess offer is rejected without admission. Consequently at most 64
     * offers can be pending. Snapshot lists are immutable and safe to retain
     * across Kotlin, Java, and Swift calls.
     *
     * The default empty state preserves source compatibility for third-party
     * session test doubles; SDK-created sessions always override it.
     */
    public val pendingFileOffers: StateFlow<List<P2pFileOffer>>
        get() = EMPTY_PENDING_FILE_OFFERS

    /**
     * Migration-only event stream of newly admitted offers. It has no replay
     * and uses a bounded best-effort buffer, so an absent or backpressured
     * collector can miss events. It is not authoritative; observe
     * [pendingFileOffers] instead.
     */
    @Deprecated("Observe pendingFileOffers")
    public val incomingFiles: SharedFlow<P2pFileOffer>

    /**
     * Offer a legacy, flush-only file stream to the peer. The peer receives a
     * [P2pFileOffer] in its retained [pendingFileOffers] state and must use the
     * deprecated raw-sink accept overload or reject the offer.
     *
     * Bytes are pulled from [source] in chunks of the configured
     * [dev.p2pkit.core.transfer.FileTransferConfig.chunkSizeBytes]; the whole
     * file is never buffered in memory. The kit takes ownership of [source]
     * and closes it automatically once the returned transfer reaches a
     * terminal state — callers must not close it themselves.
     *
     * ### Ownership of [source] when this method throws (AUDIT-2026-07 API-2)
     *
     * Ownership stays with the caller through local metadata validation:
     *
     * - Refusals thrown **before** registration leave [source] open and still
     *   owned by the caller, who must close it: the session is not
     *   [ConnectionState.Connected], [sizeBytes] is negative, [sizeBytes]
     *   exceeds `maxFileSizeBytes` ([P2pError.PayloadTooLarge]), or the name or
     *   MIME type is invalid.
     * - Once validation succeeds and the dispatcher begins its registration
     *   transaction, the kit treats [source] as transferred. A FILE_OFFER
     *   write failure, cancellation during that write, allocation failure, or
     *   concurrent close/reconnect then detaches it and starts independently
     *   bounded close before rethrowing. A non-cooperative `close()` can finish
     *   later, but the handle no longer retains it. Admission is capped at 64
     *   active outgoing transfers per session; an excess registration fails
     *   as `TRANSPORT` / `OFFER` / `RETRY_SAME_SESSION` and receives the same
     *   transferred-source cleanup.
     *
     * Concurrent-close refusals surface as
     * [P2pError.FileTransferFailed] with `REMOTE_DISCONNECTED`. A caller still
     * cannot always tell from the error alone whether registration committed;
     * after any throw, treat [source] as unusable. If its `close()` is
     * idempotent (true for `kotlinx.io.Buffer` and the file-backed sources the
     * samples use), closing it defensively is safe.
     *
     * ### Error contract (decision #12a)
     *
     * Transfer-owned failures surface as [P2pError.FileTransferFailed] with a
     * stable kind, phase, retry action, optional transfer id, and preserved
     * platform [cause][Throwable.cause]. Cancellation propagates unchanged;
     * rejection and explicit transfer cancellation are terminal transfer
     * states rather than exceptions. Authentication failures retain their
     * existing session-level [P2pError.AuthenticationFailed] type.
     *
     * @throws P2pError.PayloadTooLarge if [sizeBytes] exceeds the configured
     *   `maxFileSizeBytes` (default 2 GiB).
     * @throws P2pError.FileTransferFailed for invalid metadata, a disconnected
     *   session, offer timeout/write failure, or another transfer-owned error.
     */
    @Deprecated(
        "Legacy protocol-v1 transfer only; use sendFile(name, mimeType, PreparedFileSource)"
    )
    @Throws(Exception::class)
    public suspend fun sendFile(
        name: String,
        sizeBytes: Long,
        mimeType: String?,
        source: RawSource
    ): P2pFileTransfer

    /**
     * Offer a repeatable, SHA-256-prepared source over authenticated secure
     * protocol v2. Both peers must negotiate `file-commit-sha256-v1`.
     *
     * The SDK opens [source] only after the peer accepts, hashes the streamed
     * bytes again, and completes the returned handle only after the receiver
     * verifies the digest, flushes, durably commits its destination, and sends
     * the authenticated commit acknowledgement.
     *
     * [PreparedFileSource.open] is not called until the offer is accepted. A
     * peer that lacks the feature fails with `UNSUPPORTED_FEATURE`. No
     * plaintext or flush-only downgrade is attempted. Admission is capped at
     * 64 active outgoing transfers per session; excess registration fails as
     * `TRANSPORT` / `OFFER` / `RETRY_SAME_SESSION` without opening [source].
     */
    @Throws(Exception::class)
    public suspend fun sendFile(
        name: String,
        mimeType: String?,
        source: PreparedFileSource
    ): P2pFileTransfer = throw P2pError.FileTransferFailed(
        kind = FileTransferFailureKind.UNSUPPORTED_FEATURE,
        phase = FileTransferPhase.OFFER,
        retryability = Retryability.NOT_RETRYABLE,
        transferId = null,
        reason = "Prepared authenticated file transfer is not implemented by this session"
    )

    /**
     * Close the session and release all owned resources. Cleanup attempts are
     * bounded; the session still becomes terminal if a resource misbehaves.
     *
     * @throws P2pError.ConnectionFailed after all cleanup attempts when one
     *   or more resources failed or exceeded their close deadline.
     */
    @Throws(Exception::class)
    public suspend fun close()
}

private val EMPTY_PENDING_FILE_OFFERS: StateFlow<List<P2pFileOffer>> =
    MutableStateFlow<List<P2pFileOffer>>(emptyList()).asStateFlow()
