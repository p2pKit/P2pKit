package dev.p2pkit.provisioning.android

import dev.p2pkit.core.provisioning.WifiCredentials
import kotlinx.coroutines.flow.SharedFlow

/**
 * Narrow seam over `android.net.wifi.WifiManager` + `LocalOnlyHotspotReservation`.
 *
 * The seam exists so [AndroidNetworkProvisioningManager] can be unit-tested
 * on the JVM host without Robolectric — tests inject a fake
 * [WifiManagerWrapper] and exercise the full state machine.
 *
 * Production implementation: [WifiManagerWrapperImpl] (this module).
 */
internal interface WifiManagerWrapper {

    fun isWifiEnabled(): Boolean

    /**
     * Start a LocalOnlyHotspot. Suspends until the system reports either
     * `onStarted` or `onFailed`. SecurityException (permission missing) is
     * propagated to the caller, not wrapped here.
     */
    suspend fun startLocalOnlyHotspot(): HotspotStartResult
}

internal sealed class HotspotStartResult {
    data class Started(val handle: HotspotHandle) : HotspotStartResult()
    /** AOSP [android.net.wifi.WifiManager.LocalOnlyHotspotCallback] error code. */
    data class Failed(val reasonCode: Int) : HotspotStartResult()
}

/**
 * Live handle to a running LocalOnlyHotspot. Closing releases the
 * underlying [android.net.wifi.WifiManager.LocalOnlyHotspotReservation].
 */
internal interface HotspotHandle {

    /**
     * Current SSID + passphrase if the OS exposes them. `null` if the
     * runtime permission has been stripped (Android redacts the
     * `SoftApConfiguration` fields when the caller no longer holds the
     * required permission), or on very old API levels where the
     * `WifiConfiguration` shape returned empty fields.
     */
    fun getCredentials(): WifiCredentials?

    /**
     * Snapshot of non-loopback IPs surfaced by `NetworkInterface` *while
     * the hotspot is running*. Includes the soft-AP interface IP (the
     * gateway, typically `192.168.43.1` on AOSP, varies by OEM) once the
     * AP interface comes up.
     */
    fun apHostAddresses(): List<String>

    /**
     * Fires exactly once when the system tears the hotspot down on its
     * own (battery saver, user toggle, OEM policy). Subscribers should
     * react by emitting `NetworkProvisioningEvent.Failed(HotspotStopped(reason))`.
     */
    val stopped: SharedFlow<HotspotStopReason>

    fun close()
}

internal data class HotspotStopReason(val source: String)
