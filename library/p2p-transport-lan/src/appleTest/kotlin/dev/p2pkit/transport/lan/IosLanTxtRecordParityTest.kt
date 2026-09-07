@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.transport.TransportSecurityProfile
import kotlinx.cinterop.addressOf
import kotlinx.cinterop.convert
import kotlinx.cinterop.reinterpret
import kotlinx.cinterop.usePinned
import platform.Network.nw_txt_record_create_with_bytes
import platform.posix.uint8_tVar
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Feed identical original RDATA to the raw parser and the real Network.framework decoder. */
class IosLanTxtRecordParityTest {
    @Test
    fun everyMalformedKnownValueIsRejectedByBothDecoders() {
        for (key in LanConstants.DISCOVERY_TXT_KEYS) {
            for ((description, value) in LanTxtRecordFixtures.malformedUtf8) {
                val properties = LanTxtRecordFixtures.properties(TransportSecurityProfile.AuthenticatedV2) +
                    (key to value)
                val bytes = LanTxtRecordFixtures.encode(properties.toList())
                val apple = decodeApple(bytes)
                assertTrue(apple.malformed, "$key / $description")
                assertEquals(emptyMap(), apple.properties)
                assertNull(decodeLanTxtRecord(bytes), "$key / $description")
            }
        }
    }

    @Test
    fun unknownBinaryValuesAndExactAsciiKeySelectionHaveParity() {
        val entries = listOf(
            "future" to byteArrayOf(0xFF.toByte()),
            "NAME" to byteArrayOf(0xFF.toByte()),
            LanConstants.TXT_DEVICE_NAME to "Remote".encodeToByteArray()
        )
        assertParity(entries, mapOf(LanConstants.TXT_DEVICE_NAME to "Remote"))
    }

    @Test
    fun unicodeReplacementCharactersAndNulBytesRemainUnmodified() {
        for (name in listOf(" 📱 αβ \uFFFD = Remote ", "Remote\u0000", "é".repeat(125))) {
            assertParity(
                listOf(LanConstants.TXT_DEVICE_NAME to name.encodeToByteArray()),
                mapOf(LanConstants.TXT_DEVICE_NAME to name)
            )
        }
    }

    @Test
    fun emptyAndBooleanFieldsHaveParity() {
        for (value in listOf(null, byteArrayOf())) {
            assertParity(listOf(LanConstants.TXT_DEVICE_NAME to value), mapOf(LanConstants.TXT_DEVICE_NAME to ""))
        }
    }

    @Test
    fun duplicateTraversalAndMalformedDuplicateRejectionHaveParity() {
        val key = LanConstants.TXT_DEVICE_NAME
        val first = key to "first".encodeToByteArray()
        val last = key to "last".encodeToByteArray()
        val invalid = key to byteArrayOf(0xC3.toByte())
        assertParity(listOf(first, last), mapOf(key to "last"))
        for (entries in listOf(listOf(invalid, last), listOf(first, invalid))) {
            val bytes = LanTxtRecordFixtures.encode(entries)
            val apple = decodeApple(bytes)
            assertTrue(apple.malformed)
            assertEquals(emptyMap(), apple.properties)
            assertNull(decodeLanTxtRecord(bytes))
        }
    }

    private fun assertParity(entries: List<Pair<String, ByteArray?>>, expected: Map<String, String>) {
        val bytes = LanTxtRecordFixtures.encode(entries)
        val apple = decodeApple(bytes)
        assertFalse(apple.malformed)
        assertEquals(expected, apple.properties)
        assertEquals(expected, decodeLanTxtRecord(bytes))
    }

    private fun decodeApple(bytes: ByteArray): IosBonjour.DecodedRecord = bytes.usePinned { pinned ->
        val record = nw_txt_record_create_with_bytes(
            pinned.addressOf(0).reinterpret<uint8_tVar>(),
            bytes.size.convert()
        ) ?: error("nw_txt_record_create_with_bytes returned null")
        IosBonjour.decodeTxtRecord(record)
    }
}
