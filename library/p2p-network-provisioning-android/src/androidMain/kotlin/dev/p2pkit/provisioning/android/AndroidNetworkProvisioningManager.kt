package dev.p2pkit.provisioning.android

import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.NetworkProvisioningError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.core.provisioning.LocalNetworkConfig
import dev.p2pkit.core.provisioning.LocalNetworkResult
import dev.p2pkit.core.provisioning.ManualConnectionInfo
import dev.p2pkit.core.provisioning.NetworkProvisioningEvent
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.provisioning.ProvisioningContext
import dev.p2pkit.core.provisioning.WifiCredentials
import java.net.Inet4Address
import java.net.NetworkInterface
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Android implementation of [NetworkProvisioningManager].
 *
 * - [startLocalNetwork] / [stopLocalNetwork]: wraps `WifiManager.startLocalOnlyHotspot`.
 *   Random SSID + passphrase chosen by the OS (non-system apps cannot pick
 *   their own). Lifetime is bound to the underlying
 *   `LocalOnlyHotspotReservation` — [stopLocalNetwork] (or scope
 *   cancellation) closes the reservation.
 * - [joinLocalNetwork]: joins a specific Wi-Fi network via
 *   `WifiNetworkSpecifier` + `ConnectivityManager.requestNetwork` (the
 *   system always shows a user-approval prompt; on success the process is
 *   bound to the joined network). Requires Android 10 (API 29) — returns
 *   [JoinNetworkResult.Unsupported] below that.
 * - [getManualConnectionInfo] / [createManualPeer]: identical shape to the
 *   JVM impl. While the hotspot is running, [ManualConnectionInfo.hostAddresses]
 *   includes the soft-AP interface IP.
 *
 * Construction takes a [WifiManagerWrapper] seam for testability. The
 * production factory wires in [WifiManagerWrapperImpl]; tests inject a
 * fake so the host JVM can exercise the state machine without Robolectric.
 */
