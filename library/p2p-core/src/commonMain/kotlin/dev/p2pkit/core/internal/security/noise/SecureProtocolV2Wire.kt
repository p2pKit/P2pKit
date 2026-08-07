package dev.p2pkit.core.internal.security.noise

internal const val SECURE_V2_PREFACE_SIZE_BYTES: Int = 16
internal const val SECURE_V2_HANDSHAKE_HEADER_SIZE_BYTES: Int = 2
internal const val SECURE_V2_MAX_APP_ID_UTF8_BYTES: Int = 1_024
internal const val SECURE_V2_MAX_HANDSHAKE_PAYLOAD_BYTES: Int = 4_096
internal const val SECURE_V2_MAX_HANDSHAKE_MESSAGE_BYTES: Int =
    96 + SECURE_V2_MAX_HANDSHAKE_PAYLOAD_BYTES

private val secureV2Magic: ByteArray = byteArrayOf(
    'P'.code.toByte(),
    '2'.code.toByte(),
    'K'.code.toByte(),
    'S'.code.toByte(),
)
private val secureV2PrologueDomain: ByteArray =
    "dev.p2pkit.secure-channel.v2\u0000".encodeToByteArray()

internal data class SecureV2Preface(
    val role: NoiseRole,
) {
    fun encode(): ByteArray = ByteArray(SECURE_V2_PREFACE_SIZE_BYTES).also { encoded ->
        secureV2Magic.copyInto(encoded)
        encoded[4] = PREFACE_FORMAT_VERSION
        encoded[5] = APP_PROTOCOL_MAJOR
        encoded[6] = APP_PROTOCOL_MINOR
        encoded[7] = CIPHER_SUITE
        encoded[8] = when (role) {
            NoiseRole.Initiator -> ROLE_INITIATOR
            NoiseRole.Responder -> ROLE_RESPONDER
        }
        // byte 9 is the flags byte and bytes 10..15 are reserved. Version 2
        // requires all of them to be zero so future meanings fail closed.
    }

    companion object {
        private const val PREFACE_FORMAT_VERSION: Byte = 1
        private const val APP_PROTOCOL_MAJOR: Byte = 2
        private const val APP_PROTOCOL_MINOR: Byte = 0
        private const val CIPHER_SUITE: Byte = 1
        private const val ROLE_INITIATOR: Byte = 1
        private const val ROLE_RESPONDER: Byte = 2

        fun decode(encoded: ByteArray, expectedRole: NoiseRole? = null): SecureV2Preface {
            requireSize(encoded, SECURE_V2_PREFACE_SIZE_BYTES, "Secure protocol preface")
            if (!encoded.copyOfRange(0, secureV2Magic.size).contentEquals(secureV2Magic)) {
                throw NoiseProtocolException("Secure protocol preface has invalid magic")
            }
            if (encoded[4] != PREFACE_FORMAT_VERSION) {
                throw NoiseProtocolException("Unsupported secure preface format: ${encoded[4].toUByte()}")
            }
            if (encoded[5] != APP_PROTOCOL_MAJOR || encoded[6] != APP_PROTOCOL_MINOR) {
                throw NoiseProtocolException(
                    "Unsupported application protocol version: ${encoded[5].toUByte()}.${encoded[6].toUByte()}",
                )
            }
            if (encoded[7] != CIPHER_SUITE) {
                throw NoiseProtocolException("Unsupported secure cipher suite: ${encoded[7].toUByte()}")
            }
            val role = when (encoded[8]) {
                ROLE_INITIATOR -> NoiseRole.Initiator
                ROLE_RESPONDER -> NoiseRole.Responder
                else -> throw NoiseProtocolException("Invalid secure preface role: ${encoded[8].toUByte()}")
            }
            if (expectedRole != null && role != expectedRole) {
                throw NoiseProtocolException("Expected $expectedRole secure preface, received $role")
            }
            for (index in 9 until SECURE_V2_PREFACE_SIZE_BYTES) {
                if (encoded[index] != 0.toByte()) {
                    throw NoiseProtocolException("Secure preface flags and reserved bytes must be zero")
                }
            }
            return SecureV2Preface(role)
        }
    }
}

