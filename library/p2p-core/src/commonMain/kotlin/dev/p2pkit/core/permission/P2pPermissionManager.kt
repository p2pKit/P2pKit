package dev.p2pkit.core.permission

/**
 * Reports which runtime permissions P2pKit needs and which are still missing.
 *
 * Only **runtime** permissions are surfaced here. Install-time permissions
 * (`INTERNET`, `ACCESS_NETWORK_STATE`) belong in the app's manifest and are
 * documented in the README — they are not part of this API.
 *
 * The library never requests permissions itself; the app is responsible for
 * prompting the user. [dev.p2pkit.core.P2pKit.startAdvertising] and
 * [dev.p2pkit.core.P2pKit.startDiscovery] throw
 * [dev.p2pkit.core.P2pError.PermissionMissing] if any required permission is
 * absent.
 */
public interface P2pPermissionManager {
    public suspend fun requiredPermissions(): List<P2pPermission>
    public suspend fun missingPermissions(): List<P2pPermission>
    public suspend fun hasRequiredPermissions(): Boolean
}

/**
 * Runtime permissions that may be required by P2pKit transports.
 *
 * Which permissions are required is platform- and feature-dependent; consult
 * [P2pPermissionManager.requiredPermissions] for the active list.
 */
public enum class P2pPermission {
    LocalNetwork,
    NearbyWifiDevices,
    Bluetooth,
    Location,
    WifiState,
    ChangeWifiState
}
