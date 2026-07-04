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
import dev.p2pkit.core.transfer.isTerminal
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
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

        val inserted = lock.withLock {
            // AUDIT-2026-07 (FIL-6): re-check `closed` under the lock — a
            // concurrent closeAll() that latched `closed` and swept the maps
            // after the check at the top of this function must not be
            // followed by a late insert. Such an entry would have no close
            // path left to terminalize it, and its source would stay open.
            // Mirrors the onFileOffer re-check shape (AUDIT-2026-06 #16).
            if (closed) {
                false
            } else {
                outgoing[transferId] = OutgoingEntry(handle = handle, timer = timer, sender = null)
                true
            }
        }
        if (!inserted) {
            timer.cancel()
            val err = P2pError.ConnectionFailed("Session $sessionId is closed; cannot start file transfer")
            // Terminalize the never-registered handle so the close-once guard
            // releases the caller's source (the kit owns it — see KDoc).
            handle.markFailed(err)
            throw err
        }

        // Own the source's lifetime: the guaranteed close happens at the
        // handle's terminal transition itself (close-once guard in
        // [OutgoingFileTransferImpl] — AUDIT-2026-07 FIL-1). This watcher is
        // only a backstop: it used to be the sole close path, but the session
        // scope cancels it on teardown before it can observe the terminal
        // state, leaking the source. The terminal-transition close is what
        // makes the convenience extensions (`sendFile(file: File)`,
        // `sendFile(context, uri)`) leak-free — they open an underlying
        // InputStream and rely on this cleanup.
        scope.launch {
            handle.state.first { it.isTerminal() }
            handle.closeSourceOnce()
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
            // Mark terminal so the caller's RawSource is released; without
            // this the handle never terminalized and the source leaked for
            // the session lifetime (AUDIT-2026-06 fix). The close now happens
            // synchronously inside this terminal transition
            // (AUDIT-2026-07 FIL-1 close-once guard).
            handle.setState(FileTransferState.Cancelled("sendFile cancelled before FILE_OFFER was written"))
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
        // Best-effort notify; must NOT swallow CancellationException
        // (runCatching did — the caller's cancellation was silently eaten)
        // (AUDIT-2026-06 fix).
        try {
            sendMutex.withLock { protocol.sendFileCancel(getConnection(), handle.transferId, reason) }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            logger.debug("Session $sessionId: best-effort FILE_CANCEL for ${handle.transferId} failed: ${e.message}")
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
        try {
            sendMutex.withLock { protocol.sendFileReject(getConnection(), session.transferId, reason) }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            logger.debug("Session $sessionId: best-effort FILE_REJECT for ${session.transferId} failed: ${e.message}")
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
        try {
            sendMutex.withLock {
                if (wasAccepted) {
                    protocol.sendFileCancel(getConnection(), session.transferId, reason)
                } else {
                    protocol.sendFileReject(getConnection(), session.transferId, reason)
                }
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            logger.debug("Session $sessionId: best-effort cancel for ${session.transferId} failed: ${e.message}")
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
            try {
                sendMutex.withLock {
                    protocol.sendFileReject(
                        getConnection(),
                        transferId,
                        "sizeBytes ${payload.sizeBytes} exceeds maxFileSizeBytes ${config.maxFileSizeBytes}"
                    )
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                logger.debug("Session $sessionId: best-effort FILE_REJECT for $transferId failed: ${e.message}")
            }
            return
        }

        // Guard against a duplicate transferId (would orphan the first offer
        // and cross-wire its timers) and cap concurrently pending inbound
        // offers — each one allocates a session + two coroutines, so an
        // unbounded map was a FILE_OFFER-spam amplification vector
        // (AUDIT-2026-06 fix).
        val pendingState = lock.withLock {
            when {
                incoming.containsKey(transferId) || outgoing.containsKey(transferId) -> -1
                else -> incoming.size
            }
        }
        if (pendingState == -1) {
            logger.warn("Session $sessionId: duplicate FILE_OFFER transferId $transferId; ignoring")
            return
        }
        if (pendingState >= MAX_PENDING_INCOMING_OFFERS) {
            logger.warn(
                "Session $sessionId: rejecting file offer $transferId — " +
                    "$pendingState offers already pending (cap $MAX_PENDING_INCOMING_OFFERS)"
            )
            try {
                sendMutex.withLock {
                    protocol.sendFileReject(getConnection(), transferId, "too many pending offers")
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                logger.debug("Session $sessionId: best-effort FILE_REJECT for $transferId failed: ${e.message}")
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
            // Re-check `closed` under the lock: a concurrent closeAll() that
            // latched `closed` and swept the maps after the check at the top
            // of this function must not be followed by a late insert — the
            // entry would leak with no close path left to clean it up, and
            // the offer must not be emitted for a closed session
            // (AUDIT-2026-06 fix).
            if (closed) {
                timer.cancel()
                return
            }
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
        // AUDIT-2026-07 (FIL-4): only the first FILE_ACCEPT for a transfer
        // still in Offered may start a streamer — a duplicate accept from a
        // non-conforming peer would otherwise launch a second concurrent
        // streamer over the same source (interleaved chunk sequences, doubled
        // progress accounting). Subsumes the old isTerminal() early-return:
        // any non-Offered state (Accepted, Sending, terminal) is ignored.
        if (handle.state.value !is FileTransferState.Offered) {
            logger.warn(
                "Session $sessionId: FILE_ACCEPT for $transferId in state " +
                    "${handle.state.value}; ignoring duplicate accept"
            )
            return
        }
        // Cancel the offer timer; we're past that phase.
        entry.timer?.cancel()
        entry.timer = null
        handle.setState(FileTransferState.Accepted)

        // Launch the streamer on the session scope so close() cancels it.
        // Start LAZY so the job is registered as entry.sender BEFORE it can
        // run: a FILE_CANCEL landing between launch and registration would
        // otherwise see sender == null and be unable to cancel the streamer.
        // streamOutgoingPayload re-checks terminal state at entry, so a cancel
        // that lands after start() is still safe (AUDIT-2026-06 fix).
        val job = scope.launch(start = CoroutineStart.LAZY) {
            streamOutgoingPayload(handle)
        }
        lock.withLock { entry.sender = job }
        job.start()
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
            try {
                sendMutex.withLock {
                    protocol.sendFileCancel(getConnection(), frame.messageId, "receive error: ${err.message}")
                }
            } catch (ce: CancellationException) {
                throw ce
            } catch (t: Throwable) {
                logger.debug("Session $sessionId: best-effort FILE_CANCEL for ${frame.messageId} failed: ${t.message}")
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
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            // finish() flushes the sink, which can throw P2pError (incomplete
            // payload) OR a raw kotlinx-io IOException (disk full / closed fd).
            // Both must stay scoped to THIS transfer — letting a non-P2pError
            // escape into routeEvents would tear down the whole session
            // (AUDIT-2026-06 fix; mirrors onFileData).
            val err = if (e is P2pError) e
            else P2pError.ConnectionFailed("file receive finalize failed: ${e.message ?: e::class.simpleName}")
            entry.session.markFailed(err)
            recv.abort()
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

    /**
     * Re-enables the dispatcher after [closeAll] during a reconnect rearm.
     * [closeAll] doubles as the terminal-close path and latches [closed];
     * [P2pSessionImpl.rearmWith] calls this right after failing in-flight
     * transfers so the surviving session can still transfer files.
     */
    fun reopen() {
        closed = false
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
        // A FILE_CANCEL can race onFileAccept between its terminal check and
        // this launch; bail before streaming a single chunk in that case
        // (AUDIT-2026-06 fix).
        if (handle.state.value.isTerminal()) return
        // AUDIT-2026-07 (FIL-2): distinguish connection-write failures from
        // source-read failures. Only the latter warrant a best-effort
        // FILE_CANCEL below — the wire is healthy, and without the frame the
        // peer's accepted transfer would wait indefinitely for
        // FILE_DATA/FILE_DONE that will never come.
        var connectionWriteFailure = false
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
                try {
                    sendMutex.withLock {
                        protocol.sendFileDataFrame(getConnection(), frame)
                    }
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Throwable) {
                    connectionWriteFailure = true
                    throw e
                }
                handle.recordBytesSent(frame.payload.size)
            }
            try {
                sendMutex.withLock {
                    protocol.sendFileDone(getConnection(), handle.transferId)
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                connectionWriteFailure = true
                throw e
            }
            if (!handle.state.value.isTerminal()) {
                handle.setState(FileTransferState.Completed)
            }
            lock.withLock { outgoing.remove(handle.transferId) }
        } catch (e: CancellationException) {
            // Cancelled via cancelOutgoing or session close — state already set there.
            throw e
        } catch (e: Throwable) {
            val wasAlreadyTerminal = handle.state.value.isTerminal()
            val err = if (e is P2pError) e else P2pError.ConnectionFailed(
                if (connectionWriteFailure) "FILE_DATA write failed: ${e.message}"
                else "file source read failed: ${e.message}"
            )
            handle.markFailed(err)
            lock.withLock { outgoing.remove(handle.transferId) }
            logger.warn("Session $sessionId: outgoing transfer ${handle.transferId} failed", e)
            // AUDIT-2026-07 (FIL-2): best-effort peer notification for a
            // source-side failure on a healthy connection — mirrors the
            // receiver-side failure path in onFileData. Skipped when the wire
            // itself failed (session-level teardown informs the peer) or the
            // transfer was already terminal (its terminal path already sent
            // any required frame). The failure stays scoped to this transfer;
            // the session remains Connected.
            if (!connectionWriteFailure && !wasAlreadyTerminal) {
                try {
                    sendMutex.withLock {
                        protocol.sendFileCancel(
                            getConnection(),
                            handle.transferId,
                            "sender source failure: ${err.message}"
                        )
                    }
                } catch (ce: CancellationException) {
                    throw ce
                } catch (t: Throwable) {
                    logger.debug(
                        "Session $sessionId: best-effort FILE_CANCEL for ${handle.transferId} failed: ${t.message}"
                    )
                }
            }
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
        try {
            sendMutex.withLock {
                protocol.sendFileCancel(
                    getConnection(),
                    transferId,
                    "offer not accepted within ${config.offerTimeoutMillis}ms"
                )
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            logger.debug("Session $sessionId: best-effort FILE_CANCEL for $transferId failed: ${e.message}")
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
        try {
            sendMutex.withLock {
                protocol.sendFileReject(getConnection(), transferId, "timeout")
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            logger.debug("Session $sessionId: best-effort FILE_REJECT for $transferId failed: ${e.message}")
        }
    }

    private suspend fun removeOutgoing(transferId: MessageId) {
        lock.withLock { outgoing.remove(transferId) }
    }
}


/** Cap on concurrently pending inbound FILE_OFFERs per session (DoS bound). */
private const val MAX_PENDING_INCOMING_OFFERS: Int = 64
