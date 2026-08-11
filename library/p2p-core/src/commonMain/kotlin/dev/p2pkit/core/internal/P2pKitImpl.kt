package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.AppKilledPolicy
import dev.p2pkit.core.BackgroundPolicy
import dev.p2pkit.core.FeatureState
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
import dev.p2pkit.core.transport.RegisteredTransportFactory
import dev.p2pkit.core.transport.TransportCapability
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportDescriptor
import dev.p2pkit.core.transport.TransportPair
import dev.p2pkit.core.transport.TransportSecurityProfile
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineExceptionHandler
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.Semaphore
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
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
    private val transportFactories: List<RegisteredTransportFactory>,
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
    private val monotonicClock: () -> Long = clock,
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
    private val strictSessionInvariants: Boolean = false,
    private val sessionSetupTimeoutMillis: Long = DEFAULT_HANDSHAKE_TIMEOUT_MS,
    private val beforeSessionCommitForTest: (suspend () -> Unit)? = null,
    private val afterOutgoingConnectForTest: (suspend () -> Unit)? = null,
    private val afterSessionSetupResultForTest: (suspend () -> Unit)? = null,
    private val discoveryRefreshTimeoutMillis: Long = DEFAULT_DISCOVERY_REFRESH_TIMEOUT_MS,
    private val featureOperationSettleTimeoutMillis: Long =
        DEFAULT_FEATURE_OPERATION_SETTLE_TIMEOUT_MS,
    private val beforeTerminalWatcherRemovalForTest: (suspend () -> Unit)? = null
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

    private val advertisingFeature = FeatureControl()
    override val advertisingState: StateFlow<FeatureState> = advertisingFeature.state

    private val discoveryFeature = FeatureControl()
    override val discoveryState: StateFlow<FeatureState> = discoveryFeature.state

    private val transports: List<TransportPair>
    private val dataTransports: List<DataTransport>
    private val discoveryTransports: List<DiscoveryTransport>

    private val transportManager: TransportManager
    private val securityProfile: TransportSecurityProfile = when (securityMode) {
        is SecurityMode.AuthenticatedV2 -> TransportSecurityProfile.AuthenticatedV2
        SecurityMode.NoneForMvp -> TransportSecurityProfile.LegacyPlaintextV1
    }
    private val protocol = DefaultP2pProtocol(
        // Reassembly expiry is elapsed-time state, not a user-visible
        // timestamp. Wall-clock corrections must not retain hostile partial
        // messages indefinitely or evict a live message prematurely.
        clock = monotonicClock,
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

    /** Prevent overlapping cleanup calls when a broken observer ignores cancellation. */
    private val pathObserverCleanupGate = Semaphore(1)

    /**
     * A failed/timed-out startup rollback means an old listener may still be
     * alive. This kit instance must never call start again over that uncertain
     * ownership; terminal [stop] is the only safe recovery.
     */
    private var startupCleanupBlocker: P2pError.TransportStartFailed? = null

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
    private val stopCompletion = CompletableDeferred<Result<Unit>>()

    init {
        require(featureOperationSettleTimeoutMillis > 0L) {
            "featureOperationSettleTimeoutMillis must be > 0"
        }
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
        transports = transportFactories.map { registration ->
            val descriptor = registration.descriptor
            val pair = try {
                registration.factory.build(ctx)
            } catch (error: P2pError.TransportInitializationFailed) {
                throw error
            } catch (error: Throwable) {
                throw P2pError.TransportInitializationFailed(
                    descriptor.kind,
                    error.message ?: error::class.simpleName ?: "factory build failed",
                    error
                )
            }
            validateTransportPair(descriptor, pair)
            pair
        }
        dataTransports = transports.mapNotNull { it.data }
        discoveryTransports = transports.mapNotNull { it.discovery }
        supportedTransportKinds = transportFactories
            .filter { TransportCapability.DATA in it.descriptor.capabilities }
            .map { it.descriptor.kind }
            .toSet()

        transportManager = TransportManager(dataTransports)
        peerRegistry = PeerRegistry(
            discoveryTransports = discoveryTransports,
            scope = scope,
            clock = clock,
            monotonicClock = monotonicClock,
            logger = logger,
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
            monotonicClock = monotonicClock,
            logger = logger,
            fileTransferConfig = fileTransferConfig,
            setupTimeoutMillis = sessionSetupTimeoutMillis,
            beforeSessionCommitForTest = beforeSessionCommitForTest,
            afterOutgoingConnectForTest = afterOutgoingConnectForTest,
            afterSessionSetupResultForTest = afterSessionSetupResultForTest,
            beforeTerminalWatcherRemovalForTest = beforeTerminalWatcherRemovalForTest,
            discoveryRefreshTimeoutMillis = discoveryRefreshTimeoutMillis,
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
                // transport's own lock. One transport's ordinary failure does
                // not block the others, while caller cancellation remains
                // structural and aborts the reconnect operation.
                discoveryTransports.forEach { transport ->
                    try {
                        transport.refresh()
                    } catch (cancelled: CancellationException) {
                        throw cancelled
                    } catch (failure: Throwable) {
                        logger.warn(
                            "discovery refresh failed for ${transport.type}: " +
                                "${failure::class.simpleName}: ${failure.message ?: ""}"
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
     * call latches `startResult = success`; subsequent callers no-op. An
     * ordinary failed start does not block a retry after its rollback settles,
     * which matters for transient port-exhaustion or `EADDRINUSE` races. A
     * failed/timed-out rollback is different: uncertain native ownership is
     * latched fail-closed until terminal stop.
     *
     * Any per-transport failure surfaces as
     * [P2pError.TransportStartFailed]; we attribute the error to that
     * transport's [DataTransport.type] so the caller can show which medium
     * failed without inspecting the cause's class.
     */
    private suspend fun ensureStarted(generation: Long) {
        currentCoroutineContext().ensureActive()
        requireLifecycleActive(generation)
        startResult?.let { prior ->
            if (prior.isSuccess) return
        }
        startMutex.withLock {
            requireLifecycleActive(generation)
            startupCleanupBlocker?.let { throw it }
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
            val attempted = mutableListOf<DataTransport>()
            var observerMayHaveStarted = false
            try {
                for (transport in dataTransports) {
                    // AUDIT-2026-07 (ARCH-1): rethrow cancellation before any
                    // wrapping or latching. The whole startup transaction's
                    // outer handler rolls back every resource entered by the
                    // attempt, including this transport when a platform bind
                    // acquired a listener before observing cancellation.
                    attempted += transport
                    val r = try {
                        transport.start()
                    } catch (e: CancellationException) {
                        throw e
                    } catch (e: Throwable) {
                        Result.failure(e)
                    }
                    // Platform code can acquire a listener, cancel its caller,
                    // and return without another suspension. Observe that
                    // cancellation before treating the returned resource as a
                    // successful lifecycle commit.
                    currentCoroutineContext().ensureActive()
                    if (!isLifecycleActive(generation)) {
                        cleanupLateStart(
                            observerMayHaveStarted = false,
                            dataMayHaveStartedLate = true
                        )
                        throw lifecycleStoppedFailure()
                    }
                    if (r.isFailure) {
                        val cause = r.exceptionOrNull()
                        val startFailure = P2pError.TransportStartFailed(
                            transportKind = transport.type,
                            reason = cause?.message ?: "transport.start() returned failure",
                            underlying = cause
                        )
                        val rollbackIssues = rollbackDataStartup(attempted)
                        val failureToReport = if (rollbackIssues.isEmpty()) {
                            startFailure
                        } else {
                            startupRollbackFailure(
                                transport.type,
                                "failed data startup",
                                rollbackIssues
                            ).also { blocker ->
                                blocker.addSuppressed(startFailure)
                                startupCleanupBlocker = blocker
                            }
                        }
                        val committed = commitLifecycle(generation) {
                            startResult = Result.failure(failureToReport)
                            _state.value = P2pState.Failed(failureToReport)
                        }
                        if (!committed) {
                            cleanupLateStart(
                                observerMayHaveStarted = false,
                                dataMayHaveStartedLate = true
                            )
                            throw lifecycleStoppedFailure()
                        }
                        throw failureToReport
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
                // Best-effort path observer startup. A cleanly detached ordinary
                // failure degrades to no observer for this kit session. An
                // observer that cannot prove cleanup may still own a native
                // callback, so roll back data startup and latch fail-closed rather
                // than attaching a second monitor on retry. Cancellation of the
                // calling coroutine remains structural and propagates unchanged.
                observerMayHaveStarted = true
                val observedPathStatus: StateFlow<NetworkPathStatus>? = try {
                    pathObserver.start()
                    // Capture the successfully attached stream before publishing
                    // Running. A custom observer whose accessor itself fails is
                    // handled as the same partial-acquisition transaction.
                    pathObserver.status.also {
                        currentCoroutineContext().ensureActive()
                    }
                } catch (e: CancellationException) {
                    throw e
                } catch (e: Throwable) {
                    logger.warn(
                        "NetworkPathObserver.start() failed; path-change recovery disabled for this session",
                        e
                    )
                    val observerIssue = cleanupStalePathObserver("network path observer startup")
                    if (observerIssue == null) {
                        observerMayHaveStarted = false
                        null
                    } else {
                        val rollbackIssues = buildList {
                            add(observerIssue)
                            addAll(rollbackDataStartup(attempted))
                        }
                        val blocker = startupRollbackFailure(
                            transportFactories.first().descriptor.kind,
                            "failed network-path observer startup",
                            rollbackIssues
                        ).also { failure ->
                            failure.addSuppressed(e)
                            startupCleanupBlocker = failure
                        }
                        val failureCommitted = commitLifecycle(generation) {
                            startResult = Result.failure(blocker)
                            _state.value = P2pState.Failed(blocker)
                        }
                        if (!failureCommitted) {
                            cleanupLateStart(
                                observerMayHaveStarted = true,
                                dataMayHaveStartedLate = true
                            )
                            throw lifecycleStoppedFailure()
                        }
                        throw blocker
                    }
                }
                currentCoroutineContext().ensureActive()
                val committed = commitLifecycle(generation) {
                    // Subscribe SessionManager to path changes only while the
                    // generation is still active. stop() cannot latch terminal
                    // between this check and the final Running publication.
                    if (observedPathStatus != null) {
                        scope.launch {
                            observedPathStatus.collect { status ->
                                sessionManager.applyPathChange(status)
                            }
                        }
                    }
                    startResult = Result.success(Unit)
                    _state.value = P2pState.Running
                }
                if (!committed) {
                    cleanupLateStart(
                        observerMayHaveStarted = observedPathStatus != null,
                        dataMayHaveStartedLate = false
                    )
                    throw lifecycleStoppedFailure()
                }
            } catch (cancelled: CancellationException) {
                settleCancelledStartup(
                    generation = generation,
                    attempted = attempted,
                    observerMayHaveStarted = observerMayHaveStarted,
                    cancellation = cancelled
                )
                throw cancelled
            }
        }
    }

    override suspend fun startAdvertising() {
        val localInfo = LocalPeerInfo(
            peerId = localPeerId,
            deviceName = deviceName,
            platform = localPlatform,
            appId = appId,
            supportedTransports = supportedTransportKinds,
            securityProfile = securityProfile,
            fingerprint = localFingerprint
        )
        startFeature(
            control = advertisingFeature,
            featureName = "advertising",
            unsupportedReason = "No registered transport supports advertising",
            startTransport = { it.startAdvertising(localInfo) },
            stopTransport = { it.stopAdvertising() }
        )
    }

    override suspend fun stopAdvertising() {
        stopFeature(advertisingFeature, "advertising") { it.stopAdvertising() }
    }

    override suspend fun startDiscovery() {
        startFeature(
            control = discoveryFeature,
            featureName = "discovery",
            unsupportedReason = "No registered transport supports discovery",
            startTransport = { it.startDiscovery() },
            stopTransport = { it.stopDiscovery() }
        )
    }

    override suspend fun stopDiscovery() {
        stopFeature(discoveryFeature, "discovery") { it.stopDiscovery() }
    }

    private suspend fun startFeature(
        control: FeatureControl,
        featureName: String,
        unsupportedReason: String,
        startTransport: suspend (DiscoveryTransport) -> Unit,
        stopTransport: suspend (DiscoveryTransport) -> Unit
    ) {
        control.operationMutex.withLock {
            currentCoroutineContext().ensureActive()
            val lifecycleGeneration = beginLifecycleOperation()
            val start = lifecycleMutex.withLock {
                if (!lifecycleIsActiveLocked(lifecycleGeneration)) throw lifecycleStoppedFailure()
                if (control.mutableState.value == FeatureState.Active) return@withLock null
                val token = ++control.nextStartToken
                control.activeStartToken = token
                control.stopRequestedToken = null
                control.mutableState.value = FeatureState.Starting
                FeatureStart(token, control.cleanupRequired)
            } ?: return

            val attempted = mutableListOf<DiscoveryTransport>()
            var cancellationSettledByFailureHandler = false
            try {
                if (start.cleanupRequired) {
                    // If cancellation interrupts preparation, the outer
                    // transaction handler retries every possibly retained
                    // discovery resource before settling the public state.
                    attempted += discoveryTransports
                    val cleanupIssues = stopDiscoveryResources(
                        "prepare $featureName retry",
                        preserveCancellation = false,
                        cleanup = stopTransport
                    )
                    if (cleanupIssues.isNotEmpty()) {
                        val cleanupFailure = cleanupError("prepare $featureName retry", cleanupIssues)
                        finishFeatureStart(
                            control,
                            start.token,
                            FeatureState.Failed(cleanupFailure),
                            cleanupRequired = true
                        )
                        throw cleanupFailure
                    }
                    lifecycleMutex.withLock {
                        if (control.activeStartToken == start.token) control.cleanupRequired = false
                    }
                    attempted.clear()
                }

                if (
                    handleRequestedFeatureStop(
                        control,
                        start.token,
                        featureName,
                        emptyList(),
                        stopTransport
                    )
                ) {
                    return
                }

                // Static support is authoritative and does not depend on a
                // momentary permission/radio state. Report it before querying
                // runtime availability so an absent provider cannot be mistaken
                // for a recoverable permission failure.
                if (discoveryTransports.isEmpty()) {
                    when (
                        completeFeatureStart(
                            control,
                            start.token,
                            FeatureState.Unsupported(unsupportedReason)
                        )
                    ) {
                        FeatureCompletion.Applied -> return
                        FeatureCompletion.StopRequested -> {
                            handleRequestedFeatureStop(
                                control,
                                start.token,
                                featureName,
                                emptyList(),
                                stopTransport
                            )
                            return
                        }
                        FeatureCompletion.LifecycleStopped -> throw lifecycleStoppedFailure()
                        FeatureCompletion.Stale -> throw staleFeatureOperation(featureName)
                    }
                }

                // Only genuinely runtime-requestable permissions participate.
                // Install-time manifest declarations remain construction-time
                // diagnostics and cannot be repaired by a runtime prompt.
                val missing = try {
                    permissions.missingPermissions().also {
                        currentCoroutineContext().ensureActive()
                    }
                } catch (error: Throwable) {
                    cancellationSettledByFailureHandler = error is CancellationException
                    failFeatureStart(
                        control,
                        start.token,
                        lifecycleGeneration,
                        featureName,
                        emptyList(),
                        stopTransport,
                        error
                    )
                }
                if (
                    handleRequestedFeatureStop(
                        control,
                        start.token,
                        featureName,
                        emptyList(),
                        stopTransport
                    )
                ) {
                    return
                }
                if (missing.isNotEmpty()) {
                    when (
                        completeFeatureStart(
                            control,
                            start.token,
                            FeatureState.PermissionRequired(missing)
                        )
                    ) {
                        FeatureCompletion.Applied -> throw P2pError.PermissionMissing(missing)
                        FeatureCompletion.StopRequested -> {
                            handleRequestedFeatureStop(
                                control,
                                start.token,
                                featureName,
                                emptyList(),
                                stopTransport
                            )
                            return
                        }
                        FeatureCompletion.LifecycleStopped -> throw lifecycleStoppedFailure()
                        FeatureCompletion.Stale -> throw staleFeatureOperation(featureName)
                    }
                }

                try {
                    ensureStarted(lifecycleGeneration)
                    currentCoroutineContext().ensureActive()
                } catch (error: Throwable) {
                    cancellationSettledByFailureHandler = error is CancellationException
                    failFeatureStart(
                        control,
                        start.token,
                        lifecycleGeneration,
                        featureName,
                        emptyList(),
                        stopTransport,
                        error
                    )
                }
                if (
                    handleRequestedFeatureStop(
                        control,
                        start.token,
                        featureName,
                        emptyList(),
                        stopTransport
                    )
                ) {
                    return
                }

                for (transport in discoveryTransports) {
                    if (!isLifecycleActive(lifecycleGeneration)) {
                        rollbackDiscoveryOperation(featureName, attempted, stopTransport)
                        throw lifecycleStoppedFailure()
                    }
                    if (
                        handleRequestedFeatureStop(
                            control,
                            start.token,
                            featureName,
                            attempted,
                            stopTransport
                        )
                    ) {
                        return
                    }
                    attempted += transport
                    try {
                        startTransport(transport)
                        currentCoroutineContext().ensureActive()
                    } catch (error: Throwable) {
                        cancellationSettledByFailureHandler = error is CancellationException
                        failFeatureStart(
                            control,
                            start.token,
                            lifecycleGeneration,
                            featureName,
                            attempted,
                            stopTransport,
                            error
                        )
                    }
                    if (
                        handleRequestedFeatureStop(
                            control,
                            start.token,
                            featureName,
                            attempted,
                            stopTransport
                        )
                    ) {
                        return
                    }
                }

                currentCoroutineContext().ensureActive()
                when (completeFeatureStart(control, start.token, FeatureState.Active)) {
                    FeatureCompletion.Applied -> Unit
                    FeatureCompletion.StopRequested -> {
                        handleRequestedFeatureStop(
                            control,
                            start.token,
                            featureName,
                            attempted,
                            stopTransport
                        )
                    }
                    FeatureCompletion.LifecycleStopped -> {
                        rollbackDiscoveryOperation(featureName, attempted, stopTransport)
                        throw lifecycleStoppedFailure()
                    }
                    FeatureCompletion.Stale -> {
                        rollbackDiscoveryOperation(featureName, attempted, stopTransport)
                        throw staleFeatureOperation(featureName)
                    }
                }
            } catch (cancelled: CancellationException) {
                if (cancellationSettledByFailureHandler) throw cancelled
                val startStillOwned = withContext(NonCancellable) {
                    lifecycleMutex.withLock {
                        !stopped && control.activeStartToken == start.token
                    }
                }
                if (startStillOwned) {
                    failFeatureStart(
                        control = control,
                        token = start.token,
                        lifecycleGeneration = lifecycleGeneration,
                        featureName = featureName,
                        attempted = attempted,
                        stopTransport = stopTransport,
                        error = cancelled
                    )
                }
                val issues = rollbackDiscoveryOperation(featureName, attempted, stopTransport)
                if (issues.isNotEmpty()) {
                    cancelled.addSuppressed(cleanupError("cancel stale $featureName startup", issues))
                }
                throw cancelled
            }
        }
    }

    private suspend fun stopFeature(
        control: FeatureControl,
        featureName: String,
        stopTransport: suspend (DiscoveryTransport) -> Unit
    ) {
        val request = lifecycleMutex.withLock {
            if (stopped) throw lifecycleStoppedFailure()
            when (control.mutableState.value) {
                FeatureState.Idle -> return
                is FeatureState.PermissionRequired,
                is FeatureState.Unsupported -> {
                    control.mutableState.value = FeatureState.Idle
                    control.cleanupRequired = false
                    return
                }
                else -> {
                    control.stopCompletion?.let { existing ->
                        return@withLock FeatureStopRequest.Join(existing)
                    }
                    val completion = CompletableDeferred<Result<Unit>>()
                    control.stopCompletion = completion
                    control.stopRequestedToken = control.activeStartToken
                    control.mutableState.value = FeatureState.Stopping
                    FeatureStopRequest.Own(
                        lifecycleGeneration = this@P2pKitImpl.lifecycleGeneration,
                        completion = completion
                    )
                }
            }
        }
        if (request is FeatureStopRequest.Join) {
            request.completion.await().getOrThrow()
            return
        }
        request as FeatureStopRequest.Own
        val lifecycleGeneration = request.lifecycleGeneration
        var terminalFailure: Throwable? = null

        try {
            withContext(NonCancellable) {
                val operationSettled = control.operationMutex.acquireWithin(
                    featureOperationSettleTimeoutMillis
                )
                if (!operationSettled) {
                    val cleanupIssues = stopDiscoveryResources(
                        "stop $featureName after startup-settle timeout",
                        preserveCancellation = false,
                        cleanup = stopTransport
                    )
                    val timeoutIssue = CleanupIssue(
                        resource = "$featureName startup operation",
                        cause = IllegalStateException(
                            "$featureName startup did not settle within " +
                                "${featureOperationSettleTimeoutMillis}ms"
                        ),
                        deadlineExceeded = true
                    )
                    val failure = cleanupError(
                        "stop $featureName",
                        listOf(timeoutIssue) + cleanupIssues
                    )
                    lifecycleMutex.withLock {
                        if (lifecycleIsActiveLocked(lifecycleGeneration)) {
                            // Invalidate the late start token. If the original
                            // startup eventually returns, its stale completion
                            // path performs a second idempotent rollback.
                            control.activeStartToken = null
                            control.stopRequestedToken = null
                            control.cleanupRequired = true
                            control.mutableState.value = FeatureState.Failed(failure)
                        }
                    }
                    throw failure
                }
                try {
                    val needsCleanup = lifecycleMutex.withLock {
                        if (!lifecycleIsActiveLocked(lifecycleGeneration)) throw lifecycleStoppedFailure()
                        control.mutableState.value != FeatureState.Idle
                    }
                    if (needsCleanup) {
                        val issues = stopDiscoveryResources(
                            "stop $featureName",
                            preserveCancellation = false,
                            cleanup = stopTransport
                        )
                        val failure = issues.takeIf { it.isNotEmpty() }
                            ?.let { cleanupError("stop $featureName", it) }
                        lifecycleMutex.withLock {
                            if (lifecycleIsActiveLocked(lifecycleGeneration)) {
                                control.activeStartToken = null
                                control.stopRequestedToken = null
                                control.cleanupRequired = failure != null
                                control.mutableState.value = if (failure == null) {
                                    FeatureState.Idle
                                } else {
                                    FeatureState.Failed(failure)
                                }
                            }
                        }
                        if (failure != null) throw failure
                    }
                } finally {
                    control.operationMutex.unlock()
                }
            }
        } catch (failure: Throwable) {
            terminalFailure = failure
            throw failure
        } finally {
            withContext(NonCancellable) {
                lifecycleMutex.withLock {
                    if (control.stopCompletion === request.completion) {
                        control.stopCompletion = null
                    }
                }
                request.completion.complete(
                    terminalFailure?.let { Result.failure(it) } ?: Result.success(Unit)
                )
            }
        }
    }

    private suspend fun handleRequestedFeatureStop(
        control: FeatureControl,
        token: Long,
        featureName: String,
        attempted: List<DiscoveryTransport>,
        stopTransport: suspend (DiscoveryTransport) -> Unit
    ): Boolean {
        val checkpoint = lifecycleMutex.withLock {
            when {
                stopped -> FeatureStartCheckpoint.LifecycleStopped
                control.activeStartToken != token -> FeatureStartCheckpoint.Stale
                control.stopRequestedToken == token -> FeatureStartCheckpoint.StopRequested
                else -> FeatureStartCheckpoint.Continue
            }
        }
        if (checkpoint == FeatureStartCheckpoint.Continue) return false

        val issues = rollbackDiscoveryOperation(featureName, attempted, stopTransport)
        if (checkpoint == FeatureStartCheckpoint.Stale) {
            // A bounded explicit stop invalidated this start token while one
            // transport callback was still running. Never proceed to the next
            // transport; the public Failed state and cleanupRequired marker
            // belong to the stop owner and remain authoritative.
            if (issues.isNotEmpty()) {
                logCleanupIssues(logger, "stale $featureName startup rollback", issues)
            }
            throw staleFeatureOperation(featureName)
        }
        if (checkpoint == FeatureStartCheckpoint.LifecycleStopped) {
            if (issues.isNotEmpty()) {
                logCleanupIssues(logger, "terminal $featureName startup rollback", issues)
            }
            throw lifecycleStoppedFailure()
        }

        val failure = issues.takeIf { it.isNotEmpty() }
            ?.let { cleanupError("stop $featureName during startup", it) }
        finishFeatureStart(
            control,
            token,
            failure?.let { FeatureState.Failed(it) } ?: FeatureState.Idle,
            cleanupRequired = failure != null
        )
        if (failure != null) throw failure
        return true
    }

    private suspend fun failFeatureStart(
        control: FeatureControl,
        token: Long,
        lifecycleGeneration: Long,
        featureName: String,
        attempted: List<DiscoveryTransport>,
        stopTransport: suspend (DiscoveryTransport) -> Unit,
        error: Throwable
    ): Nothing {
        val issues = rollbackDiscoveryOperation(featureName, attempted, stopTransport)
        val lifecycleActive = withContext(NonCancellable) {
            isLifecycleActive(lifecycleGeneration)
        }
        if (!lifecycleActive) throw lifecycleStoppedFailure()

        if (error is CancellationException) {
            val cleanupFailure = issues.takeIf { it.isNotEmpty() }
                ?.let { cleanupError("cancel $featureName startup", it) }
            withContext(NonCancellable) {
                finishFeatureStart(
                    control,
                    token,
                    cleanupFailure?.let { FeatureState.Failed(it) } ?: FeatureState.Idle,
                    cleanupRequired = cleanupFailure != null
                )
            }
            throw error
        }

        val baseError = if (error is P2pError) {
            error
        } else {
            P2pError.ConnectionFailed(
                "start $featureName failed: ${error.message ?: error::class.simpleName}"
            ).also { it.underlying = error }
        }
        val publicError = if (issues.isEmpty()) {
            baseError
        } else {
            P2pError.ConnectionFailed(
                "start $featureName failed and rollback left ${issues.size} cleanup failure(s)"
            ).also {
                it.underlying = CleanupAggregateException(
                    "start $featureName and rollback",
                    listOf(CleanupIssue("start $featureName", error)) + issues
                )
            }
        }
        val stopWasRequested = lifecycleMutex.withLock {
            control.activeStartToken == token && control.stopRequestedToken == token
        }
        finishFeatureStart(
            control,
            token,
            if (stopWasRequested && issues.isEmpty()) FeatureState.Idle else FeatureState.Failed(publicError),
            cleanupRequired = issues.isNotEmpty()
        )
        throw publicError
    }

    private suspend fun completeFeatureStart(
        control: FeatureControl,
        token: Long,
        state: FeatureState
    ): FeatureCompletion = lifecycleMutex.withLock {
        when {
            stopped -> FeatureCompletion.LifecycleStopped
            control.activeStartToken != token -> FeatureCompletion.Stale
            control.stopRequestedToken == token -> {
                control.mutableState.value = FeatureState.Stopping
                FeatureCompletion.StopRequested
            }
            else -> {
                control.activeStartToken = null
                control.stopRequestedToken = null
                control.cleanupRequired = false
                control.mutableState.value = state
                FeatureCompletion.Applied
            }
        }
    }

    private suspend fun finishFeatureStart(
        control: FeatureControl,
        token: Long,
        state: FeatureState,
        cleanupRequired: Boolean
    ) {
        lifecycleMutex.withLock {
            if (!stopped && control.activeStartToken == token) {
                control.activeStartToken = null
                control.stopRequestedToken = null
                control.cleanupRequired = cleanupRequired
                control.mutableState.value = state
            }
        }
    }

    private fun staleFeatureOperation(featureName: String): IllegalStateException =
        IllegalStateException("Stale $featureName lifecycle operation")

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
                    stopFeatureForBackground("advertising", ::stopAdvertising)
                    stopFeatureForBackground("discovery", ::stopDiscovery)
                }
                sessionManager.applyBackgroundPolicy(backgroundPolicy)
            }
            is BackgroundPolicy.KeepRunning -> { /* nothing to do */ }
        }
    }

    private suspend fun stopFeatureForBackground(
        featureName: String,
        stopFeature: suspend () -> Unit
    ) {
        try {
            stopFeature()
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (failure: Throwable) {
            logger.warn("Background $featureName stop failed", failure)
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
                    markFeatureStoppingForKit(advertisingFeature)
                    markFeatureStoppingForKit(discoveryFeature)
                    true
                }
            }
        }
        if (!ownsTeardown) {
            // Idempotent concurrent callers observe completion of the same
            // teardown instead of returning while the first caller still owns
            // live resources.
            val result = withContext(NonCancellable) {
                val leaderResult = stopCompletion.await()
                // Preserve the secure-identity fail-closed retry contract: if
                // the leader retained the lease because a child ignored its
                // bound, a later idempotent stop gets another bounded join.
                val retryIssues = finishIdentityOwnershipTeardown()
                if (retryIssues.isEmpty() || leaderResult.isFailure) {
                    leaderResult
                } else {
                    logCleanupIssues(logger, "stop", retryIssues)
                    Result.failure(cleanupError("stop", retryIssues))
                }
            }
            result.getOrThrow()
            return
        }
        // NonCancellable: `stopped` latches at entry, so if the caller's
        // coroutine were cancelled mid-teardown the kit would be permanently
        // half-stopped (transports bound, scope alive) with every later
        // stop() a no-op. Each resource attempt is independently bounded and
        // retained in the aggregate result, so one bad close cannot abort the
        // remainder of teardown.
        val result = withContext(NonCancellable) {
            val issues = mutableListOf<CleanupIssue>()
            try {
                // startMutex: a concurrent ensureStarted mid-bind must not
                // interleave with teardown. Bound acquisition so a broken
                // transport start cannot park terminal stop forever.
                val acquiredStartMutex = startMutex.acquireWithin(STOP_START_MUTEX_TIMEOUT_MS)
                if (!acquiredStartMutex) {
                    logger.warn(
                        "stop(): startMutex not released within ${STOP_START_MUTEX_TIMEOUT_MS}ms " +
                            "(a transport start() is likely hung); tearing down without the lock"
                    )
                    issues += CleanupIssue(
                        "transport startup transaction",
                        IllegalStateException(
                            "start mutex was not released within ${STOP_START_MUTEX_TIMEOUT_MS}ms"
                        )
                    )
                    issues += teardownBoundResources()
                } else {
                    try {
                        issues += teardownBoundResources()
                    } finally {
                        startMutex.unlock()
                    }
                }

                capturePathObserverCleanupIssue(
                    resource = "network path observer",
                    timeoutMillis = OBSERVER_CLOSE_TIMEOUT_MS
                )?.let(issues::add)
            } catch (failure: Throwable) {
                issues += CleanupIssue("terminal teardown", failure)
            } finally {
                issues += finishIdentityOwnershipTeardown()
                _state.value = P2pState.Stopped
            }
            logCleanupIssues(logger, "stop", issues)
            val completed = if (issues.isEmpty()) {
                Result.success(Unit)
            } else {
                Result.failure(cleanupError("stop", issues))
            }
            stopCompletion.complete(completed)
            completed
        }
        result.getOrThrow()
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
                cleanupStalePathObserver("network path observer")
            }
            if (dataMayHaveStartedLate) {
                for (transport in dataTransports.asReversed()) {
                    cleanupStaleResource("${transport.type} data transport") { transport.close() }
                }
            }
        }
    }

    private suspend fun rollbackDiscoveryOperation(
        operation: String,
        attempted: List<DiscoveryTransport>,
        cleanup: suspend (DiscoveryTransport) -> Unit
    ): List<CleanupIssue> {
        val issues = mutableListOf<CleanupIssue>()
        withContext(NonCancellable) {
            for (transport in attempted.asReversed()) {
                cleanupStaleResource("${transport.type} $operation") {
                    cleanup(transport)
                }?.let(issues::add)
            }
        }
        return issues
    }

    /**
     * Undo one partial multi-transport startup without terminally disposing
     * the transport instances. Every entered transport is attempted in
     * reverse order, including the transport whose `start()` failed after
     * acquiring a platform handle.
     */
    private suspend fun rollbackDataStartup(attempted: List<DataTransport>): List<CleanupIssue> {
        val issues = mutableListOf<CleanupIssue>()
        withContext(NonCancellable) {
            for (transport in attempted.asReversed()) {
                cleanupStaleResource("${transport.type} data startup") {
                    transport.stop()
                }?.let(issues::add)
            }
        }
        return issues
    }

    /**
     * Settle cancellation at any point after startup entered its resource
     * transaction, including lifecycle-gate suspension after a platform
     * `start()` already returned. Keeping this compensation outside the
     * individual transport/observer calls closes the otherwise uncovered
     * return-to-final-commit cancellation window.
     */
    private suspend fun settleCancelledStartup(
        generation: Long,
        attempted: List<DataTransport>,
        observerMayHaveStarted: Boolean,
        cancellation: CancellationException
    ) {
        withContext(NonCancellable) {
            if (!isLifecycleActive(generation)) {
                cleanupLateStart(
                    observerMayHaveStarted = observerMayHaveStarted,
                    dataMayHaveStartedLate = attempted.isNotEmpty()
                )
                return@withContext
            }

            val rollbackIssues = buildList {
                if (observerMayHaveStarted) {
                    cleanupStalePathObserver("network path observer startup")?.let(::add)
                }
                addAll(rollbackDataStartup(attempted))
            }
            val operation = if (observerMayHaveStarted) {
                "cancelled network-path observer startup"
            } else {
                "cancelled data startup"
            }
            val blocker = rollbackIssues.takeIf { it.isNotEmpty() }?.let { issues ->
                startupRollbackFailure(
                    attempted.lastOrNull()?.type ?: transportFactories.first().descriptor.kind,
                    operation,
                    issues
                )
            }
            if (blocker != null) {
                startupCleanupBlocker = blocker
                cancellation.addSuppressed(blocker)
            }
            val committed = commitLifecycle(generation) {
                startResult = blocker?.let { Result.failure(it) }
                _state.value = blocker?.let(P2pState::Failed) ?: P2pState.Idle
            }
            if (!committed) {
                cleanupLateStart(
                    observerMayHaveStarted = observerMayHaveStarted,
                    dataMayHaveStartedLate = attempted.isNotEmpty()
                )
            }
        }
    }

    private fun startupRollbackFailure(
        transportKind: TransportKind,
        operation: String,
        issues: List<CleanupIssue>
    ): P2pError.TransportStartFailed {
        val aggregate = CleanupAggregateException(operation, issues.toList())
        return P2pError.TransportStartFailed(
            transportKind = transportKind,
            reason = "$operation cleanup was incomplete; call stop() and replace this P2pKit instance",
            underlying = aggregate
        )
    }

    private suspend fun cleanupStaleResource(
        label: String,
        cleanup: suspend () -> Unit
    ): CleanupIssue? {
        // A structured withTimeout cannot bound a platform cleanup that enters
        // NonCancellable or blocks in native I/O: it still waits for that child
        // after the deadline. Use the same independently-owned attempt as
        // terminal teardown so a cancelled start/feature operation always
        // settles its public lifecycle transaction.
        val issue = captureCleanupIssue(
            resource = label,
            timeoutMillis = STALE_OPERATION_CLEANUP_TIMEOUT_MS,
            preserveCancellation = false,
            cleanup = cleanup
        )
        if (issue != null) {
            logger.warn("Late lifecycle cleanup failed for $label", issue.cause)
        }
        return issue
    }

    private suspend fun cleanupStalePathObserver(label: String): CleanupIssue? {
        val issue = capturePathObserverCleanupIssue(
            resource = label,
            timeoutMillis = STALE_OPERATION_CLEANUP_TIMEOUT_MS
        )
        if (issue != null) {
            logger.warn("Late lifecycle cleanup failed for $label", issue.cause)
        }
        return issue
    }

    private suspend fun capturePathObserverCleanupIssue(
        resource: String,
        timeoutMillis: Long
    ): CleanupIssue? = captureCleanupIssue(
        resource = resource,
        timeoutMillis = timeoutMillis,
        preserveCancellation = false,
        operationGate = pathObserverCleanupGate
    ) {
        pathObserver.close()
    }

    /**
     * Clear the in-memory private key immediately, but release destructive
     * reset exclusion only after every kit child has terminated. If a broken
     * child ignores cancellation, retaining the idempotent usage token is the
     * required fail-closed behavior; a later stop() call retries the join.
     */
    private suspend fun finishIdentityOwnershipTeardown(): List<CleanupIssue> {
        val issues = mutableListOf<CleanupIssue>()
        try {
            localSecureIdentity?.clearPrivate()
        } catch (failure: Throwable) {
            issues += CleanupIssue("in-memory secure identity", failure)
        }
        internalJob.cancel()
        val childrenStopped = withTimeoutOrNull(INTERNAL_JOB_CLOSE_TIMEOUT_MS) {
            internalJob.cancelAndJoin()
            true
        } ?: false
        if (childrenStopped) {
            try {
                secureIdentityUsage?.release()
            } catch (failure: Throwable) {
                issues += CleanupIssue("secure identity usage lease", failure)
            }
        } else {
            issues += CleanupIssue(
                "internal coroutine scope",
                IllegalStateException(
                    "children did not terminate within ${INTERNAL_JOB_CLOSE_TIMEOUT_MS}ms"
                )
            )
        }
        return issues
    }

    /**
     * The teardown body shared by [stop]'s locked (normal) and lock-less
     * (mutex-starved) paths. Every step is bounded and idempotent
     * (sessions/transports tolerate double close), so the rare interleavings —
     * two concurrent first `stop()` calls, or the timeout firing mid-teardown
     * and the fallback re-running it — are safe.
     */
    private suspend fun teardownBoundResources(): List<CleanupIssue> {
        val issues = mutableListOf<CleanupIssue>()
        val advertisingIssues = stopDiscoveryResources("stop advertising", preserveCancellation = false) {
            it.stopAdvertising()
        }
        finishTerminalFeatureTeardown(advertisingFeature, "stop advertising", advertisingIssues)
        issues += advertisingIssues
        val discoveryIssues = stopDiscoveryResources("stop discovery", preserveCancellation = false) {
            it.stopDiscovery()
        }
        finishTerminalFeatureTeardown(discoveryFeature, "stop discovery", discoveryIssues)
        issues += discoveryIssues
        // Discovery/manual entries are process-local runtime state. Seal the
        // registry before clearing it so a late native discovery callback
        // cannot repopulate `peers` after the kit has begun terminal stop.
        peerRegistry.close()
        issues += sessionManager.shutdownAllSessions()
        captureCleanupIssue(
            resource = "network provisioning manager",
            timeoutMillis = RESOURCE_CLOSE_TIMEOUT_MS,
            preserveCancellation = false
        ) {
            networkProvisioning.close()
        }?.let(issues::add)
        for (transport in dataTransports) {
            captureCleanupIssue(
                resource = "${transport.type} data transport",
                timeoutMillis = RESOURCE_CLOSE_TIMEOUT_MS,
                preserveCancellation = false
            ) {
                transport.close()
            }?.let(issues::add)
        }
        return issues
    }

    private fun markFeatureStoppingForKit(control: FeatureControl) {
        control.stopRequestedToken = control.activeStartToken
        if (control.mutableState.value != FeatureState.Idle) {
            control.mutableState.value = FeatureState.Stopping
        }
    }

    private fun finishTerminalFeatureTeardown(
        control: FeatureControl,
        operation: String,
        issues: List<CleanupIssue>
    ) {
        control.activeStartToken = null
        control.stopRequestedToken = null
        control.cleanupRequired = issues.isNotEmpty()
        control.mutableState.value = if (issues.isEmpty()) {
            FeatureState.Idle
        } else {
            FeatureState.Failed(cleanupError(operation, issues))
        }
    }

    private suspend fun stopDiscoveryResources(
        operation: String,
        preserveCancellation: Boolean = true,
        cleanup: suspend (DiscoveryTransport) -> Unit
    ): List<CleanupIssue> {
        val issues = mutableListOf<CleanupIssue>()
        for (transport in discoveryTransports) {
            captureCleanupIssue(
                resource = "${transport.type} discovery transport",
                timeoutMillis = RESOURCE_CLOSE_TIMEOUT_MS,
                preserveCancellation = preserveCancellation
            ) {
                cleanup(transport)
            }?.let(issues::add)
        }
        logCleanupIssues(logger, operation, issues)
        return issues
    }

    private fun validateTransportPair(
        descriptor: TransportDescriptor,
        pair: TransportPair
    ) {
        val declaresData = TransportCapability.DATA in descriptor.capabilities
        val declaresDiscovery = TransportCapability.DISCOVERY in descriptor.capabilities
        val reason = when {
            declaresData != (pair.data != null) ->
                "descriptor DATA=$declaresData but built data path=${pair.data != null}"
            declaresDiscovery != (pair.discovery != null) ->
                "descriptor DISCOVERY=$declaresDiscovery but built discovery path=${pair.discovery != null}"
            pair.data != null && pair.data.type != descriptor.kind ->
                "descriptor kind ${descriptor.kind} does not match data kind ${pair.data.type}"
            pair.discovery != null && pair.discovery.type != descriptor.kind ->
                "descriptor kind ${descriptor.kind} does not match discovery kind ${pair.discovery.type}"
            else -> null
        }
        if (reason != null) {
            throw P2pError.TransportInitializationFailed(descriptor.kind, reason)
        }
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

        /**
         * Per-resource close bound for terminal and explicit feature teardown.
         * JmDNS 3.6.3's graceful unregister contract waits up to 5 seconds
         * for its canceler state, so a shorter generic deadline falsely
         * reports a healthy LAN goodbye as a leak and cancels the coroutine
         * while it still owns the discovery mutex. The independent cleanup
         * owner still guarantees that a genuinely hung resource cannot hold
         * stop beyond this deadline.
         */
        const val RESOURCE_CLOSE_TIMEOUT_MS: Long = 6_000
    }
}

