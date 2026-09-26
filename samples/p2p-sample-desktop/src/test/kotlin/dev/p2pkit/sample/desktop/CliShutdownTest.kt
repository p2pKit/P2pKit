package dev.p2pkit.sample.desktop

import java.io.BufferedReader
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.IOException
import java.io.OutputStream
import java.io.PrintStream
import java.io.StringReader
import java.nio.file.Files
import java.util.Base64
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import kotlin.system.exitProcess
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

class CliShutdownTest {
    @Test
    fun realJvmShutdownCancelsBlockedStdinAndWaitsForLexicalCleanup() {
        assertRealJvmShutdown(withBenignOption = false)
    }

    @Test
    fun realJvmShutdownPreservesInheritedOptionsAndAcceptsTheirExactStartupNote() {
        assertRealJvmShutdown(withBenignOption = true)
    }

    private fun assertRealJvmShutdown(withBenignOption: Boolean) {
        val directory = Files.createTempDirectory("p2pkit-cli-shutdown-").toFile()
        val output = File(directory, "child.log")
        var child: Process? = null
        var failure: Throwable? = null
        try {
            // Even a failed launch must leave an explicit (possibly empty) original to retain.
            Files.createFile(output.toPath())
            val executable = if (System.getProperty("os.name").startsWith("Windows")) "java.exe" else "java"
            val builder = ProcessBuilder(
                File(System.getProperty("java.home"), "bin/$executable").path,
                "-Xmx96m", "-XX:ActiveProcessorCount=2",
                "-cp", checkNotNull(System.getProperty("p2pkit.test.runtimeClasspath")),
                CliShutdownProbe::class.java.name
            ).redirectErrorStream(true).redirectOutput(output)
            if (withBenignOption) {
                // Append, rather than replace, options such as the executor's owned java.io.tmpdir.
                val environment = builder.environment()
                environment["JDK_JAVA_OPTIONS"] = listOfNotNull(
                    environment["JDK_JAVA_OPTIONS"], "-Dp2pkit.test.cliShutdown.option=present"
                ).joinToString(" ")
                builder.command().add("present")
            }
            val inheritedOptions = builder.environment()["JDK_JAVA_OPTIONS"]
            child = builder.start()
            // Keep stdin OPEN. Completing the read by EOF would conceal the bug.
            assertTrue(child.waitFor(15, TimeUnit.SECONDS), output.readText())
            assertEquals(23, child.exitValue(), output.readText())
            assertShutdownTranscript(output.readLines(), inheritedOptions)
        } catch (error: Throwable) {
            failure = error
        } finally {
            finishProbe(
                directory, failure,
                retire = {
                    val owned = child
                    if (owned?.isAlive == true) {
                        owned.destroyForcibly()
                        check(owned.waitFor(5, TimeUnit.SECONDS)) { "Owned CLI probe survived forced cleanup" }
                    }
                },
                closeInput = { child?.outputStream?.close() },
                retain = { retainProbeLog(output, "CLI_SHUTDOWN_RAW benignOption=$withBenignOption") },
                dispose = {
                    check(directory.deleteRecursively()) { "Could not remove owned CLI probe directory" }
                }
            )
        }
    }

    private fun retainProbeLog(
        output: File,
        prefix: String,
        stream: PrintStream = System.out,
        read: (File) -> ByteArray = { it.readBytes() }
    ) {
        // ASCII encoding survives Gradle's text/XML capture without changing raw line endings.
        val bytes = read(output)
        val encoded = Base64.getEncoder().encodeToString(bytes)
        stream.println("$prefix bytes=${bytes.size} base64=$encoded")
        check(!stream.checkError()) { "Could not retain the owned CLI probe transcript" }
    }

    private fun finishProbe(
        directory: File,
        primaryFailure: Throwable?,
        retire: () -> Unit,
        closeInput: () -> Unit,
        retain: () -> Unit,
        dispose: () -> Unit
    ) {
        val failures = ProbeFailures(primaryFailure)
        // Do not short-circuit: a retirement/input error must not prevent the retention attempt.
        val retired = failures.attempt(retire)
        val inputClosed = failures.attempt(closeInput)
        val retained = failures.attempt(retain)
        val disposed = retired && inputClosed && retained && failures.attempt(dispose)
        if (!disposed) failures.attempt {
            error("PROBE_EVIDENCE_HOLD: preserve ${directory.absolutePath} before outer cleanup")
        }
        failures.rethrow()
    }

    @Test
    fun probeFinalizerRetainsOriginalBytesBeforeDisposal() = withControlLog { directory, output ->
        val calls = mutableListOf<String>()
        val captured = ByteArrayOutputStream()
        PrintStream(captured).use { stream ->
            finishProbe(
                directory, null,
                retire = { calls += "retire" },
                closeInput = { calls += "close" },
                retain = { retainProbeLog(output, "CONTROL", stream); calls += "retain" },
                dispose = {
                    assertEquals(listOf("retire", "close", "retain"), calls)
                    assertEquals(
                        "CONTROL bytes=7 base64=cmF3DQoA/w==" + System.lineSeparator(), captured.toString("US-ASCII")
                    )
                    check(directory.deleteRecursively())
                    calls += "dispose"
                }
            )
        }
        assertEquals(listOf("retire", "close", "retain", "dispose"), calls)
        assertFalse(directory.exists())
    }

