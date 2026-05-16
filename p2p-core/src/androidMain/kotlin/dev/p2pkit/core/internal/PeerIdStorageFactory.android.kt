package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.android.androidApplicationContextOrNull

internal actual fun defaultPeerIdStorage(appId: AppId, logger: P2pLogger): PeerIdStorage {
    val ctx = androidApplicationContextOrNull()
    if (ctx == null) {
        logger.warn(
            "PeerId persistence: P2pKitAndroid.initialize(context) was not called. " +
                "Falling back to in-memory storage; the PeerId will regenerate on every " +
                "process restart. Call P2pKitAndroid.initialize(applicationContext) from " +
                "Application.onCreate() to enable persistence."
        )
        return InMemoryPeerIdStorage()
    }
    return FilePeerIdStorage(rootDir = ctx.filesDir, rawAppId = appId.value, logger = logger)
}
