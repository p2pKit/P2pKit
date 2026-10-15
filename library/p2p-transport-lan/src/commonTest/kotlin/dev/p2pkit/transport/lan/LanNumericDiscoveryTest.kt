package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.PeerAuthenticationHint
import dev.p2pkit.core.transport.TransportSecurityProfile
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull

class LanNumericDiscoveryTest {
    private val appId = AppId("lan-txt-test")
    private val pin = PeerFingerprint("p2f1-" + "a".repeat(52))
    private fun properties(endpoint: LanEndpoint? = null) = buildLanTxtProperties(
        PeerId("remote"), appId, "Remote", Platform.IOS, setOf(TransportKind.LAN), 2, pin, endpoint,
    )
    private fun validate(values: Map<String, String?>) = validateLanDiscoveryRecord(
        values, appId, PeerId("local"), TransportSecurityProfile.AuthenticatedV2,
    )

    @Test
    fun oldRecordsStayCompatibleAndNumericHintsNeverBecomeTrustedPins() {
        val old = properties()
        assertEquals(7, old.size)
        assertNull(assertNotNull(validate(old)).numericEndpoint)
        for (address in listOf("10.1.2.3", "172.16.0.1", "192.168.1.6", "fd00::1")) {
            val encoded = properties(LanEndpoint(address, 5432))
            val raw = LanTxtRecordFixtures.encode(encoded.map { it.key to it.value.encodeToByteArray() })
            val parsed = assertNotNull(validate(assertNotNull(decodeLanTxtRecord(raw))))
            assertEquals(address, parsed.numericEndpoint?.host)
            assertEquals(5432, parsed.numericEndpoint?.port)
            assertEquals(pin, assertIs<PeerAuthenticationHint.UntrustedDiscoveryClaim>(
                parsed.security.authenticationHint).fingerprint)
        }
    }

    @Test
    fun endpointIsAllOrNothingStrictNumericPrivateAndCanonicalPort() {
        val valid = properties(LanEndpoint("10.1.2.3", 5432))
        assertNull(validate(valid - LanConstants.TXT_NUMERIC_ADDRESS))
        assertNull(validate(valid - LanConstants.TXT_NUMERIC_PORT))
        for (address in listOf("", "host.local", "127.0.0.1", "8.8.8.8", "169.254.1.1", "224.0.0.251",
            "010.1.2.3", "10.1.2.3 ", "10.1.2.3\u0000", "fe80::1", "fd00::1%en0", "::ffff:10.1.2.3")) {
            assertNull(validate(valid + (LanConstants.TXT_NUMERIC_ADDRESS to address)), address)
        }
        for (port in listOf("", "0", "65536", "-1", "+5432", "05432", "5432 ", "5432\u0000")) {
            assertNull(validate(valid + (LanConstants.TXT_NUMERIC_PORT to port)), port)
        }
        assertNull(validate(valid + (LanConstants.TXT_NUMERIC_ADDRESS to null)))
        assertNull(validate(valid + (LanConstants.TXT_NUMERIC_PORT to null)))
    }

    @Test
    fun producerRefusesInvalidNumericHintsAndLegacyProfileCannotAdvertiseThem() {
        for (endpoint in listOf(LanEndpoint("public.example", 5432), LanEndpoint("10.1.2.3", 0))) {
            assertFailsWith<IllegalArgumentException> { properties(endpoint) }
        }
        val endpoint = LanEndpoint("10.1.2.3", 5432)
        assertFailsWith<IllegalArgumentException> {
            buildLanTxtProperties(PeerId("remote"), appId, "Remote", Platform.IOS, setOf(TransportKind.LAN),
                1, null, endpoint)
        }
        val legacy = properties(endpoint) - LanConstants.TXT_FINGERPRINT + (LanConstants.TXT_PROTOCOL_VERSION to "1")
        assertNull(validateLanDiscoveryRecord(legacy, appId, PeerId("local"),
            TransportSecurityProfile.LegacyPlaintextV1))
    }
}
