package dev.p2pkit.sample.diagnostics

import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.io.OutputStream
import java.io.PrintStream
import java.nio.file.Files
import java.util.Base64
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

class RollingJsonlFileSinkTest {
    @Test
    fun failedRotationNeverAppendsPastTheActiveFileBound() = withDirectory { directory ->
        val sink = RollingJsonlFileSink(directory, maxBytes = 4_096, maxFiles = 2)
        val original = "a".repeat(4_095) + "\n"
        sink(original.dropLast(1))
        // A nonempty filesystem entry cannot be deleted or replaced as a log.
        // This failure is deterministic without permissions/root/OS assumptions.
        val obstruction = File(directory, "diagnostic-events.jsonl.1").apply { mkdir() }
        val sentinel = File(obstruction, "unrelated.txt").apply { writeText("preserve") }

        assertFailsWith<IOException> { sink("next") }
        assertEquals(original, File(directory, "diagnostic-events.jsonl").readText())
        assertEquals("preserve", sentinel.readText())
        assertTrue(File(directory, "diagnostic-events.jsonl").length() <= 4_096)
    }

    @Test
    fun oneFileRetentionReplacesTheFullActiveGeneration() = withDirectory { directory ->
        val sink = RollingJsonlFileSink(directory, maxBytes = 4_096, maxFiles = 1)
        sink("a".repeat(4_095))
        sink("next")

        val logs = logFiles(directory)
        assertEquals(listOf("diagnostic-events.jsonl"), logs.map { it.name })
        assertEquals("next\n", logs.single().readText())
        assertTrue(logs.single().length() <= 4_096)
    }

    @Test
    fun oversizedRecordIsRejectedBeforeExistingHistoryChanges() = withDirectory { directory ->
        val sink = RollingJsonlFileSink(directory, maxBytes = 4_096, maxFiles = 2)
        sink("original")
        val before = logFiles(directory).associate { it.name to it.readText() }

        assertFailsWith<IllegalArgumentException> { sink("é".repeat(2_048)) }
        assertEquals(before, logFiles(directory).associate { it.name to it.readText() })
    }

    @Test
    fun exactUtf8AndNewlineBoundaryIsRetained() = withDirectory { directory ->
        val sink = RollingJsonlFileSink(directory, maxBytes = 4_096, maxFiles = 2)
        val exact = "é".repeat(2_047) + "a"
        sink(exact)
        assertEquals(4_096L, File(directory, "diagnostic-events.jsonl").length())
        sink("é")
        assertEquals(exact + "\n", File(directory, "diagnostic-events.jsonl.1").readText())
        assertEquals("é\n", File(directory, "diagnostic-events.jsonl").readText())
    }

    @Test
    fun checkedDeleteFailurePreventsAppendAndAllowsRetry() = withDirectory { directory ->
        var fail = false
        var appends = 0
        val operations = object : RollingJsonlFileOperations() {
            override fun delete(file: File) {
                if (fail) throw IOException("synthetic delete failure")
                super.delete(file)
            }

            override fun append(file: File, bytes: ByteArray) {
                appends++
                super.append(file, bytes)
            }
        }
        val sink = RollingJsonlFileSink(directory, 4_096, 2, operations)
        sink("a".repeat(4_095))
        sink("b".repeat(4_095))
        val before = history(directory)
        fail = true
        assertEquals("synthetic delete failure", assertFailsWith<IOException> { sink("next") }.message)
        assertEquals(2, appends)
        assertEquals(before, history(directory))
        fail = false
        sink("next")
        assertEquals("next\n", File(directory, "diagnostic-events.jsonl").readText())
        assertEquals(before.getValue("diagnostic-events.jsonl"), history(directory)["diagnostic-events.jsonl.1"])
    }

