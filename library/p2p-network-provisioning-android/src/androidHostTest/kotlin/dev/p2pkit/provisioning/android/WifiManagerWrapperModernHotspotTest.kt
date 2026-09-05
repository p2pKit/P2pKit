package dev.p2pkit.provisioning.android

import android.net.wifi.SoftApConfiguration
import android.net.wifi.WifiManager
import dev.p2pkit.core.provisioning.WifiSecurityType
import kotlinx.coroutines.test.runTest
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.Implementation
import org.robolectric.annotation.Implements
import org.robolectric.annotation.LooperMode
import org.robolectric.shadow.api.Shadow
import org.robolectric.util.ReflectionHelpers
import org.robolectric.util.ReflectionHelpers.ClassParameter
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertNotNull
import kotlin.test.assertNull

@Implements(WifiManager.LocalOnlyHotspotReservation::class, minSdk = 30)
class AdapterModernReservationShadow : AdapterReservationShadow() {
    lateinit var softAp: SoftApConfiguration

    @Implementation(minSdk = 30)
    protected fun getSoftApConfiguration(): SoftApConfiguration = softAp
}

@RunWith(RobolectricTestRunner::class)
@Config(
    sdk = [30, 35],
    manifest = Config.NONE,
    shadows = [
        AdapterWifiManagerShadow::class, AdapterModernReservationShadow::class, AdapterConnectivityManagerShadow::class
    ]
)
@LooperMode(LooperMode.Mode.PAUSED)
class WifiManagerWrapperModernHotspotTest : WifiManagerWrapperHotspotContract() {
    private fun configuration(ssid: String?, passphrase: String?, security: Int): SoftApConfiguration {
        val builder = SoftApConfiguration.Builder()
        if (ssid != null) {
            // This system API constructs the reservation's OS-owned record;
            // it is intentionally absent from the public compileSdk stubs.
            ReflectionHelpers.callInstanceMethod<SoftApConfiguration.Builder>(
                builder, "setSsid", ClassParameter.from(String::class.java, ssid)
            )
        }
        ReflectionHelpers.callInstanceMethod<SoftApConfiguration.Builder>(
            builder, "setPassphrase", ClassParameter.from(String::class.java, passphrase),
            ClassParameter.from(Int::class.javaPrimitiveType!!, security)
        )
        return builder.build()
    }

    override fun reservation(): WifiManager.LocalOnlyHotspotReservation =
        Shadow.newInstanceOf(WifiManager.LocalOnlyHotspotReservation::class.java).also {
            Shadow.extract<AdapterModernReservationShadow>(it).softAp = configuration(
                "synthetic network", "synthetic-passphrase", SoftApConfiguration.SECURITY_TYPE_WPA2_PSK
            )
        }

    @Test
    fun modernCredentialsMapEverySupportedSecurityType() = runTest {
        val securityTypes = listOf(
            SoftApConfiguration.SECURITY_TYPE_OPEN to WifiSecurityType.OPEN,
            SoftApConfiguration.SECURITY_TYPE_WPA2_PSK to WifiSecurityType.WPA2,
            SoftApConfiguration.SECURITY_TYPE_WPA3_SAE_TRANSITION to WifiSecurityType.WPA3,
            SoftApConfiguration.SECURITY_TYPE_WPA3_SAE to WifiSecurityType.WPA3
        )
        for ((native, expected) in securityTypes) {
            val passphrase = if (expected == WifiSecurityType.OPEN) null else "synthetic-passphrase"
            val reservation = reservation()
            Shadow.extract<AdapterModernReservationShadow>(reservation).softAp =
                configuration("synthetic network", passphrase, native)
            val credentials = assertNotNull(start(reservation).getCredentials())
            assertEquals("synthetic network", credentials.ssid)
            assertEquals(passphrase, credentials.password?.reveal())
            assertEquals(expected, credentials.securityType)
        }
    }

    @Test
    fun missingModernSsidIsRedactedAndUnknownSecurityIsNotInvented() = runTest {
        val reservation = reservation()
        val shadow = Shadow.extract<AdapterModernReservationShadow>(reservation)
        // Synthetic redacted/future-OS records bypass builder validation only;
        // getters and the production credential mapping still execute normally.
        shadow.softAp = configuration(null, null, SoftApConfiguration.SECURITY_TYPE_OPEN)
        assertNull(start(reservation).getCredentials())
        val unknown = reservation()
        ReflectionHelpers.setField(Shadow.extract<AdapterModernReservationShadow>(unknown).softAp, "mSecurityType", 99)
        assertEquals(WifiSecurityType.UNKNOWN, assertNotNull(start(unknown).getCredentials()).securityType)
    }
}
