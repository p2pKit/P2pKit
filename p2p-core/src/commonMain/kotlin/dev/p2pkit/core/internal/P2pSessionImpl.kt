package dev.p2pkit.core.internal

import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pMessage
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.protocol.P2pProtocol
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.transfer.FileTransferConfig
import dev.p2pkit.core.transfer.P2pFileOffer
import dev.p2pkit.core.transfer.P2pFileTransfer
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableJob
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.withContext
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.channels.ClosedReceiveChannelException
import kotlinx.coroutines.channels.ReceiveChannel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
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
}

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
/**
 * SessionManager-side view of "is this session still the one we publish?"
 * Used by [P2pSessionImpl.routeEvents] to detect zombie emissions —
 * messages emitted to the public `incoming` flow while SessionManager has
 * already evicted or replaced this session in its [SessionManager.active]
 * map / [SessionManager.sessions] StateFlow.
 *
 * Read without taking SessionManager's `activeLock` — diagnostics-only,
 * tolerating a microsecond-stale read is fine. The caller wraps the lookup
 * in a `runCatching` so a corrupt mid-write read can't itself crash the
 * receive loop.
 */
internal data class SessionRegistration(
    /**
     * Session id currently in `SessionManager.active[peer.id]`, or `null`
     * if there is no entry. Equal to the calling session's `id` when this
     * session is the registered one.
     */
    val activeSessionId: String?,
    /** True iff this exact session instance is still in `SessionManager.sessions.value`. */
    val isInPublicList: Boolean
)

