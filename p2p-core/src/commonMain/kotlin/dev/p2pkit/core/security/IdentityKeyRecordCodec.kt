package dev.p2pkit.core.security

internal class IdentityRecordCorruptException(message: String) : Exception(message)

/** Strict codec for the frozen 104-byte `P2KI` identity record. */
internal object IdentityKeyRecordCodec {
    const val RECORD_SIZE: Int = 104
    private const val SCHEMA: Int = 0x01
    private const val X25519_ALGORITHM: Int = 0x01
    private val magic = byteArrayOf('P'.code.toByte(), '2'.code.toByte(), 'K'.code.toByte(), 'I'.code.toByte())

    fun encode(namespace: IdentityNamespace, keyPair: EncodedIdentityKeyPair): ByteArray {
        val result = ByteArray(RECORD_SIZE)
        magic.copyInto(result, 0)
        result[4] = SCHEMA.toByte()
        result[5] = X25519_ALGORITHM.toByte()
        // 6..7 flags remain zero.
        namespace.hashBytes().copyInto(result, 8)
        val privateKey = keyPair.privateKeyBytes()
        val publicKey = keyPair.publicKeyBytes()
        try {
            privateKey.copyInto(result, 40)
            publicKey.copyInto(result, 72)
        } finally {
            privateKey.fill(0)
            publicKey.fill(0)
        }
        return result
    }

    fun decode(namespace: IdentityNamespace, record: ByteArray): EncodedIdentityKeyPair {
        if (record.size != RECORD_SIZE) corrupt("P2KI record must be exactly 104 bytes")
        if (!record.regionEquals(0, magic)) corrupt("P2KI magic mismatch")
        if (record[4].toInt() and 0xff != SCHEMA) corrupt("unsupported P2KI schema")
        if (record[5].toInt() and 0xff != X25519_ALGORITHM) corrupt("unsupported P2KI algorithm")
        if (record[6].toInt() != 0 || record[7].toInt() != 0) corrupt("P2KI flags must be zero")
        val storedNamespace = record.copyOfRange(8, 40)
        val expectedNamespace = namespace.hashBytes()
        if (!constantTimeEquals(storedNamespace, expectedNamespace)) corrupt("P2KI namespace mismatch")
        val privateKey = record.copyOfRange(40, 72)
        val publicKey = record.copyOfRange(72, 104)
        return try {
            EncodedIdentityKeyPair(privateKey = privateKey, publicKey = publicKey)
        } finally {
            privateKey.fill(0)
            publicKey.fill(0)
        }
    }

    private fun corrupt(message: String): Nothing = throw IdentityRecordCorruptException(message)
}

/** Frozen 72-byte `P2KM` committed-state marker and 40-byte `P2KR` reset marker. */
internal object IdentityStateMarkerCodec {
    const val COMMITTED_MARKER_SIZE: Int = 72
    const val RESET_MARKER_SIZE: Int = 40
    private const val SCHEMA: Int = 0x01
    private const val X25519_ALGORITHM: Int = 0x01
    private const val LOCAL_IDENTITY_RESET_ACTION: Int = 0x01
    private val committedMagic = byteArrayOf('P'.code.toByte(), '2'.code.toByte(), 'K'.code.toByte(), 'M'.code.toByte())
    private val resetMagic = byteArrayOf('P'.code.toByte(), '2'.code.toByte(), 'K'.code.toByte(), 'R'.code.toByte())

    fun encodeCommitted(namespace: IdentityNamespace, fingerprintDigest: ByteArray): ByteArray {
        require(fingerprintDigest.size == SHA256_SIZE_BYTES) { "fingerprint digest must be 32 bytes" }
        return ByteArray(COMMITTED_MARKER_SIZE).also { marker ->
            committedMagic.copyInto(marker, 0)
            marker[4] = SCHEMA.toByte()
            marker[5] = X25519_ALGORITHM.toByte()
            namespace.hashBytes().copyInto(marker, 8)
            fingerprintDigest.copyInto(marker, 40)
        }
    }

    fun decodeCommitted(namespace: IdentityNamespace, marker: ByteArray): ByteArray {
        validateHeader(marker, COMMITTED_MARKER_SIZE, committedMagic, X25519_ALGORITHM, "P2KM")
        validateNamespace(namespace, marker, "P2KM")
        return marker.copyOfRange(40, 72)
    }

    fun encodeResetPending(namespace: IdentityNamespace): ByteArray =
        ByteArray(RESET_MARKER_SIZE).also { marker ->
            resetMagic.copyInto(marker, 0)
            marker[4] = SCHEMA.toByte()
            marker[5] = LOCAL_IDENTITY_RESET_ACTION.toByte()
            namespace.hashBytes().copyInto(marker, 8)
        }

    fun decodeResetPending(namespace: IdentityNamespace, marker: ByteArray) {
        validateHeader(marker, RESET_MARKER_SIZE, resetMagic, LOCAL_IDENTITY_RESET_ACTION, "P2KR")
        validateNamespace(namespace, marker, "P2KR")
    }

    private fun validateHeader(
        marker: ByteArray,
        expectedSize: Int,
        expectedMagic: ByteArray,
        expectedType: Int,
        name: String
    ) {
        if (marker.size != expectedSize) corrupt("$name marker has wrong length")
        if (!marker.regionEquals(0, expectedMagic)) corrupt("$name magic mismatch")
        if (marker[4].toInt() and 0xff != SCHEMA) corrupt("unsupported $name schema")
        if (marker[5].toInt() and 0xff != expectedType) corrupt("unsupported $name type")
        if (marker[6].toInt() != 0 || marker[7].toInt() != 0) corrupt("$name flags must be zero")
    }

    private fun validateNamespace(namespace: IdentityNamespace, marker: ByteArray, name: String) {
        if (!constantTimeEquals(marker.copyOfRange(8, 40), namespace.hashBytes())) {
            corrupt("$name namespace mismatch")
        }
    }

    private fun corrupt(message: String): Nothing = throw IdentityRecordCorruptException(message)
}

private fun ByteArray.regionEquals(offset: Int, expected: ByteArray): Boolean {
    if (offset < 0 || size - offset < expected.size) return false
    var difference = 0
    for (index in expected.indices) {
        difference = difference or (this[offset + index].toInt() xor expected[index].toInt())
    }
    return difference == 0
}
