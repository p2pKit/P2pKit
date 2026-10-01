package dev.p2pkit.sample.android.rpclab

import android.content.Context
import android.os.Process
import android.system.ErrnoException
import android.system.Os
import android.system.OsConstants
import dev.p2pkit.sample.rpc.RpcPhoneProcessStats
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.security.MessageDigest
import java.util.UUID

/** Owner-selected USB run only. No Intent, network provisioning endpoint, shared storage or backup. */
internal class AndroidRpcCapacityFiles(context: Context, runLabel: String) {
    private val directory: File

    init {
        require(runLabel.matches(Regex("[a-z0-9-]{1,64}")))
        val parent = prepareHome(context)
        directory = File(parent, runLabel)
        privateDirectory(directory) // The USB coordinator must create a NEW mode-0700 run directory first.
    }

    private fun path(name: String): File {
        require(name in NAMES)
        privateDirectory(directory)
        return File(directory, name)
    }

    fun read(name: String, optional: Boolean = false): String? {
        val file = path(name)
        val before = try { Os.lstat(file.path) } catch (missing: ErrnoException) {
            if (optional && missing.errno == OsConstants.ENOENT) return null
            throw missing
        }
        check(OsConstants.S_ISREG(before.st_mode) && before.st_uid == Process.myUid() &&
            (before.st_mode and 0x1ff) == 0x180 && before.st_nlink == 1L && before.st_size in 1L..16_384L)
        val descriptor = openRpcLabDescriptor(file.path,
            OsConstants.O_RDONLY or OsConstants.O_NOFOLLOW or OsConstants.O_NONBLOCK, 0)
        val bytes = FileInputStream(descriptor).use { stream ->
            val opened = Os.fstat(descriptor)
            check(OsConstants.S_ISREG(opened.st_mode) && opened.st_uid == before.st_uid &&
                opened.st_mode == before.st_mode && opened.st_dev == before.st_dev && opened.st_ino == before.st_ino)
            check(opened.st_size == before.st_size && opened.st_nlink == 1L)
            val value = readBounded(stream, 16_384)
            val after = Os.fstat(descriptor)
            check(opened.st_size == after.st_size && opened.st_mtime == after.st_mtime &&
                opened.st_mode == after.st_mode && after.st_uid == opened.st_uid && after.st_nlink == 1L &&
                value.size.toLong() == after.st_size)
            value
        }
        require(bytes.all { it == 10.toByte() || it.toInt() in 32..126 })
        return bytes.toString(Charsets.US_ASCII)
    }

    /** Only rotating telemetry may replace an existing immutable record; readiness/cleanup are create-only. */
    fun publish(name: String, text: String) {
        require(name in setOf("ready.txt", "telemetry.txt", "closed.txt", "failed.txt"))
        require(text.length in 1..16_384 && text.all { it == '\n' || it.code in 32..126 })
        val target = path(name)
        if (name == "telemetry.txt") read(name, optional = true)
        val temporary = File(directory, ".capacity-${UUID.randomUUID()}")
        var identity: Pair<Long, Long>? = null
        try {
            val descriptor = openRpcLabDescriptor(temporary.path, OsConstants.O_WRONLY or OsConstants.O_CREAT or
                OsConstants.O_EXCL or OsConstants.O_NOFOLLOW, 0x180)
            FileOutputStream(descriptor).use { stream ->
                val info = Os.fstat(descriptor)
                identity = info.st_dev to info.st_ino
                stream.write(text.toByteArray(Charsets.US_ASCII))
                stream.fd.sync()
            }
            if (name == "telemetry.txt") Os.rename(temporary.path, target.path)
            else Os.link(temporary.path, target.path) // Atomic create-if-absent, never an evidence overwrite.
            fsyncRpcLabDirectory(directory)
        } finally {
            if (identity != null) {
                val remaining = try { Os.lstat(temporary.path) } catch (missing: ErrnoException) {
                    if (missing.errno == OsConstants.ENOENT) null else throw missing
                }
                if (remaining != null) {
                    check(identity == (remaining.st_dev to remaining.st_ino) && OsConstants.S_ISREG(remaining.st_mode))
                    // Os.unlink is hidden Android API. Public remove(3) is available
                    // since API21; the lifetime/type check above excludes directories.
                    Os.remove(temporary.path)
                }
            }
        }
    }

    companion object {
        private val NAMES = setOf("inbox.txt", "stop.txt", "ready.txt", "telemetry.txt", "closed.txt", "failed.txt")

        fun prepareHome(context: Context): File {
            val directory = File(context.applicationContext.noBackupFilesDir.canonicalFile, "rpc-capacity")
            if (!directory.exists()) {
                check(directory.mkdir())
                Os.chmod(directory.path, 0x1c0)
            }
            privateDirectory(directory)
            return directory
        }

        private fun privateDirectory(directory: File) {
            val info = Os.lstat(directory.path)
            check(OsConstants.S_ISDIR(info.st_mode) && info.st_uid == Process.myUid() &&
                (info.st_mode and 0x1ff) == 0x1c0)
        }
    }
}

private fun readBounded(stream: FileInputStream, maximum: Int): ByteArray {
    val buffer = ByteArray(maximum + 1)
    var size = 0
    while (size < buffer.size) {
        val read = stream.read(buffer, size, buffer.size - size)
        if (read < 0) break
        size += read
    }
    check(size <= maximum)
    return buffer.copyOf(size)
}

/** Self only; these are ART-process OS counters, not the JVM generator's statistics or estimates. */
internal fun androidRpcPhoneProcessStats(): RpcPhoneProcessStats {
    val status = FileInputStream("/proc/self/status").use { readBounded(it, 65_536) }.toString(Charsets.US_ASCII)
    val rssKiB = checkNotNull(Regex("(?m)^VmRSS:\\s+([0-9]+) kB$").find(status)).groupValues[1].toLong()
    val threads = checkNotNull(Regex("(?m)^Threads:\\s+([0-9]+)$").find(status)).groupValues[1].toInt()
    return RpcPhoneProcessStats(Math.multiplyExact(Process.getElapsedCpuTime(), 1_000_000L),
        Math.multiplyExact(rssKiB, 1024L), threads)
}

/** Hash our actual installed base APK, not a caller-supplied source stamp or a different device's package. */
internal fun androidRpcInstalledArtifact(context: Context): String {
    val path = context.applicationContext.applicationInfo.sourceDir
    val before = Os.lstat(path)
    check(OsConstants.S_ISREG(before.st_mode) && before.st_size in 1L..128L * 1024 * 1024)
    val descriptor = openRpcLabDescriptor(path,
        OsConstants.O_RDONLY or OsConstants.O_NOFOLLOW or OsConstants.O_NONBLOCK, 0)
    val digest = MessageDigest.getInstance("SHA-256")
    FileInputStream(descriptor).use { stream ->
        val opened = Os.fstat(descriptor)
        check(opened.st_dev == before.st_dev && opened.st_ino == before.st_ino && opened.st_size == before.st_size)
        val buffer = ByteArray(65_536)
        var total = 0L
        while (true) {
            val count = stream.read(buffer)
            if (count < 0) break
            total += count
            check(total <= before.st_size)
            digest.update(buffer, 0, count)
        }
        val after = Os.fstat(descriptor)
        check(total == before.st_size && after.st_size == before.st_size && after.st_mtime == before.st_mtime &&
            after.st_uid == before.st_uid && after.st_mode == before.st_mode)
    }
    return digest.digest().joinToString("") { "%02x".format(it) }
}
