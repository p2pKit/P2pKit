@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportHint
import dev.p2pkit.core.transport.TransportSecurityProfile
import kotlinx.cinterop.addressOf
import kotlinx.cinterop.convert
import kotlinx.cinterop.reinterpret
import kotlinx.cinterop.toKString
import kotlinx.cinterop.usePinned
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.NonCancellable
import kotlinx.coroutines.async
import kotlinx.coroutines.cancelAndJoin
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import platform.Network.nw_connection_cancel
import platform.Network.nw_connection_t
import platform.Network.nw_endpoint_create_bonjour_service
import platform.Network.nw_endpoint_get_bonjour_service_name
import platform.Network.nw_txt_record_create_with_bytes
import platform.Network.nw_txt_record_t
import platform.posix.uint8_tVar
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNotSame
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Real native endpoints/TXT at the production callback boundary, not live multicast evidence. */
class IosInvalidReresolutionTest {
    @Test
    fun missingTxtWithdrawsTheAdmittedService() = withProfiles {
        assertInvalidTransition { emitBytes(null) }
    }

    @Test
    fun malformedConsumedUtf8WithdrawsTheAdmittedService() = withProfiles {
        assertInvalidTransition { emit(properties() + ("name" to byteArrayOf(0xC3.toByte()))) }
    }

    @Test
    fun truncatedFramingWithdrawsTheAdmittedService() = withProfiles {
        assertInvalidTransition { emitBytes(bytes(properties()) + byteArrayOf(255.toByte())) }
    }

    @Test
    fun foreignAppWithdrawsTheAdmittedService() = withProfiles {
        assertInvalidTransition { emit(properties() + field("app", "other-app")) }
    }

    @Test
    fun missingPeerIdWithdrawsTheAdmittedService() = withProfiles {
        assertInvalidTransition { emit(properties() - "pid") }
    }

    @Test
    fun selfPeerIdWithdrawsTheAdmittedService() = withProfiles {
        assertInvalidTransition { emit(properties() + field("pid", context.localPeerId.value)) }
    }

    @Test
    fun blankNameWithdrawsTheAdmittedService() = withProfiles {
        assertInvalidTransition { emit(properties() + field("name", " ")) }
    }

    @Test
    fun mismatchedProtocolWithdrawsTheAdmittedServiceWithoutDowngrade() = withProfiles {
        val otherVersion = if (context.securityProfile == TransportSecurityProfile.AuthenticatedV2) "1" else "2"
        assertInvalidTransition { emit(properties() + field("pv", otherVersion)) }
    }

    @Test
    fun contradictoryFingerprintWithdrawsTheAdmittedService() = withProfiles {
        assertInvalidTransition {
            val invalid = if (context.securityProfile == TransportSecurityProfile.AuthenticatedV2) {
                properties() - "fp"
            } else {
                properties() + field("fp", "p2f1-" + "a".repeat(52))
            }
            emit(invalid)
        }
    }

    @Test
    fun foreignTxtIdentityWithdrawsOnlyItsNativeServiceNotAnotherPeer() = withProfiles {
        emit()
        val first = assertIs<PeerEvent.Found>(events.single())
        emit(properties() + field("pid", "other"), serviceName = "other")
        val other = assertIs<PeerEvent.Found>(events.last())
        val otherLease = assertNotNull(registry.lease(PeerId("other")))

        emit(properties() + field("pid", "other"))

        assertNull(discovery.announceEntryForTest(REMOTE.value))
        assertNull(registry.lease(REMOTE))
        assertSame(otherLease, registry.lease(PeerId("other")))
        assertEquals(listOf(first, other, PeerEvent.Lost(REMOTE)), events)
        assertEquals(listOf(other), lateEvents())
    }

    @Test
    fun invalidNeverAdmittedNativeServiceCannotWithdrawTxtNamedPeer() = withProfiles {
        emit()
        val admitted = events.toList()
        val lease = assertNotNull(registry.lease(REMOTE))

        emit(serviceName = "never-admitted")

        assertSame(lease, registry.lease(REMOTE))
        assertNotNull(discovery.announceEntryForTest(REMOTE.value))
        assertEquals(admitted, events)
    }

