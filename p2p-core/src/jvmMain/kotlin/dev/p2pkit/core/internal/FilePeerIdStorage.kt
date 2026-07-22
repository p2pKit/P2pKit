package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.PeerId
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.io.RandomAccessFile
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.nio.file.StandardOpenOption
import java.util.concurrent.ConcurrentHashMap
import kotlin.uuid.ExperimentalUuidApi
import kotlin.uuid.Uuid

/**
 * [PeerIdStorage] backed by a single file under
 * `<rootDir>/.p2pkit/peer-id-v2/<fullAppIdHash>/peer-id`.
 *
 * Writes use a unique, fsynced temp file plus an atomic move. A process-local
 * lock prevents overlapping JVM file locks, while a file lock coordinates
 * cooperating processes before they reread and commit one winner.
 * If the file ever exists but is empty or unparseable, it's overwritten on
 * the next [loadOrGenerate].
 *
 * AUDIT-2026-06: the directory was previously the visible `p2pkit` (no dot),
 * which contradicted the docs. A one-time migration in `readExistingOrNull`
 * adopts an id from the legacy `<rootDir>/p2pkit/...` location so existing
 * desktop installs keep their identity across the rename.
 *
 * @param rootDir Filesystem directory P2pKit can write under (e.g.,
 *   `~/.p2pkit` on JVM, `Context.filesDir` on Android).
 * @param rawAppId The user's [dev.p2pkit.core.AppId] string. A full,
 *   domain-separated SHA-256 hash is the writable namespace; the legacy
 *   sanitizer is used only to locate read-only migration inputs.
 * @param logger Used only for warn-logging I/O failures; never throws.
 */
