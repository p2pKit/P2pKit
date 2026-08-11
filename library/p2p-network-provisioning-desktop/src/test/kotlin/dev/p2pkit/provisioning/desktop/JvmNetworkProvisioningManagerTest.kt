@file:OptIn(dev.p2pkit.core.ExperimentalP2pApi::class)

package dev.p2pkit.provisioning.desktop

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
import dev.p2pkit.core.provisioning.NetworkProvisioningState
import dev.p2pkit.core.provisioning.NetworkState
import dev.p2pkit.core.provisioning.ProvisioningContext
import dev.p2pkit.core.provisioning.WifiCredentials
import dev.p2pkit.core.provisioning.WifiPassword
import dev.p2pkit.core.provisioning.WifiSecurityType
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.yield
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class JvmNetworkProvisioningManagerTest {

    private fun ctx(
        lanTcpPort: Int? = 12345,
        registrar: ManualPeerRegistrar = RecordingRegistrar(),
        parentJob: Job? = null,
        localFingerprint: PeerFingerprint? = null,
        localPairingQr: String? = null
    ): ProvisioningContext = ProvisioningContext(
        appId = AppId("jvmnp-test"),
        localPeerId = PeerId("local-id"),
        localDeviceName = "Tester",
        config = NetworkProvisioningConfig(),
        logger = P2pLogger.NoOp,
        lanTcpPort = { lanTcpPort },
        manualPeerRegistrar = registrar,
        localFingerprint = localFingerprint,
        localPairingQr = localPairingQr,
        parentJob = parentJob
    )

    @Test
    fun startLocalNetworkReturnsUnsupported() = runBlocking<Unit> {
        val mgr = JvmNetworkProvisioningManager(ctx())
        try {
            val result = mgr.startLocalNetwork(LocalNetworkConfig())
            assertIs<LocalNetworkResult.Unsupported>(result)
        } finally {
            mgr.close()
        }
    }

    @Test
    fun pollIntervalMustBePositive() {
        assertFailsWith<IllegalArgumentException> { JvmNetworkProvisioningManager(ctx(), 0) }
        assertFailsWith<IllegalArgumentException> { JvmNetworkProvisioningManager(ctx(), -1) }
    }

    @Test
    fun joinLocalNetworkReturnsUnsupported() = runBlocking<Unit> {
        val mgr = JvmNetworkProvisioningManager(ctx())
        try {
            val result = mgr.joinLocalNetwork(
                WifiCredentials(
                    ssid = "X",
                    password = WifiPassword("p"),
                    securityType = WifiSecurityType.WPA2
                )
            )
            assertIs<JoinNetworkResult.Unsupported>(result)
        } finally {
            mgr.close()
        }
    }

    @Test
    fun manualConnectionInfoReturnsNullWhenLanPortMissing() = runBlocking<Unit> {
        val mgr = JvmNetworkProvisioningManager(ctx(lanTcpPort = null))
        try {
            assertNull(mgr.getManualConnectionInfo())
        } finally {
            mgr.close()
        }
    }

    @Test
    fun manualConnectionInfoCarriesIdentityAndPortWhenPresent() = runBlocking<Unit> {
        val fingerprint = PeerFingerprint("p2f1-${"a".repeat(52)}")
        val mgr = JvmNetworkProvisioningManager(
            ctx(
                lanTcpPort = 54_321,
                localFingerprint = fingerprint,
                localPairingQr = "p2pkit-v2:test-pairing-qr"
            ),
            1_000,
            { listOf("192.168.1.42", "10.0.0.42") }
        )
        try {
            val info = mgr.getManualConnectionInfo()
            assertNotNull(info)
            assertEquals(54_321, info.port)
            assertEquals(AppId("jvmnp-test"), info.appId)
            assertEquals(PeerId("local-id"), info.peerId)
            assertEquals("Tester", info.deviceName)
            assertEquals(listOf("192.168.1.42", "10.0.0.42"), info.hostAddresses)
            assertEquals(fingerprint, info.fingerprint)
            assertEquals("p2pkit-v2:test-pairing-qr", info.pairingQr)
        } finally {
            mgr.close()
        }
    }

    @Test
    fun manualConnectionInfoReturnsNullWhenScannerFindsNoUsableAddress() = runBlocking<Unit> {
        val mgr = JvmNetworkProvisioningManager(ctx(), 1_000, { emptyList() })
        try {
            assertNull(mgr.getManualConnectionInfo())
        } finally {
            mgr.close()
        }
    }

    @Test
    fun fatalScannerErrorsAreNotConvertedToNoNetwork() = runBlocking<Unit> {
        val fatal = AssertionError("fatal scanner failure")
        val calls = AtomicInteger()
        val mgr = JvmNetworkProvisioningManager(
            ctx(),
            1_000,
            {
                if (calls.incrementAndGet() == 1) emptyList() else throw fatal
            }
        )
        try {
            withTimeout(1_000) {
                while (calls.get() == 0) yield()
            }
            val observed = assertFailsWith<AssertionError> { mgr.getManualConnectionInfo() }
            assertEquals(fatal.message, observed.message)
        } finally {
            mgr.close()
        }
    }

    @Test
    fun pollingRecoversAfterRecoverableScannerFailure() = runBlocking<Unit> {
        val calls = AtomicInteger()
        val mgr = JvmNetworkProvisioningManager(
            ctx(),
            1,
            {
                if (calls.incrementAndGet() == 1) {
                    throw IllegalStateException("transient interface enumeration failure")
                }
                listOf("192.168.1.42")
            }
        )
        try {
            val recovered = withTimeout(2_000) {
                mgr.networkState.first { it is NetworkState.ConnectedToWifi }
            }
            assertEquals(
                listOf("192.168.1.42"),
                assertIs<NetworkState.ConnectedToWifi>(recovered).localIpAddresses
            )
            assertTrue(calls.get() >= 2)
        } finally {
            mgr.close()
        }
    }

    @Test
    fun parentCancellationTerminallyClosesManager() = runBlocking<Unit> {
        val parent = Job()
        val mgr = JvmNetworkProvisioningManager(
            ctx(parentJob = parent),
            1_000,
            { emptyList() }
        )

        parent.cancel()
        parent.join()

        assertEquals(NetworkProvisioningState.Closed, mgr.state.value)
        assertIs<NetworkProvisioningError.ManagerClosed>(
            assertIs<LocalNetworkResult.Failed>(
                mgr.startLocalNetwork(LocalNetworkConfig())
            ).error
        )
        mgr.close()
    }

    @Test
    fun closeIsTerminalIdempotentAndFutureOperationsAreDeterministic() = runBlocking<Unit> {
        val mgr = JvmNetworkProvisioningManager(ctx(), 1_000, { emptyList() })

        mgr.close()
        mgr.close()

        assertEquals(NetworkProvisioningState.Closed, mgr.state.value)
        assertIs<NetworkProvisioningError.ManagerClosed>(
            assertIs<LocalNetworkResult.Failed>(
                mgr.startLocalNetwork(LocalNetworkConfig())
            ).error
        )
        assertIs<NetworkProvisioningError.ManagerClosed>(
            assertIs<JoinNetworkResult.Failed>(
                mgr.joinLocalNetwork(
                    WifiCredentials(
                        ssid = "closed",
                        password = WifiPassword("closed-password"),
                        securityType = WifiSecurityType.WPA2
                    )
                )
            ).error
        )
        assertFailsWith<NetworkProvisioningError.ManagerClosed> {
            mgr.getManualConnectionInfo()
        }
        mgr.stopLocalNetwork()
        assertEquals(NetworkProvisioningState.Closed, mgr.state.value)
    }

    @Test
    fun closeFromCancelledCallerFinallyBlockStillCompletes() = runBlocking<Unit> {
        val mgr = JvmNetworkProvisioningManager(ctx(), 1_000, { emptyList() })
        val entered = CompletableDeferred<Unit>()
        val caller = launch {
            try {
                entered.complete(Unit)
                awaitCancellation()
            } finally {
                mgr.close()
            }
        }
        entered.await()

        caller.cancel()
        caller.join()

        assertEquals(NetworkProvisioningState.Closed, mgr.state.value)
    }

    @Test
    fun closeWaitsForActiveManualInfoScanAndSuppressesItsLateResult() = runBlocking<Unit> {
        val calls = AtomicInteger()
        val scanEntered = CountDownLatch(1)
        val scanRelease = CountDownLatch(1)
        val mgr = JvmNetworkProvisioningManager(
            ctx(),
            60_000,
            {
                if (calls.incrementAndGet() == 1) {
                    emptyList()
                } else {
                    scanEntered.countDown()
                    check(scanRelease.await(2, TimeUnit.SECONDS)) {
                        "test did not release the active address scan"
                    }
                    listOf("192.168.1.42")
                }
            }
        )
        withTimeout(2_000) {
            while (calls.get() == 0) yield()
        }

        supervisorScope {
            val info = async(Dispatchers.Default) { mgr.getManualConnectionInfo() }
            try {
                assertTrue(scanEntered.await(2, TimeUnit.SECONDS), "manual-info scan did not start")
                val closing = async(Dispatchers.Default) { mgr.close() }
                withTimeout(2_000) {
                    mgr.state.first { it == NetworkProvisioningState.Closing }
                }
                assertTrue(closing.isActive, "close must join the active manager-owned operation")

                scanRelease.countDown()
                assertFailsWith<NetworkProvisioningError.ManagerClosed> { info.await() }
                withTimeout(2_000) { closing.await() }
                assertEquals(NetworkProvisioningState.Closed, mgr.state.value)
            } finally {
                scanRelease.countDown()
                mgr.close()
            }
        }
    }

    @Test
    fun addressSelectionDropsInactiveAndLinkLocalCandidates() {
        assertEquals(
            listOf("192.168.1.20", "172.16.0.20", "2001:db8::20", "192.0.2.20"),
            selectUsableNetworkAddresses(
                listOf(
                    NetworkAddressCandidate("169.254.1.20", true, linkLocal = true, siteLocal = false),
                    NetworkAddressCandidate("192.168.1.20", true, linkLocal = false, siteLocal = true),
                    NetworkAddressCandidate("10.0.0.20", false, linkLocal = false, siteLocal = true),
                    NetworkAddressCandidate("172.16.0.20", true, linkLocal = false, siteLocal = true),
                    NetworkAddressCandidate("2001:db8::20", true, linkLocal = false, siteLocal = false),
                    NetworkAddressCandidate("192.0.2.20", true, linkLocal = false, siteLocal = false)
                )
            )
        )
    }

    @OptIn(ExperimentalP2pApi::class)
    @Suppress("DEPRECATION")
    @Test
    fun createManualPeerDelegatesToRegistrar() = runBlocking<Unit> {
        val registrar = RecordingRegistrar()
        val mgr = JvmNetworkProvisioningManager(ctx(registrar = registrar))
        try {
            val peer = mgr.createManualPeer(host = "192.168.1.42", port = 7777)
            assertEquals("192.168.1.42", registrar.calls.single().host)
            assertEquals(7777, registrar.calls.single().port)
            assertEquals(TransportKind.LAN, registrar.calls.single().kind)
            assertEquals("manual:192.168.1.42:7777", peer.name)
            assertTrue(peer.supportedTransports.contains(TransportKind.LAN))
        } finally {
            mgr.close()
        }
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
