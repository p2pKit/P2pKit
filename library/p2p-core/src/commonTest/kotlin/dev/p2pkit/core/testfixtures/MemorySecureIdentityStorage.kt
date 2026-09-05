package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.internal.SecureIdentityStorage
import dev.p2pkit.core.security.EncodedIdentityKeyPair
import dev.p2pkit.core.security.IdentityNamespace
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

/**
 * Synthetic, process-only identity storage. Serializes the synchronous storage transaction and
 * returns owned key copies. Never models Keystore, Keychain, durable storage or backup protection.
 * [clear] is explicit test teardown; do not call it while a kit is using this store.
 */
internal class MemorySecureIdentityStorage : SecureIdentityStorage {
    private val mutex = Mutex()
    private val records = mutableMapOf<String, EncodedIdentityKeyPair>()

    override fun loadOrCreate(
        namespace: IdentityNamespace,
        fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray,
        generate: () -> EncodedIdentityKeyPair
    ): EncodedIdentityKeyPair = runBlocking {
        mutex.withLock {
            val existing = records[namespace.storageKey]
            if (existing != null) {
                val result = copy(existing)
                try {
                    validateFingerprintCallback(result, fingerprintDigest)
                    result
                } catch (failure: Throwable) {
                    result.clearPrivate()
                    throw failure
                }
            } else {
                val generated = generate()
                try {
                    validateFingerprintCallback(generated, fingerprintDigest)
                    val durable = copy(generated)
                    val result = try {
                        copy(durable)
                    } catch (failure: Throwable) {
                        durable.clearPrivate()
                        throw failure
                    }
                    records[namespace.storageKey] = durable
                    result
                } finally {
                    generated.clearPrivate()
                }
            }
        }
    }

    override fun reset(namespace: IdentityNamespace): Unit = runBlocking {
        mutex.withLock { records.remove(namespace.storageKey)?.clearPrivate() }
    }

    fun clear(): Unit = runBlocking {
        mutex.withLock {
            records.values.forEach { it.clearPrivate() }
            records.clear()
        }
    }

    private fun validateFingerprintCallback(
        pair: EncodedIdentityKeyPair,
        callback: (EncodedIdentityKeyPair) -> ByteArray
    ) {
        val digest = callback(pair)
        try {
            require(digest.size == 32)
        } finally {
            digest.fill(0)
        }
    }

    private fun copy(pair: EncodedIdentityKeyPair): EncodedIdentityKeyPair {
        val privateKey = pair.privateKeyBytes()
        val publicKey = pair.publicKeyBytes()
        return try {
            EncodedIdentityKeyPair(privateKey, publicKey)
        } finally {
            privateKey.fill(0)
            publicKey.fill(0)
        }
    }
}
