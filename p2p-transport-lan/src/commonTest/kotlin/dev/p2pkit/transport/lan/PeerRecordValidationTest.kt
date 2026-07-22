package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.PeerAuthenticationHint
import dev.p2pkit.core.transport.DiscoveryLifetime
import dev.p2pkit.core.transport.TransportHint
import dev.p2pkit.core.transport.discoveryLifetime
import dev.p2pkit.core.transport.TransportSecurityProfile
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull

/**
 * AUDIT-2026-07 (RBS-1) / P1-25 unit leg: pins [validDiscoveryPeerIdOrNull],
 * the shared input-validation guard every platform discovery transport
 * applies (found and lost paths) before a TXT `pid` value reaches the
 * throwing [PeerId] constructor.
 *
 * Runs on every target (JVM, Android, iOS), so the guard's behavior parity
 * is pinned once for all three transports. The platform callbacks' use of
 * the guard is covered by the JVM crafted-advertiser loopback test
 * (`JvmDiscoveryRecordValidationTest`) and the iOS TXT-record decode tests
 * (`IosBonjourTest`).
 */
class PeerRecordValidationTest {

    @Test
    fun lanRecordUsesNativeTtlLifetimeAndRetainsAllRoutingCandidates() {
        val record = assertNotNull(
            validateLanDiscoveryRecord(
                legacyProperties(),
                AppId("app"),
                PeerId("local"),
                TransportSecurityProfile.LegacyPlaintextV1
            )
        )
        val hints = listOf(
            TransportHint(TransportKind.LAN, "192.168.1.10", 9000),
            TransportHint(TransportKind.LAN, "192.168.1.11", 9000)
        )

        val peer = record.toInternalPeer(hints)

        assertEquals(DiscoveryLifetime.TransportManaged, peer.discoveryLifetime())
        assertEquals(hints.map { it.host }, peer.transportHints.map { it.host })
    }

    @Test
    fun absentPeerIdIsRejected() {
        assertNull(validDiscoveryPeerIdOrNull(null))
    }

    @Test
    fun emptyPeerIdIsRejected() {
        assertNull(validDiscoveryPeerIdOrNull(""))
    }

    @Test
    fun whitespaceOnlyPeerIdsAreRejected() {
        assertNull(validDiscoveryPeerIdOrNull(" "))
        assertNull(validDiscoveryPeerIdOrNull("   "))
        assertNull(validDiscoveryPeerIdOrNull("\t"))
        assertNull(validDiscoveryPeerIdOrNull("\n"))
        assertNull(validDiscoveryPeerIdOrNull(" \t\r\n "))
    }

    @Test
    fun conformingPeerIdPassesThroughUnchanged() {
        val uuid = "11111111-2222-3333-4444-555555555555"
        assertEquals(uuid, validDiscoveryPeerIdOrNull(uuid))
    }

    @Test
    fun peerIdWithSurroundingWhitespaceIsNotNormalized() {
        // The guard validates only; it must not rewrite identity. A value
        // with surrounding whitespace is non-blank, so it passes through
        // verbatim — exactly the value PeerId() accepts today.
        assertEquals(" abc ", validDiscoveryPeerIdOrNull(" abc "))
    }

    @Test
    fun guardAcceptsEveryBoundedSafeValueAcceptedByPeerId() {
        // Discovery imposes wire and diagnostic bounds beyond PeerId's local
        // value-object invariant. Within those bounds, it must preserve every
        // value PeerId accepts without normalization.
        val samples = listOf("", " ", "  ", "\t\n", "x", " x", "uuid-ish-value")
        for (sample in samples) {
            val guardAccepts = validDiscoveryPeerIdOrNull(sample) != null
            val constructorAccepts = runCatching { PeerId(sample) }.isSuccess
            assertEquals(
                constructorAccepts,
                guardAccepts,
                "guard/constructor disagreement on bytes=${sample.encodeToByteArray().toList()}"
            )
        }
    }

    @Test
    fun secureRecordRequiresExactV2AndCanonicalFingerprint() {
        val fingerprint = "p2f1-${"a".repeat(52)}"
        val metadata = validateLanDiscoverySecurityMetadata(
            profile = TransportSecurityProfile.AuthenticatedV2,
            protocolVersion = "2",
            fingerprint = fingerprint
        )

        val claim = assertIs<PeerAuthenticationHint.UntrustedDiscoveryClaim>(
            metadata?.authenticationHint
        )
        assertEquals(fingerprint, claim.fingerprint.value)
    }

    @Test
    fun secureRecordRejectsMissingMalformedOrWrongVersionMetadata() {
        assertNull(
            validateLanDiscoverySecurityMetadata(
                TransportSecurityProfile.AuthenticatedV2,
                protocolVersion = "2",
                fingerprint = null
            )
        )
        assertNull(
            validateLanDiscoverySecurityMetadata(
                TransportSecurityProfile.AuthenticatedV2,
                protocolVersion = "2",
                fingerprint = "p2f1-not-canonical"
            )
        )
        assertNull(
            validateLanDiscoverySecurityMetadata(
                TransportSecurityProfile.AuthenticatedV2,
                protocolVersion = "1",
                fingerprint = "p2f1-${"a".repeat(52)}"
            )
        )
    }

    @Test
    fun legacyRecordAcceptsOnlyExactV1WithoutFingerprint() {
        val valid = validateLanDiscoverySecurityMetadata(
            TransportSecurityProfile.LegacyPlaintextV1,
            protocolVersion = "1",
            fingerprint = null
        )
        assertNotNull(valid)
        assertEquals(null, valid.authenticationHint)
        assertNull(
            validateLanDiscoverySecurityMetadata(
                TransportSecurityProfile.LegacyPlaintextV1,
                protocolVersion = "2",
                fingerprint = null
            )
        )
        assertNull(
            validateLanDiscoverySecurityMetadata(
                TransportSecurityProfile.LegacyPlaintextV1,
                protocolVersion = "1",
                fingerprint = "p2f1-${"a".repeat(52)}"
            )
        )
    }

