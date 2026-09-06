package dev.p2pkit.sample.diagnostics

import java.io.File
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.StandardCopyOption

/** Only reached after [replaceDiagnosticFile] checks that NIO file APIs exist. */
internal object DiagnosticNioFileReplacement {
    fun replace(
        source: File,
        target: File,
        requireAtomic: Boolean,
        move: (Boolean) -> Unit = { atomic ->
            val options = if (atomic) {
                arrayOf(StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING)
            } else {
                arrayOf(StandardCopyOption.REPLACE_EXISTING)
            }
            Files.move(source.toPath(), target.toPath(), *options)
        }
    ) {
        try {
            move(true)
        } catch (failure: AtomicMoveNotSupportedException) {
            // Selective history clearing must never risk the only copy of other sessions.
            if (requireAtomic) throw failure
            // Preserve the existing JVM/API26+ exporter policy; diagnostic ZIPs
            // do not promise atomic publication on every provider or crash durability.
            move(false)
        }
    }
}
