package dev.p2pkit.sample.android.rpclab

import android.net.ConnectivityManager
import android.net.LinkProperties
import android.os.Looper
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNotSame
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.Shadows.shadowOf
import org.robolectric.annotation.Config
import org.robolectric.shadows.ShadowNetwork

/** Actual public callback registration/retirement under the locked host SDK, not physical Wi-Fi evidence. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [35], manifest = Config.NONE)
class AndroidRpcLabWifiObserverTest {
    @Test
    fun stopRetiresOnlyOurCallbackAndRejectsQueuedOrLateUpdates() {
        val context = RuntimeEnvironment.getApplication()
        val manager = context.getSystemService(ConnectivityManager::class.java)
        val shadow = shadowOf(manager)
        shadow.setActiveNetworkInfo(null)
        val unrelated = object : ConnectivityManager.NetworkCallback() {}
        manager.registerDefaultNetworkCallback(unrelated)
        val before = shadow.networkCallbacks.toSet()
        val observer = AndroidRpcLabWifiObserver(context)
        val received = mutableListOf<RpcLabWifiObservation>()
        try {
            observer.start(received::add)
            val ours = (shadow.networkCallbacks - before).single()
            assertEquals(RpcLabWifiIssue.NoDefaultNetwork,
                assertIs<RpcLabWifiObservation.Unavailable>(received.single()).issue)
            ours.onAvailable(ShadowNetwork.newInstance(101))
            observer.stop()
            shadowOf(Looper.getMainLooper()).idle()
            assertEquals(1, received.size)
            ours.onLost(ShadowNetwork.newInstance(101))
            shadowOf(Looper.getMainLooper()).idle()
            assertEquals(1, received.size)
            assertEquals(before, shadow.networkCallbacks.toSet())
            observer.stop()
            assertEquals(before, shadow.networkCallbacks.toSet())
        } finally {
            observer.stop()
            manager.unregisterNetworkCallback(unrelated)
        }
    }

    @Test
    fun refreshRegistersOneNewGenerationWithoutLeakingTheOldObserver() {
        val context = RuntimeEnvironment.getApplication()
        val manager = context.getSystemService(ConnectivityManager::class.java)
        val shadow = shadowOf(manager)
        shadow.setActiveNetworkInfo(null)
        val before = shadow.networkCallbacks.toSet()
        val observer = AndroidRpcLabWifiObserver(context)
        val oldResults = mutableListOf<RpcLabWifiObservation>()
        val newResults = mutableListOf<RpcLabWifiObservation>()
        try {
            observer.start(oldResults::add)
            val old = (shadow.networkCallbacks - before).single()
            observer.start(newResults::add)
            val fresh = (shadow.networkCallbacks - before).single()
            assertNotSame(old, fresh)
            old.onLinkPropertiesChanged(ShadowNetwork.newInstance(101), LinkProperties())
            fresh.onAvailable(ShadowNetwork.newInstance(102))
            shadowOf(Looper.getMainLooper()).idle()
            assertEquals(1, oldResults.size)
            assertEquals(2, newResults.size)
        } finally { observer.stop() }
        assertEquals(before, shadow.networkCallbacks.toSet())
    }
}
