package dev.p2pkit.sample.desktop

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNull

class CliOptionsTest {
    @Test
    fun namedOptionsNeverBecomeIdentity() {
        val parsed = assertIs<CliParseResult.Success>(
            parseCliOptions(arrayOf("reconnect=3,250", "trace=frames"))
        ).options

        assertNull(parsed.deviceName)
        assertNull(parsed.appId)
        assertEquals("reconnect=3,250", parsed.reconnectArg)
        assertEquals("frames", parsed.traceMode)
    }

    @Test
    fun namedOptionsMaySurroundPositionals() {
        val parsed = assertIs<CliParseResult.Success>(
            parseCliOptions(arrayOf("trace=off", "desk", "reconnect=2,0", "app"))
        ).options

        assertEquals("desk", parsed.deviceName)
        assertEquals("app", parsed.appId)
        assertEquals("reconnect=2,0", parsed.reconnectArg)
        assertEquals("off", parsed.traceMode)
    }

    @Test
    fun unknownAndDuplicateOptionsAreRejected() {
        assertIs<CliParseResult.Error>(parseCliOptions(arrayOf("--unknown")))
        assertIs<CliParseResult.Error>(parseCliOptions(arrayOf("future=value")))
        assertIs<CliParseResult.Error>(parseCliOptions(arrayOf("trace=off", "trace=frames")))
    }

    @Test
    fun helpDoesNotStartTheKit() {
        assertIs<CliParseResult.Help>(parseCliOptions(arrayOf("--help")))
        assertIs<CliParseResult.Help>(parseCliOptions(arrayOf("-h")))
    }

    @Test
    fun terminalTextDropsControlCharacters() {
        assertEquals("peer[31m-redspoof", "peer\u001B[31m-red\u0007\r\nspoof".sanitizedForTerminal())
    }
}