@OptIn(ExperimentalP2pApi::class)
public class AndroidNetworkProvisioningManager internal constructor(
    private val ctx: ProvisioningContext,
    private val wifi: WifiManagerWrapper,
    private val lifecycleHooks: ProvisioningLifecycleHooks = ProvisioningLifecycleHooks()
) : NetworkProvisioningManager {

    private val scopeJob = SupervisorJob(parent = ctx.parentJob)
    private val scope = CoroutineScope(Dispatchers.Default + scopeJob)

    private val _state = MutableStateFlow<NetworkProvisioningState>(NetworkProvisioningState.Idle)
    override val state: StateFlow<NetworkProvisioningState> = _state.asStateFlow()

    private val _networkState = MutableStateFlow<NetworkState>(NetworkState.Unknown)
    override val networkState: StateFlow<NetworkState> = _networkState.asStateFlow()

    private val _events = MutableSharedFlow<NetworkProvisioningEvent>(
        replay = 0,
        extraBufferCapacity = 16,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    override val events: Flow<NetworkProvisioningEvent> = _events.asSharedFlow()

    private val lifecycleLock = Mutex()
    private val closeLock = Mutex()
    private val closeAttemptLock = Any()
    private val handleLock = Any()
    @kotlin.concurrent.Volatile
    private var handle: HotspotHandle? = null
    private var stopWatch: Job? = null
    @kotlin.concurrent.Volatile
    private var joinHandle: JoinHandle? = null
    private var joinReleaseWatch: Job? = null
    private val retainedHotspotCleanup = mutableListOf<HotspotHandle>()
    private val retainedJoinCleanup = mutableListOf<JoinHandle>()
    private var explicitCloseInProgress: Boolean = false
    private var closeAttempt: CompletableDeferred<Throwable?>? = null
    private var closeSucceeded: Boolean = false
    @kotlin.concurrent.Volatile
    private var closed: Boolean = false

    init {
        // Release native resources (LocalOnlyHotspot reservation, joined-network
        // process binding) whenever the scope completes — including when the
        // kit's parent job is cancelled by P2pKit.stop(). Previously stop() only
        // cancelled the scope (stopping the watcher coroutines) but never invoked
        // close(), so the hotspot reservation leaked for the process lifetime.
        // closeOwnedHandles() runs without lifecycleLock and uses handleLock to
        // claim the latest handles exactly once. Failed cleanup remains owned
        // for a later explicit close() retry.
        scopeJob.invokeOnCompletion {
            beginClose()
            val explicitCloseOwnsCleanup = synchronized(handleLock) { explicitCloseInProgress }
            if (!explicitCloseOwnsCleanup) {
                closeOwnedHandles()
                _networkState.value = NetworkState.Unknown
                _state.value = NetworkProvisioningState.Closed
            }
        }
    }

    // --- NetworkProvisioningManager surface -------------------------------

    override suspend fun startLocalNetwork(config: LocalNetworkConfig): LocalNetworkResult =
        runManagerOperation(::closedLocalNetworkResult) { startLocalNetworkTransaction(config) }

    private suspend fun startLocalNetworkTransaction(
        config: LocalNetworkConfig
    ): LocalNetworkResult = lifecycleLock.withLock {
        if (isClosingOrClosed()) return@withLock closedLocalNetworkResult()
        if (config.preferredSsidPrefix != null) {
            ctx.logger.debug(
                "provisioning: Android chooses LocalOnlyHotspot credentials; preferredSsidPrefix is a non-binding hint"
            )
        }
        if (!wifi.isLocalOnlyHotspotSupported) {
            // Contract result for unsupported platforms (API < 26 or no
            // Wi-Fi hardware) instead of a linkage-error-backed
            // PlatformError (AUDIT-2026-06 fix).
            return@withLock LocalNetworkResult.Unsupported(
                "LocalOnlyHotspot requires Android 8.0 (API 26) and Wi-Fi hardware"
            )
        }
        if (synchronized(handleLock) { retainedHotspotCleanup.isNotEmpty() }) {
            val error = NetworkProvisioningError.CleanupFailed(
                "a previous hotspot reservation still requires cleanup; call stopLocalNetwork() or close() to retry"
            )
            commitIfOpen { _state.value = NetworkProvisioningState.Failed(error) }
            return@withLock LocalNetworkResult.Failed(error)
        }
        // Snapshot: handleSystemStop nulls `handle` from a collector
        // coroutine, so a double-deref here could NPE between check and
        // use (AUDIT-2026-06 fix).
        val existing = handle
        if (existing != null) {
            ctx.logger.debug("provisioning: startLocalNetwork called while already running")
            val result = buildStartedResult(
                runCatching { existing.getCredentials() }.getOrNull(), existing
            )
            return@withLock if (isClosingOrClosed()) closedLocalNetworkResult() else result
        }
        retryWrapperOwnedCleanup("starting a hotspot")?.let { error ->
            commitIfOpen {
                _state.value = NetworkProvisioningState.Failed(error)
                _events.tryEmit(NetworkProvisioningEvent.Failed(error))
            }
            return@withLock LocalNetworkResult.Failed(error)
        }
        if (!commitIfOpen { _state.value = NetworkProvisioningState.StartingLocalNetwork }) {
            return@withLock closedLocalNetworkResult()
        }

        // Bounded: the OS callback can simply never arrive on some OEMs;
        // an unbounded suspend here held lifecycleLock forever, wedging
        // every other provisioning API (AUDIT-2026-06 fix).
        val startResult = try {
            withTimeoutOrNull(OS_CALLBACK_TIMEOUT_MS) { wifi.startLocalOnlyHotspot() }
                ?: HotspotStartResult.Failed(reasonCode = -1)
        } catch (e: CancellationException) {
            if (isClosingOrClosed()) return@withLock closedLocalNetworkResult()
            commitIfOpen { _state.value = NetworkProvisioningState.Idle }
            throw e
        } catch (e: Throwable) {
            val mapped = mapStartException(e)
            ctx.logger.warn(
                "provisioning: startLocalOnlyHotspot threw ${e::class.simpleName}: " +
                    "${e.message ?: "(no message)"} → ${mapped::class.simpleName}",
                e
            )
            if (!commitIfOpen { _state.value = NetworkProvisioningState.Failed(mapped) }) {
                return@withLock closedLocalNetworkResult()
            }
            return@withLock LocalNetworkResult.Failed(mapped)
        }

        when (startResult) {
            is HotspotStartResult.CleanupPending -> {
                val err = NetworkProvisioningError.CleanupFailed(startResult.reason)
                if (!commitIfOpen {
                        _state.value = NetworkProvisioningState.Failed(err)
                        _events.tryEmit(NetworkProvisioningEvent.Failed(err))
                    }
                ) {
                    return@withLock closedLocalNetworkResult()
                }
                LocalNetworkResult.Failed(err)
            }
            is HotspotStartResult.Failed -> {
                val err = NetworkProvisioningError.HotspotStopped(
                    "startLocalOnlyHotspot failed (reason code ${startResult.reasonCode}: " +
                        "${reasonCodeName(startResult.reasonCode)})"
                )
                ctx.logger.warn("provisioning: ${err.message}")
                if (!commitIfOpen { _state.value = NetworkProvisioningState.Failed(err) }) {
                    return@withLock closedLocalNetworkResult()
                }
                LocalNetworkResult.Failed(err)
            }
            is HotspotStartResult.Started -> {
                val h = startResult.handle
                // Enter collection before publishing the handle. The wrapper
                // seam promises a one-shot terminal signal, but does not
                // require replay; a normally scheduled collector could miss a
                // stop emitted immediately after this operation returned.
                val watcher = scope.launch(start = CoroutineStart.UNDISPATCHED) {
                    handleSystemStop(h, h.stopped.first())
                }
                var installed = false
                var published = false
                var cleanupClaimed = false
                try {
                    lifecycleHooks.afterHotspotAcquired()
                    if (!installHotspot(h, watcher)) {
                        return@withLock closedLocalNetworkResult()
                    }
                    installed = true
                    val creds = runCatching { h.getCredentials() }.getOrNull()
                    val result = buildStartedResult(creds, h)
                    if (result is LocalNetworkResult.Failed) {
                        cleanupClaimed = claimHotspot(h)
                        val cleanupFailure = if (cleanupClaimed) {
                            closeHotspotOrRetain(h, "failed hotspot start")
                        } else {
                            null
                        }
                        val failureResult = cleanupFailure?.let {
                            LocalNetworkResult.Failed(
                                NetworkProvisioningError.CleanupFailed(
                                    "hotspot start failed and its reservation could not be released",
                                    it
                                )
                            )
                        } ?: result
                        if (!commitIfOpen {
                                _networkState.value = NetworkState.Unknown
                                _state.value = NetworkProvisioningState.Failed(failureResult.error)
                                _events.tryEmit(NetworkProvisioningEvent.Failed(failureResult.error))
                            }
                        ) {
                            return@withLock closedLocalNetworkResult()
                        }
                        return@withLock failureResult
                    }
                    val networkState = buildStartedNetworkState(h, creds)
                    if (!commitIfOpen {
                            _networkState.value = networkState
                            _state.value = NetworkProvisioningState.LocalNetworkRunning
                            _events.tryEmit(NetworkProvisioningEvent.LocalNetworkStarted(creds))
                        }
                    ) {
                        return@withLock closedLocalNetworkResult()
                    }
                    published = true
                    result
                } finally {
                    if (!published && !cleanupClaimed) {
                        val operationOwnsCleanup = if (installed) claimHotspot(h) else true
                        watcher.cancel()
                        if (operationOwnsCleanup) {
                            closeHotspotOrRetain(h, "unpublished hotspot result")
                        }
                    }
                }
            }
        }
    }

    /**
     * Stops the hotspot only. It does **not** release a joined network —
     * joined-network state is released when the kit is closed or [close] is
     * called (decision #8c, 2026-07-04).
     */
    override suspend fun stopLocalNetwork(): Unit = runManagerOperation({}) {
        lifecycleLock.withLock {
            val owned = synchronized(handleLock) {
                if (isClosingOrClosed()) return@withLock
                val resources = identityDistinct(
                    buildList<HotspotHandle> {
                        handle?.let { add(it) }
                        addAll(retainedHotspotCleanup)
                    }
                )
                if (resources.isEmpty()) return@withLock
                handle = null
                retainedHotspotCleanup.clear()
                val watcher = stopWatch
                stopWatch = null
                resources to watcher
            }
            commitIfOpen { _state.value = NetworkProvisioningState.StoppingLocalNetwork }
            owned.second?.cancel()
            val failures = owned.first.mapNotNull { resource ->
                closeHotspotOrRetain(resource, "stopLocalNetwork")
            }
            if (failures.isEmpty()) {
                commitIfOpen {
                    _networkState.value = NetworkState.Unknown
                    _state.value = NetworkProvisioningState.Idle
                    _events.tryEmit(NetworkProvisioningEvent.LocalNetworkStopped)
                }
            } else {
                val error = NetworkProvisioningError.CleanupFailed(
                    "failed to release ${failures.size} hotspot resource(s)",
                    aggregateCleanupCauses(failures)
                )
                commitIfOpen {
                    _networkState.value = NetworkState.Unknown
                    _state.value = NetworkProvisioningState.Failed(error)
                    _events.tryEmit(NetworkProvisioningEvent.Failed(error))
                }
                throw error
            }
        }
    }

    /**
     * At most one joined network is active per manager. A call made while a
     * join is still active fails with "a joined network is already active";
     * there is no leave path in this version — the joined-network state
     * (process-wide binding + NetworkCallback) is released when the kit is
     * closed (parent-job cancellation) or [close] is called. A `leaveNetwork()`
     * surface (or redefining stop semantics) is deferred to the post-RC spec
     * discussion (decision #8c, 2026-07-04; PRM-16).
     */
    override suspend fun joinLocalNetwork(credentials: WifiCredentials): JoinNetworkResult =
        runManagerOperation(::closedJoinNetworkResult) { joinLocalNetworkTransaction(credentials) }

    private suspend fun joinLocalNetworkTransaction(
        credentials: WifiCredentials
    ): JoinNetworkResult = lifecycleLock.withLock {
        if (isClosingOrClosed()) return@withLock closedJoinNetworkResult()
        if (!wifi.isSpecifierJoinSupported) {
            return@withLock JoinNetworkResult.Unsupported(
                "WifiNetworkSpecifier join requires Android 10 (API 29)"
            )
        }
        if (joinHandle != null) {
            // AUDIT-2026-07 (PRM-16, decision #8c): joinHandle is only
            // ever non-null after a join has *completed successfully* and
            // is still active (an in-flight join holds lifecycleLock, so
            // concurrent callers wait rather than reach this branch) —
            // word the refusal for that state, not "in progress".
            return@withLock JoinNetworkResult.Failed(
                NetworkProvisioningError.JoinFailed(
                    "a joined network is already active; it is released only when the kit is closed"
                )
            )
        }
        if (synchronized(handleLock) { retainedJoinCleanup.isNotEmpty() }) {
            val error = NetworkProvisioningError.CleanupFailed(
                "a previous joined-network binding still requires cleanup; close the manager to retry"
            )
            commitIfOpen { _state.value = NetworkProvisioningState.Failed(error) }
            return@withLock JoinNetworkResult.Failed(error)
        }
        retryWrapperOwnedCleanup("joining a network")?.let { error ->
            commitIfOpen {
                _state.value = NetworkProvisioningState.Failed(error)
                _events.tryEmit(NetworkProvisioningEvent.Failed(error))
            }
            return@withLock JoinNetworkResult.Failed(error)
        }
        val validationError = validateWifiCredentials(credentials)
        if (validationError != null) {
            return@withLock JoinNetworkResult.Failed(
                NetworkProvisioningError.JoinFailed(validationError)
            )
        }
        val ssid = credentials.ssid!!

        if (!commitIfOpen {
                _state.value = NetworkProvisioningState.JoiningNetwork
                _events.tryEmit(
                    NetworkProvisioningEvent.UserActionRequired(
                        "Approve the Wi-Fi join prompt for \"$ssid\"."
                    )
                )
            }
        ) {
            return@withLock closedJoinNetworkResult()
        }

        val joinResult = try {
            // Bounded like the hotspot wait: the approval dialog can sit
            // unanswered indefinitely (AUDIT-2026-06 fix).
            withTimeoutOrNull(OS_CALLBACK_TIMEOUT_MS) { wifi.joinWifiNetwork(credentials) }
                ?: JoinResult.Failed("join timed out after ${OS_CALLBACK_TIMEOUT_MS / 1000}s (no user approval / no matching network)")
        } catch (e: CancellationException) {
            if (isClosingOrClosed()) return@withLock closedJoinNetworkResult()
            commitIfOpen { _state.value = NetworkProvisioningState.Idle }
            throw e
        } catch (e: Throwable) {
            val mapped = mapStartException(e)
            ctx.logger.warn(
                "provisioning: joinWifiNetwork threw ${e::class.simpleName}: " +
                    "${e.message ?: "(no message)"} → ${mapped::class.simpleName}",
                e
            )
            if (!commitIfOpen { _state.value = NetworkProvisioningState.Failed(mapped) }) {
                return@withLock closedJoinNetworkResult()
            }
            return@withLock JoinNetworkResult.Failed(mapped)
        }

        when (joinResult) {
            is JoinResult.Failed -> {
                val err = NetworkProvisioningError.JoinFailed(joinResult.reason)
                ctx.logger.warn("provisioning: join failed: ${joinResult.reason}")
                if (!commitIfOpen { _state.value = NetworkProvisioningState.Failed(err) }) {
                    return@withLock closedJoinNetworkResult()
                }
                JoinNetworkResult.Failed(err)
            }
            is JoinResult.Joined -> {
                val h = joinResult.handle
                // Subscribe before the joined handle becomes observable. This
                // closes the same zero-replay admission window as the hotspot
                // watcher and makes an immediate OS release deterministic.
                val watcher = scope.launch(start = CoroutineStart.UNDISPATCHED) {
                    handleJoinReleased(h, h.released.first())
                }
                var installed = false
                var published = false
                try {
                    lifecycleHooks.afterJoinAcquired()
                    if (!installJoin(h, watcher)) {
                        return@withLock closedJoinNetworkResult()
                    }
                    installed = true
                    val nstate = h.snapshotNetworkState()
                    if (!commitIfOpen {
                            _networkState.value = nstate
                            _state.value = NetworkProvisioningState.JoinedNetwork
                            _events.tryEmit(NetworkProvisioningEvent.NetworkJoined(nstate))
                        }
                    ) {
                        return@withLock closedJoinNetworkResult()
                    }
                    published = true
                    ctx.logger.info("provisioning: joined Wi-Fi network \"$ssid\"")
                    JoinNetworkResult.Joined(nstate)
                } finally {
                    if (!published) {
                        val operationOwnsCleanup = if (installed) claimJoin(h) else true
                        watcher.cancel()
                        if (operationOwnsCleanup) {
                            closeJoinOrRetain(h, "unpublished join result")
                        }
                    }
                }
            }
        }
    }

    private suspend fun handleJoinReleased(firing: JoinHandle, reason: String) = lifecycleLock.withLock {
        // Stale guard + lock: these handlers previously mutated
        // handle/joinHandle/_state off-lock from collector coroutines,
        // racing the locked API paths (AUDIT-2026-06 fix).
        val owned = synchronized(handleLock) {
            if (joinHandle !== firing) return@withLock
            joinHandle = null
            joinReleaseWatch = null
            firing
        }
        val releaseError = NetworkProvisioningError.JoinFailed("join released: $reason")
        // close() the handle BEFORE dropping it: JoinHandleImpl.close() is the
        // ONLY code that clears bindProcessToNetwork and unregisters the
        // NetworkCallback. Nulling without closing left every socket in the
        // host process bound to the dead network (traffic blackholed until the
        // next successful join) and leaked one NetworkCallback per join cycle.
        // It also stops the wrapper's re-onAvailable branch from silently
        // re-binding after we have declared the join terminally Failed
        // (AUDIT-2026-06 fix). Cleanup is retryable; a failure remains owned
        // and is surfaced instead of falsely implying the binding is gone.
        val cleanupFailure = closeJoinOrRetain(owned, "system join release")
        val error = cleanupFailure?.let {
            NetworkProvisioningError.CleanupFailed(
                "join was released but its process binding could not be cleaned up",
                it
            )
        } ?: releaseError
        commitIfOpen {
            _state.value = NetworkProvisioningState.Failed(error)
            _networkState.value = NetworkState.Unknown
            _events.tryEmit(NetworkProvisioningEvent.Failed(error))
        }
        ctx.logger.warn("provisioning: join released — $reason")
        Unit
    }

    override suspend fun getManualConnectionInfo(): ManualConnectionInfo? =
        runManagerOperation({ throw NetworkProvisioningError.ManagerClosed() }) {
            ensureOpen()
            val port = ctx.lanTcpPort() ?: return@runManagerOperation null
            val hosts = collectInterfaceIPs() + (handle?.apHostAddresses() ?: emptyList())
            val distinct = hosts.distinct()
            if (distinct.isEmpty()) return@runManagerOperation null
            ManualConnectionInfo(
                hostAddresses = distinct,
                port = port,
                appId = ctx.appId,
                peerId = ctx.localPeerId,
                deviceName = ctx.localDeviceName,
                fingerprint = ctx.localFingerprint,
                pairingQr = ctx.localPairingQr
            )
        }

    @ExperimentalP2pApi
    @Deprecated(
        message = "Secure manual-IP connections require an expected fingerprint. Use the fingerprint overload.",
        replaceWith = ReplaceWith("createManualPeer(host, port, expectedFingerprint)")
    )
    override suspend fun createManualPeer(host: String, port: Int): Peer =
        runManagerOperation({ throw NetworkProvisioningError.ManagerClosed() }) {
            ensureOpen()
            ctx.logger.info("provisioning: createManualPeer host=$host port=$port")
            ctx.manualPeerRegistrar.registerManualPeer(host = host, port = port)
        }

    @ExperimentalP2pApi
    override suspend fun createManualPeer(
        host: String,
        port: Int,
        expectedFingerprint: PeerFingerprint
    ): Peer = runManagerOperation({ throw NetworkProvisioningError.ManagerClosed() }) {
        ensureOpen()
        ctx.logger.info("provisioning: createManualPeer host=$host port=$port with authenticated pin")
        ctx.manualPeerRegistrar.registerManualPeer(
            host = host,
            port = port,
            expectedFingerprint = expectedFingerprint
        )
    }

    private companion object {
        /** Upper bound for OS-callback waits (LOHS start, specifier join approval). */
        const val OS_CALLBACK_TIMEOUT_MS: Long = 60_000
        const val CLOSE_TIMEOUT_MS: Long = 5_000
    }

    /**
     * Cancels the background scope and releases any active hotspot or
     * Wi-Fi join. Called automatically when the kit's parent job is
     * cancelled (via [ProvisioningContext.parentJob]); apps may also call
     * it directly for explicit teardown.
     *
     * Once close begins, the manager is terminal: concurrent or later
     * [startLocalNetwork] / [joinLocalNetwork] calls return a deterministic
     * failed result and never retain a newly delivered OS handle. The same
     * terminal gate is set by parent-job cancellation before owned resources
     * are released, so a callback arriving after kit shutdown cannot create a
     * reservation or process binding outside teardown ownership.
     */
    override suspend fun close(): Unit = withContext(NonCancellable) {
        val acquiredAttempt = synchronized(closeAttemptLock) {
            if (closeSucceeded) {
                null
            } else {
                val current = closeAttempt
                if (current != null && !current.isCompleted) {
                    current to false
                } else {
                    CompletableDeferred<Throwable?>().also { closeAttempt = it } to true
                }
            }
        }
        if (acquiredAttempt == null) return@withContext

        val (attempt, ownsAttempt) = acquiredAttempt
        if (ownsAttempt) {
            val failure = runCatching {
                closeLock.withLock { performCloseAttempt() }
            }.exceptionOrNull()
            synchronized(closeAttemptLock) {
                if (failure == null) closeSucceeded = true
            }
            attempt.complete(failure)
        }
        attempt.await()?.let { throw it }
    }

    // --- internals --------------------------------------------------------

    private suspend fun performCloseAttempt() {
        beginExplicitClose()
        try {
            val joined = withTimeoutOrNull(CLOSE_TIMEOUT_MS) {
                scopeJob.cancelAndJoin()
                true
            } ?: false
            val failures = closeOwnedHandles().toMutableList()
            if (!joined) {
                failures += IllegalStateException(
                    "provisioning scope did not stop within ${CLOSE_TIMEOUT_MS}ms"
                )
            }
            _networkState.value = NetworkState.Unknown
            _state.value = NetworkProvisioningState.Closed
            if (failures.isNotEmpty()) {
                throw NetworkProvisioningError.CleanupFailed(
                    "failed to release ${failures.size} provisioning resource(s)",
                    aggregateCleanupCauses(failures)
                )
            }
        } finally {
            synchronized(handleLock) { explicitCloseInProgress = false }
        }
    }

    private suspend fun buildStartedResult(
        credentials: WifiCredentials?,
        h: HotspotHandle
    ): LocalNetworkResult {
        val info = buildManualInfoFromHandle(h)
        return if (credentials != null && credentials.ssid != null) {
            LocalNetworkResult.Started(credentials = credentials, manualConnectionInfo = info)
        } else if (info != null) {
            // OS redacted SSID/passphrase but the hotspot is up; surface the manual info
            // so the host can still share the connection out-of-band.
            LocalNetworkResult.StartedWithoutCredentials(manualConnectionInfo = info)
        } else {
            // No creds AND no manual info — the only honest answer is Failed.
            val err = NetworkProvisioningError.HotspotStopped(
                "Hotspot started but neither credentials nor manualConnectionInfo are available."
            )
            LocalNetworkResult.Failed(err)
        }
    }

    private suspend fun buildManualInfoFromHandle(h: HotspotHandle): ManualConnectionInfo? {
        val port = ctx.lanTcpPort() ?: return null
        val hosts = (collectInterfaceIPs() + h.apHostAddresses()).distinct()
        if (hosts.isEmpty()) return null
        return ManualConnectionInfo(
            hostAddresses = hosts,
            port = port,
            appId = ctx.appId,
            peerId = ctx.localPeerId,
            deviceName = ctx.localDeviceName,
            fingerprint = ctx.localFingerprint,
            pairingQr = ctx.localPairingQr
        )
    }

    private suspend fun buildStartedNetworkState(
        h: HotspotHandle,
        creds: WifiCredentials?
    ): NetworkState.LocalNetworkHosted {
        val ips = (collectInterfaceIPs() + h.apHostAddresses()).distinct()
        return NetworkState.LocalNetworkHosted(
            credentials = creds,
            localIpAddresses = ips
        )
    }

    private suspend fun handleSystemStop(firing: HotspotHandle, reason: HotspotStopReason) = lifecycleLock.withLock {
        val owned = synchronized(handleLock) {
            if (handle !== firing) return@withLock
            handle = null
            stopWatch = null
            firing
        }
        val stopError = NetworkProvisioningError.HotspotStopped(reason.source)
        val cleanupFailure = closeHotspotOrRetain(owned, "system hotspot stop")
        val error = cleanupFailure?.let {
            NetworkProvisioningError.CleanupFailed(
                "hotspot stopped but its reservation could not be cleaned up",
                it
            )
        } ?: stopError
        commitIfOpen {
            _state.value = NetworkProvisioningState.Failed(error)
            _networkState.value = NetworkState.Unknown
            _events.tryEmit(NetworkProvisioningEvent.Failed(error))
        }
        Unit
    }

    private fun claimHotspot(resource: HotspotHandle): Boolean {
        var watcher: Job? = null
        val claimed = synchronized(handleLock) {
            if (handle !== resource) {
                false
            } else {
                handle = null
                watcher = stopWatch
                stopWatch = null
                true
            }
        }
        watcher?.cancel()
        return claimed
    }

    private fun claimJoin(resource: JoinHandle): Boolean {
        var watcher: Job? = null
        val claimed = synchronized(handleLock) {
            if (joinHandle !== resource) {
                false
            } else {
                joinHandle = null
                watcher = joinReleaseWatch
                joinReleaseWatch = null
                true
            }
        }
        watcher?.cancel()
        return claimed
    }

    private fun installHotspot(h: HotspotHandle, watcher: Job): Boolean = synchronized(handleLock) {
        if (isClosingOrClosed()) false else {
            handle = h
            stopWatch = watcher
            true
        }
    }

    private fun installJoin(h: JoinHandle, watcher: Job): Boolean = synchronized(handleLock) {
        if (isClosingOrClosed()) false else {
            joinHandle = h
            joinReleaseWatch = watcher
            true
        }
    }

    private fun beginClose() {
        synchronized(handleLock) {
            if (closed) return
            closed = true
            _state.value = NetworkProvisioningState.Closing
        }
    }

    /** Atomically assigns cleanup ownership before terminal cancellation. */
    private fun beginExplicitClose() {
        synchronized(handleLock) {
            explicitCloseInProgress = true
            if (!closed) {
                closed = true
                _state.value = NetworkProvisioningState.Closing
            }
        }
    }

    /** Linearize every nonterminal publication against [beginClose]. */
    private inline fun commitIfOpen(block: () -> Unit): Boolean = synchronized(handleLock) {
        if (isClosingOrClosed()) false else {
            block()
            true
        }
    }

    private fun closeOwnedHandles(): List<Throwable> {
        val owned = synchronized(handleLock) {
            val hotspots = identityDistinct(
                buildList<HotspotHandle> {
                    handle?.let { add(it) }
                    addAll(retainedHotspotCleanup)
                }
            )
            val joins = identityDistinct(
                buildList<JoinHandle> {
                    joinHandle?.let { add(it) }
                    addAll(retainedJoinCleanup)
                }
            )
            handle = null
            joinHandle = null
            retainedHotspotCleanup.clear()
            retainedJoinCleanup.clear()
            stopWatch?.cancel()
            stopWatch = null
            joinReleaseWatch?.cancel()
            joinReleaseWatch = null
            hotspots to joins
        }
        val failures = mutableListOf<Throwable>()
        owned.first.forEach { resource ->
            closeHotspotOrRetain(resource, "terminal teardown")?.let(failures::add)
        }
        owned.second.forEach { resource ->
            closeJoinOrRetain(resource, "terminal teardown")?.let(failures::add)
        }
        val wrapperFailures = runCatching { wifi.closePendingResources() }
            .getOrElse { listOf(it) }
        wrapperFailures.forEach { failure ->
            ctx.logger.warn("provisioning: wrapper-owned native cleanup remains pending", failure)
        }
        failures += wrapperFailures
        return failures
    }

    private fun retryWrapperOwnedCleanup(context: String): NetworkProvisioningError.CleanupFailed? {
        val failures = runCatching { wifi.closePendingResources() }
            .getOrElse { listOf(it) }
        if (failures.isEmpty()) return null
        failures.forEach { failure ->
            ctx.logger.warn(
                "provisioning: wrapper-owned cleanup blocked $context",
                failure
            )
        }
        return NetworkProvisioningError.CleanupFailed(
            reason = "wrapper-owned native resources still require cleanup before $context",
            cleanupCause = aggregateCleanupCauses(failures)
        )
    }

    private fun aggregateCleanupCauses(failures: List<Throwable>): Throwable {
        val primary = failures.first()
        failures.drop(1).forEach { secondary ->
            if (secondary !== primary && primary.suppressedExceptions.none { it === secondary }) {
                primary.addSuppressed(secondary)
            }
        }
        return primary
    }

    private fun closeHotspotOrRetain(resource: HotspotHandle, context: String): Throwable? {
        val failure = runCatching(resource::close).exceptionOrNull()
        synchronized(handleLock) {
            retainedHotspotCleanup.removeAll { it === resource }
            if (failure != null) retainedHotspotCleanup += resource
        }
        if (failure != null) {
            ctx.logger.warn("provisioning: hotspot cleanup failed during $context; retained for retry", failure)
        }
        return failure
    }

    private fun closeJoinOrRetain(resource: JoinHandle, context: String): Throwable? {
        val failure = runCatching(resource::close).exceptionOrNull()
        synchronized(handleLock) {
            retainedJoinCleanup.removeAll { it === resource }
            if (failure != null) retainedJoinCleanup += resource
        }
        if (failure != null) {
            ctx.logger.warn("provisioning: joined-network cleanup failed during $context; retained for retry", failure)
        }
        return failure
    }

    private fun <T : Any> identityDistinct(values: List<T>): List<T> {
        val result = mutableListOf<T>()
        values.forEach { value ->
            if (result.none { it === value }) result += value
        }
        return result
    }

    private fun closedLocalNetworkResult(): LocalNetworkResult = LocalNetworkResult.Failed(
        NetworkProvisioningError.ManagerClosed()
    )

    private fun closedJoinNetworkResult(): JoinNetworkResult = JoinNetworkResult.Failed(
        NetworkProvisioningError.ManagerClosed()
    )

    private fun ensureOpen() {
        if (isClosingOrClosed()) throw NetworkProvisioningError.ManagerClosed()
    }

    private fun isClosingOrClosed(): Boolean = closed || !scopeJob.isActive

    /**
     * Attach the complete API transaction, including post-callback handle
     * installation or cleanup, to manager ownership. Terminal close cancels
     * and joins these children; caller cancellation waits for deterministic
     * cleanup before it is rethrown.
     */
    private suspend fun <T> runManagerOperation(
        closedResult: () -> T,
        block: suspend () -> T
    ): T {
        val operation = scope.async { block() }
        return try {
            operation.await()
        } catch (e: CancellationException) {
            withContext(NonCancellable) { operation.cancelAndJoin() }
            if (isClosingOrClosed()) {
                closedResult()
            } else {
                commitIfOpen {
                    when (_state.value) {
                        NetworkProvisioningState.StartingLocalNetwork,
                        NetworkProvisioningState.JoiningNetwork ->
                            _state.value = NetworkProvisioningState.Idle
                        else -> Unit
                    }
                }
                throw e
            }
        }
    }

    private fun mapStartException(e: Throwable): NetworkProvisioningError {
        if (e is SecurityException || e.cause is SecurityException) {
            val msg = e.message.orEmpty()
            // Some OEMs (Huawei, older Samsung, MIUI) reject startLocalOnlyHotspot
            // with a SecurityException carrying "Location mode is not enabled"
            // even when NEARBY_WIFI_DEVICES is granted. This is the device-wide
            // Location toggle, not the per-app runtime permission — only the
            // user can flip it (Settings → Location → Use location). Surface
            // it as Location-permission-missing so callers can show the right
            // remediation (open Location settings, not request a permission).
            if (msg.contains("Location mode", ignoreCase = true) ||
                msg.contains("location is disabled", ignoreCase = true) ||
                msg.contains("location services", ignoreCase = true)
            ) {
                return NetworkProvisioningError.PermissionMissingForProvisioning(
                    permissions = listOf(P2pPermission.Location)
                )
            }
            return NetworkProvisioningError.PermissionMissingForProvisioning(
                // targetSdk-aware: NEARBY_WIFI_DEVICES is ungrantable for
                // targetSdk<=32 apps even on Android 13+ (AUDIT-2026-06 fix).
                permissions = listOf(wifi.requiredRuntimePermission())
            )
        }
        return NetworkProvisioningError.PlatformError(e)
    }

    /**
     * Decode the AOSP `LocalOnlyHotspotCallback` reason code into a human
     * label. Codes are stable since API 26.
     */
    private fun reasonCodeName(code: Int): String = when (code) {
        0 -> "NO_CHANNEL"
        1 -> "GENERIC"
        2 -> "INCOMPATIBLE_MODE"
        3 -> "TETHERING_DISALLOWED"
        -1 -> "STOPPED_BEFORE_START"
        else -> "UNKNOWN($code)"
    }

    private suspend fun collectInterfaceIPs(): List<String> = withContext(Dispatchers.IO) {
        // IO dispatcher (the JVM sidecar already hops; Android ran the scan
        // on the caller's thread) and per-NIC guard: isUp/inetAddresses throw
        // SocketException when an interface vanishes mid-scan
        // (AUDIT-2026-06 fix).
        val out = mutableListOf<String>()
        val ifs = runCatching { NetworkInterface.getNetworkInterfaces() }.getOrNull()
            ?: return@withContext emptyList()
        for (nif in ifs) {
            runCatching {
                if (!nif.isUp || nif.isLoopback) return@runCatching
                for (addr in nif.inetAddresses) {
                    if (addr.isLoopbackAddress || addr.isAnyLocalAddress) continue
                    if (addr is Inet4Address) out += addr.hostAddress
                }
            }
        }
        out.distinct()
    }
}

/** Deterministic lifecycle seams used only by host-side concurrency tests. */
internal class ProvisioningLifecycleHooks(
    val afterHotspotAcquired: suspend () -> Unit = {},
    val afterJoinAcquired: suspend () -> Unit = {}
)
