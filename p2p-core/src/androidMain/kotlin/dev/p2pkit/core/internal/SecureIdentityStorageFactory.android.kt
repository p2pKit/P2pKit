package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.LocalIdentityFailureKind
import dev.p2pkit.core.LocalIdentityRecovery
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.android.androidApplicationContextOrNull
import dev.p2pkit.core.security.localIdentityError

@Suppress("UNUSED_PARAMETER")
internal actual fun defaultSecureIdentityStorage(
    appId: AppId,
    logger: P2pLogger
): SecureIdentityStorage {
    val context = androidApplicationContextOrNull() ?: throw localIdentityError(
        kind = LocalIdentityFailureKind.STORE_NOT_CONFIGURED,
        recovery = LocalIdentityRecovery.CONFIGURE_STORE,
        reason = "P2pKitAndroid.initialize(applicationContext) is required for secure identity storage"
    )
    return AndroidSecureIdentityStorage(context)
}
