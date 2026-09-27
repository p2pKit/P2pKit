package dev.p2pkit.core.protocol

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.P2pSessionProfile
import dev.p2pkit.core.reserveOrThrow

/**
 * Streaming parser for one connection. Input is copied once into a reusable
 * frame buffer; completed frames advance a cursor instead of copying the tail.
 * Only the fixed header is buffered before its declared shape and size are
 * validated.
 */
internal class FrameReader(
    private val logger: P2pLogger = P2pLogger.NoOp,
    private val expectedVersion: Byte = ProtocolConstants.LEGACY_VERSION,
    private val profile: P2pSessionProfile? = null
) {

    private var bufferLease = profile?.payloadBudget?.reserveOrThrow(INITIAL_CAPACITY.toLong())
    private var buffer: ByteArray = ByteArray(INITIAL_CAPACITY)
    private var buffered: Int = 0

    var skippedUnknownFrames: Int = 0
        private set

    /** Bytes copied solely while growing the reusable buffer; exposed for linear-work tests. */
    internal var relocatedBytes: Long = 0
        private set

    private var unknownWarnings: Int = 0

    /** Append arbitrary stream bytes and return every complete known frame in order. */
    fun feed(bytes: ByteArray): List<Frame> {
        if (bytes.isEmpty()) return emptyList()

        val frames = mutableListOf<Frame>()
        var inputOffset = 0
        try {
            while (inputOffset < bytes.size) {
                if (buffered < ProtocolConstants.HEADER_SIZE) {
                    val copied = appendFrom(
                        source = bytes,
                        sourceOffset = inputOffset,
                        byteCount = minOf(
                            bytes.size - inputOffset,
                            ProtocolConstants.HEADER_SIZE - buffered
                        )
                    )
                    inputOffset += copied
                    if (buffered < ProtocolConstants.HEADER_SIZE) break
                }

                val header = inspectHeader()
                val frameSize = ProtocolConstants.HEADER_SIZE + header.payloadLength
                if (buffered < frameSize) {
                    val copied = appendFrom(
                        source = bytes,
                        sourceOffset = inputOffset,
                        byteCount = minOf(bytes.size - inputOffset, frameSize - buffered)
                    )
                    inputOffset += copied
                    if (buffered < frameSize) break
                }

                if (header.type == null) {
                    skippedUnknownFrames++
                    warnUnknown(header.typeCode)
                } else {
                    val lease = profile?.payloadBudget?.reserveOrThrow(header.payloadLength.toLong() + 256)
                    try {
                        frames += FrameCodec.decode(
                            bytes = buffer,
                            offset = 0,
                            length = frameSize,
                            expectedVersion = expectedVersion
                        ).also { it.payloadLease = lease }
                    } catch (failure: Throwable) {
                        lease?.release()
                        throw failure
                    }
                }
                buffered = 0
                val retainedCapacity = if (profile == null) MAX_RETAINED_CAPACITY else 4_096
                if (buffer.size > retainedCapacity) {
                    val replacementLease = profile?.payloadBudget?.reserveOrThrow(INITIAL_CAPACITY.toLong())
                    buffer = ByteArray(INITIAL_CAPACITY)
                    bufferLease?.release()
                    bufferLease = replacementLease
                }
            }
            return frames
        } catch (failure: Throwable) {
            frames.forEach(Frame::releasePayload)
            throw failure
        }
    }

    fun close() {
        buffer = ByteArray(0)
        buffered = 0
        bufferLease?.release()
        bufferLease = null
    }

    internal fun bufferedBytes(): Int = buffered

    private data class Header(
        val type: PacketType?,
        val typeCode: Byte,
        val payloadLength: Int
    )

    private fun inspectHeader(): Header {
        if (buffer[0] != ProtocolConstants.MAGIC_0 ||
            buffer[1] != ProtocolConstants.MAGIC_1 ||
            buffer[2] != ProtocolConstants.MAGIC_2 ||
            buffer[3] != ProtocolConstants.MAGIC_3
        ) {
            throw P2pError.ProtocolError("Bad magic bytes")
        }

        val remoteVersion = buffer[4]
        if (remoteVersion != expectedVersion) {
            throw P2pError.VersionMismatch(
                localVersion = expectedVersion.toUByte().toInt(),
                remoteVersion = remoteVersion.toUByte().toInt()
            )
        }

        val typeCode = buffer[5]
        val type = PacketType.fromCode(typeCode)
        val payloadLength = FrameCodec.readIntBE(buffer, 32)
        if (profile != null) {
            if (type !in RESTRICTED_TYPES) {
                throw P2pError.ProtocolError("Packet type is not permitted by the restricted profile")
            }
            if (type == PacketType.DATA && (payloadLength > 65_536 ||
                (buffer[6].toInt() and FrameFlags.IS_TEXT) != 0)
            ) {
                throw P2pError.ProtocolError("Restricted DATA frame exceeds its binary chunk limit")
            }
        }
        if (payloadLength < 0) {
            throw P2pError.ProtocolError("Negative payload length in header: $payloadLength")
        }
        if (payloadLength > ProtocolConstants.MAX_FRAME_PAYLOAD_BYTES) {
            throw P2pError.ProtocolError(
                "Frame payload length $payloadLength exceeds maximum " +
                    "${ProtocolConstants.MAX_FRAME_PAYLOAD_BYTES} (universal frame bound)"
            )
        }

        val typeMaximum = FrameValidation.maxPayloadBytes(type)
        if (payloadLength > typeMaximum) {
            val packet = type?.name ?: "unknown packet 0x${typeCode.toUByte().toString(16)}"
            throw P2pError.ProtocolError(
                "$packet payload length $payloadLength exceeds maximum $typeMaximum"
            )
        }

        if (type != null) {
            val violation = FrameValidation.violation(
                type = type,
                flags = buffer[6],
                reserved = buffer[7],
                chunkIndex = FrameCodec.readIntBE(buffer, 24),
                totalChunks = FrameCodec.readIntBE(buffer, 28),
                payloadLength = payloadLength
            )
            if (violation != null) throw P2pError.ProtocolError(violation)
        }
        return Header(type, typeCode, payloadLength)
    }

    private fun appendFrom(source: ByteArray, sourceOffset: Int, byteCount: Int): Int {
        if (byteCount == 0) return 0
        ensureCapacity(buffered + byteCount)
        source.copyInto(
            destination = buffer,
            destinationOffset = buffered,
            startIndex = sourceOffset,
            endIndex = sourceOffset + byteCount
        )
        buffered += byteCount
        return byteCount
    }

    private fun ensureCapacity(required: Int) {
        if (required <= buffer.size) return
        var capacity = buffer.size
        while (capacity < required) {
            val doubled = capacity.toLong() * 2
            capacity = minOf(Int.MAX_VALUE.toLong(), maxOf(doubled, required.toLong())).toInt()
        }
        val replacementLease = profile?.payloadBudget?.reserveOrThrow(capacity.toLong())
        val replacement = try {
            ByteArray(capacity)
        } catch (failure: Throwable) {
            replacementLease?.release()
            throw failure
        }
        buffer.copyInto(replacement, endIndex = buffered)
        relocatedBytes += buffered.toLong()
        buffer = replacement
        bufferLease?.release()
        bufferLease = replacementLease
    }

    private fun warnUnknown(typeCode: Byte) {
        unknownWarnings++
        val message = when {
            unknownWarnings <= WARNING_BURST ->
                "Skipping frame with unknown packet type 0x${typeCode.toUByte().toString(16)}"
            unknownWarnings == WARNING_BURST + 1 ->
                "Further unknown packet-type warnings suppressed for this connection"
            else -> return
        }
        try {
            logger.warn(message)
        } catch (_: Throwable) {
            // Diagnostics are never allowed to change parsing or connection ownership.
        }
    }

    private companion object {
        const val INITIAL_CAPACITY: Int = 256
        const val MAX_RETAINED_CAPACITY: Int = 256 * 1024
        const val WARNING_BURST: Int = 4
        val RESTRICTED_TYPES: Set<PacketType> = setOf(
            PacketType.HELLO, PacketType.DATA, PacketType.ACK, PacketType.PING,
            PacketType.PONG, PacketType.CLOSE, PacketType.ERROR
        )
    }
}
