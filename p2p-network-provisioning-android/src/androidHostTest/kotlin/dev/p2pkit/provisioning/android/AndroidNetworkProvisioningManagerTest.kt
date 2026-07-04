@file:OptIn(dev.p2pkit.core.ExperimentalP2pApi::class)

package dev.p2pkit.provisioning.android

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.NetworkProvisioningError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.core.provisioning.LocalNetworkConfig
import dev.p2pkit.core.provisioning.LocalNetworkResult
import dev.p2pkit.core.provisioning.ManualPeerRegistrar
import dev.p2pkit.core.provisioning.NetworkProvisioningConfig
import dev.p2pkit.core.provisioning.NetworkProvisioningEvent
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.core.provisioning.ProvisioningContext
import dev.p2pkit.core.provisioning.WifiCredentials
import dev.p2pkit.core.provisioning.WifiPassword
import dev.p2pkit.core.provisioning.WifiSecurityType
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.filterIsInstance
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class AndroidNetworkProvisioningManagerTest {

    private val testCreds = WifiCredentials(
        ssid = "AndroidShare_TEST",
        password = WifiPassword("hunter2-test"),
        securityType = WifiSecurityType.WPA2
    )

    private fun ctx(
        lanTcpPort: Int? = 42_000,
        registrar: ManualPeerRegistrar = RecordingRegistrar(),
        parentJob: Job? = null
    ): ProvisioningContext = ProvisioningContext(
        appId = AppId("provisioning-android-test"),
        localPeerId = PeerId("local-id"),
        localDeviceName = "Pixel",
        config = NetworkProvisioningConfig(enableLocalHotspot = true),
        logger = P2pLogger.NoOp,
        lanTcpPort = { lanTcpPort },
        manualPeerRegistrar = registrar,
        parentJob = parentJob
    )

    @Test
    fun startReturnsFailedPermissionMissingWhenWrapperThrowsSecurityException() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(behavior = FakeWifiManagerWrapper.Behavior.ThrowSecurity)
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            val result = mgr.startLocalNetwork(LocalNetworkConfig())
            val failed = assertIs<LocalNetworkResult.Failed>(result)
            val err = assertIs<NetworkProvisioningError.PermissionMissingForProvisioning>(failed.error)
            assertTrue(err.permissions.contains(dev.p2pkit.core.permission.P2pPermission.NearbyWifiDevices))
        } finally {
            mgr.close()
        }
    }

    @Test
    fun locationModeOffSecurityExceptionMapsToLocationPermissionMissing() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.ThrowSecurityWithMessage(
                message = "Location mode is not enabled."
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            val result = mgr.startLocalNetwork(LocalNetworkConfig())
            val failed = assertIs<LocalNetworkResult.Failed>(result)
            val err = assertIs<NetworkProvisioningError.PermissionMissingForProvisioning>(failed.error)
            assertTrue(
                err.permissions.contains(dev.p2pkit.core.permission.P2pPermission.Location),
                "Location-mode-off SecurityException must surface as Location permission missing, " +
                    "got ${err.permissions}"
            )
        } finally {
            mgr.close()
        }
    }

    @Test
    fun startReturnsFailedWhenWrapperReportsHotspotStartFailure() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(behavior = FakeWifiManagerWrapper.Behavior.FailWithReason(reasonCode = 2))
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            val result = mgr.startLocalNetwork(LocalNetworkConfig())
            val failed = assertIs<LocalNetworkResult.Failed>(result)
            assertIs<NetworkProvisioningError.HotspotStopped>(failed.error)
        } finally {
            mgr.close()
        }
    }

    @Test
    fun startReturnsStartedWhenCredentialsAreAvailable() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.Start(
                credentials = testCreds,
                apHosts = listOf("192.168.43.1")
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            val result = mgr.startLocalNetwork(LocalNetworkConfig())
            val started = assertIs<LocalNetworkResult.Started>(result)
            assertEquals("AndroidShare_TEST", started.credentials.ssid)
            assertNotNull(started.manualConnectionInfo)
            assertEquals(42_000, started.manualConnectionInfo!!.port)
            assertTrue(started.manualConnectionInfo!!.hostAddresses.contains("192.168.43.1"))
            assertEquals(NetworkProvisioningState.LocalNetworkRunning, mgr.state.value)
        } finally {
            mgr.close()
        }
    }

    @Test
    fun startReturnsStartedWithoutCredentialsWhenOsRedactsThem() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.Start(
                credentials = null,
                apHosts = listOf("192.168.43.1")
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            val result = mgr.startLocalNetwork(LocalNetworkConfig())
            val started = assertIs<LocalNetworkResult.StartedWithoutCredentials>(result)
            assertTrue(started.manualConnectionInfo.hostAddresses.contains("192.168.43.1"))
        } finally {
            mgr.close()
        }
    }

    @Test
    fun stopLocalNetworkClosesTheHandleAndResetsState() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.Start(
                credentials = testCreds,
                apHosts = listOf("192.168.43.1")
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            mgr.startLocalNetwork(LocalNetworkConfig())
            assertTrue(wifi.lastHandle?.isClosed == false)
            mgr.stopLocalNetwork()
            assertTrue(wifi.lastHandle?.isClosed == true)
            assertEquals(NetworkProvisioningState.Idle, mgr.state.value)
        } finally {
            mgr.close()
        }
    }

    @Test
    fun systemInitiatedStopEmitsFailedEventAndClearsHandle() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.Start(
                credentials = testCreds,
                apHosts = listOf("192.168.43.1")
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            // Subscribe BEFORE triggering the system stop (events is replay=0).
            val failedEventDeferred = async {
                mgr.events.filterIsInstance<NetworkProvisioningEvent.Failed>().first()
            }
            mgr.startLocalNetwork(LocalNetworkConfig())
            // Give the subscriber a beat to attach (the SharedFlow's onSubscription
            // would be cleaner, but a small delay is fine for a unit test).
            delay(50)
            wifi.lastHandle?.simulateSystemStop("OEM battery policy")
            val event = withTimeout(2_000) { failedEventDeferred.await() }
            assertIs<NetworkProvisioningError.HotspotStopped>(event.error)
        } finally {
            mgr.close()
        }
    }

    // --- join paths (v0.2.1 task 12) -----------------------------------------

    @Test
    fun joinSuccessReturnsJoinedWithNetworkStateAndEmitsNetworkJoinedEvent() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.JoinSucceeds(
                networkState = dev.p2pkit.core.provisioning.NetworkState.ConnectedToWifi(
                    ssid = null,
                    localIpAddresses = listOf("192.168.43.55")
                )
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            val joinedEventDeferred = async {
                mgr.events.filterIsInstance<NetworkProvisioningEvent.NetworkJoined>().first()
            }
            // Subscriber attached.
            delay(50)
            val result = mgr.joinLocalNetwork(testCreds)
            val joined = assertIs<JoinNetworkResult.Joined>(result)
            assertEquals(NetworkProvisioningState.JoinedNetwork, mgr.state.value)
            assertIs<dev.p2pkit.core.provisioning.NetworkState.ConnectedToWifi>(joined.networkState)
            withTimeout(2_000) { joinedEventDeferred.await() }
        } finally {
            mgr.close()
        }
    }

    @Test
    fun joinFailureFromWrapperReturnsJoinFailed() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.JoinFails(reason = "user declined")
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            val result = mgr.joinLocalNetwork(testCreds)
            val failed = assertIs<JoinNetworkResult.Failed>(result)
            val err = assertIs<NetworkProvisioningError.JoinFailed>(failed.error)
            assertTrue(err.reason.contains("user declined"))
        } finally {
            mgr.close()
        }
    }

    @Test
    fun joinSecurityExceptionMapsToPermissionMissing() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.JoinThrowsSecurity(
                message = "Missing NEARBY_WIFI_DEVICES"
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            val result = mgr.joinLocalNetwork(testCreds)
            val failed = assertIs<JoinNetworkResult.Failed>(result)
            val err = assertIs<NetworkProvisioningError.PermissionMissingForProvisioning>(failed.error)
            assertTrue(err.permissions.contains(dev.p2pkit.core.permission.P2pPermission.NearbyWifiDevices))
        } finally {
            mgr.close()
        }
    }

    @Test
    fun joinLocationModeOffMapsToLocationPermissionMissing() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.JoinThrowsSecurity(
                message = "Location mode is not enabled."
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            val result = mgr.joinLocalNetwork(testCreds)
            val failed = assertIs<JoinNetworkResult.Failed>(result)
            val err = assertIs<NetworkProvisioningError.PermissionMissingForProvisioning>(failed.error)
            assertTrue(err.permissions.contains(dev.p2pkit.core.permission.P2pPermission.Location))
        } finally {
            mgr.close()
        }
    }

    @Test
    fun secondJoinWhileFirstActiveReturnsJoinFailed() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.JoinSucceeds(
                networkState = dev.p2pkit.core.provisioning.NetworkState.ConnectedToWifi(
                    ssid = null,
                    localIpAddresses = listOf("192.168.43.55")
                )
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            mgr.joinLocalNetwork(testCreds)
            val result = mgr.joinLocalNetwork(testCreds)
            val failed = assertIs<JoinNetworkResult.Failed>(result)
            val err = assertIs<NetworkProvisioningError.JoinFailed>(failed.error)
            // AUDIT-2026-07 (PRM-16, decision #8c): the refusal names the
            // actual state — an active joined network — not "in progress".
            assertTrue(err.reason.contains("already active"))
        } finally {
            mgr.close()
        }
    }

    @Test
    fun systemInitiatedJoinReleaseEmitsFailedEventAndClearsHandle() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.JoinSucceeds(
                networkState = dev.p2pkit.core.provisioning.NetworkState.ConnectedToWifi(
                    ssid = null,
                    localIpAddresses = listOf("192.168.43.55")
                )
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            val failedEventDeferred = async {
                mgr.events.filterIsInstance<NetworkProvisioningEvent.Failed>().first()
            }
            mgr.joinLocalNetwork(testCreds)
            delay(50)
            wifi.lastJoinHandle?.simulateRelease("MIUI battery policy")
            val ev = withTimeout(2_000) { failedEventDeferred.await() }
            val err = assertIs<NetworkProvisioningError.JoinFailed>(ev.error)
            assertTrue(err.reason.contains("MIUI battery policy"))
            // 2026-07 review P1-28 (A09 §3 r3): the release handler must
            // close() the JoinHandle before dropping it — close() is the only
            // path that clears the process-network binding and unregisters
            // the NetworkCallback (close-before-drop, AUDIT-2026-06 fix).
            assertTrue(
                wifi.lastJoinHandle?.isClosed == true,
                "System-initiated join release must close the JoinHandle"
            )
            assertIs<NetworkProvisioningState.Failed>(mgr.state.value)
            // The handle slot is cleared: a follow-up join must not be
            // rejected as "already active".
            assertIs<JoinNetworkResult.Joined>(mgr.joinLocalNetwork(testCreds))
        } finally {
            mgr.close()
        }
    }

    // ---- parent-job teardown path (2026-07 review P1-27, PRM-10, A09 §3 r2) ----
    // Production tears the manager down via P2pKit.stop() cancelling
    // ProvisioningContext.parentJob — the init-block invokeOnCompletion — not
    // via an explicit close() call. These tests exercise that path directly.

    @Test
    fun parentJobCancellationClosesHotspotReservation() = runBlocking<Unit> {
        val parentJob = Job()
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.Start(
                credentials = testCreds,
                apHosts = listOf("192.168.43.1")
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(parentJob = parentJob), wifi)
        try {
            mgr.startLocalNetwork(LocalNetworkConfig())
            assertTrue(wifi.lastHandle?.isClosed == false, "Reservation must be open while running")

            parentJob.cancel()
            parentJob.join() // parent completes only after the manager scope (its child) completed

            assertTrue(
                wifi.lastHandle?.isClosed == true,
                "Kit-stop path (parent-job cancellation) must close the hotspot reservation"
            )
        } finally {
            mgr.close()
        }
    }

    @Test
    fun parentJobCancellationClosesJoinBinding() = runBlocking<Unit> {
        val parentJob = Job()
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.JoinSucceeds(
                networkState = dev.p2pkit.core.provisioning.NetworkState.ConnectedToWifi(
                    ssid = null,
                    localIpAddresses = listOf("192.168.43.55")
                )
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(parentJob = parentJob), wifi)
        try {
            assertIs<JoinNetworkResult.Joined>(mgr.joinLocalNetwork(testCreds))
            assertTrue(wifi.lastJoinHandle?.isClosed == false, "Join binding must be open while joined")

            parentJob.cancel()
            parentJob.join()

            assertTrue(
                wifi.lastJoinHandle?.isClosed == true,
                "Kit-stop path (parent-job cancellation) must close the join binding"
            )
        } finally {
            mgr.close()
        }
    }

    /**
     * Divergence note (2026-07 review P1-27): the coverage plan expects a
     * start attempted after the parent job is cancelled to be refused. The
     * current implementation does not consult scope liveness on the start
     * path: the start is accepted and returns Started, and because the
     * scope's completion handler has already fired, the new reservation is
     * outside the automatic parent-job cleanup — only an explicit close()
     * releases it. This test pins the CURRENT behavior so a future refusal
     * guard is added deliberately (with this test updated), not by accident.
     */
    @Test
    fun startAfterParentJobCancellationIsCurrentlyAcceptedNotRefused() = runBlocking<Unit> {
        val parentJob = Job()
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.Start(
                credentials = testCreds,
                apHosts = listOf("192.168.43.1")
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(parentJob = parentJob), wifi)
        try {
            parentJob.cancel()
            parentJob.join()

            val result = mgr.startLocalNetwork(LocalNetworkConfig())

            // Pins the current (divergent) behavior: accepted, not refused.
            assertIs<LocalNetworkResult.Started>(result)
            // The post-cancellation reservation is not covered by the
            // parent-job completion handler (it already ran).
            assertTrue(wifi.lastHandle?.isClosed == false)
        } finally {
            mgr.close()
            // Explicit close() remains the only release path for it.
            assertTrue(
                wifi.lastHandle?.isClosed == true,
                "Explicit close() must release the post-cancellation reservation"
            )
        }
    }

    @Test
    fun getManualConnectionInfoReturnsNullWithoutLanPort() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(behavior = FakeWifiManagerWrapper.Behavior.ThrowSecurity)
        val mgr = AndroidNetworkProvisioningManager(ctx(lanTcpPort = null), wifi)
        try {
            assertNull(mgr.getManualConnectionInfo())
        } finally {
            mgr.close()
        }
    }

    @Test
    fun createManualPeerDelegatesToRegistrar() = runBlocking<Unit> {
        val registrar = RecordingRegistrar()
        val wifi = FakeWifiManagerWrapper(behavior = FakeWifiManagerWrapper.Behavior.ThrowSecurity)
        val mgr = AndroidNetworkProvisioningManager(ctx(registrar = registrar), wifi)
        try {
            val peer = mgr.createManualPeer(host = "10.0.0.5", port = 5555)
            assertEquals("10.0.0.5", registrar.calls.single().host)
            assertEquals(5555, registrar.calls.single().port)
            assertEquals("manual:10.0.0.5:5555", peer.name)
        } finally {
            mgr.close()
        }
    }
}

