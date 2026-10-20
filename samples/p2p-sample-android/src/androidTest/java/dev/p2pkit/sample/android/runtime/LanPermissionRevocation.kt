package dev.p2pkit.sample.android.runtime

import android.annotation.TargetApi
import android.app.ActivityManager
import android.app.Application
import android.app.ApplicationExitInfo
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Process
import android.os.flagging.AconfigPackage
import dev.p2pkit.core.BuildInfo
import java.io.File
import java.io.FileOutputStream
import org.json.JSONObject

/** Actual ordinary-UID readbacks and permission-kill attribution. Never grants/revokes a permission itself. */
@TargetApi(37)
internal object LanPermissionRevocation {
    const val MODE = "revocation"
    const val REENTRY = "revoked-reentry"
    private const val PACKAGE = "dev.p2pkit.sample.android"
    private const val PERMISSION = "android.permission.ACCESS_LOCAL_NETWORK"

    fun profile(app: Application, arguments: Bundle) {
        check(arguments.keySet() == setOf(
            "mode", "token", "host", "controlPort", "cliPort", "fingerprint", "sourceCommit", "sourceTree"
        ))
        check(Build.VERSION.SDK_INT == 37 && Build.VERSION.CODENAME == "REL" && Build.VERSION.PREVIEW_SDK_INT == 0)
        check(app.applicationInfo.targetSdkVersion == 37 && app.applicationInfo.uid == Process.myUid())
        check(arguments.getString("sourceCommit") == BuildInfo.COMMIT && !BuildInfo.DIRTY)
        check(checkNotNull(arguments.getString("sourceTree")).matches(Regex("[0-9a-f]{40}")))
        val permission = app.packageManager.getPermissionInfo(PERMISSION, 0)
        check(permission.protectionLevel and android.content.pm.PermissionInfo.PROTECTION_MASK_BASE ==
            android.content.pm.PermissionInfo.PROTECTION_DANGEROUS)
        val record = identity(app, arguments).put("readbackScope", "observed public flag; not generated-cache proof")
        try {
            // Same actual public reader and both defaults distinguish a present true
            // flag from a missing lookup. No reflection/hidden platform delegate.
            val reader = AconfigPackage.load("android.permission.flags")
            val first = reader.getBooleanFlagValue("access_local_network_permission_enabled", false)
            val second = reader.getBooleanFlagValue("access_local_network_permission_enabled", true)
            record.put("flagPackage", "android.permission.flags")
                .put("flagName", "access_local_network_permission_enabled")
                .put("falseDefaultValue", first).put("trueDefaultValue", second)
            write(app, arguments, "profile-${arguments.getString("mode")}.json", record)
            check(first && second) { "Mandatory LAN flag is not observed true with both defaults" }
        } catch (error: Throwable) {
            // Preserve failure without exporting arbitrary platform exception messages.
            if (!file(app, arguments, "profile-${arguments.getString("mode")}.json").exists()) {
                write(app, arguments, "profile-${arguments.getString("mode")}.json",
                    record.put("errorType", error.javaClass.name))
            }
            throw error
        }
    }

    fun checkpoint(app: Application, arguments: Bundle, result: Bundle, managerIdentity: Int) {
        check(app.checkSelfPermission(PERMISSION) == PackageManager.PERMISSION_GRANTED)
        check(result.getString("p2pkitTraffic") == "PASS")
        check(result.getString("p2pkitRawRoute") == "DENIED_THEN_ADMITTED")
        write(app, arguments, "before-revocation.json", identity(app, arguments)
            .put("managerIdentity", managerIdentity).put("traffic", "AUTHENTICATED_DUPLEX_COMPLETED")
            .put("rawRoute", result.getString("p2pkitRawRoute"))
            .put("peerFingerprint", result.getString("p2pkitPeerFingerprint")))
    }

    fun requirePermissionDrivenExit(app: Application, arguments: Bundle): JSONObject {
        val retained = file(app, arguments, "before-revocation.json")
        check(retained.isFile && retained.length() in 1..16_384)
        val before = JSONObject(retained.readText())
        val now = identity(app, arguments)
        for (name in listOf("token", "sourceCommit", "sourceTree", "firstInstallTime", "uid")) {
            check(before.get(name) == now.get(name)) { "Revocation reentry changed installation/source" }
        }
        check(before.getString("traffic") == "AUTHENTICATED_DUPLEX_COMPLETED")
        check(before.getString("rawRoute") == "DENIED_THEN_ADMITTED")
        check(before.getInt("pid") != Process.myPid())
        check(before.getLong("processStartElapsedMillis") < Process.getStartElapsedRealtime())
        check(app.checkSelfPermission(PERMISSION) == PackageManager.PERMISSION_DENIED)
        val manager = app.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val exits = manager.getHistoricalProcessExitReasons(PACKAGE, before.getInt("pid"), 8)
        val exit = exits.filter {
            it.pid == before.getInt("pid") && it.processName == PACKAGE && it.realUid == Process.myUid() &&
                it.packageUid == Process.myUid() && it.timestamp >= before.getLong("epochMillis") &&
                it.reason == ApplicationExitInfo.REASON_PERMISSION_CHANGE
        }.single()
        // No traces, arbitrary exit descriptions or private process data are read.
        return now.put("priorPid", exit.pid).put("reason", "REASON_PERMISSION_CHANGE")
            .put("reasonCode", exit.reason).put("exitEpochMillis", exit.timestamp)
            .put("claim", "OS_PERMISSION_KILL_AND_UNCHANGED_INSTALL_REENTRY_NOT_SAME_INSTANCE")
    }

    fun retainReentry(app: Application, arguments: Bundle, record: JSONObject) {
        write(app, arguments, "revoked-reentry.json", record)
    }

    private fun identity(app: Application, arguments: Bundle): JSONObject {
        val installed = app.packageManager.getPackageInfo(PACKAGE, PackageManager.PackageInfoFlags.of(0))
        return JSONObject().put("token", arguments.getString("token"))
            .put("sourceCommit", BuildInfo.COMMIT).put("sourceTree", arguments.getString("sourceTree"))
            .put("firstInstallTime", installed.firstInstallTime).put("uid", Process.myUid()).put("pid", Process.myPid())
            .put("processStartElapsedMillis", Process.getStartElapsedRealtime()).put("epochMillis", System.currentTimeMillis())
            .put("sdk", Build.VERSION.SDK_INT).put("targetSdk", app.applicationInfo.targetSdkVersion)
    }

    private fun file(app: Application, arguments: Bundle, name: String): File {
        val token = checkNotNull(arguments.getString("token")).also { check(it.matches(Regex("[0-9a-f]{32}"))) }
        val directory = File(app.noBackupFilesDir.canonicalFile, "lan-372-$token")
        check(directory.canonicalFile == directory)
        if (!directory.exists()) check(directory.mkdir())
        return File(directory, name)
    }

    private fun write(app: Application, arguments: Bundle, name: String, record: JSONObject) {
        val target = file(app, arguments, name)
        check(target.createNewFile())
        val bytes = (record.toString(2) + "\n").toByteArray(Charsets.UTF_8)
        check(bytes.size in 1..16_384)
        FileOutputStream(target).use { output -> output.write(bytes); output.fd.sync() }
    }
}