private class FeatureControl {
    val operationMutex: Mutex = Mutex()
    val mutableState: MutableStateFlow<FeatureState> = MutableStateFlow(FeatureState.Idle)
    val state: StateFlow<FeatureState> = mutableState.asStateFlow()

    /** Guarded by P2pKitImpl.lifecycleMutex, except after terminal stop owns teardown. */
    var nextStartToken: Long = 0L

    /** Guarded by P2pKitImpl.lifecycleMutex, except after terminal stop owns teardown. */
    var activeStartToken: Long? = null

    /** Guarded by P2pKitImpl.lifecycleMutex, except after terminal stop owns teardown. */
    var stopRequestedToken: Long? = null

    /** Guarded by P2pKitImpl.lifecycleMutex, except after terminal stop owns teardown. */
    var cleanupRequired: Boolean = false

    /** Exact result shared by concurrent explicit feature-stop callers. */
    var stopCompletion: CompletableDeferred<Result<Unit>>? = null
}

private data class FeatureStart(
    val token: Long,
    val cleanupRequired: Boolean
)

private sealed interface FeatureStopRequest {
    class Own(
        val lifecycleGeneration: Long,
        val completion: CompletableDeferred<Result<Unit>>
    ) : FeatureStopRequest

    class Join(
        val completion: CompletableDeferred<Result<Unit>>
    ) : FeatureStopRequest
}

