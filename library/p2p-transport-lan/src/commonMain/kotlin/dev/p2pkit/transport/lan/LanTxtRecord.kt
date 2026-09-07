package dev.p2pkit.transport.lan

import kotlin.text.CharacterCodingException

/**
 * Decode original DNS-SD TXT RDATA, before a dependency can normalize it.
 * JmDNS 3.6.3 normalizes values even in `getPropertyBytes`, so neither of its
 * property accessors is a suitable byte-validation boundary.
 *
 * Only the fixed ASCII protocol keys are consumed. Unknown values are skipped
 * without decoding or allocating them; retained state is bounded by that key
 * set and the 255-byte character-string limit. Null/empty RDATA means no fields.
 * Malformed framing or UTF-8 in any consumed occurrence rejects the whole record,
 * including an invalid duplicate followed by a valid value. Valid duplicates
 * retain their last value, matching the Apple decoder's wire-order traversal.
 * Empty and boolean-style fields both remain empty, as on Apple. No accepted
 * value is trimmed, NUL-stripped or replacement-normalized; semantic validation
 * still belongs to [validateLanDiscoveryRecord].
 */
internal fun decodeLanTxtRecord(bytes: ByteArray?): Map<String, String>? {
    if (bytes == null) return emptyMap()
    if (bytes.size > MAX_DNS_SD_TXT_RECORD_BYTES) return null
    val properties = mutableMapOf<String, String>()
    var offset = 0
    while (offset < bytes.size) {
        val length = bytes[offset++].toInt() and 0xFF
        if (length > bytes.size - offset) return null
        val end = offset + length
        var keyEnd = offset
        while (keyEnd < end && bytes[keyEnd] != '='.code.toByte()) keyEnd++
        val key = LanConstants.DISCOVERY_TXT_KEYS.firstOrNull { candidate ->
            candidate.length == keyEnd - offset &&
                candidate.indices.all { bytes[offset + it].toInt() == candidate[it].code }
        }
        if (key != null) {
            val valueStart = if (keyEnd == end) end else keyEnd + 1
            val value = try {
                bytes.decodeToString(valueStart, end, throwOnInvalidSequence = true)
            } catch (_: CharacterCodingException) {
                return null
            }
            properties[key] = value
        }
        offset = end
    }
    return properties
}

/** DNS resource-record RDLENGTH is an unsigned 16-bit value. */
private const val MAX_DNS_SD_TXT_RECORD_BYTES: Int = 65_535