internal class FilePeerIdStorage(
    rootDir: File,
    rawAppId: String,
    private val logger: P2pLogger
) : PeerIdStorage {

    private val legacySegment = sanitizeAppIdForFilesystem(rawAppId)
    private val storageDir: File =
        File(File(File(rootDir, ".p2pkit"), "peer-id-v2"), peerIdStorageKey(rawAppId))
    private val storageFile: File = File(storageDir, "peer-id")
    private val lockFile: File = File(storageDir, "peer-id.lock")
    private val processLock: Any = processLockFor(storageFile.absolutePath)

    @Volatile
    private var cached: PeerId? = null

    /** Previous hidden path, before the collision-resistant AppId namespace. */
    private val previousHiddenFile: File =
        File(File(File(rootDir, ".p2pkit"), legacySegment), "peer-id")

    /** Pre-AUDIT-2026-06 visible path. Both migration inputs remain untouched for rollback. */
    private val previousVisibleFile: File =
        File(File(File(rootDir, "p2pkit"), legacySegment), "peer-id")

    /** Absolute path of the underlying file. Exposed for tests only. */
    internal val storagePath: String get() = storageFile.absolutePath

    override fun loadOrGenerate(): PeerId {
        cached?.let { return it }
        return synchronized(processLock) {
            cached?.let { return@synchronized it }
            val resolved = try {
                withStorageLock {
                    readIdFrom(storageFile)
                        ?: migrateLegacyOrNull()
                        ?: generateAndPersistLocked()
                }
            } catch (error: Exception) {
                logger.warn(
                    "Failed to lock persistent PeerId storage at ${storageFile.absolutePath}; " +
                        "using a process-local identity for this storage instance",
                    error
                )
                readIdFrom(storageFile)
                    ?: readIdFrom(previousHiddenFile)
                    ?: readIdFrom(previousVisibleFile)
                    ?: newPeerId()
            }
            cached = resolved
            resolved
        }
    }

    /**
     * One-time migration from the legacy visible-`p2pkit` directory. If the
     * new hidden path has no id but the old one does, re-persist it under the
     * new path so the device keeps its identity across the AUDIT-2026-06
     * rename. Best-effort: any failure just falls through to a fresh id.
     */
    private fun migrateLegacyOrNull(): PeerId? {
        val (source, legacy) = listOf(previousHiddenFile, previousVisibleFile)
            .firstNotNullOfOrNull { file -> readIdFrom(file)?.let { file to it } }
            ?: return null
        logger.warn(
            "Migrating persistent PeerId from legacy ${source.absolutePath} to ${storageFile.absolutePath}"
        )
        persistOrLog(legacy)
        return legacy
    }

    private fun readIdFrom(file: File): PeerId? {
        if (!file.exists()) return null
        return try {
            val content = file.readText().trim()
            if (content.isBlank()) null else PeerId(content)
        } catch (e: Exception) {
            logger.warn("Failed to read persistent PeerId from ${file.absolutePath}; will regenerate", e)
            null
        }
    }

    @OptIn(ExperimentalUuidApi::class)
    private fun newPeerId(): PeerId = PeerId(Uuid.random().toString())

    private fun generateAndPersistLocked(): PeerId {
        val fresh = newPeerId()
        persistOrLog(fresh)
        // A competing process using this version cannot write outside the
        // file lock. Rereading still makes the durable record authoritative
        // if the filesystem reports a surprising replacement.
        return readIdFrom(storageFile) ?: fresh
    }

    private fun persistOrLog(id: PeerId) {
        try {
            persistAtomic(id)
        } catch (error: Exception) {
            logger.warn(
                "Failed to atomically persist PeerId to ${storageFile.absolutePath}; " +
                    "the returned PeerId remains stable for this storage instance only",
                error
            )
        }
    }

    private fun persistAtomic(id: PeerId) {
        ensureStorageDirectory()
        val temporary = Files.createTempFile(storageDir.toPath(), "peer-id-", ".tmp").toFile()
        try {
            FileOutputStream(temporary).use { output ->
                output.write(id.value.encodeToByteArray())
                output.fd.sync()
            }
            try {
                Files.move(
                    temporary.toPath(),
                    storageFile.toPath(),
                    StandardCopyOption.ATOMIC_MOVE,
                    StandardCopyOption.REPLACE_EXISTING
                )
            } catch (unsupported: AtomicMoveNotSupportedException) {
                throw IOException(
                    "Filesystem does not support atomic PeerId replacement at ${storageFile.absolutePath}",
                    unsupported
                )
            }
            val durable = readIdFrom(storageFile)
                ?: throw IOException("Atomic PeerId replacement did not produce a readable target")
            if (durable != id) {
                throw IOException("Atomic PeerId replacement committed a different value")
            }
            fsyncDirectoryBestEffort()
        } finally {
            if (temporary.exists() && !temporary.delete()) {
                logger.warn("Could not delete stale PeerId temp file ${temporary.absolutePath}")
            }
        }
    }

    private fun <T> withStorageLock(block: () -> T): T {
        ensureStorageDirectory()
        return RandomAccessFile(lockFile, "rw").use { randomAccess ->
            randomAccess.channel.use { channel ->
                channel.lock().use { block() }
            }
        }
    }

    private fun ensureStorageDirectory() {
        if (!storageDir.isDirectory && !storageDir.mkdirs()) {
            throw IOException("Could not create PeerId storage directory ${storageDir.absolutePath}")
        }
        if (!storageDir.isDirectory) {
            throw IOException("PeerId storage path is not a directory: ${storageDir.absolutePath}")
        }
    }

    private fun fsyncDirectoryBestEffort() {
        try {
            java.nio.channels.FileChannel.open(storageDir.toPath(), StandardOpenOption.READ).use {
                it.force(true)
            }
        } catch (error: Exception) {
            // The file contents were fsynced and the rename was atomic. Some
            // supported filesystems do not expose directory descriptors to
            // Java; report the weaker crash-durability guarantee explicitly.
            logger.warn("Could not fsync PeerId storage directory ${storageDir.absolutePath}", error)
        }
    }

    private companion object {
        private val processLocks = ConcurrentHashMap<String, Any>()

        fun processLockFor(path: String): Any = processLocks.computeIfAbsent(path) { Any() }
    }
}

/**
 * Reduce a raw appId to a path-safe directory-name segment.
 *
 * - Keeps `[A-Za-z0-9._-]`; replaces anything else with `_`.
 * - Collapses any `..` sequence to `._` so the result cannot navigate up.
 * - Trims leading dots so we don't create hidden directories.
 * - Caps the result at 64 chars.
 */
internal fun sanitizeAppIdForFilesystem(raw: String): String {
    if (raw.isBlank()) return "_"
    val sb = StringBuilder(raw.length)
    for (c in raw) {
        sb.append(if (c.isLetterOrDigit() || c == '_' || c == '-' || c == '.') c else '_')
    }
    // Replace every `..` with `._` (replace-all is non-overlapping, single
    // pass is sufficient to eliminate every traversal pair).
    val noTraversal = sb.toString().replace("..", "._")
    val trimmed = noTraversal.trimStart('.').ifEmpty { "_" }
    return trimmed.take(64)
}
