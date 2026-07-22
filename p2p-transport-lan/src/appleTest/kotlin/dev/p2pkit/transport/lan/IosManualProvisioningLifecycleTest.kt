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
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs

@OptIn(ExperimentalP2pApi::class)
class IosManualProvisioningLifecycleTest {

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
