package dev.p2pkit.sample.diagnostics

import dev.p2pkit.core.P2pError
import dev.p2pkit.core.transfer.FileTransferState
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class SampleConsoleTest {
    @Test
    fun messageSummariesContainOnlyTypeSizeAndOpaquePeer() {
        val body = "synthetic private message 👋"
        val peer = "synthetic peer identifier"
        val size = body.toByteArray().size.toLong()
        assertEquals(
            "incoming from ${anonymizeIdentifier(peer)}: <text ${size}B>",
            SampleConsole.received(peer, true, size)
        )
        val binary = SampleConsole.received(peer, false, size)
        assertTrue(binary.contains("<binary ${size}B>"))
        val sent = SampleConsole.sendingText(2, size)
        assertTrue(sent.contains("<text ${size}B>"))
        assertTrue(sent.contains("not remote processing"))
        for (line in listOf(binary, sent)) {
            assertFalse(line.contains(body))
            assertFalse(line.contains(peer))
        }
    }

    @Test
    fun identifierHasTheSameKnownVectorAsSwiftAndNoControlCharacters() {
        assertEquals("anon-ba7816bf8f01cfea", SampleConsole.identifier("abc"))
        assertTrue(SampleConsole.identifier("name\u001b[31m\n☃").matches(Regex("anon-[0-9a-f]{16}")))
    }

    @Test
    fun sdkLoggerNeverRendersFreeTextCausesOrStackTraces() {
        val lines = mutableListOf<Pair<String, String>>()
        val logger = SampleConsoleLogger { level, line -> lines += level to line }
        val canary = "synthetic-body Alice /private/example.txt 192.0.2.9"
        val failure = object : IllegalStateException(canary, Exception(canary)) {
            override fun toString(): String = error("must not stringify exceptions")
        }
        logger.debug(canary)
        logger.info(canary)
        logger.warn(canary, failure)
        logger.error(canary, failure)
        assertEquals(listOf("D", "I", "W", "E"), lines.map { it.first })
        lines.forEach { (_, line) ->
            assertTrue(line.startsWith("SDK event (details omitted)"))
            assertFalse(line.contains(canary))
            assertFalse(line.contains("private"))
        }
    }

    @Test
    fun transferFailuresAndPeerReasonsCannotReachTheConsole() {
        val canary = "private transfer rejection /Users/example/name.txt"
        assertEquals("Rejected", SampleConsole.transferState(FileTransferState.Rejected(canary)))
        assertEquals("Cancelled", SampleConsole.transferState(FileTransferState.Cancelled(canary)))
        val failed = SampleConsole.transferState(FileTransferState.Failed(P2pError.ConnectionFailed(canary)))
        assertEquals("Failed(ConnectionFailed)", failed)
        assertEquals("Sending(progress=0.5)", SampleConsole.transferState(FileTransferState.Sending(0.5f)))
        assertEquals("Failed", SampleConsole.stateLabel("Failed(error=$canary)"))
        assertEquals("Rejected", SampleConsole.stateLabel("Rejected: $canary"))
        assertEquals("Unknown", SampleConsole.stateLabel(canary))
        assertEquals("Unknown", SampleConsole.stateLabel(null))
    }
}
