package dev.p2pkit.sample.desktop

import java.io.BufferedReader
import java.io.File
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
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
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
        try {
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
        } finally {
            if (child?.isAlive == true) {
                child.destroyForcibly()
                check(child.waitFor(5, TimeUnit.SECONDS)) { "Owned CLI probe survived forced cleanup" }
            }
            try {
                child?.outputStream?.close()
            } finally {
                try {
                    if (output.isFile) {
                        // ASCII encoding survives Gradle's text/XML capture without changing raw line endings.
                        val bytes = output.readBytes()
                        val encoded = Base64.getEncoder().encodeToString(bytes)
                        println("CLI_SHUTDOWN_RAW benignOption=$withBenignOption bytes=${bytes.size} base64=$encoded")
                        check(!System.out.checkError()) { "Could not retain the owned CLI probe transcript" }
                    }
                } finally {
                    check(directory.deleteRecursively()) { "Could not remove owned CLI probe directory" }
                }
            }
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
