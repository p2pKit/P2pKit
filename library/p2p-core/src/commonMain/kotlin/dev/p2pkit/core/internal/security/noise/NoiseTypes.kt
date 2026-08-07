package dev.p2pkit.core.internal.security.noise

internal const val NOISE_PROTOCOL_NAME: String = "Noise_XX_25519_ChaChaPoly_SHA256"
internal const val NOISE_HASH_SIZE_BYTES: Int = 32
internal const val NOISE_DH_KEY_SIZE_BYTES: Int = 32
internal const val NOISE_AEAD_KEY_SIZE_BYTES: Int = 32
internal const val NOISE_AEAD_TAG_SIZE_BYTES: Int = 16
internal const val SECURE_V2_CLEANUP_TIMEOUT_MILLIS: Long = 5_000

internal enum class NoiseRole {
    Initiator,
    Responder,
}

/**
 * Noise-only primitives. Implementations must delegate every primitive to the
 * explicitly selected platform cryptography provider.
 */
internal interface NoiseCryptography {
    fun hmacSha256(key: ByteArray, data: ByteArray): ByteArray

    fun x25519(privateKey: ByteArray, publicKey: ByteArray): ByteArray

    fun chacha20Poly1305Encrypt(
        key: ByteArray,
        nonce: ByteArray,
        associatedData: ByteArray,
        plaintext: ByteArray,
    ): ByteArray

    fun chacha20Poly1305Decrypt(
        key: ByteArray,
        nonce: ByteArray,
        associatedData: ByteArray,
        ciphertext: ByteArray,
    ): ByteArray
}

internal class NoiseKeyPair(
    privateKey: ByteArray,
    publicKey: ByteArray,
) {
    private val privateKeyBytes: ByteArray = privateKey.copyOf()
    private val publicKeyBytes: ByteArray = publicKey.copyOf()

    init {
        require(privateKeyBytes.size == NOISE_DH_KEY_SIZE_BYTES) {
            "X25519 private keys must be $NOISE_DH_KEY_SIZE_BYTES bytes"
        }
        require(publicKeyBytes.size == NOISE_DH_KEY_SIZE_BYTES) {
            "X25519 public keys must be $NOISE_DH_KEY_SIZE_BYTES bytes"
        }
    }

    fun copyPrivateKey(): ByteArray = privateKeyBytes.copyOf()

    fun copyPublicKey(): ByteArray = publicKeyBytes.copyOf()

    fun copy(): NoiseKeyPair = NoiseKeyPair(privateKeyBytes, publicKeyBytes)

    fun destroy() {
        privateKeyBytes.wipe()
        publicKeyBytes.wipe()
    }
}

internal open class NoiseProtocolException(
    message: String,
    cause: Throwable? = null,
) : Exception(message, cause)

internal class NoiseAuthenticationException(
    message: String,
    cause: Throwable? = null,
) : NoiseProtocolException(message, cause)

internal class NoiseNonceExhaustedException :
    NoiseProtocolException("The Noise cipher nonce space is exhausted")

internal class NoiseTransportEofException(message: String) : NoiseProtocolException(message)

internal fun ByteArray.wipe() {
    fill(0)
}

internal fun requireSize(bytes: ByteArray, expected: Int, label: String) {
    if (bytes.size != expected) {
        throw NoiseProtocolException("$label must be $expected bytes, got ${bytes.size}")
    }
}
