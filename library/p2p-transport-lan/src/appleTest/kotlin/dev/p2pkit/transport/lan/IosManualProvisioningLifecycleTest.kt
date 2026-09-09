package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.NetworkProvisioningError
import dev.p2pkit.core.P2pLogger
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.core.provisioning.LocalNetworkConfig
import dev.p2pkit.core.provisioning.LocalNetworkResult
import dev.p2pkit.core.provisioning.ManualPeerRegistrar
import dev.p2pkit.core.provisioning.NetworkProvisioningConfig
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.core.provisioning.ProvisioningContext
import dev.p2pkit.core.provisioning.WifiCredentials
import dev.p2pkit.core.provisioning.WifiPassword
import dev.p2pkit.core.provisioning.WifiSecurityType
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.TestCoroutineScheduler
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertSame
import kotlin.test.assertTrue

@OptIn(ExperimentalP2pApi::class)
class IosManualProvisioningLifecycleTest {

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun boundedCloseSharesFailureAndRetainsOwnedWorkForRetry() = runBlocking<Unit> {
        val parent = Job()
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val manager = heldManager(parent, entered, release)
        val owned = parent.children.single()
        val scheduler = TestCoroutineScheduler()
        val closingDispatcher = StandardTestDispatcher(scheduler)
        try {
            supervisorScope {
                val info = async { manager.getManualConnectionInfo() }
                try {
                    withTimeout(2_000) { entered.await() }
                    val first = async(closingDispatcher) { runCatching { manager.close() }.exceptionOrNull() }
                    val second = async(closingDispatcher) { runCatching { manager.close() }.exceptionOrNull() }
                    scheduler.runCurrent()
                    assertEquals(NetworkProvisioningState.Closing, manager.state.value)
                    scheduler.advanceTimeBy(4_999)
                    scheduler.runCurrent()
                    assertFalse(first.isCompleted)
                    assertFalse(second.isCompleted)
                    scheduler.advanceTimeBy(1)
                    scheduler.runCurrent()
                    val failure = assertIs<NetworkProvisioningError.CleanupFailed>(
                        withTimeout(2_000) { first.await() }
                    )
                    assertSame(failure, withTimeout(2_000) { second.await() })
                    assertEquals(NetworkProvisioningState.Closed, manager.state.value)
                    assertFalse(owned.isCompleted)
                    assertTrue(parent.children.any { it === owned }, "timeout must retain the original owner")
                    assertIs<NetworkProvisioningError.ManagerClosed>(
                        assertIs<LocalNetworkResult.Failed>(manager.startLocalNetwork(LocalNetworkConfig())).error
                    )
                    release.complete(Unit)
                    withTimeout(2_000) { owned.join() }
                    assertFailsWith<NetworkProvisioningError.ManagerClosed> { info.await() }
                    manager.close()
                    manager.close()
                } finally {
                    release.complete(Unit)
                    owned.cancel()
                    withTimeout(2_000) { owned.join() }
                    scheduler.runCurrent()
                }
            }
        } finally {
            release.complete(Unit)
            manager.close()
            parent.cancel()
            parent.join()
        }
    }

    @Test
    fun parentCancellationBeginsClosingBeforeNonCooperativeWorkCompletes() = runBlocking<Unit> {
        val parent = Job()
        val entered = CompletableDeferred<Unit>()
        val release = CompletableDeferred<Unit>()
        val manager = heldManager(parent, entered, release)
        try {
            supervisorScope {
                val info = async { manager.getManualConnectionInfo() }
                try {
                    withTimeout(2_000) { entered.await() }
                    parent.cancel()
                    withTimeout(2_000) { manager.state.first { it == NetworkProvisioningState.Closing } }
                    assertFalse(parent.isCompleted)
                    release.complete(Unit)
                    withTimeout(2_000) { parent.join() }
                    assertEquals(NetworkProvisioningState.Closed, manager.state.value)
                    assertFailsWith<NetworkProvisioningError.ManagerClosed> { info.await() }
                } finally {
                    release.complete(Unit)
                }
            }
        } finally {
            release.complete(Unit)
            manager.close()
            parent.cancel()
            parent.join()
        }
    }

    private fun heldManager(
        parent: Job,
        entered: CompletableDeferred<Unit>,
        release: CompletableDeferred<Unit>
    ) = IosManualNetworkProvisioningManager(
        ProvisioningContext(
            appId = AppId("ios-provisioning-bounded-close"),
            localPeerId = PeerId("local"),
            localDeviceName = "synthetic",
            config = NetworkProvisioningConfig(),
            logger = P2pLogger.NoOp,
            lanTcpPort = { 42_000 },
            manualPeerRegistrar = RejectingRegistrar,
            parentJob = parent
        ),
        IosManualProvisioningLifecycleHooks(beforeManualInfoResult = {
            withContext(NonCancellable) {
                entered.complete(Unit)
                release.await()
            }
        }),
        AppleInterfaceAddressScanner { error("terminal work must not proceed to a new scan") }
    )

