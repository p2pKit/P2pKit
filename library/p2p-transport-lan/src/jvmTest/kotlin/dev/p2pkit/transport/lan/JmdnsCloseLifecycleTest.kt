package dev.p2pkit.transport.lan

import java.io.File
import java.nio.file.Files
import java.util.concurrent.TimeUnit
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class JmdnsCloseLifecycleTest {
    @Test
    fun realResourceCloseRegressionsExitNaturally() {
        assertEquals(17, Runtime.version().feature(), "The real-resource close fixture requires JDK 17")
        val classpath = requireNotNull(System.getProperty("p2pkit.jmdns.fixture.classpath")) {
            "The existing jvmTest task must supply its actual runtime classpath"
        }
        val reportsPath = requireNotNull(System.getProperty("p2pkit.jmdns.fixture.outputDir")) {
            "The existing jvmTest task must declare its fixture evidence directory"
        }
        val reports = File(reportsPath)
        require(reports.isAbsolute) { "The fixture evidence directory must be absolute" }
        Files.createDirectories(reports.toPath())
        val runReports = Files.createTempDirectory(reports.toPath(), "run-").toFile()
        println("JmDNS close fixture evidence run: ${runReports.name}")
        val modes = listOf(
            "control",
            "failed_recovery",
            "shared_close",
            "close_wins",
            "recovery_wins",
            "responder_close",
            "callback_executor",
            "cleanup_retry",
        )
        // These eight fresh JVMs cover the five approved regression groups, in
        // serial. An unavailable multicast-capable local IPv4 is a failure, not
        // a skipped gate. The explicit address override is inherited unchanged.
        for (mode in modes) {
            runChild(mode, classpath, runReports)
        }
    }

    private fun runChild(mode: String, classpath: String, reports: File) {
        val executable = if (System.getProperty("os.name").startsWith("Windows")) "java.exe" else "java"
        val java = File(System.getProperty("java.home"), "bin/$executable")
        // Private files in this task-owned per-invocation directory are retained
        // in full on success, failure, or cancellation. Never delete/truncate the
        // only child evidence after merely reading an assertion-message prefix.
        val output = Files.createTempFile(reports.toPath(), "$mode-", ".log").toFile()
        var child: Process? = null
        var originalFailure: Throwable? = null
        var interrupted = false
        try {
            child = ProcessBuilder(
                java.absolutePath,
                "-Xms16m",
                "-Xmx128m",
                "-XX:MaxMetaspaceSize=128m",
                "-XX:ActiveProcessorCount=2",
                "-XX:+UseSerialGC",
                "-Dorg.slf4j.simpleLogger.defaultLogLevel=off",
                "-cp",
                classpath,
                "dev.p2pkit.transport.lan.internal.jmdns.impl.JmdnsCloseLifecycleFixture",
                mode,
            ).redirectErrorStream(true).redirectOutput(output).start()
            // Fixed child watchdog, not a larger JmDNS/product quit deadline.
            // A PASS marker is insufficient: the original non-daemon timer must
            // also allow natural process exit without fixture assistance.
            val exitedNaturally = child.waitFor(45, TimeUnit.SECONDS)
            val transcript = output.inputStream().use { it.readNBytes(65_536).toString(Charsets.UTF_8) }
            assertTrue(exitedNaturally, "$mode exceeded the 45s child watchdog before rescue\n$transcript")
            assertTrue(output.length() <= 65_536, "$mode produced excessive fixture output")
            assertEquals(0, child.exitValue(), "$mode did not exit successfully and naturally\n$transcript")
            assertEquals(1, transcript.lineSequence().count { it == "PASS mode=$mode" }, transcript)
            assertFalse(transcript.contains("FAIL mode="), transcript)
            assertFalse(transcript.contains("phase=fixture_rescue_begin"), "Rescue is not close success\n$transcript")
        } catch (failure: Throwable) {
            originalFailure = failure
            interrupted = failure is InterruptedException
            throw failure
        } finally {
            // Preserve test cancellation, but still reap the one owned child if
            // the wait was interrupted. A canceled test cannot leave it running.
            interrupted = Thread.interrupted() || interrupted
            try {
                if (child?.isAlive == true) {
                    // Only this test-owned failed child; never enumerate or kill
                    // unrelated Java/Gradle processes. This cannot produce PASS.
                    child.destroyForcibly()
                    assertTrue(child.waitFor(5, TimeUnit.SECONDS), "Owned $mode fixture survived forced cleanup")
                }
            } catch (cleanupFailure: Throwable) {
                interrupted = cleanupFailure is InterruptedException || interrupted
                if (originalFailure != null) originalFailure.addSuppressed(cleanupFailure) else throw cleanupFailure
            } finally {
                if (interrupted) Thread.currentThread().interrupt()
            }
        }
    }
}
