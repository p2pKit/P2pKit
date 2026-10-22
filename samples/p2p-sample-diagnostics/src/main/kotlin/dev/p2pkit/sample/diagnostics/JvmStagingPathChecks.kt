package dev.p2pkit.sample.diagnostics

import java.io.File
import java.io.IOException
import java.nio.file.Files
import java.nio.file.LinkOption
import java.nio.file.attribute.BasicFileAttributes

/** JVM-only adapter: Android API24 uses its explicit Os.lstat adapter instead. */
internal fun isPlainJvmStagingPath(file: File): Boolean {
    val path = file.toPath().toAbsolutePath()
    var prefix = path.root ?: return false
    return try {
        val root = Files.readAttributes(prefix, BasicFileAttributes::class.java, LinkOption.NOFOLLOW_LINKS)
        if (!root.isDirectory || root.isSymbolicLink || root.isOther) return false
        // Do not normalize or canonicalize away an original `link/..` prefix.
        for ((index, name) in path.withIndex()) {
            prefix = prefix.resolve(name)
            val attrs = Files.readAttributes(prefix, BasicFileAttributes::class.java, LinkOption.NOFOLLOW_LINKS)
            if (attrs.isSymbolicLink || attrs.isOther) return false
            if (index < path.nameCount - 1 && !attrs.isDirectory) return false
            if (!attrs.isDirectory && !attrs.isRegularFile) return false
        }
        true
    } catch (_: IOException) {
        false
    } catch (_: SecurityException) {
        false
    }
}
