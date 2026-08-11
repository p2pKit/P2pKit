package dev.p2pkit.core.internal

import android.util.AtomicFile
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.PeerId
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.io.InputStream
import java.io.RandomAccessFile
import kotlin.uuid.ExperimentalUuidApi
import kotlin.uuid.Uuid

/**
 * Android counterpart of the JVM [FilePeerIdStorage]. It uses the same hashed
 * namespace and process/file-lock transaction, with [AtomicFile] providing
 * Android's crash-safe replacement semantics.
 */
internal class FilePeerIdStorage(
    rootDir: File,
    rawAppId: String,
    private val logger: P2pLogger
) : PeerIdStorage {

    private val legacySegment = sanitizeAppIdForFilesystem(rawAppId)
    private val storageDir: File =
        File(File(File(rootDir, "p2pkit"), "peer-id-v2"), peerIdStorageKey(rawAppId))
    private val storageFile: File = File(storageDir, "peer-id")
    private val atomicStorage = AtomicFile(storageFile)
    private val lockFile = File(storageDir, "peer-id.lock")
    private val previousFile = File(File(File(rootDir, "p2pkit"), legacySegment), "peer-id")

    @Volatile
    private var cached: PeerId? = null

    internal val storagePath: String get() = storageFile.absolutePath

    override fun loadOrGenerate(): PeerId {
        cached?.let { return it }
        return PeerIdProcessLockRegistry.withLock(storageFile.absolutePath) {
            cached?.let { return@withLock it }
            val resolved = try {
                withStorageLock {
                    readIdFromAtomic()
                        ?: migrateLegacyOrNull()
                        ?: generateAndPersistLocked()
                }
            } catch (error: Exception) {
                logger.warn(
                    "Failed to lock persistent PeerId storage at ${storageFile.absolutePath}; " +
                        "using a process-local identity for this storage instance",
                    error
                )
                readIdFromAtomic() ?: readIdFrom(previousFile) ?: newPeerId()
            }
            cached = resolved
            resolved
        }
    }

    private fun readIdFromAtomic(): PeerId? {
        if (!storageFile.exists() && !File(storageFile.path + ".bak").exists()) return null
        return try {
            atomicStorage.openRead().use { input ->
                decodePersistedPeerId(input.readBoundedPeerIdBytes())
            }
        } catch (e: Exception) {
            logger.warn(
                "Failed to read persistent PeerId from ${storageFile.absolutePath}; will regenerate",
                e
            )
            null
        }
    }

    private fun readIdFrom(file: File): PeerId? {
        if (!file.exists()) return null
        return try {
            file.inputStream().use { input ->
                decodePersistedPeerId(input.readBoundedPeerIdBytes())
            }
        } catch (error: Exception) {
            logger.warn("Failed to read legacy PeerId from ${file.absolutePath}", error)
            null
        }
    }

    private fun migrateLegacyOrNull(): PeerId? {
        val legacy = readIdFrom(previousFile) ?: return null
        logger.warn(
            "Migrating persistent PeerId from legacy ${previousFile.absolutePath} " +
                "to ${storageFile.absolutePath}"
        )
        persistOrLog(legacy)
        return legacy
    }

    @OptIn(ExperimentalUuidApi::class)
    private fun newPeerId(): PeerId = PeerId(Uuid.random().toString())

    private fun generateAndPersistLocked(): PeerId {
        val fresh = newPeerId()
        persistOrLog(fresh)
        return readIdFromAtomic() ?: fresh
    }

    private fun persistOrLog(id: PeerId) {
        try {
            persistAtomic(id)
        } catch (e: Exception) {
            logger.warn(
                "Failed to atomically persist PeerId to ${storageFile.absolutePath}; " +
                    "the returned PeerId remains stable for this storage instance only",
                e
            )
        }
    }

    private fun persistAtomic(id: PeerId) {
        ensureStorageDirectory()
        var output: FileOutputStream? = null
        try {
            val stream = atomicStorage.startWrite()
            output = stream
            stream.write(id.value.encodeToByteArray())
            atomicStorage.finishWrite(stream)
            output = null
        } catch (error: Exception) {
            output?.let { stream ->
                try {
                    atomicStorage.failWrite(stream)
                } catch (cleanupFailure: Exception) {
                    error.addSuppressed(cleanupFailure)
                }
            }
            throw error
        }
        val durable = readIdFromAtomic()
            ?: throw IOException("Atomic PeerId replacement did not produce a readable target")
        if (durable != id) throw IOException("Atomic PeerId replacement committed a different value")
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
        // mkdirs() reports false when a competing process creates the same
        // directory first. Judge the durable postcondition after the attempt
        // so concurrent first use does not fall back to a divergent identity.
        if (!storageDir.isDirectory && !storageDir.mkdirs() && !storageDir.isDirectory) {
            throw IOException("Could not create PeerId storage directory ${storageDir.absolutePath}")
        }
        if (!storageDir.isDirectory) {
            throw IOException("PeerId storage path is not a directory: ${storageDir.absolutePath}")
        }
    }

}

/** Android counterpart of the JVM operation-scoped process-lock registry. */
private object PeerIdProcessLockRegistry {
    private val guard = Any()
    private val entries = mutableMapOf<String, ProcessLockEntry>()

    fun <T> withLock(path: String, block: () -> T): T {
        val entry = synchronized(guard) {
            entries.getOrPut(path, ::ProcessLockEntry).also { it.users += 1 }
        }
        return try {
            synchronized(entry.monitor) { block() }
        } finally {
            synchronized(guard) {
                check(entry.users > 0) { "PeerId process-lock reference underflow" }
                entry.users -= 1
                if (entry.users == 0 && entries[path] === entry) entries.remove(path)
            }
        }
    }
}

private class ProcessLockEntry {
    val monitor: Any = Any()
    var users: Int = 0
}

private fun InputStream.readBoundedPeerIdBytes(): ByteArray {
    val buffer = ByteArray(MAX_PERSISTED_PEER_ID_BYTES + 1)
    var total = 0
    while (total < buffer.size) {
        val read = read(buffer, total, buffer.size - total)
        if (read < 0) break
        if (read == 0) {
            val next = read()
            if (next < 0) break
            buffer[total++] = next.toByte()
        } else {
            total += read
        }
    }
    require(total <= MAX_PERSISTED_PEER_ID_BYTES) {
        "persistent PeerId exceeds $MAX_PERSISTED_PEER_ID_BYTES bytes"
    }
    return buffer.copyOf(total)
}

internal fun sanitizeAppIdForFilesystem(raw: String): String {
    if (raw.isBlank()) return "_"
    val sb = StringBuilder(raw.length)
    for (c in raw) {
        sb.append(if (c.isLetterOrDigit() || c == '_' || c == '-' || c == '.') c else '_')
    }
    val noTraversal = sb.toString().replace("..", "._")
    val trimmed = noTraversal.trimStart('.').ifEmpty { "_" }
    return trimmed.take(64)
}
