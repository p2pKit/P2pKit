package dev.p2pkit.sample.diagnostics

import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.nio.file.Files
import java.util.concurrent.CountDownLatch
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
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
    fun cooperatingOwnersFailFastWithoutReleasingAnExistingNativeLock() = withDirectory { directory ->
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
            assertEquals("BUSY", nativeLockProbe(directory))
            release.countDown()
            writing.get(5, TimeUnit.SECONDS)
            contender("after")
            assertEquals("first\nafter\n", File(directory, "diagnostic-events.jsonl").readText())
            assertEquals("ACQUIRED", nativeLockProbe(directory))
        } finally {
            release.countDown()
            worker.shutdownNow()
            assertTrue(worker.awaitTermination(5, TimeUnit.SECONDS))
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

    private fun nativeLockProbe(directory: File): String {
        val java = File(System.getProperty("java.home"), "bin/java").path
        val classpath = File(DiagnosticDirectoryLockProbe::class.java.protectionDomain.codeSource.location.toURI()).path
        val process = ProcessBuilder(
            java, "-cp", classpath, DiagnosticDirectoryLockProbe::class.java.name,
            File(directory, ".diagnostic-events.jsonl.lock").path
        ).redirectErrorStream(true).start()
        try {
            assertTrue(process.waitFor(5, TimeUnit.SECONDS), "native lock probe did not finish")
            val output = process.inputStream.bufferedReader().use { it.readText() }.trim()
            assertEquals(0, process.exitValue(), output)
            return output
        } finally {
            if (process.isAlive) process.destroyForcibly()
            assertTrue(process.waitFor(5, TimeUnit.SECONDS))
        }
    }

    private fun history(directory: File): Map<String, String> =
        logFiles(directory).associate { it.name to it.readText() }

    private fun logFiles(directory: File): List<File> = directory.listFiles().orEmpty()
        .filter { it.isFile && it.name.startsWith("diagnostic-events.jsonl") }
        .sortedBy { it.name }

    private fun withDirectory(action: (File) -> Unit) {
        val directory = Files.createTempDirectory("p2pkit-rolling-failure").toFile()
        try {
            action(directory)
        } finally {
            assertTrue(directory.deleteRecursively())
        }
    }
}
