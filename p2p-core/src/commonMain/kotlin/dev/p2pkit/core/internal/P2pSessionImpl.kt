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
    private val logger: P2pLogger
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

    fun start() {
        startEpoch()
    }

    private fun startEpoch() {
        val job = SupervisorJob(parent = sessionJob)
        epochJob = job
        val epochScope = CoroutineScope(scope.coroutineContext + job)
        lastPongAt.value = clock()
        epochScope.launch { routeEvents(events) }
        epochScope.launch { keepAliveLoop(connection) }
    }

    override suspend fun send(message: P2pMessage) {
        if (_state.value != ConnectionState.Connected) {
            throw P2pError.ConnectionFailed("Session $id is ${_state.value}; cannot send")
        }
        sendMutex.withLock {
            protocol.sendMessage(connection, message)
        }
    }

    override suspend fun close() {
        val terminalAlready = connectionLock.withLock {
            val s = _state.value
            if (s == ConnectionState.Closed || s == ConnectionState.Failed) return@withLock true
            _state.value = ConnectionState.Closing
            false
        }
        if (terminalAlready) return

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
    private suspend fun onConnectionLost(cause: String) {
        val handler: ReconnectHandler? = connectionLock.withLock {
            when (_state.value) {
                ConnectionState.Connected -> {
                    val h = reconnectHandler
                    if (h == null) {
                        _state.value = ConnectionState.Failed
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
    }
}
