@file:OptIn(dev.p2pkit.core.ExperimentalP2pApi::class)

package dev.p2pkit.provisioning.android

import dev.p2pkit.core.AppId
import dev.p2pkit.core.NetworkProvisioningError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.permission.P2pPermission
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.core.provisioning.LocalNetworkConfig
import dev.p2pkit.core.provisioning.LocalNetworkResult
import dev.p2pkit.core.provisioning.ManualPeerRegistrar
import dev.p2pkit.core.provisioning.NetworkProvisioningConfig
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.core.provisioning.ProvisioningContext
import dev.p2pkit.core.provisioning.WifiCredentials
import dev.p2pkit.core.provisioning.WifiSecurityType
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue

class ProvisioningFailureClassificationTest {
    private val credentials = WifiCredentials("synthetic hotspot", null, WifiSecurityType.OPEN)

    @Test
    fun deniedCredentialReadFailsAndReleasesNewReservationInsteadOfReportingRedaction() = runBlocking {
        val fixture = FailureFixture()
        fixture.readFailure = SecurityException("synthetic credential denial")
        fixture.observed = ProvisioningPermissionState(runtimePermissionGranted = false)
        try {
            val error = assertIs<LocalNetworkResult.Failed>(
                fixture.manager.startLocalNetwork(LocalNetworkConfig())
            ).error
            assertEquals(
                listOf(P2pPermission.NearbyWifiDevices),
                assertIs<NetworkProvisioningError.PermissionMissingForProvisioning>(error).permissions
            )
            assertEquals(1, fixture.closeCalls)
            assertEquals(NetworkProvisioningState.Failed(error), fixture.manager.state.value)
        } finally {
            fixture.manager.close()
        }
        assertEquals(1, fixture.closeCalls)
    }

    @Test
    fun platformCredentialReadFailurePreservesCauseAndRetainsFailedCleanupForRetry() = runBlocking {
        val fixture = FailureFixture()
        val failure = IllegalStateException("synthetic credential failure")
        fixture.readFailure = failure
        fixture.failCloseOnce = true
        try {
            assertIs<NetworkProvisioningError.CleanupFailed>(
                assertIs<LocalNetworkResult.Failed>(fixture.manager.startLocalNetwork(LocalNetworkConfig())).error
            )
            assertEquals(1, fixture.closeCalls)
            fixture.manager.stopLocalNetwork()
            assertEquals(2, fixture.closeCalls)
            fixture.readFailure = failure
            val error = assertIs<LocalNetworkResult.Failed>(
                fixture.manager.startLocalNetwork(LocalNetworkConfig())
            ).error
            assertSame(failure, assertIs<NetworkProvisioningError.PlatformError>(error).platformException)
            assertEquals(3, fixture.closeCalls)
        } finally {
            fixture.manager.close()
        }
    }

    @Test
    fun repeatedCredentialInspectionReportsDenialWithoutLosingExistingHotspotOwnership() = runBlocking {
        val fixture = FailureFixture()
        try {
            assertIs<LocalNetworkResult.Started>(fixture.manager.startLocalNetwork(LocalNetworkConfig()))
            fixture.readFailure = SecurityException("synthetic later denial")
            fixture.observed = ProvisioningPermissionState(runtimePermissionGranted = false)
            assertIs<NetworkProvisioningError.PermissionMissingForProvisioning>(
                assertIs<LocalNetworkResult.Failed>(fixture.manager.startLocalNetwork(LocalNetworkConfig())).error
            )
            assertEquals(0, fixture.closeCalls)
            fixture.manager.stopLocalNetwork()
            assertEquals(1, fixture.closeCalls)
        } finally {
            fixture.manager.close()
        }
    }

    @Test
    fun credentialCancellationIsNotRedactionAndReleasesUnpublishedReservation() = runBlocking {
        val fixture = FailureFixture()
        fixture.readFailure = CancellationException("synthetic cancellation")
        try {
            assertFailsWith<CancellationException> { fixture.manager.startLocalNetwork(LocalNetworkConfig()) }
            assertEquals(1, fixture.closeCalls)
            assertEquals(NetworkProvisioningState.Idle, fixture.manager.state.value)
        } finally {
            fixture.manager.close()
        }
    }