    @Test
    fun conformingUpdatePreservesFoundOwnershipAndReplacesEndpointLease() = withProfiles {
        emit()
        val first = assertIs<PeerEvent.Found>(events.single())
        val lease = assertNotNull(registry.lease(REMOTE))
        val name = "Remote \uFFFD 📱"
        emit(properties() + field("name", name) + ("name\u0000suffix" to byteArrayOf(0xFF.toByte())))

        val update = assertIs<PeerEvent.Updated>(events.last())
        assertEquals(name, update.peer.publicPeer.name)
        assertEquals(2, events.size)
        assertNotSame(lease, registry.lease(REMOTE))
        assertEquals(first.peer.authenticationHint, update.peer.authenticationHint)
        assertEquals(listOf(PeerEvent.Found(update.peer)), lateEvents())
        val lost = mutableListOf<String>()
        repeat(3) { discovery.reconcileAnnounceCacheAtomically(generation, 1, lost::add) }
        assertEquals(emptyList(), lost)
        assertNotNull(discovery.announceEntryForTest(REMOTE.value))
    }

    @Test
    fun retiredGenerationCannotWithdrawOrReplaceFreshOwnership() = withProfiles {
        emit()
        val retired = generation
        discovery.refresh()
        assertTrue(generation > retired)
        emit(properties() + field("name", "fresh"))
        val freshLease = assertNotNull(registry.lease(REMOTE))
        val expectedEvents = events.toList()

        emitBytes(null, callbackGeneration = retired)
        emit(properties() + field("name", "stale"), callbackGeneration = retired)

        assertSame(freshLease, registry.lease(REMOTE))
        assertEquals("fresh", discovery.announceEntryForTest(REMOTE.value)?.peer?.publicPeer?.name)
        assertEquals(expectedEvents, events)
    }

    @Test
    fun currentInvalidResolutionWithdrawsUnconfirmedPredecessorDuringGrace() = withProfiles {
        emit()
        val first = assertIs<PeerEvent.Found>(events.single())
        val predecessor = generation
        discovery.refresh()
        assertTrue(generation > predecessor)
        assertEquals(predecessor, discovery.announceEntryForTest(REMOTE.value)?.lastConfirmedGeneration)
        assertNull(registry.lease(REMOTE), "refresh must already retire the old opaque endpoint")

        emitBytes(null)

        assertNull(discovery.announceEntryForTest(REMOTE.value))
        assertEquals(listOf(first, PeerEvent.Lost(REMOTE)), events)
        assertEquals(emptyList(), lateEvents())
    }

    @Test
    fun callbackFromRetiredBrowserCannotMutateCacheDuringRebindGap() = withProfiles {
        emit()
        val admitted = assertNotNull(discovery.announceEntryForTest(REMOTE.value))
        val expectedEvents = events.toList()
        discovery.beforeListenerRebindForTest()
        assertFalse(discovery.hasBrowserForTest)

        emitBytes(null)
        emit(properties() + field("name", "retired"))

        assertSame(admitted, discovery.announceEntryForTest(REMOTE.value))
        assertNull(registry.lease(REMOTE))
        assertEquals(expectedEvents, events)
    }

    @Test
    fun invalidResolutionReleasesOnlyItsSlotInTheBoundedCache() = withProfiles {
        emit()
        repeat(MAX_TRACKED_LAN_PEERS - 1) { index ->
            emit(properties() + field("pid", "peer-$index"), serviceName = "peer-$index")
        }
        emit(properties() + field("pid", "overflow"), serviceName = "overflow")
        assertNull(discovery.announceEntryForTest("overflow"))
        assertNull(registry.lease(PeerId("overflow")))
        assertEquals(MAX_TRACKED_LAN_PEERS, events.size)

        emitBytes(null)

        assertEquals(MAX_TRACKED_LAN_PEERS - 1, registry.sizeForTest())
        assertEquals(PeerEvent.Lost(REMOTE), events.last())
        emit(properties() + field("pid", "overflow"), serviceName = "overflow")
        assertEquals(PeerId("overflow"), assertIs<PeerEvent.Found>(events.last()).peer.publicPeer.id)
        assertNotNull(discovery.announceEntryForTest("overflow"))
        assertEquals(MAX_TRACKED_LAN_PEERS, registry.sizeForTest())
    }

    @Test
    fun withdrawingDiscoveredRouteDoesNotRemoveExplicitManualHints() = withProfiles {
        emit()
        val peer = assertIs<PeerEvent.Found>(events.single()).peer
        val manual = peer.copy(transportHints = listOf(TransportHint(TransportKind.LAN, "127.0.0.1", 43001)))

        emitBytes(null)

        assertFalse(data.canConnect(peer))
        assertTrue(data.canConnect(manual))
        assertNull(registry.lease(REMOTE))
    }

