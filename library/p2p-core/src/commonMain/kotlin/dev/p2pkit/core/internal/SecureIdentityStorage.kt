package dev.p2pkit.core.internal

import dev.p2pkit.core.security.EncodedIdentityKeyPair
import dev.p2pkit.core.security.IdentityNamespace

/** Durable, atomic storage boundary for one platform's secure local identity. */
internal interface SecureIdentityStorage {
    /**
     * Reserve this namespace for one constructing/live kit.
     *
     * Platform adapters that expose destructive reset use the reservation to
     * serialize reset against construction. The caller must release it after
     * terminal kit teardown and on every construction rollback.
     */
    fun acquireUsage(namespace: IdentityNamespace): SecureIdentityUsage =
        SecureIdentityUsage { }

    fun loadOrCreate(
        namespace: IdentityNamespace,
        fingerprintDigest: (EncodedIdentityKeyPair) -> ByteArray,
        generate: () -> EncodedIdentityKeyPair
    ): EncodedIdentityKeyPair

    /** Explicit destructive maintenance operation; never called by normal construction. */
    fun reset(namespace: IdentityNamespace)
}

/** Idempotent ownership token returned by [SecureIdentityStorage.acquireUsage]. */
internal fun interface SecureIdentityUsage {
    fun release()
}
