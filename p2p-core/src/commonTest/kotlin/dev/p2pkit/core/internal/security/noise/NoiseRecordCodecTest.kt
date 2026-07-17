package dev.p2pkit.core.internal.security.noise

import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class NoiseRecordCodecTest {
    @Test
    fun fragmentedAndBatchedRecordsDecodeExactlyOnce() {
        val first = ByteArray(16) { it.toByte() }
        val second = ByteArray(257) { (it * 3).toByte() }
        val stream = SecureRecordFrame.encode(first) + SecureRecordFrame.encode(second)
        val decoder = SecureRecordDecoder()
        val records = mutableListOf<ByteArray>()

        stream.forEach { byte -> records += decoder.feed(byteArrayOf(byte)) }
        decoder.finish()

        assertEquals(2, records.size)
        assertContentEquals(first, records[0])
        assertContentEquals(second, records[1])
    }

    @Test
    fun invalidLengthFailsAsSoonAsHeaderArrivesAndDecoderBecomesTerminal() {
        val decoder = SecureRecordDecoder()
        assertFailsWith<NoiseProtocolException> {
            decoder.feed(byteArrayOf(0, 15))
        }
        assertFailsWith<IllegalStateException> {
            decoder.feed(SecureRecordFrame.encode(ByteArray(16)))
        }
    }

    @Test
    fun oversizedLengthAndTruncatedEofFailPrecisely() {
        val oversized = SECURE_RECORD_MAX_CIPHERTEXT_BYTES + 1
        assertFailsWith<NoiseProtocolException> {
            SecureRecordDecoder().feed(
                byteArrayOf((oversized ushr 8).toByte(), oversized.toByte()),
            )
        }

        val decoder = SecureRecordDecoder()
        decoder.feed(byteArrayOf(0, 16, 1, 2, 3))
        assertFailsWith<NoiseTransportEofException> { decoder.finish() }
        assertFailsWith<IllegalStateException> { decoder.finish() }
    }

    @Test
    fun plaintextBoundaryMapsToExactCiphertextBoundary() {
        val minimum = ByteArray(SECURE_RECORD_MIN_CIPHERTEXT_BYTES)
        val maximum = ByteArray(SECURE_RECORD_MAX_CIPHERTEXT_BYTES)
        assertContentEquals(minimum, SecureRecordFrame.decode(SecureRecordFrame.encode(minimum)))
        assertContentEquals(maximum, SecureRecordFrame.decode(SecureRecordFrame.encode(maximum)))
        assertFailsWith<NoiseProtocolException> {
            SecureRecordFrame.encode(ByteArray(SECURE_RECORD_MIN_CIPHERTEXT_BYTES - 1))
        }
        assertFailsWith<NoiseProtocolException> {
            SecureRecordFrame.encode(ByteArray(SECURE_RECORD_MAX_CIPHERTEXT_BYTES + 1))
        }
    }
}
