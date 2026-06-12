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
 * are dropped by [evictStale]. Eviction is read-driven: the protocol layer
 * invokes [evictStale] only when further inbound frames arrive (there is no
 * timer), so it bounds memory while a peer keeps talking. Partials from a
 * peer that goes fully silent are reclaimed when the session itself is torn
 * down by the keep-alive timeout, not after [reassemblyTimeoutMillis].
 */
internal class Reassembler(
    private val clock: () -> Long,
    private val reassemblyTimeoutMillis: Long = ProtocolConstants.DEFAULT_REASSEMBLY_TIMEOUT_MS
) {

    private data class Pending(
        val totalChunks: Int,
        val isText: Boolean,
        val chunks: MutableMap<Int, ByteArray>,
        val firstSeenMillis: Long,
        var bufferedBytes: Long = 0
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

        // Untrusted-input guards (frame.totalChunks is peer-controlled):
        //   - cap totalChunks so the per-message chunk map can't be opened huge,
        //   - cap the number of concurrently-pending partial messages,
        // both close the session via ProtocolError. See ProtocolConstants.
        if (frame.totalChunks > ProtocolConstants.MAX_TOTAL_CHUNKS) {
            throw P2pError.ProtocolError(
                "totalChunks ${frame.totalChunks} exceeds maximum ${ProtocolConstants.MAX_TOTAL_CHUNKS}"
            )
        }
        if (frame.messageId !in pending &&
            pending.size >= ProtocolConstants.MAX_PENDING_REASSEMBLIES
        ) {
            throw P2pError.ProtocolError(
                "Too many concurrent partial messages (${pending.size}); " +
                    "max ${ProtocolConstants.MAX_PENDING_REASSEMBLIES}"
            )
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
                    "first saw ${state.totalChunks}, now ${frame.totalChunks}"
            )
        }
        // Track running buffered size (Long) and reject before a reassembled
        // message could exceed MAX_PAYLOAD_BYTES. Only count newly-seen indices
        // so a duplicate chunk can't inflate the total. Guards against both the
        // Int-overflow of summing sizes and an oversized aggregate allocation.
        if (frame.chunkIndex !in state.chunks) {
            state.bufferedBytes += frame.payload.size.toLong()
            if (state.bufferedBytes > ProtocolConstants.MAX_PAYLOAD_BYTES) {
                pending.remove(frame.messageId)
                throw P2pError.ProtocolError(
                    "Reassembled message for messageId=${frame.messageId} would exceed " +
                        "MAX_PAYLOAD_BYTES (${ProtocolConstants.MAX_PAYLOAD_BYTES})"
                )
            }
        }
        state.chunks[frame.chunkIndex] = frame.payload

        if (state.chunks.size != state.totalChunks) return null

        val totalSize = state.chunks.values.sumOf { it.size.toLong() }.toInt()
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
