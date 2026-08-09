@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportHint
import dev.p2pkit.transport.lan.interop.p2pkit_test_bind_tcp_port
import kotlin.concurrent.AtomicInt
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.cancel
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.delay
import kotlinx.coroutines.joinAll
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import platform.posix.sched_yield
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertNotNull
import kotlin.test.assertNotSame
import kotlin.test.assertNull
import kotlin.test.assertTrue

/** Real Network.framework lifecycle regressions for listener/browser recovery. */
class IosLanRecoveryTest {

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

    @Test
    fun cancellingListenerStartClosesCandidateAndAllowsCleanRetry() = runBlocking {
        val transport = IosLanDataTransport(context("start-cancel"), IosEndpointRegistry())
        try {
            val starter = launch(start = CoroutineStart.UNDISPATCHED) {
                transport.start().getOrThrow()
            }
            starter.cancel()
            starter.cancelAndJoin()

            assertTrue(starter.isCancelled)
            assertNull(transport.listener)
            assertNull(transport.tcpPort.value)

            assertTrue(transport.start().isSuccess)
            assertNotNull(transport.listener)
            assertNotNull(transport.tcpPort.value)
        } finally {
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
