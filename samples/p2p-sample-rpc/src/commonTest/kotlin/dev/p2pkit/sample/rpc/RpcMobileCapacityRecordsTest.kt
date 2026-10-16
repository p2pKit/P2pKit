package dev.p2pkit.sample.rpc

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcDiagnostics
import dev.p2pkit.rpc.RpcTrustPurpose
import dev.p2pkit.rpc.RpcTrustStore
import kotlinx.coroutines.test.runTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertTrue

class RpcMobileCapacityRecordsTest {
    private fun fixture(platform: String = "Android"): MutableMap<String, String> {
        val alphabet = "abcdefghijklmnopqrstuvwxyz234567"
        val pins = List(128) { "p2f1-${alphabet[it / 32]}${alphabet[it % 32]}" + "a".repeat(50) }
        return linkedMapOf(
            "schema" to "1", "scope" to "mobile-usb-capacity", "runLabel" to "synthetic-mobile",
            "runNonce" to "1".repeat(64), "hostSourceSha" to "2".repeat(40), "hostPlatform" to platform,
            "hostArtifactSha256" to "3".repeat(64),
            "subnets" to "192.168.14.0/24", "hostInterface" to if (platform == "Android") "wlan0" else "en0",
            "hostAddress" to "192.168.14.2", "hostPort" to "48123", "clientPins" to pins.joinToString(","),
        )
    }

    @Test
    fun approvedMobileRecordRetainsTheOriginalPolicyAnd128IndependentPins() {
        for (platform in listOf("Android", "Ios")) {
            val config = RpcMobileCapacityConfig.parse(encodeMobileRecord(fixture(platform)))
            assertEquals(platform, config.hostPlatform)
            assertEquals(128, config.pins.size)
            assertTrue(config.settings.policy(true).allows("192.168.14.3"))
            assertFalse(config.settings.policy(true).allows("8.8.8.8"))
            assertFalse(config.settings.policy(true).allows("127.0.0.1"))
        }
    }

    @Test
    fun wrongPlatformUnsafeInterfaceBroadSubnetAndMalformedBindingsRemainRejected() {
        val changes = listOf(
            "hostPlatform" to "Jvm", "hostPlatform" to "ios", "hostInterface" to "utun0",
            "subnets" to "0.0.0.0/0", "hostAddress" to "8.8.8.8", "hostPort" to "22",
            "hostPort" to "048123", "runNonce" to "guess", "hostSourceSha" to "main",
            "hostArtifactSha256" to "assumed-install",
            "scope" to "production", "runLabel" to "../private", "unknown" to "private",
        )
        for ((key, value) in changes) {
            assertFailsWith<IllegalArgumentException> {
                RpcMobileCapacityConfig.parse(encodeMobileRecord(fixture().apply { put(key, value) }))
            }
        }
    }

    @Test
    fun duplicateFieldsPinsOversizedAndNonAsciiRecordsCannotImportTrust() {
        val original = encodeMobileRecord(fixture())
        for (text in listOf(original + "schema=1\n", original + "x=\u0000\n", "x=" + "a".repeat(16_384))) {
            assertFailsWith<IllegalArgumentException> { RpcMobileCapacityConfig.parse(text) }
        }
        for (change in listOf<(List<String>) -> List<String>>({ it.dropLast(1) }, { it.dropLast(1) + it.first() })) {
            val fields = fixture()
            fields["clientPins"] = change(fields.getValue("clientPins").split(',')).joinToString(",")
            assertFailsWith<IllegalArgumentException> { RpcMobileCapacityConfig.parse(encodeMobileRecord(fields)) }
        }
    }

    @Test
    fun phoneTelemetryNamesTheActualCollectorAndNeverInventsJvmThreads() {
        for (platform in listOf("Android", "Ios")) {
            val config = RpcMobileCapacityConfig.parse(encodeMobileRecord(fixture(platform)))
            val text = mobileTelemetryRecord(config, 4, 5_000, 128,
                RpcDiagnostics(acceptedCalls = 128, completedCalls = 128), RpcPhoneProcessStats(7_000_000, 8192, 12))
            val values = parseMobileRecord(text)
            assertEquals(config.binding(), values.filterKeys { it in config.binding() })
            assertEquals("host-run-monotonic", values["clock"])
            assertEquals("128", values["completed"])
            assertEquals("8192", values["residentBytes"])
            assertEquals(mobileResources(platform), values.filterKeys { it in mobileResources(platform) })
            assertFalse("jvmThreads" in values)
            assertFalse("clientPins" in values)
            assertFalse(text.contains("192.168.14.2"))
        }
    }

