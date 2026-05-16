package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.PeerId
import java.io.File
import kotlin.uuid.ExperimentalUuidApi
import kotlin.uuid.Uuid

/**
 * [PeerIdStorage] backed by a single file under
 * `<rootDir>/p2pkit/<sanitizedAppId>/peer-id`.
 *
 * Writes are atomic via a temp file + rename to avoid corruption mid-write.
 * If the file ever exists but is empty or unparseable, it's overwritten on
 * the next [loadOrGenerate].
 *
 * @param rootDir Filesystem directory P2pKit can write under (e.g.,
 *   `~/.p2pkit` on JVM, `Context.filesDir` on Android).
 * @param rawAppId The user's [dev.p2pkit.core.AppId] string. Sanitised
 *   internally to a safe filename segment via [sanitizeAppIdForFilesystem].
 * @param logger Used only for warn-logging I/O failures; never throws.
 */
internal class FilePeerIdStorage(
    rootDir: File,
    rawAppId: String,
    private val logger: P2pLogger
) : PeerIdStorage {

    private val storageDir: File = File(File(rootDir, "p2pkit"), sanitizeAppIdForFilesystem(rawAppId))
    private val storageFile: File = File(storageDir, "peer-id")

    /** Absolute path of the underlying file. Exposed for tests only. */
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
            // Atomic write: temp file then rename.
            val tmp = File(storageDir, "peer-id.tmp")
            tmp.writeText(fresh.value)
            if (!tmp.renameTo(storageFile)) {
                // renameTo can fail on some platforms when target exists.
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

/**
 * Reduce a raw appId to a path-safe directory-name segment.
 *
 * - Keeps `[A-Za-z0-9._-]`; replaces anything else with `_`.
 * - Collapses any `..` sequence to `._` so the result cannot navigate up.
 * - Trims leading dots so we don't create hidden directories.
 * - Caps the result at 64 chars.
 */
internal fun sanitizeAppIdForFilesystem(raw: String): String {
    if (raw.isBlank()) return "_"
    val sb = StringBuilder(raw.length)
    for (c in raw) {
        sb.append(if (c.isLetterOrDigit() || c == '_' || c == '-' || c == '.') c else '_')
    }
    // Replace every `..` with `._` (replace-all is non-overlapping, single
    // pass is sufficient to eliminate every traversal pair).
    val noTraversal = sb.toString().replace("..", "._")
    val trimmed = noTraversal.trimStart('.').ifEmpty { "_" }
    return trimmed.take(64)
}
