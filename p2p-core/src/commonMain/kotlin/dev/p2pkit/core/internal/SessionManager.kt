package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.BackgroundPolicy
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.protocol.P2pProtocol
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.security.SecurityManager
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Owns the lifecycle of every active [P2pSession].
 *
 * Responsibilities:
 *   - Open outgoing sessions on [connect] (idempotent: returns an existing
 *     active session for the same peer rather than spawning a duplicate).
 *   - Accept inbound connections from each registered [DataTransport].
 *   - Run the HELLO handshake on both directions.
 *   - Wrap connections with the configured [SecurityManager].
 *   - Publish accepted sessions on [incomingSessions] and track every active
 *     session in [sessions].
 *   - Close all sessions cleanly on [stop] / [closeAllSessions].
 */
internal class SessionManager(
    private val scope: CoroutineScope,
    private val transportManager: TransportManager,
    private val protocol: P2pProtocol,
    private val security: SecurityManager,
    private val keepAlive: KeepAliveConfig,
    private val reconnectPolicy: ReconnectPolicy,
    private val localAppId: AppId,
    private val localPeerId: PeerId,
    private val localDeviceName: String,
    private val localPlatform: Platform,
    private val localTransports: Set<TransportKind>,
    private val clock: () -> Long,
    private val logger: P2pLogger
) {

    private val _sessions = MutableStateFlow<List<P2pSession>>(emptyList())
    val sessions: StateFlow<List<P2pSession>> = _sessions.asStateFlow()

    private val _incomingSessions = MutableSharedFlow<P2pSession>(
        replay = 0,
        extraBufferCapacity = 64,
        onBufferOverflow = BufferOverflow.SUSPEND
    )
    val incomingSessions: SharedFlow<P2pSession> = _incomingSessions.asSharedFlow()

    /** Maps peer id to the active session, for idempotent [connect]. */
    private val active: MutableMap<PeerId, P2pSession> = mutableMapOf()

    /**
     * Maps peer id to the in-flight [connect] attempt, so simultaneous
     * [connect] calls for the same peer share a single transport.connect
     * + handshake instead of racing each other.
     */
    private val pending: MutableMap<PeerId, CompletableDeferred<P2pSession>> = mutableMapOf()

    /** Protects [active] and [pending] across concurrent connect/incoming/close calls. */
    private val activeLock = Mutex()

    fun startAcceptingIncoming(transports: List<DataTransport>) {
        for (transport in transports) {
            transport.incomingConnections()
                .onEach { connection -> handleIncoming(connection) }
                .launchIn(scope)
        }
    }

    suspend fun connect(peer: Peer, internalPeer: InternalPeer): P2pSession {
        // Atomic decision under the lock: return an existing active session,
        // wait on someone else's in-flight connect, or become the connector.
        // The actual `await` / connect work runs OUTSIDE the lock so the lock
        // is short-held.
        val outcome: ConnectOutcome = activeLock.withLock {
            val existing = active[peer.id]
            if (existing != null && existing.state.value in ACTIVE_STATES) {
                return existing
            }
            if (existing != null) active.remove(peer.id) // terminal — replace
            val inFlight = pending[peer.id]
            if (inFlight != null) {
                ConnectOutcome.Await(inFlight)
            } else {
                val fresh = CompletableDeferred<P2pSession>()
                pending[peer.id] = fresh
                ConnectOutcome.Connect(fresh)
            }
        }

        return when (outcome) {
            is ConnectOutcome.Await -> outcome.deferred.await()
            is ConnectOutcome.Connect -> performConnect(peer, internalPeer, outcome.deferred)
        }
    }

    private suspend fun performConnect(
        peer: Peer,
        internalPeer: InternalPeer,
        deferred: CompletableDeferred<P2pSession>
    ): P2pSession {
        try {
            val transport = transportManager.selectBestTransport(internalPeer)
            val rawConnection = try {
                transport.connect(internalPeer)
            } catch (e: P2pError) {
                throw e
            } catch (e: Throwable) {
                throw P2pError.ConnectionFailed("Transport connect failed: ${e.message}")
            }
            val session = setupSession(rawConnection, expectedPeer = peer, isIncoming = false)
            deferred.complete(session)
            return session
        } catch (e: Throwable) {
            deferred.completeExceptionally(e)
            throw e
        } finally {
            activeLock.withLock {
                if (pending[peer.id] === deferred) pending.remove(peer.id)
            }
        }
    }

    private sealed class ConnectOutcome {
        data class Await(val deferred: CompletableDeferred<P2pSession>) : ConnectOutcome()
        data class Connect(val deferred: CompletableDeferred<P2pSession>) : ConnectOutcome()
    }

    private fun handleIncoming(connection: RawConnection) {
        scope.launch {
            try {
                setupSession(connection, expectedPeer = null, isIncoming = true)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                logger.warn("Incoming session setup failed", e)
                runCatching { connection.close() }
            }
        }
    }

    private suspend fun setupSession(
        rawConnection: RawConnection,
        expectedPeer: Peer?,
        isIncoming: Boolean
    ): P2pSession {
        val eventChannel = Channel<ProtocolEvent>(capacity = Channel.UNLIMITED)
        val readerJob = scope.launch {
            try {
                protocol.events(rawConnection).collect { event ->
                    eventChannel.send(event)
                }
                eventChannel.close()
            } catch (e: CancellationException) {
                eventChannel.close()
                throw e
            } catch (e: Throwable) {
                eventChannel.close(e)
            }
        }

        try {
            val peerHello = performHandshake(
                protocol = protocol,
                connection = rawConnection,
                events = eventChannel,
                localAppId = localAppId,
                localPeerId = localPeerId,
                localDeviceName = localDeviceName,
                localPlatform = localPlatform,
                localTransports = localTransports
            )
            // Security wrap — no-op in v0.1 (NoOpSecurityManager returns a
            // passthrough), but keeps the future encryption hook open.
            val resolvedPeer = expectedPeer ?: peerHello.toPeer()
            val secureConnection = security.performHandshake(rawConnection, resolvedPeer)

            val session = P2pSessionImpl(
                id = "${if (isIncoming) "in" else "out"}-${resolvedPeer.id.value}-${clock()}",
                peer = resolvedPeer,
                connection = secureConnection,
                events = eventChannel,
                protocol = protocol,
                parentScope = scope,
                keepAlive = keepAlive,
                clock = clock,
                logger = logger
            )
            session.start()
            registerSession(resolvedPeer.id, session)

            if (isIncoming) {
                _incomingSessions.emit(session)
            }
            return session
        } catch (e: Throwable) {
            readerJob.cancel()
            runCatching { rawConnection.close() }
            throw e
        }
    }

    private suspend fun registerSession(peerId: PeerId, session: P2pSession) {
        activeLock.withLock {
            active[peerId] = session
        }
        _sessions.update { it + session }

        // When the session terminates, remove it from tracking.
        scope.launch {
            session.state.first { it == ConnectionState.Closed || it == ConnectionState.Failed }
            activeLock.withLock {
                if (active[peerId] === session) active.remove(peerId)
            }
            _sessions.update { list -> list.filter { it !== session } }
        }
    }

    suspend fun closeAllSessions() {
        val snapshot = activeLock.withLock { active.values.toList() }
        for (session in snapshot) {
            runCatching { session.close() }
        }
    }

    fun applyBackgroundPolicy(policy: BackgroundPolicy) {
        when (policy) {
            is BackgroundPolicy.CloseActiveSessions -> {
                scope.launch { closeAllSessions() }
            }
            is BackgroundPolicy.KeepRunning -> { /* nothing to do */ }
        }
    }

    private companion object {
        val ACTIVE_STATES = setOf(
            ConnectionState.Connecting,
            ConnectionState.Handshaking,
            ConnectionState.Connected,
            ConnectionState.Reconnecting
        )
    }
}
