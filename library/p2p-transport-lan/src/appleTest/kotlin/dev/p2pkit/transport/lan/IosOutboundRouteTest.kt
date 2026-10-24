@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.OutboundRouteConnection
import dev.p2pkit.core.transport.OutboundRouteUnavailable
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportHint
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import platform.Network.nw_connection_cancel
import platform.Network.nw_connection_t
import platform.Network.nw_endpoint_create_bonjour_service
import platform.Network.nw_endpoint_create_host
import kotlin.test.Test
import kotlin.test.assertContentEquals
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

class IosOutboundRouteTest {
    @Test
    fun realNativeHostnameConnectionCapturesEffectiveNumericRouteAndReplaysAfterCacheChurn() = runBlocking<Unit> {
        withTestResourceCleanup { cleanup ->
            val server = IosLanDataTransport(context("server"), IosEndpointRegistry())
            cleanup.own { server.close() }
            server.start().getOrThrow()
            val port = assertNotNull(server.tcpPort.value)
            val registry = IosEndpointRegistry()
            val peer = peer("native-loopback").copy(transportHints = emptyList())
            val hostname = assertNotNull(nw_endpoint_create_host("localhost", port.toString()))
            assertNull(appleNumericEndpoint(hostname), "original hostname is not numeric routing evidence")
            assertNotNull(registry.put(peer.publicPeer.id, hostname, 1))
            val observed = mutableListOf<LanTcpEndpoint?>()
            val clientConnections = mutableListOf<IosConnectionHandle>()
            val clientContext = context("client")
            val client = IosLanDataTransport(
                clientContext, registry,
                connectionFactory = { connection, queue ->
                    IosRawConnection.wrap(connection, queue).also(clientConnections::add)
                },
                outboundEndpointProvider = { connection -> appleConnectedEndpoint(connection).also(observed::add) }
            )
            cleanup.own { client.close() }
            val firstIncoming = async(Dispatchers.Default) { server.incomingConnections().first() }
            cleanup.own { firstIncoming.cancel(); firstIncoming.join() }
            val original = withTimeout(TEST_TIMEOUT_MILLIS) { client.connect(peer) }
            cleanup.own { original.close() }
            val firstAccepted = withTimeout(TEST_TIMEOUT_MILLIS) { firstIncoming.await() }
            cleanup.own { firstAccepted.close() }
            assertNull((firstAccepted as? OutboundRouteConnection)?.outboundRoute)
            val route = assertNotNull(assertIs<OutboundRouteConnection>(original).outboundRoute)
            assertSame(client, route.transport)
            val originalNumeric = assertNotNull(observed.single(), "must observe an actual effective NWPath endpoint")
            assertEquals(port, originalNumeric.port)
            original.write(byteArrayOf(37))
            assertContentEquals(byteArrayOf(37), withTimeout(TEST_TIMEOUT_MILLIS) { firstAccepted.read().first() })
            original.close()
            firstAccepted.close()

            // Real admission/relay/endpoint collections, with only DNS callbacks controlled (not multicast proof).
            // Starting a discovery generation removes the original hostname lease before every slot is occupied.
            val dns = FakeIosLanTxtDns()
            val discovery = IosLanDiscoveryTransport(clientContext, registry, client, dns)
            cleanup.own {
                discovery.stopDiscovery()
                assertEquals(0, discovery.txtQueryCountForTest)
                assertEquals(0, discovery.txtReservedQueryCountForTest)
                assertEquals(0, discovery.txtRetainedBytesForTest)
                dns.references.forEach { reference ->
                    assertTrue(reference.deallocated && reference.disposed)
                }
            }
            discovery.startDiscovery()
            val occupantIds = (0 until MAX_TRACKED_LAN_PEERS).map { PeerId("occupant-$it") }.toSet()
            occupantIds.forEach { id ->
                val endpoint = assertNotNull(
                    nw_endpoint_create_bonjour_service(id.value, clientContext.lanServiceTypeBonjour, "local.")
                )
                assertNotNull(discovery.txtServiceForTest(endpoint, discovery.browserGenerationForTest))
                val properties = buildLanTxtProperties(
                    id, clientContext.appId, "Occupant", Platform.IOS, setOf(TransportKind.LAN),
                    LanConstants.protocolVersion(clientContext.securityProfile), clientContext.localFingerprint
                ).mapValues { (_, value) -> value.encodeToByteArray() }
                dns.references.last().answer(LanTxtRecordFixtures.encode(properties.toList()))
                assertNotNull(discovery.announceEntryForTest(id.value))
            }
            assertEquals(MAX_TRACKED_LAN_PEERS, discovery.txtQueryCountForTest)
            assertEquals(MAX_TRACKED_LAN_PEERS, discovery.txtReservedQueryCountForTest)
            assertEquals(MAX_TRACKED_LAN_PEERS, registry.sizeForTest())
            val replacement = assertNotNull(
                nw_endpoint_create_bonjour_service(
                    peer.publicPeer.id.value, clientContext.lanServiceTypeBonjour, "local."
                )
            )
            assertNull(discovery.txtServiceForTest(replacement, discovery.browserGenerationForTest))
            assertEquals(MAX_TRACKED_LAN_PEERS, dns.references.size, "capacity rejection must not allocate a query")
            assertNull(registry.put(peer.publicPeer.id, replacement, discovery.browserGenerationForTest))
            assertNull(registry.lease(peer.publicPeer.id))
            assertFalse(client.canConnect(peer), "ordinary discovery no longer offers the original route")
            val retained = withTimeout(TEST_TIMEOUT_MILLIS) {
                discovery.events.take(MAX_TRACKED_LAN_PEERS).toList()
            }
            assertEquals(occupantIds, retained.map { assertIs<PeerEvent.Found>(it).peer.publicPeer.id }.toSet())
            val secondIncoming = async(Dispatchers.Default) { server.incomingConnections().first() }
            cleanup.own { secondIncoming.cancel(); secondIncoming.join() }
            val replay = withTimeout(TEST_TIMEOUT_MILLIS) { route.connect(1_500) }
            cleanup.own { replay.close() }
            val secondAccepted = withTimeout(TEST_TIMEOUT_MILLIS) { secondIncoming.await() }
            cleanup.own { secondAccepted.close() }
            assertEquals(listOf(originalNumeric, originalNumeric), observed)
            assertSame(route, assertIs<OutboundRouteConnection>(replay).outboundRoute)
            replay.write(byteArrayOf(42))
            assertContentEquals(byteArrayOf(42), withTimeout(TEST_TIMEOUT_MILLIS) { secondAccepted.read().first() })
            assertEquals(MAX_TRACKED_LAN_PEERS, registry.sizeForTest())
            assertEquals(MAX_TRACKED_LAN_PEERS, discovery.txtQueryCountForTest)
            assertNull(registry.lease(peer.publicPeer.id), "route replay cannot consume a discovery slot")
            replay.close()
            secondAccepted.close()
            server.stop()
            assertFailsWith<OutboundRouteUnavailable> {
                withTimeout(TEST_TIMEOUT_MILLIS) { route.connect(1_500) }
            }
            assertEquals(3, clientConnections.size)
            assertTrue(withTimeout(TEST_TIMEOUT_MILLIS) { clientConnections.last().awaitNativeRetirement() })
        }
    }

