package dev.p2pkit.core.internal

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ExperimentalP2pApi
import dev.p2pkit.core.NetworkProvisioningError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.provisioning.JoinNetworkResult
import dev.p2pkit.core.provisioning.LocalNetworkConfig
import dev.p2pkit.core.provisioning.LocalNetworkResult
import dev.p2pkit.core.provisioning.ManualConnectionInfo
import dev.p2pkit.core.provisioning.NetworkProvisioningEvent
import dev.p2pkit.core.provisioning.NetworkProvisioningFactory
import dev.p2pkit.core.provisioning.NetworkProvisioningManager
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.provisioning.ProvisioningContext
import dev.p2pkit.core.provisioning.UnsupportedNetworkProvisioningManager
import dev.p2pkit.core.provisioning.WifiCredentials
import dev.p2pkit.core.provisioning.WifiPassword
import dev.p2pkit.core.provisioning.WifiSecurityType
import dev.p2pkit.core.testfixtures.createTestKit
import dev.p2pkit.core.transport.DataTransport
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportFactory
import dev.p2pkit.core.transport.TransportPair
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs

@OptIn(ExperimentalP2pApi::class)
class NetworkProvisioningCloseTest {

    private val credentials = WifiCredentials(
        ssid = "closed",
        password = WifiPassword("closed-password"),
        securityType = WifiSecurityType.WPA2
    )

    @Test
    fun unsupportedManagerCloseIsTerminalAndIdempotent() = runBlocking<Unit> {
        val manager = UnsupportedNetworkProvisioningManager()

        val unsupported = assertIs<LocalNetworkResult.Unsupported>(
            manager.startLocalNetwork(LocalNetworkConfig())
        )
        assertEquals(
            "No network provisioning implementation is registered. Add the platform module and configure " +
                "android(...), jvm(), or iosManualIp().",
            unsupported.reason
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
    fun kitStopClosesProvisioningBeforeDataTransport() = runBlocking<Unit> {
        val events = mutableListOf<String>()
        val manager = RecordingProvisioningManager(events)
        val data = RecordingDataTransport(events)
        val kit = createTestKit {
            appId = AppId("provisioning-close-order")
            deviceName = "close-order"
            transports { register(RecordingTransportFactory(data)) }
            networkProvisioning { register(RecordingProvisioningFactory(manager)) }
        }

        kit.stop()

        assertEquals(listOf("provisioning.close", "transport.close"), events)
        assertEquals(NetworkProvisioningState.Closed, manager.state.value)
    }

    @Test
    fun unsupportedCloseCompletesFromCancelledCallerFinallyBlock() = runBlocking<Unit> {
        val manager = UnsupportedNetworkProvisioningManager()
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
}

private class RecordingProvisioningFactory(
    private val manager: NetworkProvisioningManager
) : NetworkProvisioningFactory {
    override fun build(context: ProvisioningContext): NetworkProvisioningManager = manager
}

@OptIn(ExperimentalP2pApi::class)
private class RecordingProvisioningManager(
    private val eventsLog: MutableList<String>
) : NetworkProvisioningManager {
    private val mutableState = MutableStateFlow<NetworkProvisioningState>(NetworkProvisioningState.Idle)
    override val state: StateFlow<NetworkProvisioningState> = mutableState
    override val networkState: StateFlow<NetworkState> = MutableStateFlow(NetworkState.Unknown)
    override val events: Flow<NetworkProvisioningEvent> = emptyFlow()

    override suspend fun startLocalNetwork(config: LocalNetworkConfig): LocalNetworkResult =
        LocalNetworkResult.Unsupported("test")

    override suspend fun stopLocalNetwork() = Unit

    override suspend fun joinLocalNetwork(credentials: WifiCredentials): JoinNetworkResult =
        JoinNetworkResult.Unsupported("test")

    override suspend fun getManualConnectionInfo(): ManualConnectionInfo? = null

    @Deprecated("test-only implementation of the legacy overload")
    override suspend fun createManualPeer(host: String, port: Int): Peer = error("not used")

    override suspend fun createManualPeer(
        host: String,
        port: Int,
        expectedFingerprint: PeerFingerprint
    ): Peer = error("not used")

    override suspend fun close() {
        eventsLog += "provisioning.close"
        mutableState.value = NetworkProvisioningState.Closed
    }
}

private class RecordingDataTransport(
    private val eventsLog: MutableList<String>
) : DataTransport {
    private val incoming = Channel<RawConnection>(Channel.UNLIMITED)
    override val type: TransportKind = TransportKind.LAN
    override val priority: Int = 100
    override suspend fun stop() = Unit
    override fun canConnect(peer: InternalPeer): Boolean = false
    override suspend fun connect(peer: InternalPeer): RawConnection = error("not used")
    override fun incomingConnections(): Flow<RawConnection> = incoming.receiveAsFlow()

    override suspend fun close() {
        eventsLog += "transport.close"
        incoming.close()
    }
}

private class RecordingTransportFactory(
    private val data: DataTransport
) : TransportFactory {
    override val descriptor =
        dev.p2pkit.core.transport.TransportDescriptor.dataOnly(data.type)
    override fun build(context: TransportContext): TransportPair = TransportPair(data = data)
}
