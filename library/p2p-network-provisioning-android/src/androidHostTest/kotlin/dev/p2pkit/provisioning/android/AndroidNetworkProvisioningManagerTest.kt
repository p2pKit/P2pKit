@file:OptIn(dev.p2pkit.core.ExperimentalP2pApi::class)

package dev.p2pkit.provisioning.android

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.NetworkProvisioningError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
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
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.channels.BufferOverflow
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.filterIsInstance
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class AndroidNetworkProvisioningManagerTest {

    private val testFingerprint = PeerFingerprint("p2f1-${"a".repeat(52)}")
    private val testPairingQr = "p2pkit-v2:test-pairing-qr"

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
        localFingerprint = testFingerprint,
        localPairingQr = testPairingQr,
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
    fun unsupportedHotspotReturnsContractResultWithoutCallingPlatformApi() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.ThrowSecurity,
            localOnlyHotspotSupported = false
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            assertIs<LocalNetworkResult.Unsupported>(
                mgr.startLocalNetwork(LocalNetworkConfig())
            )
            assertEquals(0, wifi.hotspotStartCalls)
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
            assertEquals(testFingerprint, started.manualConnectionInfo!!.fingerprint)
            assertEquals(testPairingQr, started.manualConnectionInfo!!.pairingQr)
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
            assertEquals(testFingerprint, started.manualConnectionInfo.fingerprint)
            assertEquals(testPairingQr, started.manualConnectionInfo.pairingQr)
        } finally {
            mgr.close()
        }
    }

    @Test
    fun failedStartedHotspotClosesReservationAndPublishesFailedState() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.Start(
                credentials = null,
                apHosts = emptyList()
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(lanTcpPort = null), wifi)
        try {
            val result = assertIs<LocalNetworkResult.Failed>(
                mgr.startLocalNetwork(LocalNetworkConfig())
            )
            assertIs<NetworkProvisioningError.HotspotStopped>(result.error)
            assertTrue(
                wifi.lastHandle?.isClosed == true,
                "a live reservation must not remain installed when its public result is Failed"
            )
            assertIs<NetworkProvisioningState.Failed>(mgr.state.value)
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
    fun stopLocalNetworkReportsCleanupFailureAndRetriesRetainedReservation() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.Start(
                credentials = testCreds,
                apHosts = listOf("192.168.43.1"),
                closeFailures = 1
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            assertIs<LocalNetworkResult.Started>(mgr.startLocalNetwork(LocalNetworkConfig()))

            assertFailsWith<NetworkProvisioningError.CleanupFailed> {
                mgr.stopLocalNetwork()
            }
            assertFalse(wifi.lastHandle?.isClosed == true)
            assertEquals(1, wifi.lastHandle?.closeAttempts)
            assertIs<NetworkProvisioningState.Failed>(mgr.state.value)

            mgr.stopLocalNetwork()
            assertTrue(wifi.lastHandle?.isClosed == true)
            assertEquals(2, wifi.lastHandle?.closeAttempts)
            assertEquals(NetworkProvisioningState.Idle, mgr.state.value)
        } finally {
            mgr.close()
        }
    }

    @Test
    fun explicitCloseReportsAllCleanupFailuresAndLaterCloseRetriesThem() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.StartAndJoin(
                credentials = testCreds,
                apHosts = listOf("192.168.43.1"),
                networkState = dev.p2pkit.core.provisioning.NetworkState.ConnectedToWifi(
                    ssid = null,
                    localIpAddresses = listOf("192.168.43.55")
                ),
                hotspotCloseFailures = 1,
                joinCloseFailures = 1
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        assertIs<LocalNetworkResult.Started>(mgr.startLocalNetwork(LocalNetworkConfig()))
        assertIs<JoinNetworkResult.Joined>(mgr.joinLocalNetwork(testCreds))

        val failure = assertFailsWith<NetworkProvisioningError.CleanupFailed> { mgr.close() }
        assertTrue(failure.reason.contains("2 provisioning resource"))
        assertEquals(NetworkProvisioningState.Closed, mgr.state.value)
        assertEquals(1, wifi.lastHandle?.closeAttempts)
        assertEquals(1, wifi.lastJoinHandle?.closeAttempts)

        mgr.close()
        assertTrue(wifi.lastHandle?.isClosed == true)
        assertTrue(wifi.lastJoinHandle?.isClosed == true)
        assertEquals(2, wifi.lastHandle?.closeAttempts)
        assertEquals(2, wifi.lastJoinHandle?.closeAttempts)
    }

    @Test
    fun explicitCloseRemainsClosingUntilOwnedResourceCleanupFinishes() = runBlocking<Unit> {
        val closeEntered = CountDownLatch(1)
        val closeRelease = CountDownLatch(1)
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.Start(
                credentials = testCreds,
                apHosts = listOf("192.168.43.1"),
                closeEntered = closeEntered,
                closeRelease = closeRelease
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        assertIs<LocalNetworkResult.Started>(mgr.startLocalNetwork(LocalNetworkConfig()))

        val closing = async(Dispatchers.Default) { mgr.close() }
        assertTrue(closeEntered.await(2, TimeUnit.SECONDS), "resource cleanup did not start")
        assertEquals(NetworkProvisioningState.Closing, mgr.state.value)

        closeRelease.countDown()
        withTimeout(2_000) { closing.await() }
        assertEquals(NetworkProvisioningState.Closed, mgr.state.value)
    }

    @Test
    fun concurrentCloseCallersJoinTheSameFailingCleanupAttempt() = runBlocking<Unit> {
        val closeEntered = CountDownLatch(1)
        val closeRelease = CountDownLatch(1)
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.Start(
                credentials = testCreds,
                apHosts = listOf("192.168.43.1"),
                closeFailures = 1,
                closeEntered = closeEntered,
                closeRelease = closeRelease
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        assertIs<LocalNetworkResult.Started>(mgr.startLocalNetwork(LocalNetworkConfig()))

        val first = async(Dispatchers.Default) { runCatching { mgr.close() }.exceptionOrNull() }
        try {
            assertTrue(closeEntered.await(2, TimeUnit.SECONDS), "resource cleanup did not start")
            // Start inline until close() suspends on the first caller's attempt.
            // Merely launching on Dispatchers.Default does not prove concurrency:
            // a busy runner may schedule this coroutine only after the latch is
            // released and the failed first attempt completes, in which case a
            // new (correctly retrying) close call observes success.
            val second = async(
                Dispatchers.Default,
                start = CoroutineStart.UNDISPATCHED
            ) {
                runCatching { mgr.close() }.exceptionOrNull()
            }
            assertFalse(
                second.isCompleted,
                "second close must be awaiting the in-flight cleanup transaction"
            )

            closeRelease.countDown()
            val firstFailure = assertIs<NetworkProvisioningError.CleanupFailed>(first.await())
            val secondFailure = assertIs<NetworkProvisioningError.CleanupFailed>(second.await())
            assertTrue(
                firstFailure === secondFailure,
                "concurrent close callers must observe the same cleanup transaction result"
            )
            assertEquals(1, wifi.lastHandle?.closeAttempts)

            mgr.close()
            assertEquals(2, wifi.lastHandle?.closeAttempts)
            assertTrue(wifi.lastHandle?.isClosed == true)
        } finally {
            closeRelease.countDown()
            first.await()
            mgr.close()
        }
    }

    @Test
    fun closeReportsWrapperOwnedLateCleanupAndRetriesItLater() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.ThrowSecurity,
            pendingCleanupFailures = 1
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)

        assertFailsWith<NetworkProvisioningError.CleanupFailed> { mgr.close() }
        assertEquals(1, wifi.pendingCleanupAttempts)
        assertEquals(NetworkProvisioningState.Closed, mgr.state.value)

        mgr.close()
        assertEquals(2, wifi.pendingCleanupAttempts)
    }

    @Test
    fun hotspotStartRetriesWrapperOwnedCleanupBeforeNativeAcquisition() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.Start(
                credentials = testCreds,
                apHosts = listOf("192.168.43.1")
            ),
            pendingCleanupFailures = 1
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            val blocked = assertIs<LocalNetworkResult.Failed>(
                mgr.startLocalNetwork(LocalNetworkConfig())
            )
            assertIs<NetworkProvisioningError.CleanupFailed>(blocked.error)
            assertEquals(0, wifi.hotspotStartCalls)
            assertEquals(1, wifi.pendingCleanupAttempts)

            assertIs<LocalNetworkResult.Started>(mgr.startLocalNetwork(LocalNetworkConfig()))
            assertEquals(1, wifi.hotspotStartCalls)
            assertEquals(2, wifi.pendingCleanupAttempts)
        } finally {
            mgr.close()
        }
    }

    @Test
    fun overlappingNativeHotspotRequestIsReportedAsTypedCleanupFailure() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.HotspotCleanupPending
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            val failed = assertIs<LocalNetworkResult.Failed>(
                mgr.startLocalNetwork(LocalNetworkConfig())
            )
            assertIs<NetworkProvisioningError.CleanupFailed>(failed.error)
            assertIs<NetworkProvisioningState.Failed>(mgr.state.value)
        } finally {
            mgr.close()
        }
    }

    @Test
    fun joinRetriesWrapperOwnedCleanupBeforeNativeAcquisition() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.JoinSucceeds(
                networkState = dev.p2pkit.core.provisioning.NetworkState.ConnectedToWifi(
                    ssid = null,
                    localIpAddresses = listOf("192.168.43.55")
                )
            ),
            pendingCleanupFailures = 1
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            val blocked = assertIs<JoinNetworkResult.Failed>(mgr.joinLocalNetwork(testCreds))
            assertIs<NetworkProvisioningError.CleanupFailed>(blocked.error)
            assertEquals(0, wifi.joinCalls)
            assertEquals(1, wifi.pendingCleanupAttempts)

            assertIs<JoinNetworkResult.Joined>(mgr.joinLocalNetwork(testCreds))
            assertEquals(1, wifi.joinCalls)
            assertEquals(2, wifi.pendingCleanupAttempts)
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
            val failedEventDeferred = async(start = CoroutineStart.UNDISPATCHED) {
                mgr.events.filterIsInstance<NetworkProvisioningEvent.Failed>().first()
            }
            mgr.startLocalNetwork(LocalNetworkConfig())
            assertEquals(1, wifi.lastHandle?.stopSubscriberCount)
            wifi.lastHandle?.simulateSystemStop("OEM battery policy")
            val event = withTimeout(2_000) { failedEventDeferred.await() }
            assertIs<NetworkProvisioningError.HotspotStopped>(event.error)
            withTimeout(2_000) { wifi.lastHandle?.awaitWatcherStopped() }
        } finally {
            mgr.close()
        }
    }

    @Test
    fun systemStopCleanupFailureIsTypedAndRetainedForStopRetry() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.Start(
                credentials = testCreds,
                apHosts = listOf("192.168.43.1"),
                closeFailures = 1
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            val failedEvent = async(start = CoroutineStart.UNDISPATCHED) {
                mgr.events.filterIsInstance<NetworkProvisioningEvent.Failed>().first()
            }
            assertIs<LocalNetworkResult.Started>(mgr.startLocalNetwork(LocalNetworkConfig()))
            assertEquals(1, wifi.lastHandle?.stopSubscriberCount)
            wifi.lastHandle?.simulateSystemStop("OEM policy")

            assertIs<NetworkProvisioningError.CleanupFailed>(
                withTimeout(2_000) { failedEvent.await() }.error
            )
            assertEquals(1, wifi.lastHandle?.closeAttempts)
            withTimeout(2_000) { wifi.lastHandle?.awaitWatcherStopped() }
            mgr.stopLocalNetwork()
            assertTrue(wifi.lastHandle?.isClosed == true)
            assertEquals(NetworkProvisioningState.Idle, mgr.state.value)
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
            val joinedEventDeferred = async(start = CoroutineStart.UNDISPATCHED) {
                mgr.events.filterIsInstance<NetworkProvisioningEvent.NetworkJoined>().first()
            }
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
    fun unsupportedSpecifierJoinReturnsContractResultWithoutCallingPlatformApi() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.JoinFails("must not be called"),
            specifierJoinSupported = false
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            assertIs<JoinNetworkResult.Unsupported>(mgr.joinLocalNetwork(testCreds))
            assertEquals(0, wifi.joinCalls)
        } finally {
            mgr.close()
        }
    }

    @Test
    fun joinInputValidationPreventsPlatformBuilderErrors() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.JoinSucceeds(
                networkState = dev.p2pkit.core.provisioning.NetworkState.Unknown
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            val tooLong = WifiCredentials(
                ssid = "x".repeat(33),
                password = WifiPassword("12345678"),
                securityType = WifiSecurityType.WPA2
            )
            val failed = assertIs<JoinNetworkResult.Failed>(mgr.joinLocalNetwork(tooLong))
            assertTrue((failed.error as NetworkProvisioningError.JoinFailed).reason.contains("32 UTF-8"))
            assertNull(wifi.lastJoinHandle, "invalid input must not invoke the wrapper")
            assertEquals(
                "OPEN Wi-Fi must not include a password",
                validateWifiCredentials(
                    WifiCredentials("open", WifiPassword("12345678"), WifiSecurityType.OPEN)
                )
            )
            assertEquals(
                "Wi-Fi password must be 8..63 characters",
                validateWifiCredentials(
                    WifiCredentials("ssid", WifiPassword("short"), WifiSecurityType.WPA2)
                )
            )
            assertEquals(
                "WPA2 Wi-Fi requires a password",
                validateWifiCredentials(
                    WifiCredentials("ssid", null, WifiSecurityType.WPA2)
                )
            )
            assertEquals(
                "Wi-Fi password must contain only ASCII characters",
                validateWifiCredentials(
                    WifiCredentials("ssid", WifiPassword("é".repeat(8)), WifiSecurityType.WPA3)
                )
            )
            assertEquals(
                "OPEN Wi-Fi must not include a password",
                validateWifiCredentials(
                    WifiCredentials("open", WifiPassword(""), WifiSecurityType.OPEN)
                )
            )
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
            val failedEventDeferred = async(start = CoroutineStart.UNDISPATCHED) {
                mgr.events.filterIsInstance<NetworkProvisioningEvent.Failed>().first()
            }
            mgr.joinLocalNetwork(testCreds)
            assertEquals(1, wifi.lastJoinHandle?.releaseSubscriberCount)
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
            withTimeout(2_000) { wifi.lastJoinHandle?.awaitWatcherStopped() }
            assertIs<NetworkProvisioningState.Failed>(mgr.state.value)
            // The handle slot is cleared: a follow-up join must not be
            // rejected as "already active".
            assertIs<JoinNetworkResult.Joined>(mgr.joinLocalNetwork(testCreds))
        } finally {
            mgr.close()
        }
    }

    @Test
    fun joinReleaseCleanupFailureIsTypedAndRetriedByClose() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.JoinSucceeds(
                networkState = dev.p2pkit.core.provisioning.NetworkState.ConnectedToWifi(
                    ssid = null,
                    localIpAddresses = listOf("192.168.43.55")
                ),
                closeFailures = 1
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        val failedEvent = async(start = CoroutineStart.UNDISPATCHED) {
            mgr.events.filterIsInstance<NetworkProvisioningEvent.Failed>().first()
        }
        assertIs<JoinNetworkResult.Joined>(mgr.joinLocalNetwork(testCreds))
        assertEquals(1, wifi.lastJoinHandle?.releaseSubscriberCount)
        wifi.lastJoinHandle?.simulateRelease("network vanished")

        assertIs<NetworkProvisioningError.CleanupFailed>(
            withTimeout(2_000) { failedEvent.await() }.error
        )
        assertEquals(1, wifi.lastJoinHandle?.closeAttempts)
        withTimeout(2_000) { wifi.lastJoinHandle?.awaitWatcherStopped() }
        mgr.close()
        assertTrue(wifi.lastJoinHandle?.isClosed == true)
        assertEquals(2, wifi.lastJoinHandle?.closeAttempts)
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
    fun parentCancellationRetainsFailedHotspotCleanupForExplicitRetry() = runBlocking<Unit> {
        val parentJob = Job()
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.Start(
                credentials = testCreds,
                apHosts = listOf("192.168.43.1"),
                closeFailures = 1
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(parentJob = parentJob), wifi)
        assertIs<LocalNetworkResult.Started>(mgr.startLocalNetwork(LocalNetworkConfig()))

        parentJob.cancel()
        parentJob.join()

        assertEquals(NetworkProvisioningState.Closed, mgr.state.value)
        assertFalse(wifi.lastHandle?.isClosed == true)
        assertEquals(1, wifi.lastHandle?.closeAttempts)

        mgr.close()
        assertTrue(wifi.lastHandle?.isClosed == true)
        assertEquals(2, wifi.lastHandle?.closeAttempts)
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

    /** Parent cancellation is terminal before any later OS acquisition begins. */
    @Test
    fun startAfterParentJobCancellationIsRefusedAndDoesNotAcquireReservation() = runBlocking<Unit> {
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
            val failed = assertIs<LocalNetworkResult.Failed>(result)
            assertIs<NetworkProvisioningError.ManagerClosed>(failed.error)
            assertNull(wifi.lastHandle, "a closed manager must not call the OS start API")
            assertEquals(NetworkProvisioningState.Closed, mgr.state.value)
        } finally {
            mgr.close()
        }
    }

    @Test
    fun closeRacingHotspotStartCancelsAcquisitionAndReturnsOneTerminalFailure() = runBlocking<Unit> {
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.StartSuspends(
                entered = entered,
                release = release,
                credentials = testCreds,
                apHosts = listOf("192.168.43.1")
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            val start = async { mgr.startLocalNetwork(LocalNetworkConfig()) }
            entered.await()
            mgr.close()
            release.complete(Unit)

            val failed = assertIs<LocalNetworkResult.Failed>(start.await())
            assertIs<NetworkProvisioningError.ManagerClosed>(failed.error)
            assertNull(wifi.lastHandle, "close must cancel the acquisition before a reservation is delivered")
            assertEquals(NetworkProvisioningState.Closed, mgr.state.value)
        } finally {
            mgr.close()
            release.complete(Unit)
        }
    }

    @Test
    fun closeWaitsForCleanupAfterHotspotHandleWasDeliveredButNotInstalled() = runBlocking<Unit> {
        val acquired = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.Start(
                credentials = testCreds,
                apHosts = listOf("192.168.43.1")
            )
        )
        val mgr = AndroidNetworkProvisioningManager(
            ctx(),
            wifi,
            ProvisioningLifecycleHooks(
                afterHotspotAcquired = {
                    acquired.complete(Unit)
                    release.await()
                }
            )
        )
        try {
            val start = async { mgr.startLocalNetwork(LocalNetworkConfig()) }
            acquired.await()
            assertFalse(wifi.lastHandle?.isClosed == true)

            mgr.close()

            assertTrue(wifi.lastHandle?.isClosed == true)
            assertIs<NetworkProvisioningError.ManagerClosed>(
                assertIs<LocalNetworkResult.Failed>(start.await()).error
            )
        } finally {
            release.complete(Unit)
            mgr.close()
        }
    }

    @Test
    fun callerCancellationAfterHotspotDeliveryCleansHandleAndRestoresIdle() = runBlocking<Unit> {
        val acquired = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.Start(
                credentials = testCreds,
                apHosts = listOf("192.168.43.1")
            )
        )
        val mgr = AndroidNetworkProvisioningManager(
            ctx(),
            wifi,
            ProvisioningLifecycleHooks(
                afterHotspotAcquired = {
                    acquired.complete(Unit)
                    release.await()
                }
            )
        )
        try {
            val start = async { mgr.startLocalNetwork(LocalNetworkConfig()) }
            acquired.await()
            start.cancelAndJoin()

            assertTrue(wifi.lastHandle?.isClosed == true)
            assertEquals(NetworkProvisioningState.Idle, mgr.state.value)
        } finally {
            release.complete(Unit)
            mgr.close()
        }
    }

    @Test
    fun closeWaitsForCleanupAfterJoinHandleWasDeliveredButNotInstalled() = runBlocking<Unit> {
        val acquired = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.JoinSucceeds(
                networkState = dev.p2pkit.core.provisioning.NetworkState.ConnectedToWifi(
                    ssid = null,
                    localIpAddresses = listOf("192.168.43.55")
                )
            )
        )
        val mgr = AndroidNetworkProvisioningManager(
            ctx(),
            wifi,
            ProvisioningLifecycleHooks(
                afterJoinAcquired = {
                    acquired.complete(Unit)
                    release.await()
                }
            )
        )
        try {
            val join = async { mgr.joinLocalNetwork(testCreds) }
            acquired.await()
            assertFalse(wifi.lastJoinHandle?.isClosed == true)

            mgr.close()

            assertTrue(wifi.lastJoinHandle?.isClosed == true)
            assertIs<NetworkProvisioningError.ManagerClosed>(
                assertIs<JoinNetworkResult.Failed>(join.await()).error
            )
        } finally {
            release.complete(Unit)
            mgr.close()
        }
    }

    @Test
    fun callerCancellationCancelsOwnedAcquisitionAndRestoresIdle() = runBlocking<Unit> {
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.StartSuspends(
                entered = entered,
                release = release,
                credentials = testCreds,
                apHosts = listOf("192.168.43.1")
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            val start = async { mgr.startLocalNetwork(LocalNetworkConfig()) }
            entered.await()
            start.cancelAndJoin()

            assertEquals(NetworkProvisioningState.Idle, mgr.state.value)
            assertNull(wifi.lastHandle, "caller cancellation must cancel acquisition ownership")
        } finally {
            release.complete(Unit)
            mgr.close()
        }
    }

    @Test
    fun closeRacingJoinCancelsAcquisitionAndReturnsOneTerminalFailure() = runBlocking<Unit> {
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.JoinSuspends(
                entered = entered,
                release = release,
                networkState = dev.p2pkit.core.provisioning.NetworkState.ConnectedToWifi(
                    ssid = null,
                    localIpAddresses = listOf("192.168.43.55")
                )
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)
        try {
            val join = async { mgr.joinLocalNetwork(testCreds) }
            entered.await()
            mgr.close()
            release.complete(Unit)

            val failed = assertIs<JoinNetworkResult.Failed>(join.await())
            assertIs<NetworkProvisioningError.ManagerClosed>(failed.error)
            assertNull(wifi.lastJoinHandle, "close must cancel acquisition before process binding is delivered")
            assertEquals(NetworkProvisioningState.Closed, mgr.state.value)
        } finally {
            mgr.close()
            release.complete(Unit)
        }
    }

    @Test
    fun closeIsTerminalIdempotentAndFutureOperationsDoNotReachWifiApis() = runBlocking<Unit> {
        val wifi = FakeWifiManagerWrapper(
            behavior = FakeWifiManagerWrapper.Behavior.Start(
                credentials = testCreds,
                apHosts = listOf("192.168.43.1")
            )
        )
        val mgr = AndroidNetworkProvisioningManager(ctx(), wifi)

        mgr.close()
        mgr.close()

        assertEquals(NetworkProvisioningState.Closed, mgr.state.value)
        assertIs<NetworkProvisioningError.ManagerClosed>(
            assertIs<LocalNetworkResult.Failed>(
                mgr.startLocalNetwork(LocalNetworkConfig())
            ).error
        )
        assertIs<NetworkProvisioningError.ManagerClosed>(
            assertIs<JoinNetworkResult.Failed>(mgr.joinLocalNetwork(testCreds)).error
        )
        assertFailsWith<NetworkProvisioningError.ManagerClosed> {
            mgr.getManualConnectionInfo()
        }
        mgr.stopLocalNetwork()
        assertNull(wifi.lastHandle, "closed manager must not call the hotspot API")
        assertNull(wifi.lastJoinHandle, "closed manager must not call the join API")
        assertEquals(NetworkProvisioningState.Closed, mgr.state.value)
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
    @Suppress("DEPRECATION")
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

    @Test
    fun provisioningOwnershipAndManifestSeamsAreDeterministic() {
        val hotspot = HotspotReservationOwner<String>()
        assertTrue(hotspot.tryInstall("reservation"))
        assertEquals("reservation", hotspot.cancelAndTake())
        assertFalse(hotspot.tryInstall("late reservation"))

        val join = JoinCallbackOwner<String>()
        assertTrue(join.claimInitial())
        assertFalse(join.claimInitial())
        assertTrue(join.install("binding"))
        assertTrue(join.tryDeliver("binding") { true })
        assertEquals("binding", join.closeAndTake())
        assertFalse(join.tryDeliver("binding") { true })
        assertFalse(join.install("late binding"))
        assertNull(join.current())

        val pending = JoinCallbackOwner<String>()
        assertTrue(pending.claimInitial())
        assertTrue(pending.closeIfPending())
        assertFalse(pending.install("late callback"))

        val first = Any()
        val second = Any()
        assertTrue(ProcessBindingArbiter.tryAcquire(first))
        assertFalse(ProcessBindingArbiter.tryAcquire(second))
        ProcessBindingArbiter.release(first)
        assertTrue(ProcessBindingArbiter.tryAcquire(second))
        ProcessBindingArbiter.release(second)

        assertEquals(
            listOf(
                "android.permission.ACCESS_WIFI_STATE",
                "android.permission.CHANGE_WIFI_STATE",
                "android.permission.CHANGE_NETWORK_STATE"
            ),
            provisioningNormalManifestPermissions
        )
        assertEquals(
            dev.p2pkit.core.provisioning.NetworkState.ConnectedToWifi(
                ssid = null,
                localIpAddresses = listOf("192.168.1.2", "10.0.0.2")
            ),
            networkStateFromJoinedAddresses(listOf("192.168.1.2", "192.168.1.2", "10.0.0.2"))
        )
        assertEquals(
            dev.p2pkit.core.permission.P2pPermission.Location,
            requiredProvisioningRuntimePermission(deviceSdk = 32, targetSdk = 35)
        )
        assertEquals(
            dev.p2pkit.core.permission.P2pPermission.Location,
            requiredProvisioningRuntimePermission(deviceSdk = 35, targetSdk = 32)
        )
        assertEquals(
            dev.p2pkit.core.permission.P2pPermission.NearbyWifiDevices,
            requiredProvisioningRuntimePermission(deviceSdk = 33, targetSdk = 33)
        )
    }
}