    @Test
    fun unsupportedOrThrowingObservationPreservesOrdinaryRawIdentity() = runBlocking<Unit> {
        for (throws in listOf(false, true)) {
            withTestResourceCleanup { cleanup ->
                lateinit var controlled: ControlledConnection
                val transport = IosLanDataTransport(
                    context("unsupported"), IosEndpointRegistry(),
                    connectionFactory = { connection, _ -> ControlledConnection(connection).also { controlled = it } },
                    outboundEndpointProvider = { if (throws) error("observation unavailable") else null }
                )
                cleanup.own { transport.close() }
                val raw = transport.connect(peer())
                cleanup.own { raw.close() }
                assertSame(controlled, raw)
                assertEquals(ConnectionState.Connected, raw.state.value)
                assertNull((raw as? OutboundRouteConnection)?.outboundRoute)
            }
        }
    }

    @Test
    fun controlledRequiredInterfaceIndexChangeRefusesBeforeNativeConnectionAllocation() = runBlocking<Unit> {
        withTestResourceCleanup { cleanup ->
            var interfaceIndex: Int? = 7
            var allocations = 0
            val transport = IosLanDataTransport(
                context("required-interface"), IosEndpointRegistry(),
                connectionFactory = { connection, _ -> allocations++; ControlledConnection(connection) },
                outboundEndpointProvider = { numericEndpoint() },
                outboundInterfaceIndexForTest = { interfaceIndex }
            )
            cleanup.own { transport.close() }
            val raw = transport.connect(peer())
            cleanup.own { raw.close() }
            val route = assertNotNull(assertIs<OutboundRouteConnection>(raw).outboundRoute)
            raw.close()
            for (changed in listOf(8, null)) {
                interfaceIndex = changed
                assertFailsWith<OutboundRouteUnavailable> { route.connect(500) }
                assertEquals(1, allocations, "index/name reuse or missing context must not create a connection")
            }
        }
    }

