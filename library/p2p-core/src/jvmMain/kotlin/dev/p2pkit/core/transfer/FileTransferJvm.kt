package dev.p2pkit.core.transfer

import dev.p2pkit.core.P2pSession
import dev.p2pkit.core.internal.P2pSessionImpl
import kotlinx.io.asSource
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.io.RawSource
import java.io.File
import java.io.FileInputStream

/**
 * Send a file from the local filesystem to the peer.
 *
 * Secure SDK sessions hash one opened file on [Dispatchers.IO], retain no
 * stream while the offer is pending, and reopen [file] only after acceptance.
 * Before sending any payload, the reopened descriptor's size and SHA-256 are
 * verified against preparation, then that same descriptor is rewound. A path
 * substitution or edit already present at reopen fails as `SOURCE_CHANGED`
 * without transmitting the substituted content. This adds a full read before
 * transmission, within the configured `offerTimeoutMillis` source-open budget.
 * Verification reads at most the prepared length plus one byte, even if the
 * source grows. Slow or large-file reads may require a higher timeout.
 *
 * This is not an immutable filesystem snapshot: in-place writes after that
 * verification can still be transmitted before the streaming rehash detects
 * them and prevents commit. Keep the source immutable for the whole transfer
 * when disclosure of concurrently edited content is unacceptable. Explicit
 * legacy or third-party sessions retain the deprecated one-shot behavior.
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
    val prepared = withContext(Dispatchers.IO) { prepareJvmFileSource(file) }
    return sendFile(name = file.name, mimeType = null, source = prepared)
}

/** No descriptor is retained while an offer is pending; every open validates its own handle. */
internal fun prepareJvmFileSource(
    file: File,
    openStream: () -> FileInputStream = { file.inputStream() }
): PreparedFileSource {
    val hash = openStream().asSource().use { hashPreparedSource(it) }
    return object : PreparedFileSource {
        override val sizeBytes: Long = hash.sizeBytes
        override val sha256: Sha256Digest = hash.digest

        override fun open(): RawSource {
            val stream = openStream()
            val source = stream.asSource()
            try {
                // A path stat followed by open has its own race; compare bytes from the actual
                // opened descriptor instead. This also works when a filesystem has no fileKey.
                if (hashPreparedSource(source, expectedSizeBytes = hash.sizeBytes) != hash) {
                    throw PreparedSourceChangedException("Prepared file changed before transmission")
                }
                stream.channel.position(0)
                return source
            } catch (failure: Throwable) {
                try {
                    source.close()
                } catch (closeFailure: Throwable) {
                    failure.addSuppressed(closeFailure)
                }
                throw failure
            }
        }
    }
}