// ---- Test fakes -----------------------------------------------------------

private class FakeWifiManagerWrapper(
    private val behavior: Behavior,
    pendingCleanupFailures: Int = 0,
    private val localOnlyHotspotSupported: Boolean = true,
    private val specifierJoinSupported: Boolean = true
) : WifiManagerWrapper {

    var lastHandle: FakeHotspotHandle? = null
    var lastJoinHandle: FakeJoinHandle? = null
    var pendingCleanupAttempts: Int = 0
        private set
    var hotspotStartCalls: Int = 0
        private set
    var joinCalls: Int = 0
        private set
    private var pendingCleanupFailuresRemaining = pendingCleanupFailures

    sealed class Behavior {
        object ThrowSecurity : Behavior()
        object HotspotCleanupPending : Behavior()
        data class ThrowSecurityWithMessage(val message: String) : Behavior()
        data class FailWithReason(val reasonCode: Int) : Behavior()
        data class Start(
            val credentials: WifiCredentials?,
            val apHosts: List<String>,
            val closeFailures: Int = 0,
            val closeEntered: CountDownLatch? = null,
            val closeRelease: CountDownLatch? = null
        ) : Behavior()
        data class StartSuspends(
            val entered: CompletableDeferred<Unit>,
            val release: CompletableDeferred<Unit>,
            val credentials: WifiCredentials?,
            val apHosts: List<String>,
            val closeFailures: Int = 0
        ) : Behavior()
        data class JoinSucceeds(
            val networkState: dev.p2pkit.core.provisioning.NetworkState,
            val closeFailures: Int = 0
        ) : Behavior()
        data class JoinSuspends(
            val entered: CompletableDeferred<Unit>,
            val release: CompletableDeferred<Unit>,
            val networkState: dev.p2pkit.core.provisioning.NetworkState,
            val closeFailures: Int = 0
        ) : Behavior()
        data class StartAndJoin(
            val credentials: WifiCredentials?,
            val apHosts: List<String>,
            val networkState: dev.p2pkit.core.provisioning.NetworkState,
            val hotspotCloseFailures: Int = 0,
            val joinCloseFailures: Int = 0
        ) : Behavior()
        data class JoinFails(val reason: String) : Behavior()
        data class JoinThrowsSecurity(val message: String) : Behavior()
    }

    override fun isWifiEnabled(): Boolean = true

    override val isLocalOnlyHotspotSupported: Boolean = localOnlyHotspotSupported
    override val isSpecifierJoinSupported: Boolean = specifierJoinSupported
    override fun requiredRuntimePermission() =
        dev.p2pkit.core.permission.P2pPermission.NearbyWifiDevices

    override suspend fun startLocalOnlyHotspot(): HotspotStartResult {
        hotspotStartCalls += 1
        return when (val b = behavior) {
            Behavior.ThrowSecurity -> throw SecurityException("simulated perm-missing")
            Behavior.HotspotCleanupPending ->
                HotspotStartResult.CleanupPending("simulated native request still pending")
            is Behavior.ThrowSecurityWithMessage -> throw SecurityException(b.message)
            is Behavior.FailWithReason -> HotspotStartResult.Failed(b.reasonCode)
            is Behavior.Start -> {
                val h = FakeHotspotHandle(
                    credentials = b.credentials,
                    apHosts = b.apHosts,
                    closeFailures = b.closeFailures,
                    closeEntered = b.closeEntered,
                    closeRelease = b.closeRelease
                )
                lastHandle = h
                HotspotStartResult.Started(h)
            }
            is Behavior.StartSuspends -> {
                b.entered.complete(Unit)
                b.release.await()
                val h = FakeHotspotHandle(b.credentials, b.apHosts, b.closeFailures)
                lastHandle = h
                HotspotStartResult.Started(h)
            }
            is Behavior.StartAndJoin -> {
                val h = FakeHotspotHandle(b.credentials, b.apHosts, b.hotspotCloseFailures)
                lastHandle = h
                HotspotStartResult.Started(h)
            }
            // join-only behaviors → not a valid start call in our tests
            is Behavior.JoinSucceeds, is Behavior.JoinSuspends,
            is Behavior.JoinFails, is Behavior.JoinThrowsSecurity ->
                throw IllegalStateException("test misconfigured: join behavior used for startLocalOnlyHotspot")
        }
    }

    override suspend fun joinWifiNetwork(credentials: WifiCredentials): JoinResult {
        joinCalls += 1
        return when (val b = behavior) {
            is Behavior.JoinSucceeds -> {
                val h = FakeJoinHandle(b.networkState, b.closeFailures)
                lastJoinHandle = h
                JoinResult.Joined(h)
            }
            is Behavior.JoinSuspends -> {
                b.entered.complete(Unit)
                b.release.await()
                val h = FakeJoinHandle(b.networkState, b.closeFailures)
                lastJoinHandle = h
                JoinResult.Joined(h)
            }
            is Behavior.StartAndJoin -> {
                val h = FakeJoinHandle(b.networkState, b.joinCloseFailures)
                lastJoinHandle = h
                JoinResult.Joined(h)
            }
            is Behavior.JoinFails -> JoinResult.Failed(b.reason)
            is Behavior.JoinThrowsSecurity -> throw SecurityException(b.message)
            // start-only behaviors → not a valid join call in our tests
            Behavior.ThrowSecurity, Behavior.HotspotCleanupPending,
            is Behavior.ThrowSecurityWithMessage,
            is Behavior.FailWithReason, is Behavior.Start, is Behavior.StartSuspends ->
                throw IllegalStateException("test misconfigured: start behavior used for joinWifiNetwork")
        }
    }

    override fun closePendingResources(): List<Throwable> {
        pendingCleanupAttempts += 1
        return if (pendingCleanupFailuresRemaining > 0) {
            pendingCleanupFailuresRemaining -= 1
            listOf(IllegalStateException("simulated wrapper-owned cleanup failure"))
        } else {
            emptyList()
        }
    }
}