    @Test
    fun controlledIndexChangeAtPendingAdmissionOrHandoffRequiresObservedRetirement() = runBlocking<Unit> {
        for (beforeAdmission in listOf(true, false)) {
            withTestResourceCleanup { cleanup ->
                var interfaceIndex = 7
                val handles = mutableListOf<ControlledConnection>()
                val transport = IosLanDataTransport(
                    context("required-interface-race"), IosEndpointRegistry(),
                    connectionFactory = { connection, _ ->
                        ControlledConnection(connection).also { handle ->
                            handles += handle
                            if (handles.size == 2 && beforeAdmission) interfaceIndex = 8
                        }
                    },
                    beforeDialOwnershipHandoffForTest = {
                        if (handles.size == 2 && !beforeAdmission) interfaceIndex = 8
                    },
                    outboundEndpointProvider = { numericEndpoint() },
                    outboundInterfaceIndexForTest = { interfaceIndex }
                )
                cleanup.own { transport.close() }
                val raw = transport.connect(peer())
                cleanup.own { raw.close() }
                val route = assertNotNull(assertIs<OutboundRouteConnection>(raw).outboundRoute)
                raw.close()
                assertFailsWith<OutboundRouteUnavailable> { route.connect(500) }
                assertEquals(2, handles.size)
                assertTrue(handles.last().cancelled)
                assertEquals(1, handles.last().retirementObservations)
            }
        }
    }

    @Test
    fun missingRequiredInterfaceObservationPreservesSuccessfulRawWithoutCapability() = runBlocking<Unit> {
        withTestResourceCleanup { cleanup ->
            lateinit var controlled: ControlledConnection
            val transport = IosLanDataTransport(
                context("missing-required-interface"), IosEndpointRegistry(),
                connectionFactory = { connection, _ -> ControlledConnection(connection).also { controlled = it } },
                outboundEndpointProvider = { numericEndpoint() },
                outboundInterfaceIndexForTest = { null }
            )
            cleanup.own { transport.close() }
            val raw = transport.connect(peer())
            cleanup.own { raw.close() }
            assertSame(controlled, raw)
            assertEquals(ConnectionState.Connected, raw.state.value)
            assertNull((raw as? OutboundRouteConnection)?.outboundRoute)
        }
    }

    @Test
    fun cancellationThrownByOptionalObservationIsNotTreatedAsUnsupported() = runBlocking<Unit> {
        withTestResourceCleanup { cleanup ->
            val handles = mutableListOf<ControlledConnection>()
            val transport = IosLanDataTransport(
                context("observation-cancel"), IosEndpointRegistry(),
                connectionFactory = { connection, _ -> ControlledConnection(connection).also(handles::add) },
                outboundEndpointProvider = {
                    if (handles.size == 1) numericEndpoint() else throw CancellationException("observation cancelled")
                }
            )
            cleanup.own { transport.close() }
            val raw = transport.connect(peer())
            cleanup.own { raw.close() }
            val route = assertNotNull(assertIs<OutboundRouteConnection>(raw).outboundRoute)
            raw.close()
            assertFailsWith<CancellationException> { route.connect(500) }
            assertTrue(handles.last().cancelled)
            assertEquals(1, handles.last().retirementObservations)
        }
    }

