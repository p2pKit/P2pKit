package dev.p2pkit.sample.diagnostics

import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import java.io.File
import java.nio.file.Files
import java.util.concurrent.CountDownLatch
import java.util.zip.ZipFile
import kotlin.concurrent.thread
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertTrue

class DiagnosticModelTest {
    @Test
    fun representativeEventJsonSchemaRemainsCanonical() {
        val event = DiagnosticEvent(
            index = 7,
            timestamp = "2026-07-23T15:45:00.123Z",
            platform = "jvm",
            operatingSystem = "TestOS 1",
            applicationVersion = "1.2.3",
            buildNumber = "42",
            gitCommitSha = "0123456789abcdef0123456789abcdef01234567",
            safeDeviceId = "safe-device",
            testSessionId = "session-1",
            testId = "PS-T05",
            role = "sender",
            peerId = "anon-peer",
            connectionId = "conn-1",
            transferId = "transfer-1",
            category = "transfer",
            eventName = "transfer.completed",
            severity = DiagnosticSeverity.INFO,
            currentState = "completed",
            previousState = "transferring",
            protocolVersion = "secure-v2",
            packetType = "file_commit",
            direction = DiagnosticDirection.RECEIVED,
            payloadSizeBytes = 1024,
            sequenceNumber = 9,
            chunkNumber = 4,
            chunkCount = 4,
            retryNumber = 1,
            timeoutMillis = 5_000,
            retryDelayMillis = 250,
            durationMillis = 321,
            outcome = DiagnosticOutcome.SUCCESS,
            details = mapOf("sha256" to "abc"),
            redactedFields = listOf("token")
        )

        assertEquals(
            "{\"schemaVersion\":1,\"index\":7,\"timestamp\":\"2026-07-23T15:45:00.123Z\"," +
                "\"platform\":\"jvm\",\"operatingSystem\":\"TestOS 1\",\"applicationVersion\":\"1.2.3\"," +
                "\"buildNumber\":\"42\",\"gitCommitSha\":\"0123456789abcdef0123456789abcdef01234567\"," +
                "\"safeDeviceId\":\"safe-device\",\"testSessionId\":\"session-1\",\"testId\":\"PS-T05\"," +
                "\"role\":\"sender\",\"peerId\":\"anon-peer\",\"connectionId\":\"conn-1\"," +
                "\"transferId\":\"transfer-1\",\"category\":\"transfer\",\"eventName\":\"transfer.completed\"," +
                "\"severity\":\"INFO\",\"currentState\":\"completed\",\"previousState\":\"transferring\"," +
                "\"protocolVersion\":\"secure-v2\",\"packetType\":\"file_commit\",\"direction\":\"RECEIVED\"," +
                "\"payloadSizeBytes\":1024,\"sequenceNumber\":9,\"chunkNumber\":4,\"chunkCount\":4," +
                "\"retryNumber\":1,\"timeoutMillis\":5000,\"retryDelayMillis\":250,\"durationMillis\":321," +
                "\"errorCode\":null,\"errorDescription\":null,\"outcome\":\"SUCCESS\"," +
                "\"details\":{\"sha256\":\"abc\"},\"redactedFields\":[\"token\"]}",
            JSON.encodeToString(event)
        )
    }

    @Test
    fun requiredFieldsCorrelationAndShaAreRecorded() {
        val recorder = recorder()
        val session = recorder.startSession("PS-T05", "sender", "shared-session")
        val connection = correlationConnectionId(session, "peer-a", "peer-b")
        assertEquals(connection, correlationConnectionId(session, "peer-b", "peer-a"))

        recorder.record(
            DiagnosticRecord(
                peerId = "peer-b",
                connectionId = connection,
                transferId = "transfer-1",
                category = "file",
                eventName = DiagnosticEventNames.FILE_SENDER_HASH,
                payloadSizeBytes = 3,
                details = mapOf("sha256" to sha256("abc".toByteArray()))
            )
        )

        val event = recorder.snapshot().last()
        assertEquals("PS-T05", event.testId)
        assertEquals("shared-session", event.testSessionId)
        assertEquals("transfer-1", event.transferId)
        assertEquals(connection, event.connectionId)
        assertEquals("anon-02f95dcab675d8f7", event.peerId)
        assertEquals(64, event.details.getValue("sha256").length)
        assertTrue(event.timestamp.endsWith("Z"))
        assertEquals("test", event.platform)
        assertEquals("1.2.3", event.applicationVersion)
        assertEquals("42", event.buildNumber)
        assertEquals(40, event.gitCommitSha.length)
    }

