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
        assertNull(parsed.testId)
        assertNull(parsed.sessionId)
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
        assertIs<CliParseResult.Error>(parseCliOptions(arrayOf("test=PS-T05", "test=ENV-02")))
        assertIs<CliParseResult.Error>(parseCliOptions(arrayOf("session=bad session")))
    }

    @Test
    fun diagnosticOptionsAreSeparatedAndValidated() {
        val parsed = assertIs<CliParseResult.Success>(
            parseCliOptions(
                arrayOf(
                    "Alice",
                    "test=PS-T05",
                    "session=session-shared",
                    "role=sender",
                    "evidence=/tmp/evidence",
                    "log=/tmp/events.jsonl"
                )
            )
        ).options
        assertEquals("Alice", parsed.deviceName)
        assertEquals("PS-T05", parsed.testId)
        assertEquals("session-shared", parsed.sessionId)
        assertEquals("sender", parsed.role)
        assertEquals("/tmp/evidence", parsed.evidenceDirectory)
        assertEquals("/tmp/events.jsonl", parsed.jsonlFile)
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
