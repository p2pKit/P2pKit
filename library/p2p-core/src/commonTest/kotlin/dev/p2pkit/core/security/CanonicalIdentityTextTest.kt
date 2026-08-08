package dev.p2pkit.core.security

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerPairingQr
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNull

class CanonicalIdentityTextTest {
    @Test
    fun lowerUnpaddedBase32MatchesRfc4648Vectors() {
        assertEquals("", CanonicalIdentityText.encodeBase32(byteArrayOf()))
        assertEquals("my", CanonicalIdentityText.encodeBase32("f".encodeToByteArray()))
        assertEquals("mzxq", CanonicalIdentityText.encodeBase32("fo".encodeToByteArray()))
        assertEquals("mzxw6", CanonicalIdentityText.encodeBase32("foo".encodeToByteArray()))
        assertEquals("mzxw6yq", CanonicalIdentityText.encodeBase32("foob".encodeToByteArray()))
        assertEquals("mzxw6ytb", CanonicalIdentityText.encodeBase32("fooba".encodeToByteArray()))
        assertEquals("mzxw6ytboi", CanonicalIdentityText.encodeBase32("foobar".encodeToByteArray()))
    }

    @Test
    fun decoderRejectsEveryNonCanonicalVariant() {
        assertNull(CanonicalIdentityText.decodeBase32("MY"))
        assertNull(CanonicalIdentityText.decodeBase32("my======"))
        assertNull(CanonicalIdentityText.decodeBase32("m1"))
        assertNull(CanonicalIdentityText.decodeBase32("m y"))
        // For a 32-byte digest, four unused bits in the final Base32 symbol
        // must be zero. `b` makes those padding bits non-zero.
        assertNull(CanonicalIdentityText.decodeBase32("a".repeat(51) + "b"))
    }

    @Test
    fun fingerprintRequiresFullCanonicalDigest() {
        val canonical = "p2f1-" + "a".repeat(52)
        assertEquals(canonical, PeerFingerprint.parse(canonical).value)
        assertNull(PeerFingerprint.parseOrNull(canonical.uppercase()))
        assertNull(PeerFingerprint.parseOrNull(canonical + "="))
        assertNull(PeerFingerprint.parseOrNull("p2f1-" + "a".repeat(51)))
        assertFailsWith<IllegalArgumentException> { PeerFingerprint("p2f1-short") }
    }

    @Test
    fun qrParserRequiresExactlyFourCanonicalFields() {
        val binding = "p2a1-" + "a".repeat(52)
        val fingerprint = PeerFingerprint("p2f1-" + "a".repeat(52))
        val canonical = "p2pkit:v2:$binding:${fingerprint.value}"
        val parsed = PeerPairingQr.parse(canonical)

        assertEquals(binding, parsed.appBinding)
        assertEquals(fingerprint, parsed.fingerprint)
        assertEquals(canonical, parsed.encode())
        assertNull(PeerPairingQr.parseOrNull(" $canonical"))
        assertNull(PeerPairingQr.parseOrNull("$canonical "))
        assertNull(PeerPairingQr.parseOrNull("p2pkit:v1:$binding:${fingerprint.value}"))
        assertNull(PeerPairingQr.parseOrNull("$canonical:extra"))
        assertNull(PeerPairingQr.parseOrNull(canonical + "x".repeat(10_000)))
        assertNull(PeerPairingQr.parseOrNull("p2pkit:v2:${binding.uppercase()}:${fingerprint.value}"))
    }
}
