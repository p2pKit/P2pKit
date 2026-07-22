package dev.p2pkit.transport.lan

import platform.Foundation.NSLock
import platform.Foundation.NSUserDefaults
import kotlin.uuid.ExperimentalUuidApi
import kotlin.uuid.Uuid

/** Creates a process- and run-unique namespace so stale Bonjour records cannot cross tests. */
@OptIn(ExperimentalUuidApi::class)
internal fun newAppleLanTestNamespace(prefix: String): String = "$prefix-${Uuid.random()}"

/** Serializes and exactly restores Apple tests that touch shared user defaults. */
internal object AppleGlobalStateTestGuard {
    private val lock = NSLock()

    fun acquire(
        defaults: NSUserDefaults = NSUserDefaults.standardUserDefaults,
        vararg keys: String
    ): Lease {
        lock.lock()
        return try {
            Lease(
                defaults = defaults,
                original = keys.associateWith(defaults::objectForKey)
            )
        } catch (error: Throwable) {
            lock.unlock()
            throw error
        }
    }

    internal class Lease(
        private val defaults: NSUserDefaults,
        private val original: Map<String, Any?>
    ) {
        private var closed = false

        fun remove(key: String) {
            check(!closed) { "NSUserDefaults lease is closed" }
            check(key in original) { "key '$key' was not declared when acquiring the lease" }
            defaults.removeObjectForKey(key)
        }

        fun synchronize() {
            check(!closed) { "NSUserDefaults lease is closed" }
            defaults.synchronize()
        }

        fun close() {
            if (closed) return
            try {
                original.forEach { (key, value) ->
                    if (value == null) {
                        defaults.removeObjectForKey(key)
                    } else {
                        defaults.setObject(value, key)
                    }
                }
                defaults.synchronize()
            } finally {
                closed = true
                lock.unlock()
            }
        }
    }
}
