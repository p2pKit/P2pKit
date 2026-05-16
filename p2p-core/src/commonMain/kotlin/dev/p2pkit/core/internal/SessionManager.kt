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
import dev.p2pkit.core.transfer.FileTransferConfig
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.channels.ReceiveChannel
import kotlinx.coroutines.delay
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
 *   - When [ReconnectPolicy.Enabled] is configured, wire a per-session
 *     [ReconnectHandler] that re-dials and re-handshakes after connection
 *     loss, then rearms the same [P2pSessionImpl] in place so the public
 *     session identity is preserved.
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
    private val logger: P2pLogger,
    private val fileTransferConfig: FileTransferConfig = FileTransferConfig()
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
            val session = setupSession(
                rawConnection = rawConnection,
                expectedPeer = peer,
                isIncoming = false,
                internalPeerForReconnect = internalPeer
            )
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
                setupSession(
                    rawConnection = connection,
                    expectedPeer = null,
                    isIncoming = true,
                    internalPeerForReconnect = null
                )
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                logger.warn("Incoming session setup failed", e)
                runCatching { connection.close() }
            }
        }
    }

    /**
     * Common setup path for both outgoing and incoming sessions. Wraps the
     * raw connection in a HELLO handshake + security wrap, constructs the
     * [P2pSessionImpl], wires the reconnect handler (outgoing only when
     * policy is [ReconnectPolicy.Enabled]), and registers the session.
     */
    private suspend fun setupSession(
        rawConnection: RawConnection,
        expectedPeer: Peer?,
        isIncoming: Boolean,
        internalPeerForReconnect: InternalPeer?
    ): P2pSession {
        val handshake = runHandshake(rawConnection, expectedPeer)

        val session = P2pSessionImpl(
            id = "${if (isIncoming) "in" else "out"}-${handshake.resolvedPeer.id.value}-${clock()}",
            peer = handshake.resolvedPeer,
            initialConnection = handshake.secureConnection,
            initialEvents = handshake.events,
            protocol = protocol,
            parentScope = scope,
            keepAlive = keepAlive,
            clock = clock,
            logger = logger,
            fileTransferConfig = fileTransferConfig
        )

        // Reconnect handler is wired BEFORE start() so the very first
        // connection-loss event is observed by the handler. Wired only when:
        //   - this is an outgoing session (we have an InternalPeer to dial)
        //   - the configured policy is Enabled
        if (!isIncoming && internalPeerForReconnect != null) {
            val policy = reconnectPolicy
            if (policy is ReconnectPolicy.Enabled) {
                session.reconnectHandler = SessionReconnectHandler(
                    expectedPeer = handshake.resolvedPeer,
                    internalPeer = internalPeerForReconnect,
                    policy = policy
                )
            }
        }

        session.start()
        val outcome = registerSession(handshake.resolvedPeer.id, session, isIncoming = isIncoming)

        // Outgoing callers receive the winner via performConnect's deferred so
        // a rejected new session never leaks back to app code as a "live"
        // session. Incoming subscribers (P2pKit.incomingSessions) only see
        // sessions we actually kept.
        val resultSession = when (outcome) {
            is RegisterOutcome.Accepted -> outcome.session
            is RegisterOutcome.Replaced -> outcome.winner
            is RegisterOutcome.Rejected -> outcome.winner
        }
        if (isIncoming && outcome !is RegisterOutcome.Rejected) {
            _incomingSessions.emit(resultSession)
        }
        return resultSession
    }

    /**
     * Runs the HELLO handshake (and security wrap) on a freshly-dialled or
     * freshly-accepted [rawConnection]. Returns everything the session needs
     * to start consuming events. On any failure, closes the connection and
     * cancels the reader job before propagating.
     */
    private suspend fun runHandshake(
        rawConnection: RawConnection,
        expectedPeer: Peer?
    ): HandshakeOutputs {
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
            return HandshakeOutputs(
                secureConnection = secureConnection,
                events = eventChannel,
                readerJob = readerJob,
                resolvedPeer = resolvedPeer
            )
        } catch (e: Throwable) {
            readerJob.cancel()
            runCatching { rawConnection.close() }
            throw e
        }
    }

    private data class HandshakeOutputs(
        val secureConnection: RawConnection,
        val events: ReceiveChannel<ProtocolEvent>,
        val readerJob: Job,
        val resolvedPeer: Peer
    )

    /**
     * Per-outgoing-session reconnect driver. Lives only for sessions whose
     * policy is [ReconnectPolicy.Enabled]; invoked by [P2pSessionImpl] on
     * connection loss while the session is in [ConnectionState.Connected].
     *
     * Loop checks [P2pSession.state] before each delay and after each dial so
     * that `session.close()` and `kit.stop()` stop retries promptly. The loop
     * itself runs on the session's coroutine scope, so cancellation also
     * propagates structurally.
     *
     * Per spec §16.3 we do **not** re-resolve discovery during retry — the
     * [internalPeer] captured at session creation is reused for every
     * attempt. If the peer's address has rotated, retries exhaust until the
     * app re-discovers the peer and reconnects.
     */
    private inner class SessionReconnectHandler(
        private val expectedPeer: Peer,
        private val internalPeer: InternalPeer,
        private val policy: ReconnectPolicy.Enabled
    ) : ReconnectHandler {

        override suspend fun onConnectionLost(session: P2pSessionImpl) {
            var attempt = 0
            while (attempt < policy.maxAttempts) {
                attempt++
                try {
                    delay(policy.retryDelayMillis)
                } catch (e: CancellationException) {
                    throw e
                }
                if (session.state.value != ConnectionState.Reconnecting) return

                val outcome = runCatching {
                    val transport = transportManager.selectBestTransport(internalPeer)
                    val raw = transport.connect(internalPeer)
                    runHandshake(raw, expectedPeer = expectedPeer)
                }

                val handshake = outcome.getOrElse { e ->
                    if (e is CancellationException) throw e
                    logger.warn(
                        "Reconnect attempt $attempt/${policy.maxAttempts} for " +
                            "${expectedPeer.name} failed: ${e.message ?: e::class.simpleName}"
                    )
                    null
                } ?: continue

                if (session.state.value != ConnectionState.Reconnecting) {
                    // Session terminated while we were dialling. Discard the
                    // fresh connection; the reader's collect will exit when
                    // we close it.
                    handshake.readerJob.cancel()
                    runCatching { handshake.secureConnection.close() }
                    return
                }

                session.rearmWith(handshake.secureConnection, handshake.events)
                logger.debug(
                    "Session ${session.id}: reconnected to ${expectedPeer.name} on attempt $attempt"
                )
                return
            }
            session.markFailedAfterExhaustion()
        }
    }

    /**
     * Register a freshly-handshaked session, arbitrating simultaneous opens.
     *
     * If two peers `connect()` each other at the same instant each side ends
     * up with two `P2pSession` candidates — one outgoing, one incoming. To
     * keep the public contract of "one session per peer in
     * [P2pKit.sessions]" honest, both sides apply the same deterministic
     * tie-break:
     *
     *  - **The smaller-id peer keeps its OUTGOING session** (closes its incoming).
     *  - **The larger-id peer keeps its INCOMING session** (closes its outgoing).
     *
     * Both sides keep the same physical TCP connection (the one initiated by
     * the smaller-id peer). The other connection is closed on both ends, and
     * the peer that observes the close treats it like a clean session close.
     *
     * Returns the [RegisterOutcome] so [setupSession] can route the winner
     * back to the caller (outgoing performConnect's deferred, or
     * [P2pKit.incomingSessions] for accepted inbound sessions).
     */
    private suspend fun registerSession(
        peerId: PeerId,
        session: P2pSession,
        isIncoming: Boolean
    ): RegisterOutcome {
        val outcome: RegisterOutcome = activeLock.withLock {
            val existing = active[peerId]
            if (existing != null && existing.state.value in ACTIVE_STATES) {
                val newWinsLocally = if (localPeerId.value < peerId.value) {
                    // We're the smaller-id side — keep our outgoing, reject our incoming.
                    !isIncoming
                } else {
                    // We're the larger-id side (or equal, which is impossible
                    // by construction) — keep our incoming, reject our outgoing.
                    isIncoming
                }
                if (newWinsLocally) {
                    active[peerId] = session
                    _sessions.update { list -> list.filter { it !== existing } + session }
                    RegisterOutcome.Replaced(winner = session, loser = existing)
                } else {
                    RegisterOutcome.Rejected(winner = existing, loser = session)
                }
            } else {
                active[peerId] = session
                _sessions.update { it + session }
                RegisterOutcome.Accepted(session = session)
            }
        }

        when (outcome) {
            is RegisterOutcome.Accepted -> {
                watchForTerminal(peerId, outcome.session)
            }
            is RegisterOutcome.Replaced -> {
                logger.info(
                    "Simultaneous-open for peer ${peerId.value.take(8)}: " +
                        "promoting new ${if (isIncoming) "incoming" else "outgoing"} session, " +
                        "closing previous"
                )
                watchForTerminal(peerId, outcome.winner)
                scope.launch { runCatching { outcome.loser.close() } }
            }
            is RegisterOutcome.Rejected -> {
                logger.info(
                    "Simultaneous-open for peer ${peerId.value.take(8)}: " +
                        "rejecting new ${if (isIncoming) "incoming" else "outgoing"} session, " +
                        "existing wins"
                )
                scope.launch { runCatching { outcome.loser.close() } }
            }
        }
        return outcome
    }

    /**
     * Watch a registered session for its terminal state and clean it out of
     * [active] and [_sessions]. Extracted so [registerSession] can attach it
     * to the winner in both the Accepted and Replaced paths.
     */
    private fun watchForTerminal(peerId: PeerId, session: P2pSession) {
        scope.launch {
            session.state.first { it == ConnectionState.Closed || it == ConnectionState.Failed }
            activeLock.withLock {
                if (active[peerId] === session) active.remove(peerId)
            }
            _sessions.update { list -> list.filter { it !== session } }
        }
    }

    /** Result of a [registerSession] call. Drives the post-registration routing. */
    internal sealed class RegisterOutcome {
        data class Accepted(val session: P2pSession) : RegisterOutcome()
        data class Replaced(val winner: P2pSession, val loser: P2pSession) : RegisterOutcome()
        data class Rejected(val winner: P2pSession, val loser: P2pSession) : RegisterOutcome()
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
