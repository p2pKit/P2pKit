package dev.p2pkit.core.protocol

import kotlinx.coroutines.CancellationException
import kotlin.test.Test
import kotlin.test.assertFalse

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
}
