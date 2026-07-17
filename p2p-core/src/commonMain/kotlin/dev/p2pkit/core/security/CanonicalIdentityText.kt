package dev.p2pkit.core.security

/** Strict lowercase, unpadded RFC 4648 Base32 used by v2 identity text. */
internal object CanonicalIdentityText {
    private const val DIGEST_SIZE = 32
    private const val ENCODED_DIGEST_SIZE = 52
    private const val FINGERPRINT_PREFIX = "p2f1-"
    private const val APP_BINDING_PREFIX = "p2a1-"
    private const val PEER_ID_PREFIX = "p2id2-"
    private const val ALPHABET = "abcdefghijklmnopqrstuvwxyz234567"

    fun isFingerprint(value: String): Boolean =
        isCanonicalDigest(value, FINGERPRINT_PREFIX)

    fun isAppBinding(value: String): Boolean =
        isCanonicalDigest(value, APP_BINDING_PREFIX)

    fun fingerprintFromDigest(digest: ByteArray): String =
        formatDigest(FINGERPRINT_PREFIX, digest)

    fun appBindingFromDigest(digest: ByteArray): String =
        formatDigest(APP_BINDING_PREFIX, digest)

    fun peerIdFromDigest(digest: ByteArray): String =
        formatDigest(PEER_ID_PREFIX, digest)

    fun decodeFingerprint(value: String): ByteArray =
        decodeCanonicalDigest(value, FINGERPRINT_PREFIX)

    fun decodeAppBinding(value: String): ByteArray =
        decodeCanonicalDigest(value, APP_BINDING_PREFIX)

    internal fun encodeBase32(bytes: ByteArray): String {
        if (bytes.isEmpty()) return ""
        val out = StringBuilder((bytes.size * 8 + 4) / 5)
        var buffer = 0
        var bits = 0
        for (byte in bytes) {
            buffer = (buffer shl 8) or (byte.toInt() and 0xff)
            bits += 8
            while (bits >= 5) {
                bits -= 5
                out.append(ALPHABET[(buffer ushr bits) and 0x1f])
            }
            buffer = buffer and ((1 shl bits) - 1)
        }
        if (bits != 0) out.append(ALPHABET[(buffer shl (5 - bits)) and 0x1f])
        return out.toString()
    }

    internal fun decodeBase32(value: String): ByteArray? {
        if (value.isEmpty()) return ByteArray(0)
        val outputSize = value.length * 5 / 8
        val out = ByteArray(outputSize)
        var outputIndex = 0
        var buffer = 0
        var bits = 0
        for (char in value) {
            val decoded = when (char) {
                in 'a'..'z' -> char.code - 'a'.code
                in '2'..'7' -> char.code - '2'.code + 26
                else -> return null
            }
            buffer = (buffer shl 5) or decoded
            bits += 5
            if (bits >= 8) {
                bits -= 8
                if (outputIndex >= out.size) return null
                out[outputIndex++] = (buffer ushr bits).toByte()
                buffer = buffer and ((1 shl bits) - 1)
            }
        }
        if (outputIndex != out.size || buffer != 0) return null
        return out.takeIf { encodeBase32(it) == value }
    }

    private fun formatDigest(prefix: String, digest: ByteArray): String {
        require(digest.size == DIGEST_SIZE) { "identity digest must be 32 bytes" }
        return prefix + encodeBase32(digest)
    }

    private fun isCanonicalDigest(value: String, prefix: String): Boolean {
        if (value.length != prefix.length + ENCODED_DIGEST_SIZE || !value.startsWith(prefix)) {
            return false
        }
        return decodeBase32(value.substring(prefix.length))?.size == DIGEST_SIZE
    }

    private fun decodeCanonicalDigest(value: String, prefix: String): ByteArray {
        require(isCanonicalDigest(value, prefix)) { "identity text is not canonical" }
        return checkNotNull(decodeBase32(value.substring(prefix.length)))
    }
}
