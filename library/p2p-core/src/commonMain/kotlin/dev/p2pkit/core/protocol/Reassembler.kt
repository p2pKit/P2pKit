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
 * Partial messages that have received no new chunk for
 * [reassemblyTimeoutMillis] are dropped by [evictStale]. Eviction is by
 * inactivity (time since the last accepted chunk), not by age since the first
 * chunk, so a large message whose chunks keep arriving is never dropped
 * mid-transfer (AUDIT-2026-06 fix). Eviction is read-driven: the protocol
 * layer invokes [evictStale] only when further inbound frames arrive (there
 * is no timer), so it bounds memory while a peer keeps talking. Partials from
 * a peer that goes fully silent are reclaimed when the session itself is torn
 * down by the keep-alive timeout, not after [reassemblyTimeoutMillis].
 */
internal class Reassembler(
    private val clock: () -> Long,
    private val reassemblyTimeoutMillis: Long = ProtocolConstants.DEFAULT_REASSEMBLY_TIMEOUT_MS,
    private val sessionState: ProtocolSessionState? = null
) {

    private data class Pending(
        val totalChunks: Int,
        val isText: Boolean,
        val isEnvelope: Boolean,
        val needsAck: Boolean,
        val chunks: MutableMap<Int, ByteArray>,
        val firstSeenMillis: Long,
        var lastSeenMillis: Long,
        var bufferedBytes: Long = 0
    )

    private val pending: MutableMap<MessageId, Pending> = mutableMapOf()

    /**
     * Running sum of [Pending.bufferedBytes] across all entries in [pending].
     * Kept consistent by routing every removal through [removePending], so it
     * always equals the aggregate buffered size. Bounds total memory via
     * [ProtocolConstants.MAX_TOTAL_PENDING_BYTES] (AUDIT-2026-06 fix).
     */
    private var totalPendingBytes: Long = 0

    /**
     * Feed one DATA frame. Returns the completed [P2pMessage] when its final
     * chunk arrives, otherwise `null`. Non-DATA frames always return `null`.
     */
    fun accept(frame: Frame): P2pMessage? {
        if (frame.type != PacketType.DATA) return null
        FrameValidation.violation(
            type = frame.type,
            flags = frame.flags,
            reserved = 0,
            chunkIndex = frame.chunkIndex,
            totalChunks = frame.totalChunks,
            payloadLength = frame.payload.size
        )?.let { throw P2pError.ProtocolError(it) }

        // Single-frame fast path — no state to keep, but the message-size cap
        // still applies; without this check a single frame between
        // MAX_PAYLOAD_BYTES and MAX_FRAME_PAYLOAD_BYTES would bypass the cap
        // the multi-chunk path enforces via bufferedBytes (AUDIT-2026-06 fix).
        if (frame.totalChunks == 1) {
            val maximum = if (frame.isEnvelope) {
                ProtocolConstants.MAX_APP_MESSAGE_ENVELOPE_BYTES.toLong()
            } else {
                ProtocolConstants.MAX_PAYLOAD_BYTES
            }
            if (frame.payload.size.toLong() > maximum) {
                throw P2pError.ProtocolError(
                    "single-frame message ${frame.payload.size} exceeds " +
                        "maximum $maximum"
                )
            }
            return decodePayload(frame.payload, frame.isText, frame.isEnvelope, frame.messageId)
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
            val now = clock()
            Pending(
                totalChunks = frame.totalChunks,
                isText = frame.isText,
                isEnvelope = frame.isEnvelope,
                needsAck = frame.needsAck,
                chunks = mutableMapOf(),
                firstSeenMillis = now,
                lastSeenMillis = now
            )
        }
        if (state.totalChunks != frame.totalChunks) {
            removePending(frame.messageId)
            throw P2pError.ProtocolError(
                "Mismatched totalChunks for messageId=${frame.messageId}: " +
                    "first saw ${state.totalChunks}, now ${frame.totalChunks}"
            )
        }
        if (state.isText != frame.isText || state.isEnvelope != frame.isEnvelope ||
            state.needsAck != frame.needsAck
        ) {
            removePending(frame.messageId)
            throw P2pError.ProtocolError(
                "Mismatched DATA flags for messageId=${frame.messageId}: " +
                    "IS_TEXT, IS_ENVELOPE, and NEEDS_ACK must remain stable"
            )
        }
        // A well-behaved sender never repeats or invents chunk indices, so a
        // duplicate or out-of-range index is a protocol violation. Rejecting
        // duplicates outright (instead of silently overwriting the stored
        // bytes without counting them) makes the byte accounting below exact:
        // a re-sent index can no longer pin uncounted memory
        // (AUDIT-2026-06 fix).
        if (frame.chunkIndex !in 0 until state.totalChunks) {
            throw P2pError.ProtocolError(
                "chunkIndex ${frame.chunkIndex} out of range for messageId=${frame.messageId} " +
                    "(totalChunks=${state.totalChunks})"
            )
        }
        if (frame.chunkIndex in state.chunks) {
            throw P2pError.ProtocolError(
                "duplicate chunkIndex ${frame.chunkIndex} for messageId=${frame.messageId}"
            )
        }
        // Track running buffered sizes (Long) and reject before a reassembled
        // message could exceed MAX_PAYLOAD_BYTES, or the aggregate across all
        // pending messages could exceed MAX_TOTAL_PENDING_BYTES. Guards
        // against both the Int-overflow of summing sizes and an oversized
        // aggregate allocation.
        state.bufferedBytes += frame.payload.size.toLong()
        totalPendingBytes += frame.payload.size.toLong()
        val messageMaximum = if (state.isEnvelope) {
            ProtocolConstants.MAX_APP_MESSAGE_ENVELOPE_BYTES.toLong()
        } else {
            ProtocolConstants.MAX_PAYLOAD_BYTES
        }
        if (state.bufferedBytes > messageMaximum) {
            removePending(frame.messageId)
            throw P2pError.ProtocolError(
                "Reassembled message for messageId=${frame.messageId} would exceed " +
                    "maximum $messageMaximum"
            )
        }
        if (totalPendingBytes > ProtocolConstants.MAX_TOTAL_PENDING_BYTES) {
            val aggregate = totalPendingBytes
            removePending(frame.messageId)
            throw P2pError.ProtocolError(
                "Aggregate pending reassembly bytes ($aggregate, after messageId=" +
                    "${frame.messageId}) exceed " +
                    "MAX_TOTAL_PENDING_BYTES (${ProtocolConstants.MAX_TOTAL_PENDING_BYTES})"
            )
        }
        state.chunks[frame.chunkIndex] = frame.payload
        state.lastSeenMillis = clock()

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
        removePending(frame.messageId)
        return decodePayload(combined, state.isText, state.isEnvelope, frame.messageId)
    }

    /** Drop partial messages that have received no chunk for the timeout. */
    fun evictStale() {
        if (pending.isEmpty()) return
        val now = clock()
        val expired = pending.entries
            .filter { now - it.value.lastSeenMillis > reassemblyTimeoutMillis }
            .map { it.key }
        for (id in expired) removePending(id)
    }

    internal fun pendingCount(): Int = pending.size

    /**
     * The only way a [Pending] leaves the map — keeps [totalPendingBytes]
     * equal to the sum of the remaining entries' [Pending.bufferedBytes].
     */
    private fun removePending(id: MessageId) {
        pending.remove(id)?.let { totalPendingBytes -= it.bufferedBytes }
    }

    private fun decodePayload(
        bytes: ByteArray,
        isText: Boolean,
        isEnvelope: Boolean,
        messageId: MessageId
    ): P2pMessage {
        if (isEnvelope) {
            val state = sessionState
                ?: throw P2pError.ProtocolError("Application message envelope has no session context")
            return AppMessageEnvelope.decode(bytes, messageId, state)
        }
        if (!isText) return P2pMessage.Binary(bytes)
        return try {
            P2pMessage.Text(bytes.decodeStrictUtf8("DATA text payload"))
        } catch (failure: IllegalArgumentException) {
            throw P2pError.ProtocolError(failure.message ?: "DATA text payload is invalid")
        }
    }
}
