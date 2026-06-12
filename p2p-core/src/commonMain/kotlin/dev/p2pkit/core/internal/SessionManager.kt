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
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
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
     * Monotonic generation counter bumped on every host-network transition
     * to [NetworkPathStatus.Satisfied]. Every [SessionReconnectHandler] in
     * its retry loop snapshots the current generation and parks until it
     * changes (or its `retryDelayMillis` elapses), waking immediately on a
     * path-recovered transition instead of waiting out the delay.
     *
     * A StateFlow generation counter (not a replay=0 SharedFlow) so a
     * Satisfied transition that lands *before* the handler parks is never
     * dropped: the counter retains its value, so `first { it != snapshot }`
     * returns at once. The previous SharedFlow dropped such a signal when no
     * handler was currently subscribed, which both contradicted this field's
     * own "is cached" KDoc and made the recovery race-dependent
     * (AUDIT-2026-06 fix).
     */
    private val pathSatisfiedGeneration = MutableStateFlow(0)

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
        // Bounded so a peer flooding frames (or a slow local consumer) applies
        // TCP backpressure instead of growing an unbounded in-memory queue —
        // an UNLIMITED channel here was a remote-driven OOM vector
        // (AUDIT-2026-06 fix). 256 events absorb normal bursts; when full the
        // reader suspends and the kernel stops reading the socket.
        val eventChannel = Channel<ProtocolEvent>(capacity = 256)
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
            //
            // Synthetic manual peers (registerManualPeer mints "manual-<uuid>")
            // are exempt: the caller only knows host:port, the placeholder id
            // can never match the remote's real persisted PeerId, and rejecting
            // would make every manual-IP fallback connect fail. For those we
            // adopt the remote's HELLO identity instead (AUDIT-2026-06 fix).
            val isSyntheticManualPeer = expectedPeer != null &&
                expectedPeer.id.value.startsWith("manual-")
            if (expectedPeer != null && !isSyntheticManualPeer &&
                peerHello.peerId != expectedPeer.id.value
            ) {
                runCatching { protocol.sendError(rawConnection, "peerId mismatch") }
                throw P2pError.HandshakeRejected(
                    "peerId mismatch: expected ${expectedPeer.id.value} but remote announced ${peerHello.peerId}"
                )
            }
            // Cheap inbound guard: reject a HELLO that claims OUR OWN peerId
            // (impossible by construction from an honest peer; a spoof would
            // poison the byPeer slot / simultaneous-open tie-break).
            if (peerHello.peerId == localPeerId.value) {
                runCatching { protocol.sendError(rawConnection, "peerId collision with local") }
                throw P2pError.HandshakeRejected("remote announced our own peerId ${peerHello.peerId}")
            }
            // TODO(encryption-milestone): INBOUND peerId is otherwise still
            // trusted at face value here — a rogue LAN peer sharing the appId
            // can claim any *other* peerId and hijack that peer's session slot.
            // Full identity verification (binding peerId to a key) is deferred
            // to the SecurityManager/encryption milestone; under
            // SecurityMode.NoneForMvp the LAN is the trust boundary. See
            // AUDIT_REPORT_2026-06.md "inbound HELLO peerId never verified".
            // Security wrap — no-op in v0.1 (NoOpSecurityManager returns a
            // passthrough), but keeps the future encryption hook open.
            val resolvedPeer =
                if (expectedPeer == null || isSyntheticManualPeer) peerHello.toPeer() else expectedPeer
            val secureConnection = security.performHandshake(rawConnection, resolvedPeer)
            return HandshakeOutputs(
                secureConnection = secureConnection,
                events = eventChannel,
                readerJob = readerJob,
                resolvedPeer = resolvedPeer
            )
        } catch (e: CancellationException) {
            readerJob.cancel()
            runCatching { rawConnection.close() }
            throw e
        } catch (e: P2pError) {
            // Already typed (HandshakeRejected / VersionMismatch from
            // performHandshake, or the peerId checks above) — surface as-is.
            readerJob.cancel()
            runCatching { rawConnection.close() }
            throw e
        } catch (e: Throwable) {
            // AUDIT-2026-06: raw handshake-phase failures previously escaped
            // connect() un-typed — e.g. a write error from sendHello, or the
            // reader closing the events channel with an IOException that
            // surfaces out of events.receive(). Wrap them so callers only ever
            // see a documented P2pError, mirroring the transport-connect wrap
            // in performConnect.
            readerJob.cancel()
            runCatching { rawConnection.close() }
            throw P2pError.ConnectionFailed("Handshake failed: ${e.message}")
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

        /**
         * Path-recovered generation snapshot taken at the Reconnecting edge by
         * [onWillReconnect]. The retry loop waits for the counter to move past
         * this, so a Satisfied transition arriving any time after we entered
         * Reconnecting (even before the loop starts) wakes the dial early.
         */
        @kotlin.concurrent.Volatile
        private var pathWakeBaseline: Int = pathSatisfiedGeneration.value

        override fun onWillReconnect() {
            pathWakeBaseline = pathSatisfiedGeneration.value
        }

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
            // Start from the baseline captured at the Reconnecting edge by
            // [onWillReconnect] (NOT a fresh read here — refreshDiscovery above
            // can take long enough under load that a Satisfied landing during
            // it would otherwise be captured as the baseline and missed). Each
            // iteration parks until the counter moves past lastPathGen, then
            // re-snapshots. StateFlow retains its value, so a transition that
            // already happened is observed immediately (no drop).
            var lastPathGen = pathWakeBaseline
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
                            pathSatisfiedGeneration.first { it != lastPathGen }
                        }
                        lastPathGen = pathSatisfiedGeneration.value
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
     * - [NetworkPathStatus.Satisfied]: bump [pathSatisfiedGeneration] so any
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
                pathSatisfiedGeneration.update { it + 1 }
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
