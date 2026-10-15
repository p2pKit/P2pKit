package dev.p2pkit.sample.rpc.lab

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFails

class LabVaultTest {
    @Test
    fun controlFilesRejectDuplicatesAndNonAsciiInsteadOfSilentlyNormalizing() {
        assertEquals(mapOf("schema" to "1"), LabFiles.parse("schema=1\n".toByteArray()))
        for (bad in listOf("schema=1\nschema=2\n", "empty=\n", "key=value\r\n", "key=private\u0000value\n")) {
            assertFails { LabFiles.parse(bad.toByteArray()) }
        }
    }
}