    @Test
    fun probeFinalizerHoldsOriginalsWhenReadExportOrPrintStreamFails() {
        for (stage in listOf("read", "export", "stream")) withControlLog { directory, output ->
            val original = output.readBytes()
            val injected = IOException("synthetic $stage failure")
            val stream = when (stage) {
                "export" -> object : PrintStream(ByteArrayOutputStream()) {
                    override fun println(value: String?) = throw injected
                }
                "stream" -> PrintStream(object : OutputStream() {
                    override fun write(value: Int) = throw injected
                })
                else -> PrintStream(ByteArrayOutputStream())
            }
            val calls = mutableListOf<String>()
            stream.use {
                val failure = assertFailsWith<Exception> {
                    finishProbe(
                        directory, null,
                        retire = { calls += "retire" },
                        closeInput = { calls += "close" },
                        retain = {
                            calls += "retain"
                            retainProbeLog(output, "CONTROL", stream) { file ->
                                if (stage == "read") throw injected
                                file.readBytes()
                            }
                        },
                        dispose = { calls += "dispose"; directory.deleteRecursively() }
                    )
                }
                if (stage == "stream") {
                    assertTrue(stream.checkError()) // Real PrintStream error state, not a mocked return value.
                    assertEquals("Could not retain the owned CLI probe transcript", failure.message)
                } else assertSame(injected, failure)
                assertTrue(failure.suppressed.single().message!!.startsWith("PROBE_EVIDENCE_HOLD:"))
            }
            assertEquals(listOf("retire", "close", "retain"), calls)
            assertContentEquals(original, output.readBytes())
        }
    }

    @Test
    fun probeFinalizerPreservesPrimaryFailureAndAttemptsEveryFinalizer() {
        val primary = AssertionError("synthetic body failure")
        val retirement = IOException("synthetic retirement failure")
        val input = IOException("synthetic input closure failure")
        val retention = IOException("synthetic retention failure")
        val calls = mutableListOf<String>()
        val actual = assertFailsWith<AssertionError> {
            finishProbe(
                File("synthetic-not-created"), primary,
                retire = { calls += "retire"; throw retirement },
                closeInput = { calls += "close"; throw input },
                retain = { calls += "retain"; throw retention },
                dispose = { calls += "dispose" }
            )
        }
        assertSame(primary, actual)
        assertEquals(listOf(retirement, input, retention), actual.suppressed.take(3))
        assertTrue(actual.suppressed.last().message!!.startsWith("PROBE_EVIDENCE_HOLD:"))
        assertEquals(listOf("retire", "close", "retain"), calls)
    }

    @Test
    fun probeFinalizerHoldsOriginalWhenRetirementOrInputClosureFails() {
        for (stage in listOf("retire", "close")) withControlLog { directory, output ->
            val original = output.readBytes()
            val injected = IOException("synthetic $stage failure")
            val calls = mutableListOf<String>()
            val captured = ByteArrayOutputStream()
            PrintStream(captured).use { stream ->
                val failure = assertFailsWith<IOException> {
                    finishProbe(
                        directory, null,
                        retire = { calls += "retire"; if (stage == "retire") throw injected },
                        closeInput = { calls += "close"; if (stage == "close") throw injected },
                        retain = { retainProbeLog(output, "CONTROL", stream); calls += "retain" },
                        dispose = { calls += "dispose"; directory.deleteRecursively() }
                    )
                }
                assertSame(injected, failure)
                assertTrue(failure.suppressed.single().message!!.startsWith("PROBE_EVIDENCE_HOLD:"))
            }
            assertEquals(listOf("retire", "close", "retain"), calls)
            assertEquals("CONTROL bytes=7 base64=cmF3DQoA/w==" + System.lineSeparator(), captured.toString("US-ASCII"))
            assertContentEquals(original, output.readBytes())
        }
    }

    @Test
    fun probeFinalizerDoesNotReplaceBodyFailureWhenDisposalFails() {
        val primary = AssertionError("synthetic body failure")
        val disposal = IOException("synthetic disposal failure")
        val failure = assertFailsWith<AssertionError> {
            finishProbe(File("synthetic-not-created"), primary, {}, {}, {}, { throw disposal })
        }
        assertSame(primary, failure)
        assertSame(disposal, failure.suppressed.first())
        assertEquals(2, failure.suppressed.size)
        assertTrue(failure.suppressed.last().message!!.startsWith("PROBE_EVIDENCE_HOLD:"))
    }

    private fun withControlLog(action: (File, File) -> Unit) {
        val directory = Files.createTempDirectory("p2pkit-cli-finalizer-control-").toFile()
        val failures = ProbeFailures(null)
        try {
            val output = File(directory, "child.log").apply {
                writeBytes("raw\r\n".toByteArray(Charsets.US_ASCII) + byteArrayOf(0, -1))
            }
            action(directory, output)
        } catch (error: Throwable) {
            failures.attempt { throw error }
        } finally {
            // Only this deterministic control's source-defined bytes; never a child-process original.
            failures.attempt { check(directory.deleteRecursively()) { "Could not remove control directory" } }
            failures.rethrow()
        }
    }

