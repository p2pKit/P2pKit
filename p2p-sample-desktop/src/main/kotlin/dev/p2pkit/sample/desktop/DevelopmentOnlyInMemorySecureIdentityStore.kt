package dev.p2pkit.sample.desktop

import dev.p2pkit.core.security.JvmSecureIdentityStore

/**
 * Process-local sample storage. It deliberately loses identity on exit and is
 * not suitable for production; real JVM hosts must inject protected durable
 * storage with cross-process atomicity.
 */
internal class DevelopmentOnlyInMemorySecureIdentityStore : JvmSecureIdentityStore {
    private val values = mutableMapOf<String, ByteArray>()

    override fun read(namespace: String): ByteArray? =
        synchronized(values) { values[namespace]?.copyOf() }

    override fun putIfAbsent(namespace: String, value: ByteArray): ByteArray =
        synchronized(values) { values.getOrPut(namespace) { value.copyOf() }.copyOf() }

    override fun delete(namespace: String): Boolean =
        synchronized(values) { values.remove(namespace) != null }
}
