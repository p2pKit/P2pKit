package dev.p2pkit.core.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.FileTransferFailureKind
import dev.p2pkit.core.FileTransferPhase
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.core.Retryability
import dev.p2pkit.core.protocol.P2pProtocol
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.protocol.ProtocolSessionState
import dev.p2pkit.core.internal.security.SecureTerminalFailureSource
import dev.p2pkit.core.transfer.FileTransferConfig
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.core.transfer.PreparedFileSource
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CompletableJob
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.ClosedReceiveChannelException
import kotlinx.coroutines.channels.ReceiveChannel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.io.RawSource
import kotlin.random.Random

/**
 * Hook into [P2pSessionImpl] that drives reconnect attempts when the
 * underlying connection dies. Wired by [SessionManager] for outgoing sessions
 * when [dev.p2pkit.core.ReconnectPolicy.Enabled] is configured.
 *
 * Implementations run their retry loop on the session's coroutine scope, so
 * `session.close()` and `kit.stop()` cancel the loop automatically.
 */
internal interface ReconnectHandler {
    suspend fun onConnectionLost(session: P2pSessionImpl)

    /**
     * Called synchronously at the instant the session transitions to
     * `Reconnecting`, under the connection lock and before the retry loop is
     * launched. Lets the handler snapshot any "wake early on network
     * recovery" baseline at the exact Reconnecting edge, so a path-Satisfied
     * signal that arrives between the transition and the (async) start of the
     * retry loop is not missed (AUDIT-2026-06). Default: no-op.
     */
    fun onWillReconnect() {}
}

/**
 * SessionStore-side view of "is this session still the one we publish?"
 * Used by [P2pSessionImpl.routeEvents] to detect zombie emissions —
 * messages emitted to the public `incoming` flow while [SessionStore] has
 * already evicted or replaced this session in its byPeer map / published
 * sessions StateFlow.
 *
 * Read from immutable snapshots published by [SessionStore]. The caller
 * only enforces this result after its own registration transaction commits;
 * before that point the session is intentionally absent from the store.
 */
internal data class SessionRegistration(
    /**
     * Session id currently in SessionStore's byPeer map for this peer, or
     * `null` if there is no entry. Equal to the calling session's `id`
     * when this session is the registered one.
     */
    val activeSessionId: String?,
    /** True iff this exact session instance is still in SessionStore's published sessions list. */
    val isInPublicList: Boolean
)

private data class QueuedApplicationMessage(
    val message: P2pMessage,
    val retainedBytes: Long
)

/**
 * Concrete [P2pSession] backed by a [RawConnection]. The connection can be
 * swapped via [rearmWith] when a [ReconnectHandler] re-establishes the link
 * after a transient failure — the public [P2pSession] identity (and any flows
 * the app subscribed to) survives the swap.
 *
 * The session serializes outbound writes through a [Mutex] (concurrent `send`
 * calls never produce interleaved frames). Inbound events arrive on the
 * current epoch's [events] channel — DATA → [incoming], PING → reply with
 * PONG, PONG → reset keep-alive deadline, CLOSE → clean close (no retry),
 * ERROR → connection-lost (eligible for retry).
 */
