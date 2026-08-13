@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.LocalPeerInfo
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportHint
import dev.p2pkit.transport.lan.interop.p2pkit_nw_create_plain_tcp_parameters
import dev.p2pkit.transport.lan.interop.p2pkit_test_bind_tcp_port
import kotlin.concurrent.AtomicInt
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.joinAll
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import platform.Network.nw_connection_cancel
import platform.Network.nw_connection_create
import platform.Network.nw_connection_t
import platform.Network.nw_endpoint_create_host
import platform.posix.sched_yield
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNotSame
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Real Network.framework lifecycle regressions for listener/browser recovery. */
class IosLanRecoveryTest {

    private class ControlledInboundConnection(
        private val nativeConnection: nw_connection_t
    ) : IosConnectionHandle {
        override val state: StateFlow<dev.p2pkit.core.ConnectionState> =
            MutableStateFlow(dev.p2pkit.core.ConnectionState.Connecting)
        var cancelled: Boolean = false
            private set

        override suspend fun write(bytes: ByteArray) = error("not used")
        override fun read(): Flow<ByteArray> = emptyFlow()
        override suspend fun close() = cancelNow("close")

        override fun cancelNow(reason: String) {
            if (cancelled) return
            cancelled = true
            nw_connection_cancel(nativeConnection)
        }
    }

    private fun nativeConnection(): nw_connection_t {
        val parameters = p2pkit_nw_create_plain_tcp_parameters()
            ?: error("p2pkit_nw_create_plain_tcp_parameters returned null")
        val endpoint = nw_endpoint_create_host("127.0.0.1", "9")
            ?: error("nw_endpoint_create_host returned null")
        return nw_connection_create(endpoint, parameters)
            ?: error("nw_connection_create returned null")
    }

    @Test
    fun listenerAndDialParametersEnablePeerToPeerRouting() = runBlocking {
        val data = IosLanDataTransport(context("awdl-params"), IosEndpointRegistry())
        try {
            assertTrue(data.parametersIncludePeerToPeerForTest())
        } finally {
            data.close()
        }
    }

    @Test
    fun browserPolicyIsAwDlCapableAndProhibitsCellular() {
        val parameters = createAppleLanBrowserParameters()

        assertTrue(appleLanBrowserIncludesPeerToPeerForTest(parameters))
        assertTrue(appleLanBrowserProhibitsCellularForTest(parameters))
    }

    @Test
    fun sameInterfaceAddressRotationRequiresRebind() {
        assertTrue(
            applePathNeedsRebind(
                becameSatisfied = false,
                isFirstEver = false,
                interfaceChanged = false,
                addressChanged = true
            )
        )
    }

    @Test
    fun otherInterfaceParticipatesInPathFingerprint() {
        val ordinaryWifi = appleInterfaceFingerprint(
            usesWifi = true,
            usesCellular = false,
            usesWired = false,
            usesOther = false
        )
        val hotspotOrPeerToPeer = appleInterfaceFingerprint(
            usesWifi = true,
            usesCellular = false,
            usesWired = false,
            usesOther = true
        )

        assertFalse(ordinaryWifi == hotspotOrPeerToPeer)
        assertEquals(8, hotspotOrPeerToPeer and 8)
    }

    private fun context(suffix: String): TransportContext = TransportContext(
        appId = AppId("ios-lan-recovery-$suffix"),
        localPeerId = PeerId("ios-lan-recovery-local-$suffix"),
        deviceName = "recovery-$suffix",
        platform = Platform.IOS
    )

    private fun peer(pid: String): InternalPeer = InternalPeer(
        publicPeer = Peer(
            id = PeerId(pid),
            name = "peer-$pid",
            platform = Platform.IOS,
            supportedTransports = setOf(TransportKind.LAN)
        ),
        transportHints = listOf(TransportHint(TransportKind.LAN))
    )

    private fun localPeer(suffix: String): LocalPeerInfo = LocalPeerInfo(
        peerId = PeerId("ios-lan-recovery-local-$suffix"),
        deviceName = "recovery-$suffix",
        platform = Platform.IOS,
        appId = AppId("ios-lan-recovery-$suffix"),
        supportedTransports = setOf(TransportKind.LAN)
    )

