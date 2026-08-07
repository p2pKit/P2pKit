package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pLogger

/** Select the platform default secure identity storage, or fail closed. */
internal expect fun defaultSecureIdentityStorage(
    appId: AppId,
    logger: P2pLogger
): SecureIdentityStorage
