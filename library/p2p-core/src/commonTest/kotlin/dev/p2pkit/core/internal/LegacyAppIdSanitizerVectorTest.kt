package dev.p2pkit.core.internal

import kotlin.test.Test
import kotlin.test.assertEquals

class LegacyAppIdSanitizerVectorTest {
    @Test
    fun historicalMappingsAndIntentionalCollisionsRemainFrozen() {
        val prefix64 = "0123456789012345678901234567890123456789012345678901234567890123"
        val vectors = listOf(
            "com.example.transfer" to "com.example.transfer",
            "" to "_",
            " \t\r\n" to "_",
            "." to "_",
            ".." to "_",
            "..." to "_.",
            "...." to "_._",
            "a....b" to "a._._b",
            ".-_" to "-_",
            "../../etc/passwd" to "__.__etc_passwd",
            "tenant/a" to "tenant_a",
            "tenant?a" to "tenant_a",
            "a b:c\\d" to "a_b_c_d",
            "éΩ中٣" to "éΩ中٣",
            "e\u0301" to "e_",
            "\uD83D\uDE00" to "__",
            "\uD801\uDC00" to "__",
            "x\uD800y" to "x_y",
            "x\uDC00y" to "x_y",
            prefix64.dropLast(1) to "012345678901234567890123456789012345678901234567890123456789012",
            prefix64 to "0123456789012345678901234567890123456789012345678901234567890123",
            "$prefix64!" to "0123456789012345678901234567890123456789012345678901234567890123",
            "$prefix64-one" to "0123456789012345678901234567890123456789012345678901234567890123",
            "$prefix64-two" to "0123456789012345678901234567890123456789012345678901234567890123"
        )

        vectors.forEachIndexed { index, (raw, expected) ->
            assertEquals(expected, sanitizeAppIdLegacySegment(raw), "legacy compatibility vector $index")
        }
    }
}
