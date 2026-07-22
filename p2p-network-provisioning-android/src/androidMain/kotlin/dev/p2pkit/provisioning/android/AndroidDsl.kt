package dev.p2pkit.provisioning.android

import android.content.Context
import dev.p2pkit.core.dsl.NetworkProvisioningConfigBuilder

/**
 * Register the Android Network Provisioning module.
 *
 * Usage inside a [dev.p2pkit.core.P2pKit.create] block:
 *
 * ```kotlin
 * P2pKit.create {
 *     appId = AppId("…")
 *     deviceName = "…"
 *     transports { lan(applicationContext) }
 *     networkProvisioning {
 *         enableLocalHotspot = true
 *         enableManualIpFallback = true
 *         android(applicationContext)
 *     }
 * }
 * ```
 *
 * What the Android module surfaces:
 *  - `startLocalNetwork()` → hosts a `LocalOnlyHotspot` (random SSID + passphrase
 *    chosen by the OS; non-system apps cannot pick their own).
 *  - `stopLocalNetwork()` → releases the reservation cleanly.
 *  - `joinLocalNetwork()` → joins the given SSID via `WifiNetworkSpecifier` +
 *    `ConnectivityManager.requestNetwork` (system user-approval prompt) on
 *    Android 10+ (API 29); returns `Unsupported` below that.
 *  - `getManualConnectionInfo()` + `createManualPeer()` → identical shape to JVM.
 *
 * **Permissions:** the host app must declare and request:
 *  - `NEARBY_WIFI_DEVICES` (targetSdk ≥ 33, with `usesPermissionFlags="neverForLocation"`)
 *  - or `ACCESS_FINE_LOCATION` (targetSdk < 33)
 *  - and the install-time `ACCESS_WIFI_STATE`, `CHANGE_WIFI_STATE`, and
 *    `CHANGE_NETWORK_STATE` entries. The latter three cannot be requested at
 *    runtime; the Android permission manager logs a diagnostic when they are
 *    absent from the merged application manifest.
 *
 * P2pKit reports missing perms via [P2pKit.permissions]; the host app
 * triggers the OS prompt itself. The library never requests them.
 */
public fun NetworkProvisioningConfigBuilder.android(applicationContext: Context) {
    register(AndroidProvisioningFactory(applicationContext))
}
