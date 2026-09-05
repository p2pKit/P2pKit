package dev.p2pkit.provisioning.android

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkRequest
import android.net.wifi.WifiConfiguration
import android.net.wifi.WifiManager
import android.os.Build
import android.os.Handler
import android.os.Looper
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Implementation
import org.robolectric.annotation.Implements
import org.robolectric.shadow.api.Shadow
import org.robolectric.shadows.ShadowConnectivityManager
import org.robolectric.shadows.ShadowWifiManager

/**
 * Controls framework callbacks, not the production wrapper or its ownership
 * helpers. Each Robolectric sandbox has its own services and synthetic data.
 * This fixture does not emulate Binder, radio hardware, or OEM timing.
 */
@Implements(WifiManager::class)
class AdapterWifiManagerShadow : ShadowWifiManager() {
    data class Request(val callback: WifiManager.LocalOnlyHotspotCallback, val handler: Handler) {
        fun deliver(action: WifiManager.LocalOnlyHotspotCallback.() -> Unit) {
            check(handler.looper === Looper.getMainLooper())
            check(handler.post { callback.action() })
            shadowOf(Looper.getMainLooper()).idle()
        }
    }

    val requests = mutableListOf<Request>()
    var startFailure: Throwable? = null

    @Implementation(minSdk = 26)
    protected fun startLocalOnlyHotspot(callback: WifiManager.LocalOnlyHotspotCallback, handler: Handler) {
        startFailure?.let { throw it }
        requests += Request(callback, handler)
    }
}

@Suppress("DEPRECATION") // The real adapter must read WifiConfiguration on API 26..29.
@Implements(WifiManager.LocalOnlyHotspotReservation::class, minSdk = 26)
open class AdapterReservationShadow {
    var configuration: WifiConfiguration? = null
    var closeCalls = 0
    var remainingCloseFailures = 0

    @Implementation
    protected fun getWifiConfiguration(): WifiConfiguration? = configuration

    @Implementation
    protected fun close() {
        closeCalls += 1
        if (remainingCloseFailures > 0) {
            remainingCloseFailures -= 1
            throw IllegalStateException("synthetic reservation close failure")
        }
    }
}

@Implements(ConnectivityManager::class)
class AdapterConnectivityManagerShadow : ShadowConnectivityManager() {
    data class Request(val request: NetworkRequest, val callback: ConnectivityManager.NetworkCallback)

    val requests = mutableListOf<Request>()
    val activeCallbacks = mutableSetOf<ConnectivityManager.NetworkCallback>()
    val unregisterCalls = mutableListOf<ConnectivityManager.NetworkCallback>()
    val bindings = mutableListOf<Network?>()
    var requestFailure: Throwable? = null
    var bindAccepted = true
    var beforeNonNullBind: (() -> Unit)? = null
    var remainingUnregisterFailures = 0

    @Implementation
    override fun requestNetwork(request: NetworkRequest, callback: ConnectivityManager.NetworkCallback) {
        requestFailure?.let { throw it }
        requests += Request(request, callback)
        check(activeCallbacks.add(callback))
    }

    @Implementation
    override fun unregisterNetworkCallback(callback: ConnectivityManager.NetworkCallback) {
        unregisterCalls += callback
        if (remainingUnregisterFailures > 0) {
            remainingUnregisterFailures -= 1
            throw IllegalStateException("synthetic callback unregister failure")
        }
        require(activeCallbacks.remove(callback)) { "callback already unregistered" }
    }

    @Implementation(minSdk = 23)
    override fun bindProcessToNetwork(network: Network?): Boolean {
        bindings += network
        if (network != null) beforeNonNullBind?.invoke()
        return if (network == null || bindAccepted) super.bindProcessToNetwork(network) else false
    }
}

internal class WifiManagerAdapterFixture {
    val application: android.app.Application = RuntimeEnvironment.getApplication()
    val wifi: AdapterWifiManagerShadow = Shadow.extract(application.getSystemService(Context.WIFI_SERVICE))
    val connectivity: AdapterConnectivityManagerShadow =
        Shadow.extract(application.getSystemService(Context.CONNECTIVITY_SERVICE))
    val wrapper = WifiManagerWrapperImpl(application)
    val hotspots = mutableListOf<HotspotHandle>()
    val joins = mutableListOf<JoinHandle>()

    init {
        println("Android adapter framework SDK=${Build.VERSION.SDK_INT}")
    }

    fun close() {
        try {
            hotspots.forEach { it.close() }
        } finally {
            try {
                joins.forEach { it.close() }
            } finally {
                // Also release a request if an assertion failed before delivery.
                wifi.requests.forEach { it.deliver { onFailed(1) } }
                connectivity.activeCallbacks.toList().forEach { it.onUnavailable() }
                check(wrapper.closePendingResources().isEmpty())
                check(connectivity.activeCallbacks.isEmpty())
                check(
                    (application.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager)
                        .boundNetworkForProcess == null
                ) { "adapter leaked its process network binding" }
                val probe = Any()
                check(ProcessBindingArbiter.tryAcquire(probe)) { "adapter leaked its process binding token" }
                try {
                    check(ProcessBindingArbiter.isOwner(probe))
                } finally {
                    ProcessBindingArbiter.release(probe)
                }
            }
        }
    }
}