// ---- Test fakes -----------------------------------------------------------

private class FakeWifiManagerWrapper(
    private val behavior: Behavior
) : WifiManagerWrapper {

    var lastHandle: FakeHotspotHandle? = null
    var lastJoinHandle: FakeJoinHandle? = null

    sealed class Behavior {
        object ThrowSecurity : Behavior()
        data class ThrowSecurityWithMessage(val message: String) : Behavior()
        data class FailWithReason(val reasonCode: Int) : Behavior()
        data class Start(val credentials: WifiCredentials?, val apHosts: List<String>) : Behavior()
        data class JoinSucceeds(val networkState: dev.p2pkit.core.provisioning.NetworkState) : Behavior()
        data class JoinFails(val reason: String) : Behavior()
        data class JoinThrowsSecurity(val message: String) : Behavior()
    }

    override fun isWifiEnabled(): Boolean = true

    override val isLocalOnlyHotspotSupported: Boolean = true
    override val isSpecifierJoinSupported: Boolean = true
    override fun requiredRuntimePermission() =
        dev.p2pkit.core.permission.P2pPermission.NearbyWifiDevices

    override suspend fun startLocalOnlyHotspot(): HotspotStartResult {
        return when (val b = behavior) {
            Behavior.ThrowSecurity -> throw SecurityException("simulated perm-missing")
            is Behavior.ThrowSecurityWithMessage -> throw SecurityException(b.message)
            is Behavior.FailWithReason -> HotspotStartResult.Failed(b.reasonCode)
            is Behavior.Start -> {
                val h = FakeHotspotHandle(b.credentials, b.apHosts)
                lastHandle = h
                HotspotStartResult.Started(h)
            }
            // join-only behaviors → not a valid start call in our tests
            is Behavior.JoinSucceeds, is Behavior.JoinFails, is Behavior.JoinThrowsSecurity ->
                throw IllegalStateException("test misconfigured: join behavior used for startLocalOnlyHotspot")
        }
    }

    override suspend fun joinWifiNetwork(credentials: WifiCredentials): JoinResult {
        return when (val b = behavior) {
            is Behavior.JoinSucceeds -> {
                val h = FakeJoinHandle(b.networkState)
                lastJoinHandle = h
                JoinResult.Joined(h)
            }
            is Behavior.JoinFails -> JoinResult.Failed(b.reason)
            is Behavior.JoinThrowsSecurity -> throw SecurityException(b.message)
            // start-only behaviors → not a valid join call in our tests
            Behavior.ThrowSecurity, is Behavior.ThrowSecurityWithMessage,
            is Behavior.FailWithReason, is Behavior.Start ->
                throw IllegalStateException("test misconfigured: start behavior used for joinWifiNetwork")
        }
    }
}

