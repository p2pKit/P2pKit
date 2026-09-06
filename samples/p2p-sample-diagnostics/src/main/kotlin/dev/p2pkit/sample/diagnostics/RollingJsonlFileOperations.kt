package dev.p2pkit.sample.diagnostics

import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.io.RandomAccessFile
import java.nio.channels.OverlappingFileLockException
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
        val path = coordinationFile.canonicalPath
        val entry = synchronized(entries) {
            entries.getOrPut(path) { Entry() }.also { it.references++ }
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