    @Test
    fun pendingDialKeepsItsOwnershipAndOldFailureCannotDeleteRecoveredEndpoint() = withProfiles {
        emit()
        val peer = assertIs<PeerEvent.Found>(events.single()).peer
        coroutineScope {
            val dial = async(start = CoroutineStart.UNDISPATCHED) { runCatching { data.connect(peer) } }
            val connection = connections.single()

            emitBytes(null)

            assertFalse(connection.cancelled, "discovery does not own an already started dial")
            assertFalse(data.canConnect(peer))
            assertIs<P2pError.NoTransportAvailable>(runCatching { data.connect(peer) }.exceptionOrNull())
            assertEquals(1, connections.size, "a new dial cannot reuse withdrawn registry ownership")
            emit(properties() + field("name", "recovered"))
            val replacement = assertNotNull(registry.lease(REMOTE))
            connection.fail()

            assertIs<P2pError.ConnectionFailed>(dial.await().exceptionOrNull())
            assertTrue(connection.cancelled)
            assertSame(replacement, registry.lease(REMOTE))
            assertEquals("recovered", discovery.announceEntryForTest(REMOTE.value)?.peer?.publicPeer?.name)
        }
    }

    @Test
    fun pendingDialCanCompleteAfterWithdrawalWithoutRecreatingDiscovery() = withProfiles {
        emit()
        val peer = assertIs<PeerEvent.Found>(events.single()).peer
        coroutineScope {
            val dial = async(start = CoroutineStart.UNDISPATCHED) { data.connect(peer) }
            val connection = connections.single()

            emitBytes(null)
            connection.succeed()

            val handedOff = dial.await()
            try {
                assertSame(connection, handedOff)
                assertFalse(connection.cancelled)
                assertNull(registry.lease(REMOTE))
                assertNull(discovery.announceEntryForTest(REMOTE.value))
                assertEquals(emptyList(), lateEvents())
            } finally {
                handedOff.close()
            }
            assertTrue(connection.cancelled)
        }
    }

    @Test
    fun stopClearsOwnershipAndQueuedCallbacksCannotResurrectIt() = withProfiles {
        emit()
        val first = assertIs<PeerEvent.Found>(events.single())
        val retired = generation

        discovery.stopDiscovery()
        emit(callbackGeneration = retired)
        emitBytes(null, callbackGeneration = retired)

        assertNull(discovery.announceEntryForTest(REMOTE.value))
        assertNull(registry.lease(REMOTE))
        assertEquals(listOf(first, PeerEvent.Lost(REMOTE)), events)
        assertEquals(emptyList(), lateEvents())
        discovery.startDiscovery()
        emit()
        assertIs<PeerEvent.Found>(events.last())
        assertEquals(3, events.size)
    }

    private class Fixture(profile: TransportSecurityProfile) {
        val context = TransportContext(
            appId = AppId("lan-txt-test"),
            localPeerId = PeerId("local"),
            deviceName = "Observer",
            platform = Platform.IOS,
            securityProfile = profile
        )
        val registry = IosEndpointRegistry()
        val connections = mutableListOf<ControlledConnection>()
        val data = IosLanDataTransport(
            context,
            registry,
            connectionFactory = { native, _ -> ControlledConnection(native).also { connections += it } }
        )
        val discovery = IosLanDiscoveryTransport(context, registry, data)
        val events = mutableListOf<PeerEvent>()
        val generation: Int get() = discovery.browserGenerationForTest

        fun properties(): Map<String, ByteArray?> = LanTxtRecordFixtures.properties(context.securityProfile)

        fun bytes(properties: Map<String, ByteArray?>): ByteArray = LanTxtRecordFixtures.encode(properties.toList())

        fun emit(
            properties: Map<String, ByteArray?> = properties(),
            serviceName: String = REMOTE.value,
            callbackGeneration: Int = generation
        ) = emitBytes(bytes(properties), serviceName, callbackGeneration)

        fun emitBytes(
            bytes: ByteArray?,
            serviceName: String = REMOTE.value,
            callbackGeneration: Int = generation
        ) {
            val endpoint = assertNotNull(
                nw_endpoint_create_bonjour_service(serviceName, context.lanServiceTypeBonjour, "local.")
            )
            val txt: nw_txt_record_t = bytes?.usePinned { pinned ->
                assertNotNull(
                    nw_txt_record_create_with_bytes(
                        if (bytes.isEmpty()) null else pinned.addressOf(0).reinterpret<uint8_tVar>(),
                        bytes.size.convert()
                    )
                )
            }
            discovery.emitResolvedPeer(endpoint, txt, isUpdate = true, generation = callbackGeneration)
        }

