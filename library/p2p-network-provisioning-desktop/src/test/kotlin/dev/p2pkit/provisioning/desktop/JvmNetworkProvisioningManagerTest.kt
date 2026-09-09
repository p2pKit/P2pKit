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
import dev.p2pkit.core.provisioning.NetworkProvisioningEvent
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
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.supervisorScope
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceTimeBy
import kotlinx.coroutines.test.runCurrent
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.withTimeout
import kotlinx.coroutines.yield
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

class JvmNetworkProvisioningManagerTest {

    private fun ctx(
        lanTcpPort: Int? = 12345,
        registrar: ManualPeerRegistrar = RecordingRegistrar(),
        parentJob: Job? = null,
        localFingerprint: PeerFingerprint? = null,
        localPairingQr: String? = null,
        logger: P2pLogger = P2pLogger.NoOp
    ): ProvisioningContext = ProvisioningContext(
        appId = AppId("jvmnp-test"),
        localPeerId = PeerId("local-id"),
        localDeviceName = "Tester",
        config = NetworkProvisioningConfig(),
        logger = logger,
        lanTcpPort = { lanTcpPort },
        manualPeerRegistrar = registrar,
        localFingerprint = localFingerprint,
        localPairingQr = localPairingQr,
        parentJob = parentJob
    )

    @Test
    @Suppress("DEPRECATION")
    fun manualRegistrationLogsKeepContextWithoutPersistingEndpointOrPin() = runBlocking<Unit> {
        val logger = RecordingProvisioningLogger()
        val manager = JvmNetworkProvisioningManager(ctx(logger = logger), 60_000, { emptyList() })
        val pin = PeerFingerprint("p2f1-${"a".repeat(52)}")
        try {
            manager.createManualPeer("203.0.113.77", 47_561)
            manager.createManualPeer("203.0.113.77", 47_561, pin)
            assertEquals(
                listOf("provisioning: createManualPeer", "provisioning: createManualPeer with authenticated pin"),
                logger.messages
            )
            for (privateValue in listOf("203.0.113.77", "47561", pin.value)) {
                assertTrue(logger.messages.none { privateValue in it })
            }
        } finally {
            manager.close()
        }
    }

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

    @OptIn(ExperimentalCoroutinesApi::class)
    @Test
    fun pollFailureEscalationIsOncePerStreakAndRearmsAfterRecovery() = runTest {
        val failure = IllegalStateException("synthetic enumeration failure")
        val logger = RecordingProvisioningLogger()
        var fail = true
        val manager = JvmNetworkProvisioningManager(
            ctx(logger = logger),
            1_000,
            { if (fail) throw failure else emptyList() },
            StandardTestDispatcher(testScheduler)
        )
        val events = mutableListOf<NetworkProvisioningEvent>()
        backgroundScope.launch(start = CoroutineStart.UNDISPATCHED) {
            manager.events.collect { events += it }
        }
        try {
            runCurrent() // One transient failure is diagnostic-only.
            assertTrue(logger.warnings.isEmpty())
            assertTrue(events.isEmpty())
            fail = false
            advanceTimeBy(1_000)
            runCurrent()
            assertEquals(NetworkState.NoNetwork, manager.networkState.value)
            assertTrue(logger.warnings.isEmpty())

            fail = true
            advanceTimeBy(3_000)
            runCurrent()
            assertEquals(NetworkState.Unknown, manager.networkState.value)
            assertSame(failure, logger.warnings.single())
            assertSame(
                failure,
                assertIs<NetworkProvisioningError.PlatformError>(
                    assertIs<NetworkProvisioningEvent.Failed>(events.single()).error
                ).platformException
            )
            advanceTimeBy(20_000)
            runCurrent()
            assertEquals(1, logger.warnings.size)
            assertEquals(1, events.size)

            fail = false
            advanceTimeBy(1_000)
            runCurrent()
            assertEquals(NetworkState.NoNetwork, manager.networkState.value)
            fail = true
            advanceTimeBy(3_000)
            runCurrent()
            assertEquals(listOf<Throwable?>(failure, failure), logger.warnings)
            assertEquals(2, events.size)
            assertEquals(NetworkProvisioningState.Idle, manager.state.value)
        } finally {
            manager.close()
        }
        val terminalLogs = logger.messages.toList()
        advanceTimeBy(20_000)
        runCurrent()
        assertEquals(terminalLogs, logger.messages, "cancellation must not become a poll failure")
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
        val mgr = JvmNetworkProvisioningManager(
            ctx(registrar = registrar, localFingerprint = PeerFingerprint("p2f1-${"a".repeat(52)}")),
            1_000,
            { emptyList() }
        )
        try {
            val peer = mgr.createManualPeer(host = "192.168.1.42", port = 7777)
            val call = registrar.calls.single()
            assertEquals("192.168.1.42", call.host)
            assertEquals(7777, call.port)
            assertEquals(TransportKind.LAN, call.kind)
            assertNull(call.deviceName)
            assertNull(call.expectedFingerprint, "The deprecated overload must not invent a local-identity pin")
            assertEquals("manual:192.168.1.42:7777", peer.name)
            assertTrue(peer.supportedTransports.contains(TransportKind.LAN))
        } finally {
            mgr.close()
        }
    }

