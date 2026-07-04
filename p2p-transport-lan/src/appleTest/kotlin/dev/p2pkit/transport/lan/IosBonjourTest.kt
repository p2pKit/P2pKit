package dev.p2pkit.transport.lan

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNull
import kotlin.test.assertTrue

/**
 * Unit tests for the iOS Bonjour TXT-record helpers.
 *
 * Round-trip on every input we plausibly ship over the wire:
 * - The six `LanConstants.TXT_*` keys (the only keys the discovery
 *   transport advertises today).
 * - Empty values (key present, value blank).
 * - Unicode values (device names — surrogate pairs in emoji, non-ASCII
 *   in international names).
 * - Null record reference (decode-side).
 *
 * Also verifies that the discovery filter contract in
 * `IosLanDiscoveryTransport.emitPeer` — "drop peers missing TXT_PEER_ID
 * or TXT_APP_ID" — survives a missing-key TXT round-trip.
 */
class IosBonjourTest {

    @Test
    fun emptyMapRoundTrips() {
        val record = IosBonjour.mapToTxtRecord(emptyMap())
        val decoded = IosBonjour.txtRecordToMap(record)
        assertEquals(emptyMap(), decoded)
    }

    @Test
    fun fullLanConstantsKeySetRoundTrips() {
        val original = mapOf(
            LanConstants.TXT_PEER_ID to "11111111-2222-3333-4444-555555555555",
            LanConstants.TXT_APP_ID to "p2pkit-test-app",
            LanConstants.TXT_DEVICE_NAME to "iPhone 17 Pro",
            LanConstants.TXT_PLATFORM to "IOS",
            LanConstants.TXT_CAPABILITIES to "LAN",
            LanConstants.TXT_PROTOCOL_VERSION to "1"
        )
        val record = IosBonjour.mapToTxtRecord(original)
        val decoded = IosBonjour.txtRecordToMap(record)
        assertEquals(original, decoded)
    }

    @Test
    fun emptyValueRoundTripsAsEmptyString() {
        val original = mapOf(LanConstants.TXT_DEVICE_NAME to "")
        val record = IosBonjour.mapToTxtRecord(original)
        val decoded = IosBonjour.txtRecordToMap(record)
        assertEquals(original, decoded)
    }

    @Test
    fun unicodeValueRoundTrips() {
        // Emoji = surrogate pair; Greek letters = multi-byte UTF-8; mix.
        val original = mapOf(
            LanConstants.TXT_DEVICE_NAME to "📱 iPhone αβγ δέ"
        )
        val record = IosBonjour.mapToTxtRecord(original)
        val decoded = IosBonjour.txtRecordToMap(record)
        assertEquals(original, decoded)
    }

    @Test
    fun nullRecordDecodesToEmptyMap() {
        // nw_browse_result_copy_txt_record_object returns null for services
        // that advertised without a TXT record. Decoding must not crash.
        assertEquals(emptyMap(), IosBonjour.txtRecordToMap(null))
    }

    @Test
    fun missingPeerIdDropsPeerInDiscoveryFilter() {
        // Encodes a TXT with everything EXCEPT pid — same shape a foreign
        // _p2pkit._tcp advertiser without our protocol could emit. The
        // discovery filter in IosLanDiscoveryTransport.emitPeer does
        // `attrs[TXT_PEER_ID] ?: return` — make sure the decode step
        // preserves the missing-key signal (i.e., decoded map has no
        // TXT_PEER_ID entry) so the filter actually fires.
        val partial = mapOf(
            LanConstants.TXT_APP_ID to "p2pkit-test",
            LanConstants.TXT_DEVICE_NAME to "Rogue"
        )
        val record = IosBonjour.mapToTxtRecord(partial)
        val decoded = IosBonjour.txtRecordToMap(record)
        assertEquals(partial, decoded)
        assertTrue(LanConstants.TXT_PEER_ID !in decoded)
    }

