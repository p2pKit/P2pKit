package dev.p2pkit.core

import dev.p2pkit.core.security.CanonicalIdentityText
import kotlin.jvm.JvmInline

/**
 * Identifier of the application that this P2pKit instance belongs to.
 *
 * Discovery is scoped by [AppId]: peers advertising a different value are
 * filtered out before they reach [P2pKit.peers]. Use the same [AppId] on every
 * device of the same product.
 */
@JvmInline
public value class AppId(public val value: String) {
    init {
        require(value.isNotBlank()) { "AppId must not be blank" }
    }
}

/**
 * Stable identifier of a peer device.
 *
 * In authenticated protocol v2 this is a self-certifying, AppId-bound value
 * derived from the peer's persistent X25519 public key. It remains stable
 * while that secure identity is retained; an explicit identity reset changes
 * it and requires peers to pin the replacement identity. Explicit legacy mode
 * retains the original persisted UUID behavior for migration compatibility.
 */
@JvmInline
public value class PeerId(public val value: String) {
    init {
        require(value.isNotBlank()) { "PeerId must not be blank" }
    }
}

/**
 * Full, canonical fingerprint of an authenticated P2pKit v2 X25519 identity.
 *
 * The wire/security layer proves possession of the corresponding private key.
 * This value is the high-entropy pin applications exchange directly or in a
 * QR code; it is never a short human-entered pairing code. Canonical text is
 * `p2f1-` followed by 52 lowercase, unpadded Base32 characters.
 */
@JvmInline
public value class PeerFingerprint(public val value: String) {
    init {
        require(CanonicalIdentityText.isFingerprint(value)) {
            "PeerFingerprint must be canonical p2f1 Base32 text"
        }
    }

    override fun toString(): String = value

    public companion object {
        /** Parse exact canonical text or throw [IllegalArgumentException]. */
        public fun parse(value: String): PeerFingerprint = PeerFingerprint(value)

        /** Parse exact canonical text, returning `null` for every malformed form. */
        public fun parseOrNull(value: String): PeerFingerprint? =
            if (CanonicalIdentityText.isFingerprint(value)) PeerFingerprint(value) else null

        internal fun fromDigest(digest: ByteArray): PeerFingerprint =
            PeerFingerprint(CanonicalIdentityText.fingerprintFromDigest(digest))
    }

    internal fun digestBytes(): ByteArray =
        CanonicalIdentityText.decodeFingerprint(value)
}

/**
 * Canonical high-entropy pairing QR payload.
 *
 * Text is exactly `p2pkit:v2:<app-binding>:<fingerprint>`. Parsing this type
 * proves only canonical syntax. The security configuration additionally
 * compares [appBinding] with the binding derived from the local exact [AppId]
 * before treating [fingerprint] as an authorization pin.
 */
public data class PeerPairingQr(
    public val appBinding: String,
    public val fingerprint: PeerFingerprint
) {
    init {
        require(CanonicalIdentityText.isAppBinding(appBinding)) {
            "appBinding must be canonical p2a1 Base32 text"
        }
    }

    /** Return the exact canonical QR text. */
    public fun encode(): String = "p2pkit:v2:$appBinding:${fingerprint.value}"

    override fun toString(): String = encode()

    public companion object {
        private const val CANONICAL_TEXT_LENGTH: Int = 125

        /** Parse an exact canonical QR payload or throw [IllegalArgumentException]. */
        public fun parse(value: String): PeerPairingQr =
            parseOrNull(value) ?: throw IllegalArgumentException(
                "Pairing QR must be canonical p2pkit:v2:<app-binding>:<fingerprint> text"
            )

        /** Parse exact canonical text, returning `null` for every malformed form. */
        public fun parseOrNull(value: String): PeerPairingQr? {
            if (value.length != CANONICAL_TEXT_LENGTH) return null
            val parts = value.split(':')
            if (parts.size != 4 || parts[0] != "p2pkit" || parts[1] != "v2") return null
            if (!CanonicalIdentityText.isAppBinding(parts[2])) return null
            val fingerprint = PeerFingerprint.parseOrNull(parts[3]) ?: return null
            val parsed = PeerPairingQr(parts[2], fingerprint)
            return parsed.takeIf { it.encode() == value }
        }
    }
}

/**
 * Optional cryptographic identity of a peer after a security handshake.
 *
 * [fingerprint] is non-null for authenticated protocol v2 and null only for
 * the explicitly selected legacy plaintext migration mode.
 */
public data class PeerIdentity(
    val peerId: PeerId,
    val fingerprint: PeerFingerprint? = null
) {
    /** Source-migration alias for the pre-v2 string property. */
    @Deprecated(
        message = "Use the canonical typed fingerprint property.",
        replaceWith = ReplaceWith("fingerprint?.value")
    )
    public val publicKeyFingerprint: String? get() = fingerprint?.value
}
