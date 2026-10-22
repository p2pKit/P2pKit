package dev.p2pkit.sample.android

import android.system.ErrnoException
import android.system.Os
import android.system.OsConstants
import dev.p2pkit.sample.diagnostics.cleanupStaleTransferPartsOnce
import java.io.File

/** Explicit API21+ syscalls: the shared JVM NIO adapter is not an API24 dependency. */
internal fun isPlainAndroidStagingPath(file: File): Boolean {
    val prefixes = generateSequence(file.absoluteFile) { it.parentFile }.toList().asReversed()
    return try {
        // Keep raw components until inspected, including a link before `..`.
        for ((index, prefix) in prefixes.withIndex()) {
            val mode = Os.lstat(prefix.path).st_mode
            val directory = OsConstants.S_ISDIR(mode)
            if (OsConstants.S_ISLNK(mode)) return false
            if (index < prefixes.lastIndex && !directory) return false
            if (!directory && !OsConstants.S_ISREG(mode)) return false
        }
        true
    } catch (_: ErrnoException) {
        // Missing/inaccessible/unsupported entries confer no cleanup authority.
        false
    } catch (_: SecurityException) {
        false
    }
}

internal fun cleanupAndroidStaleTransferPartsOnce(directory: File): Unit =
    cleanupStaleTransferPartsOnce(directory, ::isPlainAndroidStagingPath)
