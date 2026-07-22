package dev.p2pkit.core

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import dev.p2pkit.core.internal.NetworkPathCallbackState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Android network-path observer backed by `ConnectivityManager.NetworkCallback`.
 *
 * `P2pKitAndroid.initialize(context)` makes this the platform default. Apps
 * may also construct one explicitly to override the lifecycle DSL:
 *
 * ```kotlin
 * P2pKit.create {
 *     ...
 *     lifecycle {
 *         reconnectPolicy = ReconnectPolicy.Enabled(maxAttempts = 8, retryDelayMillis = 500)
 *         networkPathObserver = AndroidNetworkPathObserver(applicationContext)
 *     }
 * }
 * ```
 *
 * Watches all networks reachable via Wi-Fi or Ethernet transport,
 * regardless of upstream-internet status. On `onAvailable` →
 * [NetworkPathStatus.Satisfied]. On `onLost` (and no other matching
 * network remaining) → [NetworkPathStatus.Unsatisfied].
 *
 * Semantics chosen for LAN/P2P reachability, not internet reachability.
 * A peer's hotspot Wi-Fi without upstream internet still counts as a
 * Satisfied path because peers on that LAN are reachable. This is the
 * correct signal for our reconnect machinery, which cares whether *any*
 * link is usable for TCP/Bonjour traffic — not whether the device can
 * reach the public internet.
 *
 * Cellular networks are intentionally NOT matched. LAN peer discovery
 * (NSD/Bonjour) is interface-bound and won't traverse cellular, so a
 * cellular-only device cannot reach LAN peers; reporting Satisfied in
 * that case would only trigger fruitless reconnect attempts. If the
 * device acquires Wi-Fi (e.g., joins a hotspot), this observer will
 * flip to Satisfied at that point.
 *
 * Requires `ACCESS_NETWORK_STATE` (already required by the LAN
 * transport — install-time permission, no runtime prompt).
 *
 * A successful [close] resets [status] to [NetworkPathStatus.Unknown] and
 * invalidates the callback generation. If native unregister fails, the
 * observer retains ownership so another [close] can retry; [start] will not
 * attach a second callback over that registration.
 */
public class AndroidNetworkPathObserver internal constructor(
    private val monitor: AndroidNetworkPathMonitor,
    private val logger: P2pLogger = P2pLogger.NoOp
) : NetworkPathObserver {

    public constructor(
        context: Context,
        logger: P2pLogger = P2pLogger.NoOp
    ) : this(ConnectivityManagerNetworkPathMonitor(context.applicationContext), logger)

    private val _status = MutableStateFlow<NetworkPathStatus>(NetworkPathStatus.Unknown)
    public override val status: StateFlow<NetworkPathStatus> = _status.asStateFlow()

    private val startMutex = Mutex()
    private val callbackStateLock = Any()
    private val callbackState = NetworkPathCallbackState<Any>()

    public override suspend fun start(): Unit = startMutex.withLock {
        val generation = synchronized(callbackStateLock) { callbackState.begin() }
            ?: return@withLock
        val listener = object : AndroidNetworkPathListener {
            override fun onAvailable(network: Any) {
                synchronized(callbackStateLock) {
                    callbackState.available(generation, network)?.let { _status.value = it }
                }
            }

            override fun onLost(network: Any) {
                synchronized(callbackStateLock) {
                    // Only flip after the last matching network is gone.
                    callbackState.lost(generation, network)?.let { _status.value = it }
                }
            }
        }
        try {
            monitor.register(listener)
        } catch (e: Throwable) {
            synchronized(callbackStateLock) {
                callbackState.detach(generation)?.let { _status.value = it }
            }
            logger.warn("registerNetworkCallback failed; path observer will report Unknown", e)
        }
    }

    public override suspend fun close(): Unit = startMutex.withLock {
        val generation = synchronized(callbackStateLock) { callbackState.currentGeneration() }
            ?: return@withLock
        try {
            monitor.unregister()
        } catch (e: Throwable) {
            // Keep ownership and the live generation so a later close retries
            // the exact registration instead of leaking it and attaching a
            // second callback on restart.
            logger.warn("unregisterNetworkCallback failed; path observer still owns callback", e)
            return@withLock
        }
        synchronized(callbackStateLock) {
            callbackState.detach(generation)?.let { _status.value = it }
        }
    }
}

internal interface AndroidNetworkPathListener {
    fun onAvailable(network: Any)
    fun onLost(network: Any)
}

internal interface AndroidNetworkPathMonitor {
    fun register(listener: AndroidNetworkPathListener)
    fun unregister()
}

private class ConnectivityManagerNetworkPathMonitor(context: Context) : AndroidNetworkPathMonitor {
    private val connectivity =
        context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    private var callback: ConnectivityManager.NetworkCallback? = null

    override fun register(listener: AndroidNetworkPathListener) {
        check(callback == null) { "network callback is already registered" }
        val cb = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) = listener.onAvailable(network)
            override fun onLost(network: Network) = listener.onLost(network)
        }
        val request = NetworkRequest.Builder()
            .addTransportType(NetworkCapabilities.TRANSPORT_WIFI)
            .addTransportType(NetworkCapabilities.TRANSPORT_ETHERNET)
            .build()
        connectivity.registerNetworkCallback(request, cb)
        callback = cb
    }

    override fun unregister() {
        val cb = callback ?: return
        connectivity.unregisterNetworkCallback(cb)
        callback = null
    }
}
