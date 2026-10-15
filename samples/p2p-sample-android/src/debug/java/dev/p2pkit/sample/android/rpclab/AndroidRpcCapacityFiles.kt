package dev.p2pkit.sample.android.rpclab

import android.content.Context
import android.os.Process
import android.system.ErrnoException
import android.system.Os
import android.system.OsConstants
import android.system.StructStat
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
        // Immutable records become visible only after the creator closes/fsyncs
        // the data and atomically creates its empty completion marker. Android
        // forbids app hard links; neither a partial file nor its mere existence
        // is a publication. Rotating telemetry still uses an atomic rename.
        val completion = if (name == "telemetry.txt") null else (completed(name, optional) ?: return null)
        val before = try { Os.lstat(file.path) } catch (missing: ErrnoException) {
            if (optional && completion == null && missing.errno == OsConstants.ENOENT) return null
            throw missing
        }
        privateRecord(before)
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
        if (completion != null) check(sameRecord(completion, checkNotNull(completed(name, optional = false))))
        return bytes.toString(Charsets.US_ASCII)
    }

    /** No retries/reclamation of an interrupted immutable publication: use a fresh run instead. */
    private fun completed(name: String, optional: Boolean): StructStat? {
        val marker = File(directory, ".complete-$name")
        val before = try { Os.lstat(marker.path) } catch (missing: ErrnoException) {
            if (optional && missing.errno == OsConstants.ENOENT) return null
            throw missing
        }
        privateRecord(before, marker = true)
        val descriptor = openRpcLabDescriptor(marker.path,
            OsConstants.O_RDONLY or OsConstants.O_NOFOLLOW or OsConstants.O_NONBLOCK, 0)
        try {
            val opened = Os.fstat(descriptor)
            privateRecord(opened, marker = true)
            check(sameRecord(before, opened))
        } finally { Os.close(descriptor) }
        return before
    }

    /** Only rotating telemetry may replace a record. All other data AND markers use O_EXCL. */
    fun publish(name: String, text: String) {
        require(name in setOf("ready.txt", "telemetry.txt", "closed.txt", "failed.txt"))
        require(text.length in 1..16_384 && text.all { it == '\n' || it.code in 32..126 })
        val target = path(name)
        if (name != "telemetry.txt") {
            val marker = File(directory, ".complete-$name")
            // An orphan marker must not bless newly written data. lstat also
            // refuses a dangling symlink; File.exists() would miss that case.
            val existing = try { Os.lstat(marker.path) } catch (missing: ErrnoException) {
                if (missing.errno == OsConstants.ENOENT) null else throw missing
            }
            if (existing != null) throw ErrnoException("immutable RPC control already exists", OsConstants.EEXIST)
            val descriptor = openRpcLabDescriptor(target.path, OsConstants.O_WRONLY or OsConstants.O_CREAT or
                OsConstants.O_EXCL or OsConstants.O_NOFOLLOW, 0x180)
            FileOutputStream(descriptor).use { stream ->
                privateRecord(Os.fstat(descriptor), marker = true) // Newly created, still empty.
                stream.write(text.toByteArray(Charsets.US_ASCII))
                stream.fd.sync()
                privateRecord(Os.fstat(descriptor))
            }
            fsyncRpcLabDirectory(directory)
            val seal = openRpcLabDescriptor(marker.path, OsConstants.O_WRONLY or OsConstants.O_CREAT or
                OsConstants.O_EXCL or OsConstants.O_NOFOLLOW, 0x180)
            try {
                privateRecord(Os.fstat(seal), marker = true)
                Os.fsync(seal)
            } finally { Os.close(seal) }
            fsyncRpcLabDirectory(directory)
            return
        }
        read(name, optional = true)
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
            Os.rename(temporary.path, target.path)
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

/** Shared by actual lstat/fstat admission and the hostile-metadata regression control. */
internal fun admitsRpcCapacityRecord(mode: Int, uid: Int, links: Long, size: Long, marker: Boolean = false): Boolean =
    OsConstants.S_ISREG(mode) && uid == Process.myUid() && (mode and 0x1ff) == 0x180 && links == 1L &&
        (if (marker) size == 0L else size in 1L..16_384L)

private fun privateRecord(info: StructStat, marker: Boolean = false) {
    check(admitsRpcCapacityRecord(info.st_mode, info.st_uid, info.st_nlink, info.st_size, marker))
}

private fun sameRecord(before: StructStat, after: StructStat): Boolean =
    before.st_dev == after.st_dev && before.st_ino == after.st_ino && before.st_uid == after.st_uid &&
        before.st_mode == after.st_mode && before.st_size == after.st_size && before.st_nlink == after.st_nlink &&
        before.st_mtime == after.st_mtime

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
