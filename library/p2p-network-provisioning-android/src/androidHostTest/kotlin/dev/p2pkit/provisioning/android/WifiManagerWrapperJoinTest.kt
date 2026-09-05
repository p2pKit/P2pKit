package dev.p2pkit.provisioning.android

import android.net.LinkAddress
import android.net.LinkProperties
import android.net.Network
import android.net.NetworkCapabilities
import android.net.wifi.WifiConfiguration
import android.net.wifi.WifiNetworkSpecifier
import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.provisioning.WifiCredentials
import dev.p2pkit.core.provisioning.WifiPassword
import dev.p2pkit.core.provisioning.WifiSecurityType
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.test.TestScope
import kotlinx.coroutines.test.runTest
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.LooperMode
import org.robolectric.shadows.ShadowNetwork
import org.robolectric.util.ReflectionHelpers
import org.robolectric.util.ReflectionHelpers.ClassParameter
import java.net.InetAddress
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread
import kotlin.test.AfterTest
import kotlin.test.BeforeTest
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNull
import kotlin.test.assertTrue

@RunWith(RobolectricTestRunner::class)
@Config(
    sdk = [29, 30, 35],
    manifest = Config.NONE,
    shadows = [AdapterWifiManagerShadow::class, AdapterConnectivityManagerShadow::class]
)
@LooperMode(LooperMode.Mode.PAUSED)
class WifiManagerWrapperJoinTest {
    private lateinit var fixture: WifiManagerAdapterFixture
    private val credentials = WifiCredentials(
        "synthetic network", WifiPassword("synthetic-passphrase"), WifiSecurityType.WPA2
    )

    @BeforeTest
    fun setUpAdapter() {
        fixture = WifiManagerAdapterFixture()
    }

    @AfterTest
    fun closeAdapterResources() {
        if (::fixture.isInitialized) fixture.close()
    }

    private fun TestScope.begin(credentials: WifiCredentials = this@WifiManagerWrapperJoinTest.credentials) =
        async(start = CoroutineStart.UNDISPATCHED) { fixture.wrapper.joinWifiNetwork(credentials) }

    private suspend fun TestScope.join(network: Network): JoinHandle {
        val pending = begin()
        fixture.connectivity.requests.last().callback.onAvailable(network)
        return assertIs<JoinResult.Joined>(pending.await()).handle.also { fixture.joins += it }
    }

