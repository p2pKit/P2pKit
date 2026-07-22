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
import dev.p2pkit.core.permission.P2pPermission
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
 * `ACCESS_WIFI_STATE`, `CHANGE_WIFI_STATE`, and `CHANGE_NETWORK_STATE` are
 * install-time requirements and are diagnosed by [AndroidP2pPermissionManager].
 */
internal class WifiManagerWrapperImpl(
    private val applicationContext: Context
) : WifiManagerWrapper {

    // Nullable: ethernet-only Android devices (TV boxes, IoT) have no
    // WifiManager; the previous unconditional cast NPE-crashed kit creation
    // there even though plain LAN/mDNS works fine over ethernet
    // (AUDIT-2026-06 fix).
    private val wifi: WifiManager? =
        applicationContext.applicationContext.getSystemService(Context.WIFI_SERVICE) as? WifiManager
    private val connectivity: ConnectivityManager =
        applicationContext.applicationContext
            .getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager

    override fun isWifiEnabled(): Boolean = wifi?.isWifiEnabled ?: false

    override val isLocalOnlyHotspotSupported: Boolean
        get() = wifi != null && android.os.Build.VERSION.SDK_INT >= 26

    override val isSpecifierJoinSupported: Boolean
        get() = android.os.Build.VERSION.SDK_INT >= 29

    override fun requiredRuntimePermission(): P2pPermission {
        val targetSdk = applicationContext.applicationContext.applicationInfo.targetSdkVersion
        return if (android.os.Build.VERSION.SDK_INT >= 33 && targetSdk >= 33) {
            P2pPermission.NearbyWifiDevices
        } else {
            P2pPermission.Location
        }
    }

    @Suppress("MissingPermission") // Permission handling is the caller's responsibility.
    override suspend fun startLocalOnlyHotspot(): HotspotStartResult =
        suspendCancellableCoroutine { cont ->
            val handler = Handler(Looper.getMainLooper())
            val handleHolder = HotspotReservationOwner<HotspotHandleImpl>()
            val callback = object : WifiManager.LocalOnlyHotspotCallback() {
                override fun onStarted(reservation: WifiManager.LocalOnlyHotspotReservation) {
                    val handle = HotspotHandleImpl(reservation, handleHolder.stopped)
                    if (cont.isActive && handleHolder.tryInstall(handle)) {
                        val resumed = runCatching {
                            cont.resume(HotspotStartResult.Started(handle))
                            true
                        }.getOrDefault(false)
                        if (!resumed) {
                            handleHolder.cancelAndTake()?.let { runCatching { it.close() } }
                        }
                    } else {
                        // Caller cancelled (e.g. withTimeout) before the OS
                        // callback: nobody will ever own this reservation, so
                        // release it immediately instead of leaking the
                        // hotspot until process death (AUDIT-2026-06 fix).
                        handleHolder.cancelAndTake()?.let { runCatching { it.close() } }
                        runCatching { handle.close() }
                    }
                }
                override fun onStopped() {
                    val h = handleHolder.current()
                    if (h != null) {
                        handleHolder.stopped.tryEmit(HotspotStopReason("system stopped"))
                    } else if (cont.isActive) {
                        runCatching {
                            cont.resume(HotspotStartResult.Failed(reasonCode = STOPPED_BEFORE_START))
                        }
                    }
                }
                override fun onFailed(reason: Int) {
                    if (cont.isActive) {
                        runCatching { cont.resume(HotspotStartResult.Failed(reasonCode = reason)) }
                    }
                }
            }
            val w = wifi
            if (w == null) {
                if (cont.isActive) cont.resume(HotspotStartResult.Failed(reasonCode = STOPPED_BEFORE_START))
                return@suspendCancellableCoroutine
            }
            w.startLocalOnlyHotspot(callback, handler)
            cont.invokeOnCancellation {
                handleHolder.cancelAndTake()?.let { runCatching { it.close() } }
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
            // replay=1: one-shot terminal signal; with replay=0 an emission
            // landing before the manager's watcher subscribed was silently
            // dropped (AUDIT-2026-06 fix).
            val releasedFlow: MutableSharedFlow<String> = MutableSharedFlow(
                replay = 1,
                extraBufferCapacity = 1,
                onBufferOverflow = BufferOverflow.DROP_OLDEST
            )
            val owner = JoinCallbackOwner<JoinHandleImpl>()
            val callback = object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) {
                    if (owner.claimInitial()) {
                        if (!cont.isActive) {
                            // Caller cancelled before the user approved the
                            // join: binding now would silently re-route the
                            // whole process with no owner to ever unbind it
                            // (AUDIT-2026-06 fix).
                            owner.closeAndTake()?.let { runCatching { it.close() } }
                            runCatching { connectivity.unregisterNetworkCallback(this) }
                            return
                        }
                        val bindingToken = Any()
                        val h = JoinHandleImpl(
                            network = network,
                            connectivity = connectivity,
                            callback = this,
                            _released = releasedFlow,
                            owner = owner,
                            bindingToken = bindingToken
                        )
                        if (!ProcessBindingArbiter.tryAcquire(bindingToken)) {
                            owner.closeAndTake()
                            runCatching { connectivity.unregisterNetworkCallback(this) }
                            if (cont.isActive) {
                                runCatching {
                                    cont.resume(
                                        JoinResult.Failed("another provisioning manager owns the process network binding")
                                    )
                                }
                            }
                            return
                        }
                        val bound = runCatching {
                            connectivity.bindProcessToNetwork(network)
                        }.getOrDefault(false)
                        if (!bound) {
                            h.close()
                            runCatching { connectivity.unregisterNetworkCallback(this) }
                            if (cont.isActive) {
                                runCatching {
                                    cont.resume(
                                        JoinResult.Failed("bindProcessToNetwork rejected the joined network")
                                    )
                                }
                            }
                            return
                        }
                        if (!owner.install(h)) {
                            h.close()
                            runCatching { connectivity.unregisterNetworkCallback(this) }
                            return
                        }
                        if (cont.isActive) {
                            val resumed = runCatching {
                                cont.resume(JoinResult.Joined(h))
                                true
                            }.getOrDefault(false)
                            if (!resumed) {
                                owner.closeAndTake()?.let { runCatching { it.close() } }
                                runCatching { connectivity.unregisterNetworkCallback(this) }
                            }
                        } else {
                            owner.closeAndTake()?.let { runCatching { it.close() } }
                            runCatching { connectivity.unregisterNetworkCallback(this) }
                        }
                    } else {
                        // Reconnection after a transient drop — route only while
                        // the owned handle is still live. A queued callback after
                        // close must not resurrect process-wide binding.
                        owner.current()?.rebind(network)
                    }
                }

                override fun onUnavailable() {
                    if (owner.claimInitial()) {
                        owner.closeAndTake()
                        runCatching { connectivity.unregisterNetworkCallback(this) }
                        if (cont.isActive) {
                            runCatching {
                                cont.resume(
                                    JoinResult.Failed("network unavailable — user declined, SSID not found, or wrong passphrase")
                                )
                            }
                        }
                    } else if (owner.closeIfPending()) {
                        // onAvailable may have claimed the first callback but
                        // not installed its handle yet. Make that in-flight
                        // path terminal so it cannot bind after onUnavailable.
                        runCatching { connectivity.unregisterNetworkCallback(this) }
                        if (cont.isActive) {
                            runCatching {
                                cont.resume(
                                    JoinResult.Failed("network unavailable — user declined, SSID not found, or wrong passphrase")
                                )
                            }
                        }
                    } else {
                        releasedFlow.tryEmit("system released (onUnavailable)")
                    }
                }

                override fun onLost(network: Network) {
                    releasedFlow.tryEmit("system released (onLost)")
                }
            }
            try {
                connectivity.requestNetwork(request, callback)
            } catch (e: SecurityException) {
                owner.closeAndTake()
                runCatching { connectivity.unregisterNetworkCallback(callback) }
                if (cont.isActive) {
                    runCatching {
                        cont.resume(
                            JoinResult.Failed("requestNetwork rejected the required install-time permission")
                        )
                    }
                }
                return@suspendCancellableCoroutine
            }
            cont.invokeOnCancellation {
                owner.closeAndTake()?.let { runCatching { it.close() } }
                    ?: runCatching { connectivity.unregisterNetworkCallback(callback) }
            }
        }
    }

    /** Sentinel for the "onStopped fired without an onStarted ever happening" edge case. */
    private companion object {
        const val STOPPED_BEFORE_START = -1
    }
}

