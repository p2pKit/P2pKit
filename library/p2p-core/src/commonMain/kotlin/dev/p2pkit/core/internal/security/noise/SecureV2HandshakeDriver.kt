package dev.p2pkit.core.internal.security.noise

import dev.p2pkit.core.security.PlatformSecurityCryptography

internal class SecureV2HandshakeDriver(
    private val cryptography: PlatformSecurityCryptography,
) {
    suspend fun establish(
        pump: SingleCollectorRawPump,
        role: NoiseRole,
        appId: String,
        localStatic: NoiseKeyPair,
        authorizeRemoteStatic: suspend (ByteArray) -> Boolean,
    ): SecureV2HandshakeOutcome {
        var localPreface: ByteArray? = null
        var remotePreface: ByteArray? = null
        var handshake: NoiseXXHandshake? = null
        var result: NoiseHandshakeResult? = null
        var succeeded = false
        try {
            val encodedLocalPreface = SecureV2Preface(role).encode()
            localPreface = encodedLocalPreface
            val encodedRemotePreface = exchangePrefaces(pump, role, encodedLocalPreface)
            remotePreface = encodedRemotePreface
            val initiatorPreface = when (role) {
                NoiseRole.Initiator -> encodedLocalPreface
                NoiseRole.Responder -> encodedRemotePreface
            }
            val responderPreface = when (role) {
                NoiseRole.Initiator -> encodedRemotePreface
                NoiseRole.Responder -> encodedLocalPreface
            }
            val prologue = SecureV2Prologue.encode(appId, initiatorPreface, responderPreface)
            try {
                handshake = NoiseXXHandshake(
                    role = role,
                    localStatic = localStatic,
                    ephemeralKeyPair = ::generateNoiseKeyPair,
                    sha256 = cryptography::sha256,
                    cryptography = cryptography,
                    prologue = prologue,
                )
            } finally {
                prologue.wipe()
            }

            runEmptyPayloadHandshake(pump, role, handshake, authorizeRemoteStatic)
            result = handshake.takeResult()
            val remoteStaticPublicKey = result.copyRemoteStaticPublicKey()
            val handshakeHash = result.copyHandshakeHash()
            val connection = NoiseSecureRawConnection(
                pump = pump,
                sendCipher = result.sendCipher,
                receiveCipher = result.receiveCipher,
            )
            result.clearMetadata()
            succeeded = true
            return SecureV2HandshakeOutcome(
                connection = connection,
                remoteStaticPublicKey = remoteStaticPublicKey,
                handshakeHash = handshakeHash,
            )
        } catch (cause: Throwable) {
            try {
                pump.close()
            } catch (cleanup: Throwable) {
                cause.addSuppressed(cleanup)
            }
            throw cause
        } finally {
            localPreface?.wipe()
            remotePreface?.wipe()
            handshake?.destroy()
            if (!succeeded) result?.destroy()
        }
    }

    private suspend fun exchangePrefaces(
        pump: SingleCollectorRawPump,
        role: NoiseRole,
        localPreface: ByteArray,
    ): ByteArray = when (role) {
        NoiseRole.Initiator -> {
            pump.write(localPreface)
            val remote = pump.readExactly(SECURE_V2_PREFACE_SIZE_BYTES)
            try {
                SecureV2Preface.decode(remote, NoiseRole.Responder)
                remote
            } catch (cause: Throwable) {
                remote.wipe()
                throw cause
            }
        }
        NoiseRole.Responder -> {
            val remote = pump.readExactly(SECURE_V2_PREFACE_SIZE_BYTES)
            try {
                SecureV2Preface.decode(remote, NoiseRole.Initiator)
                pump.write(localPreface)
                remote
            } catch (cause: Throwable) {
                remote.wipe()
                throw cause
            }
        }
    }

    private suspend fun runEmptyPayloadHandshake(
        pump: SingleCollectorRawPump,
        role: NoiseRole,
        handshake: NoiseXXHandshake,
        authorizeRemoteStatic: suspend (ByteArray) -> Boolean,
    ) {
        when (role) {
            NoiseRole.Initiator -> {
                writeFlight(pump, SecureV2HandshakeFlight.InitiatorMessageOne, handshake.writeMessage(ByteArray(0)))
                readFlight(pump, SecureV2HandshakeFlight.ResponderMessageTwo, handshake)
                authorize(handshake, authorizeRemoteStatic)
                writeFlight(pump, SecureV2HandshakeFlight.InitiatorMessageThree, handshake.writeMessage(ByteArray(0)))
            }
            NoiseRole.Responder -> {
                readFlight(pump, SecureV2HandshakeFlight.InitiatorMessageOne, handshake)
                writeFlight(pump, SecureV2HandshakeFlight.ResponderMessageTwo, handshake.writeMessage(ByteArray(0)))
                readFlight(pump, SecureV2HandshakeFlight.InitiatorMessageThree, handshake)
                authorize(handshake, authorizeRemoteStatic)
            }
        }
    }

    private suspend fun authorize(
        handshake: NoiseXXHandshake,
        authorizeRemoteStatic: suspend (ByteArray) -> Boolean,
    ) {
        val remoteStatic = handshake.copyRemoteStaticPublicKey()
        try {
            if (!authorizeRemoteStatic(remoteStatic)) {
                throw NoiseAuthenticationException("Remote Noise static key was not authorized")
            }
        } finally {
            remoteStatic.wipe()
        }
    }

    private suspend fun writeFlight(
        pump: SingleCollectorRawPump,
        flight: SecureV2HandshakeFlight,
        message: ByteArray,
    ) {
        var frame: ByteArray? = null
        try {
            frame = SecureV2EmptyHandshakeFrame.encode(flight, message)
            pump.write(frame)
        } finally {
            message.wipe()
            frame?.wipe()
        }
    }

    private suspend fun readFlight(
        pump: SingleCollectorRawPump,
        flight: SecureV2HandshakeFlight,
        handshake: NoiseXXHandshake,
    ) {
        val header = pump.readExactly(SECURE_V2_HANDSHAKE_HEADER_SIZE_BYTES)
        val length = try {
            readU16BigEndian(header[0], header[1])
        } finally {
            header.wipe()
        }
        if (length != flight.bodySizeBytes) {
            throw NoiseProtocolException(
                "${flight.name} must contain exactly ${flight.bodySizeBytes} bytes; got $length",
            )
        }
        val message = pump.readExactly(length)
        try {
            handshake.readMessage(message).requireEmptyPayload()
        } finally {
            message.wipe()
        }
    }

    private fun generateNoiseKeyPair(): NoiseKeyPair {
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
}

internal class SecureV2HandshakeOutcome(
    val connection: NoiseSecureRawConnection,
    remoteStaticPublicKey: ByteArray,
    handshakeHash: ByteArray,
) {
    private val remoteStaticBytes = remoteStaticPublicKey.copyOf()
    private val handshakeHashBytes = handshakeHash.copyOf()

    init {
        remoteStaticPublicKey.wipe()
        handshakeHash.wipe()
    }

    fun copyRemoteStaticPublicKey(): ByteArray = remoteStaticBytes.copyOf()

    fun copyHandshakeHash(): ByteArray = handshakeHashBytes.copyOf()

    fun clearMetadata() {
        remoteStaticBytes.wipe()
        handshakeHashBytes.wipe()
    }
}

private fun ByteArray.requireEmptyPayload() {
    try {
        if (isNotEmpty()) {
            throw NoiseProtocolException("Secure protocol v2 Noise handshake payload must be empty")
        }
    } finally {
        wipe()
    }
}
