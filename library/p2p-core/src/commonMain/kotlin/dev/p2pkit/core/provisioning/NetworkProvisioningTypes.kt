package dev.p2pkit.core.provisioning

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.NetworkProvisioningError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.internal.immutableListSnapshot
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

    /**
     * @throws IllegalArgumentException if [host] is unsafe/blank or [port] is
     *   outside `1..65535`.
     */
    @ExperimentalP2pApi
    @Throws(Exception::class)
    @Deprecated(
        message = "Secure manual-IP connections require an expected fingerprint. Use the fingerprint overload.",
        replaceWith = ReplaceWith("createManualPeer(host, port, expectedFingerprint)")
    )
    public suspend fun createManualPeer(host: String, port: Int): Peer

    /**
     * Register a manual endpoint pinned to an out-of-band v2 identity.
     *
     * @throws IllegalArgumentException if [host] is unsafe/blank or [port] is
     *   outside `1..65535`.
     */
    @ExperimentalP2pApi
    @Throws(Exception::class)
    public suspend fun createManualPeer(
        host: String,
        port: Int,
        expectedFingerprint: PeerFingerprint
    ): Peer

    /**
     * Permanently dispose this manager and every resource it owns.
     *
     * Idempotent and concurrency-safe: concurrent callers join one cleanup
     * transaction. The method returns only after bounded cleanup has been
     * attempted. Once closing begins, no later operation may acquire or
     * publish a native handle. A cleanup failure is reported after the
     * manager becomes terminal; retained cleanup ownership may be retried by
     * a later `close()` call.
     */
    @Throws(Exception::class)
    public suspend fun close()
}

/** Provisioning manager's own lifecycle, distinct from the underlying network. */
public sealed class NetworkProvisioningState {
    public data object Idle : NetworkProvisioningState()
    public data object StartingLocalNetwork : NetworkProvisioningState()
    public data object LocalNetworkRunning : NetworkProvisioningState()
    public data object JoiningNetwork : NetworkProvisioningState()
    public data object JoinedNetwork : NetworkProvisioningState()
    public data object StoppingLocalNetwork : NetworkProvisioningState()
    public data object Closing : NetworkProvisioningState()
    public data object Closed : NetworkProvisioningState()
    public data class Failed(val error: NetworkProvisioningError) : NetworkProvisioningState()
}

/** Observed state of the host device's network. */
public sealed class NetworkState {
    public data object Unknown : NetworkState()
    public data object NoNetwork : NetworkState()
    public class ConnectedToWifi(
        /** SSID, or `null` if the OS withholds it (e.g., Android 10+ without location). */
        public val ssid: String?,
        localIpAddresses: List<String>
    ) : NetworkState() {
        /** Stable, unmodifiable snapshot of local interface addresses. */
        public val localIpAddresses: List<String> = immutableListSnapshot(localIpAddresses)

        public operator fun component1(): String? = ssid
        public operator fun component2(): List<String> = localIpAddresses

        public fun copy(
            ssid: String? = this.ssid,
            localIpAddresses: List<String> = this.localIpAddresses
        ): ConnectedToWifi = ConnectedToWifi(ssid, localIpAddresses)

        override fun equals(other: Any?): Boolean =
            this === other ||
                other is ConnectedToWifi &&
                ssid == other.ssid &&
                localIpAddresses == other.localIpAddresses

        override fun hashCode(): Int = 31 * (ssid?.hashCode() ?: 0) + localIpAddresses.hashCode()

        override fun toString(): String =
            "ConnectedToWifi(ssid=$ssid, localIpAddresses=$localIpAddresses)"
    }

    public class ConnectedToEthernet(localIpAddresses: List<String>) : NetworkState() {
        /** Stable, unmodifiable snapshot of local interface addresses. */
        public val localIpAddresses: List<String> = immutableListSnapshot(localIpAddresses)

        public operator fun component1(): List<String> = localIpAddresses

        public fun copy(
            localIpAddresses: List<String> = this.localIpAddresses
        ): ConnectedToEthernet = ConnectedToEthernet(localIpAddresses)

