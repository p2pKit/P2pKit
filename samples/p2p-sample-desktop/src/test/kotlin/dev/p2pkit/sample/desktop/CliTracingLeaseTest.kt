package dev.p2pkit.sample.desktop

import dev.p2pkit.core.protocol.FrameTrace
import dev.p2pkit.transport.lan.JvmLanDiag
import java.io.ByteArrayOutputStream
import java.io.PrintStream
import kotlinx.coroutines.CancellationException
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue

class CliTracingLeaseTest {
    @Test
    fun defaultAndExplicitOffDoNotEnableEitherConsoleStream() = withCleanTracing {
        for (args in listOf(emptyArray(), arrayOf("trace=off"))) {
            val mode = assertIs<CliParseResult.Success>(parseCliOptions(args)).options.traceMode
            val output = captureConsole {
                CliTracingLease.acquire(mode) { error("No frame callback without opt-in") }.use {
                    assertFalse(JvmLanDiag.enabled)
                    assertFalse(JvmLanDiag.traceFrames)
                    assertFalse(FrameTrace.enabled)
                    JvmLanDiag.log("test", "synthetic-lan-line")
                    JvmLanDiag.frame("test", "synthetic-byte-chunk")
                }
            }
            assertEquals("", output)
        }
    }

    @Test
    fun onAndFramesEnableOnlyTheirRequestedDetailAndRestoreTheDefaults() = withCleanTracing {
        for (mode in listOf("on", "frames")) {
            val recorded = mutableListOf<String>()
            val output = captureConsole {
                CliTracingLease.acquire(mode, recorded::add).use {
                    assertTrue(JvmLanDiag.enabled)
                    assertEquals(mode == "frames", JvmLanDiag.traceFrames)
                    assertTrue(FrameTrace.enabled)
                    JvmLanDiag.log("test", "synthetic-lan-line")
                    JvmLanDiag.frame("test", "synthetic-byte-chunk")
                    // Invoke the installed sink, not a simulated network transfer.
                    FrameTrace.sink("TX type=DATA len=16B")
                }
            }
            assertTrue(output.contains("P2pKitLAN "))
            assertTrue(output.contains("P2pKitFRAME TX type=DATA len=16B"))
            assertEquals(mode == "frames", output.contains("synthetic-byte-chunk"))
            assertEquals(listOf("TX type=DATA len=16B"), recorded)
            assertFalse(JvmLanDiag.enabled)
            assertFalse(JvmLanDiag.traceFrames)
            assertFalse(FrameTrace.enabled)
        }
    }

    @Test
    fun overlappingRequestsReleaseOnlyTheirOwnDetailAndTokensAreIdempotent() = withCleanTracing {
        CliTracingLease.acquire("on") {}.use { first ->
            CliTracingLease.acquire("frames") {}.use { second ->
                first.close()
                first.close()
                assertTrue(JvmLanDiag.enabled)
                assertTrue(JvmLanDiag.traceFrames)
                assertTrue(FrameTrace.enabled)
                second.close()
                assertFalse(JvmLanDiag.enabled)
                assertFalse(JvmLanDiag.traceFrames)
                CliTracingLease.acquire("on") {}.use {
                    second.close()
                    assertTrue(JvmLanDiag.enabled)
                    assertFalse(JvmLanDiag.traceFrames)
                    assertTrue(FrameTrace.enabled)
                }
            }
        }
    }

    @Test
    fun removingByteRequestWhileAnOnOwnerRemainsDoesNotLatchByteTracing() = withCleanTracing {
        CliTracingLease.acquire("on") {}.use {
            CliTracingLease.acquire("frames") {}.use { bytes ->
                bytes.close()
                assertTrue(JvmLanDiag.enabled)
                assertFalse(JvmLanDiag.traceFrames)
                // FrameTrace intentionally has no restoration stack.
                assertFalse(FrameTrace.enabled)
            }
        }
        assertFalse(JvmLanDiag.enabled)
    }

    @Test
    fun offDoesNotDisableAnExplicitHostOverride() = withCleanTracing {
        JvmLanDiag.enabled = true
        JvmLanDiag.traceFrames = true
        val hostSink: (String) -> Unit = {}
        FrameTrace.installSink(enabled = true, sink = hostSink).let { host ->
            try {
                CliTracingLease.acquire("off") {}.use {
                    assertTrue(JvmLanDiag.enabled)
                    assertTrue(JvmLanDiag.traceFrames)
                    assertTrue(FrameTrace.enabled)
                    assertSame(hostSink, FrameTrace.sink)
                }
                assertTrue(JvmLanDiag.enabled)
                assertTrue(JvmLanDiag.traceFrames)
                assertSame(hostSink, FrameTrace.sink)
            } finally {
                host.release()
            }
        }
    }

    @Test
    fun aDefaultOwnerDoesNotDisableAnotherActiveOptIn() = withCleanTracing {
        CliTracingLease.acquire("on") {}.use { active ->
            val activeSink = FrameTrace.sink
            CliTracingLease.acquire(null) {}.use {
                assertTrue(JvmLanDiag.enabled)
                assertSame(activeSink, FrameTrace.sink)
                active.close()
                assertFalse(JvmLanDiag.enabled)
                assertFalse(JvmLanDiag.traceFrames)
                assertFalse(FrameTrace.enabled)
            }
        }
    }

    @Test
    fun lexicalCleanupRestoresFlagsOnFailureAndPreservesCancellationIdentity() = withCleanTracing {
        val failure = IllegalStateException("synthetic start failure")
        assertSame(failure, assertFailsWith<IllegalStateException> {
            CliTracingLease.acquire("frames") {}.use { throw failure }
        })
        assertFalse(JvmLanDiag.enabled)
        assertFalse(JvmLanDiag.traceFrames)
        assertFalse(FrameTrace.enabled)
        val cancellation = CancellationException("synthetic cancellation")
        assertSame(cancellation, assertFailsWith<CancellationException> {
            CliTracingLease.acquire("on") {}.use { throw cancellation }
        })
        assertFalse(JvmLanDiag.enabled)
        assertFalse(FrameTrace.enabled)
    }

    private fun withCleanTracing(block: () -> Unit) {
        val enabled = JvmLanDiag.enabled
        val bytes = JvmLanDiag.traceFrames
        val frames = FrameTrace.enabled
        val sink = FrameTrace.sink
        try {
            JvmLanDiag.enabled = false
            JvmLanDiag.traceFrames = false
            FrameTrace.enabled = false
            block()
        } finally {
            JvmLanDiag.enabled = enabled
            JvmLanDiag.traceFrames = bytes
            FrameTrace.sink = sink
            FrameTrace.enabled = frames
        }
    }

    private fun captureConsole(block: () -> Unit): String {
        val original = System.out
        val output = ByteArrayOutputStream()
        PrintStream(output, true, Charsets.UTF_8).use { capture ->
            try {
                System.setOut(capture)
                block()
            } finally {
                System.setOut(original)
            }
        }
        return output.toString(Charsets.UTF_8)
    }
}