    @Test
    fun missingAppIdDropsPeerInDiscoveryFilter() {
        // Symmetric to the pid-missing case: the discovery filter requires
        // both pid and app present and matching local appId.
        val partial = mapOf(
            LanConstants.TXT_PEER_ID to "stranger-uuid",
            LanConstants.TXT_DEVICE_NAME to "Stranger"
        )
        val record = IosBonjour.mapToTxtRecord(partial)
        val decoded = IosBonjour.txtRecordToMap(record)
        assertEquals(partial, decoded)
        assertTrue(LanConstants.TXT_APP_ID !in decoded)
    }

    @Test
    fun unknownKeysSurviveRoundTripAndAreIgnoredByFilter() {
        // A future-version peer might add new TXT keys. We should still
        // decode the message (forward compat) without dropping the peer if
        // pid+app are present. The discovery filter ignores unknown keys.
        val withExtra = mapOf(
            LanConstants.TXT_PEER_ID to "valid-pid",
            LanConstants.TXT_APP_ID to "p2pkit-test",
            "future-key-1" to "value",
            "future-key-2" to ""
        )
        val record = IosBonjour.mapToTxtRecord(withExtra)
        val decoded = IosBonjour.txtRecordToMap(record)
        assertEquals(withExtra, decoded)
    }

    @Test
    fun blankPeerIdValueIsRejectedByDiscoveryValidation() {
        // AUDIT-2026-07 (RBS-1) / P1-25 iOS leg: a same-service-type
        // advertiser can publish a whitespace-only pid value. It survives the
        // real nw_txt_record round-trip verbatim, so the discovery transport
        // must drop the record via validDiscoveryPeerIdOrNull (emitPeer and
        // emitLost both funnel through it) instead of letting PeerId() throw
        // across the nw_browser callback boundary.
        val malformed = mapOf(
            LanConstants.TXT_PEER_ID to " ",
            LanConstants.TXT_APP_ID to "p2pkit-test"
        )
        val decoded = IosBonjour.txtRecordToMap(IosBonjour.mapToTxtRecord(malformed))
        assertEquals(" ", decoded[LanConstants.TXT_PEER_ID])
        assertNull(validDiscoveryPeerIdOrNull(decoded[LanConstants.TXT_PEER_ID]))
    }

    @Test
    fun emptyPeerIdValueIsRejectedAndConformingPeerIdAccepted() {
        // Key-present-empty-value and key-without-value both decode to ""
        // (see txtRecordToMap) — the validation guard must reject that
        // shape too, while a conforming pid passes through untouched.
        val malformed = mapOf(LanConstants.TXT_PEER_ID to "")
        val decoded = IosBonjour.txtRecordToMap(IosBonjour.mapToTxtRecord(malformed))
        assertEquals("", decoded[LanConstants.TXT_PEER_ID])
        assertNull(validDiscoveryPeerIdOrNull(decoded[LanConstants.TXT_PEER_ID]))

        val conforming = mapOf(
            LanConstants.TXT_PEER_ID to "11111111-2222-3333-4444-555555555555"
        )
        val conformingDecoded = IosBonjour.txtRecordToMap(IosBonjour.mapToTxtRecord(conforming))
        assertEquals(
            "11111111-2222-3333-4444-555555555555",
            validDiscoveryPeerIdOrNull(conformingDecoded[LanConstants.TXT_PEER_ID])
        )
    }

    @Test
    fun longUtf8ValueRoundTrips() {
        // A device name field of ~150 chars exercises the value-length
        // path. Bonjour TXT key+value pairs are capped at 255 bytes total;
        // this stays under that, well above any reasonable device name.
        val longName = "Abdo's Phone — Project P2pKit v0.3.0-dev macOS test, " +
            "running NSDate.timeIntervalSince1970 suite"
        val original = mapOf(LanConstants.TXT_DEVICE_NAME to longName)
        val record = IosBonjour.mapToTxtRecord(original)
        val decoded = IosBonjour.txtRecordToMap(record)
        assertEquals(original, decoded)
    }
}