    @Test
    fun stopAndRestartNeverReviveAnOldCapabilityOrAllocateNativeConnection() = runBlocking<Unit> {
        withTestResourceCleanup { cleanup ->
            var allocations = 0
            val transport = IosLanDataTransport(
                context("generation"), IosEndpointRegistry(), role = LanRole.DialOnly,
                connectionFactory = { connection, _ -> allocations++; ControlledConnection(connection) },
                outboundEndpointProvider = { numericEndpoint() }
            )
            cleanup.own { transport.close() }
            val raw = transport.connect(peer())
            cleanup.own { raw.close() }
            val route = assertNotNull(assertIs<OutboundRouteConnection>(raw).outboundRoute)
            raw.close()
            transport.stop()
            assertFalse(route.isCurrent)
            assertFailsWith<OutboundRouteUnavailable> { route.connect(500) }
            transport.start().getOrThrow()
            assertFalse(route.isCurrent)
            assertFailsWith<OutboundRouteUnavailable> { route.connect(500) }
            assertEquals(1, allocations)
        }
    }

    @Test
    fun missingReplayReadbackRequiresObservedNativeRetirementBeforeFallback() = runBlocking<Unit> {
        withTestResourceCleanup { cleanup ->
            val handles = mutableListOf<ControlledConnection>()
            val transport = IosLanDataTransport(
                context("readback"), IosEndpointRegistry(),
                connectionFactory = { connection, _ -> ControlledConnection(connection).also(handles::add) },
                outboundEndpointProvider = { if (handles.size == 1) numericEndpoint() else null }
            )
            cleanup.own { transport.close() }
            val raw = transport.connect(peer())
            cleanup.own { raw.close() }
            val route = assertNotNull(assertIs<OutboundRouteConnection>(raw).outboundRoute)
            raw.close()
            assertFailsWith<OutboundRouteUnavailable> { route.connect(500) }
            assertEquals(2, handles.size)
            assertTrue(handles.last().cancelled)
            assertEquals(1, handles.last().retirementObservations)
        }
    }

    @Test
    fun cancelRequestAloneNeverCertifiesFallbackAndFailedCloseRetainsItsCleanupOwner() = runBlocking<Unit> {
        val handles = mutableListOf<ControlledConnection>()
        val transport = IosLanDataTransport(
            context("retirement"), IosEndpointRegistry(),
            connectionFactory = { connection, _ ->
                ControlledConnection(connection, confirmedRetirement = handles.isEmpty()).also(handles::add)
            },
            outboundEndpointProvider = { if (handles.size == 1) numericEndpoint() else null }
        )
        try {
            transport.start().getOrThrow()
            assertNotNull(transport.tcpPort.value)
            val raw = transport.connect(peer())
            val route = assertNotNull(assertIs<OutboundRouteConnection>(raw).outboundRoute)
            raw.close()
            val failure = assertFailsWith<LanRouteRejected> { route.connect(500) }
            assertTrue(failure.suppressedExceptions.any { it is IllegalStateException })
            assertTrue(handles.last().cancelled)
            assertFalse(transport.start().isSuccess, "unconfirmed ownership must prevent restart")
            assertFailsWith<IllegalStateException> { transport.close() }
            assertNull(transport.tcpPort.value, "failed route cleanup must not orphan the live listener")
            assertNull(transport.listener)
            assertFalse(route.isCurrent)
            handles.last().confirmedRetirement = true
            transport.close() // Retry must still find the exact owner even after the first close latched closed.
            assertEquals(3, handles.last().retirementObservations)
        } finally {
            handles.forEach { it.confirmedRetirement = true }
            transport.close()
            handles.forEach { it.close() }
        }
    }

