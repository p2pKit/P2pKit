package dev.p2pkit.sample.diagnostics

import java.io.File
import java.io.IOException

private val diagnosticNioAvailable: Boolean = try {
    Class.forName("java.nio.file.Files")
    true
} catch (_: ClassNotFoundException) {
    false
}

/** Same-directory replacement; never remove the original before attempting the replacement. */
internal fun replaceDiagnosticFile(source: File, target: File) {
    replaceDiagnosticFile(source, target, requireAtomic = false)
}

internal fun replaceDiagnosticFile(source: File, target: File, requireAtomic: Boolean) {
    require(source.parentFile?.canonicalPath == target.parentFile?.canonicalPath) {
        "Diagnostic replacement requires sibling files"
    }
    if (diagnosticNioAvailable) {
        // Keep API26 types in a separate class, never loaded on Android 24/25.
        DiagnosticNioFileReplacement.replace(source, target, requireAtomic)
    } else {
        // Android java.io.File uses POSIX rename, including replacement. Siblings
        // stay on the same filesystem; failure preserves the original. No copy/delete.
        if (!source.renameTo(target)) throw IOException("Could not replace diagnostic evidence")
    }
}