    @Test
    fun cancellingListenerStartClosesCandidateAndAllowsCleanRetry() = runBlocking {
        val candidateReady = CompletableDeferred<Unit>()
        val allowOwnershipCommit = CompletableDeferred<Unit>()
        val transport = IosLanDataTransport(
            transportContext = context("start-cancel"),
            endpointRegistry = IosEndpointRegistry(),
            listenerReadyBarrierForTest = {
                candidateReady.complete(Unit)
                allowOwnershipCommit.await()
            }
        )
        try {
            val starter = launch(start = CoroutineStart.UNDISPATCHED) {
                transport.start().getOrThrow()
            }
            withTimeout(RECOVERY_TIMEOUT_MILLIS) { candidateReady.await() }
            starter.cancel()
            starter.cancelAndJoin()

            assertTrue(starter.isCancelled, "the in-flight start must observe caller cancellation")
            assertNull(transport.listener, "a cancelled start must not commit listener ownership")
            assertNull(transport.tcpPort.value, "a cancelled start must depublish its candidate port")

            allowOwnershipCommit.complete(Unit)
            assertTrue(transport.start().isSuccess, "the same transport must retry after cancellation")
            assertNotNull(transport.listener, "the retry must own a live listener")
            assertNotNull(transport.tcpPort.value, "the retry must publish its bound port")
        } finally {
            allowOwnershipCommit.complete(Unit)
            transport.close()
        }
        Unit
    }

    @Test
    fun currentListenerCancellationDepublishesThenRecoversWithoutExternalPathEvent() = runBlocking {
        val transport = IosLanDataTransport(context("listener-failure"), IosEndpointRegistry())
        try {
            assertTrue(transport.start().isSuccess)
            val oldListener = assertNotNull(transport.listener)

            transport.cancelCurrentListenerForTest()

            withTimeout(RECOVERY_TIMEOUT_MILLIS) {
                while (transport.listener === oldListener || transport.tcpPort.value == null) {
                    delay(POLL_MILLIS)
                }
            }
            assertNotSame(oldListener, transport.listener)
            assertNotNull(transport.tcpPort.value)
        } finally {
            transport.close()
        }
        Unit
    }

    @Test
    fun listenerRecoveryClearsEndpointPublishedAtBrowserRetirementBoundary() = runBlocking<Unit> {
        val endpointRegistry = IosEndpointRegistry()
        val transport = IosLanDataTransport(context("retirement-boundary"), endpointRegistry)
        val stalePeer = PeerId("retirement-boundary-stale-peer")
        var hookCalls = 0
        transport.beforeListenerRebind = {
            hookCalls += 1
            endpointRegistry.put(
                stalePeer,
                assertNotNull(nw_endpoint_create_host("127.0.0.1", "43005")),
                browserGeneration = hookCalls
            )
        }
        try {
            assertTrue(transport.start().isSuccess)
            val oldListener = assertNotNull(transport.listener)

            transport.cancelCurrentListenerForTest()

            withTimeout(RECOVERY_TIMEOUT_MILLIS) {
                while (transport.listener === oldListener || transport.tcpPort.value == null) {
                    delay(POLL_MILLIS)
                }
            }
            assertTrue(hookCalls >= 1)
            assertEquals(
                0,
                endpointRegistry.sizeForTest(),
                "the final clear must follow retirement of the old browser callback owner"
            )
        } finally {
            transport.close()
        }
    }

    @Test
    fun closeReleasesTheExactNativeListenerPort() = runBlocking {
        val transport = IosLanDataTransport(context("exact-port"), IosEndpointRegistry())
        assertTrue(transport.start().isSuccess)
        val releasedPort = assertNotNull(transport.tcpPort.value)
        val occupiedV4 = p2pkit_test_bind_tcp_port(releasedPort.toUShort(), false)
        val occupiedV6 = p2pkit_test_bind_tcp_port(releasedPort.toUShort(), true)
        assertTrue(
            occupiedV4 != 0 || occupiedV6 != 0,
            "the live listener must own the exact port in at least one address family"
        )

        transport.close()

        assertEquals(
            0,
            p2pkit_test_bind_tcp_port(releasedPort.toUShort(), false),
            "close must release the exact IPv4 listener port before returning"
        )
        assertEquals(
            0,
            p2pkit_test_bind_tcp_port(releasedPort.toUShort(), true),
            "close must release the exact IPv6 listener port before returning"
        )
        Unit
    }