    @Test
    @Suppress("DEPRECATION") // Inspect the actual platform specifier's OS-facing record.
    fun requestsLocalWifiWithoutInternetAndPreservesCredentialSecurity() = runTest {
        for (security in listOf(WifiSecurityType.OPEN, WifiSecurityType.WPA2, WifiSecurityType.WPA3)) {
            val password = if (security == WifiSecurityType.OPEN) null else credentials.password
            val pending = begin(WifiCredentials(credentials.ssid, password, security))
            val request = fixture.connectivity.requests.last()
            assertTrue(request.request.hasTransport(NetworkCapabilities.TRANSPORT_WIFI))
            assertFalse(request.request.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET))
            val capabilities = ReflectionHelpers.getField<NetworkCapabilities>(request.request, "networkCapabilities")
            val specifier = assertIs<WifiNetworkSpecifier>(capabilities.networkSpecifier)
            val config = ReflectionHelpers.getField<WifiConfiguration>(specifier, "wifiConfiguration")
            assertEquals("\"synthetic network\"", config.SSID)
            if (password == null) assertNull(config.preSharedKey)
            else assertEquals("\"synthetic-passphrase\"", config.preSharedKey)
            val keyManagement = when (security) {
                WifiSecurityType.OPEN -> WifiConfiguration.KeyMgmt.NONE
                WifiSecurityType.WPA3 -> WifiConfiguration.KeyMgmt.SAE
                else -> WifiConfiguration.KeyMgmt.WPA_PSK
            }
            assertTrue(config.allowedKeyManagement[keyManagement])
            pending.cancelAndJoin()
            assertEquals(1, fixture.connectivity.unregisterCalls.count { it === request.callback })
        }
        assertTrue(fixture.connectivity.bindings.isEmpty())
    }

    @Test
    fun blankSsidFailsBeforeRequestingOrBinding() = runTest {
        for (ssid in listOf(null, "", "  ")) {
            assertIs<JoinResult.Failed>(
                fixture.wrapper.joinWifiNetwork(WifiCredentials(ssid, null, WifiSecurityType.OPEN))
            )
        }
        assertTrue(fixture.connectivity.requests.isEmpty())
        assertTrue(fixture.connectivity.bindings.isEmpty())
    }

    @Test
    fun successfulJoinCloseIsIdempotentAndLateCallbacksCannotRebind() = runTest {
        val network = ShadowNetwork.newInstance(71)
        val handle = join(network)
        val callback = fixture.connectivity.requests.single().callback
        handle.close()
        handle.close()
        callback.onAvailable(ShadowNetwork.newInstance(72))
        callback.onLost(network)
        callback.onUnavailable()
        assertEquals(listOf(network, null), fixture.connectivity.bindings)
        assertEquals(listOf(callback), fixture.connectivity.unregisterCalls)
        assertTrue(fixture.connectivity.activeCallbacks.isEmpty())
    }

    @Test
    fun cancellationBeforeAvailableUnregistersOnceAndSuppressesLateBinding() = runTest {
        val pending = begin()
        val callback = fixture.connectivity.requests.single().callback
        pending.cancelAndJoin()
        callback.onAvailable(ShadowNetwork.newInstance(73))
        callback.onUnavailable()
        assertEquals(listOf(callback), fixture.connectivity.unregisterCalls)
        assertTrue(fixture.connectivity.bindings.isEmpty())
        assertTrue(fixture.wrapper.closePendingResources().isEmpty())
    }

    @Test
    fun cancellationAfterBindingBeforeResultDispatchReleasesUnclaimedJoin() = runTest {
        val pending = begin()
        val callback = fixture.connectivity.requests.single().callback
        val network = ShadowNetwork.newInstance(74)
        callback.onAvailable(network)
        pending.cancelAndJoin()
        assertTrue(pending.isCancelled)
        assertEquals(listOf(network, null), fixture.connectivity.bindings)
        assertEquals(listOf(callback), fixture.connectivity.unregisterCalls)
        assertTrue(fixture.wrapper.closePendingResources().isEmpty())
    }

    @Test
    fun unavailableBeforeAvailableFailsAndUnregistersWithoutBinding() = runTest {
        val pending = begin()
        val callback = fixture.connectivity.requests.single().callback
        callback.onUnavailable()
        assertIs<JoinResult.Failed>(pending.await())
        callback.onAvailable(ShadowNetwork.newInstance(75))
        assertEquals(listOf(callback), fixture.connectivity.unregisterCalls)
        assertTrue(fixture.connectivity.bindings.isEmpty())
    }

    @Test
    fun replacingNetworkRejectsStaleLossAndCurrentLossReleasesOnce() = runTest {
        val old = ShadowNetwork.newInstance(76)
        val current = ShadowNetwork.newInstance(77)
        val handle = join(old)
        val callback = fixture.connectivity.requests.single().callback
        // Construct an OS-owned record without Android's private
        // InetAddress.parseNumericAddress extension (not present on a host JDK).
        val address = ReflectionHelpers.callConstructor(
            LinkAddress::class.java,
            ClassParameter.from(InetAddress::class.java, InetAddress.getByAddress(byteArrayOf(-64, 0, 2, 77))),
            ClassParameter.from(Int::class.javaPrimitiveType!!, 24)
        )
        val properties = LinkProperties()
        ReflectionHelpers.callInstanceMethod<Boolean>(
            properties, "addLinkAddress", ClassParameter.from(LinkAddress::class.java, address)
        )
        fixture.connectivity.setLinkProperties(current, properties)
        callback.onAvailable(current)
        callback.onLost(old)
        assertEquals(listOf(old, current), fixture.connectivity.bindings)
        assertTrue(fixture.connectivity.unregisterCalls.isEmpty())
        assertTrue(handle.released.replayCache.isEmpty())
        val state = assertIs<NetworkState.ConnectedToWifi>(handle.snapshotNetworkState())
        assertEquals(listOf("192.0.2.77"), state.localIpAddresses)
        callback.onLost(current)
        callback.onLost(current)
        assertEquals(listOf("system released (onLost)"), handle.released.replayCache)
        assertEquals(listOf(old, current, null), fixture.connectivity.bindings)
        assertEquals(listOf(callback), fixture.connectivity.unregisterCalls)
    }

    @Test
    fun secondManagerCannotStealBindingAndCanJoinAfterOwnerCloses() = runTest {
        val network = ShadowNetwork.newInstance(78)
        val handle = join(network)
        val second = WifiManagerWrapperImpl(fixture.application)
        val rejected = async(start = CoroutineStart.UNDISPATCHED) { second.joinWifiNetwork(credentials) }
        val rejectedCallback = fixture.connectivity.requests.last().callback
        rejectedCallback.onAvailable(ShadowNetwork.newInstance(79))
        assertIs<JoinResult.Failed>(rejected.await())
        assertEquals(listOf(network), fixture.connectivity.bindings)
        assertEquals(listOf(rejectedCallback), fixture.connectivity.unregisterCalls)
        handle.close()
        val retry = async(start = CoroutineStart.UNDISPATCHED) { second.joinWifiNetwork(credentials) }
        fixture.connectivity.requests.last().callback.onAvailable(ShadowNetwork.newInstance(80))
        val next = assertIs<JoinResult.Joined>(retry.await()).handle.also { fixture.joins += it }
        next.close()
        assertTrue(second.closePendingResources().isEmpty())
    }

    @Test
    fun rejectedInitialBindReleasesCallbackAndTokenWithoutClearingAnotherNetwork() = runTest {
        fixture.connectivity.bindAccepted = false
        val pending = begin()
        val callback = fixture.connectivity.requests.single().callback
        val network = ShadowNetwork.newInstance(81)
        callback.onAvailable(network)
        assertIs<JoinResult.Failed>(pending.await())
        assertEquals(listOf(network), fixture.connectivity.bindings)
        assertEquals(listOf(callback), fixture.connectivity.unregisterCalls)
        fixture.connectivity.bindAccepted = true
        join(ShadowNetwork.newInstance(82)).close()
    }

    @Test
    fun failedCancellationUnregisterRemainsOwnedUntilCleanupRetry() = runTest {
        val pending = begin()
        val callback = fixture.connectivity.requests.single().callback
        fixture.connectivity.remainingUnregisterFailures = 1
        pending.cancelAndJoin()
        assertEquals(setOf(callback), fixture.connectivity.activeCallbacks)
        assertEquals(listOf(callback), fixture.connectivity.unregisterCalls)
        assertTrue(fixture.wrapper.closePendingResources().isEmpty())
        assertTrue(fixture.connectivity.activeCallbacks.isEmpty())
        assertEquals(listOf(callback, callback), fixture.connectivity.unregisterCalls)
        assertTrue(fixture.wrapper.closePendingResources().isEmpty())
        assertEquals(2, fixture.connectivity.unregisterCalls.size)
    }

    @Test
    fun synchronousPermissionFailureEscapesAndNextRequestCanSucceed() = runTest {
        fixture.connectivity.requestFailure = SecurityException("synthetic permission denial")
        assertFailsWith<SecurityException> { fixture.wrapper.joinWifiNetwork(credentials) }
        assertTrue(fixture.connectivity.activeCallbacks.isEmpty())
        assertTrue(fixture.connectivity.bindings.isEmpty())
        // The platform may throw before registration. Already-unregistered
        // IllegalArgumentException must not become an unretryable cleanup error.
        assertTrue(fixture.wrapper.closePendingResources().isEmpty())
        fixture.connectivity.requestFailure = null
        join(ShadowNetwork.newInstance(83)).close()
    }

    @Test
    fun cancellationDuringInitialBindingCannotDeadlockOrLeaveABinding() = runTest {
        val pending = begin()
        val callback = fixture.connectivity.requests.single().callback
        val network = ShadowNetwork.newInstance(84)
        val entered = CountDownLatch(1)
        val release = CountDownLatch(1)
        val callbackFailure = AtomicReference<Throwable?>()
        val cancellationFailure = AtomicReference<Throwable?>()
        fixture.connectivity.beforeNonNullBind = {
            entered.countDown()
            check(release.await(5, TimeUnit.SECONDS)) { "synthetic bind was not released" }
        }
        val delivering = thread(name = "adapter-bind-callback", isDaemon = true) {
            try {
                callback.onAvailable(network)
            } catch (failure: Throwable) {
                callbackFailure.set(failure)
            }
        }
        var cancelling: Thread? = null
        try {
            assertTrue(entered.await(5, TimeUnit.SECONDS))
            cancelling = thread(name = "adapter-bind-cancel", isDaemon = true) {
                try {
                    pending.cancel()
                } catch (failure: Throwable) {
                    cancellationFailure.set(failure)
                }
            }
            // Positive handshake: cancellation must be waiting for the owned
            // native bind, not merely scheduled at an arbitrary wall-clock delay.
            val deadline = System.nanoTime() + TimeUnit.SECONDS.toNanos(5)
            while (cancelling.isAlive && cancelling.state != Thread.State.BLOCKED && System.nanoTime() < deadline) {
                Thread.yield()
            }
            assertEquals(Thread.State.BLOCKED, cancelling.state)
        } finally {
            release.countDown()
            delivering.join(5_000)
            cancelling?.join(5_000)
            fixture.connectivity.beforeNonNullBind = null
        }
        assertFalse(delivering.isAlive)
        assertFalse(cancelling.isAlive)
        assertNull(callbackFailure.get())
        assertNull(cancellationFailure.get())
        pending.cancelAndJoin()
        assertEquals(listOf(network, null), fixture.connectivity.bindings)
        assertEquals(listOf(callback), fixture.connectivity.unregisterCalls)
        assertTrue(fixture.wrapper.closePendingResources().isEmpty())
    }
}
