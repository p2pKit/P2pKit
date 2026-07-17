package dev.p2pkit.sample.kmp

import dev.p2pkit.core.security.JvmSecureIdentityStore

/** Development-only process-local storage; production hosts must replace it. */
internal class DevelopmentOnlyInMemorySecureIdentityStore : JvmSecureIdentityStore {
    private val values = mutableMapOf<String, ByteArray>()

    override fun read(namespace: String): ByteArray? =
        synchronized(values) { values[namespace]?.copyOf() }

    override fun putIfAbsent(namespace: String, value: ByteArray): ByteArray =
        synchronized(values) { values.getOrPut(namespace) { value.copyOf() }.copyOf() }

    override fun delete(namespace: String): Boolean =
        synchronized(values) { values.remove(namespace) != null }
}
