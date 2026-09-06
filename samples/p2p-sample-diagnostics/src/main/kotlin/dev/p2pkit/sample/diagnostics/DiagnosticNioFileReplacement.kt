package dev.p2pkit.sample.diagnostics

import java.io.File
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.nio.file.StandardCopyOption

/** Only reached after [replaceDiagnosticFile] checks that NIO file APIs exist. */
internal object DiagnosticNioFileReplacement {
    fun replace(source: File, target: File) {
        try {
            Files.move(
                source.toPath(), target.toPath(), StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING
            )
        } catch (_: AtomicMoveNotSupportedException) {
            // Preserve the existing JVM/API26+ exporter policy; diagnostic ZIPs
            // do not promise atomic publication on every provider or crash durability.
            Files.move(source.toPath(), target.toPath(), StandardCopyOption.REPLACE_EXISTING)
        }
    }
}