    @Test
    fun everyMoveFailureStopsAppendAndRetryPreservesGenerationOrder() = withDirectory { root ->
        val movedNames = listOf("diagnostic-events.jsonl.2", "diagnostic-events.jsonl.1", "diagnostic-events.jsonl")
        for (failedName in movedNames) {
            val directory = File(root, failedName).apply { mkdir() }
            var fail = false
            var appends = 0
            val operations = object : RollingJsonlFileOperations() {
                override fun move(source: File, destination: File) {
                    if (fail && source.name == failedName) throw IOException("synthetic move failure")
                    super.move(source, destination)
                }

                override fun append(file: File, bytes: ByteArray) {
                    appends++
                    super.append(file, bytes)
                }
            }
            val sink = RollingJsonlFileSink(directory, 4_096, 4, operations)
            for (letter in listOf("a", "b", "c", "d")) sink(letter.repeat(4_095))
            fail = true
            assertEquals("synthetic move failure", assertFailsWith<IOException> { sink("e") }.message)
            assertEquals(4, appends)
            assertEquals("d".repeat(4_095) + "\n", File(directory, "diagnostic-events.jsonl").readText())
            assertTrue(logFiles(directory).all { it.length() <= 4_096 })
            fail = false
            sink("e")
            val ageOrder = logFiles(directory).map { it.readText().first() }
            assertEquals(ageOrder.sortedDescending(), ageOrder)
            assertEquals(ageOrder.distinct(), ageOrder)
            assertEquals('e', ageOrder.first())
            assertTrue(logFiles(directory).size <= 4)
        }
    }

    @Test
    fun bulkClearSurfacesDeletionFailureAndOnlyRemovesOwnedLogs() = withDirectory { directory ->
        var fail = true
        val operations = object : RollingJsonlFileOperations() {
            override fun delete(file: File) {
                if (fail && file.name.endsWith(".1")) throw IOException("synthetic clear failure")
                super.delete(file)
            }
        }
        File(directory, "diagnostic-events.jsonl").writeText("new\n")
        File(directory, "diagnostic-events.jsonl.1").writeText("old\n")
        val sentinel = File(directory, "unrelated.txt").apply { writeText("preserve") }
        val sink = RollingJsonlFileSink(directory, 4_096, 2, operations)
        assertEquals("synthetic clear failure", assertFailsWith<IOException> { sink.clear() }.message)
        assertEquals("old\n", File(directory, "diagnostic-events.jsonl.1").readText())
        assertEquals("preserve", sentinel.readText())
        fail = false
        sink.clear()
        sink.clear()
        assertTrue(logFiles(directory).isEmpty())
        assertEquals("preserve", sentinel.readText())
        assertTrue(File(directory, ".diagnostic-events.jsonl.lock").isFile)
        assertEquals(0L, File(directory, ".diagnostic-events.jsonl.lock").length())
    }

    @Test
    fun listingFailureDoesNotBecomeAnEmptyDirectory() = withDirectory { directory ->
        val original = File(directory, "diagnostic-events.jsonl").apply { writeText("original\n") }
        val operations = object : RollingJsonlFileOperations() {
            override fun list(directory: File): Array<File> = throw IOException("synthetic listing failure")
        }
        val sink = RollingJsonlFileSink(directory, 4_096, 2, operations)
        for (operation in listOf<() -> Unit>(
            { sink("next") }, { sink.clear() }, { sink.clearSession("session-a") }, { sink.evidenceFiles("session-a") }
        )) {
            assertEquals("synthetic listing failure", assertFailsWith<IOException>(block = operation).message)
            assertEquals("original\n", original.readText())
        }
    }

