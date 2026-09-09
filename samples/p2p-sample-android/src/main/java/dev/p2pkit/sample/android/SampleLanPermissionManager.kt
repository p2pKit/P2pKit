package dev.p2pkit.sample.android

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.permission.P2pPermissionManager

internal const val ACCESS_LOCAL_NETWORK_PERMISSION = "android.permission.ACCESS_LOCAL_NETWORK"

/**
 * Pre-creation reporter for this known-LAN sample, not a replacement for an owned kit's permissions.
 * Both device and final application target opt into Android 17's raw LAN policy. Each query reads
 * the live grant; an exception propagates rather than being reported as permission granted.
 */
internal class SampleLanPermissionManager(context: Context) : P2pPermissionManager {
    private val appContext = context.applicationContext

    override suspend fun requiredPermissions(): List<P2pPermission> =
        if (Build.VERSION.SDK_INT >= 37 && appContext.applicationInfo.targetSdkVersion >= 37) {
            listOf(P2pPermission.LocalNetwork)
        } else {
            emptyList()
        }

    override suspend fun missingPermissions(): List<P2pPermission> = requiredPermissions().filter {
        appContext.checkSelfPermission(ACCESS_LOCAL_NETWORK_PERMISSION) != PackageManager.PERMISSION_GRANTED
    }

    override suspend fun hasRequiredPermissions(): Boolean = missingPermissions().isEmpty()
}
