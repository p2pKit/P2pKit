package dev.p2pkit.core.transfer

import dev.p2pkit.core.P2pSession
import kotlinx.io.asSource
import java.io.File

/**
 * Send a file from the local filesystem to the peer.
 *
 * Convenience wrapper over [P2pSession.sendFile] that opens [file] for
 * reading, wraps the `InputStream` as a `kotlinx.io.RawSource`, and forwards
 * to the core API. The underlying stream is closed automatically when the
 * returned [P2pFileTransfer] reaches any terminal state (Completed, Rejected,
 * Cancelled, Failed) — the caller does not need to manage it.
 *
 * The transfer's [P2pFileTransfer.name] is `file.name`, and `sizeBytes` is
 * measured from the opened file descriptor. This avoids a path-stat/open race;
 * mutation after the descriptor is opened is outside the snapshot contract and
 * causes the transfer to fail if the promised byte count can no longer be read.
 *
 * @throws IllegalArgumentException if [file] does not exist or is not a regular file
 */
public suspend fun P2pSession.sendFile(file: File): P2pFileTransfer {
    require(file.exists()) { "File does not exist: ${file.absolutePath}" }
    require(file.isFile) { "Not a regular file: ${file.absolutePath}" }
    val stream = file.inputStream()
    val source = stream.asSource()
    return try {
        val openedSize = stream.channel.size()
        require(openedSize >= 0L) { "Cannot determine opened file size: ${file.absolutePath}" }
        sendFile(
            name = file.name,
            sizeBytes = openedSize,
            mimeType = null,
            source = source
        )
    } catch (e: Throwable) {
        runCatching { source.close() }
        throw e
    }
}