    @Test
    fun nestedSecurityCauseUsesCurrentGrantForBothStartAndJoin() = runBlocking {
        val fixture = FailureFixture()
        fixture.operationFailure = IllegalStateException(
            "outer", RuntimeException("inner", SecurityException("denied"))
        )
        fixture.observed = ProvisioningPermissionState(runtimePermissionGranted = false)
        try {
            assertIs<NetworkProvisioningError.PermissionMissingForProvisioning>(
                assertIs<LocalNetworkResult.Failed>(fixture.manager.startLocalNetwork(LocalNetworkConfig())).error
            )
            assertIs<NetworkProvisioningError.PermissionMissingForProvisioning>(
                assertIs<JoinNetworkResult.Failed>(fixture.manager.joinLocalNetwork(credentials)).error
            )
            assertEquals(2, fixture.probeCalls)
        } finally {
            fixture.manager.close()
        }
    }

    @Test
    fun arbitrarySecurityDenialAndFailedProbeDoNotInventAMissingRuntimePermission() = runBlocking {
        val fixture = FailureFixture()
        val failure = object : SecurityException("Location mode is not enabled. CHANGE_NETWORK_STATE denied") {
            // Extra state prevents coroutine stacktrace recovery from copying
            // this sentinel, keeping the cause-identity assertion meaningful.
            val marker = Any()
        }
        fixture.operationFailure = failure
        fixture.observed = ProvisioningPermissionState(runtimePermissionGranted = true, locationEnabled = true)
        try {
            for (probeFailure in listOf(null, IllegalStateException("probe unavailable"))) {
                fixture.probeFailure = probeFailure
                val error = assertIs<LocalNetworkResult.Failed>(
                    fixture.manager.startLocalNetwork(LocalNetworkConfig())
                ).error
                assertSame(failure, assertIs<NetworkProvisioningError.PlatformError>(error).platformException)
            }
        } finally {
            fixture.manager.close()
        }
    }

    @Test
    fun securityCauseWalkTerminatesForCyclesAndHasAFixedWorkBound() {
        val first = IllegalStateException("first")
        val second = IllegalStateException("second", first)
        first.initCause(second)
        assertFalse(hasProvisioningSecurityCause(first))
        var failure: Throwable = SecurityException("denied")
        repeat(2) { failure = IllegalStateException("wrapper", failure) }
        assertTrue(hasProvisioningSecurityCause(failure))
        repeat(32) { failure = IllegalStateException("wrapper", failure) }
        assertFalse(hasProvisioningSecurityCause(failure))
    }
}

private class FailureFixture : WifiManagerWrapper, HotspotHandle {
    var readFailure: Throwable? = null
    var operationFailure: Throwable? = null
    var probeFailure: Throwable? = null
    var observed = ProvisioningPermissionState(runtimePermissionGranted = true, locationEnabled = true)
    var closeCalls = 0
    var failCloseOnce = false
    var probeCalls = 0
    override val isLocalOnlyHotspotSupported = true
    override val isSpecifierJoinSupported = true
    override fun requiredRuntimePermission() = P2pPermission.NearbyWifiDevices
    override fun permissionState(): ProvisioningPermissionState {
        probeCalls += 1
        probeFailure?.let { throw it }
        return observed
    }
    override suspend fun startLocalOnlyHotspot(): HotspotStartResult {
        operationFailure?.let { throw it }
        return HotspotStartResult.Started(this)
    }
    override suspend fun joinWifiNetwork(credentials: WifiCredentials): JoinResult {
        throw checkNotNull(operationFailure)
    }
    override fun getCredentials(): WifiCredentials? {
        readFailure?.let { throw it }
        return WifiCredentials("synthetic hotspot", null, WifiSecurityType.OPEN)
    }
    override fun apHostAddresses() = listOf("192.0.2.1")
    override val stopped = MutableSharedFlow<HotspotStopReason>()
    override fun close() {
        closeCalls += 1
        if (failCloseOnce) {
            failCloseOnce = false
            error("synthetic close failure")
        }
    }
    val manager = AndroidNetworkProvisioningManager(
        ProvisioningContext(
            appId = AppId("permission-failure-test"),
            localPeerId = PeerId("local"),
            localDeviceName = "synthetic",
            config = NetworkProvisioningConfig(),
            logger = P2pLogger.NoOp,
            lanTcpPort = { 42000 },
            manualPeerRegistrar = object : ManualPeerRegistrar {
                override fun registerManualPeer(
                    host: String,
                    port: Int,
                    kind: TransportKind,
                    deviceName: String?,
                    expectedFingerprint: PeerFingerprint?
                ): Peer = error("not used")
            }
        ),
        this
    )
}