internal class P2pSessionImpl(
    override val id: String,
    override val peer: Peer,
    initialConnection: RawConnection,
    initialEvents: ReceiveChannel<ProtocolEvent>,
    private val protocol: P2pProtocol,
    private val parentScope: CoroutineScope,
    private val keepAlive: KeepAliveConfig,
    private val clock: () -> Long,
    private val logger: P2pLogger,
    private val fileTransferConfig: FileTransferConfig = FileTransferConfig(),
    private val random: Random = Random.Default,
    /**
     * Optional best-effort lookup of this session's registration state in
     * the owning SessionManager. Wired by SessionManager itself; `null`
     * for stand-alone tests that don't go through a SessionManager. When
     * present, [routeEvents] consults it before every `Message` emit and
     * logs a `ZOMBIE` warning if the registration says this session is
     * no longer the published one — which is the smoking-gun signature of
     * the hypothesis-B1 leak (epoch coroutines outliving a terminal
     * transition and continuing to pump incoming messages into the
     * public flow).
     */
    private val lookupRegistration: ((P2pSession) -> SessionRegistration)? = null
) : P2pSession {

    private val sessionJob = SupervisorJob(parent = parentScope.coroutineContext[Job])
    private val scope = CoroutineScope(parentScope.coroutineContext + sessionJob)

    private val _state = MutableStateFlow(ConnectionState.Connected)
    override val state: StateFlow<ConnectionState> = _state.asStateFlow()

    private val _incoming = MutableSharedFlow<P2pMessage>(
        replay = 0,
        extraBufferCapacity = 64,
        onBufferOverflow = BufferOverflow.SUSPEND
    )
    override val incoming: SharedFlow<P2pMessage> = _incoming.asSharedFlow()

    private val sendMutex = Mutex()
    private val lastPongAt = MutableStateFlow(clock())

    /**
     * Lock guarding [connection], [events], [epochJob], and the
     * [_state] transitions driven by connection loss. Held briefly during
     * [rearmWith] and the `onConnectionLost` decision.
     */
    private val connectionLock = Mutex()

    private var connection: RawConnection = initialConnection
    private var events: ReceiveChannel<ProtocolEvent> = initialEvents

    /**
     * Job that owns this epoch's [routeEvents] and [keepAliveLoop]. Cancelled
     * on rearm so the new epoch starts cleanly; cancelled on close so the
     * loops exit when the session is torn down.
     */
    private var epochJob: CompletableJob? = null

    /**
     * Wired by [SessionManager] for outgoing sessions when
     * [dev.p2pkit.core.ReconnectPolicy.Enabled] is configured. Null for
     * incoming sessions or when the policy is `Disabled`.
     */
    internal var reconnectHandler: ReconnectHandler? = null

    private val fileTransferDispatcher: FileTransferDispatcher by lazy {
        FileTransferDispatcher(
            sessionId = id,
            remotePeer = peer,
            protocol = protocol,
            getConnection = { connection },
            sendMutex = sendMutex,
            config = fileTransferConfig,
            scope = scope,
            random = random,
            logger = logger
        )
    }

    override val incomingFiles: SharedFlow<P2pFileOffer>
        get() = fileTransferDispatcher.incomingFiles

    fun start() {
        startEpoch()
    }

    private fun startEpoch() {
        val job = SupervisorJob(parent = sessionJob)
        epochJob = job
        val epochScope = CoroutineScope(scope.coroutineContext + job)
        // Capture the current connection ref once so all three loops act on
        // the same epoch's connection. Rearm replaces `connection` and
        // cancels the epoch; new loops then see the new ref.
        val epochConnection = connection
        lastPongAt.value = clock()
        epochScope.launch { routeEvents(events) }
        epochScope.launch { keepAliveLoop(epochConnection) }
        epochScope.launch { observeRawState(epochConnection) }
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
     */
    private suspend fun observeRawState(epochConnection: RawConnection) {
        epochConnection.state.collect { rawState ->
            when (rawState) {
                ConnectionState.Closed, ConnectionState.Failed -> {
                    if (_state.value == ConnectionState.Connected) {
                        onConnectionLost("raw connection -> $rawState")
                    }
                }
                else -> { /* Connecting / Connected / Handshaking — wait */ }
            }
        }
    }

    override suspend fun send(message: P2pMessage) {
        if (_state.value != ConnectionState.Connected) {
            throw P2pError.ConnectionFailed("Session $id is ${_state.value}; cannot send")
        }
        sendMutex.withLock {
            protocol.sendMessage(connection, message)
        }
    }

    override suspend fun sendFile(
        name: String,
        sizeBytes: Long,
        mimeType: String?,
        source: RawSource
    ): P2pFileTransfer {
        if (_state.value != ConnectionState.Connected) {
            throw P2pError.ConnectionFailed("Session $id is ${_state.value}; cannot send file")
        }
        return fileTransferDispatcher.sendFile(name, sizeBytes, mimeType, source)
    }

    override suspend fun close() {
        // Idempotent: skip if already terminal.
        val alreadyTerminal = connectionLock.withLock {
            val s = _state.value
            s == ConnectionState.Closed || s == ConnectionState.Failed
        }
        if (alreadyTerminal) return

        // Best-effort CLOSE frame BEFORE we tear the wire down. Must happen
        // before [transitionToTerminal] cancels the epoch — once the epoch
        // is gone, [connection] is closed and the protocol writer would
        // throw. This is the only terminal path that sends a CLOSE frame;
        // unintentional failure paths don't (the wire is presumably already
        // dead).
        runCatching {
            sendMutex.withLock { protocol.sendClose(connection) }
        }

        // Centralised cleanup: file transfers, epoch cancel, raw close, and
        // the state flip to Closed all happen here atomically.
        transitionToTerminal(ConnectionState.Closed, "user close()")

        // Additionally tear down the rest of the session — primarily the
        // reconnect handler if one is still mid-dial. Only [close] does
        // this, because failure paths cannot: they are themselves called
        // from coroutines that are children of [sessionJob], and cancelling
        // their own ancestor would prevent the cleanup from completing.
        // [close] runs from outside [sessionJob] (the kit's scope or a
        // user-controlled scope), so the cancelAndJoin is safe.
        sessionJob.cancelAndJoin()
    }

    /**
     * Replace the underlying connection after a successful reconnect. The
     * old epoch is cancelled and the old connection is closed before the new
     * epoch starts. State transitions to [ConnectionState.Connected].
     *
     * No-op if the session was closed concurrently while the caller was
     * dialling the new connection — in that case the freshly-dialled
     * connection is closed and we leave the terminal state alone.
     */
    internal suspend fun rearmWith(
        newConnection: RawConnection,
        newEvents: ReceiveChannel<ProtocolEvent>
    ) {
        connectionLock.withLock {
            val s = _state.value
            if (s == ConnectionState.Closing || s == ConnectionState.Closed || s == ConnectionState.Failed) {
                runCatching { newConnection.close() }
                return
            }
            epochJob?.cancelAndJoin()
            runCatching { connection.close() }
            connection = newConnection
            events = newEvents
            startEpoch()
            _state.value = ConnectionState.Connected
        }
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
     *   1. Atomic decision under [connectionLock]: if already terminal, this
     *      call is a no-op. Otherwise flip `_state` to [target].
     *   2. The cleanup block runs in [NonCancellable] context. This matters
     *      because the most common caller path is `onConnectionLost` triggered
     *      by `observeRawState`, whose coroutine runs inside the epoch we're
     *      about to cancel — without [NonCancellable] the cleanup itself
     *      would be cancelled at the first suspension point, leaking the
     *      raw connection and the file-transfer dispatcher.
     *   3. Cleanup order: tear down file transfers first (they may be
     *      writing to the connection); cancel the epoch (stops
     *      `routeEvents` from emitting to `_incoming` — guarantees contract
     *      C1: no incoming after terminal); then close the raw connection
     *      (releases NWConnection / Socket FD).
     *   4. The runtime invariants at the end aren't paranoia — they document
     *      the post-condition and crash early if a future refactor breaks it.
     *
     * **What this method does NOT do:**
     *   - It does not cancel the session-wide [sessionJob]. The failure
     *     paths cannot — they are called from coroutines that are themselves
     *     children of `sessionJob`. Only the user-initiated [close] (which
     *     runs from outside `sessionJob`) does the additional
     *     `sessionJob.cancelAndJoin` step after this method returns.
     *   - It does not send a CLOSE frame on the wire. Only `close()` does
     *     that, before calling this method.
     *
     * @param target [ConnectionState.Closed] or [ConnectionState.Failed]
     * @param cause one-line diagnostic string ("user close", "PING timeout",
     *   "reconnect exhausted", "raw connection -> failed", …)
     */
    private suspend fun transitionToTerminal(
        target: ConnectionState,
        cause: String
    ) {
        check(target == ConnectionState.Closed || target == ConnectionState.Failed) {
            "transitionToTerminal: target must be Closed or Failed, got $target"
        }
        val didTransition = connectionLock.withLock {
            val current = _state.value
            if (current == ConnectionState.Closed || current == ConnectionState.Failed) {
                // I-double-terminal: a second call is idempotent. No cleanup
                // (the first call did it).
                return
            }
            _state.value = target
            true
        }
        if (!didTransition) return  // unreachable; defensive.

        logger.debug("Session $id: terminal → ${target.name} ($cause)")

        // NonCancellable so the cleanup completes even when our caller is in
        // the cancellation tree of [epochJob] (the typical case — see KDoc).
        withContext(NonCancellable) {
            // File transfers first: they may be mid-write on the connection;
            // tear them down before we close the socket so they surface a
            // sensible "session ended" status instead of a mid-write
            // IOException.
            runCatching {
                fileTransferDispatcher.closeAll("session $id ${target.name}: $cause")
            }
            // Cancel the epoch — stops routeEvents, keepAliveLoop, and the
            // parked observeRawState. Guarantees no further _incoming.emit.
            epochJob?.cancel()
            // Close the underlying raw connection.
            runCatching { connection.close() }
        }

        // Hard invariants. check() throws on violation; that's intentional —
        // if any of these fail, the SDK is in a state where downstream
        // behaviour is undefined and we'd rather crash on the developer's
        // machine than ship a silent corruption.
        check(_state.value == target) {
            "I-terminal-state: expected ${target.name} after transition, got ${_state.value.name}"
        }
        val ej = epochJob
        check(ej == null || ej.isCancelled) {
            "I-terminal-epoch: epochJob still alive after transition to ${target.name}"
        }
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
     * **after** SessionManager has already evicted us from `active` and
     * `_sessions`. That is the hypothesis-B1 leak: messages reach the
     * Swift collector (still subscribed to the shared flow) while the UI
     * — which reads `kit.sessions.value` — shows "not connected." Cancel
     * the epoch and close the raw so the session footprint is fully torn
     * down before SessionManager's `watchForTerminal` finishes its
     * activeLock / `_sessions` cleanup.
     */
    internal suspend fun markFailedAfterExhaustion() {
        // Guard: only this method's contract requires we transition only
        // when in Reconnecting. transitionToTerminal itself accepts any
        // non-terminal state, but a stale exhaustion call should not flip
        // a session that somehow re-Connected via a race.
        val proceed = connectionLock.withLock {
            _state.value == ConnectionState.Reconnecting
        }
        if (proceed) {
            transitionToTerminal(ConnectionState.Failed, "reconnect exhausted")
        }
    }

    private suspend fun routeEvents(channel: ReceiveChannel<ProtocolEvent>) {
        try {
            for (event in channel) {
                when (event) {
                    is ProtocolEvent.Message -> {
                        // Zombie-detection. If we're about to push a message
                        // into the public `incoming` flow but SessionManager
                        // no longer treats us as the registered session for
                        // this peer (either evicted or replaced), the public
                        // session-list view is desynced from the live
                        // message stream — the failure mode described in the
                        // architecture review's hypothesis B1. Log loudly
                        // every time it happens; we still emit the message
                        // so observable behaviour doesn't regress, but the
                        // warning surfaces the inconsistency for the next
                        // run's log dump.
                        val reg = lookupRegistration?.let { lookup ->
                            runCatching { lookup(this@P2pSessionImpl) }.getOrNull()
                        }
                        if (reg != null) {
                            val differentActive = reg.activeSessionId != null &&
                                reg.activeSessionId != id
                            if (!reg.isInPublicList || differentActive) {
                                logger.warn(
                                    "ZOMBIE session emitting Message: " +
                                        "sessionId=$id " +
                                        "peerId=${peer.id.value.take(8)} " +
                                        "state=${_state.value.name} " +
                                        "activeSessionId=${reg.activeSessionId ?: "(none)"} " +
                                        "inPublicList=${reg.isInPublicList}"
                                )
                            }
                        }
                        _incoming.emit(event.message)
                    }
                    is ProtocolEvent.Ping -> {
                        runCatching {
                            sendMutex.withLock { protocol.sendPong(connection) }
                        }.onFailure { logger.warn("Session $id: failed to send PONG", it) }
                    }
                    is ProtocolEvent.Pong -> lastPongAt.value = clock()
                    is ProtocolEvent.Hello -> {
                        logger.debug("Session $id: ignoring late HELLO")
                    }
                    is ProtocolEvent.Ack -> {
                        // Reserved for v0.2 reliability work.
                    }
                    is ProtocolEvent.Close -> {
                        // Clean close from peer — never retry.
                        markCleanlyClosed()
                        return
                    }
                    is ProtocolEvent.PeerError -> {
                        logger.warn("Session $id: peer error: ${event.reason}")
                        onConnectionLost("peer error: ${event.reason}")
                        return
                    }
                    is ProtocolEvent.FileOffer -> fileTransferDispatcher.onFileOffer(event.transferId, event.payload)
                    is ProtocolEvent.FileAccept -> fileTransferDispatcher.onFileAccept(event.transferId)
                    is ProtocolEvent.FileReject -> fileTransferDispatcher.onFileReject(event.transferId, event.reason)
                    is ProtocolEvent.FileData -> fileTransferDispatcher.onFileData(event.frame)
                    is ProtocolEvent.FileDone -> fileTransferDispatcher.onFileDone(event.transferId)
                    is ProtocolEvent.FileCancel -> fileTransferDispatcher.onFileCancel(event.transferId, event.reason)
                }
            }
            // Channel completed without explicit close or error frame. This
            // is a "remote hangup". For v0.2 we treat it like a clean close —
            // there is no error to react to, only a closed socket. The clean
            // close path skips reconnect per spec.
            markCleanlyClosed()
        } catch (e: CancellationException) {
            throw e
        } catch (_: ClosedReceiveChannelException) {
            markCleanlyClosed()
        } catch (e: Throwable) {
            logger.warn("Session $id: routeEvents failed", e)
            onConnectionLost("routeEvents threw: ${e.message ?: e::class.simpleName}")
        }
    }

    private suspend fun keepAliveLoop(epochConnection: RawConnection) {
        while (scope.isActive && _state.value == ConnectionState.Connected) {
            delay(keepAlive.pingIntervalMillis)
            if (!scope.isActive || _state.value != ConnectionState.Connected) return
            try {
                sendMutex.withLock { protocol.sendPing(epochConnection) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                logger.warn("Session $id: failed to send PING", e)
                onConnectionLost("PING send failed: ${e.message ?: e::class.simpleName}")
                return
            }
            val sinceLastPong = clock() - lastPongAt.value
            if (sinceLastPong > keepAlive.timeoutMillis) {
                logger.warn(
                    "Session $id: no PONG received for $sinceLastPong ms " +
                        "(timeout=${keepAlive.timeoutMillis} ms)"
                )
                onConnectionLost("keep-alive timeout")
                return
            }
        }
    }

    private suspend fun markCleanlyClosed() {
        // Guard: only act on Connected. transitionToTerminal itself is
        // idempotent vs Closed/Failed, but a stale clean-close shouldn't
        // override an in-flight Reconnecting (a brand new raw might be
        // about to rearm us).
        val proceed = connectionLock.withLock {
            _state.value == ConnectionState.Connected
        }
        if (proceed) {
            transitionToTerminal(ConnectionState.Closed, "remote hangup / clean close")
        }
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

    private suspend fun onConnectionLost(cause: String) {
        // Decide under the lock:
        //   - shouldFail = "transition to Failed via transitionToTerminal"
        //   - handler    = "kick off a reconnect attempt"
        // Only one is true; both can be false (already terminal / Reconnecting).
        var shouldFail = false
        val handler: ReconnectHandler? = connectionLock.withLock {
            when (_state.value) {
                ConnectionState.Connected -> {
                    val h = reconnectHandler
                    if (h == null) {
                        shouldFail = true  // hand off to transitionToTerminal below
                        null
                    } else {
                        _state.value = ConnectionState.Reconnecting
                        h
                    }
                }
                else -> null  // already Reconnecting / Closing / Closed / Failed — leave it
            }
        }
        if (handler != null) {
            logger.debug("Session $id: connection lost ($cause), starting reconnect")
            // Run on the session scope so close() / kit.stop() cancel it.
            scope.launch { handler.onConnectionLost(this@P2pSessionImpl) }
        } else if (shouldFail) {
            // No reconnect handler (incoming session, or outgoing with
            // Disabled). Centralised terminal path handles state flip,
            // epoch cancel, file-transfer teardown, and raw close in one
            // place.
            transitionToTerminal(ConnectionState.Failed, cause)
        }
    }
}
