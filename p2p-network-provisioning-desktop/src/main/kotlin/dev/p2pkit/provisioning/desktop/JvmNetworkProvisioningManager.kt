package dev.p2pkit.provisioning.desktop

import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.core.provisioning.LocalNetworkConfig
import dev.p2pkit.core.provisioning.LocalNetworkResult
import dev.p2pkit.core.provisioning.ManualConnectionInfo
import dev.p2pkit.core.provisioning.ManualPeerRegistrar
import dev.p2pkit.core.provisioning.NetworkProvisioningEvent
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.provisioning.ProvisioningContext
import dev.p2pkit.core.provisioning.WifiCredentials
import java.net.Inet4Address
import java.net.Inet6Address
import java.net.NetworkInterface
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * JVM desktop implementation of [NetworkProvisioningManager].
 *
 * JVM cannot host a Wi-Fi hotspot or programmatically join a Wi-Fi network —
 * those are Android-only capabilities. This manager surfaces those
 * limitations via `Unsupported` results, but does implement the
 * **manual-IP fallback** path: [getManualConnectionInfo] returns the local
 * non-loopback addresses and the LAN transport's TCP port so the user can
 * exchange a `host:port` out-of-band when mDNS is blocked, and
 * [createManualPeer] registers that pair as a synthetic peer the kit can
 * dial via the normal `connect(peer)` API.
 *
 * Network state ([networkState]) is polled from `NetworkInterface` every
 * 5 s. JVM cannot reliably distinguish Wi-Fi from Ethernet across all OS
 * families, so we report [NetworkState.ConnectedToWifi] when any
 * non-loopback IPv4 is present and [NetworkState.NoNetwork] otherwise. The
 * SSID is always reported as `null`.
 */
@OptIn(ExperimentalP2pApi::class)
public class JvmNetworkProvisioningManager(
    private val ctx: ProvisioningContext,
    parentJob: Job? = null,
    private val pollIntervalMillis: Long = DEFAULT_POLL_INTERVAL_MS
) : NetworkProvisioningManager {

    private val scopeJob = SupervisorJob(parent = parentJob)
    private val scope = CoroutineScope(Dispatchers.IO + scopeJob)

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

    init {
        scope.launch { pollNetworkLoop() }
    }

    override suspend fun startLocalNetwork(config: LocalNetworkConfig): LocalNetworkResult =
        LocalNetworkResult.Unsupported(
            "JVM desktop cannot host Wi-Fi hotspots; use Android for hosting."
        )

    override suspend fun stopLocalNetwork() {
        // No-op: nothing to stop on JVM.
    }

    override suspend fun joinLocalNetwork(credentials: WifiCredentials): JoinNetworkResult =
        JoinNetworkResult.Unsupported(
            "JVM desktop cannot programmatically join Wi-Fi networks; the user must use the OS network UI."
        )

    override suspend fun getManualConnectionInfo(): ManualConnectionInfo? {
        val port = ctx.lanTcpPort ?: return null
        val ips = withContext(Dispatchers.IO) { collectNonLoopbackAddresses() }
        if (ips.isEmpty()) return null
        return ManualConnectionInfo(
            hostAddresses = ips,
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

    /** Cancels the background polling loop. Called by [P2pKit.stop]'s scope cancellation indirectly. */
    public fun close() {
        scopeJob.cancel()
    }

    // --- internals --------------------------------------------------------

    private suspend fun pollNetworkLoop() {
        while (scope.isActive) {
            runCatching {
                val ips = collectNonLoopbackAddresses()
                _networkState.value = if (ips.isEmpty()) {
                    NetworkState.NoNetwork
                } else {
                    NetworkState.ConnectedToWifi(ssid = null, localIpAddresses = ips)
                }
            }.onFailure { e ->
                ctx.logger.debug("provisioning: NetworkInterface poll failed: ${e.message}")
                _networkState.value = NetworkState.Unknown
            }
            delay(pollIntervalMillis)
        }
    }

    private fun collectNonLoopbackAddresses(): List<String> {
        val out = mutableListOf<String>()
        val interfaces = try {
            NetworkInterface.getNetworkInterfaces() ?: return emptyList()
        } catch (_: Throwable) {
            return emptyList()
        }
        for (nif in interfaces) {
            if (!nif.isUp || nif.isLoopback) continue
            for (addr in nif.inetAddresses) {
                if (addr.isLoopbackAddress || addr.isAnyLocalAddress) continue
                when (addr) {
                    is Inet4Address -> out.add(addr.hostAddress)
                    is Inet6Address -> {
                        // Link-local IPv6 addresses are not useful for LAN dialing across
                        // hosts; skip them.
                        if (!addr.isLinkLocalAddress) out.add(addr.hostAddress)
                    }
                }
            }
        }
        return out.distinct()
    }

    private companion object {
        const val DEFAULT_POLL_INTERVAL_MS: Long = 5_000
    }
}
