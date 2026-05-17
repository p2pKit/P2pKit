package dev.p2pkit.provisioning.android

import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.NetworkProvisioningError
import dev.p2pkit.core.Peer
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
 * - [joinLocalNetwork]: returns [JoinNetworkResult.Unsupported] until
 *   v0.2.1 task 12 (Wi-Fi join via `WifiNetworkSpecifier`) lands.
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
    private var handle: HotspotHandle? = null
    private var stopWatch: Job? = null
    private var joinHandle: JoinHandle? = null
    private var joinReleaseWatch: Job? = null

    // --- NetworkProvisioningManager surface -------------------------------

    override suspend fun startLocalNetwork(config: LocalNetworkConfig): LocalNetworkResult =
        lifecycleLock.withLock {
            if (handle != null) {
                ctx.logger.debug("provisioning: startLocalNetwork called while already running")
                return@withLock buildStartedResult(handle!!.getCredentials(), handle!!)
            }
            _state.value = NetworkProvisioningState.StartingLocalNetwork

            val startResult = runCatching { wifi.startLocalOnlyHotspot() }
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
                            handleSystemStop(reason)
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

    override suspend fun joinLocalNetwork(credentials: WifiCredentials): JoinNetworkResult =
        lifecycleLock.withLock {
            if (joinHandle != null) {
                return@withLock JoinNetworkResult.Failed(
                    NetworkProvisioningError.JoinFailed(
                        "a join is already in progress; close the kit before retrying"
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

            val joinResult = runCatching { wifi.joinWifiNetwork(credentials) }
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
                        h.released.collect { reason -> handleJoinReleased(reason) }
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

    private fun handleJoinReleased(reason: String) {
        val err = NetworkProvisioningError.JoinFailed("join released: $reason")
        joinHandle = null
        joinReleaseWatch = null
        _state.value = NetworkProvisioningState.Failed(err)
        _networkState.value = NetworkState.Unknown
        _events.tryEmit(NetworkProvisioningEvent.Failed(err))
        ctx.logger.warn("provisioning: join released — $reason")
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
            deviceName = ctx.localDeviceName
        )
    }

    @ExperimentalP2pApi
    override suspend fun createManualPeer(host: String, port: Int): Peer {
        ctx.logger.info("provisioning: createManualPeer host=$host port=$port")
        return ctx.manualPeerRegistrar.registerManualPeer(host = host, port = port)
    }

    /**
     * Cancels the background scope and releases any active hotspot or
     * Wi-Fi join. Called automatically when the kit's parent job is
     * cancelled (via [ProvisioningContext.parentJob]); apps may also call
     * it directly for explicit teardown.
     */
    public fun close() {
        scopeJob.cancel()
        runCatching { handle?.close() }
        handle = null
        runCatching { joinHandle?.close() }
        joinHandle = null
    }

    // --- internals --------------------------------------------------------

    private fun buildStartedResult(
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

    private fun buildManualInfoFromHandle(h: HotspotHandle): ManualConnectionInfo? {
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

    private fun publishStartedNetworkState(h: HotspotHandle, creds: WifiCredentials?) {
        val ips = (collectInterfaceIPs() + h.apHostAddresses()).distinct()
        _networkState.value = NetworkState.LocalNetworkHosted(
            credentials = creds,
            localIpAddresses = ips
        )
    }

    private fun handleSystemStop(reason: HotspotStopReason) {
        val err = NetworkProvisioningError.HotspotStopped(reason.source)
        handle = null
        stopWatch = null
        _state.value = NetworkProvisioningState.Failed(err)
        _networkState.value = NetworkState.Unknown
        _events.tryEmit(NetworkProvisioningEvent.Failed(err))
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
                permissions = listOf(P2pPermission.NearbyWifiDevices)
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

    private fun collectInterfaceIPs(): List<String> {
        val out = mutableListOf<String>()
        val ifs = runCatching { NetworkInterface.getNetworkInterfaces() }.getOrNull() ?: return emptyList()
        for (nif in ifs) {
            if (!nif.isUp || nif.isLoopback) continue
            for (addr in nif.inetAddresses) {
                if (addr.isLoopbackAddress || addr.isAnyLocalAddress) continue
                if (addr is Inet4Address) out += addr.hostAddress
            }
        }
        return out.distinct()
    }
}