private class FakeHotspotHandle(
    private val credentials: WifiCredentials?,
    private val apHosts: List<String>,
    closeFailures: Int = 0,
    private val closeEntered: CountDownLatch? = null,
    private val closeRelease: CountDownLatch? = null
) : HotspotHandle {

    private val _stopped: MutableSharedFlow<HotspotStopReason> = MutableSharedFlow(
        replay = 0,
        extraBufferCapacity = 1,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )

    override val stopped: SharedFlow<HotspotStopReason> = _stopped.asSharedFlow()
    var isClosed: Boolean = false
        private set
    var closeAttempts: Int = 0
        private set
    private var closeFailuresRemaining: Int = closeFailures
    val stopSubscriberCount: Int get() = _stopped.subscriptionCount.value

    override fun getCredentials(): WifiCredentials? = credentials
    override fun apHostAddresses(): List<String> = apHosts
    override fun close() {
        closeAttempts += 1
        closeEntered?.countDown()
        if (closeRelease != null) {
            check(closeRelease.await(2, TimeUnit.SECONDS)) {
                "test did not release blocked hotspot cleanup"
            }
        }
        if (closeFailuresRemaining > 0) {
            closeFailuresRemaining -= 1
            throw IllegalStateException("simulated hotspot close failure")
        }
        isClosed = true
    }

    fun simulateSystemStop(reason: String) {
        _stopped.tryEmit(HotspotStopReason(reason))
    }

    suspend fun awaitWatcherStopped() {
        _stopped.subscriptionCount.first { it == 0 }
    }
}

private class FakeJoinHandle(
    private val state: dev.p2pkit.core.provisioning.NetworkState,
    closeFailures: Int = 0
) : JoinHandle {

    private val _released: MutableSharedFlow<String> = MutableSharedFlow(
        replay = 0,
        extraBufferCapacity = 1,
        onBufferOverflow = BufferOverflow.DROP_OLDEST
    )
    override val released: SharedFlow<String> = _released.asSharedFlow()
    var isClosed: Boolean = false
        private set
    var closeAttempts: Int = 0
        private set
    private var closeFailuresRemaining: Int = closeFailures
    val releaseSubscriberCount: Int get() = _released.subscriptionCount.value

    override fun snapshotNetworkState(): dev.p2pkit.core.provisioning.NetworkState = state
    override fun close() {
        closeAttempts += 1
        if (closeFailuresRemaining > 0) {
            closeFailuresRemaining -= 1
            throw IllegalStateException("simulated join close failure")
        }
        isClosed = true
    }

    fun simulateRelease(reason: String) {
        _released.tryEmit(reason)
    }

    suspend fun awaitWatcherStopped() {
        _released.subscriptionCount.first { it == 0 }
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
        deviceName: String?,
        expectedFingerprint: PeerFingerprint?
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
