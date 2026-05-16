package dev.p2pkit.provisioning.android

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.permission.P2pPermissionManager

/**
 * Android [P2pPermissionManager] tuned for the v0.2.1 provisioning surface.
 *
 * Reports which runtime permissions are required for hotspot hosting and
 * Wi-Fi discovery on the local device, branching by SDK level:
 *
 * | Target SDK | Required permission             |
 * |------------|---------------------------------|
 * | ≥ 33       | `NEARBY_WIFI_DEVICES`           |
 * | 29..32     | `ACCESS_FINE_LOCATION`          |
 * | ≤ 28       | `ACCESS_COARSE_LOCATION`        |
 *
 * Pure reporter — the library never requests permissions. The host app
 * is responsible for the runtime prompt; [missingPermissions] tells it
 * which prompts to launch.
 */
public class AndroidP2pPermissionManager(
    applicationContext: Context
) : P2pPermissionManager {

    private val appContext: Context = applicationContext.applicationContext

    override suspend fun requiredPermissions(): List<P2pPermission> =
        listOf(requiredWifiAwarePermission())

    override suspend fun missingPermissions(): List<P2pPermission> {
        val androidPerm = androidPermissionStringFor(requiredWifiAwarePermission())
        val granted = androidPerm == null ||
            appContext.checkSelfPermission(androidPerm) == PackageManager.PERMISSION_GRANTED
        return if (granted) emptyList() else listOf(requiredWifiAwarePermission())
    }

    override suspend fun hasRequiredPermissions(): Boolean = missingPermissions().isEmpty()

    private fun requiredWifiAwarePermission(): P2pPermission = when {
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU -> P2pPermission.NearbyWifiDevices
        Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q -> P2pPermission.Location
        else -> P2pPermission.Location
    }

    private fun androidPermissionStringFor(p: P2pPermission): String? = when (p) {
        P2pPermission.NearbyWifiDevices ->
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU)
                Manifest.permission.NEARBY_WIFI_DEVICES
            else null
        P2pPermission.Location -> Manifest.permission.ACCESS_FINE_LOCATION
        P2pPermission.WifiState -> Manifest.permission.ACCESS_WIFI_STATE
        P2pPermission.ChangeWifiState -> Manifest.permission.CHANGE_WIFI_STATE
        else -> null
    }
}
