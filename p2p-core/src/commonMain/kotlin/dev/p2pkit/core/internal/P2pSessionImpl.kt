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
 * Concrete [P2pSession] backed by a single [RawConnection].
 *
 * The session owns a [Mutex] that serializes outbound writes (concurrent
 * `send` calls from app code never produce interleaved frames). Inbound
 * events arrive on [events] — DATA → [incoming], PING → reply with PONG,
 * PONG → reset keep-alive deadline, CLOSE/ERROR → fail.
 */
internal class P2pSessionImpl(
    override val id: String,
    override val peer: Peer,
    private val connection: RawConnection,
    private val events: ReceiveChannel<ProtocolEvent>,
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

    fun start() {
        scope.launch { routeEvents() }
        scope.launch { keepAliveLoop() }
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
        if (_state.value == ConnectionState.Closed || _state.value == ConnectionState.Failed) return
        _state.value = ConnectionState.Closing
        runCatching {
            sendMutex.withLock { protocol.sendClose(connection) }
        }
        sessionJob.cancelAndJoin()
        runCatching { connection.close() }
        _state.value = ConnectionState.Closed
    }

    private suspend fun routeEvents() {
        try {
            for (event in events) {
                when (event) {
                    is ProtocolEvent.Message -> _incoming.emit(event.message)
                    is ProtocolEvent.Ping -> {
                        runCatching {
                            sendMutex.withLock { protocol.sendPong(connection) }
                        }.onFailure { logger.warn("Session $id: failed to send PONG", it) }
                    }
                    is ProtocolEvent.Pong -> lastPongAt.value = clock()
                    is ProtocolEvent.Hello -> {
                        // Already handshaked; an extra HELLO is unexpected but harmless.
                        logger.debug("Session $id: ignoring late HELLO")
                    }
                    is ProtocolEvent.Ack -> {
                        // Reserved for v0.2 reliability work.
                    }
                    is ProtocolEvent.Close -> {
                        _state.value = ConnectionState.Closed
                        return
                    }
                    is ProtocolEvent.PeerError -> {
                        logger.warn("Session $id: peer error: ${event.reason}")
                        _state.value = ConnectionState.Failed
                        return
                    }
                }
            }
            // Channel completed without explicit close — treat as remote hangup.
            if (_state.value == ConnectionState.Connected) {
                _state.value = ConnectionState.Closed
            }
        } catch (e: CancellationException) {
            throw e
        } catch (_: ClosedReceiveChannelException) {
            if (_state.value == ConnectionState.Connected) {
                _state.value = ConnectionState.Closed
            }
        } catch (e: Throwable) {
            logger.warn("Session $id: routeEvents failed", e)
            _state.value = ConnectionState.Failed
        }
    }

    private suspend fun keepAliveLoop() {
        while (scope.isActive && _state.value == ConnectionState.Connected) {
            delay(keepAlive.pingIntervalMillis)
            if (!scope.isActive || _state.value != ConnectionState.Connected) return
            try {
                sendMutex.withLock { protocol.sendPing(connection) }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                logger.warn("Session $id: failed to send PING", e)
                _state.value = ConnectionState.Failed
                return
            }
            val sinceLastPong = clock() - lastPongAt.value
            if (sinceLastPong > keepAlive.timeoutMillis) {
                logger.warn(
                    "Session $id: no PONG received for $sinceLastPong ms " +
                        "(timeout=${keepAlive.timeoutMillis} ms); marking session failed"
                )
                _state.value = ConnectionState.Failed
                return
            }
        }
    }
}
