package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.AppKilledPolicy
import dev.p2pkit.core.BackgroundPolicy
import dev.p2pkit.core.KeepAliveConfig
import dev.p2pkit.core.NetworkPathObserver
import dev.p2pkit.core.NetworkPathStatus
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pKit
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.P2pState
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.PeerAuthorizationPolicy
import dev.p2pkit.core.Platform
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.permission.P2pPermissionManager
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.protocol.ProtocolConstants
import dev.p2pkit.core.provisioning.NetworkProvisioningConfig
import dev.p2pkit.core.provisioning.NetworkProvisioningFactory
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.ProvisioningContext
import dev.p2pkit.core.provisioning.UnsupportedNetworkProvisioningManager
import dev.p2pkit.core.security.LocalSecureIdentity
import dev.p2pkit.core.security.PlatformSecurityCryptography
import dev.p2pkit.core.security.SecureIdentityService
import dev.p2pkit.core.security.platformSecurityCryptography
import dev.p2pkit.core.internal.security.AuthenticatedV2SecurityEngine
import dev.p2pkit.core.internal.security.noise.SECURE_V2_MAX_APP_ID_UTF8_BYTES
import dev.p2pkit.core.transfer.FileTransferConfig
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.HasLocalTcpEndpoint
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportSecurityProfile
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.withContext
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Production [P2pKit] implementation. Wired up by
 * [dev.p2pkit.core.dsl.P2pKitBuilder].
 */
