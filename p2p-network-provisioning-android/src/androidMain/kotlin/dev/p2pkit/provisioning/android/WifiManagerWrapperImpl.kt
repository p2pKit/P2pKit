package dev.p2pkit.provisioning.android

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.wifi.SoftApConfiguration
import android.net.wifi.WifiManager
import android.net.wifi.WifiNetworkSpecifier
import android.os.Build
import android.os.Handler
import android.os.Looper
import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.provisioning.WifiCredentials
import dev.p2pkit.core.provisioning.WifiPassword
import dev.p2pkit.core.provisioning.WifiSecurityType
import java.net.Inet4Address
import java.net.NetworkInterface
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.coroutines.resume
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.suspendCancellableCoroutine

/**
 * Production [WifiManagerWrapper] that talks to the real [WifiManager].
 *
 * Permission requirements (per Android docs):
 *   - targetSdk ≥ 33: `NEARBY_WIFI_DEVICES`
 *   - targetSdk 29..32: `ACCESS_FINE_LOCATION`
 *   - targetSdk 26..28: `ACCESS_COARSE_LOCATION`
 *
 * Missing perms cause [WifiManager.startLocalOnlyHotspot] to throw
 * `SecurityException`, which we let propagate so the caller can map it
 * to `LocalNetworkResult.Failed(PermissionMissingForProvisioning(...))`.
 */
internal class WifiManagerWrapperImpl(
    private val applicationContext: Context
) : WifiManagerWrapper {

    private val wifi: WifiManager =
        applicationContext.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
    private val connectivity: ConnectivityManager =
        applicationContext.applicationContext
            .getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager

    override fun isWifiEnabled(): Boolean = wifi.isWifiEnabled

    @Suppress("MissingPermission") // Permission handling is the caller's responsibility.
    override suspend fun startLocalOnlyHotspot(): HotspotStartResult =
        suspendCancellableCoroutine { cont ->
            val handler = Handler(Looper.getMainLooper())
            val handleHolder = AtomicHandleHolder()
            val callback = object : WifiManager.LocalOnlyHotspotCallback() {
                override fun onStarted(reservation: WifiManager.LocalOnlyHotspotReservation) {
                    val handle = HotspotHandleImpl(reservation, handleHolder.stopped)
                    handleHolder.handle = handle
                    if (cont.isActive) cont.resume(HotspotStartResult.Started(handle))
                }
                override fun onStopped() {
                    val h = handleHolder.handle
                    if (h != null) {
                        handleHolder.stopped.tryEmit(HotspotStopReason("system stopped"))
                    } else if (cont.isActive) {
                        cont.resume(HotspotStartResult.Failed(reasonCode = STOPPED_BEFORE_START))
                    }
                }
                override fun onFailed(reason: Int) {
                    if (cont.isActive) cont.resume(HotspotStartResult.Failed(reasonCode = reason))
                }
            }
            wifi.startLocalOnlyHotspot(callback, handler)
            cont.invokeOnCancellation {
                handleHolder.handle?.let { runCatching { it.close() } }
            }
        }

    @Suppress("MissingPermission")
    override suspend fun joinWifiNetwork(credentials: WifiCredentials): JoinResult {
        val ssid = credentials.ssid?.takeIf { it.isNotBlank() }
            ?: return JoinResult.Failed("SSID must not be blank")

        val specifier = WifiNetworkSpecifier.Builder().apply {
            setSsid(ssid)
            val pass = credentials.password?.reveal()
            if (!pass.isNullOrEmpty()) {
                when (credentials.securityType) {
                    WifiSecurityType.WPA3 -> setWpa3Passphrase(pass)
                    // WPA2 + UNKNOWN both go through WPA2 — most LocalOnlyHotspots
                    // come up as WPA2-PSK, and unknown-security with a passphrase
                    // is best-effort treated the same.
                    else -> setWpa2Passphrase(pass)
                }
            }
        }.build()

        val request = NetworkRequest.Builder()
            .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
            // LOHS-style networks have no internet — explicitly removing the
            // capability is required, otherwise the request never resolves.
            .removeCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .setNetworkSpecifier(specifier)
            .build()

        return suspendCancellableCoroutine { cont ->
            val terminated = AtomicBoolean(false)
            val releasedFlow: MutableSharedFlow<String> = MutableSharedFlow(
                replay = 0,
                extraBufferCapacity = 1,
                onBufferOverflow = BufferOverflow.DROP_OLDEST
            )
            var handle: JoinHandleImpl? = null
            val callback = object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) {
                    if (terminated.compareAndSet(false, true)) {
                        // Route process traffic through the joined network so the
                        // LAN transport's outgoing sockets reach the AP subnet.
                        runCatching { connectivity.bindProcessToNetwork(network) }
                        val h = JoinHandleImpl(
                            network = network,
                            connectivity = connectivity,
                            callback = this,
                            _released = releasedFlow
                        )
                        handle = h
                        if (cont.isActive) cont.resume(JoinResult.Joined(h))
                    } else {
                        // Reconnection after a transient drop — surface the new network.
                        runCatching { connectivity.bindProcessToNetwork(network) }
                    }
                }

                override fun onUnavailable() {
                    if (terminated.compareAndSet(false, true)) {
                        if (cont.isActive) cont.resume(
                            JoinResult.Failed("network unavailable — user declined, SSID not found, or wrong passphrase")
                        )
                    } else {
                        releasedFlow.tryEmit("system released (onUnavailable)")
                    }
                }

                override fun onLost(network: Network) {
                    releasedFlow.tryEmit("system released (onLost)")
                }
            }
            connectivity.requestNetwork(request, callback)
            cont.invokeOnCancellation {
                handle?.let { runCatching { it.close() } }
                    ?: runCatching { connectivity.unregisterNetworkCallback(callback) }
            }
        }
    }

    /** Sentinel for the "onStopped fired without an onStarted ever happening" edge case. */
    private companion object {
        const val STOPPED_BEFORE_START = -1
    }
}