    @Test
    fun reducedLimitsRemoveOnlyObsoleteOrOversizedGenerations() = withDirectory { directory ->
        File(directory, "diagnostic-events.jsonl").writeText("a".repeat(5_000))
        File(directory, "diagnostic-events.jsonl.1").writeText("keep\n")
        File(directory, "diagnostic-events.jsonl.2").writeText("obsolete\n")
        File(directory, "diagnostic-events.jsonl.99").writeText("obsolete\n")
        val sentinel = File(directory, "other.jsonl").apply { writeText("preserve") }
        RollingJsonlFileSink(directory, 4_096, 2)("next")
        assertEquals(
            mapOf("diagnostic-events.jsonl" to "next\n", "diagnostic-events.jsonl.1" to "keep\n"),
            history(directory)
        )
        assertEquals("preserve", sentinel.readText())
    }

    @Test
    fun failedAppendRollsBackAndReleasesOwnershipForAnotherSink() = withDirectory { directory ->
        File(directory, "diagnostic-events.jsonl").writeText("before\n")
        val operations = object : RollingJsonlFileOperations() {
            override fun append(file: File, bytes: ByteArray) {
                FileOutputStream(file, true).use { it.write(bytes, 0, 2) }
                throw IOException("synthetic partial append")
            }
        }
        val sink = RollingJsonlFileSink(directory, 4_096, 2, operations)
        assertEquals("synthetic partial append", assertFailsWith<IOException> { sink("broken") }.message)
        assertEquals("before\n", File(directory, "diagnostic-events.jsonl").readText())
        RollingJsonlFileSink(directory, 4_096, 2)("after")
        assertEquals("before\nafter\n", File(directory, "diagnostic-events.jsonl").readText())
    }

    @Test
    fun failedRollbackIsReportedAndIncompleteTailIsNeverJoinedToTheNextRecord() = withDirectory { directory ->
        File(directory, "diagnostic-events.jsonl").writeText("before\n")
        val operations = object : RollingJsonlFileOperations() {
            override fun append(file: File, bytes: ByteArray) {
                FileOutputStream(file, true).use { it.write(bytes, 0, 2) }
                throw IOException("synthetic partial append")
            }

            override fun truncate(file: File, length: Long): Unit = throw IOException("synthetic rollback failure")
        }
        val sink = RollingJsonlFileSink(directory, 4_096, 2, operations)
        val failure = assertFailsWith<IOException> { sink("broken") }
        assertEquals("synthetic partial append", failure.message)
        assertEquals(listOf("synthetic rollback failure"), failure.suppressed.map { it.message })
        RollingJsonlFileSink(directory, 4_096, 2)("after")
        assertEquals("after\n", File(directory, "diagnostic-events.jsonl").readText())
        assertEquals("before\nbr", File(directory, "diagnostic-events.jsonl.1").readText())
        assertTrue(logFiles(directory).all { it.length() <= 4_096 })
    }

    @Test
    fun invalidLimitsAndDirectoryFailuresDoNotCreateOrModifyLogs() = withDirectory { directory ->
        for (count in listOf(Int.MIN_VALUE, 0, 33, Int.MAX_VALUE)) {
            assertFailsWith<IllegalArgumentException> { RollingJsonlFileSink(directory, 4_096, count) }
        }
        assertFailsWith<IllegalArgumentException> { RollingJsonlFileSink(directory, 4_095, 2) }
        assertTrue(directory.listFiles().orEmpty().isEmpty())
        val blocker = File(directory, "not-directory").apply { writeText("preserve") }
        assertFailsWith<IOException> { RollingJsonlFileSink(blocker)("next") }
        assertFailsWith<IOException> { RollingJsonlFileSink(File(blocker, "child"))("next") }
        assertEquals("preserve", blocker.readText())
        val missing = File(directory, "absent")
        val sink = RollingJsonlFileSink(missing)
        sink.clear()
        sink.clearSession("session-a")
        assertTrue(sink.evidenceFiles("session-a").isEmpty())
        assertTrue(!missing.exists())
    }

    @Test
    fun cooperatingOwnersFailFastWithoutReleasingAnExistingNativeLock() {
        assertCooperatingOwners(withBenignOption = false)
    }

