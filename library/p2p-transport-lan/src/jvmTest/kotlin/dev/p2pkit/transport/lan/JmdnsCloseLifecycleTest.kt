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

    private fun startupDiagnosticJvmArguments(mode: String): Array<String> {
        val startupPrimitives = System.getProperty("p2pkit.audit.jmdnsStartupPrimitives")
        val pythonExecutable = System.getProperty("p2pkit.audit.pythonExecutable")
        if (startupPrimitives == null && pythonExecutable == null) return emptyArray()
        require(startupPrimitives == "true" && pythonExecutable != null) {
            "JmDNS startup diagnostics require both explicit properties"
        }
        val python = File(pythonExecutable)
        require(
            pythonExecutable.toByteArray(Charsets.UTF_8).size in 1..16_384 &&
                pythonExecutable.none { it < ' ' || it == '\u007f' } &&
                python.isAbsolute && python.isFile && python.canExecute() &&
                runCatching { python.canonicalPath == pythonExecutable }.getOrDefault(false),
        ) { "JmDNS startup diagnostics require a canonical executable interpreter" }
        if (mode != "control") return emptyArray()
        // The fixture probes only after a captured failure and still rethrows that failure.
        return arrayOf(
            "-Dp2pkit.audit.jmdnsStartupPrimitives=true",
            "-Dp2pkit.audit.pythonExecutable=$pythonExecutable",
            // BEGIN JMDNS_POLICY_CONTROL_ARGUMENTS
            *policyDiagnosticJvmArguments(),
            // END JMDNS_POLICY_CONTROL_ARGUMENTS
        )
    }

    // BEGIN JMDNS_POLICY_CONTROL_PROPERTIES
    private fun policyDiagnosticJvmArguments(): Array<String> {
        val names = listOf(
            "p2pkit.audit.jmdnsPolicyLibrary",
            "p2pkit.audit.jmdnsPolicyLibrarySha256",
            "p2pkit.audit.jmdnsPolicyLibraryIdentity",
            "p2pkit.audit.jmdnsPolicyRecordSha256",
            "p2pkit.audit.jmdnsPolicyJavaHome",
        )
        val values = names.associateWith {
            requireNotNull(System.getProperty(it)) { "JmDNS policy diagnostics require all five bound properties" }
        }
        val libraryPath = values.getValue(names[0])
        val javaHomePath = values.getValue(names[4])
        for (path in listOf(libraryPath, javaHomePath)) {
            require(
                path.toByteArray(Charsets.UTF_8).size in 1..16_384 &&
                    path.none { it < ' ' || it == '\u007f' } && File(path).isAbsolute &&
                    runCatching { File(path).canonicalPath == path }.getOrDefault(false),
            ) { "JmDNS policy diagnostics require canonical paths" }
        }
        require(libraryPath.endsWith(
            "/library/p2p-transport-lan/build/reports/jmdns-policy-native/libp2pkit-jmdns-policy.dylib",
        )) { "JmDNS policy diagnostics require the fixed compiled library path" }
        require(listOf(names[1], names[3]).all { values.getValue(it).matches(Regex("[0-9a-f]{64}")) }) {
            "JmDNS policy diagnostics require exact hashes"
        }
        val encodedIdentity = values.getValue(names[2])
        val components = encodedIdentity.split(':')
        require(components.size == 8 && components.all { it.matches(Regex("0|[1-9][0-9]{0,18}")) }) {
            "JmDNS policy diagnostics require the original file identity"
        }
        val identity = components.map { requireNotNull(it.toLongOrNull()) { "Invalid policy identity integer" } }
        require(identity[1] > 0 && (identity[2] and 0xf000L) == 0x8000L && (identity[2] and 0x12L) == 0L &&
            identity[4] == 1L && identity[5] in 1L..1_048_576L && identity[6] > 0 && identity[7] > 0) {
            "JmDNS policy diagnostics require a bounded regular original file"
        }
        require(Runtime.version().feature() == 17 &&
            runCatching { File(System.getProperty("java.home")).canonicalPath == javaHomePath }.getOrDefault(false)) {
            "JmDNS policy diagnostics require the compiler-header JDK in the actual worker"
        }
        // The failure-only Java helper rechecks original stat/hash/record and
        // actual child JDK immediately before load; forwarding grants no authority.
        return names.map { "-D$it=${values.getValue(it)}" }.toTypedArray()
    }
    // END JMDNS_POLICY_CONTROL_PROPERTIES

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
                *startupDiagnosticJvmArguments(mode),
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
