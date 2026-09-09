package dev.p2pkit.core.internal

import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
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
 * The LAN transport always relies on **normal (install-time)** permissions
 * (`INTERNET`, `ACCESS_NETWORK_STATE`, `ACCESS_WIFI_STATE`,
 * `CHANGE_WIFI_MULTICAST_STATE`) — auto-granted at install iff declared in
 * the manifest, impossible to request at runtime. They therefore must never
 * surface through [P2pPermissionManager], which is the SDK's
 * runtime-permission-request surface: an app feeding `missingPermissions()`
 * into `ActivityResultContracts.RequestPermission` would loop forever on a
 * permission no prompt can grant. A forgotten declaration is a build-time
 * mistake, so it is flagged as a construction-time warn instead (see
 * [warnIfLanManifestPermissionsUndeclared]) — the classic "forgot
 * CHANGE_WIFI_MULTICAST_STATE → silent zero-discovery" case is still caught
 * without misreporting them as runtime requests. Separately, device API 37+
 * with final application target SDK 37+ requires the live dangerous
 * `ACCESS_LOCAL_NETWORK` grant for raw LAN access. Library compile SDK does
 * not determine the consumer's target or grant.
 */
internal actual fun defaultPlatformPermissionManager(logger: P2pLogger, usesLan: Boolean): P2pPermissionManager {
    if (!usesLan) return NoOpP2pPermissionManager()
    val ctx = androidApplicationContextOrNull()
    if (ctx == null) {
        logger.warn(
            "P2pKitAndroid.initialize(context) was not called; P2pKit.permissions cannot " +
                "verify LAN permissions and will report none. Call it from Application.onCreate()."
        )
        return NoOpP2pPermissionManager()
    }
    warnIfLanManifestPermissionsUndeclared(ctx.applicationContext, logger)
    return AndroidLanPermissionManager(ctx.applicationContext)
}

/**
 * Non-fatal manifest diagnostic. For a normal permission,
 * `checkSelfPermission` returns `DENIED` only when the permission is missing
 * from the manifest, so this warn fires exactly for the build-time mistake it
 * is meant to surface. It never throws: the app cannot recover at runtime (no
 * prompt can grant an undeclared install-time permission), so failing
 * startAdvertising/startDiscovery would hard-break apps over a condition only
 * a manifest edit can fix.
 */
private fun warnIfLanManifestPermissionsUndeclared(appContext: Context, logger: P2pLogger) {
    val undeclared = androidLanManifestPermissions.filter {
        appContext.checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED
    }
    if (undeclared.isNotEmpty()) {
        logger.warn(
            "AndroidManifest.xml is missing ${undeclared.joinToString()}. Declare " +
                "them (<uses-permission>) or LAN transport/path observation may fail — " +
                "INTERNET gates sockets, ACCESS_NETWORK_STATE gates route observation, and " +
                "CHANGE_WIFI_MULTICAST_STATE gates the multicast lock the JmDNS receiver " +
                "needs. These are install-time (protection level: normal) permissions: they " +
                "cannot be requested at runtime, so P2pKit.permissions does not report them."
        )
    }
}

/**
 * Reports only the applicable runtime LAN grant, never normal manifest
 * permissions. Use the permission name rather than an API 37 SDK constant so
 * the library continues to compile against API 36. Both device and final app
 * target must opt into the Android 17 enforcement boundary. Android 16's
 * explicit compatibility-test opt-in is a separate policy, not the default.
 *
 * Provisioning sidecars DO require real runtime permissions
 * (`NEARBY_WIFI_DEVICES` / `ACCESS_FINE_LOCATION`) and ship their own
 * manager (`AndroidP2pPermissionManager`). Wiring that manager in via
 * `P2pKitBuilder.permissionManager` makes it gate
 * startAdvertising/startDiscovery too — which re-creates the over-gating
 * this class exists to remove. Recommended integration (decision #7a,
 * 2026-07-04): keep this default on the kit and query the sidecar's manager
 * immediately before provisioning calls only.
 */
private class AndroidLanPermissionManager(private val appContext: Context) : P2pPermissionManager {
    override suspend fun requiredPermissions(): List<P2pPermission> =
        if (Build.VERSION.SDK_INT >= 37 && appContext.applicationInfo.targetSdkVersion >= 37) {
            listOf(P2pPermission.LocalNetwork)
        } else {
            emptyList()
        }

    override suspend fun missingPermissions(): List<P2pPermission> = requiredPermissions().filter {
        appContext.checkSelfPermission("android.permission.ACCESS_LOCAL_NETWORK") != PackageManager.PERMISSION_GRANTED
    }

    override suspend fun hasRequiredPermissions(): Boolean = missingPermissions().isEmpty()
}
