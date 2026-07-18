package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.PeerId
import kotlin.uuid.ExperimentalUuidApi
import kotlin.uuid.Uuid
import platform.Foundation.NSFileManager
import platform.Foundation.NSUserDefaults
import platform.Foundation.NSTemporaryDirectory
import platform.Foundation.NSLock
import platform.posix.LOCK_EX
import platform.posix.LOCK_UN
import platform.posix.O_CREAT
import platform.posix.O_RDWR
import platform.posix.S_IRUSR
import platform.posix.S_IWUSR
import platform.posix.close
import platform.posix.errno
import platform.posix.flock
import platform.posix.open

/**
 * iOS [PeerIdStorage] backed by `NSUserDefaults.standardUserDefaults`.
 *
 * NSUserDefaults persists across app launches, survives iOS upgrades, and is
 * cleared on app uninstall — matching the on-uninstall semantics of the
 * Android `filesDir`-based storage. Unlike Android, iOS apps always have
 * writable app-scoped storage, so there is no init-context dance and no
 * in-memory fallback.
 *
 * A legacy-sanitized bucket preserves rollback/test cleanup compatibility,
 * while a full AppId hash keys each entry so lossy sanitizer collisions never
 * share writable state. An NSLock plus POSIX file lock serializes first use
 * across threads and cooperating processes.
 *
 * Internal — apps don't construct this directly; [defaultPeerIdStorage]
 * routes here on iOS.
 */
internal class NSUserDefaultsPeerIdStorage(
    appId: AppId,
    private val logger: P2pLogger,
    private val defaults: NSUserDefaults = NSUserDefaults.standardUserDefaults,
    private val synchronizeDefaults: () -> Boolean = { defaults.synchronize() }
) : PeerIdStorage {

    private val legacySuffix = sanitizeAppIdForKey(appId.value)
    private val legacyKey = "dev.p2pkit.peerId.$legacySuffix"
    private val bucketKey = "dev.p2pkit.peerId.v2.$legacySuffix"
    private val entryKey = peerIdStorageKey(appId.value)
    private val lockDirectory = "${NSTemporaryDirectory()}p2pkit-peer-id-locks"
    private val lockPath = "$lockDirectory/$legacySuffix.lock"
    private var cached: PeerId? = null

    override fun loadOrGenerate(): PeerId {
        return withProcessLock {
            cached?.let { return@withProcessLock it }
            val resolved = try {
                withCrossProcessLock {
                    if (!synchronizeDefaults()) {
                        throw IllegalStateException(
                            "NSUserDefaults did not refresh PeerId bucket $bucketKey"
                        )
                    }
                    readBucketEntryOrNull()
                        ?: migrateLegacyOrNull()
                        ?: generateAndPersistLocked()
                }
            } catch (error: Exception) {
                logger.warn(
                    "Failed to coordinate persistent PeerId under NSUserDefaults key $bucketKey; " +
                        "using a process-local identity for this storage instance",
                    error
                )
                readBucketEntryOrNull() ?: readLegacyOrNull() ?: newPeerId()
            }
            cached = resolved
            resolved
        }
    }

    private fun readBucketEntryOrNull(): PeerId? {
        val raw = defaults.dictionaryForKey(bucketKey)?.get(entryKey) as? String ?: return null
        val trimmed = raw.trim()
        return if (trimmed.isEmpty()) null else PeerId(trimmed)
    }

    private fun readLegacyOrNull(): PeerId? {
        val raw = defaults.stringForKey(legacyKey) ?: return null
        val trimmed = raw.trim()
        return if (trimmed.isEmpty()) null else PeerId(trimmed)
    }

    private fun migrateLegacyOrNull(): PeerId? {
        val legacy = readLegacyOrNull() ?: return null
        logger.warn("Migrating persistent PeerId from legacy NSUserDefaults key $legacyKey")
        persistOrLog(legacy)
        return legacy
    }

    @OptIn(ExperimentalUuidApi::class)
    private fun newPeerId(): PeerId = PeerId(Uuid.random().toString())

    private fun generateAndPersistLocked(): PeerId {
        val fresh = newPeerId()
        persistOrLog(fresh)
        return readBucketEntryOrNull() ?: fresh
    }

    private fun persistOrLog(id: PeerId) {
        try {
            val bucket = defaults.dictionaryForKey(bucketKey)?.toMutableMap()
                ?: mutableMapOf<Any?, Any?>()
            bucket[entryKey] = id.value
            defaults.setObject(bucket, bucketKey)
            if (!synchronizeDefaults()) {
                throw IllegalStateException("NSUserDefaults did not synchronize PeerId bucket $bucketKey")
            }
            val durable = readBucketEntryOrNull()
                ?: throw IllegalStateException("Persisted PeerId bucket did not contain its committed entry")
            if (durable != id) {
                throw IllegalStateException("Persisted PeerId bucket committed a different value")
            }
        } catch (e: Exception) {
            logger.warn(
                "Failed to persist PeerId to NSUserDefaults under key $bucketKey; " +
                    "the returned PeerId remains stable for this storage instance only",
                e
            )
        }
    }

    private inline fun <T> withProcessLock(block: () -> T): T {
        processLock.lock()
        return try {
            block()
        } finally {
            processLock.unlock()
        }
    }

    @OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)
    private inline fun <T> withCrossProcessLock(block: () -> T): T {
        val created = NSFileManager.defaultManager.createDirectoryAtPath(
            path = lockDirectory,
            withIntermediateDirectories = true,
            attributes = null,
            error = null
        )
        if (!created) throw IllegalStateException("Could not create PeerId lock directory $lockDirectory")
        val descriptor = open(lockPath, O_CREAT or O_RDWR, S_IRUSR or S_IWUSR)
        if (descriptor < 0) {
            throw IllegalStateException("Could not open PeerId lock $lockPath (errno=$errno)")
        }
        try {
            if (flock(descriptor, LOCK_EX) != 0) {
                throw IllegalStateException("Could not acquire PeerId lock $lockPath (errno=$errno)")
            }
            return block()
        } finally {
            flock(descriptor, LOCK_UN)
            close(descriptor)
        }
    }

    private companion object {
        private val processLock = NSLock()
    }
}

/**
 * Reduce a raw appId to a safe `NSUserDefaults` key suffix.
 *
 * Keeps `[A-Za-z0-9._-]`, replaces anything else with `_`, collapses any
 * `..` to `._` (parallels [sanitizeAppIdForFilesystem] on JVM/Android), and
 * caps the result at 64 characters.
 */
internal fun sanitizeAppIdForKey(raw: String): String {
    if (raw.isBlank()) return "_"
    val sb = StringBuilder(raw.length)
    for (c in raw) {
        sb.append(if (c.isLetterOrDigit() || c == '_' || c == '-' || c == '.') c else '_')
    }
    val noTraversal = sb.toString().replace("..", "._")
    val trimmed = noTraversal.trimStart('.').ifEmpty { "_" }
    return trimmed.take(64)
}
