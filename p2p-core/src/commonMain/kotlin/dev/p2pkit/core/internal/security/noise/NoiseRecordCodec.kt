package dev.p2pkit.core.internal.security.noise

internal const val SECURE_RECORD_MAX_PLAINTEXT_BYTES: Int = 16_384
internal const val SECURE_RECORD_MIN_CIPHERTEXT_BYTES: Int = NOISE_AEAD_TAG_SIZE_BYTES
internal const val SECURE_RECORD_MAX_CIPHERTEXT_BYTES: Int =
    SECURE_RECORD_MAX_PLAINTEXT_BYTES + NOISE_AEAD_TAG_SIZE_BYTES
internal const val SECURE_RECORD_HEADER_SIZE_BYTES: Int = 2

internal object SecureRecordFrame {
    fun encode(ciphertext: ByteArray): ByteArray {
        validateCiphertextLength(ciphertext.size)
        return ByteArray(SECURE_RECORD_HEADER_SIZE_BYTES + ciphertext.size).also { frame ->
            writeU16BigEndian(ciphertext.size, frame, 0)
            ciphertext.copyInto(frame, SECURE_RECORD_HEADER_SIZE_BYTES)
        }
    }

    fun decode(frame: ByteArray): ByteArray {
        if (frame.size < SECURE_RECORD_HEADER_SIZE_BYTES) {
            throw NoiseProtocolException("Truncated secure record header")
        }
        val length = readU16BigEndian(frame[0], frame[1])
        validateCiphertextLength(length)
        if (frame.size != SECURE_RECORD_HEADER_SIZE_BYTES + length) {
            throw NoiseProtocolException("Secure record length does not match its ciphertext")
        }
        return frame.copyOfRange(SECURE_RECORD_HEADER_SIZE_BYTES, frame.size)
    }

    fun validateCiphertextLength(length: Int) {
        if (length !in SECURE_RECORD_MIN_CIPHERTEXT_BYTES..SECURE_RECORD_MAX_CIPHERTEXT_BYTES) {
            throw NoiseProtocolException(
                "Secure record ciphertext length $length is outside " +
                    "$SECURE_RECORD_MIN_CIPHERTEXT_BYTES..$SECURE_RECORD_MAX_CIPHERTEXT_BYTES",
            )
        }
    }
}

/**
 * Fragment-tolerant record decoder. Segments are queued and copied exactly
 * once into each completed record; accumulated input is never recopied.
 */
internal class SecureRecordDecoder {
    private val segments = ArrayDeque<ByteArray>()
    private var firstSegmentOffset: Int = 0
    private var availableBytes: Int = 0
    private var expectedCiphertextBytes: Int? = null
    private var terminal: Boolean = false

    fun feed(bytes: ByteArray): List<ByteArray> {
        check(!terminal) { "Secure record decoder is terminal" }
        if (bytes.isNotEmpty()) {
            segments.addLast(bytes.copyOf())
            availableBytes = checkedAvailableBytes(availableBytes, bytes.size)
        }

        val records = mutableListOf<ByteArray>()
        try {
            while (true) {
                if (expectedCiphertextBytes == null) {
                    if (availableBytes < SECURE_RECORD_HEADER_SIZE_BYTES) break
                    val header = take(SECURE_RECORD_HEADER_SIZE_BYTES)
                    val length = readU16BigEndian(header[0], header[1])
                    header.wipe()
                    SecureRecordFrame.validateCiphertextLength(length)
                    expectedCiphertextBytes = length
                }

                val expected = checkNotNull(expectedCiphertextBytes)
                if (availableBytes < expected) break
                records += take(expected)
                expectedCiphertextBytes = null
            }
        } catch (cause: Exception) {
            terminal = true
            clearBuffers()
            throw cause
        }
        return records
    }

    fun finish() {
        check(!terminal) { "Secure record decoder is terminal" }
        if (availableBytes != 0 || expectedCiphertextBytes != null) {
            terminal = true
            clearBuffers()
            throw NoiseTransportEofException("Secure record stream ended in the middle of a record")
        }
        terminal = true
        clearBuffers()
    }

    fun clear() {
        terminal = true
        clearBuffers()
    }

    private fun clearBuffers() {
        while (segments.isNotEmpty()) {
            segments.removeFirst().wipe()
        }
        firstSegmentOffset = 0
        availableBytes = 0
        expectedCiphertextBytes = null
    }

    private fun take(byteCount: Int): ByteArray {
        check(byteCount <= availableBytes)
        val result = ByteArray(byteCount)
        var resultOffset = 0
        while (resultOffset < byteCount) {
            val segment = segments.first()
            val copyCount = minOf(byteCount - resultOffset, segment.size - firstSegmentOffset)
            segment.copyInto(
                destination = result,
                destinationOffset = resultOffset,
                startIndex = firstSegmentOffset,
                endIndex = firstSegmentOffset + copyCount,
            )
            resultOffset += copyCount
            firstSegmentOffset += copyCount
            availableBytes -= copyCount
            if (firstSegmentOffset == segment.size) {
                segments.removeFirst().wipe()
                firstSegmentOffset = 0
            }
        }
        return result
    }

    private fun checkedAvailableBytes(current: Int, added: Int): Int {
        if (added > Int.MAX_VALUE - current) {
            throw NoiseProtocolException("Secure record input buffer length overflow")
        }
        return current + added
    }
}
