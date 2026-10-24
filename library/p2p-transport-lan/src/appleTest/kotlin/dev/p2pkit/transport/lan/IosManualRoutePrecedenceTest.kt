@file:OptIn(kotlinx.cinterop.ExperimentalForeignApi::class)

package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.ConnectionState
import dev.p2pkit.core.P2pError
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerFingerprint
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.PeerAuthenticationHint
import dev.p2pkit.core.transport.PeerOrigin
import dev.p2pkit.core.transport.TransportContext
import dev.p2pkit.core.transport.TransportHint
import dev.p2pkit.core.transport.TransportSecurityProfile
import kotlinx.cinterop.toKString
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.emptyFlow
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withTimeout
import platform.Network.nw_connection_cancel
import platform.Network.nw_connection_copy_endpoint
import platform.Network.nw_connection_t
import platform.Network.nw_endpoint_create_bonjour_service
import platform.Network.nw_endpoint_get_bonjour_service_name
import platform.Network.nw_endpoint_get_hostname
import platform.Network.nw_endpoint_get_port
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/**
 * Native endpoint selection with controlled connection states, not live
 * multicast, TCP or Noise. Core registration/handshake tests separately enforce
 * manual provenance and the full pin. #120 automatic admission remains open.
 */
class IosManualRoutePrecedenceTest {
    @Test
    fun copiedPeerIdInFullBonjourCacheCannotShadowPinnedManualLanEndpoint() = runBlocking<Unit> {
        checkRoute(manualPeer(), ExpectedRoute.HostHint, fillCache = true)
    }

    @Test
    fun failedManualDialDoesNotInvalidateBonjourOwnership() = runBlocking<Unit> {
        checkRoute(manualPeer(), ExpectedRoute.HostHint, failDial = true)
    }

    @Test
    fun legacyManualLanEndpointAlsoPrecedesBonjour() = runBlocking<Unit> {
        checkRoute(
            manualPeer().copy(authenticationHint = null),
            ExpectedRoute.HostHint,
            profile = TransportSecurityProfile.LegacyPlaintextV1
        )
    }

    @Test
    fun advertisedFingerprintAndHostDoNotOverrideBonjourLease() = runBlocking<Unit> {
        checkRoute(
            manualPeer().copy(
                origin = PeerOrigin.Discovered,
                authenticationHint = PeerAuthenticationHint.UntrustedDiscoveryClaim(PIN)
            ),
            ExpectedRoute.Bonjour
        )
    }

    @Test
    fun failedDiscoveredDialStillInvalidatesOnlyItsUsedLease() = runBlocking<Unit> {
        checkRoute(
            manualPeer().copy(origin = PeerOrigin.Discovered),
            ExpectedRoute.Bonjour,
            failDial = true
        )
    }

    @Test
    fun manualRegistrationForAnotherTransportDoesNotPromoteALanDiscoveryHint() = runBlocking<Unit> {
        checkRoute(
            manualPeer().copy(
                transportHints = listOf(TransportHint(TransportKind.BLE, host = "manual-ble", port = 9), HOST_HINT)
            ),
            ExpectedRoute.Bonjour
        )
    }

    @Test
    fun invalidManualHintsDoNotSuppressAnExistingBonjourLease() = runBlocking<Unit> {
        invalidHints().forEach { hint ->
            checkRoute(manualPeer().copy(transportHints = listOf(hint)), ExpectedRoute.Bonjour)
        }
    }

    @Test
    fun invalidHostHintsWithoutALeaseCannotStartANativeConnection() = runBlocking<Unit> {
        withTestResourceCleanup { cleanup ->
            val transport = IosLanDataTransport(
                transportContext = context(TransportSecurityProfile.AuthenticatedV2),
                endpointRegistry = IosEndpointRegistry(),
                connectionFactory = { _, _ -> error("invalid host/port must be rejected before native dialing") }
            )
            cleanup.own { transport.close() }
            invalidHints().forEach { hint ->
                assertFailsWith<P2pError.NoTransportAvailable> {
                    withTimeout(TEST_TIMEOUT_MILLIS) {
                        transport.connect(manualPeer().copy(transportHints = listOf(hint)))
                    }
                }
            }
        }
    }

    private enum class ExpectedRoute { HostHint, Bonjour }