    @Test
    fun createManualPeerWithFingerprintForwardsEachExactRemotePin() = runBlocking<Unit> {
        val registrar = RecordingRegistrar()
        val localFingerprint = PeerFingerprint("p2f1-${"a".repeat(52)}")
        // Repeated calls with distinct pins expose local, constant and stale-pin substitutions.
        val remotePins = listOf(
            PeerFingerprint("p2f1-${"b".repeat(51)}a"),
            PeerFingerprint("p2f1-${"c".repeat(51)}a")
        )
        assertTrue(remotePins.all { it != localFingerprint })
        val mgr = JvmNetworkProvisioningManager(
            ctx(registrar = registrar, localFingerprint = localFingerprint),
            1_000,
            { emptyList() }
        )
        try {
            val peers = withTimeout(1_000) {
                remotePins.map { pin ->
                    mgr.createManualPeer(host = "192.0.2.42", port = 7777, expectedFingerprint = pin)
                }
            }
            assertEquals(
                remotePins.map { pin -> RecordingRegistrar.Call("192.0.2.42", 7777, TransportKind.LAN, null, pin) },
                registrar.calls
            )
            for (peer in peers) {
                assertEquals("manual:192.0.2.42:7777", peer.name)
                assertEquals(setOf(TransportKind.LAN), peer.supportedTransports)
            }
        } finally {
            mgr.close()
        }
    }
}

@OptIn(ExperimentalP2pApi::class)
private class RecordingRegistrar : ManualPeerRegistrar {
    data class Call(
        val host: String,
        val port: Int,
        val kind: TransportKind,
        val deviceName: String?,
        val expectedFingerprint: PeerFingerprint?
    )
    val calls: MutableList<Call> = mutableListOf()

    override fun registerManualPeer(
        host: String,
        port: Int,
        kind: TransportKind,
        deviceName: String?,
        expectedFingerprint: PeerFingerprint?
    ): Peer {
        calls += Call(host, port, kind, deviceName, expectedFingerprint)
        return Peer(
            id = PeerId("manual-$host:$port"),
            name = deviceName ?: "manual:$host:$port",
            platform = Platform.UNKNOWN,
            supportedTransports = setOf(kind)
        )
    }
}

private class RecordingProvisioningLogger : P2pLogger {
    val messages = mutableListOf<String>()
    val warnings = mutableListOf<Throwable?>()
    override fun debug(message: String) { messages += message }
    override fun info(message: String) { messages += message }
    override fun warn(message: String, throwable: Throwable?) {
        messages += message
        warnings += throwable
    }
    override fun error(message: String, throwable: Throwable?) { messages += message }
}