    @Test
    fun restartableStopReleasesListenerAndSameInstanceStartsAgain() = runBlocking<Unit> {
        val transport = IosLanDataTransport(context("restartable-stop"), IosEndpointRegistry())
        try {
            assertTrue(transport.start().isSuccess)
            assertEquals(3, transport.lifecycleObserverCountForTest)
            val releasedPort = assertNotNull(transport.tcpPort.value)

            transport.stop()
            transport.stop()
            assertNull(transport.listener)
            assertNull(transport.tcpPort.value)
            assertEquals(0, transport.lifecycleObserverCountForTest)
            assertEquals(0, p2pkit_test_bind_tcp_port(releasedPort.toUShort(), false))

            assertTrue(transport.start().isSuccess)
            assertNotNull(transport.listener)
            assertNotNull(transport.tcpPort.value)
            assertEquals(3, transport.lifecycleObserverCountForTest)
        } finally {
            transport.close()
        }
    }

    @Test
    fun restartableStopDoesNotCarryAnInactiveLifecycleEpisodeForward() = runBlocking<Unit> {
        val transport = IosLanDataTransport(
            context("restartable-lifecycle-signals"),
            IosEndpointRegistry()
        )
        try {
            assertTrue(transport.start().isSuccess)
            assertFalse(
                transport.handleLifecycleSignalForTest(AppleLifecycleSignal.WillResignActive)
            )

            transport.stop()
            assertFalse(
                transport.handleLifecycleSignalForTest(AppleLifecycleSignal.DidBecomeActive),
                "stopped transport has no lifecycle callback owner"
            )

            assertTrue(transport.start().isSuccess)
            assertFalse(
                transport.handleLifecycleSignalForTest(AppleLifecycleSignal.WillResignActive)
            )
            assertTrue(
                transport.handleLifecycleSignalForTest(AppleLifecycleSignal.DidBecomeActive),
                "the first inactive episode after restart must schedule recovery"
            )
        } finally {
            transport.close()
        }
    }

    @Test
    fun staleListenerCallbackIsRejectedAndNativeConnectionIsCancelled() = runBlocking<Unit> {
        val rejected = AtomicInt(0)
        var wrapperCreations = 0
        val transport = IosLanDataTransport(
            transportContext = context("stale-inbound"),
            endpointRegistry = IosEndpointRegistry(),
            connectionRejector = { connection ->
                rejected.incrementAndGet()
                nw_connection_cancel(connection)
            },
            connectionFactory = { connection, _ ->
                wrapperCreations += 1
                ControlledInboundConnection(connection)
            }
        )
        try {
            assertTrue(transport.start().isSuccess)
            val staleOwner = assertNotNull(transport.listener)
            transport.stop()
            assertTrue(transport.start().isSuccess)
            assertNotSame(staleOwner, transport.listener)

            assertFalse(
                transport.handleInboundConnectionForTest(staleOwner, nativeConnection())
            )
            assertEquals(1, rejected.value)
            assertEquals(0, wrapperCreations, "a stale callback must not start a wrapper")
        } finally {
            transport.close()
        }
    }

    @Test
    fun currentListenerCallbackTransfersExactlyOneConnection() = runBlocking<Unit> {
        var created: ControlledInboundConnection? = null
        val transport = IosLanDataTransport(
            transportContext = context("current-inbound"),
            endpointRegistry = IosEndpointRegistry(),
            connectionFactory = { connection, _ ->
                ControlledInboundConnection(connection).also { created = it }
            }
        )
        try {
            assertTrue(transport.start().isSuccess)
            val owner = assertNotNull(transport.listener)
            val received = async { transport.incomingConnections().first() }

            assertTrue(transport.handleInboundConnectionForTest(owner, nativeConnection()))
            val accepted = assertNotNull(created)
            assertSame(accepted, withTimeout(RECOVERY_TIMEOUT_MILLIS) { received.await() })
            assertFalse(accepted.cancelled, "consumer owns a successfully transferred connection")
            accepted.close()
        } finally {
            transport.close()
        }
    }

