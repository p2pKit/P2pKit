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
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.PeerIdentity
import dev.p2pkit.core.Platform
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.internal.security.AuthenticatedV2SecurityEngine
import dev.p2pkit.core.internal.security.noise.NoiseRole
import dev.p2pkit.core.protocol.P2pProtocol
import dev.p2pkit.core.protocol.ProtocolConstants
import dev.p2pkit.core.protocol.ProtocolEvent
import dev.p2pkit.core.protocol.ProtocolSessionState
import dev.p2pkit.core.security.LocalSecureIdentity
import dev.p2pkit.core.security.SecureConnection
import dev.p2pkit.core.transfer.FileTransferConfig
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.PeerAuthenticationHint
import dev.p2pkit.core.transport.PeerOrigin
import dev.p2pkit.core.transport.RawConnection
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.DelicateCoroutinesApi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.channels.ReceiveChannel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.collect
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Serializes the short session-publication commit with the owning kit's
 * terminal lifecycle transition. Expensive dial, handshake, and close work
 * always runs outside this gate.
 */
internal interface SessionLifecycleGate {
    public suspend fun isActive(expectedGeneration: Long?): Boolean

    public suspend fun <T : Any> commit(
        expectedGeneration: Long?,
        block: suspend () -> T
    ): T?
}

/**
 * Owns the lifecycle of every active [P2pSession].
 *
 * Responsibilities:
 *   - Open outgoing sessions on [connect] (idempotent: returns an existing
 *     active session for the same peer rather than spawning a duplicate).
 *   - Accept inbound connections from each registered [DataTransport].
 *   - Establish the selected whole-kit security profile before HELLO parsing.
 *   - Run the HELLO handshake on both directions over that selected stream.
 *   - Publish accepted sessions on [incomingSessions] and track every active
 *     session in [sessions].
 *   - When [ReconnectPolicy.Enabled] is configured, wire a per-session
 *     [ReconnectHandler] that re-dials and re-handshakes after connection
 *     loss, then rearms the same [P2pSessionImpl] in place so the public
 *     session identity is preserved.
 *   - Close all sessions cleanly on kit stop or [closeAllSessions].
 */