@OptIn(dev.p2pkit.core.ExperimentalP2pApi::class)
@Suppress("DEPRECATION")
internal class P2pKitImpl(
    override val appId: AppId,
    private val deviceName: String,
    private val localPlatform: Platform,
    override val localPeerId: PeerId,
    private val localSecureIdentity: LocalSecureIdentity?,
    private val secureIdentityService: SecureIdentityService?,
    private val secureIdentityUsage: SecureIdentityUsage?,
    private val securityCryptography: PlatformSecurityCryptography?,
    private val transportFactories: List<TransportFactory>,
    private val keepAlive: KeepAliveConfig,
    private val reconnectPolicy: ReconnectPolicy,
    private val backgroundPolicy: BackgroundPolicy,
    @Suppress("unused") private val appKilledPolicy: AppKilledPolicy,
    private val securityMode: SecurityMode,
    private val provisioningConfig: NetworkProvisioningConfig,
    private val provisioningFactory: NetworkProvisioningFactory?,
    private val fileTransferConfig: FileTransferConfig,
    override val permissions: P2pPermissionManager,
    private val logger: P2pLogger,
    private val clock: () -> Long,
    parentJob: Job?,
    private val pathObserver: NetworkPathObserver,
    /**
     * Test-only (#19 / 2026-07 TST-9, decision #15a): forwarded to
     * [SessionManager] → [SessionStore] so bookkeeping-invariant violations
     * throw instead of `logger.warn`ing. Production default `false`
     * (log-don't-crash); set only through the internal
     * [dev.p2pkit.core.dsl.P2pKitBuilder.strictSessionInvariants] knob,
     * which the commonTest `createTestKit` fixture enables.
     */
    private val strictSessionInvariants: Boolean = false
) : P2pKit {

    private val internalJob = SupervisorJob(parent = parentJob)

    // AUDIT-2026-07 (CON-3 rider, ARCH-4): kit-scope CoroutineExceptionHandler.
    // The SupervisorJob already keeps sibling coroutines alive, but an uncaught
    // failure in any internal collector previously escalated to the platform's
    // default handler — which terminates the host process on Android. Route it
    // to the injectable logger instead: crash prevention / defense-in-depth
    // behind the per-collector handling (e.g. startAcceptingIncoming's catch).
    // CancellationException never reaches a CoroutineExceptionHandler, so
    // cancellation semantics are untouched.
    private val uncaughtHandler = CoroutineExceptionHandler { _, e ->
        logger.error("P2pKit internal coroutine failed uncaught", e)
    }
    private val scope = CoroutineScope(Dispatchers.Default + internalJob + uncaughtHandler)

    override val networkProvisioning: NetworkProvisioningManager

    override val localDeviceName: String get() = deviceName

    override val localFingerprint: PeerFingerprint? get() = localSecureIdentity?.fingerprint

    override val localPairingQr: String? = localSecureIdentity?.let { identity ->
        checkNotNull(secureIdentityService).pairingQr(appId, identity.fingerprint)
    }

    override fun parsePeerPairingQr(value: String): PeerFingerprint? =
        secureIdentityService?.parsePairingQr(appId, value)

    override val networkPathStatus: StateFlow<NetworkPathStatus>
        get() = pathObserver.status

    private val _state = MutableStateFlow<P2pState>(P2pState.Idle)
    override val state: StateFlow<P2pState> = _state.asStateFlow()

    private val transports: List<Pair<DataTransport, DiscoveryTransport?>>
    private val dataTransports: List<DataTransport>
    private val discoveryTransports: List<DiscoveryTransport>

    private val transportManager: TransportManager
    private val securityProfile: TransportSecurityProfile = when (securityMode) {
        is SecurityMode.AuthenticatedV2 -> TransportSecurityProfile.AuthenticatedV2
        SecurityMode.NoneForMvp -> TransportSecurityProfile.LegacyPlaintextV1
    }
    private val protocol = DefaultP2pProtocol(
        clock = clock,
        logger = logger,
        version = when (securityProfile) {
            TransportSecurityProfile.AuthenticatedV2 -> ProtocolConstants.SECURE_VERSION
            TransportSecurityProfile.LegacyPlaintextV1 -> ProtocolConstants.LEGACY_VERSION
        }
    )
    private val sessionManager: SessionManager

    private val peerRegistry: PeerRegistry

    private val supportedTransportKinds: Set<TransportKind>

    // Lazy-start gate. `start()` is suspend and idempotent — a successful
    // start latches in via [startResult] = Result.success; a failed start
    // is recorded but lets the next caller retry. The mutex prevents two
    // concurrent suspend callers from racing two transport bind attempts.
    // The fast-path read of [startResult] outside the mutex is intentionally
    // un-synchronised: if a stale read says "not started," the slow path
    // re-checks under the lock. Worst case is one extra `withLock` round-trip.
    private val startMutex = Mutex()
    private var startResult: Result<Unit>? = null

    // Set once by [stop]. A stopped kit is terminal: its internal scope is
    // cancelled and cannot be revived, so every lifecycle entry point rejects
    // further calls instead of silently returning success onto a dead scope.
    @kotlin.concurrent.Volatile
    private var stopped: Boolean = false

    /**
     * Short commit gate shared by every public lifecycle operation and
     * session registration. Platform work never runs while this mutex is held.
     */
    private val lifecycleMutex = Mutex()
    private var lifecycleGeneration: Long = 0L
    private val stopCompletion = CompletableDeferred<Unit>()

    init {
        // V0.4-PROVENANCE (L2): emit framework identity to BOTH the
        // user-supplied P2pLogger (visible to samples that wire it) AND
        // the platform's native log channel (visible regardless of host
        // wiring). The native path matters because the default P2pLogger
        // is NoOp — without it, the iPhone Xcode console (which uses
        // the default logger in the iOS sample) would never show the
        // build identity.
        val identity = dev.p2pkit.core.BuildInfo.describe()
        logger.info("[buildInfo] $identity")
        nativeBuildInfoLog(identity)

        // Materialize transports
        val ctx = TransportContext(
            appId = appId,
            localPeerId = localPeerId,
            deviceName = deviceName,
            platform = localPlatform,
            securityProfile = securityProfile,
            localFingerprint = localFingerprint
        )
        transports = transportFactories.map { factory ->
            val pair = factory.build(ctx)
            pair.data to pair.discovery
        }
        dataTransports = transports.map { it.first }
        discoveryTransports = transports.mapNotNull { it.second }
        supportedTransportKinds = dataTransports.map { it.type }.toSet()

        transportManager = TransportManager(dataTransports)
        peerRegistry = PeerRegistry(
            discoveryTransports = discoveryTransports,
            scope = scope,
            clock = clock,
            securityProfile = securityProfile,
            peerIdFromFingerprint = secureIdentityService?.let { service ->
                { fingerprint -> service.peerId(appId, fingerprint) }
            }
        )
        sessionManager = SessionManager(
            scope = scope,
            transportManager = transportManager,
            protocol = protocol,
            securityMode = securityMode,
            localSecureIdentity = localSecureIdentity,
            authenticatedSecurity = securityCryptography?.let(::AuthenticatedV2SecurityEngine),
            keepAlive = keepAlive,
            reconnectPolicy = reconnectPolicy,
            localAppId = appId,
            localPeerId = localPeerId,
            localDeviceName = deviceName,
            localPlatform = localPlatform,
            localTransports = supportedTransportKinds,
            clock = clock,
            logger = logger,
            fileTransferConfig = fileTransferConfig,
            lifecycleGate = object : SessionLifecycleGate {
                override suspend fun isActive(expectedGeneration: Long?): Boolean =
                    lifecycleMutex.withLock {
                        lifecycleIsActiveLocked(expectedGeneration)
                    }

                override suspend fun <T : Any> commit(
                    expectedGeneration: Long?,
                    block: suspend () -> T
                ): T? = lifecycleMutex.withLock {
                    if (lifecycleIsActiveLocked(expectedGeneration)) block() else null
                }
            },
            peerLookup = peerRegistry::internalPeer,
            refreshDiscovery = {
                // V0.4-DISCOVERY-REFRESH: fan out to every registered
                // discovery transport. Run sequentially under each
                // transport's own lock; runCatching keeps one transport's
                // failure from blocking the others.
                discoveryTransports.forEach { transport ->
                    runCatching { transport.refresh() }
                        .onFailure { e ->
                            logger.warn(
                                "discovery refresh failed for ${transport.type}: " +
                                    "${e::class.simpleName}: ${e.message ?: ""}"
                            )
                        }
                }
            },
            strictInvariants = strictSessionInvariants
        )
        peerRegistry.start()
        sessionManager.startAcceptingIncoming(dataTransports)

        // Build the provisioning manager from the registered factory, or fall
        // back to Unsupported if none was registered. Done last in init so the
        // factory sees a fully-wired peerRegistry. Since the v0.3 transport
        // lifecycle refactor, the LAN transport's TCP port isn't bound until
        // start() runs — so we hand the factory a `() -> Int?` provider that
        // reads the current value each time the manager queries it.
        networkProvisioning = run {
            val factory = provisioningFactory
            if (factory == null) {
                UnsupportedNetworkProvisioningManager()
            } else {
                val lanEndpoint = dataTransports.filterIsInstance<HasLocalTcpEndpoint>()
                    .firstOrNull()
                val ctx = ProvisioningContext(
                    appId = appId,
                    localPeerId = localPeerId,
                    localDeviceName = deviceName,
                    config = provisioningConfig,
                    logger = logger,
                    lanTcpPort = { lanEndpoint?.tcpPort?.value },
                    manualPeerRegistrar = peerRegistry,
                    localFingerprint = localFingerprint,
                    localPairingQr = localPairingQr,
                    parentJob = internalJob
                )
                runCatching { factory.build(ctx) }.getOrElse { e ->
                    logger.warn(
                        "Network provisioning factory threw during build; falling back to Unsupported",
                        e
                    )
                    UnsupportedNetworkProvisioningManager()
                }
            }
        }

        if (reconnectPolicy is ReconnectPolicy.Enabled) {
            logger.debug(
                "ReconnectPolicy.Enabled (maxAttempts=${reconnectPolicy.maxAttempts}, " +
                    "retryDelayMillis=${reconnectPolicy.retryDelayMillis}). Outgoing sessions " +
                    "will retry after connection loss; incoming sessions still fail directly."
            )
        }
    }

    override val peers: StateFlow<List<Peer>> get() = peerRegistry.peers
    override val incomingSessions: SharedFlow<P2pSession> get() = sessionManager.incomingSessions
    override val sessions: StateFlow<List<P2pSession>> get() = sessionManager.sessions

    override suspend fun start() {
        val generation = beginLifecycleOperation()
        ensureStarted(generation)
    }

    /**
     * Bring every registered transport up. Idempotent: a successful first
     * call latches `startResult = success`; subsequent callers no-op. A
     * failed start does NOT latch — the next call retries the bind, which
     * matters for transient port-exhaustion or `EADDRINUSE` races where
     * a second attempt seconds later will succeed.
     *
     * Any per-transport failure surfaces as
     * [P2pError.TransportStartFailed]; we attribute the error to that
     * transport's [DataTransport.type] so the caller can show which medium
     * failed without inspecting the cause's class.
     */
    private suspend fun ensureStarted(generation: Long) {
        requireLifecycleActive(generation)
        startResult?.let { prior ->
            if (prior.isSuccess) return
        }
        startMutex.withLock {
            requireLifecycleActive(generation)
            startResult?.let { prior ->
                if (prior.isSuccess) return
            }
            // Drive Idle/Failed -> Starting as a generation commit. stop()
            // either observes this first and advances to Stopping, or wins
            // first and rejects the write; Starting can never overwrite it.
            val startingCommitted = commitLifecycle(generation) {
                if (_state.value == P2pState.Idle || _state.value is P2pState.Failed) {
                    _state.value = P2pState.Starting
                }
            }
            if (!startingCommitted) {
                throw lifecycleStoppedFailure()
            }
            for (transport in dataTransports) {
                // AUDIT-2026-07 (ARCH-1): rethrow cancellation before any
                // wrapping or latching. The previous `runCatching` captured
                // CancellationException too, so a caller cancelled mid-bind
                // (a routine host-lifecycle event, e.g. an Android scope
                // cancelling `kit.start()`) had its CE converted into
                // TransportStartFailed, `startResult` latched as failure, and
                // the public state corrupted to Failed. On cancellation we
                // leave `startResult` and `_state` untouched (still Starting)
                // so a subsequent start() retries cleanly.
                val r = try {
                    transport.start()
                } catch (e: CancellationException) {
                    if (!isLifecycleActive(generation)) {
                        cleanupLateStart(
                            observerMayHaveStarted = false,
                            dataMayHaveStartedLate = true
                        )
                    }
                    throw e
                } catch (e: Throwable) {
                    Result.failure(e)
                }
                if (!isLifecycleActive(generation)) {
                    cleanupLateStart(
                        observerMayHaveStarted = false,
                        dataMayHaveStartedLate = true
                    )
                    throw lifecycleStoppedFailure()
                }
                if (r.isFailure) {
                    val cause = r.exceptionOrNull()
                    val failed = P2pError.TransportStartFailed(
                        transportKind = transport.type,
                        reason = cause?.message ?: "transport.start() returned failure",
                        underlying = cause
                    )
                    val committed = commitLifecycle(generation) {
                        startResult = Result.failure(failed)
                        _state.value = P2pState.Failed(failed)
                    }
                    if (!committed) {
                        cleanupLateStart(
                            observerMayHaveStarted = false,
                            dataMayHaveStartedLate = true
                        )
                        throw lifecycleStoppedFailure()
                    }
                    throw failed
                }
            }
            // AUDIT-2026-06 (stop-hang fix): stop() bounds its wait for this
            // mutex; if one of the transport.start() calls above hung past
            // that bound, stop() has already torn the kit down WITHOUT the
            // lock. Re-check before latching success — a Stopped kit must
            // never latch startResult=success or flip (back) to Running.
            // Close whatever this bind loop just (re)opened; transport
            // close() is idempotent for the ones stop() already closed.
            if (!isLifecycleActive(generation)) {
                cleanupLateStart(
                    observerMayHaveStarted = false,
                    dataMayHaveStartedLate = true
                )
                throw IllegalStateException("P2pKit has been stopped; create a new instance")
            }
            // Best-effort path observer startup. A failure here is logged
            // but never propagates — `networkPathStatus` simply stays at
            // [NetworkPathStatus.Unknown] and the SDK behaves as if no
            // observer is wired up. Cancellation of the calling coroutine is
            // NOT a failure, though: rethrow it instead of logging it away
            // (AUDIT-2026-07 (ARCH-1), same shape as the bind loop above).
            try {
                pathObserver.start()
            } catch (e: CancellationException) {
                if (!isLifecycleActive(generation)) {
                    cleanupLateStart(
                        observerMayHaveStarted = true,
                        dataMayHaveStartedLate = false
                    )
                }
                throw e
            } catch (e: Throwable) {
                logger.warn("NetworkPathObserver.start() failed; path-change recovery disabled for this session", e)
            }
            val committed = commitLifecycle(generation) {
                // Subscribe SessionManager to path changes only while the
                // generation is still active. stop() cannot latch terminal
                // between this check and the final Running publication.
                scope.launch {
                    pathObserver.status.collect { status ->
                        sessionManager.applyPathChange(status)
                    }
                }
                startResult = Result.success(Unit)
                _state.value = P2pState.Running
            }
            if (!committed) {
                cleanupLateStart(
                    observerMayHaveStarted = true,
                    dataMayHaveStartedLate = false
                )
                throw lifecycleStoppedFailure()
            }
        }
    }

    override suspend fun startAdvertising() {
        val generation = beginLifecycleOperation()
        ensurePermissions()
        ensureStarted(generation)
        try {
            val localInfo = LocalPeerInfo(
                peerId = localPeerId,
                deviceName = deviceName,
                platform = localPlatform,
                appId = appId,
                supportedTransports = supportedTransportKinds,
                securityProfile = securityProfile,
                fingerprint = localFingerprint
            )
            for (transport in discoveryTransports) {
                requireLifecycleActive(generation)
                transport.startAdvertising(localInfo)
                if (!isLifecycleActive(generation)) throw lifecycleStoppedFailure()
            }
        } catch (e: CancellationException) {
            if (!isLifecycleActive(generation)) {
                cleanupLateDiscoveryOperation("advertising") { it.stopAdvertising() }
            }
            throw e
        } catch (e: Throwable) {
            if (!isLifecycleActive(generation)) {
                cleanupLateDiscoveryOperation("advertising") { it.stopAdvertising() }
                throw lifecycleStoppedFailure()
            }
            // A partial advertise failure must not leave state stuck — surface
            // it as Failed (consistent with the ensureStarted bind-failure path).
            val err = if (e is P2pError) e
            else P2pError.ConnectionFailed("startAdvertising failed: ${e.message ?: e::class.simpleName}")
            if (!commitLifecycle(generation) { _state.value = P2pState.Failed(err) }) {
                cleanupLateDiscoveryOperation("advertising") {
                    it.stopAdvertising()
                }
                throw lifecycleStoppedFailure()
            }
            throw err
        }
        val committed = commitLifecycle(generation) {
            if (_state.value is P2pState.Failed) _state.value = P2pState.Running
        }
        if (!committed) {
            cleanupLateDiscoveryOperation("advertising") {
                it.stopAdvertising()
            }
            throw lifecycleStoppedFailure()
        }
    }

    override suspend fun stopAdvertising() {
        for (transport in discoveryTransports) {
            runCatching { transport.stopAdvertising() }
        }
    }

    override suspend fun startDiscovery() {
        val generation = beginLifecycleOperation()
        ensurePermissions()
        ensureStarted(generation)
        try {
            for (transport in discoveryTransports) {
                requireLifecycleActive(generation)
                transport.startDiscovery()
                if (!isLifecycleActive(generation)) throw lifecycleStoppedFailure()
            }
        } catch (e: CancellationException) {
            if (!isLifecycleActive(generation)) {
                cleanupLateDiscoveryOperation("discovery") { it.stopDiscovery() }
            }
            throw e
        } catch (e: Throwable) {
            if (!isLifecycleActive(generation)) {
                cleanupLateDiscoveryOperation("discovery") { it.stopDiscovery() }
                throw lifecycleStoppedFailure()
            }
            // Mirror startAdvertising: surface a typed error instead of
            // letting a raw platform exception escape the public API
            // (AUDIT-2026-06 fix).
            val err = if (e is P2pError) e
            else P2pError.ConnectionFailed("startDiscovery failed: ${e.message ?: e::class.simpleName}")
            if (!commitLifecycle(generation) { _state.value = P2pState.Failed(err) }) {
                cleanupLateDiscoveryOperation("discovery") {
                    it.stopDiscovery()
                }
                throw lifecycleStoppedFailure()
            }
            throw err
        }
        val committed = commitLifecycle(generation) {
            if (_state.value is P2pState.Failed) _state.value = P2pState.Running
        }
        if (!committed) {
            cleanupLateDiscoveryOperation("discovery") {
                it.stopDiscovery()
            }
            throw lifecycleStoppedFailure()
        }
    }

    override suspend fun stopDiscovery() {
        for (transport in discoveryTransports) {
            runCatching { transport.stopDiscovery() }
        }
    }

    override suspend fun connect(peer: Peer): P2pSession {
        return connectInternal(peer, expectedFingerprint = null)
    }

    override suspend fun connect(
        peer: Peer,
        expectedFingerprint: PeerFingerprint
    ): P2pSession = connectInternal(peer, expectedFingerprint)

    private suspend fun connectInternal(
        peer: Peer,
        expectedFingerprint: PeerFingerprint?
    ): P2pSession {
        val generation = beginLifecycleOperation()
        ensureStarted(generation)
        val internalPeer = peerRegistry.internalPeer(peer.id)
            ?: dev.p2pkit.core.transport.InternalPeer(
                publicPeer = peer,
                transportHints = peer.supportedTransports.map {
                    dev.p2pkit.core.transport.TransportHint(type = it)
                }
            )
        return sessionManager.connect(
            peer = peer,
            internalPeer = internalPeer,
            expectedFingerprint = expectedFingerprint,
            lifecycleGeneration = generation
        )
    }

    override fun lastSeen(peerId: PeerId): Long? = peerRegistry.lastSeen(peerId)

    override fun notifyAppBackgrounded() {
        when (backgroundPolicy) {
            is BackgroundPolicy.CloseActiveSessions -> {
                // Close sessions + pause advertising/discovery, but do NOT emit
                // P2pState.Stopped: the data transports stay bound (only stop()
                // closes them) and the kit is still functional, so reporting
                // Stopped would lie to host UIs and never recover on foreground.
                // applyBackgroundPolicy already closes active sessions; don't
                // double-close here.
                scope.launch {
                    runCatching { stopAdvertising() }
                    runCatching { stopDiscovery() }
                }
                sessionManager.applyBackgroundPolicy(backgroundPolicy)
            }
            is BackgroundPolicy.KeepRunning -> { /* nothing to do */ }
        }
    }

    override fun notifyAppForegrounded() {
        // v0.1: app must re-call startAdvertising()/startDiscovery() itself.
        logger.debug("P2pKit.notifyAppForegrounded — app should re-invoke startAdvertising/startDiscovery if needed")
    }

    override suspend fun stop() {
        val ownsTeardown = withContext(NonCancellable) {
            lifecycleMutex.withLock {
                if (stopped) {
                    false
                } else {
                    // The generation changes before any resource snapshot.
                    // Late operations can finish platform work, but cannot
                    // publish and must execute their compensating cleanup.
                    stopped = true
                    lifecycleGeneration += 1
                    _state.value = P2pState.Stopping
                    true
                }
            }
        }
        if (!ownsTeardown) {
            // Idempotent concurrent callers observe completion of the same
            // teardown instead of returning while the first caller still owns
            // live resources.
            withContext(NonCancellable) {
                stopCompletion.await()
                // Preserve the secure-identity fail-closed retry contract: if
                // the leader retained the lease because a child ignored its
                // bound, a later idempotent stop gets another bounded join.
                finishIdentityOwnershipTeardown()
            }
            return
        }
        // NonCancellable: `stopped` latches at entry, so if the caller's
        // coroutine were cancelled mid-teardown the kit would be permanently
        // half-stopped (transports bound, scope alive) with every later
        // stop() a no-op. closeAllSessions is additionally runCatching-
        // wrapped so one bad session cannot abort the rest of teardown
        // (AUDIT-2026-06 fix).
        withContext(NonCancellable) {
            try {
            // startMutex: a concurrent ensureStarted mid-bind must not
            // interleave with teardown (it could keep binding transports
            // after we closed them, then latch Running/startResult-success
            // AFTER Stopped). But the acquisition must be BOUNDED: if
            // ensureStarted is parked inside a hung transport.start() while
            // holding this mutex, an unbounded withLock would park stop()
            // uncancellably (inside NonCancellable) forever
            // (AUDIT-2026-06 fix). On timeout, tear down WITHOUT the lock —
            // best-effort, and safe against a late rebind because `stopped`
            // is already set and ensureStarted's post-bind re-check closes
            // anything it bound in the meantime.
            val acquired = withTimeoutOrNull(STOP_START_MUTEX_TIMEOUT_MS) {
                startMutex.withLock { teardownBoundResources() }
                true
            } ?: false
            if (!acquired) {
                logger.warn(
                    "stop(): startMutex not released within ${STOP_START_MUTEX_TIMEOUT_MS}ms " +
                        "(a transport start() is likely hung); tearing down without the lock"
                )
                teardownBoundResources()
            }

            // AUDIT-2026-07 (ARCH-2): this tail previously ran OUTSIDE the
            // NonCancellable block and unbounded, with two failure shapes:
            // a caller cancelled mid-teardown aborted `pathObserver.close()`
            // at its first suspension point (the platform observer leaked and
            // Stopped was never latched by this call), and a close() parked
            // on the observer's internal mutex (e.g. one still held by a hung
            // observer start()) parked stop() forever. Keep it inside
            // NonCancellable and bound the observer close, mirroring the
            // bounded startMutex acquisition above (AUDIT-2026-06 pattern).
            //
            // Provisioning managers attach their scope to internalJob; the
            // internalJob.cancel() below fires their invokeOnCompletion
            // teardown (e.g. AndroidNetworkProvisioningManager releases its
            // LocalOnlyHotspot reservation and unbinds the joined network
            // there).
            val observerClosed = withTimeoutOrNull(OBSERVER_CLOSE_TIMEOUT_MS) {
                try {
                    pathObserver.close()
                } catch (e: CancellationException) {
                    // Only the bounding timeout's own cancellation can reach
                    // here (this block is NonCancellable from the outside);
                    // rethrow so withTimeoutOrNull reports it as `null`.
                    throw e
                } catch (e: Throwable) {
                    logger.warn("NetworkPathObserver.close() failed during stop()", e)
                }
                true
            } ?: false
            if (!observerClosed) {
                logger.warn(
                    "stop(): NetworkPathObserver.close() did not complete within " +
                        "${OBSERVER_CLOSE_TIMEOUT_MS}ms; abandoning it (its platform monitor " +
                        "may stay attached until process exit)"
                )
            }
            } finally {
                try {
                    finishIdentityOwnershipTeardown()
                } finally {
                    _state.value = P2pState.Stopped
                    stopCompletion.complete(Unit)
                }
            }
        }
    }

    private suspend fun beginLifecycleOperation(): Long = lifecycleMutex.withLock {
        if (stopped) throw lifecycleStoppedFailure()
        lifecycleGeneration
    }

    private suspend fun requireLifecycleActive(expectedGeneration: Long) {
        if (!isLifecycleActive(expectedGeneration)) throw lifecycleStoppedFailure()
    }

    private suspend fun isLifecycleActive(expectedGeneration: Long?): Boolean =
        lifecycleMutex.withLock {
            lifecycleIsActiveLocked(expectedGeneration)
        }

    private fun lifecycleIsActiveLocked(expectedGeneration: Long?): Boolean =
        !stopped && (expectedGeneration == null || expectedGeneration == lifecycleGeneration)

    private suspend fun commitLifecycle(
        expectedGeneration: Long,
        block: () -> Unit
    ): Boolean = lifecycleMutex.withLock {
        if (!lifecycleIsActiveLocked(expectedGeneration)) return@withLock false
        block()
        true
    }

    private fun lifecycleStoppedFailure(): IllegalStateException =
        IllegalStateException("P2pKit has been stopped; create a new instance")

    private suspend fun cleanupLateStart(
        observerMayHaveStarted: Boolean,
        dataMayHaveStartedLate: Boolean
    ) {
        withContext(NonCancellable) {
            if (observerMayHaveStarted) {
                cleanupStaleResource("network path observer") { pathObserver.close() }
            }
            if (dataMayHaveStartedLate) {
                for (transport in dataTransports.asReversed()) {
                    cleanupStaleResource("${transport.type} data transport") { transport.close() }
                }
            }
        }
    }

    private suspend fun cleanupLateDiscoveryOperation(
        operation: String,
        cleanup: suspend (DiscoveryTransport) -> Unit
    ) {
        withContext(NonCancellable) {
            for (transport in discoveryTransports.asReversed()) {
                cleanupStaleResource("${transport.type} $operation") { cleanup(transport) }
            }
        }
    }

    private suspend fun cleanupStaleResource(
        label: String,
        cleanup: suspend () -> Unit
    ) {
        val completed = try {
            withTimeoutOrNull(STALE_OPERATION_CLEANUP_TIMEOUT_MS) {
                cleanup()
                true
            } ?: false
        } catch (e: Throwable) {
            logger.warn("Late lifecycle cleanup failed for $label", e)
            return
        }
        if (!completed) {
            logger.warn(
                "Late lifecycle cleanup for $label exceeded " +
                    "$STALE_OPERATION_CLEANUP_TIMEOUT_MS ms"
            )
        }
    }

    /**
     * Clear the in-memory private key immediately, but release destructive
     * reset exclusion only after every kit child has terminated. If a broken
     * child ignores cancellation, retaining the idempotent usage token is the
     * required fail-closed behavior; a later stop() call retries the join.
     */
    private suspend fun finishIdentityOwnershipTeardown() {
        localSecureIdentity?.clearPrivate()
        internalJob.cancel()
        val childrenStopped = withTimeoutOrNull(INTERNAL_JOB_CLOSE_TIMEOUT_MS) {
            internalJob.cancelAndJoin()
            true
        } ?: false
        if (childrenStopped) secureIdentityUsage?.release()
    }

    /**
     * The teardown body shared by [stop]'s locked (normal) and lock-less
     * (mutex-starved) paths. Every step is runCatching-wrapped and idempotent
     * (sessions/transports tolerate double close), so the rare interleavings —
     * two concurrent first `stop()` calls, or the timeout firing mid-teardown
     * and the fallback re-running it — are safe.
     */
    private suspend fun teardownBoundResources() {
        runCatching { stopAdvertising() }
        runCatching { stopDiscovery() }
        runCatching { sessionManager.closeAllSessions() }
        for (transport in dataTransports) {
            runCatching { transport.close() }
        }
    }

    // Gates on genuinely runtime-requestable permissions only (e.g. the
    // provisioning sidecar's NEARBY_WIFI_DEVICES / ACCESS_FINE_LOCATION via
    // its own P2pPermissionManager). The default platform managers report
    // none — Android's install-time Wi-Fi permissions are deliberately NOT
    // surfaced here; a missing manifest declaration is a construction-time
    // warn instead (AUDIT-2026-06 permission-gate regression fix; see
    // PermissionManagerFactory.android.kt).
    private suspend fun ensurePermissions() {
        val missing = permissions.missingPermissions()
        if (missing.isNotEmpty()) throw P2pError.PermissionMissing(missing)
    }

    /**
     * TEST-ONLY seam (#19 / 2026-07 P1-03) — never call from production
     * code. Forwards to [SessionManager.forceStoreInvariantViolationForTest]
     * so the strict-invariants meta-test can prove that a bookkeeping
     * violation inside a **kit-built** store throws under
     * [strictSessionInvariants] (and only warns under the production
     * default), validating the builder → kit → manager → store threading
     * end to end.
     */
    internal suspend fun forceSessionStoreInvariantViolationForTest(session: P2pSession) {
        sessionManager.forceStoreInvariantViolationForTest(session)
    }

    private companion object {
        /**
         * How long [stop] waits to take [startMutex] from a concurrent
         * [ensureStarted] before falling back to lock-less teardown. Generous
         * next to any healthy transport bind (milliseconds); only a hung
         * `transport.start()` holds the mutex this long (AUDIT-2026-06,
         * stop-hang fix).
         */
        const val STOP_START_MUTEX_TIMEOUT_MS: Long = 5_000

        /**
         * How long [stop] waits for [NetworkPathObserver.close] before
         * abandoning it. A healthy observer detaches in microseconds; only
         * one parked on its own internal state (e.g. a mutex still held by a
         * hung `start()`) reaches this bound (AUDIT-2026-07 (ARCH-2)).
         */
        const val OBSERVER_CLOSE_TIMEOUT_MS: Long = 5_000

        /** Bound before fail-closed retention of the destructive-reset lease. */
        const val INTERNAL_JOB_CLOSE_TIMEOUT_MS: Long = 5_000

        /** Bound for each resource created by an operation that lost its generation. */
        const val STALE_OPERATION_CLEANUP_TIMEOUT_MS: Long = 2_000
    }
}

