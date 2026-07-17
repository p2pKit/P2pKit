package dev.p2pkit.core.dsl

import dev.p2pkit.core.internal.JvmSecureIdentityStoreAdapter
import dev.p2pkit.core.security.JvmSecureIdentityStore

/**
 * Supply the JVM host's protected, durable storage for secure-v2 identity.
 *
 * Core intentionally has no passwordless/plain-file default. The same [store]
 * instance must be retained for explicit identity reset so live-kit exclusion
 * can be enforced in this process.
 */
public fun P2pKitBuilder.jvmSecureIdentityStore(store: JvmSecureIdentityStore) {
    secureIdentityStorage = JvmSecureIdentityStoreAdapter(store)
}