    private class ProbeFailures(primaryFailure: Throwable?) {
        private var first = primaryFailure

        fun attempt(action: () -> Unit): Boolean = try {
            action()
            true
        } catch (error: Throwable) {
            val primary = first
            if (primary == null) first = error else if (primary !== error) primary.addSuppressed(error)
            false
        }

        fun rethrow() {
            first?.let { throw it }
        }
    }

    private fun assertShutdownTranscript(lines: List<String>, inheritedOptions: String?) {
        val startupNote = inheritedOptions?.let { "NOTE: Picked up JDK_JAVA_OPTIONS: $it" }
        assertEquals(
            listOfNotNull(startupNote) +
                listOf("read-entered", "cleanup-started", "cleanup-finished", "diagnostics-finalized"),
            lines
        )
    }

    @Test
    fun shutdownTranscriptRejectsUnknownDiagnosticsAndChangedMarkerSequences() {
        val markers = listOf("read-entered", "cleanup-started", "cleanup-finished", "diagnostics-finalized")
        val options = "-Dp2pkit.test.cliShutdown.option=present"
        val note = "NOTE: Picked up JDK_JAVA_OPTIONS: $options"
        for (inheritedOptions in listOf(null, options)) {
            val prefix = if (inheritedOptions == null) emptyList() else listOf(note)
            val expected = prefix + markers
            assertShutdownTranscript(expected, inheritedOptions)
            val invalid = mutableListOf<List<String>>()
            for (index in markers.indices) {
                invalid += prefix + markers.filterIndexed { position, _ -> position != index }
                invalid += prefix + markers.toMutableList().apply { add(index, markers[index]) }
            }
            for (index in 0 until markers.lastIndex) {
                invalid += prefix + markers.toMutableList().apply {
                    this[index] = markers[index + 1]
                    this[index + 1] = markers[index]
                }
            }
            for (extra in listOf("unexpected stderr", "NOTE: Picked up JDK_JAVA_OPTIONS: wrong", note, "")) {
                invalid += expected + extra
                invalid += listOf(extra) + expected
            }
            if (inheritedOptions != null) {
                invalid += markers
                invalid += markers.take(1) + note + markers.drop(1)
            }
            for (lines in invalid) {
                assertFailsWith<AssertionError> { assertShutdownTranscript(lines, inheritedOptions) }
            }
        }
    }

    @Test
    fun normalInputFailureAndNonShutdownCancellationKeepTheirOriginalOutcomes() {
        val finalized = mutableListOf<String>()
        runCliWithShutdownHook {
            CliConsoleInput(BufferedReader(StringReader("first\n\nlast\n"))).use { input ->
                assertEquals("first", input.readLine())
                assertEquals("", input.readLine())
                assertEquals("last", input.readLine())
                assertEquals(null, input.readLine())
            }
            finalized += "normal"
        }
        val failure = IllegalStateException("synthetic startup failure")
        assertSame(failure, assertFailsWith<IllegalStateException> {
            runCliWithShutdownHook {
                try {
                    throw failure
                } finally {
                    finalized += "failure"
                }
            }
        })
        val cancellation = CancellationException("caller cancellation, not JVM shutdown")
        assertSame(cancellation, assertFailsWith<CancellationException> {
            runCliWithShutdownHook {
                try {
                    throw cancellation
                } finally {
                    finalized += "cancelled"
                }
            }
        })
        assertEquals(listOf("normal", "failure", "cancelled"), finalized)
    }
}

/** Runs only in the owned child JVM. Runtime.exit exercises real JVM hooks on every host. */
internal object CliShutdownProbe {
    @JvmStatic
    fun main(args: Array<String>) {
        if (args.isNotEmpty()) {
            check(System.getProperty("p2pkit.test.cliShutdown.option") == args.single()) {
                "The appended JVM option did not reach the child"
            }
        }
        val reading = CountDownLatch(1)
        Thread({
            check(reading.await(10, TimeUnit.SECONDS)) { "Input reader never entered" }
            exitProcess(23)
        }, "p2pkit-cli-probe-exit").start()
        val input = CliConsoleInput(object : BufferedReader(StringReader("")) {
            override fun readLine(): String? {
                println("read-entered")
                reading.countDown()
                return System.`in`.bufferedReader().readLine()
            }
        })
        runCliWithShutdownHook {
            try {
                input.use {
                    try {
                        it.readLine()
                        error("Parent must keep stdin open")
                    } finally {
                        withContext(NonCancellable) {
                            println("cleanup-started")
                            // Force a real suspension: returning the hook after only
                            // requesting cancellation must not look like a cleanup pass.
                            delay(150)
                            println("cleanup-finished")
                        }
                    }
                }
            } finally {
                println("diagnostics-finalized")
            }
        }
    }
}
