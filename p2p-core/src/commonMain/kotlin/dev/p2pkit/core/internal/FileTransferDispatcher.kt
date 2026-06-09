package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.protocol.FileOfferPayload
import dev.p2pkit.core.protocol.Frame
import dev.p2pkit.core.protocol.MessageId
import dev.p2pkit.core.protocol.P2pProtocol
import dev.p2pkit.core.protocol.StreamingFileReceiver
import dev.p2pkit.core.protocol.streamFileData
import dev.p2pkit.core.transfer.FileTransferConfig
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlin.concurrent.Volatile
import kotlin.random.Random
import kotlinx.io.RawSink
import kotlinx.io.RawSource

/**
 * Per-session orchestrator for file transfers. One instance per
 * [P2pSessionImpl]; receives demultiplexed `ProtocolEvent.File*` events from
 * the session's inbound reader and exposes [incomingFiles] + [sendFile] to
 * the public [dev.p2pkit.core.P2pSession] interface.
 *
 * Outgoing flow:
 *   `sendFile()` → FILE_OFFER → await accept/reject (with timeout)
 *   → on accept: stream FILE_DATA frames pulled from the caller-provided
 *     [RawSource] in `config.chunkSizeBytes` blocks → FILE_DONE → Completed.
 *   → on reject / timeout / cancel: send FILE_CANCEL (if appropriate),
 *     transition to Rejected / Cancelled.
 *
 * Incoming flow:
 *   FILE_OFFER arrives → validate size against [FileTransferConfig.maxFileSizeBytes];
 *   either auto-reject "too large" or emit an [P2pFileOffer] to [incomingFiles]
 *   and start the accept-or-reject timer. On `accept(sink)` open a
 *   [StreamingFileReceiver] and send FILE_ACCEPT; on `reject(reason)` send
 *   FILE_REJECT; on timeout auto-reject.
 *
 * All wire writes go through the session's shared `sendMutex` so file frames
 * never interleave with messages / PINGs on the same connection.
 */
