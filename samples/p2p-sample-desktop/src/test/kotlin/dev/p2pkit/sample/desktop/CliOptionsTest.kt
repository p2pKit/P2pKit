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
    fun tracingDefaultsToNoOptInAndAcceptsExplicitOn() {
        assertNull(assertIs<CliParseResult.Success>(parseCliOptions(emptyArray())).options.traceMode)
        val on = assertIs<CliParseResult.Success>(parseCliOptions(arrayOf("trace=on", "desk"))).options
        assertEquals("on", on.traceMode)
        assertEquals("desk", on.deviceName)
        assertNull(on.appId)
        assertIs<CliParseResult.Error>(parseCliOptions(arrayOf("trace=on", "trace=off")))
        assertIs<CliParseResult.Error>(parseCliOptions(arrayOf("trace=unknown")))
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
    fun invalidReconnectNeverStartsWithSilentlyDisabledRetries() {
        val invalid = listOf(
            "", "bad", "0,1", "-1,1", "1,-1", "1", "1,2,3", "2147483648,1", "1,9223372036854775808"
        )
        for (value in invalid) {
            assertIs<CliParseResult.Error>(parseCliOptions(arrayOf("reconnect=$value")), value)
        }
        assertIs<CliParseResult.Success>(parseCliOptions(arrayOf("reconnect=5,1000")))
    }

    @Test
    fun everyNamedOptionRejectsDuplicatesAndBlankValues() {
        val options = listOf(
            "reconnect=5,1000", "trace=off", "test=PS-T05", "session=case", "role=both",
            "evidence=/tmp", "log=/tmp/events"
        )
        for (option in options) {
            assertIs<CliParseResult.Error>(parseCliOptions(arrayOf(option, option)), option)
            assertIs<CliParseResult.Error>(parseCliOptions(arrayOf(option.substringBefore('=') + "=")), option)
        }
    }

    @Test
    fun oversizedArgumentsAreRejectedWithoutRepeatingTheirValues() {
        val error = assertIs<CliParseResult.Error>(parseCliOptions(arrayOf("secret".repeat(CLI_MAX_INPUT_CHARS))))
        kotlin.test.assertFalse(error.message.contains("secret"))
        assertIs<CliParseResult.Error>(parseCliOptions(Array(33) { "argument" }))
    }

    @Test
    fun terminalTextDropsControlCharacters() {
        assertEquals("peer[31m-redspoof", "peer\u001B[31m-red\u0007\r\nspoof".sanitizedForTerminal())
    }
}
