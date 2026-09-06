package dev.p2pkit.sample.diagnostics

import java.io.File
import java.io.IOException
import java.nio.file.AtomicMoveNotSupportedException
import java.nio.file.Files
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlin.concurrent.thread
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertContentEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertSame
import kotlin.test.assertTrue

class DiagnosticClearTest {
    @Test
    fun replacementNeverDeletesTheOnlyCopyOfAnotherSession() = withDirectory { directory ->
        val original = object : File(directory, "diagnostic-events.jsonl") {
            override fun delete(): Boolean = super.delete().also { deleted ->
                if (deleted) {
                    check(mkdir())
                    File(this, "replacement-obstruction").writeText("synthetic fault")
                }
            }
        }
        original.writeText("{\"testSessionId\":\"selected\"}\n{\"testSessionId\":\"other\"}\n")
        val operations = object : RollingJsonlFileOperations() {
            override fun list(directory: File): Array<File> = arrayOf(original)
        }
        val sink = RollingJsonlFileSink(directory, 4_096, 2, operations)

        sink.clearSession("selected")

        assertTrue(original.isFile, "clearing must never discard the original before replacement")
        assertTrue("other" in original.readText())
        assertFalse("selected" in original.readText())
    }

    @Test
    fun clearingMatchesOnlyTheDecodedTopLevelSession() = withDirectory { directory ->
        val file = File(directory, "diagnostic-events.jsonl")
        val unrelated = "{\"testSessionId\":\"other\",\"extra\":{\"testSessionId\":\"selected\"}}"
        val malformed = "not json: \"testSessionId\":\"selected\""
        file.writeText(
            "{\"testSessionId\": \"selected\"}\n" +
                "{\"testSessionId\":\"selec\\u0074ed\"}\n$unrelated\n$malformed\n"
        )

        RollingJsonlFileSink(directory).clearSession("selected")

        assertEquals("$unrelated\n$malformed\n", file.readText())
    }

    @Test
    fun unrelatedAndMalformedRecordsKeepTheirExactBytes() = withDirectory { directory ->
        val file = File(directory, "diagnostic-events.jsonl")
        val retained = (
            "\r\n{\"testSessionId\":\"Selected\"}\r\n" +
                "{\"testSessionId\":\"selected-other\"}\n" +
                "{\"testSessionId\":null}\n{\"testSessionId\":3}\n" +
                "[\"selected\"]\n\"selected\"\n" +
                "{\"testSessionId\":\"other\",\"extra\":{\"testSessionId\":\"selected\"}}\n"
            ).toByteArray() + byteArrayOf(0xc3.toByte(), 0x28) +
            "{\"testSessionId\":\"selected\"}\ntruncated: \"testSessionId\":\"selected\"".toByteArray()
        file.writeBytes("{\"testSession\\u0049d\" : \"selec\\u0074ed\"}\r\n".toByteArray() + retained)

        RollingJsonlFileSink(directory).clearSession("selected")

        assertContentEquals(retained, file.readBytes())
    }

    @Test
    fun failedStagingOrReplacementPreservesOriginalsAndOnlyCleansOwnedStaging() {
        for (phase in listOf("create", "write", "replace")) withDirectory { directory ->
            val original = File(directory, "diagnostic-events.jsonl")
            val bytes = "{\"testSessionId\":\"selected\"}\n{\"testSessionId\":\"other\"}\r\n".toByteArray()
            original.writeBytes(bytes)
            val unowned = File(directory, ".diagnostic-events.jsonl.rewrite").apply { writeText("unrelated") }
            val failure = IOException("synthetic $phase failure")
            val operations = object : RollingJsonlFileOperations() {
                override fun createRewrite(original: File): File {
                    if (phase == "create") throw failure
                    return super.createRewrite(original)
                }

                override fun rewrite(original: File, staged: File, maxRecordBytes: Long, retain: (String) -> Boolean) {
                    if (phase == "write") {
                        staged.writeText("partial staging")
                        throw failure
                    }
                    super.rewrite(original, staged, maxRecordBytes, retain)
                }

                override fun replace(staged: File, original: File) {
                    if (phase == "replace") throw failure
                    super.replace(staged, original)
                }
            }
            val sink = RollingJsonlFileSink(directory, 4_096, 4, operations)

            assertSame(failure, assertFailsWith<IOException> { sink.clearSession("selected") })
            assertContentEquals(bytes, original.readBytes(), phase)
            assertEquals("unrelated", unowned.readText())
            assertTrue(directory.listFiles()!!.none { it.name.startsWith(".p2pkit-clear-") })
        }
    }