internal class FileTransferDispatcher(
    private val sessionId: String,
    private val remotePeer: Peer,
    private val protocol: P2pProtocol,
    private val getConnection: () -> RawConnection,
    private val sendMutex: Mutex,
    private val config: FileTransferConfig,
    private val scope: CoroutineScope,
    private val random: Random,
    private val logger: P2pLogger
) {

    private val _incomingOffers = MutableSharedFlow<P2pFileOffer>(
        replay = 0,
        extraBufferCapacity = 64,
        onBufferOverflow = BufferOverflow.SUSPEND
    )
    val incomingFiles: SharedFlow<P2pFileOffer> = _incomingOffers.asSharedFlow()

    private val outgoing: MutableMap<MessageId, OutgoingEntry> = mutableMapOf()
    private val incoming: MutableMap<MessageId, IncomingEntry> = mutableMapOf()
    private val lock = Mutex()
    @Volatile private var closed: Boolean = false

    private class OutgoingEntry(
        val handle: OutgoingFileTransferImpl,
        var timer: Job?,
        var sender: Job?
    )

    private class IncomingEntry(
        val session: IncomingFileSession,
        var timer: Job?,
        var acceptedOrRejected: Boolean = false
    )

    // ---- Outgoing API ----

    suspend fun sendFile(
        name: String,
        sizeBytes: Long,
        mimeType: String?,
        source: RawSource
    ): P2pFileTransfer {
        require(sizeBytes >= 0) { "sizeBytes must be non-negative, got $sizeBytes" }
        if (sizeBytes > config.maxFileSizeBytes) {
            throw P2pError.PayloadTooLarge(maxBytes = config.maxFileSizeBytes, actualBytes = sizeBytes)
        }
        if (closed) {
            throw P2pError.ConnectionFailed("Session $sessionId is closed; cannot start file transfer")
        }

        val transferId = MessageId.random(random)
        val handle = OutgoingFileTransferImpl(
            peer = remotePeer,
            name = name,
            sizeBytes = sizeBytes,
            mimeType = mimeType,
            transferId = transferId,
            source = source,
            dispatcher = this
        )

        val timer = scope.launch {
            try {
                delay(config.offerTimeoutMillis)
            } catch (e: CancellationException) {
                return@launch
            }
            handleOutgoingTimeout(transferId)
        }

        lock.withLock {
            outgoing[transferId] = OutgoingEntry(handle = handle, timer = timer, sender = null)
        }

        // Own the source's lifetime: close it whenever this transfer reaches a
        // terminal state. This is what makes the convenience extensions
        // (`sendFile(file: File)`, `sendFile(context, uri)`) leak-free — they
        // open an underlying InputStream and rely on this cleanup.
        scope.launch {
            handle.state.first { it.isTerminal() }
            runCatching { source.close() }
        }

        // Send FILE_OFFER. Failure here means the connection is gone — surface
        // it as Failed and rethrow so the caller's await fails fast.
        val payload = FileOfferPayload(name = name, sizeBytes = sizeBytes, mimeType = mimeType)
        try {
            sendMutex.withLock {
                protocol.sendFileOffer(getConnection(), transferId, payload)
            }
        } catch (e: CancellationException) {
            removeOutgoing(transferId)
            timer.cancel()
            throw e
        } catch (e: Throwable) {
            val err = if (e is P2pError) e else P2pError.ConnectionFailed("FILE_OFFER write failed: ${e.message}")
            lock.withLock {
                outgoing.remove(transferId)?.let { it.timer?.cancel(); it.sender?.cancel() }
            }
            handle.markFailed(err)
            throw err
        }
        return handle
    }

    suspend fun cancelOutgoing(handle: OutgoingFileTransferImpl, reason: String?) {
        val entry = lock.withLock {
            val e = outgoing[handle.transferId] ?: return
            if (handle.state.value.isTerminal()) return
            handle.setState(FileTransferState.Cancelled(reason))
            outgoing.remove(handle.transferId)
            e
        }
        entry.timer?.cancel()
        entry.sender?.cancel()
        runCatching {
            sendMutex.withLock { protocol.sendFileCancel(getConnection(), handle.transferId, reason) }
        }.onFailure {
            logger.debug("Session $sessionId: best-effort FILE_CANCEL for ${handle.transferId} failed: ${it.message}")
        }
    }

    // ---- Incoming API (called by IncomingFileSession on user action) ----

    suspend fun acceptOffer(session: IncomingFileSession, sink: RawSink): P2pFileTransfer {
        val entry = lock.withLock {
            val e = incoming[session.transferId]
                ?: throw IllegalStateException("Offer ${session.id} is no longer pending")
            if (e.acceptedOrRejected) {
                throw IllegalStateException("Offer ${session.id} was already accepted or rejected")
            }
            if (session.state.value.isTerminal()) {
                throw IllegalStateException("Offer ${session.id} is in terminal state ${session.state.value}")
            }
            e.acceptedOrRejected = true
            e.timer?.cancel()
            e.timer = null
            session.setReceiver(StreamingFileReceiver(session.transferId, session.sizeBytes, sink))
            session.setState(FileTransferState.Accepted)
            e
        }
        try {
            sendMutex.withLock {
                protocol.sendFileAccept(getConnection(), session.transferId)
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            val err = if (e is P2pError) e else P2pError.ConnectionFailed("FILE_ACCEPT write failed: ${e.message}")
            session.markFailed(err)
            lock.withLock { incoming.remove(session.transferId) }
            throw err
        }
        // For zero-byte files we may transition to Sending(1.0) on the first
        // FILE_DONE without ever seeing FILE_DATA; that's handled in onFileDone.
        @Suppress("UNUSED_VARIABLE")
        val unused = entry  // suppress unused warning
        return session
    }

    suspend fun rejectOffer(session: IncomingFileSession, reason: String?) {
        val entry = lock.withLock {
            val e = incoming[session.transferId] ?: return
            if (e.acceptedOrRejected) return
            if (session.state.value.isTerminal()) return
            e.acceptedOrRejected = true
            e.timer?.cancel()
            session.setState(FileTransferState.Rejected(reason))
            incoming.remove(session.transferId)
            e
        }
        runCatching {
            sendMutex.withLock { protocol.sendFileReject(getConnection(), session.transferId, reason) }
        }.onFailure {
            logger.debug("Session $sessionId: best-effort FILE_REJECT for ${session.transferId} failed: ${it.message}")
        }
        @Suppress("UNUSED_VARIABLE")
        val unused = entry
    }

    suspend fun cancelIncoming(session: IncomingFileSession, reason: String?) {
        val (removed, wasAccepted) = lock.withLock {
            val e = incoming[session.transferId] ?: return
            val accepted = e.acceptedOrRejected
            if (session.state.value.isTerminal()) return
            session.setState(FileTransferState.Cancelled(reason))
            e.timer?.cancel()
            incoming.remove(session.transferId)
            session.receiver?.abort()
            e to accepted
        }
        @Suppress("UNUSED_VARIABLE")
        val unused = removed
        // If we hadn't yet accepted, send FILE_REJECT (peer hasn't started streaming);
        // if we had, send FILE_CANCEL (peer is mid-stream).
        runCatching {
            sendMutex.withLock {
                if (wasAccepted) {
                    protocol.sendFileCancel(getConnection(), session.transferId, reason)
                } else {
                    protocol.sendFileReject(getConnection(), session.transferId, reason)
                }
            }
        }.onFailure {
            logger.debug("Session $sessionId: best-effort cancel for ${session.transferId} failed: ${it.message}")
        }
    }

    // ---- Inbound protocol-event dispatch (called from P2pSessionImpl.routeEvents) ----

    suspend fun onFileOffer(transferId: MessageId, payload: FileOfferPayload) {
        if (closed) return

        // Validate size up-front. If it exceeds our local config, auto-reject so the
        // sender knows immediately and doesn't sit on a timeout.
        if (payload.sizeBytes > config.maxFileSizeBytes) {
            logger.warn(
                "Session $sessionId: rejecting file offer $transferId — " +
                    "size ${payload.sizeBytes} exceeds maxFileSizeBytes ${config.maxFileSizeBytes}"
            )
            runCatching {
                sendMutex.withLock {
                    protocol.sendFileReject(
                        getConnection(),
                        transferId,
                        "sizeBytes ${payload.sizeBytes} exceeds maxFileSizeBytes ${config.maxFileSizeBytes}"
                    )
                }
            }
            return
        }

        val session = IncomingFileSession(
            peer = remotePeer,
            name = payload.name,
            sizeBytes = payload.sizeBytes,
            mimeType = payload.mimeType,
            transferId = transferId,
            dispatcher = this
        )
        val timer = scope.launch {
            try {
                delay(config.offerTimeoutMillis)
            } catch (e: CancellationException) {
                return@launch
            }
            autoRejectIncoming(transferId)
        }
        lock.withLock {
            incoming[transferId] = IncomingEntry(session = session, timer = timer)
        }
        // Don't block the session's routeEvents loop on a slow subscriber. With
        // extraBufferCapacity=64 in the SharedFlow this is essentially always
        // immediate, but launching protects PING/PONG/CLOSE liveness in the
        // pathological case where the app is slow to subscribe.
        scope.launch { _incomingOffers.emit(session) }
    }

    suspend fun onFileAccept(transferId: MessageId) {
        val entry = lock.withLock { outgoing[transferId] }
        if (entry == null) {
            logger.debug("Session $sessionId: FILE_ACCEPT for unknown transfer $transferId; ignoring")
            return
        }
        val handle = entry.handle
        // Cancel the offer timer; we're past that phase.
        entry.timer?.cancel()
        entry.timer = null
        if (handle.state.value.isTerminal()) return
        handle.setState(FileTransferState.Accepted)

        // Launch the streamer on the session scope so close() cancels it.
        val job = scope.launch {
            streamOutgoingPayload(handle)
        }
        lock.withLock { entry.sender = job }
    }

    suspend fun onFileReject(transferId: MessageId, reason: String?) {
        val entry = lock.withLock { outgoing.remove(transferId) }
        if (entry == null) {
            logger.debug("Session $sessionId: FILE_REJECT for unknown transfer $transferId; ignoring")
            return
        }
        entry.timer?.cancel()
        entry.sender?.cancel()
        if (!entry.handle.state.value.isTerminal()) {
            entry.handle.setState(FileTransferState.Rejected(reason))
        }
    }

    suspend fun onFileData(frame: Frame) {
        val entry = lock.withLock { incoming[frame.messageId] }
        if (entry == null) {
            logger.debug("Session $sessionId: FILE_DATA for unknown transfer ${frame.messageId}; ignoring")
            return
        }
        val recv = entry.session.receiver
        if (recv == null) {
            logger.warn(
                "Session $sessionId: FILE_DATA for ${frame.messageId} arrived before accept; dropping"
            )
            return
        }
        try {
            val total = recv.acceptDataChunk(frame)
            entry.session.recordBytesReceived(total)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            // acceptDataChunk can throw P2pError (protocol violation) OR a raw
            // kotlinx-io IOException from the sink (disk full / closed fd). Both
            // must stay scoped to THIS transfer — letting a non-P2pError escape
            // into routeEvents would tear down the whole session (every other
            // transfer + message) because one receiver's disk filled up.
            val err = if (e is P2pError) e
            else P2pError.ConnectionFailed("file receive write failed: ${e.message ?: e::class.simpleName}")
            entry.session.markFailed(err)
            recv.abort()
            lock.withLock { incoming.remove(frame.messageId) }
            // Tell the peer we won't be completing this.
            runCatching {
                sendMutex.withLock {
                    protocol.sendFileCancel(getConnection(), frame.messageId, "receive error: ${err.message}")
                }
            }
        }
    }

    suspend fun onFileDone(transferId: MessageId) {
        val entry = lock.withLock { incoming[transferId] }
        if (entry == null) {
            logger.debug("Session $sessionId: FILE_DONE for unknown transfer $transferId; ignoring")
            return
        }
        val recv = entry.session.receiver
        if (recv == null) {
            logger.warn("Session $sessionId: FILE_DONE for $transferId without prior accept")
            return
        }
        try {
            recv.finish()
            entry.session.setState(FileTransferState.Completed)
        } catch (e: P2pError) {
            entry.session.markFailed(e)
        } finally {
            lock.withLock { incoming.remove(transferId) }
        }
    }

    suspend fun onFileCancel(transferId: MessageId, reason: String?) {
        // Could be either side's transfer — check both maps.
        val outg = lock.withLock { outgoing.remove(transferId) }
        if (outg != null) {
            outg.timer?.cancel()
            outg.sender?.cancel()
            if (!outg.handle.state.value.isTerminal()) {
                outg.handle.setState(FileTransferState.Cancelled(reason))
            }
            return
        }
        val inc = lock.withLock { incoming.remove(transferId) }
        if (inc != null) {
            inc.timer?.cancel()
            inc.session.receiver?.abort()
            if (!inc.session.state.value.isTerminal()) {
                inc.session.setState(FileTransferState.Cancelled(reason))
            }
            return
        }
        logger.debug("Session $sessionId: FILE_CANCEL for unknown transfer $transferId; ignoring")
    }

    /** Called from the session on close / connection loss. Cancels every in-flight transfer. */
    suspend fun closeAll(reason: String) {
        closed = true
        val (outs, ins) = lock.withLock {
            val o = outgoing.values.toList().also { outgoing.clear() }
            val i = incoming.values.toList().also { incoming.clear() }
            o to i
        }
        for (e in outs) {
            e.timer?.cancel()
            e.sender?.cancel()
            if (!e.handle.state.value.isTerminal()) {
                e.handle.markFailed(P2pError.ConnectionFailed(reason))
            }
        }
        for (e in ins) {
            e.timer?.cancel()
            e.session.receiver?.abort()
            if (!e.session.state.value.isTerminal()) {
                e.session.markFailed(P2pError.ConnectionFailed(reason))
            }
        }
    }

    // ---- Internal helpers ----

    private suspend fun streamOutgoingPayload(handle: OutgoingFileTransferImpl) {
        try {
            if (handle.sizeBytes > 0) {
                handle.setState(FileTransferState.Sending(0f))
            }
            streamFileData(
                transferId = handle.transferId,
                rawSource = handle.source,
                sizeBytes = handle.sizeBytes,
                chunkSizeBytes = config.chunkSizeBytes
            ).collect { frame ->
                sendMutex.withLock {
                    protocol.sendFileDataFrame(getConnection(), frame)
                }
                handle.recordBytesSent(frame.payload.size)
            }
            sendMutex.withLock {
                protocol.sendFileDone(getConnection(), handle.transferId)
            }
            if (!handle.state.value.isTerminal()) {
                handle.setState(FileTransferState.Completed)
            }
            lock.withLock { outgoing.remove(handle.transferId) }
        } catch (e: CancellationException) {
            // Cancelled via cancelOutgoing or session close — state already set there.
            throw e
        } catch (e: Throwable) {
            val err = if (e is P2pError) e else P2pError.ConnectionFailed("FILE_DATA write failed: ${e.message}")
            handle.markFailed(err)
            lock.withLock { outgoing.remove(handle.transferId) }
            logger.warn("Session $sessionId: outgoing transfer ${handle.transferId} failed", e)
        }
    }

    private suspend fun handleOutgoingTimeout(transferId: MessageId) {
        val entry = lock.withLock {
            val e = outgoing[transferId] ?: return
            // Only timeout if still in Offered state — sender goroutine hasn't started.
            if (e.handle.state.value !is FileTransferState.Offered) return
            e.handle.setState(FileTransferState.Cancelled("offer not accepted within ${config.offerTimeoutMillis}ms"))
            outgoing.remove(transferId)
            e
        }
        entry.sender?.cancel()
        runCatching {
            sendMutex.withLock {
                protocol.sendFileCancel(
                    getConnection(),
                    transferId,
                    "offer not accepted within ${config.offerTimeoutMillis}ms"
                )
            }
        }
    }

    private suspend fun autoRejectIncoming(transferId: MessageId) {
        val entry = lock.withLock {
            val e = incoming[transferId] ?: return
            if (e.acceptedOrRejected) return
            e.acceptedOrRejected = true
            e.session.setState(FileTransferState.Rejected("timeout"))
            incoming.remove(transferId)
            e
        }
        @Suppress("UNUSED_VARIABLE")
        val unused = entry
        runCatching {
            sendMutex.withLock {
                protocol.sendFileReject(getConnection(), transferId, "timeout")
            }
        }
    }

    private suspend fun removeOutgoing(transferId: MessageId) {
        lock.withLock { outgoing.remove(transferId) }
    }
}

private fun FileTransferState.isTerminal(): Boolean = when (this) {
    is FileTransferState.Completed,
    is FileTransferState.Rejected,
    is FileTransferState.Cancelled,
    is FileTransferState.Failed -> true
    else -> false
}
