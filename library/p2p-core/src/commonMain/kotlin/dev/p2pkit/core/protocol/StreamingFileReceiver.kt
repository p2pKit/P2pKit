package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.internal.security.Sha256Hasher
import dev.p2pkit.core.transfer.Sha256Digest
import kotlinx.io.RawSink
import kotlinx.io.Sink
import kotlinx.io.buffered
import kotlinx.io.write

/**
 * Streaming `FILE_DATA` frame consumer. Owns the receiver-side [Sink] for one
 * file transfer; the session dispatcher calls [acceptDataChunk] for every
 * matching `FILE_DATA` frame. Legacy `FILE_DONE` uses [finish]; authenticated
 * `FILE_FINISH` uses [prepareFinish] for verification and then
 * [flushPrepared] before durable destination commit.
 *
 * Throws [P2pError.ProtocolError] if the sender pushes more bytes than the
 * offer promised, if a completion signal arrives before the full payload has been
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
    private val hasher = Sha256Hasher()
    private var closed: Boolean = false
    private var preparedSummary: FileReceiveSummary? = null

    val bytesReceived: Long get() = bytesWritten

    /**
     * Append a `FILE_DATA` frame's payload to the sink. Returns the new total
     * bytes written.
     */
    fun acceptDataChunk(frame: Frame): Long {
        check(!closed) { "Receiver for $transferId already finished" }
        check(preparedSummary == null) { "Receiver for $transferId already prepared completion" }
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
        hasher.update(frame.payload)
        bytesWritten = newTotal
        nextExpectedIndex++
        return bytesWritten
    }

    /**
     * Validate the byte/chunk totals, flush the sink, and return the streamed
     * SHA-256. Throws if the full payload has not been received.
     */
    fun finish(): FileReceiveSummary {
        val summary = prepareFinish()
        flushPrepared()
        return summary
    }

    /** Validate totals and freeze the streamed digest without flushing bytes. */
    fun prepareFinish(): FileReceiveSummary {
        check(!closed) { "Receiver for $transferId already finished" }
        preparedSummary?.let { return it }
        if (bytesWritten != sizeBytes) {
            throw P2pError.ProtocolError(
                "FILE_DONE for $transferId arrived after $bytesWritten of " +
                    "$sizeBytes bytes; transfer is incomplete"
            )
        }
        val summary = FileReceiveSummary(
            sizeBytes = bytesWritten,
            chunkCount = nextExpectedIndex,
            contentDigest = hasher.finish()
        )
        preparedSummary = summary
        return summary
    }

    /** Flush only after the authenticated finish values and digest match. */
    fun flushPrepared() {
        check(!closed) { "Receiver for $transferId already finished" }
        checkNotNull(preparedSummary) { "Receiver for $transferId was not prepared" }
        checkNotNull(sink) { "Receiver for $transferId no longer owns a sink" }.flush()
        closed = true
        sink = null
    }

    /**
     * Drop buffered partial data and release the sink reference on
     * cancel/reject. The higher layer terminalizes either the caller-owned
     * legacy sink or the SDK-owned transactional destination; this method must
     * not race that cleanup with a writer.
     */
    fun abort() {
        if (closed) return
        closed = true
        sink = null
        preparedSummary = null
    }

    fun isComplete(): Boolean = bytesWritten == sizeBytes
}

internal data class FileReceiveSummary(
    val sizeBytes: Long,
    val chunkCount: Int,
    val contentDigest: Sha256Digest
)
