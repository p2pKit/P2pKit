package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pLogger
import java.io.File

internal actual fun defaultPeerIdStorage(appId: AppId, logger: P2pLogger): PeerIdStorage {
    return FilePeerIdStorage(
        rootDir = resolveJvmPeerIdRoot(logger),
        rawAppId = appId.value,
        logger = logger
    )
}

internal fun resolveJvmPeerIdRoot(logger: P2pLogger): File {
    usableDirectoryProperty("user.home")?.let { return it }
    logger.warn("user.home is blank, missing, or not a writable directory; trying java.io.tmpdir")

    val temporaryRoot = usableDirectoryProperty("java.io.tmpdir")
        ?: throw IllegalStateException(
            "Persistent PeerId storage requires a writable user.home or java.io.tmpdir; " +
                "the working directory is never used implicitly"
        )
    val fallback = File(temporaryRoot, "p2pkit-fallback")
    if (!fallback.isDirectory && !fallback.mkdirs()) {
        throw IllegalStateException(
            "Could not create persistent PeerId fallback directory ${fallback.absolutePath}"
        )
    }
    if (!fallback.isDirectory || !fallback.canWrite()) {
        throw IllegalStateException(
            "Persistent PeerId fallback is not writable: ${fallback.absolutePath}"
        )
    }
    logger.warn("Persistent PeerId storage is using temporary fallback ${fallback.absolutePath}")
    return fallback
}

private fun usableDirectoryProperty(name: String): File? {
    val raw = System.getProperty(name)?.trim().orEmpty()
    if (raw.isEmpty()) return null
    val directory = File(raw)
    return directory.takeIf { it.isDirectory && it.canWrite() }
}
