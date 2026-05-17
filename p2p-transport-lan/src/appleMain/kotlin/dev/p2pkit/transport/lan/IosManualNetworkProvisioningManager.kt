package dev.p2pkit.transport.lan

import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.Peer
import dev.p2pkit.core.dsl.NetworkProvisioningConfigBuilder
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.core.provisioning.LocalNetworkConfig
import dev.p2pkit.core.provisioning.LocalNetworkResult
import dev.p2pkit.core.provisioning.ManualConnectionInfo
import dev.p2pkit.core.provisioning.NetworkProvisioningEvent
import dev.p2pkit.core.provisioning.NetworkProvisioningFactory
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.provisioning.ProvisioningContext
import dev.p2pkit.core.provisioning.WifiCredentials
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Minimum-viable iOS implementation of [NetworkProvisioningManager].
 *
 * Apple does not allow third-party iOS apps to host Wi-Fi hotspots or
 * silently join Wi-Fi networks, so [startLocalNetwork] and
 * [joinLocalNetwork] return [LocalNetworkResult.Unsupported] /
 * [JoinNetworkResult.Unsupported] respectively. Those are documented
 * limitations — they will never be implementable in this module.
 *
 * The single feature this manager DOES expose is **manual-IP fallback**:
 * - [getManualConnectionInfo] returns the local kit's `host:port` for
 *   exchanging out-of-band (e.g., to a JVM/Android peer over a chat or
 *   QR code).
 * - [createManualPeer] registers a synthetic peer keyed by
 *   `TransportHint(host, port)` so the iOS LAN data transport can dial
 *   it via `nw_endpoint_create_host` — see
 *   [IosLanDataTransport.connect]'s manual-IP fallback branch.
 *
 * The `hostAddresses` list returned by [getManualConnectionInfo] is
 * populated from `NWPathMonitor` cached state when available; otherwise
 * empty (Swift consumers can read the local IP themselves if needed via
 * the host-side OS API).
 */
public class IosManualNetworkProvisioningManager internal constructor(
    private val ctx: ProvisioningContext
) : NetworkProvisioningManager {

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

    override suspend fun startLocalNetwork(config: LocalNetworkConfig): LocalNetworkResult =
        LocalNetworkResult.Unsupported(
            "iOS cannot host Wi-Fi hotspots — Apple does not expose this to third-party apps."
        )

    override suspend fun stopLocalNetwork() {
        // No-op — nothing to stop.
    }

    override suspend fun joinLocalNetwork(credentials: WifiCredentials): JoinNetworkResult =
        JoinNetworkResult.Unsupported(
            "iOS cannot programmatically join arbitrary Wi-Fi networks — the user must use the system Settings."
        )

    override suspend fun getManualConnectionInfo(): ManualConnectionInfo? {
        val port = ctx.lanTcpPort ?: return null
        // Apple does not give us a non-loopback IP list synchronously without
        // a path monitor subscription; populating hostAddresses requires the
        // Swift consumer to read it themselves (e.g., via
        // CNCopySupportedInterfaces or NWPathMonitor on the iOS side and pass
        // it in). Returning an empty list still surfaces the port and ids,
        // which is all the dialer needs.
        return ManualConnectionInfo(
            hostAddresses = emptyList(),
            port = port,
            appId = ctx.appId,
            peerId = ctx.localPeerId,
            deviceName = ctx.localDeviceName
        )
    }

    @OptIn(ExperimentalP2pApi::class)
    override suspend fun createManualPeer(host: String, port: Int): Peer {
        ctx.logger.info("provisioning: createManualPeer host=$host port=$port")
        IosLanDebug.log("provision", "createManualPeer host=$host port=$port")
        return ctx.manualPeerRegistrar.registerManualPeer(host = host, port = port)
    }
}

/**
 * Factory used by the DSL extension below.
 */
public object IosManualProvisioningFactory : NetworkProvisioningFactory {
    override fun build(context: ProvisioningContext): NetworkProvisioningManager =
        IosManualNetworkProvisioningManager(ctx = context)
}

/**
 * Register the iOS manual-IP-only provisioning module.
 *
 * Usage:
 *
 * ```kotlin
 * P2pKit.create {
 *     appId = AppId("…")
 *     deviceName = "…"
 *     transports { lan() }
 *     networkProvisioning { iosManualIp() }
 * }
 * ```
 *
 * After this is registered, Swift consumers can call
 * `kit.networkProvisioning.createManualPeer(host:port:completionHandler:)`
 * to dial a peer directly by IP — useful when NWBrowser-based discovery
 * isn't yielding results (corporate Wi-Fi blocking multicast, iOS
 * Simulator network sandbox, etc.). Hotspot host / Wi-Fi join APIs
 * remain `Unsupported`.
 */
public fun NetworkProvisioningConfigBuilder.iosManualIp() {
    register(IosManualProvisioningFactory)
}
