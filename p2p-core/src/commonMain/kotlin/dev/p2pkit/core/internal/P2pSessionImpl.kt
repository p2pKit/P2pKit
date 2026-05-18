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
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
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
    private val random: Random = Random.Default
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
        val terminalAlready = connectionLock.withLock {
            val s = _state.value
            if (s == ConnectionState.Closed || s == ConnectionState.Failed) return@withLock true
            _state.value = ConnectionState.Closing
            false
        }
        if (terminalAlready) return

        // Abort in-flight file transfers before we tear the connection down so
        // their state surfaces a sensible "session closed" cause rather than a
        // mid-write IOException.
        runCatching { fileTransferDispatcher.closeAll("session $id closed") }
        // Best-effort CLOSE frame on whatever connection is current.
        runCatching {
            sendMutex.withLock { protocol.sendClose(connection) }
        }
        // Cancel every child (epoch loops + any in-flight reconnect handler).
        sessionJob.cancelAndJoin()
        runCatching { connection.close() }
        _state.value = ConnectionState.Closed
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
     * Final transition when the reconnect handler exhausts its retry budget.
     * No-op if the session is already in a terminal state (e.g., the user
     * called [close] while we were retrying — close wins).
     */
    internal suspend fun markFailedAfterExhaustion() {
        connectionLock.withLock {
            if (_state.value == ConnectionState.Reconnecting) {
                _state.value = ConnectionState.Failed
            }
        }
    }

    private suspend fun routeEvents(channel: ReceiveChannel<ProtocolEvent>) {
        try {
            for (event in channel) {
                when (event) {
                    is ProtocolEvent.Message -> _incoming.emit(event.message)
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
        connectionLock.withLock {
            if (_state.value == ConnectionState.Connected) {
                _state.value = ConnectionState.Closed
            }
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
        var cleanupForFail = false
        val handler: ReconnectHandler? = connectionLock.withLock {
            when (_state.value) {
                ConnectionState.Connected -> {
                    val h = reconnectHandler
                    if (h == null) {
                        _state.value = ConnectionState.Failed
                        cleanupForFail = true
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
        }
        if (cleanupForFail) {
            // No reconnect handler is wired (incoming session, or outgoing
            // with ReconnectPolicy.Disabled). State is now Failed and
            // SessionManager's watchForTerminal will remove us from the
            // public lists. Without explicit cleanup, the epoch's three
            // coroutines (routeEvents / keepAliveLoop / observeRawState)
            // linger until kit.stop() — observeRawState in particular parks
            // on raw.state.collect forever because the StateFlow is stable
            // at Closed and never emits again. Cancel the epoch so the
            // session footprint is closed promptly, and fire-and-forget
            // close the underlying raw connection on the session scope so
            // the NWConnection / Socket releases its file descriptor.
            logger.debug(
                "Session $id: Failed ($cause), cancelling epoch + closing raw connection"
            )
            epochJob?.cancel()
            scope.launch { runCatching { connection.close() } }
        }
    }
}