private class FakeHotspotHandle(
    private val credentials: WifiCredentials?,
    private val apHosts: List<String>
) : HotspotHandle {

    private val _stopped: MutableSharedFlow<HotspotStopReason> = MutableSharedFlow(
        replay = 0,
        extraBufferCapacity = 1,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )

    override val stopped: SharedFlow<HotspotStopReason> = _stopped.asSharedFlow()
    var isClosed: Boolean = false
        private set

    override fun getCredentials(): WifiCredentials? = credentials
    override fun apHostAddresses(): List<String> = apHosts
    override fun close() {
        isClosed = true
    }

    fun simulateSystemStop(reason: String) {
        _stopped.tryEmit(HotspotStopReason(reason))
    }
}

private class FakeJoinHandle(
    private val state: dev.p2pkit.core.provisioning.NetworkState
) : JoinHandle {

    private val _released: MutableSharedFlow<String> = MutableSharedFlow(
        replay = 0,
        extraBufferCapacity = 1,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    override val released: SharedFlow<String> = _released.asSharedFlow()
    var isClosed: Boolean = false
        private set

    override fun snapshotNetworkState(): dev.p2pkit.core.provisioning.NetworkState = state
    override fun close() { isClosed = true }

    fun simulateRelease(reason: String) {
        _released.tryEmit(reason)
    }
}

@OptIn(ExperimentalP2pApi::class)
private class RecordingRegistrar : ManualPeerRegistrar {
    data class Call(val host: String, val port: Int, val kind: TransportKind, val deviceName: String?)
    val calls: MutableList<Call> = mutableListOf()

    override fun registerManualPeer(
        host: String,
        port: Int,
        kind: TransportKind,
        deviceName: String?
    ): Peer {
        calls += Call(host, port, kind, deviceName)
        return Peer(
            id = PeerId("manual-$host:$port"),
            name = deviceName ?: "manual:$host:$port",
            platform = Platform.UNKNOWN,
            supportedTransports = setOf(kind)
        )
    }
}
