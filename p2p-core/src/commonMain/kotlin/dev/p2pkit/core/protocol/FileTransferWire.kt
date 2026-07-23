package dev.p2pkit.core.protocol

import dev.p2pkit.core.FileTransferFailureKind
import dev.p2pkit.core.FileTransferPhase
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.Retryability
import dev.p2pkit.core.internal.security.sha256
import dev.p2pkit.core.transfer.Sha256Digest

internal class SecureFileOffer private constructor(
    val transferId: MessageId,
    val name: String,
    val sizeBytes: Long,
    val mimeType: String?,
    val contentDigest: Sha256Digest,
    private val encoded: ByteArray
) {
    val offerHash: Sha256Digest = sha256(encoded)
    fun encode(): ByteArray = encoded.copyOf()

    override fun equals(other: Any?): Boolean = other is SecureFileOffer &&
        transferId == other.transferId && encoded.contentEquals(other.encoded)

    override fun hashCode(): Int = 31 * transferId.hashCode() + encoded.contentHashCode()

    companion object {
        private val MAGIC = byteArrayOf(0x50, 0x32, 0x46, 0x4f) // P2FO
        private const val FIXED_BYTES = 4 + 1 + 1 + 1 + 1 + MessageId.SIZE + 8 + 2 + 32

        fun create(
            transferId: MessageId,
            name: String,
            sizeBytes: Long,
            mimeType: String?,
            digest: Sha256Digest
        ): SecureFileOffer {
            FileOfferPayload.validate(FileOfferPayload(name, sizeBytes, mimeType))
            val nameBytes = name.encodeToByteArray()
            val mimeBytes = mimeType?.encodeToByteArray()
            val output = ByteArray(FIXED_BYTES + nameBytes.size + (mimeBytes?.let { 2 + it.size } ?: 0))
            val writer = TransferWriter(output)
            writer.bytes(MAGIC)
            writer.u8(FILE_TRANSFER_SCHEMA_VERSION)
            writer.u8(DIGEST_SHA256)
            writer.u8(COMPLETION_DURABLE_COMMIT)
            writer.u8(if (mimeBytes == null) 0 else FLAG_MIME)
            writer.bytes(transferId.bytes)
            writer.u64(sizeBytes)
            writer.sizedU16(nameBytes)
            if (mimeBytes != null) writer.sizedU16(mimeBytes)
            writer.bytes(digest.copyBytes())
            return SecureFileOffer(transferId, name, sizeBytes, mimeType, digest, output)
        }

        fun decode(frameTransferId: MessageId, bytes: ByteArray): SecureFileOffer {
            val reader = TransferReader(bytes)
            reader.requireMagic(MAGIC, "FILE_OFFER")
            reader.requireSchema("FILE_OFFER")
            if (reader.u8() != DIGEST_SHA256) throw P2pError.ProtocolError("FILE_OFFER digest must be SHA-256")
            if (reader.u8() != COMPLETION_DURABLE_COMMIT) {
                throw P2pError.ProtocolError("FILE_OFFER must require durable commit")
            }
            val flags = reader.u8()
            if (flags and FLAG_MIME.inv() != 0) throw P2pError.ProtocolError("FILE_OFFER flags are invalid")
            reader.requireTransferId(frameTransferId, "FILE_OFFER")
            val size = reader.u64()
            val name = reader.sizedU16("FILE_OFFER name", FileOfferPayload.MAX_NAME_UTF8_BYTES)
                .decodeStrictUtf8("FILE_OFFER name")
            val mime = if (flags and FLAG_MIME != 0) {
                reader.sizedU16("FILE_OFFER MIME type", FileOfferPayload.MAX_MIME_UTF8_BYTES)
                    .decodeStrictUtf8("FILE_OFFER MIME type")
            } else {
                null
            }
            val digest = Sha256Digest(reader.bytes(Sha256Digest.SIZE_BYTES))
            reader.requireFinished("FILE_OFFER")
            FileOfferPayload.validate(FileOfferPayload(name, size, mime))
            return SecureFileOffer(frameTransferId, name, size, mime, digest, bytes.copyOf())
        }
    }
}

