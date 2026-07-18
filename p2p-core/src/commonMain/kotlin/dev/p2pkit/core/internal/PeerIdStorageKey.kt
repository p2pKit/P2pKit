package dev.p2pkit.core.internal

import dev.p2pkit.core.security.platformSecurityCryptography
import dev.p2pkit.core.security.toLowerHex

/** Collision-resistant, path-safe namespace for deprecated UUID PeerId storage. */
internal fun peerIdStorageKey(rawAppId: String): String {
    val label = "dev.p2pkit.legacy-peer-id-storage.v2\u0000".encodeToByteArray()
    val inputSize = label.size.toLong() + Int.SIZE_BYTES + rawAppId.length.toLong() * 2L
    require(inputSize <= Int.MAX_VALUE) { "AppId is too large for persistent PeerId storage" }
    val input = ByteArray(inputSize.toInt())
    label.copyInto(input)
    var offset = label.size
    input[offset++] = (rawAppId.length ushr 24).toByte()
    input[offset++] = (rawAppId.length ushr 16).toByte()
    input[offset++] = (rawAppId.length ushr 8).toByte()
    input[offset++] = rawAppId.length.toByte()
    // Hash UTF-16 code units directly. Unlike replacement-based UTF-8
    // encoding, this remains injective before hashing even for malformed
    // surrogate input accepted by the deprecated plaintext AppId path.
    for (character in rawAppId) {
        input[offset++] = (character.code ushr 8).toByte()
        input[offset++] = character.code.toByte()
    }
    val digest = platformSecurityCryptography().sha256(input)
    return try {
        digest.toLowerHex()
    } finally {
        input.fill(0)
        digest.fill(0)
    }
}
