package dev.p2pkit.transport.lan

import dev.p2pkit.core.PeerId
import kotlin.test.Test
import kotlin.test.assertEquals
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
    fun guardRejectsExactlyTheValuesPeerIdThrowsOn() {
        // Contract link: the guard must return null for exactly the inputs
        // the PeerId constructor rejects, so a guarded discovery callback
        // can never throw from the constructor.
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
}
