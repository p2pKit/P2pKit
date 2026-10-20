package dev.p2pkit.transport.lan

import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlinx.coroutines.runBlocking

/** Offline trace admission controls; these are not performance measurements. */
class ProtocolPingLatencyTest {
    private val sequence = listOf(
        "TX type=PING len=0B", "RX type=PING len=0B", "TX type=PONG len=0B", "RX type=PONG len=0B"
    )

    @Test
    fun completeOrderedExchangeHasExactBoundary() = runBlocking {
        val collector = PingTraceCollector(2)
        repeat(2) { sample -> sequence.forEachIndexed { index, line -> collector.observe(line, sample * 10L + index) } }
        collector.finished.await()
        assertEquals(listOf(listOf(0L, 1L, 2L, 3L), listOf(10L, 11L, 12L, 13L)), collector.samples())
    }

    @Test
    fun partialExchangeBeforeObserverBoundaryCannotCountAsSample() = runBlocking {
        val collector = PingTraceCollector(1)
        sequence.drop(1).forEachIndexed { index, line -> collector.observe(line, index.toLong()) }
        assertFailsWith<IllegalStateException> { collector.samples() }
        sequence.forEachIndexed { index, line -> collector.observe(line, 10L + index) }
        collector.finished.await()
        assertEquals(listOf(listOf(10L, 11L, 12L, 13L)), collector.samples())
    }

    @Test
    fun duplicateOutOfOrderTruncatedAndClockRegressionFailClosed() = runBlocking {
        for (lines in listOf(listOf(sequence[0], sequence[0]), listOf("TX type=DATA len=0B"))) {
            val collector = PingTraceCollector(1)
            lines.forEachIndexed { index, line -> collector.observe(line, index.toLong()) }
            assertFailsWith<IllegalStateException> { collector.finished.await() }
        }
        val partial = PingTraceCollector(1)
        sequence.take(3).forEachIndexed { index, line -> partial.observe(line, index.toLong()) }
        assertFailsWith<IllegalStateException> { partial.samples() }
        val backwards = PingTraceCollector(1)
        backwards.observe(sequence[0], 2)
        backwards.observe(sequence[1], 1)
        assertFailsWith<IllegalStateException> { backwards.finished.await() }
        Unit
    }
}
