package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError
import kotlinx.io.RawSink
import kotlinx.io.Sink
import kotlinx.io.buffered
import kotlinx.io.write

/**
 * Streaming `FILE_DATA` frame consumer. Owns the receiver-side [Sink] for one
 * file transfer; the session dispatcher calls [acceptDataChunk] for every
 * matching `FILE_DATA` frame and [finish] once `FILE_DONE` arrives.
 *
 * Throws [P2pError.ProtocolError] if the sender pushes more bytes than the
 * offer promised, if `FILE_DONE` arrives before the full payload has been
 * received, or if the chunk sequence is out of order.
 *
 * Memory: only one chunk's worth of bytes is held at a time — the underlying
 * `RawSink` is responsible for any downstream buffering or disk I/O.
 */
internal class StreamingFileReceiver(
    val transferId: MessageId,
    val sizeBytes: Long,
    rawSink: RawSink
) {
    init {
        require(sizeBytes >= 0) { "sizeBytes must be non-negative, got $sizeBytes" }
    }

    private var sink: Sink? = rawSink.buffered()
    private var bytesWritten: Long = 0
    private var nextExpectedIndex: Int = 0
    private var expectedTotalChunks: Int? = null
    private var closed: Boolean = false

    val bytesReceived: Long get() = bytesWritten

    /**
     * Append a `FILE_DATA` frame's payload to the sink. Returns the new total
     * bytes written.
     */
    fun acceptDataChunk(frame: Frame): Long {
        check(!closed) { "Receiver for $transferId already finished" }
        require(frame.type == PacketType.FILE_DATA) {
            "Expected FILE_DATA, got ${frame.type}"
        }
        require(frame.messageId == transferId) {
            "Frame messageId ${frame.messageId} != transfer $transferId"
        }
        FrameValidation.violation(
            type = frame.type,
            flags = frame.flags,
            reserved = 0,
            chunkIndex = frame.chunkIndex,
            totalChunks = frame.totalChunks,
            payloadLength = frame.payload.size
        )?.let { throw P2pError.ProtocolError(it) }
        val establishedTotal = expectedTotalChunks
        if (establishedTotal == null) {
            expectedTotalChunks = frame.totalChunks
        } else if (establishedTotal != frame.totalChunks) {
            throw P2pError.ProtocolError(
                "FILE_DATA totalChunks changed for $transferId: " +
                    "$establishedTotal to ${frame.totalChunks}"
            )
        }
        if (frame.chunkIndex != nextExpectedIndex) {
            throw P2pError.ProtocolError(
                "Out-of-order FILE_DATA for $transferId: expected " +
                    "chunkIndex=$nextExpectedIndex, got ${frame.chunkIndex}"
            )
        }
        val payloadSize = frame.payload.size.toLong()
        if (payloadSize > sizeBytes - bytesWritten) {
            throw P2pError.ProtocolError(
                "FILE_DATA for $transferId exceeds advertised size " +
                    "$sizeBytes (already received $bytesWritten, next chunk is $payloadSize)"
            )
        }
        val newTotal = bytesWritten + payloadSize
        if (frame.isLastChunk != (newTotal == sizeBytes)) {
            throw P2pError.ProtocolError(
                "FILE_DATA LAST_CHUNK does not match advertised size for $transferId"
            )
        }
        checkNotNull(sink) { "Receiver for $transferId no longer owns a sink" }
            .write(frame.payload)
        bytesWritten = newTotal
        nextExpectedIndex++
        return bytesWritten
    }

    /**
     * Called when `FILE_DONE` arrives. Flushes the sink. Throws if the full
     * payload hasn't been received.
     */
    fun finish() {
        check(!closed) { "Receiver for $transferId already finished" }
        if (bytesWritten != sizeBytes) {
            throw P2pError.ProtocolError(
                "FILE_DONE for $transferId arrived after $bytesWritten of " +
                    "$sizeBytes bytes; transfer is incomplete"
            )
        }
        val ownedSink = checkNotNull(sink) { "Receiver for $transferId no longer owns a sink" }
        ownedSink.flush()
        closed = true
        sink = null
    }

    /**
     * Drop buffered partial data and release the sink reference on
     * cancel/reject. The caller owns the RawSink and decides whether to flush,
     * close, or delete it; abort must not run user I/O or race a writer.
     */
    fun abort() {
        if (closed) return
        closed = true
        sink = null
    }

    fun isComplete(): Boolean = bytesWritten == sizeBytes
}
