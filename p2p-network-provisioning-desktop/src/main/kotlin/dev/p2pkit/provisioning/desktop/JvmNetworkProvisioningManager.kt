package dev.p2pkit.provisioning.desktop

import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
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
import java.net.SocketException
import java.util.Collections
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
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
 * Network state ([networkState]) is polled from active `NetworkInterface`
 * instances every 5 s. JVM cannot reliably distinguish Wi-Fi from Ethernet
 * across all OS families, so we report [NetworkState.ConnectedToWifi] when
 * usable non-loopback addresses are present and [NetworkState.NoNetwork]
 * otherwise. Down, virtual, and link-local candidates are excluded; private
 * LAN addresses are ranked first. The SSID is always reported as `null`.
 */
@OptIn(ExperimentalP2pApi::class)
public class JvmNetworkProvisioningManager private constructor(
    private val ctx: ProvisioningContext,
    pollIntervalMillisInput: Long,
    private val addressScanner: NetworkAddressScanner
) : NetworkProvisioningManager {

    private val pollIntervalMillis: Long = pollIntervalMillisInput.also {
        require(it > 0) { "pollIntervalMillis must be positive" }
    }

    /**
     * Creates the desktop provisioning sidecar. Polling must be positive so
     * the background loop cannot become a busy-spin or silently disable
     * cancellation fairness.
     */
    public constructor(
        ctx: ProvisioningContext,
        pollIntervalMillis: Long = DEFAULT_POLL_INTERVAL_MS
    ) : this(ctx, pollIntervalMillis, NetworkAddressScanner { collectNonLoopbackAddresses() })

    /** Host-test seam for deterministic address/fatal-error coverage. */
    internal constructor(
        ctx: ProvisioningContext,
        pollIntervalMillis: Long,
        addressScanner: () -> List<String>
    ) : this(ctx, pollIntervalMillis, NetworkAddressScanner(addressScanner))

    private val scopeJob = SupervisorJob(parent = ctx.parentJob)
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
        val port = ctx.lanTcpPort() ?: return null
        val ips = withContext(Dispatchers.IO) { addressScanner.scan() }
        if (ips.isEmpty()) return null
        return ManualConnectionInfo(
            hostAddresses = ips,
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

    /** Cancels the background polling loop. Called indirectly by `P2pKit.stop()` scope cancellation. */
    public fun close() {
        scopeJob.cancel()
    }

    // --- internals --------------------------------------------------------

    private suspend fun pollNetworkLoop() {
        while (scope.isActive) {
            try {
                val ips = addressScanner.scan()
                _networkState.value = if (ips.isEmpty()) {
                    NetworkState.NoNetwork
                } else {
                    NetworkState.ConnectedToWifi(ssid = null, localIpAddresses = ips)
                }
            } catch (e: SocketException) {
                ctx.logger.debug("provisioning: NetworkInterface poll failed: ${e.message}")
                _networkState.value = NetworkState.Unknown
            } catch (e: kotlinx.coroutines.CancellationException) {
                throw e
            }
            delay(pollIntervalMillis)
        }
    }

    private companion object {
        const val DEFAULT_POLL_INTERVAL_MS: Long = 5_000
    }
}

internal fun interface NetworkAddressScanner {
    fun scan(): List<String>
}

/**
 * Collects addresses from active, non-virtual interfaces. Java does not
 * expose a portable default-route API, so the scan uses interface liveness
 * and address-family characteristics rather than claiming every stale
 * address as Wi-Fi. Socket failures are recoverable; fatal Errors and
 * cancellation are deliberately allowed to propagate.
 */
internal fun collectNonLoopbackAddresses(): List<String> {
    val interfaces = try {
        NetworkInterface.getNetworkInterfaces()?.asSequence().orEmpty()
    } catch (e: SocketException) {
        throw e
    }
    val candidates = mutableListOf<NetworkAddressCandidate>()
    for (nif in interfaces) {
        val active = try {
            nif.isUp && !nif.isLoopback && !nif.isVirtual
        } catch (e: SocketException) {
            continue
        }
        if (!active) continue
        val addresses = try {
            Collections.list(nif.inetAddresses)
        } catch (e: SocketException) {
            continue
        }
        for (addr in addresses) {
            val host = addr.hostAddress ?: continue
            when (addr) {
                is Inet4Address -> candidates += NetworkAddressCandidate(
                    hostAddress = host,
                    interfaceActive = true,
                    linkLocal = addr.isLinkLocalAddress,
                    siteLocal = addr.isSiteLocalAddress
                )
                is Inet6Address -> if (!addr.isLinkLocalAddress) {
                    candidates += NetworkAddressCandidate(
                        hostAddress = host,
                        interfaceActive = true,
                        linkLocal = false,
                        siteLocal = addr.isSiteLocalAddress
                    )
                }
            }
        }
    }
    return selectUsableNetworkAddresses(candidates)
}

internal data class NetworkAddressCandidate(
    val hostAddress: String,
    val interfaceActive: Boolean,
    val linkLocal: Boolean,
    val siteLocal: Boolean
)

/** Removes stale/ineligible candidates and prefers private LAN addresses. */
internal fun selectUsableNetworkAddresses(
    candidates: List<NetworkAddressCandidate>
): List<String> = candidates.asSequence()
    .filter { it.interfaceActive && !it.linkLocal }
    .distinctBy { it.hostAddress }
    .sortedWith(compareByDescending<NetworkAddressCandidate> { it.siteLocal })
    .map { it.hostAddress }
    .toList()
