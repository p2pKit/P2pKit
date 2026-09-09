package dev.p2pkit.core.internal

import dev.p2pkit.core.LocalIdentityFailureKind
import dev.p2pkit.core.LocalIdentityRecovery
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.security.localIdentityError
import java.io.File
import java.io.RandomAccessFile
import kotlinx.coroutines.CancellationException

/** Keep same-alias operations serialized without holding a global guard across I/O. */
internal fun <T> withAndroidIdentityStorageLock(
    storageKey: String,
    directory: File,
    block: () -> T
): T = AndroidSecureIdentityOperationLocks.withLock(storageKey) {
    try {
        if (!directory.isDirectory) directory.mkdirs()
        if (!directory.isDirectory) {
            throw IllegalStateException("Could not create Android identity storage directory")
        }
        RandomAccessFile(File(directory, "identity.lock"), "rw").use { randomAccess ->
            randomAccess.channel.use { channel ->
                channel.lock().use { block() }
            }
        }
    } catch (error: P2pError.LocalIdentityUnavailable) {
        throw error
    } catch (error: CancellationException) {
        throw error
    } catch (error: Exception) {
        throw localIdentityError(
            kind = LocalIdentityFailureKind.PERSISTENCE_FAILED,
            recovery = LocalIdentityRecovery.RETRY,
            reason = "Could not lock Android secure identity state",
            cause = error
        )
    }
}

/**
 * Entries count owners and queued callers before acquiring the operation lock.
 * Key by namespace, not path: different roots can still share a Keystore alias.
 * Completed namespaces are removed; the map guard never owns filesystem/crypto work.
 */
internal object AndroidSecureIdentityOperationLocks {
    private val guard = Any()
    private val entries = mutableMapOf<String, Entry>()

    fun <T> withLock(storageKey: String, block: () -> T): T {
        val entry = synchronized(guard) {
            entries.getOrPut(storageKey, ::Entry).also { it.users += 1 }
        }
        return try {
            synchronized(entry.monitor) { block() }
        } finally {
            synchronized(guard) {
                check(entry.users > 0) { "Android identity operation-lock reference underflow" }
                entry.users -= 1
                if (entry.users == 0 && entries[storageKey] === entry) entries.remove(storageKey)
            }
        }
    }

    internal fun entryCountForTest(): Int = synchronized(guard) { entries.size }

    internal fun usersForTest(storageKey: String): Int = synchronized(guard) { entries[storageKey]?.users ?: 0 }

    private class Entry {
        val monitor = Any()
        var users = 0
    }
}
