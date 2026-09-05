package dev.p2pkit.core.testfixtures

import dev.p2pkit.core.security.PlatformSecurityCryptography
import dev.p2pkit.core.security.platformSecurityCryptography
import kotlin.concurrent.atomics.AtomicReference
import kotlin.concurrent.atomics.ExperimentalAtomicApi

/**
 * Decorates the real provider, retaining references to synthetic transport cipher arrays ONLY.
 * Noise handshake AEAD uses a transcript hash as associated data; transport records use empty AD.
 * No keys, nonces, payloads or fingerprints are logged, serialized or returned by this observer.
 * These observations prove library array cleanup, not provider-internal erasure or crypto assurance.
 */
@OptIn(ExperimentalAtomicApi::class)
internal class TrackingSecurityCryptography(
    private val delegate: PlatformSecurityCryptography = platformSecurityCryptography()
) : PlatformSecurityCryptography by delegate {
    private val keys = AtomicReference<List<TrackedTransportKey>>(emptyList())

    fun transportKeys(): List<TrackedTransportKey> = keys.load()

    override fun chacha20Poly1305Encrypt(
        key: ByteArray,
        nonce: ByteArray,
        associatedData: ByteArray,
        plaintext: ByteArray
    ): ByteArray {
        observe(key, associatedData)
        return delegate.chacha20Poly1305Encrypt(key, nonce, associatedData, plaintext)
    }

    override fun chacha20Poly1305Decrypt(
        key: ByteArray,
        nonce: ByteArray,
        associatedData: ByteArray,
        ciphertext: ByteArray
    ): ByteArray {
        observe(key, associatedData)
        return delegate.chacha20Poly1305Decrypt(key, nonce, associatedData, ciphertext)
    }

    private fun observe(key: ByteArray, associatedData: ByteArray) {
        if (associatedData.isNotEmpty()) return
        while (true) {
            val current = keys.load()
            if (current.any { it.isSameArray(key) }) return
            if (keys.compareAndSet(current, current + TrackedTransportKey(key))) return
        }
    }
}

/** Reads the original array rather than a copy, so omitting an actual wipe makes the test fail. */
internal class TrackedTransportKey(private val bytes: ByteArray) {
    val wasLiveWhenObserved: Boolean = bytes.size == 32 && bytes.any { it != 0.toByte() }
    fun isSameArray(other: ByteArray): Boolean = bytes === other
    fun isCleared(): Boolean = bytes.all { it == 0.toByte() }
}