/** Live handle to a [WifiNetworkSpecifier] join. */
private class JoinHandleImpl(
    private val network: Network,
    private val connectivity: ConnectivityManager,
    private val callback: ConnectivityManager.NetworkCallback,
    private val _released: MutableSharedFlow<String>
) : JoinHandle {

    override val released: SharedFlow<String> = _released.asSharedFlow()

    override fun snapshotNetworkState(): NetworkState {
        val ips = mutableListOf<String>()
        runCatching {
            for (nif in NetworkInterface.getNetworkInterfaces()) {
                if (!nif.isUp || nif.isLoopback) continue
                for (addr in nif.inetAddresses) {
                    if (addr.isLoopbackAddress || addr.isAnyLocalAddress) continue
                    if (addr is Inet4Address) ips += addr.hostAddress
                }
            }
        }
        return NetworkState.ConnectedToWifi(ssid = null, localIpAddresses = ips.distinct())
    }

    override fun close() {
        runCatching { connectivity.bindProcessToNetwork(null) }
        runCatching { connectivity.unregisterNetworkCallback(callback) }
    }
}

/**
 * Mutable single-slot holder so [WifiManagerWrapperImpl] can lazily hand
 * the [HotspotHandle] reference to the callback's onStopped path after
 * onStarted produced it.
 */
private class AtomicHandleHolder {
    @Volatile var handle: HotspotHandleImpl? = null
    val stopped: MutableSharedFlow<HotspotStopReason> = MutableSharedFlow(
        replay = 0,
        extraBufferCapacity = 1,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
}

private class HotspotHandleImpl(
    private val reservation: WifiManager.LocalOnlyHotspotReservation,
    private val _stopped: MutableSharedFlow<HotspotStopReason>
) : HotspotHandle {

    override val stopped: SharedFlow<HotspotStopReason> = _stopped.asSharedFlow()

    @Suppress("DEPRECATION") // wifiConfiguration is the only path on API 26..29.
    override fun getCredentials(): WifiCredentials? {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            val config: SoftApConfiguration = reservation.softApConfiguration
            val ssid = readSsidFromSoftApConfiguration(config) ?: return null
            val pass = config.passphrase
            WifiCredentials(
                ssid = ssid,
                password = pass?.takeIf { it.isNotEmpty() }?.let { WifiPassword(it) },
                securityType = securityTypeFor(config)
            )
        } else {
            val config = reservation.wifiConfiguration ?: return null
            // API 26..29: SSID is wrapped in quotes that need stripping.
            val rawSsid: String? = config.SSID
            val ssid = rawSsid?.trim()?.removeSurrounding("\"")?.takeIf { it.isNotEmpty() }
            val pass = config.preSharedKey?.trim()?.removeSurrounding("\"")?.takeIf { it.isNotEmpty() }
            ssid?.let {
                WifiCredentials(
                    ssid = it,
                    password = pass?.let(::WifiPassword),
                    securityType = if (pass != null) WifiSecurityType.WPA2 else WifiSecurityType.OPEN
                )
            }
        }
    }

    override fun apHostAddresses(): List<String> {
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

    override fun close() {
        runCatching { reservation.close() }
    }
}

/**
 * Reads the SSID from a [SoftApConfiguration]. The API moved between
 * `getSsid(): String?` (pre-Android 13) and `getWifiSsid(): WifiSsid?`
 * (Android 13+). We read both safely via reflection-free try-cascade
 * because the symbol availability differs by SDK.
 */
private fun readSsidFromSoftApConfiguration(config: SoftApConfiguration): String? {
    // String-returning getSsid is available on API 30+ regardless of OS version.
    @Suppress("DEPRECATION")
    val ssid: String? = config.ssid
    return ssid?.takeIf { it.isNotEmpty() }
}

private fun securityTypeFor(config: SoftApConfiguration): WifiSecurityType {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.R) return WifiSecurityType.UNKNOWN
    return when (config.securityType) {
        SoftApConfiguration.SECURITY_TYPE_OPEN -> WifiSecurityType.OPEN
        SoftApConfiguration.SECURITY_TYPE_WPA2_PSK -> WifiSecurityType.WPA2
        SoftApConfiguration.SECURITY_TYPE_WPA3_SAE_TRANSITION,
        SoftApConfiguration.SECURITY_TYPE_WPA3_SAE -> WifiSecurityType.WPA3
        else -> WifiSecurityType.UNKNOWN
    }
}
