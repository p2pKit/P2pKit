package dev.p2pkit.sample.diagnostics

import kotlinx.serialization.decodeFromString
import kotlinx.serialization.encodeToString
import java.io.File
import java.nio.file.Files
import java.util.zip.ZipFile
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class DiagnosticRedactionTest {
    @Test
    fun transportTextCannotEscapeThroughMemoryPersistenceOrZip() {
        val directory = Files.createTempDirectory("p2pkit-redaction").toFile()
        try {
            val sink = RollingJsonlFileSink(File(directory, "logs"))
            val recorder = recorder(eventSink = sink)
            recorder.startSession("ENV-02", "receiver", "redaction-session")
            // Current discovery, interface, dial/accept and connection formats.
            // Values are synthetic; no network, device or application data is read.
            val lines = listOf(
                "P2pKitLAN [1][browse] serviceAdded callback: instance=SYNTHETIC-PEER leaseActive=true",
                "P2pKitLAN [1][browse] serviceRemoved callback: instance=SYNTHETIC-PEER hasPeerId=true",
                "P2pKitLAN [1][browse] serviceResolved callback: instance=SYNTHETIC-PEER hasInfo=true",
                "P2pKitLAN [1][browse] serviceRemoved instance=SYNTHETIC-PEER pid=12345678",
                "P2pKitLAN [1][nic] local interfaces: test0 \"SYNTHETIC-ADAPTER\" addrs=[192.0.2.10]",
                "P2pKitLAN [1][dial] connect peer=12345678 -> 192.0.2.10:5000 (timeout=1000ms)",
                "P2pKitLAN [1][accept] accepted /192.0.2.10:5000",
                "P2pKitLAN [1][conn] opened SYNTHETIC-LABEL/[fe80::1%test0]:5000",
                "[AndroidLanDiscoveryTransport] serviceAdded instance=SYNTHETIC-PEER",
                "[browse] resolved instance=\"SYNTHETIC Private Device\"",
                "[future-format] unrelatedLabel=SYNTHETIC-UNRECOGNIZED",
                "[browse] instance=😀 SYNTHETIC-UNICODE\nsecond-line=SYNTHETIC-SECOND"
            )
            for (line in lines) {
                recorder.record(DiagnosticRecord(
                    category = "transport",
                    eventName = DiagnosticEventNames.TRANSPORT_LOG,
                    details = mapOf("line" to line)
                ))
            }
            val archive = DiagnosticEvidenceExporter.export(
                recorder,
                File(directory, "exports"),
                additionalFiles = sink.evidenceFiles(recorder.activeSessionId)
            )
            val outputs = mutableListOf(recorder.jsonLines())
            File(directory, "logs").listFiles().orEmpty().forEach { outputs += it.readText() }
            ZipFile(archive).use { zip ->
                zip.entries().asSequence().filterNot { it.isDirectory }.forEach { entry ->
                    outputs += zip.getInputStream(entry).bufferedReader().use { it.readText() }
                }
            }
            outputs.forEach { text ->
                assertFalse("SYNTHETIC-" in text || "SYNTHETIC Private" in text, "raw transport text escaped")
                assertFalse("192.0.2.10" in text || "fe80::1" in text, "raw endpoint escaped")
            }
            val events = recorder.snapshot().filter { it.eventName == DiagnosticEventNames.TRANSPORT_LOG }
            assertEquals(lines.size, events.size)
            events.forEach { event ->
                assertEquals("<redacted>", event.details["line"])
                assertEquals(listOf("line"), event.redactedFields)
            }
            assertTrue(DiagnosticEvidenceExporter.verifyChecksums(archive))
        } finally {
            directory.deleteRecursively()
        }
    }

    @Test
    fun unknownDetailsAndInvalidAllowlistedValuesFailClosed() {
        val invalid = listOf(
            "line" to "instance=SYNTHETIC-PEER",
            "message" to "unlabelled SYNTHETIC-PEER",
            "frame" to "future SYNTHETIC-PEER",
            "rawFrameRedacted" to "TX type=TEXT len=1B instance=SYNTHETIC-PEER",
            "futureField" to "SYNTHETIC-PEER",
            "testMode" to "true SYNTHETIC-PEER",
            "authenticated" to "TRUE",
            "sha256" to "a".repeat(63),
            "sha256" to "a".repeat(65),
            "messageId" to "a".repeat(31),
            "platform" to "SYNTHETIC-PEER",
            "totalBytes" to "9223372036854775808",
            "totalBytes" to "-1",
            "progressPercent" to "101",
            "futureField" to "a".repeat(64)
        )
        for ((key, value) in invalid) {
            val result = DiagnosticRedactor.redact(mapOf(key to value))
            assertEquals(mapOf(key to "<redacted>"), result.values, key)
            assertEquals(listOf(key), result.redactedFields, key)
        }
    }

    @Test
    fun knownStructuredEvidenceRetainsOnlyItsDeclaredValueShape() {
        val values = mapOf(
            "authenticated" to "true",
            "testMode" to "false",
            "contentsExported" to "false",
            "operatorDeclared" to "true",
            "sessionSnapshot" to "true",
            "senderDigestAvailable" to "false",
            "sha256" to "a".repeat(64),
            "packageSha256" to "b".repeat(64),
            "messageId" to "c".repeat(32),
            "match" to "unknown",
            "totalBytes" to Long.MAX_VALUE.toString(),
            "progressPercent" to "100",
            "platform" to "JVM_DESKTOP",
            "location" to "app-private",
            "source" to "android-content-uri",
            "securityPolicy" to "authenticated-same-app-test-only",
            "identityStorage" to "in-memory-per-kit",
            "feature" to "file-commit-sha256-v1",
            "messageType" to "binary"
        )
        val result = DiagnosticRedactor.redact(values)
        assertEquals(values, result.values)
        assertTrue(result.redactedFields.isEmpty())
        assertEquals(result, DiagnosticRedactor.redact(result.values))
    }

    @Test
    fun configurationDetailsUseTheSameFailClosedPolicy() {
        val recorder = recorder(configuration = DiagnosticConfiguration(
            faultInjection = mapOf("enabled" to "false", "futureSwitch" to "SYNTHETIC-PEER"),
            values = mapOf("testMode" to "true", "futureSetting" to "SYNTHETIC-PEER")
        ))
        val summary = recorder.summary()
        assertEquals(
            mapOf("enabled" to "false", "futureSwitch" to "<redacted>"),
            summary.configuration.faultInjection
        )
        assertEquals(mapOf("testMode" to "true", "futureSetting" to "<redacted>"), summary.configuration.values)
    }

    @Test
    fun sharedDetailPolicyFixture() {
        val source = checkNotNull(javaClass.getResourceAsStream("/diagnostic-detail-policy.json"))
            .bufferedReader().use { it.readText() }
        val cases = JSON.decodeFromString<Map<String, Map<String, List<String>>>>(source)
        assertEquals(setOf("accepted", "rejected"), cases.keys)
        for ((disposition, fields) in cases) {
            for ((key, values) in fields) {
                for (value in values) {
                    val result = DiagnosticRedactor.redact(mapOf(key to value))
                    val accepted = disposition == "accepted"
                    assertEquals(mapOf(key to if (accepted) value else "<redacted>"), result.values, "$key: $value")
                    assertEquals(if (accepted) emptyList() else listOf(key), result.redactedFields, "$key: $value")
                }
            }
        }
    }

    @Test
    fun persistedLegacyEventsAreSanitizedWithoutRewritingSourceOrCorrelation() {
        val directory = Files.createTempDirectory("p2pkit-redaction-legacy").toFile()
        try {
            val recorder = recorder()
            recorder.startSession("ENV-02", "receiver", "redaction-session")
            recorder.record(DiagnosticRecord(
                peerId = "SYNTHETIC-PEER",
                sdkSessionId = "SYNTHETIC-SDK-SESSION",
                transferId = "a".repeat(32),
                category = "transport",
                eventName = DiagnosticEventNames.TRANSPORT_LOG
            ))
            val legacy = recorder.snapshot().last().copy(
                details = mapOf("line" to "instance=SYNTHETIC-PEER", "sha256" to "b".repeat(64)),
                redactedFields = listOf("peerName")
            )
            val original = JSON.encodeToString(legacy) + "\n"
            val file = File(directory, "diagnostic-events.jsonl").apply { writeText(original) }
            val sink = RollingJsonlFileSink(directory)
            val exported = sink.evidenceFiles(recorder.activeSessionId).getValue("process-${file.name}")
            val event = JSON.decodeFromString<DiagnosticEvent>(exported.toString(Charsets.UTF_8).trim())
            assertEquals("<redacted>", event.details["line"])
            assertEquals(legacy.details["sha256"], event.details["sha256"])
            assertEquals(listOf("line", "peerName"), event.redactedFields)
            assertEquals(legacy.copy(details = event.details, redactedFields = event.redactedFields), event)
            assertEquals(original, file.readText(), "export must not destroy the operator's local original")
            assertEquals(
                exported.toList(),
                sink.evidenceFiles(recorder.activeSessionId).getValue("process-${file.name}").toList()
            )
        } finally {
            directory.deleteRecursively()
        }
    }

    private fun recorder(
        eventSink: (String) -> Unit = {},
        configuration: DiagnosticConfiguration = DiagnosticConfiguration()
    ) = DiagnosticRecorder(
        environment = DiagnosticEnvironment("test", "TestOS", "1", "1", "0".repeat(40), "safe-test"),
        configuration = configuration,
        idFactory = { "redaction-session" },
        eventSink = eventSink
    )
}
