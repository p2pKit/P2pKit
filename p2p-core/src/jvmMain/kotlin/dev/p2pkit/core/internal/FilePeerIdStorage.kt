package dev.p2pkit.core.internal

import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.PeerId
import java.io.File
import kotlin.uuid.ExperimentalUuidApi
import kotlin.uuid.Uuid

/**
 * [PeerIdStorage] backed by a single file under
 * `<rootDir>/.p2pkit/<sanitizedAppId>/peer-id` (hidden directory, matching
 * the documented `<user.home>/.p2pkit/...` path).
 *
 * Writes are atomic via a temp file + rename to avoid corruption mid-write.
 * If the file ever exists but is empty or unparseable, it's overwritten on
 * the next [loadOrGenerate].
 *
 * AUDIT-2026-06: the directory was previously the visible `p2pkit` (no dot),
 * which contradicted the docs. A one-time migration in [readExistingOrNull]
 * adopts an id from the legacy `<rootDir>/p2pkit/...` location so existing
 * desktop installs keep their identity across the rename.
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

    private val storageDir: File = File(File(rootDir, ".p2pkit"), sanitizeAppIdForFilesystem(rawAppId))
    private val storageFile: File = File(storageDir, "peer-id")

    /** Legacy pre-AUDIT-2026-06 location (visible `p2pkit`), read once for migration. */
    private val legacyFile: File =
        File(File(File(rootDir, "p2pkit"), sanitizeAppIdForFilesystem(rawAppId)), "peer-id")

    /** Absolute path of the underlying file. Exposed for tests only. */
    internal val storagePath: String get() = storageFile.absolutePath

    override fun loadOrGenerate(): PeerId {
        readExistingOrNull()?.let { return it }
        migrateLegacyOrNull()?.let { return it }
        return generateAndPersist()
    }

    private fun readExistingOrNull(): PeerId? = readIdFrom(storageFile)

    /**
     * One-time migration from the legacy visible-`p2pkit` directory. If the
     * new hidden path has no id but the old one does, re-persist it under the
     * new path so the device keeps its identity across the AUDIT-2026-06
     * rename. Best-effort: any failure just falls through to a fresh id.
     */
    private fun migrateLegacyOrNull(): PeerId? {
        val legacy = readIdFrom(legacyFile) ?: return null
        logger.warn(
            "Migrating persistent PeerId from legacy ${legacyFile.absolutePath} to ${storageFile.absolutePath}"
        )
        persist(legacy)
        return legacy
    }

    private fun readIdFrom(file: File): PeerId? {
        if (!file.exists()) return null
        return try {
            val content = file.readText().trim()
            if (content.isBlank()) null else PeerId(content)
        } catch (e: Throwable) {
            logger.warn("Failed to read persistent PeerId from ${file.absolutePath}; will regenerate", e)
            null
        }
    }

    @OptIn(ExperimentalUuidApi::class)
    private fun generateAndPersist(): PeerId {
        val fresh = PeerId(Uuid.random().toString())
        persist(fresh)
        return fresh
    }

    private fun persist(id: PeerId) {
        try {
            storageDir.mkdirs()
            // Atomic write: temp file then rename.
            val tmp = File(storageDir, "peer-id.tmp")
            tmp.writeText(id.value)
            if (!tmp.renameTo(storageFile)) {
                // renameTo can fail on some platforms when target exists.
                storageFile.writeText(id.value)
                tmp.delete()
            }
        } catch (e: Throwable) {
            logger.warn(
                "Failed to persist PeerId to ${storageFile.absolutePath}; PeerId will not survive restart",
                e
            )
        }
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
