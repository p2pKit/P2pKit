package dev.p2pkit.core.security

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId

internal const val X25519_KEY_SIZE_BYTES: Int = 32
internal const val SHA256_SIZE_BYTES: Int = 32

/** Exact, collision-resistant storage namespace for one [AppId]. */
internal class IdentityNamespace(
    val appId: AppId,
    appIdBytes: ByteArray,
    hash: ByteArray
) {
    private val appIdBytesOwned = appIdBytes.copyOf()
    private val hashOwned = hash.copyOf()

    init {
        require(appIdBytesOwned.contentEquals(appId.value.encodeToByteArray())) {
            "identity namespace AppId bytes do not match AppId"
        }
        require(hashOwned.size == SHA256_SIZE_BYTES) {
            "identity namespace hash must be 32 bytes"
        }
    }

    val storageKey: String = hashOwned.toLowerHex()

    fun appIdBytes(): ByteArray = appIdBytesOwned.copyOf()

    fun hashBytes(): ByteArray = hashOwned.copyOf()
}

/** Provider-independent canonical raw X25519 keypair. */
internal class EncodedIdentityKeyPair(
    privateKey: ByteArray,
    publicKey: ByteArray
) {
    private val privateKeyOwned = privateKey.copyOf()
    private val publicKeyOwned = publicKey.copyOf()

    init {
        require(privateKeyOwned.size == X25519_KEY_SIZE_BYTES) {
            "X25519 private key must be 32 bytes"
        }
        require(publicKeyOwned.size == X25519_KEY_SIZE_BYTES) {
            "X25519 public key must be 32 bytes"
        }
    }

    fun privateKeyBytes(): ByteArray = privateKeyOwned.copyOf()

    fun publicKeyBytes(): ByteArray = publicKeyOwned.copyOf()

    /** Best-effort clearing of the bytes owned by this value. */
    fun clearPrivate() {
        privateKeyOwned.fill(0)
    }
}

/** Fully validated local secure identity returned to kit construction. */
internal class LocalSecureIdentity(
    val peerId: PeerId,
    val fingerprint: PeerFingerprint,
    val keyPair: EncodedIdentityKeyPair
) {
    fun clearPrivate() {
        keyPair.clearPrivate()
    }
}

/** Primitive-provider boundary; platform/provider code supplies the implementation. */
internal interface IdentityCryptography {
    fun sha256(bytes: ByteArray): ByteArray

    fun generateX25519KeyPair(): EncodedIdentityKeyPair

    fun deriveX25519PublicKey(privateKey: ByteArray): ByteArray
}

internal fun constantTimeEquals(left: ByteArray, right: ByteArray): Boolean {
    var difference = left.size xor right.size
    val commonSize = minOf(left.size, right.size)
    for (index in 0 until commonSize) {
        difference = difference or (left[index].toInt() xor right[index].toInt())
    }
    // Preserve fixed work for the security values used here (all are 32 bytes)
    // even if a faulty provider returns the wrong size.
    for (index in commonSize until left.size) {
        difference = difference or (left[index].toInt() xor 0)
    }
    for (index in commonSize until right.size) {
        difference = difference or (right[index].toInt() xor 0)
    }
    return difference == 0
}

internal fun ByteArray.toLowerHex(): String {
    val alphabet = "0123456789abcdef"
    val result = CharArray(size * 2)
    for (index in indices) {
        val value = this[index].toInt() and 0xff
        result[index * 2] = alphabet[value ushr 4]
        result[index * 2 + 1] = alphabet[value and 0x0f]
    }
    return result.concatToString()
}
