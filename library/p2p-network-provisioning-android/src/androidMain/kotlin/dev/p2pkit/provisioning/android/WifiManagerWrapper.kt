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

    /**
     * True on API 26+ with a WifiManager and declared Wi-Fi hardware. The
     * manager returns `Unsupported` otherwise (module minSdk is 24).
     * Radio enablement and permissions are transient state, not capability;
     * a true result does not guarantee that the OS will accept a start.
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
     * Post-failure diagnostic only; never an atomic authorization check.
     * Unknown/failed probes must not turn an arbitrary SecurityException into
     * a runtime-permission failure. Platform calls remain authoritative.
     */
    fun permissionState(): ProvisioningPermissionState = ProvisioningPermissionState()

    /**
     * Blocking snapshot of all active non-loopback interfaces, not just a
     * hotspot. The manager owns the IO dispatch and uses this same scanner
     * for manual connection information and hosted-network snapshots.
     */
    fun scanInterfaceAddresses(): List<String> = collectProvisioningInterfaceAddresses()

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

    /**
     * Retry native cleanup that failed before a handle could be transferred
     * to the manager (for example, a reservation delivered after coroutine
     * cancellation). Implementations retain ownership until cleanup succeeds.
     *
     * The default keeps host-test fakes source-compatible.
     */
    fun closePendingResources(): List<Throwable> = emptyList()
}

internal sealed class HotspotStartResult {
    data class Started(val handle: HotspotHandle) : HotspotStartResult()
    /** AOSP [android.net.wifi.WifiManager.LocalOnlyHotspotCallback] error code. */
    data class Failed(val reasonCode: Int) : HotspotStartResult()
    /** A prior platform request still owns a callback or failed cleanup. */
    data class CleanupPending(val reason: String) : HotspotStartResult()
}

/**
 * Live handle to a running LocalOnlyHotspot. Closing releases the
 * underlying [android.net.wifi.WifiManager.LocalOnlyHotspotReservation].
 */
internal interface HotspotHandle {

    /**
     * Current SSID + passphrase if the OS exposes them. A returned `null`
     * means no usable credential record was exposed; it does not establish
     * whether permissions changed or the OS redacted the record. A thrown
     * failure (including SecurityException) must remain distinguishable from
     * `null`, and cancellation must propagate.
     */
    fun getCredentials(): WifiCredentials?

    /**
     * Fires exactly once when the system tears the hotspot down on its
     * own (battery saver, user toggle, OEM policy). Subscribers should
     * react by emitting `NetworkProvisioningEvent.Failed(HotspotStopped(reason))`.
     */
    val stopped: SharedFlow<HotspotStopReason>

    /** Idempotent and retryable: failures are propagated to the owner. */
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

    /** Idempotent and retryable: failures are propagated to the owner. */
    fun close()
}
