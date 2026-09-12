package dev.p2pkit.sample.diagnostics

import java.nio.file.Files
import java.util.zip.ZipFile
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertTrue
import kotlinx.serialization.decodeFromString

class SecureConnectionDiagnosticTest {
    @Test
    fun profileRecordsPreserveOwnersButNeverInventOptionalFeaturesInJsonlOrExport() {
        val recorder = DiagnosticRecorder(
            environment = DiagnosticEnvironment(
                platform = "test",
                operatingSystem = "TestOS 1",
                applicationVersion = "test",
                buildNumber = "1",
                gitCommitSha = "a".repeat(40),
                safeDeviceId = "synthetic-device"
            )
        )
        recorder.startSession("PS-T05", "both", "synthetic-profile-test")
        // Android does not attach an SDK-session field here; JVM callers do.
        for (session in listOf(null, "synthetic-session", "synthetic-session")) {
            recorder.record(secureV2ConnectionRecord("synthetic-peer", "owned-connection", session))
        }
        val jsonl = recorder.jsonLines()
        val profiles = jsonl.lineSequence().filter { it.isNotBlank() }
            .map { JSON.decodeFromString<DiagnosticEvent>(it) }
            .filter { it.eventName == DiagnosticEventNames.PROTOCOL_NEGOTIATED }.toList()
        assertEquals(3, profiles.size)
        assertEquals(
            listOf(null, anonymizeIdentifier("synthetic-session"), anonymizeIdentifier("synthetic-session")),
            profiles.map { it.sdkSessionId }
        )
        for (event in profiles) {
            assertEquals("protocol", event.category)
            assertEquals("secure-v2", event.currentState)
            assertEquals("secure-v2", event.protocolVersion)
            assertEquals(anonymizeIdentifier("synthetic-peer"), event.peerId)
            assertEquals("owned-connection", event.connectionId)
            assertTrue(event.details.isEmpty())
        }
        assertFalse(jsonl.contains("file-commit-sha256-v1"))
        val directory = Files.createTempDirectory("secure-profile-diagnostics-").toFile()
        try {
            val archive = DiagnosticEvidenceExporter.export(recorder, directory)
            ZipFile(archive).use { zip ->
                val exported = zip.getInputStream(zip.getEntry("events.jsonl")).bufferedReader().use { it.readText() }
                assertEquals(jsonl, exported)
            }
        } finally {
            assertTrue(directory.deleteRecursively(), "Retire only this test's diagnostic archive")
        }
    }
}
