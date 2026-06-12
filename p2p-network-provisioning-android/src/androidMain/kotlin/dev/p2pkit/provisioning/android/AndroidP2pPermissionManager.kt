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
 * | Device API && target SDK | Required permission    |
 * |--------------------------|------------------------|
 * | both ≥ 33                | `NEARBY_WIFI_DEVICES`  |
 * | otherwise                | `ACCESS_FINE_LOCATION` |
 *
 * NEARBY_WIFI_DEVICES enforcement keys on the APP's targetSdk, not the
 * device API: a targetSdk ≤ 32 app on Android 13+ is still governed by
 * FINE_LOCATION and cannot be granted NEARBY at all (AUDIT-2026-06 fix —
 * previously this branched on device SDK only and the table promised a
 * COARSE row the implementation never had).
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

    private fun requiredWifiAwarePermission(): P2pPermission {
        val targetSdk = appContext.applicationInfo.targetSdkVersion
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            targetSdk >= Build.VERSION_CODES.TIRAMISU
        ) {
            P2pPermission.NearbyWifiDevices
        } else {
            P2pPermission.Location
        }
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
