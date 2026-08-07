package dev.p2pkit.transport.lan

import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class JvmLanDiagTest {

    private var previousEnabled: Boolean = false

    @BeforeTest
    fun enableSink() {
        previousEnabled = JvmLanDiag.enabled
        JvmLanDiag.enabled = true
    }

    @AfterTest
    fun restoreSink() {
        JvmLanDiag.enabled = previousEnabled
    }

    @Test
    fun sinkSanitizesPeerControlledTagAndMessage() {
        val marker = "diag-${System.nanoTime()}"
        JvmLanDiag.log("peer\u001B[31m", "$marker\u202Espoof")

        val line = JvmLanDiag.events.replayCache.lastOrNull { marker in it }
        assertNotNull(line)
        assertFalse('\u001B' in line)
        assertFalse('\u202E' in line)
        assertTrue('\uFFFD' in line)
    }
}
