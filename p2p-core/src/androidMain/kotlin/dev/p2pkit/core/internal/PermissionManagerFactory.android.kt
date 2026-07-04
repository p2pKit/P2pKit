package dev.p2pkit.core.internal

import android.Manifest
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
 * The LAN transport relies only on **normal (install-time)** permissions
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
 * without gating startAdvertising/startDiscovery (AUDIT-2026-06
 * permission-gate regression fix).
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
    warnIfLanManifestPermissionsUndeclared(ctx.applicationContext, logger)
    return AndroidLanPermissionManager()
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
    val undeclared = listOf(
        Manifest.permission.ACCESS_WIFI_STATE,
        Manifest.permission.CHANGE_WIFI_MULTICAST_STATE
    ).filter { appContext.checkSelfPermission(it) != PackageManager.PERMISSION_GRANTED }
    if (undeclared.isNotEmpty()) {
        logger.warn(
            "AndroidManifest.xml is missing ${undeclared.joinToString()}. Declare " +
                "them (<uses-permission>) or LAN discovery/advertising may find no peers — " +
                "CHANGE_WIFI_MULTICAST_STATE gates the multicast lock the JmDNS receiver " +
                "needs. These are install-time (protection level: normal) permissions: they " +
                "cannot be requested at runtime, so P2pKit.permissions does not report them."
        )
    }
}

/**
 * Reports **no runtime permissions**: core LAN discovery/advertising needs
 * none on any supported API level (minSdk 24+). The Wi-Fi permissions the
 * transport depends on are install-time (see file header); reporting them
 * from [missingPermissions] made [P2pKitImpl] throw
 * [dev.p2pkit.core.P2pError.PermissionMissing] from
 * startAdvertising/startDiscovery for apps that worked under the previous
 * no-op default. Dropping the mapping also removes the double meaning of
 * [P2pPermission.ChangeWifiState] (core mapped it to
 * `CHANGE_WIFI_MULTICAST_STATE` while the provisioning sidecar maps it to
 * `CHANGE_WIFI_STATE`) — the enum member now has a single Android mapping,
 * the sidecar's.
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
private class AndroidLanPermissionManager : P2pPermissionManager {
    override suspend fun requiredPermissions(): List<P2pPermission> = emptyList()
    override suspend fun missingPermissions(): List<P2pPermission> = emptyList()
    override suspend fun hasRequiredPermissions(): Boolean = true
}
