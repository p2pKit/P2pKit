@file:OptIn(ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.cinterop.addressOf
import kotlinx.cinterop.convert
import kotlinx.cinterop.readBytes
import kotlinx.cinterop.reinterpret
import kotlinx.cinterop.usePinned
import platform.Network.nw_txt_record_access_bytes
import platform.Network.nw_txt_record_create_dictionary
import platform.Network.nw_txt_record_set_key
import platform.Network.nw_txt_record_t
import platform.posix.uint8_tVar

/**
 * Bonjour helpers for the iOS LAN transport.
 *
 * Round-trips a `Map<String, String>` of TXT keys/values against the
 * `nw_txt_record_t` API so the iOS side wire-matches what JmDNS and NSD
 * emit on JVM and Android. Same key names ([LanConstants.TXT_PEER_ID] etc.)
 * land in the TXT record on every platform; consumers therefore read peers
 * identically regardless of who advertised.
 */
internal object IosBonjour {

    data class DecodedRecord(
        val properties: Map<String, String>,
        val malformed: Boolean
    )

    /**
     * Build an `nw_txt_record_t` populated with the given UTF-8 string
     * entries. Values must already encode safely as UTF-8 (the existing
     * keys — peer id, app id, device name, platform tag — all do).
     */
    fun mapToTxtRecord(entries: Map<String, String>): nw_txt_record_t {
        val record = nw_txt_record_create_dictionary()
            ?: error("nw_txt_record_create_dictionary returned null")
        for ((key, value) in entries) {
            require(lanTxtEntryFits(key, value)) {
                "Bonjour TXT '$key' exceeds the $MAX_DNS_SD_TXT_ENTRY_BYTES-byte entry limit"
            }
            val valueBytes = value.encodeToByteArray()
            val accepted = if (valueBytes.isEmpty()) {
                nw_txt_record_set_key(
                    txt_record = record,
                    key = key,
                    value = null,
                    value_len = 0.convert()
                )
            } else {
                valueBytes.usePinned { pinned ->
                    nw_txt_record_set_key(
                        txt_record = record,
                        key = key,
                        value = pinned.addressOf(0).reinterpret<uint8_tVar>(),
                        value_len = valueBytes.size.convert()
                    )
                }
            }
            check(accepted) { "Network.framework rejected Bonjour TXT key '$key'" }
        }
        return record
    }

    /**
     * Copy at most one wire-bounded TXT record while native storage is valid,
     * then select protocol keys from their complete original bytes. The
     * property iterator's C-string keys would alias `name\u0000suffix` to
     * `name`, and some records are buffers that it cannot iterate at all.
     * Unknown keys do not select fields or decode value strings. Empty and
     * boolean-style known fields both become `""`. Failed access, malformed
     * framing or invalid UTF-8 in any consumed value rejects the whole record.
     */
    fun decodeTxtRecord(record: nw_txt_record_t): DecodedRecord {
        if (record == null) return DecodedRecord(emptyMap(), malformed = false)
        var decoded: Map<String, String>? = null
        val accessed = nw_txt_record_access_bytes(record) { bytes, length ->
            decoded = decodeLanTxtRecord(length) { byteCount ->
                bytes?.readBytes(byteCount)
            }
            decoded != null
        }
        val properties = decoded?.takeIf { accessed }
        return DecodedRecord(properties.orEmpty(), malformed = properties == null)
    }

    fun txtRecordToMap(record: nw_txt_record_t): Map<String, String> =
        decodeTxtRecord(record).properties
}
