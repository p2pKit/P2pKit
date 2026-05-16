package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger

/**
 * Streaming parser. Bytes from a [dev.p2pkit.core.transport.RawConnection]
 * arrive in arbitrary chunk sizes; this class buffers them and emits complete
 * [Frame]s as they become available.
 *
 * Not thread-safe — each connection has its own reader instance, used from a
 * single coroutine.
 *
 * @param logger Used to warn about frames with **unknown packet type codes**.
 *   Per Spec §17 those frames are skipped (no session close) for forward
 *   compatibility with future protocol additions.
 * @param skippedUnknownFrames Counter exposed for tests; counts how many
 *   frames were dropped because of [UnknownPacketTypeException].
 */
internal class FrameReader(
    private val logger: P2pLogger = P2pLogger.NoOp
) {

    private var buffer: ByteArray = EMPTY

    var skippedUnknownFrames: Int = 0
        private set

    /**
     * Append [bytes] to the internal buffer and return zero or more complete
     * frames that can now be decoded.
     *
     * Throws [P2pError.ProtocolError] if the buffered bytes are structurally
     * invalid (e.g., bad magic) — those errors do close the session. Unknown
     * packet types are skipped silently apart from a warn-level log.
     */
    fun feed(bytes: ByteArray): List<Frame> {
        if (bytes.isEmpty() && buffer.isEmpty()) return emptyList()
        if (bytes.isNotEmpty()) {
            val combined = ByteArray(buffer.size + bytes.size)
            buffer.copyInto(combined, 0)
            bytes.copyInto(combined, buffer.size)
            buffer = combined
        }

        val out = mutableListOf<Frame>()
        while (true) {
            if (buffer.size < ProtocolConstants.HEADER_SIZE) break
            val payloadLen = FrameCodec.readIntBE(buffer, 32)
            if (payloadLen < 0) {
                throw P2pError.ProtocolError("Negative payload length in header: $payloadLen")
            }
            val frameSize = ProtocolConstants.HEADER_SIZE + payloadLen
            if (buffer.size < frameSize) break

            val frameBytes = buffer.copyOfRange(0, frameSize)
            try {
                out.add(FrameCodec.decode(frameBytes))
            } catch (e: UnknownPacketTypeException) {
                // Spec §17: ignore + log warn, do not close the session.
                skippedUnknownFrames++
                logger.warn("Skipping frame with unknown packet type: ${e.message}")
            }
            buffer = if (buffer.size == frameSize) EMPTY else buffer.copyOfRange(frameSize, buffer.size)
        }
        return out
    }

    internal fun bufferedBytes(): Int = buffer.size

    private companion object {
        val EMPTY = ByteArray(0)
    }
}
