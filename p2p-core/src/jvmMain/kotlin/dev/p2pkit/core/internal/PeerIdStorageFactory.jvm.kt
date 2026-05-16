package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pLogger
import java.io.File

internal actual fun defaultPeerIdStorage(appId: AppId, logger: P2pLogger): PeerIdStorage {
    val home = System.getProperty("user.home")?.let(::File)
        ?: File(System.getProperty("java.io.tmpdir") ?: ".", "p2pkit-fallback")
    return FilePeerIdStorage(rootDir = home, rawAppId = appId.value, logger = logger)
}
