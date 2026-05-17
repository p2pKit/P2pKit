package dev.p2pkit.core

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import dev.p2pkit.core.NetworkPathStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Android network-path observer backed by `ConnectivityManager.NetworkCallback`.
 *
 * Construct one with the host app's `applicationContext` and register it via
 * the kit DSL:
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
 * Watches the system's default network with `NET_CAPABILITY_INTERNET`. On
 * `onAvailable` / `onCapabilitiesChanged` (validated) → [NetworkPathStatus.Satisfied].
 * On `onLost` (no other matching network remaining) → [NetworkPathStatus.Unsatisfied].
 *
 * Note: this observer only consults `INTERNET` capability — LAN-only
 * scenarios (e.g., joined to a peer's hotspot with no upstream internet)
 * may report `Unsatisfied` even though the LAN is reachable. The SDK's
 * keep-alive PING / read-error path is the secondary signal for that
 * case, and the reconnect machinery still kicks in via the existing
 * mechanisms — this observer just adds a faster trigger for the common
 * full-network-drop case.
 *
 * Requires `ACCESS_NETWORK_STATE` (already required by the LAN
 * transport — install-time permission, no runtime prompt).
 */
public class AndroidNetworkPathObserver(
    context: Context,
    private val logger: P2pLogger = P2pLogger.NoOp
) : NetworkPathObserver {

    private val appContext: Context = context.applicationContext
    private val connectivity: ConnectivityManager =
        appContext.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager

    private val _status = MutableStateFlow<NetworkPathStatus>(NetworkPathStatus.Unknown)
    public override val status: StateFlow<NetworkPathStatus> = _status.asStateFlow()

    private val startMutex = Mutex()
    private val activeNetworks: MutableSet<Network> = mutableSetOf()
    @Volatile
    private var callback: ConnectivityManager.NetworkCallback? = null

    public override suspend fun start(): Unit = startMutex.withLock {
        if (callback != null) return@withLock
        val cb = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                synchronized(activeNetworks) { activeNetworks.add(network) }
                _status.value = NetworkPathStatus.Satisfied
            }

            override fun onLost(network: Network) {
                val empty = synchronized(activeNetworks) {
                    activeNetworks.remove(network)
                    activeNetworks.isEmpty()
                }
                // Only flip to Unsatisfied when the last validated network
                // has gone away — handover events (Wi-Fi → cellular) emit
                // onAvailable for the new network before onLost for the old,
                // so flipping eagerly would cause a spurious Unsatisfied
                // tick during seamless transitions.
                if (empty) _status.value = NetworkPathStatus.Unsatisfied
            }

            override fun onCapabilitiesChanged(
                network: Network,
                capabilities: NetworkCapabilities
            ) {
                // No-op for now — we only care about presence/absence, not
                // whether the network is metered, VPN'd, etc.
            }
        }
        val request = NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build()
        try {
            connectivity.registerNetworkCallback(request, cb)
            callback = cb
        } catch (e: Throwable) {
            logger.warn("registerNetworkCallback failed; path observer will report Unknown", e)
        }
    }

    public override suspend fun close(): Unit = startMutex.withLock {
        val cb = callback ?: return@withLock
        runCatching { connectivity.unregisterNetworkCallback(cb) }
        callback = null
        synchronized(activeNetworks) { activeNetworks.clear() }
    }
}