    @Test
    fun sensitiveValuesAndNetworkAddressesAreRedacted() {
        val recorder = recorder()
        recorder.startSession("PS-T01", "receiver", "session-redaction")
        recorder.record(
            DiagnosticRecord(
                category = "security",
                eventName = "security.redaction.checked",
                errorDescription = "connect 192.168.1.8 using Bearer abc.def payload=private-bytes",
                details = mapOf(
                    "password" to "do-not-export",
                    "ssid" to "private-network",
                    "note" to "host 10.0.0.2 message=private-text"
                )
            )
        )
        val event = recorder.snapshot().last()
        assertEquals("<redacted>", event.details["password"])
        assertEquals("<redacted>", event.details["ssid"])
        assertTrue(event.details.getValue("note").contains("<redacted-ip:"))
        assertFalse(event.errorDescription.orEmpty().contains("abc.def"))
        assertFalse(event.errorDescription.orEmpty().contains("private-bytes"))
        assertFalse(event.details.getValue("note").contains("private-text"))
        assertEquals(listOf("password", "ssid"), event.redactedFields)
    }

    @Test
    fun exportHasDeterministicValidNameFilesAndChecksums() {
        val recorder = recorder(timestamp = { "2026-07-23T15:45:00.000Z" })
        recorder.startSession("PS-T01", "sender", "session-abc123")
        recorder.completeSession(DiagnosticOutcome.SUCCESS, "done", "Completed")
        val directory = Files.createTempDirectory("p2pkit-evidence").toFile()
        try {
            val zip = DiagnosticEvidenceExporter.export(recorder, directory)
            assertEquals("PS-T01_test_2026-07-23T154500_session-abc123.zip", zip.name)
            assertTrue(DiagnosticEvidenceExporter.verifyChecksums(zip))
            ZipFile(zip).use {
                assertNotNull(it.getEntry("events.jsonl"))
                assertNotNull(it.getEntry("events.txt"))
                assertNotNull(it.getEntry("summary.json"))
                assertNotNull(it.getEntry("manual-evidence-required.txt"))
                assertNotNull(it.getEntry("checksums.sha256"))
            }
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun rotationSessionCleanupAndFiltersAreBounded() {
        val recorder = recorder(maxEvents = 4, maxSessions = 2)
        repeat(3) { sessionIndex ->
            recorder.startSession("PS-T0$sessionIndex", "peer", "session-$sessionIndex")
            repeat(3) {
                recorder.record(
                    DiagnosticRecord(
                        transferId = "transfer-$sessionIndex",
                        category = "test",
                        eventName = "test.event.$it",
                        severity = if (it == 2) DiagnosticSeverity.ERROR else DiagnosticSeverity.INFO
                    )
                )
            }
        }
        assertTrue(recorder.snapshot().size <= 4)
        assertTrue(recorder.droppedEventCount() > 0)
        assertTrue(
            recorder.snapshot(DiagnosticFilter(transferId = "transfer-2")).all {
                it.transferId == "transfer-2"
            }
        )
        assertTrue(
            recorder.snapshot(DiagnosticFilter(minimumSeverity = DiagnosticSeverity.ERROR)).all {
                it.severity == DiagnosticSeverity.ERROR
            }
        )
        val removed = recorder.clearCurrentSession()
        assertTrue(removed > 0)
        assertTrue(recorder.snapshot().none { it.testSessionId == "session-2" })
    }

    @Test
    fun terminalOutcomesMatchRealEventAndSessionsDoNotMixUnderConcurrency() {
        val recorder = recorder(maxEvents = 2_000)
        recorder.startSession("PS-T06", "both", "session-concurrent")
        val ready = CountDownLatch(8)
        val start = CountDownLatch(1)
        val threads = (0 until 8).map { transfer ->
            thread {
                ready.countDown()
                start.await()
                repeat(100) { chunk ->
                    recorder.record(
                        DiagnosticRecord(
                            transferId = "transfer-$transfer",
                            category = "transfer",
                            eventName = DiagnosticEventNames.TRANSFER_PROGRESS,
                            chunkNumber = chunk,
                            chunkCount = 100
                        )
                    )
                }
            }
        }
        ready.await()
        start.countDown()
        threads.forEach { it.join() }
        recorder.completeSession(DiagnosticOutcome.RECOVERY, "recovered", "Completed")

        val events = recorder.snapshot()
        assertEquals(802, events.size)
        assertEquals(800, events.count { it.eventName == DiagnosticEventNames.TRANSFER_PROGRESS })
        assertEquals(100, events.count { it.transferId == "transfer-3" })
        assertEquals(DiagnosticOutcome.RECOVERY, recorder.summary().finalOutcome)
    }

    @Test
    fun loggingAndDelegateFailuresNeverEscapeObservedOperation() {
        val recorder = recorder(eventSink = { error("sink failed") })
        recorder.startSession("PS-T05", "sender", "session-safe")
        val logger = StructuredSdkLogger(
            recorder,
            delegate = object : dev.p2pkit.core.P2pLogger {
                override fun debug(message: String): Unit = throw IllegalStateException("delegate failed")
                override fun info(message: String): Unit = throw IllegalStateException("delegate failed")
                override fun warn(message: String, throwable: Throwable?): Unit =
                    throw IllegalStateException("delegate failed")
                override fun error(message: String, throwable: Throwable?): Unit =
                    throw IllegalStateException("delegate failed")
            }
        )
        logger.warn("authenticated protocol violation", IllegalStateException("bad"))
        assertTrue(recorder.droppedEventCount() >= 2)
        assertEquals(DiagnosticEventNames.PROTOCOL_PACKET_REJECTED, recorder.snapshot().last().eventName)
    }

    @Test
    fun frameParserRecordsPacketsChunksAcknowledgmentsAndRejects() {
        val recorder = recorder()
        recorder.startSession("ENV-02", "sender", "session-frame")
        StructuredFrameTrace.record(
            recorder,
            "TX type=FILE_DATA len=65536B chunk=2/4 id=abcd1234",
            "conn-1"
        )
        StructuredFrameTrace.record(
            recorder,
            "RX type=FILE_COMMIT len=72B xfer=feedbeef",
            "conn-1"
        )
        StructuredFrameTrace.record(recorder, "not-a-frame", "conn-1")
        val events = recorder.snapshot().takeLast(3)
        assertEquals("file_data", events[0].packetType)
        assertEquals(2, events[0].chunkNumber)
        assertEquals(DiagnosticEventNames.TRANSFER_ACK, events[1].eventName)
        assertEquals("feedbeef", events[1].transferId)
        assertEquals(DiagnosticEventNames.PROTOCOL_PACKET_REJECTED, events[2].eventName)
    }

    @Test
    fun finalResultSupportsAllRequiredTerminalKinds() {
        DiagnosticOutcome.entries.forEach { outcome ->
            val recorder = recorder()
            recorder.startSession("PS-T04", "both", "session-${outcome.name.lowercase()}")
            recorder.completeSession(outcome, outcome.name, "terminal")
            assertEquals(outcome, recorder.summary().finalOutcome)
        }
    }

    @Test
    fun peerIdsAreNonReversibleAndStable() {
        assertEquals(anonymizeIdentifier("same"), anonymizeIdentifier("same"))
        assertNotEquals(anonymizeIdentifier("same"), anonymizeIdentifier("other"))
        assertFalse(anonymizeIdentifier("same").contains("same"))
    }

    @Test
    fun rollingJsonlSinkRotatesAndClearsOnlyRequestedSession() {
        val directory = Files.createTempDirectory("p2pkit-rolling").toFile()
        try {
            val sink = RollingJsonlFileSink(directory, maxBytes = 4_096, maxFiles = 2)
            sink("""{"testSessionId":"session-a","index":1}""")
            repeat(200) { sink("""{"testSessionId":"session-b","index":$it,"padding":"${"x".repeat(80)}"}""") }
            sink("""{"testSessionId":"session-a","index":2}""")
            val files = directory.listFiles().orEmpty().filter { it.name.endsWith(".jsonl") }
            assertTrue(files.size <= 2)
            assertTrue(files.all { it.length() <= 4_096 })
            sink.clearSession("session-b")
            assertTrue(directory.listFiles().orEmpty().none { file ->
                file.readText().contains("\"testSessionId\":\"session-b\"")
            })
            assertTrue(directory.listFiles().orEmpty().any { file ->
                file.readText().contains("\"testSessionId\":\"session-a\"")
            })
        } finally {
            directory.deleteRecursively()
        }
    }

    private fun recorder(
        maxEvents: Int = 100,
        maxSessions: Int = 8,
        timestamp: () -> String = { "2026-07-23T15:45:00.123Z" },
        eventSink: (String) -> Unit = {}
    ): DiagnosticRecorder = DiagnosticRecorder(
        environment = DiagnosticEnvironment(
            platform = "test",
            operatingSystem = "TestOS 1",
            applicationVersion = "1.2.3",
            buildNumber = "42",
            gitCommitSha = "0123456789abcdef0123456789abcdef01234567",
            safeDeviceId = "safe-test-device"
        ),
        maxEvents = maxEvents,
        maxSessions = maxSessions,
        timestamp = timestamp,
        idFactory = { "session-fixed" },
        eventSink = eventSink
    )
}
