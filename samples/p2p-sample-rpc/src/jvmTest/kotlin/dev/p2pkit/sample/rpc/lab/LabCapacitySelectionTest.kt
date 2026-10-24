package dev.p2pkit.sample.rpc.lab

import java.nio.file.Path
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class LabCapacitySelectionTest {
    private fun config(): Map<String, String> = mapOf(
        "schema" to "1", "role" to "host", "runLabel" to "capacity-test", "sourceSha" to "a".repeat(40),
        "endpointAddress" to "192.168.252.1", "port" to "29872", "subnets" to "192.168.252.0/30",
        "interface" to "rpc-local", "localAddress" to "192.168.252.1",
    )

    @Test fun originalSchemaStillSelectsOnlyTheOriginal128Profile() {
        assertEquals(128, LabConfig(Path.of("/unused-fixture"), config()).clientCount)
        assertFailsWith<IllegalArgumentException> {
            LabConfig(Path.of("/unused-fixture"), config() + ("clientCount" to "256"))
        }
    }

    @Test fun comparisonSchemaRequiresAnExplicitReviewedProfile() {
        for (count in listOf(128, 256)) {
            assertEquals(count, LabConfig(Path.of("/unused-fixture"),
                config() + mapOf("schema" to "2", "clientCount" to count.toString())).clientCount)
        }
        for (count in listOf("0", "129", "255", "257", "512")) {
            assertFailsWith<IllegalArgumentException> {
                LabConfig(Path.of("/unused-fixture"), config() + mapOf("schema" to "2", "clientCount" to count))
            }
        }
        assertFailsWith<IllegalArgumentException> {
            LabConfig(Path.of("/unused-fixture"), config() + ("schema" to "2"))
        }
    }

    private fun telemetry(): Map<String, String> = mapOf(
        "schema" to "1", "runLabel" to "capacity-test", "sequence" to "1", "uptimeMillis" to "1000",
        "cpuNanos" to "100", "residentBytes" to "1024", "nativeThreads" to "20", "jvmThreads" to "18",
        "connected" to "256", "accepted" to "100", "completed" to "100", "refused" to "0", "duplicates" to "0",
        "droppedNotifications" to "0", "protocolFailures" to "0", "connectionFailures" to "0", "running" to "0",
        "queued" to "0", "records" to "100", "payloadBytes" to "1024",
    )

    @Test fun telemetryCannotSilentlyPromoteAnOld128CampaignInto256Qualification() {
        val actual = LabTelemetry.decode(telemetry(), "capacity-test", 256)
        assertEquals(256, actual.host.distinctAuthenticatedClients)
        assertFailsWith<IllegalArgumentException> { LabTelemetry.decode(telemetry(), "capacity-test") }
        for ((key, value) in mapOf("connected" to "257", "running" to "257", "queued" to "513",
            "records" to "262145", "payloadBytes" to (128L * 1_048_576 + 1).toString())) {
            assertFailsWith<IllegalArgumentException> {
                LabTelemetry.decode(telemetry() + (key to value), "capacity-test", 256)
            }
        }
    }
}