    @Test
    fun cooperatingOwnersPreserveInheritedJvmOptionsAndTheirExactStartupNote() {
        assertCooperatingOwners(withBenignOption = true)
    }

    private fun assertCooperatingOwners(withBenignOption: Boolean) = withDirectory { directory ->
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val operations = object : RollingJsonlFileOperations() {
            override fun append(file: File, bytes: ByteArray) {
                entered.countDown()
                check(release.await(10, TimeUnit.SECONDS)) { "test owner was not released" }
                super.append(file, bytes)
            }
        }
        val owner = RollingJsonlFileSink(directory, 4_096, 2, operations)
        val contender = RollingJsonlFileSink.forFile(File(directory, "diagnostic-events.jsonl"), 4_096, 2)
        val worker = Executors.newSingleThreadExecutor()
        var failure: Throwable? = null
        try {
            val writing = worker.submit { owner("first") }
            assertTrue(entered.await(5, TimeUnit.SECONDS))
            for (operation in listOf<() -> Unit>(
                { contender("blocked") }, { contender.clear() },
                { contender.clearSession("session-a") }, { contender.evidenceFiles("session-a") }
            )) assertEquals("Diagnostic log family is busy", assertFailsWith<IOException>(block = operation).message)
            // Different families, even in the same directory, must not share the busy guard.
            RollingJsonlFileSink(File(directory, "other"))("independent")
            RollingJsonlFileSink.forFile(File(directory, "separate.jsonl"))("independent")
            nativeLockProbe(directory, "BUSY", withBenignOption)
            release.countDown()
            writing.get(5, TimeUnit.SECONDS)
            contender("after")
            assertEquals("first\nafter\n", File(directory, "diagnostic-events.jsonl").readText())
            nativeLockProbe(directory, "ACQUIRED", withBenignOption)
        } catch (error: Throwable) {
            failure = error
        } finally {
            val failures = ProbeFailures(failure)
            failures.attempt { release.countDown() }
            failures.attempt { worker.shutdownNow() }
            failures.attempt { assertTrue(worker.awaitTermination(5, TimeUnit.SECONDS)) }
            failures.rethrow()
        }
    }

    @Test
    fun concurrentCallsToOneSinkKeepCompleteRecordsAndTheDiskBound() = withDirectory { directory ->
        val sink = RollingJsonlFileSink(directory, 4_096, 2)
        val pool = Executors.newFixedThreadPool(4)
        val start = CountDownLatch(1)
        val expected = (0 until 40).map { "$it:" + "x".repeat(120) }.toSet()
        try {
            val jobs = (0 until 4).map { worker ->
                pool.submit {
                    check(start.await(5, TimeUnit.SECONDS))
                    repeat(10) { sink("${worker * 10 + it}:" + "x".repeat(120)) }
                }
            }
            start.countDown()
            jobs.forEach { it.get(5, TimeUnit.SECONDS) }
            val logs = logFiles(directory)
            val actual = logs.flatMap { it.readLines() }
            assertEquals(expected.size, actual.size)
            assertEquals(expected, actual.toSet())
            assertTrue(logs.size <= 2)
            assertTrue(logs.all { it.length() <= 4_096 })
        } finally {
            start.countDown()
            pool.shutdownNow()
            assertTrue(pool.awaitTermination(5, TimeUnit.SECONDS))
        }
    }

    @Test
    fun namedFileSinkUsesTheExactEscapedFamilyAndLeavesOtherFilesUntouched() = withDirectory { directory ->
        val active = File(directory, "operator.[log].jsonl")
        val sentinel = File(directory, "operator.xlogx.jsonl").apply { writeText("preserve") }
        val sink = RollingJsonlFileSink.forFile(active, 4_096, 2)
        sink("a".repeat(4_095))
        sink("next")
        assertEquals("next\n", active.readText())
        assertEquals("a".repeat(4_095) + "\n", File(directory, "${active.name}.1").readText())
        assertEquals("preserve", sentinel.readText())
        sink.clear()
        assertTrue(!active.exists())
        assertTrue(!File(directory, "${active.name}.1").exists())
        assertEquals("preserve", sentinel.readText())
        assertTrue(File(directory, ".${active.name}.lock").isFile)
    }

