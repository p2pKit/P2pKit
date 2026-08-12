package dev.p2pkit.core.security

import dev.p2pkit.core.internal.security.noise.NoiseXXHandshakeTest
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFails

/** Host execution of Android's explicit Bouncy Castle security provider. */
class AndroidSecurityProviderAndroidHostTest {
    private val cryptography: PlatformSecurityCryptography = platformSecurityCryptography()

    @Test
    fun sha256AndHmacSha256MatchPublishedKnownAnswers() {
        assertContentEquals(
            "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad".hexBytes(),
            cryptography.sha256("abc".encodeToByteArray())
        )
        assertContentEquals(
            "b0344c61d8db38535ca8afceaf0bf12b881dc200c9833da726e9376c2e32cff7".hexBytes(),
            cryptography.hmacSha256(
                key = ByteArray(20) { 0x0b },
                data = "Hi There".encodeToByteArray()
            )
        )
    }

    @Test
    fun x25519MatchesRfc7748PublicKeysAndSharedSecret() {
        val alicePrivate =
            "77076d0a7318a57d3c16c17251b26645df4c2f87ebc0992ab177fba51db92c2a".hexBytes()
        val bobPrivate =
            "5dab087e624a8a4b79e17f8b83800ee66f3bb1292618b6fd1c2f8b27ff88e0eb".hexBytes()
        val alicePublic =
            "8520f0098930a754748b7ddcb43ef75a0dbf3a0d26381af4eba4a98eaa9b4e6a".hexBytes()
        val bobPublic =
            "de9edb7d7b7dc1b4d35b61c2ece435373f8343c85b78674dadfc7e146f882b4f".hexBytes()
        val expectedSecret =
            "4a5d9d5ba4ce2de1728e3bf480350f25e07e21c947d19e3376f09b3c1e161742".hexBytes()

        try {
            assertContentEquals(alicePublic, cryptography.deriveX25519PublicKey(alicePrivate))
            assertContentEquals(bobPublic, cryptography.deriveX25519PublicKey(bobPrivate))
            assertContentEquals(expectedSecret, cryptography.x25519(alicePrivate, bobPublic))
            assertContentEquals(expectedSecret, cryptography.x25519(bobPrivate, alicePublic))
        } finally {
            alicePrivate.fill(0)
            bobPrivate.fill(0)
            expectedSecret.fill(0)
        }
    }

    @Test
    fun androidProviderMatchesFrozenNoiseTranscriptAndRejectsAeadTampering() {
        // The common vector independently fixes every Noise XX handshake and
        // transport byte; invoking it here proves the Android actual rather
        // than relying on JVM/iOS execution of the same common implementation.
        NoiseXXHandshakeTest().cacophonyNoiseXx25519ChaChaPolySha256Vector()

        val key = ByteArray(32) { it.toByte() }
        val nonce = ByteArray(12) { (it + 32).toByte() }
        val aad = "android-provider-aad".encodeToByteArray()
        val plaintext = "authenticated android provider payload".encodeToByteArray()
        val ciphertext = cryptography.chacha20Poly1305Encrypt(key, nonce, aad, plaintext)
        try {
            assertEquals(plaintext.size + 16, ciphertext.size)
            assertContentEquals(
                plaintext,
                cryptography.chacha20Poly1305Decrypt(key, nonce, aad, ciphertext)
            )
            val tampered = ciphertext.copyOf().also {
                it[it.lastIndex] = (it.last().toInt() xor 1).toByte()
            }
            try {
                assertFails {
                    cryptography.chacha20Poly1305Decrypt(key, nonce, aad, tampered)
                }
            } finally {
                tampered.fill(0)
            }
        } finally {
            key.fill(0)
            plaintext.fill(0)
            ciphertext.fill(0)
        }
    }
}

private fun String.hexBytes(): ByteArray {
    require(length % 2 == 0)
    return ByteArray(length / 2) { index ->
        val high = this[index * 2].digitToInt(16)
        val low = this[index * 2 + 1].digitToInt(16)
        ((high shl 4) or low).toByte()
    }
}
