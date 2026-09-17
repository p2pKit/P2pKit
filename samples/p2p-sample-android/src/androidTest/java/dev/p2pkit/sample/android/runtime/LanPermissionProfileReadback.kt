package dev.p2pkit.sample.android.runtime

import android.annotation.TargetApi
import android.app.Activity
import android.app.Instrumentation
import android.content.Context
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.Process
import android.os.SystemClock
import android.system.Os
import android.system.OsConstants
import android.system.StructStat
import dev.p2pkit.core.BuildInfo
import java.io.File
import java.util.UUID

/** Private, test-only public-reader observations. No guest/profile qualification or permission changes. */
@TargetApi(37)
internal object LanPermissionProfileReadback {
    private val ARGUMENTS = setOf(
        "mode", "token", "sourceCommit", "sourceTree", "appApkSha256", "testApkSha256", "profileSha256", "installId",
    )

    fun run(instrumentation: Instrumentation, arguments: Bundle) {
        val terminal = Bundle().apply {
            putString("class", LanPermissionRuntimeInstrumentation::class.java.name)
            putString("test", "publicFlagProfileReadback")
            putInt("numtests", 1)
            putInt("current", 1)
            putString("p2pkitReadbackMode", LanReadbackCollector.MODE)
            putString("p2pkitQualification", "HOLD_UNQUALIFIED_RUNTIME_SEMANTICS")
            putString("p2pkitPermissionEnforcement", "NOT_PROVEN")
            putString("p2pkitSameInstanceRevocation", "NOT_EXECUTED")
        }
        var complete = false
        try {
            check(arguments.keySet() == ARGUMENTS && arguments.getString("mode") == LanReadbackCollector.MODE)
            fun argument(name: String): String = checkNotNull(arguments.getString(name))
            val references = LanReadbackCollector.References(
                argument("token"), argument("sourceCommit"), argument("sourceTree"), argument("appApkSha256"),
                argument("testApkSha256"), argument("profileSha256"), argument("installId"),
            ).also { it.validate() }
            terminal.putString("p2pkitToken", references.token)
            check(Build.VERSION.SDK_INT == 37) { "An actual API37 process is required" }
            val app = instrumentation.targetContext.applicationContext
            check(app.packageName == LanReadbackCollector.PACKAGE && Process.myUid() in 10000..19999)
            val root = app.noBackupFilesDir.canonicalFile
            val directory = File(root, "lan-readback-${references.token}")
            check(!directory.exists() && directory.mkdir() && directory.canonicalFile == directory)
            Os.chmod(directory.path, 448) // 0700, under this app's private no-backup root.
            val directoryIdentity = Os.lstat(directory.path)
            check(OsConstants.S_ISDIR(directoryIdentity.st_mode))
            check(directoryIdentity.st_uid == Process.myUid() && directoryIdentity.st_mode and 511 == 448)
            terminal.putString("p2pkitEvidence", "no_backup/${directory.name}/readback.json")
            val result = LanReadbackCollector.collect(
                references, AndroidPort(app), UUID.randomUUID().toString().replace("-", ""),
            ) { bytes -> retain(directory, directoryIdentity, bytes) }
            complete = result.complete
            terminal.putString("p2pkitReadbackRetained", result.retained.toString())
            result.byteCount?.let { terminal.putString("p2pkitReadbackBytes", it.toString()) }
            result.sha256?.let { terminal.putString("p2pkitReadbackSha256", it) }
            result.failureStage?.let { terminal.putString("p2pkitFailureStage", it) }
            result.failure?.let { terminal.putString("p2pkitFailureType", it.javaClass.name) }
        } catch (error: Throwable) {
            terminal.putString("p2pkitFailureType", error.javaClass.name)
        }
        terminal.putString("p2pkitReadbackOutcome", if (complete) "RECORDED_UNQUALIFIED" else "FAILED")
        terminal.putString("p2pkitReadbackCompleted", "1")
        instrumentation.sendStatus(if (complete) 0 else -2, Bundle(terminal))
        instrumentation.finish(if (complete) Activity.RESULT_OK else Activity.RESULT_CANCELED, terminal)
    }

