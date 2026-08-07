package dev.p2pkit.core.internal.security.noise

import dev.p2pkit.core.security.PlatformSecurityCryptography
import dev.p2pkit.core.security.platformSecurityCryptography
import kotlinx.coroutines.CancellationException
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class NoiseXXHandshakeTest {
    private val cryptography: PlatformSecurityCryptography = platformSecurityCryptography()

    @Test
    fun cacophonyNoiseXx25519ChaChaPolySha256Vector() {
        val initiatorStatic = keyPair(INITIATOR_STATIC_PRIVATE)
        val responderStatic = keyPair(RESPONDER_STATIC_PRIVATE)
        val initiator = handshake(
            role = NoiseRole.Initiator,
            static = initiatorStatic,
            ephemeralPrivate = INITIATOR_EPHEMERAL_PRIVATE,
            prologue = CACOPHONY_PROLOGUE.hexBytes(),
        )
        val responder = handshake(
            role = NoiseRole.Responder,
            static = responderStatic,
            ephemeralPrivate = RESPONDER_EPHEMERAL_PRIVATE,
            prologue = CACOPHONY_PROLOGUE.hexBytes(),
        )

        try {
            val messageOnePayload = MESSAGE_ONE_PAYLOAD.hexBytes()
            val messageOne = initiator.writeMessage(messageOnePayload)
            assertHexEquals(MESSAGE_ONE_CIPHERTEXT, messageOne)
            assertContentEquals(messageOnePayload, responder.readMessage(messageOne))

            val messageTwoPayload = MESSAGE_TWO_PAYLOAD.hexBytes()
            val messageTwo = responder.writeMessage(messageTwoPayload)
            assertHexEquals(MESSAGE_TWO_CIPHERTEXT, messageTwo)
            assertContentEquals(messageTwoPayload, initiator.readMessage(messageTwo))

            val messageThreePayload = MESSAGE_THREE_PAYLOAD.hexBytes()
            val messageThree = initiator.writeMessage(messageThreePayload)
            assertHexEquals(MESSAGE_THREE_CIPHERTEXT, messageThree)
            assertContentEquals(messageThreePayload, responder.readMessage(messageThree))

            val initiatorResult = initiator.takeResult()
            val responderResult = responder.takeResult()
            try {
                assertHexEquals(CACOPHONY_HANDSHAKE_HASH, initiatorResult.copyHandshakeHash())
                assertHexEquals(CACOPHONY_HANDSHAKE_HASH, responderResult.copyHandshakeHash())
                assertContentEquals(
                    responderStatic.copyPublicKey(),
                    initiatorResult.copyRemoteStaticPublicKey(),
                )
                assertContentEquals(
                    initiatorStatic.copyPublicKey(),
                    responderResult.copyRemoteStaticPublicKey(),
                )

                val responderTransportPlaintext = TRANSPORT_RESPONDER_ONE_PAYLOAD.hexBytes()
                val responderTransportCiphertext = responderResult.sendCipher.encryptWithAd(
                    ByteArray(0),
                    responderTransportPlaintext,
                )
                assertHexEquals(TRANSPORT_RESPONDER_ONE_CIPHERTEXT, responderTransportCiphertext)
                assertContentEquals(
                    responderTransportPlaintext,
                    initiatorResult.receiveCipher.decryptWithAd(ByteArray(0), responderTransportCiphertext),
                )

                val initiatorTransportPlaintext = TRANSPORT_INITIATOR_PAYLOAD.hexBytes()
                val initiatorTransportCiphertext = initiatorResult.sendCipher.encryptWithAd(
                    ByteArray(0),
                    initiatorTransportPlaintext,
                )
                assertHexEquals(TRANSPORT_INITIATOR_CIPHERTEXT, initiatorTransportCiphertext)
                assertContentEquals(
                    initiatorTransportPlaintext,
                    responderResult.receiveCipher.decryptWithAd(ByteArray(0), initiatorTransportCiphertext),
                )

                val responderTransportPlaintextTwo = TRANSPORT_RESPONDER_TWO_PAYLOAD.hexBytes()
                val responderTransportCiphertextTwo = responderResult.sendCipher.encryptWithAd(
                    ByteArray(0),
                    responderTransportPlaintextTwo,
                )
                assertHexEquals(TRANSPORT_RESPONDER_TWO_CIPHERTEXT, responderTransportCiphertextTwo)
                assertContentEquals(
                    responderTransportPlaintextTwo,
                    initiatorResult.receiveCipher.decryptWithAd(ByteArray(0), responderTransportCiphertextTwo),
                )
            } finally {
                initiatorResult.destroy()
                responderResult.destroy()
            }
        } finally {
            initiator.destroy()
            responder.destroy()
            initiatorStatic.destroy()
            responderStatic.destroy()
        }
    }

    @Test
    fun productionEmptyPayloadFlightsHaveExactBodiesAndCompletedStateIsImmutable() {
        val initiatorStatic = generatedKeyPair()
        val responderStatic = generatedKeyPair()
        val initiator = generatedHandshake(NoiseRole.Initiator, initiatorStatic)
        val responder = generatedHandshake(NoiseRole.Responder, responderStatic)
        try {
            val messageOne = initiator.writeMessage(ByteArray(0))
            assertEquals(32, messageOne.size)
            assertContentEquals(ByteArray(0), responder.readMessage(messageOne))

            val messageTwo = responder.writeMessage(ByteArray(0))
            assertEquals(96, messageTwo.size)
            assertContentEquals(ByteArray(0), initiator.readMessage(messageTwo))

            val messageThree = initiator.writeMessage(ByteArray(0))
            assertEquals(64, messageThree.size)
            assertContentEquals(ByteArray(0), responder.readMessage(messageThree))

            assertFailsWith<IllegalStateException> { initiator.writeMessage(ByteArray(0)) }
            assertFailsWith<IllegalStateException> { responder.readMessage(messageThree) }

            val initiatorResult = initiator.takeResult()
            val responderResult = responder.takeResult()
            try {
                assertContentEquals(
                    responderStatic.copyPublicKey(),
                    initiatorResult.copyRemoteStaticPublicKey(),
                )
                assertContentEquals(
                    initiatorStatic.copyPublicKey(),
                    responderResult.copyRemoteStaticPublicKey(),
                )
                assertFailsWith<IllegalStateException> { initiator.readMessage(messageTwo) }
                assertFailsWith<IllegalStateException> { responder.writeMessage(ByteArray(0)) }
                assertFailsWith<IllegalStateException> { initiator.takeResult() }
            } finally {
                initiatorResult.destroy()
                responderResult.destroy()
            }
        } finally {
            initiator.destroy()
            responder.destroy()
            initiatorStatic.destroy()
            responderStatic.destroy()
        }
    }

    @Test
    fun authenticationFailureAbortsHandshakeAndRejectsRetry() {
        val initiatorStatic = generatedKeyPair()
        val responderStatic = generatedKeyPair()
        val initiator = generatedHandshake(NoiseRole.Initiator, initiatorStatic)
        val responder = generatedHandshake(NoiseRole.Responder, responderStatic)
        try {
            val messageOne = initiator.writeMessage(ByteArray(0))
            responder.readMessage(messageOne)
            val tamperedMessageTwo = responder.writeMessage(ByteArray(0)).also { message ->
                message[message.lastIndex] = (message.last().toInt() xor 1).toByte()
            }
            assertFailsWith<NoiseAuthenticationException> {
                initiator.readMessage(tamperedMessageTwo)
            }
            assertFailsWith<IllegalStateException> {
                initiator.readMessage(tamperedMessageTwo)
            }
        } finally {
            initiator.destroy()
            responder.destroy()
            initiatorStatic.destroy()
            responderStatic.destroy()
        }
    }

    @Test
    fun allZeroDiffieHellmanOutputIsRejectedAfterFixedWorkCheck() {
        val zeroDh = object : NoiseCryptography by cryptography {
            override fun x25519(privateKey: ByteArray, publicKey: ByteArray): ByteArray = ByteArray(32)
        }
        val initiatorStatic = generatedKeyPair()
        val responderStatic = generatedKeyPair()
        val initiator = NoiseXXHandshake(
            role = NoiseRole.Initiator,
            localStatic = initiatorStatic,
            ephemeralKeyPair = ::generatedKeyPair,
            sha256 = cryptography::sha256,
            cryptography = zeroDh,
            prologue = ByteArray(0),
        )
        val responder = NoiseXXHandshake(
            role = NoiseRole.Responder,
            localStatic = responderStatic,
            ephemeralKeyPair = ::generatedKeyPair,
            sha256 = cryptography::sha256,
            cryptography = zeroDh,
            prologue = ByteArray(0),
        )
        try {
            responder.readMessage(initiator.writeMessage(ByteArray(0)))
            val failure = assertFailsWith<NoiseAuthenticationException> {
                responder.writeMessage(ByteArray(0))
            }
            assertEquals(true, failure.message?.contains("all-zero"))
            assertFailsWith<IllegalStateException> { responder.writeMessage(ByteArray(0)) }
        } finally {
            initiator.destroy()
            responder.destroy()
            initiatorStatic.destroy()
            responderStatic.destroy()
        }
    }

    @Test
    fun cipherAuthenticationAndNonceFailuresAreTerminal() {
        val key = ByteArray(32) { it.toByte() }
        val sender = NoiseCipherState(cryptography, key)
        val receiver = NoiseCipherState(cryptography, key)
        val plaintext = "authenticated".encodeToByteArray()
        val ciphertext = sender.encryptWithAd(ByteArray(0), plaintext)
        val tampered = ciphertext.copyOf().also { it[it.lastIndex] = (it.last().toInt() xor 1).toByte() }

        assertFailsWith<NoiseAuthenticationException> {
            receiver.decryptWithAd(ByteArray(0), tampered)
        }
        assertFailsWith<NoiseProtocolException> {
            receiver.decryptWithAd(ByteArray(0), ciphertext)
        }

        val exhausted = NoiseCipherState(cryptography, key, ULong.MAX_VALUE)
        assertFailsWith<NoiseNonceExhaustedException> {
            exhausted.encryptWithAd(ByteArray(0), plaintext)
        }
        assertFailsWith<NoiseProtocolException> {
            exhausted.encryptWithAd(ByteArray(0), plaintext)
        }

        sender.destroy()
        receiver.destroy()
        exhausted.destroy()
        key.wipe()
        ciphertext.wipe()
        tampered.wipe()
    }

    @Test
    fun providerCancellationIsPreservedAndCipherStillFailsClosed() {
        val cancellation = CancellationException("provider operation cancelled")
        val cancellingCryptography = object : NoiseCryptography by cryptography {
            override fun chacha20Poly1305Encrypt(
                key: ByteArray,
                nonce: ByteArray,
                associatedData: ByteArray,
                plaintext: ByteArray,
            ): ByteArray = throw cancellation
        }
        val cipher = NoiseCipherState(cancellingCryptography, ByteArray(32) { it.toByte() })

        val observed = assertFailsWith<CancellationException> {
            cipher.encryptWithAd(ByteArray(0), "secret".encodeToByteArray())
        }
        assertEquals(cancellation, observed)
        assertFailsWith<NoiseProtocolException> {
            cipher.encryptWithAd(ByteArray(0), "retry".encodeToByteArray())
        }
        cipher.destroy()
    }

    private fun handshake(
        role: NoiseRole,
        static: NoiseKeyPair,
        ephemeralPrivate: String,
        prologue: ByteArray,
    ): NoiseXXHandshake = NoiseXXHandshake(
        role = role,
        localStatic = static,
        ephemeralKeyPair = { keyPair(ephemeralPrivate) },
        sha256 = cryptography::sha256,
        cryptography = cryptography,
        prologue = prologue,
    )

    private fun generatedHandshake(role: NoiseRole, static: NoiseKeyPair): NoiseXXHandshake =
        NoiseXXHandshake(
            role = role,
            localStatic = static,
            ephemeralKeyPair = ::generatedKeyPair,
            sha256 = cryptography::sha256,
            cryptography = cryptography,
            prologue = "test-prologue".encodeToByteArray(),
        )

    private fun keyPair(privateKeyHex: String): NoiseKeyPair {
        val privateKey = privateKeyHex.hexBytes()
        val publicKey = cryptography.deriveX25519PublicKey(privateKey)
        return try {
            NoiseKeyPair(privateKey, publicKey)
        } finally {
            privateKey.wipe()
            publicKey.wipe()
        }
    }

    private fun generatedKeyPair(): NoiseKeyPair {
        val encoded = cryptography.generateX25519KeyPair()
        val privateKey = encoded.privateKeyBytes()
        val publicKey = encoded.publicKeyBytes()
        return try {
            NoiseKeyPair(privateKey, publicKey)
        } finally {
            encoded.clearPrivate()
            privateKey.wipe()
            publicKey.wipe()
        }
    }

    private fun assertHexEquals(expected: String, actual: ByteArray) {
        assertContentEquals(expected.hexBytes(), actual)
    }

    private companion object {
        const val CACOPHONY_PROLOGUE = "4a6f686e2047616c74"
        const val INITIATOR_STATIC_PRIVATE = "e61ef9919cde45dd5f82166404bd08e38bceb5dfdfded0a34c8df7ed542214d1"
        const val INITIATOR_EPHEMERAL_PRIVATE = "893e28b9dc6ca8d611ab664754b8ceb7bac5117349a4439a6b0569da977c464a"
        const val RESPONDER_STATIC_PRIVATE = "4a3acbfdb163dec651dfa3194dece676d437029c62a408b4c5ea9114246e4893"
        const val RESPONDER_EPHEMERAL_PRIVATE = "bbdb4cdbd309f1a1f2e1456967fe288cadd6f712d65dc7b7793d5e63da6b375b"
        const val CACOPHONY_HANDSHAKE_HASH = "c8e5f64e846193be2a834104c2a009868d6c9f3bd3c186299888b488b2f1f58e"

        const val MESSAGE_ONE_PAYLOAD = "4c756477696720766f6e204d69736573"
        const val MESSAGE_ONE_CIPHERTEXT =
            "ca35def5ae56cec33dc2036731ab14896bc4c75dbb07a61f879f8e3afa4c79444c756477696720766f6e204d69736573"
        const val MESSAGE_TWO_PAYLOAD = "4d757272617920526f746862617264"
        const val MESSAGE_TWO_CIPHERTEXT =
            "95ebc60d2b1fa672c1f46a8aa265ef51bfe38e7ccb39ec5be34069f14480884381cbad1f276e038c48378ffce2b65285e08d6b68aaa3629a5a8639392490e5b9bd5269c2f1e4f488ed8831161f19b7815528f8982ffe09be9b5c412f8a0db50f8814c7194e83f23dbd8d162c9326ad"
        const val MESSAGE_THREE_PAYLOAD = "462e20412e20486179656b"
        const val MESSAGE_THREE_CIPHERTEXT =
            "c7195ffacac1307ff99046f219750fc47693e23c3cb08b89c2af808b444850a80ae475b9df0f169ae80a89be0865b57f58c9fea0d4ec82a286427402f113e4b6ae769a1d95941d49b25030"

        const val TRANSPORT_RESPONDER_ONE_PAYLOAD = "4361726c204d656e676572"
        const val TRANSPORT_RESPONDER_ONE_CIPHERTEXT =
            "96763ed773f8e47bb3712f0e29b3060ffc956ffc146cee53d5e1df"
        const val TRANSPORT_INITIATOR_PAYLOAD = "4a65616e2d426170746973746520536179"
        const val TRANSPORT_INITIATOR_CIPHERTEXT =
            "3e40f15f6f3a46ae446b253bf8b1d9ffb6ed9b174d272328ff91a7e2e5c79c07f5"
        const val TRANSPORT_RESPONDER_TWO_PAYLOAD = "457567656e2042f6686d20766f6e2042617765726b"
        const val TRANSPORT_RESPONDER_TWO_CIPHERTEXT =
            "eb3f3515110702e047a6c9da4478b6ead94873c11c0f2d710ddb3f09fce024b3a58502ae3f"
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
