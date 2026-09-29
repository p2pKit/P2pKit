package dev.p2pkit.sample.rpc.lab

import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withTimeout
import java.nio.file.Files
import java.nio.file.Path
import java.nio.file.attribute.PosixFilePermissions
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse

class LabTelemetryTest {
    private fun sample(sequence: Long): ByteArray = LabFiles.encode(linkedMapOf(
        "schema" to "1", "runLabel" to "unit-test", "sequence" to sequence.toString(),
        "uptimeMillis" to "100", "cpuNanos" to "50", "residentBytes" to "4096", "nativeThreads" to "10",
        "jvmThreads" to "8", "connected" to "128", "accepted" to "20", "completed" to "20",
        "refused" to "0", "duplicates" to "0", "droppedNotifications" to "0", "protocolFailures" to "0",
        "connectionFailures" to "0", "running" to "0", "queued" to "0", "records" to "20", "payloadBytes" to "0",
    ))

    private fun directory(): Path = Files.createTempDirectory(
        "rpc-lab-telemetry-", PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rwx------")),
    ).toRealPath()

    private fun cleanup(root: Path) {
        Files.deleteIfExists(root.resolve("host-telemetry.txt"))
        Files.delete(root)
    }

    @Test
    fun waitsForAnActuallyNewSampleWithoutReplayingThePreviousOne() = runTest {
        val root = directory()
        try {
            val file = root.resolve("host-telemetry.txt")
            LabFiles.write(file, sample(1))
            val next = async { withTimeout(500) { awaitLabTelemetry(root, "unit-test", 1) } }
            delay(100)
            assertFalse(next.isCompleted)
            LabFiles.write(file, sample(2), replace = true)
            val result = next.await()
            assertEquals(2L, result.first)
            assertEquals(128, result.second.host.distinctAuthenticatedClients)
        } finally { cleanup(root) }
    }

    @Test
    fun repeatedOrMissingSamplesReachTheExistingCallerDeadline() = runTest {
        val root = directory()
        try {
            assertFailsWith<TimeoutCancellationException> {
                withTimeout(500) { awaitLabTelemetry(root, "unit-test", -1) }
            }
            LabFiles.write(root.resolve("host-telemetry.txt"), sample(1))
            assertFailsWith<TimeoutCancellationException> {
                withTimeout(500) { awaitLabTelemetry(root, "unit-test", 1) }
            }
        } finally { cleanup(root) }
    }

    @Test
    fun replayWrongRunAndImpossibleResourceValuesAreRejected() = runTest {
        val root = directory()
        try {
            val file = root.resolve("host-telemetry.txt")
            LabFiles.write(file, sample(1))
            assertFailsWith<IllegalArgumentException> { awaitLabTelemetry(root, "unit-test", 2) }
            assertFailsWith<IllegalArgumentException> { awaitLabTelemetry(root, "other-run", 0) }
            val values = LabFiles.parse(sample(2)).toMutableMap()
            for ((field, bad) in listOf("connected" to "129", "queued" to "257", "nativeThreads" to "0")) {
                val changed = values + (field to bad)
                assertFailsWith<IllegalArgumentException> { LabTelemetry.decode(changed, "unit-test") }
            }
        } finally { cleanup(root) }
    }
}
