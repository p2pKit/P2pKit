package dev.p2pkit.sample.desktop.ui

import java.io.File
import java.io.IOException

/**
 * 2026-07 (SMP-1, P1-32): pick a destination no other transfer is writing to.
 * `createNewFile()` atomically claims the name, so a repeated offer with the
 * same name lands in `"<base> (n)<ext>"` instead of truncating the previous
 * copy, and two concurrent same-named offers can never open two streams onto
 * the same path.
 *
 * The desktop UI, CLI, Android, and Apple samples implement this same
 * platform-neutral contract with their native filesystem APIs: sanitize the
 * name, atomically claim a numbered candidate, and fail after a bounded
 * namespace. `UniqueSaveFileTest` in this module pins the JVM contract; keep
 * the platform copies behaviorally aligned.
 */
internal fun uniqueSaveFile(dir: File, sanitizedName: String): File {
    val safeName = sanitizedName
        .filterNot { it.isISOControl() }
        .replace(Regex("""[\\/:*?"<>|]"""), "_")
        .trim()
        .takeUnless { it.isEmpty() || it == "." || it == ".." }
        ?: "untitled"
    val dot = safeName.lastIndexOf('.')
    val base = if (dot > 0) safeName.substring(0, dot) else safeName
    val ext = if (dot > 0) safeName.substring(dot) else ""
    for (n in 0..10_000) {
        val candidate = if (n == 0) File(dir, safeName) else File(dir, "$base ($n)$ext")
        try {
            if (candidate.createNewFile()) return candidate // atomic claim
        } catch (error: Exception) {
            throw IOException("cannot claim destination ${candidate.absolutePath}", error)
        }
    }
    throw IOException("destination namespace exhausted for '$safeName'")
}