internal data class SecureFileFinish(
    val transferId: MessageId,
    val sizeBytes: Long,
    val chunkCount: Int,
    val contentDigest: Sha256Digest,
    val offerHash: Sha256Digest
) {
    fun encode(): ByteArray = fixedTransferPayload(
        magic = FINISH_MAGIC,
        transferId = transferId,
        trailingSize = 8 + 4 + 32 + 32
    ) { writer ->
        writer.u64(sizeBytes)
        writer.u32(chunkCount)
        writer.bytes(contentDigest.copyBytes())
        writer.bytes(offerHash.copyBytes())
    }

    companion object {
        private val FINISH_MAGIC = byteArrayOf(0x50, 0x32, 0x46, 0x46) // P2FF
        fun decode(frameTransferId: MessageId, bytes: ByteArray): SecureFileFinish {
            val reader = fixedTransferReader(FINISH_MAGIC, frameTransferId, bytes, "FILE_FINISH")
            val result = SecureFileFinish(
                transferId = frameTransferId,
                sizeBytes = reader.u64(),
                chunkCount = reader.u32(),
                contentDigest = Sha256Digest(reader.bytes(32)),
                offerHash = Sha256Digest(reader.bytes(32))
            )
            reader.requireFinished("FILE_FINISH")
            return result
        }
    }
}

internal data class SecureFileCommit(
    val transferId: MessageId,
    val sizeBytes: Long,
    val contentDigest: Sha256Digest,
    val offerHash: Sha256Digest
) {
    fun encode(): ByteArray = fixedTransferPayload(
        magic = COMMIT_MAGIC,
        transferId = transferId,
        trailingSize = 8 + 32 + 32
    ) { writer ->
        writer.u64(sizeBytes)
        writer.bytes(contentDigest.copyBytes())
        writer.bytes(offerHash.copyBytes())
    }

    companion object {
        private val COMMIT_MAGIC = byteArrayOf(0x50, 0x32, 0x46, 0x43) // P2FC
        fun decode(frameTransferId: MessageId, bytes: ByteArray): SecureFileCommit {
            val reader = fixedTransferReader(COMMIT_MAGIC, frameTransferId, bytes, "FILE_COMMIT")
            val result = SecureFileCommit(
                transferId = frameTransferId,
                sizeBytes = reader.u64(),
                contentDigest = Sha256Digest(reader.bytes(32)),
                offerHash = Sha256Digest(reader.bytes(32))
            )
            reader.requireFinished("FILE_COMMIT")
            return result
        }
    }
}

internal enum class FileResultCode(val code: Int) {
    DIGEST_MISMATCH(1),
    STORAGE_FAILURE(2),
    PROTOCOL_FAILURE(3),
    SOURCE_CHANGED(4),
    TIMEOUT(5);

    companion object {
        fun fromCode(code: Int): FileResultCode = entries.firstOrNull { it.code == code }
            ?: throw P2pError.ProtocolError("Unknown FILE_RESULT code $code")
    }
}

