package dev.p2pkit.core.security

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.internal.defaultSecureIdentityStorage

/**
 * Permanently deletes this Android installation's secure-v2 identity for
 * [appId]. The next secure kit construction creates a different PeerId and
 * fingerprint, so every remote peer must be re-pinned.
 *
 * This operation fails while a kit in this process owns the identity. The
 * application must also ensure that no other process is constructing or using
 * the same AppId while reset runs.
 *
 * An interrupted reset remains fail-closed and can be completed only by
 * calling this function again.
 */
@Throws(Exception::class)
public fun resetAndroidSecureIdentity(appId: AppId) {
    SecureIdentityService(
        cryptography = platformSecurityCryptography(),
        storage = defaultSecureIdentityStorage(appId, P2pLogger.NoOp)
    ).reset(appId)
}
