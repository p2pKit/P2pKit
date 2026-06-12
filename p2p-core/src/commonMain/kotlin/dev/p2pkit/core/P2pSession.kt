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

    public val state: StateFlow<ConnectionState>

    public val incoming: SharedFlow<P2pMessage>

    /**
     * Send a single message to the peer.
     *
     * Throws [P2pError.PayloadTooLarge] for any message whose encoded payload
     * exceeds the configured maximum (default 4 MiB) — [P2pMessage.Text] is
     * measured in UTF-8 bytes. Throws [P2pError.ConnectionFailed] if the
     * connection has dropped.
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
     * @throws P2pError.PayloadTooLarge if [sizeBytes] exceeds the configured
     *   `maxFileSizeBytes` (default 2 GiB).
     * @throws P2pError.ConnectionFailed if the session is not in
     *   [ConnectionState.Connected].
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
