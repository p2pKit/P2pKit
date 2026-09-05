package dev.p2pkit.provisioning.android

import android.net.wifi.WifiManager
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runTest
import org.robolectric.shadow.api.Shadow
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertTrue

/** Same real-adapter lifecycle assertions on both credential API branches. */
abstract class WifiManagerWrapperHotspotContract {
    internal lateinit var fixture: WifiManagerAdapterFixture

    @BeforeTest
    fun setUpAdapter() {
        fixture = WifiManagerAdapterFixture()
    }

    @AfterTest
    fun closeAdapterResources() {
        if (::fixture.isInitialized) fixture.close()
    }

    protected abstract fun reservation(): WifiManager.LocalOnlyHotspotReservation

    internal suspend fun TestScope.start(reservation: WifiManager.LocalOnlyHotspotReservation): HotspotHandle {
        val pending = async(start = CoroutineStart.UNDISPATCHED) { fixture.wrapper.startLocalOnlyHotspot() }
        fixture.wifi.requests.last().deliver { onStarted(reservation) }
        return assertIs<HotspotStartResult.Started>(pending.await()).handle.also { fixture.hotspots += it }
    }

    @Test
    fun usesMainLooperAndClosesSuccessfulReservationExactlyOnce() = runTest {
        val reservation = reservation()
        val handle = start(reservation)
        handle.close()
        handle.close()
        assertEquals(1, Shadow.extract<AdapterReservationShadow>(reservation).closeCalls)
        assertTrue(fixture.wrapper.closePendingResources().isEmpty())
    }

    @Test
    fun cancellationBeforeStartedClosesLateReservationAndKeepsPendingRequestGate() = runTest {
        val pending = async(start = CoroutineStart.UNDISPATCHED) { fixture.wrapper.startLocalOnlyHotspot() }
        pending.cancelAndJoin()
        assertIs<HotspotStartResult.CleanupPending>(fixture.wrapper.startLocalOnlyHotspot())
        assertEquals(1, fixture.wifi.requests.size)
        val reservation = reservation()
        fixture.wifi.requests.single().deliver { onStarted(reservation) }
        assertEquals(1, Shadow.extract<AdapterReservationShadow>(reservation).closeCalls)
        assertTrue(fixture.wrapper.closePendingResources().isEmpty())

        val retry = async(start = CoroutineStart.UNDISPATCHED) { fixture.wrapper.startLocalOnlyHotspot() }
        assertEquals(2, fixture.wifi.requests.size)
        fixture.wifi.requests.last().deliver { onFailed(WifiManager.LocalOnlyHotspotCallback.ERROR_NO_CHANNEL) }
        assertEquals(
            WifiManager.LocalOnlyHotspotCallback.ERROR_NO_CHANNEL,
            assertIs<HotspotStartResult.Failed>(retry.await()).reasonCode
        )
    }

    @Test
    fun cancellationAfterStartedBeforeResultDispatchClosesUnclaimedReservation() = runTest {
        val pending = async(start = CoroutineStart.UNDISPATCHED) { fixture.wrapper.startLocalOnlyHotspot() }
        val reservation = reservation()
        fixture.wifi.requests.single().deliver { onStarted(reservation) }
        // The callback resumed the continuation; StandardTestDispatcher has
        // not dispatched its result yet. Prompt cancellation must retain no handle.
        pending.cancelAndJoin()
        assertTrue(pending.isCancelled)
        assertEquals(1, Shadow.extract<AdapterReservationShadow>(reservation).closeCalls)
        assertTrue(fixture.wrapper.closePendingResources().isEmpty())
    }

    @Test
    fun stopBeforeStartedFailsAndReleasesRequestGate() = runTest {
        val pending = async(start = CoroutineStart.UNDISPATCHED) { fixture.wrapper.startLocalOnlyHotspot() }
        fixture.wifi.requests.single().deliver { onStopped() }
        assertEquals(-1, assertIs<HotspotStartResult.Failed>(pending.await()).reasonCode)
        assertTrue(fixture.wrapper.closePendingResources().isEmpty())
        val handle = start(reservation())
        assertEquals(2, fixture.wifi.requests.size)
        handle.close()
    }

    @Test
    fun systemStopIsVisibleToALateSubscriber() = runTest {
        val handle = start(reservation())
        fixture.wifi.requests.single().deliver { onStopped() }
        assertEquals(HotspotStopReason("system stopped"), handle.stopped.first())
    }

    @Test
    fun nativePermissionFailureEscapesAndDoesNotWedgeNextStart() = runTest {
        fixture.wifi.startFailure = SecurityException("synthetic permission denial")
        assertFailsWith<SecurityException> { fixture.wrapper.startLocalOnlyHotspot() }
        assertTrue(fixture.wrapper.closePendingResources().isEmpty())
        fixture.wifi.startFailure = null
        start(reservation()).close()
        assertEquals(1, fixture.wifi.requests.size)
    }

    @Test
    fun failedLateReservationCloseIsRetainedAndRetried() = runTest {
        val pending = async(start = CoroutineStart.UNDISPATCHED) { fixture.wrapper.startLocalOnlyHotspot() }
        pending.cancelAndJoin()
        val reservation = reservation()
        val shadow = Shadow.extract<AdapterReservationShadow>(reservation)
        shadow.remainingCloseFailures = 1
        fixture.wifi.requests.single().deliver { onStarted(reservation) }
        assertEquals(1, shadow.closeCalls)
        assertTrue(fixture.wrapper.closePendingResources().isEmpty())
        assertEquals(2, shadow.closeCalls)
        assertTrue(fixture.wrapper.closePendingResources().isEmpty())
        assertEquals(2, shadow.closeCalls)
    }
}
