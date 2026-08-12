package dev.p2pkit.core.security

import dev.p2pkit.core.AppId
import dev.p2pkit.core.internal.JvmSecureIdentityStoreAdapter

/**
 * Permanently reset this AppId's JVM secure-v2 local identity.
 *
 * The next secure construction creates a different PeerId and fingerprint;
 * every remote peer must explicitly re-pin this device. Configured remote
 * pins are not deleted. Reset fails with
 * [dev.p2pkit.core.P2pError.LocalIdentityUnavailable] and
 * `LIVE_IDENTITY_IN_USE` while a kit using the same [store] instance is known
 * live in this process.
 *
 * The host must additionally guarantee that no other process using the same
 * backing store is constructing or using this AppId. Core cannot infer that
 * cross-process lifecycle from the synchronous store SPI. This function is
 * synchronous and may block on the host store; invoke it away from a UI/event
 * thread when that store performs blocking I/O.
 *
 * @throws dev.p2pkit.core.P2pError.LocalIdentityUnavailable when reset cannot
 *   safely complete. Follow the error's `recovery` value.
 */
public fun resetJvmSecureIdentity(
    appId: AppId,
    store: JvmSecureIdentityStore
) {
    SecureIdentityService(
        cryptography = platformSecurityCryptography(),
        storage = JvmSecureIdentityStoreAdapter(store)
    ).reset(appId)
}
