package dev.p2pkit.sample.android.rpclab

import android.os.Build
import android.system.Os
import android.system.OsConstants
import androidx.annotation.RequiresApi
import dev.p2pkit.sample.rpc.RpcTestArchivePage
import dev.p2pkit.sample.rpc.RpcTestArchiveScan
import dev.p2pkit.sample.rpc.RpcTestEvidenceWriter
import java.io.File
import java.io.FileInputStream
import java.nio.file.Files

/** Only the private archive directory; streaming enumeration never materializes all archived filenames. */
internal class RpcTestArchiveFiles(private val directory: File) {
    private fun read(file: File): String {
        val before = Os.lstat(file.path)
        check(OsConstants.S_ISREG(before.st_mode) && before.st_nlink == 1L && before.st_size in 1..65_536)
        val descriptor = Os.open(file.path, OsConstants.O_RDONLY or OsConstants.O_NOFOLLOW or OsConstants.O_NONBLOCK, 0)
        return FileInputStream(descriptor).use { stream ->
            val opened = Os.fstat(descriptor)
            check(opened.st_ino == before.st_ino && opened.st_dev == before.st_dev && opened.st_size == before.st_size)
            val bytes = ByteArray(before.st_size.toInt())
            try {
                var offset = 0
                while (offset < bytes.size) {
                    val count = stream.read(bytes, offset, bytes.size - offset)
                    check(count > 0)
                    offset += count
                }
                check(stream.read() == -1)
                val after = Os.lstat(file.path)
                check(after.st_ino == before.st_ino && after.st_dev == before.st_dev && after.st_size == before.st_size)
                bytes.toString(Charsets.UTF_8)
            } finally { bytes.fill(0) }
        }
    }

    @RequiresApi(26)
    private fun visit(accept: (String, String) -> Unit) {
        check(Build.VERSION.SDK_INT >= 26)
        if (!directory.exists()) return
        check(OsConstants.S_ISDIR(Os.lstat(directory.path).st_mode))
        var entries = 0
        Files.newDirectoryStream(directory.toPath()).use { paths ->
            paths.forEach { path ->
                check(++entries <= 2_000_000) { "Archive entry limit exceeded; originals retained" }
                val name = path.fileName.toString()
                if (name.matches(Regex("[a-f0-9]{32}\\.json"))) {
                    val runId = name.removeSuffix(".json")
                    if (!File(directory, "$runId.deleted").exists()) accept(runId, read(path.toFile()))
                }
            }
        }
    }

    fun browse(beforeMillis: Long = Long.MAX_VALUE, beforeRunId: String = ""): RpcTestArchivePage {
        check(Build.VERSION.SDK_INT >= 26) { "Full archive enumeration requires Android 8 or a computer collector" }
        val scan = RpcTestArchiveScan(beforeMillis, beforeRunId)
        visit(scan::accept)
        return scan.finish()
    }

    fun export(appendLine: (String) -> Unit, runId: String? = null) {
        val writer = RpcTestEvidenceWriter(false, appendLine)
        if (runId == null) {
            check(Build.VERSION.SDK_INT >= 26)
            visit(writer::append)
        } else {
            require(runId.matches(Regex("[a-f0-9]{32}")))
            check(!File(directory, "$runId.deleted").exists())
            writer.append(runId, read(File(directory, "$runId.json")))
        }
        writer.finish()
    }
}
