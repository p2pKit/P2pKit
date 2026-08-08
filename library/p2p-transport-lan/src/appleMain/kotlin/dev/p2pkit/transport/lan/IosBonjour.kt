@file:OptIn(ExperimentalForeignApi::class, BetaInteropApi::class)

package dev.p2pkit.transport.lan

import kotlinx.cinterop.BetaInteropApi
import kotlinx.cinterop.ExperimentalForeignApi
import kotlinx.cinterop.addressOf
import kotlinx.cinterop.convert
import kotlinx.cinterop.readBytes
import kotlinx.cinterop.reinterpret
import kotlinx.cinterop.toKString
import kotlinx.cinterop.usePinned
import platform.Network.nw_txt_record_apply
import platform.Network.nw_txt_record_create_dictionary
import platform.Network.nw_txt_record_find_key_empty_value
import platform.Network.nw_txt_record_find_key_no_value
import platform.Network.nw_txt_record_find_key_non_empty_value
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
     * Decode the bounded protocol key/value pairs in [record] into a map.
     * Unknown keys are skipped before reading their values, so a foreign or
     * future record cannot force allocations for data this version ignores.
     * Empty values surface as `""`; boolean-style entries with no value at
     * all ALSO surface as `""` (indistinguishable from empty-value entries
     * after decoding), so every key present in the record appears in the map.
     */
    fun decodeTxtRecord(record: nw_txt_record_t): DecodedRecord {
        if (record == null) return DecodedRecord(emptyMap(), malformed = false)
        val out = mutableMapOf<String, String>()
        var valid = true
        nw_txt_record_apply(record) { keyPtr, found, valuePtr, valueLen ->
            val key = keyPtr?.toKString() ?: return@nw_txt_record_apply true
            if (key !in LanConstants.DISCOVERY_TXT_KEYS) return@nw_txt_record_apply true
            when (found) {
                nw_txt_record_find_key_non_empty_value -> {
                    val valueLength = valueLen.toInt()
                    val maximum = MAX_DNS_SD_TXT_ENTRY_BYTES - key.encodeToByteArray().size - 1
                    if (valuePtr != null && valueLength in 1..maximum) {
                        val bytes = valuePtr.readBytes(valueLength)
                        val decoded = try {
                            bytes.decodeToString(throwOnInvalidSequence = true)
                        } catch (_: Exception) {
                            valid = false
                            return@nw_txt_record_apply false
                        }
                        out[key] = decoded
                    } else {
                        valid = false
                        return@nw_txt_record_apply false
                    }
                }

                nw_txt_record_find_key_empty_value -> {
                    out[key] = ""
                }

                nw_txt_record_find_key_no_value -> {
                    out[key] = ""
                }
                // .invalid / .not_present — skip.
            }
            true
        }
        return if (valid) {
            DecodedRecord(out, malformed = false)
        } else {
            DecodedRecord(emptyMap(), malformed = true)
        }
    }

    fun txtRecordToMap(record: nw_txt_record_t): Map<String, String> =
        decodeTxtRecord(record).properties
}
