package dev.p2pkit.core

import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
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
 * [incoming] is a hot [SharedFlow] with `replay = 0`,
 * `extraBufferCapacity = 64`, `onBufferOverflow = SUSPEND`. **Subscribe
 * immediately after `connect()` or when accepting an incoming session** —
 * messages emitted before any subscriber attaches are not buffered.
 *
 * ### Lifecycle
 *
 * `close()` transitions the session to `Closed` ([ConnectionState.Closing] is
 * declared but never emitted today). After [close], the underlying connection
 * is released and [incoming] completes.
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
     * Inbound file offers from the peer. Emitted when the peer calls
     * [sendFile]. Subscribe immediately after `connect()` or when accepting an
     * incoming session — offers emitted before any subscriber attaches are not
     * buffered.
     *
     * Each offer must be responded to with either [P2pFileOffer.accept] or
     * [P2pFileOffer.reject] within the configured `offerTimeoutMillis`
     * (default 30 s) or it is auto-rejected with reason `"timeout"`.
     */
    public val incomingFiles: SharedFlow<P2pFileOffer>

    /**
     * Offer a file to the peer. The peer receives a [P2pFileOffer] on its
     * [incomingFiles] flow and must call `accept(sink)` or `reject(reason)`
     * for the transfer to make progress.
     *
     * Bytes are pulled from [source] in chunks of the configured
     * [dev.p2pkit.core.transfer.FileTransferConfig.chunkSizeBytes]; the whole
     * file is never buffered in memory. The kit takes ownership of [source]
     * and closes it automatically once the returned transfer reaches a
     * terminal state — callers must not close it themselves.
     *
     * ### Ownership of [source] when this method throws (AUDIT-2026-07 API-2)
     *
     * Ownership transfers to the kit only once the transfer is registered
     * internally (immediately before the FILE_OFFER frame is written):
     *
     * - Refusals thrown **before** registration leave [source] open and still
     *   owned by the caller, who must close it: the session is not
     *   [ConnectionState.Connected], [sizeBytes] is negative, [sizeBytes]
     *   exceeds `maxFileSizeBytes` ([P2pError.PayloadTooLarge]), or the
     *   session's file-transfer machinery has already shut down.
     * - Throws **at or after** registration close [source] before rethrowing:
     *   a FILE_OFFER write failure, cancellation while the offer is being
     *   written, or losing a race with a concurrent session close/reconnect.
     *
     * The two shapes of a concurrent-close refusal (just before vs. just
     * after registration) surface as the same [P2pError.ConnectionFailed], so
     * a caller cannot always tell from the error alone whether the kit closed
     * [source]. After any throw from this method, treat [source] as unusable;
     * if its `close()` is idempotent (true for `kotlinx.io.Buffer` and the
     * file-backed sources the samples use), closing it defensively is safe.
     *
     * ### Error contract (decision #12a)
     *
     * Same as [send]: failures surface as typed [P2pError] and
     * [kotlinx.coroutines.CancellationException] propagates unchanged; any
     * unexpected exception is wrapped in [P2pError.ConnectionFailed] with the
     * original preserved as [cause][Throwable.cause]. In particular a
     * negative [sizeBytes] surfaces as [P2pError.ConnectionFailed] wrapping
     * the underlying `IllegalArgumentException`.
     *
     * @throws P2pError.PayloadTooLarge if [sizeBytes] exceeds the configured
     *   `maxFileSizeBytes` (default 2 GiB).
     * @throws P2pError.ConnectionFailed if the session is not in
     *   [ConnectionState.Connected], the offer could not be written, or any
     *   other unexpected failure occurred (original exception as `cause`).
     */
    @Throws(Exception::class)
    public suspend fun sendFile(
        name: String,
        sizeBytes: Long,
        mimeType: String?,
        source: RawSource
    ): P2pFileTransfer

    @Throws(Exception::class)
    public suspend fun close()
}
