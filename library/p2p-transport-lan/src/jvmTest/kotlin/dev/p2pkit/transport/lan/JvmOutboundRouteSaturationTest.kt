package dev.p2pkit.transport.lan

import dev.p2pkit.core.AppId
import dev.p2pkit.core.PeerId
import dev.p2pkit.core.Platform
import dev.p2pkit.core.TransportKind
import dev.p2pkit.core.transport.InternalPeer
import dev.p2pkit.core.transport.OutboundRouteConnection
import dev.p2pkit.core.transport.PeerEvent
import dev.p2pkit.core.transport.RawConnection
import dev.p2pkit.transport.lan.internal.jmdns.ServiceInfo
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.take
import kotlinx.coroutines.flow.toList
import kotlinx.coroutines.runBlocking
import kotlinx.coroutines.withContext
import kotlinx.coroutines.withTimeout
import kotlin.test.Test
import kotlin.test.assertEquals
import kotlin.test.assertFalse
import kotlin.test.assertIs
import kotlin.test.assertNotNull
import kotlin.test.assertSame
import kotlin.test.assertTrue

/** Actual admission/relay bounds through callback delivery; real TCP, not multicast or authentication evidence. */
class JvmOutboundRouteSaturationTest {
    @Test
    fun realTcpRouteReplaysWhileDiscoveryAdmissionsAndRelayRejectTargetAtCapacity() = runBlocking<Unit> {
        val loopback = InetAddress.getByAddress(byteArrayOf(127, 0, 0, 1))
        val listener = ServerSocket(0, 8, loopback).apply { soTimeout = 5_000 }
        val registration = LanServiceRegistration(
            AppId("route-saturation"), PeerId("route-local"), "Local", Platform.JVM_DESKTOP
        )
        val backend = JvmDeterministicDiscoveryTestBackend { emptyList() }
        val discovery = JvmLanDiscoveryTransport(registration, backend)
        val sockets = mutableListOf<Socket>()
        val transport = JvmLanDataTransport(registration, socketFactory = { Socket().also(sockets::add) })
        val targetId = PeerId("a-route-target")
        val occupantIds = (0 until MAX_TRACKED_LAN_PEERS).map { PeerId("z-occupant-$it") }.toSet()
        var original: RawConnection? = null
        var replay: RawConnection? = null
        var accepted: Socket? = null
        try {
            discovery.startDiscovery()
            backend.advertise(advertisement(registration, targetId, loopback, listener.localPort))
            val target = assertIs<PeerEvent.Found>(withTimeout(5_000) { discovery.events.first() }).peer
            assertEquals(targetId, target.publicPeer.id)
            original = transport.connect(target)
            accepted = withContext(Dispatchers.IO) { listener.accept().apply { soTimeout = 5_000 } }
            val route = assertNotNull(assertIs<OutboundRouteConnection>(original).outboundRoute)
            original.write(byteArrayOf(37))
            assertEquals(37, withContext(Dispatchers.IO) { assertNotNull(accepted).getInputStream().read() })
            original.close()
            accepted.close()

            backend.withdraw(targetId.value)
            occupantIds.forEach { id ->
                backend.advertise(advertisement(registration, id, loopback, listener.localPort))
            }
            // A different but valid replacement is refused upstream, not merely ignored by a fake route.
            val replacementAddress = InetAddress.getByAddress(byteArrayOf(127, 0, 0, 2))
            backend.advertise(advertisement(registration, targetId, replacementAddress, 1))
            assertEquals(occupantIds, snapshot(discovery).map { it.publicPeer.id }.toSet())
            assertTrue(route.isCurrent)

            replay = route.connect(1_500)
            accepted = withContext(Dispatchers.IO) { listener.accept().apply { soTimeout = 5_000 } }
            replay.write(byteArrayOf(42))
            assertEquals(42, withContext(Dispatchers.IO) { assertNotNull(accepted).getInputStream().read() })
            assertSame(route, assertIs<OutboundRouteConnection>(replay).outboundRoute)
            assertEquals(2, sockets.size)
            assertTrue(sockets.first().isClosed)
            assertEquals(loopback, sockets.last().inetAddress)
            assertEquals(listener.localPort, sockets.last().port)
            assertEquals(occupantIds, snapshot(discovery).map { it.publicPeer.id }.toSet())

            // Freeing one actual admission proves the earlier replacement was eligible but capacity-blocked.
            backend.withdraw(occupantIds.first().value)
            backend.refresh(registration.localPeerId)
            val afterCapacityFreed = snapshot(discovery)
            val replacement = afterCapacityFreed.single { it.publicPeer.id == targetId }
            assertEquals("127.0.0.2", replacement.transportHints.single().host)
            assertEquals(1, replacement.transportHints.single().port)
            assertFalse(afterCapacityFreed.any { it.publicPeer.id == occupantIds.first() })
        } finally {
            try {
                discovery.stopDiscovery()
            } finally {
                original?.close()
                replay?.close()
                accepted?.close()
                listener.close()
                transport.close()
                sockets.forEach(Socket::close)
            }
        }
    }

    private suspend fun snapshot(discovery: JvmLanDiscoveryTransport): List<InternalPeer> = withTimeout(5_000) {
        discovery.events.take(MAX_TRACKED_LAN_PEERS).toList().map { assertIs<PeerEvent.Found>(it).peer }
    }

    private fun advertisement(
        registration: LanServiceRegistration,
        peerId: PeerId,
        address: InetAddress,
        port: Int
    ) = JvmTestDiscoveryAdvertisement(
        instanceName = peerId.value,
        info = ServiceInfo.create(
            registration.serviceTypeJmdns, peerId.value, port, 0, 0,
            buildLanTxtProperties(
                peerId, registration.appId, "Remote", Platform.JVM_DESKTOP, setOf(TransportKind.LAN),
                registration.protocolVersion, registration.fingerprint
            )
        ),
        candidates = listOf(address)
    )
}
