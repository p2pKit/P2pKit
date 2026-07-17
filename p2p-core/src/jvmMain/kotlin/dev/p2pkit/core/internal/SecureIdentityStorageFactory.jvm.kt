package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.LocalIdentityFailureKind
import dev.p2pkit.core.LocalIdentityRecovery
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.security.localIdentityError

internal actual fun defaultSecureIdentityStorage(
    appId: AppId,
    logger: P2pLogger
): SecureIdentityStorage {
    // There is no portable JVM secret-protection facility or password source.
    // A plaintext file must never be presented as secure identity storage.
    throw localIdentityError(
        kind = LocalIdentityFailureKind.STORE_NOT_CONFIGURED,
        recovery = LocalIdentityRecovery.CONFIGURE_STORE,
        reason = "secure mode on JVM requires an explicit JvmSecureIdentityStore for ${appId.value}"
    )
}
