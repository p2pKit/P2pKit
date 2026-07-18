package dev.p2pkit.core.protocol

/** Decode canonical wire text without replacement characters for malformed UTF-8. */
internal fun ByteArray.decodeStrictUtf8(field: String): String = try {
    decodeToString(throwOnInvalidSequence = true)
} catch (failure: Exception) {
    throw IllegalArgumentException("$field is not valid UTF-8", failure)
}

/** Validate bounded text before it reaches identity, filesystem, UI, or log surfaces. */
internal fun validateWireText(
    value: String,
    field: String,
    maxChars: Int,
    maxUtf8Bytes: Int,
    requireNonBlank: Boolean = false
) {
    require(!requireNonBlank || value.isNotBlank()) { "$field must not be blank" }
    require(value.length <= maxChars) { "$field too long: ${value.length} > $maxChars characters" }
    val encodedSize = try {
        value.encodeToByteArray(throwOnInvalidSequence = true).size
    } catch (failure: Exception) {
        throw IllegalArgumentException("$field contains an invalid Unicode sequence", failure)
    }
    require(encodedSize <= maxUtf8Bytes) { "$field too long: $encodedSize > $maxUtf8Bytes UTF-8 bytes" }
    require(value.none(Char::isForbiddenWireControl)) { "$field contains forbidden control characters" }
}

/** Fixed-size safe detail for peer-controlled diagnostics. */
internal fun Throwable.safeDiagnosticDetail(): String {
    val raw = message ?: this::class.simpleName ?: "decode failure"
    return buildString(minOf(raw.length, MAX_DIAGNOSTIC_CHARS)) {
        for (character in raw.take(MAX_DIAGNOSTIC_CHARS)) {
            append(if (character.isForbiddenWireControl()) '\uFFFD' else character)
        }
    }
}

private fun Char.isForbiddenWireControl(): Boolean {
    val value = code
    return value in 0x00..0x1F || value in 0x7F..0x9F ||
        value == 0x061C || value == 0x200E || value == 0x200F ||
        value in 0x202A..0x202E || value in 0x2066..0x2069
}

private const val MAX_DIAGNOSTIC_CHARS: Int = 160
