package dev.p2pkit.sample.diagnostics

import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.io.RandomAccessFile
import java.nio.channels.OverlappingFileLockException
import java.nio.charset.CharacterCodingException
import java.util.concurrent.Semaphore

/** Narrow fault-injection seam; the defaults execute real, Android API24-compatible file operations. */
internal open class RollingJsonlFileOperations {
    open fun list(directory: File): Array<File> =
        directory.listFiles() ?: throw IOException("Could not list diagnostic log directory")

    open fun delete(file: File) {
        if (file.exists() && !file.delete()) throw IOException("Could not delete diagnostic log")
        if (file.exists()) throw IOException("Diagnostic log remains after deletion")
    }

    open fun move(source: File, destination: File) {
        // Generations are siblings and the destination must already be vacant.
        // Never fall back to copy/delete or overwrite an unexpected entry.
        if (destination.exists() || !source.renameTo(destination)) {
            throw IOException("Could not rotate diagnostic log")
        }
        if (source.exists() || !destination.isFile) throw IOException("Diagnostic rotation did not complete")
    }

    open fun append(file: File, bytes: ByteArray) {
        FileOutputStream(file, true).use {
            it.write(bytes)
            it.write('\n'.code)
        }
    }

    open fun truncate(file: File, length: Long) {
        if (file.exists()) RandomAccessFile(file, "rw").use { it.setLength(length) }
    }

    open fun createRewrite(original: File): File =
        File.createTempFile(".p2pkit-clear-", ".tmp", original.parentFile)

    open fun rewrite(original: File, staged: File, maxRecordBytes: Long, retain: (String) -> Boolean) {
        // Keep each retained line's original bytes, including CRLF, invalid UTF-8 and
        // an incomplete final line. Bound staging memory by the configured record limit.
        staged.outputStream().buffered().use { output ->
            original.inputStream().buffered().use { input ->
                val line = ByteArrayOutputStream()
                fun emit() {
                    val bytes = line.toByteArray()
                    val text = try {
                        bytes.decodeToString(throwOnInvalidSequence = true)
                    } catch (_: CharacterCodingException) {
                        null
                    }
                    if (text == null || retain(text)) output.write(bytes)
                    line.reset()
                }
                val buffer = ByteArray(DEFAULT_BUFFER_SIZE)
                while (true) {
                    val count = input.read(buffer)
                    if (count < 0) break
                    var start = 0
                    for (index in 0 until count) {
                        if (buffer[index] == '\n'.code.toByte()) {
                            val size = index + 1 - start
                            if (size > maxRecordBytes - line.size()) {
                                throw IOException("Diagnostic record exceeds the log file limit")
                            }
                            line.write(buffer, start, size)
                            emit()
                            start = index + 1
                        }
                    }
                    val remaining = count - start
                    if (remaining > maxRecordBytes - line.size()) {
                        throw IOException("Diagnostic record exceeds the log file limit")
                    }
                    line.write(buffer, start, remaining)
                }
                if (line.size() > 0) emit()
            }
        }
    }

    open fun replace(staged: File, original: File) {
        replaceDiagnosticFile(staged, original, requireAtomic = true)
    }

    fun endsWithNewline(file: File): Boolean {
        if (!file.exists() || file.length() == 0L) return true
        return RandomAccessFile(file, "r").use {
            it.seek(it.length() - 1)
            it.read() == '\n'.code
        }
    }
}

/**
 * An in-process guard is required in addition to the OS lock: on some platforms closing a
 * second channel to the same file releases the process's first channel's native lock too.
 * Reference counts keep the registry bounded by currently attempted operations, not paths seen.
 */
internal object RollingJsonlFileLock {
    private class Entry {
        val permit: Semaphore = Semaphore(1)
        var references: Int = 0
    }

    private val entries: MutableMap<String, Entry> = mutableMapOf()

    fun <T> withLock(coordinationFile: File, action: () -> T): T {
        val (path, entry) = synchronized(entries) {
            // Canonical spelling is reliable only after the coordination entry exists.
            // Serialize its exclusive creation, including cold case aliases. createNewFile
            // never opens/closes an existing file, so it cannot release an owner's OS lock.
            if (!coordinationFile.exists()) coordinationFile.createNewFile()
            if (!coordinationFile.isFile) throw IOException("Could not create diagnostic coordination file")
            val path = coordinationFile.canonicalPath
            path to entries.getOrPut(path) { Entry() }.also { it.references++ }
        }
        val acquired = entry.permit.tryAcquire()
        try {
            if (!acquired) throw IOException("Diagnostic log family is busy")
            return RandomAccessFile(coordinationFile, "rw").use { coordination ->
                val claim = try {
                    coordination.channel.tryLock()
                } catch (_: OverlappingFileLockException) {
                    null
                } ?: throw IOException("Diagnostic log family is busy")
                var actionFailure: Throwable? = null
                try {
                    action()
                } catch (failure: Throwable) {
                    actionFailure = failure
                    throw failure
                } finally {
                    try {
                        claim.release()
                    } catch (releaseFailure: Exception) {
                        val failure = actionFailure
                        if (failure == null) throw releaseFailure
                        failure.addSuppressed(releaseFailure)
                    }
                }
            }
        } finally {
            if (acquired) entry.permit.release()
            synchronized(entries) {
                entry.references--
                if (entry.references == 0) entries.remove(path)
            }
        }
    }
}