    @Test
    fun invalidCounterOrResourceEvidenceCannotBeSerializedAsASample() {
        val config = RpcMobileCapacityConfig.parse(encodeMobileRecord(fixture()))
        val resources = RpcPhoneProcessStats(0, 1024, 1)
        assertFailsWith<IllegalArgumentException> { RpcPhoneProcessStats(-1, 1, 1) }
        assertFailsWith<IllegalArgumentException> { RpcPhoneProcessStats(0, 0, 1) }
        assertFailsWith<IllegalArgumentException> { RpcPhoneProcessStats(0, 1, 0) }
        for (stats in listOf(RpcDiagnostics(runningCalls = 129), RpcDiagnostics(queuedCalls = 257),
            RpcDiagnostics(retainedRecords = 131_073), RpcDiagnostics(completedCalls = -1))) {
            assertFailsWith<IllegalArgumentException> { mobileTelemetryRecord(config, 1, 1000, 0, stats, resources) }
        }
        assertFailsWith<IllegalArgumentException> {
            mobileTelemetryRecord(config, 1, 1000, 129, RpcDiagnostics(), resources)
        }
    }

    @Test
    fun onlyTheExactUsbRunCanRequestStopWithoutAuthorizingAnyRpcCommand() {
        val config = RpcMobileCapacityConfig.parse(encodeMobileRecord(fixture()))
        val stop = config.binding() + mapOf("action" to "stop")
        assertTrue(mobileStopRequested(config, encodeMobileRecord(stop)))
        for (change in listOf("action" to "start", "action" to "erase", "runNonce" to "0".repeat(64),
            "hostPlatform" to "Ios", "extra" to "private")) {
            assertFalse(mobileStopRequested(config, encodeMobileRecord(stop + change)))
        }
    }

    @Test
    fun runtimeCleanupCannotEraseAFailedOrManuallyInterruptedControlSession() {
        val config = RpcMobileCapacityConfig.parse(encodeMobileRecord(fixture()))
        val healthy = parseMobileRecord(mobileClosedRecord(config, true))
        val failed = parseMobileRecord(mobileClosedRecord(config, false))
        assertEquals("true", healthy["controlHealthy"])
        assertEquals("false", failed["controlHealthy"])
        assertEquals(healthy - "controlHealthy", failed - "controlHealthy")
        assertEquals("true", failed["runtimeClosed"])
        assertEquals("true", failed["clientPinsRemoved"])
    }

    @Test
    fun cleanupRemovesOnlyItsExplicitSyntheticPinsAndNeverAnUnrelatedApproval() = runTest {
        val config = RpcMobileCapacityConfig.parse(encodeMobileRecord(fixture()))
        var saved = config.pins
        var replacements = 0
        val store = object : RpcTrustStore {
            override suspend fun load(appId: AppId, purpose: RpcTrustPurpose): Set<PeerFingerprint> {
                assertEquals(RpcCapacityContract.appId, appId)
                assertEquals(RpcTrustPurpose.HostClients, purpose)
                return saved
            }
            override suspend fun replace(appId: AppId, purpose: RpcTrustPurpose, fingerprints: Set<PeerFingerprint>) {
                replacements++
                saved = fingerprints
            }
        }
        val unrelated = PeerFingerprint.parse("p2f1-z" + "a".repeat(51))
        saved = saved + unrelated
        assertFailsWith<IllegalStateException> { retireMobileCapacityPins(store, config.pins) }
        assertTrue(unrelated in saved)
        assertEquals(0, replacements)
        // A local revocation before cleanup must not be undone by restoring the imported set.
        saved = config.pins - config.pins.first()
        retireMobileCapacityPins(store, config.pins)
        assertTrue(saved.isEmpty())
        assertEquals(1, replacements)
    }
}
