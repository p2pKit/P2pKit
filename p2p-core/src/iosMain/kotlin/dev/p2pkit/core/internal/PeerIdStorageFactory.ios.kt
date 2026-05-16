package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pLogger

internal actual fun defaultPeerIdStorage(appId: AppId, logger: P2pLogger): PeerIdStorage =
    NSUserDefaultsPeerIdStorage(appId = appId, logger = logger)