    private class AndroidPort(private val app: Context) : LanReadbackCollector.Port {
        override fun identity(): LanReadbackCollector.Identity {
            // Fresh package-manager observations, not just a cached Context.applicationInfo object.
            val installed = app.packageManager.getPackageInfo(
                LanReadbackCollector.PACKAGE, PackageManager.PackageInfoFlags.of(0),
            )
            val info = checkNotNull(installed.applicationInfo)
            val uid = Process.myUid()
            return LanReadbackCollector.Identity(
                BuildInfo.COMMIT, BuildInfo.DIRTY, installed.packageName, uid / 100000, uid, info.uid,
                Process.myPid(), Process.getStartElapsedRealtime(), installed.firstInstallTime,
                Build.VERSION.SDK_INT, info.targetSdkVersion, Build.VERSION.CODENAME, Build.VERSION.PREVIEW_SDK_INT,
            )
        }

        override fun stamp(): LanReadbackCollector.Stamp =
            LanReadbackCollector.Stamp(System.currentTimeMillis(), SystemClock.elapsedRealtime())

        override fun load(packageName: String): Any = Api37LanFlagReader.load(packageName)

        override fun read(reader: Any, flagName: String, defaultValue: Boolean): Boolean =
            Api37LanFlagReader.read(reader, flagName, defaultValue)

        override fun errorDetails(error: Throwable): LanReadbackCollector.ErrorDetails {
            val type = error.javaClass.name
            // Do not resolve the flagged error helper again after an unrelated linkage/access failure.
            val code = if (type == LanReadbackCollector.STORAGE_ERROR) Api37LanFlagReader.errorCode(error) else null
            return LanReadbackCollector.ErrorDetails(type, code)
        }
    }

    private fun retain(directory: File, original: StructStat, bytes: ByteArray) {
        check(bytes.size in 1..LanReadbackCollector.MAX_RECORD_BYTES)
        fun verifyDirectory() {
            val observed = Os.lstat(directory.path)
            check(OsConstants.S_ISDIR(observed.st_mode) && observed.st_uid == Process.myUid())
            check(observed.st_dev == original.st_dev && observed.st_ino == original.st_ino)
            check(observed.st_mode and 511 == 448 && directory.canonicalFile == directory)
        }
        verifyDirectory()
        val file = File(directory, "readback.json")
        val descriptor = Os.open(
            file.path,
            OsConstants.O_CREAT or OsConstants.O_EXCL or OsConstants.O_RDWR or
                OsConstants.O_CLOEXEC or OsConstants.O_NOFOLLOW,
            384, // 0600; one new file, no overwrite, deletion, public log or exception message.
        )
        var first: Throwable? = null
        try {
            val before = Os.fstat(descriptor)
            check(OsConstants.S_ISREG(before.st_mode) && before.st_uid == Process.myUid())
            check(before.st_nlink == 1L && before.st_size == 0L && before.st_mode and 511 == 384)
            var offset = 0
            while (offset < bytes.size) {
                val count = Os.write(descriptor, bytes, offset, bytes.size - offset)
                check(count in 1..bytes.size - offset)
                offset += count
            }
            Os.fsync(descriptor)
            check(Os.lseek(descriptor, 0, OsConstants.SEEK_SET) == 0L)
            val readback = ByteArray(bytes.size)
            offset = 0
            while (offset < readback.size) {
                val count = Os.read(descriptor, readback, offset, readback.size - offset)
                check(count in 1..readback.size - offset)
                offset += count
            }
            check(Os.read(descriptor, ByteArray(1), 0, 1) == 0 && readback.contentEquals(bytes))
            val after = Os.fstat(descriptor)
            val named = Os.lstat(file.path)
            for (observed in listOf(after, named)) {
                check(OsConstants.S_ISREG(observed.st_mode) && observed.st_uid == before.st_uid)
                check(observed.st_dev == before.st_dev && observed.st_ino == before.st_ino)
                check(observed.st_nlink == 1L && observed.st_size == bytes.size.toLong())
                check(observed.st_mode and 511 == 384)
            }
            verifyDirectory()
        } catch (error: Throwable) {
            first = error
            throw error
        } finally {
            try {
                Os.close(descriptor)
            } catch (error: Throwable) {
                if (first == null) throw error else first.addSuppressed(error)
            }
        }
    }
}
