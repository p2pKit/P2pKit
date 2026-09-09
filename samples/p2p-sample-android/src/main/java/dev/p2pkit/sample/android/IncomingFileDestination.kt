package dev.p2pkit.sample.android

import java.io.File
import java.io.IOException

/** A chosen directory or reserved file, paired with its storage-domain diagnostic label. */
internal data class IncomingFileLocation(val file: File, val storageDomain: String)

/** Preserve external-app storage with a lazy internal fallback; the label follows the actual selection. */
internal fun incomingFileDirectory(
    externalFilesDir: File?,
    peerName: String,
    internalFilesDir: () -> File
): IncomingFileLocation {
    val baseDir = externalFilesDir ?: internalFilesDir()
    val storageDomain = if (externalFilesDir == null) "app-private" else "app-scoped-external"
    return IncomingFileLocation(
        File(baseDir, "p2pkit-incoming/${sanitizeIncomingPathComponent(peerName)}"),
        storageDomain
    )
}

internal fun sanitizeIncomingPathComponent(raw: String): String {
    val cleaned = raw.filterNot { it.isISOControl() }
        .replace(Regex("""[\\/:*?"<>|]"""), "_")
        .trim()
    return cleaned.takeUnless { it.isEmpty() || it == "." || it == ".." } ?: "untitled"
}

/** Atomically reserves a bounded, non-colliding destination for an incoming file. */
internal fun uniqueDestination(
    directory: File,
    rawName: String,
    createNewFile: (File) -> Boolean = { candidate -> candidate.createNewFile() },
): File {
    val safeName = sanitizeIncomingPathComponent(rawName)
    val dot = safeName.lastIndexOf('.')
    val stem = if (dot > 0) safeName.substring(0, dot) else safeName
    val extension = if (dot > 0) safeName.substring(dot) else ""
    for (index in 0..10_000) {
        val candidate = if (index == 0) {
            File(directory, safeName)
        } else {
            File(directory, "$stem ($index)$extension")
        }
        try {
            if (createNewFile(candidate)) return candidate
        } catch (error: IOException) {
            throw IOException("cannot claim destination ${candidate.absolutePath}", error)
        } catch (error: SecurityException) {
            throw IOException("cannot claim destination ${candidate.absolutePath}", error)
        }
    }
    throw IOException("destination namespace exhausted for '$safeName'")
}
