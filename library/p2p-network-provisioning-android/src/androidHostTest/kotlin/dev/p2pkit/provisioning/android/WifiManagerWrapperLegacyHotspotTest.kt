package dev.p2pkit.provisioning.android

import android.net.wifi.WifiConfiguration
import android.net.wifi.WifiManager
import dev.p2pkit.core.provisioning.WifiSecurityType
import kotlinx.coroutines.test.runTest
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.LooperMode
import org.robolectric.shadow.api.Shadow
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull

@RunWith(RobolectricTestRunner::class)
@Config(
    sdk = [26, 29],
    manifest = Config.NONE,
    shadows = [
        AdapterWifiManagerShadow::class, AdapterReservationShadow::class, AdapterConnectivityManagerShadow::class
    ]
)
@LooperMode(LooperMode.Mode.PAUSED)
@Suppress("DEPRECATION")
class WifiManagerWrapperLegacyHotspotTest : WifiManagerWrapperHotspotContract() {
    override fun reservation(): WifiManager.LocalOnlyHotspotReservation =
        Shadow.newInstanceOf(WifiManager.LocalOnlyHotspotReservation::class.java).also {
            Shadow.extract<AdapterReservationShadow>(it).configuration = WifiConfiguration().apply {
                SSID = "  \"synthetic network\"  "
                preSharedKey = "  \"synthetic-passphrase\"  "
            }
        }

    @Test
    fun legacyCredentialsStripQuotesAndWhitespace() = runTest {
        val credentials = assertNotNull(start(reservation()).getCredentials())
        assertEquals("synthetic network", credentials.ssid)
        assertEquals("synthetic-passphrase", credentials.password?.reveal())
        assertEquals(WifiSecurityType.WPA2, credentials.securityType)
    }

    @Test
    fun absentOrEmptyLegacyPassphraseMeansOpenNetwork() = runTest {
        for (passphrase in listOf(null, "", "  ", "\"\"")) {
            val reservation = reservation()
            Shadow.extract<AdapterReservationShadow>(reservation).configuration!!.preSharedKey = passphrase
            val credentials = assertNotNull(start(reservation).getCredentials())
            assertNull(credentials.password)
            assertEquals(WifiSecurityType.OPEN, credentials.securityType)
        }
    }

    @Test
    fun missingConfigurationAndEmptyLegacySsidAreRedacted() = runTest {
        val missing = reservation()
        Shadow.extract<AdapterReservationShadow>(missing).configuration = null
        assertNull(start(missing).getCredentials())
        for (ssid in listOf(null, "", "  ", "\"\"")) {
            val reservation = reservation()
            Shadow.extract<AdapterReservationShadow>(reservation).configuration!!.SSID = ssid
            assertNull(start(reservation).getCredentials())
        }
    }
}
