package dev.p2pkit.core.internal

import java.util.concurrent.locks.ReentrantLock
import kotlin.concurrent.withLock

/** Serializes JVM tests that temporarily replace process-wide system properties. */
internal object JvmSystemPropertyTestGuard {
    private val lock = ReentrantLock()

    fun <T> withValues(values: Map<String, String?>, block: () -> T): T = lock.withLock {
        val original = values.keys.associateWith(System::getProperty)
        try {
            values.forEach { (name, value) -> setOrClear(name, value) }
            block()
        } finally {
            original.forEach { (name, value) -> setOrClear(name, value) }
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
