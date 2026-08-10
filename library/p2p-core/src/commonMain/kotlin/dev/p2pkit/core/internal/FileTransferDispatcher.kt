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
import dev.p2pkit.core.protocol.ProtocolSessionState
import dev.p2pkit.core.protocol.ProtocolFeatures
import dev.p2pkit.core.protocol.SecureFileCommit
import dev.p2pkit.core.protocol.SecureFileFinish
import dev.p2pkit.core.protocol.SecureFileOffer
import dev.p2pkit.core.protocol.SecureFileResult
import dev.p2pkit.core.protocol.FileResultCode
import dev.p2pkit.core.internal.security.Sha256Hasher
import dev.p2pkit.core.transfer.FileTransferDestination
import dev.p2pkit.core.protocol.streamFileData
import dev.p2pkit.core.transfer.FileTransferConfig
import dev.p2pkit.core.transfer.FileTransferState
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.core.transfer.PreparedFileSource
import dev.p2pkit.core.transfer.Sha256Digest
import dev.p2pkit.core.transfer.acceptedIdleTimeoutMillis
import dev.p2pkit.core.transfer.acceptedOverallTimeoutMillis
import dev.p2pkit.core.transfer.commitTimeoutMillis
import dev.p2pkit.core.transfer.isTerminal
import dev.p2pkit.core.transfer.outgoingOfferWatchdogMillis
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
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
    private val getProtocolState: () -> ProtocolSessionState = { ProtocolSessionState.legacy() },
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

    /**
     * Referential write generation. [reopen] replaces it while the session
     * owns [sendMutex] across its raw-connection swap. Every transfer entry
     * retains the generation in which it was admitted, so an application
     * coroutine queued before reconnect is rejected after acquiring the mutex
     * instead of resolving [getConnection] to the replacement stream.
     */
    @Volatile
    private var writeEpoch: FileTransferWriteEpoch = FileTransferWriteEpoch()

    private enum class OutgoingPhase { OFFERED, STREAMING, COMMIT_WAIT }

    private class OutgoingEntry(
        val handle: OutgoingFileTransferImpl,
        val writeEpoch: FileTransferWriteEpoch,
        @Volatile
        var phase: OutgoingPhase = OutgoingPhase.OFFERED,
        var timer: Job? = null,
        var sender: Job? = null
    )

    private enum class IncomingPhase { OFFERED, ACCEPTING, ACCEPTED }

    private class IncomingEntry(
        val session: IncomingFileSession,
        val payload: FileOfferPayload,
        val secureOffer: SecureFileOffer?,
        val writeEpoch: FileTransferWriteEpoch,
        @Volatile
        var phase: IncomingPhase = IncomingPhase.OFFERED,
        var offerTimer: Job? = null,
        var idleTimer: Job? = null,
        var overallTimer: Job? = null,
        var idleGeneration: Long = 0L,
        val acceptanceCommitted: CompletableDeferred<Boolean> = CompletableDeferred()
    )

    // ---- Outgoing API ----

    suspend fun sendFile(
        name: String,
        sizeBytes: Long,
        mimeType: String?,
        source: RawSource
    ): P2pFileTransfer {
        if (getProtocolState().secure) {
            throw fileFailure(
                kind = FileTransferFailureKind.UNSUPPORTED_FEATURE,
                phase = FileTransferPhase.OFFER,
                retryability = Retryability.NOT_RETRYABLE,
                transferId = null,
                reason = "Authenticated file transfer requires a PreparedFileSource"
            )
        }
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
                OutgoingEntry(handle, writeEpoch).also { outgoing[transferId] = it }
            }
        } catch (e: Throwable) {
            runCatching { source.close() }
            throw e
        }

        val transferId = entry.handle.transferId
        try {
            withEpochWrite(entry.writeEpoch) { connection ->
                protocol.sendFileOffer(connection, transferId, payload)
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

    suspend fun sendPreparedFile(
        name: String,
        mimeType: String?,
        source: PreparedFileSource
    ): P2pFileTransfer {
        val state = getProtocolState()
        if (!state.secure || !state.supports(ProtocolFeatures.FILE_COMMIT_SHA256_V1)) {
            throw fileFailure(
                kind = FileTransferFailureKind.UNSUPPORTED_FEATURE,
                phase = FileTransferPhase.OFFER,
                retryability = Retryability.NOT_RETRYABLE,
                transferId = null,
                reason = "Peer did not negotiate ${ProtocolFeatures.FILE_COMMIT_SHA256_V1}"
            )
        }
        val sizeBytes: Long
        val expectedDigest: Sha256Digest
        try {
            sizeBytes = source.sizeBytes
            expectedDigest = source.sha256
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            throw failureFromCause(
                kind = FileTransferFailureKind.SOURCE_IO,
                phase = FileTransferPhase.SOURCE_READ,
                retryability = Retryability.RETRY_AFTER_USER_ACTION,
                transferId = null,
                prefix = "prepared source snapshot failed",
                cause = e
            )
        }
        if (sizeBytes < 0L) {
            throw fileFailure(
                kind = FileTransferFailureKind.INVALID_METADATA,
                phase = FileTransferPhase.OFFER,
                retryability = Retryability.NOT_RETRYABLE,
                transferId = null,
                reason = "Prepared source sizeBytes must be non-negative"
            )
        }
        if (sizeBytes > config.maxFileSizeBytes) {
            throw P2pError.PayloadTooLarge(config.maxFileSizeBytes, sizeBytes)
        }
        requireSupportedChunkCount(sizeBytes)
        val base = FileOfferPayload(name, sizeBytes, mimeType)
        try {
            FileOfferPayload.validate(base)
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

        val pair = lock.withLock {
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
            val secureOffer = SecureFileOffer.create(
                transferId, name, sizeBytes, mimeType, expectedDigest
            )
            val handle = OutgoingFileTransferImpl(
                peer = remotePeer,
                name = name,
                sizeBytes = sizeBytes,
                mimeType = mimeType,
                transferId = transferId,
                source = null,
                preparedSource = source,
                expectedDigest = expectedDigest,
                offerHash = secureOffer.offerHash,
                dispatcher = this
            )
            OutgoingEntry(handle, writeEpoch).also { outgoing[transferId] = it } to secureOffer
        }
        val entry = pair.first
        val secureOffer = pair.second
        try {
            withEpochWrite(entry.writeEpoch) { connection ->
                protocol.sendSecureFileOffer(connection, secureOffer)
            }
        } catch (e: CancellationException) {
            removeOutgoing(entry.handle.transferId, entry)?.cancelJobs()
            withContext(NonCancellable) {
                entry.handle.setState(FileTransferState.Cancelled("sendFile cancelled before FILE_OFFER was written"))
            }
            throw e
        } catch (e: Throwable) {
            val error = failureFromCause(
                FileTransferFailureKind.TRANSPORT,
                FileTransferPhase.OFFER,
                Retryability.RETRY_NEW_SESSION,
                entry.handle.transferId,
                "FILE_OFFER write failed",
                e
            )
            removeOutgoing(entry.handle.transferId, entry)?.cancelJobs()
            entry.handle.markFailed(error)
            throw error
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
        sendBestEffort("FILE_CANCEL for ${handle.transferId}", entry.writeEpoch) { connection ->
            protocol.sendFileCancel(connection, handle.transferId, reason)
        }
    }

    // ---- Incoming API ----

    suspend fun acceptOffer(session: IncomingFileSession, sink: RawSink): P2pFileTransfer {
        if (session.secureOffer != null) {
            throw fileFailure(
                kind = FileTransferFailureKind.UNSUPPORTED_FEATURE,
                phase = FileTransferPhase.ACCEPT,
                retryability = Retryability.NOT_RETRYABLE,
                transferId = session.transferId,
                reason = "Authenticated file transfer requires a FileTransferDestination"
            )
        }
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
                withEpochWrite(entry.writeEpoch) { connection ->
                    protocol.sendFileAccept(connection, session.transferId)
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
        entry.acceptanceCommitted.complete(committed)
        if (committed) armAcceptedDeadlines(entry)
        return session
    }

    suspend fun acceptOffer(
        session: IncomingFileSession,
        destination: FileTransferDestination
    ): P2pFileTransfer {
        if (session.secureOffer == null) {
            throw fileFailure(
                kind = FileTransferFailureKind.UNSUPPORTED_FEATURE,
                phase = FileTransferPhase.ACCEPT,
                retryability = Retryability.NOT_RETRYABLE,
                transferId = session.transferId,
                reason = "Legacy file transfer does not support durable destinations"
            )
        }
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
        val sink = try {
            destination.openSink()
        } catch (e: CancellationException) {
            removeIncoming(session.transferId, entry)?.cancelJobs()
            withContext(NonCancellable) {
                runCatching { destination.abort(null) }
                session.setState(FileTransferState.Cancelled("accept cancelled while opening destination"))
            }
            throw e
        } catch (e: Throwable) {
            val error = failureFromCause(
                FileTransferFailureKind.STORAGE,
                FileTransferPhase.ACCEPT,
                Retryability.RETRY_AFTER_USER_ACTION,
                session.transferId,
                "destination open failed",
                e
            ) as P2pError.FileTransferFailed
            removeIncoming(session.transferId, entry)?.cancelJobs()
            runCatching { destination.abort(error) }
            session.markFailed(error)
            throw error
        }
        val installed = try {
            session.installReceiver(sink, destination)
        } catch (e: CancellationException) {
            removeIncoming(session.transferId, entry)?.cancelJobs()
            withContext(NonCancellable) {
                runCatching { destination.abort(null) }
                session.setState(FileTransferState.Cancelled("accept cancelled while installing destination"))
            }
            throw e
        } catch (e: Throwable) {
            val error = failureFromCause(
                FileTransferFailureKind.STORAGE,
                FileTransferPhase.ACCEPT,
                Retryability.RETRY_AFTER_USER_ACTION,
                session.transferId,
                "destination install failed",
                e
            ) as P2pError.FileTransferFailed
            removeIncoming(session.transferId, entry)?.cancelJobs()
            runCatching { destination.abort(error) }
            session.markFailed(error)
            throw error
        }
        if (!installed) {
            removeIncoming(session.transferId, entry)?.cancelJobs()
            runCatching { destination.abort(null) }
            throw IllegalStateException("Offer ${session.id} became terminal during acceptance")
        }
        try {
            withTimeout(config.offerTimeoutMillis) {
                withEpochWrite(entry.writeEpoch) { connection ->
                    protocol.sendSecureFileAccept(connection, session.transferId)
                }
            }
            currentCoroutineContext().ensureActive()
        } catch (e: TimeoutCancellationException) {
            val error = fileFailure(
                FileTransferFailureKind.TIMEOUT,
                FileTransferPhase.ACCEPT,
                Retryability.RETRY_NEW_SESSION,
                session.transferId,
                "FILE_ACCEPT write did not finish within ${config.offerTimeoutMillis}ms",
                e
            )
            compensateAmbiguousAccept(entry, FileTransferState.Failed(error))
            throw error
        } catch (e: CancellationException) {
            compensateAmbiguousAccept(entry,
                FileTransferState.Cancelled("accept cancelled while FILE_ACCEPT was in flight"))
            throw e
        } catch (e: Throwable) {
            val error = failureFromCause(
                FileTransferFailureKind.TRANSPORT,
                FileTransferPhase.ACCEPT,
                Retryability.RETRY_NEW_SESSION,
                session.transferId,
                "FILE_ACCEPT write failed",
                e
            )
            compensateAmbiguousAccept(entry, FileTransferState.Failed(error))
            throw error
        }
        val committed = lock.withLock {
            val current = incoming[session.transferId]
            if (current === entry && current.phase == IncomingPhase.ACCEPTING) {
                current.phase = IncomingPhase.ACCEPTED
                removePendingOfferLocked(current.session)
                true
            } else false
        }
        entry.acceptanceCommitted.complete(committed)
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
        entry.acceptanceCommitted.complete(false)
        entry.cancelJobs()
        session.setState(FileTransferState.Rejected(reason))
        sendBestEffort("FILE_REJECT for ${session.transferId}", entry.writeEpoch) { connection ->
            protocol.sendFileReject(connection, session.transferId, reason)
        }
    }

    suspend fun cancelIncoming(session: IncomingFileSession, reason: String?) {
        val entry = lock.withLock {
            val current = incoming.remove(session.transferId) ?: return
            removePendingOfferLocked(current.session)
            current
        }
        entry.acceptanceCommitted.complete(false)
        val accepted = entry.phase != IncomingPhase.OFFERED
        val changed = withContext(NonCancellable) {
            val changed = session.setState(FileTransferState.Cancelled(reason))
            entry.cancelJobs()
            changed
        }
        if (!changed) return
        sendBestEffort("cancel for ${session.transferId}", entry.writeEpoch) { connection ->
            if (accepted) {
                protocol.sendFileCancel(connection, session.transferId, reason)
            } else {
                protocol.sendFileReject(connection, session.transferId, reason)
            }
        }
    }

    // ---- Inbound protocol events ----

    suspend fun onFileOffer(
        transferId: MessageId,
        payload: FileOfferPayload,
        secureOffer: SecureFileOffer? = null
    ) {
        if (closed) return
        val eventEpoch = writeEpoch
        if (payload.sizeBytes > config.maxFileSizeBytes || !hasSupportedChunkCount(payload.sizeBytes)) {
            val reason = if (payload.sizeBytes > config.maxFileSizeBytes) {
                "sizeBytes ${payload.sizeBytes} exceeds maxFileSizeBytes ${config.maxFileSizeBytes}"
            } else {
                "file requires more than ${Int.MAX_VALUE} chunks"
            }
            sendBestEffort("FILE_REJECT for $transferId", eventEpoch) { connection ->
                protocol.sendFileReject(connection, transferId, reason)
            }
            return
        }

        val session = IncomingFileSession(
            peer = remotePeer,
            name = payload.name,
            sizeBytes = payload.sizeBytes,
            mimeType = payload.mimeType,
            transferId = transferId,
            secureOffer = secureOffer,
            dispatcher = this
        )
        val insertion = lock.withLock {
            val existingIncoming = incoming[transferId]
            when {
                closed -> OfferInsertion.CLOSED
                existingIncoming != null && existingIncoming.payload == payload &&
                    existingIncoming.secureOffer == secureOffer ->
                    OfferInsertion.EXACT_DUPLICATE
                existingIncoming != null -> OfferInsertion.CONFLICT
                outgoing.containsKey(transferId) -> OfferInsertion.CONFLICT
                incoming.size >= MAX_PENDING_INCOMING_OFFERS -> OfferInsertion.CAPACITY
                else -> {
                    val entry = IncomingEntry(session, payload, secureOffer, eventEpoch)
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
                sendBestEffort("capacity FILE_REJECT for $transferId", eventEpoch) { connection ->
                    protocol.sendFileReject(connection, transferId, "too many pending offers")
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
            if (entry.secureOffer != null) {
                failIncomingSecureTransfer(
                    entry,
                    if (e is P2pError.ProtocolError) {
                        FileResultCode.PROTOCOL_FAILURE
                    } else {
                        FileResultCode.STORAGE_FAILURE
                    },
                    FileTransferPhase.RECEIVE,
                    e.message ?: "file receive write failed",
                    e
                )
            } else {
                failIncomingTransfer(entry, "file receive write failed", e)
            }
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
        if (entry.secureOffer != null) {
            failIncomingSecureTransfer(
                entry,
                FileResultCode.PROTOCOL_FAILURE,
                FileTransferPhase.VERIFY,
                "legacy FILE_DONE received for authenticated transfer",
                P2pError.ProtocolError("Authenticated transfer requires FILE_FINISH")
            )
            return
        }
        try {
            val completed = entry.session.finishLegacyReceiver()
            if (completed) removeIncoming(transferId, entry)?.cancelJobs()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            failIncomingTransfer(entry, "file receive finalize failed", e)
        }
    }

    suspend fun onFileFinish(finish: SecureFileFinish) {
        val entry = lock.withLock { incoming[finish.transferId] }
        if (entry == null) {
            logger.debug("Session $sessionId: FILE_FINISH for unknown transfer ${finish.transferId}; ignoring")
            return
        }
        if (entry.phase == IncomingPhase.ACCEPTING && !entry.acceptanceCommitted.await()) {
            return
        }
        if (entry.phase != IncomingPhase.ACCEPTED || entry.secureOffer == null) {
            val failure = P2pError.ProtocolError(
                "FILE_FINISH arrived before authenticated acceptance"
            )
            if (entry.secureOffer != null) {
                failIncomingSecureTransfer(
                    entry,
                    FileResultCode.PROTOCOL_FAILURE,
                    FileTransferPhase.VERIFY,
                    "invalid FILE_FINISH transition",
                    failure
                )
            } else {
                failIncomingTransfer(entry, "invalid FILE_FINISH transition", failure)
            }
            return
        }
        entry.idleTimer?.cancel()
        entry.overallTimer?.cancel()
        try {
            val committed = withTimeout(config.commitTimeoutMillis) {
                entry.session.verifyAndCommit(finish)
            }
            if (!committed) return
            removeIncoming(finish.transferId, entry)?.cancelJobs()
            val offer = checkNotNull(entry.secureOffer)
            try {
                withEpochWrite(entry.writeEpoch) { connection ->
                    protocol.sendFileCommit(
                        connection,
                        SecureFileCommit(
                            finish.transferId,
                            finish.sizeBytes,
                            finish.contentDigest,
                            offer.offerHash
                        )
                    )
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                logger.warn(
                    "Session $sessionId: durable transfer ${finish.transferId} committed but " +
                        "FILE_COMMIT write failed",
                    e
                )
            }
        } catch (e: TimeoutCancellationException) {
            failIncomingSecureTransfer(
                entry,
                FileResultCode.TIMEOUT,
                FileTransferPhase.DURABLE_COMMIT,
                "receiver durable commit timed out after ${config.commitTimeoutMillis}ms",
                e
            )
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            val failed = e as? P2pError.FileTransferFailed
            val code = when (failed?.kind) {
                FileTransferFailureKind.INTEGRITY -> FileResultCode.DIGEST_MISMATCH
                FileTransferFailureKind.STORAGE -> FileResultCode.STORAGE_FAILURE
                else -> if (e is P2pError.ProtocolError) {
                    FileResultCode.PROTOCOL_FAILURE
                } else {
                    FileResultCode.STORAGE_FAILURE
                }
            }
            val phase = failed?.phase ?: if (e is P2pError.ProtocolError) {
                FileTransferPhase.VERIFY
            } else {
                FileTransferPhase.DURABLE_COMMIT
            }
            failIncomingSecureTransfer(
                entry,
                code,
                phase,
                e.message ?: "receiver commit failed",
                e
            )
        }
    }

    suspend fun onFileCommit(commit: SecureFileCommit) {
        val result = lock.withLock {
            val current = outgoing[commit.transferId] ?: return
            if (current.phase != OutgoingPhase.COMMIT_WAIT) {
                outgoing.remove(commit.transferId)
                return@withLock CommitResult.InvalidTransition(current, current.phase)
            }
            val expectedDigest = current.handle.expectedDigest
            val expectedOfferHash = current.handle.offerHash
            if (commit.sizeBytes != current.handle.sizeBytes ||
                commit.contentDigest != expectedDigest || commit.offerHash != expectedOfferHash
            ) {
                outgoing.remove(commit.transferId)
                CommitResult.Mismatch(current)
            } else {
                outgoing.remove(commit.transferId)
                CommitResult.Committed(current)
            }
        }
        result.entry.cancelJobs()
        when (result) {
            is CommitResult.Committed -> result.entry.handle.setState(FileTransferState.Completed)
            is CommitResult.Mismatch -> result.entry.handle.markFailed(
                fileFailure(
                    FileTransferFailureKind.INTEGRITY,
                    FileTransferPhase.DURABLE_COMMIT,
                    Retryability.NOT_RETRYABLE,
                    commit.transferId,
                    "FILE_COMMIT does not match the authenticated offer"
                )
            )
            is CommitResult.InvalidTransition -> result.entry.handle.markFailed(
                fileFailure(
                    FileTransferFailureKind.TRANSFER_PROTOCOL,
                    FileTransferPhase.DURABLE_COMMIT,
                    Retryability.NOT_RETRYABLE,
                    commit.transferId,
                    "FILE_COMMIT arrived while sender was ${result.phase}"
                )
            )
        }
    }

    suspend fun onFileResult(result: SecureFileResult) {
        val outgoingEntry = removeOutgoing(result.transferId)
        if (outgoingEntry != null) {
            outgoingEntry.cancelJobs()
            outgoingEntry.handle.markFailed(result.toPublicFailure())
            return
        }
        val incomingEntry = removeIncoming(result.transferId)
        if (incomingEntry != null) {
            incomingEntry.cancelJobs()
            incomingEntry.session.markFailed(result.toPublicFailure())
            return
        }
        logger.debug("Session $sessionId: FILE_RESULT for unknown transfer ${result.transferId}; ignoring")
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

    /**
     * Admit a fresh connection epoch after [beginCloseAll] and
     * [awaitCloseAll] have settled the previous one. The owning session holds
     * [sendMutex] across its raw-connection swap and this transition.
     */
    fun reopen() {
        check(closed) { "File-transfer dispatcher can reopen only after closeAll" }
        writeEpoch = FileTransferWriteEpoch()
        closed = false
    }

    suspend fun closeAll(
        reason: String,
        failureKind: FileTransferFailureKind = FileTransferFailureKind.REMOTE_DISCONNECTED,
        retryability: Retryability = Retryability.RETRY_NEW_SESSION
    ) {
        awaitCloseAll(beginCloseAll(reason, failureKind, retryability))
    }

    /**
     * Atomically seals transfer admission, removes every owned entry, requests
     * cancellation, and terminalizes public handles. The returned jobs remain
     * owned by the caller until [awaitCloseAll] settles them.
     *
     * The session lifecycle intentionally invokes this phase before closing
     * the raw stream, then closes the stream to unblock stalled writers, and
     * only then awaits the returned jobs. Direct callers use [closeAll], which
     * composes both phases without a raw-stream step.
     */
    suspend fun beginCloseAll(
        reason: String,
        failureKind: FileTransferFailureKind = FileTransferFailureKind.REMOTE_DISCONNECTED,
        retryability: Retryability = Retryability.RETRY_NEW_SESSION
    ): List<Job> {
        closed = true
        val jobsToJoin = mutableSetOf<Job>()
        val (outgoingEntries, incomingEntries) = lock.withLock {
            val outs = outgoing.values.toList().also { outgoing.clear() }
            val ins = incoming.values.toList().also { incoming.clear() }
            _pendingFileOffers.value = immutableListSnapshot(emptyList())
            outs to ins
        }
        for (entry in outgoingEntries) {
            jobsToJoin += entry.cancelJobs()
            entry.handle.markFailed(
                fileFailure(
                    kind = failureKind,
                    phase = when (entry.phase) {
                        OutgoingPhase.OFFERED -> FileTransferPhase.OFFER
                        OutgoingPhase.STREAMING -> FileTransferPhase.SEND
                        OutgoingPhase.COMMIT_WAIT -> FileTransferPhase.DURABLE_COMMIT
                    },
                    retryability = retryability,
                    transferId = entry.handle.transferId,
                    reason = reason
                )
            )
        }
        for (entry in incomingEntries) {
            jobsToJoin += entry.cancelJobs()
            entry.acceptanceCommitted.complete(false)
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
        }

        return jobsToJoin.toList()
    }

    /** Settle the ownership returned by [beginCloseAll] before any reopen. */
    suspend fun awaitCloseAll(jobsToJoin: List<Job>) {
        // A reconnect may reopen this dispatcher against a different raw
        // stream immediately after settlement. Cancellation alone is
        // insufficient: a source read or protocol implementation can delay
        // observing cancellation. The write-generation check prevents such a
        // job from reaching the replacement stream; joining additionally
        // proves that every job owned by the previous epoch has terminated.
        val callerJob = currentCoroutineContext()[Job]
        for (job in jobsToJoin) {
            if (job !== callerJob) job.join()
        }
    }

    // ---- Timers and ownership helpers ----

    private suspend fun streamOutgoingPayload(entry: OutgoingEntry) {
        val handle = entry.handle
        if (handle.state.value.isTerminal()) return
        var connectionWriteFailure = false
        val expectedDigest = handle.expectedDigest
        val hasher = expectedDigest?.let { Sha256Hasher() }
        try {
            if (handle.preparedSource != null) handle.openPreparedSource()
            if (handle.sizeBytes > 0L) handle.setState(FileTransferState.Sending(0f))
            streamFileData(
                transferId = handle.transferId,
                rawSource = handle.sourceOrThrow(),
                sizeBytes = handle.sizeBytes,
                chunkSizeBytes = config.chunkSizeBytes
            ).collect { frame ->
                hasher?.update(frame.payload)
                try {
                    withEpochWrite(entry.writeEpoch) { connection ->
                        protocol.sendFileDataFrame(connection, frame)
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
            if (expectedDigest != null) {
                val actualDigest = checkNotNull(hasher).finish()
                if (actualDigest != expectedDigest) {
                    val error = fileFailure(
                        FileTransferFailureKind.SOURCE_CHANGED,
                        FileTransferPhase.SOURCE_READ,
                        Retryability.RETRY_AFTER_USER_ACTION,
                        handle.transferId,
                        "Prepared source SHA-256 changed before or during streaming"
                    )
                    val removed = removeOutgoing(handle.transferId, entry)
                    handle.markFailed(error)
                    sendBestEffort(
                        "SOURCE_CHANGED FILE_RESULT for ${handle.transferId}",
                        entry.writeEpoch
                    ) { connection ->
                        protocol.sendFileResult(
                            connection,
                            SecureFileResult(
                                handle.transferId,
                                FileResultCode.SOURCE_CHANGED,
                                FileTransferPhase.SOURCE_READ,
                                error.message
                            )
                        )
                    }
                    removed?.cancelJobs()
                    return
                }
                val transitioned = lock.withLock {
                    if (outgoing[handle.transferId] === entry && entry.phase == OutgoingPhase.STREAMING) {
                        entry.phase = OutgoingPhase.COMMIT_WAIT
                        true
                    } else false
                }
                if (!transitioned) return
                try {
                    withEpochWrite(entry.writeEpoch) { connection ->
                        protocol.sendFileFinish(
                            connection,
                            SecureFileFinish(
                                handle.transferId,
                                handle.sizeBytes,
                                chunkCount(handle.sizeBytes),
                                actualDigest,
                                checkNotNull(handle.offerHash)
                            )
                        )
                    }
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Throwable) {
                    connectionWriteFailure = true
                    throw e
                }
                armOutgoingCommitWatchdog(entry)
                return
            }
            try {
                withEpochWrite(entry.writeEpoch) { connection ->
                    protocol.sendFileDone(connection, handle.transferId)
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
                sendBestEffort(
                    "FILE_CANCEL for ${handle.transferId}",
                    entry.writeEpoch
                ) { connection ->
                    protocol.sendFileCancel(
                        connection,
                        handle.transferId,
                        "sender source failure: ${err.message}"
                    )
                }
            }
        }
    }

    private fun chunkCount(sizeBytes: Long): Int = if (sizeBytes == 0L) {
        0
    } else {
        (1L + (sizeBytes - 1L) / config.chunkSizeBytes.toLong()).toInt()
    }

    private suspend fun armOutgoingCommitWatchdog(entry: OutgoingEntry) {
        val job = scope.launch(start = CoroutineStart.LAZY) {
            delay(config.commitTimeoutMillis)
            val removed = lock.withLock {
                val current = outgoing[entry.handle.transferId]
                if (current !== entry || current.phase != OutgoingPhase.COMMIT_WAIT) return@launch
                outgoing.remove(entry.handle.transferId)
                current
            }
            removed.handle.markFailed(
                fileFailure(
                    FileTransferFailureKind.TIMEOUT,
                    FileTransferPhase.DURABLE_COMMIT,
                    Retryability.RETRY_NEW_SESSION,
                    removed.handle.transferId,
                    "FILE_COMMIT not received within ${config.commitTimeoutMillis}ms"
                )
            )
            removed.cancelJobs()
        }
        val installed = lock.withLock {
            if (outgoing[entry.handle.transferId] === entry && entry.phase == OutgoingPhase.COMMIT_WAIT) {
                entry.timer = job
                true
            } else false
        }
        if (installed) job.start() else job.cancel()
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
        sendBestEffort(
            "offer-watchdog FILE_CANCEL for ${entry.handle.transferId}",
            entry.writeEpoch
        ) { connection ->
            protocol.sendFileCancel(
                connection,
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
        removed.acceptanceCommitted.complete(false)
        withContext(NonCancellable) {
            removed.session.setState(FileTransferState.Rejected("timeout"))
            removed.cancelJobs()
            sendCleanupBestEffort(
                "timeout FILE_REJECT for ${entry.session.transferId}",
                entry.writeEpoch
            ) { connection ->
                protocol.sendFileReject(connection, entry.session.transferId, "timeout")
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
            sendCleanupBestEffort(
                "$kind-timeout terminal for ${entry.session.transferId}",
                entry.writeEpoch
            ) { connection ->
                if (entry.secureOffer != null) {
                    protocol.sendFileResult(
                        connection,
                        SecureFileResult(
                            entry.session.transferId,
                            FileResultCode.TIMEOUT,
                            FileTransferPhase.RECEIVE,
                            "$kind transfer timeout"
                        )
                    )
                } else {
                    protocol.sendFileCancel(connection, entry.session.transferId, "$kind transfer timeout")
                }
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
                    withEpochWrite(entry.writeEpoch) { connection ->
                        protocol.sendFileCancel(
                            connection,
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
        sendBestEffort("FILE_CANCEL for ${entry.session.transferId}", entry.writeEpoch) { connection ->
            protocol.sendFileCancel(
                connection,
                entry.session.transferId,
                "receive error: ${err.message}"
            )
        }
    }

    private suspend fun failIncomingSecureTransfer(
        entry: IncomingEntry,
        code: FileResultCode,
        phase: FileTransferPhase,
        reason: String,
        cause: Throwable
    ) {
        val kind = when (code) {
            FileResultCode.DIGEST_MISMATCH -> FileTransferFailureKind.INTEGRITY
            FileResultCode.STORAGE_FAILURE -> FileTransferFailureKind.STORAGE
            FileResultCode.PROTOCOL_FAILURE -> FileTransferFailureKind.TRANSFER_PROTOCOL
            FileResultCode.SOURCE_CHANGED -> FileTransferFailureKind.SOURCE_CHANGED
            FileResultCode.TIMEOUT -> FileTransferFailureKind.TIMEOUT
        }
        val retryability = when (code) {
            FileResultCode.STORAGE_FAILURE -> Retryability.RETRY_AFTER_USER_ACTION
            FileResultCode.TIMEOUT -> Retryability.RETRY_NEW_SESSION
            else -> Retryability.NOT_RETRYABLE
        }
        val error = fileFailure(
            kind,
            phase,
            retryability,
            entry.session.transferId,
            reason,
            cause
        )
        removeIncoming(entry.session.transferId, entry)?.cancelJobs()
        entry.session.markFailed(error)
        sendBestEffort("FILE_RESULT for ${entry.session.transferId}", entry.writeEpoch) { connection ->
            protocol.sendFileResult(
                connection,
                SecureFileResult(entry.session.transferId, code, phase, error.message)
            )
        }
    }

    private suspend fun <T> withEpochWrite(
        expectedEpoch: FileTransferWriteEpoch,
        block: suspend (RawConnection) -> T
    ): T {
        sendMutex.lock()
        try {
            if (closed || writeEpoch !== expectedEpoch) {
                throw StaleFileTransferEpochException(
                    "Transfer operation belongs to a closed or replaced connection epoch"
                )
            }
            return block(getConnection())
        } finally {
            sendMutex.unlock()
        }
    }

    private suspend fun sendBestEffort(
        label: String,
        expectedEpoch: FileTransferWriteEpoch,
        block: suspend (RawConnection) -> Unit
    ) {
        try {
            withEpochWrite(expectedEpoch, block)
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            logger.debug("Session $sessionId: best-effort $label failed: ${e.message}")
        }
    }

    /** Bounded cleanup notification used only after ownership is already terminal. */
    private suspend fun sendCleanupBestEffort(
        label: String,
        expectedEpoch: FileTransferWriteEpoch,
        block: suspend (RawConnection) -> Unit
    ) {
        try {
            withTimeout(config.offerTimeoutMillis) {
                withEpochWrite(expectedEpoch, block)
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
        current.also { it.acceptanceCommitted.complete(false) }
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

    private fun OutgoingEntry.cancelJobs(): List<Job> {
        val jobs = listOfNotNull(timer, sender).distinct()
        timer?.cancel()
        sender?.cancel()
        timer = null
        sender = null
        return jobs
    }

    private fun IncomingEntry.cancelJobs(): List<Job> {
        val jobs = listOfNotNull(offerTimer, idleTimer, overallTimer).distinct()
        offerTimer?.cancel()
        idleTimer?.cancel()
        overallTimer?.cancel()
        offerTimer = null
        idleTimer = null
        overallTimer = null
        return jobs
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

    private sealed interface CommitResult {
        val entry: OutgoingEntry
        data class Committed(override val entry: OutgoingEntry) : CommitResult
        data class Mismatch(override val entry: OutgoingEntry) : CommitResult
        data class InvalidTransition(
            override val entry: OutgoingEntry,
            val phase: OutgoingPhase
        ) : CommitResult
    }
}

private const val MAX_PENDING_INCOMING_OFFERS: Int = 64
private const val MAX_TRANSFER_ID_ATTEMPTS: Int = 128
private const val MAX_TRANSFER_FAILURE_REASON_CHARS: Int = 512

/** Referential generation marker for dispatcher writes. */
private class FileTransferWriteEpoch

private class StaleFileTransferEpochException(message: String) : IllegalStateException(message)