        override fun equals(other: Any?): Boolean =
            this === other ||
                other is ConnectedToEthernet && localIpAddresses == other.localIpAddresses

        override fun hashCode(): Int = localIpAddresses.hashCode()

        override fun toString(): String =
            "ConnectedToEthernet(localIpAddresses=$localIpAddresses)"
    }

    public class LocalNetworkHosted(
        /** Credentials of the hosted hotspot, or `null` if the OEM did not expose them. */
        public val credentials: WifiCredentials?,
        localIpAddresses: List<String>
    ) : NetworkState() {
        /** Stable, unmodifiable snapshot of local interface addresses. */
        public val localIpAddresses: List<String> = immutableListSnapshot(localIpAddresses)

        public operator fun component1(): WifiCredentials? = credentials
        public operator fun component2(): List<String> = localIpAddresses

        public fun copy(
            credentials: WifiCredentials? = this.credentials,
            localIpAddresses: List<String> = this.localIpAddresses
        ): LocalNetworkHosted = LocalNetworkHosted(credentials, localIpAddresses)

        override fun equals(other: Any?): Boolean =
            this === other ||
                other is LocalNetworkHosted &&
                credentials == other.credentials &&
                localIpAddresses == other.localIpAddresses

        override fun hashCode(): Int =
            31 * (credentials?.hashCode() ?: 0) + localIpAddresses.hashCode()

        override fun toString(): String =
            "LocalNetworkHosted(credentials=$credentials, localIpAddresses=$localIpAddresses)"
    }
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
public class ManualConnectionInfo(
    hostAddresses: List<String>,
    public val port: Int,
    public val appId: AppId,
    public val peerId: PeerId,
    public val deviceName: String,
    /** Local authenticated identity to exchange out of band in secure v2. */
    public val fingerprint: PeerFingerprint? = null,
    /** Canonical AppId-bound QR payload carrying [fingerprint], when secure. */
    public val pairingQr: String? = null
) {
    /** Stable, unmodifiable snapshot of advertised manual connection addresses. */
    public val hostAddresses: List<String> = immutableListSnapshot(hostAddresses)

    public operator fun component1(): List<String> = hostAddresses
    public operator fun component2(): Int = port
    public operator fun component3(): AppId = appId
    public operator fun component4(): PeerId = peerId
    public operator fun component5(): String = deviceName
    public operator fun component6(): PeerFingerprint? = fingerprint
    public operator fun component7(): String? = pairingQr

    public fun copy(
        hostAddresses: List<String> = this.hostAddresses,
        port: Int = this.port,
        appId: AppId = this.appId,
        peerId: PeerId = this.peerId,
        deviceName: String = this.deviceName,
        fingerprint: PeerFingerprint? = this.fingerprint,
        pairingQr: String? = this.pairingQr
    ): ManualConnectionInfo = ManualConnectionInfo(
        hostAddresses,
        port,
        appId,
        peerId,
        deviceName,
        fingerprint,
        pairingQr
    )

    override fun equals(other: Any?): Boolean =
        this === other ||
            other is ManualConnectionInfo &&
            hostAddresses == other.hostAddresses &&
            port == other.port &&
            appId == other.appId &&
            peerId == other.peerId &&
            deviceName == other.deviceName &&
            fingerprint == other.fingerprint &&
            pairingQr == other.pairingQr

    override fun hashCode(): Int {
        var result = hostAddresses.hashCode()
        result = 31 * result + port
        result = 31 * result + appId.hashCode()
        result = 31 * result + peerId.hashCode()
        result = 31 * result + deviceName.hashCode()
        result = 31 * result + (fingerprint?.hashCode() ?: 0)
        result = 31 * result + (pairingQr?.hashCode() ?: 0)
        return result
    }

    override fun toString(): String =
        "ManualConnectionInfo(hostAddresses=$hostAddresses, port=$port, appId=$appId, " +
            "peerId=$peerId, deviceName=$deviceName, fingerprint=$fingerprint, pairingQr=$pairingQr)"
}

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
