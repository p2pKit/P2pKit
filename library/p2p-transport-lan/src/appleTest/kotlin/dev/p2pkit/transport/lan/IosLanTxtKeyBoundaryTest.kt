@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.transport.TransportSecurityProfile
import kotlinx.cinterop.addressOf
import kotlinx.cinterop.convert
import kotlinx.cinterop.reinterpret
import kotlinx.cinterop.usePinned
import platform.Network.nw_txt_record_create_with_bytes
import platform.Network.nw_txt_record_set_key
import platform.posix.uint8_tVar
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Exercise original key bytes through real Network.framework records, not a pre-decoded map. */
class IosLanTxtKeyBoundaryTest {
    @Test
    fun nulSuffixKeysNeverSupplyCanonicalFields() {
        for (key in LanConstants.DISCOVERY_TXT_KEYS) {
            val bytes = LanTxtRecordFixtures.encode(listOf("$key\u0000suffix" to "alias".encodeToByteArray()))
            assertValid(bytes, emptyMap())
        }
    }

    @Test
    fun aliasesNeverOverwriteEarlierCanonicalValues() {
        for (key in LanConstants.DISCOVERY_TXT_KEYS) {
            val bytes = LanTxtRecordFixtures.encode(
                listOf(key to "exact".encodeToByteArray(), "$key\u0000suffix" to "alias".encodeToByteArray())
            )
            assertValid(bytes, mapOf(key to "exact"))
        }
    }

    @Test
    fun canonicalFieldsAfterAliasesAreStillRead() {
        for (key in LanConstants.DISCOVERY_TXT_KEYS) {
            // Network.framework can classify this as a raw buffer rather than a dictionary.
            val bytes = LanTxtRecordFixtures.encode(
                listOf("$key\u0000suffix" to "alias".encodeToByteArray(), key to "exact".encodeToByteArray())
            )
            assertValid(bytes, mapOf(key to "exact"))
        }
    }

    @Test
    fun aliasesCannotSatisfyRequiredSemanticFields() {
        for (profile in TransportSecurityProfile.entries) {
            val properties = LanTxtRecordFixtures.properties(profile)
            val required = listOf(
                LanConstants.TXT_PEER_ID,
                LanConstants.TXT_APP_ID,
                LanConstants.TXT_PROTOCOL_VERSION
            ) +
                if (profile == TransportSecurityProfile.AuthenticatedV2) listOf(LanConstants.TXT_FINGERPRINT)
                else emptyList()
            for (key in required) {
                val bytes = LanTxtRecordFixtures.encode(
                    (properties - key).toList() + ("$key\u0000suffix" to properties.getValue(key))
                )
                val decoded = decode(bytes)
                assertFalse(decoded.malformed)
                assertNull(
                    validateLanDiscoveryRecord(decoded.properties, AppId("lan-txt-test"), PeerId("local"), profile),
                    "$profile / $key must not be supplied by an unknown key"
                )
            }
        }
    }

    @Test
    fun conformingRecordsWithForeignAliasesStillValidateInBothProfiles() {
        for (profile in TransportSecurityProfile.entries) {
            val entries = LanTxtRecordFixtures.properties(profile).toList() +
                LanConstants.DISCOVERY_TXT_KEYS.map { "$it\u0000suffix" to byteArrayOf(0xFF.toByte()) }
            val decoded = decode(LanTxtRecordFixtures.encode(entries))
            assertFalse(decoded.malformed)
            val record = assertNotNull(
                validateLanDiscoveryRecord(decoded.properties, AppId("lan-txt-test"), PeerId("local"), profile)
            )
            assertEquals(PeerId("remote"), record.peerId)
            assertEquals("Remote", record.deviceName)
        }
    }

    @Test
    fun unknownMalformedKeyBytesAndValuesAreNotConsumed() {
        val name = LanConstants.TXT_DEVICE_NAME.encodeToByteArray()
        val aliases = listOf(
            name + byteArrayOf(0),
            byteArrayOf(0) + name,
            "na\u0000me".encodeToByteArray(),
            name + byteArrayOf(0, 0xFF.toByte()),
            byteArrayOf(0xC3.toByte()) + name,
            name + byteArrayOf(0xC3.toByte()),
            "namé".encodeToByteArray()
        )
        for (key in aliases) {
            val bytes = frame("name=exact".encodeToByteArray(), key + byteArrayOf(61, 0xFF.toByte()))
            assertValid(bytes, mapOf(LanConstants.TXT_DEVICE_NAME to "exact"))
        }
    }

    @Test
    fun knownValuesRemainStrictEvenBesideUnknownAliases() {
        for (entries in listOf(
            listOf("name\u0000suffix" to "ignored".encodeToByteArray(), "name" to byteArrayOf(0xC3.toByte())),
            listOf("name" to byteArrayOf(0xC3.toByte()), "name\u0000suffix" to "ignored".encodeToByteArray())
        )) {
            val bytes = LanTxtRecordFixtures.encode(entries)
            val decoded = decode(bytes)
            assertTrue(decoded.malformed)
            assertEquals(emptyMap(), decoded.properties)
            assertNull(decodeLanTxtRecord(bytes))
        }
    }

