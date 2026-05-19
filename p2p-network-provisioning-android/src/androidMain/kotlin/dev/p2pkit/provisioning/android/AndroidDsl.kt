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
 *  - `joinLocalNetwork()` → `Unsupported` until v0.2.1 task 12 ships `WifiNetworkSpecifier` join.
 *  - `getManualConnectionInfo()` + `createManualPeer()` → identical shape to JVM.
 *
 * **Permissions:** the host app must declare and request:
 *  - `NEARBY_WIFI_DEVICES` (targetSdk ≥ 33, with `usesPermissionFlags="neverForLocation"`)
 *  - or `ACCESS_FINE_LOCATION` (targetSdk < 33)
 *
 * P2pKit reports missing perms via [P2pKit.permissions]; the host app
 * triggers the OS prompt itself. The library never requests them.
 */
public fun NetworkProvisioningConfigBuilder.android(applicationContext: Context) {
    register(AndroidProvisioningFactory(applicationContext))
}
