package dev.p2pkit.sample.rpc.lab

import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.rpc.RpcDiagnostics
import dev.p2pkit.sample.rpc.RpcCapacityHostPlatform
import dev.p2pkit.sample.rpc.RpcMobileCapacityConfig
import dev.p2pkit.sample.rpc.RpcPhoneLab
import dev.p2pkit.sample.rpc.RpcPhoneProcessStats
import dev.p2pkit.sample.rpc.mobileTelemetryRecord
import dev.p2pkit.sample.rpc.parseMobileRecord
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

class LabMobileTest {
    private fun fixture(root: Path, platform: String = "Android"): LabMobile {
        val config = LabConfig(root, mapOf(
            "schema" to "1", "role" to "client", "runLabel" to "unit-mobile", "sourceSha" to RpcPhoneLab.compiledSource,
            "endpointAddress" to "192.168.14.2", "port" to "48123", "subnets" to "192.168.14.0/24",
            "interface" to "en0", "localAddress" to "192.168.14.3",
        ))
        return LabMobile(config, mapOf("schema" to "1", "scope" to "mobile-usb-capacity", "runLabel" to "unit-mobile",
            "hostSourceSha" to RpcPhoneLab.compiledSource, "hostArtifactSha256" to "3".repeat(64),
            "runNonce" to "1".repeat(64), "hostPlatform" to platform, "hostInterface" to "wlan0"))
    }

    private inline fun withFixture(
        platform: String = "Android", action: (LabMobile, RpcMobileCapacityConfig, Path) -> Unit,
    ) {
        val root = Files.createTempDirectory("rpc-mobile-control-",
            PosixFilePermissions.asFileAttribute(PosixFilePermissions.fromString("rwx------"))).toRealPath()
        try {
            val mobile = fixture(root, platform)
            val alphabet = "abcdefghijklmnopqrstuvwxyz234567"
            val pins = List(128) {
                PeerFingerprint.parse("p2f1-${alphabet[it / 32]}${alphabet[it % 32]}" + "a".repeat(50))
            }
            mobile.prepare(pins)
            val phone = RpcMobileCapacityConfig.parse(LabFiles.read(root.resolve("mobile-inbox.txt"))
                .toString(Charsets.US_ASCII))
            action(mobile, phone, root)
        } finally {
            Files.deleteIfExists(root.resolve("mobile-inbox.txt"))
            Files.deleteIfExists(root.resolve("host-telemetry.txt"))
            Files.delete(root)
        }
    }

    @Test
    fun mobileImportAndReadyBindTheActualPhoneSourceArtifactRunAndHost() {
        for (platform in listOf("Android", "Ios")) withFixture(platform) { mobile, config, _ ->
            assertEquals(RpcCapacityHostPlatform.valueOf(platform), mobile.platform)
            assertEquals(128, config.pins.size)
            val ready = config.binding() + mapOf("fingerprint" to config.pins.first().value,
                "address" to "192.168.14.2", "port" to "48123", "compiledSourceMatched" to "true",
                "artifactKind" to if (platform == "Android") "android-installed-base-apk"
                    else "ios-installed-executable")
            mobile.ready(ready)
            for (bad in listOf("runNonce" to "0".repeat(64), "hostSourceSha" to "2".repeat(40),
                "hostArtifactSha256" to "4".repeat(64), "hostPlatform" to "Jvm", "address" to "127.0.0.1",
                "compiledSourceMatched" to "false", "artifactKind" to "unverified-build")) {
                assertFailsWith<IllegalArgumentException> { mobile.ready(ready + bad) }
            }
        }
    }

    @Test
    fun mobileTelemetryRequiresItsRealCollectorAndRejectsJvmOrSentinelSubstitution() {
        for (platform in listOf("Android", "Ios")) withFixture(platform) { mobile, config, _ ->
            val values = parseMobileRecord(mobileTelemetryRecord(config, 1, 1000, 128,
                RpcDiagnostics(acceptedCalls = 128, completedCalls = 128), RpcPhoneProcessStats(7_000_000, 8192, 12)))
            assertEquals(12, mobile.telemetry(values).liveThreads)
            for (bad in listOf("runNonce" to "0".repeat(64), "jvmThreads" to "1", "nativeThreads" to "0",
                "cpuSource" to "jvm", "cpuNanos" to "1", "clock" to "generator", "queued" to "257",
                "records" to "131073", "sequence" to "3000", "completed" to "-1")) {
                assertFailsWith<IllegalArgumentException> { mobile.telemetry(values + bad) }
            }
            assertFailsWith<IllegalArgumentException> { LabTelemetry.decode(values, config.runLabel) }
        }
    }

    @Test
    fun usbSnapshotsMustAdvanceInsideTheExistingProviderDeadline() = runTest {
        withFixture { mobile, config, root ->
            fun record(sequence: Long) = mobileTelemetryRecord(config, sequence, sequence * 1000, 128,
                RpcDiagnostics(), RpcPhoneProcessStats(0, 8192, 12)).toByteArray(Charsets.US_ASCII)
            val file = root.resolve("host-telemetry.txt")
            LabFiles.write(file, record(1))
            val result = async { withTimeout(500) { awaitLabTelemetry(root, config.runLabel, 1, mobile) } }
            delay(100)
            assertFalse(result.isCompleted)
            LabFiles.write(file, record(2), replace = true)
            assertEquals(2L, result.await().first)
        }
    }
}
