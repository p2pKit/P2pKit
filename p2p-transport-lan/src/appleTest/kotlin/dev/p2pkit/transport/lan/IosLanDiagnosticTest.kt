package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlin.test.Ignore
import kotlin.test.Test

/**
 * Diagnostic-only test: holds a kit alive long enough that external tools
 * (`dns-sd`, the JVM CLI, an Android device) can observe its Bonjour
 * advertisement on the host network.
 *
 * Marked `@Ignore` so it doesn't slow the normal `iosSimulatorArm64Test`
 * cycle. Kotlin/Native test binaries offer no flag to force-run an
 * `@Ignore`d test (Gradle's `--tests` filter cannot override the
 * annotation), so to run the diagnostic, temporarily remove the `@Ignore`
 * line and run:
 *
 *     ./gradlew :p2p-transport-lan:iosSimulatorArm64Test \
 *         --tests 'dev.p2pkit.transport.lan.IosLanDiagnosticTest'
 *
 * Restore the `@Ignore` before committing. (AUDIT-2026-06: an earlier
 * version of this comment suggested `-Dkotlin.native.tests.ignored=false`,
 * which is consumed nowhere and cannot reach the simulator-hosted binary.)
 */
@Suppress("DEPRECATION")
class IosLanDiagnosticTest {

    @Test
    @Ignore
    fun advertiseForSixtySecondsForInteropCapture() {
        runBlocking {
            // Use the SAME default appId the JVM CLI uses so they discover
            // each other without flag changes:
            //     ./p2p-sample-desktop ... → appId = "p2pkit-desktop-sample"
            val appIdValue = "p2pkit-desktop-sample"
            val peerIdKey = "dev.p2pkit.peerId.$appIdValue"
            val peerIdV2Key = "dev.p2pkit.peerId.v2.$appIdValue"
            val defaultsLease = AppleGlobalStateTestGuard.acquire(
                keys = arrayOf(peerIdKey, peerIdV2Key)
            )
            var kit: P2pKit? = null
            try {
                defaultsLease.remove(peerIdKey)
                defaultsLease.remove(peerIdV2Key)
                defaultsLease.synchronize()

                kit = P2pKit.create {
                    appId = AppId(appIdValue)
                    deviceName = "iOSDiagnostic"
                    security { mode = dev.p2pkit.core.SecurityMode.NoneForMvp }
                    transports { lan() }
                }
                kit.startAdvertising()
                kit.startDiscovery()
                println("DIAG: kit started, advertising for 60 s")
                println("DIAG: localPeerId=${kit.localPeerId.value}")
                println("DIAG: appId=${kit.appId.value}")
                println("DIAG: deviceName=${kit.localDeviceName}")
                repeat(12) {
                    delay(5_000)
                    val peers = kit.peers.value
                    println("DIAG: t=${(it + 1) * 5}s peers=${peers.size}: ${peers.map { p -> "${p.name}(${p.id.value.take(8)})" }}")
                }
            } finally {
                try {
                    kit?.let { created ->
                        created.stop()
                        println("DIAG: kit stopped")
                    }
                } finally {
                    defaultsLease.close()
                }
            }
        }
    }
}
