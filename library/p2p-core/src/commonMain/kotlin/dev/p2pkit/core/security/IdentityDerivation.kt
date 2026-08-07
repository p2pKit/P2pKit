package dev.p2pkit.core.security

import dev.p2pkit.core.AppId
import dev.p2pkit.core.LocalIdentityFailureKind
import dev.p2pkit.core.LocalIdentityRecovery
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.PeerPairingQr
import kotlinx.coroutines.CancellationException

internal object IdentityDerivation {
    private val namespaceLabel = "dev.p2pkit.identity-namespace.v2\u0000".encodeToByteArray()
    private val fingerprintLabel = "dev.p2pkit.x25519-fingerprint.v1\u0000".encodeToByteArray()
    private val peerIdLabel = "dev.p2pkit.peer-id.v2\u0000".encodeToByteArray()
    private val appBindingLabel = "dev.p2pkit.app-binding.v1\u0000".encodeToByteArray()

    fun namespace(appId: AppId, cryptography: IdentityCryptography): IdentityNamespace {
        if (!appId.value.isWellFormedUtf16()) {
            throw P2pError.SecurityConfigurationInvalid(
                "Secure v2 AppId must contain well-formed Unicode"
            )
        }
        val appIdBytes = appId.value.encodeToByteArray()
        if (appIdBytes.size > UShort.MAX_VALUE.toInt()) {
            throw P2pError.SecurityConfigurationInvalid(
                "Secure v2 AppId UTF-8 encoding must fit an unsigned 16-bit length"
            )
        }
        val hash = sha256(
            cryptography,
            concatenate(namespaceLabel, u16be(appIdBytes.size), appIdBytes)
        )
        return IdentityNamespace(appId, appIdBytes, hash)
    }

    fun fingerprintDigest(
        publicKey: ByteArray,
        cryptography: IdentityCryptography
    ): ByteArray {
        require(publicKey.size == X25519_KEY_SIZE_BYTES) { "X25519 public key must be 32 bytes" }
        return sha256(cryptography, concatenate(fingerprintLabel, publicKey))
    }

    fun fingerprint(
        publicKey: ByteArray,
        cryptography: IdentityCryptography
    ): PeerFingerprint = PeerFingerprint.fromDigest(fingerprintDigest(publicKey, cryptography))

    fun peerId(
        namespace: IdentityNamespace,
        fingerprintDigest: ByteArray,
        cryptography: IdentityCryptography
    ): PeerId {
        require(fingerprintDigest.size == SHA256_SIZE_BYTES) {
            "fingerprint digest must be 32 bytes"
        }
        val appIdBytes = namespace.appIdBytes()
        val digest = sha256(
            cryptography,
            concatenate(peerIdLabel, u16be(appIdBytes.size), appIdBytes, fingerprintDigest)
        )
        return PeerId(CanonicalIdentityText.peerIdFromDigest(digest))
    }

    fun appBinding(
        namespace: IdentityNamespace,
        cryptography: IdentityCryptography
    ): String {
        val appIdBytes = namespace.appIdBytes()
        val digest = sha256(
            cryptography,
            concatenate(appBindingLabel, u16be(appIdBytes.size), appIdBytes)
        )
        return CanonicalIdentityText.appBindingFromDigest(digest)
    }

    fun pairingQr(
        namespace: IdentityNamespace,
        fingerprint: PeerFingerprint,
        cryptography: IdentityCryptography
    ): PeerPairingQr = PeerPairingQr(appBinding(namespace, cryptography), fingerprint)

    /** Parse a QR and require its full AppId binding to match in constant time. */
    fun parsePairingQr(
        value: String,
        namespace: IdentityNamespace,
        cryptography: IdentityCryptography
    ): PeerFingerprint? {
        val parsed = PeerPairingQr.parseOrNull(value) ?: return null
        val expected = CanonicalIdentityText.decodeAppBinding(appBinding(namespace, cryptography))
        val actual = CanonicalIdentityText.decodeAppBinding(parsed.appBinding)
        return try {
            parsed.fingerprint.takeIf { constantTimeEquals(expected, actual) }
        } finally {
            expected.fill(0)
            actual.fill(0)
        }
    }

    private fun sha256(cryptography: IdentityCryptography, input: ByteArray): ByteArray {
        val digest = try {
            cryptography.sha256(input)
        } catch (e: P2pError.LocalIdentityUnavailable) {
            throw e
        } catch (e: CancellationException) {
            throw e
        } catch (e: Exception) {
            throw localIdentityError(
                kind = LocalIdentityFailureKind.CRYPTO_PROVIDER_UNAVAILABLE,
                recovery = LocalIdentityRecovery.FIX_PLATFORM_CONFIGURATION,
                reason = "SHA-256 provider failed",
                cause = e
            )
        } finally {
            input.fill(0)
        }
        if (digest.size != SHA256_SIZE_BYTES) {
            digest.fill(0)
            throw localIdentityError(
                kind = LocalIdentityFailureKind.STORE_CONTRACT_VIOLATION,
                recovery = LocalIdentityRecovery.FIX_PLATFORM_CONFIGURATION,
                reason = "SHA-256 provider returned a non-32-byte digest"
            )
        }
        return try {
            digest.copyOf()
        } finally {
            digest.fill(0)
        }
    }
}

private fun String.isWellFormedUtf16(): Boolean {
    var index = 0
    while (index < length) {
        when (this[index].code) {
            in 0xd800..0xdbff -> {
                if (index + 1 >= length || this[index + 1].code !in 0xdc00..0xdfff) return false
                index += 2
            }
            in 0xdc00..0xdfff -> return false
            else -> index++
        }
    }
    return true
}

internal fun u16be(value: Int): ByteArray {
    require(value in 0..UShort.MAX_VALUE.toInt()) { "value does not fit U16" }
    return byteArrayOf((value ushr 8).toByte(), value.toByte())
}

internal fun concatenate(vararg values: ByteArray): ByteArray {
    var size = 0
    for (value in values) {
        require(size <= Int.MAX_VALUE - value.size) { "byte concatenation overflow" }
        size += value.size
    }
    val result = ByteArray(size)
    var offset = 0
    for (value in values) {
        value.copyInto(result, offset)
        offset += value.size
    }
    return result
}

internal fun localIdentityError(
    kind: LocalIdentityFailureKind,
    recovery: LocalIdentityRecovery,
    reason: String,
    cause: Throwable? = null
): P2pError.LocalIdentityUnavailable =
    P2pError.LocalIdentityUnavailable(kind, recovery, reason).also { it.underlying = cause }