        suspend fun lateEvents(): List<PeerEvent> = coroutineScope {
            val snapshot = mutableListOf<PeerEvent>()
            // Initial StateFlow snapshot is delivered synchronously; no timing-based absence assertion.
            val collector = launch(Dispatchers.Unconfined, start = CoroutineStart.UNDISPATCHED) {
                discovery.events.collect { snapshot += it }
            }
            try {
                snapshot.toList()
            } finally {
                collector.cancelAndJoin()
            }
        }

        suspend fun assertInvalidTransition(invalidate: Fixture.() -> Unit) {
            emit()
            val first = assertIs<PeerEvent.Found>(events.single())
            val lease = assertNotNull(registry.lease(REMOTE))
            assertNotNull(discovery.announceEntryForTest(REMOTE.value))
            assertTrue(data.canConnect(first.peer))

            invalidate()

            assertNull(
                discovery.announceEntryForTest(REMOTE.value),
                "invalid re-resolution must revoke cached ownership"
            )
            assertNull(registry.lease(REMOTE), "future dials must not reuse the invalidated endpoint")
            assertFalse(data.canConnect(first.peer))
            assertEquals(listOf(first, PeerEvent.Lost(REMOTE)), events)
            assertEquals(emptyList(), lateEvents())
            repeat(3) { invalidate() }
            assertEquals(listOf(first, PeerEvent.Lost(REMOTE)), events, "withdrawal must be idempotent")
            val lost = mutableListOf<String>()
            repeat(3) { discovery.reconcileAnnounceCacheAtomically(generation, 1, lost::add) }
            assertEquals(emptyList(), lost, "reconciliation must not retain or re-emit the rejected peer")

            // A native object already leased to a dial stays owned by that dial, not by the cache.
            assertEquals(REMOTE.value, nw_endpoint_get_bonjour_service_name(lease.endpoint)?.toKString())
            emit()
            val recovered = assertIs<PeerEvent.Found>(events.last())
            assertEquals(3, events.size)
            val freshLease = assertNotNull(registry.lease(REMOTE))
            assertNotSame(lease, freshLease)
            assertFalse(registry.removeIfCurrent(REMOTE, lease), "an old dial must not delete recovered ownership")
            assertSame(freshLease, registry.lease(REMOTE))
            assertEquals(listOf(recovered), lateEvents())
        }
    }

    /** Real unstarted NWConnection ownership, with deterministic state instead of an external TCP peer. */
    private class ControlledConnection(private val native: nw_connection_t) : IosConnectionHandle {
        private val mutableState = MutableStateFlow(ConnectionState.Connecting)
        override val state: StateFlow<ConnectionState> = mutableState
        var cancelled: Boolean = false
            private set

        override suspend fun write(bytes: ByteArray): Unit = error("not used")
        override fun read(): Flow<ByteArray> = emptyFlow()
        override suspend fun close() = cancelNow("test cleanup")

        override fun cancelNow(reason: String) {
            if (cancelled) return
            cancelled = true
            mutableState.value = ConnectionState.Closed
            nw_connection_cancel(native)
        }

        fun fail() { mutableState.value = ConnectionState.Closed }
        fun succeed() { mutableState.value = ConnectionState.Connected }
    }

    private fun withProfiles(block: suspend Fixture.() -> Unit) = runBlocking<Unit> {
        for (profile in TransportSecurityProfile.entries) {
            val fixture = Fixture(profile)
            val collector = launch(Dispatchers.Unconfined, start = CoroutineStart.UNDISPATCHED) {
                fixture.discovery.events.collect { fixture.events += it }
            }
            try {
                withTimeout(TEST_TIMEOUT_MILLIS) {
                    fixture.discovery.startDiscovery()
                    assertTrue(fixture.discovery.hasBrowserForTest)
                    fixture.block()
                }
            } finally {
                withContext(NonCancellable) {
                    collector.cancelAndJoin()
                    try {
                        fixture.discovery.stopDiscovery()
                    } finally {
                        try {
                            fixture.data.close()
                        } finally {
                            fixture.connections.forEach { it.cancelNow("test finalizer") }
                        }
                    }
                }
            }
        }
    }

    private companion object {
        val REMOTE: PeerId = PeerId("remote")
        const val TEST_TIMEOUT_MILLIS: Long = 5_000

        fun field(key: String, value: String): Pair<String, ByteArray?> = key to value.encodeToByteArray()
    }
}
