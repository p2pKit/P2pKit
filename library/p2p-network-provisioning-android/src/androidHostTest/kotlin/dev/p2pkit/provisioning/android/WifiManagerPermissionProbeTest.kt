package dev.p2pkit.provisioning.android

import android.Manifest
import android.content.Context
import android.location.LocationManager
import android.os.Build
import android.provider.Settings
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import kotlin.test.Test
import kotlin.test.assertEquals

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [26, 35], manifest = Config.NONE)
class WifiManagerPermissionProbeTest {
    @Test
    @Suppress("DEPRECATION") // The production API-26 branch reads LOCATION_MODE.
    fun postFailureProbeDistinguishesRevokedGrantFromSystemLocationToggle() {
        val application = RuntimeEnvironment.getApplication()
        application.applicationInfo.targetSdkVersion = Build.VERSION.SDK_INT
        val wrapper = WifiManagerWrapperImpl(application)
        val permission = if (Build.VERSION.SDK_INT >= 33) {
            Manifest.permission.NEARBY_WIFI_DEVICES
        } else {
            Manifest.permission.ACCESS_FINE_LOCATION
        }
        shadowOf(application).denyPermissions(permission)
        assertEquals(false, wrapper.permissionState().runtimePermissionGranted)
        shadowOf(application).grantPermissions(permission)
        for (enabled in listOf(false, true)) {
            if (Build.VERSION.SDK_INT >= 28) {
                shadowOf(application.getSystemService(Context.LOCATION_SERVICE) as LocationManager)
                    .setLocationEnabled(enabled)
            } else {
                Settings.Secure.putInt(
                    application.contentResolver,
                    Settings.Secure.LOCATION_MODE,
                    if (enabled) Settings.Secure.LOCATION_MODE_HIGH_ACCURACY else Settings.Secure.LOCATION_MODE_OFF
                )
            }
            assertEquals(
                ProvisioningPermissionState(runtimePermissionGranted = true, locationEnabled = enabled),
                wrapper.permissionState()
            )
        }
    }
}
