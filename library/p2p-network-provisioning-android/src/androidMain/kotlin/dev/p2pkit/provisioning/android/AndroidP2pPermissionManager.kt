package dev.p2pkit.provisioning.android

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.util.Log
import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.permission.P2pPermissionManager

/**
 * Android [P2pPermissionManager] for the optional provisioning sidecar.
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
 * which prompts to launch. Install-time provisioning permissions are checked
 * separately at construction and reported through a warning because Android
 * does not permit requesting them through this API.
 */
public class AndroidP2pPermissionManager(
    applicationContext: Context
) : P2pPermissionManager {

    private val appContext: Context = applicationContext.applicationContext

    init {
        val missingNormal = provisioningNormalManifestPermissions.filter {
            appContext.checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED
        }
        if (missingNormal.isNotEmpty()) {
            Log.w(
                "P2pKitProvisioning",
                "AndroidManifest.xml is missing ${missingNormal.joinToString()}; " +
                    "provisioning callbacks may fail. These are install-time permissions " +
                    "and cannot be requested through P2pPermissionManager."
            )
        }
    }

    override suspend fun requiredPermissions(): List<P2pPermission> =
        listOf(requiredProvisioningPermission())

    override suspend fun missingPermissions(): List<P2pPermission> {
        val required = requiredProvisioningPermission()
        val androidPerm = androidPermissionStringFor(required)
        val granted = androidPerm == null ||
            appContext.checkSelfPermission(androidPerm) == PackageManager.PERMISSION_GRANTED
        return if (granted) emptyList() else listOf(required)
    }

    override suspend fun hasRequiredPermissions(): Boolean = missingPermissions().isEmpty()

    private fun requiredProvisioningPermission(): P2pPermission {
        val targetSdk = appContext.applicationInfo.targetSdkVersion
        return requiredProvisioningRuntimePermission(
            deviceSdk = Build.VERSION.SDK_INT,
            targetSdk = targetSdk
        )
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
