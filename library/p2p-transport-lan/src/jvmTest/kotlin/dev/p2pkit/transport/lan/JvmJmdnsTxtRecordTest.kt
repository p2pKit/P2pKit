package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.transport.TransportSecurityProfile
import javax.jmdns.ServiceInfo
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull

/** Tests the same real-ServiceInfo parsing entry point used by this platform's listener. */
class JvmJmdnsTxtRecordTest {
    @Test
    fun everyConsumedFieldRejectsMalformedBytesWhileValidRecordsStillParse() {
        for (profile in TransportSecurityProfile.entries) {
            val registration = registration(profile)
            assertNotNull(validateJmdnsDiscoveryRecord(service(profile), registration))
            for (key in LanConstants.DISCOVERY_TXT_KEYS) {
                for ((description, bytes) in LanTxtRecordFixtures.malformedUtf8) {
                    val info = service(profile, mapOf(key to bytes))
                    assertNull(validateJmdnsDiscoveryRecord(info, registration), "$profile / $key / $description")
                }
            }
            assertNotNull(validateJmdnsDiscoveryRecord(service(profile), registration))
        }
    }

    @Test
    fun propertyCacheNormalizationCannotEraseOriginalMalformedOrDuplicateValues() {
        for (profile in TransportSecurityProfile.entries) {
            val registration = registration(profile)
            for (duplicate in listOf(false, true)) {
                val entries = LanTxtRecordFixtures.properties(profile).toList() +
                    (LanConstants.TXT_DEVICE_NAME to byteArrayOf(0xC3.toByte())) +
                    if (duplicate) listOf(LanConstants.TXT_DEVICE_NAME to "last".encodeToByteArray()) else emptyList()
                val raw = LanTxtRecordFixtures.encode(entries)
                val info = ServiceInfo.create(LanConstants.serviceTypeJmdns(profile), "remote", 45_001, 0, 0, raw)
                // Populate the dependency's decoded cache first: neither accessor is the raw boundary.
                info.getPropertyString(LanConstants.TXT_DEVICE_NAME)
                info.getPropertyBytes(LanConstants.TXT_DEVICE_NAME)
                assertContentEquals(raw, info.textBytes)
                assertNull(validateJmdnsDiscoveryRecord(info, registration))
            }
        }
    }

    @Test
    fun emptyBooleanAndNulNamesRemainInvalidInsteadOfBecomingTrueOrTrimmed() {
        for (profile in TransportSecurityProfile.entries) {
            for (value in listOf(null, byteArrayOf(), "Remote\u0000".encodeToByteArray())) {
                assertNull(
                    validateJmdnsDiscoveryRecord(
                        service(profile, mapOf(LanConstants.TXT_DEVICE_NAME to value)),
                        registration(profile)
                    )
                )
            }
        }
    }

    @Test
    fun literalUnicodeAndUnknownBinaryFieldsRemainValidWithoutNormalization() {
        for (profile in TransportSecurityProfile.entries) {
            val name = " 📱 αβ \uFFFD = Remote "
            val id = "remote-\uFFFD"
            val info = service(
                profile,
                mapOf(
                    LanConstants.TXT_PEER_ID to id.encodeToByteArray(),
                    LanConstants.TXT_DEVICE_NAME to name.encodeToByteArray(),
                    "future" to byteArrayOf(0xFF.toByte())
                )
            )
            val record = assertNotNull(validateJmdnsDiscoveryRecord(info, registration(profile)))
            assertEquals(id, record.peerId.value)
            assertEquals(name, record.deviceName)
        }
    }

    @Test
    fun appProfileAndLocalIdentityFiltersStillApplyAfterRawDecoding() {
        for (profile in TransportSecurityProfile.entries) {
            val info = service(profile)
            assertNotNull(validateJmdnsDiscoveryRecord(info, registration(profile)))
            assertNull(validateJmdnsDiscoveryRecord(info, registration(profile, AppId("other-app"))))
            val otherProfile = TransportSecurityProfile.entries.single { it != profile }
            assertNull(validateJmdnsDiscoveryRecord(info, registration(otherProfile)))
            assertNull(
                validateJmdnsDiscoveryRecord(
                    service(profile, mapOf(LanConstants.TXT_PEER_ID to "local".encodeToByteArray())),
                    registration(profile)
                )
            )
        }
    }

    private fun registration(
        profile: TransportSecurityProfile,
        appId: AppId = AppId("lan-txt-test")
    ) = LanServiceRegistration(
        appId = appId,
        localPeerId = PeerId("local"),
        deviceName = "Observer",
        platform = Platform.JVM_DESKTOP,
        securityProfile = profile,
        fingerprint = if (profile == TransportSecurityProfile.AuthenticatedV2) {
            PeerFingerprint("p2f1-" + "b".repeat(51) + "a")
        } else {
            null
        },
        tcpPort = 45_000
    )

    private fun service(
        profile: TransportSecurityProfile,
        replacements: Map<String, ByteArray?> = emptyMap()
    ): ServiceInfo = ServiceInfo.create(
        LanConstants.serviceTypeJmdns(profile),
        "remote",
        45_001,
        0,
        0,
        LanTxtRecordFixtures.encode((LanTxtRecordFixtures.properties(profile) + replacements).toList())
    )
}