    @Test
    fun connectionWrapperFailureRejectsNativeConnectionWithoutEscapingCallback() =
        runBlocking<Unit> {
            val rejected = AtomicInt(0)
            val transport = IosLanDataTransport(
                transportContext = context("failed-inbound-wrapper"),
                endpointRegistry = IosEndpointRegistry(),
                connectionRejector = { connection ->
                    rejected.incrementAndGet()
                    nw_connection_cancel(connection)
                },
                connectionFactory = { _, _ -> error("synthetic wrapper failure") }
            )
            try {
                assertTrue(transport.start().isSuccess)

                assertFalse(
                    transport.handleInboundConnectionForTest(
                        assertNotNull(transport.listener),
                        nativeConnection()
                    )
                )
                assertEquals(1, rejected.value)
            } finally {
                transport.close()
            }
        }

    @Test
    fun stopWaitsForAdmissionThenDrainsUntransferredConnection() = runBlocking<Unit> {
        val admissionEntered = CompletableDeferred<Unit>()
        val retireAttempted = CompletableDeferred<Unit>()
        val releaseAdmission = AtomicInt(0)
        var created: ControlledInboundConnection? = null
        val transport = IosLanDataTransport(
            transportContext = context("stop-inbound-race"),
            endpointRegistry = IosEndpointRegistry(),
            beforeInboundOfferForTest = {
                admissionEntered.complete(Unit)
                while (releaseAdmission.value == 0) sched_yield()
            },
            beforeInboundRetireForTest = { retireAttempted.complete(Unit) },
            connectionFactory = { connection, _ ->
                ControlledInboundConnection(connection).also { created = it }
            }
        )
        try {
            assertTrue(transport.start().isSuccess)
            val owner = assertNotNull(transport.listener)
            val callback = async(Dispatchers.Default) {
                transport.handleInboundConnectionForTest(owner, nativeConnection())
            }
            admissionEntered.await()
            val stopEntered = CompletableDeferred<Unit>()
            val stopper = launch(Dispatchers.Default) {
                stopEntered.complete(Unit)
                transport.stop()
            }
            stopEntered.await()
            retireAttempted.await()
            assertFalse(
                stopper.isCompleted,
                "stop must wait while the admission transaction owns the boundary"
            )
            releaseAdmission.value = 1

            assertTrue(withTimeout(RECOVERY_TIMEOUT_MILLIS) { callback.await() })
            withTimeout(RECOVERY_TIMEOUT_MILLIS) { stopper.join() }
            assertTrue(
                assertNotNull(created).cancelled,
                "stop must drain ownership that no session consumed"
            )
        } finally {
            releaseAdmission.value = 1
            transport.close()
        }
    }

    @Test
    fun cancelledCallerStillCompletesListenerCleanup() = runBlocking {
        val transport = IosLanDataTransport(context("cancelled-close"), IosEndpointRegistry())
        assertTrue(transport.start().isSuccess)
        val releasedPort = assertNotNull(transport.tcpPort.value)

        val closer = launch(start = CoroutineStart.UNDISPATCHED) {
            coroutineContext.cancel()
            transport.close()
        }
        closer.join()

        assertTrue(closer.isCancelled)
        assertNull(transport.listener)
        assertNull(transport.tcpPort.value)
        assertEquals(0, p2pkit_test_bind_tcp_port(releasedPort.toUShort(), false))
        assertEquals(0, p2pkit_test_bind_tcp_port(releasedPort.toUShort(), true))
    }

