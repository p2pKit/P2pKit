package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.PeerId
import java.io.File
import kotlin.uuid.ExperimentalUuidApi
import kotlin.uuid.Uuid

/**
 * Android copy of the JVM [FilePeerIdStorage]. Same `java.io.File` semantics;
 * duplicated because :p2p-core does not ship a `jvmAndroidMain` intermediate
 * source set in v0.2. If/when one is added, the two copies converge.
 */
internal class FilePeerIdStorage(
    rootDir: File,
    rawAppId: String,
    private val logger: P2pLogger
) : PeerIdStorage {

    private val storageDir: File = File(File(rootDir, "p2pkit"), sanitizeAppIdForFilesystem(rawAppId))
    private val storageFile: File = File(storageDir, "peer-id")

    internal val storagePath: String get() = storageFile.absolutePath

    override fun loadOrGenerate(): PeerId {
        readExistingOrNull()?.let { return it }
        return generateAndPersist()
    }

    private fun readExistingOrNull(): PeerId? {
        if (!storageFile.exists()) return null
        return try {
            val content = storageFile.readText().trim()
            if (content.isBlank()) null else PeerId(content)
        } catch (e: Throwable) {
            logger.warn(
                "Failed to read persistent PeerId from ${storageFile.absolutePath}; will regenerate",
                e
            )
            null
        }
    }

    @OptIn(ExperimentalUuidApi::class)
    private fun generateAndPersist(): PeerId {
        val fresh = PeerId(Uuid.random().toString())
        try {
            storageDir.mkdirs()
            val tmp = File(storageDir, "peer-id.tmp")
            tmp.writeText(fresh.value)
            if (!tmp.renameTo(storageFile)) {
                storageFile.writeText(fresh.value)
                tmp.delete()
            }
        } catch (e: Throwable) {
            logger.warn(
                "Failed to persist PeerId to ${storageFile.absolutePath}; PeerId will not survive restart",
                e
            )
        }
        return fresh
    }
}

internal fun sanitizeAppIdForFilesystem(raw: String): String {
    if (raw.isBlank()) return "_"
    val sb = StringBuilder(raw.length)
    for (c in raw) {
        sb.append(if (c.isLetterOrDigit() || c == '_' || c == '-' || c == '.') c else '_')
    }
    val noTraversal = sb.toString().replace("..", "._")
    val trimmed = noTraversal.trimStart('.').ifEmpty { "_" }
    return trimmed.take(64)
}
