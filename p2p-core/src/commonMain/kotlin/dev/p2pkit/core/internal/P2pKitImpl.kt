package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.AppKilledPolicy
import dev.p2pkit.core.BackgroundPolicy
import dev.p2pkit.core.KeepAliveConfig
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
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.DiscoveryTransport
import dev.p2pkit.core.transport.HasLocalTcpEndpoint
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking

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
    override val permissions: P2pPermissionManager,
    private val logger: P2pLogger,
    private val clock: () -> Long,
    parentJob: Job?
) : P2pKit {

    private val internalJob = SupervisorJob(parent = parentJob)
    private val scope = CoroutineScope(Dispatchers.Default + internalJob)

    override val networkProvisioning: NetworkProvisioningManager

    override val localDeviceName: String get() = deviceName

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

    init {
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
            logger = logger
        )
        peerRegistry.start()
        sessionManager.startAcceptingIncoming(dataTransports)

        // Build the provisioning manager from the registered factory, or fall
        // back to Unsupported if none was registered. Done last in init so the
        // factory sees a fully-wired peerRegistry and the LAN transport's
        // bound TCP port (when present).
        networkProvisioning = run {
            val factory = provisioningFactory
            if (factory == null) {
                UnsupportedNetworkProvisioningManager()
            } else {
                val lanPort = dataTransports.filterIsInstance<HasLocalTcpEndpoint>()
                    .firstOrNull()?.tcpPort
                val ctx = ProvisioningContext(
                    appId = appId,
                    localPeerId = localPeerId,
                    localDeviceName = deviceName,
                    config = provisioningConfig,
                    logger = logger,
                    lanTcpPort = lanPort,
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

    override suspend fun startAdvertising() {
        ensurePermissions()
        _state.value = P2pState.Starting
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
        _state.value = P2pState.Running
    }

    override suspend fun stopAdvertising() {
        for (transport in discoveryTransports) {
            runCatching { transport.stopAdvertising() }
        }
    }

    override suspend fun startDiscovery() {
        ensurePermissions()
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
        sessionManager.applyBackgroundPolicy(backgroundPolicy)
        when (backgroundPolicy) {
            is BackgroundPolicy.CloseActiveSessions -> {
                scope.launch {
                    runCatching { stopAdvertising() }
                    runCatching { stopDiscovery() }
                    _state.value = P2pState.Stopped
                }
            }
            is BackgroundPolicy.KeepRunning -> { /* nothing to do */ }
        }
    }

    override fun notifyAppForegrounded() {
        // v0.1: app must re-call startAdvertising()/startDiscovery() itself.
        logger.debug("P2pKit.notifyAppForegrounded — app should re-invoke startAdvertising/startDiscovery if needed")
    }

    override suspend fun stop() {
        _state.value = P2pState.Stopping
        runCatching { stopAdvertising() }
        runCatching { stopDiscovery() }
        sessionManager.closeAllSessions()
        for (transport in dataTransports) {
            runCatching { transport.close() }
        }
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
    logger: P2pLogger,
    peerIdStorageOverride: PeerIdStorage? = null
): P2pKit {
    val peerIdStorage = peerIdStorageOverride ?: defaultPeerIdStorage(appId, logger)
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
        permissions = dev.p2pkit.core.permission.NoOpP2pPermissionManager(),
        logger = logger,
        clock = ::systemTimeMillis,
        parentJob = null
    )
}
