package dev.p2pkit.sample.diagnostics

import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.io.RandomAccessFile
import java.nio.channels.FileLock
import java.nio.channels.OverlappingFileLockException
import java.util.UUID

/**
 * A private staging namespace, never a filename rule over the received-file inbox.
 * Each transfer publishes its ownership record only after holding its OS lease.
 * Reclamation requires that record AND an exclusive nonblocking OS lock. Unknown
 * entries and legacy sibling parts are deliberately left alone: their age/name
 * cannot distinguish a completed file from another process's live transfer.
 * The caller supplies a trusted app-controlled inbox (not an adversarial filesystem).
 */
internal object TransferStagingOwnership {
    private const val ROOT = ".p2pkit-transfer-staging-v1"
    private const val RECORD = "ownership"
    private const val LOCK = "lease"
    private const val MAGIC = "p2pkit-sample-transfer-staging-v1\n"
    private val monitor = Any()
    // Do not open/close a second descriptor for a locally locked inode: on some
    // POSIX implementations that can release this process's original file lock.
    private val active = mutableSetOf<String>()

    fun claim(inbox: File): Lease = synchronized(monitor) {
        val root = root(inbox)
        val token = UUID.randomUUID().toString()
        val directory = File(root, token)
        if (!directory.mkdir()) throw IOException("Could not claim transfer staging directory")
        val lockFile = File(directory, LOCK)
        var handle: RandomAccessFile? = null
        var lock: FileLock? = null
        try {
            if (!lockFile.createNewFile()) throw IOException("Staging lease already exists")
            handle = RandomAccessFile(lockFile, "rw")
            lock = handle.channel.tryLock() ?: throw IOException("Could not acquire new staging lease")
            val record = File(directory, RECORD)
            if (!record.createNewFile()) throw IOException("Staging ownership record already exists")
            FileOutputStream(record).use { output ->
                output.write((MAGIC + token + "\n").toByteArray(Charsets.UTF_8))
                output.fd.sync()
            }
            active.add(directory.path)
            Lease(directory, handle, lock)
        } catch (failure: Throwable) {
            try { lock?.release() } catch (cleanup: Throwable) { failure.addSuppressed(cleanup) }
            try { handle?.close() } catch (cleanup: Throwable) { failure.addSuppressed(cleanup) }
            // No payload has been opened. Never recurse into unexpected entries.
            listOf(File(directory, RECORD), lockFile, directory).forEach { owned ->
                if (owned.exists() && !owned.delete()) {
                    failure.addSuppressed(IOException("Could not remove incomplete staging claim"))
                }
            }
            throw failure
        }
    }

    fun reconcile(inbox: File) = synchronized(monitor) {
        val parent = inbox.canonicalFile
        val roots = parent.listFiles() ?: throw IOException("Could not list transfer inbox")
        for (root in roots.filter { isRootName(it.name) }) {
            // A pre-upgrade received file can legitimately have this name.
            if (isPlainFile(root)) continue
            requirePlainDirectory(root)
            reconcileRoot(root)
        }
    }

    private fun reconcileRoot(root: File) {
        val entries = root.listFiles() ?: throw IOException("Could not list transfer staging namespace")
        for (directory in entries) {
            if (!isPlainDirectory(directory) || directory.path in active) continue
            val token = directory.name
            if (runCatching { UUID.fromString(token).toString() }.getOrNull() != token) continue
            val record = File(directory, RECORD)
            val lockFile = File(directory, LOCK)
            if (!isPlainFile(record) || !isPlainFile(lockFile)) continue
            val expected = (MAGIC + token + "\n").toByteArray(Charsets.UTF_8)
            if (!matchesRecord(record, expected)) continue
            // Opening an existing, validated file does not confer ownership; only
            // the successfully acquired OS lock below does. Never wait on a writer.
            RandomAccessFile(lockFile, "rw").use { handle ->
                val lock = try { handle.channel.tryLock() } catch (_: OverlappingFileLockException) { null }
                if (lock != null) {
                    val reconciled = lock.use {
                        if (safeContents(directory)) {
                            deleteParts(directory)
                            deleteChecked(record)
                            true
                        } else {
                            false
                        }
                    }
                    // Windows requires closing the lock handle before unlinking it.
                    handle.close()
                    if (reconciled) {
                        deleteChecked(lockFile)
                        deleteChecked(directory)
                    }
                }
            }
        }
    }

    private fun root(inbox: File): File {
        val parent = inbox.canonicalFile
        requirePlainDirectory(parent)
        for (index in 0..1000) {
            val root = File(parent, if (index == 0) ROOT else "$ROOT.$index")
            if (!root.mkdir() && !root.exists()) throw IOException("Could not create transfer staging namespace")
            if (isPlainFile(root)) continue // Preserve accepted filenames, including older completed payloads.
            requirePlainDirectory(root)
            return root
        }
        throw IOException("Could not claim an available staging namespace")
    }

    private fun isRootName(name: String): Boolean = name == ROOT ||
        name.removePrefix("$ROOT.").toIntOrNull()?.let { it in 1..1000 && name == "$ROOT.$it" } == true

    private fun isPlainDirectory(file: File): Boolean = file.isDirectory && file.canonicalFile == file.absoluteFile
    private fun isPlainFile(file: File): Boolean = file.isFile && file.canonicalFile == file.absoluteFile
    private fun requirePlainDirectory(file: File) {
        if (!isPlainDirectory(file)) throw IOException("Staging namespace is not a plain directory")
    }

    private fun isPart(file: File): Boolean = file.name.startsWith(".p2pkit-") && file.name.endsWith(".part")

    private fun matchesRecord(record: File, expected: ByteArray): Boolean {
        if (record.length() != expected.size.toLong()) return false
        return record.inputStream().use { input ->
            val bytes = ByteArray(expected.size + 1)
            var count = 0
            while (count < bytes.size) {
                val read = input.read(bytes, count, bytes.size - count)
                if (read < 0) break
                if (read == 0) return@use false
                count += read
            }
            count == expected.size && bytes.copyOf(count).contentEquals(expected)
        }
    }

    private fun safeContents(directory: File): Boolean = directory.listFiles()?.all {
        isPlainFile(it) && (it.name == RECORD || it.name == LOCK || isPart(it))
    } == true

    private fun deleteParts(directory: File) {
        val entries = directory.listFiles() ?: throw IOException("Could not list owned staging directory")
        entries.filter(::isPart).forEach(::deleteChecked)
    }

    private fun deleteChecked(file: File) {
        if (file.exists() && !file.delete()) throw IOException("Could not remove owned staging entry")
    }

    internal class Lease internal constructor(
        val directory: File,
        private val handle: RandomAccessFile,
        private val lock: FileLock
    ) {
        private var retired = false

        /** Call only after the delegate has closed its writer, including failed-open cleanup. */
        fun retire() = synchronized(monitor) {
            if (retired) return@synchronized
            if (!safeContents(directory)) throw IOException("Unexpected entry in owned staging directory")
            deleteParts(directory)
            deleteChecked(File(directory, RECORD))
            if (lock.isValid) lock.release()
            handle.close()
            deleteChecked(File(directory, LOCK))
            deleteChecked(directory)
            active.remove(directory.path)
            retired = true
        }
    }
}
