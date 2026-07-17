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
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeoutOrNull
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

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
    private val wifi: WifiManagerWrapper
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
    @kotlin.concurrent.Volatile
    private var handle: HotspotHandle? = null
    private var stopWatch: Job? = null
    @kotlin.concurrent.Volatile
    private var joinHandle: JoinHandle? = null
    private var joinReleaseWatch: Job? = null

    init {
        // Release native resources (LocalOnlyHotspot reservation, joined-network
        // process binding) whenever the scope completes — including when the
        // kit's parent job is cancelled by P2pKit.stop(). Previously stop() only
        // cancelled the scope (stopping the watcher coroutines) but never invoked
        // close(), so the hotspot reservation leaked for the process lifetime.
        // Fields are @Volatile so this handler (which runs without lifecycleLock)
        // observes the latest writes. close() releases are idempotent (runCatching).
        scopeJob.invokeOnCompletion {
            runCatching { handle?.close() }
            runCatching { joinHandle?.close() }
        }
    }

    // --- NetworkProvisioningManager surface -------------------------------

    override suspend fun startLocalNetwork(config: LocalNetworkConfig): LocalNetworkResult =
        lifecycleLock.withLock {
            if (!wifi.isLocalOnlyHotspotSupported) {
                // Contract result for unsupported platforms (API < 26 or no
                // Wi-Fi hardware) instead of a linkage-error-backed
                // PlatformError (AUDIT-2026-06 fix).
                return@withLock LocalNetworkResult.Unsupported(
                    "LocalOnlyHotspot requires Android 8.0 (API 26) and Wi-Fi hardware"
                )
            }
            // Snapshot: handleSystemStop nulls `handle` from a collector
            // coroutine, so a double-deref here could NPE between check and
            // use (AUDIT-2026-06 fix).
            val existing = handle
            if (existing != null) {
                ctx.logger.debug("provisioning: startLocalNetwork called while already running")
                return@withLock buildStartedResult(runCatching { existing.getCredentials() }.getOrNull(), existing)
            }
            _state.value = NetworkProvisioningState.StartingLocalNetwork

            // Bounded: the OS callback can simply never arrive on some OEMs;
            // an unbounded suspend here held lifecycleLock forever, wedging
            // every other provisioning API (AUDIT-2026-06 fix).
            val startResult = runCatching {
                withTimeoutOrNull(OS_CALLBACK_TIMEOUT_MS) { wifi.startLocalOnlyHotspot() }
                    ?: HotspotStartResult.Failed(reasonCode = -1)
            }
                .getOrElse { e ->
                    val mapped = mapStartException(e)
                    ctx.logger.warn(
                        "provisioning: startLocalOnlyHotspot threw ${e::class.simpleName}: " +
                            "${e.message ?: "(no message)"} → ${mapped::class.simpleName}",
                        e
                    )
                    _state.value = NetworkProvisioningState.Failed(mapped)
                    return@withLock LocalNetworkResult.Failed(mapped)
                }

            when (startResult) {
                is HotspotStartResult.Failed -> {
                    val err = NetworkProvisioningError.HotspotStopped(
                        "startLocalOnlyHotspot failed (reason code ${startResult.reasonCode}: " +
                            "${reasonCodeName(startResult.reasonCode)})"
                    )
                    ctx.logger.warn("provisioning: ${err.message}")
                    _state.value = NetworkProvisioningState.Failed(err)
                    LocalNetworkResult.Failed(err)
                }
                is HotspotStartResult.Started -> {
                    val h = startResult.handle
                    handle = h
                    stopWatch = scope.launch {
                        h.stopped.collect { reason ->
                            handleSystemStop(h, reason)
                        }
                    }
                    val creds = runCatching { h.getCredentials() }.getOrNull()
                    publishStartedNetworkState(h, creds)
                    _state.value = NetworkProvisioningState.LocalNetworkRunning
                    _events.tryEmit(NetworkProvisioningEvent.LocalNetworkStarted(creds))
                    buildStartedResult(creds, h)
                }
            }
        }

    /**
     * Stops the hotspot only. It does **not** release a joined network —
     * joined-network state is released when the kit is closed or [close] is
     * called (decision #8c, 2026-07-04).
     */
    override suspend fun stopLocalNetwork() {
        lifecycleLock.withLock {
            val h = handle ?: return
            _state.value = NetworkProvisioningState.StoppingLocalNetwork
            stopWatch?.cancel()
            stopWatch = null
            runCatching { h.close() }
            handle = null
            _networkState.value = NetworkState.Unknown
            _state.value = NetworkProvisioningState.Idle
            _events.tryEmit(NetworkProvisioningEvent.LocalNetworkStopped)
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
        lifecycleLock.withLock {
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
            val ssid = credentials.ssid?.takeIf { it.isNotBlank() }
                ?: return@withLock JoinNetworkResult.Failed(
                    NetworkProvisioningError.JoinFailed("SSID must not be blank")
                )

            _state.value = NetworkProvisioningState.JoiningNetwork
            _events.tryEmit(
                NetworkProvisioningEvent.UserActionRequired(
                    "Approve the Wi-Fi join prompt for \"$ssid\"."
                )
            )

            val joinResult = runCatching {
                // Bounded like the hotspot wait: the approval dialog can sit
                // unanswered indefinitely (AUDIT-2026-06 fix).
                withTimeoutOrNull(OS_CALLBACK_TIMEOUT_MS) { wifi.joinWifiNetwork(credentials) }
                    ?: JoinResult.Failed("join timed out after ${OS_CALLBACK_TIMEOUT_MS / 1000}s (no user approval / no matching network)")
            }
                .getOrElse { e ->
                    val mapped = mapStartException(e)
                    ctx.logger.warn(
                        "provisioning: joinWifiNetwork threw ${e::class.simpleName}: " +
                            "${e.message ?: "(no message)"} → ${mapped::class.simpleName}",
                        e
                    )
                    _state.value = NetworkProvisioningState.Failed(mapped)
                    return@withLock JoinNetworkResult.Failed(mapped)
                }

            when (joinResult) {
                is JoinResult.Failed -> {
                    val err = NetworkProvisioningError.JoinFailed(joinResult.reason)
                    ctx.logger.warn("provisioning: join failed: ${joinResult.reason}")
                    _state.value = NetworkProvisioningState.Failed(err)
                    JoinNetworkResult.Failed(err)
                }
                is JoinResult.Joined -> {
                    val h = joinResult.handle
                    joinHandle = h
                    joinReleaseWatch = scope.launch {
                        h.released.collect { reason -> handleJoinReleased(h, reason) }
                    }
                    val nstate = h.snapshotNetworkState()
                    _networkState.value = nstate
                    _state.value = NetworkProvisioningState.JoinedNetwork
                    _events.tryEmit(NetworkProvisioningEvent.NetworkJoined(nstate))
                    ctx.logger.info("provisioning: joined Wi-Fi network \"$ssid\"")
                    JoinNetworkResult.Joined(nstate)
                }
            }
        }

    private suspend fun handleJoinReleased(firing: JoinHandle, reason: String) = lifecycleLock.withLock {
        // Stale guard + lock: these handlers previously mutated
        // handle/joinHandle/_state off-lock from collector coroutines,
        // racing the locked API paths (AUDIT-2026-06 fix).
        if (joinHandle !== firing) return@withLock
        val err = NetworkProvisioningError.JoinFailed("join released: $reason")
        // close() the handle BEFORE dropping it: JoinHandleImpl.close() is the
        // ONLY code that clears bindProcessToNetwork and unregisters the
        // NetworkCallback. Nulling without closing left every socket in the
        // host process bound to the dead network (traffic blackholed until the
        // next successful join) and leaked one NetworkCallback per join cycle.
        // It also stops the wrapper's re-onAvailable branch from silently
        // re-binding after we have declared the join terminally Failed
        // (AUDIT-2026-06 fix; close() is idempotent via runCatching).
        joinHandle?.let { h -> runCatching { h.close() } }
        joinHandle = null
        joinReleaseWatch = null
        _state.value = NetworkProvisioningState.Failed(err)
        _networkState.value = NetworkState.Unknown
        _events.tryEmit(NetworkProvisioningEvent.Failed(err))
        ctx.logger.warn("provisioning: join released — $reason")
        Unit
    }

    override suspend fun getManualConnectionInfo(): ManualConnectionInfo? {
        val port = ctx.lanTcpPort() ?: return null
        val hosts = collectInterfaceIPs() + (handle?.apHostAddresses() ?: emptyList())
        val distinct = hosts.distinct()
        if (distinct.isEmpty()) return null
        return ManualConnectionInfo(
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
    override suspend fun createManualPeer(host: String, port: Int): Peer {
        ctx.logger.info("provisioning: createManualPeer host=$host port=$port")
        return ctx.manualPeerRegistrar.registerManualPeer(host = host, port = port)
    }

    @ExperimentalP2pApi
    override suspend fun createManualPeer(
        host: String,
        port: Int,
        expectedFingerprint: PeerFingerprint
    ): Peer {
        ctx.logger.info("provisioning: createManualPeer host=$host port=$port with authenticated pin")
        return ctx.manualPeerRegistrar.registerManualPeer(
            host = host,
            port = port,
            expectedFingerprint = expectedFingerprint
        )
    }

    private companion object {
        /** Upper bound for OS-callback waits (LOHS start, specifier join approval). */
        const val OS_CALLBACK_TIMEOUT_MS: Long = 60_000
    }

    /**
     * Cancels the background scope and releases any active hotspot or
     * Wi-Fi join. Called automatically when the kit's parent job is
     * cancelled (via [ProvisioningContext.parentJob]); apps may also call
     * it directly for explicit teardown.
     *
     * Documented limitation (2026-07 P1-27; decision #8c): a
     * [startLocalNetwork] / [joinLocalNetwork] call made *after* the parent
     * job has been cancelled is still accepted, and resources acquired then
     * sit outside the parent-job completion cleanup (that handler has
     * already fired) — an explicit call to this method is the only release
     * path for them. The lifecycle rework (refusing post-cancel starts,
     * together with a `leaveNetwork()` surface) is deferred to the post-RC
     * spec discussion.
     */
    public fun close() {
        scopeJob.cancel()
        runCatching { handle?.close() }
        handle = null
        runCatching { joinHandle?.close() }
        joinHandle = null
    }

    // --- internals --------------------------------------------------------

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
            deviceName = ctx.localDeviceName
        )
    }

    private suspend fun publishStartedNetworkState(h: HotspotHandle, creds: WifiCredentials?) {
        val ips = (collectInterfaceIPs() + h.apHostAddresses()).distinct()
        _networkState.value = NetworkState.LocalNetworkHosted(
            credentials = creds,
            localIpAddresses = ips
        )
    }

    private suspend fun handleSystemStop(firing: HotspotHandle, reason: HotspotStopReason) = lifecycleLock.withLock {
        if (handle !== firing) return@withLock
        val err = NetworkProvisioningError.HotspotStopped(reason.source)
        handle = null
        stopWatch = null
        _state.value = NetworkProvisioningState.Failed(err)
        _networkState.value = NetworkState.Unknown
        _events.tryEmit(NetworkProvisioningEvent.Failed(err))
        Unit
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
