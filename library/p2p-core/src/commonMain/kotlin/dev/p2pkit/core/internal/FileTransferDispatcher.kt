package dev.p2pkit.core.internal

import dev.p2pkit.core.FileTransferFailureKind
import dev.p2pkit.core.FileTransferPhase
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.Retryability
import dev.p2pkit.core.internal.security.Sha256Hasher
import dev.p2pkit.core.protocol.FileOfferPayload
import dev.p2pkit.core.protocol.FileResultCode
import dev.p2pkit.core.protocol.Frame
import dev.p2pkit.core.protocol.MessageId
import dev.p2pkit.core.protocol.P2pProtocol
import dev.p2pkit.core.protocol.PreparedSourceLengthChangedException
import dev.p2pkit.core.protocol.ProtocolConstants
import dev.p2pkit.core.protocol.ProtocolFeatures
import dev.p2pkit.core.protocol.ProtocolSessionState
import dev.p2pkit.core.protocol.SecureFileCommit
import dev.p2pkit.core.protocol.SecureFileFinish
import dev.p2pkit.core.protocol.SecureFileOffer
import dev.p2pkit.core.protocol.SecureFileResult
import dev.p2pkit.core.protocol.streamFileData
import dev.p2pkit.core.protocol.validateWireText
import dev.p2pkit.core.transfer.FileTransferConfig
import dev.p2pkit.core.transfer.FileTransferDestination
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
import kotlinx.coroutines.CoroutineDispatcher
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
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
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.io.RawSink
import kotlinx.io.RawSource
import kotlin.concurrent.Volatile
import kotlin.coroutines.EmptyCoroutineContext
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
    private val logger: P2pLogger,
    private val independentOperationDispatcher: CoroutineDispatcher = blockingIoDispatcher(),
    private val independentCleanupDispatcher: CoroutineDispatcher =
        blockingApplicationCleanupDispatcher(),
    private val outgoingReadDispatcher: CoroutineDispatcher? = blockingFileReadDispatcher(),
    private val protocolOperationDispatcher: CoroutineDispatcher = blockingProtocolDispatcher(),
    private val operationDeadlineDispatcher: CoroutineDispatcher = Dispatchers.Default
) {

    private val incomingOffers = MutableSharedFlow<P2pFileOffer>(
        replay = 0,
        extraBufferCapacity = MAX_INCOMING_OFFER_EVENT_BUFFER,
        onBufferOverflow = BufferOverflow.SUSPEND
    )
    val incomingFiles: SharedFlow<P2pFileOffer> = incomingOffers.asSharedFlow()

    private val _pendingFileOffers = MutableStateFlow<List<P2pFileOffer>>(emptyList())
    val pendingFileOffers: StateFlow<List<P2pFileOffer>> = _pendingFileOffers.asStateFlow()

    private val outgoing: MutableMap<MessageId, OutgoingEntry> = mutableMapOf()
    private val incoming: MutableMap<MessageId, IncomingEntry> = mutableMapOf()

    /**
     * Authenticated inbound transactions that reached a terminal outcome in
     * the current connection epoch. Entries are never evicted within an
     * epoch: evicting one would let a delayed/replayed FILE_OFFER publish a
     * second application offer and potentially commit the same transaction
     * twice. Admission reserves one ledger slot for every live secure offer,
     * so terminal registration can remain atomic with map removal.
     */
    private val terminalIncoming: MutableMap<MessageId, TerminalIncomingTransaction> =
        mutableMapOf()
    private val ambiguousIncomingTransferIds: MutableSet<MessageId> = mutableSetOf()
    private var ambiguousIncomingCapacityExhausted: Boolean = false
    private val lock = Mutex()

    /**
     * Non-cooperative application callbacks and protocol writers run on
     * independent jobs so their callers retain a real deadline. Keep separate
     * admission gates: a wedged destination must not consume the capacity
     * needed to report its terminal result to the peer. A timed-out worker
     * retains its permit until it actually exits, bounding detached work even
     * when application/native code ignores cancellation indefinitely.
     */
    private val applicationOperationGate = Semaphore(MAX_CONCURRENT_FILE_OPERATIONS)
    private val cleanupOperationGate = Semaphore(MAX_CONCURRENT_FILE_OPERATIONS)
    private val protocolOperationGate = Semaphore(MAX_CONCURRENT_FILE_OPERATIONS)
    private val outgoingStreamGate = Semaphore(MAX_CONCURRENT_OUTGOING_STREAMS)

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
        var sender: Job? = null,
        var overallTimer: Job? = null,
        var idleGeneration: Long = 0L
    )

    private enum class IncomingPhase { OFFERED, ACCEPTING, ACCEPTED, FINALIZING }

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

    private data class TerminalIncomingTransaction(
        val offer: SecureFileOffer,
        val response: IncomingTerminalResponse
    )

    private sealed interface IncomingTerminalResponse {
        data class Commit(val value: SecureFileCommit) : IncomingTerminalResponse
        data class Result(val value: SecureFileResult) : IncomingTerminalResponse
        data class Reject(val reason: String?) : IncomingTerminalResponse
        data class Cancel(val reason: String?) : IncomingTerminalResponse
    }

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
                requireOutgoingCapacityLocked()
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
            withContext(NonCancellable) {
                cleanupOutgoingSource(source, "failed outgoing registration")
            }
            throw e
        }

        val transferId = entry.handle.transferId
        var offerWritten = false
        try {
            sendInitialOfferWithinDeadline(entry) { connection ->
                protocol.sendFileOffer(connection, transferId, payload)
            }
            offerWritten = true
            withContext(NonCancellable) { armOutgoingOfferWatchdog(entry) }
            currentCoroutineContext().ensureActive()
        } catch (e: CancellationException) {
            val removed = removeOutgoing(transferId, entry)
            removed?.cancelJobs()
            withContext(NonCancellable) {
                entry.handle.setState(
                    FileTransferState.Cancelled(
                        if (offerWritten) {
                            "sendFile cancelled after FILE_OFFER was written"
                        } else {
                            "sendFile cancelled before FILE_OFFER was written"
                        }
                    )
                )
                // A writer can put the complete offer on the wire and then
                // throw. An unknown FILE_CANCEL is harmless, whereas omitting
                // compensation can leave a remote retained offer alive.
                sendCleanupBestEffort(
                    "cancelled registration FILE_CANCEL for $transferId",
                    entry.writeEpoch
                ) { connection ->
                    protocol.sendFileCancel(connection, transferId, "sendFile was cancelled")
                }
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
            sendCleanupBestEffort(
                "failed registration FILE_CANCEL for $transferId",
                entry.writeEpoch
            ) { connection ->
                protocol.sendFileCancel(connection, transferId, "offer registration failed")
            }
            throw err
        }
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
        val sourceSnapshot = try {
            when (
                val result = runBoundedIndependentOperation(
                    timeoutMillis = config.offerTimeoutMillis,
                    preserveCancellation = false,
                    operationDispatcher = independentOperationDispatcher,
                    deadlineDispatcher = operationDeadlineDispatcher,
                    operationGate = applicationOperationGate
                ) {
                    PreparedSourceSnapshot(source.sizeBytes, source.sha256)
                }
            ) {
                is BoundedOperationResult.Success -> result.value
                is BoundedOperationResult.Failure -> throw classifyCallbackCancellation(
                    result.cause,
                    FileTransferFailureKind.SOURCE_IO,
                    FileTransferPhase.SOURCE_READ,
                    Retryability.RETRY_AFTER_USER_ACTION,
                    null,
                    "prepared source snapshot failed"
                )
                is BoundedOperationResult.TimedOut -> throw fileFailure(
                    kind = FileTransferFailureKind.TIMEOUT,
                    phase = FileTransferPhase.SOURCE_READ,
                    retryability = Retryability.RETRY_AFTER_USER_ACTION,
                    transferId = null,
                    reason = "prepared source snapshot did not finish within ${result.timeoutMillis}ms",
                    cause = result.cause
                )
            }
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
        val sizeBytes = sourceSnapshot.sizeBytes
        val expectedDigest = sourceSnapshot.sha256
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
            requireOutgoingCapacityLocked()
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
        var offerWritten = false
        try {
            sendInitialOfferWithinDeadline(entry) { connection ->
                protocol.sendSecureFileOffer(connection, secureOffer)
            }
            offerWritten = true
            withContext(NonCancellable) { armOutgoingOfferWatchdog(entry) }
            currentCoroutineContext().ensureActive()
        } catch (e: CancellationException) {
            removeOutgoing(entry.handle.transferId, entry)?.cancelJobs()
            withContext(NonCancellable) {
                entry.handle.setState(
                    FileTransferState.Cancelled(
                        if (offerWritten) {
                            "sendFile cancelled after FILE_OFFER was written"
                        } else {
                            "sendFile cancelled before FILE_OFFER was written"
                        }
                    )
                )
                sendCleanupBestEffort(
                    "cancelled registration FILE_CANCEL for ${entry.handle.transferId}",
                    entry.writeEpoch
                ) { connection ->
                    protocol.sendFileCancel(
                        connection,
                        entry.handle.transferId,
                        "sendFile was cancelled"
                    )
                }
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
            sendCleanupBestEffort(
                "failed registration FILE_CANCEL for ${entry.handle.transferId}",
                entry.writeEpoch
            ) { connection ->
                protocol.sendFileCancel(
                    connection,
                    entry.handle.transferId,
                    "offer registration failed"
                )
            }
            throw error
        }
        return entry.handle
    }

    suspend fun cancelOutgoing(handle: OutgoingFileTransferImpl, reason: String?) {
        val entry = lock.withLock {
            val current = outgoing[handle.transferId] ?: return
            if (current.handle !== handle) return
            outgoing.remove(handle.transferId)
            current
        }
        val changed = withContext(NonCancellable) {
            entry.cancelJobs()
            terminalizeOutgoing(
                entry,
                FileTransferState.Cancelled(reason),
                "cancelled outgoing transfer ${handle.transferId}"
            )
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
            if (current.session !== session) {
                throw IllegalStateException("Offer ${session.id} is no longer the current offer")
            }
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

        sendFileAcceptWithinDeadline(entry, secure = false)

        withContext(NonCancellable) {
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
        }
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
            if (current.session !== session) {
                throw IllegalStateException("Offer ${session.id} is no longer the current offer")
            }
            if (current.phase != IncomingPhase.OFFERED || session.state.value.isTerminal()) {
                throw IllegalStateException("Offer ${session.id} was already accepted or rejected")
            }
            current.phase = IncomingPhase.ACCEPTING
            current.offerTimer?.cancel()
            current.offerTimer = null
            current
        }
        val sink = try {
            when (
                val result = runBoundedIndependentOperation(
                    timeoutMillis = config.offerTimeoutMillis,
                    preserveCancellation = false,
                    operationDispatcher = independentOperationDispatcher,
                    deadlineDispatcher = operationDeadlineDispatcher,
                    operationGate = applicationOperationGate,
                    onLateSuccess = {
                        abortUnownedDestination(
                            destination,
                            cause = null,
                            label = "late destination open for ${session.transferId}"
                        )
                    }
                ) {
                    destination.openSink()
                }
            ) {
                is BoundedOperationResult.Success -> result.value
                is BoundedOperationResult.Failure -> throw classifyCallbackCancellation(
                    result.cause,
                    FileTransferFailureKind.STORAGE,
                    FileTransferPhase.ACCEPT,
                    Retryability.RETRY_AFTER_USER_ACTION,
                    session.transferId,
                    "destination open failed"
                )
                is BoundedOperationResult.TimedOut -> throw fileFailure(
                    FileTransferFailureKind.TIMEOUT,
                    FileTransferPhase.ACCEPT,
                    Retryability.RETRY_AFTER_USER_ACTION,
                    session.transferId,
                    "destination open did not finish within ${result.timeoutMillis}ms",
                    result.cause
                )
            }
        } catch (e: CancellationException) {
            val response = IncomingTerminalResponse.Cancel("receiver acceptance cancelled")
            withContext(NonCancellable) {
                val removed = removeIncomingTerminal(session.transferId, entry, response)
                removed?.cancelJobs()
                abortUnownedDestination(
                    destination,
                    cause = null,
                    label = "cancelled destination open for ${session.transferId}"
                )
                session.setState(FileTransferState.Cancelled("accept cancelled while opening destination"))
                if (removed != null) {
                    sendIncomingTerminalResponse(
                        session.transferId,
                        response,
                        entry.writeEpoch,
                        "cancelled destination open"
                    )
                }
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
            val response = incomingFailureResponse(session.transferId, error)
            val removed = removeIncomingTerminal(session.transferId, entry, response)
            removed?.cancelJobs()
            abortUnownedDestination(
                destination,
                cause = error,
                label = "failed destination open for ${session.transferId}"
            )
            session.markFailed(error)
            if (removed != null) {
                sendIncomingTerminalResponse(
                    session.transferId,
                    response,
                    entry.writeEpoch,
                    "failed destination open"
                )
            }
            throw error
        }
        val installed = try {
            session.installReceiver(sink, destination)
        } catch (e: CancellationException) {
            val response = IncomingTerminalResponse.Cancel("receiver acceptance cancelled")
            withContext(NonCancellable) {
                val removed = removeIncomingTerminal(session.transferId, entry, response)
                removed?.cancelJobs()
                abortUnownedDestination(
                    destination,
                    cause = null,
                    label = "cancelled destination install for ${session.transferId}"
                )
                session.setState(FileTransferState.Cancelled("accept cancelled while installing destination"))
                if (removed != null) {
                    sendIncomingTerminalResponse(
                        session.transferId,
                        response,
                        entry.writeEpoch,
                        "cancelled destination install"
                    )
                }
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
            val response = incomingFailureResponse(session.transferId, error)
            val removed = removeIncomingTerminal(session.transferId, entry, response)
            removed?.cancelJobs()
            abortUnownedDestination(
                destination,
                cause = error,
                label = "failed destination install for ${session.transferId}"
            )
            session.markFailed(error)
            if (removed != null) {
                sendIncomingTerminalResponse(
                    session.transferId,
                    response,
                    entry.writeEpoch,
                    "failed destination install"
                )
            }
            throw error
        }
        if (!installed) {
            val response = IncomingTerminalResponse.Cancel("receiver acceptance did not commit")
            val removed = removeIncomingTerminal(session.transferId, entry, response)
            removed?.cancelJobs()
            abortUnownedDestination(
                destination,
                cause = null,
                label = "terminal destination install for ${session.transferId}"
            )
            if (removed != null) {
                sendIncomingTerminalResponse(
                    session.transferId,
                    response,
                    entry.writeEpoch,
                    "terminal destination install"
                )
            }
            throw IllegalStateException("Offer ${session.id} became terminal during acceptance")
        }
        sendFileAcceptWithinDeadline(entry, secure = true)
        withContext(NonCancellable) {
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
        }
        return session
    }

    suspend fun rejectOffer(session: IncomingFileSession, reason: String?) {
        val response = incomingRejectResponse(reason)
        val entry = lock.withLock {
            val current = incoming[session.transferId]
                ?: throw IllegalStateException("Offer ${session.id} is no longer pending")
            if (current.session !== session) {
                throw IllegalStateException("Offer ${session.id} is no longer the current offer")
            }
            if (current.phase != IncomingPhase.OFFERED || session.state.value.isTerminal()) {
                throw IllegalStateException("Offer ${session.id} was already accepted or rejected")
            }
            removeIncomingLocked(current, response)
        }
        entry.cancelJobs()
        session.setState(FileTransferState.Rejected(reason))
        sendIncomingTerminalResponse(
            transferId = session.transferId,
            response = response,
            expectedEpoch = entry.writeEpoch,
            label = "FILE_REJECT"
        )
    }

    suspend fun cancelIncoming(session: IncomingFileSession, reason: String?) {
        val (entry, response) = lock.withLock {
            val current = incoming[session.transferId] ?: return
            if (current.session !== session) return
            val accepted = current.phase != IncomingPhase.OFFERED
            val terminalResponse = if (accepted) {
                incomingCancelResponse(reason)
            } else {
                incomingRejectResponse(reason)
            }
            removeIncomingLocked(current, terminalResponse) to terminalResponse
        }
        val changed = withContext(NonCancellable) {
            entry.cancelJobs()
            terminalizeIncoming(entry, FileTransferState.Cancelled(reason))
        }
        if (!changed) return
        sendIncomingTerminalResponse(
            transferId = session.transferId,
            response = response,
            expectedEpoch = entry.writeEpoch,
            label = "cancel"
        )
    }

    // ---- Inbound protocol events ----

    suspend fun onFileOffer(
        transferId: MessageId,
        payload: FileOfferPayload,
        secureOffer: SecureFileOffer? = null
    ) {
        if (closed) return
        val eventEpoch = writeEpoch
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
            val terminal = terminalIncoming[transferId]
            val existingIncoming = incoming[transferId]
            when {
                closed -> OfferInsertion.CLOSED
                terminal != null && terminal.offer == secureOffer ->
                    OfferInsertion.ReplayTerminal(terminal.response)
                terminal != null -> OfferInsertion.CONFLICT
                ambiguousIncomingCapacityExhausted -> OfferInsertion.Capacity(
                    "ambiguous transfer-id capacity exhausted; reconnect required"
                )
                transferId in ambiguousIncomingTransferIds -> OfferInsertion.RETIRED
                existingIncoming != null && existingIncoming.payload == payload &&
                    existingIncoming.secureOffer == secureOffer ->
                    OfferInsertion.EXACT_DUPLICATE
                existingIncoming != null -> OfferInsertion.CONFLICT
                outgoing.containsKey(transferId) -> OfferInsertion.CONFLICT
                payload.sizeBytes > config.maxFileSizeBytes -> OfferInsertion.Capacity(
                    "sizeBytes ${payload.sizeBytes} exceeds maxFileSizeBytes " +
                        config.maxFileSizeBytes
                )
                !hasSupportedChunkCount(payload.sizeBytes) -> OfferInsertion.Capacity(
                    "file requires more than ${Int.MAX_VALUE} chunks"
                )
                incoming.size >= MAX_ACTIVE_INCOMING_TRANSFERS -> OfferInsertion.Capacity(
                    "too many active incoming transfers"
                )
                secureOffer != null &&
                    secureIncomingTransactionCountLocked() >= MAX_TERMINAL_INCOMING_TRANSACTIONS ->
                    OfferInsertion.Capacity(
                        "authenticated transfer replay ledger capacity exhausted; reconnect required"
                    )
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
            is OfferInsertion.ReplayTerminal -> {
                logger.debug(
                    "Session $sessionId: replayed terminal FILE_OFFER transferId $transferId; " +
                        "replaying terminal response"
                )
                sendIncomingTerminalResponse(
                    transferId = transferId,
                    response = insertion.response,
                    expectedEpoch = eventEpoch,
                    label = "replayed terminal response"
                )
                return
            }
            OfferInsertion.RETIRED -> {
                sendBestEffort("retired-id FILE_CANCEL for $transferId", eventEpoch) { connection ->
                    protocol.sendFileCancel(connection, transferId, "transfer id is retired in this session")
                }
                return
            }
            OfferInsertion.CONFLICT -> throw fileFailure(
                kind = FileTransferFailureKind.TRANSFER_PROTOCOL,
                phase = FileTransferPhase.OFFER,
                retryability = Retryability.NOT_RETRYABLE,
                transferId = transferId,
                reason = "Conflicting FILE_OFFER reused transferId $transferId"
            )
            is OfferInsertion.Capacity -> {
                sendBestEffort("capacity FILE_REJECT for $transferId", eventEpoch) { connection ->
                    protocol.sendFileReject(connection, transferId, insertion.reason)
                }
                return
            }
            is OfferInsertion.Inserted -> {
                armIncomingOfferTimer(insertion.entry)
                // This deprecated migration stream is deliberately
                // non-authoritative. Never create a suspending emission job:
                // a slow collector could otherwise retain an unowned child
                // after the offer was rejected or the session closed. Keep
                // admission/close ordering under the ownership lock and drop
                // the event if the bounded migration buffer is full.
                lock.withLock {
                    val entry = insertion.entry
                    if (!closed && incoming[transferId] === entry &&
                        entry.phase == IncomingPhase.OFFERED
                    ) {
                        incomingOffers.tryEmit(entry.session)
                    }
                }
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

        val sender = scope.launch(
            context = outgoingReadDispatcher ?: EmptyCoroutineContext,
            start = CoroutineStart.LAZY
        ) {
            var permitAcquired = false
            try {
                outgoingStreamGate.acquire()
                permitAcquired = true
                currentCoroutineContext().ensureActive()
                streamOutgoingPayload(entry)
            } finally {
                if (permitAcquired) outgoingStreamGate.release()
            }
        }
        val registered = lock.withLock {
            if (outgoing[transferId] === entry && entry.phase == OutgoingPhase.STREAMING) {
                entry.sender = sender
                true
            } else {
                false
            }
        }
        if (registered && armOutgoingOverallDeadline(entry)) {
            sender.start()
        } else {
            sender.cancel()
        }
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
                terminalizeOutgoing(
                    result.entry,
                    FileTransferState.Rejected(reason),
                    "rejected outgoing transfer $transferId"
                )
            }
        }
    }

    suspend fun onFileData(frame: Frame) {
        val entry = lock.withLock { incoming[frame.messageId] }
        if (entry == null) {
            logger.debug("Session $sessionId: FILE_DATA for unknown transfer ${frame.messageId}; ignoring")
            return
        }
        when (entry.phase) {
            IncomingPhase.OFFERED -> {
                logger.warn(
                    "Session $sessionId: FILE_DATA for ${frame.messageId} arrived before accept; dropping"
                )
                return
            }
            IncomingPhase.FINALIZING -> {
                logger.warn(
                    "Session $sessionId: FILE_DATA for ${frame.messageId} arrived after finalization began; " +
                        "dropping"
                )
                return
            }
            IncomingPhase.ACCEPTING,
            IncomingPhase.ACCEPTED -> Unit
        }
        try {
            val total = when (
                val result = runBoundedIndependentOperation(
                    timeoutMillis = config.acceptedIdleTimeoutMillis,
                    preserveCancellation = false,
                    operationDispatcher = independentOperationDispatcher,
                    deadlineDispatcher = operationDeadlineDispatcher,
                    operationGate = applicationOperationGate
                ) {
                    entry.session.acceptData(frame)
                }
            ) {
                is BoundedOperationResult.Success -> result.value
                is BoundedOperationResult.Failure -> throw classifyCallbackCancellation(
                    result.cause,
                    FileTransferFailureKind.STORAGE,
                    FileTransferPhase.RECEIVE,
                    Retryability.RETRY_AFTER_USER_ACTION,
                    frame.messageId,
                    "file receive write failed"
                )
                is BoundedOperationResult.TimedOut -> {
                    timeoutAcceptedIncoming(entry, requiredIdleGeneration = null, kind = "idle")
                    return
                }
            } ?: return
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
        val entry = when (val decision = beginIncomingFinalization(transferId)) {
            IncomingFinalization.Missing -> {
                logger.debug("Session $sessionId: FILE_DONE for unknown transfer $transferId; ignoring")
                return
            }
            is IncomingFinalization.NotAccepted -> {
                logger.warn(
                    "Session $sessionId: FILE_DONE for $transferId while receiver was " +
                        "${decision.phase}; ignoring"
                )
                return
            }
            IncomingFinalization.AlreadyStarted -> {
                logger.debug("Session $sessionId: duplicate FILE_DONE for $transferId; ignoring")
                return
            }
            is IncomingFinalization.Started -> decision.entry
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
            val completed = when (
                val result = runBoundedIndependentOperation(
                    timeoutMillis = config.acceptedIdleTimeoutMillis,
                    preserveCancellation = false,
                    operationDispatcher = independentOperationDispatcher,
                    deadlineDispatcher = operationDeadlineDispatcher,
                    operationGate = applicationOperationGate
                ) {
                    entry.session.finishLegacyReceiver()
                }
            ) {
                is BoundedOperationResult.Success -> result.value
                is BoundedOperationResult.Failure -> throw classifyCallbackCancellation(
                    result.cause,
                    FileTransferFailureKind.STORAGE,
                    FileTransferPhase.FLUSH,
                    Retryability.RETRY_AFTER_USER_ACTION,
                    transferId,
                    "legacy receiver flush failed"
                )
                is BoundedOperationResult.TimedOut -> throw fileFailure(
                    kind = FileTransferFailureKind.TIMEOUT,
                    phase = FileTransferPhase.FLUSH,
                    retryability = Retryability.RETRY_NEW_SESSION,
                    transferId = transferId,
                    reason = "legacy receiver flush timed out after ${result.timeoutMillis}ms",
                    cause = result.cause
                )
            }
            if (completed) removeIncoming(transferId, entry)?.cancelJobs()
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            failIncomingTransfer(entry, "file receive finalize failed", e)
        }
    }

    suspend fun onFileFinish(finish: SecureFileFinish) {
        val entry = when (val decision = beginIncomingFinalization(finish.transferId)) {
            IncomingFinalization.Missing -> {
                logger.debug(
                    "Session $sessionId: FILE_FINISH for unknown transfer ${finish.transferId}; ignoring"
                )
                return
            }
            is IncomingFinalization.NotAccepted -> {
                val failure = P2pError.ProtocolError(
                    "FILE_FINISH arrived while receiver was ${decision.phase}"
                )
                if (decision.entry.secureOffer != null) {
                    failIncomingSecureTransfer(
                        decision.entry,
                        FileResultCode.PROTOCOL_FAILURE,
                        FileTransferPhase.VERIFY,
                        "invalid FILE_FINISH transition",
                        failure
                    )
                } else {
                    failIncomingTransfer(decision.entry, "invalid FILE_FINISH transition", failure)
                }
                return
            }
            IncomingFinalization.AlreadyStarted -> {
                logger.debug(
                    "Session $sessionId: duplicate FILE_FINISH for ${finish.transferId}; ignoring"
                )
                return
            }
            is IncomingFinalization.Started -> decision.entry
        }
        if (entry.secureOffer == null) {
            val failure = P2pError.ProtocolError(
                "FILE_FINISH arrived for a legacy transfer"
            )
            failIncomingTransfer(entry, "invalid FILE_FINISH transition", failure)
            return
        }
        try {
            val committed = when (
                val result = runBoundedIndependentOperation(
                    timeoutMillis = config.commitTimeoutMillis,
                    preserveCancellation = false,
                    operationDispatcher = independentOperationDispatcher,
                    deadlineDispatcher = operationDeadlineDispatcher,
                    operationGate = applicationOperationGate
                ) {
                    entry.session.verifyAndCommit(finish)
                }
            ) {
                is BoundedOperationResult.Success -> result.value
                is BoundedOperationResult.Failure -> throw classifyCallbackCancellation(
                    result.cause,
                    FileTransferFailureKind.STORAGE,
                    FileTransferPhase.DURABLE_COMMIT,
                    Retryability.RETRY_AFTER_USER_ACTION,
                    finish.transferId,
                    "receiver durable commit failed"
                )
                is BoundedOperationResult.TimedOut -> {
                    failIncomingSecureTransfer(
                        entry,
                        FileResultCode.TIMEOUT,
                        FileTransferPhase.DURABLE_COMMIT,
                        "receiver durable commit timed out after ${result.timeoutMillis}ms",
                        result.cause
                    )
                    return
                }
            }
            if (!committed) return
            val offer = checkNotNull(entry.secureOffer)
            val response = IncomingTerminalResponse.Commit(
                SecureFileCommit(
                    finish.transferId,
                    finish.sizeBytes,
                    finish.contentDigest,
                    offer.offerHash
                )
            )
            val removed = removeIncomingTerminal(
                finish.transferId,
                entry,
                response
            ) ?: return
            removed.cancelJobs()
            sendIncomingTerminalResponse(
                transferId = finish.transferId,
                response = response,
                expectedEpoch = entry.writeEpoch,
                label = "FILE_COMMIT"
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
            is CommitResult.Committed -> terminalizeOutgoing(
                result.entry,
                FileTransferState.Completed,
                "committed outgoing transfer ${commit.transferId}"
            )
            is CommitResult.Mismatch -> terminalizeOutgoing(
                result.entry,
                FileTransferState.Failed(
                    fileFailure(
                        FileTransferFailureKind.INTEGRITY,
                        FileTransferPhase.DURABLE_COMMIT,
                        Retryability.NOT_RETRYABLE,
                        commit.transferId,
                        "FILE_COMMIT does not match the authenticated offer"
                    )
                ),
                "mismatched outgoing commit ${commit.transferId}"
            )
            is CommitResult.InvalidTransition -> terminalizeOutgoing(
                result.entry,
                FileTransferState.Failed(
                    fileFailure(
                        FileTransferFailureKind.TRANSFER_PROTOCOL,
                        FileTransferPhase.DURABLE_COMMIT,
                        Retryability.NOT_RETRYABLE,
                        commit.transferId,
                        "FILE_COMMIT arrived while sender was ${result.phase}"
                    )
                ),
                "invalid outgoing commit ${commit.transferId}"
            )
        }
    }

    suspend fun onFileResult(result: SecureFileResult) {
        val outgoingEntry = removeOutgoing(result.transferId)
        if (outgoingEntry != null) {
            outgoingEntry.cancelJobs()
            terminalizeOutgoing(
                outgoingEntry,
                FileTransferState.Failed(result.toPublicFailure()),
                "failed outgoing transfer ${result.transferId}"
            )
            return
        }
        val incomingEntry = removeIncomingTerminal(
            transferId = result.transferId,
            response = IncomingTerminalResponse.Result(result)
        )
        if (incomingEntry != null) {
            incomingEntry.cancelJobs()
            terminalizeIncoming(
                incomingEntry,
                FileTransferState.Failed(result.toPublicFailure())
            )
            return
        }
        logger.debug("Session $sessionId: FILE_RESULT for unknown transfer ${result.transferId}; ignoring")
    }

    suspend fun onFileCancel(transferId: MessageId, reason: String?) {
        val outgoingEntry = removeOutgoing(transferId)
        if (outgoingEntry != null) {
            outgoingEntry.cancelJobs()
            terminalizeOutgoing(
                outgoingEntry,
                FileTransferState.Cancelled(reason),
                "remote-cancelled outgoing transfer $transferId"
            )
            return
        }
        val incomingEntry = removeIncomingTerminal(
            transferId = transferId,
            response = incomingCancelResponse(reason)
        )
        if (incomingEntry != null) {
            incomingEntry.cancelJobs()
            terminalizeIncoming(incomingEntry, FileTransferState.Cancelled(reason))
            return
        }
        logger.debug("Session $sessionId: FILE_CANCEL for unknown transfer $transferId; ignoring")
    }

    /**
     * Admit a fresh connection epoch after [beginCloseAll] and
     * [awaitCloseAll] have settled the previous one. The owning session holds
     * [sendMutex] across its raw-connection swap and this transition.
     */
    suspend fun reopen() {
        lock.withLock {
            check(closed) { "File-transfer dispatcher can reopen only after closeAll" }
            terminalIncoming.clear()
            ambiguousIncomingTransferIds.clear()
            ambiguousIncomingCapacityExhausted = false
            writeEpoch = FileTransferWriteEpoch()
            closed = false
        }
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
            val terminalResources = entry.handle.transitionTerminalWithoutCleanup(
                FileTransferState.Failed(
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
            )
            terminalResources?.source?.let { source ->
                jobsToJoin += launchIndependentCleanup {
                    cleanupOutgoingSource(
                        source,
                        "terminal outgoing transfer ${entry.handle.transferId}"
                    )
                }
            }
        }
        for (entry in incomingEntries) {
            jobsToJoin += entry.cancelJobs()
            entry.acceptanceCommitted.complete(false)
            val terminalState = if (entry.phase == IncomingPhase.OFFERED) {
                FileTransferState.Cancelled(reason)
            } else {
                FileTransferState.Failed(
                    fileFailure(
                        kind = failureKind,
                        phase = when (entry.phase) {
                            IncomingPhase.ACCEPTING -> FileTransferPhase.ACCEPT
                            IncomingPhase.FINALIZING -> if (entry.secureOffer == null) {
                                FileTransferPhase.FLUSH
                            } else {
                                FileTransferPhase.DURABLE_COMMIT
                            }
                            IncomingPhase.OFFERED,
                            IncomingPhase.ACCEPTED -> FileTransferPhase.RECEIVE
                        },
                        retryability = retryability,
                        transferId = entry.session.transferId,
                        reason = reason
                    )
                )
            }
            if (entry.session.transitionTerminalWithoutCleanup(terminalState)) {
                jobsToJoin += launchIncomingTerminalCleanup(
                    entry.session,
                    (terminalState as? FileTransferState.Failed)?.error as?
                        P2pError.FileTransferFailed
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
            if (expectedDigest != null) openPreparedSourceWithinDeadline(handle)
            if (!armOutgoingIdleDeadline(entry)) return
            if (handle.sizeBytes > 0L) handle.setState(FileTransferState.Sending(0f))
            streamFileData(
                transferId = handle.transferId,
                rawSource = handle.sourceOrThrow(),
                sizeBytes = handle.sizeBytes,
                chunkSizeBytes = config.chunkSizeBytes,
                requireExactSize = expectedDigest != null
            ).collect { frame ->
                hasher?.update(frame.payload)
                try {
                    withEpochWrite(entry.writeEpoch) { connection ->
                        protocol.sendFileDataFrame(connection, frame)
                    }
                } catch (e: CancellationException) {
                    // A protocol callback can throw CancellationException
                    // while this sender job is still active. Remember that
                    // the failing operation was a wire write; the outer
                    // cancellation check still propagates genuine job
                    // cancellation without terminal reclassification.
                    connectionWriteFailure = true
                    throw e
                } catch (e: Throwable) {
                    connectionWriteFailure = true
                    throw e
                }
                if (!handle.recordBytesSent(frame.payload.size)) {
                    throw CancellationException("Transfer ${handle.transferId} terminalized while writing")
                }
                rearmOutgoingIdleDeadline(entry)
            }
            if (handle.state.value.isTerminal()) return
            if (expectedDigest != null) {
                val actualDigest = checkNotNull(hasher).finish()
                if (actualDigest != expectedDigest) {
                    failPreparedSourceChanged(
                        entry = entry,
                        reason = "Prepared source SHA-256 changed before or during streaming"
                    )
                    return
                }
                val transitioned = lock.withLock {
                    if (outgoing[handle.transferId] === entry && entry.phase == OutgoingPhase.STREAMING) {
                        entry.phase = OutgoingPhase.COMMIT_WAIT
                        entry.timer?.cancel()
                        entry.timer = null
                        entry.overallTimer?.cancel()
                        entry.overallTimer = null
                        entry.idleGeneration++
                        true
                    } else false
                }
                if (!transitioned) return
                try {
                    sendSecureFinishWithinDeadline(
                        entry,
                        SecureFileFinish(
                            handle.transferId,
                            handle.sizeBytes,
                            chunkCount(handle.sizeBytes),
                            actualDigest,
                            checkNotNull(handle.offerHash)
                        )
                    )
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Throwable) {
                    connectionWriteFailure = (e as? P2pError.FileTransferFailed)?.kind !=
                        FileTransferFailureKind.TIMEOUT
                    throw e
                }
                handle.detachSourceAfterStreaming()?.let { source ->
                    launchIndependentCleanup {
                        cleanupOutgoingSource(
                            source,
                            "streamed prepared source ${handle.transferId}"
                        )
                    }
                }
                armOutgoingCommitWatchdog(entry)
                return
            }
            try {
                withEpochWrite(entry.writeEpoch) { connection ->
                    protocol.sendFileDone(connection, handle.transferId)
                }
            } catch (e: CancellationException) {
                connectionWriteFailure = true
                throw e
            } catch (e: Throwable) {
                connectionWriteFailure = true
                throw e
            }
            val removed = removeOutgoing(handle.transferId, entry) ?: return
            removed.cancelTimers()
            terminalizeOutgoing(
                removed,
                FileTransferState.Completed,
                "completed outgoing transfer ${handle.transferId}"
            )
        } catch (e: CancellationException) {
            currentCoroutineContext().ensureActive()
            failOutgoingPayload(entry, e, connectionWriteFailure)
        } catch (e: PreparedSourceLengthChangedException) {
            failPreparedSourceChanged(
                entry = entry,
                reason = e.message ?: "Prepared source length changed before or during streaming",
                cause = e
            )
        } catch (e: Throwable) {
            failOutgoingPayload(entry, e, connectionWriteFailure)
        }
    }

    private suspend fun failOutgoingPayload(
        entry: OutgoingEntry,
        cause: Throwable,
        connectionWriteFailure: Boolean
    ) {
        val handle = entry.handle
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
            cause = cause
        )
        val removed = removeOutgoing(handle.transferId, entry) ?: return
        removed.cancelTimers()
        val changed = terminalizeOutgoing(
            removed,
            FileTransferState.Failed(err),
            "failed outgoing transfer ${handle.transferId}"
        )
        logger.warn("Session $sessionId: outgoing transfer ${handle.transferId} failed", cause)
        if (connectionWriteFailure || !changed) return
        if (handle.expectedDigest != null &&
            err is P2pError.FileTransferFailed &&
            err.kind == FileTransferFailureKind.TIMEOUT
        ) {
            sendBestEffort(
                "source-timeout FILE_RESULT for ${handle.transferId}",
                entry.writeEpoch
            ) { connection ->
                protocol.sendFileResult(
                    connection,
                    SecureFileResult(
                        handle.transferId,
                        FileResultCode.TIMEOUT,
                        err.phase,
                        "sender source timeout"
                    )
                )
            }
        } else {
            sendBestEffort(
                "FILE_CANCEL for ${handle.transferId}",
                entry.writeEpoch
            ) { connection ->
                protocol.sendFileCancel(
                    connection,
                    handle.transferId,
                    "sender source failure"
                )
            }
        }
    }

    private suspend fun openPreparedSourceWithinDeadline(handle: OutgoingFileTransferImpl) {
        when (
            val result = runBoundedIndependentOperation(
                timeoutMillis = config.offerTimeoutMillis,
                preserveCancellation = false,
                operationDispatcher = independentOperationDispatcher,
                deadlineDispatcher = operationDeadlineDispatcher,
                operationGate = applicationOperationGate,
                onLateSuccess = { source ->
                    cleanupOutgoingSource(
                        source,
                        "late prepared source for ${handle.transferId}"
                    )
                },
                operation = handle::createPreparedSource
            )
        ) {
            is BoundedOperationResult.Success -> handle.installPreparedSource(result.value)
            is BoundedOperationResult.Failure -> throw classifyCallbackCancellation(
                result.cause,
                FileTransferFailureKind.SOURCE_IO,
                FileTransferPhase.SOURCE_READ,
                Retryability.RETRY_AFTER_USER_ACTION,
                handle.transferId,
                "prepared source open failed"
            )
            is BoundedOperationResult.TimedOut -> throw fileFailure(
                kind = FileTransferFailureKind.TIMEOUT,
                phase = FileTransferPhase.SOURCE_READ,
                retryability = Retryability.RETRY_AFTER_USER_ACTION,
                transferId = handle.transferId,
                reason = "Prepared source open did not finish within ${result.timeoutMillis}ms",
                cause = result.cause
            )
        }
    }

    private suspend fun failPreparedSourceChanged(
        entry: OutgoingEntry,
        reason: String,
        cause: Throwable? = null
    ) {
        val handle = entry.handle
        val removed = removeOutgoing(handle.transferId, entry) ?: return
        val error = fileFailure(
            FileTransferFailureKind.SOURCE_CHANGED,
            FileTransferPhase.SOURCE_READ,
            Retryability.RETRY_AFTER_USER_ACTION,
            handle.transferId,
            reason,
            cause
        )
        val changed = terminalizeOutgoing(
            removed,
            FileTransferState.Failed(error),
            "changed prepared source ${handle.transferId}"
        )
        try {
            if (changed) {
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
                            "prepared source changed"
                        )
                    )
                }
            }
        } finally {
            removed.cancelJobs()
        }
    }

    private fun chunkCount(sizeBytes: Long): Int = if (sizeBytes == 0L) {
        0
    } else {
        (1L + (sizeBytes - 1L) / config.chunkSizeBytes.toLong()).toInt()
    }

    private suspend fun armOutgoingOverallDeadline(entry: OutgoingEntry): Boolean {
        val timer = scope.launch(start = CoroutineStart.LAZY) {
            delay(config.acceptedOverallTimeoutMillis)
            timeoutOutgoingStreaming(entry, requiredIdleGeneration = null, kind = "overall")
        }
        val installed = lock.withLock {
            if (outgoing[entry.handle.transferId] === entry &&
                entry.phase == OutgoingPhase.STREAMING
            ) {
                entry.overallTimer = timer
                true
            } else {
                false
            }
        }
        if (installed) timer.start() else timer.cancel()
        return installed
    }

    private suspend fun armOutgoingIdleDeadline(entry: OutgoingEntry): Boolean {
        var timer: Job? = null
        val installed = lock.withLock {
            if (outgoing[entry.handle.transferId] !== entry ||
                entry.phase != OutgoingPhase.STREAMING
            ) {
                false
            } else {
                val generation = ++entry.idleGeneration
                timer = scope.launch(start = CoroutineStart.LAZY) {
                    delay(config.acceptedIdleTimeoutMillis)
                    timeoutOutgoingStreaming(entry, generation, "idle")
                }
                entry.timer = timer
                true
            }
        }
        if (installed) checkNotNull(timer).start() else timer?.cancel()
        return installed
    }

    private suspend fun rearmOutgoingIdleDeadline(entry: OutgoingEntry) {
        var replacement: Job? = null
        val old = lock.withLock {
            if (outgoing[entry.handle.transferId] !== entry ||
                entry.phase != OutgoingPhase.STREAMING
            ) {
                null
            } else {
                val generation = ++entry.idleGeneration
                replacement = scope.launch(start = CoroutineStart.LAZY) {
                    delay(config.acceptedIdleTimeoutMillis)
                    timeoutOutgoingStreaming(entry, generation, "idle")
                }
                entry.timer.also { entry.timer = replacement }
            }
        }
        if (replacement == null) return
        old?.cancel()
        checkNotNull(replacement).start()
    }

    private suspend fun timeoutOutgoingStreaming(
        entry: OutgoingEntry,
        requiredIdleGeneration: Long?,
        kind: String
    ) {
        val removed = lock.withLock {
            val current = outgoing[entry.handle.transferId]
            if (current !== entry || current.phase != OutgoingPhase.STREAMING) return
            if (requiredIdleGeneration != null &&
                current.idleGeneration != requiredIdleGeneration
            ) {
                return
            }
            outgoing.remove(entry.handle.transferId)
            current
        }
        withContext(NonCancellable) {
            removed.cancelJobs()
            val error = fileFailure(
                kind = FileTransferFailureKind.TIMEOUT,
                phase = FileTransferPhase.SEND,
                retryability = Retryability.RETRY_NEW_SESSION,
                transferId = removed.handle.transferId,
                reason = "$kind outgoing transfer timeout after " +
                    (if (kind == "idle") {
                        config.acceptedIdleTimeoutMillis
                    } else {
                        config.acceptedOverallTimeoutMillis
                    }) + "ms"
            )
            val resources = removed.handle.transitionTerminalWithoutCleanup(
                FileTransferState.Failed(error)
            )
            resources?.source?.let { source ->
                launchIndependentCleanup {
                    cleanupOutgoingSource(
                        source,
                        "$kind-timeout outgoing transfer ${removed.handle.transferId}"
                    )
                }
            }
            sendCleanupBestEffort(
                "$kind-timeout terminal for ${removed.handle.transferId}",
                removed.writeEpoch
            ) { connection ->
                if (removed.handle.expectedDigest != null) {
                    protocol.sendFileResult(
                        connection,
                        SecureFileResult(
                            removed.handle.transferId,
                            FileResultCode.TIMEOUT,
                            FileTransferPhase.SEND,
                            "$kind outgoing transfer timeout"
                        )
                    )
                } else {
                    protocol.sendFileCancel(
                        connection,
                        removed.handle.transferId,
                        "$kind outgoing transfer timeout"
                    )
                }
            }
        }
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
            withContext(NonCancellable) {
                removed.cancelJobs()
                terminalizeOutgoing(
                    removed,
                    FileTransferState.Failed(
                        fileFailure(
                            FileTransferFailureKind.TIMEOUT,
                            FileTransferPhase.DURABLE_COMMIT,
                            Retryability.RETRY_NEW_SESSION,
                            removed.handle.transferId,
                            "FILE_COMMIT not received within ${config.commitTimeoutMillis}ms"
                        )
                    ),
                    "commit-timeout outgoing transfer ${removed.handle.transferId}"
                )
            }
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
        terminalizeOutgoing(
            removed,
            FileTransferState.Failed(
                fileFailure(
                    kind = FileTransferFailureKind.TIMEOUT,
                    phase = FileTransferPhase.OFFER,
                    retryability = Retryability.RETRY_SAME_SESSION,
                    transferId = entry.handle.transferId,
                    reason = "offer response not received within ${config.outgoingOfferWatchdogMillis}ms"
                )
            ),
            "offer-timeout outgoing transfer ${entry.handle.transferId}"
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
        val response = IncomingTerminalResponse.Reject("timeout")
        val removed = lock.withLock {
            val current = incoming[entry.session.transferId]
            if (current !== entry || current.phase != IncomingPhase.OFFERED) return
            removeIncomingLocked(current, response)
        }
        withContext(NonCancellable) {
            removed.cancelJobs()
            terminalizeIncoming(removed, FileTransferState.Rejected("timeout"))
            sendIncomingTerminalResponse(
                transferId = entry.session.transferId,
                response = response,
                expectedEpoch = entry.writeEpoch,
                label = "timeout FILE_REJECT"
            )
        }
    }

    private suspend fun armAcceptedDeadlines(entry: IncomingEntry) {
        var idle: Job? = null
        var overall: Job? = null
        val installed = lock.withLock {
            if (incoming[entry.session.transferId] !== entry || entry.phase != IncomingPhase.ACCEPTED) {
                false
            } else {
                val idleGeneration = ++entry.idleGeneration
                idle = newIdleTimer(entry, idleGeneration)
                overall = scope.launch(start = CoroutineStart.LAZY) {
                    delay(config.acceptedOverallTimeoutMillis)
                    timeoutAcceptedIncoming(entry, null, "overall")
                }
                entry.idleTimer = idle
                entry.overallTimer = overall
                true
            }
        }
        if (installed) {
            checkNotNull(idle).start()
            checkNotNull(overall).start()
        } else {
            idle?.cancel()
            overall?.cancel()
        }
    }

    private suspend fun beginIncomingFinalization(
        transferId: MessageId
    ): IncomingFinalization {
        val observed = lock.withLock { incoming[transferId] }
            ?: return IncomingFinalization.Missing
        if (observed.phase == IncomingPhase.ACCEPTING &&
            !observed.acceptanceCommitted.await()
        ) {
            return IncomingFinalization.Missing
        }
        return lock.withLock {
            val current = incoming[transferId]
                ?: return@withLock IncomingFinalization.Missing
            when (current.phase) {
                IncomingPhase.ACCEPTED -> {
                    current.phase = IncomingPhase.FINALIZING
                    current.idleTimer?.cancel()
                    current.overallTimer?.cancel()
                    current.idleTimer = null
                    current.overallTimer = null
                    IncomingFinalization.Started(current)
                }
                IncomingPhase.FINALIZING -> IncomingFinalization.AlreadyStarted
                IncomingPhase.OFFERED,
                IncomingPhase.ACCEPTING -> IncomingFinalization.NotAccepted(
                    current,
                    current.phase
                )
            }
        }
    }

    private suspend fun rearmIncomingIdleDeadline(entry: IncomingEntry) {
        var replacement: Job? = null
        val old = lock.withLock {
            if (incoming[entry.session.transferId] !== entry ||
                entry.phase != IncomingPhase.ACCEPTED
            ) {
                null
            } else {
                val generation = ++entry.idleGeneration
                replacement = newIdleTimer(entry, generation)
                entry.idleTimer.also { entry.idleTimer = replacement }
            }
        }
        if (replacement == null) return
        old?.cancel()
        checkNotNull(replacement).start()
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
        val response = if (entry.secureOffer != null) {
            IncomingTerminalResponse.Result(
                SecureFileResult(
                    entry.session.transferId,
                    FileResultCode.TIMEOUT,
                    FileTransferPhase.RECEIVE,
                    "$kind transfer timeout"
                )
            )
        } else {
            IncomingTerminalResponse.Cancel("$kind transfer timeout")
        }
        val removed = lock.withLock {
            val current = incoming[entry.session.transferId]
            if (current !== entry || current.phase != IncomingPhase.ACCEPTED) return
            if (requiredIdleGeneration != null && current.idleGeneration != requiredIdleGeneration) return
            removeIncomingLocked(current, response)
        }
        withContext(NonCancellable) {
            removed.cancelJobs()
            terminalizeIncoming(
                removed,
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
            sendIncomingTerminalResponse(
                transferId = entry.session.transferId,
                response = response,
                expectedEpoch = entry.writeEpoch,
                label = "$kind-timeout terminal"
            )
        }
    }

    private suspend fun sendFileAcceptWithinDeadline(
        entry: IncomingEntry,
        secure: Boolean
    ) {
        try {
            when (
                val result = runBoundedIndependentOperation(
                    timeoutMillis = config.offerTimeoutMillis,
                    preserveCancellation = false,
                    operationDispatcher = protocolOperationDispatcher,
                    deadlineDispatcher = operationDeadlineDispatcher,
                    operationGate = protocolOperationGate,
                    onLateSuccess = {
                        // FILE_ACCEPT may have crossed the wire after the
                        // caller already timed out/cancelled. Send a second
                        // bounded compensation after that late write releases
                        // the epoch mutex; the immediate compensation can have
                        // timed out behind the still-wedged accept writer.
                        sendRetiredAcceptCompensation(entry, "late-accept")
                    }
                ) {
                    withEpochWrite(entry.writeEpoch) { connection ->
                        if (secure) {
                            protocol.sendSecureFileAccept(connection, entry.session.transferId)
                        } else {
                            protocol.sendFileAccept(connection, entry.session.transferId)
                        }
                    }
                }
            ) {
                is BoundedOperationResult.Success -> Unit
                is BoundedOperationResult.Failure -> throw classifyCallbackCancellation(
                    result.cause,
                    FileTransferFailureKind.TRANSPORT,
                    FileTransferPhase.ACCEPT,
                    Retryability.RETRY_NEW_SESSION,
                    entry.session.transferId,
                    "FILE_ACCEPT write failed"
                )
                is BoundedOperationResult.TimedOut -> throw fileFailure(
                    kind = FileTransferFailureKind.TIMEOUT,
                    phase = FileTransferPhase.ACCEPT,
                    retryability = Retryability.RETRY_NEW_SESSION,
                    transferId = entry.session.transferId,
                    reason = "FILE_ACCEPT write did not finish within ${result.timeoutMillis}ms",
                    cause = result.cause
                )
            }
            currentCoroutineContext().ensureActive()
        } catch (cancelled: CancellationException) {
            compensateAmbiguousAccept(
                entry,
                FileTransferState.Cancelled("accept cancelled while FILE_ACCEPT was in flight")
            )
            throw cancelled
        } catch (failure: Throwable) {
            val error = failureFromCause(
                kind = FileTransferFailureKind.TRANSPORT,
                phase = FileTransferPhase.ACCEPT,
                retryability = Retryability.RETRY_NEW_SESSION,
                transferId = entry.session.transferId,
                prefix = "FILE_ACCEPT write failed",
                cause = failure
            )
            compensateAmbiguousAccept(entry, FileTransferState.Failed(error))
            throw error
        }
    }

    private suspend fun sendInitialOfferWithinDeadline(
        entry: OutgoingEntry,
        send: suspend (RawConnection) -> Unit
    ) {
        when (
            val result = runBoundedIndependentOperation(
                timeoutMillis = config.offerTimeoutMillis,
                preserveCancellation = false,
                operationDispatcher = protocolOperationDispatcher,
                deadlineDispatcher = operationDeadlineDispatcher,
                operationGate = protocolOperationGate,
                onLateSuccess = {
                    // A non-cooperative writer can complete FILE_OFFER after
                    // sendFile already timed out or was cancelled. Compensate
                    // only after that writer releases the epoch mutex.
                    sendCleanupBestEffort(
                        "late-offer FILE_CANCEL for ${entry.handle.transferId}",
                        entry.writeEpoch
                    ) { connection ->
                        protocol.sendFileCancel(
                            connection,
                            entry.handle.transferId,
                            "offer did not commit locally"
                        )
                    }
                }
            ) {
                withEpochWrite(entry.writeEpoch, send)
            }
        ) {
            is BoundedOperationResult.Success -> Unit
            is BoundedOperationResult.Failure -> throw classifyCallbackCancellation(
                result.cause,
                FileTransferFailureKind.TRANSPORT,
                FileTransferPhase.OFFER,
                Retryability.RETRY_NEW_SESSION,
                entry.handle.transferId,
                "FILE_OFFER write failed"
            )
            is BoundedOperationResult.TimedOut -> throw fileFailure(
                kind = FileTransferFailureKind.TIMEOUT,
                phase = FileTransferPhase.OFFER,
                retryability = Retryability.RETRY_NEW_SESSION,
                transferId = entry.handle.transferId,
                reason = "FILE_OFFER write did not finish within ${result.timeoutMillis}ms",
                cause = result.cause
            )
        }
    }

    private suspend fun sendSecureFinishWithinDeadline(
        entry: OutgoingEntry,
        finish: SecureFileFinish
    ) {
        when (
            val result = runBoundedIndependentOperation(
                timeoutMillis = config.acceptedIdleTimeoutMillis,
                preserveCancellation = false,
                operationDispatcher = protocolOperationDispatcher,
                deadlineDispatcher = operationDeadlineDispatcher,
                operationGate = protocolOperationGate,
                onLateSuccess = {
                    // FILE_FINISH may cross the wire after the local timeout
                    // has terminalized and detached its source. Reconcile the
                    // peer only after the wedged writer releases sendMutex.
                    sendCleanupBestEffort(
                        "late-finish FILE_CANCEL for ${entry.handle.transferId}",
                        entry.writeEpoch
                    ) { connection ->
                        protocol.sendFileCancel(
                            connection,
                            entry.handle.transferId,
                            "FILE_FINISH did not commit locally"
                        )
                    }
                }
            ) {
                withEpochWrite(entry.writeEpoch) { connection ->
                    protocol.sendFileFinish(connection, finish)
                }
            }
        ) {
            is BoundedOperationResult.Success -> Unit
            is BoundedOperationResult.Failure -> throw classifyCallbackCancellation(
                result.cause,
                FileTransferFailureKind.TRANSPORT,
                FileTransferPhase.SEND,
                Retryability.RETRY_NEW_SESSION,
                entry.handle.transferId,
                "FILE_FINISH write failed"
            )
            is BoundedOperationResult.TimedOut -> throw fileFailure(
                kind = FileTransferFailureKind.TIMEOUT,
                phase = FileTransferPhase.SEND,
                retryability = Retryability.RETRY_NEW_SESSION,
                transferId = entry.handle.transferId,
                reason = "FILE_FINISH write did not finish within ${result.timeoutMillis}ms",
                cause = result.cause
            )
        }
    }

    private suspend fun compensateAmbiguousAccept(
        entry: IncomingEntry,
        terminalState: FileTransferState
    ) {
        withContext(NonCancellable) {
            val response = IncomingTerminalResponse.Cancel("accept did not commit")
            val removed = lock.withLock {
                val current = incoming[entry.session.transferId]
                if (current !== entry) return@withLock null
                if (current.secureOffer != null) {
                    removeIncomingLocked(current, response)
                } else {
                    incoming.remove(entry.session.transferId)
                    removePendingOfferLocked(current.session)
                    current.acceptanceCommitted.complete(false)
                    if (ambiguousIncomingTransferIds.size < MAX_AMBIGUOUS_INCOMING_TRANSFER_IDS) {
                        ambiguousIncomingTransferIds += entry.session.transferId
                    } else {
                        // Fail closed for the remainder of this epoch instead
                        // of evicting an id that a late FILE_ACCEPT could
                        // still use.
                        ambiguousIncomingCapacityExhausted = true
                    }
                    current
                }
            } ?: return@withContext
            removed.cancelJobs()
            terminalizeIncoming(removed, terminalState)
            // This is already terminal cleanup. A protocol implementation or
            // socket write can ignore cancellation, so a structured
            // withTimeout inside NonCancellable would still wait forever for
            // its child. Use the independent bounded owner shared by every
            // other terminal control notification.
            sendRetiredAcceptCompensation(entry, "compensating")
        }
    }

    private suspend fun sendRetiredAcceptCompensation(
        entry: IncomingEntry,
        label: String
    ) {
        val response = lock.withLock {
            terminalIncoming[entry.session.transferId]?.response
                ?: if (entry.session.transferId in ambiguousIncomingTransferIds ||
                    ambiguousIncomingCapacityExhausted
                ) {
                    IncomingTerminalResponse.Cancel("accept did not commit")
                } else {
                    null
                }
        }
        if (response == null) return
        sendIncomingTerminalResponse(
            transferId = entry.session.transferId,
            response = response,
            expectedEpoch = entry.writeEpoch,
            label = "$label FILE_CANCEL"
        )
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
        val removed = removeIncoming(entry.session.transferId, entry) ?: return
        removed.cancelJobs()
        if (!terminalizeIncoming(removed, FileTransferState.Failed(err))) return
        sendBestEffort("FILE_CANCEL for ${entry.session.transferId}", entry.writeEpoch) { connection ->
            protocol.sendFileCancel(
                connection,
                entry.session.transferId,
                if (protocolViolation) {
                    "receiver protocol failure"
                } else {
                    "receiver storage failure"
                }
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
        // Preserve an already-classified failure so callers retain the
        // original platform callback as `cause`. Wrapping it again would make
        // the public cause another FileTransferFailed and hide the storage or
        // integrity exception that actually failed the operation. Only reuse
        // a classification that agrees with the wire result we are sending;
        // mismatched failures are wrapped defensively below.
        val classified = cause as? P2pError.FileTransferFailed
        val error = if (
            classified != null &&
            classified.kind == kind &&
            classified.phase == phase &&
            classified.retryability == retryability &&
            classified.transferId == entry.session.transferId.toString()
        ) {
            classified
        } else {
            fileFailure(
                kind,
                phase,
                retryability,
                entry.session.transferId,
                reason,
                cause
            )
        }
        val response = IncomingTerminalResponse.Result(
            SecureFileResult(
                entry.session.transferId,
                code,
                phase,
                safeWireFailureReason(code)
            )
        )
        val removed = removeIncomingTerminal(
            entry.session.transferId,
            entry,
            response
        ) ?: return
        removed.cancelJobs()
        if (!terminalizeIncoming(removed, FileTransferState.Failed(error))) return
        sendIncomingTerminalResponse(
            transferId = entry.session.transferId,
            response = response,
            expectedEpoch = entry.writeEpoch,
            label = "FILE_RESULT"
        )
    }

    private fun safeWireFailureReason(code: FileResultCode): String = when (code) {
        FileResultCode.DIGEST_MISMATCH -> "content digest mismatch"
        FileResultCode.STORAGE_FAILURE -> "receiver storage failure"
        FileResultCode.PROTOCOL_FAILURE -> "file-transfer protocol failure"
        FileResultCode.SOURCE_CHANGED -> "prepared source changed"
        FileResultCode.TIMEOUT -> "file-transfer timeout"
    }

    private fun incomingFailureResponse(
        transferId: MessageId,
        error: P2pError.FileTransferFailed
    ): IncomingTerminalResponse.Result {
        val code = when (error.kind) {
            FileTransferFailureKind.INTEGRITY -> FileResultCode.DIGEST_MISMATCH
            FileTransferFailureKind.TRANSFER_PROTOCOL -> FileResultCode.PROTOCOL_FAILURE
            FileTransferFailureKind.SOURCE_CHANGED -> FileResultCode.SOURCE_CHANGED
            FileTransferFailureKind.TIMEOUT -> FileResultCode.TIMEOUT
            else -> FileResultCode.STORAGE_FAILURE
        }
        return IncomingTerminalResponse.Result(
            SecureFileResult(
                transferId = transferId,
                code = code,
                phase = error.phase,
                reason = safeWireFailureReason(code)
            )
        )
    }

    private fun incomingRejectResponse(reason: String?): IncomingTerminalResponse.Reject =
        IncomingTerminalResponse.Reject(
            boundedTerminalReason(reason, fallback = "receiver rejected transfer")
        )

    private fun incomingCancelResponse(reason: String?): IncomingTerminalResponse.Cancel =
        IncomingTerminalResponse.Cancel(
            boundedTerminalReason(reason, fallback = "receiver cancelled transfer")
        )

    private fun boundedTerminalReason(reason: String?, fallback: String): String? {
        if (reason == null) return null
        return try {
            validateWireText(
                value = reason,
                field = "file-transfer terminal reason",
                maxChars = ProtocolConstants.MAX_REASON_PAYLOAD_BYTES,
                maxUtf8Bytes = ProtocolConstants.MAX_REASON_PAYLOAD_BYTES,
                requireNonBlank = true
            )
            reason
        } catch (_: IllegalArgumentException) {
            fallback
        }
    }

    private suspend fun sendIncomingTerminalResponse(
        transferId: MessageId,
        response: IncomingTerminalResponse,
        expectedEpoch: FileTransferWriteEpoch,
        label: String
    ) {
        sendCleanupBestEffort("$label for $transferId", expectedEpoch) { connection ->
            when (response) {
                is IncomingTerminalResponse.Commit ->
                    protocol.sendFileCommit(connection, response.value)
                is IncomingTerminalResponse.Result ->
                    protocol.sendFileResult(connection, response.value)
                is IncomingTerminalResponse.Reject ->
                    protocol.sendFileReject(connection, transferId, response.reason)
                is IncomingTerminalResponse.Cancel ->
                    protocol.sendFileCancel(connection, transferId, response.reason)
            }
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
        sendBestEffortWithinDeadline(
            label = label,
            expectedEpoch = expectedEpoch,
            // True caller cancellation is still propagated because the
            // invoking context is inactive. A callback-generated
            // CancellationException is only a failed best-effort write and
            // must not cancel the otherwise healthy event/session coroutine.
            preserveCancellation = false,
            block = block
        )
    }

    /** Bounded cleanup notification used only after ownership is already terminal. */
    private suspend fun sendCleanupBestEffort(
        label: String,
        expectedEpoch: FileTransferWriteEpoch,
        block: suspend (RawConnection) -> Unit
    ) {
        sendBestEffortWithinDeadline(
            label = label,
            expectedEpoch = expectedEpoch,
            preserveCancellation = false,
            block = block
        )
    }

    private suspend fun sendBestEffortWithinDeadline(
        label: String,
        expectedEpoch: FileTransferWriteEpoch,
        preserveCancellation: Boolean,
        block: suspend (RawConnection) -> Unit
    ) {
        val issue = captureCleanupIssue(
            resource = "file-transfer $label",
            timeoutMillis = config.offerTimeoutMillis,
            preserveCancellation = preserveCancellation,
            operationDispatcher = protocolOperationDispatcher,
            deadlineDispatcher = operationDeadlineDispatcher,
            operationGate = protocolOperationGate
        ) {
            withEpochWrite(expectedEpoch, block)
        }
        if (issue != null) {
            logger.debug(
                "Session $sessionId: bounded best-effort $label failed: " +
                    (issue.cause.message ?: issue.cause::class.simpleName)
            )
        }
    }

    /**
     * Release an incoming session's receiver/destination after its public
     * terminal state has already committed. The worker enters NonCancellable
     * so it eventually acquires an operation lock held by a late write or
     * commit, while [captureCleanupIssue] bounds how long that worker can hold
     * the caller.
     */
    internal suspend fun cleanupIncomingTerminalResources(
        session: IncomingFileSession,
        cause: P2pError.FileTransferFailed?
    ) {
        val issue = captureCleanupIssue(
            resource = "incoming transfer ${session.transferId}",
            timeoutMillis = config.offerTimeoutMillis,
            preserveCancellation = false,
            operationDispatcher = independentCleanupDispatcher,
            deadlineDispatcher = operationDeadlineDispatcher,
            operationGate = cleanupOperationGate
        ) {
            withContext(NonCancellable) {
                session.detachTerminalResources()?.abort(cause)
            }
        }
        if (issue != null) {
            logCleanupIssues(logger, "incoming file terminal cleanup", listOf(issue))
        }
    }

    internal suspend fun cleanupOutgoingSource(source: RawSource, label: String) {
        val issue = captureCleanupIssue(
            resource = label,
            timeoutMillis = config.offerTimeoutMillis,
            preserveCancellation = false,
            operationDispatcher = independentCleanupDispatcher,
            deadlineDispatcher = operationDeadlineDispatcher,
            operationGate = cleanupOperationGate
        ) {
            source.close()
        }
        if (issue != null) {
            logCleanupIssues(logger, "outgoing file source cleanup", listOf(issue))
        }
    }

    /** Destination ownership has not been installed in [IncomingFileSession]. */
    private suspend fun abortUnownedDestination(
        destination: FileTransferDestination,
        cause: P2pError.FileTransferFailed?,
        label: String
    ) {
        val issue = captureCleanupIssue(
            resource = label,
            timeoutMillis = config.offerTimeoutMillis,
            preserveCancellation = false,
            operationDispatcher = independentCleanupDispatcher,
            deadlineDispatcher = operationDeadlineDispatcher,
            operationGate = cleanupOperationGate
        ) {
            destination.abort(cause)
        }
        if (issue != null) {
            logCleanupIssues(logger, "file destination abort", listOf(issue))
        }
    }

    /**
     * A callback may throw [CancellationException] without the invoking
     * coroutine having been cancelled. Treat that as the callback's typed
     * operational failure; true caller cancellation is propagated directly
     * by [runBoundedIndependentOperation] before a result reaches this helper.
     */
    private fun classifyCallbackCancellation(
        cause: Throwable,
        kind: FileTransferFailureKind,
        phase: FileTransferPhase,
        retryability: Retryability,
        transferId: MessageId?,
        prefix: String
    ): Throwable = if (cause is CancellationException) {
        fileFailure(
            kind = kind,
            phase = phase,
            retryability = retryability,
            transferId = transferId,
            reason = "$prefix: ${cause.message ?: "callback threw CancellationException"}",
            cause = cause
        )
    } else {
        cause
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
        check(current.secureOffer == null) {
            "Authenticated inbound removal requires a terminal ledger outcome"
        }
        removeIncomingLocked(current, terminalResponse = null)
    }

    private suspend fun removeIncomingTerminal(
        transferId: MessageId,
        expected: IncomingEntry? = null,
        response: IncomingTerminalResponse
    ): IncomingEntry? = lock.withLock {
        val current = incoming[transferId] ?: return@withLock null
        if (expected != null && current !== expected) return@withLock null
        removeIncomingLocked(current, response)
    }

    private fun removeIncomingLocked(
        current: IncomingEntry,
        terminalResponse: IncomingTerminalResponse?
    ): IncomingEntry {
        val secureOffer = current.secureOffer
        if (secureOffer != null) {
            checkNotNull(terminalResponse) {
                "Authenticated inbound removal requires a terminal ledger outcome"
            }
            check(terminalIncoming[current.session.transferId] == null) {
                "Authenticated inbound transfer already has a terminal ledger outcome"
            }
            check(terminalIncoming.size < MAX_TERMINAL_INCOMING_TRANSACTIONS) {
                "Authenticated inbound terminal ledger reservation was lost"
            }
            terminalIncoming[current.session.transferId] = TerminalIncomingTransaction(
                offer = secureOffer,
                response = terminalResponse
            )
        }
        incoming.remove(current.session.transferId)
        removePendingOfferLocked(current.session)
        current.acceptanceCommitted.complete(false)
        return current
    }

    private fun secureIncomingTransactionCountLocked(): Int =
        terminalIncoming.size + incoming.values.count { it.secureOffer != null }

    private fun removePendingOfferLocked(session: IncomingFileSession) {
        val current = _pendingFileOffers.value
        if (current.none { it === session }) return
        _pendingFileOffers.value = immutableListSnapshot(current.filterNot { it === session })
    }

    private fun allocateTransferIdLocked(): MessageId {
        if (ambiguousIncomingCapacityExhausted) {
            throw fileFailure(
                kind = FileTransferFailureKind.TRANSFER_PROTOCOL,
                phase = FileTransferPhase.OFFER,
                retryability = Retryability.RETRY_NEW_SESSION,
                transferId = null,
                reason = "Ambiguous incoming transfer-id capacity is exhausted; reconnect required"
            )
        }
        repeat(MAX_TRANSFER_ID_ATTEMPTS) {
            val candidate = MessageId.random(random)
            if (candidate !in outgoing && candidate !in incoming &&
                candidate !in terminalIncoming && candidate !in ambiguousIncomingTransferIds
            ) {
                return candidate
            }
        }
        throw fileFailure(
            kind = FileTransferFailureKind.TRANSFER_PROTOCOL,
            phase = FileTransferPhase.OFFER,
            retryability = Retryability.RETRY_NEW_SESSION,
            transferId = null,
            reason = "Unable to allocate a unique transfer id after $MAX_TRANSFER_ID_ATTEMPTS attempts"
        )
    }

    private fun requireOutgoingCapacityLocked() {
        if (outgoing.size < MAX_ACTIVE_OUTGOING_TRANSFERS) return
        throw fileFailure(
            kind = FileTransferFailureKind.TRANSPORT,
            phase = FileTransferPhase.OFFER,
            retryability = Retryability.RETRY_SAME_SESSION,
            transferId = null,
            reason = "Concurrent outgoing transfer capacity " +
                "($MAX_ACTIVE_OUTGOING_TRANSFERS) is exhausted"
        )
    }

    /** Commit public terminal state and detach cleanup from protocol progress. */
    private suspend fun terminalizeOutgoing(
        entry: OutgoingEntry,
        state: FileTransferState,
        cleanupLabel: String
    ): Boolean {
        val resources = entry.handle.transitionTerminalWithoutCleanup(state) ?: return false
        resources.source?.let { source ->
            launchIndependentCleanup {
                cleanupOutgoingSource(source, cleanupLabel)
            }
        }
        return true
    }

    /** Commit public terminal state and detach destination cleanup from callers. */
    private fun terminalizeIncoming(
        entry: IncomingEntry,
        state: FileTransferState
    ): Boolean {
        if (!entry.session.transitionTerminalWithoutCleanup(state)) return false
        launchIncomingTerminalCleanup(
            entry.session,
            (state as? FileTransferState.Failed)?.error as? P2pError.FileTransferFailed
        )
        return true
    }

    /**
     * Start terminal resource cleanup outside the session coroutine tree.
     * [beginCloseAll] starts every source/destination cleanup before it returns,
     * and hands these jobs to [awaitCloseAll], so teardown is concurrent,
     * owned, and bounded by one configured deadline rather than N sequential
     * deadlines.
     */
    private fun launchIncomingTerminalCleanup(
        session: IncomingFileSession,
        cause: P2pError.FileTransferFailed?
    ): Job = launchIndependentCleanup {
        cleanupIncomingTerminalResources(session, cause)
    }

    private fun launchIndependentCleanup(block: suspend () -> Unit): Job {
        val owner = SupervisorJob()
        val job = CoroutineScope(owner + independentCleanupDispatcher).launch(
            start = CoroutineStart.UNDISPATCHED
        ) {
            block()
        }
        job.invokeOnCompletion { owner.cancel() }
        return job
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
        val jobs = listOfNotNull(timer, sender, overallTimer).distinct()
        cancelTimers()
        sender?.cancel()
        sender = null
        return jobs
    }

    private fun OutgoingEntry.cancelTimers() {
        timer?.cancel()
        overallTimer?.cancel()
        timer = null
        overallTimer = null
        idleGeneration++
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
        data class ReplayTerminal(
            val response: IncomingTerminalResponse
        ) : OfferInsertion
        data object RETIRED : OfferInsertion
        data object CONFLICT : OfferInsertion
        data class Capacity(val reason: String) : OfferInsertion
        data class Inserted(val entry: IncomingEntry) : OfferInsertion
    }

    private sealed interface IncomingFinalization {
        data object Missing : IncomingFinalization
        data object AlreadyStarted : IncomingFinalization
        data class NotAccepted(
            val entry: IncomingEntry,
            val phase: IncomingPhase
        ) : IncomingFinalization
        data class Started(val entry: IncomingEntry) : IncomingFinalization
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

    private data class PreparedSourceSnapshot(
        val sizeBytes: Long,
        val sha256: Sha256Digest
    )
}

private const val MAX_ACTIVE_INCOMING_TRANSFERS: Int = 64
private const val MAX_INCOMING_OFFER_EVENT_BUFFER: Int = 64
private const val MAX_ACTIVE_OUTGOING_TRANSFERS: Int = 64
private const val MAX_TERMINAL_INCOMING_TRANSACTIONS: Int = 256
private const val MAX_AMBIGUOUS_INCOMING_TRANSFER_IDS: Int = 256
private const val MAX_CONCURRENT_FILE_OPERATIONS: Int = 8
private const val MAX_CONCURRENT_OUTGOING_STREAMS: Int = 8
private const val MAX_TRANSFER_ID_ATTEMPTS: Int = 128
private const val MAX_TRANSFER_FAILURE_REASON_CHARS: Int = 512

/** Referential generation marker for dispatcher writes. */
private class FileTransferWriteEpoch

private class StaleFileTransferEpochException(message: String) : IllegalStateException(message)
