package dev.p2pkit.transport.lan

import dev.p2pkit.core.transport.TransportSecurityProfile

/** Synthetic wire bytes, not values round-tripped through a dependency's property decoder. */
internal object LanTxtRecordFixtures {
    val malformedUtf8: List<Pair<String, ByteArray>>
        get() = listOf(
            "truncated two-byte sequence" to byteArrayOf(0xC3.toByte()),
            "invalid continuation" to byteArrayOf(0xC3.toByte(), 0x28),
            "isolated continuation" to byteArrayOf(0x80.toByte()),
            "overlong encoding" to byteArrayOf(0xC0.toByte(), 0xAF.toByte()),
            "truncated three-byte sequence" to byteArrayOf(0xE2.toByte(), 0x82.toByte()),
            "encoded surrogate" to byteArrayOf(0xED.toByte(), 0xA0.toByte(), 0x80.toByte()),
            "truncated four-byte sequence" to byteArrayOf(0xF0.toByte(), 0x9F.toByte(), 0x93.toByte()),
            "beyond Unicode range" to byteArrayOf(0xF4.toByte(), 0x90.toByte(), 0x80.toByte(), 0x80.toByte()),
            "invalid lead byte" to byteArrayOf(0xFF.toByte())
        )

    fun properties(profile: TransportSecurityProfile): Map<String, ByteArray?> = buildMap {
        put(LanConstants.TXT_PEER_ID, "remote".encodeToByteArray())
        put(LanConstants.TXT_APP_ID, "lan-txt-test".encodeToByteArray())
        put(LanConstants.TXT_DEVICE_NAME, "Remote".encodeToByteArray())
        put(LanConstants.TXT_PLATFORM, "JVM_DESKTOP".encodeToByteArray())
        put(LanConstants.TXT_CAPABILITIES, "LAN".encodeToByteArray())
        put(LanConstants.TXT_PROTOCOL_VERSION, LanConstants.protocolVersion(profile).toString().encodeToByteArray())
        if (profile == TransportSecurityProfile.AuthenticatedV2) {
            put(LanConstants.TXT_FINGERPRINT, ("p2f1-" + "a".repeat(52)).encodeToByteArray())
        }
    }

    /** Null means a boolean-style key, distinct on the wire from an empty value. */
    fun encode(entries: List<Pair<String, ByteArray?>>): ByteArray = buildList {
        for ((key, value) in entries) {
            val entry = key.encodeToByteArray() + if (value == null) byteArrayOf() else byteArrayOf(61) + value
            require(entry.size in 1..255)
            add(entry.size.toByte())
            addAll(entry.toList())
        }
    }.toByteArray()
}