    @Test
    fun unexpectedBrowserCancellationCreatesAFreshGeneration() = runBlocking {
        val endpointRegistry = IosEndpointRegistry()
        val data = IosLanDataTransport(context("browser-failure"), endpointRegistry)
        val discovery = IosLanDiscoveryTransport(
            context("browser-failure"),
            endpointRegistry,
            data
        )
        try {
            assertTrue(data.start().isSuccess)
            discovery.startDiscovery()
            val originalGeneration = discovery.browserGenerationForTest
            assertTrue(discovery.hasBrowserForTest)
            endpointRegistry.put(
                PeerId("browser-failure-stale-peer"),
                assertNotNull(
                    platform.Network.nw_endpoint_create_host("127.0.0.1", "43003")
                ),
                browserGeneration = originalGeneration
            )

            discovery.cancelCurrentBrowserForTest()

            withTimeout(RECOVERY_TIMEOUT_MILLIS) {
                while (
                    discovery.browserGenerationForTest <= originalGeneration ||
                    !discovery.hasBrowserForTest
                ) {
                    delay(POLL_MILLIS)
                }
            }
            assertTrue(discovery.browserGenerationForTest > originalGeneration)
            assertTrue(discovery.hasBrowserForTest)
            assertEquals(0, endpointRegistry.sizeForTest())
        } finally {
            discovery.stopDiscovery()
            data.close()
        }
        Unit
    }

    @Test
    fun stopDiscoveryDuringListenerRebindCannotResurrectBrowser() = runBlocking<Unit> {
        val endpointRegistry = IosEndpointRegistry()
        val data = IosLanDataTransport(context("stop-during-rebind"), endpointRegistry)
        val discovery = IosLanDiscoveryTransport(
            context("stop-during-rebind"),
            endpointRegistry,
            data
        )
        try {
            assertTrue(data.start().isSuccess)
            discovery.startDiscovery()
            assertTrue(discovery.hasBrowserForTest)

            discovery.beforeListenerRebindForTest()
            assertFalse(discovery.hasBrowserForTest)
            discovery.stopDiscovery()
            discovery.afterListenerRebindForTest(assertNotNull(data.listener))

            assertFalse(
                discovery.hasBrowserForTest,
                "revoked host intent must win over a saved pre-rebind restore request"
            )
        } finally {
            discovery.stopDiscovery()
            data.close()
        }
    }

    @Test
    fun startDiscoveryDuringListenerRebindDoesNotCreateSecondBrowser() = runBlocking<Unit> {
        val endpointRegistry = IosEndpointRegistry()
        val data = IosLanDataTransport(context("start-during-rebind"), endpointRegistry)
        val discovery = IosLanDiscoveryTransport(
            context("start-during-rebind"),
            endpointRegistry,
            data
        )
        try {
            assertTrue(data.start().isSuccess)
            discovery.beforeListenerRebindForTest()

            discovery.startDiscovery()
            assertTrue(discovery.hasBrowserForTest)
            assertEquals(1, discovery.browserGenerationForTest)

            discovery.afterListenerRebindForTest(assertNotNull(data.listener))

            assertTrue(discovery.hasBrowserForTest)
            assertEquals(
                1,
                discovery.browserGenerationForTest,
                "the interleaving must create exactly one native browser generation"
            )
        } finally {
            discovery.stopDiscovery()
            data.close()
        }
    }

    @Test
    fun listenerRebindCancelsNudgeOwnedByRetiringListener() = runBlocking<Unit> {
        val endpointRegistry = IosEndpointRegistry()
        val data = IosLanDataTransport(context("rebind-nudge"), endpointRegistry)
        val discovery = IosLanDiscoveryTransport(context("rebind-nudge"), endpointRegistry, data)
        try {
            assertTrue(data.start().isSuccess)
            discovery.startAdvertising(localPeer("rebind-nudge"))
            discovery.afterListenerRebindForTest(assertNotNull(data.listener))
            assertTrue(discovery.hasPendingNudgeForTest)

            discovery.beforeListenerRebindForTest()

            assertFalse(
                discovery.hasPendingNudgeForTest,
                "a retired listener must not receive delayed descriptor mutations"
            )
        } finally {
            discovery.stopAdvertising()
            data.close()
        }
    }

    @Test
    fun stopAdvertisingCancelsPendingBonjourNudge() = runBlocking<Unit> {
        val endpointRegistry = IosEndpointRegistry()
        val data = IosLanDataTransport(context("stop-nudge"), endpointRegistry)
        val discovery = IosLanDiscoveryTransport(context("stop-nudge"), endpointRegistry, data)
        try {
            assertTrue(data.start().isSuccess)
            discovery.startAdvertising(localPeer("stop-nudge"))
            discovery.afterListenerRebindForTest(assertNotNull(data.listener))
            assertTrue(discovery.hasPendingNudgeForTest)

            discovery.stopAdvertising()

            assertFalse(discovery.hasPendingNudgeForTest)
        } finally {
            discovery.stopAdvertising()
            data.close()
        }
    }

