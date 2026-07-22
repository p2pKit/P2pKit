package dev.p2pkit.sample.desktop.ui

import kotlin.test.Test
import kotlin.test.assertEquals

class TerminalTextTest {
    @Test
    fun stripsAnsiOscAndLineControlCharacters() {
        val hostile = "peer\u001B[31m-red\u0007\r\nspoof"
        assertEquals("peer[31m-redspoof", hostile.sanitizedForTerminal())
    }
}