internal data class SecureFileResult(
    val transferId: MessageId,
    val code: FileResultCode,
    val phase: FileTransferPhase,
    val reason: String?
) {
    fun encode(): ByteArray {
        val reasonBytes = reason?.encodeToByteArray() ?: ByteArray(0)
        if (reason != null) validateWireText(reason, "FILE_RESULT reason",
            ProtocolConstants.MAX_REASON_PAYLOAD_BYTES,
            ProtocolConstants.MAX_REASON_PAYLOAD_BYTES, true)
        val output = ByteArray(4 + 1 + 1 + 1 + 1 + MessageId.SIZE + 2 + reasonBytes.size)
        val writer = TransferWriter(output)
        writer.bytes(RESULT_MAGIC)
        writer.u8(FILE_TRANSFER_SCHEMA_VERSION)
        writer.u8(code.code)
        writer.u8(phase.toWireCode())
        writer.u8(if (reason == null) 0 else 1)
        writer.bytes(transferId.bytes)
        writer.sizedU16(reasonBytes)
        return output
    }

    fun toPublicFailure(): P2pError.FileTransferFailed {
        val kind = when (code) {
            FileResultCode.DIGEST_MISMATCH -> FileTransferFailureKind.INTEGRITY
            FileResultCode.STORAGE_FAILURE -> FileTransferFailureKind.STORAGE
            FileResultCode.PROTOCOL_FAILURE -> FileTransferFailureKind.TRANSFER_PROTOCOL
            FileResultCode.SOURCE_CHANGED -> FileTransferFailureKind.SOURCE_CHANGED
            FileResultCode.TIMEOUT -> FileTransferFailureKind.TIMEOUT
        }
        val retryability = when (code) {
            FileResultCode.STORAGE_FAILURE -> Retryability.RETRY_AFTER_USER_ACTION
            FileResultCode.TIMEOUT -> Retryability.RETRY_NEW_SESSION
            FileResultCode.DIGEST_MISMATCH,
            FileResultCode.PROTOCOL_FAILURE,
            FileResultCode.SOURCE_CHANGED -> Retryability.NOT_RETRYABLE
        }
        return P2pError.FileTransferFailed(
            kind = kind,
            phase = phase,
            retryability = retryability,
            transferId = transferId.toString(),
            reason = (reason ?: "Remote file transfer failed: $code")
                .take(MAX_PUBLIC_FAILURE_REASON_CHARS)
        )
    }

    companion object {
        private val RESULT_MAGIC = byteArrayOf(0x50, 0x32, 0x46, 0x52) // P2FR
        fun decode(frameTransferId: MessageId, bytes: ByteArray): SecureFileResult {
            val reader = TransferReader(bytes)
            reader.requireMagic(RESULT_MAGIC, "FILE_RESULT")
            reader.requireSchema("FILE_RESULT")
            val code = FileResultCode.fromCode(reader.u8())
            val phase = fileTransferPhaseFromWireCode(reader.u8())
            val flags = reader.u8()
            if (flags !in 0..1) throw P2pError.ProtocolError("FILE_RESULT flags are invalid")
            reader.requireTransferId(frameTransferId, "FILE_RESULT")
            val reasonBytes = reader.sizedU16("FILE_RESULT reason", ProtocolConstants.MAX_REASON_PAYLOAD_BYTES)
            if ((flags == 0) != reasonBytes.isEmpty()) {
                throw P2pError.ProtocolError("FILE_RESULT reason presence flag is inconsistent")
            }
            val reason = if (reasonBytes.isEmpty()) null else reasonBytes.decodeStrictUtf8("FILE_RESULT reason")
                .also { validateWireText(it, "FILE_RESULT reason",
                    ProtocolConstants.MAX_REASON_PAYLOAD_BYTES,
                    ProtocolConstants.MAX_REASON_PAYLOAD_BYTES, true) }
            reader.requireFinished("FILE_RESULT")
            return SecureFileResult(frameTransferId, code, phase, reason)
        }
    }
}

internal object SecureFileAccept {
    private val MAGIC = byteArrayOf(0x50, 0x32, 0x46, 0x41) // P2FA
    fun encode(transferId: MessageId): ByteArray = fixedTransferPayload(MAGIC, transferId, 8) {
        it.u64(0)
    }
    fun decode(frameTransferId: MessageId, bytes: ByteArray) {
        val reader = fixedTransferReader(MAGIC, frameTransferId, bytes, "FILE_ACCEPT")
        if (reader.u64() != 0L) throw P2pError.ProtocolError("FILE_ACCEPT resume offset must be zero")
        reader.requireFinished("FILE_ACCEPT")
    }
}

private const val FILE_TRANSFER_SCHEMA_VERSION = 1
private const val DIGEST_SHA256 = 1
private const val COMPLETION_DURABLE_COMMIT = 1
private const val FLAG_MIME = 1
private const val MAX_PUBLIC_FAILURE_REASON_CHARS = 512

private fun FileTransferPhase.toWireCode(): Int = when (this) {
    FileTransferPhase.OFFER -> 1
    FileTransferPhase.ACCEPT -> 2
    FileTransferPhase.SOURCE_READ -> 3
    FileTransferPhase.SEND -> 4
    FileTransferPhase.RECEIVE -> 5
    FileTransferPhase.VERIFY -> 6
    FileTransferPhase.FLUSH -> 7
    FileTransferPhase.DURABLE_COMMIT -> 8
}

private fun fileTransferPhaseFromWireCode(code: Int): FileTransferPhase = when (code) {
    1 -> FileTransferPhase.OFFER
    2 -> FileTransferPhase.ACCEPT
    3 -> FileTransferPhase.SOURCE_READ
    4 -> FileTransferPhase.SEND
    5 -> FileTransferPhase.RECEIVE
    6 -> FileTransferPhase.VERIFY
    7 -> FileTransferPhase.FLUSH
    8 -> FileTransferPhase.DURABLE_COMMIT
    else -> throw P2pError.ProtocolError("Unknown FILE_RESULT phase $code")
}

