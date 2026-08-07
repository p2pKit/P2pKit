package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pLogger

@Suppress("UNUSED_PARAMETER")
internal actual fun defaultSecureIdentityStorage(
    appId: AppId,
    logger: P2pLogger
): SecureIdentityStorage = IosSecureIdentityStorage()