    private fun nativeLockProbe(directory: File, expected: String, withBenignOption: Boolean) {
        val java = File(System.getProperty("java.home"), "bin/java").path
        val classpath = File(DiagnosticDirectoryLockProbe::class.java.protectionDomain.codeSource.location.toURI()).path
        val output = Files.createTempFile(directory.toPath(), "native-lock-probe-", ".log").toFile()
        val builder = ProcessBuilder(
            java, "-cp", classpath, DiagnosticDirectoryLockProbe::class.java.name,
            File(directory, ".diagnostic-events.jsonl.lock").path
        ).redirectErrorStream(true).redirectOutput(output)
        if (withBenignOption) {
            val environment = builder.environment()
            // Keep inherited ownership options; append only this test's benign property.
            environment["JDK_JAVA_OPTIONS"] = listOfNotNull(
                environment["JDK_JAVA_OPTIONS"], "-Dp2pkit.test.nativeLockProbe.option=present"
            ).joinToString(" ")
            builder.command().add("present")
        }
        val inheritedOptions = builder.environment()["JDK_JAVA_OPTIONS"]
        var process: Process? = null
        var failure: Throwable? = null
        try {
            process = builder.start()
            assertTrue(process.waitFor(5, TimeUnit.SECONDS), "native lock probe did not finish")
            assertEquals(0, process.exitValue(), output.readText())
            assertNativeLockTranscript(output.readLines(), expected, inheritedOptions)
        } catch (error: Throwable) {
            failure = error
        } finally {
            finishProbe(
                directory, failure,
                retire = {
                    val owned = process
                    if (owned?.isAlive == true) {
                        owned.destroyForcibly()
                        check(owned.waitFor(5, TimeUnit.SECONDS)) { "Owned native lock probe survived forced cleanup" }
                    }
                },
                closeInput = { process?.outputStream?.close() },
                retain = {
                    retainProbeLog(output, "NATIVE_LOCK_PROBE_RAW expected=$expected benignOption=$withBenignOption")
                },
                dispose = { check(output.delete()) { "Could not remove owned native lock probe output" } }
            )
        }
    }

