package dev.p2pkit.core.transfer

import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.internal.P2pSessionImpl
import kotlinx.io.asSource
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.io.RawSource
import java.io.File

/**
 * Send a file from the local filesystem to the peer.
 *
 * Secure SDK sessions hash one opened snapshot on [Dispatchers.IO], retain no
 * stream while the offer is pending, and reopen [file] only after acceptance.
 * The streamed bytes are hashed again, so mutation between preparation and
 * transfer fails as `SOURCE_CHANGED`. Explicit legacy or third-party session
 * implementations retain the deprecated one-shot `RawSource` behavior.
 *
 * The transfer's [P2pFileTransfer.name] is `file.name`; the prepared size is
 * measured while hashing rather than trusted from an earlier path stat.
 *
 * @throws IllegalArgumentException if [file] does not exist or is not a regular file
 */
@Suppress("DEPRECATION")
public suspend fun P2pSession.sendFile(file: File): P2pFileTransfer {
    require(file.exists()) { "File does not exist: ${file.absolutePath}" }
    require(file.isFile) { "Not a regular file: ${file.absolutePath}" }
    if (this !is P2pSessionImpl || !usesAuthenticatedFileTransfer) {
        val stream = file.inputStream()
        val source = stream.asSource()
        return try {
            sendFile(file.name, stream.channel.size(), null, source)
        } catch (e: Throwable) {
            runCatching { source.close() }
            throw e
        }
    }
    val prepared = withContext(Dispatchers.IO) {
        val source = file.inputStream().asSource()
        val hash = try {
            hashPreparedSource(source)
        } finally {
            source.close()
        }
        object : PreparedFileSource {
            override val sizeBytes: Long = hash.sizeBytes
            override val sha256: Sha256Digest = hash.digest
            override fun open(): RawSource = file.inputStream().asSource()
        }
    }
    return sendFile(name = file.name, mimeType = null, source = prepared)
}
