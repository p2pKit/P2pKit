package dev.p2pkit.sample.rpc

import dev.p2pkit.rpc.RpcDiagnostics
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class RpcMobileCapacityProfileTest {
    private fun fixture(clients: Int = 256, schema: String = "2", platform: String = "Android"):
        Map<String, String> {
        val alphabet = "abcdefghijklmnopqrstuvwxyz234567"
        val pins = List(clients) { "p2f1-${alphabet[it / 32]}${alphabet[it % 32]}" + "a".repeat(50) }
        return linkedMapOf(
            "schema" to schema, "scope" to "mobile-usb-capacity", "runLabel" to "profile-test",
            "runNonce" to "1".repeat(64), "hostSourceSha" to "2".repeat(40), "hostPlatform" to platform,
            "hostArtifactSha256" to "3".repeat(64), "subnets" to "192.168.14.0/24",
            "hostInterface" to if (platform == "Android") "wlan0" else "en0",
            "hostAddress" to "192.168.14.2", "hostPort" to "48123", "clientPins" to pins.joinToString(","),
        ) + if (schema == "2") mapOf("clientCount" to clients.toString()) else emptyMap()
    }

    @Test
    fun explicitProfilesBindSelectedCountWithoutWideningLegacyRecords() {
        for (platform in listOf("Android", "Ios")) {
            val legacy = RpcMobileCapacityConfig.parse(encodeMobileRecord(fixture(128, "1", platform)))
            assertEquals(128, legacy.clientCount)
            assertFalse("clientCount" in legacy.binding())
            for (clients in listOf(128, 256)) {
                val encoded = encodeMobileRecord(fixture(clients, platform = platform))
                assertTrue(encoded.length <= 16_384)
                val config = RpcMobileCapacityConfig.parse(encoded)
                assertEquals(clients, config.clientCount)
                assertEquals(clients, config.pins.size)
                assertEquals("2", config.binding()["schema"])
                assertEquals(clients.toString(), config.binding()["clientCount"])
                assertEquals(clients, config.limits.trustedClients)
            }
        }
        assertFailsWith<IllegalArgumentException> {
            RpcMobileCapacityConfig.parse(encodeMobileRecord(fixture(256, "1")))
        }
        assertFailsWith<IllegalArgumentException> {
            RpcMobileCapacityConfig.parse(encodeMobileRecord(fixture(128, "1") + ("clientCount" to "128")))
        }
    }

    @Test
    fun profileAndPinCountCannotBeInferredOrChangedWithoutAnExplicitMatchingRecord() {
        for (changed in listOf("0", "127", "129", "257", "512", "0256", "+256", "256 ")) {
            assertFailsWith<IllegalArgumentException> {
                RpcMobileCapacityConfig.parse(encodeMobileRecord(fixture() + ("clientCount" to changed)))
            }
        }
        for (fields in listOf(fixture() - "clientCount", fixture() + ("clientCount" to "128"),
            fixture(128) + ("clientCount" to "256"), fixture() + ("schema" to "3"))) {
            assertFailsWith<IllegalArgumentException> { RpcMobileCapacityConfig.parse(encodeMobileRecord(fields)) }
        }
    }

    @Test
    fun selectedProfileBindsTelemetryStopAndCleanupAndRejectsOneOverEveryBound() {
        val resources = RpcPhoneProcessStats(7_000_000, 8192, 12)
        for (clients in listOf(128, 256)) {
            val config = RpcMobileCapacityConfig.parse(encodeMobileRecord(fixture(clients)))
            val limits = config.limits
            val stats = RpcDiagnostics(runningCalls = limits.runningCalls, queuedCalls = limits.queuedCalls,
                retainedRecords = limits.totalRecords, retainedPayloadBytes = limits.payloadBytes)
            val text = mobileTelemetryRecord(config, 1, 1000, clients, stats, resources)
            val record = parseMobileRecord(text)
            assertEquals(config.binding(), record.filterKeys { it in config.binding() })
            assertEquals(clients.toString(), record["connected"])
            assertEquals(limits.payloadBytes.toString(), record["payloadBytes"])
            assertFalse("clientPins" in record)
            assertFalse(text.contains(config.settings.localAddress))
            for (changed in listOf(stats.copy(runningCalls = limits.runningCalls + 1),
                stats.copy(queuedCalls = limits.queuedCalls + 1), stats.copy(retainedRecords = limits.totalRecords + 1),
                stats.copy(retainedPayloadBytes = limits.payloadBytes + 1))) {
                assertFailsWith<IllegalArgumentException> {
                    mobileTelemetryRecord(config, 1, 1000, clients, changed, resources)
                }
            }
            assertFailsWith<IllegalArgumentException> {
                mobileTelemetryRecord(config, 1, 1000, clients + 1, stats, resources)
            }
            val stop = config.binding() + ("action" to "stop")
            assertTrue(mobileStopRequested(config, encodeMobileRecord(stop)))
            assertFalse(mobileStopRequested(config, encodeMobileRecord(stop +
                ("clientCount" to if (clients == 128) "256" else "128"))))
            val closed = parseMobileRecord(mobileClosedRecord(config, true))
            assertEquals(config.binding(), closed.filterKeys { it in config.binding() })
            assertTrue(config.matchesHealthyClosed(encodeMobileRecord(closed)))
            assertFalse(config.matchesHealthyClosed(mobileClosedRecord(config, false)))
            assertFalse(config.matchesHealthyClosed(encodeMobileRecord(closed + ("runtimeClosed" to "false"))))
            assertFalse(config.matchesHealthyClosed(encodeMobileRecord(closed + ("clientCount" to
                if (clients == 128) "256" else "128"))))
        }
    }

    @Test
    fun missingBatteryObservationsStayUnavailableAndLegacyTelemetryKeysStayIdentical() {
        val resources = RpcPhoneProcessStats(7_000_000, 8192, 12)
        val legacy = RpcMobileCapacityConfig.parse(encodeMobileRecord(fixture(128, "1")))
        val current = RpcMobileCapacityConfig.parse(encodeMobileRecord(fixture(128)))
        val old = parseMobileRecord(mobileTelemetryRecord(legacy, 1, 1000, 128, RpcDiagnostics(), resources))
        val fresh = parseMobileRecord(mobileTelemetryRecord(current, 1, 1000, 128, RpcDiagnostics(), resources))
        assertTrue(old.keys.intersect(RpcPhoneEnvironmentStats.FIELDS).isEmpty())
        assertEquals(RpcPhoneEnvironmentStats.FIELDS, fresh.filterValues { it == "unavailable" }.keys)
        assertEquals(old - legacy.binding().keys,
            fresh - current.binding().keys - RpcPhoneEnvironmentStats.FIELDS)
    }

    @Test
    fun actualBatteryAndThermalFieldsArePlatformBoundAndStopAtSeriousOrCritical() {
        val android = RpcPhoneEnvironmentStats(75_000, -123_000, 31_000,
            "unplugged", "android-battery-manager", "fair", "android-power-manager")
        val config = RpcMobileCapacityConfig.parse(encodeMobileRecord(fixture()))
        val record = parseMobileRecord(mobileTelemetryRecord(config, 1, 1000, 256,
            RpcDiagnostics(), RpcPhoneProcessStats(7_000_000, 8192, 12, android)))
        assertEquals("-123000", record["batteryCurrentMicroamps"])
        assertEquals("31000", record["batteryTemperatureMilliC"])
        val decoded = RpcPhoneEnvironmentStats.parse(
            record.filterKeys { it in RpcPhoneEnvironmentStats.FIELDS }, "Android")
        assertFalse(decoded.requiresThermalStop)
        for (state in listOf("serious", "critical")) {
            assertTrue(RpcPhoneEnvironmentStats(null, null, null, "unknown", "ios-uidevice",
                state, "ios-process-info").requiresThermalStop)
        }
        assertFailsWith<IllegalArgumentException> { android.record("Ios") }
        assertFailsWith<IllegalArgumentException> {
            RpcPhoneEnvironmentStats(50_000, 1, null, "charging", "ios-uidevice", "nominal", "ios-process-info")
        }
        assertFailsWith<IllegalArgumentException> {
            RpcPhoneEnvironmentStats(100_001, null, null, "unknown", "android-battery-manager",
                "unavailable", "unavailable")
        }
        assertFailsWith<IllegalArgumentException> {
            RpcPhoneEnvironmentStats.parse(android.record("Android") + ("batteryCurrentMicroamps" to "-0"), "Android")
        }
    }
}