    @Test
    fun newBrowserGenerationInvalidatesOpaqueEndpointsBeforeFreshResults() {
        val endpointRegistry = IosEndpointRegistry()
        val data = IosLanDataTransport(context("endpoint-generation"), endpointRegistry)
        val discovery = IosLanDiscoveryTransport(
            context("endpoint-generation"),
            endpointRegistry,
            data
        )
        val peerId = PeerId("endpoint-generation-remote")
        val endpoint = platform.Network.nw_endpoint_create_host("127.0.0.1", "43001")
        endpointRegistry.put(
            peerId,
            assertNotNull(endpoint),
            browserGeneration = 1
        )
        assertEquals(1, endpointRegistry.sizeForTest())

        discovery.beginBrowserGenerationForTest()

        assertEquals(0, endpointRegistry.sizeForTest())
        assertEquals(1, discovery.browserGenerationForTest)
    }

    @Test
    fun listenerRebindRetirementInvalidatesAllOldBrowserEndpoints() = runBlocking<Unit> {
        val endpointRegistry = IosEndpointRegistry()
        val data = IosLanDataTransport(context("retire-endpoint"), endpointRegistry)
        val discovery = IosLanDiscoveryTransport(context("retire-endpoint"), endpointRegistry, data)
        val peerId = PeerId("retire-endpoint-remote")
        try {
            assertTrue(data.start().isSuccess)
            endpointRegistry.put(
                peerId,
                assertNotNull(nw_endpoint_create_host("127.0.0.1", "43004")),
                browserGeneration = 1
            )

            discovery.beforeListenerRebindForTest()

            assertEquals(
                0,
                endpointRegistry.sizeForTest(),
                "browser retirement and endpoint invalidation are one ownership transaction"
            )
        } finally {
            data.close()
        }
    }

    @Test
    fun stalePruneCannotDeleteAConcurrentFreshRediscovery() = runBlocking {
        val endpointRegistry = IosEndpointRegistry()
        val data = IosLanDataTransport(context("cache-race"), endpointRegistry)
        val discovery = IosLanDiscoveryTransport(context("cache-race"), endpointRegistry, data)
        try {
            val pid = "cache-race-peer"
            val stale = peer(pid)
            val fresh = stale.copy(publicPeer = stale.publicPeer.copy(name = "fresh"))
            val eventOrder = mutableListOf<String>()
            val pruneEntered = CompletableDeferred<Unit>()
            val allowPruneToFinish = AtomicInt(0)

            discovery.confirmAnnounceEntryAtomically(
                pid,
                AnnounceEntry(stale, lastConfirmedGeneration = 1)
            )

            val prune = launch(Dispatchers.Default) {
                discovery.reconcileAnnounceCacheAtomically(
                    currentGeneration = 2,
                    graceTicks = 1,
                    onLost = {
                        eventOrder += "lost"
                        pruneEntered.complete(Unit)
                        while (allowPruneToFinish.value == 0) sched_yield()
                    }
                )
            }
            pruneEntered.await()

            val confirmationAttempted = CompletableDeferred<Unit>()
            val confirm = launch(Dispatchers.Default) {
                confirmationAttempted.complete(Unit)
                discovery.confirmAnnounceEntryAtomically(
                    pid,
                    AnnounceEntry(fresh, lastConfirmedGeneration = 2),
                    onConfirmed = { eventOrder += "found" }
                )
            }
            confirmationAttempted.await()
            allowPruneToFinish.value = 1
            joinAll(prune, confirm)

            val retained = assertNotNull(discovery.announceEntryForTest(pid))
            assertEquals(2, retained.lastConfirmedGeneration)
            assertEquals("fresh", retained.peer.publicPeer.name)
            assertEquals(listOf("lost", "found"), eventOrder)
        } finally {
            discovery.stopDiscovery()
            data.close()
        }
    }

    private companion object {
        const val POLL_MILLIS: Long = 10
        const val RECOVERY_TIMEOUT_MILLIS: Long = 8_000
    }
}
