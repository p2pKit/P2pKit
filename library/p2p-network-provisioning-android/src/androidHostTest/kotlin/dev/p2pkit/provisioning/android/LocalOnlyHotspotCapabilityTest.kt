package dev.p2pkit.provisioning.android

import android.content.pm.PackageManager
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertTrue

class LocalOnlyHotspotCapabilityTest {

    @Test
    fun supportRequiresApi26ServiceAndWifiHardware() {
        for (deviceSdk in listOf(24, 25, 26, 29, 32, 33, 36)) {
            for (hasWifiManager in listOf(false, true)) {
                for (hasWifiHardware in listOf(false, true)) {
                    val queries = mutableListOf<String>()
                    val supported = supportsLocalOnlyHotspot(deviceSdk, hasWifiManager) { feature ->
                        queries += feature
                        hasWifiHardware
                    }
                    val context = "API $deviceSdk, WifiManager=$hasWifiManager, FEATURE_WIFI=$hasWifiHardware"
                    assertEquals(deviceSdk >= 26 && hasWifiManager && hasWifiHardware, supported, context)
                    assertEquals(
                        if (deviceSdk >= 26 && hasWifiManager) listOf(PackageManager.FEATURE_WIFI) else emptyList(),
                        queries,
                        context
                    )
                }
            }
        }
    }

    @Test
    fun supportedHardwareNeedsNoTransientRadioOrPermissionSignal() {
        // The production policy deliberately has no radio-state or permission
        // input. This host test is not an execution of Android's radio APIs.
        val queries = mutableListOf<String>()
        assertTrue(
            supportsLocalOnlyHotspot(deviceSdk = 36, hasWifiManager = true) { feature ->
                queries += feature
                assertEquals(PackageManager.FEATURE_WIFI, feature)
                true
            }
        )
        assertEquals(listOf(PackageManager.FEATURE_WIFI), queries)
    }
}
