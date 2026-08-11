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
 *   - device and targetSdk ≥ 33: `NEARBY_WIFI_DEVICES`
 *   - otherwise: `ACCESS_FINE_LOCATION`
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

    private val pendingCleanup = RetryableCleanupRegistry()
    private val hotspotRequest = PendingNativeRequest()

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
        return requiredProvisioningRuntimePermission(
            deviceSdk = Build.VERSION.SDK_INT,
            targetSdk = targetSdk
        )
    }

    @Suppress("MissingPermission") // Permission handling is the caller's responsibility.
    override suspend fun startLocalOnlyHotspot(): HotspotStartResult {
        val requestToken = hotspotRequest.tryBegin()
        if (requestToken == null) {
            return HotspotStartResult.CleanupPending(
                "an earlier LocalOnlyHotspot request is still awaiting its terminal OS callback"
            )
        }
        return suspendCancellableCoroutine { cont ->
            val handler = Handler(Looper.getMainLooper())
            val handleHolder = HotspotReservationOwner<HotspotHandleImpl>()
            val callback = object : WifiManager.LocalOnlyHotspotCallback() {
                override fun onStarted(reservation: WifiManager.LocalOnlyHotspotReservation) {
                    try {
                        val handle = HotspotHandleImpl(reservation, handleHolder.stopped)
                        if (cont.isActive && handleHolder.tryInstall(handle)) {
                            val resumed = runCatching {
                                cont.resume(HotspotStartResult.Started(handle))
                                true
                            }.getOrDefault(false)
                            if (!resumed) {
                                handleHolder.cancelAndTake()?.let(::closeOrRetain)
                            }
                        } else {
                            // Caller cancelled (e.g. withTimeout) before the OS
                            // callback: nobody will ever own this reservation, so
                            // release it immediately instead of leaking the
                            // hotspot until process death (AUDIT-2026-06 fix).
                            handleHolder.cancelAndTake()?.let(::closeOrRetain)
                            closeOrRetain(handle)
                        }
                    } finally {
                        hotspotRequest.complete(requestToken)
                    }
                }
                override fun onStopped() {
                    val h = handleHolder.current()
                    if (h != null) {
                        handleHolder.stopped.tryEmit(HotspotStopReason("system stopped"))
                    } else if (cont.isActive) {
                        hotspotRequest.complete(requestToken)
                        runCatching {
                            cont.resume(HotspotStartResult.Failed(reasonCode = STOPPED_BEFORE_START))
                        }
                    } else {
                        hotspotRequest.complete(requestToken)
                    }
                }
                override fun onFailed(reason: Int) {
                    hotspotRequest.complete(requestToken)
                    if (cont.isActive) {
                        runCatching { cont.resume(HotspotStartResult.Failed(reasonCode = reason)) }
                    }
                }
            }
            val w = wifi
            if (w == null) {
                hotspotRequest.complete(requestToken)
                if (cont.isActive) cont.resume(HotspotStartResult.Failed(reasonCode = STOPPED_BEFORE_START))
                return@suspendCancellableCoroutine
            }
            try {
                w.startLocalOnlyHotspot(callback, handler)
            } catch (failure: Throwable) {
                hotspotRequest.complete(requestToken)
                throw failure
            }
            cont.invokeOnCancellation {
                handleHolder.cancelAndTake()?.let(::closeOrRetain)
            }
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
                            owner.closeAndTake()?.let(::closeOrRetain)
                            unregisterOrRetain(this)
                            return
                        }
                        val bindingToken = Any()
                        if (!ProcessBindingArbiter.tryAcquire(bindingToken)) {
                            owner.closeAndTake()
                            unregisterOrRetain(this)
                            if (cont.isActive) {
                                runCatching {
                                    cont.resume(
                                        JoinResult.Failed("another provisioning manager owns the process network binding")
                                    )
                                }
                            }
                            return
                        }
                        val h = JoinHandleImpl(
                            network = network,
                            connectivity = connectivity,
                            callback = this,
                            _released = releasedFlow,
                            owner = owner,
                            bindingToken = bindingToken
                        )
                        if (!owner.install(h)) {
                            closeOrRetain(h)
                            return
                        }
                        val bound = try {
                            h.bindInitial()
                        } catch (e: Exception) {
                            owner.closeAndTake()?.let(::closeOrRetain)
                                ?: closeOrRetain(h)
                            if (cont.isActive) {
                                runCatching { cont.resumeWith(Result.failure(e)) }
                            }
                            return
                        }
                        if (!bound) {
                            owner.closeAndTake()?.let(::closeOrRetain)
                                ?: closeOrRetain(h)
                            if (cont.isActive) {
                                runCatching {
                                    cont.resume(
                                        JoinResult.Failed("bindProcessToNetwork rejected the joined network")
                                    )
                                }
                            }
                            return
                        }
                        val delivered = owner.tryDeliver(h) {
                            if (!cont.isActive) {
                                false
                            } else {
                                runCatching {
                                    cont.resume(JoinResult.Joined(h))
                                    true
                                }.getOrDefault(false)
                            }
                        }
                        if (!delivered) {
                            owner.closeAndTake()?.let(::closeOrRetain)
                                ?: closeOrRetain(h)
                            if (cont.isActive) {
                                runCatching {
                                    cont.resume(JoinResult.Failed("network was released before join completed"))
                                }
                            }
                            return
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
                        unregisterOrRetain(this)
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
                        unregisterOrRetain(this)
                        if (cont.isActive) {
                            runCatching {
                                cont.resume(
                                    JoinResult.Failed("network unavailable — user declined, SSID not found, or wrong passphrase")
                                )
                            }
                        }
                    } else {
                        val terminal = owner.closeAndTakeWithDelivery()
                        terminal.handle?.let(::closeOrRetain)
                        if (terminal.newlyClosed) {
                            if (terminal.wasDelivered) {
                                releasedFlow.tryEmit("system released (onUnavailable)")
                            } else if (cont.isActive) {
                                runCatching {
                                    cont.resume(
                                        JoinResult.Failed(
                                            "network unavailable before join completed"
                                        )
                                    )
                                }
                            }
                        }
                    }
                }

                override fun onLost(network: Network) {
                    val current = owner.current()
                    val terminal = current?.claimReleaseIfCurrent(network)
                    if (current != null && terminal != null) {
                        closeOrRetain(current)
                        if (terminal.wasDelivered) {
                            releasedFlow.tryEmit("system released (onLost)")
                        } else if (cont.isActive) {
                            runCatching {
                                cont.resume(
                                    JoinResult.Failed("network was lost before join completed")
                                )
                            }
                        }
                    }
                }
            }
            try {
                connectivity.requestNetwork(request, callback)
            } catch (e: Exception) {
                owner.closeAndTake()
                unregisterOrRetain(callback)
                // Preserve SecurityException so the manager can produce the
                // typed PermissionMissingForProvisioning result promised by
                // this seam. Other synchronous platform failures are mapped
                // to PlatformError by the same manager boundary.
                throw e
            }
            cont.invokeOnCancellation {
                owner.closeAndTake()?.let(::closeOrRetain)
                    ?: unregisterOrRetain(callback)
            }
        }
    }

    override fun closePendingResources(): List<Throwable> = buildList {
        addAll(pendingCleanup.retryAll())
        if (hotspotRequest.isPending()) {
            add(
                IllegalStateException(
                    "LocalOnlyHotspot request is still awaiting its terminal OS callback"
                )
            )
        }
    }

    private fun closeOrRetain(handle: HotspotHandleImpl) {
        pendingCleanup.runOrRetain(handle, handle::close)
    }

    private fun closeOrRetain(handle: JoinHandleImpl) {
        pendingCleanup.runOrRetain(handle, handle::close)
    }

    private fun unregisterOrRetain(callback: ConnectivityManager.NetworkCallback) {
        pendingCleanup.runOrRetain(callback) {
            unregisterNetworkCallback(connectivity, callback)
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

    private val networkLease = CurrentNetworkLease(network)
    private val cleanup = RetryableJoinCleanup(
        clearProcessBinding = { connectivity.bindProcessToNetwork(null) },
        unregisterCallback = { unregisterNetworkCallback(connectivity, callback) },
        releaseBindingToken = { ProcessBindingArbiter.release(bindingToken) },
        // Cleanup failures are propagated to the manager or retained by the
        // wrapper. The released flow remains a lifecycle signal, not a second
        // diagnostics channel that could obscure the actual terminal cause.
        report = {}
    )

    override val released: SharedFlow<String> = _released.asSharedFlow()

    override fun snapshotNetworkState(): NetworkState {
        val current = networkLease.snapshot()
        val addresses = runCatching {
            connectivity.getLinkProperties(current)
                ?.linkAddresses
                ?.mapNotNull { it.address.hostAddress }
                .orEmpty()
        }.getOrElse { emptyList() }
        return networkStateFromJoinedAddresses(addresses)
    }

    override fun close() {
        networkLease.close {
            owner.markClosed(this)
            cleanup.close()
        }
    }

    fun bindInitial(): Boolean = cleanup.bindInitial {
        connectivity.bindProcessToNetwork(networkLease.snapshot())
    }

    fun rebind(next: Network): Boolean {
        val bound = networkLease.rebind(
            next = next,
            canRebind = {
                owner.current() === this && ProcessBindingArbiter.isOwner(bindingToken)
            },
            bind = { cleanup.rebind { connectivity.bindProcessToNetwork(next) } }
        )
        if (!bound) _released.tryEmit("system released (rebind rejected)")
        return bound
    }

    /** Atomically rejects a delayed loss callback for a superseded network. */
    fun claimReleaseIfCurrent(lost: Network): JoinOwnerClosure<JoinHandleImpl>? {
        var closure: JoinOwnerClosure<JoinHandleImpl>? = null
        val claimed = networkLease.claimLoss(
            lost = lost,
            canClaim = { owner.current() === this },
            onClaim = { closure = owner.closeAndTakeWithDelivery() }
        )
        return closure.takeIf { claimed }
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
    private var delivered = false
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

    /**
     * Linearization point between a live handle and continuation delivery.
     * Terminal callbacks use the same lock, so exactly one side can win.
     */
    fun tryDeliver(expected: T, deliver: () -> Boolean): Boolean = synchronized(lock) {
        if (closed || delivered || handle !== expected) return@synchronized false
        val succeeded = runCatching(deliver).getOrDefault(false)
        if (!succeeded || closed || handle !== expected) {
            false
        } else {
            delivered = true
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

    fun closeAndTakeWithDelivery(): JoinOwnerClosure<T> = synchronized(lock) {
        if (closed) {
            JoinOwnerClosure(handle = null, wasDelivered = delivered, newlyClosed = false)
        } else {
            closed = true
            val current = handle
            handle = null
            JoinOwnerClosure(handle = current, wasDelivered = delivered, newlyClosed = true)
        }
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

internal data class JoinOwnerClosure<T>(
    val handle: T?,
    val wasDelivered: Boolean,
    val newlyClosed: Boolean
)

private class HotspotHandleImpl(
    private val reservation: WifiManager.LocalOnlyHotspotReservation,
    private val _stopped: MutableSharedFlow<HotspotStopReason>
) : HotspotHandle {

    private val closeLock = Any()
    private var closed = false

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
        synchronized(closeLock) {
            if (closed) return
            reservation.close()
            closed = true
        }
    }
}

/** Treat an already-unregistered callback as successfully cleaned up. */
private fun unregisterNetworkCallback(
    connectivity: ConnectivityManager,
    callback: ConnectivityManager.NetworkCallback
) {
    try {
        connectivity.unregisterNetworkCallback(callback)
    } catch (_: IllegalArgumentException) {
        // Android throws when the request was already released. There is no
        // remaining callback ownership to retain or retry in that case.
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
