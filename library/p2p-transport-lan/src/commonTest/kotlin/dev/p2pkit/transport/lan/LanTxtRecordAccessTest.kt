package dev.p2pkit.transport.lan

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull

class LanTxtRecordAccessTest {
    @Test
    fun oversizedNativeLengthsNeverNarrowOrReadStorage() {
        val oversizedLengths = listOf(
            65_536UL,
            Int.MAX_VALUE.toULong(),
            UInt.MAX_VALUE.toULong(),
            1UL shl 32,
            (1UL shl 32) + 1UL,
            ULong.MAX_VALUE
        )
        for (length in oversizedLengths) {
            var reads = 0
            assertNull(decodeLanTxtRecord(length) {
                reads++
                byteArrayOf()
            }, "length=$length")
            assertEquals(0, reads, "length=$length must be rejected before narrowing or reading")
        }
    }

    @Test
    fun emptyRecordNeverDereferencesNativeStorage() {
        assertEquals(emptyMap(), decodeLanTxtRecord(0UL) { error("empty native storage must not be read") })
    }

    @Test
    fun largestWireRecordTakesExactlyOneBoundedSnapshot() {
        var reads = 0
        assertEquals(emptyMap(), decodeLanTxtRecord(65_535UL) { length ->
            reads++
            assertEquals(65_535, length)
            ByteArray(length)
        })
        assertEquals(1, reads)
    }

    @Test
    fun missingShortOrLongCopiesAreNotAbsentRecords() {
        for (bytes in listOf(null, byteArrayOf(), byteArrayOf(0), byteArrayOf(0, 0, 0))) {
            var reads = 0
            assertNull(decodeLanTxtRecord(2UL) { length ->
                reads++
                assertEquals(2, length)
                bytes
            })
            assertEquals(1, reads)
        }
    }

    @Test
    fun exactNativeCopyUsesOriginalKeysAndStrictValues() {
        val alias = "name\u0000suffix" to byteArrayOf(0xFF.toByte())
        val canonical = "name" to " Remote\uFFFD ".encodeToByteArray()
        val bytes = LanTxtRecordFixtures.encode(listOf(alias, canonical))
        assertEquals(mapOf("name" to " Remote\uFFFD "), decodeLanTxtRecord(bytes.size.toULong()) { bytes })
        val malformed = LanTxtRecordFixtures.encode(listOf(canonical, "name" to byteArrayOf(0xC3.toByte())))
        assertNull(decodeLanTxtRecord(malformed.size.toULong()) { malformed })
    }

    @Test
    fun exactCopyWithTruncatedFramingIsMalformed() {
        val bytes = LanTxtRecordFixtures.encode(listOf("name" to "Remote".encodeToByteArray())) +
            byteArrayOf(255.toByte())
        assertNull(decodeLanTxtRecord(bytes.size.toULong()) { bytes })
    }

    @Test
    fun decodedFieldsDoNotBorrowTheNativeCopy() {
        val bytes = LanTxtRecordFixtures.encode(listOf("name" to "first".encodeToByteArray()))
        var reads = 0
        val decoded = decodeLanTxtRecord(bytes.size.toULong()) { length ->
            reads++
            assertEquals(bytes.size, length)
            bytes
        }
        bytes.fill(0)
        assertEquals(mapOf("name" to "first"), decoded)
        assertEquals(1, reads)
    }
}
