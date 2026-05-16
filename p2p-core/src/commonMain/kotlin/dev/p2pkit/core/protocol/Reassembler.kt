package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pMessage

/**
 * Collects [Frame]s for the same [MessageId] until all chunks have arrived,
 * then yields a complete [P2pMessage].
 *
 * Only DATA frames are reassembled; control frames (HELLO, ACK, PING, ...)
 * cause [accept] to return `null` and the caller is expected to route them
 * separately.
 *
 * Partial messages whose first chunk is older than [reassemblyTimeoutMillis]
 * are dropped by [evictStale] — this prevents memory leaks if a peer hangs up
 * mid-transfer.
 */
internal class Reassembler(
    private val clock: () -> Long,
    private val reassemblyTimeoutMillis: Long = ProtocolConstants.DEFAULT_REASSEMBLY_TIMEOUT_MS
) {

    private data class Pending(
        val totalChunks: Int,
        val isText: Boolean,
        val chunks: MutableMap<Int, ByteArray>,
        val firstSeenMillis: Long
    )

    private val pending: MutableMap<MessageId, Pending> = mutableMapOf()

    /**
     * Feed one DATA frame. Returns the completed [P2pMessage] when its final
     * chunk arrives, otherwise `null`. Non-DATA frames always return `null`.
     */
    fun accept(frame: Frame): P2pMessage? {
        if (frame.type != PacketType.DATA) return null

        // Single-frame fast path — no state to keep.
        if (frame.totalChunks == 1) {
            return decodePayload(frame.payload, frame.isText)
        }

        val state = pending.getOrPut(frame.messageId) {
            Pending(
                totalChunks = frame.totalChunks,
                isText = frame.isText,
                chunks = mutableMapOf(),
                firstSeenMillis = clock()
            )
        }
        if (state.totalChunks != frame.totalChunks) {
            pending.remove(frame.messageId)
            throw P2pError.ProtocolError(
                "Mismatched totalChunks for messageId=${frame.messageId}: " +
                    "first saw ${state.totalChunks}, now $frame.totalChunks"
            )
        }
        state.chunks[frame.chunkIndex] = frame.payload

        if (state.chunks.size != state.totalChunks) return null

        val totalSize = state.chunks.values.sumOf { it.size }
        val combined = ByteArray(totalSize)
        var offset = 0
        for (i in 0 until state.totalChunks) {
            val piece = state.chunks[i]
                ?: throw P2pError.ProtocolError("Missing chunk $i for messageId=${frame.messageId}")
            piece.copyInto(combined, offset)
            offset += piece.size
        }
        pending.remove(frame.messageId)
        return decodePayload(combined, state.isText)
    }

    /** Drop partial messages whose first chunk is older than the timeout. */
    fun evictStale() {
        if (pending.isEmpty()) return
        val now = clock()
        val expired = pending.entries
            .filter { now - it.value.firstSeenMillis > reassemblyTimeoutMillis }
            .map { it.key }
        for (id in expired) pending.remove(id)
    }

    internal fun pendingCount(): Int = pending.size

    private fun decodePayload(bytes: ByteArray, isText: Boolean): P2pMessage =
        if (isText) P2pMessage.Text(bytes.decodeToString())
        else P2pMessage.Binary(bytes)
}