internal class SessionManager(
    private val scope: CoroutineScope,
    private val transportManager: TransportManager,
    private val protocol: P2pProtocol,
    private val securityMode: SecurityMode,
    private val localSecureIdentity: LocalSecureIdentity?,
    private val authenticatedSecurity: AuthenticatedV2SecurityEngine?,
    private val keepAlive: KeepAliveConfig,
    private val reconnectPolicy: ReconnectPolicy,
    private val localAppId: AppId,
    private val localPeerId: PeerId,
    private val localDeviceName: String,
    private val localPlatform: Platform,
    private val localTransports: Set<TransportKind>,
    private val clock: () -> Long,
    private val monotonicClock: () -> Long = clock,
    private val logger: P2pLogger,
    private val fileTransferConfig: FileTransferConfig = FileTransferConfig(),
    private val lifecycleGate: SessionLifecycleGate,
    private val setupTimeoutMillis: Long = DEFAULT_HANDSHAKE_TIMEOUT_MS,
    private val beforeSessionCommitForTest: (suspend () -> Unit)? = null,
    private val afterOutgoingConnectForTest: (suspend () -> Unit)? = null,
    private val afterSessionSetupResultForTest: (suspend () -> Unit)? = null,
    private val beforeIncomingSetupLaunchForTest: (() -> Unit)? = null,
    private val beforeTerminalWatcherRemovalForTest: (suspend () -> Unit)? = null,
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
    private val refreshDiscovery: suspend () -> Unit = {},
    private val discoveryRefreshTimeoutMillis: Long = DEFAULT_DISCOVERY_REFRESH_TIMEOUT_MS,
    /**
     * Test-only (#19 / 2026-07 TST-9, decision #15a): when `true`,
     * [SessionStore.checkInvariants] throws on a detected bookkeeping
     * violation instead of `logger.warn`ing — the suites run with a
     * NoOp/quiet logger, so warn-only enforcement would let a store
     * regression pass every test silently.
     *
     * Default `false` = production behavior (log-don't-crash). [P2pKitImpl]
     * forwards its own `strictSessionInvariants` constructor parameter here,
     * which itself defaults to `false` and is only ever set through the
     * internal [dev.p2pkit.core.dsl.P2pKitBuilder.strictSessionInvariants]
     * knob (enabled by the commonTest `createTestKit` fixture) — so every
     * production construction path still resolves to `false`.
     */
    private val strictInvariants: Boolean = false
) {

    init {
        require(setupTimeoutMillis > 0L) { "setupTimeoutMillis must be > 0" }
        require(discoveryRefreshTimeoutMillis > 0L) {
            "discoveryRefreshTimeoutMillis must be > 0"
        }
    }

    /**
     * Single source of truth for session bookkeeping — owns the byPeer
     * map, the in-flight `pending` map, and the published [sessions]
     * StateFlow under a single mutex. See [SessionStore] kdoc for the
     * rationale (replaces the previous "two stores updated by convention"
     * model).
     */
    private val store = SessionStore(logger, strictInvariants = strictInvariants)
    val sessions: StateFlow<List<P2pSession>> = store.sessions

    /**
     * TEST-ONLY seam (#19 / 2026-07 P1-03) — never call from production
     * code. Forwards to [SessionStore.forceInvariantViolationForTest] so
     * the strict-invariants meta-test can force a known-bad bookkeeping
     * state inside a kit-built store and assert the [strictInvariants]
     * enforcement (throw vs warn) end to end.
     */
    internal suspend fun forceStoreInvariantViolationForTest(session: P2pSession) {
        store.forceInvariantViolationForTest(session)
    }

    /**
     * AUDIT-2026-07 (SEC-1, decision #9a): pre-handshake admission gate.
     * Bounds how many inbound connections may hold pre-handshake setup
     * resources (bounded event channel + reader job + setup coroutine)
     * concurrently. [handleIncoming] takes a permit with a non-suspending
     * `tryAcquire` — refusal closes the connection immediately, before any
     * per-connection resources are allocated — and the permit is released
     * exactly once when the handshake settles (success or failure; see
     * [setupSession]'s `onHandshakeSettled`). Outgoing connects are not
     * gated. See [MAX_CONCURRENT_PRE_HANDSHAKE_SETUPS].
     */
    private val preHandshakeGate = Semaphore(MAX_CONCURRENT_PRE_HANDSHAKE_SETUPS)

    /** A timed-out refresh retains this permit until its actual worker exits. */
    private val discoveryRefreshGate = Semaphore(1)

    /**
     * Initial incoming and outgoing setups are registered before their
     * handshake coroutine starts. Terminal shutdown seals this registry and
     * cancels its jobs while the transport is still open. This covers the
     * interval where the peer has completed HELLO but our side has not yet
     * published a [P2pSession], so the ordinary session store cannot own the
     * connection yet.
     */
    private val setupRegistry = MutableStateFlow(SessionSetupRegistry())

    /** Process-local suffix that keeps session ids unique even when the wall clock is fixed or coarse. */
    private val sessionSequence = MutableStateFlow(0L)

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
    private val authoritativePath = MutableStateFlow(
        AuthoritativePath(NetworkPathStatus.Unknown, generation = 0L)
    )

    fun startAcceptingIncoming(transports: List<DataTransport>) {
        for (transport in transports) {
            scope.launch { collectIncomingWithRecovery(transport) }
        }
    }

    private suspend fun collectIncomingWithRecovery(transport: DataTransport) {
        var consecutiveFailures = 0
        while (currentCoroutineContext().isActive) {
            var acceptedAny = false
            try {
                transport.incomingConnections().collect { connection ->
                    acceptedAny = true
                    consecutiveFailures = 0
                    handleIncoming(connection)
                }
                currentCoroutineContext().ensureActive()
                logger.warn("inbound acceptance completed unexpectedly for ${transport.type}")
            } catch (cancelled: CancellationException) {
                // A transport flow can throw CancellationException while this
                // collector's Job is still active. That is an SPI failure,
                // not structural cancellation; genuine scope cancellation is
                // rethrown by ensureActive().
                currentCoroutineContext().ensureActive()
                logger.warn("inbound acceptance ended for ${transport.type}", cancelled)
            } catch (failure: Throwable) {
                logger.warn("inbound acceptance ended for ${transport.type}", failure)
            }
            if (!acceptedAny) consecutiveFailures += 1
            val exponent = minOf(consecutiveFailures - 1, MAX_INCOMING_RECOLLECT_EXPONENT)
            val backoff = minOf(
                INCOMING_RECOLLECT_INITIAL_DELAY_MS shl exponent.coerceAtLeast(0),
                INCOMING_RECOLLECT_MAX_DELAY_MS
            )
            delay(backoff)
        }
    }

    suspend fun connect(
        peer: Peer,
        internalPeer: InternalPeer,
        expectedFingerprint: PeerFingerprint? = null,
        lifecycleGeneration: Long
    ): P2pSession {
        val effectiveFingerprint = resolveTrustedFingerprint(
            internalPeer = internalPeer,
            explicitFingerprint = expectedFingerprint
        )
        var mayRetryAfterDifferentAuthorization = effectiveFingerprint != null
        while (true) {
            if (!lifecycleGate.isActive(lifecycleGeneration)) {
                throw lifecycleStoppedFailure()
            }
            // Atomic decision delegated to the store: return an existing active
            // session, wait on someone else's in-flight connect, or become the
            // connector. The actual `await` / connect work runs OUTSIDE the
            // store's mutex (the decision is short-held, the work is not).
            when (val decision = store.startOrJoin(peer.id)) {
                is ConnectDecision.Existing ->
                    return decision.session
                        .requireFingerprint(effectiveFingerprint)
                        .requireActiveLifecycle(lifecycleGeneration)
                is ConnectDecision.JoinPending -> {
                    val joined = try {
                        decision.deferred.await()
                    } catch (cause: Throwable) {
                        // A concurrent unpinned/wrong-pinned attempt does not
                        // get to erase this caller's explicit authorization.
                        // performConnect removes the pending slot before it
                        // completes the deferred, so this one bounded retry
                        // cannot rejoin the failed attempt.
                        val authorizationSpecificFailure =
                            cause is P2pError.AuthorizationRejected ||
                                cause is P2pError.AuthenticatedIdentityMismatch
                        if (mayRetryAfterDifferentAuthorization && authorizationSpecificFailure) {
                            mayRetryAfterDifferentAuthorization = false
                            continue
                        }
                        throw cause
                    }
                    return joined
                        .requireFingerprint(effectiveFingerprint)
                        .requireActiveLifecycle(lifecycleGeneration)
                }
                is ConnectDecision.BecomeConnector ->
                    return performConnect(
                        peer = peer,
                        internalPeer = internalPeer,
                        expectedFingerprint = effectiveFingerprint,
                        deferred = decision.deferred,
                        lifecycleGeneration = lifecycleGeneration
                    )
            }
        }
    }

    @Suppress("DEPRECATION")
    private fun resolveTrustedFingerprint(
        internalPeer: InternalPeer,
        explicitFingerprint: PeerFingerprint?
    ): PeerFingerprint? {
        val applicationPin = (internalPeer.authenticationHint as?
            PeerAuthenticationHint.TrustedApplicationPin)?.fingerprint
        if (explicitFingerprint != null && applicationPin != null &&
            explicitFingerprint != applicationPin
        ) {
            throw P2pError.AuthenticatedIdentityMismatch(
                "The explicit fingerprint conflicts with the stored application pin"
            )
        }

        return when (securityMode) {
            is SecurityMode.AuthenticatedV2 -> {
                val resolved = explicitFingerprint ?: applicationPin
                if (internalPeer.origin == PeerOrigin.Manual && resolved == null) {
                    throw P2pError.SecurityConfigurationInvalid(
                        "Secure manual-IP connections require an out-of-band fingerprint"
                    )
                }
                resolved
            }
            SecurityMode.NoneForMvp -> {
                if (explicitFingerprint != null || applicationPin != null) {
                    throw P2pError.SecurityConfigurationInvalid(
                        "A fingerprint cannot be authenticated by legacy plaintext mode"
                    )
                }
                null
            }
        }
    }

    private fun P2pSession.requireFingerprint(
        expectedFingerprint: PeerFingerprint?
    ): P2pSession {
        if (expectedFingerprint != null && peerIdentity.fingerprint != expectedFingerprint) {
            throw P2pError.AuthenticatedIdentityMismatch(
                "The existing session has a different authenticated identity"
            )
        }
        return this
    }

    private suspend fun P2pSession.requireActiveLifecycle(
        lifecycleGeneration: Long
    ): P2pSession {
        if (!lifecycleGate.isActive(lifecycleGeneration)) {
            throw lifecycleStoppedFailure()
        }
        return this
    }

    private suspend fun performConnect(
        peer: Peer,
        internalPeer: InternalPeer,
        expectedFingerprint: PeerFingerprint?,
        deferred: CompletableDeferred<P2pSession>,
        lifecycleGeneration: Long
    ): P2pSession {
        var completedSession: P2pSession? = null
        var uncommittedConnection: RawConnection? = null
        var failure: Throwable? = null
        try {
            if (!lifecycleGate.isActive(lifecycleGeneration)) {
                throw lifecycleStoppedFailure()
            }
            val transport = transportManager.selectBestTransport(internalPeer)
            if (!lifecycleGate.isActive(lifecycleGeneration)) {
                throw lifecycleStoppedFailure()
            }
            val rawConnection = try {
                transport.connect(internalPeer)
            } catch (e: CancellationException) {
                throw e
            } catch (e: P2pError) {
                throw e
            } catch (e: Throwable) {
                throw P2pError.ConnectionFailed("Transport connect failed: ${e.message}").also {
                    it.underlying = e
                }
            }
            uncommittedConnection = rawConnection
            afterOutgoingConnectForTest?.invoke()
            currentCoroutineContext().ensureActive()
            if (!lifecycleGate.isActive(lifecycleGeneration)) {
                throw lifecycleStoppedFailure()
            }
            // setupSession owns rawConnection from this point and closes it
            // on every pre-registration failure/cancellation path.
            uncommittedConnection = null
            val session = try {
                runTrackedSessionSetup(rawConnection) {
                    setupSession(
                        rawConnection = rawConnection,
                        expectedPeer = peer,
                        expectedFingerprint = expectedFingerprint,
                        isIncoming = false,
                        internalPeerForReconnect = internalPeer,
                        isManualPeer = internalPeer.origin == PeerOrigin.Manual,
                        lifecycleGeneration = lifecycleGeneration
                    )
                }
            } catch (cancelled: CancellationException) {
                // Cancellation of the setup child by terminal kit shutdown is
                // a lifecycle failure for an otherwise-active application
                // caller. Preserve genuine caller cancellation unchanged.
                currentCoroutineContext().ensureActive()
                if (!lifecycleGate.isActive(lifecycleGeneration)) {
                    throw lifecycleStoppedFailure()
                }
                throw cancelled
            }
            if (!lifecycleGate.isActive(lifecycleGeneration)) {
                // The setup committed before stop() linearized, but delivery
                // lost the race. Never return a session terminal teardown has
                // already removed or closed.
                rollbackCommittedOutgoingSession(session.peer.id, session)
                throw lifecycleStoppedFailure()
            }
            completedSession = session
            return session
        } catch (e: Throwable) {
            failure = e
            throw e
        } finally {
            val connectionToClose = uncommittedConnection
            if (connectionToClose != null) {
                try {
                    closeUncommittedConnection(connectionToClose)
                } catch (cleanupFailure: Throwable) {
                    failure?.addSuppressed(cleanupFailure)
                        ?: logger.warn("Uncommitted outgoing connection cleanup failed", cleanupFailure)
                }
            }
            // Pending ownership must be removed even when this coroutine is
            // already cancelled. Complete waiters only after removal so a
            // pinned waiter can never observe and rejoin a stale attempt.
            withContext(NonCancellable) {
                try {
                    store.endPending(peer.id, deferred)
                } finally {
                    val cause = failure
                    if (cause == null) {
                        deferred.complete(checkNotNull(completedSession))
                    } else {
                        deferred.completeExceptionally(cause)
                    }
                }
            }
        }
    }

    @OptIn(DelicateCoroutinesApi::class, ExperimentalCoroutinesApi::class)
    private fun handleIncoming(connection: RawConnection) {
        // AUDIT-2026-07 (SEC-1, decision #9a): inbound admission control,
        // stage 1 — pre-handshake concurrency. Non-suspending tryAcquire so
        // the accept collector never parks: once
        // [MAX_CONCURRENT_PRE_HANDSHAKE_SETUPS] inbound setups are in flight
        // (e.g. many connections from a non-conforming device that never
        // complete HELLO), further inbound connections are refused — closed
        // immediately with a warn diagnostic, before any per-connection
        // resources (event channel, reader job) are allocated. A conforming
        // peer simply redials once capacity frees up.
        if (!preHandshakeGate.tryAcquire()) {
            logger.warn(
                "Inbound connection refused: pre-handshake setups at capacity " +
                    "($MAX_CONCURRENT_PRE_HANDSHAKE_SETUPS)"
            )
            // This cleanup must not inherit the kit Job: shutdown can
            // linearize between the capacity decision and launch. Use the
            // bounded independent owner so a just-refused socket always gets
            // a close attempt even when the kit scope is already cancelled.
            launchIndependentUncommittedConnectionCleanup(connection)
            return
        }
        beforeIncomingSetupLaunchForTest?.invoke()
        // ATOMIC guarantees this ownership body starts even when terminal
        // cancellation linearizes after admission but immediately before
        // launch. The first suspension may then deliver cancellation, and
        // runTrackedSessionSetup's unowned-raw fallback closes the socket.
        val launchBodyStarted = CompletableDeferred<Unit>()
        val setupLaunch = scope.launch(start = CoroutineStart.ATOMIC) {
            launchBodyStarted.complete(Unit)
            // Exactly-once permit release: [setupSession] invokes
            // onHandshakeSettled from a `finally` around the handshake, so
            // BOTH outcomes — success and every failure path (setup timeout,
            // handshake rejection, connection loss, cancellation) — release
            // the permit. The outer `finally` below is a safety net for the
            // theoretical window where this coroutine is torn down before
            // [setupSession] runs; both call sites execute sequentially on
            // this coroutine, so the plain [released] flag is race-free.
            var released = false
            val releaseOnce: () -> Unit = {
                if (!released) {
                    released = true
                    preHandshakeGate.release()
                }
            }
            try {
                runTrackedSessionSetup(connection) {
                    setupSession(
                        rawConnection = connection,
                        expectedPeer = null,
                        expectedFingerprint = null,
                        isIncoming = true,
                        internalPeerForReconnect = null,
                        isManualPeer = false,
                        lifecycleGeneration = null,
                        onHandshakeSettled = releaseOnce
                    )
                }
            } catch (e: CancellationException) {
                throw e
            } catch (e: Throwable) {
                logger.warn("Incoming session setup failed", e)
                closeUncommittedConnection(connection)
            } finally {
                releaseOnce()
            }
        }
        setupLaunch.invokeOnCompletion {
            // A parent cancelled before this ATOMIC child reached its body
            // never entered runTrackedSessionSetup and therefore never
            // transferred raw ownership to the setup registry. Completion
            // callbacks are non-suspending, so hand that sole remaining
            // cleanup obligation to a detached, bounded worker.
            if (!launchBodyStarted.isCompleted) {
                preHandshakeGate.release()
                launchIndependentUncommittedConnectionCleanup(connection)
            }
        }
    }

    @OptIn(DelicateCoroutinesApi::class, ExperimentalCoroutinesApi::class)
    private fun launchIndependentUncommittedConnectionCleanup(connection: RawConnection) {
        val owner = SupervisorJob()
        val cleanupJob = CoroutineScope(owner + Dispatchers.Default).launch(
            start = CoroutineStart.ATOMIC
        ) {
            closeUncommittedConnection(connection)
        }
        cleanupJob.invokeOnCompletion { owner.cancel() }
    }

    /**
     * Run one initial session setup in its own cancellable child and publish
     * that child to [setupRegistry] before it starts. The separate child lets
     * kit shutdown cancel only the setup transaction (not an application's
     * entire calling coroutine for an outgoing `connect`) and gives
     * [cleanupHandshake] a chance to send CLOSE before transport teardown.
     */
    private suspend fun runTrackedSessionSetup(
        rawConnection: RawConnection,
        block: suspend () -> SessionSetupResult
    ): P2pSession {
        val delivery = MutableStateFlow<SessionSetupDelivery>(SessionSetupDelivery.Pending)
        // The caller owns the raw connection until the setup registry has
        // accepted an ActiveSessionSetup (or the rejected-registration path
        // has closed it itself). In particular, a cancelled parent can reach
        // the first coroutineScope boundary before its block creates the lazy
        // setup child. That boundary used to leave no registry entry, no
        // setup child, and therefore no cleanup owner for the accepted socket
        // on Kotlin/Native.
        var setupOwnsRawConnection = false
        return try {
            val result = coroutineScope {
                val bodyStarted = CompletableDeferred<Unit>()
                val setupJob = async(start = CoroutineStart.LAZY) {
                    bodyStarted.complete(Unit)
                    val producedResult = block()
                    val produced = SessionSetupDelivery.Produced(producedResult)
                    check(delivery.compareAndSet(SessionSetupDelivery.Pending, produced)) {
                        "session setup result ownership was already settled"
                    }
                    producedResult
                }
                val setup = ActiveSessionSetup(setupJob, rawConnection, bodyStarted)
                setupJob.invokeOnCompletion { unregisterSessionSetup(setup) }

                if (!registerSessionSetup(setup)) {
                    setupJob.cancel(CancellationException("P2pKit stopped before session setup started"))
                    withContext(NonCancellable) { closeUncommittedConnection(rawConnection) }
                    setupOwnsRawConnection = true
                    throw lifecycleStoppedFailure()
                }
                // There is no suspension between successful registration and
                // this hand-off. From here, either the setup body owns cleanup
                // or the await failure path below closes a child that never
                // started.
                setupOwnsRawConnection = true

                setupJob.start()
                try {
                    setupJob.await()
                } catch (failure: Throwable) {
                    setupJob.cancel()
                    withContext(NonCancellable) {
                        setupJob.join()
                        if (!bodyStarted.isCompleted) {
                            closeUncommittedConnection(rawConnection)
                        }
                    }
                    throw failure
                }
            }

            // Claim only after coroutineScope has completed its own
            // cancellation/child-settlement boundary. From the successful CAS
            // to the function return there is no suspension point, so a caller
            // either receives the session or the catch below rolls it back.
            afterSessionSetupResultForTest?.invoke()
            currentCoroutineContext().ensureActive()
            val produced = delivery.value as? SessionSetupDelivery.Produced
                ?: error("session setup completed without a produced result")
            check(
                produced.result === result &&
                    delivery.compareAndSet(produced, SessionSetupDelivery.Claimed)
            ) {
                "session setup result was not available for delivery"
            }
            result.session
        } catch (failure: Throwable) {
            withContext(NonCancellable) {
                if (!setupOwnsRawConnection) {
                    closeUncommittedConnection(rawConnection)
                }
                val produced = delivery.value as? SessionSetupDelivery.Produced
                if (produced != null && delivery.compareAndSet(
                        produced,
                        SessionSetupDelivery.Abandoned
                    )
                ) {
                    produced.result.rollbackIfUndelivered?.invoke()
                }
            }
            throw failure
        }
    }

    private fun registerSessionSetup(setup: ActiveSessionSetup): Boolean {
        while (true) {
            val current = setupRegistry.value
            if (!current.accepting) return false
            val updated = current.copy(active = current.active + setup)
            if (setupRegistry.compareAndSet(current, updated)) return true
        }
    }

    private fun unregisterSessionSetup(setup: ActiveSessionSetup) {
        while (true) {
            val current = setupRegistry.value
            if (setup !in current.active) return
            val updated = current.copy(active = current.active - setup)
            if (setupRegistry.compareAndSet(current, updated)) return
        }
    }

    /** Atomically refuse future setups and return every setup already owned. */
    private fun sealSessionSetups(): Set<ActiveSessionSetup> {
        while (true) {
            val current = setupRegistry.value
            val sealed = if (current.accepting) current.copy(accepting = false) else current
            if (sealed === current || setupRegistry.compareAndSet(current, sealed)) {
                return sealed.active
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
        expectedFingerprint: PeerFingerprint?,
        isIncoming: Boolean,
        internalPeerForReconnect: InternalPeer?,
        isManualPeer: Boolean = false,
        lifecycleGeneration: Long?,
        /**
         * AUDIT-2026-07 (SEC-1): invoked exactly once, from the `finally`
         * below, the moment the handshake settles — on success AND on every
         * failure path. [handleIncoming] passes its pre-handshake permit
         * release here so admission capacity is returned as soon as the
         * connection graduates from (or fails) the handshake, rather than
         * being held through registration and the incoming-sessions emit.
         */
        onHandshakeSettled: (() -> Unit)? = null
    ): SessionSetupResult {
        val handshake = try {
            runHandshake(
                rawConnection = rawConnection,
                expectedPeer = expectedPeer,
                expectedFingerprint = expectedFingerprint,
                isManualPeer = isManualPeer,
                isIncoming = isIncoming
            )
        } finally {
            onHandshakeSettled?.invoke()
        }

        val session = P2pSessionImpl(
            id = nextSessionId(isIncoming, handshake.resolvedPeer.id),
            peer = handshake.resolvedPeer,
            peerIdentity = handshake.peerIdentity,
            initialConnection = handshake.secureConnection,
            initialEvents = handshake.events,
            initialReaderJob = handshake.readerJob,
            initialProtocolState = handshake.protocolState,
            protocol = protocol,
            parentScope = scope,
            keepAlive = keepAlive,
            clock = clock,
            monotonicClock = monotonicClock,
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
                    expectedIdentity = handshake.peerIdentity,
                    originalInternalPeer = internalPeerForReconnect,
                    policy = policy
                )
            }
        }

        var sessionOwnershipTransferred = false
        var committedOutgoingSession: P2pSession? = null
        try {
            session.start()
            currentCoroutineContext().ensureActive()
            beforeSessionCommitForTest?.invoke()
            currentCoroutineContext().ensureActive()
            val committed = lifecycleGate.commit(lifecycleGeneration) {
                val outcome = registerSession(
                    handshake.resolvedPeer.id,
                    session,
                    isIncoming = isIncoming
                )
                if (outcome is RegisterOutcome.Accepted || outcome is RegisterOutcome.Replaced) {
                    session.markRegistrationCommitted()
                }

                // Outgoing callers receive the winner via performConnect's deferred
                // so a rejected new session never leaks back to app code as a
                // "live" session. Incoming subscribers only see sessions admitted
                // by the same atomic lifecycle commit as the public sessions flow.
                val resultSession = when (outcome) {
                    is RegisterOutcome.Accepted -> outcome.session
                    is RegisterOutcome.Replaced -> outcome.winner
                    is RegisterOutcome.Rejected -> outcome.winner
                    is RegisterOutcome.RefusedAtCapacity -> outcome.session
                }
                val published = if (isIncoming &&
                    (outcome is RegisterOutcome.Accepted || outcome is RegisterOutcome.Replaced)
                ) {
                    _incomingSessions.tryEmit(resultSession)
                } else {
                    true
                }
                CommittedSession(resultSession, published, outcome)
            }
            if (committed == null) throw lifecycleStoppedFailure()
            val outcome = committed.outcome
            sessionOwnershipTransferred = when (outcome) {
                is RegisterOutcome.Accepted,
                is RegisterOutcome.Replaced -> true
                is RegisterOutcome.Rejected,
                is RegisterOutcome.RefusedAtCapacity -> false
            }
            if (!isIncoming && sessionOwnershipTransferred) {
                committedOutgoingSession = committed.resultSession
            }

            // A replaced session is no longer reachable through SessionStore,
            // so close it here under the setup transaction's non-cancellable,
            // bounded ownership instead of relying on an untracked scope.launch
            // that terminal kit shutdown can cancel before it starts.
            if (outcome is RegisterOutcome.Replaced) {
                closeDetachedSession(outcome.loser)
            }
            if (!committed.published) {
                withContext(NonCancellable) {
                    store.removeIfMatches(handshake.resolvedPeer.id, committed.resultSession)
                    closeDetachedSession(committed.resultSession)
                }
                throw P2pError.ConnectionFailed(
                    "Incoming session publication capacity was exhausted"
                )
            }
            if (outcome !is RegisterOutcome.RefusedAtCapacity) {
                applyAuthoritativePathAfterRegistration(committed.resultSession)
            }
            val rollback = committedOutgoingSession?.let { committedSession ->
                suspend {
                    rollbackCommittedOutgoingSession(
                        handshake.resolvedPeer.id,
                        committedSession
                    )
                }
            }
            return SessionSetupResult(committed.resultSession, rollback)
        } catch (failure: Throwable) {
            committedOutgoingSession?.let { committedSession ->
                committedOutgoingSession = null
                rollbackCommittedOutgoingSession(handshake.resolvedPeer.id, committedSession)
            }
            throw failure
        } finally {
            if (!sessionOwnershipTransferred) closeDetachedSession(session)
        }
    }

    private suspend fun rollbackCommittedOutgoingSession(
        peerId: PeerId,
        session: P2pSession
    ) {
        withContext(NonCancellable) {
            store.removeIfMatches(peerId, session)
            closeDetachedSession(session)
        }
    }

    private suspend fun closeDetachedSession(session: P2pSession) {
        withContext(NonCancellable) {
            // HELLO has completed by the time a session exists. This covers a
            // rejected candidate, a capacity refusal, and a previously
            // published loser that arbitration just detached from the store.
            // Close it with the normal protocol-level CLOSE transaction rather
            // than exposing a reconnectable EOF. The independent cleanup owner
            // is required because P2pSession.close deliberately finishes in
            // NonCancellable; a structured withTimeout cannot bound such a child.
            captureCleanupIssue(
                resource = "detached session ${session.id}",
                // P2pSession.close has several independently bounded phases;
                // use the established whole-session bound rather than timing
                // out at the first phase boundary and orphaning healthy cleanup.
                timeoutMillis = SESSION_CLOSE_TIMEOUT_MS,
                preserveCancellation = false
            ) {
                session.close()
            }?.let { issue ->
                logCleanupIssues(logger, "detached session cleanup", listOf(issue))
            }
        }
    }

    private suspend fun closeUncommittedConnection(connection: RawConnection) {
        withContext(NonCancellable) {
            captureCleanupIssue(
                resource = "uncommitted raw connection",
                timeoutMillis = SESSION_COMMIT_CLEANUP_TIMEOUT_MS,
                preserveCancellation = false
            ) {
                connection.close()
            }?.let { issue ->
                logCleanupIssues(logger, "uncommitted connection cleanup", listOf(issue))
            }
        }
    }

    private fun lifecycleStoppedFailure(): IllegalStateException =
        IllegalStateException("P2pKit stopped before the session could be committed")

    private data class CommittedSession(
        val resultSession: P2pSession,
        val published: Boolean,
        val outcome: RegisterOutcome
    )

    private fun nextSessionId(isIncoming: Boolean, peerId: PeerId): String {
        while (true) {
            val current = sessionSequence.value
            val next = if (current == Long.MAX_VALUE) Long.MIN_VALUE else current + 1L
            if (sessionSequence.compareAndSet(current, next)) {
                return "${if (isIncoming) "in" else "out"}-${peerId.value}-${clock()}-$next"
            }
        }
    }

    /**
     * Establishes the whole-kit security profile and then performs HELLO over
     * that stream. The sole protocol reader is deliberately created only after
     * authenticated v2 succeeds; it can never consume or bypass raw Noise
     * bytes. One deadline covers preface, Noise, encrypted HELLO, validation,
     * and publication inputs.
     */
    @Suppress("DEPRECATION")
    private suspend fun runHandshake(
        rawConnection: RawConnection,
        expectedPeer: Peer?,
        expectedFingerprint: PeerFingerprint?,
        isManualPeer: Boolean,
        isIncoming: Boolean
    ): HandshakeOutputs {
        var selectedConnection: RawConnection? = null
        var eventChannel: Channel<ProtocolEvent>? = null
        var readerJob: Job? = null

        try {
            return withTimeout(setupTimeoutMillis) {
                val protocolVersion: Byte
                val peerIdentityBeforeHello: PeerIdentity?
                selectedConnection = when (val mode = securityMode) {
                    is SecurityMode.AuthenticatedV2 -> {
                        protocolVersion = ProtocolConstants.SECURE_VERSION
                        val identity = checkNotNull(localSecureIdentity) {
                            "Authenticated v2 requires a loaded local identity"
                        }
                        val engine = checkNotNull(authenticatedSecurity) {
                            "Authenticated v2 requires the built-in security engine"
                        }
                        engine.establish(
                            rawConnection = rawConnection,
                            parentScope = scope,
                            role = if (isIncoming) NoiseRole.Responder else NoiseRole.Initiator,
                            appId = localAppId,
                            localIdentity = identity,
                            authorization = mode.authorization,
                            expectedPeerId = expectedPeer?.id,
                            expectedFingerprint = expectedFingerprint
                        ).also { secure ->
                            peerIdentityBeforeHello = secure.peerIdentity
                        }
                    }
                    SecurityMode.NoneForMvp -> {
                        protocolVersion = ProtocolConstants.LEGACY_VERSION
                        peerIdentityBeforeHello = null
                        rawConnection
                    }
                }

                // Bounded protocol queue. In secure mode this is the first and
                // only reader ever created above the raw transport pump.
                val channel = Channel<ProtocolEvent>(capacity = 256)
                eventChannel = channel
                val connection = checkNotNull(selectedConnection)
                val protocolState = ProtocolSessionState(
                    localPeerId = localPeerId.value,
                    secure = securityMode is SecurityMode.AuthenticatedV2
                )
                val launchedReader = scope.launch {
                    try {
                        protocol.events(connection, protocolState).collect { event -> channel.send(event) }
                        channel.close()
                    } catch (e: CancellationException) {
                        channel.close()
                        throw e
                    } catch (e: Throwable) {
                        channel.close(e)
                    }
                }
                readerJob = launchedReader

                val peerHello = performHandshake(
                    protocol = protocol,
                    connection = connection,
                    events = channel,
                    localAppId = localAppId,
                    localPeerId = localPeerId,
                    localDeviceName = localDeviceName,
                    localPlatform = localPlatform,
                    localTransports = localTransports,
                    protocolState = protocolState,
                    protocolVersion = protocolVersion,
                    handshakeTimeoutMillis = setupTimeoutMillis
                )

                val peerIdentity = when (securityMode) {
                    is SecurityMode.AuthenticatedV2 -> {
                        val authenticated = checkNotNull(peerIdentityBeforeHello)
                        if (peerHello.peerId != authenticated.peerId.value) {
                            sendHandshakeErrorBestEffort(connection, "authenticated identity mismatch")
                            throw P2pError.AuthenticatedIdentityMismatch(
                                "Encrypted HELLO did not match the authenticated key-derived identity"
                            )
                        }
                        authenticated
                    }
                    SecurityMode.NoneForMvp -> PeerIdentity(PeerId(peerHello.peerId), null)
                }

                if (peerIdentity.peerId == localPeerId) {
                    sendHandshakeErrorBestEffort(connection, "peer identity collision with local")
                    throw if (securityMode is SecurityMode.AuthenticatedV2) {
                        P2pError.AuthenticatedIdentityMismatch(
                            "Remote authenticated as the local identity"
                        )
                    } else {
                        P2pError.HandshakeRejected("Remote HELLO claims our own peerId")
                    }
                }

                val helloPeer = peerHello.toPeer()
                val resolvedPeer = when (securityMode) {
                    is SecurityMode.AuthenticatedV2 -> helloPeer.copy(id = peerIdentity.peerId)
                    SecurityMode.NoneForMvp -> {
                        if (expectedPeer != null && !isManualPeer &&
                            peerHello.peerId != expectedPeer.id.value
                        ) {
                            sendHandshakeErrorBestEffort(connection, "peerId mismatch")
                            throw P2pError.HandshakeRejected(
                                "Remote HELLO peerId mismatch for the selected peer"
                            )
                        }
                        if (expectedPeer == null) helloPeer else expectedPeer
                    }
                }

                HandshakeOutputs(
                    secureConnection = connection,
                    events = channel,
                    readerJob = launchedReader,
                    resolvedPeer = resolvedPeer,
                    peerIdentity = peerIdentity,
                    protocolState = protocolState
                )
            }
        } catch (e: TimeoutCancellationException) {
            // Nested withTimeout calls reuse TimeoutCancellationException for
            // both their own deadline and a cancelled caller's deadline. If
            // our parent context is no longer active, the caller owns this
            // cancellation; preserve it instead of reporting a false
            // authentication/HELLO timeout. Cleanup still owns the raw stream
            // and gets the same bounded clean-close opportunity as any other
            // caller cancellation.
            if (!currentCoroutineContext().isActive) {
                cleanupHandshake(
                    rawConnection,
                    selectedConnection,
                    readerJob,
                    sendCleanClose = true
                )?.let(e::addSuppressed)
                throw e
            }
            cleanupHandshake(rawConnection, selectedConnection, readerJob)?.let(e::addSuppressed)
            throw if (securityMode is SecurityMode.AuthenticatedV2) {
                P2pError.AuthenticationFailed(
                    "Authenticated protocol v2 setup timed out after $setupTimeoutMillis ms"
                ).also { it.underlying = e }
            } else {
                P2pError.HandshakeRejected(
                    "Plaintext HELLO timed out after $setupTimeoutMillis ms"
                )
            }
        } catch (e: CancellationException) {
            cleanupHandshake(
                rawConnection,
                selectedConnection,
                readerJob,
                sendCleanClose = true
            )?.let(e::addSuppressed)
            throw e
        } catch (e: P2pError) {
            cleanupHandshake(rawConnection, selectedConnection, readerJob)?.let(e::addSuppressed)
            throw e
        } catch (e: Throwable) {
            cleanupHandshake(rawConnection, selectedConnection, readerJob)?.let(e::addSuppressed)
            throw if (securityMode is SecurityMode.AuthenticatedV2) {
                P2pError.AuthenticationFailed(
                    "Authenticated protocol v2 setup failed"
                ).also { it.underlying = e }
            } else {
                P2pError.ConnectionFailed("Plaintext HELLO failed: ${e.message}").also {
                    it.underlying = e
                }
            }
        }
    }

    private suspend fun cleanupHandshake(
        rawConnection: RawConnection,
        selectedConnection: RawConnection?,
        readerJob: Job?,
        sendCleanClose: Boolean = false
    ): Throwable? = withContext(NonCancellable) {
        val issues = mutableListOf<CleanupIssue>()
        // Before a secure stream is returned, AuthenticatedV2SecurityEngine
        // exclusively owns and closes rawConnection on every failure. Closing
        // it again here would violate close-once transport contracts.
        val connectionToClose = selectedConnection ?: rawConnection.takeIf {
            securityMode !is SecurityMode.AuthenticatedV2
        }
        // Targeted setup cancellation happens while the transport is still
        // open. Keep the reader alive until CLOSE has had its bounded send
        // opportunity: cancelling an Apple receive first calls
        // nw_connection_cancel and makes the clean frame impossible.
        val closeSend = if (sendCleanClose && selectedConnection != null) {
            CoroutineScope(currentCoroutineContext()).launch(start = CoroutineStart.UNDISPATCHED) {
                runCatching { protocol.sendClose(selectedConnection) }
            }.also { job ->
                withTimeoutOrNull(HANDSHAKE_CLEANUP_TIMEOUT_MS) { job.join() }
            }
        } else {
            null
        }
        readerJob?.cancel()
        if (connectionToClose != null) {
            captureCleanupIssue(
                resource = "handshake connection",
                timeoutMillis = HANDSHAKE_CLEANUP_TIMEOUT_MS,
                preserveCancellation = false
            ) {
                connectionToClose.close()
            }?.let(issues::add)
        }
        closeSend?.cancel()
        closeSend?.let { sender ->
            captureCleanupIssue(
                resource = "handshake CLOSE sender",
                timeoutMillis = HANDSHAKE_CLEANUP_TIMEOUT_MS,
                preserveCancellation = false
            ) {
                sender.join()
            }?.let(issues::add)
        }
        readerJob?.let { reader ->
            captureCleanupIssue(
                resource = "handshake protocol reader",
                timeoutMillis = HANDSHAKE_CLEANUP_TIMEOUT_MS,
                preserveCancellation = false
            ) {
                reader.join()
            }?.let(issues::add)
        }
        issues.takeIf { it.isNotEmpty() }?.let {
            CleanupAggregateException("handshake cleanup", it.toList())
        }
    }

    private suspend fun sendHandshakeErrorBestEffort(connection: RawConnection, reason: String) {
        try {
            protocol.sendError(connection, reason)
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (failure: Throwable) {
            logger.debug(
                "Unable to send handshake rejection to peer: " +
                    "${failure::class.simpleName}: ${failure.message ?: ""}"
            )
        }
    }

    private data class HandshakeOutputs(
        val secureConnection: RawConnection,
        val events: ReceiveChannel<ProtocolEvent>,
        val readerJob: Job,
        val resolvedPeer: Peer,
        val peerIdentity: PeerIdentity,
        val protocolState: ProtocolSessionState
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
        private val expectedIdentity: PeerIdentity,
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
            runDiscoveryRefresh(peerShort, "initial")

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
            val periodicRefreshJob = launchPeriodicRefresh(
                ownerScope = CoroutineScope(currentCoroutineContext()),
                session = session,
                peerShort = peerShort
            )
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
                        // Provenance is a property of how the session's dialed
                        // identity was minted, fixed at connect time — reuse
                        // the original InternalPeer's origin so a manual
                        // session's re-handshake keeps the mismatch exemption
                        // (the remote's HELLO can never equal the synthetic id).
                        runHandshake(
                            rawConnection = raw,
                            expectedPeer = expectedPeer,
                            // Every reconnect is pinned to the key authenticated
                            // by the first session, even under AcceptAny.
                            expectedFingerprint = expectedIdentity.fingerprint,
                            isManualPeer = originalInternalPeer.origin == PeerOrigin.Manual,
                            isIncoming = false
                        )
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
                        cleanupUnusedReconnectHandshake(
                            handshake,
                            "session left Reconnecting before rearm"
                        )
                        return
                    }

                    val rearmed = try {
                        session.rearmWith(
                            handshake.secureConnection,
                            handshake.events,
                            handshake.protocolState,
                            handshake.readerJob
                        )
                    } catch (cancelled: CancellationException) {
                        throw cancelled
                    } catch (failure: Throwable) {
                        logger.warn(
                            "reconnect: attempt=$attempt/${policy.maxAttempts} peer=$peerShort " +
                                "name=${expectedPeer.name} REARM_FAILED " +
                                "reason=${failure::class.simpleName}: ${failure.message ?: ""}"
                        )
                        if (session.state.value != ConnectionState.Reconnecting) return
                        continue
                    }
                    if (!rearmed) {
                        logger.info(
                            "reconnect: attempt=$attempt/${policy.maxAttempts} peer=$peerShort " +
                                "name=${expectedPeer.name} DISCARDED sessionState=${session.state.value}"
                        )
                        return
                    }
                    logger.info(
                        "reconnect: attempt=$attempt/${policy.maxAttempts} peer=$peerShort " +
                            "name=${expectedPeer.name} SUCCEEDED dialed=$dialedStr source=$source"
                    )
                    return
                }
                session.markFailedAfterExhaustion()
            } finally {
                withContext(NonCancellable) {
                    periodicRefreshJob.cancelAndJoin()
                }
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
         * Launched as a child of the reconnect handler. This makes the refresh
         * loop part of the session's structured lifetime; the outer `finally`
         * cancels and joins it before the handler can finish.
         */
        private fun launchPeriodicRefresh(
            ownerScope: CoroutineScope,
            session: P2pSessionImpl,
            peerShort: String
        ): Job {
            val periodMs = 3000L
            val jitterMs = 400L
            return ownerScope.launch {
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
                        runDiscoveryRefresh(peerShort, "periodic tick=$tick")
                    }
                } finally {
                    logger.info(
                        "reconnect: periodic refresh stopped peer=$peerShort " +
                            "name=${expectedPeer.name} ticks=$tick reason=$stopReason"
                    )
                }
            }
        }

        /**
         * Executes an application/transport-controlled refresh behind an
         * independent deadline. A callback that ignores cancellation may
         * retain one worker, but [discoveryRefreshGate] prevents repeated
         * reconnect ticks from accumulating detached refresh operations.
         */
        private suspend fun runDiscoveryRefresh(peerShort: String, phase: String) {
            when (
                val result = runBoundedIndependentOperation(
                    timeoutMillis = discoveryRefreshTimeoutMillis,
                    // A transport callback can throw CancellationException
                    // without cancelling this reconnect job. Treat that as a
                    // refresh failure; genuine caller cancellation is still
                    // detected from the awaiting coroutine's inactive Job.
                    preserveCancellation = false,
                    operationGate = discoveryRefreshGate,
                    operation = refreshDiscovery
                )
            ) {
                is BoundedOperationResult.Success -> logger.info(
                    "reconnect: refresh complete phase=$phase peer=$peerShort " +
                        "name=${expectedPeer.name}"
                )
                is BoundedOperationResult.Failure -> logger.warn(
                    "reconnect: refresh failed phase=$phase peer=$peerShort " +
                        "name=${expectedPeer.name} reason=${result.cause::class.simpleName}: " +
                        (result.cause.message ?: "")
                )
                is BoundedOperationResult.TimedOut -> logger.warn(
                    "reconnect: refresh timed out phase=$phase peer=$peerShort " +
                        "name=${expectedPeer.name} timeoutMs=${result.timeoutMillis}"
                )
            }
        }

        private suspend fun cleanupUnusedReconnectHandshake(
            handshake: HandshakeOutputs,
            reason: String
        ) {
            withContext(NonCancellable) {
                handshake.readerJob.cancel()
                val issues = mutableListOf<CleanupIssue>()
                captureCleanupIssue(
                    resource = "unused reconnect connection ($reason)",
                    timeoutMillis = HANDSHAKE_CLEANUP_TIMEOUT_MS,
                    preserveCancellation = false
                ) {
                    handshake.secureConnection.close()
                }?.let(issues::add)
                captureCleanupIssue(
                    resource = "unused reconnect reader ($reason)",
                    timeoutMillis = HANDSHAKE_CLEANUP_TIMEOUT_MS,
                    preserveCancellation = false
                ) {
                    handshake.readerJob.join()
                }?.let(issues::add)
                logCleanupIssues(logger, "reconnect cleanup", issues)
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
     * `P2pKit.sessions`" honest, both sides apply the same deterministic
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
     * `P2pKit.incomingSessions` for accepted inbound sessions).
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
            }
            is RegisterOutcome.Rejected -> {
                logger.info(
                    "Simultaneous-open for peer ${peerId.value.take(8)}: " +
                        "rejecting new ${if (isIncoming) "incoming" else "outgoing"} session, " +
                        "existing wins"
                )
            }
            is RegisterOutcome.RefusedAtCapacity -> {
                // AUDIT-2026-07 (SEC-1, decision #9a): inbound admission
                // control, stage 2 — total-session bound. A net-new inbound
                // session past [MAX_TOTAL_ACTIVE_SESSIONS] is refused: warn
                // and close it cleanly (CLOSE frame, so the remote observes
                // an orderly shutdown, never a retry-provoking failure).
                // Refusal is a returned outcome + close, never an exception
                // into the accept collector. Outgoing registrations and
                // simultaneous-open arbitration (no net session growth) are
                // exempt — see [SessionStore.tryRegister].
                logger.warn(
                    "Inbound session refused for peer ${peerId.value.take(8)}: " +
                        "total active sessions at capacity ($MAX_TOTAL_ACTIVE_SESSIONS)"
                )
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
            // P2pSessionImpl publishes its terminal state before the bounded
            // resource transaction finishes so close/loss races classify
            // deterministically. Keep SessionStore ownership until that runtime
            // actually terminates; otherwise an in-flight event can look like a
            // zombie solely because the watcher evicted the session first.
            if (session is P2pSessionImpl) {
                val terminated = withTimeoutOrNull(SESSION_CLOSE_TIMEOUT_MS) {
                    session.awaitRuntimeTermination()
                    true
                } ?: false
                if (!terminated) {
                    logger.warn(
                        "Session ${session.id} runtime did not terminate within " +
                            "$SESSION_CLOSE_TIMEOUT_MS ms before store eviction"
                    )
                }
            }
            beforeTerminalWatcherRemovalForTest?.invoke()
            store.removeIfMatches(peerId, session)
        }
    }

    suspend fun closeAllSessions() {
        val snapshot = store.activeSnapshot()
        val issues = closeSessionSnapshot(snapshot, preserveCancellation = true)
        if (issues.isNotEmpty()) {
            logCleanupIssues(logger, "session close", issues)
            throw cleanupError("session close", issues)
        }
    }

    /** Terminal kit shutdown: detach public state before watcher scope cancellation. */
    suspend fun shutdownAllSessions(): List<CleanupIssue> {
        // Seal and cancel setup transactions before any DataTransport is
        // closed. A setup is not present in SessionStore until after HELLO,
        // but its peer may already have published a session and therefore
        // requires a protocol CLOSE rather than a reconnectable EOF.
        val activeSetups = sealSessionSetups()
        val setupIssues = cancelSessionSetupSnapshot(activeSetups)
        val snapshot = store.drainForShutdown()
        snapshot.pending.forEach { pending ->
            pending.completeExceptionally(lifecycleStoppedFailure())
        }
        val issues = setupIssues + closeSessionSnapshot(
            snapshot.sessions,
            preserveCancellation = false
        )
        logCleanupIssues(logger, "session shutdown", issues)
        return issues
    }

    private suspend fun cancelSessionSetupSnapshot(
        setups: Set<ActiveSessionSetup>
    ): List<CleanupIssue> = coroutineScope {
        setups.mapIndexed { index, setup ->
            async {
                setup.job.cancel(CancellationException("P2pKit stopped during session setup"))
                captureCleanupIssue(
                    resource = "session setup ${index + 1}",
                    timeoutMillis = SESSION_CLOSE_TIMEOUT_MS,
                    preserveCancellation = false
                ) {
                    setup.job.join()
                    // A lazily-created setup cancelled before its body began
                    // never acquired protocol ownership, so close its raw
                    // connection here. Started bodies own cleanup themselves
                    // (including the bounded CLOSE send) and must not be
                    // double-closed through a secure wrapper.
                    if (!setup.bodyStarted.isCompleted) {
                        setup.rawConnection.close()
                    }
                }
            }
        }.awaitAll().filterNotNull()
    }

    private suspend fun closeSessionSnapshot(
        sessions: List<P2pSession>,
        preserveCancellation: Boolean
    ): List<CleanupIssue> = coroutineScope {
        sessions.map { session ->
            async {
                captureCleanupIssue(
                    resource = "session ${session.id}",
                    timeoutMillis = SESSION_CLOSE_TIMEOUT_MS,
                    preserveCancellation = preserveCancellation
                ) {
                    session.close()
                }
            }
        }.awaitAll().filterNotNull()
    }

    private suspend fun applyAuthoritativePathAfterRegistration(session: P2pSession) {
        withContext(NonCancellable) {
            val observed = authoritativePath.value
            if (observed.status == NetworkPathStatus.Unsatisfied &&
                authoritativePath.value == observed
            ) {
                (session as? P2pSessionImpl)?.notifyPathLost()
            }
        }
    }

    /**
     * Handle a host-network path-status change. Called by [P2pKitImpl] which
     * subscribes to the kit's `NetworkPathObserver` once at startup.
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
     *   not "no network" — matches the no-op network-path observer default
     *   on platforms with no observer wired up.
     */
    fun applyPathChange(status: NetworkPathStatus) {
        val authority = publishAuthoritativePath(status)
        when (status) {
            NetworkPathStatus.Unsatisfied -> {
                scope.launch {
                    val toNotify = store.activeSnapshot()
                    for (s in toNotify) {
                        if (authoritativePath.value != authority) return@launch
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

    private fun publishAuthoritativePath(status: NetworkPathStatus): AuthoritativePath {
        while (true) {
            val previous = authoritativePath.value
            val next = AuthoritativePath(status, previous.generation + 1L)
            if (authoritativePath.compareAndSet(previous, next)) return next
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

/**
 * AUDIT-2026-07 (SEC-1, decision #9a): maximum number of inbound connections
 * allowed to hold pre-handshake setup resources (bounded event channel +
 * reader job + setup coroutine) concurrently. The 10 s handshake timeout
 * bounds each individual setup's duration; this bounds their NUMBER, so
 * malformed or excessive peer input (many connections that never complete
 * HELLO) cannot drive unbounded fd/coroutine/heap growth. Connections past
 * the bound are refused (closed + warn) before anything is allocated.
 *
 * Internal admission-control POLICY, not public API: the value may be tuned
 * (or surfaced as configuration) in a later release without breaking anyone.
 * A conforming mesh keeps handshakes sub-second, so 16 concurrent setups is
 * ample headroom.
 */
internal const val MAX_CONCURRENT_PRE_HANDSHAKE_SETUPS: Int = 16

/** Per-resource bound used only while rolling back an incomplete handshake. */
internal const val HANDSHAKE_CLEANUP_TIMEOUT_MS: Long = 2_000

/** Per-raw-connection bound used while rolling back an incomplete session commit. */
internal const val SESSION_COMMIT_CLEANUP_TIMEOUT_MS: Long = 2_000

/** Bounds a discovery refresh callback without constraining reconnect itself. */
internal const val DEFAULT_DISCOVERY_REFRESH_TIMEOUT_MS: Long = 6_000

/** Per-session close bound used by background and terminal cleanup. */
internal const val SESSION_CLOSE_TIMEOUT_MS: Long = 10_000

/** Initial and maximum delays for recovering a transient incoming-flow failure. */
internal const val INCOMING_RECOLLECT_INITIAL_DELAY_MS: Long = 100
internal const val INCOMING_RECOLLECT_MAX_DELAY_MS: Long = 5_000
internal const val MAX_INCOMING_RECOLLECT_EXPONENT: Int = 6

private data class ActiveSessionSetup(
    val job: Job,
    val rawConnection: RawConnection,
    val bodyStarted: CompletableDeferred<Unit>
)

private class SessionSetupResult(
    val session: P2pSession,
    val rollbackIfUndelivered: (suspend () -> Unit)?
)

private sealed interface SessionSetupDelivery {
    data object Pending : SessionSetupDelivery
    class Produced(val result: SessionSetupResult) : SessionSetupDelivery
    data object Claimed : SessionSetupDelivery
    data object Abandoned : SessionSetupDelivery
}

private data class SessionSetupRegistry(
    val accepting: Boolean = true,
    val active: Set<ActiveSessionSetup> = emptySet()
)

private data class AuthoritativePath(
    val status: NetworkPathStatus,
    val generation: Long
)

/**
 * AUDIT-2026-07 (SEC-1, decision #9a): upper bound on total concurrently
 * ACTIVE sessions before a net-new INBOUND session is refused at
 * registration ([SessionStore.tryRegister]). Outgoing (app-initiated)
 * connects are never refused by this bound, and simultaneous-open
 * arbitration is exempt (replace/reject causes no net session growth).
 * Terminal-but-not-yet-evicted sessions do not count.
 *
 * Internal admission-control POLICY, not public API: the value may be tuned
 * (or surfaced as configuration) in a later release without breaking anyone.
 */
internal const val MAX_TOTAL_ACTIVE_SESSIONS: Int = 64
