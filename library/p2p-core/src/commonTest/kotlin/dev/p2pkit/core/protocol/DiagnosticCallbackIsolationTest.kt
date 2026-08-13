package dev.p2pkit.core.protocol

import kotlinx.coroutines.CancellationException
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class DiagnosticCallbackIsolationTest {

    @Test
    fun frameTraceSinkCannotCancelOrFailProtocolWork() {
        val originalEnabled = FrameTrace.enabled
        val originalSink = FrameTrace.sink
        try {
            FrameTrace.enabled = true
            FrameTrace.sink = { throw CancellationException("diagnostic callback") }
            FrameTrace.emit { "TX PING" }
            assertFalse(FrameTrace.enabled)

            FrameTrace.enabled = true
            FrameTrace.sink = { throw AssertionError("diagnostic callback") }
            FrameTrace.emit { "RX PONG" }
            assertFalse(FrameTrace.enabled)
        } finally {
            FrameTrace.sink = originalSink
            FrameTrace.enabled = originalEnabled
        }
    }

    @Test
    fun staleFrameTraceLeaseCannotDetachNewOwner() {
        val originalEnabled = FrameTrace.enabled
        val originalSink = FrameTrace.sink
        try {
            val lines = mutableListOf<String>()
            val stale = FrameTrace.installSink(enabled = true) { lines += "stale:$it" }
            val current = FrameTrace.installSink(enabled = true) { lines += "current:$it" }

            stale.release()
            FrameTrace.emit { "TX PING" }
            assertEquals(listOf("current:TX PING"), lines)
            assertTrue(FrameTrace.enabled)

            current.release()
            FrameTrace.emit { "RX PONG" }
            assertEquals(listOf("current:TX PING"), lines)
            assertFalse(FrameTrace.enabled)
            current.release()
        } finally {
            FrameTrace.sink = originalSink
            FrameTrace.enabled = originalEnabled
        }
    }
}
