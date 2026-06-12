package dev.p2pkit.core.internal

import android.content.Context
import android.content.pm.PackageManager
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.android.androidApplicationContextOrNull
import dev.p2pkit.core.permission.NoOpP2pPermissionManager
import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.permission.P2pPermissionManager

/**
 * Default Android permission manager. Uses the application context registered
 * via `P2pKitAndroid.initialize(context)`. If init was never called there is
 * no context to query, so it degrades to a no-op (with a warn) rather than
 * guessing.
 *
 * The LAN transport relies on three Wi-Fi/network permissions. `INTERNET` and
 * the two `ACCESS_*_STATE` permissions are normal (install-time) — auto-granted
 * iff declared in the manifest — and `CHANGE_WIFI_MULTICAST_STATE` gates the
 * multicast lock the JmDNS receiver needs. `checkSelfPermission` returns
 * `DENIED` when a permission is simply missing from the manifest, so this
 * manager catches the common "forgot to declare the multicast permission"
 * mistake that otherwise manifests as silent zero-discovery.
 */
internal actual fun defaultPlatformPermissionManager(logger: P2pLogger): P2pPermissionManager {
    val ctx = androidApplicationContextOrNull()
    if (ctx == null) {
        logger.warn(
            "P2pKitAndroid.initialize(context) was not called; P2pKit.permissions cannot " +
                "verify LAN permissions and will report none. Call it from Application.onCreate()."
        )
        return NoOpP2pPermissionManager()
    }
    return AndroidLanPermissionManager(ctx.applicationContext)
}

private class AndroidLanPermissionManager(
    private val appContext: Context
) : P2pPermissionManager {

    override suspend fun requiredPermissions(): List<P2pPermission> =
        listOf(P2pPermission.WifiState, P2pPermission.ChangeWifiState)

    override suspend fun missingPermissions(): List<P2pPermission> =
        requiredPermissions().filterNot { granted(androidName(it)) }

    override suspend fun hasRequiredPermissions(): Boolean = missingPermissions().isEmpty()

    private fun granted(name: String): Boolean =
        appContext.checkSelfPermission(name) == PackageManager.PERMISSION_GRANTED

    private fun androidName(p: P2pPermission): String = when (p) {
        P2pPermission.WifiState -> android.Manifest.permission.ACCESS_WIFI_STATE
        P2pPermission.ChangeWifiState -> android.Manifest.permission.CHANGE_WIFI_MULTICAST_STATE
        else -> android.Manifest.permission.ACCESS_NETWORK_STATE
    }
}
