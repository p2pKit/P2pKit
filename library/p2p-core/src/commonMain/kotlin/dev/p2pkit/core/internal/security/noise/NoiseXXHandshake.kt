package dev.p2pkit.core.internal.security.noise

import kotlinx.coroutines.CancellationException

internal class NoiseCipherState(
    private val cryptography: NoiseCryptography,
    key: ByteArray? = null,
    initialNonce: ULong = 0u,
) {
    private var keyBytes: ByteArray? = null
    private var nonce: ULong = 0u
    private var terminalFailure: Boolean = false

    init {
        if (key == null) {
            require(initialNonce == 0uL) { "An unkeyed Noise cipher cannot have a nonce" }
        } else {
            initializeKey(key)
            nonce = initialNonce
        }
    }

    fun hasKey(): Boolean = keyBytes != null

    fun initializeKey(key: ByteArray) {
        check(!terminalFailure) { "Failed Noise cipher state cannot be reinitialized" }
        requireSize(key, NOISE_AEAD_KEY_SIZE_BYTES, "Noise cipher key")
        keyBytes?.wipe()
        keyBytes = key.copyOf()
        nonce = 0u
    }

    fun encryptWithAd(associatedData: ByteArray, plaintext: ByteArray): ByteArray {
        ensureNotFailed()
        val currentKey = keyBytes ?: return plaintext.copyOf()
        var nonceBytes: ByteArray? = null
        return try {
            ensureNonceAvailable()
            val encodedNonce = noiseNonce(nonce)
            nonceBytes = encodedNonce
            val ciphertext = cryptography.chacha20Poly1305Encrypt(
                key = currentKey,
                nonce = encodedNonce,
                associatedData = associatedData,
                plaintext = plaintext,
            )
            if (ciphertext.size != plaintext.size + NOISE_AEAD_TAG_SIZE_BYTES) {
                ciphertext.wipe()
                throw NoiseProtocolException("ChaCha20-Poly1305 returned an invalid ciphertext length")
            }
            nonce += 1u
            ciphertext
        } catch (cause: NoiseProtocolException) {
            failClosed()
            throw cause
        } catch (cause: CancellationException) {
            failClosed()
            throw cause
        } catch (cause: Exception) {
            failClosed()
            throw NoiseProtocolException("Noise encryption failed", cause)
        } catch (cause: Throwable) {
            failClosed()
            throw cause
        } finally {
            nonceBytes?.wipe()
        }
    }

    fun decryptWithAd(associatedData: ByteArray, ciphertext: ByteArray): ByteArray {
        ensureNotFailed()
        val currentKey = keyBytes ?: return ciphertext.copyOf()
        var nonceBytes: ByteArray? = null
        return try {
            if (ciphertext.size < NOISE_AEAD_TAG_SIZE_BYTES) {
                throw NoiseAuthenticationException("Noise ciphertext is shorter than its authentication tag")
            }
            ensureNonceAvailable()
            val encodedNonce = noiseNonce(nonce)
            nonceBytes = encodedNonce
            val plaintext = cryptography.chacha20Poly1305Decrypt(
                key = currentKey,
                nonce = encodedNonce,
                associatedData = associatedData,
                ciphertext = ciphertext,
            )
            if (plaintext.size != ciphertext.size - NOISE_AEAD_TAG_SIZE_BYTES) {
                plaintext.wipe()
                throw NoiseAuthenticationException("ChaCha20-Poly1305 returned an invalid plaintext length")
            }
            nonce += 1u
            plaintext
        } catch (cause: NoiseProtocolException) {
            failClosed()
            throw cause
        } catch (cause: CancellationException) {
            failClosed()
            throw cause
        } catch (cause: Exception) {
            failClosed()
            throw NoiseAuthenticationException("Noise ciphertext authentication failed", cause)
        } catch (cause: Throwable) {
            failClosed()
            throw cause
        } finally {
            nonceBytes?.wipe()
        }
    }

    fun destroy() {
        keyBytes?.wipe()
        keyBytes = null
        nonce = 0u
        terminalFailure = true
    }

    private fun ensureNonceAvailable() {
        // Noise reserves 2^64-1 and permits nonces 0 through 2^64-2.
        if (nonce == ULong.MAX_VALUE) throw NoiseNonceExhaustedException()
    }

    private fun ensureNotFailed() {
        if (terminalFailure) throw NoiseProtocolException("Noise cipher state is terminal")
    }

    private fun failClosed() {
        keyBytes?.wipe()
        keyBytes = null
        nonce = ULong.MAX_VALUE
        terminalFailure = true
    }

    private fun noiseNonce(value: ULong): ByteArray = ByteArray(12).also { encoded ->
        for (index in 0 until 8) {
            encoded[4 + index] = (value shr (index * 8)).toByte()
        }
    }
}