    @Test
    fun closeIsTerminalIdempotentAndFutureOperationsAreDeterministic() = runBlocking<Unit> {
        val manager = IosManualNetworkProvisioningManager(
            ProvisioningContext(
                appId = AppId("ios-provisioning-close"),
                localPeerId = PeerId("local"),
                localDeviceName = "iPhone",
                config = NetworkProvisioningConfig(),
                logger = P2pLogger.NoOp,
                lanTcpPort = { 42_000 },
                manualPeerRegistrar = RejectingRegistrar
            )
        )
        val credentials = WifiCredentials(
            ssid = "closed",
            password = WifiPassword("closed-password"),
            securityType = WifiSecurityType.WPA2
        )

        manager.close()
        manager.close()

        assertEquals(NetworkProvisioningState.Closed, manager.state.value)
        assertIs<NetworkProvisioningError.ManagerClosed>(
            assertIs<LocalNetworkResult.Failed>(
                manager.startLocalNetwork(LocalNetworkConfig())
            ).error
        )
        assertIs<NetworkProvisioningError.ManagerClosed>(
            assertIs<JoinNetworkResult.Failed>(manager.joinLocalNetwork(credentials)).error
        )
        assertFailsWith<NetworkProvisioningError.ManagerClosed> {
            manager.getManualConnectionInfo()
        }
        manager.stopLocalNetwork()
        assertEquals(NetworkProvisioningState.Closed, manager.state.value)
    }

    @Test
    fun closeCompletesFromCancelledCallerFinallyBlock() = runBlocking<Unit> {
        val manager = IosManualNetworkProvisioningManager(
            ProvisioningContext(
                appId = AppId("ios-provisioning-cancelled-close"),
                localPeerId = PeerId("local"),
                localDeviceName = "iPhone",
                config = NetworkProvisioningConfig(),
                logger = P2pLogger.NoOp,
                lanTcpPort = { 42_000 },
                manualPeerRegistrar = RejectingRegistrar
            )
        )
        val entered = CompletableDeferred<Unit>()
        val caller = launch {
            try {
                entered.complete(Unit)
                awaitCancellation()
            } finally {
                manager.close()
            }
        }
        entered.await()

        caller.cancel()
        caller.join()

        assertEquals(NetworkProvisioningState.Closed, manager.state.value)
    }

    @Test
    fun parentCancellationTerminallyClosesManager() = runBlocking<Unit> {
        val parent = Job()
        val manager = IosManualNetworkProvisioningManager(
            ProvisioningContext(
                appId = AppId("ios-provisioning-parent-close"),
                localPeerId = PeerId("local"),
                localDeviceName = "iPhone",
                config = NetworkProvisioningConfig(),
                logger = P2pLogger.NoOp,
                lanTcpPort = { 42_000 },
                manualPeerRegistrar = RejectingRegistrar,
                parentJob = parent
            )
        )

        parent.cancel()
        parent.join()

        assertEquals(NetworkProvisioningState.Closed, manager.state.value)
        assertIs<NetworkProvisioningError.ManagerClosed>(
            assertIs<LocalNetworkResult.Failed>(
                manager.startLocalNetwork(LocalNetworkConfig())
            ).error
        )
        manager.close()
    }

    @Test
    fun closeCancelsAndJoinsAnActiveManualInfoOperation() = runBlocking<Unit> {
        val operationEntered = CompletableDeferred<Unit>()
        val operationRelease = CompletableDeferred<Unit>()
        val manager = IosManualNetworkProvisioningManager(
            ProvisioningContext(
                appId = AppId("ios-provisioning-active-close"),
                localPeerId = PeerId("local"),
                localDeviceName = "iPhone",
                config = NetworkProvisioningConfig(),
                logger = P2pLogger.NoOp,
                lanTcpPort = { 42_000 },
                manualPeerRegistrar = RejectingRegistrar
            ),
            IosManualProvisioningLifecycleHooks(
                beforeManualInfoResult = {
                    operationEntered.complete(Unit)
                    operationRelease.await()
                }
            )
        )
        supervisorScope {
            val info = async { manager.getManualConnectionInfo() }
            try {
                operationEntered.await()

                manager.close()

                assertFailsWith<NetworkProvisioningError.ManagerClosed> { info.await() }
                assertEquals(NetworkProvisioningState.Closed, manager.state.value)
            } finally {
                operationRelease.complete(Unit)
                manager.close()
            }
        }
    }
}

@OptIn(ExperimentalP2pApi::class)
private object RejectingRegistrar : ManualPeerRegistrar {
    override fun registerManualPeer(
        host: String,
        port: Int,
        kind: TransportKind,
        deviceName: String?,
        expectedFingerprint: PeerFingerprint?
    ): Peer = error("not used")
}