    @Test
    fun stopDuringPendingAdmissionOrFinalHandoffCannotPublishOldGeneration() = runBlocking<Unit> {
        for (beforeAdmission in listOf(true, false)) {
            withTestResourceCleanup { cleanup ->
                val handles = mutableListOf<ControlledConnection>()
                lateinit var transport: IosLanDataTransport
                transport = IosLanDataTransport(
                    context("handoff"), IosEndpointRegistry(),
                    connectionFactory = { connection, _ ->
                        ControlledConnection(connection).also { handle ->
                            handles += handle
                            if (handles.size == 2 && beforeAdmission) runBlocking { transport.stop() }
                        }
                    },
                    beforeDialOwnershipHandoffForTest = {
                        if (handles.size == 2 && !beforeAdmission) runBlocking { transport.stop() }
                    },
                    outboundEndpointProvider = { numericEndpoint() }
                )
                cleanup.own { transport.close() }
                val raw = transport.connect(peer())
                cleanup.own { raw.close() }
                val route = assertNotNull(assertIs<OutboundRouteConnection>(raw).outboundRoute)
                raw.close()
                assertFailsWith<OutboundRouteUnavailable> { route.connect(500) }
                assertFalse(route.isCurrent)
                assertTrue(handles.last().cancelled)
                assertEquals(2, handles.size)
            }
        }
    }

    @Test
    fun replayCancellationPropagatesAndRetiresItsNativeOwner() = runBlocking<Unit> {
        withTestResourceCleanup { cleanup ->
            val created = CompletableDeferred<ControlledConnection>()
            var count = 0
            val transport = IosLanDataTransport(
                context("cancellation"), IosEndpointRegistry(),
                connectionFactory = { connection, _ ->
                    count++
                    ControlledConnection(connection, connecting = count == 2).also {
                        if (count == 2) created.complete(it)
                    }
                },
                outboundEndpointProvider = { numericEndpoint() }
            )
            cleanup.own { transport.close() }
            val raw = transport.connect(peer())
            cleanup.own { raw.close() }
            val route = assertNotNull(assertIs<OutboundRouteConnection>(raw).outboundRoute)
            raw.close()
            val replay = async { route.connect(1_500) }
            cleanup.own { replay.cancel(); replay.join() }
            val handle = withTimeout(TEST_TIMEOUT_MILLIS) { created.await() }
            replay.cancel()
            withTimeout(TEST_TIMEOUT_MILLIS) { replay.join() }
            assertFailsWith<CancellationException> { replay.await() }
            assertTrue(handle.cancelled)
            assertEquals(1, handle.retirementObservations)
            assertEquals(2, count)
        }
    }

    private class ControlledConnection(
        private val native: nw_connection_t,
        var confirmedRetirement: Boolean = true,
        connecting: Boolean = false
    ) : IosConnectionHandle {
        private val mutableState = MutableStateFlow(
            if (connecting) ConnectionState.Connecting else ConnectionState.Connected
        )
        override val state: StateFlow<ConnectionState> = mutableState
        var cancelled = false
        var retirementObservations = 0
        override suspend fun write(bytes: ByteArray) = error("not used")
        override fun read(): Flow<ByteArray> = emptyFlow()
        override suspend fun close() = cancelNow("test cleanup")
        override fun cancelNow(reason: String) {
            if (cancelled) return
            cancelled = true
            mutableState.value = ConnectionState.Closed
            nw_connection_cancel(native)
        }
        override suspend fun awaitNativeRetirement(): Boolean {
            retirementObservations++
            return confirmedRetirement
        }
    }

    private fun context(id: String) = TransportContext(
        AppId("ios-outbound-route"), PeerId("route-$id"), id, Platform.IOS
    )

    private fun peer(id: String = "controlled") = InternalPeer(
        Peer(PeerId("route-$id"), "remote", Platform.IOS, setOf(TransportKind.LAN)),
        listOf(TransportHint(TransportKind.LAN, "127.0.0.1", 40_001))
    )

    private fun numericEndpoint() = LanTcpEndpoint(
        assertNotNull(LanNumericAddress.copyOf(byteArrayOf(127, 0, 0, 1))), 40_001
    )

    private companion object {
        const val TEST_TIMEOUT_MILLIS: Long = 10_000
    }
}