private fun fixedTransferPayload(
    magic: ByteArray,
    transferId: MessageId,
    trailingSize: Int,
    body: (TransferWriter) -> Unit
): ByteArray {
    val output = ByteArray(4 + 1 + 3 + MessageId.SIZE + trailingSize)
    val writer = TransferWriter(output)
    writer.bytes(magic)
    writer.u8(FILE_TRANSFER_SCHEMA_VERSION)
    writer.u8(0)
    writer.u8(0)
    writer.u8(0)
    writer.bytes(transferId.bytes)
    body(writer)
    check(writer.position == output.size)
    return output
}

private fun fixedTransferReader(
    magic: ByteArray,
    frameTransferId: MessageId,
    bytes: ByteArray,
    field: String
): TransferReader = TransferReader(bytes).also {
    it.requireMagic(magic, field)
    it.requireSchema(field)
    if (it.u8() != 0 || it.u8() != 0 || it.u8() != 0) {
        throw P2pError.ProtocolError("$field reserved bytes must be zero")
    }
    it.requireTransferId(frameTransferId, field)
}

private class TransferWriter(private val output: ByteArray) {
    var position: Int = 0
        private set
    fun u8(value: Int) { output[position++] = value.toByte() }
    fun u16(value: Int) {
        require(value in 0..0xffff)
        output[position++] = (value ushr 8).toByte()
        output[position++] = value.toByte()
    }
    fun u32(value: Int) {
        require(value >= 0)
        output[position++] = (value ushr 24).toByte()
        output[position++] = (value ushr 16).toByte()
        output[position++] = (value ushr 8).toByte()
        output[position++] = value.toByte()
    }
    fun u64(value: Long) {
        require(value >= 0)
        for (shift in 56 downTo 0 step 8) output[position++] = (value ushr shift).toByte()
    }
    fun bytes(value: ByteArray) { value.copyInto(output, position); position += value.size }
    fun sizedU16(value: ByteArray) { u16(value.size); bytes(value) }
}

private class TransferReader(private val input: ByteArray) {
    private var position = 0
    private val remaining: Int get() = input.size - position
    fun u8(): Int = bytes(1)[0].toInt() and 0xff
    fun u16(): Int {
        val value = bytes(2)
        return ((value[0].toInt() and 0xff) shl 8) or (value[1].toInt() and 0xff)
    }
    fun u32(): Int {
        val value = bytes(4)
        val result = ((value[0].toInt() and 0xff) shl 24) or
            ((value[1].toInt() and 0xff) shl 16) or
            ((value[2].toInt() and 0xff) shl 8) or (value[3].toInt() and 0xff)
        if (result < 0) throw P2pError.ProtocolError("Unsigned transfer value exceeds supported range")
        return result
    }
    fun u64(): Long {
        val value = bytes(8)
        if (value[0].toInt() and 0x80 != 0) {
            throw P2pError.ProtocolError("Unsigned transfer value exceeds supported range")
        }
        var result = 0L
        for (byte in value) result = (result shl 8) or (byte.toLong() and 0xff)
        return result
    }
    fun bytes(count: Int): ByteArray {
        if (count < 0 || count > remaining) throw P2pError.ProtocolError("Truncated file-transfer payload")
        return input.copyOfRange(position, position + count).also { position += count }
    }
    fun sizedU16(field: String, max: Int): ByteArray {
        val size = u16()
        if (size > max) throw P2pError.ProtocolError("$field exceeds $max bytes")
        return bytes(size)
    }
    fun requireMagic(expected: ByteArray, field: String) {
        if (!bytes(expected.size).contentEquals(expected)) throw P2pError.ProtocolError("Invalid $field magic")
    }
    fun requireSchema(field: String) {
        if (u8() != FILE_TRANSFER_SCHEMA_VERSION) throw P2pError.ProtocolError("Unsupported $field schema")
    }
    fun requireTransferId(expected: MessageId, field: String) {
        if (MessageId(bytes(MessageId.SIZE)) != expected) {
            throw P2pError.ProtocolError("$field transferId does not match frame header")
        }
    }
    fun requireFinished(field: String) {
        if (remaining != 0) throw P2pError.ProtocolError("$field has trailing bytes")
    }
}
