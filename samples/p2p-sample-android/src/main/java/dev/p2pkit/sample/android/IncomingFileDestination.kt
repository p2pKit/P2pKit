package dev.p2pkit.sample.android

import java.io.File
import java.io.IOException

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