internal class NoiseHandshakeResult internal constructor(
    val sendCipher: NoiseCipherState,
    val receiveCipher: NoiseCipherState,
    remoteStaticPublicKey: ByteArray,
    handshakeHash: ByteArray,
) {
    private val remoteStaticBytes: ByteArray = remoteStaticPublicKey.copyOf()
    private val handshakeHashBytes: ByteArray = handshakeHash.copyOf()

    fun copyRemoteStaticPublicKey(): ByteArray = remoteStaticBytes.copyOf()

    fun copyHandshakeHash(): ByteArray = handshakeHashBytes.copyOf()

    fun clearMetadata() {
        remoteStaticBytes.wipe()
        handshakeHashBytes.wipe()
    }

    fun destroy() {
        sendCipher.destroy()
        receiveCipher.destroy()
        clearMetadata()
    }
}

/**
 * Exact Noise XX state machine for Noise_XX_25519_ChaChaPoly_SHA256.
 *
 * The caller supplies ephemeral key generation so vector tests can inject the
 * mandated key material while production delegates generation to its selected
 * platform provider. A failed read/write irreversibly aborts this state.
 */
internal class NoiseXXHandshake(
    private val role: NoiseRole,
    localStatic: NoiseKeyPair,
    private val ephemeralKeyPair: () -> NoiseKeyPair,
    private val sha256: (ByteArray) -> ByteArray,
    private val cryptography: NoiseCryptography,
    prologue: ByteArray,
) {
    private val symmetric = NoiseSymmetricState(sha256, cryptography, prologue)
    private val localStatic: NoiseKeyPair = localStatic.copy()
    private var localEphemeral: NoiseKeyPair? = null
    private var remoteEphemeral: ByteArray? = null
    private var remoteStatic: ByteArray? = null
    private var messageIndex: Int = 0
    private var aborted: Boolean = false
    private var completed: Boolean = false
    private var pendingResult: NoiseHandshakeResult? = null

    fun writeMessage(payload: ByteArray): ByteArray = guarded("write") {
        require(payload.size <= SECURE_V2_MAX_HANDSHAKE_PAYLOAD_BYTES) {
            "Noise handshake payload exceeds $SECURE_V2_MAX_HANDSHAKE_PAYLOAD_BYTES bytes"
        }
        when (role) {
            NoiseRole.Initiator -> when (messageIndex) {
                0 -> writeInitiatorMessageOne(payload)
                2 -> writeInitiatorMessageThree(payload)
                else -> invalidTurn("write")
            }
            NoiseRole.Responder -> when (messageIndex) {
                1 -> writeResponderMessageTwo(payload)
                else -> invalidTurn("write")
            }
        }
    }

    fun readMessage(message: ByteArray): ByteArray = guarded("read") {
        if (message.size > SECURE_V2_MAX_HANDSHAKE_MESSAGE_BYTES) {
            throw NoiseProtocolException(
                "Noise handshake message exceeds $SECURE_V2_MAX_HANDSHAKE_MESSAGE_BYTES bytes",
            )
        }
        when (role) {
            NoiseRole.Initiator -> when (messageIndex) {
                1 -> readInitiatorMessageTwo(message)
                else -> invalidTurn("read")
            }
            NoiseRole.Responder -> when (messageIndex) {
                0 -> readResponderMessageOne(message)
                2 -> readResponderMessageThree(message)
                else -> invalidTurn("read")
            }
        }
    }

    fun takeResult(): NoiseHandshakeResult {
        check(!aborted) { "Noise handshake is aborted" }
        check(completed) { "Noise handshake is not complete" }
        return checkNotNull(pendingResult) { "Noise handshake result was already taken" }.also {
            pendingResult = null
        }
    }

    /** Defensive copy available as soon as the XX remote-static token is authenticated. */
    fun copyRemoteStaticPublicKey(): ByteArray {
        check(!aborted) { "Noise handshake is aborted" }
        pendingResult?.let { return it.copyRemoteStaticPublicKey() }
        return checkNotNull(remoteStatic) { "Remote Noise static key is not authenticated yet" }.copyOf()
    }

    fun destroy() {
        abortInternal(destroyPendingResult = true)
    }

    private fun writeInitiatorMessageOne(payload: ByteArray): ByteArray {
        val ephemeral = generateEphemeral()
        var publicKey: ByteArray? = null
        var encryptedPayload: ByteArray? = null
        try {
            publicKey = ephemeral.copyPublicKey()
            symmetric.mixHash(publicKey)
            encryptedPayload = symmetric.encryptAndHash(payload)
            val message = concatenate(publicKey, encryptedPayload)
            messageIndex = 1
            return message
        } finally {
            publicKey?.wipe()
            encryptedPayload?.wipe()
        }
    }

    private fun readResponderMessageOne(message: ByteArray): ByteArray {
        requireMessageLengthIn(
            message = message,
            minimum = NOISE_DH_KEY_SIZE_BYTES,
            maximum = NOISE_DH_KEY_SIZE_BYTES + SECURE_V2_MAX_HANDSHAKE_PAYLOAD_BYTES,
            label = "Noise XX message 1",
        )
        val ephemeral = message.copyOfRange(0, NOISE_DH_KEY_SIZE_BYTES)
        val encodedPayload = message.copyOfRange(NOISE_DH_KEY_SIZE_BYTES, message.size)
        try {
            replaceRemoteEphemeral(ephemeral)
            symmetric.mixHash(ephemeral)
            val payload = symmetric.decryptAndHash(encodedPayload)
            messageIndex = 1
            return payload
        } finally {
            ephemeral.wipe()
            encodedPayload.wipe()
        }
    }

    private fun writeResponderMessageTwo(payload: ByteArray): ByteArray {
        val ephemeral = generateEphemeral()
        var ephemeralPublic: ByteArray? = null
        var staticPublic: ByteArray? = null
        var encryptedStatic: ByteArray? = null
        var encryptedPayload: ByteArray? = null
        try {
            ephemeralPublic = ephemeral.copyPublicKey()
            symmetric.mixHash(ephemeralPublic)
            mixDh(ephemeral.copyPrivateKey(), requireRemoteEphemeral(), "ee")

            staticPublic = localStatic.copyPublicKey()
            encryptedStatic = symmetric.encryptAndHash(staticPublic)
            mixDh(localStatic.copyPrivateKey(), requireRemoteEphemeral(), "es")
            encryptedPayload = symmetric.encryptAndHash(payload)

            val message = concatenate(ephemeralPublic, encryptedStatic, encryptedPayload)
            messageIndex = 2
            return message
        } finally {
            ephemeralPublic?.wipe()
            staticPublic?.wipe()
            encryptedStatic?.wipe()
            encryptedPayload?.wipe()
        }
    }

    private fun readInitiatorMessageTwo(message: ByteArray): ByteArray {
        val minimum = NOISE_DH_KEY_SIZE_BYTES +
            NOISE_DH_KEY_SIZE_BYTES + NOISE_AEAD_TAG_SIZE_BYTES +
            NOISE_AEAD_TAG_SIZE_BYTES
        requireMessageLengthIn(
            message = message,
            minimum = minimum,
            maximum = minimum + SECURE_V2_MAX_HANDSHAKE_PAYLOAD_BYTES,
            label = "Noise XX message 2",
        )

        val ephemeral = message.copyOfRange(0, NOISE_DH_KEY_SIZE_BYTES)
        var encryptedStatic: ByteArray? = null
        var staticPublic: ByteArray? = null
        var encryptedPayload: ByteArray? = null
        try {
            replaceRemoteEphemeral(ephemeral)
            symmetric.mixHash(ephemeral)
            mixDh(requireLocalEphemeral().copyPrivateKey(), ephemeral, "ee")

            val encryptedStaticEnd =
                NOISE_DH_KEY_SIZE_BYTES + NOISE_DH_KEY_SIZE_BYTES + NOISE_AEAD_TAG_SIZE_BYTES
            encryptedStatic = message.copyOfRange(NOISE_DH_KEY_SIZE_BYTES, encryptedStaticEnd)
            staticPublic = symmetric.decryptAndHash(encryptedStatic)
            requireSize(staticPublic, NOISE_DH_KEY_SIZE_BYTES, "Remote Noise static public key")
            replaceRemoteStatic(staticPublic)
            mixDh(requireLocalEphemeral().copyPrivateKey(), staticPublic, "es")

            encryptedPayload = message.copyOfRange(encryptedStaticEnd, message.size)
            val payload = symmetric.decryptAndHash(encryptedPayload)
            messageIndex = 2
            return payload
        } finally {
            ephemeral.wipe()
            encryptedStatic?.wipe()
            staticPublic?.wipe()
            encryptedPayload?.wipe()
        }
    }

    private fun writeInitiatorMessageThree(payload: ByteArray): ByteArray {
        var staticPublic: ByteArray? = null
        var encryptedStatic: ByteArray? = null
        var encryptedPayload: ByteArray? = null
        var message: ByteArray? = null
        var succeeded = false
        try {
            staticPublic = localStatic.copyPublicKey()
            encryptedStatic = symmetric.encryptAndHash(staticPublic)
            mixDh(localStatic.copyPrivateKey(), requireRemoteEphemeral(), "se")
            encryptedPayload = symmetric.encryptAndHash(payload)
            message = concatenate(encryptedStatic, encryptedPayload)
            complete()
            succeeded = true
            return message
        } finally {
            staticPublic?.wipe()
            encryptedStatic?.wipe()
            encryptedPayload?.wipe()
            if (!succeeded) message?.wipe()
        }
    }

    private fun readResponderMessageThree(message: ByteArray): ByteArray {
        val minimum = NOISE_DH_KEY_SIZE_BYTES + NOISE_AEAD_TAG_SIZE_BYTES + NOISE_AEAD_TAG_SIZE_BYTES
        requireMessageLengthIn(
            message = message,
            minimum = minimum,
            maximum = minimum + SECURE_V2_MAX_HANDSHAKE_PAYLOAD_BYTES,
            label = "Noise XX message 3",
        )
        val encryptedStaticEnd = NOISE_DH_KEY_SIZE_BYTES + NOISE_AEAD_TAG_SIZE_BYTES
        var encryptedStatic: ByteArray? = null
        var staticPublic: ByteArray? = null
        var encryptedPayload: ByteArray? = null
        try {
            encryptedStatic = message.copyOfRange(0, encryptedStaticEnd)
            staticPublic = symmetric.decryptAndHash(encryptedStatic)
            requireSize(staticPublic, NOISE_DH_KEY_SIZE_BYTES, "Remote Noise static public key")
            replaceRemoteStatic(staticPublic)
            mixDh(requireLocalEphemeral().copyPrivateKey(), staticPublic, "se")

            encryptedPayload = message.copyOfRange(encryptedStaticEnd, message.size)
            val payload = symmetric.decryptAndHash(encryptedPayload)
            complete()
            return payload
        } finally {
            encryptedStatic?.wipe()
            staticPublic?.wipe()
            encryptedPayload?.wipe()
        }
    }

    private fun complete() {
        val remoteStatic = checkNotNull(remoteStatic) { "Noise XX completed without a remote static key" }
        val split = symmetric.split()
        var handshakeHash: ByteArray? = null
        var resultCommitted = false
        try {
            handshakeHash = symmetric.copyHandshakeHash()
            val sendCipher = when (role) {
                NoiseRole.Initiator -> split.first
                NoiseRole.Responder -> split.second
            }
            val receiveCipher = when (role) {
                NoiseRole.Initiator -> split.second
                NoiseRole.Responder -> split.first
            }
            pendingResult = NoiseHandshakeResult(
                sendCipher = sendCipher,
                receiveCipher = receiveCipher,
                remoteStaticPublicKey = remoteStatic,
                handshakeHash = handshakeHash,
            )
            resultCommitted = true
            messageIndex = 3
            completed = true
            destroyHandshakeSecrets()
        } finally {
            handshakeHash?.wipe()
            if (!resultCommitted) {
                split.first.destroy()
                split.second.destroy()
            }
        }
    }

    private fun generateEphemeral(): NoiseKeyPair {
        check(localEphemeral == null) { "Noise ephemeral key already exists" }
        return ephemeralKeyPair().also { localEphemeral = it }
    }

    private fun mixDh(privateKey: ByteArray, publicKey: ByteArray, token: String) {
        try {
            requireSize(privateKey, NOISE_DH_KEY_SIZE_BYTES, "$token private key")
            requireSize(publicKey, NOISE_DH_KEY_SIZE_BYTES, "$token public key")
            val sharedSecret = try {
                cryptography.x25519(privateKey, publicKey)
            } catch (cause: CancellationException) {
                throw cause
            } catch (cause: Exception) {
                throw NoiseAuthenticationException("Noise $token Diffie-Hellman operation failed", cause)
            } catch (cause: Throwable) {
                throw cause
            }
            try {
                requireSize(sharedSecret, NOISE_DH_KEY_SIZE_BYTES, "$token shared secret")
                var aggregate = 0
                for (byte in sharedSecret) {
                    aggregate = aggregate or (byte.toInt() and 0xff)
                }
                if (aggregate == 0) {
                    throw NoiseAuthenticationException("Noise $token produced an all-zero shared secret")
                }
                symmetric.mixKey(sharedSecret)
            } finally {
                sharedSecret.wipe()
            }
        } finally {
            privateKey.wipe()
        }
    }

    private fun replaceRemoteEphemeral(value: ByteArray) {
        requireSize(value, NOISE_DH_KEY_SIZE_BYTES, "Remote Noise ephemeral public key")
        remoteEphemeral?.wipe()
        remoteEphemeral = value.copyOf()
    }

    private fun replaceRemoteStatic(value: ByteArray) {
        requireSize(value, NOISE_DH_KEY_SIZE_BYTES, "Remote Noise static public key")
        remoteStatic?.wipe()
        remoteStatic = value.copyOf()
    }

    private fun requireLocalEphemeral(): NoiseKeyPair =
        checkNotNull(localEphemeral) { "Local Noise ephemeral key is unavailable" }

    private fun requireRemoteEphemeral(): ByteArray =
        checkNotNull(remoteEphemeral) { "Remote Noise ephemeral key is unavailable" }

    private fun invalidTurn(operation: String): Nothing =
        throw NoiseProtocolException("Cannot $operation Noise XX message at step $messageIndex as $role")

    private fun <T> guarded(operation: String, block: () -> T): T {
        check(!aborted) { "Noise handshake is aborted" }
        check(!completed) { "Noise handshake is already complete" }
        return try {
            block()
        } catch (cause: NoiseProtocolException) {
            abortInternal(destroyPendingResult = true)
            throw cause
        } catch (cause: CancellationException) {
            abortInternal(destroyPendingResult = true)
            throw cause
        } catch (cause: IllegalArgumentException) {
            abortInternal(destroyPendingResult = true)
            throw NoiseProtocolException("Noise handshake $operation rejected invalid input", cause)
        } catch (cause: IllegalStateException) {
            abortInternal(destroyPendingResult = true)
            throw NoiseProtocolException("Noise handshake $operation occurred in an invalid state", cause)
        } catch (cause: Exception) {
            abortInternal(destroyPendingResult = true)
            throw NoiseProtocolException("Noise handshake $operation failed", cause)
        } catch (cause: Throwable) {
            abortInternal(destroyPendingResult = true)
            throw cause
        }
    }

    private fun abortInternal(destroyPendingResult: Boolean) {
        if (aborted) return
        aborted = true
        destroyHandshakeSecrets()
        if (destroyPendingResult) {
            pendingResult?.destroy()
            pendingResult = null
        }
    }

    private fun destroyHandshakeSecrets() {
        localStatic.destroy()
        localEphemeral?.destroy()
        localEphemeral = null
        remoteEphemeral?.wipe()
        remoteEphemeral = null
        remoteStatic?.wipe()
        remoteStatic = null
        symmetric.destroy()
    }
}

