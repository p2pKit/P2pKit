package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.Peer
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.OutboundRouteConnection
import dev.p2pkit.core.transport.OutboundRouteUnavailable
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.core.transport.TransportHint
import java.net.Inet6Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.Socket
import java.net.SocketAddress
import kotlinx.coroutines.runBlocking
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFailsWith
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertNull
import kotlin.test.assertTrue

class AndroidOutboundRouteContextTest {
    @Test
    fun replayPreservesExplicitHotspotBindingInsteadOfFallingBackToDefaultRoute() = runBlocking<Unit> {
        val selected = target(1)
        val state = AndroidLanNetworkState { error("selected route must not consult a default network") }
        state.select(selected)
        val original = BoundSocket()
        val replay = BoundSocket()
        val sockets = ArrayDeque(listOf(original, replay))
        val transport = transport(state) { assertNull(it); sockets.removeFirst() }
        var fresh: RawConnection? = null
        try {
            val raw = transport.connect(peer())
            val route = assertNotNull(assertIs<OutboundRouteConnection>(raw).outboundRoute)
            raw.close()
            fresh = route.connect(900)
            assertEquals(selected.address, original.bound?.address)
            assertEquals(selected.address, replay.bound?.address)
            assertEquals(0, replay.bound?.port)
            assertTrue(replay.boundBeforeConnect)
            assertEquals(original.destination, replay.destination)
            assertTrue(sockets.isEmpty())
        } finally {
            fresh?.close()
            transport.close()
            original.close()
            replay.close()
        }
    }

    @Test
    fun changedFreshFingerprintRefusesBeforeAllocationAndCannotReviveThroughAba() = runBlocking<Unit> {
        val first = target(1)
        var current = first
        var resolutions = 0
        val state = AndroidLanNetworkState(requireFresh = true) { resolutions++; current }
        var allocations = 0
        val socket = BoundSocket()
        val transport = transport(state) { allocations++; socket }
        try {
            val raw = transport.connect(peer())
            val route = assertNotNull(assertIs<OutboundRouteConnection>(raw).outboundRoute)
            raw.close()
            assertEquals(1, resolutions, "optional capture must not add an ordinary route lookup")
            current = first.copy(fingerprint = "new-network-context")
            assertFailsWith<OutboundRouteUnavailable> { route.connect(500) }
            assertFalse(route.isCurrent)
            current = first
            assertFailsWith<OutboundRouteUnavailable> { route.connect(500) }
            assertEquals(1, allocations, "neither changed nor ABA context may create a socket")
            assertEquals(2, resolutions)
        } finally {
            transport.close()
            socket.close()
        }
    }

    @Test
    fun discoveryClearAndRepublishOfIdenticalRouteStillRetiresToken() = runBlocking<Unit> {
        val selected = target(1)
        val state = AndroidLanNetworkState { selected }.apply { select(selected) }
        var allocations = 0
        val socket = BoundSocket()
        val transport = transport(state) { allocations++; socket }
        try {
            val raw = transport.connect(peer())
            val route = assertNotNull(assertIs<OutboundRouteConnection>(raw).outboundRoute)
            raw.close()
            state.clear()
            state.select(selected)
            assertFalse(route.isCurrent)
            assertFailsWith<OutboundRouteUnavailable> { route.connect(500) }
            assertEquals(1, allocations)
        } finally {
            transport.close()
            socket.close()
        }
    }

    @Test
    fun networkContextChangeDuringReplayRetiresSocketRatherThanUsingNewRoute() = runBlocking<Unit> {
        val state = AndroidLanNetworkState().apply { select(target(1)) }
        val original = BoundSocket()
        val replay = BoundSocket { state.select(target(2)) }
        val sockets = ArrayDeque(listOf(original, replay))
        val transport = transport(state) { sockets.removeFirst() }
        try {
            val raw = transport.connect(peer())
            val route = assertNotNull(assertIs<OutboundRouteConnection>(raw).outboundRoute)
            raw.close()
            assertFailsWith<OutboundRouteUnavailable> { route.connect(500) }
            assertTrue(replay.isClosed)
            assertEquals(target(1).address, replay.bound?.address)
            assertFalse(route.isCurrent)
            assertTrue(sockets.isEmpty())
        } finally {
            transport.close()
            original.close()
            replay.close()
        }
    }

    @Test
    fun revisionDistinguishesIpv6ScopesEvenWhenJavaAddressEqualityDoesNot() {
        val bytes = ByteArray(16).also { it[0] = 0xfe.toByte(); it[1] = 0x80.toByte(); it[15] = 1 }
        val first = target(1).copy(address = Inet6Address.getByAddress(null, bytes, 7))
        val otherScope = first.copy(address = Inet6Address.getByAddress(null, bytes, 8))
        assertEquals(first.address, otherScope.address, "fixture exercises Java's scope-insensitive equality")
        val state = AndroidLanNetworkState().apply { select(first) }
        val revision = assertNotNull(state.selectedRoute()).revision
        state.select(otherScope)
        assertTrue(state.routeRevision > revision)
        state.select(first)
        assertTrue(state.routeRevision > revision)
    }

    private class BoundSocket(private val onConnect: () -> Unit = {}) : Socket() {
        var bound: InetSocketAddress? = null
        var destination: InetSocketAddress? = null
        var boundBeforeConnect = false
        override fun bind(bindpoint: SocketAddress?) { bound = bindpoint as InetSocketAddress }
        override fun connect(endpoint: SocketAddress?, timeout: Int) {
            boundBeforeConnect = bound != null
            destination = endpoint as InetSocketAddress
            onConnect()
        }
        override fun setTcpNoDelay(on: Boolean) = Unit
        override fun getLocalSocketAddress(): SocketAddress? = bound
        override fun getRemoteSocketAddress(): SocketAddress? = destination
    }

    private fun transport(state: AndroidLanNetworkState, factory: (android.net.Network?) -> Socket) =
        AndroidLanDataTransport(
            LanServiceRegistration(AppId("route-context"), PeerId("route-local"), "local", Platform.ANDROID),
            networkState = state, socketFactory = factory
        )

    private fun target(lastOctet: Int) = AndroidLanBindTarget(
        null, "softap0", InetAddress.getByAddress(byteArrayOf(192.toByte(), 168.toByte(), 43, lastOctet.toByte())),
        emptyList(), "hotspot-context-$lastOctet"
    )

    private fun peer() = InternalPeer(
        Peer(PeerId("route-peer"), "remote", Platform.ANDROID, setOf(TransportKind.LAN)),
        listOf(TransportHint(TransportKind.LAN, "192.168.43.20", 40_001))
    )
}