    private suspend fun checkRoute(
        peer: InternalPeer,
        expected: ExpectedRoute,
        fillCache: Boolean = false,
        failDial: Boolean = false,
        profile: TransportSecurityProfile = TransportSecurityProfile.AuthenticatedV2
    ) = withTestResourceCleanup { cleanup ->
        val registry = IosEndpointRegistry()
        val claimedEndpoint = assertNotNull(nw_endpoint_create_bonjour_service(
            peer.publicPeer.id.value,
            LanConstants.serviceTypeBonjour(profile),
            "local."
        ))
        val cachedLease = assertNotNull(registry.put(peer.publicPeer.id, claimedEndpoint, browserGeneration = 1))
        if (fillCache) {
            repeat(MAX_TRACKED_LAN_PEERS - 1) { index ->
                assertNotNull(registry.put(PeerId("occupant-$index"), claimedEndpoint, browserGeneration = 1))
            }
            assertNull(registry.put(PeerId("overflow"), claimedEndpoint, browserGeneration = 1))
        }
        var wrapped: ControlledConnection? = null
        val transport = IosLanDataTransport(
            transportContext = context(profile),
            endpointRegistry = registry,
            connectionFactory = { connection, _ ->
                val endpoint = assertNotNull(nw_connection_copy_endpoint(connection))
                when (expected) {
                    ExpectedRoute.HostHint -> {
                        assertEquals(HOST_HINT.host, nw_endpoint_get_hostname(endpoint)?.toKString())
                        assertEquals(HOST_HINT.port, nw_endpoint_get_port(endpoint).toInt())
                        assertNull(nw_endpoint_get_bonjour_service_name(endpoint))
                    }
                    ExpectedRoute.Bonjour -> {
                        assertEquals(
                            peer.publicPeer.id.value,
                            nw_endpoint_get_bonjour_service_name(endpoint)?.toKString()
                        )
                    }
                }
                ControlledConnection(connection, failDial).also { handle ->
                    wrapped = handle
                    cleanup.own { handle.close() }
                }
            }
        )
        cleanup.own { transport.close() }
        assertTrue(transport.canConnect(peer))
        if (failDial) {
            assertFailsWith<P2pError.ConnectionFailed> {
                withTimeout(TEST_TIMEOUT_MILLIS) { transport.connect(peer) }
            }
            assertTrue(assertNotNull(wrapped).cancelled)
        } else {
            val connection = withTimeout(TEST_TIMEOUT_MILLIS) { transport.connect(peer) }
            assertSame(assertNotNull(wrapped), connection)
        }
        if (failDial && expected == ExpectedRoute.Bonjour) {
            assertNull(registry.lease(peer.publicPeer.id))
            assertEquals(0, registry.sizeForTest())
        } else {
            assertSame(cachedLease, registry.lease(peer.publicPeer.id))
            assertEquals(if (fillCache) MAX_TRACKED_LAN_PEERS else 1, registry.sizeForTest())
        }
    }

    private class ControlledConnection(
        private val native: nw_connection_t,
        fail: Boolean
    ) : IosConnectionHandle {
        private val mutableState = MutableStateFlow(if (fail) ConnectionState.Closed else ConnectionState.Connected)
        override val state: StateFlow<ConnectionState> = mutableState
        var cancelled: Boolean = false
            private set

        override suspend fun write(bytes: ByteArray) = error("not used")
        override fun read(): Flow<ByteArray> = emptyFlow()
        override suspend fun close() = cancelNow("test cleanup")

        override fun cancelNow(reason: String) {
            if (cancelled) return
            cancelled = true
            mutableState.value = ConnectionState.Closed
            nw_connection_cancel(native)
        }
    }

    private fun manualPeer() = InternalPeer(
        publicPeer = Peer(PeerId("manual-route-peer"), "manual", Platform.UNKNOWN, setOf(TransportKind.LAN)),
        // Mirrors PeerRegistry: one local manual contribution first, followed
        // by discovery hints. The cached Bonjour endpoint is keyed by its id.
        transportHints = listOf(HOST_HINT, TransportHint(TransportKind.LAN, port = 44_002)),
        origin = PeerOrigin.Manual,
        authenticationHint = PeerAuthenticationHint.TrustedApplicationPin(PIN)
    )

    private fun context(profile: TransportSecurityProfile) = TransportContext(
        appId = AppId("ios-manual-route-precedence"),
        localPeerId = PeerId("ios-manual-route-local"),
        deviceName = "local",
        platform = Platform.IOS,
        securityProfile = profile
    )

    private fun invalidHints() = listOf(
        HOST_HINT.copy(host = null),
        HOST_HINT.copy(host = " "),
        HOST_HINT.copy(port = null),
        HOST_HINT.copy(port = 0),
        HOST_HINT.copy(port = 65_536)
    )

    private companion object {
        val PIN: PeerFingerprint = PeerFingerprint("p2f1-${"a".repeat(52)}")
        val HOST_HINT: TransportHint = TransportHint(TransportKind.LAN, host = "127.0.0.1", port = 44_001)
        const val TEST_TIMEOUT_MILLIS: Long = 5_000
    }
}