private class NoiseSymmetricState(
    private val sha256: (ByteArray) -> ByteArray,
    private val cryptography: NoiseCryptography,
    prologue: ByteArray,
) {
    private var chainingKey: ByteArray
    private var handshakeHash: ByteArray
    private val cipher = NoiseCipherState(cryptography)
    private var destroyed: Boolean = false

    init {
        val protocolName = NOISE_PROTOCOL_NAME.encodeToByteArray()
        val initialHash = if (protocolName.size <= NOISE_HASH_SIZE_BYTES) {
            protocolName.copyOf(NOISE_HASH_SIZE_BYTES)
        } else {
            hash(protocolName)
        }
        protocolName.wipe()
        chainingKey = initialHash.copyOf()
        handshakeHash = initialHash
        try {
            mixHash(prologue)
        } catch (cause: Throwable) {
            destroy()
            throw cause
        }
    }

    fun mixHash(data: ByteArray) {
        ensureActive()
        val combined = concatenate(handshakeHash, data)
        val next = try {
            hash(combined)
        } finally {
            combined.wipe()
        }
        handshakeHash.wipe()
        handshakeHash = next
    }

    fun mixKey(inputKeyMaterial: ByteArray) {
        ensureActive()
        val outputs = hkdf2(chainingKey, inputKeyMaterial)
        chainingKey.wipe()
        chainingKey = outputs.first
        try {
            cipher.initializeKey(outputs.second)
        } finally {
            outputs.second.wipe()
        }
    }

    fun encryptAndHash(plaintext: ByteArray): ByteArray {
        ensureActive()
        val ciphertext = cipher.encryptWithAd(handshakeHash, plaintext)
        mixHash(ciphertext)
        return ciphertext
    }

    fun decryptAndHash(ciphertext: ByteArray): ByteArray {
        ensureActive()
        // The transcript advances only after successful authentication.
        val plaintext = cipher.decryptWithAd(handshakeHash, ciphertext)
        mixHash(ciphertext)
        return plaintext
    }

    fun split(): Pair<NoiseCipherState, NoiseCipherState> {
        ensureActive()
        val outputs = hkdf2(chainingKey, ByteArray(0))
        var first: NoiseCipherState? = null
        return try {
            first = NoiseCipherState(cryptography, outputs.first)
            val second = NoiseCipherState(cryptography, outputs.second)
            first to second
        } catch (cause: Throwable) {
            first?.destroy()
            throw cause
        } finally {
            outputs.first.wipe()
            outputs.second.wipe()
        }
    }

    fun copyHandshakeHash(): ByteArray {
        ensureActive()
        return handshakeHash.copyOf()
    }

    fun destroy() {
        if (destroyed) return
        destroyed = true
        chainingKey.wipe()
        handshakeHash.wipe()
        cipher.destroy()
    }

    private fun hkdf2(chainingKey: ByteArray, inputKeyMaterial: ByteArray): Pair<ByteArray, ByteArray> {
        val temporaryKey = hmac(chainingKey, inputKeyMaterial)
        try {
            val outputOne = hmac(temporaryKey, byteArrayOf(1))
            try {
                val outputTwoInput = concatenate(outputOne, byteArrayOf(2))
                try {
                    val outputTwo = hmac(temporaryKey, outputTwoInput)
                    return outputOne to outputTwo
                } finally {
                    outputTwoInput.wipe()
                }
            } catch (cause: Throwable) {
                outputOne.wipe()
                throw cause
            }
        } finally {
            temporaryKey.wipe()
        }
    }

    private fun hash(data: ByteArray): ByteArray {
        val output = sha256(data)
        return try {
            requireSize(output, NOISE_HASH_SIZE_BYTES, "SHA-256 output")
            output
        } catch (cause: Throwable) {
            output.wipe()
            throw cause
        }
    }

    private fun hmac(key: ByteArray, data: ByteArray): ByteArray {
        val output = cryptography.hmacSha256(key, data)
        return try {
            requireSize(output, NOISE_HASH_SIZE_BYTES, "HMAC-SHA-256 output")
            output
        } catch (cause: Throwable) {
            output.wipe()
            throw cause
        }
    }

    private fun ensureActive() {
        check(!destroyed) { "Noise symmetric state is destroyed" }
    }
}

private fun requireMessageLengthIn(
    message: ByteArray,
    minimum: Int,
    maximum: Int,
    label: String,
) {
    if (message.size !in minimum..maximum) {
        throw NoiseProtocolException("$label length ${message.size} is outside $minimum..$maximum")
    }
}

private fun concatenate(vararg arrays: ByteArray): ByteArray {
    var size = 0
    arrays.forEach { bytes ->
        if (bytes.size > Int.MAX_VALUE - size) {
            throw NoiseProtocolException("Noise byte sequence length overflow")
        }
        size += bytes.size
    }
    return ByteArray(size).also { destination ->
        var offset = 0
        arrays.forEach { bytes ->
            bytes.copyInto(destination, offset)
            offset += bytes.size
        }
    }
}
