package dev.p2pkit.provisioning.desktop

import dev.p2pkit.core.security.JvmSecureIdentityStore

/** Process-local test double; never use this as durable production storage. */
internal class InMemoryTestJvmSecureIdentityStore : JvmSecureIdentityStore {
    private val values = mutableMapOf<String, ByteArray>()

    override fun read(namespace: String): ByteArray? =
        synchronized(values) { values[namespace]?.copyOf() }

    override fun putIfAbsent(namespace: String, value: ByteArray): ByteArray =
        synchronized(values) {
            values.getOrPut(namespace) { value.copyOf() }.copyOf()
        }

    override fun delete(namespace: String): Boolean =
        synchronized(values) { values.remove(namespace) != null }
}