    private fun retainProbeLog(
        output: File,
        prefix: String,
        stream: PrintStream = System.out,
        read: (File) -> ByteArray = { it.readBytes() }
    ) {
        // Retain original bytes independently of text/XML newline processing.
        val bytes = read(output)
        val encoded = Base64.getEncoder().encodeToString(bytes)
        stream.println("$prefix bytes=${bytes.size} base64=$encoded")
        check(!stream.checkError()) { "Could not retain the native lock probe transcript" }
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
        // Every attempt is independent; a live/unknown child never authorizes raw-output disposal.
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
                    check(output.delete())
                    calls += "dispose"
                }
            )
        }
        assertEquals(listOf("retire", "close", "retain", "dispose"), calls)
        assertFalse(output.exists())
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
                        dispose = { calls += "dispose"; output.delete() }
                    )
                }
                if (stage == "stream") {
                    assertTrue(stream.checkError())
                    assertEquals("Could not retain the native lock probe transcript", failure.message)
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
                        dispose = { calls += "dispose"; output.delete() }
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

    @Test
    fun enclosingDirectoryHoldsRawLogsAndUnknownListingsWithoutMaskingBodyFailure() {
        for (stage in listOf("raw", "body", "listing")) withControlLog { directory, output ->
            val original = output.readBytes()
            val primary = IOException("synthetic body failure")
            val failure = assertFailsWith<Exception> {
                withDirectory(directory, list = { if (stage == "listing") null else it.listFiles() }) {
                    if (stage == "body") throw primary
                }
            }
            if (stage == "body") assertSame(primary, failure)
            else assertEquals(
                if (stage == "raw") "Unretained native lock probe output" else "Cannot inspect owned test directory",
                failure.message
            )
            assertTrue(failure.suppressed.single().message!!.startsWith("PROBE_EVIDENCE_HOLD:"))
            assertContentEquals(original, output.readBytes())
        }
    }

    private fun withControlLog(action: (File, File) -> Unit) {
        val directory = Files.createTempDirectory("p2pkit-lock-finalizer-control-").toFile()
        val failures = ProbeFailures(null)
        try {
            val output = File(directory, "native-lock-probe-control.log").apply {
                writeBytes("raw\r\n".toByteArray(Charsets.US_ASCII) + byteArrayOf(0, -1))
            }
            action(directory, output)
        } catch (error: Throwable) {
            failures.attempt { throw error }
        } finally {
            // Only source-defined control bytes, never a real subprocess/lock fixture's evidence.
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

    private fun assertNativeLockTranscript(lines: List<String>, expected: String, inheritedOptions: String?) {
        val startupNote = inheritedOptions?.let { "NOTE: Picked up JDK_JAVA_OPTIONS: $it" }
        assertEquals(listOfNotNull(startupNote) + expected, lines)
    }

    @Test
    fun nativeLockTranscriptRejectsMissingChangedAndUnexpectedOutput() {
        val options = "-Dp2pkit.test.nativeLockProbe.option=present"
        val note = "NOTE: Picked up JDK_JAVA_OPTIONS: $options"
        for (expected in listOf("BUSY", "ACQUIRED")) {
            for (inheritedOptions in listOf(null, options)) {
                val prefix = if (inheritedOptions == null) emptyList() else listOf(note)
                val transcript = prefix + expected
                assertNativeLockTranscript(transcript, expected, inheritedOptions)
                val invalid = mutableListOf(prefix, prefix + "UNKNOWN", prefix + listOf("BUSY", "ACQUIRED"))
                for (extra in listOf(
                    expected, "unexpected stderr", "NOTE: Picked up JDK_JAVA_OPTIONS: wrong", note, ""
                )) {
                    invalid += transcript + extra
                    invalid += listOf(extra) + transcript
                }
                if (inheritedOptions != null) {
                    invalid += listOf(expected)
                    invalid += listOf(expected, note)
                }
                for (lines in invalid) {
                    assertFailsWith<AssertionError> { assertNativeLockTranscript(lines, expected, inheritedOptions) }
                }
            }
        }
    }

    private fun history(directory: File): Map<String, String> =
        logFiles(directory).associate { it.name to it.readText() }

    private fun logFiles(directory: File): List<File> = directory.listFiles().orEmpty()
        .filter { it.isFile && it.name.startsWith("diagnostic-events.jsonl") }
        .sortedBy { it.name }

    private fun withDirectory(
        directory: File = Files.createTempDirectory("p2pkit-rolling-failure").toFile(),
        list: (File) -> Array<File>? = { it.listFiles() },
        action: (File) -> Unit
    ) {
        var failure: Throwable? = null
        try {
            action(directory)
        } catch (error: Throwable) {
            failure = error
        } finally {
            val failures = ProbeFailures(failure)
            // A failed body may still have an unretired worker. Never delete through that uncertainty.
            val disposed = failure == null && failures.attempt {
                val entries = checkNotNull(list(directory)) { "Cannot inspect owned test directory" }
                check(entries.none { it.name.startsWith("native-lock-probe-") && it.name.endsWith(".log") }) {
                    "Unretained native lock probe output"
                }
                check(directory.deleteRecursively()) { "Could not remove owned test directory" }
            }
            if (!disposed) failures.attempt {
                error("PROBE_EVIDENCE_HOLD: preserve ${directory.absolutePath} before outer cleanup")
            }
            failures.rethrow()
        }
    }
}
