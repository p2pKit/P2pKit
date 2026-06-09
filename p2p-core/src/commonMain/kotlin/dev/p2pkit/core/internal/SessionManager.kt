package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.BackgroundPolicy
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.NetworkPathStatus
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
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.launchIn
import kotlinx.coroutines.flow.onEach
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull

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
    private val fileTransferConfig: FileTransferConfig = FileTransferConfig(),
    /**
     * Lock-free best-effort lookup of the latest [InternalPeer] known to
     * [PeerRegistry] for a given [PeerId]. Read by [SessionReconnectHandler]
     * before every reconnect attempt so address rotation (DHCP lease change,
     * hotspot move, captive-portal reattach) is picked up automatically.
     *
     * Returns `null` when the registry has no entry (peer evicted as stale,
     * never discovered); the handler falls back to its original capture.
     *
     * Default `{ null }` makes existing tests that construct SessionManager
     * without a registry transparently fall back to the captured peer.
     */
    private val peerLookup: (PeerId) -> InternalPeer? = { null },
    /**
     * V0.4-DISCOVERY-REFRESH: invoked once when an outgoing session enters
     * `Reconnecting`, before the first retry attempt. Wired by P2pKitImpl
     * to call `DiscoveryTransport.refresh()` on every registered discovery
     * transport — forces a fresh active mDNS query so the remote peer's
     * post-rebind port can land in `PeerRegistry` before the next dial.
     *
     * Default `{}` keeps existing tests (no transports / no registry)
     * working without a refresh path.
     */
    private val refreshDiscovery: suspend () -> Unit = {}
) {

    /**
     * Single source of truth for session bookkeeping — owns the byPeer
     * map, the in-flight `pending` map, and the published [sessions]
     * StateFlow under a single mutex. See [SessionStore] kdoc for the
     * rationale (replaces the previous "two stores updated by convention"
     * model).
     */
    private val store = SessionStore(logger)
    val sessions: StateFlow<List<P2pSession>> = store.sessions

    private val _incomingSessions = MutableSharedFlow<P2pSession>(
        replay = 0,
        extraBufferCapacity = 64,
        onBufferOverflow = BufferOverflow.SUSPEND
    )
    val incomingSessions: SharedFlow<P2pSession> = _incomingSessions.asSharedFlow()

    /**
     * Path-recovered signal consumed by every [SessionReconnectHandler]
     * currently in its retry loop. When the host's network path
     * transitions to [NetworkPathStatus.Satisfied], [applyPathChange]
     * emits to this flow and any handler currently parked in its
     * `retryDelayMillis` wait will wake immediately and attempt a dial
     * instead of waiting out the rest of the delay.
     *
     * `extraBufferCapacity = 1` + `DROP_OLDEST` means: if Satisfied fires
     * while no handler is parked (e.g., all handlers are mid-dial), the
     * latest signal is cached. The first handler to enter `.first()` next
     * picks it up — subsequent handlers see no buffered value (replay=0)
     * and wait for the next emit or for their delay to expire.
     */
    private val pathSatisfiedSignal = MutableSharedFlow<Unit>(
        replay = 0,
        extraBufferCapacity = 1,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )

    fun startAcceptingIncoming(transports: List<DataTransport>) {
        for (transport in transports) {
            transport.incomingConnections()
                .onEach { connection -> handleIncoming(connection) }
                .launchIn(scope)
        }
    }

    suspend fun connect(peer: Peer, internalPeer: InternalPeer): P2pSession {
        // Atomic decision delegated to the store: return an existing active
        // session, wait on someone else's in-flight connect, or become the
        // connector. The actual `await` / connect work runs OUTSIDE the
        // store's mutex (the decision is short-held, the work is not).
        return when (val decision = store.startOrJoin(peer.id)) {
            is ConnectDecision.Existing -> decision.session
            is ConnectDecision.JoinPending -> decision.deferred.await()
            is ConnectDecision.BecomeConnector ->
                performConnect(peer, internalPeer, decision.deferred)
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
            store.endPending(peer.id, deferred)
        }
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
            fileTransferConfig = fileTransferConfig,
            lookupRegistration = store::registrationOf
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
                    originalInternalPeer = internalPeerForReconnect,
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
            // Identity check for OUTGOING connects: we dialed a specific peer
            // (expectedPeer) at a discovery-supplied host:port. Any LAN device
            // can answer on that address (spoof / race), so verify the remote's
            // claimed PeerId in its HELLO matches who we intended to reach;
            // otherwise we'd register a stranger under the expected peer's id.
            // Under NoneForMvp this closes the accidental/active host:port-race
            // case (full protection needs the security handshake).
            if (expectedPeer != null && peerHello.peerId != expectedPeer.id.value) {
                runCatching { protocol.sendError(rawConnection, "peerId mismatch") }
                throw P2pError.HandshakeRejected(
                    "peerId mismatch: expected ${expectedPeer.id.value} but remote announced ${peerHello.peerId}"
                )
            }
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
     * V0.4-RECONNECT: each attempt re-resolves the target [InternalPeer] via
     * [peerLookup] (typically `PeerRegistry::internalPeer`) so address
     * rotation — DHCP lease change, hotspot move, captive-portal reattach,
     * Android NSD rebind after network rotation — is picked up automatically.
     * The lookup is a lock-free [kotlinx.coroutines.flow.StateFlow.value]
     * snapshot read, performed immediately before transport selection /
     * dial to minimise the stale window. The result is NOT cached between
     * attempts; every attempt does a fresh lookup. If the registry has no
     * entry (peer evicted as stale, never registered), the fallback is the
     * [originalInternalPeer] captured at session creation — the address we
     * successfully connected to once, which is a reasonable last-resort
     * guess and matches the v0.3 behaviour.
     */
    private inner class SessionReconnectHandler(
        private val expectedPeer: Peer,
        private val originalInternalPeer: InternalPeer,
        private val policy: ReconnectPolicy.Enabled
    ) : ReconnectHandler {

        override suspend fun onConnectionLost(session: P2pSessionImpl) {
            var attempt = 0
            var lastResolvedHints = originalInternalPeer.transportHints
            val peerShort = expectedPeer.id.value.take(8)
            val cachedStr = renderHints(originalInternalPeer.transportHints)
            // V0.4-DISCOVERY-REFRESH: ask every discovery transport to send
            // a fresh active query before the first dial. Closes the gap
            // where the remote peer rebound to a new port but our NSD cache
            // hasn't observed the re-announcement yet — the active query
            // forces the remote responder to answer with its current state.
            // Errors are caught + logged but do not block the retry loop.
            logger.info(
                "reconnect: refresh requested peer=$peerShort name=${expectedPeer.name}"
            )
            try {
                refreshDiscovery()
                logger.info(
                    "reconnect: refresh complete peer=$peerShort name=${expectedPeer.name}"
                )
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                logger.warn(
                    "reconnect: refresh failed peer=$peerShort name=${expectedPeer.name} " +
                        "reason=${e::class.simpleName}: ${e.message ?: ""}"
                )
            }

            // V0.5-PERIODIC-REFRESH (Phase 2.5): the one-shot refresh above
            // fires the moment we enter `Reconnecting`, but if the remote
            // peer's Wi-Fi is still down at that instant its re-announce
            // hasn't been sent yet — by the time it lands seconds later, our
            // single refresh window has already passed and every subsequent
            // dial uses the stale port from JmDNS's cache. Launching a
            // background loop that refires `refreshDiscovery()` every ~3s
            // (with small jitter to desync concurrent reconnects) keeps the
            // local NSD cache aligned with the remote's actual state
            // throughout the entire retry budget. Cancelled in the `finally`
            // below on every exit path — success, exhaustion, or session
            // state change.
            val periodicRefreshJob = launchPeriodicRefresh(session, peerShort)
            try {
                while (attempt < policy.maxAttempts) {
                    attempt++
                    try {
                        // Wait either for the retry delay OR for a path-satisfied
                        // signal, whichever fires first. The signal accelerates
                        // recovery on Wi-Fi handovers: an `Unsatisfied → Satisfied`
                        // transition wakes parked handlers immediately so the next
                        // dial happens within milliseconds of the network coming
                        // back instead of after the full `retryDelayMillis`.
                        withTimeoutOrNull(policy.retryDelayMillis) {
                            pathSatisfiedSignal.first()
                        }
                    } catch (e: CancellationException) {
                        throw e
                    }
                    if (session.state.value != ConnectionState.Reconnecting) return

                    // Fresh per-attempt lookup. No caching between attempts; the
                    // read happens immediately before transport selection so the
                    // stale window between snapshot and dial is microseconds.
                    val resolved = peerLookup(expectedPeer.id)
                    val target = resolved ?: originalInternalPeer
                    val registryHit = resolved != null
                    val resolvedStr = if (resolved != null) renderHints(resolved.transportHints) else "—"
                    val dialedStr = renderHints(target.transportHints)
                    val changedFromPrev = target.transportHints != lastResolvedHints
                    val source = if (registryHit) "REGISTRY" else "FALLBACK"
                    logger.info(
                        "reconnect: attempt=$attempt/${policy.maxAttempts} peer=$peerShort " +
                            "name=${expectedPeer.name} cached=$cachedStr resolved=$resolvedStr " +
                            "dialed=$dialedStr source=$source registryHit=$registryHit " +
                            "changedFromPrev=$changedFromPrev"
                    )
                    lastResolvedHints = target.transportHints

                    val outcome = runCatching {
                        val transport = transportManager.selectBestTransport(target)
                        val raw = transport.connect(target)
                        runHandshake(raw, expectedPeer = expectedPeer)
                    }

                    val handshake = outcome.getOrElse { e ->
                        if (e is CancellationException) throw e
                        logger.warn(
                            "reconnect: attempt=$attempt/${policy.maxAttempts} peer=$peerShort " +
                                "name=${expectedPeer.name} FAILED dialed=$dialedStr source=$source " +
                                "reason=${e::class.simpleName}: ${e.message ?: ""}"
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
                    logger.info(
                        "reconnect: attempt=$attempt/${policy.maxAttempts} peer=$peerShort " +
                            "name=${expectedPeer.name} SUCCEEDED dialed=$dialedStr source=$source"
                    )
                    return
                }
                session.markFailedAfterExhaustion()
            } finally {
                periodicRefreshJob.cancel()
            }
        }

        /**
         * V0.5-PERIODIC-REFRESH: background coroutine that refires
         * [refreshDiscovery] every ~3s (with jitter) while the session is in
         * `Reconnecting`. Started by [onConnectionLost] right after the
         * initial one-shot refresh; cancelled in that function's `finally` so
         * every exit path — rearm success, attempt exhaustion, state change
         * to `Failed`/`Closed`, or scope cancellation — also stops the loop.
         *
         * Self-stops as a defensive belt-and-suspenders if it ever observes
         * the session leaving `Reconnecting` between ticks; the outer
         * `cancel()` is authoritative, this is just to log a more specific
         * reason than "cancelled" when the state-transition path runs first.
         *
         * Launched on the SessionManager's [scope] (not the session's scope)
         * so a session-scope-cancellation race during rearmWith() can't kill
         * the periodic refresh mid-tick — the outer `finally` cancels it
         * deterministically.
         */
        private fun launchPeriodicRefresh(
            session: P2pSessionImpl,
            peerShort: String
        ): Job {
            val periodMs = 3000L
            val jitterMs = 400L
            return scope.launch {
                var tick = 0
                var stopReason = "cancelled"
                logger.info(
                    "reconnect: periodic refresh started peer=$peerShort " +
                        "name=${expectedPeer.name} periodMs=$periodMs jitterMs=±$jitterMs"
                )
                try {
                    while (true) {
                        val nextDelay = ((periodMs - jitterMs)..(periodMs + jitterMs)).random()
                        delay(nextDelay)
                        if (session.state.value != ConnectionState.Reconnecting) {
                            stopReason = "stateChange:${session.state.value}"
                            break
                        }
                        tick++
                        logger.info(
                            "reconnect: periodic refresh tick=$tick peer=$peerShort " +
                                "name=${expectedPeer.name} delayMs=$nextDelay"
                        )
                        try {
                            refreshDiscovery()
                        } catch (e: CancellationException) {
                            throw e
                        } catch (e: Throwable) {
                            logger.warn(
                                "reconnect: periodic refresh tick=$tick peer=$peerShort " +
                                    "name=${expectedPeer.name} FAILED " +
                                    "reason=${e::class.simpleName}: ${e.message ?: ""}"
                            )
                        }
                    }
                } finally {
                    logger.info(
                        "reconnect: periodic refresh stopped peer=$peerShort " +
                            "name=${expectedPeer.name} ticks=$tick reason=$stopReason"
                    )
                }
            }
        }

        private fun renderHints(hints: List<dev.p2pkit.core.transport.TransportHint>): String =
            if (hints.isEmpty()) "—" else hints.joinToString(",") { h ->
                "${h.type}:${h.host ?: "?"}:${h.port ?: "?"}"
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
        val outcome = store.tryRegister(
            peerId = peerId,
            session = session,
            isIncoming = isIncoming,
            localPeerIdValue = localPeerId.value
        )

        val existingStateLabel = (outcome as? RegisterOutcome.Replaced)?.loser?.state?.value?.name
            ?: (outcome as? RegisterOutcome.Rejected)?.loser?.state?.value?.name
        logger.info(
            "registerSession ${if (isIncoming) "in" else "out"} peer=${peerId.value.take(8)} " +
                "decision=${outcome::class.simpleName} " +
                "existingState=${existingStateLabel ?: "none"}"
        )

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
     * the store. Extracted so [registerSession] can attach it to the winner
     * in both the Accepted and Replaced paths.
     */
    private fun watchForTerminal(peerId: PeerId, session: P2pSession) {
        scope.launch {
            session.state.first { it == ConnectionState.Closed || it == ConnectionState.Failed }
            store.removeIfMatches(peerId, session)
        }
    }

    suspend fun closeAllSessions() {
        val snapshot = store.activeSnapshot()
        for (session in snapshot) {
            runCatching { session.close() }
        }
    }

    /**
     * Handle a host-network path-status change. Called by [P2pKitImpl] which
     * subscribes to the kit's [NetworkPathObserver] once at startup.
     *
     * - [NetworkPathStatus.Unsatisfied]: route every active session through
     *   [P2pSessionImpl.notifyPathLost], which calls `onConnectionLost`. The
     *   session's existing decision tree handles the rest — sessions wired
     *   with a reconnect handler go to `Reconnecting`; sessions without one
     *   go straight to `Failed`. Concurrent triggers from PING failure or
     *   raw-state observers are de-duped by the connection lock in
     *   `onConnectionLost`.
     * - [NetworkPathStatus.Satisfied]: emit to [pathSatisfiedSignal] so any
     *   reconnect handler currently parked in `retryDelayMillis` wakes and
     *   attempts immediately.
     * - [NetworkPathStatus.Unknown]: no-op. Treated as "no information",
     *   not "no network" — matches the [NoOpNetworkPathObserver] default
     *   on platforms with no observer wired up.
     */
    fun applyPathChange(status: NetworkPathStatus) {
        when (status) {
            NetworkPathStatus.Unsatisfied -> {
                scope.launch {
                    val toNotify = store.activeSnapshot()
                    for (s in toNotify) {
                        (s as? P2pSessionImpl)?.notifyPathLost()
                    }
                }
            }
            NetworkPathStatus.Satisfied -> {
                pathSatisfiedSignal.tryEmit(Unit)
            }
            NetworkPathStatus.Unknown -> { /* no action */ }
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
}
