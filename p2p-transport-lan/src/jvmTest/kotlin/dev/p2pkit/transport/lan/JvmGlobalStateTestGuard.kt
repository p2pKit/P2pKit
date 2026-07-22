package dev.p2pkit.transport.lan

import java.util.concurrent.locks.ReentrantLock

/** Serializes LAN tests that temporarily replace process-wide JVM properties. */
internal object JvmGlobalStateTestGuard {
    private val lock = ReentrantLock()

    fun acquire(vararg propertyNames: String): Lease {
        lock.lock()
        return try {
            Lease(propertyNames.associateWith(System::getProperty))
        } catch (error: Throwable) {
            lock.unlock()
            throw error
        }
    }

    fun <T> withValues(values: Map<String, String?>, block: () -> T): T {
        val lease = acquire(*values.keys.toTypedArray())
        return try {
            values.forEach { (name, value) -> lease.set(name, value) }
            block()
        } finally {
            lease.close()
        }
    }

    internal class Lease(
        private val original: Map<String, String?>
    ) : AutoCloseable {
        private var closed = false

        fun set(name: String, value: String?) {
            check(!closed) { "system-property lease is closed" }
            check(name in original) { "property '$name' was not declared when acquiring the lease" }
            setOrClear(name, value)
        }

        fun <T> withValue(name: String, value: String?, block: () -> T): T {
            check(!closed) { "system-property lease is closed" }
            check(name in original) { "property '$name' was not declared when acquiring the lease" }
            val before = System.getProperty(name)
            return try {
                setOrClear(name, value)
                block()
            } finally {
                setOrClear(name, before)
            }
        }

        override fun close() {
            if (closed) return
            try {
                original.forEach { (name, value) -> setOrClear(name, value) }
            } finally {
                closed = true
                lock.unlock()
            }
        }
    }

    private fun setOrClear(name: String, value: String?) {
        if (value == null) {
            System.clearProperty(name)
        } else {
            System.setProperty(name, value)
        }
    }
}
