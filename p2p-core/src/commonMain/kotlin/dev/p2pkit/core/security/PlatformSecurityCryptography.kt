package dev.p2pkit.core.security

import dev.p2pkit.core.internal.security.noise.NoiseCryptography
import dev.p2pkit.core.internal.security.noise.wipe
import dev.whyoleg.cryptography.CryptographyProvider
import dev.whyoleg.cryptography.DelicateCryptographyApi
import dev.whyoleg.cryptography.algorithms.ChaCha20Poly1305
import dev.whyoleg.cryptography.algorithms.HMAC
import dev.whyoleg.cryptography.algorithms.SHA256
import dev.whyoleg.cryptography.algorithms.XDH

/** One explicit provider selection shared by identity and Noise operations. */
internal interface PlatformSecurityCryptography : IdentityCryptography, NoiseCryptography

internal expect fun platformSecurityCryptography(): PlatformSecurityCryptography

/**
 * Provider-independent adapter. Platform factories pass an explicit provider;
 * this code deliberately never consults CryptographyProvider.Default.
 */
@OptIn(DelicateCryptographyApi::class)
internal class ProviderSecurityCryptography(
    provider: CryptographyProvider,
) : PlatformSecurityCryptography {
    private val digest = provider.get(SHA256)
    private val hmac = provider.get(HMAC)
    private val xdh = provider.get(XDH)
    private val chacha20Poly1305 = provider.get(ChaCha20Poly1305)

    override fun sha256(bytes: ByteArray): ByteArray {
        val output = digest.hasher().hashBlocking(bytes)
        return try {
            requireSha256(output)
            output
        } catch (cause: Exception) {
            output.wipe()
            throw cause
        }
    }

    override fun generateX25519KeyPair(): EncodedIdentityKeyPair {
        val keyPair = xdh.keyPairGenerator(XDH.Curve.X25519).generateKeyBlocking()
        var privateKey: ByteArray? = null
        var publicKey: ByteArray? = null
        return try {
            val privateBytes = keyPair.privateKey.encodeToByteArrayBlocking(XDH.PrivateKey.Format.RAW)
            privateKey = privateBytes
            val publicBytes = keyPair.publicKey.encodeToByteArrayBlocking(XDH.PublicKey.Format.RAW)
            publicKey = publicBytes
            requireX25519Private(privateBytes)
            requireX25519Public(publicBytes)
            EncodedIdentityKeyPair(privateBytes, publicBytes)
        } finally {
            privateKey?.wipe()
            publicKey?.wipe()
        }
    }

    override fun deriveX25519PublicKey(privateKey: ByteArray): ByteArray {
        requireX25519Private(privateKey)
        val decoded = xdh.privateKeyDecoder(XDH.Curve.X25519)
            .decodeFromByteArrayBlocking(XDH.PrivateKey.Format.RAW, privateKey)
        val output = decoded.getPublicKeyBlocking()
            .encodeToByteArrayBlocking(XDH.PublicKey.Format.RAW)
        return try {
            requireX25519Public(output)
            output
        } catch (cause: Exception) {
            output.wipe()
            throw cause
        }
    }

    override fun hmacSha256(key: ByteArray, data: ByteArray): ByteArray {
        val output = hmac.keyDecoder(SHA256)
            .decodeFromByteArrayBlocking(HMAC.Key.Format.RAW, key)
            .signatureGenerator()
            .generateSignatureBlocking(data)
        return try {
            requireSha256(output)
            output
        } catch (cause: Exception) {
            output.wipe()
            throw cause
        }
    }

    override fun x25519(privateKey: ByteArray, publicKey: ByteArray): ByteArray {
        requireX25519Private(privateKey)
        requireX25519Public(publicKey)
        val decodedPrivate = xdh.privateKeyDecoder(XDH.Curve.X25519)
            .decodeFromByteArrayBlocking(XDH.PrivateKey.Format.RAW, privateKey)
        val decodedPublic = xdh.publicKeyDecoder(XDH.Curve.X25519)
            .decodeFromByteArrayBlocking(XDH.PublicKey.Format.RAW, publicKey)
        val output = decodedPrivate.sharedSecretGenerator()
            .generateSharedSecretToByteArrayBlocking(decodedPublic)
        return try {
            requireX25519Secret(output)
            output
        } catch (cause: Exception) {
            output.wipe()
            throw cause
        }
    }

    override fun chacha20Poly1305Encrypt(
        key: ByteArray,
        nonce: ByteArray,
        associatedData: ByteArray,
        plaintext: ByteArray,
    ): ByteArray {
        requireChaChaInputs(key, nonce)
        return chacha20Poly1305.keyDecoder()
            .decodeFromByteArrayBlocking(ChaCha20Poly1305.Key.Format.RAW, key)
            .cipher()
            .encryptWithIvBlocking(nonce, plaintext, associatedData)
    }

    override fun chacha20Poly1305Decrypt(
        key: ByteArray,
        nonce: ByteArray,
        associatedData: ByteArray,
        ciphertext: ByteArray,
    ): ByteArray {
        requireChaChaInputs(key, nonce)
        return chacha20Poly1305.keyDecoder()
            .decodeFromByteArrayBlocking(ChaCha20Poly1305.Key.Format.RAW, key)
            .cipher()
            .decryptWithIvBlocking(nonce, ciphertext, associatedData)
    }

    private fun requireSha256(bytes: ByteArray) {
        check(bytes.size == SHA256_SIZE_BYTES) {
            "Explicit cryptography provider returned ${bytes.size} SHA-256 bytes"
        }
    }

    private fun requireX25519Private(bytes: ByteArray) {
        require(bytes.size == X25519_KEY_SIZE_BYTES) {
            "X25519 private key must be $X25519_KEY_SIZE_BYTES bytes"
        }
    }

    private fun requireX25519Public(bytes: ByteArray) {
        require(bytes.size == X25519_KEY_SIZE_BYTES) {
            "X25519 public key must be $X25519_KEY_SIZE_BYTES bytes"
        }
    }

    private fun requireX25519Secret(bytes: ByteArray) {
        check(bytes.size == X25519_KEY_SIZE_BYTES) {
            "Explicit cryptography provider returned ${bytes.size} X25519 shared-secret bytes"
        }
    }

    private fun requireChaChaInputs(key: ByteArray, nonce: ByteArray) {
        require(key.size == 32) { "ChaCha20-Poly1305 key must be 32 bytes" }
        require(nonce.size == 12) { "ChaCha20-Poly1305 nonce must be 12 bytes" }
    }
}
