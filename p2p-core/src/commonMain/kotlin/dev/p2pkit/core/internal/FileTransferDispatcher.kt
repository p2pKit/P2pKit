package dev.p2pkit.core.internal

import dev.p2pkit.core.FileTransferFailureKind
import dev.p2pkit.core.FileTransferPhase
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.Retryability
import dev.p2pkit.core.protocol.FileOfferPayload
import dev.p2pkit.core.protocol.Frame
import dev.p2pkit.core.protocol.MessageId
import dev.p2pkit.core.protocol.P2pProtocol
import dev.p2pkit.core.protocol.streamFileData
import dev.p2pkit.core.transfer.FileTransferConfig
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.core.transfer.acceptedIdleTimeoutMillis
import dev.p2pkit.core.transfer.acceptedOverallTimeoutMillis
import dev.p2pkit.core.transfer.isTerminal
import dev.p2pkit.core.transfer.outgoingOfferWatchdogMillis
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.io.RawSink
import kotlinx.io.RawSource
import kotlin.concurrent.Volatile
import kotlin.random.Random

/**
 * Per-session file-transfer owner. The dispatcher mutex protects only map and
 * timer ownership. Application source/sink I/O is serialized by each transfer
 * and always runs after map ownership has been resolved.
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

    private val incomingOffers = MutableSharedFlow<P2pFileOffer>(
        replay = 0,
        extraBufferCapacity = MAX_PENDING_INCOMING_OFFERS,
        onBufferOverflow = BufferOverflow.SUSPEND
    )
    val incomingFiles: SharedFlow<P2pFileOffer> = incomingOffers.asSharedFlow()

    private val _pendingFileOffers = MutableStateFlow<List<P2pFileOffer>>(emptyList())
    val pendingFileOffers: StateFlow<List<P2pFileOffer>> = _pendingFileOffers.asStateFlow()

    private val outgoing: MutableMap<MessageId, OutgoingEntry> = mutableMapOf()
    private val incoming: MutableMap<MessageId, IncomingEntry> = mutableMapOf()
    private val lock = Mutex()

    @Volatile
    private var closed: Boolean = false

    private enum class OutgoingPhase { OFFERED, STREAMING }

    private class OutgoingEntry(
        val handle: OutgoingFileTransferImpl,
        @Volatile
        var phase: OutgoingPhase = OutgoingPhase.OFFERED,
        var timer: Job? = null,
        var sender: Job? = null
    )

    private enum class IncomingPhase { OFFERED, ACCEPTING, ACCEPTED }

    private class IncomingEntry(
        val session: IncomingFileSession,
        val payload: FileOfferPayload,
        @Volatile
        var phase: IncomingPhase = IncomingPhase.OFFERED,
        var offerTimer: Job? = null,
        var idleTimer: Job? = null,
        var overallTimer: Job? = null,
        var idleGeneration: Long = 0L
    )

    // ---- Outgoing API ----

    suspend fun sendFile(
        name: String,
        sizeBytes: Long,
        mimeType: String?,
        source: RawSource
    ): P2pFileTransfer {
        if (sizeBytes < 0L) {
            val cause = IllegalArgumentException("sizeBytes must be non-negative, got $sizeBytes")
            throw fileFailure(
                kind = FileTransferFailureKind.INVALID_METADATA,
                phase = FileTransferPhase.OFFER,
                retryability = Retryability.NOT_RETRYABLE,
                transferId = null,
                reason = cause.message ?: "sizeBytes must be non-negative",
                cause = cause
            )
        }
        if (sizeBytes > config.maxFileSizeBytes) {
            throw P2pError.PayloadTooLarge(config.maxFileSizeBytes, sizeBytes)
        }
        requireSupportedChunkCount(sizeBytes)

        val payload = FileOfferPayload(name = name, sizeBytes = sizeBytes, mimeType = mimeType)
        try {
            FileOfferPayload.validate(payload)
        } catch (e: IllegalArgumentException) {
            throw fileFailure(
                kind = FileTransferFailureKind.INVALID_METADATA,
                phase = FileTransferPhase.OFFER,
                retryability = Retryability.NOT_RETRYABLE,
                transferId = null,
                reason = e.message ?: "Invalid file-offer metadata",
                cause = e
            )
        }

        val entry = try {
            lock.withLock {
                if (closed) {
                    throw fileFailure(
                        kind = FileTransferFailureKind.REMOTE_DISCONNECTED,
                        phase = FileTransferPhase.OFFER,
                        retryability = Retryability.RETRY_NEW_SESSION,
                        transferId = null,
                        reason = "Session $sessionId is closed; cannot start file transfer"
                    )
                }
                val transferId = allocateTransferIdLocked()
                val handle = OutgoingFileTransferImpl(
                    peer = remotePeer,
                    name = name,
                    sizeBytes = sizeBytes,
                    mimeType = mimeType,
                    transferId = transferId,
                    source = source,
                    dispatcher = this
                )
                OutgoingEntry(handle).also { outgoing[transferId] = it }
            }
        } catch (e: Throwable) {
            runCatching { source.close() }
            throw e
        }

        val transferId = entry.handle.transferId
        try {
            sendMutex.withLock {
                protocol.sendFileOffer(getConnection(), transferId, payload)
            }
        } catch (e: CancellationException) {
            val removed = removeOutgoing(transferId, entry)
            removed?.cancelJobs()
            withContext(NonCancellable) {
                entry.handle.setState(
                    FileTransferState.Cancelled("sendFile cancelled before FILE_OFFER was written")
                )
            }
            throw e
        } catch (e: Throwable) {
            val err = failureFromCause(
                kind = FileTransferFailureKind.TRANSPORT,
                phase = FileTransferPhase.OFFER,
                retryability = Retryability.RETRY_NEW_SESSION,
                transferId = transferId,
                prefix = "FILE_OFFER write failed",
                cause = e
            )
            removeOutgoing(transferId, entry)?.cancelJobs()
            entry.handle.markFailed(err)
            throw err
        }

        armOutgoingOfferWatchdog(entry)
        return entry.handle
    }

    suspend fun cancelOutgoing(handle: OutgoingFileTransferImpl, reason: String?) {
        val entry = removeOutgoing(handle.transferId) ?: return
        val changed = withContext(NonCancellable) {
            val changed = handle.setState(FileTransferState.Cancelled(reason))
            entry.cancelJobs()
            changed
        }
        if (!changed) return
        sendBestEffort("FILE_CANCEL for ${handle.transferId}") {
            protocol.sendFileCancel(getConnection(), handle.transferId, reason)
        }
    }

    // ---- Incoming API ----

    suspend fun acceptOffer(session: IncomingFileSession, sink: RawSink): P2pFileTransfer {
        val entry = lock.withLock {
            val current = incoming[session.transferId]
                ?: throw IllegalStateException("Offer ${session.id} is no longer pending")
            if (current.phase != IncomingPhase.OFFERED || session.state.value.isTerminal()) {
                throw IllegalStateException("Offer ${session.id} was already accepted or rejected")
            }
            current.phase = IncomingPhase.ACCEPTING
            current.offerTimer?.cancel()
            current.offerTimer = null
            current
        }

        if (!session.installReceiver(sink)) {
            removeIncoming(session.transferId, entry)?.cancelJobs()
            throw IllegalStateException("Offer ${session.id} became terminal during acceptance")
        }

        try {
            withTimeout(config.offerTimeoutMillis) {
                sendMutex.withLock {
                    protocol.sendFileAccept(getConnection(), session.transferId)
                }
            }
            currentCoroutineContext().ensureActive()
        } catch (e: TimeoutCancellationException) {
            val err = fileFailure(
                kind = FileTransferFailureKind.TIMEOUT,
                phase = FileTransferPhase.ACCEPT,
                retryability = Retryability.RETRY_NEW_SESSION,
                transferId = session.transferId,
                reason = "FILE_ACCEPT write did not finish within ${config.offerTimeoutMillis}ms",
                cause = e
            )
            compensateAmbiguousAccept(entry, FileTransferState.Failed(err))
            throw err
        } catch (e: CancellationException) {
            compensateAmbiguousAccept(
                entry,
                FileTransferState.Cancelled("accept cancelled while FILE_ACCEPT was in flight")
            )
            throw e
        } catch (e: Throwable) {
            val err = failureFromCause(
                kind = FileTransferFailureKind.TRANSPORT,
                phase = FileTransferPhase.ACCEPT,
                retryability = Retryability.RETRY_NEW_SESSION,
                transferId = session.transferId,
                prefix = "FILE_ACCEPT write failed",
                cause = e
            )
            compensateAmbiguousAccept(entry, FileTransferState.Failed(err))
            throw err
        }

        val committed = lock.withLock {
            val current = incoming[session.transferId]
            if (current === entry && current.phase == IncomingPhase.ACCEPTING) {
                current.phase = IncomingPhase.ACCEPTED
                removePendingOfferLocked(current.session)
                true
            } else {
                false
            }
        }
        if (committed) armAcceptedDeadlines(entry)
        return session
    }

    suspend fun rejectOffer(session: IncomingFileSession, reason: String?) {
        val entry = lock.withLock {
            val current = incoming[session.transferId]
                ?: throw IllegalStateException("Offer ${session.id} is no longer pending")
            if (current.phase != IncomingPhase.OFFERED || session.state.value.isTerminal()) {
                throw IllegalStateException("Offer ${session.id} was already accepted or rejected")
            }
            incoming.remove(session.transferId)
            removePendingOfferLocked(current.session)
            current
        }
        entry.cancelJobs()
        session.setState(FileTransferState.Rejected(reason))
        sendBestEffort("FILE_REJECT for ${session.transferId}") {
            protocol.sendFileReject(getConnection(), session.transferId, reason)
        }
    }

    suspend fun cancelIncoming(session: IncomingFileSession, reason: String?) {
        val entry = lock.withLock {
            val current = incoming.remove(session.transferId) ?: return
            removePendingOfferLocked(current.session)
            current
        }
        val accepted = entry.phase != IncomingPhase.OFFERED
        val changed = withContext(NonCancellable) {
            val changed = session.setState(FileTransferState.Cancelled(reason))
            entry.cancelJobs()
            changed
        }
        if (!changed) return
        sendBestEffort("cancel for ${session.transferId}") {
            if (accepted) {
                protocol.sendFileCancel(getConnection(), session.transferId, reason)
            } else {
                protocol.sendFileReject(getConnection(), session.transferId, reason)
            }
        }
    }

    // ---- Inbound protocol events ----

    suspend fun onFileOffer(transferId: MessageId, payload: FileOfferPayload) {
        if (closed) return
        if (payload.sizeBytes > config.maxFileSizeBytes || !hasSupportedChunkCount(payload.sizeBytes)) {
            val reason = if (payload.sizeBytes > config.maxFileSizeBytes) {
                "sizeBytes ${payload.sizeBytes} exceeds maxFileSizeBytes ${config.maxFileSizeBytes}"
            } else {
                "file requires more than ${Int.MAX_VALUE} chunks"
            }
            sendBestEffort("FILE_REJECT for $transferId") {
                protocol.sendFileReject(getConnection(), transferId, reason)
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
        val insertion = lock.withLock {
            val existingIncoming = incoming[transferId]
            when {
                closed -> OfferInsertion.CLOSED
                existingIncoming != null && existingIncoming.payload == payload ->
                    OfferInsertion.EXACT_DUPLICATE
                existingIncoming != null -> OfferInsertion.CONFLICT
                outgoing.containsKey(transferId) -> OfferInsertion.CONFLICT
                incoming.size >= MAX_PENDING_INCOMING_OFFERS -> OfferInsertion.CAPACITY
                else -> {
                    val entry = IncomingEntry(session, payload)
                    incoming[transferId] = entry
                    _pendingFileOffers.value = immutableListSnapshot(
                        _pendingFileOffers.value + session
                    )
                    OfferInsertion.Inserted(entry)
                }
            }
        }
        when (insertion) {
            OfferInsertion.CLOSED -> return
            OfferInsertion.EXACT_DUPLICATE -> {
                logger.debug("Session $sessionId: repeated FILE_OFFER transferId $transferId; ignoring")
                return
            }
            OfferInsertion.CONFLICT -> throw fileFailure(
                kind = FileTransferFailureKind.TRANSFER_PROTOCOL,
                phase = FileTransferPhase.OFFER,
                retryability = Retryability.NOT_RETRYABLE,
                transferId = transferId,
                reason = "Conflicting FILE_OFFER reused transferId $transferId"
            )
            OfferInsertion.CAPACITY -> {
                sendBestEffort("capacity FILE_REJECT for $transferId") {
                    protocol.sendFileReject(getConnection(), transferId, "too many pending offers")
                }
                return
            }
            is OfferInsertion.Inserted -> {
                armIncomingOfferTimer(insertion.entry)
                scope.launch { incomingOffers.emit(insertion.entry.session) }
            }
        }
    }

    suspend fun onFileAccept(transferId: MessageId) {
        val entry = lock.withLock {
            val current = outgoing[transferId] ?: return
            if (current.phase != OutgoingPhase.OFFERED) return
            current.phase = OutgoingPhase.STREAMING
            current.timer?.cancel()
            current.timer = null
            current
        }
        if (!entry.handle.setState(FileTransferState.Accepted)) return

        val sender = scope.launch(start = CoroutineStart.LAZY) {
            streamOutgoingPayload(entry)
        }
        val registered = lock.withLock {
            if (outgoing[transferId] === entry && entry.phase == OutgoingPhase.STREAMING) {
                entry.sender = sender
                true
            } else {
                false
            }
        }
        if (registered) sender.start() else sender.cancel()
    }

    suspend fun onFileReject(transferId: MessageId, reason: String?) {
        val result = lock.withLock {
            val current = outgoing[transferId] ?: return
            if (current.phase != OutgoingPhase.OFFERED) {
                RejectResult.InvalidTransition(current.handle.state.value)
            } else {
                outgoing.remove(transferId)
                RejectResult.Removed(current)
            }
        }
        when (result) {
            is RejectResult.InvalidTransition -> logger.warn(
                "Session $sessionId: FILE_REJECT for $transferId after acceptance " +
                    "in state ${result.state}; ignoring invalid transition"
            )
            is RejectResult.Removed -> {
                result.entry.cancelJobs()
                result.entry.handle.setState(FileTransferState.Rejected(reason))
            }
        }
    }

    suspend fun onFileData(frame: Frame) {
        val entry = lock.withLock { incoming[frame.messageId] }
        if (entry == null) {
            logger.debug("Session $sessionId: FILE_DATA for unknown transfer ${frame.messageId}; ignoring")
            return
        }
        if (entry.phase == IncomingPhase.OFFERED) {
            logger.warn("Session $sessionId: FILE_DATA for ${frame.messageId} arrived before accept; dropping")
            return
        }
        try {
            val total = entry.session.acceptData(frame) ?: return
            if (total > 0L) rearmIncomingIdleDeadline(entry)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            failIncomingTransfer(entry, "file receive write failed", e)
        }
    }

    suspend fun onFileDone(transferId: MessageId) {
        val entry = lock.withLock { incoming[transferId] }
        if (entry == null) {
            logger.debug("Session $sessionId: FILE_DONE for unknown transfer $transferId; ignoring")
            return
        }
        if (entry.phase == IncomingPhase.OFFERED) {
            logger.warn("Session $sessionId: FILE_DONE for $transferId without prior accept")
            return
        }
        try {
            val completed = entry.session.finishReceiver()
            if (completed) removeIncoming(transferId, entry)?.cancelJobs()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            failIncomingTransfer(entry, "file receive finalize failed", e)
        }
    }

    suspend fun onFileCancel(transferId: MessageId, reason: String?) {
        val outgoingEntry = removeOutgoing(transferId)
        if (outgoingEntry != null) {
            outgoingEntry.cancelJobs()
            outgoingEntry.handle.setState(FileTransferState.Cancelled(reason))
            return
        }
        val incomingEntry = removeIncoming(transferId)
        if (incomingEntry != null) {
            incomingEntry.cancelJobs()
            incomingEntry.session.setState(FileTransferState.Cancelled(reason))
            return
        }
        logger.debug("Session $sessionId: FILE_CANCEL for unknown transfer $transferId; ignoring")
    }

    fun reopen() {
        closed = false
    }

    suspend fun closeAll(
        reason: String,
        failureKind: FileTransferFailureKind = FileTransferFailureKind.REMOTE_DISCONNECTED,
        retryability: Retryability = Retryability.RETRY_NEW_SESSION
    ) {
        closed = true
        val (outgoingEntries, incomingEntries) = lock.withLock {
            val outs = outgoing.values.toList().also { outgoing.clear() }
            val ins = incoming.values.toList().also { incoming.clear() }
            _pendingFileOffers.value = immutableListSnapshot(emptyList())
            outs to ins
        }
        for (entry in outgoingEntries) {
            entry.handle.markFailed(
                fileFailure(
                    kind = failureKind,
                    phase = if (entry.phase == OutgoingPhase.OFFERED) {
                        FileTransferPhase.OFFER
                    } else {
                        FileTransferPhase.SEND
                    },
                    retryability = retryability,
                    transferId = entry.handle.transferId,
                    reason = reason
                )
            )
            entry.cancelJobs()
        }
        for (entry in incomingEntries) {
            if (entry.phase == IncomingPhase.OFFERED) {
                entry.session.setState(FileTransferState.Cancelled(reason))
            } else {
                entry.session.markFailed(
                    fileFailure(
                        kind = failureKind,
                        phase = if (entry.phase == IncomingPhase.ACCEPTING) {
                            FileTransferPhase.ACCEPT
                        } else {
                            FileTransferPhase.RECEIVE
                        },
                        retryability = retryability,
                        transferId = entry.session.transferId,
                        reason = reason
                    )
                )
            }
            entry.cancelJobs()
        }
    }

    // ---- Timers and ownership helpers ----

    private suspend fun streamOutgoingPayload(entry: OutgoingEntry) {
        val handle = entry.handle
        if (handle.state.value.isTerminal()) return
        var connectionWriteFailure = false
        try {
            if (handle.sizeBytes > 0L) handle.setState(FileTransferState.Sending(0f))
            streamFileData(
                transferId = handle.transferId,
                rawSource = handle.sourceOrThrow(),
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
                if (!handle.recordBytesSent(frame.payload.size)) {
                    throw CancellationException("Transfer ${handle.transferId} terminalized while writing")
                }
            }
            if (handle.state.value.isTerminal()) return
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
            handle.setState(FileTransferState.Completed)
            removeOutgoing(handle.transferId, entry)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            val alreadyTerminal = handle.state.value.isTerminal()
            val err = failureFromCause(
                kind = if (connectionWriteFailure) {
                    FileTransferFailureKind.TRANSPORT
                } else {
                    FileTransferFailureKind.SOURCE_IO
                },
                phase = if (connectionWriteFailure) {
                    FileTransferPhase.SEND
                } else {
                    FileTransferPhase.SOURCE_READ
                },
                retryability = if (connectionWriteFailure) {
                    Retryability.RETRY_NEW_SESSION
                } else {
                    Retryability.RETRY_AFTER_USER_ACTION
                },
                transferId = handle.transferId,
                prefix = if (connectionWriteFailure) "FILE_DATA write failed" else "file source read failed",
                cause = e
            )
            handle.markFailed(err)
            removeOutgoing(handle.transferId, entry)
            logger.warn("Session $sessionId: outgoing transfer ${handle.transferId} failed", e)
            if (!connectionWriteFailure && !alreadyTerminal) {
                sendBestEffort("FILE_CANCEL for ${handle.transferId}") {
                    protocol.sendFileCancel(
                        getConnection(),
                        handle.transferId,
                        "sender source failure: ${err.message}"
                    )
                }
            }
        }
    }

    private suspend fun armOutgoingOfferWatchdog(entry: OutgoingEntry) {
        val job = scope.launch(start = CoroutineStart.LAZY) {
            delay(config.outgoingOfferWatchdogMillis)
            handleOutgoingOfferWatchdog(entry)
        }
        val installed = lock.withLock {
            if (outgoing[entry.handle.transferId] === entry && entry.phase == OutgoingPhase.OFFERED) {
                entry.timer = job
                true
            } else {
                false
            }
        }
        if (installed) job.start() else job.cancel()
    }

    private suspend fun handleOutgoingOfferWatchdog(entry: OutgoingEntry) {
        val removed = lock.withLock {
            val current = outgoing[entry.handle.transferId]
            if (current !== entry || current.phase != OutgoingPhase.OFFERED) return
            outgoing.remove(entry.handle.transferId)
            current
        }
        removed.handle.setState(
            FileTransferState.Failed(
                fileFailure(
                    kind = FileTransferFailureKind.TIMEOUT,
                    phase = FileTransferPhase.OFFER,
                    retryability = Retryability.RETRY_SAME_SESSION,
                    transferId = entry.handle.transferId,
                    reason = "offer response not received within ${config.outgoingOfferWatchdogMillis}ms"
                )
            )
        )
        sendBestEffort("offer-watchdog FILE_CANCEL for ${entry.handle.transferId}") {
            protocol.sendFileCancel(
                getConnection(),
                entry.handle.transferId,
                "offer response timeout"
            )
        }
    }

    private suspend fun armIncomingOfferTimer(entry: IncomingEntry) {
        val job = scope.launch(start = CoroutineStart.LAZY) {
            delay(config.offerTimeoutMillis)
            autoRejectIncoming(entry)
        }
        val installed = lock.withLock {
            if (incoming[entry.session.transferId] === entry && entry.phase == IncomingPhase.OFFERED) {
                entry.offerTimer = job
                true
            } else {
                false
            }
        }
        if (installed) job.start() else job.cancel()
    }

    private suspend fun autoRejectIncoming(entry: IncomingEntry) {
        val removed = lock.withLock {
            val current = incoming[entry.session.transferId]
            if (current !== entry || current.phase != IncomingPhase.OFFERED) return
            incoming.remove(entry.session.transferId)
            removePendingOfferLocked(current.session)
            current
        }
        withContext(NonCancellable) {
            removed.session.setState(FileTransferState.Rejected("timeout"))
            removed.cancelJobs()
            sendCleanupBestEffort("timeout FILE_REJECT for ${entry.session.transferId}") {
                protocol.sendFileReject(getConnection(), entry.session.transferId, "timeout")
            }
        }
    }

    private suspend fun armAcceptedDeadlines(entry: IncomingEntry) {
        val idleGeneration = lock.withLock {
            if (incoming[entry.session.transferId] !== entry || entry.phase != IncomingPhase.ACCEPTED) {
                return
            }
            ++entry.idleGeneration
        }
        val idle = newIdleTimer(entry, idleGeneration)
        val overall = scope.launch(start = CoroutineStart.LAZY) {
            delay(config.acceptedOverallTimeoutMillis)
            timeoutAcceptedIncoming(entry, null, "overall")
        }
        val installed = lock.withLock {
            if (incoming[entry.session.transferId] === entry && entry.phase == IncomingPhase.ACCEPTED) {
                entry.idleTimer = idle
                entry.overallTimer = overall
                true
            } else {
                false
            }
        }
        if (installed) {
            idle.start()
            overall.start()
        } else {
            idle.cancel()
            overall.cancel()
        }
    }

    private suspend fun rearmIncomingIdleDeadline(entry: IncomingEntry) {
        val generation = lock.withLock {
            if (incoming[entry.session.transferId] !== entry || entry.phase != IncomingPhase.ACCEPTED) {
                return
            }
            ++entry.idleGeneration
        }
        val replacement = newIdleTimer(entry, generation)
        val old = lock.withLock {
            if (incoming[entry.session.transferId] !== entry ||
                entry.phase != IncomingPhase.ACCEPTED ||
                entry.idleGeneration != generation
            ) {
                null
            } else {
                entry.idleTimer.also { entry.idleTimer = replacement }
            }
        }
        if (old != null) {
            old.cancel()
            replacement.start()
        } else {
            replacement.cancel()
        }
    }

    private fun newIdleTimer(entry: IncomingEntry, generation: Long): Job =
        scope.launch(start = CoroutineStart.LAZY) {
            delay(config.acceptedIdleTimeoutMillis)
            timeoutAcceptedIncoming(entry, generation, "idle")
        }

    private suspend fun timeoutAcceptedIncoming(
        entry: IncomingEntry,
        requiredIdleGeneration: Long?,
        kind: String
    ) {
        val removed = lock.withLock {
            val current = incoming[entry.session.transferId]
            if (current !== entry || current.phase != IncomingPhase.ACCEPTED) return
            if (requiredIdleGeneration != null && current.idleGeneration != requiredIdleGeneration) return
            incoming.remove(entry.session.transferId)
            current
        }
        withContext(NonCancellable) {
            removed.session.setState(
                FileTransferState.Failed(
                    fileFailure(
                        kind = FileTransferFailureKind.TIMEOUT,
                        phase = FileTransferPhase.RECEIVE,
                        retryability = Retryability.RETRY_NEW_SESSION,
                        transferId = entry.session.transferId,
                        reason = "$kind transfer timeout after " +
                            (if (kind == "idle") {
                                config.acceptedIdleTimeoutMillis
                            } else {
                                config.acceptedOverallTimeoutMillis
                            }) + "ms"
                    )
                )
            )
            removed.cancelJobs()
            sendCleanupBestEffort("$kind-timeout FILE_CANCEL for ${entry.session.transferId}") {
                protocol.sendFileCancel(getConnection(), entry.session.transferId, "$kind transfer timeout")
            }
        }
    }

    private suspend fun compensateAmbiguousAccept(
        entry: IncomingEntry,
        terminalState: FileTransferState
    ) {
        withContext(NonCancellable) {
            removeIncoming(entry.session.transferId, entry)
            entry.cancelJobs()
            entry.session.setState(terminalState)
            try {
                withTimeout(config.offerTimeoutMillis) {
                    sendMutex.withLock {
                        protocol.sendFileCancel(
                            getConnection(),
                            entry.session.transferId,
                            "accept did not commit"
                        )
                    }
                }
            } catch (e: TimeoutCancellationException) {
                logger.debug(
                    "Session $sessionId: compensating FILE_CANCEL for " +
                        "${entry.session.transferId} failed: ${e.message}"
                )
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                logger.debug(
                    "Session $sessionId: compensating FILE_CANCEL for " +
                        "${entry.session.transferId} failed: ${e.message}"
                )
            }
        }
    }

    private suspend fun failIncomingTransfer(entry: IncomingEntry, prefix: String, cause: Throwable) {
        val protocolViolation = cause is P2pError.ProtocolError
        val err = failureFromCause(
            kind = if (protocolViolation) {
                FileTransferFailureKind.TRANSFER_PROTOCOL
            } else {
                FileTransferFailureKind.STORAGE
            },
            phase = if (protocolViolation) {
                FileTransferPhase.RECEIVE
            } else if (prefix.contains("finalize")) {
                FileTransferPhase.FLUSH
            } else {
                FileTransferPhase.RECEIVE
            },
            retryability = if (protocolViolation) {
                Retryability.NOT_RETRYABLE
            } else {
                Retryability.RETRY_AFTER_USER_ACTION
            },
            transferId = entry.session.transferId,
            prefix = prefix,
            cause = cause
        )
        removeIncoming(entry.session.transferId, entry)?.cancelJobs()
        entry.session.markFailed(err)
        sendBestEffort("FILE_CANCEL for ${entry.session.transferId}") {
            protocol.sendFileCancel(
                getConnection(),
                entry.session.transferId,
                "receive error: ${err.message}"
            )
        }
    }

    private suspend fun sendBestEffort(label: String, block: suspend () -> Unit) {
        try {
            sendMutex.withLock { block() }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            logger.debug("Session $sessionId: best-effort $label failed: ${e.message}")
        }
    }

    /** Bounded cleanup notification used only after ownership is already terminal. */
    private suspend fun sendCleanupBestEffort(label: String, block: suspend () -> Unit) {
        try {
            withTimeout(config.offerTimeoutMillis) {
                sendMutex.withLock { block() }
            }
        } catch (e: TimeoutCancellationException) {
            logger.debug("Session $sessionId: bounded cleanup $label timed out")
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            logger.debug("Session $sessionId: bounded cleanup $label failed: ${e.message}")
        }
    }

    private fun failureFromCause(
        kind: FileTransferFailureKind,
        phase: FileTransferPhase,
        retryability: Retryability,
        transferId: MessageId?,
        prefix: String,
        cause: Throwable
    ): P2pError = when (cause) {
        is P2pError.FileTransferFailed -> cause
        is P2pError.AuthenticationFailed -> cause
        else -> fileFailure(
            kind = kind,
            phase = phase,
            retryability = retryability,
            transferId = transferId,
            reason = "$prefix: " +
                (cause.message ?: cause::class.simpleName ?: "unknown failure")
                    .take(MAX_TRANSFER_FAILURE_REASON_CHARS),
            cause = cause
        )
    }

    private fun fileFailure(
        kind: FileTransferFailureKind,
        phase: FileTransferPhase,
        retryability: Retryability,
        transferId: MessageId?,
        reason: String,
        cause: Throwable? = null
    ): P2pError.FileTransferFailed = P2pError.FileTransferFailed(
        kind = kind,
        phase = phase,
        retryability = retryability,
        transferId = transferId?.toString(),
        reason = reason.take(MAX_TRANSFER_FAILURE_REASON_CHARS)
    ).also { it.underlying = cause }

    private suspend fun removeOutgoing(
        transferId: MessageId,
        expected: OutgoingEntry? = null
    ): OutgoingEntry? = lock.withLock {
        val current = outgoing[transferId] ?: return@withLock null
        if (expected != null && current !== expected) return@withLock null
        outgoing.remove(transferId)
    }

    private suspend fun removeIncoming(
        transferId: MessageId,
        expected: IncomingEntry? = null
    ): IncomingEntry? = lock.withLock {
        val current = incoming[transferId] ?: return@withLock null
        if (expected != null && current !== expected) return@withLock null
        incoming.remove(transferId)
        removePendingOfferLocked(current.session)
        current
    }

    private fun removePendingOfferLocked(session: IncomingFileSession) {
        val current = _pendingFileOffers.value
        if (current.none { it === session }) return
        _pendingFileOffers.value = immutableListSnapshot(current.filterNot { it === session })
    }

    private fun allocateTransferIdLocked(): MessageId {
        repeat(MAX_TRANSFER_ID_ATTEMPTS) {
            val candidate = MessageId.random(random)
            if (candidate !in outgoing && candidate !in incoming) return candidate
        }
        throw fileFailure(
            kind = FileTransferFailureKind.TRANSFER_PROTOCOL,
            phase = FileTransferPhase.OFFER,
            retryability = Retryability.RETRY_NEW_SESSION,
            transferId = null,
            reason = "Unable to allocate a unique transfer id after $MAX_TRANSFER_ID_ATTEMPTS attempts"
        )
    }

    private fun requireSupportedChunkCount(sizeBytes: Long) {
        if (!hasSupportedChunkCount(sizeBytes)) {
            throw fileFailure(
                kind = FileTransferFailureKind.INVALID_METADATA,
                phase = FileTransferPhase.OFFER,
                retryability = Retryability.NOT_RETRYABLE,
                transferId = null,
                reason = "Transfer requires more than ${Int.MAX_VALUE} chunks " +
                    "for chunkSizeBytes=${config.chunkSizeBytes}"
            )
        }
    }

    private fun hasSupportedChunkCount(sizeBytes: Long): Boolean {
        if (sizeBytes == 0L) return true
        val count = 1L + (sizeBytes - 1L) / config.chunkSizeBytes.toLong()
        return count <= Int.MAX_VALUE.toLong()
    }

    private fun OutgoingEntry.cancelJobs() {
        timer?.cancel()
        sender?.cancel()
        timer = null
        sender = null
    }

    private fun IncomingEntry.cancelJobs() {
        offerTimer?.cancel()
        idleTimer?.cancel()
        overallTimer?.cancel()
        offerTimer = null
        idleTimer = null
        overallTimer = null
    }

    private sealed interface OfferInsertion {
        data object CLOSED : OfferInsertion
        data object EXACT_DUPLICATE : OfferInsertion
        data object CONFLICT : OfferInsertion
        data object CAPACITY : OfferInsertion
        data class Inserted(val entry: IncomingEntry) : OfferInsertion
    }

    private sealed interface RejectResult {
        data class InvalidTransition(val state: FileTransferState) : RejectResult
        data class Removed(val entry: OutgoingEntry) : RejectResult
    }
}

private const val MAX_PENDING_INCOMING_OFFERS: Int = 64
private const val MAX_TRANSFER_ID_ATTEMPTS: Int = 128
private const val MAX_TRANSFER_FAILURE_REASON_CHARS: Int = 512