/**
 * Builds a [P2pKitImpl] from collected DSL configuration. Called by
 * [dev.p2pkit.core.dsl.P2pKitBuilder.build]. Public so the DSL package can
 * reach it; internal-by-convention to the SDK.
 */
internal fun newP2pKit(
    appId: AppId,
    deviceName: String,
    transportFactories: List<TransportFactory>,
    keepAlive: KeepAliveConfig,
    reconnectPolicy: ReconnectPolicy,
    backgroundPolicy: BackgroundPolicy,
    appKilledPolicy: AppKilledPolicy,
    securityMode: SecurityMode,
    provisioningConfig: NetworkProvisioningConfig,
    provisioningFactory: NetworkProvisioningFactory?,
    fileTransferConfig: FileTransferConfig,
    logger: P2pLogger,
    peerIdStorageOverride: PeerIdStorage? = null,
    secureIdentityStorageOverride: SecureIdentityStorage? = null,
    networkPathObserverOverride: NetworkPathObserver? = null,
    permissionManagerOverride: dev.p2pkit.core.permission.P2pPermissionManager? = null,
    strictSessionInvariants: Boolean = false
): P2pKit {
    // Authorization is a whole-kit security decision. Snapshot caller-owned
    // collections before any identity or transport becomes observable so a
    // later mutation cannot silently change which remote keys are admitted.
    val frozenSecurityMode = securityMode.snapshotForKitOwnership()
    val secureIdentityService: SecureIdentityService?
    val secureIdentityUsage: SecureIdentityUsage?
    val secureIdentity: LocalSecureIdentity?
    val cryptography: PlatformSecurityCryptography?
    val localPeerId: PeerId

    @Suppress("DEPRECATION")
    when (frozenSecurityMode) {
        is SecurityMode.AuthenticatedV2 -> {
            val appIdByteCount = appId.value.encodeToByteArray().size
            if (appIdByteCount > SECURE_V2_MAX_APP_ID_UTF8_BYTES) {
                throw P2pError.SecurityConfigurationInvalid(
                    "Secure v2 AppId UTF-8 length exceeds $SECURE_V2_MAX_APP_ID_UTF8_BYTES bytes"
                )
            }
            cryptography = platformSecurityCryptography()
            val secureIdentityStorage = secureIdentityStorageOverride
                ?: defaultSecureIdentityStorage(appId, logger)
            secureIdentityService = SecureIdentityService(cryptography, secureIdentityStorage)
            val usage = secureIdentityService.acquireUsage(appId)
            val identity = try {
                secureIdentityService.loadOrCreate(appId)
            } catch (cause: Throwable) {
                usage.release()
                throw cause
            }
            secureIdentityUsage = usage
            secureIdentity = identity
            localPeerId = identity.peerId
        }
        SecurityMode.NoneForMvp -> {
            cryptography = null
            secureIdentityService = null
            secureIdentityUsage = null
            secureIdentity = null
            val peerIdStorage = peerIdStorageOverride ?: defaultPeerIdStorage(appId, logger)
            localPeerId = peerIdStorage.loadOrGenerate()
        }
    }
    return try {
        val pathObserver = networkPathObserverOverride ?: defaultNetworkPathObserver(logger)
        val permissionManager = permissionManagerOverride ?: defaultPlatformPermissionManager(logger)
        P2pKitImpl(
            appId = appId,
            deviceName = deviceName,
            localPlatform = currentPlatform(),
            localPeerId = localPeerId,
            localSecureIdentity = secureIdentity,
            secureIdentityService = secureIdentityService,
            secureIdentityUsage = secureIdentityUsage,
            securityCryptography = cryptography,
            transportFactories = transportFactories,
            keepAlive = keepAlive,
            reconnectPolicy = reconnectPolicy,
            backgroundPolicy = backgroundPolicy,
            appKilledPolicy = appKilledPolicy,
            securityMode = frozenSecurityMode,
            provisioningConfig = provisioningConfig,
            provisioningFactory = provisioningFactory,
            fileTransferConfig = fileTransferConfig,
            permissions = permissionManager,
            logger = logger,
            clock = ::systemTimeMillis,
            parentJob = null,
            pathObserver = pathObserver,
            strictSessionInvariants = strictSessionInvariants
        )
    } catch (cause: Throwable) {
        secureIdentity?.clearPrivate()
        secureIdentityUsage?.release()
        throw cause
    }
}

@Suppress("DEPRECATION")
@OptIn(dev.p2pkit.core.ExplicitSecurityRisk::class)
private fun SecurityMode.snapshotForKitOwnership(): SecurityMode = when (this) {
    is SecurityMode.AuthenticatedV2 -> copy(
        authorization = when (val policy = authorization) {
            is PeerAuthorizationPolicy.PinnedOnly -> policy.copy(
                fingerprints = policy.fingerprints.toSet()
            )
            PeerAuthorizationPolicy.RejectUnknown -> policy
            PeerAuthorizationPolicy.AcceptAnyAuthenticatedSameApp -> policy
        }
    )
    SecurityMode.NoneForMvp -> this
}
