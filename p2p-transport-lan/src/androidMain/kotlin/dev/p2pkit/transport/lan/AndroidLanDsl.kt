package dev.p2pkit.transport.lan

import android.content.Context
import dev.p2pkit.core.dsl.TransportsBuilder
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair

/**
 * Register the LAN transport (JmDNS discovery + TCP data) on Android.
 *
 * v0.5 (task #25) swapped the previous `NsdManager`-based discovery for
 * in-process JmDNS so the SDK owns the mDNS cache. `Context` is still
 * required because the multicast-lock and connectivity-manager hooks
 * are obtained from `Context.getSystemService`. Only
 * [Context.getApplicationContext] is held, so a short-lived Activity is
 * safe to pass.
 *
 * Usage:
 *
 * ```kotlin
 * P2pKit.create {
 *     appId = AppId("com.example")
 *     deviceName = "My Phone"
 *     transports { lan(applicationContext) }
 * }
 * ```
 *
 * Required permissions in `AndroidManifest.xml`:
 * - `android.permission.INTERNET` (install-time)
 * - `android.permission.ACCESS_NETWORK_STATE` (install-time)
 * - `android.permission.CHANGE_WIFI_MULTICAST_STATE` (install-time; needed for
 *   mDNS reception on some devices/Wi-Fi states)
 * - `android.permission.NEARBY_WIFI_DEVICES` (runtime, API 33+); without this,
 *   add `android.permission.ACCESS_FINE_LOCATION` for older API levels.
 *
 * The actual `ServerSocket(0)` bind happens inside the transport's `start()`
 * (called by [dev.p2pkit.core.P2pKit.start], or lazily by the first
 * `startAdvertising` / `connect`). Factory construction has no blocking I/O.
 */
public fun TransportsBuilder.lan(applicationContext: Context) {
    register(AndroidLanTransportFactory(applicationContext.applicationContext))
}

internal class AndroidLanTransportFactory(
    private val androidContext: Context
) : TransportFactory {
    override fun build(context: TransportContext): TransportPair {
        val networkState = AndroidLanNetworkState()
        val registration = LanServiceRegistration(
            appId = context.appId,
            localPeerId = context.localPeerId,
            deviceName = context.deviceName,
            platform = context.platform,
            securityProfile = context.securityProfile,
            fingerprint = context.localFingerprint
        )
        return TransportPair(
            data = AndroidLanDataTransport(registration, networkState),
            discovery = AndroidLanDiscoveryTransport(androidContext, registration, networkState)
        )
    }
}