/**
 * Live handle to a [WifiNetworkSpecifier] join. Reconnect callbacks can
 * replace the bound [Network] only while this handle owns the process-wide
 * binding token.
 */
private class JoinHandleImpl(
    network: Network,
    private val connectivity: ConnectivityManager,
    private val callback: ConnectivityManager.NetworkCallback,
    private val _released: MutableSharedFlow<String>,
    private val owner: JoinCallbackOwner<JoinHandleImpl>,
    private val bindingToken: Any
) : JoinHandle {

    @Volatile
    private var network: Network = network
    private val closed = AtomicBoolean(false)

    override val released: SharedFlow<String> = _released.asSharedFlow()

    override fun snapshotNetworkState(): NetworkState {
        val addresses = runCatching {
            connectivity.getLinkProperties(network)
                ?.linkAddresses
                ?.mapNotNull { it.address.hostAddress }
                .orEmpty()
        }.getOrElse { emptyList() }
        return networkStateFromJoinedAddresses(addresses)
    }

    override fun close() {
        if (!closed.compareAndSet(false, true)) return
        owner.markClosed(this)
        val unbound = runCatching { connectivity.bindProcessToNetwork(null) }
            .getOrElse {
                _released.tryEmit("process binding clear threw: ${it.message ?: it::class.simpleName}")
                false
            }
        if (!unbound) _released.tryEmit("process binding clear rejected")
        runCatching { connectivity.unregisterNetworkCallback(callback) }
            .onFailure { _released.tryEmit("network callback unregister threw: ${it.message ?: it::class.simpleName}") }
        ProcessBindingArbiter.release(bindingToken)
    }

    fun rebind(next: Network): Boolean {
        if (closed.get() || !ProcessBindingArbiter.isOwner(bindingToken)) return false
        val bound = runCatching { connectivity.bindProcessToNetwork(next) }.getOrDefault(false)
        if (!bound) {
            _released.tryEmit("system released (rebind rejected)")
            close()
            return false
        }
        network = next
        return true
    }
}

