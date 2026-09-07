package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.transport.TransportSecurityProfile
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull

class LanTxtRecordTest {
    @Test
    fun everyKnownValueIsStrictUtf8AndPartialRecordsAreDiscarded() {
        for (key in LanConstants.DISCOVERY_TXT_KEYS) {
            for ((description, value) in LanTxtRecordFixtures.malformedUtf8) {
                val entries = listOf(LanConstants.TXT_PEER_ID to "valid-first".encodeToByteArray(), key to value)
                assertNull(decodeLanTxtRecord(LanTxtRecordFixtures.encode(entries)), "$key / $description")
            }
        }
    }

    @Test
    fun unknownKeysAreSkippedWithoutDecodingOrRetainingTheirValues() {
        val ignored = (1..200).map { "future-$it" to byteArrayOf(0xFF.toByte()) }
        val entries = ignored + listOf(LanConstants.TXT_DEVICE_NAME to "Remote".encodeToByteArray())
        assertEquals(
            mapOf(LanConstants.TXT_DEVICE_NAME to "Remote"),
            decodeLanTxtRecord(LanTxtRecordFixtures.encode(entries))
        )
    }

    @Test
    fun protocolKeysMatchTheirExactAsciiBytes() {
        val entries = listOf(
            "NAME" to "uppercase".encodeToByteArray(),
            "na\uFFFDme" to byteArrayOf(0xFF.toByte()),
            "name-extra" to byteArrayOf(0xFF.toByte()),
            LanConstants.TXT_DEVICE_NAME to "lowercase".encodeToByteArray()
        )
        assertEquals(
            mapOf(LanConstants.TXT_DEVICE_NAME to "lowercase"),
            decodeLanTxtRecord(LanTxtRecordFixtures.encode(entries))
        )
    }

    @Test
    fun literalReplacementCharactersUnicodeAndEqualsSignsAreNotNormalized() {
        val values = mapOf(
            LanConstants.TXT_PEER_ID to " remote-\uFFFD ",
            LanConstants.TXT_DEVICE_NAME to " 📱 αβ \uFFFD = Remote "
        )
        val bytes = LanTxtRecordFixtures.encode(values.map { (key, value) -> key to value.encodeToByteArray() })
        assertEquals(values, decodeLanTxtRecord(bytes))
        assertEquals(values[LanConstants.TXT_PEER_ID], validDiscoveryPeerIdOrNull(values[LanConstants.TXT_PEER_ID]))
    }

    @Test
    fun emptyAndBooleanValuesArePresentAndEmpty() {
        for (value in listOf(null, byteArrayOf())) {
            val bytes = LanTxtRecordFixtures.encode(listOf(LanConstants.TXT_DEVICE_NAME to value))
            assertEquals(mapOf(LanConstants.TXT_DEVICE_NAME to ""), decodeLanTxtRecord(bytes))
        }
    }

    @Test
    fun nulIsPreservedForSemanticRejectionRatherThanStripped() {
        val profile = TransportSecurityProfile.AuthenticatedV2
        val properties = LanTxtRecordFixtures.properties(profile) +
            (LanConstants.TXT_DEVICE_NAME to "Remote\u0000".encodeToByteArray())
        val decoded = assertNotNull(decodeLanTxtRecord(LanTxtRecordFixtures.encode(properties.toList())))
        assertEquals("Remote\u0000", decoded[LanConstants.TXT_DEVICE_NAME])
        assertNull(validateLanDiscoveryRecord(decoded, AppId("lan-txt-test"), PeerId("local"), profile))
    }

    @Test
    fun duplicatesRetainTheLastValueButEveryOccurrenceMustDecodeStrictly() {
        val key = LanConstants.TXT_DEVICE_NAME
        val first = key to "first".encodeToByteArray()
        val last = key to "last".encodeToByteArray()
        val invalid = key to byteArrayOf(0xC3.toByte())
        assertEquals(mapOf(key to "last"), decodeLanTxtRecord(LanTxtRecordFixtures.encode(listOf(first, last))))
        assertNull(decodeLanTxtRecord(LanTxtRecordFixtures.encode(listOf(invalid, last))))
        assertNull(decodeLanTxtRecord(LanTxtRecordFixtures.encode(listOf(first, invalid))))
    }

    @Test
    fun fullUnsignedEntryLengthAndUtf8ByteBoundaryAreAccepted() {
        val name = "é".repeat(125)
        val bytes = LanTxtRecordFixtures.encode(listOf(LanConstants.TXT_DEVICE_NAME to name.encodeToByteArray()))
        assertEquals(255, bytes.first().toInt() and 0xFF)
        assertEquals(mapOf(LanConstants.TXT_DEVICE_NAME to name), decodeLanTxtRecord(bytes))
    }

    @Test
    fun truncatedFramingRejectsEvenAfterAValidEntryOrForAnUnknownKey() {
        val valid = LanTxtRecordFixtures.encode(listOf(LanConstants.TXT_DEVICE_NAME to "Remote".encodeToByteArray()))
        assertNull(decodeLanTxtRecord(byteArrayOf(1)))
        assertNull(decodeLanTxtRecord(valid + byteArrayOf(255.toByte())))
        assertNull(decodeLanTxtRecord(valid + byteArrayOf(9) + "future=x".encodeToByteArray()))
        assertNull(decodeLanTxtRecord(valid.copyOf(valid.size - 1)))
    }

    @Test
    fun missingEmptyAndZeroLengthEntriesDoNotInventFields() {
        assertEquals(emptyMap(), decodeLanTxtRecord(null))
        assertEquals(emptyMap(), decodeLanTxtRecord(byteArrayOf()))
        assertEquals(emptyMap(), decodeLanTxtRecord(byteArrayOf(0, 0)))
        val valid = LanTxtRecordFixtures.encode(listOf(LanConstants.TXT_DEVICE_NAME to "Remote".encodeToByteArray()))
        assertEquals(mapOf(LanConstants.TXT_DEVICE_NAME to "Remote"), decodeLanTxtRecord(byteArrayOf(0) + valid))
    }

    @Test
    fun resourceRecordLengthIsBoundedBeforeProcessingEntries() {
        assertEquals(emptyMap(), decodeLanTxtRecord(ByteArray(65_535)))
        assertNull(decodeLanTxtRecord(ByteArray(65_536)))
    }

    @Test
    fun decodedStringsDoNotBorrowTheInputArray() {
        val bytes = LanTxtRecordFixtures.encode(listOf(LanConstants.TXT_DEVICE_NAME to "A".encodeToByteArray()))
        val decoded = decodeLanTxtRecord(bytes)
        bytes[bytes.lastIndex] = 'B'.code.toByte()
        assertEquals(mapOf(LanConstants.TXT_DEVICE_NAME to "A"), decoded)
    }
}
