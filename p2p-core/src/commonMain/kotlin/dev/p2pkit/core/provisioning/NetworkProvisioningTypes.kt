package dev.p2pkit.core.provisioning

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.NetworkProvisioningError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import kotlin.jvm.JvmInline
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow

/**
 * Optional sidecar that helps two devices reach the same local network.
 *
 * The core module ships only the [UnsupportedNetworkProvisioningManager]
 * fallback, used when no factory is registered in the
 * `networkProvisioning { … }` DSL block. Real implementations live in the
 * optional platform modules: Android `LocalOnlyHotspot` hosting and
 * `WifiNetworkSpecifier` join (`:p2p-network-provisioning-android`), JVM
 * manual-IP fallback (`:p2p-network-provisioning-desktop`), and iOS
 * manual-IP (`iosManualIp()` in `:p2p-transport-lan`). The API shape is
 * locked here so consumers can mock it. See Spec §20.
 */
public interface NetworkProvisioningManager {
    public val state: StateFlow<NetworkProvisioningState>
    public val networkState: StateFlow<NetworkState>
    public val events: Flow<NetworkProvisioningEvent>

    @Throws(Exception::class)
    public suspend fun startLocalNetwork(config: LocalNetworkConfig = LocalNetworkConfig()): LocalNetworkResult
    @Throws(Exception::class)
    public suspend fun stopLocalNetwork()

    @Throws(Exception::class)
    public suspend fun joinLocalNetwork(credentials: WifiCredentials): JoinNetworkResult

    @Throws(Exception::class)
    public suspend fun getManualConnectionInfo(): ManualConnectionInfo?

    @ExperimentalP2pApi
    @Throws(Exception::class)
    @Deprecated(
        message = "Secure manual-IP connections require an expected fingerprint. Use the fingerprint overload.",
        replaceWith = ReplaceWith("createManualPeer(host, port, expectedFingerprint)")
    )
    public suspend fun createManualPeer(host: String, port: Int): Peer

    /** Register a manual endpoint pinned to an out-of-band v2 identity. */
    @ExperimentalP2pApi
    @Throws(Exception::class)
    public suspend fun createManualPeer(
        host: String,
        port: Int,
        expectedFingerprint: PeerFingerprint
    ): Peer
}

/** Provisioning manager's own lifecycle, distinct from the underlying network. */
public sealed class NetworkProvisioningState {
    public data object Idle : NetworkProvisioningState()
    public data object StartingLocalNetwork : NetworkProvisioningState()
    public data object LocalNetworkRunning : NetworkProvisioningState()
    public data object JoiningNetwork : NetworkProvisioningState()
    public data object JoinedNetwork : NetworkProvisioningState()
    public data object StoppingLocalNetwork : NetworkProvisioningState()
    public data class Failed(val error: NetworkProvisioningError) : NetworkProvisioningState()
}

/** Observed state of the host device's network. */
public sealed class NetworkState {
    public data object Unknown : NetworkState()
    public data object NoNetwork : NetworkState()
    public data class ConnectedToWifi(
        /** SSID, or `null` if the OS withholds it (e.g., Android 10+ without location). */
        val ssid: String?,
        val localIpAddresses: List<String>
    ) : NetworkState()
    public data class ConnectedToEthernet(val localIpAddresses: List<String>) : NetworkState()
    public data class LocalNetworkHosted(
        /** Credentials of the hosted hotspot, or `null` if the OEM did not expose them. */
        val credentials: WifiCredentials?,
        val localIpAddresses: List<String>
    ) : NetworkState()
}

/** Result of [NetworkProvisioningManager.startLocalNetwork]. */
public sealed class LocalNetworkResult {
    public data class Started(
        val credentials: WifiCredentials,
        val manualConnectionInfo: ManualConnectionInfo?
    ) : LocalNetworkResult()

    /** Hotspot is up but the OS would not surface SSID/password. Use [manualConnectionInfo]. */
    public data class StartedWithoutCredentials(
        val manualConnectionInfo: ManualConnectionInfo
    ) : LocalNetworkResult()

    public data class RequiresUserAction(val instruction: String) : LocalNetworkResult()
    public data class Unsupported(val reason: String) : LocalNetworkResult()
    public data class Failed(val error: NetworkProvisioningError) : LocalNetworkResult()
}

/** Result of [NetworkProvisioningManager.joinLocalNetwork]. */
public sealed class JoinNetworkResult {
    /** Request accepted; observe `events` for the final [Joined] or [Failed] outcome. */
    public data object Pending : JoinNetworkResult()
    public data class Joined(val networkState: NetworkState) : JoinNetworkResult()
    public data class RequiresUserAction(val instruction: String) : JoinNetworkResult()
    public data class Unsupported(val reason: String) : JoinNetworkResult()
    public data class Failed(val error: NetworkProvisioningError) : JoinNetworkResult()
}

/** Provisioning events emitted out-of-band. */
public sealed class NetworkProvisioningEvent {
    public data class LocalNetworkStarted(val credentials: WifiCredentials?) : NetworkProvisioningEvent()
    public data object LocalNetworkStopped : NetworkProvisioningEvent()
    public data class NetworkJoined(val state: NetworkState) : NetworkProvisioningEvent()
    public data class UserActionRequired(val instruction: String) : NetworkProvisioningEvent()
    public data class Failed(val error: NetworkProvisioningError) : NetworkProvisioningEvent()
}

/** Wi-Fi credentials advertised or accepted by provisioning. */
public data class WifiCredentials(
    val ssid: String?,
    val password: WifiPassword?,
    val securityType: WifiSecurityType
)

/** Wraps a Wi-Fi password to avoid accidental logging via `toString`. */
@JvmInline
public value class WifiPassword(private val value: String) {
    public fun reveal(): String = value
    override fun toString(): String = "***"
}

public enum class WifiSecurityType { OPEN, WPA2, WPA3, UNKNOWN }

/**
 * Info shown to a user when discovery fails and they want to connect manually.
 *
 * Carries host/port — the only public type that does so. Apps pass this back
 * via [NetworkProvisioningManager.createManualPeer] to obtain a synthetic
 * [Peer] that can be handed to [dev.p2pkit.core.P2pKit.connect].
 */
public data class ManualConnectionInfo(
    val hostAddresses: List<String>,
    val port: Int,
    val appId: AppId,
    val peerId: PeerId,
    val deviceName: String,
    /** Local authenticated identity to exchange out of band in secure v2. */
    val fingerprint: PeerFingerprint? = null,
    /** Canonical AppId-bound QR payload carrying [fingerprint], when secure. */
    val pairingQr: String? = null
)

/** Configuration hints for [NetworkProvisioningManager.startLocalNetwork]. */
public data class LocalNetworkConfig(
    /** Hint; the OS may ignore it. */
    val preferredSsidPrefix: String? = null
)

/** DSL-level enable flags for the provisioning sidecar. */
public data class NetworkProvisioningConfig(
    val enableLocalHotspot: Boolean = false,
    val enableWifiJoin: Boolean = false,
    val enableManualIpFallback: Boolean = true
)