/**
 * Mutable single-slot holder so [WifiManagerWrapperImpl] can lazily hand
 * the [HotspotHandle] reference to the callback's onStopped path after
 * onStarted produced it.
 */
internal class HotspotReservationOwner<T> {
    private var handle: T? = null
    private var cancelled: Boolean = false
    // replay=1 — see releasedFlow note (AUDIT-2026-06 fix).
    val stopped: MutableSharedFlow<HotspotStopReason> = MutableSharedFlow(
        replay = 1,
        extraBufferCapacity = 1,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )

    @Synchronized
    fun tryInstall(next: T): Boolean {
        if (cancelled) return false
        handle = next
        return true
    }

    @Synchronized
    fun current(): T? = handle

    @Synchronized
    fun cancelAndTake(): T? {
        cancelled = true
        val current = handle
        handle = null
        return current
    }
}

/** Serializes the process-wide `bindProcessToNetwork` owner across managers. */
internal object ProcessBindingArbiter {
    private val lock = Any()
    private var owner: Any? = null

    fun tryAcquire(token: Any): Boolean = synchronized(lock) {
        if (owner != null) false else {
            owner = token
            true
        }
    }

    fun isOwner(token: Any): Boolean = synchronized(lock) { owner === token }

    fun release(token: Any) = synchronized(lock) {
        if (owner === token) owner = null
    }
}

internal class JoinCallbackOwner<T> {
    private val lock = Any()
    private var initialClaimed = false
    private var closed = false
    private var handle: T? = null

    fun claimInitial(): Boolean = synchronized(lock) {
        if (closed || initialClaimed) false else {
            initialClaimed = true
            true
        }
    }

    fun install(next: T): Boolean = synchronized(lock) {
        if (closed) false else {
            handle = next
            true
        }
    }

    fun current(): T? = synchronized(lock) { handle.takeUnless { closed } }

    fun closeAndTake(): T? = synchronized(lock) {
        closed = true
        val current = handle
        handle = null
        current
    }

    /** Closes only the callback phase before a live handle has been installed. */
    fun closeIfPending(): Boolean = synchronized(lock) {
        if (closed || handle != null) false else {
            closed = true
            true
        }
    }

    fun markClosed(firing: T) = synchronized(lock) {
        closed = true
        if (handle === firing) handle = null
    }
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
            // Per-interface guard: isUp/inetAddresses can throw
            // SocketException when an interface vanishes mid-scan (hotspot/
            // VPN churn — exactly when provisioning runs). Skip the bad NIC
            // instead of letting the raw exception escape (AUDIT-2026-06 fix).
            runCatching {
                if (!nif.isUp || nif.isLoopback) return@runCatching
                for (addr in nif.inetAddresses) {
                    if (addr.isLoopbackAddress || addr.isAnyLocalAddress) continue
                    if (addr is Inet4Address) out += addr.hostAddress
                }
            }
        }
        return out.distinct()
    }

    override fun close() {
        runCatching { reservation.close() }
    }
}

/**
 * Reads the SSID from a [SoftApConfiguration]. Android 13 deprecated
 * `getSsid(): String?` in favour of `getWifiSsid(): WifiSsid?`, but the
 * deprecated string getter remains available and populated on every API
 * level where `SoftApConfiguration` exists (30+), so this reads only
 * `config.ssid` with the deprecation suppressed — there is no
 * `getWifiSsid()` fallback.
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
