package dev.p2pkit.provisioning.android

import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.provisioning.NetworkState
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
     * True when the platform supports LocalOnlyHotspot (API 26+). The manager
     * returns the contract's `Unsupported` result below that instead of
     * letting a NoSuchMethodError surface as PlatformError
     * (AUDIT-2026-06 fix; module minSdk is 24).
     */
    val isLocalOnlyHotspotSupported: Boolean

    /** True when WifiNetworkSpecifier join is supported (API 29+). */
    val isSpecifierJoinSupported: Boolean

    /**
     * The runtime permission that actually gates hotspot/join for THIS app:
     * NEARBY_WIFI_DEVICES only when both the device (API 33+) and the app's
     * targetSdk are 33+; otherwise ACCESS_FINE_LOCATION. Android keys
     * enforcement on targetSdk, so reporting NEARBY to a targetSdk<=32 app
     * told it to request an ungrantable permission (AUDIT-2026-06 fix).
     */
    fun requiredRuntimePermission(): P2pPermission

    /**
     * Start a LocalOnlyHotspot. Suspends until the system reports either
     * `onStarted` or `onFailed`. SecurityException (permission missing) is
     * propagated to the caller, not wrapped here.
     */
    suspend fun startLocalOnlyHotspot(): HotspotStartResult

    /**
     * Join a specific Wi-Fi network using `WifiNetworkSpecifier` +
     * `ConnectivityManager.requestNetwork`. The system always shows a
     * user-approval prompt. Suspends until either `onAvailable`
     * (Joined) or `onUnavailable` (Failed) terminates the request.
     *
     * On success the wrapper has already called
     * `ConnectivityManager.bindProcessToNetwork(network)` so the kit's
     * outgoing TCP sockets route through the joined network. The handle's
     * `close()` clears the process binding and unregisters the callback.
     *
     * SecurityException (permission missing, Location-mode-off) is
     * propagated to the caller.
     */
    suspend fun joinWifiNetwork(credentials: WifiCredentials): JoinResult
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

/** Result of [WifiManagerWrapper.joinWifiNetwork]. */
internal sealed class JoinResult {
    data class Joined(val handle: JoinHandle) : JoinResult()
    /** User declined the prompt, SSID not found, wrong passphrase, etc. */
    data class Failed(val reason: String) : JoinResult()
}

/**
 * Live handle to a successful Specifier join. Closing releases the
 * `NetworkCallback` and clears the process-wide network binding.
 */
internal interface JoinHandle {
    /** Snapshot of the joined network for `NetworkProvisioningManager.networkState`. */
    fun snapshotNetworkState(): NetworkState

    /**
     * Fires when the OS releases the join — user toggled Wi-Fi off,
     * battery saver dropped it, the AP went away, app was backgrounded
     * too long on MIUI, etc. Carries a human-readable reason.
     */
    val released: SharedFlow<String>

    fun close()
}
