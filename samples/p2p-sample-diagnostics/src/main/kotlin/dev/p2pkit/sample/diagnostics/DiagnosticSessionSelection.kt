package dev.p2pkit.sample.diagnostics

import kotlinx.serialization.decodeFromString
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive

/** Malformed or ambiguously attributed records are never deleted by a session-specific clear. */
internal fun diagnosticLineBelongsToSession(line: String, sessionId: String): Boolean =
    runCatching {
        if (!hasStrictTokensAndOneSessionKey(line)) return@runCatching false
        val id = (JSON.parseToJsonElement(line) as? JsonObject)?.get("testSessionId") as? JsonPrimitive
        id?.isString == true && id.content == sessionId
    }.getOrDefault(false)

/**
 * The JSON library checks document structure, but its tree reader admits non-JSON bare
 * primitives/raw controls and overwrites duplicate keys. Check every token before parsing,
 * including values hidden by duplicate unrelated keys. The trailing-comma guard is mirrored
 * on Swift, where Foundation accepts that non-JSON syntax. This is iterative and input-bounded.
 */
private fun hasStrictTokensAndOneSessionKey(line: String): Boolean {
    var index = 0
    var depth = 0
    var sessionKeys = 0
    while (index < line.length) {
        when (val char = line[index]) {
            ' ', '\t', '\r', '\n' -> index++
            '{', '[' -> {
                depth++
                index++
            }
            '}', ']' -> {
                depth--
                index++
            }
            ':' -> index++
            ',' -> {
                var next = index + 1
                while (next < line.length && line[next] in JSON_WHITESPACE) next++
                if (next == line.length || line[next] == '}' || line[next] == ']') return false
                index++
            }
            '"' -> {
                val start = index++
                var closed = false
                while (index < line.length) {
                    val value = line[index++]
                    if (value == '"') {
                        closed = true
                        break
                    }
                    if (value < ' ') return false
                    if (value == '\\') {
                        if (index == line.length) return false
                        when (line[index++]) {
                            '"', '\\', '/', 'b', 'f', 'n', 'r', 't' -> Unit
                            'u' -> repeat(4) {
                                if (index == line.length || line[index++] !in JSON_HEX) return false
                            }
                            else -> return false
                        }
                    }
                }
                if (!closed) return false
                var next = index
                while (next < line.length && line[next] in JSON_WHITESPACE) next++
                if (depth == 1 && next < line.length && line[next] == ':' &&
                    JSON.decodeFromString<String>(line.substring(start, index)) == "testSessionId"
                ) {
                    sessionKeys++
                    if (sessionKeys > 1) return false
                }
            }
            else -> {
                if (char < ' ') return false
                val start = index
                while (index < line.length && line[index] !in JSON_DELIMITERS) index++
                val token = line.substring(start, index)
                if (token !in JSON_LITERALS && !JSON_NUMBER.matches(token)) return false
            }
        }
        if (depth < 0) return false
    }
    return depth == 0 && sessionKeys == 1
}

private const val JSON_WHITESPACE = " \t\r\n"
private const val JSON_DELIMITERS = " \t\r\n{}[]:,\""
private const val JSON_HEX = "0123456789abcdefABCDEF"
private val JSON_LITERALS = setOf("true", "false", "null")
private val JSON_NUMBER = Regex("-?(0|[1-9][0-9]*)(\\.[0-9]+)?([eE][+-]?[0-9]+)?")
