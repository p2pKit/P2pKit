package dev.p2pkit.sample.desktop

import java.io.BufferedReader
import java.io.File
import java.io.StringReader
import java.nio.file.Files
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
        val directory = Files.createTempDirectory("p2pkit-cli-shutdown-").toFile()
        val output = File(directory, "child.log")
        var child: Process? = null
        try {
            val executable = if (System.getProperty("os.name").startsWith("Windows")) "java.exe" else "java"
            child = ProcessBuilder(
                File(System.getProperty("java.home"), "bin/$executable").path,
                "-Xmx96m", "-XX:ActiveProcessorCount=2",
                "-cp", checkNotNull(System.getProperty("p2pkit.test.runtimeClasspath")),
                CliShutdownProbe::class.java.name
            ).redirectErrorStream(true).redirectOutput(output).start()
            // Keep stdin OPEN. Completing the read by EOF would conceal the bug.
            assertTrue(child.waitFor(15, TimeUnit.SECONDS), output.readText())
            assertEquals(23, child.exitValue(), output.readText())
            assertEquals(
                listOf("read-entered", "cleanup-started", "cleanup-finished", "diagnostics-finalized"),
                output.readLines()
            )
        } finally {
            if (child?.isAlive == true) {
                child.destroyForcibly()
                check(child.waitFor(5, TimeUnit.SECONDS)) { "Owned CLI probe survived forced cleanup" }
            }
            child?.outputStream?.close()
            check(directory.deleteRecursively()) { "Could not remove owned CLI probe directory" }
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