    @Test
    fun localTxtBuilderRejectsOversizedIdentityFieldsAndTruncatesOnlyDisplayName() {
        assertFailsWith<IllegalArgumentException> {
            buildLanTxtProperties(
                peerId = PeerId("p".repeat(252)),
                appId = AppId("app"),
                deviceName = "device",
                platform = Platform.UNKNOWN,
                supportedTransports = setOf(TransportKind.LAN),
                protocolVersion = 1,
                fingerprint = null
            )
        }
        assertFailsWith<IllegalArgumentException> {
            buildLanTxtProperties(
                peerId = PeerId("peer"),
                appId = AppId("a".repeat(252)),
                deviceName = "device",
                platform = Platform.UNKNOWN,
                supportedTransports = setOf(TransportKind.LAN),
                protocolVersion = 1,
                fingerprint = null
            )
        }
        assertFailsWith<IllegalArgumentException> {
            buildLanTxtProperties(
                peerId = PeerId("peer"),
                appId = AppId("app"),
                deviceName = "device",
                platform = Platform.UNKNOWN,
                supportedTransports = setOf(TransportKind.BLE),
                protocolVersion = 1,
                fingerprint = null
            )
        }

        val properties = buildLanTxtProperties(
            peerId = PeerId("peer"),
            appId = AppId("app"),
            deviceName = "🙂".repeat(100),
            platform = Platform.UNKNOWN,
            supportedTransports = setOf(TransportKind.LAN),
            protocolVersion = 1,
            fingerprint = null
        )
        val boundedName = properties.getValue(LanConstants.TXT_DEVICE_NAME)
        assertEquals(0, boundedName.encodeToByteArray().size % 4)
        assertEquals(true, lanTxtEntryFits(LanConstants.TXT_DEVICE_NAME, boundedName))
        assertEquals(62, boundedName.length / 2)
    }

    @Test
    fun completeRecordParserRejectsOversizeControlsAndWrongApp() {
        val valid = legacyProperties()
        assertNotNull(
            validateLanDiscoveryRecord(
                valid,
                AppId("app"),
                PeerId("local"),
                TransportSecurityProfile.LegacyPlaintextV1
            )
        )
        assertNull(
            validateLanDiscoveryRecord(
                valid + (LanConstants.TXT_DEVICE_NAME to "spoof\u001B[31m"),
                AppId("app"),
                PeerId("local"),
                TransportSecurityProfile.LegacyPlaintextV1
            )
        )
        assertNull(
            validateLanDiscoveryRecord(
                valid + (LanConstants.TXT_DEVICE_NAME to "x".repeat(251)),
                AppId("app"),
                PeerId("local"),
                TransportSecurityProfile.LegacyPlaintextV1
            )
        )
        assertNull(
            validateLanDiscoveryRecord(
                valid,
                AppId("another-app"),
                PeerId("local"),
                TransportSecurityProfile.LegacyPlaintextV1
            )
        )
        assertNull(
            validateLanDiscoveryRecord(
                valid + (
                    LanConstants.TXT_CAPABILITIES to
                        List(33) { TransportKind.LAN.name }.joinToString(",")
                    ),
                AppId("app"),
                PeerId("local"),
                TransportSecurityProfile.LegacyPlaintextV1
            )
        )
        assertNull(
            validateLanDiscoveryRecord(
                valid + (LanConstants.TXT_CAPABILITIES to TransportKind.BLE.name),
                AppId("app"),
                PeerId("local"),
                TransportSecurityProfile.LegacyPlaintextV1
            )
        )

        val optionalNulls = valid + mapOf(
            LanConstants.TXT_DEVICE_NAME to null,
            LanConstants.TXT_PLATFORM to null,
            LanConstants.TXT_CAPABILITIES to null,
            LanConstants.TXT_FINGERPRINT to null
        )
        val parsed = assertNotNull(
            validateLanDiscoveryRecord(
                optionalNulls,
                AppId("app"),
                PeerId("local"),
                TransportSecurityProfile.LegacyPlaintextV1
            )
        )
        assertEquals("remote", parsed.deviceName)
        assertEquals(Platform.UNKNOWN, parsed.platform)
        assertEquals(setOf(TransportKind.LAN), parsed.supportedTransports)
    }

    @Test
    fun diagnosticsReplaceControlsAndBoundPeerInput() {
        val safe = sanitizeLanDiagnostic("peer\u001B[31m\u202Ename" + "x".repeat(300))
        assertEquals(false, '\u001B' in safe)
        assertEquals(false, '\u202E' in safe)
        assertEquals(true, '\uFFFD' in safe)
        assertEquals(160, safe.length)

        val emojiBoundary = sanitizeLanDiagnostic("x".repeat(159) + "🙂")
        assertEquals(159, emojiBoundary.length)
        assertEquals(false, emojiBoundary.last().isHighSurrogate())

        val malformed = sanitizeLanDiagnostic("peer\uD800name")
        assertEquals(true, '\uFFFD' in malformed)
    }

    private fun legacyProperties(): Map<String, String?> = mapOf(
        LanConstants.TXT_PEER_ID to "remote",
        LanConstants.TXT_APP_ID to "app",
        LanConstants.TXT_DEVICE_NAME to "Remote",
        LanConstants.TXT_PLATFORM to Platform.JVM_DESKTOP.name,
        LanConstants.TXT_CAPABILITIES to TransportKind.LAN.name,
        LanConstants.TXT_PROTOCOL_VERSION to "1"
    )
}
