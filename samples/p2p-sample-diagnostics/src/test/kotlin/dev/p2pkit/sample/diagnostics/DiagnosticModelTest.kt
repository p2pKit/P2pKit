package dev.p2pkit.sample.diagnostics

import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import java.io.File
import java.io.FileOutputStream
import java.nio.file.Files
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream
import kotlin.concurrent.thread
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertNotEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull
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
    fun concurrentPeersAndTransfersKeepExactCorrelation() {
        val recorder = recorder(maxEvents = 2_000)
        recorder.startSession("PS-T01", "both", "shared-session")
        val registry = DiagnosticCorrelationRegistry(
            activeSessionId = { recorder.activeSessionId },
            maxTransfers = 32
        )
        registry.setLocalPeerId("local-peer")
        val peerA = assertNotNull(registry.registerConnection("sdk-session-a", "peer-a"))
        val peerB = assertNotNull(registry.registerConnection("sdk-session-b", "peer-b"))
        assertNotEquals(peerA.connectionId, peerB.connectionId)

        val ready = CountDownLatch(2)
        val start = CountDownLatch(1)
        val threads = listOf("transfer-a" to "peer-a", "transfer-b" to "peer-b").map {
                (transferId, peerId) ->
            thread {
                ready.countDown()
                start.await()
                repeat(100) {
                    val correlation = assertNotNull(registry.registerTransfer(transferId, peerId))
                    recorder.record(
                        DiagnosticRecord(
                            peerId = correlation.peerId,
                            connectionId = correlation.connectionId,
                            transferId = transferId,
                            category = "transfer",
                            eventName = DiagnosticEventNames.TRANSFER_PROGRESS
                        )
                    )
                }
            }
        }
        assertTrue(ready.await(5, TimeUnit.SECONDS))
        start.countDown()
        threads.forEach { it.join(5_000) }
        assertTrue(threads.none { it.isAlive })

        val events = recorder.snapshot().filter { it.transferId != null }
        assertEquals(setOf(peerA.connectionId), events.filter { it.transferId == "transfer-a" }
            .mapNotNull { it.connectionId }.toSet())
        assertEquals(setOf(peerB.connectionId), events.filter { it.transferId == "transfer-b" }
            .mapNotNull { it.connectionId }.toSet())
        assertEquals(peerA, registry.connectionForSession("sdk-session-a"))
        assertEquals(peerB, registry.connectionForPeer("peer-b"))
    }

    @Test
    fun frameTraceUsesExactTransferOwnerAndLeavesAmbiguityUnassigned() {
        val recorder = recorder()
        recorder.startSession("PS-T01", "both", "shared-session")
        val registry = DiagnosticCorrelationRegistry(
            activeSessionId = { recorder.activeSessionId }
        )
        registry.setLocalPeerId("local-peer")
        registry.registerConnection("sdk-session-a", "peer-a")
        registry.registerConnection("sdk-session-b", "peer-b")
        val first = assertNotNull(registry.registerTransfer("a".repeat(32), "peer-a"))
        registry.registerTransfer("b".repeat(32), "peer-b")

        StructuredFrameTrace.record(
            recorder,
            "TX type=FILE_DATA len=64B chunk=0/1 id=${"a".repeat(32)} LAST",
            correlationForTransfer = registry::correlationForTransfer
        )
        val attributed = recorder.snapshot().last()
        assertEquals("a".repeat(32), attributed.transferId)
        assertEquals(first.connectionId, attributed.connectionId)
        assertEquals(anonymizeIdentifier("peer-a"), attributed.peerId)

        // A same transfer id on a different connection cannot be resolved
        // from a process-global frame line; it must never become last-wins.
        registry.registerTransfer("a".repeat(32), "peer-b")
        StructuredFrameTrace.record(
            recorder,
            "RX type=FILE_COMMIT len=72B xfer=${"a".repeat(32)}",
            correlationForTransfer = registry::correlationForTransfer
        )
        val ambiguous = recorder.snapshot().last()
        assertEquals("a".repeat(32), ambiguous.transferId)
        assertNull(ambiguous.connectionId)
        assertNull(ambiguous.peerId)
    }

    @Test
    fun transferCorrelationNeverInventsAnUnobservedConnection() {
        val recorder = recorder()
        recorder.startSession("PS-T01", "sender", "shared-session")
        val registry = DiagnosticCorrelationRegistry(
            activeSessionId = { recorder.activeSessionId }
        )
        registry.setLocalPeerId("local-peer")

        assertNull(registry.connectionForPeer("peer-a"))
        assertNull(registry.registerTransfer("transfer-a", "peer-a"))
        assertNull(registry.correlationForTransfer("transfer-a"))
    }

    @Test
    fun newTestSessionNeverReusesPriorConnectionCorrelation() {
        val recorder = recorder()
        recorder.startSession("PS-T01", "both", "session-a")
        val registry = DiagnosticCorrelationRegistry(
            activeSessionId = { recorder.activeSessionId }
        )
        registry.setLocalPeerId("local-peer")
        val before = assertNotNull(registry.registerConnection("sdk-session", "peer-a"))

        recorder.startSession("PS-T01", "both", "session-b")
        registry.resetSession()
        assertNull(registry.connectionForPeer("peer-a"))
        assertNull(registry.connectionForSession("sdk-session"))
        val after = assertNotNull(registry.registerConnection("sdk-session", "peer-a"))
        assertNotEquals(before.connectionId, after.connectionId)
        assertEquals(after, registry.connectionForSession("sdk-session"))
    }

    @Test
    fun retiredSdkSessionCannotEraseReplacementTransferOwnership() {
        val recorder = recorder()
        recorder.startSession("PS-T01", "both", "shared-session")
        val registry = DiagnosticCorrelationRegistry(
            activeSessionId = { recorder.activeSessionId }
        )
        registry.setLocalPeerId("local-peer")
        val retired = assertNotNull(registry.registerConnection("sdk-session-old", "peer-a"))
        val replacement = assertNotNull(
            registry.registerConnection("sdk-session-new", "peer-a")
        )
        assertEquals(retired.connectionId, replacement.connectionId)
        assertNull(registry.connectionForSession("sdk-session-old"))
        val transfer = assertNotNull(
            registry.registerTransfer("transfer-new", "peer-a", "sdk-session-new")
        )

        assertNull(registry.removeConnection("sdk-session-old"))
        assertEquals(replacement, registry.connectionForPeer("peer-a"))
        assertEquals(transfer, registry.correlationForTransfer("transfer-new"))
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
    fun redactionCoversIpv6ScopesMacAddressesCredentialsAndNames() {
        val recorder = recorder()
        recorder.startSession("ENV-02", "receiver", "session-network-redaction")
        recorder.record(
            DiagnosticRecord(
                category = "security",
                eventName = "security.network_values.checked",
                errorDescription =
                    "peer=Alice filename=private.txt host=[fe80::1%en0] " +
                        "gateway=2001:db8::42 mac=aa:bb:cc:dd:ee:ff token=ghp_secretvalue",
                details = mapOf(
                    "filename" to "private.txt",
                    "peerName" to "Alice's phone",
                    "device_name" to "Personal iPhone",
                    "ipv6Address" to "fe80::1%en0",
                    "mac" to "11-22-33-44-55-66",
                    "safeNote" to
                        "route 192.0.2.10 -> [fe80::abcd%wlan0] via 00:11:22:33:44:55"
                )
            )
        )

        val event = recorder.snapshot().last()
        assertEquals("<redacted>", event.details["filename"])
        assertEquals("<redacted>", event.details["peerName"])
        assertEquals("<redacted>", event.details["device_name"])
        assertEquals("<redacted>", event.details["ipv6Address"])
        assertTrue(event.details.getValue("mac").contains("<redacted-mac:"))
        assertTrue(event.details.getValue("safeNote").contains("<redacted-ip:"))
        assertTrue(event.details.getValue("safeNote").contains("<redacted-mac:"))
        val exportedText = buildString {
            append(event.errorDescription)
            append(event.details.values.joinToString())
        }
        listOf(
            "Alice",
            "private.txt",
            "fe80::1",
            "2001:db8::42",
            "aa:bb:cc:dd:ee:ff",
            "ghp_secretvalue",
            "192.0.2.10",
            "00:11:22:33:44:55"
        ).forEach { secret -> assertFalse(secret in exportedText, "leaked $secret") }
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
            recorder.record(
                DiagnosticRecord(category = "test", eventName = "test.export.repeated")
            )
            val replacement = DiagnosticEvidenceExporter.export(recorder, directory)
            assertEquals(zip, replacement)
            assertTrue(DiagnosticEvidenceExporter.verifyChecksums(replacement))
            ZipFile(replacement).use {
                val events = it.getInputStream(it.getEntry("events.jsonl")).bufferedReader().readText()
                assertTrue("test.export.repeated" in events)
            }
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun additionalEvidenceCannotReplaceCanonicalFiles() {
        val recorder = recorder()
        recorder.startSession("PS-T01", "sender", "session-reserved")
        val directory = Files.createTempDirectory("p2pkit-evidence-reserved").toFile()
        try {
            listOf(
                "events.jsonl",
                "events.txt",
                "summary.json",
                "manual-evidence-required.txt",
                "checksums.sha256"
            ).forEach { reserved ->
                assertFailsWith<IllegalArgumentException> {
                    DiagnosticEvidenceExporter.export(
                        recorder,
                        directory,
                        additionalFiles = mapOf(reserved to "replacement".toByteArray())
                    )
                }
            }
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun checksumVerificationRejectsUnlistedAndDuplicateManifestEntries() {
        val directory = Files.createTempDirectory("p2pkit-evidence-manifest").toFile()
        try {
            val payload = "payload".toByteArray()
            val digest = sha256(payload)
            val unlisted = File(directory, "unlisted.zip")
            writeZip(
                unlisted,
                listOf(
                    "events.jsonl" to payload,
                    "extra.txt" to "extra".toByteArray(),
                    "checksums.sha256" to "$digest  events.jsonl\n".toByteArray()
                )
            )
            assertFalse(DiagnosticEvidenceExporter.verifyChecksums(unlisted))

            val duplicate = File(directory, "duplicate.zip")
            writeZip(
                duplicate,
                listOf(
                    "events.jsonl" to payload,
                    "checksums.sha256" to (
                        "$digest  events.jsonl\n$digest  events.jsonl\n"
                    ).toByteArray()
                )
            )
            assertFalse(DiagnosticEvidenceExporter.verifyChecksums(duplicate))
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun finalOutcomeComesOnlyFromTheExplicitSessionCompletionEvent() {
        val recorder = recorder()
        recorder.startSession("PS-T05", "both", "session-outcome")
        recorder.record(
            DiagnosticRecord(
                transferId = "transfer-1",
                category = "transfer",
                eventName = DiagnosticEventNames.TRANSFER_COMPLETED,
                currentState = "completed",
                outcome = DiagnosticOutcome.SUCCESS
            )
        )
        recorder.record(
            DiagnosticRecord(
                category = "diagnostics",
                eventName = DiagnosticEventNames.DIAGNOSTIC_FAILURE,
                severity = DiagnosticSeverity.ERROR,
                outcome = DiagnosticOutcome.FAILURE
            )
        )

        assertNull(recorder.summary().finalOutcome)
        assertNull(recorder.summary().finalState)

        recorder.completeSession(DiagnosticOutcome.CANCELLATION, "operator cancelled", "cancelled")
        assertEquals(DiagnosticOutcome.CANCELLATION, recorder.summary().finalOutcome)
        assertEquals("cancelled", recorder.summary().finalState)
    }

    @Test
    fun hashAndIntegrityEvidenceNeverMixesTransfers() {
        val recorder = recorder()
        recorder.startSession("PS-T01", "both", "session-transfers")
        fun hash(transferId: String, sender: Boolean, digest: String) {
            recorder.record(
                DiagnosticRecord(
                    connectionId = "connection-$transferId",
                    transferId = transferId,
                    category = "file",
                    eventName = if (sender) {
                        DiagnosticEventNames.FILE_SENDER_HASH
                    } else {
                        DiagnosticEventNames.FILE_RECEIVER_HASH
                    },
                    payloadSizeBytes = if (sender) 10 else 11,
                    details = mapOf("sha256" to digest)
                )
            )
        }
        hash("transfer-a", sender = true, digest = "a".repeat(64))
        hash("transfer-b", sender = false, digest = "b".repeat(64))
        recorder.record(
            DiagnosticRecord(
                transferId = "transfer-b",
                category = "file",
                eventName = DiagnosticEventNames.FILE_INTEGRITY_CHECKED,
                details = mapOf("match" to "false")
            )
        )

        val ambiguous = recorder.summary()
        assertNull(ambiguous.selectedTransferId)
        assertNull(ambiguous.senderSha256)
        assertNull(ambiguous.receiverSha256)
        assertNull(ambiguous.integrityMatch)
        assertEquals(2, ambiguous.transferSummaries.size)

        val first = recorder.summary(selectedTransferId = "transfer-a")
        assertEquals("transfer-a", first.selectedTransferId)
        assertEquals("a".repeat(64), first.senderSha256)
        assertNull(first.receiverSha256)
        assertNull(first.integrityMatch)

        val second = recorder.summary(selectedTransferId = "transfer-b")
        assertEquals("transfer-b", second.selectedTransferId)
        assertNull(second.senderSha256)
        assertEquals("b".repeat(64), second.receiverSha256)
        assertFalse(second.integrityMatch ?: true)
    }

    @Test
    fun sessionContextAndPersistedIndexOrderAreAtomicWhileSinkIsBlocked() {
        val firstSinkCall = CountDownLatch(1)
        val releaseSink = CountDownLatch(1)
        val sessionChanged = CountDownLatch(1)
        val persisted = mutableListOf<String>()
        val persistedLock = Any()
        val recorder = recorder(eventSink = { line ->
            synchronized(persistedLock) { persisted += line }
            if (firstSinkCall.count == 1L) {
                firstSinkCall.countDown()
                check(releaseSink.await(5, TimeUnit.SECONDS)) { "test did not release sink" }
            }
        })

        val first = thread {
            recorder.startSession("PS-T01", "sender", "session-a")
        }
        assertTrue(firstSinkCall.await(5, TimeUnit.SECONDS), "first sink call never started")
        val second = thread {
            recorder.startSession("PS-T02", "receiver", "session-b")
            recorder.record(
                DiagnosticRecord(
                    category = "test",
                    eventName = "test.atomic_context"
                )
            )
            sessionChanged.countDown()
        }
        assertTrue(
            sessionChanged.await(5, TimeUnit.SECONDS),
            "session mutation waited for the external sink, so the sink ran under the recorder lock"
        )
        releaseSink.countDown()
        first.join(5_000)
        second.join(5_000)
        assertFalse(first.isAlive)
        assertFalse(second.isAlive)

        val stored = recorder.snapshot()
        assertEquals(listOf(1L, 2L, 3L), stored.map { it.index })
        assertEquals("session-a", stored[0].testSessionId)
        assertEquals("PS-T01", stored[0].testId)
        assertTrue(stored.drop(1).all { it.testSessionId == "session-b" && it.testId == "PS-T02" })
        val persistedEvents = synchronized(persistedLock) {
            persisted.map { JSON.decodeFromString<DiagnosticEvent>(it) }
        }
        assertEquals(stored.map { it.index }, persistedEvents.map { it.index })
    }

    @Test
    fun blockedExternalSinkCannotCreateAnUnboundedPendingQueue() {
        val sinkEntered = CountDownLatch(1)
        val releaseSink = CountDownLatch(1)
        val persisted = mutableListOf<DiagnosticEvent>()
        val recorder = recorder(maxEvents = 4, eventSink = { line ->
            synchronized(persisted) {
                persisted += JSON.decodeFromString<DiagnosticEvent>(line)
            }
            if (sinkEntered.count == 1L) {
                sinkEntered.countDown()
                check(releaseSink.await(5, TimeUnit.SECONDS)) { "test did not release sink" }
            }
        })
        val owner = thread {
            recorder.startSession("PS-T01", "sender", "session-bounded-sink")
        }
        assertTrue(sinkEntered.await(5, TimeUnit.SECONDS))

        repeat(20) { index ->
            recorder.record(
                DiagnosticRecord(
                    category = "test",
                    eventName = "test.pending.$index"
                )
            )
        }
        releaseSink.countDown()
        owner.join(5_000)
        assertFalse(owner.isAlive)

        val persistedSnapshot = synchronized(persisted) { persisted.toList() }
        assertTrue(persistedSnapshot.size <= 5, "one in-flight event plus four bounded pending events")
        assertEquals(persistedSnapshot.map { it.index }.sorted(), persistedSnapshot.map { it.index })
        assertTrue(recorder.droppedEventCount() >= 17)
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
    fun loggerSeparatesConnectionRecoveryFromTransferRetries() {
        val recorder = recorder()
        recorder.startSession("PS-T05", "both", "session-retry-classification")
        val logger = StructuredSdkLogger(recorder)

        logger.info("reconnect: attempt=2 peer=redacted")
        logger.info("reconnect: attempt=2 succeeded")
        logger.info("file transfer retry attempt=3")

        assertEquals(
            listOf(
                DiagnosticEventNames.RECOVERY_STARTED,
                DiagnosticEventNames.RECOVERY_COMPLETED,
                DiagnosticEventNames.TRANSFER_RETRY
            ),
            recorder.snapshot().takeLast(3).map { it.eventName }
        )
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
            val recorder = recorder(maxEvents = 1_000, eventSink = sink)
            recorder.startSession("PS-T01", "sender", "session-a")
            recorder.record(DiagnosticRecord(category = "test", eventName = "test.session_a.first"))
            recorder.startSession("PS-T02", "receiver", "session-b")
            repeat(200) { index ->
                recorder.record(
                    DiagnosticRecord(
                        category = "test",
                        eventName = "test.session_b.$index",
                        details = mapOf("padding" to "x".repeat(80))
                    )
                )
            }
            recorder.startSession("PS-T01", "sender", "session-a")
            recorder.record(DiagnosticRecord(category = "test", eventName = "test.session_a.last"))
            val selected = sink.evidenceFiles("session-a")
            assertTrue(selected.isNotEmpty())
            assertTrue(selected.values.all { bytes ->
                val text = bytes.decodeToString()
                "\"testSessionId\":\"session-a\"" in text &&
                    "\"testSessionId\":\"session-b\"" !in text
            })
            val evidenceDirectory = File(directory, "evidence")
            val archive = DiagnosticEvidenceExporter.export(
                recorder,
                evidenceDirectory,
                additionalFiles = selected
            )
            assertTrue(DiagnosticEvidenceExporter.verifyChecksums(archive))
            ZipFile(archive).use { zip ->
                val processEntries = buildList {
                    val entries = zip.entries()
                    while (entries.hasMoreElements()) {
                        entries.nextElement().takeIf { it.name.startsWith("process-") }?.let(::add)
                    }
                }
                assertTrue(processEntries.isNotEmpty())
                val processText = processEntries.joinToString("\n") {
                    zip.getInputStream(it).bufferedReader().readText()
                }
                assertTrue("\"testSessionId\":\"session-a\"" in processText)
                assertFalse("\"testSessionId\":\"session-b\"" in processText)
            }
            val files = directory.listFiles().orEmpty().filter {
                it.name.matches(Regex("""diagnostic-events\.jsonl(?:\.\d+)?"""))
            }
            assertTrue(files.size <= 2)
            assertTrue(files.all { it.length() <= 4_096 })
            sink.clearSession("session-b")
            assertTrue(files.none { file ->
                file.readText().contains("\"testSessionId\":\"session-b\"")
            })
            assertTrue(files.any { file ->
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

    private fun writeZip(file: File, entries: List<Pair<String, ByteArray>>) {
        ZipOutputStream(FileOutputStream(file)).use { zip ->
            entries.forEach { (name, contents) ->
                zip.putNextEntry(ZipEntry(name))
                zip.write(contents)
                zip.closeEntry()
            }
        }
    }
}
