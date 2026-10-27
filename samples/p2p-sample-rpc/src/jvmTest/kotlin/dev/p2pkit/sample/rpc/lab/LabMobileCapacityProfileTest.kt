package dev.p2pkit.sample.rpc.lab

import dev.p2pkit.rpc.RpcDiagnostics
import dev.p2pkit.sample.rpc.RpcMobileCapacityConfig
import dev.p2pkit.sample.rpc.RpcPhoneEnvironmentStats
import dev.p2pkit.sample.rpc.RpcPhoneLab
import dev.p2pkit.sample.rpc.RpcPhoneProcessStats
import dev.p2pkit.sample.rpc.encodeMobileRecord
import dev.p2pkit.sample.rpc.mobileTelemetryRecord
import dev.p2pkit.sample.rpc.parseMobileRecord
import java.nio.file.Path
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith

class LabMobileCapacityProfileTest {
    private fun lab(clients: Int, schema: String = "2"): LabConfig = LabConfig(Path.of("/unused-fixture"), mapOf(
        "schema" to schema, "role" to "client", "runLabel" to "lab-mobile-test",
        "sourceSha" to RpcPhoneLab.compiledSource, "endpointAddress" to "192.168.14.2", "port" to "48123",
        "subnets" to "192.168.14.0/24", "interface" to "eth0", "localAddress" to "192.168.14.3",
    ) + if (schema == "2") mapOf("clientCount" to clients.toString()) else emptyMap())

    private fun mobile(lab: LabConfig): RpcMobileCapacityConfig {
        val alphabet = "abcdefghijklmnopqrstuvwxyz234567"
        val pins = List(lab.clientCount) { "p2f1-${alphabet[it / 32]}${alphabet[it % 32]}" + "a".repeat(50) }
        val fields = mapOf(
            "schema" to lab.values.getValue("schema"), "scope" to "mobile-usb-capacity", "runLabel" to lab.runLabel,
            "runNonce" to "1".repeat(64), "hostSourceSha" to lab.sourceSha, "hostPlatform" to "Android",
            "hostArtifactSha256" to "3".repeat(64), "subnets" to "192.168.14.0/24", "hostInterface" to "wlan0",
            "hostAddress" to lab.endpointAddress, "hostPort" to lab.port.toString(),
            "clientPins" to pins.joinToString(","),
        ) + if (lab.values.getValue("schema") == "2") mapOf("clientCount" to lab.clientCount.toString()) else emptyMap()
        return RpcMobileCapacityConfig.parse(encodeMobileRecord(fields))
    }

    @Test
    fun phoneAndDriverMustAgreeOnSchemaProfileAndAllReadinessBindings() {
        for (clients in listOf(128, 256)) {
            val lab = lab(clients)
            val config = mobile(lab)
            val descriptor = config.binding() + ("hostInterface" to "wlan0")
            val collector = LabMobile(lab, descriptor)
            val ready = config.binding() + mapOf("fingerprint" to config.pins.first().value,
                "address" to lab.endpointAddress, "port" to lab.port.toString(), "compiledSourceMatched" to "true",
                "artifactKind" to "android-installed-base-apk")
            collector.ready(ready)
            for (changed in listOf("clientCount" to if (clients == 128) "256" else "128",
                "runNonce" to "0".repeat(64), "hostArtifactSha256" to "4".repeat(64),
                "compiledSourceMatched" to "false", "artifactKind" to "ios-installed-executable")) {
                assertFailsWith<IllegalArgumentException> { collector.ready(ready + changed) }
            }
            assertFailsWith<IllegalArgumentException> {
                LabMobile(lab(if (clients == 128) 256 else 128), descriptor)
            }
            assertFailsWith<IllegalArgumentException> { LabMobile(lab(128, "1"), descriptor) }
        }
    }

    @Test
    fun realSharedTelemetryIsAcceptedOnlyWithinTheSelectedProfileAndSafeThermalState() {
        for (clients in listOf(128, 256)) {
            val lab = lab(clients)
            val config = mobile(lab)
            val collector = LabMobile(lab, config.binding() + ("hostInterface" to "wlan0"))
            val stats = RpcDiagnostics(runningCalls = config.limits.runningCalls,
                queuedCalls = config.limits.queuedCalls,
                retainedRecords = config.limits.totalRecords, retainedPayloadBytes = config.limits.payloadBytes)
            val record = parseMobileRecord(mobileTelemetryRecord(config, 1, 1000, clients, stats,
                RpcPhoneProcessStats(7_000_000, 8192, 12)))
            val sample = collector.telemetry(record)
            assertEquals(clients, sample.host.distinctAuthenticatedClients)
            assertEquals(stats, sample.host.diagnostics)
            for (changed in listOf("clientCount" to if (clients == 128) "256" else "128",
                "connected" to (clients + 1).toString(), "running" to (config.limits.runningCalls + 1).toString(),
                "queued" to (config.limits.queuedCalls + 1).toString(),
                "records" to (config.limits.totalRecords + 1).toString(),
                "payloadBytes" to (config.limits.payloadBytes + 1).toString(), "batteryPercentMilli" to "invented")) {
                assertFailsWith<IllegalArgumentException> { collector.telemetry(record + changed) }
            }
            for (state in listOf("serious", "critical")) {
                val environment = RpcPhoneEnvironmentStats(null, null, null, "unknown", "android-battery-manager",
                    state, "android-power-manager")
                val interrupted = parseMobileRecord(mobileTelemetryRecord(config, 2, 2000, clients, stats,
                    RpcPhoneProcessStats(8_000_000, 8192, 12, environment)))
                assertFailsWith<IllegalArgumentException> { collector.telemetry(interrupted) }
            }
        }
    }
}
