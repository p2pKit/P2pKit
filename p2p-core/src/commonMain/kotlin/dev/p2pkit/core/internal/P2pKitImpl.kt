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
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.ReconnectPolicy
import dev.p2pkit.core.SecurityMode
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.permission.P2pPermissionManager
import dev.p2pkit.core.protocol.DefaultP2pProtocol
import dev.p2pkit.core.provisioning.NetworkProvisioningConfig
import dev.p2pkit.core.provisioning.NetworkProvisioningFactory
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.ProvisioningContext
import dev.p2pkit.core.provisioning.UnsupportedNetworkProvisioningManager
import dev.p2pkit.core.security.NoOpSecurityManager
import dev.p2pkit.core.security.SecurityManager
import dev.p2pkit.core.transfer.FileTransferConfig
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.HasLocalTcpEndpoint
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Production [P2pKit] implementation. Wired up by
 * [dev.p2pkit.core.dsl.P2pKitBuilder].
 */
@OptIn(dev.p2pkit.core.ExperimentalP2pApi::class)
internal class P2pKitImpl(
    override val appId: AppId,
    private val deviceName: String,
    private val localPlatform: Platform,
    override val localPeerId: PeerId,
    private val transportFactories: List<TransportFactory>,
    private val keepAlive: KeepAliveConfig,
    private val reconnectPolicy: ReconnectPolicy,
    private val backgroundPolicy: BackgroundPolicy,
    @Suppress("unused") private val appKilledPolicy: AppKilledPolicy,
    @Suppress("unused") private val securityMode: SecurityMode,
    private val provisioningConfig: NetworkProvisioningConfig,
    private val provisioningFactory: NetworkProvisioningFactory?,
    private val fileTransferConfig: FileTransferConfig,
    override val permissions: P2pPermissionManager,
    private val logger: P2pLogger,
    private val clock: () -> Long,
    parentJob: Job?,
    private val pathObserver: NetworkPathObserver
) : P2pKit {

    private val internalJob = SupervisorJob(parent = parentJob)
    private val scope = CoroutineScope(Dispatchers.Default + internalJob)

    override val networkProvisioning: NetworkProvisioningManager

    override val localDeviceName: String get() = deviceName

    override val networkPathStatus: StateFlow<NetworkPathStatus>
        get() = pathObserver.status

    private val _state = MutableStateFlow<P2pState>(P2pState.Idle)
    override val state: StateFlow<P2pState> = _state.asStateFlow()

    private val transports: List<Pair<DataTransport, DiscoveryTransport?>>
    private val dataTransports: List<DataTransport>
    private val discoveryTransports: List<DiscoveryTransport>

    private val transportManager: TransportManager
    private val security: SecurityManager = NoOpSecurityManager()
    private val protocol = DefaultP2pProtocol(clock = clock, logger = logger)
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
            platform = localPlatform
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
            clock = clock
        )
        sessionManager = SessionManager(
            scope = scope,
            transportManager = transportManager,
            protocol = protocol,
            security = security,
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
            }
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
        ensureStarted()
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
    private suspend fun ensureStarted() {
        if (stopped) throw IllegalStateException("P2pKit has been stopped; create a new instance")
        startResult?.let { prior ->
            if (prior.isSuccess) return
        }
        startMutex.withLock {
            if (stopped) throw IllegalStateException("P2pKit has been stopped; create a new instance")
            startResult?.let { prior ->
                if (prior.isSuccess) return
            }
            // Drive the documented lifecycle: Idle/Failed -> Starting on the
            // first (or retried) start attempt.
            if (_state.value == P2pState.Idle || _state.value is P2pState.Failed) {
                _state.value = P2pState.Starting
            }
            for (transport in dataTransports) {
                val r = runCatching { transport.start() }.getOrElse { Result.failure(it) }
                if (r.isFailure) {
                    val cause = r.exceptionOrNull()
                    val failed = P2pError.TransportStartFailed(
                        transportKind = transport.type,
                        reason = cause?.message ?: "transport.start() returned failure",
                        underlying = cause
                    )
                    startResult = Result.failure(failed)
                    // Surface the documented terminal Failed state (Errors.kt
                    // claims TransportStartFailed surfaces through the lifecycle).
                    _state.value = P2pState.Failed(failed)
                    throw failed
                }
            }
            // Best-effort path observer startup. A failure here is logged
            // but never propagates — `networkPathStatus` simply stays at
            // [NetworkPathStatus.Unknown] and the SDK behaves as if no
            // observer is wired up.
            runCatching { pathObserver.start() }.onFailure {
                logger.warn("NetworkPathObserver.start() failed; path-change recovery disabled for this session", it)
            }
            // Subscribe SessionManager to path changes. Done after the
            // observer starts so [SessionManager.applyPathChange] sees the
            // observer's initial emission. We launch on the kit's internal
            // scope so the subscription tears down with kit.stop().
            scope.launch {
                pathObserver.status.collect { status ->
                    sessionManager.applyPathChange(status)
                }
            }
            startResult = Result.success(Unit)
            // Successful start reaches Running, regardless of which entry point
            // (start / startAdvertising / startDiscovery / connect) triggered it.
            _state.value = P2pState.Running
        }
    }

    override suspend fun startAdvertising() {
        ensurePermissions()
        ensureStarted()
        try {
            val localInfo = LocalPeerInfo(
                peerId = localPeerId,
                deviceName = deviceName,
                platform = localPlatform,
                appId = appId,
                supportedTransports = supportedTransportKinds
            )
            for (transport in discoveryTransports) {
                transport.startAdvertising(localInfo)
            }
        } catch (e: CancellationException) {
            throw e
        } catch (e: Throwable) {
            // A partial advertise failure must not leave state stuck — surface
            // it as Failed (consistent with the ensureStarted bind-failure path).
            val err = if (e is P2pError) e
            else P2pError.ConnectionFailed("startAdvertising failed: ${e.message ?: e::class.simpleName}")
            _state.value = P2pState.Failed(err)
            throw err
        }
    }

    override suspend fun stopAdvertising() {
        for (transport in discoveryTransports) {
            runCatching { transport.stopAdvertising() }
        }
    }

    override suspend fun startDiscovery() {
        ensurePermissions()
        ensureStarted()
        for (transport in discoveryTransports) {
            transport.startDiscovery()
        }
    }

    override suspend fun stopDiscovery() {
        for (transport in discoveryTransports) {
            runCatching { transport.stopDiscovery() }
        }
    }

    override suspend fun connect(peer: Peer): P2pSession {
        ensureStarted()
        val internalPeer = peerRegistry.internalPeer(peer.id)
            ?: dev.p2pkit.core.transport.InternalPeer(
                publicPeer = peer,
                transportHints = peer.supportedTransports.map {
                    dev.p2pkit.core.transport.TransportHint(type = it)
                }
            )
        return sessionManager.connect(peer, internalPeer)
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
        // Terminal & idempotent. internalJob.cancel() below permanently kills
        // the scope that powers SessionManager / PeerRegistry / accept loops,
        // so the instance cannot be revived — the `stopped` flag makes any
        // subsequent lifecycle call fail loudly (IllegalStateException) instead
        // of latching onto a dead scope and silently no-op'ing.
        if (stopped) return
        stopped = true
        _state.value = P2pState.Stopping
        runCatching { stopAdvertising() }
        runCatching { stopDiscovery() }
        sessionManager.closeAllSessions()
        for (transport in dataTransports) {
            runCatching { transport.close() }
        }
        // Provisioning managers attach their scope to internalJob; the
        // internalJob.cancel() below fires their invokeOnCompletion teardown
        // (e.g. AndroidNetworkProvisioningManager releases its LocalOnlyHotspot
        // reservation and unbinds the joined network there).
        runCatching { pathObserver.close() }
        internalJob.cancel()
        _state.value = P2pState.Stopped
    }

    private suspend fun ensurePermissions() {
        val missing = permissions.missingPermissions()
        if (missing.isNotEmpty()) throw P2pError.PermissionMissing(missing)
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
    networkPathObserverOverride: NetworkPathObserver? = null
): P2pKit {
    val peerIdStorage = peerIdStorageOverride ?: defaultPeerIdStorage(appId, logger)
    val pathObserver = networkPathObserverOverride ?: defaultNetworkPathObserver(logger)
    return P2pKitImpl(
        appId = appId,
        deviceName = deviceName,
        localPlatform = currentPlatform(),
        localPeerId = peerIdStorage.loadOrGenerate(),
        transportFactories = transportFactories,
        keepAlive = keepAlive,
        reconnectPolicy = reconnectPolicy,
        backgroundPolicy = backgroundPolicy,
        appKilledPolicy = appKilledPolicy,
        securityMode = securityMode,
        provisioningConfig = provisioningConfig,
        provisioningFactory = provisioningFactory,
        fileTransferConfig = fileTransferConfig,
        permissions = dev.p2pkit.core.permission.NoOpP2pPermissionManager(),
        logger = logger,
        clock = ::systemTimeMillis,
        parentJob = null,
        pathObserver = pathObserver
    )
}
