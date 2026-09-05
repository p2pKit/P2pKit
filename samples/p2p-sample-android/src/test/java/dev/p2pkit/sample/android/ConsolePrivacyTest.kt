package dev.p2pkit.sample.android

import dev.p2pkit.sample.diagnostics.SampleConsole
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class ConsolePrivacyTest {
    @Test
    fun messageFormatterUsesByteCountsInsteadOfTheMessageOrPeerIdentity() {
        val body = "synthetic private text 👋"
        val peerId = "synthetic-stable-peer-id"
        val size = body.toByteArray().size.toLong()
        val received = SampleConsole.received(peerId, true, size)
        val sent = SampleConsole.sendingText(2, size)
        for (line in listOf(received, sent)) {
            assertTrue(line.contains("<text ${size}B>"))
            assertFalse(line.contains(body))
            assertFalse(line.contains(peerId))
        }
    }

    @Test
    fun actualTailLoggerDropsDetailsBeforeBothLogcatAndTheInAppTail() {
        val logcat = mutableListOf<Pair<String, String>>()
        val tail = mutableListOf<Pair<String, String>>()
        // No Android runtime is mocked: only the final platform writer is injected.
        val logger = TailLogger(
            recordLog = { level, line -> tail += level to line },
            logcat = { level, line -> logcat += level to line }
        )
        val canary = "Synthetic Private Name /private/example.txt 192.0.2.9"
        logger.debug(canary)
        logger.info(canary)
        logger.warn(canary, IllegalArgumentException(canary))
        logger.error(canary, IllegalStateException(canary, Exception(canary)))
        assertEquals(listOf("D", "I", "W", "E"), logcat.map { it.first })
        assertEquals(logcat, tail)
        assertTrue(logcat.last().second.contains("IllegalStateException"))
        logcat.forEach { (_, line) -> assertFalse(line.contains(canary)) }
    }
}
