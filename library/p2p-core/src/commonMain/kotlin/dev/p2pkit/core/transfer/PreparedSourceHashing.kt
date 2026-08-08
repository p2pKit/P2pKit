package dev.p2pkit.core.transfer

import dev.p2pkit.core.internal.security.Sha256Hasher
import kotlinx.io.Buffer
import kotlinx.io.RawSource
import kotlinx.io.readByteArray

internal data class PreparedSourceHash(val sizeBytes: Long, val digest: Sha256Digest)

internal fun hashPreparedSource(source: RawSource): PreparedSourceHash {
    val hasher = Sha256Hasher()
    val buffer = Buffer()
    var total = 0L
    while (true) {
        val read = source.readAtMostTo(buffer, HASH_CHUNK_BYTES.toLong())
        if (read == -1L) break
        check(read > 0L) {
            "Prepared source returned 0 bytes for a positive read request"
        }
        val bytes = buffer.readByteArray(read.toInt())
        hasher.update(bytes)
        total += read
    }
    return PreparedSourceHash(total, hasher.finish())
}

private const val HASH_CHUNK_BYTES: Int = 64 * 1024
