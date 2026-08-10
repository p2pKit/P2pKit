package dev.p2pkit.core.protocol

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.io.EOFException
import kotlinx.io.RawSource
import kotlinx.io.buffered
import kotlinx.io.readByteArray

/**
 * Streaming `FILE_DATA` frame producer. Pulls bytes from [rawSource] in
 * `chunkSizeBytes` increments and emits one [Frame] per chunk.
 *
 * The caller (typically the session writer) collects this flow and writes each
 * frame to the connection serially through the session's send mutex. Stops
 * after exactly [sizeBytes] bytes have been read. Legacy callers intentionally
 * treat that length as a prefix boundary. Authenticated prepared-source callers
 * set [requireExactSize], which additionally proves that the source ends at the
 * declared boundary and classifies both early EOF and trailing bytes as a
 * prepared-snapshot change.
 *
 * Zero-byte files emit zero frames — the caller sends the protocol-appropriate
 * legacy `FILE_DONE` or authenticated `FILE_FINISH` completion signal.
 *
 * Cancellation: the coroutine collecting this flow can cancel at any time;
 * the source is **not** closed by this function — the caller owns its lifetime.
 */
internal fun streamFileData(
    transferId: MessageId,
    rawSource: RawSource,
    sizeBytes: Long,
    chunkSizeBytes: Int,
    requireExactSize: Boolean = false
): Flow<Frame> = flow {
    require(sizeBytes >= 0) { "sizeBytes must be non-negative, got $sizeBytes" }
    require(chunkSizeBytes > 0) { "chunkSizeBytes must be positive, got $chunkSizeBytes" }
    if (sizeBytes == 0L && !requireExactSize) return@flow

    val source = rawSource.buffered()
    if (sizeBytes == 0L) {
        if (!source.exhausted()) {
            throw PreparedSourceLengthChangedException(
                "Prepared source contains bytes beyond its declared empty snapshot"
            )
        }
        return@flow
    }
    val totalLong = 1L + (sizeBytes - 1L) / chunkSizeBytes.toLong()
    require(totalLong <= Int.MAX_VALUE.toLong()) {
        "Transfer requires $totalLong chunks; the wire format supports at most ${Int.MAX_VALUE}"
    }
    val total = totalLong.toInt()
    var sent = 0L
    var index = 0
    while (sent < sizeBytes) {
        val want = minOf(chunkSizeBytes.toLong(), sizeBytes - sent).toInt()
        val payload = try {
            source.readByteArray(want)
        } catch (failure: EOFException) {
            if (requireExactSize) {
                throw PreparedSourceLengthChangedException(
                    "Prepared source ended before its declared $sizeBytes-byte snapshot",
                    failure
                )
            }
            throw failure
        }
        val isLast = index == total - 1
        emit(
            Frame(
                type = PacketType.FILE_DATA,
                flags = if (isLast) FrameFlags.LAST_CHUNK.toByte() else 0,
                messageId = transferId,
                chunkIndex = index,
                totalChunks = total,
                payload = payload
            )
        )
        sent += want
        index++
    }
    if (requireExactSize && !source.exhausted()) {
        throw PreparedSourceLengthChangedException(
            "Prepared source contains bytes beyond its declared $sizeBytes-byte snapshot"
        )
    }
}

/** Internal marker used to map a prepared-source length change to `SOURCE_CHANGED`. */
internal class PreparedSourceLengthChangedException(
    message: String,
    cause: Throwable? = null
) : Exception(message, cause)
