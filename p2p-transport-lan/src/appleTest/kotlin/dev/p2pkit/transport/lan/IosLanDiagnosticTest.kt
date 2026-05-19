package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.P2pKit
import kotlinx.coroutines.delay
import kotlinx.coroutines.runBlocking
import kotlin.test.Ignore
import kotlin.test.Test
import platform.Foundation.NSUserDefaults

/**
 * Diagnostic-only test: holds a kit alive long enough that external tools
 * (`dns-sd`, the JVM CLI, an Android device) can observe its Bonjour
 * advertisement on the host network.
 *
 * Marked `@Ignore` so it doesn't slow the normal `iosSimulatorArm64Test`
 * cycle. Run explicitly during cross-platform interop validation via:
 *
 *     ./gradlew :p2p-transport-lan:iosSimulatorArm64Test \
 *         --tests 'dev.p2pkit.transport.lan.IosLanDiagnosticTest' \
 *         -Pkotlin.tests.individualTaskReports=false \
 *         -Dkotlin.native.tests.ignored=false
 *
 * (Or temporarily remove the `@Ignore` for the duration of the capture.)
 */
class IosLanDiagnosticTest {

    @Test
    @Ignore
    fun advertiseForSixtySecondsForInteropCapture() {
        runBlocking {
            // Use the SAME default appId the JVM CLI uses so they discover
            // each other without flag changes:
            //     ./p2p-sample-desktop ... → appId = "p2pkit-desktop-sample"
            val appIdValue = "p2pkit-desktop-sample"
            NSUserDefaults.standardUserDefaults.removeObjectForKey("dev.p2pkit.peerId.$appIdValue")

            val kit = P2pKit.create {
                appId = AppId(appIdValue)
                deviceName = "iOSDiagnostic"
                transports { lan() }
            }
            try {
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
                kit.stop()
                println("DIAG: kit stopped")
                NSUserDefaults.standardUserDefaults.removeObjectForKey("dev.p2pkit.peerId.$appIdValue")
            }
        }
    }
}