    @Test
    fun validUnicodeEmptyAndBooleanValuesRemainCompatible() {
        for (value in listOf(" 📱 αβ \uFFFD = Remote ".encodeToByteArray(), byteArrayOf(), null)) {
            val bytes = LanTxtRecordFixtures.encode(listOf(LanConstants.TXT_DEVICE_NAME to value))
            assertValid(bytes, mapOf(LanConstants.TXT_DEVICE_NAME to (value?.decodeToString() ?: "")))
        }
    }

    @Test
    fun nativeDictionaryValuesUseTheSameStrictDecoder() {
        val record = IosBonjour.mapToTxtRecord(mapOf(LanConstants.TXT_DEVICE_NAME to "Remote\uFFFD"))
        val initial = IosBonjour.decodeTxtRecord(record)
        assertFalse(initial.malformed)
        assertEquals(mapOf(LanConstants.TXT_DEVICE_NAME to "Remote\uFFFD"), initial.properties)
        byteArrayOf(0xC3.toByte()).usePinned { pinned ->
            assertTrue(
                nw_txt_record_set_key(record, "name", pinned.addressOf(0).reinterpret<uint8_tVar>(), 1.convert())
            )
        }
        val invalid = IosBonjour.decodeTxtRecord(record)
        assertTrue(invalid.malformed)
        assertEquals(emptyMap(), invalid.properties)
    }

    @Test
    fun decodedStringsDoNotBorrowNativeDictionaryStorage() {
        val record = IosBonjour.mapToTxtRecord(mapOf(LanConstants.TXT_DEVICE_NAME to "first"))
        val first = IosBonjour.decodeTxtRecord(record)
        "last".encodeToByteArray().usePinned { pinned ->
            assertTrue(
                nw_txt_record_set_key(record, "name", pinned.addressOf(0).reinterpret<uint8_tVar>(), 4.convert())
            )
        }
        assertEquals(mapOf(LanConstants.TXT_DEVICE_NAME to "first"), first.properties)
        assertEquals(mapOf(LanConstants.TXT_DEVICE_NAME to "last"), IosBonjour.decodeTxtRecord(record).properties)
    }

    @Test
    fun truncatedRawBuffersAreMalformedNotPartiallyAccepted() {
        val valid = frame("name=exact".encodeToByteArray())
        for (bytes in listOf(valid + byteArrayOf(255.toByte()), byteArrayOf(2, 1), valid.copyOf(valid.size - 1))) {
            val decoded = decode(bytes)
            assertTrue(decoded.malformed)
            assertEquals(emptyMap(), decoded.properties)
            assertNull(decodeLanTxtRecord(bytes))
        }
    }

    @Test
    fun emptyRecordsAndTheWireLengthBoundaryRemainBounded() {
        assertValid(byteArrayOf(0), emptyMap())
        assertValid(ByteArray(65_535), emptyMap())
        val absent = IosBonjour.decodeTxtRecord(null)
        val empty = IosBonjour.decodeTxtRecord(IosBonjour.mapToTxtRecord(emptyMap()))
        assertFalse(absent.malformed)
        assertFalse(empty.malformed)
        assertEquals(emptyMap(), absent.properties)
        assertEquals(emptyMap(), empty.properties)
    }

    @Test
    fun zeroLengthAndUnknownEntriesDoNotHideCanonicalFields() {
        val bytes = byteArrayOf(0) + frame(
            "future=".encodeToByteArray() + byteArrayOf(0xFF.toByte()),
            "name=exact".encodeToByteArray()
        ) + byteArrayOf(0)
        assertValid(bytes, mapOf(LanConstants.TXT_DEVICE_NAME to "exact"))
    }

    private fun frame(vararg entries: ByteArray): ByteArray = buildList {
        for (entry in entries) {
            require(entry.size in 1..255)
            add(entry.size.toByte())
            addAll(entry.toList())
        }
    }.toByteArray()

    private fun assertValid(bytes: ByteArray, expected: Map<String, String>) {
        val decoded = decode(bytes)
        assertFalse(decoded.malformed)
        assertEquals(expected, decoded.properties)
        assertEquals(expected, decodeLanTxtRecord(bytes))
    }

    private fun decode(bytes: ByteArray): IosBonjour.DecodedRecord = bytes.usePinned { pinned ->
        val record = nw_txt_record_create_with_bytes(
            pinned.addressOf(0).reinterpret<uint8_tVar>(),
            bytes.size.convert()
        ) ?: error("nw_txt_record_create_with_bytes returned null for bounded test input")
        IosBonjour.decodeTxtRecord(record)
    }
}