internal class P2pSessionImpl(
    override val id: String,
    override val peer: Peer,
    override val peerIdentity: PeerIdentity = PeerIdentity(peer.id),
    initialConnection: RawConnection,
    initialEvents: ReceiveChannel<ProtocolEvent>,
    initialReaderJob: Job? = null,
    initialProtocolState: ProtocolSessionState = ProtocolSessionState.legacy(),
    private val protocol: P2pProtocol,
    private val parentScope: CoroutineScope,
    private val keepAlive: KeepAliveConfig,
    private val clock: () -> Long,
    private val monotonicClock: () -> Long = clock,
    private val logger: P2pLogger,
    private val fileTransferConfig: FileTransferConfig = FileTransferConfig(),
    private val random: Random = Random.Default,
    /**
     * Optional best-effort lookup of this session's registration state in
     * the owning SessionManager. Wired by SessionManager itself; `null`
     * for stand-alone tests that don't go through a SessionManager. When
     * present, [routeEvents] consults it before every `Message` emit after
     * registration commits and drops the message if this session is no
     * longer published. Before commit, absence from the store is expected
     * and must not be mistaken for detachment.
     */
    private val lookupRegistration: ((P2pSession) -> SessionRegistration)? = null,
    private val beforeApplicationMessageEmitForTest: (suspend (P2pMessage) -> Unit)? = null,
    private val afterTerminalClaimForTest: (suspend () -> Unit)? = null,
    private val afterTerminalStatePublishedForTest: (suspend () -> Unit)? = null,
    private val applicationDeliveryCloseTimeoutMillis: Long = SESSION_RESOURCE_CLOSE_TIMEOUT_MS,
    private val afterApplicationDeliveryDrainForTest: (suspend () -> Unit)? = null
) : P2pSession {

    init {
        require(applicationDeliveryCloseTimeoutMillis > 0L) {
            "applicationDeliveryCloseTimeoutMillis must be > 0"
        }
    }

    internal val usesAuthenticatedFileTransfer: Boolean
        get() = protocolState.secure

    private val sessionJob = SupervisorJob(parent = parentScope.coroutineContext[Job])
    private val scope = CoroutineScope(parentScope.coroutineContext + sessionJob)

    private val _state = MutableStateFlow(ConnectionState.Connected)
    override val state: StateFlow<ConnectionState> = _state.asStateFlow()

    private val _incoming = MutableSharedFlow<P2pMessage>(replay = 0)
    override val incoming: SharedFlow<P2pMessage> = _incoming.asSharedFlow()

    /* Protocol control never waits for an application collector. */
    private val applicationMessages = Channel<QueuedApplicationMessage>(Channel.UNLIMITED)
    private val applicationMessageQueueLock = Mutex()
    private val applicationEmissionMutex = Mutex()
    private var queuedApplicationMessages: Int = 0
    private var queuedApplicationBytes: Long = 0L
    private var applicationDeliveryJob: Job? = null
    private val registrationCommitted = MutableStateFlow(false)

    private val sendMutex = Mutex()
    private val lastPongAt = MutableStateFlow(monotonicClock())

    /**
     * Lock guarding [connection], [events], [readerJob], [epochJob], [epochToken], and the
     * [_state] transitions driven by connection loss. Held briefly during
     * [rearmWith] and the `onConnectionLost` decision.
     */
    private val connectionLock = Mutex()

    /**
     * Non-null while one terminal transition owns the interval between its
     * final epoch/state decision and terminal-state publication. Guarded by
     * [connectionLock]. Reconnect, local close, and new public writes must not
     * mutate or use the epoch once a terminal owner has claimed it.
     */
    private var terminalTransitionClaim: Any? = null

    /**
     * Exact result of the one local close transaction. A caller that observes
     * [ConnectionState.Closing] joins this owner instead of running another
     * CLOSE/cleanup transaction or racing its timeout against the leader.
     */
    private val localCloseCompletion = CompletableDeferred<List<CleanupIssue>>()

    private var connection: RawConnection = initialConnection
    private var events: ReceiveChannel<ProtocolEvent> = initialEvents
    private var readerJob: Job? = initialReaderJob
    private var protocolState: ProtocolSessionState = initialProtocolState
    private var epochToken: ConnectionEpochToken = ConnectionEpochToken()

    /**
     * Job that owns this epoch's [routeEvents] and [keepAliveLoop]. Cancelled
     * on rearm so the new epoch starts cleanly; cancelled on close so the
     * loops exit when the session is torn down.
     */
    private var epochJob: CompletableJob? = null

    /** Serializes reconnect adoption without holding [connectionLock] across cleanup. */
    private val rearmLock = Mutex()

    /**
     * Wired by [SessionManager] for outgoing sessions when
     * [dev.p2pkit.core.ReconnectPolicy.Enabled] is configured. Null for
     * incoming sessions or when the policy is `Disabled`.
     */
    internal var reconnectHandler: ReconnectHandler? = null

    private val fileTransferDispatcherLazy = lazy {
        FileTransferDispatcher(
            sessionId = id,
            remotePeer = peer,
            protocol = protocol,
            getConnection = { connection },
            getProtocolState = { protocolState },
            sendMutex = sendMutex,
            config = fileTransferConfig,
            scope = scope,
            random = random,
            logger = logger
        )
    }
    private val fileTransferDispatcher: FileTransferDispatcher get() = fileTransferDispatcherLazy.value

    @Deprecated("Observe pendingFileOffers")
    override val incomingFiles: SharedFlow<P2pFileOffer>
        get() = fileTransferDispatcher.incomingFiles

    override val pendingFileOffers: StateFlow<List<P2pFileOffer>>
        get() = fileTransferDispatcher.pendingFileOffers

    fun start() {
        check(applicationDeliveryJob == null) { "Session $id was already started" }
        // Establish file-transfer admission before any protocol event or
        // terminal transition can run. A terminal owner can then always seal
        // this dispatcher; no late lazy initialization can escape closeAll.
        fileTransferDispatcherLazy.value
        applicationDeliveryJob = scope.launch { deliverApplicationMessages() }
        startEpoch()
    }

    internal fun markRegistrationCommitted() {
        registrationCommitted.value = true
    }

    private fun startEpoch() {
        val job = SupervisorJob(parent = sessionJob)
        epochJob = job
        val epochScope = CoroutineScope(scope.coroutineContext + job)
        // Capture the current connection ref once so all epoch-bound loops act on
        // the same epoch's connection. Rearm replaces `connection` and
        // cancels the epoch; new loops then see the new ref.
        val epochConnection = connection
        val epoch = ConnectionEpoch(epochConnection, readerJob, job, epochToken)
        lastPongAt.value = monotonicClock()
        epochScope.launch { routeEvents(events) }
        epochScope.launch { keepAliveLoop(epochConnection) }
        // Keep liveness enforcement independent of outbound writes. A peer
        // that stops draining its socket can park another holder of
        // sendMutex; the PONG deadline must still be evaluated while that
        // writer is suspended.
        epochScope.launch { pongDeadlineWatchdog() }
        epochScope.launch { observeSecureTerminalFailure(epochConnection, epoch) }
        epochScope.launch { observeRawState(epochConnection, epoch) }
    }

    private suspend fun observeSecureTerminalFailure(
        epochConnection: RawConnection,
        epoch: ConnectionEpoch
    ) {
        val source = epochConnection as? SecureTerminalFailureSource ?: return
        val failure = source.terminalFailure.first { it != null } ?: return
        transitionForSecureFailure(failure, epoch)
    }

    private suspend fun transitionForSecureFailure(
        failure: P2pError,
        epoch: ConnectionEpoch
    ) {
        val (kind, reason) = when (failure) {
            is P2pError.AuthenticationFailed ->
                FileTransferFailureKind.AUTHENTICATION to failure.reason
            is P2pError.ProtocolError ->
                FileTransferFailureKind.TRANSFER_PROTOCOL to failure.reason
            else -> error("Unsupported secure terminal failure: ${failure::class.simpleName}")
        }
        transitionToTerminal(
            target = ConnectionState.Failed,
            cause = reason,
            fileFailureKind = kind,
            fileRetryability = Retryability.NOT_RETRYABLE,
            expectedEpoch = epoch
        )
    }

    /**
     * Watches the underlying [RawConnection.state] and triggers
     * [onConnectionLost] the moment it transitions to `Closed` or `Failed`
     * while our session is still `Connected`. Before this loop existed the
     * session's authoritative source for "connection died" was either:
     *   (a) the read flow ending (which fires from `routeEvents` when the
     *       protocol's event channel closes — depends on the OS surfacing
     *       a receive error, which can lag a real outage), or
     *   (b) the keep-alive PING send failing or PONG timing out (worst
     *       case one full `pingIntervalMillis` after the break).
     *
     * On iOS specifically, an `nw_connection_send` error sets `closed=true`
     * + `_state = Closed` synchronously in the send completion handler.
     * Without this observer, `session.state` would still report Connected
     * for up to a ping interval; users see "messages sent successfully" in
     * the UI logic but the bytes never reach the wire.
     *
     * Once raw goes to a terminal state we only act if our own state is
     * still `Connected`. If we're already `Closing`, `Reconnecting`, or
     * a terminal state, [onConnectionLost] short-circuits inside its mutex.
     *
     * AUDIT-2026-07 (SES-1): before classifying on the raw state alone, this
     * observer defers for a bounded window so [routeEvents] can classify from
     * the protocol events that are already buffered. The transports collapse
     * remote EOF and a read failure into the same signature (read flow
     * completes normally, raw state flips to `Closed`), so the raw state by
     * itself cannot distinguish a clean goodbye from an abrupt loss — but
     * ordering can: a CLOSE frame is parsed and buffered into the events
     * channel strictly *before* the read flow completes, so by the time the
     * raw state flips, any CLOSE that will ever arrive is already queued
     * ahead of the channel close. Within the window, [routeEvents] latches
     * the deterministic outcome (CLOSE frame → clean `Closed` via
     * [markCleanlyClosed]; completion without CLOSE → [onConnectionLost]).
     * The raw-only fallback after the window stays load-bearing for
     * send-side-only failures where the read side lags (e.g. an iOS send
     * error flips the raw state synchronously) — the case this observer was
     * built for.
     */
    private suspend fun observeRawState(
        epochConnection: RawConnection,
        epoch: ConnectionEpoch
    ) {
        epochConnection.state.collect { rawState ->
            when (rawState) {
                ConnectionState.Closed, ConnectionState.Failed -> {
                    if (_state.value == ConnectionState.Connected) {
                        val secureFailure =
                            (epochConnection as? SecureTerminalFailureSource)
                                ?.terminalFailure?.value
                        if (secureFailure != null) {
                            transitionForSecureFailure(secureFailure, epoch)
                            return@collect
                        }
                        // AUDIT-2026-07 (SES-1): bounded deferral to the
                        // protocol-event classification (see KDoc above).
                        // withTimeoutOrNull swallows only its own timeout;
                        // a real CancellationException still propagates.
                        withTimeoutOrNull(RAW_TERMINAL_CLASSIFICATION_GRACE_MS) {
                            _state.first { it != ConnectionState.Connected }
                        }
                        if (_state.value == ConnectionState.Connected) {
                            val delayedSecureFailure =
                                (epochConnection as? SecureTerminalFailureSource)
                                    ?.terminalFailure?.value
                            if (delayedSecureFailure != null) {
                                transitionForSecureFailure(delayedSecureFailure, epoch)
                            } else {
                                onConnectionLost("raw connection -> $rawState")
                            }
                        }
                    }
                }
                else -> { /* Connecting / Connected / Handshaking — wait */ }
            }
        }
    }

    /**
     * AUDIT-2026-07 (API-2, decision #12a): typed-error contract at the
     * public [send]/[sendFile] boundary. [CancellationException] and
     * already-typed [P2pError]s pass through as-is; any other [Throwable] —
     * raw platform write failures (JVM/Android `IOException` including the
     * 30 s write-watchdog timeout, iOS `nw_connection` failure shapes),
     * internal state exceptions, argument-validation errors — is wrapped in
     * [P2pError.ConnectionFailed] with the original exception preserved as
     * the error's `cause`.
     *
     * The wrap lives here, at the public boundary, and NOT in
     * `DefaultP2pProtocol.writeFrame`: internal callers (keep-alive
     * PING/PONG, the file-transfer dispatcher, the best-effort CLOSE sender)
     * keep seeing the raw exceptions their classification logic expects.
     * Because this is commonMain, the contract is identical on JVM, Android,
     * and iOS.
     */
    private inline fun <T> typedSendBoundary(operation: String, block: () -> T): T =
        try {
            block()
        } catch (e: CancellationException) {
            throw e
        } catch (e: P2pError) {
            throw e
        } catch (e: Throwable) {
            throw P2pError.ConnectionFailed(
                "$operation failed on session $id: ${e.message ?: e::class.simpleName}"
            ).also { it.underlying = e }
        }

    private inline fun <T> typedFileTransferBoundary(block: () -> T): T =
        try {
            block()
        } catch (e: CancellationException) {
            throw e
        } catch (e: P2pError) {
            throw e
        } catch (e: Throwable) {
            val invalidMetadata = e is IllegalArgumentException
            throw P2pError.FileTransferFailed(
                kind = if (invalidMetadata) {
                    FileTransferFailureKind.INVALID_METADATA
                } else {
                    FileTransferFailureKind.TRANSPORT
                },
                phase = FileTransferPhase.OFFER,
                retryability = if (invalidMetadata) {
                    Retryability.NOT_RETRYABLE
                } else {
                    Retryability.RETRY_NEW_SESSION
                },
                transferId = null,
                reason = (
                    "sendFile failed on session $id: " +
                        (e.message ?: e::class.simpleName ?: "unknown failure")
                            .take(MAX_TRANSFER_FAILURE_REASON_CHARS)
                    ).take(MAX_TRANSFER_FAILURE_REASON_CHARS)
            ).also { it.underlying = e }
        }

    override suspend fun send(message: P2pMessage) {
        val target = connectedProtocolTarget("send")
        // AUDIT-2026-07 (API-2): see [typedSendBoundary].
        typedSendBoundary("send") {
            sendMutex.withLock {
                ensureProtocolTargetActive(target, "send")
                protocol.sendMessage(target.connection, message, target.protocolState)
            }
        }
    }

    private suspend fun connectedProtocolTarget(operation: String): ProtocolTarget =
        connectionLock.withLock {
            if (_state.value != ConnectionState.Connected || terminalTransitionClaim != null) {
                throw P2pError.ConnectionFailed(
                    "Session $id is ${_state.value}; cannot $operation"
                )
            }
            ProtocolTarget(connection, protocolState, epochToken)
        }

    private suspend fun ensureProtocolTargetActive(target: ProtocolTarget, operation: String) {
        connectionLock.withLock {
            if (
                _state.value != ConnectionState.Connected ||
                terminalTransitionClaim != null ||
                epochToken !== target.epochToken
            ) {
                throw P2pError.ConnectionFailed(
                    "Session $id changed connection epoch before $operation could write"
                )
            }
        }
    }

    @Deprecated(
        "Legacy protocol-v1 transfer only; use sendFile(name, mimeType, PreparedFileSource)"
    )
    override suspend fun sendFile(
        name: String,
        sizeBytes: Long,
        mimeType: String?,
        source: RawSource
    ): P2pFileTransfer {
        ensureFileTransferCanStart()
        // Ownership-on-throw
        // contract is documented on [P2pSession.sendFile]: local validation
        // refusals leave [source] caller-owned and open; once the dispatcher
        // starts its registration transaction, throws close it via the
        // handle's terminal transition (FIL-1 close-once guard).
        return typedFileTransferBoundary {
            fileTransferDispatcher.sendFile(name, sizeBytes, mimeType, source)
        }
    }

    override suspend fun sendFile(
        name: String,
        mimeType: String?,
        source: PreparedFileSource
    ): P2pFileTransfer {
        ensureFileTransferCanStart()
        return typedFileTransferBoundary {
            fileTransferDispatcher.sendPreparedFile(name, mimeType, source)
        }
    }

    private suspend fun ensureFileTransferCanStart() {
        val unavailable = connectionLock.withLock {
            if (_state.value == ConnectionState.Connected && terminalTransitionClaim == null) {
                null
            } else {
                _state.value
            }
        }
        if (unavailable != null) {
            throw P2pError.FileTransferFailed(
                kind = FileTransferFailureKind.REMOTE_DISCONNECTED,
                phase = FileTransferPhase.OFFER,
                retryability = Retryability.RETRY_NEW_SESSION,
                transferId = null,
                reason = "Session $id is $unavailable or terminating; cannot send file"
            )
        }
    }

    override suspend fun close() {
        // Commit local-close intent before touching the wire. Raw-state and
        // protocol observers then see Closing and cannot classify the socket
        // teardown as an unrelated Failed outcome. Exactly one caller owns
        // the bounded cleanup; concurrent close callers join its result.
        var joinLocalClose = false
        var localCloseConnection: RawConnection? = null
        val ownsLocalClose = connectionLock.withLock {
            if (terminalTransitionClaim != null) {
                false
            } else when (_state.value) {
                ConnectionState.Closed, ConnectionState.Failed -> false
                ConnectionState.Closing -> {
                    joinLocalClose = true
                    false
                }
                else -> {
                    _state.value = ConnectionState.Closing
                    localCloseConnection = connection
                    true
                }
            }
        }
        if (joinLocalClose) {
            val issues = localCloseCompletion.await()
            if (issues.isNotEmpty()) {
                throw cleanupError("session $id close", issues)
            }
            return
        }
        if (!ownsLocalClose) {
            captureCleanupIssue(
                resource = "session $id runtime",
                timeoutMillis = SESSION_RUNTIME_CLOSE_TIMEOUT_MS
            ) {
                sessionJob.join()
            }?.let { issue ->
                logCleanupIssues(logger, "session $id close", listOf(issue))
                throw cleanupError("session $id close", listOf(issue))
            }
            return
        }

        var cleanupIssues: List<CleanupIssue> = emptyList()
        withContext(NonCancellable) {
            try {
                // Best-effort CLOSE frame BEFORE we tear the wire down. Must
                // happen before [transitionToTerminal] cancels the epoch —
                // once the epoch is gone, [connection] is closed and the
                // protocol writer would throw. Only the WAIT is bounded; raw
                // close below is what unblocks a cancellation-ignoring write.
                // Start inline through the first real suspension so the
                // bounded wait measures send/mutex progress, not admission
                // latency on a saturated dispatcher. Without UNDISTPATCHED,
                // the child could remain queued for the whole two-second
                // window; teardown would then cancel the raw connection
                // without ever attempting the CLOSE frame, causing a clean
                // peer shutdown to look like a reconnectable network loss.
                val closeSend = scope.launch(start = CoroutineStart.UNDISPATCHED) {
                    runCatching {
                        sendMutex.withLock {
                            protocol.sendClose(checkNotNull(localCloseConnection))
                        }
                    }
                }
                withTimeoutOrNull(CLOSE_FRAME_TIMEOUT_MS) { closeSend.join() }

                val issues = transitionToTerminal(
                    ConnectionState.Closed,
                    "user close()",
                    fileFailureKind = FileTransferFailureKind.TRANSPORT,
                    fileRetryability = Retryability.NOT_RETRYABLE,
                    allowFromClosing = true
                ).toMutableList()
                closeSend.cancel()

                // transitionToTerminal cancels the runtime after every
                // terminal cleanup attempt. Bound the join too: a blocking
                // child must not make close() unbounded after a failed raw
                // close.
                captureCleanupIssue(
                    resource = "session $id runtime",
                    timeoutMillis = SESSION_RUNTIME_CLOSE_TIMEOUT_MS,
                    preserveCancellation = false
                ) {
                    sessionJob.cancelAndJoin()
                }?.let(issues::add)
                cleanupIssues = issues
                logCleanupIssues(logger, "session $id close", issues)
                localCloseCompletion.complete(issues)
            } catch (failure: Throwable) {
                localCloseCompletion.completeExceptionally(failure)
                throw failure
            }
        }

        // The committed close transaction is non-cancellable so ownership is
        // never stranded in Closing, but the initiating caller's cancellation
        // still propagates unchanged after cleanup.
        currentCoroutineContext().ensureActive()
        if (cleanupIssues.isNotEmpty()) {
            throw cleanupError("session $id close", cleanupIssues)
        }
    }

    /**
     * Replace the underlying connection after a successful reconnect. The
     * old epoch, protocol reader, transfers, raw stream, and outbound write
     * gate are settled before the new epoch starts. State transitions to
     * [ConnectionState.Connected].
     *
     * No-op if the session was closed concurrently while the caller was
     * dialling the new connection — in that case the freshly-dialled
     * connection is closed and we leave the terminal state alone.
     * Reusing the installed [RawConnection] instance is rejected and fails
     * the session closed because ownership cannot be transferred safely.
     *
     * @return `true` only when this method installed and started the
     *   replacement epoch; `false` when a terminal/concurrent transition won.
     */
    internal suspend fun rearmWith(
        newConnection: RawConnection,
        newEvents: ReceiveChannel<ProtocolEvent>,
        newProtocolState: ProtocolSessionState = ProtocolSessionState.legacy(),
        newReaderJob: Job? = null
    ): Boolean {
        // The reconnect handler is normally single-owner, but make accidental
        // concurrent adoption fail closed without suspending before this method
        // assumes ownership of the replacement connection and reader.
        if (!rearmLock.tryLock()) {
            closeDetachedEpoch(newConnection, newReaderJob, "concurrent reconnect replacement")
            return false
        }
        var replacementAccepted = false
        var replacementSharesCurrentEpoch = false
        var sendGateAcquired = false
        try {
            val captured = connectionLock.withLock {
                val s = _state.value
                if (
                    terminalTransitionClaim != null ||
                    s == ConnectionState.Closing ||
                    s == ConnectionState.Closed ||
                    s == ConnectionState.Failed
                ) {
                    null
                } else {
                    ConnectionEpoch(connection, readerJob, epochJob, epochToken)
                }
            } ?: return false

            if (newConnection === captured.connection) {
                replacementSharesCurrentEpoch = true
                val issue = CleanupIssue(
                    resource = "session $id reconnect replacement",
                    cause = IllegalArgumentException(
                        "Reconnect must provide a new RawConnection instance"
                    )
                )
                logCleanupIssues(logger, "session $id reconnect cleanup", listOf(issue))
                failRearmCleanupIfCurrent(captured, listOf(issue))
                throw cleanupError("session $id reconnect cleanup", listOf(issue))
            }

            // Cleanup happens outside connectionLock. A cancellation-ignoring
            // epoch, protocol reader, or host destination must not prevent a
            // concurrent close() from committing Closing and taking ownership.
            val cleanupIssues = withContext(NonCancellable) {
                val issues = mutableListOf<CleanupIssue>()
                var transferJobs: List<Job>? = null
                var transferTerminalizationSucceeded = true
                captured.runtimeJob?.cancel()
                captured.readerJob?.cancel()
                if (fileTransferDispatcherLazy.isInitialized()) {
                    val beginIssue = captureCleanupIssue(
                        resource = "session $id reconnect file-transfer terminalization",
                        timeoutMillis = SESSION_RESOURCE_CLOSE_TIMEOUT_MS,
                        preserveCancellation = false
                    ) {
                        transferJobs = fileTransferDispatcher.beginCloseAll(
                            "reconnect: connection replaced"
                        )
                    }
                    beginIssue?.let {
                        transferTerminalizationSucceeded = false
                        issues += it
                    }
                }
                closeOwnedEpochConnection(
                    captured,
                    "session $id replaced raw connection"
                )?.let(issues::add)
                transferJobs.takeIf { transferTerminalizationSucceeded }?.let { jobs ->
                    captureCleanupIssue(
                        resource = "session $id reconnect file-transfer jobs",
                        timeoutMillis = SESSION_RESOURCE_CLOSE_TIMEOUT_MS,
                        preserveCancellation = false
                    ) {
                        fileTransferDispatcher.awaitCloseAll(jobs)
                    }?.let(issues::add)
                }
                captured.runtimeJob?.let { runtime ->
                    captureCleanupIssue(
                        resource = "session $id replaced epoch runtime",
                        timeoutMillis = SESSION_RUNTIME_CLOSE_TIMEOUT_MS,
                        preserveCancellation = false
                    ) {
                        runtime.join()
                    }?.let(issues::add)
                }
                captured.readerJob?.let { reader ->
                    captureCleanupIssue(
                        resource = "session $id replaced protocol reader",
                        timeoutMillis = SESSION_RESOURCE_CLOSE_TIMEOUT_MS,
                        preserveCancellation = false
                    ) {
                        reader.join()
                    }?.let(issues::add)
                }
                issues
            }
            if (cleanupIssues.isNotEmpty()) {
                logCleanupIssues(logger, "session $id reconnect cleanup", cleanupIssues)
                failRearmCleanupIfCurrent(captured, cleanupIssues)
                throw cleanupError("session $id reconnect cleanup", cleanupIssues)
            }

            // A caller cancellation that arrived during committed cleanup is
            // rethrown before a replacement can become observable.
            currentCoroutineContext().ensureActive()

            val sendGateIssue = acquireRearmSendGate()
            if (sendGateIssue != null) {
                logCleanupIssues(logger, "session $id reconnect cleanup", listOf(sendGateIssue))
                failRearmCleanupIfCurrent(captured, listOf(sendGateIssue))
                throw cleanupError("session $id reconnect cleanup", listOf(sendGateIssue))
            }
            sendGateAcquired = true
            // The non-cancellable acquisition above may have outlived its
            // caller. Never publish the replacement for a cancelled attempt.
            currentCoroutineContext().ensureActive()

            val committed = connectionLock.withLock {
                val stateAllowsRearm = _state.value == ConnectionState.Reconnecting ||
                    _state.value == ConnectionState.Connected
                if (terminalTransitionClaim != null ||
                    !stateAllowsRearm ||
                    epochToken !== captured.epochToken ||
                    connection !== captured.connection ||
                    readerJob !== captured.readerJob ||
                    epochJob !== captured.runtimeJob
                ) {
                    false
                } else {
                    connection = newConnection
                    events = newEvents
                    readerJob = newReaderJob
                    protocolState = newProtocolState
                    epochToken = ConnectionEpochToken()
                    // closeAll latches the dispatcher closed. Reopen only in
                    // the same commit that installs a live replacement.
                    if (fileTransferDispatcherLazy.isInitialized()) {
                        fileTransferDispatcher.reopen()
                    }
                    // V0.5.1-RECONNECT-RACE (issue #15): flip to Connected BEFORE
                    // launching the new epoch. `keepAliveLoop` gates its outer
                    // `while` on `_state.value == Connected`; on a multi-thread
                    // dispatcher the launched coroutine can read the field on
                    // another worker before this thread reaches the assignment,
                    // see Reconnecting, exit immediately, and leave the rearmed
                    // session with no liveness watchdog. Next disconnect goes
                    // undetected (Android stuck in Connected).
                    _state.value = ConnectionState.Connected
                    startEpoch()
                    true
                }
            }
            if (!committed) return false
            replacementAccepted = true
        } finally {
            if (sendGateAcquired) sendMutex.unlock()
            if (!replacementAccepted) {
                if (replacementSharesCurrentEpoch) {
                    closeDetachedReader(newReaderJob, "invalid reconnect replacement")
                } else {
                    closeDetachedEpoch(newConnection, newReaderJob, "discarded reconnect replacement")
                }
            }
            rearmLock.unlock()
        }
        return true
    }

    /**
     * Waits for every outbound operation admitted by the old epoch to leave
     * [sendMutex]. The old raw stream is already closed, so shipped transports
     * unblock their bounded writers. Holding this gate across the swap makes
     * queued old-epoch operations observe the new token and fail before write.
     */
    private suspend fun acquireRearmSendGate(): CleanupIssue? {
        // Mask caller cancellation until ownership of the mutex is known;
        // otherwise prompt-cancellation delivery could acquire the mutex and
        // throw before the caller records that it must unlock it.
        val acquired = withContext(NonCancellable + Dispatchers.Default) {
            sendMutex.acquireWithin(SESSION_RESOURCE_CLOSE_TIMEOUT_MS)
        }
        if (acquired) return null
        return CleanupIssue(
            resource = "session $id replaced outbound writer",
            cause = IllegalStateException(
                "old epoch writer did not release within ${SESSION_RESOURCE_CLOSE_TIMEOUT_MS}ms"
            )
        )
    }

    private suspend fun failRearmCleanupIfCurrent(
        captured: ConnectionEpoch,
        issues: List<CleanupIssue>
    ) {
        transitionToTerminal(
            ConnectionState.Failed,
            "reconnect cleanup incomplete (${issues.size} resource failure(s))",
            expectedEpoch = captured
        )
    }

    private suspend fun closeDetachedEpoch(
        connection: RawConnection,
        readerJob: Job?,
        label: String
    ) {
        withContext(NonCancellable) {
            readerJob?.cancel()
            closeDetachedConnection(connection, label)
            closeDetachedReader(readerJob, label)
        }
    }

    private suspend fun closeDetachedReader(readerJob: Job?, label: String) {
        withContext(NonCancellable) {
            readerJob?.cancel()
            readerJob?.let { reader ->
                captureCleanupIssue(
                    resource = "session $id $label protocol reader",
                    timeoutMillis = SESSION_RESOURCE_CLOSE_TIMEOUT_MS,
                    preserveCancellation = false
                ) {
                    reader.join()
                }?.let { issue ->
                    logCleanupIssues(logger, "session $id reconnect cleanup", listOf(issue))
                }
            }
        }
    }

    /**
     * Close the raw stream at most once for this installed epoch. Reconnect
     * cleanup and terminal cleanup may race after each independently captures
     * the same epoch; the token transfers the single close result between
     * them instead of requiring third-party transports to tolerate duplicates.
     */
    private suspend fun closeOwnedEpochConnection(
        epoch: ConnectionEpoch,
        resource: String
    ): CleanupIssue? {
        val token = epoch.epochToken
        token.rawCloseLock.lock()
        try {
            if (!token.rawCloseAttempted) {
                token.rawCloseAttempted = true
                token.rawCloseIssue = captureCleanupIssue(
                    resource = resource,
                    timeoutMillis = SESSION_RESOURCE_CLOSE_TIMEOUT_MS,
                    preserveCancellation = false
                ) {
                    epoch.connection.close()
                }
            }
            return token.rawCloseIssue
        } finally {
            token.rawCloseLock.unlock()
        }
    }

    private suspend fun closeDetachedConnection(connection: RawConnection, label: String) {
        val issue = withContext(NonCancellable) {
            captureCleanupIssue(
                resource = "session $id $label",
                timeoutMillis = SESSION_RESOURCE_CLOSE_TIMEOUT_MS,
                preserveCancellation = false
            ) {
                connection.close()
            }
        }
        if (issue != null) logCleanupIssues(logger, "session $id reconnect cleanup", listOf(issue))
    }

    /**
     * The single, canonical path to a terminal state. Every transition into
     * [ConnectionState.Closed] or [ConnectionState.Failed] goes through this
     * method, regardless of trigger (user `close()`, remote hangup, PING
     * timeout, reconnect exhaustion, path-loss without a handler). Centralising
     * the transition converts what used to be a 4-way convention — "if you
     * set `_state.value = Failed`, remember to also cancel the epoch, close
     * the connection, and tear down file transfers" — into a structural
     * guarantee: the cleanup happens iff the state flip happens, atomically
     * and in the same place.
     *
     * **Behaviour:**
     *   1. Atomic decision under [connectionLock]: if another terminal owner
     *      or an incompatible state/epoch already won, this call is a no-op.
     *      Otherwise claim the current epoch, cancel application delivery,
     *      and use [applicationEmissionMutex] as the no-post-terminal-message
     *      linearization point before publishing `_state = target`.
     *   2. The cleanup transaction runs in [NonCancellable] context. This matters
     *      because the most common caller path is `onConnectionLost` triggered
     *      by `observeRawState`, whose coroutine runs inside the epoch we're
     *      about to cancel — without [NonCancellable] the cleanup itself
     *      would be cancelled at the first suspension point, leaking the
     *      raw connection and the file-transfer dispatcher.
     *      Each external resource attempt has an independently owned deadline,
     *      so cancellation-ignoring platform code is reported and abandoned.
     *   3. Cleanup order: seal and terminalize file transfers; cancel the
     *      epoch and protocol reader (stops `routeEvents` from emitting to
     *      `_incoming` — guarantees contract C1: no incoming after terminal);
     *      close the raw connection to unblock stalled writers; then join the
     *      cancelled transfer jobs and protocol reader.
     *   4. The runtime invariants at the end aren't paranoia — they document
     *      the post-condition and crash early if a future refactor breaks it.
     *
     * **What this method does NOT do:**
     *   - It does not send a CLOSE frame on the wire. Only `close()` does
     *     that, before calling this method.
     *
     * @param target [ConnectionState.Closed] or [ConnectionState.Failed]
     * @param cause one-line diagnostic string ("user close", "PING timeout",
     *   "reconnect exhausted", "raw connection -> failed", …)
     */
    private suspend fun transitionToTerminal(
        target: ConnectionState,
        cause: String,
        fileFailureKind: FileTransferFailureKind = FileTransferFailureKind.REMOTE_DISCONNECTED,
        fileRetryability: Retryability = Retryability.RETRY_NEW_SESSION,
        allowFromClosing: Boolean = false,
        requiredState: ConnectionState? = null,
        expectedEpoch: ConnectionEpoch? = null
    ): List<CleanupIssue> {
        check(target == ConnectionState.Closed || target == ConnectionState.Failed) {
            "transitionToTerminal: target must be Closed or Failed, got $target"
        }
        val claim = Any()
        var terminalEpoch: ConnectionEpoch? = null
        val claimed = connectionLock.withLock {
            val current = _state.value
            val expectedStillCurrent = expectedEpoch == null ||
                (
                    epochToken === expectedEpoch.epochToken &&
                        connection === expectedEpoch.connection &&
                        readerJob === expectedEpoch.readerJob &&
                        epochJob === expectedEpoch.runtimeJob
                    )
            if (
                terminalTransitionClaim != null ||
                !expectedStillCurrent ||
                (requiredState != null && current != requiredState)
            ) {
                false
            } else if (
                current == ConnectionState.Closed ||
                current == ConnectionState.Failed ||
                (current == ConnectionState.Closing && !allowFromClosing)
            ) {
                false
            } else {
                terminalEpoch = ConnectionEpoch(connection, readerJob, epochJob, epochToken)
                terminalTransitionClaim = claim
                true
            }
        }
        if (!claimed) return emptyList()

        // Once the epoch is claimed, no competing close/rearm/terminal path
        // may mutate it. State publication, resource cleanup, invariant
        // checks, and runtime cancellation form one non-cancellable
        // transaction: a cancellation delivered at any internal boundary
        // cannot leave a terminal public state backed by live resources.
        val cleanupIssues = withContext(NonCancellable) {
            afterTerminalClaimForTest?.invoke()
            applicationMessages.close()
            applicationDeliveryJob?.cancel()
            applicationEmissionMutex.withLock {
                connectionLock.withLock {
                    check(terminalTransitionClaim === claim) {
                        "Terminal transition claim was replaced for session $id"
                    }
                    _state.value = target
                    terminalTransitionClaim = null
                }
            }
            afterTerminalStatePublishedForTest?.invoke()
            logger.debug("Session $id: terminal → ${target.name} ($cause)")

            val issues = mutableListOf<CleanupIssue>()
            var transferJobs: List<Job>? = null
            var transferTerminalizationSucceeded = true
            // File transfers first: they may be mid-write on the connection;
            // terminalize their handles and cancel their jobs before closing
            // the socket, then settle those jobs after close has unblocked any
            // stalled writer.
            if (fileTransferDispatcherLazy.isInitialized()) {
                val beginIssue = captureCleanupIssue(
                    resource = "session $id file-transfer terminalization",
                    timeoutMillis = SESSION_RESOURCE_CLOSE_TIMEOUT_MS,
                    preserveCancellation = false
                ) {
                    transferJobs = fileTransferDispatcher.beginCloseAll(
                        reason = "session $id ${target.name}: $cause",
                        failureKind = fileFailureKind,
                        retryability = fileRetryability
                    )
                }
                beginIssue?.let {
                    transferTerminalizationSucceeded = false
                    issues += it
                }
            }
            // Cancel the epoch — stops routeEvents, keepAliveLoop, and the
            // parked observeRawState. Guarantees no further _incoming.emit.
            val ownedEpoch = checkNotNull(terminalEpoch)
            ownedEpoch.runtimeJob?.cancel()
            ownedEpoch.readerJob?.cancel()
            // Close the underlying raw connection.
            closeOwnedEpochConnection(
                ownedEpoch,
                "session $id raw connection"
            )?.let(issues::add)
            transferJobs.takeIf { transferTerminalizationSucceeded }?.let { jobs ->
                captureCleanupIssue(
                    resource = "session $id file-transfer jobs",
                    timeoutMillis = SESSION_RESOURCE_CLOSE_TIMEOUT_MS,
                    preserveCancellation = false
                ) {
                    fileTransferDispatcher.awaitCloseAll(jobs)
                }?.let(issues::add)
            }
            ownedEpoch.readerJob?.let { reader ->
                captureCleanupIssue(
                    resource = "session $id protocol reader",
                    timeoutMillis = SESSION_RESOURCE_CLOSE_TIMEOUT_MS,
                    preserveCancellation = false
                ) {
                    reader.join()
                }?.let(issues::add)
            }
            applicationDeliveryJob?.let { delivery ->
                captureCleanupIssue(
                    resource = "session $id application delivery",
                    timeoutMillis = applicationDeliveryCloseTimeoutMillis,
                    preserveCancellation = false
                ) {
                    delivery.join()
                }?.let(issues::add)
            }
            drainQueuedApplicationMessages()
            afterApplicationDeliveryDrainForTest?.invoke()
            logCleanupIssues(logger, "session $id terminal cleanup", issues)

            // Hard invariants. check() throws on violation; that's intentional
            // — if any of these fail, the SDK is in a state where downstream
            // behaviour is undefined and we'd rather crash on the developer's
            // machine than ship a silent corruption.
            check(_state.value == target) {
                "I-terminal-state: expected ${target.name} after transition, got ${_state.value.name}"
            }
            val ej = epochJob
            check(ej == null || ej.isCancelled) {
                "I-terminal-epoch: epochJob still alive after transition to ${target.name}"
            }

            // This is deliberately last. Remote failure paths run inside a
            // child of sessionJob, so cancelling earlier would interrupt their
            // own resource cleanup. The completed post-conditions above remain
            // observable before this transaction exits.
            sessionJob.cancel(CancellationException("Session $id reached ${target.name}: $cause"))
            issues
        }
        return cleanupIssues
    }

    private suspend fun enqueueApplicationMessage(message: P2pMessage): Boolean {
        val messageBytes = message.retainedSizeBytes()
        return applicationMessageQueueLock.withLock {
            if (
                queuedApplicationMessages >= MAX_QUEUED_APPLICATION_MESSAGES ||
                messageBytes > MAX_QUEUED_APPLICATION_BYTES - queuedApplicationBytes
            ) {
                return@withLock false
            }
            queuedApplicationMessages += 1
            queuedApplicationBytes += messageBytes
            val sent = applicationMessages.trySend(QueuedApplicationMessage(message, messageBytes))
            if (sent.isFailure) {
                queuedApplicationMessages -= 1
                queuedApplicationBytes -= messageBytes
            }
            sent.isSuccess
        }
    }

    private suspend fun deliverApplicationMessages() {
        for (queued in applicationMessages) {
            try {
                beforeApplicationMessageEmitForTest?.invoke(queued.message)
                applicationEmissionMutex.withLock {
                    currentCoroutineContext().ensureActive()
                    _incoming.emit(queued.message)
                }
            } finally {
                // The terminal owner cancels this delivery job before it
                // drains queued messages. Releasing ownership must therefore
                // survive cancellation even when the accounting mutex is
                // briefly contended; otherwise an in-flight message can leak
                // permanently from the bounded backlog counters.
                withContext(NonCancellable) {
                    applicationMessageQueueLock.withLock {
                        queuedApplicationMessages -= 1
                        queuedApplicationBytes -= queued.retainedBytes
                    }
                }
            }
        }
    }

    private suspend fun drainQueuedApplicationMessages() {
        var drainedMessages = 0
        var drainedBytes = 0L
        while (true) {
            val queued = applicationMessages.tryReceive().getOrNull() ?: break
            drainedMessages += 1
            drainedBytes += queued.retainedBytes
        }
        if (drainedMessages == 0) return
        applicationMessageQueueLock.withLock {
            check(queuedApplicationMessages >= drainedMessages) {
                "Application backlog message ownership underflow for session $id"
            }
            check(queuedApplicationBytes >= drainedBytes) {
                "Application backlog byte ownership underflow for session $id"
            }
            queuedApplicationMessages -= drainedMessages
            queuedApplicationBytes -= drainedBytes
        }
    }

    private fun P2pMessage.retainedSizeBytes(): Long {
        val payloadBytes = when (this) {
            is P2pMessage.Text -> value.encodeToByteArray().size.toLong()
            is P2pMessage.Binary -> payloadSizeBytes.toLong()
        }
        val metadata = when (this) {
            is P2pMessage.Text -> metadata
            is P2pMessage.Binary -> metadata
        }
        return metadata.entries.fold(payloadBytes) { total, (key, value) ->
            total + key.encodeToByteArray().size + value.encodeToByteArray().size
        }
    }

    internal val runtimeJobIsActiveForTest: Boolean
        get() = sessionJob.isActive

    internal suspend fun applicationBacklogForTest(): Pair<Int, Long> =
        applicationMessageQueueLock.withLock {
            queuedApplicationMessages to queuedApplicationBytes
        }

    /** Wait until every child owned by this session has terminated. */
    internal suspend fun awaitRuntimeTermination() {
        sessionJob.join()
    }

    /**
     * Final transition when the reconnect handler exhausts its retry budget.
     * No-op if the session is already in a terminal state (e.g., the user
     * called [close] while we were retrying — close wins).
     *
     * Symmetric with the no-handler branch of [onConnectionLost]: once we
     * flip to Failed without ever rearming, the epoch coroutines from the
     * last attempt — `routeEvents`, `keepAliveLoop`, and especially
     * `observeRawState` (which parks on `raw.state.collect` because the
     * StateFlow stabilises at Closed and never re-emits) — would otherwise
     * outlive the session's public lifetime. Without the cancel,
     * `routeEvents` can keep pumping inbound `_incoming.emit(...)` calls
     * **after** SessionStore has already evicted us from byPeer / the
     * published sessions list. That is the hypothesis-B1 leak: messages
     * reach the Swift collector (still subscribed to the shared flow)
     * while the UI — which reads `kit.sessions.value` — shows "not
     * connected." Cancel the epoch and close the raw so the session
     * footprint is fully torn down before SessionManager's
     * `watchForTerminal` finishes its store cleanup.
     */
    internal suspend fun markFailedAfterExhaustion() {
        // The source-state condition is checked in the same critical section
        // as the terminal claim. A stale exhaustion call must not fail a
        // connection that rearmed between a best-effort state read and claim.
        transitionToTerminal(
            ConnectionState.Failed,
            "reconnect exhausted",
            requiredState = ConnectionState.Reconnecting
        )
    }

    private suspend fun routeEvents(channel: ReceiveChannel<ProtocolEvent>) {
        try {
            for (event in channel) {
                when (event) {
                    is ProtocolEvent.Message -> {
                        // Detached-session protection. If we're about to push
                        // a message into the public `incoming` flow but SessionManager
                        // no longer treats us as the registered session for
                        // this peer (either evicted or replaced), the public
                        // session-list view is desynced from the live
                        // message stream — the failure mode described in the
                        // architecture review's hypothesis B1. Before this
                        // session's registration commits, absence from the
                        // store is normal and the check is deliberately idle.
                        val reg = lookupRegistration
                            ?.takeIf { registrationCommitted.value }
                            ?.let { lookup ->
                                runCatching { lookup(this@P2pSessionImpl) }.getOrNull()
                            }
                        if (reg != null) {
                            val differentActive = reg.activeSessionId != null &&
                                reg.activeSessionId != id
                            if (!reg.isInPublicList || differentActive) {
                                logger.warn(
                                    "Detached session dropped Message: " +
                                        "sessionId=$id " +
                                        "peerId=${peer.id.value.take(8)} " +
                                        "state=${_state.value.name} " +
                                        "activeSessionId=${reg.activeSessionId ?: "(none)"} " +
                                        "inPublicList=${reg.isInPublicList}"
                                )
                                continue
                            }
                        }
                        if (!enqueueApplicationMessage(event.message)) {
                            logger.warn(
                                "Session $id: application receive backlog exceeded " +
                                    "$MAX_QUEUED_APPLICATION_MESSAGES messages / " +
                                    "$MAX_QUEUED_APPLICATION_BYTES bytes"
                            )
                            transitionToTerminal(
                                ConnectionState.Failed,
                                "application receive backlog exceeded"
                            )
                            return
                        }
                    }
                    is ProtocolEvent.Ping -> {
                        try {
                            sendMutex.withLock { protocol.sendPong(connection) }
                        } catch (cancelled: CancellationException) {
                            throw cancelled
                        } catch (failure: Throwable) {
                            logger.warn("Session $id: failed to send PONG", failure)
                            onConnectionLost(
                                "PONG send failed: ${failure.message ?: failure::class.simpleName}"
                            )
                            return
                        }
                    }
                    is ProtocolEvent.Pong -> lastPongAt.value = monotonicClock()
                    is ProtocolEvent.Hello -> {
                        logger.debug("Session $id: ignoring late HELLO")
                    }
                    is ProtocolEvent.Ack -> {
                        // Reserved for v0.2 reliability work.
                    }
                    is ProtocolEvent.Close -> {
                        // Clean close from peer — never retry. The received
                        // CLOSE frame is the single remote-side clean-close
                        // authority (AUDIT-2026-07 SES-1); see
                        // [markCleanlyClosed].
                        markCleanlyClosed()
                        return
                    }
                    is ProtocolEvent.PeerError -> {
                        logger.warn("Session $id: peer error: ${event.reason}")
                        onConnectionLost("peer error: ${event.reason}")
                        return
                    }
                    is ProtocolEvent.FileOffer -> fileTransferDispatcher.onFileOffer(
                        event.transferId,
                        event.payload,
                        event.secureOffer
                    )
                    is ProtocolEvent.FileAccept -> fileTransferDispatcher.onFileAccept(event.transferId)
                    is ProtocolEvent.FileReject -> fileTransferDispatcher.onFileReject(event.transferId, event.reason)
                    is ProtocolEvent.FileData -> fileTransferDispatcher.onFileData(event.frame)
                    is ProtocolEvent.FileDone -> fileTransferDispatcher.onFileDone(event.transferId)
                    is ProtocolEvent.FileFinish -> fileTransferDispatcher.onFileFinish(event.payload)
                    is ProtocolEvent.FileCommit -> fileTransferDispatcher.onFileCommit(event.payload)
                    is ProtocolEvent.FileResult -> fileTransferDispatcher.onFileResult(event.payload)
                    is ProtocolEvent.FileCancel -> fileTransferDispatcher.onFileCancel(event.transferId, event.reason)
                }
            }
            // AUDIT-2026-07 (SES-1): the events channel completed without a
            // CLOSE frame (a received CLOSE returns from the loop above and
            // never reaches this line). Every shipped transport surfaces both
            // remote EOF and a read failure as this same normal completion,
            // so "the wire ended with no CLOSE" is the one reliable signal
            // that the peer did NOT close cleanly. Route it through
            // [onConnectionLost]: outgoing sessions with a reconnect handler
            // deterministically enter Reconnecting; sessions without one
            // (incoming, or ReconnectPolicy.Disabled) deterministically reach
            // Failed. Never the clean-Closed outcome — "clean closes never
            // retry" requires the inverse too: a hangup without CLOSE is not
            // a clean close. (Pre-2026-07 this branch called
            // markCleanlyClosed(), racing [observeRawState] for the terminal
            // outcome on every remote loss.)
            onConnectionLost("remote hangup without CLOSE frame")
        } catch (e: CancellationException) {
            throw e
        } catch (_: ClosedReceiveChannelException) {
            // AUDIT-2026-07 (SES-1): same classification as the completion
            // branch above — the channel ended without delivering a CLOSE.
            onConnectionLost("remote hangup without CLOSE frame (receive on closed channel)")
        } catch (e: P2pError.FileTransferFailed) {
            if (e.kind == FileTransferFailureKind.TRANSFER_PROTOCOL) {
                logger.warn("Session $id: structural file-transfer protocol violation", e)
                transitionToTerminal(
                    target = ConnectionState.Failed,
                    cause = e.reason,
                    fileFailureKind = FileTransferFailureKind.TRANSFER_PROTOCOL,
                    fileRetryability = Retryability.NOT_RETRYABLE
                )
            } else {
                logger.warn("Session $id: routeEvents file-transfer failure", e)
                onConnectionLost("routeEvents threw: ${e.message ?: e::class.simpleName}")
            }
        } catch (e: P2pError.ProtocolError) {
            logger.warn("Session $id: authenticated protocol violation", e)
            transitionToTerminal(
                target = ConnectionState.Failed,
                cause = e.reason,
                fileFailureKind = FileTransferFailureKind.TRANSFER_PROTOCOL,
                fileRetryability = Retryability.NOT_RETRYABLE
            )
        } catch (e: P2pError.AuthenticatedIdentityMismatch) {
            logger.warn("Session $id: authenticated envelope identity mismatch", e)
            transitionToTerminal(
                target = ConnectionState.Failed,
                cause = e.reason,
                fileFailureKind = FileTransferFailureKind.AUTHENTICATION,
                fileRetryability = Retryability.NOT_RETRYABLE
            )
        } catch (e: P2pError.VersionMismatch) {
            logger.warn("Session $id: protocol version mismatch", e)
            transitionToTerminal(
                target = ConnectionState.Failed,
                cause = e.message ?: "Protocol version mismatch",
                fileFailureKind = FileTransferFailureKind.TRANSFER_PROTOCOL,
                fileRetryability = Retryability.NOT_RETRYABLE
            )
        } catch (e: P2pError.AuthenticationFailed) {
            logger.warn("Session $id: authenticated transport failure", e)
            transitionToTerminal(
                target = ConnectionState.Failed,
                cause = e.reason,
                fileFailureKind = FileTransferFailureKind.AUTHENTICATION,
                fileRetryability = Retryability.NOT_RETRYABLE
            )
        } catch (e: Throwable) {
            logger.warn("Session $id: routeEvents failed", e)
            onConnectionLost("routeEvents threw: ${e.message ?: e::class.simpleName}")
        }
    }

    private suspend fun keepAliveLoop(epochConnection: RawConnection) {
        while (scope.isActive && _state.value == ConnectionState.Connected) {
            delay(keepAlive.pingIntervalMillis)
            if (!scope.isActive || _state.value != ConnectionState.Connected) return
            // Avoid starting another PING once the independent deadline
            // watchdog has already observed an expired PONG deadline. This
            // check is only an optimization; it must not be the sole
            // liveness check because the send below may suspend indefinitely.
            val sincePongBeforeSend = monotonicClock() - lastPongAt.value
            if (sincePongBeforeSend >= keepAlive.timeoutMillis) {
                logger.warn(
                    "Session $id: no PONG received for $sincePongBeforeSend ms " +
                        "(timeout=${keepAlive.timeoutMillis} ms; checked before PING send)"
                )
                onConnectionLost("keep-alive timeout")
                return
            }
            try {
                sendMutex.withLock { protocol.sendPing(epochConnection) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                logger.warn("Session $id: failed to send PING", e)
                onConnectionLost("PING send failed: ${e.message ?: e::class.simpleName}")
                return
            }
            val sinceLastPong = monotonicClock() - lastPongAt.value
            if (sinceLastPong >= keepAlive.timeoutMillis) {
                logger.warn(
                    "Session $id: no PONG received for $sinceLastPong ms " +
                        "(timeout=${keepAlive.timeoutMillis} ms)"
                )
                onConnectionLost("keep-alive timeout")
                return
            }
        }
    }

    /**
     * Enforces the PONG deadline without touching [sendMutex]. The ping loop
     * also checks the deadline, but its outbound write can be parked behind an
     * application or file-transfer send. This coroutine remains able to wake,
     * observe [lastPongAt], and transition the session while that happens.
     *
     * The delay is bounded by the current deadline rather than a fixed tick;
     * a PONG arriving during the delay is observed when the old deadline is
     * reached, then the next delay is calculated from the refreshed timestamp.
     * The coroutine is a child of the epoch job, so rearm and terminal cleanup
     * cancel it with the rest of that epoch.
     */
    private suspend fun pongDeadlineWatchdog() {
        while (scope.isActive && _state.value == ConnectionState.Connected) {
            val sinceLastPong = monotonicClock() - lastPongAt.value
            if (sinceLastPong >= keepAlive.timeoutMillis) {
                logger.warn(
                    "Session $id: no PONG received for $sinceLastPong ms " +
                        "(timeout=${keepAlive.timeoutMillis} ms; deadline watchdog)"
                )
                onConnectionLost("keep-alive timeout")
                return
            }
            delay(keepAlive.timeoutMillis - sinceLastPong)
        }
    }

    /**
     * Latch the clean-`Closed` outcome for a CLOSE frame received from the
     * peer. AUDIT-2026-07 (SES-1): since the remote-termination determinism
     * fix, this is only reachable from [routeEvents]' `ProtocolEvent.Close`
     * branch — a wire that ends *without* a CLOSE frame routes through
     * [onConnectionLost] instead, so a received CLOSE is the single
     * remote-side classification that yields `Closed`.
     *
     * Proceeds from `Connected` AND from `Reconnecting`: the CLOSE frame is
     * authoritative over a concurrent raw-terminal classification. The frame
     * always enters the event pipeline before the read flow completes, so a
     * session that raced into `Reconnecting` off the raw-state flip (the
     * [observeRawState] deferral window elapsed under load) is corrected to
     * the spec-mandated `Closed` as soon as the buffered CLOSE is processed;
     * the reconnect retry loop re-checks state before every dial and
     * [rearmWith] no-ops on terminal states, so no further dial happens. A
     * CLOSE processed by a live [routeEvents] is always from the *current*
     * epoch — [rearmWith] cancel-and-joins the old epoch's routeEvents under
     * [connectionLock] before flipping back to `Connected` — so this can
     * never close a freshly rearmed session on a stale frame. Terminal
     * states still win: [transitionToTerminal] stays idempotent and a local
     * `close()` / prior `Failed` is never overridden.
     */
    private suspend fun markCleanlyClosed() {
        val proceed = connectionLock.withLock {
            _state.value == ConnectionState.Connected ||
                _state.value == ConnectionState.Reconnecting
        }
        if (proceed) {
            transitionToTerminal(ConnectionState.Closed, "remote CLOSE frame (clean close)")
        }
    }

    /**
     * Called by [SessionManager.applyPathChange] when the host device's
     * network path transitions to [dev.p2pkit.core.NetworkPathStatus.Unsatisfied].
     * Routes through [onConnectionLost] so the existing
     * Connected→Reconnecting (or Connected→Failed when no reconnect
     * handler is wired) gate runs untouched. The mutex inside
     * [onConnectionLost] makes this safe to call concurrently with PING
     * failures or with [observeRawState] reacting to the same network drop.
     */
    internal suspend fun notifyPathLost() {
        onConnectionLost("network path unsatisfied")
    }

    /**
     * Single entry point for "this epoch's connection died". Decides whether
     * to retry (transition to [ConnectionState.Reconnecting] and invoke the
     * handler) or fail terminally (transition to [ConnectionState.Failed]).
     *
     * Holds [connectionLock] only long enough to make the decision so the
     * retry coroutine, which itself takes the lock inside [rearmWith], does
     * not deadlock.
     */
    private suspend fun onConnectionLost(cause: String) {
        // Decide under the lock:
        //   - shouldFail = "transition to Failed via transitionToTerminal"
        //   - handler    = "kick off a reconnect attempt"
        // Only one is true; both can be false (already terminal / Reconnecting).
        var shouldFail = false
        val handler: ReconnectHandler? = connectionLock.withLock {
            if (terminalTransitionClaim != null) {
                null
            } else when (_state.value) {
                ConnectionState.Connected -> {
                    val h = reconnectHandler
                    if (h == null) {
                        shouldFail = true  // hand off to transitionToTerminal below
                        null
                    } else {
                        _state.value = ConnectionState.Reconnecting
                        // Snapshot the path-wake baseline at the exact
                        // Reconnecting edge (still under the lock, before the
                        // async retry loop launches) so a Satisfied signal that
                        // lands in that gap still wakes the handler early
                        // (AUDIT-2026-06).
                        h.onWillReconnect()
                        h
                    }
                }
                else -> null  // already Reconnecting / Closing / Closed / Failed — leave it
            }
        }
        if (handler != null) {
            logger.debug("Session $id: connection lost ($cause), starting reconnect")
            // Run on the session scope so close() / kit.stop() cancel it.
            scope.launch {
                try {
                    handler.onConnectionLost(this@P2pSessionImpl)
                } catch (cancelled: CancellationException) {
                    throw cancelled
                } catch (failure: Throwable) {
                    logger.warn("Session $id: reconnect handler failed", failure)
                    transitionToTerminal(
                        ConnectionState.Failed,
                        "reconnect handler failed: " +
                            (failure.message ?: failure::class.simpleName),
                        requiredState = ConnectionState.Reconnecting
                    )
                }
            }
            // Stabilization watchdog: emit a single WARN if the session is
            // still in Reconnecting after [STUCK_RECONNECTING_THRESHOLD_MS].
            // Under normal operation a session should either reach Connected
            // (rearmWith) or Failed (markFailedAfterExhaustion) well within
            // `maxAttempts × retryDelayMillis` — typically a few seconds.
            // Persisting past 30 s indicates a bug in the reconnect path
            // (e.g., a stale internalPeer pointing at an unreachable address,
            // a `pathSatisfiedSignal` emission consumed by another handler and
            // never re-emitted, or a deadlocked reconnect handler). Launched
            // on the session scope so `close()` / `kit.stop()` cancel it.
            scope.launch {
                delay(STUCK_RECONNECTING_THRESHOLD_MS)
                if (_state.value == ConnectionState.Reconnecting) {
                    logger.warn(
                        "Session $id: STUCK in Reconnecting for >${STUCK_RECONNECTING_THRESHOLD_MS}ms " +
                            "(cause=$cause). Investigate: stale internalPeer, lost path signal, " +
                            "or deadlocked SessionReconnectHandler."
                    )
                }
            }
        } else if (shouldFail) {
            // No reconnect handler (incoming session, or outgoing with
            // Disabled). Centralised terminal path handles state flip,
            // epoch cancel, file-transfer teardown, and raw close in one
            // place.
            transitionToTerminal(ConnectionState.Failed, cause)
        }
    }

    private companion object {
        private const val MAX_TRANSFER_FAILURE_REASON_CHARS: Int = 512

        /**
         * How long [close] waits for the best-effort CLOSE frame to reach the
         * wire before proceeding with teardown. Bounds only the wait — the
         * send job itself is left to be unblocked by the connection close
         * inside [transitionToTerminal] (see the comment in [close]).
         */
        const val CLOSE_FRAME_TIMEOUT_MS: Long = 2_000

        /** Bounds each terminal resource attempt and the final runtime join. */
        const val SESSION_RESOURCE_CLOSE_TIMEOUT_MS: Long = 2_000
        const val SESSION_RUNTIME_CLOSE_TIMEOUT_MS: Long = 2_000

        const val MAX_QUEUED_APPLICATION_MESSAGES: Int = 64
        const val MAX_QUEUED_APPLICATION_BYTES: Long = 8L * 1024L * 1024L

        /**
         * Threshold for the stuck-Reconnecting watchdog. Generous enough to
         * cover any reasonable `maxAttempts × retryDelayMillis` budget
         * (default is ~4 s; even pathological configs rarely exceed 20 s);
         * crossing it means the reconnect path is wedged. Used during the
         * post-S3 stabilization phase to surface lifecycle leaks that the
         * structural fixes haven't covered yet.
         */
        const val STUCK_RECONNECTING_THRESHOLD_MS: Long = 30_000

        /**
         * AUDIT-2026-07 (SES-1): how long [observeRawState] waits for the
         * protocol-event pipeline to classify a remote termination before
         * classifying on the raw state alone. A CLOSE frame is buffered into
         * the events channel strictly before the read flow completes (which
         * is what flips the raw state), so when a clean goodbye is in flight,
         * [routeEvents] latches it well within this window on anything but a
         * fully starved dispatcher. Kept small because the window also delays
         * the send-side-only failure path (raw state terminal while the read
         * side lags — the prompt-detection case [observeRawState] was built
         * for) by at most this much.
         */
        const val RAW_TERMINAL_CLASSIFICATION_GRACE_MS: Long = 250
    }
}

private data class ProtocolTarget(
    val connection: RawConnection,
    val protocolState: ProtocolSessionState,
    val epochToken: ConnectionEpochToken
)

private data class ConnectionEpoch(
    val connection: RawConnection,
    val readerJob: Job?,
    val runtimeJob: CompletableJob?,
    val epochToken: ConnectionEpochToken
)

/** Referential generation marker and single-close owner; unlike a counter it cannot wrap. */
private class ConnectionEpochToken {
    val rawCloseLock: Mutex = Mutex()
    var rawCloseAttempted: Boolean = false
    var rawCloseIssue: CleanupIssue? = null
}
