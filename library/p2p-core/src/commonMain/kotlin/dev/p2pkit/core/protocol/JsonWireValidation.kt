package dev.p2pkit.core.protocol

import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.json.Json

/**
 * Reject ambiguous duplicate fields before kotlinx.serialization builds a
 * typed object. Its JSON decoder otherwise keeps one duplicate value, while
 * another implementation is allowed to keep the other. Security-sensitive
 * HELLO fields and file-offer metadata must therefore have one unambiguous
 * interpretation across implementations.
 *
 * Only top-level object fields are part of the current wire schemas. Unknown
 * nested extension values remain forward-compatible and are left to the JSON
 * decoder, but every top-level field (known or unknown) must be unique.
 */
internal fun rejectDuplicateTopLevelJsonFields(jsonText: String, payloadName: String) {
    val containers = mutableListOf<Char>()
    val fields = mutableSetOf<String>()
    var index = 0
    while (index < jsonText.length) {
        when (val character = jsonText[index]) {
            '{', '[' -> {
                containers += character
                index++
            }
            '}', ']' -> {
                if (containers.isNotEmpty()) containers.removeAt(containers.lastIndex)
                index++
            }
            '"' -> {
                val tokenEnd = findJsonStringEnd(jsonText, index, payloadName)
                if (containers.size == 1 && containers.last() == '{' &&
                    nextJsonTokenIsColon(jsonText, tokenEnd)
                ) {
                    val field = decodeJsonFieldName(jsonText.substring(index, tokenEnd), payloadName)
                    if (!fields.add(field)) {
                        throw IllegalArgumentException(
                            "$payloadName contains a duplicate top-level field"
                        )
                    }
                }
                index = tokenEnd
            }
            else -> index++
        }
    }
}

private fun findJsonStringEnd(text: String, start: Int, payloadName: String): Int {
    var escaped = false
    var index = start + 1
    while (index < text.length) {
        val character = text[index++]
        when {
            escaped -> escaped = false
            character == '\\' -> escaped = true
            character == '"' -> return index
        }
    }
    throw IllegalArgumentException("$payloadName contains an unterminated JSON string")
}

private fun nextJsonTokenIsColon(text: String, tokenEnd: Int): Boolean {
    var index = tokenEnd
    while (index < text.length && text[index].isJsonWhitespace()) index++
    return index < text.length && text[index] == ':'
}

private fun decodeJsonFieldName(token: String, payloadName: String): String = try {
    JSON_FIELD_DECODER.decodeFromString<String>(token)
} catch (_: Exception) {
    // Never retain peer-controlled field text in an exception or diagnostic.
    throw IllegalArgumentException("$payloadName contains an invalid JSON field name")
}

private fun Char.isJsonWhitespace(): Boolean =
    this == ' ' || this == '\t' || this == '\r' || this == '\n'

@OptIn(ExperimentalSerializationApi::class)
private val JSON_FIELD_DECODER = Json {
    exceptionsWithDebugInfo = false
}
