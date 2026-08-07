package dev.p2pkit.core.protocol

import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.io.RawSource
import kotlinx.io.buffered
import kotlinx.io.readByteArray

/**
 * Streaming `FILE_DATA` frame producer. Pulls bytes from [rawSource] in
 * `chunkSizeBytes` increments and emits one [Frame] per chunk.
 *
 * The caller (typically the session writer) collects this flow and writes each
 * frame to the connection serially through the session's send mutex. Stops
 * after exactly [sizeBytes] bytes have been read; if the source has fewer
 * bytes the kotlinx-io `readByteArray` call throws.
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
    chunkSizeBytes: Int
): Flow<Frame> = flow {
    require(sizeBytes >= 0) { "sizeBytes must be non-negative, got $sizeBytes" }
    require(chunkSizeBytes > 0) { "chunkSizeBytes must be positive, got $chunkSizeBytes" }
    if (sizeBytes == 0L) return@flow

    val source = rawSource.buffered()
    val totalLong = 1L + (sizeBytes - 1L) / chunkSizeBytes.toLong()
    require(totalLong <= Int.MAX_VALUE.toLong()) {
        "Transfer requires $totalLong chunks; the wire format supports at most ${Int.MAX_VALUE}"
    }
    val total = totalLong.toInt()
    var sent = 0L
    var index = 0
    while (sent < sizeBytes) {
        val want = minOf(chunkSizeBytes.toLong(), sizeBytes - sent).toInt()
        val payload = source.readByteArray(want)
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
}
