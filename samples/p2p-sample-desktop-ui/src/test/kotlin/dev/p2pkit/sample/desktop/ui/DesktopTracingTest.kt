package dev.p2pkit.sample.desktop.ui

import dev.p2pkit.core.protocol.FrameTrace
import dev.p2pkit.transport.lan.JvmLanDiag
import java.io.File
import java.util.concurrent.TimeUnit
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class DesktopTracingTest {
    @Test
    fun aFreshJvmWithoutOptInDoesNotEmitEitherTraceStream() {
        val output = runProbe()
        assertFalse(output.contains("P2pKitLAN "))
        assertFalse(output.contains("P2pKitFRAME "))
        assertTrue(output.contains("PROBE frames=false bytes=false callbacks=0"))
    }

    @Test
    fun propertyOptInEnablesLanAndDecodedFramesButNotSocketChunks() {
        val output = runProbe("dev.p2pkit.lan.trace" to "TrUe")
        assertTrue(output.contains("P2pKitLAN "))
        assertTrue(output.contains("P2pKitFRAME TX type=DATA len=16B"))
        assertFalse(output.contains("synthetic-byte-chunk"))
        assertTrue(output.contains("PROBE frames=true bytes=false callbacks=1"))
    }

    @Test
    fun byteChunkDetailsNeedBothExplicitProperties() {
        val bytesOnly = runProbe("dev.p2pkit.lan.traceFrames" to "true")
        assertFalse(bytesOnly.contains("P2pKitLAN "))
        assertFalse(bytesOnly.contains("P2pKitFRAME "))
        val enabled = runProbe("dev.p2pkit.lan.trace" to "true", "dev.p2pkit.lan.traceFrames" to "true")
        assertTrue(enabled.contains("synthetic-byte-chunk"))
        assertTrue(enabled.contains("PROBE frames=true bytes=true callbacks=1"))
    }

    @Test
    fun falseAndUnrecognizedPropertyValuesDoNotOptIn() {
        for (value in listOf("false", "yes", " true ")) {
            val output = runProbe("dev.p2pkit.lan.trace" to value)
            assertFalse(output.contains("P2pKitLAN "))
            assertFalse(output.contains("P2pKitFRAME "))
        }
    }

    private fun runProbe(vararg properties: Pair<String, String>): String {
        // Each JVM initializes the real library singleton from its own startup
        // properties; no in-process mock of the library default/property read.
        val classpath = System.getProperty("dev.p2pkit.sample.test.runtimeClasspath")
            ?: System.getProperty("java.class.path")
        check(classpath.isNotEmpty())
        val java = File(System.getProperty("java.home"), "bin/java").absolutePath
        val command = listOf(java, "-Xmx128m") + properties.map { (key, value) -> "-D$key=$value" } +
            listOf("-cp", classpath, DesktopTracingProbe::class.java.name)
        val builder = ProcessBuilder(command).redirectErrorStream(true)
        // Keep this synthetic child deterministic without changing the host.
        listOf("JAVA_TOOL_OPTIONS", "JDK_JAVA_OPTIONS", "_JAVA_OPTIONS").forEach(builder.environment()::remove)
        val process = builder.start()
        return try {
            assertTrue(process.waitFor(10, TimeUnit.SECONDS), "Synthetic tracing probe did not terminate")
            val output = process.inputStream.bufferedReader().use { it.readText() }
            assertEquals(0, process.exitValue(), output)
            output
        } finally {
            process.destroy()
            if (!process.waitFor(1, TimeUnit.SECONDS)) {
                process.destroyForcibly()
                assertTrue(process.waitFor(5, TimeUnit.SECONDS), "Tracing probe cleanup failed")
            }
        }
    }
}

/** Synthetic launcher: exercises the actual property/sink path without a GUI or real network. */
object DesktopTracingProbe {
    @JvmStatic
    fun main(args: Array<String>) {
        check(args.isEmpty())
        var callbacks = 0
        val lease = installDesktopFrameTracing { callbacks++ }
        try {
            JvmLanDiag.log("test", "synthetic-lan-line")
            JvmLanDiag.frame("test", "synthetic-byte-chunk=32B")
            if (FrameTrace.enabled) FrameTrace.sink("TX type=DATA len=16B")
            println("PROBE frames=${FrameTrace.enabled} bytes=${JvmLanDiag.traceFrames} callbacks=$callbacks")
        } finally {
            lease?.release()
        }
        check(!FrameTrace.enabled)
    }
}
