package dev.p2pkit.core.transfer

import dev.p2pkit.core.internal.security.Sha256Hasher
import kotlinx.io.Buffer
import kotlinx.io.RawSource
import kotlinx.io.readByteArray

internal data class PreparedSourceHash(val sizeBytes: Long, val digest: Sha256Digest)

/** When revalidating, read at most the prepared length plus one byte, even if the source grows. */
internal fun hashPreparedSource(source: RawSource, expectedSizeBytes: Long? = null): PreparedSourceHash {
    require(expectedSizeBytes == null || expectedSizeBytes >= 0L)
    val hasher = Sha256Hasher()
    val buffer = Buffer()
    var total = 0L
    while (true) {
        val request = expectedSizeBytes?.let { (it - total).coerceIn(1L, HASH_CHUNK_BYTES.toLong()) }
            ?: HASH_CHUNK_BYTES.toLong()
        val read = source.readAtMostTo(buffer, request)
        if (read == -1L) break
        check(read > 0L) {
            "Prepared source returned 0 bytes for a positive read request"
        }
        if (expectedSizeBytes != null && read > expectedSizeBytes - total) {
            throw PreparedSourceChangedException("Prepared file grew before transmission")
        }
        val bytes = buffer.readByteArray(read.toInt())
        hasher.update(bytes)
        total += read
    }
    if (expectedSizeBytes != null && total != expectedSizeBytes) {
        throw PreparedSourceChangedException("Prepared file shrank before transmission")
    }
    return PreparedSourceHash(total, hasher.finish())
}

private const val HASH_CHUNK_BYTES: Int = 64 * 1024

/** Internal marker for a detected prepared-source size or content change, including during open. */
internal open class PreparedSourceChangedException(
    message: String,
    cause: Throwable? = null
) : Exception(message, cause)