internal object SecureV2Prologue {
    fun encode(
        appId: String,
        initiatorPreface: ByteArray,
        responderPreface: ByteArray,
    ): ByteArray {
        val appIdBytes = appId.encodeToByteArray()
        require(appIdBytes.size <= SECURE_V2_MAX_APP_ID_UTF8_BYTES) {
            "appId UTF-8 representation must not exceed $SECURE_V2_MAX_APP_ID_UTF8_BYTES bytes"
        }
        SecureV2Preface.decode(initiatorPreface, NoiseRole.Initiator)
        SecureV2Preface.decode(responderPreface, NoiseRole.Responder)

        return ByteArray(
            secureV2PrologueDomain.size +
                SECURE_V2_HANDSHAKE_HEADER_SIZE_BYTES +
                appIdBytes.size +
                initiatorPreface.size +
                responderPreface.size,
        ).also { prologue ->
            var offset = 0
            secureV2PrologueDomain.copyInto(prologue, offset)
            offset += secureV2PrologueDomain.size
            writeU16BigEndian(appIdBytes.size, prologue, offset)
            offset += SECURE_V2_HANDSHAKE_HEADER_SIZE_BYTES
            appIdBytes.copyInto(prologue, offset)
            offset += appIdBytes.size
            initiatorPreface.copyInto(prologue, offset)
            offset += initiatorPreface.size
            responderPreface.copyInto(prologue, offset)
        }
    }
}

internal object SecureV2HandshakeFrame {
    fun encode(message: ByteArray): ByteArray {
        if (message.size > SECURE_V2_MAX_HANDSHAKE_MESSAGE_BYTES) {
            throw NoiseProtocolException(
                "Noise handshake message exceeds $SECURE_V2_MAX_HANDSHAKE_MESSAGE_BYTES bytes",
            )
        }
        return ByteArray(SECURE_V2_HANDSHAKE_HEADER_SIZE_BYTES + message.size).also { frame ->
            writeU16BigEndian(message.size, frame, 0)
            message.copyInto(frame, SECURE_V2_HANDSHAKE_HEADER_SIZE_BYTES)
        }
    }

    fun decode(frame: ByteArray): ByteArray {
        if (frame.size < SECURE_V2_HANDSHAKE_HEADER_SIZE_BYTES) {
            throw NoiseProtocolException("Truncated Noise handshake frame header")
        }
        val length = readU16BigEndian(frame[0], frame[1])
        if (length > SECURE_V2_MAX_HANDSHAKE_MESSAGE_BYTES) {
            throw NoiseProtocolException(
                "Noise handshake message exceeds $SECURE_V2_MAX_HANDSHAKE_MESSAGE_BYTES bytes",
            )
        }
        if (frame.size != SECURE_V2_HANDSHAKE_HEADER_SIZE_BYTES + length) {
            throw NoiseProtocolException("Noise handshake frame length does not match its payload")
        }
        return frame.copyOfRange(SECURE_V2_HANDSHAKE_HEADER_SIZE_BYTES, frame.size)
    }
}

/** Production v2 uses empty Noise handshake payloads for all three flights. */
internal enum class SecureV2HandshakeFlight(
    val bodySizeBytes: Int,
) {
    InitiatorMessageOne(32),
    ResponderMessageTwo(96),
    InitiatorMessageThree(64),
}

internal object SecureV2EmptyHandshakeFrame {
    fun encode(flight: SecureV2HandshakeFlight, message: ByteArray): ByteArray {
        validate(flight, message)
        return SecureV2HandshakeFrame.encode(message)
    }

    fun decode(flight: SecureV2HandshakeFlight, frame: ByteArray): ByteArray =
        SecureV2HandshakeFrame.decode(frame).also { validate(flight, it) }

    private fun validate(flight: SecureV2HandshakeFlight, message: ByteArray) {
        if (message.size != flight.bodySizeBytes) {
            throw NoiseProtocolException(
                "${flight.name} must contain exactly ${flight.bodySizeBytes} bytes; got ${message.size}",
            )
        }
    }
}

internal fun readU16BigEndian(first: Byte, second: Byte): Int =
    ((first.toInt() and 0xff) shl 8) or (second.toInt() and 0xff)

internal fun writeU16BigEndian(value: Int, destination: ByteArray, offset: Int) {
    require(value in 0..UShort.MAX_VALUE.toInt()) { "Value must fit in an unsigned 16-bit integer" }
    require(offset >= 0 && offset + 1 < destination.size) { "U16 destination is too small" }
    destination[offset] = (value ushr 8).toByte()
    destination[offset + 1] = value.toByte()
}
