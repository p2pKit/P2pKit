package dev.p2pkit.core.internal

import platform.Foundation.NSLock

/** Per-Keychain-account exclusion; only short map mutations use the global guard. */
internal object IosSecureIdentityOperationLocks {
    private val guard = NSLock()
    private val entries = mutableMapOf<String, Entry>()

    fun <T> withLock(storageKey: String, block: () -> T): T {
        // Count queued callers as owners before they can wait on the entry.
        val entry = withGuard {
            entries.getOrPut(storageKey, ::Entry).also { it.users += 1 }
        }
        return try {
            entry.lock.lock()
            try {
                block()
            } finally {
                entry.lock.unlock()
            }
        } finally {
            withGuard {
                check(entry.users > 0) { "iOS identity operation-lock reference underflow" }
                entry.users -= 1
                if (entry.users == 0 && entries[storageKey] === entry) entries.remove(storageKey)
            }
        }
    }

    internal fun entryCountForTest(): Int = withGuard { entries.size }

    internal fun usersForTest(storageKey: String): Int = withGuard { entries[storageKey]?.users ?: 0 }

    private fun <T> withGuard(block: () -> T): T {
        guard.lock()
        return try {
            block()
        } finally {
            guard.unlock()
        }
    }

    private class Entry {
        val lock = NSLock()
        var users = 0
    }
}