    @Test
    fun partialMultiGenerationFailureIsReportedAndCanBeRetried() = withDirectory { directory ->
        val selected = "{\"testSessionId\":\"selected\"}\n"
        val other = "{\"testSessionId\":\"other\"}\r\n"
        val files = (0..2).map { index ->
            File(directory, "diagnostic-events.jsonl" + if (index == 0) "" else ".$index")
                .apply { writeText(selected + other) }
        }
        var fail = true
        val operations = object : RollingJsonlFileOperations() {
            override fun replace(staged: File, original: File) {
                if (fail && original == files[1]) throw IOException("synthetic second-file failure")
                super.replace(staged, original)
            }
        }
        val sink = RollingJsonlFileSink(directory, 4_096, 4, operations)

        assertFailsWith<IOException> { sink.clearSession("selected") }
        assertEquals(listOf(other, selected + other, selected + other), files.map { it.readText() })
        assertTrue(directory.listFiles()!!.none { it.name.startsWith(".p2pkit-clear-") })
        fail = false
        sink.clearSession("selected")
        assertEquals(List(3) { other }, files.map { it.readText() })
        sink.clearSession("selected")
        assertEquals(List(3) { other }, files.map { it.readText() })
    }

    @Test
    fun cleanupFailureIsAttachedWithoutHidingThePrimaryFailure() = withDirectory { directory ->
        val original = File(directory, "diagnostic-events.jsonl").apply {
            writeText("{\"testSessionId\":\"other\"}\n")
        }
        val before = original.readBytes()
        val primary = IOException("synthetic replacement failure")
        val cleanup = IOException("synthetic cleanup failure")
        val operations = object : RollingJsonlFileOperations() {
            override fun replace(staged: File, original: File): Unit = throw primary
            override fun delete(file: File): Unit = throw cleanup
        }

        val error = assertFailsWith<IOException> {
            RollingJsonlFileSink(directory, 4_096, 4, operations).clearSession("selected")
        }

        assertSame(primary, error)
        assertEquals(listOf(cleanup), error.suppressed.toList())
        assertContentEquals(before, original.readBytes())
        assertEquals(1, directory.listFiles()!!.count { it.name.startsWith(".p2pkit-clear-") })
    }

    @Test
    fun selectiveReplacementNeverUsesTheNonAtomicExporterFallback() = withDirectory { directory ->
        val source = File(directory, "staged").apply { writeText("new") }
        val target = File(directory, "original").apply { writeText("old") }
        val attempts = mutableListOf<Boolean>()
        val unsupported = AtomicMoveNotSupportedException("synthetic", "synthetic", "unsupported")
        val move: (Boolean) -> Unit = { atomic ->
            attempts += atomic
            if (atomic) throw unsupported
        }

        assertSame(unsupported, assertFailsWith<AtomicMoveNotSupportedException> {
            DiagnosticNioFileReplacement.replace(source, target, requireAtomic = true, move = move)
        })
        assertEquals(listOf(true), attempts)
        assertEquals("new", source.readText())
        assertEquals("old", target.readText())
        attempts.clear()
        DiagnosticNioFileReplacement.replace(source, target, requireAtomic = false, move = move)
        assertEquals(listOf(true, false), attempts, "the existing export policy must remain unchanged")
    }

    @Test
    fun exactRecordByteLimitSucceedsButOneByteOverFailsWithoutReplacement() = withDirectory { directory ->
        val original = File(directory, "diagnostic-events.jsonl")
        val prefix = "{\"testSessionId\":\"selected\",\"padding\":\""
        val suffix = "\"}\n"
        val exact = prefix + "a".repeat(4_096 - prefix.length - suffix.length) + suffix
        val sink = RollingJsonlFileSink(directory, 4_096, 2)
        original.writeText(exact)
        sink.clearSession("selected")
        assertEquals(0L, original.length())
        original.writeText(" " + exact)
        assertFailsWith<IOException> { sink.clearSession("selected") }
        assertEquals(" " + exact, original.readText())
        assertTrue(directory.listFiles()!!.none { it.name.startsWith(".p2pkit-clear-") })
    }

    @Test
    fun inFlightAndQueuedSinkWritesMakeClearFailWithoutChangingMemory() {
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val recorder = recorder { _ ->
            if (entered.count > 0) {
                entered.countDown()
                check(release.await(5, TimeUnit.SECONDS))
            }
        }
        val worker = thread(name = "diagnostic-clear-inflight") {
            recorder.startSession("PS-T01", "both", "selected")
        }
        try {
            assertTrue(entered.await(5, TimeUnit.SECONDS))
            recorder.record(DiagnosticRecord(category = "test", eventName = "test.queued"))
            val before = recorder.snapshot()
            assertFailsWith<IOException> { recorder.clearCurrentSession() }
            assertEquals(before, recorder.snapshot())
        } finally {
            release.countDown()
            worker.join(5_000)
            assertFalse(worker.isAlive)
        }
        assertTrue(recorder.clearCurrentSession() > 0)
        assertTrue(recorder.snapshot().isEmpty())
        assertEquals(0L, recorder.droppedEventCount())
    }

    private fun recorder(sink: (String) -> Unit = {}): DiagnosticRecorder = DiagnosticRecorder(
        environment = DiagnosticEnvironment("test", "synthetic", "test", "test", "test", "synthetic"),
        timestamp = { "2026-09-06T00:00:00Z" },
        eventSink = sink
    )

    private fun withDirectory(action: (File) -> Unit) {
        val directory = Files.createTempDirectory("p2pkit-clear").toFile()
        try {
            action(directory)
        } finally {
            assertTrue(directory.deleteRecursively())
        }
    }
}