/** Bounds how long explicit feature stop waits for a concurrent start owner. */
internal const val DEFAULT_FEATURE_OPERATION_SETTLE_TIMEOUT_MS: Long = 6_000

private enum class FeatureCompletion {
    Applied,
    StopRequested,
    LifecycleStopped,
    Stale
}

private enum class FeatureStartCheckpoint {
    Continue,
    StopRequested,
    LifecycleStopped,
    Stale
}

/**
 * Builds a [P2pKitImpl] from collected DSL configuration. Called by
 * [dev.p2pkit.core.dsl.P2pKitBuilder.build]. Public so the DSL package can
 * reach it; internal-by-convention to the SDK.
 */
internal fun newP2pKit(
    appId: AppId,
    deviceName: String,
    transportFactories: List<RegisteredTransportFactory>,
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
    strictSessionInvariants: Boolean = false,
    sessionSetupTimeoutMillis: Long = DEFAULT_HANDSHAKE_TIMEOUT_MS,
    beforeSessionCommitForTest: (suspend () -> Unit)? = null,
    afterOutgoingConnectForTest: (suspend () -> Unit)? = null,
    afterSessionSetupResultForTest: (suspend () -> Unit)? = null,
    discoveryRefreshTimeoutMillis: Long = DEFAULT_DISCOVERY_REFRESH_TIMEOUT_MS,
    featureOperationSettleTimeoutMillis: Long = DEFAULT_FEATURE_OPERATION_SETTLE_TIMEOUT_MS,
    beforeTerminalWatcherRemovalForTest: (suspend () -> Unit)? = null
): P2pKit {
    // Establish the failure-isolating boundary before identity storage,
    // platform factories, transport construction, or any coroutine can log.
    val safeLogger = logger.failureIsolated()
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
                ?: defaultSecureIdentityStorage(appId, safeLogger)
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
            val peerIdStorage = peerIdStorageOverride ?: defaultPeerIdStorage(appId, safeLogger)
            localPeerId = peerIdStorage.loadOrGenerate()
        }
    }
    return try {
        val validatedLocalPeerId = validateLocalPeerId(localPeerId)
        val pathObserver = networkPathObserverOverride ?: defaultNetworkPathObserver(safeLogger)
        val permissionManager = permissionManagerOverride ?: defaultPlatformPermissionManager(safeLogger)
        P2pKitImpl(
            appId = appId,
            deviceName = deviceName,
            localPlatform = currentPlatform(),
            localPeerId = validatedLocalPeerId,
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
            logger = safeLogger,
            clock = ::systemTimeMillis,
            monotonicClock = ::monotonicTimeMillis,
            parentJob = null,
            pathObserver = pathObserver,
            strictSessionInvariants = strictSessionInvariants,
            sessionSetupTimeoutMillis = sessionSetupTimeoutMillis,
            beforeSessionCommitForTest = beforeSessionCommitForTest,
            afterOutgoingConnectForTest = afterOutgoingConnectForTest,
            afterSessionSetupResultForTest = afterSessionSetupResultForTest,
            discoveryRefreshTimeoutMillis = discoveryRefreshTimeoutMillis,
            featureOperationSettleTimeoutMillis = featureOperationSettleTimeoutMillis,
            beforeTerminalWatcherRemovalForTest = beforeTerminalWatcherRemovalForTest
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
